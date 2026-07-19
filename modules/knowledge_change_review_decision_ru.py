"""Human Review Decision Contract — LocalComet v6.84.5.1e9c.

Create one immutable, deterministic human-review decision bound to one exact
e9b ``KnowledgeChangeReviewArtifact``.  The result records review evidence and
then stops.  It has no persistence, Vault-write, publication, merge, rebase,
execution, model, network, subprocess, Tauri, frontend, registry, or consumer
authority.

Contract: localcomet.knowledge-change-review-decision/1.0
Lifecycle: exact e9b artifact -> exact decision binding -> decision -> HARD STOP
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any, Final

from modules.knowledge_change_review_ru import (
    CONTRACT_VERSION as REVIEW_CONTRACT_VERSION,
    KnowledgeChangeReviewArtifact,
    ReviewStatus,
)


CONTRACT_VERSION: Final[str] = "localcomet.knowledge-change-review-decision/1.0"
IDENTITY_VERSION: Final[str] = "1.0"
IDENTITY_DOMAIN: Final[str] = "HUMAN_REVIEW_DECISION_IDENTITY"
DECISION_ID_PREFIX: Final[str] = "kdecision:"

MAX_COMMENT_CHARS: Final[int] = 2_000
MAX_COMMENT_UTF8_BYTES: Final[int] = 4_096
MAX_ACTOR_IDENTIFIER_CHARS: Final[int] = 256
MAX_ACTOR_IDENTIFIER_UTF8_BYTES: Final[int] = 512
MAX_ACTOR_DISPLAY_NAME_CHARS: Final[int] = 256
MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES: Final[int] = 512
MAX_ACTOR_SOURCE_CHARS: Final[int] = 128
MAX_ACTOR_SOURCE_UTF8_BYTES: Final[int] = 256

HARD_STOP: Final[bool] = True
REVIEW_DECISION_ONLY: Final[bool] = True
ACTOR_METADATA_EVIDENCE_ONLY: Final[bool] = True
HUMAN_IDENTITY_AUTHENTICATED: Final[bool] = False
GRANTS_WRITE_AUTHORITY: Final[bool] = False
GRANTS_VAULT_WRITE_AUTHORITY: Final[bool] = False
GRANTS_PERSISTENCE_AUTHORITY: Final[bool] = False
GRANTS_PUBLICATION_AUTHORITY: Final[bool] = False
GRANTS_MERGE_AUTHORITY: Final[bool] = False
GRANTS_REBASE_AUTHORITY: Final[bool] = False
GRANTS_EXECUTION_AUTHORITY: Final[bool] = False
GRANTS_POLICY_AUTHORITY: Final[bool] = False
GRANTS_MODEL_GATEWAY_AUTHORITY: Final[bool] = False
GRANTS_TAURI_FRONTEND_AUTHORITY: Final[bool] = False
GRANTS_AUTOMATIC_APPROVAL_AUTHORITY: Final[bool] = False

_PROPOSAL_ID_RE = re.compile(r"^kprop:[0-9a-f]{64}$")
_REVIEW_ID_RE = re.compile(r"^kreview:[0-9a-f]{64}$")
_CHANGE_ID_RE = re.compile(r"^kchange:[0-9a-f]{64}$")
_REVISION_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DECISION_ID_RE = re.compile(r"^kdecision:[0-9a-f]{64}$")


class HumanReviewDecisionValue(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class HumanReviewDecisionRejectionCode(str, Enum):
    WRONG_REVIEW_ARTIFACT_TYPE = "WRONG_REVIEW_ARTIFACT_TYPE"
    INVALID_REVIEW_ARTIFACT = "INVALID_REVIEW_ARTIFACT"
    UNSUPPORTED_REVIEW_CONTRACT = "UNSUPPORTED_REVIEW_CONTRACT"
    INVALID_BINDING_VALUE = "INVALID_BINDING_VALUE"
    PROPOSAL_ID_MISMATCH = "PROPOSAL_ID_MISMATCH"
    REVIEW_ARTIFACT_IDENTITY_MISMATCH = "REVIEW_ARTIFACT_IDENTITY_MISMATCH"
    CHANGE_IDENTITY_MISMATCH = "CHANGE_IDENTITY_MISMATCH"
    OBSERVED_VAULT_REVISION_MISMATCH = "OBSERVED_VAULT_REVISION_MISMATCH"
    STALE_CURRENT_VAULT_REVISION = "STALE_CURRENT_VAULT_REVISION"
    UNSUPPORTED_DECISION = "UNSUPPORTED_DECISION"
    BLOCKED_APPROVAL_FORBIDDEN = "BLOCKED_APPROVAL_FORBIDDEN"
    APPROVAL_REQUIRES_CHANGE_IDENTITY = "APPROVAL_REQUIRES_CHANGE_IDENTITY"
    COMMENT_TYPE_INVALID = "COMMENT_TYPE_INVALID"
    COMMENT_REQUIRED = "COMMENT_REQUIRED"
    COMMENT_CHARACTER_LIMIT_EXCEEDED = "COMMENT_CHARACTER_LIMIT_EXCEEDED"
    COMMENT_UTF8_ENCODING_INVALID = "COMMENT_UTF8_ENCODING_INVALID"
    COMMENT_UTF8_BYTE_LIMIT_EXCEEDED = "COMMENT_UTF8_BYTE_LIMIT_EXCEEDED"
    ACTOR_TYPE_INVALID = "ACTOR_TYPE_INVALID"


class HumanReviewDecisionRejected(ValueError):
    """Deterministic typed rejection from the e9c decision boundary."""

    def __init__(self, code: HumanReviewDecisionRejectionCode) -> None:
        if type(code) is not HumanReviewDecisionRejectionCode:
            raise TypeError("code must be HumanReviewDecisionRejectionCode")
        self.code = code
        super().__init__(code.value)


def _validate_actor_text(
    name: str,
    value: str,
    *,
    max_chars: int,
    max_utf8_bytes: int,
) -> None:
    if type(value) is not str:
        raise ValueError(f"{name} must be an exact string")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")
    if "\x00" in value:
        raise ValueError(f"{name} must not contain NUL")
    if len(value) > max_chars:
        raise ValueError(f"{name} exceeds {max_chars} characters")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(f"{name} must be valid UTF-8") from None
    if len(encoded) > max_utf8_bytes:
        raise ValueError(f"{name} exceeds {max_utf8_bytes} UTF-8 bytes")


@dataclass(frozen=True, slots=True)
class HumanReviewerMetadata:
    """Bounded descriptive reviewer evidence; never an authority credential."""

    actor_identifier: str
    display_name: str
    source: str

    def __post_init__(self) -> None:
        _validate_actor_text(
            "actor_identifier",
            self.actor_identifier,
            max_chars=MAX_ACTOR_IDENTIFIER_CHARS,
            max_utf8_bytes=MAX_ACTOR_IDENTIFIER_UTF8_BYTES,
        )
        _validate_actor_text(
            "display_name",
            self.display_name,
            max_chars=MAX_ACTOR_DISPLAY_NAME_CHARS,
            max_utf8_bytes=MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES,
        )
        _validate_actor_text(
            "source",
            self.source,
            max_chars=MAX_ACTOR_SOURCE_CHARS,
            max_utf8_bytes=MAX_ACTOR_SOURCE_UTF8_BYTES,
        )


def _decision_rule_error(
    review_status: ReviewStatus,
    change_identity: str | None,
    decision: HumanReviewDecisionValue,
) -> HumanReviewDecisionRejectionCode | None:
    if review_status is ReviewStatus.BLOCKED and decision is HumanReviewDecisionValue.APPROVE:
        return HumanReviewDecisionRejectionCode.BLOCKED_APPROVAL_FORBIDDEN
    if decision is HumanReviewDecisionValue.APPROVE and change_identity is None:
        return HumanReviewDecisionRejectionCode.APPROVAL_REQUIRES_CHANGE_IDENTITY
    return None


@dataclass(frozen=True, slots=True)
class HumanReviewDecision:
    contract_version: str
    review_contract_version: str
    review_status: ReviewStatus
    proposal_id: str
    review_artifact_identity: str
    change_identity: str | None
    observed_vault_revision: str
    decision: HumanReviewDecisionValue
    comment: str
    actor: HumanReviewerMetadata
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

    def __post_init__(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("decision contract version mismatch")
        if self.review_contract_version != REVIEW_CONTRACT_VERSION:
            raise ValueError("review contract version mismatch")
        if type(self.review_status) is not ReviewStatus:
            raise ValueError("review_status must be ReviewStatus")
        if type(self.proposal_id) is not str or not _PROPOSAL_ID_RE.fullmatch(self.proposal_id):
            raise ValueError("proposal_id is invalid")
        if (
            type(self.review_artifact_identity) is not str
            or not _REVIEW_ID_RE.fullmatch(self.review_artifact_identity)
        ):
            raise ValueError("review_artifact_identity is invalid")
        if self.change_identity is not None and (
            type(self.change_identity) is not str
            or not _CHANGE_ID_RE.fullmatch(self.change_identity)
        ):
            raise ValueError("change_identity is invalid")
        if (
            type(self.observed_vault_revision) is not str
            or not _REVISION_RE.fullmatch(self.observed_vault_revision)
        ):
            raise ValueError("observed_vault_revision is invalid")
        if type(self.decision) is not HumanReviewDecisionValue:
            raise ValueError("decision must be HumanReviewDecisionValue")
        decision_error = _decision_rule_error(
            self.review_status,
            self.change_identity,
            self.decision,
        )
        if decision_error is not None:
            raise ValueError(decision_error.value)
        comment_error = _comment_error(self.comment, self.decision)
        if comment_error is not None:
            raise ValueError(comment_error.value)
        if type(self.actor) is not HumanReviewerMetadata:
            raise ValueError("actor must be HumanReviewerMetadata")
        expected_boundary = _authority_boundary_values()
        actual_boundary = _authority_boundary_values(self)
        if actual_boundary != expected_boundary:
            raise ValueError("HARD STOP/no-authority boundary mismatch")
        if type(self.decision_identity) is not str or not _DECISION_ID_RE.fullmatch(
            self.decision_identity
        ):
            raise ValueError("decision_identity is invalid")
        expected_identity = _compute_decision_identity(
            contract_version=self.contract_version,
            review_contract_version=self.review_contract_version,
            review_status=self.review_status,
            proposal_id=self.proposal_id,
            review_artifact_identity=self.review_artifact_identity,
            change_identity=self.change_identity,
            observed_vault_revision=self.observed_vault_revision,
            decision=self.decision,
            comment=self.comment,
            actor=self.actor,
            boundary=actual_boundary,
        )
        if self.decision_identity != expected_identity:
            raise ValueError("decision_identity does not bind the complete artifact")

def _authority_boundary_values(
    decision: HumanReviewDecision | None = None,
) -> tuple[tuple[str, bool], ...]:
    if decision is not None:
        return (
            ("hard_stop", decision.hard_stop),
            ("review_decision_only", decision.review_decision_only),
            ("actor_metadata_evidence_only", decision.actor_metadata_evidence_only),
            ("human_identity_authenticated", decision.human_identity_authenticated),
            ("grants_write_authority", decision.grants_write_authority),
            ("grants_vault_write_authority", decision.grants_vault_write_authority),
            ("grants_persistence_authority", decision.grants_persistence_authority),
            ("grants_publication_authority", decision.grants_publication_authority),
            ("grants_merge_authority", decision.grants_merge_authority),
            ("grants_rebase_authority", decision.grants_rebase_authority),
            ("grants_execution_authority", decision.grants_execution_authority),
            ("grants_policy_authority", decision.grants_policy_authority),
            ("grants_model_gateway_authority", decision.grants_model_gateway_authority),
            ("grants_tauri_frontend_authority", decision.grants_tauri_frontend_authority),
            (
                "grants_automatic_approval_authority",
                decision.grants_automatic_approval_authority,
            ),
        )
    return (
        ("hard_stop", HARD_STOP),
        ("review_decision_only", REVIEW_DECISION_ONLY),
        ("actor_metadata_evidence_only", ACTOR_METADATA_EVIDENCE_ONLY),
        ("human_identity_authenticated", HUMAN_IDENTITY_AUTHENTICATED),
        ("grants_write_authority", GRANTS_WRITE_AUTHORITY),
        ("grants_vault_write_authority", GRANTS_VAULT_WRITE_AUTHORITY),
        ("grants_persistence_authority", GRANTS_PERSISTENCE_AUTHORITY),
        ("grants_publication_authority", GRANTS_PUBLICATION_AUTHORITY),
        ("grants_merge_authority", GRANTS_MERGE_AUTHORITY),
        ("grants_rebase_authority", GRANTS_REBASE_AUTHORITY),
        ("grants_execution_authority", GRANTS_EXECUTION_AUTHORITY),
        ("grants_policy_authority", GRANTS_POLICY_AUTHORITY),
        ("grants_model_gateway_authority", GRANTS_MODEL_GATEWAY_AUTHORITY),
        ("grants_tauri_frontend_authority", GRANTS_TAURI_FRONTEND_AUTHORITY),
        ("grants_automatic_approval_authority", GRANTS_AUTOMATIC_APPROVAL_AUTHORITY),
    )


def _decision_identity_payload(
    *,
    contract_version: str,
    review_contract_version: str,
    review_status: ReviewStatus,
    proposal_id: str,
    review_artifact_identity: str,
    change_identity: str | None,
    observed_vault_revision: str,
    decision: HumanReviewDecisionValue,
    comment: str,
    actor: HumanReviewerMetadata,
    boundary: tuple[tuple[str, bool], ...],
) -> dict[str, Any]:
    return {
        "decision_contract_version": contract_version,
        "review_contract_version": review_contract_version,
        "review_status": review_status.value,
        "proposal_id": proposal_id,
        "review_artifact_identity": review_artifact_identity,
        "change_identity": change_identity,
        "observed_vault_revision": observed_vault_revision,
        "decision": decision.value,
        "comment": comment,
        "actor": _actor_identity_payload(actor),
        "semantics": {key: value for key, value in boundary},
    }


def _actor_identity_payload(actor: HumanReviewerMetadata) -> dict[str, str]:
    return {
        "actor_identifier": actor.actor_identifier,
        "display_name": actor.display_name,
        "source": actor.source,
    }


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _compute_decision_identity(
    *,
    contract_version: str,
    review_contract_version: str,
    review_status: ReviewStatus,
    proposal_id: str,
    review_artifact_identity: str,
    change_identity: str | None,
    observed_vault_revision: str,
    decision: HumanReviewDecisionValue,
    comment: str,
    actor: HumanReviewerMetadata,
    boundary: tuple[tuple[str, bool], ...],
) -> str:
    payload = _decision_identity_payload(
        contract_version=contract_version,
        review_contract_version=review_contract_version,
        review_status=review_status,
        proposal_id=proposal_id,
        review_artifact_identity=review_artifact_identity,
        change_identity=change_identity,
        observed_vault_revision=observed_vault_revision,
        decision=decision,
        comment=comment,
        actor=actor,
        boundary=boundary,
    )
    envelope = {
        "domain": IDENTITY_DOMAIN,
        "version": IDENTITY_VERSION,
        "payload": payload,
    }
    return DECISION_ID_PREFIX + hashlib.sha256(_canonical_json_bytes(envelope)).hexdigest()


def _comment_error(
    comment: Any,
    decision: HumanReviewDecisionValue,
) -> HumanReviewDecisionRejectionCode | None:
    if type(comment) is not str:
        return HumanReviewDecisionRejectionCode.COMMENT_TYPE_INVALID
    if len(comment) > MAX_COMMENT_CHARS:
        return HumanReviewDecisionRejectionCode.COMMENT_CHARACTER_LIMIT_EXCEEDED
    try:
        encoded = comment.encode("utf-8")
    except UnicodeEncodeError:
        return HumanReviewDecisionRejectionCode.COMMENT_UTF8_ENCODING_INVALID
    if len(encoded) > MAX_COMMENT_UTF8_BYTES:
        return HumanReviewDecisionRejectionCode.COMMENT_UTF8_BYTE_LIMIT_EXCEEDED
    if decision is HumanReviewDecisionValue.REQUEST_CHANGES and not comment.strip():
        return HumanReviewDecisionRejectionCode.COMMENT_REQUIRED
    return None


def _reject(code: HumanReviewDecisionRejectionCode) -> None:
    raise HumanReviewDecisionRejected(code)


def _validate_review_artifact(review_artifact: KnowledgeChangeReviewArtifact) -> None:
    if type(review_artifact.contract_version) is not str:
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)
    if review_artifact.contract_version != REVIEW_CONTRACT_VERSION:
        _reject(HumanReviewDecisionRejectionCode.UNSUPPORTED_REVIEW_CONTRACT)
    if type(review_artifact.status) is not ReviewStatus:
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)
    if type(review_artifact.proposal_id) is not str or not _PROPOSAL_ID_RE.fullmatch(
        review_artifact.proposal_id
    ):
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)
    if (
        type(review_artifact.review_artifact_identity) is not str
        or not _REVIEW_ID_RE.fullmatch(review_artifact.review_artifact_identity)
    ):
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)
    if review_artifact.change_identity is not None and (
        type(review_artifact.change_identity) is not str
        or not _CHANGE_ID_RE.fullmatch(review_artifact.change_identity)
    ):
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)
    if review_artifact.status is ReviewStatus.BLOCKED and review_artifact.change_identity is not None:
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)
    if (
        type(review_artifact.observed_vault_revision) is not str
        or not _REVISION_RE.fullmatch(review_artifact.observed_vault_revision)
    ):
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)


def _validate_binding_text(value: Any, pattern: re.Pattern[str]) -> None:
    if type(value) is not str or not pattern.fullmatch(value):
        _reject(HumanReviewDecisionRejectionCode.INVALID_BINDING_VALUE)


def _coerce_decision(value: HumanReviewDecisionValue | str) -> HumanReviewDecisionValue:
    if type(value) is HumanReviewDecisionValue:
        return value
    if type(value) is str:
        try:
            return HumanReviewDecisionValue(value)
        except ValueError:
            pass
    _reject(HumanReviewDecisionRejectionCode.UNSUPPORTED_DECISION)
    raise AssertionError("unreachable")


def create_human_review_decision(
    review_artifact: KnowledgeChangeReviewArtifact,
    *,
    expected_proposal_id: str,
    expected_review_artifact_identity: str,
    expected_change_identity: str | None,
    expected_observed_vault_revision: str,
    current_observed_vault_revision: str,
    decision: HumanReviewDecisionValue | str,
    comment: str,
    actor: HumanReviewerMetadata,
) -> HumanReviewDecision:
    """Validate exact e9b binding and return an immutable HARD STOP artifact."""
    if type(review_artifact) is not KnowledgeChangeReviewArtifact:
        _reject(HumanReviewDecisionRejectionCode.WRONG_REVIEW_ARTIFACT_TYPE)
    _validate_review_artifact(review_artifact)

    _validate_binding_text(expected_proposal_id, _PROPOSAL_ID_RE)
    _validate_binding_text(expected_review_artifact_identity, _REVIEW_ID_RE)
    if expected_change_identity is not None:
        _validate_binding_text(expected_change_identity, _CHANGE_ID_RE)
    _validate_binding_text(expected_observed_vault_revision, _REVISION_RE)
    _validate_binding_text(current_observed_vault_revision, _REVISION_RE)

    if expected_proposal_id != review_artifact.proposal_id:
        _reject(HumanReviewDecisionRejectionCode.PROPOSAL_ID_MISMATCH)
    if expected_review_artifact_identity != review_artifact.review_artifact_identity:
        _reject(HumanReviewDecisionRejectionCode.REVIEW_ARTIFACT_IDENTITY_MISMATCH)
    if expected_change_identity != review_artifact.change_identity:
        _reject(HumanReviewDecisionRejectionCode.CHANGE_IDENTITY_MISMATCH)
    if expected_observed_vault_revision != review_artifact.observed_vault_revision:
        _reject(HumanReviewDecisionRejectionCode.OBSERVED_VAULT_REVISION_MISMATCH)
    if current_observed_vault_revision != review_artifact.observed_vault_revision:
        _reject(HumanReviewDecisionRejectionCode.STALE_CURRENT_VAULT_REVISION)

    selected_decision = _coerce_decision(decision)
    decision_error = _decision_rule_error(
        review_artifact.status,
        review_artifact.change_identity,
        selected_decision,
    )
    if decision_error is not None:
        _reject(decision_error)

    comment_error = _comment_error(comment, selected_decision)
    if comment_error is not None:
        _reject(comment_error)
    if type(actor) is not HumanReviewerMetadata:
        _reject(HumanReviewDecisionRejectionCode.ACTOR_TYPE_INVALID)

    boundary = _authority_boundary_values()
    decision_identity = _compute_decision_identity(
        contract_version=CONTRACT_VERSION,
        review_contract_version=REVIEW_CONTRACT_VERSION,
        review_status=review_artifact.status,
        proposal_id=review_artifact.proposal_id,
        review_artifact_identity=review_artifact.review_artifact_identity,
        change_identity=review_artifact.change_identity,
        observed_vault_revision=review_artifact.observed_vault_revision,
        decision=selected_decision,
        comment=comment,
        actor=actor,
        boundary=boundary,
    )
    boundary_values = dict(boundary)
    return HumanReviewDecision(
        contract_version=CONTRACT_VERSION,
        review_contract_version=REVIEW_CONTRACT_VERSION,
        review_status=review_artifact.status,
        proposal_id=review_artifact.proposal_id,
        review_artifact_identity=review_artifact.review_artifact_identity,
        change_identity=review_artifact.change_identity,
        observed_vault_revision=review_artifact.observed_vault_revision,
        decision=selected_decision,
        comment=comment,
        actor=actor,
        decision_identity=decision_identity,
        hard_stop=boundary_values["hard_stop"],
        review_decision_only=boundary_values["review_decision_only"],
        actor_metadata_evidence_only=boundary_values["actor_metadata_evidence_only"],
        human_identity_authenticated=boundary_values["human_identity_authenticated"],
        grants_write_authority=boundary_values["grants_write_authority"],
        grants_vault_write_authority=boundary_values["grants_vault_write_authority"],
        grants_persistence_authority=boundary_values["grants_persistence_authority"],
        grants_publication_authority=boundary_values["grants_publication_authority"],
        grants_merge_authority=boundary_values["grants_merge_authority"],
        grants_rebase_authority=boundary_values["grants_rebase_authority"],
        grants_execution_authority=boundary_values["grants_execution_authority"],
        grants_policy_authority=boundary_values["grants_policy_authority"],
        grants_model_gateway_authority=boundary_values["grants_model_gateway_authority"],
        grants_tauri_frontend_authority=boundary_values["grants_tauri_frontend_authority"],
        grants_automatic_approval_authority=boundary_values[
            "grants_automatic_approval_authority"
        ],
    )


__all__ = [
    "CONTRACT_VERSION",
    "REVIEW_CONTRACT_VERSION",
    "IDENTITY_VERSION",
    "IDENTITY_DOMAIN",
    "DECISION_ID_PREFIX",
    "MAX_COMMENT_CHARS",
    "MAX_COMMENT_UTF8_BYTES",
    "MAX_ACTOR_IDENTIFIER_CHARS",
    "MAX_ACTOR_IDENTIFIER_UTF8_BYTES",
    "MAX_ACTOR_DISPLAY_NAME_CHARS",
    "MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES",
    "MAX_ACTOR_SOURCE_CHARS",
    "MAX_ACTOR_SOURCE_UTF8_BYTES",
    "HumanReviewDecisionValue",
    "HumanReviewDecisionRejectionCode",
    "HumanReviewDecisionRejected",
    "HumanReviewerMetadata",
    "HumanReviewDecision",
    "create_human_review_decision",
]
