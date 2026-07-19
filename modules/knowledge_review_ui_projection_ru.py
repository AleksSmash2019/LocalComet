"""Bounded, immutable, JSON-safe projections for knowledge review UI data.

This module is deliberately a one-way presentation boundary.  It accepts only
the real e9b/e9c immutable artifacts, copies their descriptive data into frozen
projection records, and materializes newly allocated JSON containers.  It does
not perform persistence, IPC, frontend, filesystem, network, or authority work.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
import json
from pathlib import PurePosixPath, PureWindowsPath
import re
from typing import Any, Final

from modules.knowledge_change_review_ru import (
    CONTRACT_VERSION as REVIEW_CONTRACT_VERSION,
    ConflictCode,
    ConflictFinding,
    ConflictSeverity,
    FrozenCanonicalValue,
    KnowledgeChangeReviewArtifact,
    LineEndingProfile,
    ProposedContentSnapshot,
    RepresentationDelta,
    ReviewStatus,
    compute_semantic_text_hash,
    compute_text_raw_hash,
)
from modules.knowledge_change_review_decision_ru import (
    CONTRACT_VERSION as DECISION_CONTRACT_VERSION,
    HumanReviewDecision,
    HumanReviewDecisionValue,
    HumanReviewerMetadata,
)


PROJECTION_CONTRACT_VERSION: Final[str] = "localcomet.knowledge-review-ui/1.0"

# All projection limits are intentionally tighter than the e9b source and the
# 4,194,304-byte full-diff ceiling.
MAX_TOTAL_JSON_BYTES: Final[int] = 262_144
MAX_SOURCE_BODY_BYTES: Final[int] = 1_048_576
MAX_SOURCE_DIFF_BYTES: Final[int] = 4_194_304
MAX_SOURCE_HUMAN_PREVIEW_BYTES: Final[int] = 32_768
MAX_SOURCE_HUMAN_PREVIEW_LINES: Final[int] = 400
MAX_BODY_PREVIEW_BYTES: Final[int] = 16_384
MAX_BODY_PREVIEW_LINES: Final[int] = 200
MAX_DIFF_PREVIEW_BYTES: Final[int] = 16_384
MAX_DIFF_PREVIEW_LINES: Final[int] = 200
MAX_HUMAN_PREVIEW_BYTES: Final[int] = 8_192
MAX_HUMAN_PREVIEW_LINES: Final[int] = 120
MAX_FINDING_MESSAGE_BYTES: Final[int] = 2_048
MAX_FINDING_MESSAGE_LINES: Final[int] = 40
MAX_METADATA_COLLECTION_ITEMS: Final[int] = 128
MAX_SOURCE_COLLECTION_ITEMS: Final[int] = 4_096
MAX_PROJECTED_FINDINGS: Final[int] = 16
MAX_SOURCE_FINDINGS: Final[int] = 256
MAX_PROJECTED_FINDING_DETAILS: Final[int] = 16
MAX_SOURCE_FINDING_DETAILS: Final[int] = 256
MAX_VALIDATION_DEPTH: Final[int] = 16
MAX_VALIDATION_NODES: Final[int] = 1_024
MAX_VALIDATION_MAPPING_ITEMS: Final[int] = 128
MAX_VALIDATION_SEQUENCE_ITEMS: Final[int] = 128
MAX_VALIDATION_KEY_CHARS: Final[int] = 256
MAX_VALIDATION_KEY_BYTES: Final[int] = 1_024
MAX_VALIDATION_STRING_CHARS: Final[int] = 8_192
MAX_VALIDATION_STRING_BYTES: Final[int] = 32_768
MAX_GENERAL_STRING_CHARS: Final[int] = 8_192
MAX_GENERAL_STRING_BYTES: Final[int] = 32_768
MAX_SOURCE_PATH_CHARS: Final[int] = 512
MAX_SOURCE_PATH_BYTES: Final[int] = 2_048
MAX_SAFE_JSON_INTEGER: Final[int] = 9_007_199_254_740_991
MAX_MATERIALIZED_STRING_CHARS: Final[int] = 32_768
MAX_MATERIALIZED_STRING_BYTES: Final[int] = 32_768
MAX_MATERIALIZED_ARRAY_ITEMS: Final[int] = 4_096
MAX_MATERIALIZED_NODES: Final[int] = 8_192

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROPOSAL_ID_RE = re.compile(r"^kprop:[0-9a-f]{64}$")
_REVIEW_ID_RE = re.compile(r"^kreview:[0-9a-f]{64}$")
_CHANGE_ID_RE = re.compile(r"^kchange:[0-9a-f]{64}$")
_DECISION_ID_RE = re.compile(r"^kdecision:[0-9a-f]{64}$")
_STABLE_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_OPERATIONS: Final[frozenset[str]] = frozenset(
    {
        "UPDATE_EXISTING",
        "CREATE_NEW",
        "DELETE",
        "MOVE",
        "RENAME",
        "SUPERSEDE",
    }
)
_VALIDATION_OUTCOMES: Final[frozenset[str]] = frozenset(
    {"VALID", "INVALID", "STALE"}
)


class ProjectionKind(str, Enum):
    KNOWLEDGE_CHANGE_REVIEW = "KNOWLEDGE_CHANGE_REVIEW"
    KNOWLEDGE_CHANGE_REVIEW_SUMMARY = "KNOWLEDGE_CHANGE_REVIEW_SUMMARY"
    HUMAN_REVIEW_DECISION = "HUMAN_REVIEW_DECISION"


class ProjectionRejectionCode(str, Enum):
    WRONG_REVIEW_ARTIFACT_TYPE = "WRONG_REVIEW_ARTIFACT_TYPE"
    WRONG_DECISION_TYPE = "WRONG_DECISION_TYPE"
    WRONG_PROJECTION_TYPE = "WRONG_PROJECTION_TYPE"
    UNSUPPORTED_REVIEW_CONTRACT = "UNSUPPORTED_REVIEW_CONTRACT"
    UNSUPPORTED_DECISION_CONTRACT = "UNSUPPORTED_DECISION_CONTRACT"
    INVALID_REVIEW_ARTIFACT = "INVALID_REVIEW_ARTIFACT"
    INVALID_DECISION_ARTIFACT = "INVALID_DECISION_ARTIFACT"
    INVALID_NESTED_TYPE = "INVALID_NESTED_TYPE"
    INVALID_IDENTITY = "INVALID_IDENTITY"
    INVALID_UTF8 = "INVALID_UTF8"
    UNSAFE_SOURCE_PATH = "UNSAFE_SOURCE_PATH"
    PATH_LIMIT_EXCEEDED = "PATH_LIMIT_EXCEEDED"
    STRING_LIMIT_EXCEEDED = "STRING_LIMIT_EXCEEDED"
    COLLECTION_LIMIT_EXCEEDED = "COLLECTION_LIMIT_EXCEEDED"
    VALIDATION_DEPTH_EXCEEDED = "VALIDATION_DEPTH_EXCEEDED"
    VALIDATION_NODE_LIMIT_EXCEEDED = "VALIDATION_NODE_LIMIT_EXCEEDED"
    VALIDATION_MAPPING_LIMIT_EXCEEDED = "VALIDATION_MAPPING_LIMIT_EXCEEDED"
    VALIDATION_SEQUENCE_LIMIT_EXCEEDED = "VALIDATION_SEQUENCE_LIMIT_EXCEEDED"
    INVALID_VALIDATION_VALUE = "INVALID_VALIDATION_VALUE"
    BLOCKED_CHANGE_MATERIAL_EXPOSED = "BLOCKED_CHANGE_MATERIAL_EXPOSED"
    INCONSISTENT_DIFF_MATERIAL = "INCONSISTENT_DIFF_MATERIAL"
    PROJECTION_JSON_LIMIT_EXCEEDED = "PROJECTION_JSON_LIMIT_EXCEEDED"
    SERIALIZATION_FAILED = "SERIALIZATION_FAILED"


class ProjectionRejected(ValueError):
    """Deterministic typed rejection from the projection boundary."""

    def __init__(self, code: ProjectionRejectionCode, field_name: str = "") -> None:
        if type(code) is not ProjectionRejectionCode:
            raise TypeError("code must be ProjectionRejectionCode")
        if type(field_name) is not str:
            raise TypeError("field_name must be string")
        self.code = code
        self.field_name = field_name
        message = code.value if not field_name else f"{code.value}:{field_name}"
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class BoundedTextPreview:
    preview_text: str
    is_preview: bool
    truncated: bool
    original_utf8_bytes: int
    original_line_count: int
    preview_utf8_bytes: int
    preview_line_count: int


@dataclass(frozen=True, slots=True)
class ProposedBodyProjection:
    preview_text: str
    is_preview: bool
    truncated: bool
    original_utf8_bytes: int
    original_line_count: int
    preview_utf8_bytes: int
    preview_line_count: int
    raw_text_hash: str
    semantic_text_hash: str


@dataclass(frozen=True, slots=True)
class BoundedStringCollection:
    items: tuple[str, ...]
    original_count: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class ValidationMappingEntryProjection:
    key: str
    value: "ValidationValueProjection"


@dataclass(frozen=True, slots=True)
class ValidationValueProjection:
    type_tag: str
    scalar_value: str | int | bool | None
    mapping_items: tuple[ValidationMappingEntryProjection, ...]
    sequence_items: tuple["ValidationValueProjection", ...]


@dataclass(frozen=True, slots=True)
class ValidationSnapshotProjection:
    value: ValidationValueProjection
    truncated: bool


@dataclass(frozen=True, slots=True)
class SourceValidationFindingProjection:
    code: str
    severity: str


@dataclass(frozen=True, slots=True)
class BoundedSourceValidationFindings:
    items: tuple[SourceValidationFindingProjection, ...]
    original_count: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class FindingDetailProjection:
    key: str
    value: str


@dataclass(frozen=True, slots=True)
class BoundedFindingDetails:
    items: tuple[FindingDetailProjection, ...]
    original_count: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class ReviewFindingProjection:
    code: str
    severity: str
    message: BoundedTextPreview
    details: BoundedFindingDetails


@dataclass(frozen=True, slots=True)
class BoundedReviewFindings:
    items: tuple[ReviewFindingProjection, ...]
    original_count: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class LineEndingProfileProjection:
    crlf_count: int
    lf_count: int
    cr_count: int
    terminal_newline: bool


@dataclass(frozen=True, slots=True)
class RepresentationDeltaProjection:
    before_present: bool
    after_present: bool
    before_line_endings: LineEndingProfileProjection | None
    after_line_endings: LineEndingProfileProjection
    terminal_newline_changed: bool
    after_source_bytes_known: bool
    source_bytes_changed_text_identical: bool
    raw_text_changed_semantic_equal: bool
    semantic_content_changed: bool
    identity: str


@dataclass(frozen=True, slots=True)
class ProposedContentProjection:
    title: str
    body_text: ProposedBodyProjection
    type: str
    status: str
    knowledge_layer: str
    evidence_class: str
    authority: str
    canonical: bool
    canonical_scope: str | None
    aliases: BoundedStringCollection
    releases: BoundedStringCollection
    source_paths: BoundedStringCollection
    evidence_refs: BoundedStringCollection
    supersedes: BoundedStringCollection
    superseded_by: BoundedStringCollection
    updated: str
    last_reviewed: str
    verified_at: str | None


@dataclass(frozen=True, slots=True)
class DiffProjection:
    preview: BoundedTextPreview
    preview_truncated: bool
    preview_is_full_diff: bool
    full_diff_present: bool
    full_diff_hash: str
    full_diff_utf8_bytes: int


@dataclass(frozen=True, slots=True)
class KnowledgeChangeReviewProjection:
    projection_contract: str
    kind: ProjectionKind
    contract_version: str
    status: str
    proposal_id: str
    proposal_content_hash: str
    operation: str
    target_stable_id: str
    expected_vault_revision: str
    observed_vault_revision: str
    validation_outcome: str
    validation_snapshot: ValidationSnapshotProjection
    source_validation_findings: BoundedSourceValidationFindings
    stable_id_set_hash: str
    proposed_content_snapshot: ProposedContentProjection
    findings: BoundedReviewFindings
    before_source_byte_hash: str | None
    before_text_raw_hash: str | None
    before_semantic_text_hash: str | None
    proposed_text_raw_hash: str
    proposed_semantic_text_hash: str
    diff: DiffProjection | None
    representation_delta: RepresentationDeltaProjection | None
    change_identity: str | None
    review_artifact_identity: str
    human_review_preview: BoundedTextPreview


@dataclass(frozen=True, slots=True)
class KnowledgeChangeReviewSummaryProjection:
    projection_contract: str
    kind: ProjectionKind
    contract_version: str
    status: str
    blocked: bool
    proposal_id: str
    target_stable_id: str
    operation: str
    expected_vault_revision: str
    observed_vault_revision: str
    review_artifact_identity: str
    change_identity: str | None
    finding_count: int
    normal_change_material_present: bool
    detail_projection_truncated: bool


@dataclass(frozen=True, slots=True)
class HumanReviewerMetadataProjection:
    actor_identifier: str
    display_name: str
    source: str


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionProjection:
    projection_contract: str
    kind: ProjectionKind
    contract_version: str
    review_contract_version: str
    review_status: str
    proposal_id: str
    review_artifact_identity: str
    change_identity: str | None
    observed_vault_revision: str
    decision: str
    comment: str
    actor: HumanReviewerMetadataProjection
    decision_identity: str
    hard_stop: bool
    review_decision_only: bool
    actor_metadata_evidence_only: bool
    human_identity_authenticated: bool
    grants_write_authority: bool
    grants_vault_write_authority: bool
    grants_persistence_authority: bool
    grants_publication_authority: bool
    grants_merge_authority: bool
    grants_rebase_authority: bool
    grants_execution_authority: bool
    grants_policy_authority: bool
    grants_model_gateway_authority: bool
    grants_tauri_frontend_authority: bool
    grants_automatic_approval_authority: bool


@dataclass(slots=True)
class _ValidationBudget:
    nodes: int = 0


@dataclass(slots=True)
class _MaterializationBudget:
    nodes: int = 0


def _reject(code: ProjectionRejectionCode, field_name: str = "") -> None:
    raise ProjectionRejected(code, field_name)


def _encoded_utf8(value: str, field_name: str) -> bytes:
    if type(value) is not str:
        _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, field_name)
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError:
        _reject(ProjectionRejectionCode.INVALID_UTF8, field_name)
    raise AssertionError("unreachable")


def _validate_string(
    value: str,
    field_name: str,
    *,
    max_chars: int = MAX_GENERAL_STRING_CHARS,
    max_bytes: int = MAX_GENERAL_STRING_BYTES,
) -> bytes:
    encoded = _encoded_utf8(value, field_name)
    if len(value) > max_chars or len(encoded) > max_bytes:
        _reject(ProjectionRejectionCode.STRING_LIMIT_EXCEEDED, field_name)
    return encoded


def _validate_optional_string(value: str | None, field_name: str) -> None:
    if value is None:
        return
    _validate_string(value, field_name)


def _validate_pattern(value: Any, pattern: re.Pattern[str], field_name: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        _reject(ProjectionRejectionCode.INVALID_IDENTITY, field_name)
    return value


def _validate_optional_hash(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _validate_pattern(value, _SHA256_RE, field_name)


def _line_count(value: str) -> int:
    return len(value.splitlines())


def _bounded_prefix(
    value: str,
    field_name: str,
    *,
    max_bytes: int,
    max_lines: int,
    force_incomplete: bool = False,
) -> BoundedTextPreview:
    encoded = _encoded_utf8(value, field_name)
    pieces = value.splitlines(keepends=True)
    candidate = "".join(pieces[:max_lines]) if len(pieces) > max_lines else value
    candidate_bytes = candidate.encode("utf-8")
    if len(candidate_bytes) > max_bytes:
        candidate = candidate_bytes[:max_bytes].decode("utf-8", errors="ignore")
    if force_incomplete and value and candidate == value:
        candidate = candidate[:-1]
    preview_bytes = candidate.encode("utf-8")
    return BoundedTextPreview(
        preview_text=candidate,
        is_preview=True,
        truncated=candidate != value,
        original_utf8_bytes=len(encoded),
        original_line_count=_line_count(value),
        preview_utf8_bytes=len(preview_bytes),
        preview_line_count=_line_count(candidate),
    )


def _project_string_collection(
    value: tuple[str, ...],
    field_name: str,
    *,
    source_paths: bool = False,
) -> BoundedStringCollection:
    if type(value) is not tuple:
        _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, field_name)
    if len(value) > MAX_SOURCE_COLLECTION_ITEMS:
        _reject(ProjectionRejectionCode.COLLECTION_LIMIT_EXCEEDED, field_name)
    for index, item in enumerate(value):
        item_field = f"{field_name}[{index}]"
        if source_paths:
            _validate_source_path(item, item_field)
        else:
            _validate_string(item, item_field)
    kept = tuple(item for item in value[:MAX_METADATA_COLLECTION_ITEMS])
    return BoundedStringCollection(
        items=kept,
        original_count=len(value),
        truncated=len(value) > MAX_METADATA_COLLECTION_ITEMS,
    )


def _validate_source_path(value: str, field_name: str) -> None:
    encoded = _encoded_utf8(value, field_name)
    if len(value) > MAX_SOURCE_PATH_CHARS or len(encoded) > MAX_SOURCE_PATH_BYTES:
        _reject(ProjectionRejectionCode.PATH_LIMIT_EXCEEDED, field_name)
    if not value or "\x00" in value:
        _reject(ProjectionRejectionCode.UNSAFE_SOURCE_PATH, field_name)
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or bool(windows.root)
        or value.startswith("/")
        or value.startswith("\\")
    ):
        _reject(ProjectionRejectionCode.UNSAFE_SOURCE_PATH, field_name)
    segments = value.replace("\\", "/").split("/")
    if any(
        segment == ".."
        or segment.rstrip(" ") == ".."
        or segment.rstrip(" .") == ".."
        for segment in segments
    ):
        _reject(ProjectionRejectionCode.UNSAFE_SOURCE_PATH, field_name)
    meaningful_segments = tuple(
        segment for segment in segments if segment not in ("", ".")
    )
    if not meaningful_segments:
        _reject(ProjectionRejectionCode.UNSAFE_SOURCE_PATH, field_name)


def _project_validation_value(
    value: FrozenCanonicalValue,
    *,
    depth: int,
    budget: _ValidationBudget,
    active: set[int],
) -> ValidationValueProjection:
    if type(value) is not FrozenCanonicalValue:
        _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, "validation_snapshot")
    if depth > MAX_VALIDATION_DEPTH:
        _reject(ProjectionRejectionCode.VALIDATION_DEPTH_EXCEEDED, "validation_snapshot")
    budget.nodes += 1
    if budget.nodes > MAX_VALIDATION_NODES:
        _reject(ProjectionRejectionCode.VALIDATION_NODE_LIMIT_EXCEEDED, "validation_snapshot")
    object_id = id(value)
    if object_id in active:
        _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.cycle")
    active.add(object_id)
    try:
        if type(value.type_tag) is not str:
            _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.type_tag")
        if type(value.mapping_items) is not tuple or type(value.sequence_items) is not tuple:
            _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.channels")
        tag = value.type_tag
        if tag == "mapping":
            if value.scalar_value is not None or value.sequence_items:
                _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.mapping")
            if len(value.mapping_items) > MAX_VALIDATION_MAPPING_ITEMS:
                _reject(
                    ProjectionRejectionCode.VALIDATION_MAPPING_LIMIT_EXCEEDED,
                    "validation_snapshot.mapping",
                )
            projected_entries: list[ValidationMappingEntryProjection] = []
            previous_key: str | None = None
            for item in value.mapping_items:
                if type(item) is not tuple or len(item) != 2:
                    _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.mapping")
                key, child = item
                if type(key) is not str:
                    _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.key")
                key_bytes = _encoded_utf8(key, "validation_snapshot.key")
                if len(key) > MAX_VALIDATION_KEY_CHARS or len(key_bytes) > MAX_VALIDATION_KEY_BYTES:
                    _reject(ProjectionRejectionCode.STRING_LIMIT_EXCEEDED, "validation_snapshot.key")
                if previous_key is not None and key <= previous_key:
                    _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.key_order")
                previous_key = key
                projected_entries.append(
                    ValidationMappingEntryProjection(
                        key=key,
                        value=_project_validation_value(
                            child,
                            depth=depth + 1,
                            budget=budget,
                            active=active,
                        ),
                    )
                )
            return ValidationValueProjection(
                type_tag="mapping",
                scalar_value=None,
                mapping_items=tuple(projected_entries),
                sequence_items=(),
            )
        if tag == "sequence":
            if value.scalar_value is not None or value.mapping_items:
                _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.sequence")
            if len(value.sequence_items) > MAX_VALIDATION_SEQUENCE_ITEMS:
                _reject(
                    ProjectionRejectionCode.VALIDATION_SEQUENCE_LIMIT_EXCEEDED,
                    "validation_snapshot.sequence",
                )
            return ValidationValueProjection(
                type_tag="sequence",
                scalar_value=None,
                mapping_items=(),
                sequence_items=tuple(
                    _project_validation_value(
                        child,
                        depth=depth + 1,
                        budget=budget,
                        active=active,
                    )
                    for child in value.sequence_items
                ),
            )
        if value.mapping_items or value.sequence_items:
            _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.scalar")
        scalar = value.scalar_value
        if tag == "null":
            if scalar is not None:
                _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.null")
        elif tag == "bool":
            if type(scalar) is not bool:
                _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.bool")
        elif tag == "int":
            if type(scalar) is not int or abs(scalar) > MAX_SAFE_JSON_INTEGER:
                _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.int")
        elif tag == "string":
            if type(scalar) is not str:
                _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.string")
            _validate_string(
                scalar,
                "validation_snapshot.string",
                max_chars=MAX_VALIDATION_STRING_CHARS,
                max_bytes=MAX_VALIDATION_STRING_BYTES,
            )
        else:
            _reject(ProjectionRejectionCode.INVALID_VALIDATION_VALUE, "validation_snapshot.type_tag")
        return ValidationValueProjection(
            type_tag=tag,
            scalar_value=scalar,
            mapping_items=(),
            sequence_items=(),
        )
    finally:
        active.remove(object_id)


def _project_source_validation_findings(
    value: tuple[tuple[str, str], ...],
) -> BoundedSourceValidationFindings:
    if type(value) is not tuple:
        _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, "source_validation_findings")
    if len(value) > MAX_SOURCE_FINDINGS:
        _reject(ProjectionRejectionCode.COLLECTION_LIMIT_EXCEEDED, "source_validation_findings")
    projected: list[SourceValidationFindingProjection] = []
    for index, item in enumerate(value):
        if type(item) is not tuple or len(item) != 2:
            _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, f"source_validation_findings[{index}]")
        code, severity = item
        _validate_string(code, f"source_validation_findings[{index}].code")
        _validate_string(severity, f"source_validation_findings[{index}].severity")
        if index < MAX_METADATA_COLLECTION_ITEMS:
            projected.append(SourceValidationFindingProjection(code=code, severity=severity))
    return BoundedSourceValidationFindings(
        items=tuple(projected),
        original_count=len(value),
        truncated=len(value) > MAX_METADATA_COLLECTION_ITEMS,
    )


def _project_finding_details(
    value: tuple[tuple[str, str], ...],
    finding_index: int,
) -> BoundedFindingDetails:
    if type(value) is not tuple:
        _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, f"findings[{finding_index}].details")
    if len(value) > MAX_SOURCE_FINDING_DETAILS:
        _reject(ProjectionRejectionCode.COLLECTION_LIMIT_EXCEEDED, f"findings[{finding_index}].details")
    projected: list[FindingDetailProjection] = []
    for detail_index, item in enumerate(value):
        field_name = f"findings[{finding_index}].details[{detail_index}]"
        if type(item) is not tuple or len(item) != 2:
            _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, field_name)
        key, detail_value = item
        _validate_string(key, f"{field_name}.key")
        _validate_string(detail_value, f"{field_name}.value")
        if detail_index < MAX_PROJECTED_FINDING_DETAILS:
            projected.append(FindingDetailProjection(key=key, value=detail_value))
    return BoundedFindingDetails(
        items=tuple(projected),
        original_count=len(value),
        truncated=len(value) > MAX_PROJECTED_FINDING_DETAILS,
    )


def _project_review_findings(value: tuple[ConflictFinding, ...]) -> BoundedReviewFindings:
    if type(value) is not tuple:
        _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, "findings")
    if len(value) > MAX_SOURCE_FINDINGS:
        _reject(ProjectionRejectionCode.COLLECTION_LIMIT_EXCEEDED, "findings")
    projected: list[ReviewFindingProjection] = []
    for index, finding in enumerate(value):
        if type(finding) is not ConflictFinding:
            _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, f"findings[{index}]")
        if type(finding.code) is not ConflictCode or type(finding.severity) is not ConflictSeverity:
            _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, f"findings[{index}].enum")
        _validate_string(finding.code.value, f"findings[{index}].code")
        _validate_string(finding.severity.value, f"findings[{index}].severity")
        message = _bounded_prefix(
            finding.message,
            f"findings[{index}].message",
            max_bytes=MAX_FINDING_MESSAGE_BYTES,
            max_lines=MAX_FINDING_MESSAGE_LINES,
        )
        details = _project_finding_details(finding.details, index)
        if index < MAX_PROJECTED_FINDINGS:
            projected.append(
                ReviewFindingProjection(
                    code=finding.code.value,
                    severity=finding.severity.value,
                    message=message,
                    details=details,
                )
            )
    return BoundedReviewFindings(
        items=tuple(projected),
        original_count=len(value),
        truncated=len(value) > MAX_PROJECTED_FINDINGS,
    )


def _project_line_endings(
    value: LineEndingProfile,
    field_name: str,
) -> LineEndingProfileProjection:
    if type(value) is not LineEndingProfile:
        _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, field_name)
    for name in ("crlf_count", "lf_count", "cr_count"):
        count = getattr(value, name)
        if type(count) is not int or count < 0 or count > MAX_SAFE_JSON_INTEGER:
            _reject(ProjectionRejectionCode.INVALID_REVIEW_ARTIFACT, f"{field_name}.{name}")
    if type(value.terminal_newline) is not bool:
        _reject(ProjectionRejectionCode.INVALID_REVIEW_ARTIFACT, f"{field_name}.terminal_newline")
    return LineEndingProfileProjection(
        crlf_count=value.crlf_count,
        lf_count=value.lf_count,
        cr_count=value.cr_count,
        terminal_newline=value.terminal_newline,
    )


def _project_representation_delta(
    value: RepresentationDelta,
) -> RepresentationDeltaProjection:
    if type(value) is not RepresentationDelta:
        _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, "representation_delta")
    boolean_fields = (
        "before_present",
        "after_present",
        "terminal_newline_changed",
        "after_source_bytes_known",
        "source_bytes_changed_text_identical",
        "raw_text_changed_semantic_equal",
        "semantic_content_changed",
    )
    for name in boolean_fields:
        if type(getattr(value, name)) is not bool:
            _reject(ProjectionRejectionCode.INVALID_REVIEW_ARTIFACT, f"representation_delta.{name}")
    if value.before_present != (value.before_line_endings is not None):
        _reject(ProjectionRejectionCode.INVALID_REVIEW_ARTIFACT, "representation_delta.before_line_endings")
    before = (
        None
        if value.before_line_endings is None
        else _project_line_endings(value.before_line_endings, "representation_delta.before_line_endings")
    )
    after = _project_line_endings(value.after_line_endings, "representation_delta.after_line_endings")
    identity = _validate_pattern(value.identity, _SHA256_RE, "representation_delta.identity")
    return RepresentationDeltaProjection(
        before_present=value.before_present,
        after_present=value.after_present,
        before_line_endings=before,
        after_line_endings=after,
        terminal_newline_changed=value.terminal_newline_changed,
        after_source_bytes_known=value.after_source_bytes_known,
        source_bytes_changed_text_identical=value.source_bytes_changed_text_identical,
        raw_text_changed_semantic_equal=value.raw_text_changed_semantic_equal,
        semantic_content_changed=value.semantic_content_changed,
        identity=identity,
    )


def _project_proposed_content(
    value: ProposedContentSnapshot,
    *,
    proposed_raw_hash: str,
    proposed_semantic_hash: str,
) -> ProposedContentProjection:
    if type(value) is not ProposedContentSnapshot:
        _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, "proposed_content_snapshot")
    for name in (
        "title",
        "type",
        "status",
        "knowledge_layer",
        "evidence_class",
        "authority",
        "updated",
        "last_reviewed",
    ):
        _validate_string(getattr(value, name), f"proposed_content_snapshot.{name}")
    if type(value.canonical) is not bool:
        _reject(ProjectionRejectionCode.INVALID_REVIEW_ARTIFACT, "proposed_content_snapshot.canonical")
    _validate_optional_string(value.canonical_scope, "proposed_content_snapshot.canonical_scope")
    _validate_optional_string(value.verified_at, "proposed_content_snapshot.verified_at")
    body_preview = _bounded_prefix(
        value.body_text,
        "proposed_content_snapshot.body_text",
        max_bytes=MAX_BODY_PREVIEW_BYTES,
        max_lines=MAX_BODY_PREVIEW_LINES,
    )
    body = ProposedBodyProjection(
        preview_text=body_preview.preview_text,
        is_preview=body_preview.is_preview,
        truncated=body_preview.truncated,
        original_utf8_bytes=body_preview.original_utf8_bytes,
        original_line_count=body_preview.original_line_count,
        preview_utf8_bytes=body_preview.preview_utf8_bytes,
        preview_line_count=body_preview.preview_line_count,
        raw_text_hash=proposed_raw_hash,
        semantic_text_hash=proposed_semantic_hash,
    )
    return ProposedContentProjection(
        title=value.title,
        body_text=body,
        type=value.type,
        status=value.status,
        knowledge_layer=value.knowledge_layer,
        evidence_class=value.evidence_class,
        authority=value.authority,
        canonical=value.canonical,
        canonical_scope=value.canonical_scope,
        aliases=_project_string_collection(value.aliases, "proposed_content_snapshot.aliases"),
        releases=_project_string_collection(value.releases, "proposed_content_snapshot.releases"),
        source_paths=_project_string_collection(
            value.source_paths,
            "proposed_content_snapshot.source_paths",
            source_paths=True,
        ),
        evidence_refs=_project_string_collection(
            value.evidence_refs,
            "proposed_content_snapshot.evidence_refs",
        ),
        supersedes=_project_string_collection(value.supersedes, "proposed_content_snapshot.supersedes"),
        superseded_by=_project_string_collection(
            value.superseded_by,
            "proposed_content_snapshot.superseded_by",
        ),
        updated=value.updated,
        last_reviewed=value.last_reviewed,
        verified_at=value.verified_at,
    )


def _project_diff(artifact: KnowledgeChangeReviewArtifact) -> DiffProjection | None:
    source_diff = artifact.deterministic_text_diff
    source_hash = artifact.deterministic_text_diff_hash
    if source_diff is None and source_hash is None:
        return None
    if type(source_diff) is not str or type(source_hash) is not str:
        _reject(ProjectionRejectionCode.INCONSISTENT_DIFF_MATERIAL, "deterministic_text_diff")
    _validate_pattern(source_hash, _SHA256_RE, "deterministic_text_diff_hash")
    full_bytes = _encoded_utf8(source_diff, "deterministic_text_diff")
    if len(full_bytes) > MAX_SOURCE_DIFF_BYTES:
        _reject(ProjectionRejectionCode.STRING_LIMIT_EXCEEDED, "deterministic_text_diff")
    preview = _bounded_prefix(
        source_diff,
        "deterministic_text_diff",
        max_bytes=MAX_DIFF_PREVIEW_BYTES,
        max_lines=MAX_DIFF_PREVIEW_LINES,
        force_incomplete=True,
    )
    return DiffProjection(
        preview=preview,
        preview_truncated=preview.truncated,
        preview_is_full_diff=False,
        full_diff_present=True,
        full_diff_hash=source_hash,
        full_diff_utf8_bytes=len(full_bytes),
    )


def project_knowledge_change_review(
    artifact: KnowledgeChangeReviewArtifact,
) -> KnowledgeChangeReviewProjection:
    """Project one exact real e9b review artifact into bounded UI evidence."""
    if type(artifact) is not KnowledgeChangeReviewArtifact:
        _reject(ProjectionRejectionCode.WRONG_REVIEW_ARTIFACT_TYPE)
    if artifact.contract_version != REVIEW_CONTRACT_VERSION:
        _reject(ProjectionRejectionCode.UNSUPPORTED_REVIEW_CONTRACT)
    if type(artifact.status) is not ReviewStatus:
        _reject(ProjectionRejectionCode.INVALID_REVIEW_ARTIFACT, "status")
    _validate_pattern(artifact.proposal_id, _PROPOSAL_ID_RE, "proposal_id")
    _validate_pattern(artifact.proposal_content_hash, _SHA256_RE, "proposal_content_hash")
    if type(artifact.operation) is not str or artifact.operation not in _OPERATIONS:
        _reject(ProjectionRejectionCode.INVALID_REVIEW_ARTIFACT, "operation")
    if (
        type(artifact.target_stable_id) is not str
        or len(artifact.target_stable_id) > 128
        or _STABLE_ID_RE.fullmatch(artifact.target_stable_id) is None
    ):
        _reject(ProjectionRejectionCode.INVALID_REVIEW_ARTIFACT, "target_stable_id")
    _validate_pattern(artifact.expected_vault_revision, _SHA256_RE, "expected_vault_revision")
    _validate_pattern(artifact.observed_vault_revision, _SHA256_RE, "observed_vault_revision")
    if type(artifact.validation_outcome) is not str or artifact.validation_outcome not in _VALIDATION_OUTCOMES:
        _reject(ProjectionRejectionCode.INVALID_REVIEW_ARTIFACT, "validation_outcome")
    _validate_pattern(artifact.stable_id_set_hash, _SHA256_RE, "stable_id_set_hash")
    _validate_pattern(artifact.review_artifact_identity, _REVIEW_ID_RE, "review_artifact_identity")
    _validate_optional_hash(artifact.before_source_byte_hash, "before_source_byte_hash")
    _validate_optional_hash(artifact.before_text_raw_hash, "before_text_raw_hash")
    _validate_optional_hash(artifact.before_semantic_text_hash, "before_semantic_text_hash")
    proposed_raw_hash = _validate_pattern(
        artifact.proposed_text_raw_hash,
        _SHA256_RE,
        "proposed_text_raw_hash",
    )
    proposed_semantic_hash = _validate_pattern(
        artifact.proposed_semantic_text_hash,
        _SHA256_RE,
        "proposed_semantic_text_hash",
    )
    if type(artifact.proposed_content_snapshot) is not ProposedContentSnapshot:
        _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, "proposed_content_snapshot")
    body_text = artifact.proposed_content_snapshot.body_text
    body_bytes = _encoded_utf8(body_text, "proposed_content_snapshot.body_text")
    if len(body_bytes) > MAX_SOURCE_BODY_BYTES:
        _reject(
            ProjectionRejectionCode.STRING_LIMIT_EXCEEDED,
            "proposed_content_snapshot.body_text",
        )
    if compute_text_raw_hash(body_text) != proposed_raw_hash:
        _reject(ProjectionRejectionCode.INVALID_REVIEW_ARTIFACT, "proposed_text_raw_hash")
    if compute_semantic_text_hash(body_text) != proposed_semantic_hash:
        _reject(ProjectionRejectionCode.INVALID_REVIEW_ARTIFACT, "proposed_semantic_text_hash")

    blocked_material = (
        artifact.deterministic_text_diff,
        artifact.deterministic_text_diff_hash,
        artifact.representation_delta,
        artifact.change_identity,
    )
    if artifact.status is ReviewStatus.BLOCKED:
        if any(value is not None for value in blocked_material):
            _reject(ProjectionRejectionCode.BLOCKED_CHANGE_MATERIAL_EXPOSED)
    elif any(value is None for value in blocked_material):
        _reject(ProjectionRejectionCode.INCONSISTENT_DIFF_MATERIAL)

    change_identity = artifact.change_identity
    if change_identity is not None:
        _validate_pattern(change_identity, _CHANGE_ID_RE, "change_identity")
    diff = _project_diff(artifact)
    representation = (
        None
        if artifact.representation_delta is None
        else _project_representation_delta(artifact.representation_delta)
    )
    if (diff is None) != (representation is None):
        _reject(ProjectionRejectionCode.INCONSISTENT_DIFF_MATERIAL)

    validation = ValidationSnapshotProjection(
        value=_project_validation_value(
            artifact.validation_snapshot,
            depth=0,
            budget=_ValidationBudget(),
            active=set(),
        ),
        truncated=False,
    )
    human_preview_bytes = _encoded_utf8(
        artifact.human_review_preview,
        "human_review_preview",
    )
    if (
        len(human_preview_bytes) > MAX_SOURCE_HUMAN_PREVIEW_BYTES
        or _line_count(artifact.human_review_preview) > MAX_SOURCE_HUMAN_PREVIEW_LINES
    ):
        _reject(ProjectionRejectionCode.STRING_LIMIT_EXCEEDED, "human_review_preview")
    projection = KnowledgeChangeReviewProjection(
        projection_contract=PROJECTION_CONTRACT_VERSION,
        kind=ProjectionKind.KNOWLEDGE_CHANGE_REVIEW,
        contract_version=artifact.contract_version,
        status=artifact.status.value,
        proposal_id=artifact.proposal_id,
        proposal_content_hash=artifact.proposal_content_hash,
        operation=artifact.operation,
        target_stable_id=artifact.target_stable_id,
        expected_vault_revision=artifact.expected_vault_revision,
        observed_vault_revision=artifact.observed_vault_revision,
        validation_outcome=artifact.validation_outcome,
        validation_snapshot=validation,
        source_validation_findings=_project_source_validation_findings(
            artifact.source_validation_findings
        ),
        stable_id_set_hash=artifact.stable_id_set_hash,
        proposed_content_snapshot=_project_proposed_content(
            artifact.proposed_content_snapshot,
            proposed_raw_hash=proposed_raw_hash,
            proposed_semantic_hash=proposed_semantic_hash,
        ),
        findings=_project_review_findings(artifact.findings),
        before_source_byte_hash=artifact.before_source_byte_hash,
        before_text_raw_hash=artifact.before_text_raw_hash,
        before_semantic_text_hash=artifact.before_semantic_text_hash,
        proposed_text_raw_hash=proposed_raw_hash,
        proposed_semantic_text_hash=proposed_semantic_hash,
        diff=diff,
        representation_delta=representation,
        change_identity=change_identity,
        review_artifact_identity=artifact.review_artifact_identity,
        human_review_preview=_bounded_prefix(
            artifact.human_review_preview,
            "human_review_preview",
            max_bytes=MAX_HUMAN_PREVIEW_BYTES,
            max_lines=MAX_HUMAN_PREVIEW_LINES,
        ),
    )
    canonical_projection_json_bytes(projection)
    return projection


def _review_projection_detail_truncated(
    projection: KnowledgeChangeReviewProjection,
) -> bool:
    proposed = projection.proposed_content_snapshot
    collection_truncated = any(
        collection.truncated
        for collection in (
            proposed.aliases,
            proposed.releases,
            proposed.source_paths,
            proposed.evidence_refs,
            proposed.supersedes,
            proposed.superseded_by,
        )
    )
    finding_detail_truncated = any(
        finding.message.truncated or finding.details.truncated
        for finding in projection.findings.items
    )
    return any(
        (
            projection.validation_snapshot.truncated,
            projection.source_validation_findings.truncated,
            proposed.body_text.truncated,
            collection_truncated,
            projection.findings.truncated,
            finding_detail_truncated,
            projection.diff is not None and projection.diff.preview_truncated,
            projection.human_review_preview.truncated,
        )
    )


def project_knowledge_change_review_summary(
    artifact: KnowledgeChangeReviewArtifact,
) -> KnowledgeChangeReviewSummaryProjection:
    """Derive one bounded queue row from the accepted full review projection."""
    full = project_knowledge_change_review(artifact)
    blocked = full.status == ReviewStatus.BLOCKED.value
    normal_change_material_present = (
        full.change_identity is not None
        and full.diff is not None
        and full.representation_delta is not None
    )
    summary = KnowledgeChangeReviewSummaryProjection(
        projection_contract=full.projection_contract,
        kind=ProjectionKind.KNOWLEDGE_CHANGE_REVIEW_SUMMARY,
        contract_version=full.contract_version,
        status=full.status,
        blocked=blocked,
        proposal_id=full.proposal_id,
        target_stable_id=full.target_stable_id,
        operation=full.operation,
        expected_vault_revision=full.expected_vault_revision,
        observed_vault_revision=full.observed_vault_revision,
        review_artifact_identity=full.review_artifact_identity,
        change_identity=full.change_identity,
        finding_count=full.findings.original_count,
        normal_change_material_present=normal_change_material_present,
        detail_projection_truncated=_review_projection_detail_truncated(full),
    )
    canonical_projection_json_bytes(summary)
    return summary


def _validate_decision_text(
    value: str,
    field_name: str,
    *,
    max_chars: int,
    max_bytes: int,
    nonblank: bool = False,
) -> None:
    encoded = _validate_string(
        value,
        field_name,
        max_chars=max_chars,
        max_bytes=max_bytes,
    )
    if "\x00" in value or (nonblank and not value.strip()) or len(encoded) > max_bytes:
        _reject(ProjectionRejectionCode.INVALID_DECISION_ARTIFACT, field_name)


def project_human_review_decision(
    decision: HumanReviewDecision,
) -> HumanReviewDecisionProjection:
    """Project one exact real e9c decision as descriptive, no-authority evidence."""
    if type(decision) is not HumanReviewDecision:
        _reject(ProjectionRejectionCode.WRONG_DECISION_TYPE)
    if decision.contract_version != DECISION_CONTRACT_VERSION:
        _reject(ProjectionRejectionCode.UNSUPPORTED_DECISION_CONTRACT)
    if decision.review_contract_version != REVIEW_CONTRACT_VERSION:
        _reject(ProjectionRejectionCode.UNSUPPORTED_REVIEW_CONTRACT)
    if type(decision.review_status) is not ReviewStatus:
        _reject(ProjectionRejectionCode.INVALID_DECISION_ARTIFACT, "review_status")
    if type(decision.decision) is not HumanReviewDecisionValue:
        _reject(ProjectionRejectionCode.INVALID_DECISION_ARTIFACT, "decision")
    _validate_pattern(decision.proposal_id, _PROPOSAL_ID_RE, "proposal_id")
    _validate_pattern(decision.review_artifact_identity, _REVIEW_ID_RE, "review_artifact_identity")
    _validate_pattern(decision.observed_vault_revision, _SHA256_RE, "observed_vault_revision")
    _validate_pattern(decision.decision_identity, _DECISION_ID_RE, "decision_identity")
    if decision.change_identity is not None:
        _validate_pattern(decision.change_identity, _CHANGE_ID_RE, "change_identity")
    if decision.review_status is ReviewStatus.BLOCKED and decision.change_identity is not None:
        _reject(ProjectionRejectionCode.INVALID_DECISION_ARTIFACT, "change_identity")
    if decision.decision is HumanReviewDecisionValue.APPROVE and decision.change_identity is None:
        _reject(ProjectionRejectionCode.INVALID_DECISION_ARTIFACT, "decision")
    _validate_decision_text(
        decision.comment,
        "comment",
        max_chars=2_000,
        max_bytes=4_096,
        nonblank=decision.decision is HumanReviewDecisionValue.REQUEST_CHANGES,
    )
    if type(decision.actor) is not HumanReviewerMetadata:
        _reject(ProjectionRejectionCode.INVALID_NESTED_TYPE, "actor")
    _validate_decision_text(
        decision.actor.actor_identifier,
        "actor.actor_identifier",
        max_chars=256,
        max_bytes=512,
        nonblank=True,
    )
    _validate_decision_text(
        decision.actor.display_name,
        "actor.display_name",
        max_chars=256,
        max_bytes=512,
        nonblank=True,
    )
    _validate_decision_text(
        decision.actor.source,
        "actor.source",
        max_chars=128,
        max_bytes=256,
        nonblank=True,
    )
    expected_boundary = {
        "hard_stop": True,
        "review_decision_only": True,
        "actor_metadata_evidence_only": True,
        "human_identity_authenticated": False,
        "grants_write_authority": False,
        "grants_vault_write_authority": False,
        "grants_persistence_authority": False,
        "grants_publication_authority": False,
        "grants_merge_authority": False,
        "grants_rebase_authority": False,
        "grants_execution_authority": False,
        "grants_policy_authority": False,
        "grants_model_gateway_authority": False,
        "grants_tauri_frontend_authority": False,
        "grants_automatic_approval_authority": False,
    }
    for name, expected in expected_boundary.items():
        actual = getattr(decision, name)
        if type(actual) is not bool or actual is not expected:
            _reject(ProjectionRejectionCode.INVALID_DECISION_ARTIFACT, name)
    try:
        HumanReviewDecision.__post_init__(decision)
    except (AttributeError, TypeError, ValueError):
        _reject(ProjectionRejectionCode.INVALID_DECISION_ARTIFACT, "decision_identity")
    projection = HumanReviewDecisionProjection(
        projection_contract=PROJECTION_CONTRACT_VERSION,
        kind=ProjectionKind.HUMAN_REVIEW_DECISION,
        contract_version=decision.contract_version,
        review_contract_version=decision.review_contract_version,
        review_status=decision.review_status.value,
        proposal_id=decision.proposal_id,
        review_artifact_identity=decision.review_artifact_identity,
        change_identity=decision.change_identity,
        observed_vault_revision=decision.observed_vault_revision,
        decision=decision.decision.value,
        comment=decision.comment,
        actor=HumanReviewerMetadataProjection(
            actor_identifier=decision.actor.actor_identifier,
            display_name=decision.actor.display_name,
            source=decision.actor.source,
        ),
        decision_identity=decision.decision_identity,
        hard_stop=decision.hard_stop,
        review_decision_only=decision.review_decision_only,
        actor_metadata_evidence_only=decision.actor_metadata_evidence_only,
        human_identity_authenticated=decision.human_identity_authenticated,
        grants_write_authority=decision.grants_write_authority,
        grants_vault_write_authority=decision.grants_vault_write_authority,
        grants_persistence_authority=decision.grants_persistence_authority,
        grants_publication_authority=decision.grants_publication_authority,
        grants_merge_authority=decision.grants_merge_authority,
        grants_rebase_authority=decision.grants_rebase_authority,
        grants_execution_authority=decision.grants_execution_authority,
        grants_policy_authority=decision.grants_policy_authority,
        grants_model_gateway_authority=decision.grants_model_gateway_authority,
        grants_tauri_frontend_authority=decision.grants_tauri_frontend_authority,
        grants_automatic_approval_authority=decision.grants_automatic_approval_authority,
    )
    canonical_projection_json_bytes(projection)
    return projection


_PROJECTION_RECORD_TYPES: Final[tuple[type[Any], ...]] = (
    BoundedTextPreview,
    ProposedBodyProjection,
    BoundedStringCollection,
    ValidationMappingEntryProjection,
    ValidationValueProjection,
    ValidationSnapshotProjection,
    SourceValidationFindingProjection,
    BoundedSourceValidationFindings,
    FindingDetailProjection,
    BoundedFindingDetails,
    ReviewFindingProjection,
    BoundedReviewFindings,
    LineEndingProfileProjection,
    RepresentationDeltaProjection,
    ProposedContentProjection,
    DiffProjection,
    KnowledgeChangeReviewProjection,
    KnowledgeChangeReviewSummaryProjection,
    HumanReviewerMetadataProjection,
    HumanReviewDecisionProjection,
)
_ROOT_PROJECTION_TYPES: Final[tuple[type[Any], ...]] = (
    KnowledgeChangeReviewProjection,
    KnowledgeChangeReviewSummaryProjection,
    HumanReviewDecisionProjection,
)


def _materialize(
    value: Any,
    *,
    active: set[int] | None = None,
    budget: _MaterializationBudget | None = None,
) -> Any:
    if active is None:
        active = set()
    if budget is None:
        budget = _MaterializationBudget()
    budget.nodes += 1
    if budget.nodes > MAX_MATERIALIZED_NODES:
        _reject(ProjectionRejectionCode.SERIALIZATION_FAILED, "materialized_node_limit")
    value_type = type(value)
    if value is None or value_type is bool:
        return value
    if value_type is int:
        if abs(value) > MAX_SAFE_JSON_INTEGER:
            _reject(ProjectionRejectionCode.SERIALIZATION_FAILED, "integer_bound")
        return value
    if value_type is str:
        _validate_string(
            value,
            "materialized_string",
            max_chars=MAX_MATERIALIZED_STRING_CHARS,
            max_bytes=MAX_MATERIALIZED_STRING_BYTES,
        )
        return value
    if value_type is ProjectionKind:
        return value.value
    if value_type is tuple:
        if len(value) > MAX_MATERIALIZED_ARRAY_ITEMS:
            _reject(ProjectionRejectionCode.SERIALIZATION_FAILED, "array_bound")
        object_id = id(value)
        if object_id in active:
            _reject(ProjectionRejectionCode.SERIALIZATION_FAILED, "cycle")
        active.add(object_id)
        try:
            return [
                _materialize(item, active=active, budget=budget)
                for item in value
            ]
        finally:
            active.remove(object_id)
    if value_type in _PROJECTION_RECORD_TYPES:
        object_id = id(value)
        if object_id in active:
            _reject(ProjectionRejectionCode.SERIALIZATION_FAILED, "cycle")
        active.add(object_id)
        try:
            return {
                field.name: _materialize(
                    getattr(value, field.name),
                    active=active,
                    budget=budget,
                )
                for field in fields(value)
            }
        finally:
            active.remove(object_id)
    _reject(ProjectionRejectionCode.SERIALIZATION_FAILED, value_type.__name__)
    raise AssertionError("unreachable")


def materialize_json_value(
    projection: (
        KnowledgeChangeReviewProjection
        | KnowledgeChangeReviewSummaryProjection
        | HumanReviewDecisionProjection
    ),
) -> dict[str, Any]:
    """Return fresh standard-JSON containers for one supported projection."""
    if type(projection) not in _ROOT_PROJECTION_TYPES:
        _reject(ProjectionRejectionCode.WRONG_PROJECTION_TYPE)
    materialized = _materialize(projection)
    if type(materialized) is not dict:
        _reject(ProjectionRejectionCode.SERIALIZATION_FAILED)
    encoded = _canonical_json_value_bytes(materialized)
    if len(encoded) > MAX_TOTAL_JSON_BYTES:
        _reject(ProjectionRejectionCode.PROJECTION_JSON_LIMIT_EXCEEDED)
    return materialized


def _canonical_json_value_bytes(materialized: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            materialized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError):
        _reject(ProjectionRejectionCode.SERIALIZATION_FAILED)
    raise AssertionError("unreachable")


def canonical_projection_json_bytes(
    projection: (
        KnowledgeChangeReviewProjection
        | KnowledgeChangeReviewSummaryProjection
        | HumanReviewDecisionProjection
    ),
) -> bytes:
    """Return deterministic canonical UTF-8 JSON, subject to the hard byte cap."""
    materialized = materialize_json_value(projection)
    return _canonical_json_value_bytes(materialized)


__all__ = [
    "PROJECTION_CONTRACT_VERSION",
    "MAX_TOTAL_JSON_BYTES",
    "MAX_SOURCE_BODY_BYTES",
    "MAX_SOURCE_DIFF_BYTES",
    "MAX_SOURCE_HUMAN_PREVIEW_BYTES",
    "MAX_SOURCE_HUMAN_PREVIEW_LINES",
    "MAX_BODY_PREVIEW_BYTES",
    "MAX_BODY_PREVIEW_LINES",
    "MAX_DIFF_PREVIEW_BYTES",
    "MAX_DIFF_PREVIEW_LINES",
    "MAX_HUMAN_PREVIEW_BYTES",
    "MAX_HUMAN_PREVIEW_LINES",
    "MAX_METADATA_COLLECTION_ITEMS",
    "MAX_SOURCE_PATH_CHARS",
    "MAX_SAFE_JSON_INTEGER",
    "MAX_MATERIALIZED_STRING_CHARS",
    "MAX_MATERIALIZED_STRING_BYTES",
    "MAX_MATERIALIZED_ARRAY_ITEMS",
    "MAX_MATERIALIZED_NODES",
    "ProjectionKind",
    "ProjectionRejectionCode",
    "ProjectionRejected",
    "BoundedTextPreview",
    "ProposedBodyProjection",
    "BoundedStringCollection",
    "ValidationMappingEntryProjection",
    "ValidationValueProjection",
    "ValidationSnapshotProjection",
    "SourceValidationFindingProjection",
    "BoundedSourceValidationFindings",
    "FindingDetailProjection",
    "BoundedFindingDetails",
    "ReviewFindingProjection",
    "BoundedReviewFindings",
    "LineEndingProfileProjection",
    "RepresentationDeltaProjection",
    "ProposedContentProjection",
    "DiffProjection",
    "KnowledgeChangeReviewProjection",
    "KnowledgeChangeReviewSummaryProjection",
    "HumanReviewerMetadataProjection",
    "HumanReviewDecisionProjection",
    "project_knowledge_change_review",
    "project_knowledge_change_review_summary",
    "project_human_review_decision",
    "materialize_json_value",
    "canonical_projection_json_bytes",
]
