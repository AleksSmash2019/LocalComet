"""Knowledge Change Proposal Contract — v6.84.5.1e9a.

Model-independent, deterministic, proposal-only contract for untrusted agents to
propose changes to durable LocalComet knowledge without authority to modify the
canonical Vault.

This module implements:
- KnowledgeChangeProposal: versioned, bounded, canonicalized proposal structure
- ProposalValidator: deterministic validation against current Vault revision
- ValidationResult: immutable structured outcome (VALID/INVALID/STALE)
- No Vault writes, no publication path, no approval path, no persistent store.

Contract version: localcomet.knowledge-change-proposal / 1.0
Proposal identity prefix: kprop:
Supported operations: UPDATE_EXISTING, CREATE_NEW
Rejected operations: DELETE, MOVE, RENAME, SUPERSEDE (reserved, non-validating)
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from modules.knowledge_contract_ru import (
    KnowledgeAdapterError,
    KnowledgeErrorCode,
    _SHA256_RE,
    _VAULT_REVISION_RE,
    _bounded_integer,
    _contains_absolute_path,
    _freeze,
    _thaw,
)
from tools.validate_localcomet_vault import ID_RE, ValidationResult as VaultValidationResult

sys.dont_write_bytecode = True

CONTRACT_VERSION = "localcomet.knowledge-change-proposal/1.0"
PROPOSAL_ID_PREFIX = "kprop:"
PROPOSAL_ID_RE = re.compile(r"^kprop:[0-9a-f]{64}$")
_STABLE_ID_MAXLEN = 128
_PROPOSER_METADATA_MAXLEN = 512
_REASON_MAXLEN = 2048
_CONTENT_MAXLEN = 1_048_576
_EVIDENCE_REF_MAXLEN = 256
_MAX_EVIDENCE_REFS = 32
_MAX_TOTAL_PROPOSAL_BYTES = 2_097_152
_SUPERSEDE_RESERVED = "SUPERSEDE_RESERVED"


class ProposalOperation(str, Enum):
    UPDATE_EXISTING = "UPDATE_EXISTING"
    CREATE_NEW = "CREATE_NEW"
    DELETE = "DELETE"
    MOVE = "MOVE"
    RENAME = "RENAME"
    SUPERSEDE = "SUPERSEDE"


class ValidationOutcome(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    STALE = "STALE"


class ProposalValidationCode(str, Enum):
    OK = "OK"
    MISSING_CONTRACT_VERSION = "MISSING_CONTRACT_VERSION"
    UNSUPPORTED_CONTRACT_VERSION = "UNSUPPORTED_CONTRACT_VERSION"
    EMPTY_PROPOSAL_ID = "EMPTY_PROPOSAL_ID"
    MALFORMED_PROPOSAL_ID = "MALFORMED_PROPOSAL_ID"
    EMPTY_STABLE_ID = "EMPTY_STABLE_ID"
    MALFORMED_STABLE_ID = "MALFORMED_STABLE_ID"
    STABLE_ID_TOO_LONG = "STABLE_ID_TOO_LONG"
    MISSING_OPERATION = "MISSING_OPERATION"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    UPDATE_TARGET_MISSING = "UPDATE_TARGET_MISSING"
    CREATE_STABLE_ID_COLLISION = "CREATE_STABLE_ID_COLLISION"
    MALFORMED_EXPECTED_VAULT_REVISION = "MALFORMED_EXPECTED_VAULT_REVISION"
    STALE_BASE_REVISION = "STALE_BASE_REVISION"
    ABSOLUTE_PATH_ATTEMPT = "ABSOLUTE_PATH_ATTEMPT"
    PARENT_TRAVERSAL_ATTEMPT = "PARENT_TRAVERSAL_ATTEMPT"
    DESTRUCTIVE_OPERATION_REJECTED = "DESTRUCTIVE_OPERATION_REJECTED"
    SUPERSEDE_RESERVED_NON_VALIDATING = "SUPERSEDE_RESERVED_NON_VALIDATING"
    PROPOSER_AUTHORITY_SPOOFING = "PROPOSER_AUTHORITY_SPOOFING"
    PROPOSER_LIFECYCLE_SPOOFING = "PROPOSER_LIFECYCLE_SPOOFING"
    MALFORMED_EVIDENCE_REFERENCE = "MALFORMED_EVIDENCE_REFERENCE"
    TOO_MANY_EVIDENCE_REFERENCES = "TOO_MANY_EVIDENCE_REFERENCES"
    EVIDENCE_REFERENCE_TOO_LONG = "EVIDENCE_REFERENCE_TOO_LONG"
    OVERSIZED_CONTENT = "OVERSIZED_CONTENT"
    OVERSIZED_TOTAL_PROPOSAL = "OVERSIZED_TOTAL_PROPOSAL"
    SECRET_DETECTED = "SECRET_DETECTED"
    PROPOSER_METADATA_TOO_LONG = "PROPOSER_METADATA_TOO_LONG"
    REASON_TOO_LONG = "REASON_TOO_LONG"
    HASH_AMBIGUITY = "HASH_AMBIGUITY"
    CANONICALIZATION_AMBIGUITY = "CANONICALIZATION_AMBIGUITY"
    MUTATION_DURING_VALIDATION = "MUTATION_DURING_VALIDATION"
    INTERNAL_VALIDATION_ERROR = "INTERNAL_VALIDATION_ERROR"


@dataclass(frozen=True, slots=True)
class ProposerMetadata:
    agent_type: str = ""
    agent_instance_id: str = ""
    model_identifier: str = ""
    source_workflow: str = ""

    def __post_init__(self) -> None:
        for name, value in (("agent_type", self.agent_type), ("agent_instance_id", self.agent_instance_id),
                            ("model_identifier", self.model_identifier), ("source_workflow", self.source_workflow)):
            if not isinstance(value, str):
                raise ValueError(f"proposer metadata {name} must be string")
            if len(value) > _PROPOSER_METADATA_MAXLEN:
                raise ValueError(f"proposer metadata {name} exceeds {_PROPOSER_METADATA_MAXLEN} chars")
        if _contains_absolute_path((self.agent_type, self.agent_instance_id, self.model_identifier, self.source_workflow)):
            raise ValueError("proposer metadata contains absolute path")

    def to_dict(self) -> dict[str, str]:
        return {
            "agent_type": self.agent_type,
            "agent_instance_id": self.agent_instance_id,
            "model_identifier": self.model_identifier,
            "source_workflow": self.source_workflow,
        }


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    reference: str
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.reference, str) or not self.reference:
            raise ValueError("evidence reference must be non-empty string")
        if len(self.reference) > _EVIDENCE_REF_MAXLEN:
            raise ValueError(f"evidence reference exceeds {_EVIDENCE_REF_MAXLEN} chars")
        if not isinstance(self.description, str):
            raise ValueError("evidence description must be string")
        if len(self.description) > _EVIDENCE_REF_MAXLEN:
            raise ValueError(f"evidence description exceeds {_EVIDENCE_REF_MAXLEN} chars")
        if _contains_absolute_path(self.reference) or _contains_absolute_path(self.description):
            raise ValueError("evidence reference contains absolute path")

    def to_dict(self) -> dict[str, str]:
        return {"reference": self.reference, "description": self.description}


@dataclass(frozen=True, slots=True)
class ProposedNoteContent:
    title: str
    body_text: str
    type: str
    status: str
    knowledge_layer: str
    evidence_class: str
    authority: str
    canonical: bool = False
    canonical_scope: str | None = None
    aliases: tuple[str, ...] = ()
    releases: tuple[str, ...] = ()
    source_paths: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    superseded_by: tuple[str, ...] = ()
    updated: str = ""
    last_reviewed: str = ""
    verified_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.title, str):
            raise ValueError("proposed title must be string")
        if not isinstance(self.body_text, str):
            raise ValueError("proposed body_text must be string")
        if len(self.body_text) > _CONTENT_MAXLEN:
            raise ValueError(f"proposed content exceeds {_CONTENT_MAXLEN} chars")
        if not isinstance(self.type, str) or not self.type:
            raise ValueError("proposed type must be non-empty string")
        if not isinstance(self.status, str) or not self.status:
            raise ValueError("proposed status must be non-empty string")
        if not isinstance(self.knowledge_layer, str) or not self.knowledge_layer:
            raise ValueError("proposed knowledge_layer must be non-empty string")
        if not isinstance(self.evidence_class, str) or not self.evidence_class:
            raise ValueError("proposed evidence_class must be non-empty string")
        if not isinstance(self.authority, str) or not self.authority:
            raise ValueError("proposed authority must be non-empty string")
        if not isinstance(self.canonical, bool):
            raise ValueError("proposed canonical must be boolean")
        if self.canonical_scope is not None and (not isinstance(self.canonical_scope, str) or not self.canonical_scope):
            raise ValueError("proposed canonical_scope must be non-empty string when set")
        for seq_name, seq_val in (("aliases", self.aliases), ("releases", self.releases),
                                   ("source_paths", self.source_paths), ("evidence_refs", self.evidence_refs),
                                   ("supersedes", self.supersedes), ("superseded_by", self.superseded_by)):
            if not isinstance(seq_val, tuple):
                raise ValueError(f"proposed {seq_name} must be tuple")
            for item in seq_val:
                if not isinstance(item, str):
                    raise ValueError(f"proposed {seq_name} item must be string")
                if _contains_absolute_path(item):
                    raise ValueError(f"proposed {seq_name} contains absolute path")
        if self.updated and not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", self.updated):
            raise ValueError("proposed updated must be YYYY-MM-DD")
        if self.last_reviewed and not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", self.last_reviewed):
            raise ValueError("proposed last_reviewed must be YYYY-MM-DD")
        if self.verified_at is not None:
            if not isinstance(self.verified_at, str):
                raise ValueError("proposed verified_at must be string or None")
            try:
                from datetime import datetime
                datetime.fromisoformat(self.verified_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("proposed verified_at must be ISO timestamp") from exc

    def to_dict(self) -> dict[str, Any]:
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


@dataclass(frozen=True, slots=True)
class CanonicalLocationHint:
    relative_path: str
    parent_stable_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.relative_path, str) or not self.relative_path:
            raise ValueError("canonical location hint relative_path must be non-empty string")
        if PurePosixPath(self.relative_path).is_absolute() or PureWindowsPath(self.relative_path).is_absolute():
            raise ValueError("canonical location hint must not be absolute path")
        parts = [p for p in re.split(r"[\\/]", self.relative_path) if p not in ("", ".")]
        if any(p == ".." for p in parts):
            raise ValueError("canonical location hint parent traversal forbidden")
        if self.parent_stable_id is not None:
            if not isinstance(self.parent_stable_id, str) or not ID_RE.fullmatch(self.parent_stable_id):
                raise ValueError("canonical location hint parent_stable_id must be valid stable ID")

    def to_dict(self) -> dict[str, Any]:
        return {"relative_path": self.relative_path, "parent_stable_id": self.parent_stable_id}


@dataclass(frozen=True, slots=True)
class Provenance:
    reason: str
    source_observation: str = ""
    related_stable_ids: tuple[str, ...] = ()
    evidence_references: tuple[EvidenceReference, ...] = ()
    workflow_origin: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("provenance reason must be non-empty string")
        if len(self.reason) > _REASON_MAXLEN:
            raise ValueError(f"provenance reason exceeds {_REASON_MAXLEN} chars")
        if not isinstance(self.source_observation, str):
            raise ValueError("provenance source_observation must be string")
        if len(self.source_observation) > _REASON_MAXLEN:
            raise ValueError(f"provenance source_observation exceeds {_REASON_MAXLEN} chars")
        if not isinstance(self.workflow_origin, str):
            raise ValueError("provenance workflow_origin must be string")
        if len(self.workflow_origin) > _REASON_MAXLEN:
            raise ValueError(f"provenance workflow_origin exceeds {_REASON_MAXLEN} chars")
        for sid in self.related_stable_ids:
            if not isinstance(sid, str) or not ID_RE.fullmatch(sid):
                raise ValueError("provenance related_stable_ids must be valid stable IDs")
        if len(self.evidence_references) > _MAX_EVIDENCE_REFS:
            raise ValueError(f"evidence references exceed {_MAX_EVIDENCE_REFS}")
        for ref in self.evidence_references:
            if not isinstance(ref, EvidenceReference):
                raise ValueError("provenance evidence_references must be EvidenceReference objects")
        if _contains_absolute_path((self.reason, self.source_observation, self.workflow_origin,
                                     self.related_stable_ids, self.evidence_references)):
            raise ValueError("provenance contains absolute path")

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "source_observation": self.source_observation,
            "related_stable_ids": list(self.related_stable_ids),
            "evidence_references": [ref.to_dict() for ref in self.evidence_references],
            "workflow_origin": self.workflow_origin,
        }


@dataclass(frozen=True, slots=True)
class KnowledgeChangeProposal:
    proposal_id: str
    contract_version: str
    operation: ProposalOperation
    target_stable_id: str
    expected_vault_revision: str
    proposer: ProposerMetadata
    provenance: Provenance
    proposed_content: ProposedNoteContent | None = None
    canonical_location_hint: CanonicalLocationHint | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, str) or not PROPOSAL_ID_RE.fullmatch(self.proposal_id):
            raise ValueError("proposal_id must match kprop:<sha256>")
        if not isinstance(self.contract_version, str) or self.contract_version != CONTRACT_VERSION:
            raise ValueError(f"contract_version must be {CONTRACT_VERSION}")
        if not isinstance(self.operation, ProposalOperation):
            try:
                object.__setattr__(self, "operation", ProposalOperation(self.operation))
            except (TypeError, ValueError) as exc:
                raise ValueError("operation must be valid ProposalOperation") from exc
        if not isinstance(self.target_stable_id, str) or not self.target_stable_id:
            raise ValueError("target_stable_id must be non-empty string")
        if len(self.target_stable_id) > _STABLE_ID_MAXLEN:
            raise ValueError(f"target_stable_id exceeds {_STABLE_ID_MAXLEN} chars")
        if not ID_RE.fullmatch(self.target_stable_id):
            raise ValueError("target_stable_id must be valid stable ID pattern")
        if not isinstance(self.expected_vault_revision, str) or not _VAULT_REVISION_RE.fullmatch(self.expected_vault_revision):
            raise ValueError("expected_vault_revision must be sha256:<64-hex>")
        if not isinstance(self.proposer, ProposerMetadata):
            raise ValueError("proposer must be ProposerMetadata")
        if not isinstance(self.provenance, Provenance):
            raise ValueError("provenance must be Provenance")
        if self.proposed_content is not None and not isinstance(self.proposed_content, ProposedNoteContent):
            raise ValueError("proposed_content must be ProposedNoteContent or None")
        if self.canonical_location_hint is not None and not isinstance(self.canonical_location_hint, CanonicalLocationHint):
            raise ValueError("canonical_location_hint must be CanonicalLocationHint or None")
        if self.operation in (ProposalOperation.UPDATE_EXISTING, ProposalOperation.CREATE_NEW):
            if self.proposed_content is None:
                raise ValueError(f"operation {self.operation.value} requires proposed_content")
        if self.operation is ProposalOperation.CREATE_NEW:
            if self.canonical_location_hint is None:
                raise ValueError("CREATE_NEW requires canonical_location_hint")
        if self.operation is ProposalOperation.UPDATE_EXISTING:
            if self.canonical_location_hint is not None:
                raise ValueError("UPDATE_EXISTING must not provide canonical_location_hint")
        if _contains_absolute_path(self):
            raise ValueError("proposal contains absolute path")

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "contract_version": self.contract_version,
            "operation": self.operation.value,
            "target_stable_id": self.target_stable_id,
            "expected_vault_revision": self.expected_vault_revision,
            "proposer": self.proposer.to_dict(),
            "provenance": self.provenance.to_dict(),
            "proposed_content": self.proposed_content.to_dict() if self.proposed_content else None,
            "canonical_location_hint": self.canonical_location_hint.to_dict() if self.canonical_location_hint else None,
        }


def _canonical_proposal_bytes(proposal: KnowledgeChangeProposal) -> bytes:
    payload = {
        "proposal_id": proposal.proposal_id,
        "contract_version": proposal.contract_version,
        "operation": proposal.operation.value,
        "target_stable_id": proposal.target_stable_id,
        "expected_vault_revision": proposal.expected_vault_revision,
        "proposer": proposal.proposer.to_dict(),
        "provenance": proposal.provenance.to_dict(),
        "proposed_content": proposal.proposed_content.to_dict() if proposal.proposed_content else None,
        "canonical_location_hint": proposal.canonical_location_hint.to_dict() if proposal.canonical_location_hint else None,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_proposal_content_hash(proposal: KnowledgeChangeProposal) -> str:
    return "sha256:" + hashlib.sha256(_canonical_proposal_bytes(proposal)).hexdigest()


def compute_proposal_instance_id(proposal: KnowledgeChangeProposal) -> str:
    return PROPOSAL_ID_PREFIX + hashlib.sha256(_canonical_proposal_bytes(proposal)).hexdigest()


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    code: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "severity": self.severity}


@dataclass(frozen=True, slots=True)
class ValidationResult:
    outcome: ValidationOutcome
    proposal_id: str
    proposal_content_hash: str
    contract_version: str
    operation: str
    target_stable_id: str
    expected_vault_revision: str
    validated_vault_revision: str
    findings: tuple[ValidationFinding, ...] = ()
    provenance_summary: dict[str, Any] | None = None
    evidence_reference_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, ValidationOutcome):
            try:
                object.__setattr__(self, "outcome", ValidationOutcome(self.outcome))
            except (TypeError, ValueError) as exc:
                raise ValueError("outcome must be ValidationOutcome") from exc
        if not isinstance(self.proposal_id, str) or not PROPOSAL_ID_RE.fullmatch(self.proposal_id):
            raise ValueError("validation result proposal_id invalid")
        if not isinstance(self.proposal_content_hash, str):
            raise ValueError("validation result proposal_content_hash invalid")
        # Accept both "sha256:" prefix and raw 64-hex
        if self.proposal_content_hash.startswith("sha256:"):
            if not _SHA256_RE.fullmatch(self.proposal_content_hash[7:]):
                raise ValueError("validation result proposal_content_hash invalid")
        elif not _SHA256_RE.fullmatch(self.proposal_content_hash):
            raise ValueError("validation result proposal_content_hash invalid")
        if not isinstance(self.contract_version, str) or self.contract_version != CONTRACT_VERSION:
            raise ValueError("validation result contract_version invalid")
        if not isinstance(self.operation, str):
            raise ValueError("validation result operation invalid")
        if not isinstance(self.target_stable_id, str):
            raise ValueError("validation result target_stable_id invalid")
        if not isinstance(self.expected_vault_revision, str) or not _VAULT_REVISION_RE.fullmatch(self.expected_vault_revision):
            raise ValueError("validation result expected_vault_revision invalid")
        if not isinstance(self.validated_vault_revision, str) or not _VAULT_REVISION_RE.fullmatch(self.validated_vault_revision):
            raise ValueError("validation result validated_vault_revision invalid")
        if not isinstance(self.findings, tuple):
            object.__setattr__(self, "findings", tuple(self.findings))
        for f in self.findings:
            if not isinstance(f, ValidationFinding):
                raise ValueError("findings must be ValidationFinding objects")
        if self.provenance_summary is not None and not isinstance(self.provenance_summary, dict):
            raise ValueError("provenance_summary must be dict or None")
        if not isinstance(self.evidence_reference_count, int) or self.evidence_reference_count < 0:
            raise ValueError("evidence_reference_count must be non-negative int")

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "proposal_id": self.proposal_id,
            "proposal_content_hash": self.proposal_content_hash,
            "contract_version": self.contract_version,
            "operation": self.operation,
            "target_stable_id": self.target_stable_id,
            "expected_vault_revision": self.expected_vault_revision,
            "validated_vault_revision": self.validated_vault_revision,
            "findings": [f.to_dict() for f in self.findings],
            "provenance_summary": self.provenance_summary,
            "evidence_reference_count": self.evidence_reference_count,
        }


class ProposalValidator:
    def __init__(
        self,
        vault_revision: str,
        stable_ids: frozenset[str] | set[str] | None = None,
        *,
        vault_root: Path | None = None,
        project_root: Path | None = None,
        max_notes: int = 2000,
        max_note_bytes: int = 1_048_576,
        max_total_scan_bytes: int = 67_108_864,
    ) -> None:
        self._provided_revision = vault_revision
        self._provided_stable_ids = frozenset(stable_ids) if stable_ids is not None else None
        self._vault_root = Path(os.fspath(vault_root)) if vault_root else None
        self._project_root = Path(os.fspath(project_root)) if project_root else None
        self._max_notes = max_notes
        self._max_note_bytes = max_note_bytes
        self._max_total_scan_bytes = max_total_scan_bytes
        self._cached_validation: VaultValidationResult | None = None
        self._cached_stable_ids: frozenset[str] | None = None

    def _get_current_vault_revision(self) -> str:
        if self._provided_revision:
            return self._provided_revision
        if self._cached_validation is None:
            if not self._vault_root or not self._project_root:
                raise KnowledgeAdapterError(
                    KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR,
                    "ProposalValidator requires either vault_revision or vault_root+project_root",
                )
            self._cached_validation = vault_validator.validate_vault(
                self._vault_root,
                self._project_root,
                max_notes=self._max_notes,
                max_note_bytes=self._max_note_bytes,
                max_total_scan_bytes=self._max_total_scan_bytes,
            )
            if self._cached_validation.status == "FAIL" or self._cached_validation.error_count > 0:
                raise KnowledgeAdapterError(
                    KnowledgeErrorCode.KNOWLEDGE_VALIDATION_FAILED,
                    "Current Vault validation failed; cannot validate proposals against invalid baseline.",
                )
        return self._cached_validation.vault_revision

    def _get_stable_ids(self) -> frozenset[str]:
        if self._provided_stable_ids is not None:
            return self._provided_stable_ids
        if self._cached_stable_ids is None:
            self._get_current_vault_revision()
            if self._cached_validation:
                stable_ids = set()
                for note in self._cached_validation.__dict__.get("notes", []):
                    if hasattr(note, "note_id") and note.note_id and ID_RE.fullmatch(note.note_id):
                        stable_ids.add(note.note_id)
                self._cached_stable_ids = frozenset(stable_ids)
        return self._cached_stable_ids or frozenset()

    def validate(self, proposal: KnowledgeChangeProposal) -> ValidationResult:
        current_revision = self._get_current_vault_revision()
        stable_ids = self._get_stable_ids()

        findings: list[ValidationFinding] = []

        if proposal.contract_version != CONTRACT_VERSION:
            findings.append(ValidationFinding(
                ProposalValidationCode.UNSUPPORTED_CONTRACT_VERSION.value,
                f"Unsupported contract version: {proposal.contract_version}",
            ))

        if proposal.operation in (ProposalOperation.DELETE, ProposalOperation.MOVE, ProposalOperation.RENAME):
            findings.append(ValidationFinding(
                ProposalValidationCode.DESTRUCTIVE_OPERATION_REJECTED.value,
                f"Operation {proposal.operation.value} is not supported in this contract version",
            ))
        elif proposal.operation is ProposalOperation.SUPERSEDE:
            findings.append(ValidationFinding(
                ProposalValidationCode.SUPERSEDE_RESERVED_NON_VALIDATING.value,
                "SUPERSEDE is reserved for future use and cannot validate in this release",
            ))

        if proposal.operation is ProposalOperation.UPDATE_EXISTING:
            if proposal.target_stable_id not in stable_ids:
                findings.append(ValidationFinding(
                    ProposalValidationCode.UPDATE_TARGET_MISSING.value,
                    f"UPDATE_EXISTING target stable ID not found in current Vault: {proposal.target_stable_id}",
                ))
        elif proposal.operation is ProposalOperation.CREATE_NEW:
            if proposal.target_stable_id in stable_ids:
                findings.append(ValidationFinding(
                    ProposalValidationCode.CREATE_STABLE_ID_COLLISION.value,
                    f"CREATE_NEW target stable ID collides with existing: {proposal.target_stable_id}",
                ))

        if proposal.expected_vault_revision != current_revision:
            findings.append(ValidationFinding(
                ProposalValidationCode.STALE_BASE_REVISION.value,
                f"Proposal expected Vault revision {proposal.expected_vault_revision} but current is {current_revision}",
            ))

        proposer_dict = proposal.proposer.to_dict()
        reserved_keys = {"VALIDATED", "APPROVED", "PUBLISHED", "USER_APPROVAL", "CANONICAL", "VERIFIED_BY_LOCALCOMET"}
        for key, value in proposer_dict.items():
            if key in reserved_keys or value in reserved_keys:
                findings.append(ValidationFinding(
                    ProposalValidationCode.PROPOSER_AUTHORITY_SPOOFING.value,
                    f"Proposer metadata contains reserved authority term: {key}={value}",
                ))

        prov_dict = proposal.provenance.to_dict()
        # Check provenance fields for reserved lifecycle terms
        for field in ("source_observation", "workflow_origin"):
            val = prov_dict.get(field, "")
            if val in reserved_keys:
                findings.append(ValidationFinding(
                    ProposalValidationCode.PROPOSER_LIFECYCLE_SPOOFING.value,
                    f"Provenance {field} contains reserved lifecycle term: {val}",
                ))
        for ref in prov_dict.get("evidence_references", []):
            if isinstance(ref, dict) and ref.get("verified") is True:
                findings.append(ValidationFinding(
                    ProposalValidationCode.PROPOSER_LIFECYCLE_SPOOFING.value,
                    "Evidence reference claims verified status not granted by this contract",
                ))

        if proposal.proposed_content:
            content_bytes = proposal.proposed_content.body_text.encode("utf-8")
            if len(content_bytes) > _CONTENT_MAXLEN:
                findings.append(ValidationFinding(
                    ProposalValidationCode.OVERSIZED_CONTENT.value,
                    f"Proposed content exceeds {_CONTENT_MAXLEN} bytes",
                ))
            if self._detect_secrets(proposal.proposed_content.body_text):
                findings.append(ValidationFinding(
                    ProposalValidationCode.SECRET_DETECTED.value,
                    "Proposed content contains detected secret pattern",
                ))

        total_bytes = len(_canonical_proposal_bytes(proposal))
        if total_bytes > _MAX_TOTAL_PROPOSAL_BYTES:
            findings.append(ValidationFinding(
                ProposalValidationCode.OVERSIZED_TOTAL_PROPOSAL.value,
                f"Total proposal size {total_bytes} exceeds {_MAX_TOTAL_PROPOSAL_BYTES} bytes",
            ))

        if proposal.provenance and len(proposal.provenance.evidence_references) > _MAX_EVIDENCE_REFS:
            findings.append(ValidationFinding(
                ProposalValidationCode.TOO_MANY_EVIDENCE_REFERENCES.value,
                f"Evidence references exceed {_MAX_EVIDENCE_REFS}",
            ))

        for ref in proposal.provenance.evidence_references:
            if len(ref.reference) > _EVIDENCE_REF_MAXLEN:
                findings.append(ValidationFinding(
                    ProposalValidationCode.EVIDENCE_REFERENCE_TOO_LONG.value,
                    f"Evidence reference exceeds {_EVIDENCE_REF_MAXLEN} chars",
                ))

        if findings:
            outcome = ValidationOutcome.INVALID
            for f in findings:
                if f.code == ProposalValidationCode.STALE_BASE_REVISION.value:
                    outcome = ValidationOutcome.STALE
                    break
        else:
            outcome = ValidationOutcome.VALID

        content_hash = compute_proposal_content_hash(proposal)
        provenance_summary = {
            "reason": proposal.provenance.reason[:200],
            "source_observation": proposal.provenance.source_observation[:200] if proposal.provenance.source_observation else "",
            "related_stable_ids": list(proposal.provenance.related_stable_ids),
            "workflow_origin": proposal.provenance.workflow_origin[:200] if proposal.provenance.workflow_origin else "",
        }

        return ValidationResult(
            outcome=outcome,
            proposal_id=proposal.proposal_id,
            proposal_content_hash=content_hash,
            contract_version=CONTRACT_VERSION,
            operation=proposal.operation.value,
            target_stable_id=proposal.target_stable_id,
            expected_vault_revision=proposal.expected_vault_revision,
            validated_vault_revision=current_revision,
            findings=tuple(findings),
            provenance_summary=provenance_summary,
            evidence_reference_count=len(proposal.provenance.evidence_references),
        )

    def _detect_secrets(self, text: str) -> bool:
        patterns = [
            re.compile(r"\bsk-(?:live-)?[A-Za-z0-9]{20,}\b"),
            re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
            re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
            re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password|passwd|client_secret)\s*[:=]\s*[\"']?[A-Za-z0-9_./+\-=]{20,}"),
            re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
        ]
        for pattern in patterns:
            if pattern.search(text):
                return True
        return False


def create_proposal_from_untrusted(
    *,
    operation: str,
    target_stable_id: str,
    expected_vault_revision: str,
    proposer: dict[str, str] | None = None,
    provenance: dict[str, Any] | None = None,
    proposed_content: dict[str, Any] | None = None,
    canonical_location_hint: dict[str, Any] | None = None,
) -> KnowledgeChangeProposal:
    proposer_obj = ProposerMetadata(
        agent_type=(proposer or {}).get("agent_type", ""),
        agent_instance_id=(proposer or {}).get("agent_instance_id", ""),
        model_identifier=(proposer or {}).get("model_identifier", ""),
        source_workflow=(proposer or {}).get("source_workflow", ""),
    )

    evidence_refs = []
    for ref in (provenance or {}).get("evidence_references", []):
        evidence_refs.append(EvidenceReference(
            reference=ref.get("reference", ""),
            description=ref.get("description", ""),
        ))

    provenance_obj = Provenance(
        reason=(provenance or {}).get("reason", ""),
        source_observation=(provenance or {}).get("source_observation", ""),
        related_stable_ids=tuple((provenance or {}).get("related_stable_ids", [])),
        evidence_references=tuple(evidence_refs),
        workflow_origin=(provenance or {}).get("workflow_origin", ""),
    )

    content_obj = None
    if proposed_content:
        content_obj = ProposedNoteContent(
            title=proposed_content.get("title", ""),
            body_text=proposed_content.get("body_text", ""),
            type=proposed_content.get("type", ""),
            status=proposed_content.get("status", ""),
            knowledge_layer=proposed_content.get("knowledge_layer", ""),
            evidence_class=proposed_content.get("evidence_class", ""),
            authority=proposed_content.get("authority", ""),
            canonical=proposed_content.get("canonical", False),
            canonical_scope=proposed_content.get("canonical_scope"),
            aliases=tuple(proposed_content.get("aliases", [])),
            releases=tuple(proposed_content.get("releases", [])),
            source_paths=tuple(proposed_content.get("source_paths", [])),
            evidence_refs=tuple(proposed_content.get("evidence_refs", [])),
            supersedes=tuple(proposed_content.get("supersedes", [])),
            superseded_by=tuple(proposed_content.get("superseded_by", [])),
            updated=proposed_content.get("updated", ""),
            last_reviewed=proposed_content.get("last_reviewed", ""),
            verified_at=proposed_content.get("verified_at"),
        )

    hint_obj = None
    if canonical_location_hint:
        hint_obj = CanonicalLocationHint(
            relative_path=canonical_location_hint.get("relative_path", ""),
            parent_stable_id=canonical_location_hint.get("parent_stable_id"),
        )

    temp_proposal = KnowledgeChangeProposal(
        proposal_id="kprop:" + "0" * 64,
        contract_version=CONTRACT_VERSION,
        operation=operation,
        target_stable_id=target_stable_id,
        expected_vault_revision=expected_vault_revision,
        proposer=proposer_obj,
        provenance=provenance_obj,
        proposed_content=content_obj,
        canonical_location_hint=hint_obj,
    )

    instance_id = compute_proposal_instance_id(temp_proposal)

    return KnowledgeChangeProposal(
        proposal_id=instance_id,
        contract_version=CONTRACT_VERSION,
        operation=operation,
        target_stable_id=target_stable_id,
        expected_vault_revision=expected_vault_revision,
        proposer=proposer_obj,
        provenance=provenance_obj,
        proposed_content=content_obj,
        canonical_location_hint=hint_obj,
    )


__all__ = [
    "CONTRACT_VERSION",
    "PROPOSAL_ID_PREFIX",
    "PROPOSAL_ID_RE",
    "ProposalOperation",
    "ValidationOutcome",
    "ProposalValidationCode",
    "ProposerMetadata",
    "EvidenceReference",
    "ProposedNoteContent",
    "CanonicalLocationHint",
    "Provenance",
    "KnowledgeChangeProposal",
    "ValidationFinding",
    "ValidationResult",
    "ProposalValidator",
    "compute_proposal_content_hash",
    "compute_proposal_instance_id",
    "create_proposal_from_untrusted",
]