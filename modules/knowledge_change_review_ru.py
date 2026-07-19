"""Knowledge Review Layer — v6.84.5.1e9b.

Deterministically binds one e9a KnowledgeChangeProposal to its exact
ValidationResult, verifies caller-supplied in-memory target snapshots, performs
bounded operation-specific conflict analysis, and returns an immutable review
artifact. The module has no write, approval, publication, persistence, model,
network, subprocess, shell, browser, Tauri, or frontend path.

Contract: localcomet.knowledge-change-review/1.0
Lifecycle: proposal -> exact validation binding -> review artifact -> hard stop
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import difflib
import hashlib
import json
from pathlib import PurePosixPath, PureWindowsPath
import re
from types import MappingProxyType
from typing import Any, Final, Mapping, Sequence

from modules.knowledge_change_proposal_ru import (
    KnowledgeChangeProposal,
    ProposalOperation,
    ProposalValidator,
    ProposedNoteContent,
    ValidationOutcome,
    ValidationResult,
    compute_proposal_content_hash,
    compute_proposal_instance_id,
    create_proposal_from_untrusted,
)


CONTRACT_VERSION: Final[str] = "localcomet.knowledge-change-review/1.0"
SEMANTIC_NORMALIZATION_VERSION: Final[str] = "semantic-normalization/v1"
IDENTITY_VERSION: Final[str] = "1.0"
CHANGE_ID_PREFIX: Final[str] = "kchange:"
REVIEW_ID_PREFIX: Final[str] = "kreview:"
TRUNCATION_MARKER: Final[str] = "... REVIEW_DIFF_PREVIEW_TRUNCATED ..."

MAX_SOURCE_BYTES: Final[int] = 1_048_576
MAX_TRUSTED_TEXT_CHARS: Final[int] = 1_048_576
MAX_PROPOSED_CONTENT_BYTES: Final[int] = 1_048_576
MAX_STABLE_IDS: Final[int] = 4_096
MAX_EVIDENCE_REFERENCES: Final[int] = 32
MAX_PROVENANCE_ENTRIES: Final[int] = 128
MAX_FINDINGS: Final[int] = 16
MAX_FINDING_MESSAGE_CHARS: Final[int] = 1_024
MAX_FINDING_DETAIL_ITEMS: Final[int] = 16
MAX_FINDING_DETAIL_CHARS: Final[int] = 512
MAX_FULL_DIFF_BYTES: Final[int] = 4_194_304
MAX_PREVIEW_BYTES: Final[int] = 32_768
MAX_PREVIEW_LINES: Final[int] = 400
MAX_PATH_LENGTH: Final[int] = 512
MAX_STABLE_ID_LENGTH: Final[int] = 128
MAX_PROPOSED_SNAPSHOT_BYTES: Final[int] = 1_048_576
MAX_METADATA_PREVIEW_VALUE_BYTES: Final[int] = 1_024
MAX_VALIDATION_SNAPSHOT_DEPTH: Final[int] = 24
MAX_VALIDATION_SNAPSHOT_NODES: Final[int] = 4_096
MAX_VALIDATION_MAPPING_ENTRIES: Final[int] = 256
MAX_VALIDATION_SEQUENCE_ENTRIES: Final[int] = 256
MAX_VALIDATION_KEY_LENGTH: Final[int] = 256
MAX_VALIDATION_STRING_LENGTH: Final[int] = 8_192

_SHA256_VALUE_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REVISION_RE = _SHA256_VALUE_RE
_STABLE_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


class ReviewStatus(str, Enum):
    CLEAR = "CLEAR"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ConflictSeverity(str, Enum):
    BLOCKING = "BLOCKING"
    REVIEW = "REVIEW"


class ConflictCode(str, Enum):
    VALIDATION_RESULT_PROPOSAL_MISMATCH = "VALIDATION_RESULT_PROPOSAL_MISMATCH"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    STALE_VAULT_REVISION = "STALE_VAULT_REVISION"
    TARGET_MISSING = "TARGET_MISSING"
    TARGET_CHANGED_SINCE_PROPOSAL = "TARGET_CHANGED_SINCE_PROPOSAL"
    TARGET_STATE_COMPARISON_UNAVAILABLE = "TARGET_STATE_COMPARISON_UNAVAILABLE"
    TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL = "TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL"
    UNVERIFIED_TEXT_INPUT = "UNVERIFIED_TEXT_INPUT"
    STABLE_ID_COLLISION = "STABLE_ID_COLLISION"
    PROPOSED_CONTENT_ALREADY_IDENTICAL = "PROPOSED_CONTENT_ALREADY_IDENTICAL"
    PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT = "PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT"


_FINDING_ORDER: Final[Mapping[ConflictCode, int]] = MappingProxyType({
    ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH: 0,
    ConflictCode.UNSUPPORTED_OPERATION: 1,
    ConflictCode.STALE_VAULT_REVISION: 2,
    ConflictCode.TARGET_MISSING: 3,
    ConflictCode.UNVERIFIED_TEXT_INPUT: 4,
    ConflictCode.TARGET_CHANGED_SINCE_PROPOSAL: 5,
    ConflictCode.TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL: 6,
    ConflictCode.TARGET_STATE_COMPARISON_UNAVAILABLE: 7,
    ConflictCode.STABLE_ID_COLLISION: 8,
    ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL: 9,
    ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT: 10,
})


_CANONICAL_VALUE_TAGS: Final[frozenset[str]] = frozenset({
    "null",
    "bool",
    "int",
    "string",
    "mapping",
    "sequence",
})

_PROPOSED_CONTENT_FIELD_ORDER: Final[tuple[str, ...]] = (
    "title",
    "body_text",
    "type",
    "status",
    "knowledge_layer",
    "evidence_class",
    "authority",
    "canonical",
    "canonical_scope",
    "aliases",
    "releases",
    "source_paths",
    "evidence_refs",
    "supersedes",
    "superseded_by",
    "updated",
    "last_reviewed",
    "verified_at",
)


@dataclass(frozen=True, slots=True)
class FrozenCanonicalValue:
    """Type-tagged immutable canonical value used for validation snapshots."""

    type_tag: str
    scalar_value: str | int | bool | None = None
    mapping_items: tuple[tuple[str, "FrozenCanonicalValue"], ...] = ()
    sequence_items: tuple["FrozenCanonicalValue", ...] = ()

    def __post_init__(self) -> None:
        if self.type_tag not in _CANONICAL_VALUE_TAGS:
            raise ValueError("unsupported canonical value type tag")
        if not isinstance(self.mapping_items, tuple) or not isinstance(self.sequence_items, tuple):
            raise ValueError("canonical value collections must be immutable tuples")

        if self.type_tag == "mapping":
            if self.scalar_value is not None or self.sequence_items:
                raise ValueError("mapping canonical value has invalid payload channels")
            previous_key: str | None = None
            for item in self.mapping_items:
                if not isinstance(item, tuple) or len(item) != 2:
                    raise ValueError("mapping canonical items must be key/value tuples")
                key, child = item
                if not isinstance(key, str) or not isinstance(child, FrozenCanonicalValue):
                    raise ValueError("mapping canonical item has invalid type")
                if previous_key is not None and key <= previous_key:
                    raise ValueError("mapping canonical keys must be unique and sorted")
                previous_key = key
            return

        if self.type_tag == "sequence":
            if self.scalar_value is not None or self.mapping_items:
                raise ValueError("sequence canonical value has invalid payload channels")
            if not all(isinstance(item, FrozenCanonicalValue) for item in self.sequence_items):
                raise ValueError("sequence canonical items must be canonical values")
            return

        if self.mapping_items or self.sequence_items:
            raise ValueError("scalar canonical value must not contain child items")
        if self.type_tag == "null" and self.scalar_value is not None:
            raise ValueError("null canonical value must contain None")
        if self.type_tag == "bool" and type(self.scalar_value) is not bool:
            raise ValueError("bool canonical value must contain bool")
        if self.type_tag == "int" and type(self.scalar_value) is not int:
            raise ValueError("int canonical value must contain int")
        if self.type_tag == "string" and type(self.scalar_value) is not str:
            raise ValueError("string canonical value must contain string")

    def identity_payload(self) -> dict[str, Any]:
        if self.type_tag == "mapping":
            return {
                "type": "mapping",
                "items": [
                    [key, child.identity_payload()]
                    for key, child in self.mapping_items
                ],
            }
        if self.type_tag == "sequence":
            return {
                "type": "sequence",
                "items": [child.identity_payload() for child in self.sequence_items],
            }
        if self.type_tag == "null":
            return {"type": "null"}
        return {"type": self.type_tag, "value": self.scalar_value}


@dataclass(frozen=True, slots=True)
class ProposedContentSnapshot:
    """Frozen review projection of every real e9a ProposedNoteContent field."""

    title: str
    body_text: str
    type: str
    status: str
    knowledge_layer: str
    evidence_class: str
    authority: str
    canonical: bool
    canonical_scope: str | None
    aliases: tuple[str, ...]
    releases: tuple[str, ...]
    source_paths: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    supersedes: tuple[str, ...]
    superseded_by: tuple[str, ...]
    updated: str
    last_reviewed: str
    verified_at: str | None

    def __post_init__(self) -> None:
        string_fields = (
            "title",
            "body_text",
            "type",
            "status",
            "knowledge_layer",
            "evidence_class",
            "authority",
            "updated",
            "last_reviewed",
        )
        for name in string_fields:
            if type(getattr(self, name)) is not str:
                raise ValueError(f"proposed content snapshot {name} must be string")
        if type(self.canonical) is not bool:
            raise ValueError("proposed content snapshot canonical must be bool")
        for name in ("canonical_scope", "verified_at"):
            value = getattr(self, name)
            if value is not None and type(value) is not str:
                raise ValueError(f"proposed content snapshot {name} must be string or None")
        for name in (
            "aliases",
            "releases",
            "source_paths",
            "evidence_refs",
            "supersedes",
            "superseded_by",
        ):
            value = getattr(self, name)
            if not isinstance(value, tuple) or not all(type(item) is str for item in value):
                raise ValueError(f"proposed content snapshot {name} must be tuple[str, ...]")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "body_text": self.body_text,
            "type": self.type,
            "status": self.status,
            "knowledge_layer": self.knowledge_layer,
            "evidence_class": self.evidence_class,
            "authority": self.authority,
            "canonical": self.canonical,
            "canonical_scope": self.canonical_scope,
            "aliases": list(self.aliases),
            "releases": list(self.releases),
            "source_paths": list(self.source_paths),
            "evidence_refs": list(self.evidence_refs),
            "supersedes": list(self.supersedes),
            "superseded_by": list(self.superseded_by),
            "updated": self.updated,
            "last_reviewed": self.last_reviewed,
            "verified_at": self.verified_at,
        }

    def metadata_items(self) -> tuple[tuple[str, Any], ...]:
        payload = self.identity_payload()
        return tuple(
            (name, payload[name])
            for name in _PROPOSED_CONTENT_FIELD_ORDER
            if name != "body_text"
        )


@dataclass(frozen=True, slots=True)
class ConflictFinding:
    code: ConflictCode
    severity: ConflictSeverity
    message: str
    details: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.code, ConflictCode):
            object.__setattr__(self, "code", ConflictCode(self.code))
        if not isinstance(self.severity, ConflictSeverity):
            object.__setattr__(self, "severity", ConflictSeverity(self.severity))
        if not isinstance(self.message, str) or not self.message:
            raise ValueError("finding message must be a non-empty string")
        if len(self.message) > MAX_FINDING_MESSAGE_CHARS:
            raise ValueError("finding message exceeds bound")
        normalized_details = tuple(self.details)
        if len(normalized_details) > MAX_FINDING_DETAIL_ITEMS:
            raise ValueError("finding details exceed bound")
        checked: list[tuple[str, str]] = []
        for item in normalized_details:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("finding details must be key/value tuples")
            key, value = item
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("finding detail key and value must be strings")
            if not key or len(key) > MAX_FINDING_DETAIL_CHARS or len(value) > MAX_FINDING_DETAIL_CHARS:
                raise ValueError("finding detail exceeds bound")
            checked.append((key, value))
        object.__setattr__(self, "details", tuple(sorted(checked)))

    def identity_payload(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "details": [[key, value] for key, value in self.details],
        }


@dataclass(frozen=True, slots=True)
class LineEndingProfile:
    crlf_count: int
    lf_count: int
    cr_count: int
    terminal_newline: bool

    def __post_init__(self) -> None:
        for value in (self.crlf_count, self.lf_count, self.cr_count):
            if not isinstance(value, int) or value < 0:
                raise ValueError("line-ending counts must be non-negative integers")
        if not isinstance(self.terminal_newline, bool):
            raise ValueError("terminal_newline must be bool")

    @property
    def label(self) -> str:
        present = []
        if self.crlf_count:
            present.append("CRLF")
        if self.lf_count:
            present.append("LF")
        if self.cr_count:
            present.append("CR")
        if not present:
            present.append("NONE")
        return "+".join(present)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "crlf_count": self.crlf_count,
            "lf_count": self.lf_count,
            "cr_count": self.cr_count,
            "terminal_newline": self.terminal_newline,
        }


@dataclass(frozen=True, slots=True)
class RepresentationDelta:
    before_present: bool
    after_present: bool
    before_line_endings: LineEndingProfile | None
    after_line_endings: LineEndingProfile
    terminal_newline_changed: bool
    after_source_bytes_known: bool
    source_bytes_changed_text_identical: bool
    raw_text_changed_semantic_equal: bool
    semantic_content_changed: bool
    identity: str

    def __post_init__(self) -> None:
        if not isinstance(self.before_present, bool) or not isinstance(self.after_present, bool):
            raise ValueError("representation presence flags must be bool")
        if self.before_present and not isinstance(self.before_line_endings, LineEndingProfile):
            raise ValueError("before line-ending profile required when before is present")
        if not self.before_present and self.before_line_endings is not None:
            raise ValueError("before line-ending profile forbidden when before is absent")
        if not isinstance(self.after_line_endings, LineEndingProfile):
            raise ValueError("after line-ending profile required")
        if not isinstance(self.after_source_bytes_known, bool):
            raise ValueError("after_source_bytes_known must be bool")
        if not _SHA256_VALUE_RE.fullmatch(self.identity):
            raise ValueError("representation identity must be sha256:<64-hex>")


@dataclass(frozen=True, slots=True)
class TrustedTargetSnapshot:
    source_bytes: bytes
    trusted_text: str
    source_relative_path: str
    target_stable_id: str
    captured_vault_revision: str
    source_byte_hash: str
    text_raw_hash: str
    semantic_text_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_bytes, bytes):
            raise ValueError("source_bytes must be immutable bytes")
        if not isinstance(self.trusted_text, str):
            raise ValueError("trusted_text must be string")
        for name in (
            "source_relative_path",
            "target_stable_id",
            "captured_vault_revision",
            "source_byte_hash",
            "text_raw_hash",
            "semantic_text_hash",
        ):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f"{name} must be string")


@dataclass(frozen=True, slots=True)
class CurrentKnowledgeState:
    observed_vault_revision: str
    current_stable_ids: frozenset[str] | set[str] | tuple[str, ...] | list[str]
    current_target: TrustedTargetSnapshot | None = None
    baseline_target: TrustedTargetSnapshot | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.observed_vault_revision, str) or not _REVISION_RE.fullmatch(
            self.observed_vault_revision
        ):
            raise ValueError("observed_vault_revision must be sha256:<64-hex>")
        if type(self.current_stable_ids) not in (frozenset, set, tuple, list):
            raise ValueError(
                "current_stable_ids must be list, tuple, set, or frozenset of strings"
            )
        try:
            stable_ids = frozenset(self.current_stable_ids)
        except TypeError as exc:
            raise ValueError("current_stable_ids entries must be strings") from exc
        if len(stable_ids) > MAX_STABLE_IDS:
            raise ValueError("current_stable_ids exceeds hard bound")
        for stable_id in stable_ids:
            if type(stable_id) is not str:
                raise ValueError("current_stable_ids entries must be strings")
            _validate_stable_id(stable_id)
        object.__setattr__(self, "current_stable_ids", stable_ids)
        if self.current_target is not None and not isinstance(self.current_target, TrustedTargetSnapshot):
            raise ValueError("current_target must be TrustedTargetSnapshot or None")
        if self.baseline_target is not None and not isinstance(self.baseline_target, TrustedTargetSnapshot):
            raise ValueError("baseline_target must be TrustedTargetSnapshot or None")


@dataclass(frozen=True, slots=True)
class KnowledgeChangeReviewArtifact:
    contract_version: str
    status: ReviewStatus
    proposal_id: str
    proposal_content_hash: str
    operation: str
    target_stable_id: str
    expected_vault_revision: str
    observed_vault_revision: str
    validation_outcome: str
    validation_snapshot: FrozenCanonicalValue
    source_validation_findings: tuple[tuple[str, str], ...]
    stable_id_set_hash: str
    proposed_content_snapshot: ProposedContentSnapshot
    findings: tuple[ConflictFinding, ...]
    before_source_byte_hash: str | None
    before_text_raw_hash: str | None
    before_semantic_text_hash: str | None
    proposed_text_raw_hash: str | None
    proposed_semantic_text_hash: str | None
    deterministic_text_diff: str | None
    deterministic_text_diff_hash: str | None
    representation_delta: RepresentationDelta | None
    change_identity: str | None
    review_artifact_identity: str
    human_review_preview: str

    def __post_init__(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("review artifact contract version mismatch")
        if not isinstance(self.status, ReviewStatus):
            object.__setattr__(self, "status", ReviewStatus(self.status))
        if not isinstance(self.findings, tuple):
            raise ValueError("findings must be immutable tuple")
        if not isinstance(self.source_validation_findings, tuple):
            raise ValueError("source_validation_findings must be immutable tuple")
        if not isinstance(self.validation_snapshot, FrozenCanonicalValue):
            raise ValueError("validation_snapshot must be FrozenCanonicalValue")
        if not isinstance(self.proposed_content_snapshot, ProposedContentSnapshot):
            raise ValueError("proposed_content_snapshot must be ProposedContentSnapshot")
        if not _SHA256_VALUE_RE.fullmatch(self.stable_id_set_hash):
            raise ValueError("stable_id_set_hash invalid")
        if not re.fullmatch(r"kreview:[0-9a-f]{64}", self.review_artifact_identity):
            raise ValueError("review_artifact_identity invalid")
        if self.change_identity is not None and not re.fullmatch(r"kchange:[0-9a-f]{64}", self.change_identity):
            raise ValueError("change_identity invalid")
        if any(
            finding.severity is ConflictSeverity.BLOCKING
            for finding in self.findings
        ) and any(
            value is not None
            for value in (
                self.deterministic_text_diff,
                self.deterministic_text_diff_hash,
                self.representation_delta,
                self.change_identity,
            )
        ):
            raise ValueError("blocking artifact must not expose normal change material")
        preview_bytes = self.human_review_preview.encode("utf-8")
        if len(preview_bytes) > MAX_PREVIEW_BYTES:
            raise ValueError("human_review_preview exceeds byte bound")
        if len(self.human_review_preview.splitlines()) > MAX_PREVIEW_LINES:
            raise ValueError("human_review_preview exceeds line bound")


@dataclass(frozen=True, slots=True)
class _SnapshotVerification:
    valid: bool
    errors: tuple[str, ...]
    decoded_text: str | None


@dataclass(slots=True)
class _SnapshotBudget:
    nodes: int = 0


class _CanonicalSnapshotError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def semantic_normalize_v1(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("semantic_normalize_v1 requires string")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def compute_source_byte_hash(source_bytes: bytes) -> str:
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    return _sha256(source_bytes)


def compute_text_raw_hash(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be string")
    return _sha256(text.encode("utf-8"))


def compute_semantic_text_hash(text: str) -> str:
    return _sha256(semantic_normalize_v1(text).encode("utf-8"))


def create_trusted_target_snapshot(
    *,
    source_bytes: bytes,
    source_relative_path: str,
    target_stable_id: str,
    captured_vault_revision: str,
) -> TrustedTargetSnapshot:
    if not isinstance(source_bytes, bytes):
        raise ValueError("source_bytes must be immutable bytes")
    if len(source_bytes) > MAX_SOURCE_BYTES:
        raise ValueError("source_bytes exceeds hard bound")
    try:
        trusted_text = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("source_bytes are not strict UTF-8") from exc
    if len(trusted_text) > MAX_TRUSTED_TEXT_CHARS:
        raise ValueError("trusted_text exceeds hard bound")
    _validate_relative_path(source_relative_path)
    _validate_stable_id(target_stable_id)
    _validate_revision(captured_vault_revision)
    return TrustedTargetSnapshot(
        source_bytes=source_bytes,
        trusted_text=trusted_text,
        source_relative_path=source_relative_path,
        target_stable_id=target_stable_id,
        captured_vault_revision=captured_vault_revision,
        source_byte_hash=compute_source_byte_hash(source_bytes),
        text_raw_hash=compute_text_raw_hash(trusted_text),
        semantic_text_hash=compute_semantic_text_hash(trusted_text),
    )


def analyze_review(
    proposal: KnowledgeChangeProposal,
    validation_result: ValidationResult,
    current_state: CurrentKnowledgeState,
) -> KnowledgeChangeReviewArtifact:
    """Return an immutable deterministic review artifact and perform no side effects."""
    if not isinstance(proposal, KnowledgeChangeProposal):
        raise TypeError("proposal must be the real e9a KnowledgeChangeProposal")
    if not isinstance(validation_result, ValidationResult):
        raise TypeError("validation_result must be the real e9a ValidationResult")
    if not isinstance(current_state, CurrentKnowledgeState):
        raise TypeError("current_state must be CurrentKnowledgeState")
    if proposal.proposed_content is None:
        raise ValueError("supported e9b operations require proposed_content")

    proposed_snapshot = _snapshot_proposed_content(proposal.proposed_content)
    _validate_proposal_bounds(proposal, proposed_snapshot)
    proposed_text = proposed_snapshot.body_text
    proposed_raw_hash = compute_text_raw_hash(proposed_text)
    proposed_semantic_hash = compute_semantic_text_hash(proposed_text)
    proposal_content_hash = compute_proposal_content_hash(proposal)
    stable_id_set_hash = _stable_id_set_hash(current_state.current_stable_ids)

    findings: list[ConflictFinding] = []
    try:
        validation_snapshot = _snapshot_validation_result(validation_result)
    except _CanonicalSnapshotError as exc:
        validation_snapshot = _validation_snapshot_error_value(exc.code)
        findings.append(_finding(
            ConflictCode.UNVERIFIED_TEXT_INPUT,
            ConflictSeverity.BLOCKING,
            "The mutable e9a ValidationResult data could not be safely snapshotted.",
            ("validation_snapshot_error", exc.code),
        ))

    source_validation_findings = tuple(
        (finding.code, finding.severity) for finding in validation_result.findings
    )

    binding_errors = _validation_binding_errors(proposal, validation_result, proposal_content_hash)
    if binding_errors:
        findings.append(_finding(
            ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,
            ConflictSeverity.BLOCKING,
            "The supplied e9a ValidationResult is not bound to the exact proposal.",
            ("mismatched_fields", ",".join(binding_errors)),
        ))

    if proposal.operation not in (ProposalOperation.UPDATE_EXISTING, ProposalOperation.CREATE_NEW):
        findings.append(_finding(
            ConflictCode.UNSUPPORTED_OPERATION,
            ConflictSeverity.BLOCKING,
            "The proposal operation is outside the e9b review boundary.",
            ("operation", proposal.operation.value),
        ))

    observed_revision = current_state.observed_vault_revision
    if (
        validation_result.outcome is ValidationOutcome.STALE
        or proposal.expected_vault_revision != observed_revision
        or validation_result.validated_vault_revision != observed_revision
    ):
        findings.append(_finding(
            ConflictCode.STALE_VAULT_REVISION,
            ConflictSeverity.BLOCKING,
            "The proposal or validation result is stale relative to the observed Vault revision.",
            ("expected", proposal.expected_vault_revision),
            ("validated", validation_result.validated_vault_revision),
            ("observed", observed_revision),
        ))

    operation_analysis_allowed = (
        not binding_errors
        and validation_result.outcome is ValidationOutcome.VALID
        and proposal.operation in (ProposalOperation.UPDATE_EXISTING, ProposalOperation.CREATE_NEW)
    )

    before_snapshot: TrustedTargetSnapshot | None = None
    full_diff: str | None = None
    full_diff_hash: str | None = None
    representation_delta: RepresentationDelta | None = None
    change_identity: str | None = None
    before_source_hash: str | None = None
    before_raw_hash: str | None = None
    before_semantic_hash: str | None = None

    if operation_analysis_allowed and proposal.operation is ProposalOperation.UPDATE_EXISTING:
        before_snapshot, operation_findings = _analyze_update_state(proposal, current_state)
        findings.extend(operation_findings)
        if before_snapshot is not None:
            before_source_hash = before_snapshot.source_byte_hash
            before_raw_hash = before_snapshot.text_raw_hash
            before_semantic_hash = before_snapshot.semantic_text_hash
        if before_snapshot is not None and not _has_blocking_finding(findings):
            full_diff, full_diff_hash, representation_delta = _build_change_material(
                stable_id=proposal.target_stable_id,
                before_text=before_snapshot.trusted_text,
                before_source_bytes=before_snapshot.source_bytes,
                after_text=proposed_text,
                create_new=False,
            )
            change_identity = _compute_change_identity(
                proposal=proposal,
                proposal_content_hash=proposal_content_hash,
                proposed_content_snapshot=proposed_snapshot,
                observed_revision=observed_revision,
                stable_id_set_hash=stable_id_set_hash,
                before_snapshot=before_snapshot,
                proposed_raw_hash=proposed_raw_hash,
                proposed_semantic_hash=proposed_semantic_hash,
                full_diff_hash=full_diff_hash,
                representation_identity=representation_delta.identity,
            )

    elif operation_analysis_allowed and proposal.operation is ProposalOperation.CREATE_NEW:
        operation_findings = _analyze_create_state(proposal, current_state)
        findings.extend(operation_findings)
        if not _has_blocking_finding(findings):
            full_diff, full_diff_hash, representation_delta = _build_change_material(
                stable_id=proposal.target_stable_id,
                before_text=None,
                before_source_bytes=None,
                after_text=proposed_text,
                create_new=True,
            )
            change_identity = _compute_change_identity(
                proposal=proposal,
                proposal_content_hash=proposal_content_hash,
                proposed_content_snapshot=proposed_snapshot,
                observed_revision=observed_revision,
                stable_id_set_hash=stable_id_set_hash,
                before_snapshot=None,
                proposed_raw_hash=proposed_raw_hash,
                proposed_semantic_hash=proposed_semantic_hash,
                full_diff_hash=full_diff_hash,
                representation_identity=representation_delta.identity,
            )

    ordered_findings = _order_and_deduplicate_findings(findings)
    status = _derive_status(validation_result.outcome, ordered_findings)
    preview = _build_human_preview(
        proposal=proposal,
        proposed_content_snapshot=proposed_snapshot,
        validation_result=validation_result,
        status=status,
        findings=ordered_findings,
        representation_delta=representation_delta,
        full_diff=full_diff,
    )
    review_identity = _compute_review_identity(
        proposal=proposal,
        proposal_content_hash=proposal_content_hash,
        proposed_content_snapshot=proposed_snapshot,
        validation_snapshot=validation_snapshot,
        status=status,
        observed_revision=observed_revision,
        stable_id_set_hash=stable_id_set_hash,
        findings=ordered_findings,
        before_source_hash=before_source_hash,
        before_raw_hash=before_raw_hash,
        before_semantic_hash=before_semantic_hash,
        proposed_raw_hash=proposed_raw_hash,
        proposed_semantic_hash=proposed_semantic_hash,
        full_diff_hash=full_diff_hash,
        representation_identity=representation_delta.identity if representation_delta else None,
        change_identity=change_identity,
    )

    return KnowledgeChangeReviewArtifact(
        contract_version=CONTRACT_VERSION,
        status=status,
        proposal_id=proposal.proposal_id,
        proposal_content_hash=proposal_content_hash,
        operation=proposal.operation.value,
        target_stable_id=proposal.target_stable_id,
        expected_vault_revision=proposal.expected_vault_revision,
        observed_vault_revision=observed_revision,
        validation_outcome=validation_result.outcome.value,
        validation_snapshot=validation_snapshot,
        source_validation_findings=source_validation_findings,
        stable_id_set_hash=stable_id_set_hash,
        proposed_content_snapshot=proposed_snapshot,
        findings=ordered_findings,
        before_source_byte_hash=before_source_hash,
        before_text_raw_hash=before_raw_hash,
        before_semantic_text_hash=before_semantic_hash,
        proposed_text_raw_hash=proposed_raw_hash,
        proposed_semantic_text_hash=proposed_semantic_hash,
        deterministic_text_diff=full_diff,
        deterministic_text_diff_hash=full_diff_hash,
        representation_delta=representation_delta,
        change_identity=change_identity,
        review_artifact_identity=review_identity,
        human_review_preview=preview,
    )

def _snapshot_proposed_content(content: ProposedNoteContent) -> ProposedContentSnapshot:
    if not isinstance(content, ProposedNoteContent):
        raise TypeError("proposed_content must be the real e9a ProposedNoteContent")
    return ProposedContentSnapshot(
        title=content.title,
        body_text=content.body_text,
        type=content.type,
        status=content.status,
        knowledge_layer=content.knowledge_layer,
        evidence_class=content.evidence_class,
        authority=content.authority,
        canonical=content.canonical,
        canonical_scope=content.canonical_scope,
        aliases=tuple(content.aliases),
        releases=tuple(content.releases),
        source_paths=tuple(content.source_paths),
        evidence_refs=tuple(content.evidence_refs),
        supersedes=tuple(content.supersedes),
        superseded_by=tuple(content.superseded_by),
        updated=content.updated,
        last_reviewed=content.last_reviewed,
        verified_at=content.verified_at,
    )


def _validate_proposal_bounds(
    proposal: KnowledgeChangeProposal,
    proposed_snapshot: ProposedContentSnapshot,
) -> None:
    _validate_stable_id(proposal.target_stable_id)
    _validate_revision(proposal.expected_vault_revision)
    proposed_bytes = proposed_snapshot.body_text.encode("utf-8")
    if len(proposed_bytes) > MAX_PROPOSED_CONTENT_BYTES:
        raise ValueError("proposed body content exceeds hard byte bound")
    snapshot_bytes = _canonical_json_bytes(proposed_snapshot.identity_payload())
    if len(snapshot_bytes) > MAX_PROPOSED_SNAPSHOT_BYTES:
        raise ValueError("proposed structured content exceeds hard byte bound")
    if len(proposal.provenance.evidence_references) > MAX_EVIDENCE_REFERENCES:
        raise ValueError("evidence references exceed hard bound")
    if _count_provenance_entries(proposal.provenance.to_dict()) > MAX_PROVENANCE_ENTRIES:
        raise ValueError("provenance entries exceed hard bound")


def _validation_binding_errors(
    proposal: KnowledgeChangeProposal,
    result: ValidationResult,
    expected_content_hash: str,
) -> tuple[str, ...]:
    comparisons = (
        ("proposal_id", result.proposal_id, proposal.proposal_id, str),
        ("proposal_content_hash", result.proposal_content_hash, expected_content_hash, str),
        ("contract_version", result.contract_version, proposal.contract_version, str),
        ("operation", result.operation, proposal.operation.value, str),
        ("target_stable_id", result.target_stable_id, proposal.target_stable_id, str),
        (
            "expected_vault_revision",
            result.expected_vault_revision,
            proposal.expected_vault_revision,
            str,
        ),
    )
    mismatches = []
    for field_name, actual, expected, expected_type in comparisons:
        if type(actual) is not expected_type or actual != expected:
            mismatches.append(field_name)
    return tuple(mismatches)


def _analyze_update_state(
    proposal: KnowledgeChangeProposal,
    state: CurrentKnowledgeState,
) -> tuple[TrustedTargetSnapshot | None, list[ConflictFinding]]:
    findings: list[ConflictFinding] = []
    if proposal.target_stable_id not in state.current_stable_ids or state.current_target is None:
        findings.append(_finding(
            ConflictCode.TARGET_MISSING,
            ConflictSeverity.BLOCKING,
            "The current target snapshot is missing.",
            ("target_stable_id", proposal.target_stable_id),
        ))
        return None, findings

    current = state.current_target
    current_verification = _verify_snapshot(current)
    current_context_errors = []
    if current.target_stable_id != proposal.target_stable_id:
        current_context_errors.append("current_target_stable_id")
    if current.captured_vault_revision != state.observed_vault_revision:
        current_context_errors.append("current_captured_vault_revision")
    if not current_verification.valid or current_context_errors:
        findings.append(_finding(
            ConflictCode.UNVERIFIED_TEXT_INPUT,
            ConflictSeverity.BLOCKING,
            "The current target snapshot failed verification.",
            ("errors", ",".join(current_verification.errors + tuple(current_context_errors))),
        ))
        return None, findings

    baseline = state.baseline_target
    if baseline is None:
        findings.append(_finding(
            ConflictCode.TARGET_STATE_COMPARISON_UNAVAILABLE,
            ConflictSeverity.REVIEW,
            "No trusted baseline snapshot was supplied; historical target drift is not claimed.",
            ("expected_vault_revision", proposal.expected_vault_revision),
        ))
        return current, findings

    baseline_verification = _verify_snapshot(baseline)
    baseline_context_errors = []
    if baseline.target_stable_id != proposal.target_stable_id:
        baseline_context_errors.append("baseline_target_stable_id")
    if baseline.captured_vault_revision != proposal.expected_vault_revision:
        baseline_context_errors.append("baseline_captured_vault_revision")
    if not baseline_verification.valid or baseline_context_errors:
        findings.append(_finding(
            ConflictCode.UNVERIFIED_TEXT_INPUT,
            ConflictSeverity.BLOCKING,
            "The baseline target snapshot failed verification.",
            ("errors", ",".join(baseline_verification.errors + tuple(baseline_context_errors))),
        ))
        return current, findings

    if baseline.source_bytes != current.source_bytes:
        if baseline.trusted_text == current.trusted_text:
            findings.append(_finding(
                ConflictCode.TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL,
                ConflictSeverity.REVIEW,
                "Target source bytes changed while decoded text remained identical.",
                ("baseline_source_byte_hash", baseline.source_byte_hash),
                ("current_source_byte_hash", current.source_byte_hash),
            ))
        else:
            findings.append(_finding(
                ConflictCode.TARGET_CHANGED_SINCE_PROPOSAL,
                ConflictSeverity.BLOCKING,
                "The verified target changed since the proposal baseline.",
                ("baseline_text_raw_hash", baseline.text_raw_hash),
                ("current_text_raw_hash", current.text_raw_hash),
            ))
    return current, findings


def _analyze_create_state(
    proposal: KnowledgeChangeProposal,
    state: CurrentKnowledgeState,
) -> list[ConflictFinding]:
    findings: list[ConflictFinding] = []
    if state.current_target is not None or state.baseline_target is not None:
        findings.append(_finding(
            ConflictCode.UNVERIFIED_TEXT_INPUT,
            ConflictSeverity.BLOCKING,
            "CREATE_NEW must not receive a target preimage or baseline snapshot.",
            ("operation", proposal.operation.value),
        ))
    if proposal.target_stable_id in state.current_stable_ids:
        findings.append(_finding(
            ConflictCode.STABLE_ID_COLLISION,
            ConflictSeverity.BLOCKING,
            "The proposed stable ID already exists in the bounded current state.",
            ("target_stable_id", proposal.target_stable_id),
        ))
    return findings


def _verify_snapshot(snapshot: TrustedTargetSnapshot) -> _SnapshotVerification:
    errors: list[str] = []
    if len(snapshot.source_bytes) > MAX_SOURCE_BYTES:
        errors.append("source_bytes_oversized")
    if len(snapshot.trusted_text) > MAX_TRUSTED_TEXT_CHARS:
        errors.append("trusted_text_oversized")
    try:
        _validate_relative_path(snapshot.source_relative_path)
    except ValueError:
        errors.append("invalid_relative_path")
    try:
        _validate_stable_id(snapshot.target_stable_id)
    except ValueError:
        errors.append("invalid_stable_id")
    try:
        _validate_revision(snapshot.captured_vault_revision)
    except ValueError:
        errors.append("invalid_revision")

    decoded_text: str | None = None
    try:
        decoded_text = snapshot.source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        errors.append("utf8_decode_failure")
    if decoded_text is not None and decoded_text != snapshot.trusted_text:
        errors.append("bytes_text_mismatch")
    if snapshot.source_byte_hash != compute_source_byte_hash(snapshot.source_bytes):
        errors.append("source_byte_hash_mismatch")
    if snapshot.text_raw_hash != compute_text_raw_hash(snapshot.trusted_text):
        errors.append("text_raw_hash_mismatch")
    if snapshot.semantic_text_hash != compute_semantic_text_hash(snapshot.trusted_text):
        errors.append("semantic_text_hash_mismatch")
    for value, label in (
        (snapshot.source_byte_hash, "source_byte_hash_format"),
        (snapshot.text_raw_hash, "text_raw_hash_format"),
        (snapshot.semantic_text_hash, "semantic_text_hash_format"),
    ):
        if not _SHA256_VALUE_RE.fullmatch(value):
            errors.append(label)
    return _SnapshotVerification(not errors, tuple(sorted(set(errors))), decoded_text)


def _build_change_material(
    *,
    stable_id: str,
    before_text: str | None,
    before_source_bytes: bytes | None,
    after_text: str,
    create_new: bool,
) -> tuple[str, str, RepresentationDelta]:
    full_diff = _deterministic_text_diff(
        stable_id,
        before_text,
        after_text,
        create_new=create_new,
    )
    if len(full_diff.encode("utf-8")) > MAX_FULL_DIFF_BYTES:
        raise ValueError("deterministic full diff exceeds hard bound")
    full_diff_hash = _domain_hash(
        "DETERMINISTIC_TEXT_DIFF_HASH",
        IDENTITY_VERSION,
        {"diff": full_diff},
    )
    representation_delta = _representation_delta(
        before_text=before_text,
        before_source_bytes=before_source_bytes,
        after_text=after_text,
        after_source_bytes=None,
    )
    return full_diff, full_diff_hash, representation_delta

def _deterministic_text_diff(
    stable_id: str,
    before_text: str | None,
    after_text: str,
    *,
    create_new: bool,
) -> str:
    before_normalized = semantic_normalize_v1(before_text) if before_text is not None else ""
    after_normalized = semantic_normalize_v1(after_text)
    before_lines = before_normalized.splitlines(keepends=True)
    after_lines = after_normalized.splitlines(keepends=True)
    from_label = "/dev/null" if create_new else f"before-body/{stable_id}"
    to_label = f"after-body/{stable_id}"
    return "".join(difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=from_label,
        tofile=to_label,
        n=3,
        lineterm="\n",
    ))


def _representation_delta(
    *,
    before_text: str | None,
    before_source_bytes: bytes | None,
    after_text: str,
    after_source_bytes: bytes | None,
) -> RepresentationDelta:
    before_profile = _line_ending_profile(before_text) if before_text is not None else None
    after_profile = _line_ending_profile(after_text)
    before_present = before_text is not None
    terminal_changed = (
        before_profile.terminal_newline != after_profile.terminal_newline
        if before_profile is not None
        else False
    )
    after_source_bytes_known = after_source_bytes is not None
    source_bytes_changed_text_identical = (
        before_present
        and before_source_bytes is not None
        and after_source_bytes is not None
        and before_source_bytes != after_source_bytes
        and before_text == after_text
    )
    raw_changed_semantic_equal = (
        before_present
        and before_text != after_text
        and semantic_normalize_v1(before_text or "") == semantic_normalize_v1(after_text)
    )
    semantic_changed = (
        not before_present
        or semantic_normalize_v1(before_text or "") != semantic_normalize_v1(after_text)
    )
    identity_payload = {
        "before_present": before_present,
        "after_present": True,
        "before_line_endings": before_profile.identity_payload() if before_profile else None,
        "after_line_endings": after_profile.identity_payload(),
        "terminal_newline_changed": terminal_changed,
        "after_source_bytes_known": after_source_bytes_known,
        "source_bytes_changed_text_identical": source_bytes_changed_text_identical,
        "raw_text_changed_semantic_equal": raw_changed_semantic_equal,
        "semantic_content_changed": semantic_changed,
    }
    identity = _domain_hash(
        "REPRESENTATION_DELTA_IDENTITY",
        IDENTITY_VERSION,
        identity_payload,
    )
    return RepresentationDelta(
        before_present=before_present,
        after_present=True,
        before_line_endings=before_profile,
        after_line_endings=after_profile,
        terminal_newline_changed=terminal_changed,
        after_source_bytes_known=after_source_bytes_known,
        source_bytes_changed_text_identical=source_bytes_changed_text_identical,
        raw_text_changed_semantic_equal=raw_changed_semantic_equal,
        semantic_content_changed=semantic_changed,
        identity=identity,
    )


def _line_ending_profile(text: str) -> LineEndingProfile:
    crlf_count = text.count("\r\n")
    without_crlf = text.replace("\r\n", "")
    lf_count = without_crlf.count("\n")
    cr_count = without_crlf.count("\r")
    return LineEndingProfile(
        crlf_count=crlf_count,
        lf_count=lf_count,
        cr_count=cr_count,
        terminal_newline=text.endswith("\n") or text.endswith("\r"),
    )


def _compute_change_identity(
    *,
    proposal: KnowledgeChangeProposal,
    proposal_content_hash: str,
    proposed_content_snapshot: ProposedContentSnapshot,
    observed_revision: str,
    stable_id_set_hash: str,
    before_snapshot: TrustedTargetSnapshot | None,
    proposed_raw_hash: str | None,
    proposed_semantic_hash: str | None,
    full_diff_hash: str,
    representation_identity: str,
) -> str:
    payload = {
        "proposal_id": proposal.proposal_id,
        "proposal_content_hash": proposal_content_hash,
        "proposed_content_snapshot": proposed_content_snapshot.identity_payload(),
        "operation": proposal.operation.value,
        "target_stable_id": proposal.target_stable_id,
        "expected_vault_revision": proposal.expected_vault_revision,
        "observed_vault_revision": observed_revision,
        "stable_id_set_hash": stable_id_set_hash,
        "before": {
            "source_relative_path": before_snapshot.source_relative_path,
            "source_byte_hash": before_snapshot.source_byte_hash,
            "text_raw_hash": before_snapshot.text_raw_hash,
            "semantic_text_hash": before_snapshot.semantic_text_hash,
            "captured_vault_revision": before_snapshot.captured_vault_revision,
        } if before_snapshot else None,
        "after": {
            "text_raw_hash": proposed_raw_hash,
            "semantic_text_hash": proposed_semantic_hash,
        },
        "deterministic_text_diff_hash": full_diff_hash,
        "representation_delta_identity": representation_identity,
    }
    return CHANGE_ID_PREFIX + _domain_digest("CHANGE_IDENTITY", IDENTITY_VERSION, payload)


def _compute_review_identity(
    *,
    proposal: KnowledgeChangeProposal,
    proposal_content_hash: str,
    proposed_content_snapshot: ProposedContentSnapshot,
    validation_snapshot: FrozenCanonicalValue,
    status: ReviewStatus,
    observed_revision: str,
    stable_id_set_hash: str,
    findings: tuple[ConflictFinding, ...],
    before_source_hash: str | None,
    before_raw_hash: str | None,
    before_semantic_hash: str | None,
    proposed_raw_hash: str | None,
    proposed_semantic_hash: str | None,
    full_diff_hash: str | None,
    representation_identity: str | None,
    change_identity: str | None,
) -> str:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "status": status.value,
        "proposal": {
            "proposal_id": proposal.proposal_id,
            "proposal_content_hash": proposal_content_hash,
            "proposed_content_snapshot": proposed_content_snapshot.identity_payload(),
            "operation": proposal.operation.value,
            "target_stable_id": proposal.target_stable_id,
            "expected_vault_revision": proposal.expected_vault_revision,
        },
        "validation_snapshot": validation_snapshot.identity_payload(),
        "observed_vault_revision": observed_revision,
        "stable_id_set_hash": stable_id_set_hash,
        "findings": [finding.identity_payload() for finding in findings],
        "before": {
            "source_byte_hash": before_source_hash,
            "text_raw_hash": before_raw_hash,
            "semantic_text_hash": before_semantic_hash,
        },
        "proposed": {
            "text_raw_hash": proposed_raw_hash,
            "semantic_text_hash": proposed_semantic_hash,
        },
        "deterministic_text_diff_hash": full_diff_hash,
        "representation_delta_identity": representation_identity,
        "change_identity": change_identity,
    }
    return REVIEW_ID_PREFIX + _domain_digest("REVIEW_ARTIFACT_IDENTITY", IDENTITY_VERSION, payload)


def _snapshot_validation_result(result: ValidationResult) -> FrozenCanonicalValue:
    payload = {
        "outcome": result.outcome.value,
        "proposal_id": result.proposal_id,
        "proposal_content_hash": result.proposal_content_hash,
        "contract_version": result.contract_version,
        "operation": result.operation,
        "target_stable_id": result.target_stable_id,
        "expected_vault_revision": result.expected_vault_revision,
        "validated_vault_revision": result.validated_vault_revision,
        "findings": [
            {"code": item.code, "severity": item.severity}
            for item in result.findings
        ],
        "provenance_summary": result.provenance_summary,
        "evidence_reference_count": result.evidence_reference_count,
    }
    return _freeze_canonical_value(payload)


def _validation_snapshot_error_value(error_code: str) -> FrozenCanonicalValue:
    return FrozenCanonicalValue(
        type_tag="mapping",
        mapping_items=(
            (
                "snapshot_error",
                FrozenCanonicalValue(type_tag="string", scalar_value=error_code),
            ),
            (
                "snapshot_valid",
                FrozenCanonicalValue(type_tag="bool", scalar_value=False),
            ),
        ),
    )


def _freeze_canonical_value(
    value: Any,
    *,
    depth: int = 0,
    active_container_ids: set[int] | None = None,
    budget: _SnapshotBudget | None = None,
) -> FrozenCanonicalValue:
    if active_container_ids is None:
        active_container_ids = set()
    if budget is None:
        budget = _SnapshotBudget()
    if depth > MAX_VALIDATION_SNAPSHOT_DEPTH:
        raise _CanonicalSnapshotError("maximum_depth_exceeded")

    budget.nodes += 1
    if budget.nodes > MAX_VALIDATION_SNAPSHOT_NODES:
        raise _CanonicalSnapshotError("maximum_total_nodes_exceeded")

    if value is None:
        return FrozenCanonicalValue(type_tag="null")
    if type(value) is bool:
        return FrozenCanonicalValue(type_tag="bool", scalar_value=value)
    if type(value) is int:
        return FrozenCanonicalValue(type_tag="int", scalar_value=value)
    if type(value) is str:
        if len(value) > MAX_VALIDATION_STRING_LENGTH:
            raise _CanonicalSnapshotError("maximum_string_value_length_exceeded")
        return FrozenCanonicalValue(type_tag="string", scalar_value=value)

    if isinstance(value, Mapping):
        container_id = id(value)
        if container_id in active_container_ids:
            raise _CanonicalSnapshotError("cycle_detected")
        try:
            entry_count = len(value)
        except Exception as exc:
            raise _CanonicalSnapshotError("mapping_access_failure") from exc
        if entry_count > MAX_VALIDATION_MAPPING_ENTRIES:
            raise _CanonicalSnapshotError("maximum_mapping_entries_exceeded")
        try:
            keys = list(value.keys())
        except Exception as exc:
            raise _CanonicalSnapshotError("mapping_access_failure") from exc
        for key in keys:
            if type(key) is not str:
                raise _CanonicalSnapshotError("mapping_key_not_string")
            if len(key) > MAX_VALIDATION_KEY_LENGTH:
                raise _CanonicalSnapshotError("maximum_mapping_key_length_exceeded")
        keys.sort()
        active_container_ids.add(container_id)
        try:
            items = tuple(
                (
                    key,
                    _freeze_canonical_value(
                        value[key],
                        depth=depth + 1,
                        active_container_ids=active_container_ids,
                        budget=budget,
                    ),
                )
                for key in keys
            )
        except _CanonicalSnapshotError:
            raise
        except Exception as exc:
            raise _CanonicalSnapshotError("mapping_access_failure") from exc
        finally:
            active_container_ids.remove(container_id)
        return FrozenCanonicalValue(type_tag="mapping", mapping_items=items)

    if type(value) in (list, tuple):
        container_id = id(value)
        if container_id in active_container_ids:
            raise _CanonicalSnapshotError("cycle_detected")
        if len(value) > MAX_VALIDATION_SEQUENCE_ENTRIES:
            raise _CanonicalSnapshotError("maximum_sequence_entries_exceeded")
        active_container_ids.add(container_id)
        try:
            items = tuple(
                _freeze_canonical_value(
                    item,
                    depth=depth + 1,
                    active_container_ids=active_container_ids,
                    budget=budget,
                )
                for item in value
            )
        finally:
            active_container_ids.remove(container_id)
        return FrozenCanonicalValue(type_tag="sequence", sequence_items=items)

    raise _CanonicalSnapshotError("unsupported_value_type")


def _has_blocking_finding(findings: Sequence[ConflictFinding]) -> bool:
    return any(
        finding.severity is ConflictSeverity.BLOCKING
        for finding in findings
    )

def _derive_status(
    validation_outcome: ValidationOutcome,
    findings: tuple[ConflictFinding, ...],
) -> ReviewStatus:
    if validation_outcome is not ValidationOutcome.VALID:
        return ReviewStatus.BLOCKED
    if any(finding.severity is ConflictSeverity.BLOCKING for finding in findings):
        return ReviewStatus.BLOCKED
    if findings:
        return ReviewStatus.REVIEW_REQUIRED
    return ReviewStatus.CLEAR


def _order_and_deduplicate_findings(
    findings: Sequence[ConflictFinding],
) -> tuple[ConflictFinding, ...]:
    by_code: dict[ConflictCode, ConflictFinding] = {}
    for finding in findings:
        existing = by_code.get(finding.code)
        if existing is None:
            by_code[finding.code] = finding
            continue
        if (
            finding.severity is ConflictSeverity.BLOCKING
            and existing.severity is not ConflictSeverity.BLOCKING
        ):
            by_code[finding.code] = finding
        elif finding.severity is existing.severity and finding.details < existing.details:
            by_code[finding.code] = finding
    ordered = tuple(sorted(by_code.values(), key=lambda item: _FINDING_ORDER[item.code]))
    if len(ordered) > MAX_FINDINGS:
        raise ValueError("findings exceed hard bound")
    return ordered


def _build_human_preview(
    *,
    proposal: KnowledgeChangeProposal,
    proposed_content_snapshot: ProposedContentSnapshot,
    validation_result: ValidationResult,
    status: ReviewStatus,
    findings: tuple[ConflictFinding, ...],
    representation_delta: RepresentationDelta | None,
    full_diff: str | None,
) -> str:
    lines = [
        f"LocalComet Knowledge Review {CONTRACT_VERSION}",
        f"Status: {status.value}",
        f"Proposal: {proposal.proposal_id}",
        f"Operation: {proposal.operation.value}",
        f"Target: {proposal.target_stable_id}",
        f"Validation outcome: {validation_result.outcome.value}",
        "Findings:",
    ]
    if findings:
        for finding in findings:
            lines.append(f"- {finding.code.value} [{finding.severity.value}]: {finding.message}")
    else:
        lines.append("- none")

    lines.extend([
        "Proposed content review projection:",
        "- publication-byte claim: unavailable by contract",
        "- current structured metadata comparison: unavailable from the trusted text-only target snapshot",
    ])
    proposed_payload = proposed_content_snapshot.identity_payload()
    for field_name in _PROPOSED_CONTENT_FIELD_ORDER:
        lines.append(
            f"- {field_name}: {_bounded_preview_value(proposed_payload[field_name])}"
        )

    lines.append("Body-text representation:")
    if representation_delta is None:
        lines.append("- unavailable")
    else:
        before_label = (
            representation_delta.before_line_endings.label
            if representation_delta.before_line_endings
            else "ABSENT"
        )
        after_label = representation_delta.after_line_endings.label
        lines.extend([
            f"- line endings: {before_label} -> {after_label}",
            f"- terminal newline changed: {str(representation_delta.terminal_newline_changed).lower()}",
            f"- proposed publication source bytes known: "
            f"{str(representation_delta.after_source_bytes_known).lower()}",
            f"- source bytes changed, decoded text identical: "
            f"{str(representation_delta.source_bytes_changed_text_identical).lower()}",
            f"- raw text changed, semantic text equal: "
            f"{str(representation_delta.raw_text_changed_semantic_equal).lower()}",
            f"- semantic body content changed: "
            f"{str(representation_delta.semantic_content_changed).lower()}",
        ])
    lines.append("Deterministic semantic body diff:")
    if full_diff:
        lines.extend(full_diff.splitlines())
    else:
        lines.append("(empty)")
    return _truncate_preview(lines)


def _bounded_preview_value(value: Any) -> str:
    serialized = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    encoded = serialized.encode("utf-8")
    if len(encoded) <= MAX_METADATA_PREVIEW_VALUE_BYTES:
        return serialized
    prefix_budget = max(1, MAX_METADATA_PREVIEW_VALUE_BYTES // 2)
    prefix = encoded[:prefix_budget].decode("utf-8", errors="ignore")
    summary = {
        "preview_prefix": prefix,
        "sha256": _sha256(encoded),
        "truncated": True,
        "utf8_bytes": len(encoded),
    }
    bounded = json.dumps(
        summary,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    if len(bounded.encode("utf-8")) > MAX_METADATA_PREVIEW_VALUE_BYTES:
        raise AssertionError("metadata preview bound invariant violated")
    return bounded

def _truncate_preview(lines: Sequence[str]) -> str:
    if not lines:
        return ""
    output: list[str] = []
    byte_count = 0
    truncated = False
    marker_bytes = len((TRUNCATION_MARKER + "\n").encode("utf-8"))
    line_limit = max(1, MAX_PREVIEW_LINES - 1)
    byte_limit = max(1, MAX_PREVIEW_BYTES - marker_bytes)
    for line in lines:
        normalized = line.replace("\r\n", "\n").replace("\r", "\n")
        for physical_line in normalized.split("\n"):
            candidate = physical_line + "\n"
            candidate_bytes = len(candidate.encode("utf-8"))
            if len(output) >= line_limit or byte_count + candidate_bytes > byte_limit:
                truncated = True
                break
            output.append(candidate)
            byte_count += candidate_bytes
        if truncated:
            break
    if truncated:
        output.append(TRUNCATION_MARKER + "\n")
    result = "".join(output)
    if len(result.encode("utf-8")) > MAX_PREVIEW_BYTES:
        raise AssertionError("preview byte bound invariant violated")
    if len(result.splitlines()) > MAX_PREVIEW_LINES:
        raise AssertionError("preview line bound invariant violated")
    return result


def _finding(
    code: ConflictCode,
    severity: ConflictSeverity,
    message: str,
    *details: tuple[str, str],
) -> ConflictFinding:
    return ConflictFinding(code=code, severity=severity, message=message, details=tuple(details))


def _stable_id_set_hash(stable_ids: frozenset[str]) -> str:
    return _domain_hash(
        "CURRENT_STABLE_ID_SET",
        IDENTITY_VERSION,
        {"stable_ids": sorted(stable_ids)},
    )


def _count_provenance_entries(value: Any) -> int:
    if isinstance(value, Mapping):
        return len(value) + sum(_count_provenance_entries(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return len(value) + sum(_count_provenance_entries(item) for item in value)
    return 1


def _validate_relative_path(path: str) -> None:
    if not isinstance(path, str) or not path or len(path) > MAX_PATH_LENGTH or "\x00" in path:
        raise ValueError("invalid relative path")
    posix_path = PurePosixPath(path)
    windows_path = PureWindowsPath(path)
    if posix_path.root or windows_path.drive or windows_path.root:
        raise ValueError("absolute, rooted, or drive-qualified path forbidden")
    parts = tuple(part for part in re.split(r"[\\/]", path) if part not in ("", "."))
    if not parts or any(part == ".." for part in parts):
        raise ValueError("path traversal forbidden")


def _validate_stable_id(stable_id: str) -> None:
    if (
        not isinstance(stable_id, str)
        or not stable_id
        or len(stable_id) > MAX_STABLE_ID_LENGTH
        or not _STABLE_ID_RE.fullmatch(stable_id)
    ):
        raise ValueError("invalid stable ID")


def _validate_revision(revision: str) -> None:
    if not isinstance(revision, str) or not _REVISION_RE.fullmatch(revision):
        raise ValueError("invalid Vault revision")


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _domain_digest(domain: str, version: str, payload: Any) -> str:
    envelope = {"domain": domain, "version": version, "payload": payload}
    return hashlib.sha256(_canonical_json_bytes(envelope)).hexdigest()


def _domain_hash(domain: str, version: str, payload: Any) -> str:
    return "sha256:" + _domain_digest(domain, version, payload)


E9A_API_BINDINGS: Final[Mapping[str, Any]] = MappingProxyType({
    "KnowledgeChangeProposal": KnowledgeChangeProposal,
    "ValidationResult": ValidationResult,
    "ProposalOperation": ProposalOperation,
    "ValidationOutcome": ValidationOutcome,
    "ProposalValidator": ProposalValidator,
    "ProposedNoteContent": ProposedNoteContent,
    "compute_proposal_content_hash": compute_proposal_content_hash,
    "compute_proposal_instance_id": compute_proposal_instance_id,
    "create_proposal_from_untrusted": create_proposal_from_untrusted,
})


__all__ = [
    "CONTRACT_VERSION",
    "SEMANTIC_NORMALIZATION_VERSION",
    "MAX_SOURCE_BYTES",
    "MAX_TRUSTED_TEXT_CHARS",
    "MAX_PROPOSED_CONTENT_BYTES",
    "MAX_STABLE_IDS",
    "MAX_EVIDENCE_REFERENCES",
    "MAX_PROVENANCE_ENTRIES",
    "MAX_FINDINGS",
    "MAX_FULL_DIFF_BYTES",
    "MAX_PREVIEW_BYTES",
    "MAX_PREVIEW_LINES",
    "MAX_PATH_LENGTH",
    "MAX_STABLE_ID_LENGTH",
    "MAX_PROPOSED_SNAPSHOT_BYTES",
    "MAX_METADATA_PREVIEW_VALUE_BYTES",
    "MAX_VALIDATION_SNAPSHOT_DEPTH",
    "MAX_VALIDATION_SNAPSHOT_NODES",
    "MAX_VALIDATION_MAPPING_ENTRIES",
    "MAX_VALIDATION_SEQUENCE_ENTRIES",
    "MAX_VALIDATION_KEY_LENGTH",
    "MAX_VALIDATION_STRING_LENGTH",
    "TRUNCATION_MARKER",
    "ReviewStatus",
    "ConflictSeverity",
    "ConflictCode",
    "FrozenCanonicalValue",
    "ProposedContentSnapshot",
    "ConflictFinding",
    "LineEndingProfile",
    "RepresentationDelta",
    "TrustedTargetSnapshot",
    "CurrentKnowledgeState",
    "KnowledgeChangeReviewArtifact",
    "semantic_normalize_v1",
    "compute_source_byte_hash",
    "compute_text_raw_hash",
    "compute_semantic_text_hash",
    "create_trusted_target_snapshot",
    "analyze_review",
    "E9A_API_BINDINGS",
]
