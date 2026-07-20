from __future__ import annotations

import hashlib
import re
import secrets
import threading
import uuid
from dataclasses import dataclass, field, fields, replace
from typing import Any, Callable, Mapping

from modules.knowledge_contract_ru import (
    DEFAULT_CONTEXT_CHARS,
    DEFAULT_MAX_RESULTS,
    KnowledgeAdapterError,
    KnowledgeContextError,
    KnowledgeContextRequest,
    KnowledgeContextResult,
    KnowledgeContextState,
    KnowledgeErrorCode,
    QueryIntent,
)
from modules.knowledge_injection_ru import (
    KnowledgeInjectionContractError,
    KnowledgeInjectionDecision,
    KnowledgeInjectionDecisionSource,
    KnowledgeInjectionEnvelope,
    KnowledgeInjectionError,
    KnowledgeInjectionPreview,
    KnowledgeInjectionRecord,
    KnowledgeInjectionState,
    decide_envelope,
    mark_envelope_injected,
    prepare_injection_envelope,
    verify_envelope_integrity,
    verify_provider_messages,
)
from modules.knowledge_change_proposal_ru import KnowledgeChangeProposal, ValidationResult
from modules.knowledge_change_review_ru import (
    CONTRACT_VERSION as KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
    CurrentKnowledgeState,
    KnowledgeChangeReviewArtifact,
    ReviewStatus,
    analyze_review,
)
from modules.knowledge_change_review_decision_ru import (
    CONTRACT_VERSION as HUMAN_REVIEW_DECISION_CONTRACT,
    MAX_ACTOR_DISPLAY_NAME_CHARS,
    MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES,
    MAX_ACTOR_IDENTIFIER_CHARS,
    MAX_ACTOR_IDENTIFIER_UTF8_BYTES,
    MAX_ACTOR_SOURCE_CHARS,
    MAX_ACTOR_SOURCE_UTF8_BYTES,
    MAX_COMMENT_CHARS,
    MAX_COMMENT_UTF8_BYTES,
    HumanReviewDecision,
    HumanReviewDecisionRejected,
    HumanReviewDecisionValue,
    HumanReviewerMetadata,
    create_human_review_decision,
)
from modules.knowledge_review_ui_projection_ru import (
    ProjectionRejected,
    ProjectionRejectionCode,
    materialize_json_value,
    project_human_review_decision,
    project_knowledge_change_review,
    project_knowledge_change_review_summary,
)


DESKTOP_CONTROL_PLANE_VERSION = "v6.84.5.1"
IPC_PROTOCOL = "localcomet.ipc"
IPC_PROTOCOL_VERSION = "1.0"
SIDECAR_RUNTIME_VERSION = "v6.84.3"
KNOWLEDGE_CONTEXT_CONTROL_PLANE_RELEASE = "v6.84.5.1e5"
KNOWLEDGE_INJECTION_CONTROL_PLANE_RELEASE = "v6.84.5.1e6"
KNOWLEDGE_REVIEW_LIST_CONTRACT = "localcomet.knowledge-review-list/1.0"
KNOWLEDGE_REVIEW_GET_CONTRACT = "localcomet.knowledge-review-get/1.0"
KNOWLEDGE_REVIEW_SNAPSHOT_CONTRACT = "localcomet.knowledge-review-snapshot/1.0"
KNOWLEDGE_REVIEW_REFRESH_CONTRACT = "localcomet.knowledge-review-refresh/1.0"
KNOWLEDGE_REVIEW_DECISION_CREATE_CONTRACT = (
    "localcomet.knowledge-review-decision-create/1.0"
)
KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION = "v6.84.6"
KNOWLEDGE_REVIEW_SOURCE = "LOCAL_CONTROL_PLANE"
MAX_KNOWLEDGE_REVIEW_ARTIFACTS = 128
MAX_KNOWLEDGE_REVIEW_PAGE_SIZE = 50
MAX_KNOWLEDGE_REVIEW_DECISIONS = 128
MAX_REVIEW_ACTIVITY_ITEMS = 128

SESSION_STATES = ("OPEN", "CLOSED")
THREAD_STATES = ("ACTIVE", "CLOSED")
TURN_STATES = ("CREATED", "RUNNING", "CANCELLING", "CANCELLED", "COMPLETED", "FAILED")
ITEM_STATES = ("STARTED", "STREAMING", "COMPLETED", "FAILED")
ITEM_KINDS = (
    "approval_request",
    "assistant_message",
    "reasoning",
    "status",
    "tool_proposal",
    "tool_result",
    "user_message",
    "verification_result",
)
GENERATED_ITEM_KINDS = ("assistant_message", "status", "user_message")
CONTROL_PLANE_METHODS = (
    "app.bootstrap",
    "app.status",
    "knowledge.review.decision.create",
    "knowledge.review.get",
    "knowledge.review.list",
    "knowledge.review.refresh",
    "knowledge.review.snapshot",
    "session.close",
    "session.create",
    "session.get",
    "thread.create",
    "thread.get",
    "turn.cancel",
    "turn.start_mock",
    "turn.status",
)
SUPPORTED_METHODS = tuple(sorted(CONTROL_PLANE_METHODS + ("app.health", "app.shutdown")))
EVENT_METHODS = (
    "item.completed",
    "item.delta",
    "item.started",
    "knowledge.context.failed",
    "knowledge.context.ready",
    "knowledge.context.requested",
    "session.closed",
    "session.created",
    "sidecar.status",
    "thread.created",
    "turn.cancelled",
    "turn.completed",
    "turn.failed",
    "turn.started",
)
CANCEL_REASONS = ("timeout", "user_requested", "window_closing")
BEHAVIORS = ("complete", "pending_model", "wait_for_cancel")
DESKTOP_KNOWLEDGE_ACTIONS = (
    "CANCEL",
    "INCLUDE_AND_SEND",
    "REJECT_AND_SEND_WITHOUT_KNOWLEDGE",
)
ID_RE = re.compile(r"^[0-9a-f]{24}$")
KNOWLEDGE_REVIEW_ID_RE = re.compile(r"^kreview:[0-9a-f]{64}$")
KNOWLEDGE_PROPOSAL_ID_RE = re.compile(r"^kprop:[0-9a-f]{64}$")
KNOWLEDGE_CHANGE_ID_RE = re.compile(r"^kchange:[0-9a-f]{64}$")
KNOWLEDGE_DECISION_ID_RE = re.compile(r"^kdecision:[0-9a-f]{64}$")
VAULT_REVISION_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SECRET_RE = re.compile(
    r"(?i)(sk-[A-Za-z0-9_\-]{8,}|bearer\s+[A-Za-z0-9._\-]{8,}|"
    r"(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s'\";]{6,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----|"
    r"Traceback \(most recent call last\):.*)",
    re.DOTALL,
)
_WINDOWS_USER_PATH_RE = r"[A-Z]:" + r"\\Users\\" + r"[^\\\s]+"
_POSIX_HOME_PATH_RE = "/" + "home" + r"/[^/\s]+"
_MAC_USER_PATH_RE = "/" + "Users" + r"/[^/\s]+"
_UNC_PATH_RE = r"\\\\" + r"[^\\\s]+" + r"\\" + r"[^\\\s]+"
PATH_RE = re.compile(
    r"(?i)("
    + "|".join(
        (
            _WINDOWS_USER_PATH_RE,
            _POSIX_HOME_PATH_RE,
            _MAC_USER_PATH_RE,
            _UNC_PATH_RE,
        )
    )
    + r")"
)


class ControlPlaneError(Exception):
    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.message = _bounded_text(message, 512)
        self.details = dict(details or {})


@dataclass(frozen=True, slots=True)
class ControlPlaneLimits:
    maximum_sessions: int = 16
    maximum_threads_per_session: int = 32
    maximum_turns_per_thread: int = 64
    maximum_items_per_turn: int = 128
    maximum_title_characters: int = 120
    maximum_prompt_characters: int = 8192
    maximum_preview_characters: int = 512
    maximum_item_delta_characters: int = 65536
    maximum_events_per_request: int = 64
    maximum_total_event_text_characters: int = 1_048_576
    maximum_response_json_size: int = 1_048_576
    maximum_remembered_closed_sessions: int = 16
    maximum_knowledge_review_artifacts: int = MAX_KNOWLEDGE_REVIEW_ARTIFACTS
    maximum_knowledge_review_page_size: int = MAX_KNOWLEDGE_REVIEW_PAGE_SIZE
    maximum_knowledge_review_decisions: int = MAX_KNOWLEDGE_REVIEW_DECISIONS

    def __post_init__(self) -> None:
        hard_maximums = {
            "maximum_sessions": 64,
            "maximum_threads_per_session": 128,
            "maximum_turns_per_thread": 256,
            "maximum_items_per_turn": 512,
            "maximum_prompt_characters": 32768,
            "maximum_events_per_request": 256,
            "maximum_total_event_text_characters": 4_194_304,
            "maximum_knowledge_review_artifacts": MAX_KNOWLEDGE_REVIEW_ARTIFACTS,
            "maximum_knowledge_review_page_size": MAX_KNOWLEDGE_REVIEW_PAGE_SIZE,
            "maximum_knowledge_review_decisions": MAX_KNOWLEDGE_REVIEW_DECISIONS,
        }
        for item in fields(self):
            name = item.name
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            hard = hard_maximums.get(name)
            if hard is not None and value > hard:
                raise ValueError(f"{name} exceeds hard maximum")


@dataclass(frozen=True, slots=True)
class ControlPlaneEvent:
    method: str
    sequence: int
    reply_to: str
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ControlPlaneDispatchResult:
    events: tuple[ControlPlaneEvent, ...]
    response: Mapping[str, Any]


@dataclass(slots=True)
class _Session:
    session_id: str
    title: str
    state: str = "OPEN"
    thread_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _Thread:
    thread_id: str
    session_id: str
    title: str
    state: str = "ACTIVE"
    turn_ids: list[str] = field(default_factory=list)
    active_turn_id: str | None = None


@dataclass(slots=True)
class _Turn:
    turn_id: str
    thread_id: str
    state: str
    prompt_sha256: str
    prompt_text: str
    prompt_preview: str
    prompt_character_count: int
    item_ids: list[str] = field(default_factory=list)
    last_sequence: int = -1
    model_called: bool = False
    tools_executed: int = 0
    knowledge_request_id: str | None = None
    knowledge_context: KnowledgeContextResult | None = None


@dataclass(slots=True)
class _Item:
    item_id: str
    turn_id: str
    kind: str
    state: str
    text: str = ""


@dataclass(slots=True)
class _KnowledgeContextRecord:
    request: KnowledgeContextRequest
    result: KnowledgeContextResult
    lifecycle: list[KnowledgeContextState]
    next_sequence: int = 0


@dataclass(frozen=True, slots=True)
class _DesktopKnowledgeDecisionReceipt:
    injection_id: str
    turn_id: str
    action: str
    preview_hash: str
    state: str
    model_turn_id: str | None
    model_dispatched: bool
    knowledge_included: bool

    def to_dict(self, *, duplicate: bool = False) -> dict[str, Any]:
        return {
            "injection_id": self.injection_id,
            "turn_id": self.turn_id,
            "action": self.action,
            "preview_hash": self.preview_hash,
            "state": self.state,
            "decision_source": KnowledgeInjectionDecisionSource.USER_APPROVAL.value,
            "model_turn_id": self.model_turn_id,
            "model_dispatched": self.model_dispatched,
            "knowledge_included": self.knowledge_included,
            "duplicate": duplicate,
        }


class DesktopControlPlane:
    def __init__(
        self,
        *,
        limits: ControlPlaneLimits | None = None,
        id_factory: Callable[[], str] | None = None,
        knowledge_adapter: Any | None = None,
        knowledge_request_id_factory: Callable[[], str] | None = None,
        knowledge_injection_id_factory: Callable[[], str] | None = None,
        knowledge_reviews: (
            list[KnowledgeChangeReviewArtifact]
            | tuple[KnowledgeChangeReviewArtifact, ...]
            | None
        ) = None,
    ) -> None:
        self.limits = limits or default_control_plane_limits()
        self._id_factory = id_factory or _secure_id
        self._knowledge_adapter = knowledge_adapter
        self._knowledge_request_id_factory = knowledge_request_id_factory or _secure_knowledge_request_id
        self._knowledge_injection_id_factory = knowledge_injection_id_factory or _secure_knowledge_injection_id
        self._sessions: dict[str, _Session] = {}
        self._threads: dict[str, _Thread] = {}
        self._turns: dict[str, _Turn] = {}
        self._items: dict[str, _Item] = {}
        self._knowledge_requests: dict[str, _KnowledgeContextRecord] = {}
        self._turn_current_knowledge_request: dict[str, str] = {}
        self._knowledge_injections: dict[str, KnowledgeInjectionRecord] = {}
        self._knowledge_injection_lock = threading.RLock()
        self._desktop_knowledge_receipts: dict[str, _DesktopKnowledgeDecisionReceipt] = {}
        self._desktop_knowledge_in_flight: set[str] = set()
        self._closed_session_ids: list[str] = []
        self._knowledge_review_lock = threading.RLock()
        self._knowledge_reviews = self._snapshot_knowledge_reviews(knowledge_reviews)
        self._knowledge_review_decisions: dict[str, HumanReviewDecision] = {}

    def dispatch(self, method: str, payload: Mapping[str, Any], *, request_id: str) -> ControlPlaneDispatchResult:
        findings = validate_control_plane_payload(method, payload)
        if findings:
            raise ControlPlaneError("invalid_payload", findings[0])
        if method == "app.bootstrap":
            return self._result((), self.bootstrap_snapshot())
        if method == "app.status":
            return self._result((), self.status_snapshot())
        if method == "knowledge.review.list":
            return self._list_knowledge_reviews(payload)
        if method == "knowledge.review.get":
            return self._get_knowledge_review(str(payload["review_artifact_identity"]))
        if method == "knowledge.review.snapshot":
            return self._knowledge_review_snapshot(refresh=False)
        if method == "knowledge.review.refresh":
            return self._knowledge_review_snapshot(refresh=True)
        if method == "knowledge.review.decision.create":
            return self._create_knowledge_review_decision(payload)
        if method == "session.create":
            return self._create_session(payload, request_id)
        if method == "session.get":
            return self._result((), self._session_summary(self._require_session(payload["session_id"])))
        if method == "session.close":
            return self._close_session(str(payload["session_id"]), request_id)
        if method == "thread.create":
            return self._create_thread(payload, request_id)
        if method == "thread.get":
            return self._result((), self._thread_summary(self._require_thread(payload["thread_id"])))
        if method == "turn.start_mock":
            return self._start_mock_turn(payload, request_id)
        if method == "turn.status":
            return self._result((), self._turn_summary(self._require_turn(payload["turn_id"])))
        if method == "turn.cancel":
            return self._cancel_turn(payload, request_id)
        raise ControlPlaneError("unsupported_method", "unsupported control-plane method")

    def _snapshot_knowledge_reviews(
        self,
        knowledge_reviews: (
            list[KnowledgeChangeReviewArtifact]
            | tuple[KnowledgeChangeReviewArtifact, ...]
            | None
        ),
    ) -> tuple[KnowledgeChangeReviewArtifact, ...]:
        if knowledge_reviews is None:
            source: list[KnowledgeChangeReviewArtifact] | tuple[KnowledgeChangeReviewArtifact, ...] = ()
        elif type(knowledge_reviews) not in (list, tuple):
            raise TypeError("knowledge_reviews must be an exact list or tuple")
        else:
            source = knowledge_reviews
        if len(source) > self.limits.maximum_knowledge_review_artifacts:
            raise ValueError("knowledge_reviews exceeds artifact limit")
        snapshot = tuple(source)
        identities: set[str] = set()
        for artifact in snapshot:
            if type(artifact) is not KnowledgeChangeReviewArtifact:
                raise TypeError("knowledge_reviews entries must be exact KnowledgeChangeReviewArtifact")
            identity = artifact.review_artifact_identity
            if identity in identities:
                raise ValueError("duplicate review_artifact_identity")
            identities.add(identity)
        return tuple(sorted(snapshot, key=lambda artifact: artifact.review_artifact_identity))

    def produce_knowledge_review(
        self,
        proposal: KnowledgeChangeProposal,
        validation_result: ValidationResult,
        current_state: CurrentKnowledgeState,
    ) -> KnowledgeChangeReviewArtifact:
        """Produce and retain one real e9b artifact for trusted in-process callers."""
        if type(proposal) is not KnowledgeChangeProposal:
            raise TypeError("proposal must be the exact KnowledgeChangeProposal type")
        if type(validation_result) is not ValidationResult:
            raise TypeError("validation_result must be the exact ValidationResult type")
        if type(current_state) is not CurrentKnowledgeState:
            raise TypeError("current_state must be the exact CurrentKnowledgeState type")

        artifact = analyze_review(proposal, validation_result, current_state)
        if type(artifact) is not KnowledgeChangeReviewArtifact:
            raise TypeError("analyze_review must return the exact KnowledgeChangeReviewArtifact type")

        with self._knowledge_review_lock:
            existing = next(
                (
                    candidate
                    for candidate in self._knowledge_reviews
                    if candidate.review_artifact_identity == artifact.review_artifact_identity
                ),
                None,
            )
            if existing is not None:
                if existing == artifact:
                    return existing
                raise ValueError("review_artifact_identity collision with unequal artifact")
            if len(self._knowledge_reviews) >= self.limits.maximum_knowledge_review_artifacts:
                raise ValueError("knowledge review artifact limit reached")
            self._knowledge_reviews = tuple(
                sorted(
                    (*self._knowledge_reviews, artifact),
                    key=lambda candidate: candidate.review_artifact_identity,
                )
            )
            return artifact

    def _list_knowledge_reviews(
        self,
        payload: Mapping[str, Any],
    ) -> ControlPlaneDispatchResult:
        offset = int(payload["offset"])
        limit = int(payload["limit"])
        if offset > self.limits.maximum_knowledge_review_artifacts:
            raise ControlPlaneError("invalid_payload", "invalid_offset")
        if limit > self.limits.maximum_knowledge_review_page_size:
            raise ControlPlaneError("invalid_payload", "invalid_limit")
        with self._knowledge_review_lock:
            review_snapshot = self._knowledge_reviews
        total_count = len(review_snapshot)
        selected = review_snapshot[offset:offset + limit]
        try:
            items = [
                materialize_json_value(project_knowledge_change_review_summary(artifact))
                for artifact in selected
            ]
        except ProjectionRejected as exc:
            self._raise_projection_error(exc)
        returned_count = len(items)
        next_offset_value = offset + returned_count
        truncated = next_offset_value < total_count
        response = {
            "contract": KNOWLEDGE_REVIEW_LIST_CONTRACT,
            "source": KNOWLEDGE_REVIEW_SOURCE,
            "fixture": False,
            "offset": offset,
            "limit": limit,
            "total_count": total_count,
            "returned_count": returned_count,
            "truncated": truncated,
            "next_offset": next_offset_value if truncated else None,
            "items": items,
        }
        return self._result((), response)

    def _get_knowledge_review(
        self,
        review_artifact_identity: str,
    ) -> ControlPlaneDispatchResult:
        with self._knowledge_review_lock:
            review_snapshot = self._knowledge_reviews
        artifact = next(
            (
                candidate
                for candidate in review_snapshot
                if candidate.review_artifact_identity == review_artifact_identity
            ),
            None,
        )
        if artifact is None:
            raise ControlPlaneError("request_not_found", "knowledge review artifact was not found")
        try:
            projection = materialize_json_value(project_knowledge_change_review(artifact))
        except ProjectionRejected as exc:
            self._raise_projection_error(exc)
        return self._result(
            (),
            {
                "contract": KNOWLEDGE_REVIEW_GET_CONTRACT,
                "source": KNOWLEDGE_REVIEW_SOURCE,
                "fixture": False,
                "projection": projection,
            },
        )

    def _knowledge_review_snapshot(self, *, refresh: bool) -> ControlPlaneDispatchResult:
        adapter_status, refresh_error_code = self._knowledge_adapter_status(refresh=refresh)
        current_revision = adapter_status.get("vault_revision")
        if type(current_revision) is not str or VAULT_REVISION_RE.fullmatch(current_revision) is None:
            current_revision = None
        adapter_state = adapter_status.get("state")
        if type(adapter_state) is not str:
            adapter_state = "NOT_CONFIGURED"
        last_error_code = adapter_status.get("last_error_code")
        if type(last_error_code) is not str:
            last_error_code = refresh_error_code

        with self._knowledge_review_lock:
            review_snapshot = self._knowledge_reviews
            decision_snapshot = tuple(self._knowledge_review_decisions.values())

        review_states: list[dict[str, Any]] = []
        stale_count = 0
        blocked_count = 0
        for artifact in review_snapshot:
            stale = (
                artifact.observed_vault_revision != current_revision
                if current_revision is not None
                else None
            )
            if stale is True:
                stale_count += 1
            if artifact.status is ReviewStatus.BLOCKED:
                blocked_count += 1
            review_states.append(
                {
                    "review_artifact_identity": artifact.review_artifact_identity,
                    "status": artifact.status.value,
                    "stale": stale,
                }
            )

        contract = (
            KNOWLEDGE_REVIEW_REFRESH_CONTRACT
            if refresh
            else KNOWLEDGE_REVIEW_SNAPSHOT_CONTRACT
        )
        return self._result(
            (),
            {
                "contract": contract,
                "command_center_version": KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION,
                "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
                "sidecar_runtime_version": SIDECAR_RUNTIME_VERSION,
                "source": KNOWLEDGE_REVIEW_SOURCE,
                "fixture": False,
                "refresh_requested": refresh,
                "refresh_succeeded": refresh and refresh_error_code is None,
                "current_vault_revision": current_revision,
                "freshness_known": current_revision is not None,
                "knowledge_state": _bounded_text(adapter_state, 64),
                "last_error_code": (
                    _bounded_text(last_error_code, 64)
                    if type(last_error_code) is str
                    else None
                ),
                "inbox_count": len(review_snapshot),
                "stale_count": stale_count,
                "blocked_count": blocked_count,
                "session_decision_count": len(decision_snapshot),
                "review_states": review_states,
                "hard_stop": True,
                "persistence": False,
                "vault_write_authority": False,
                "publication_authority": False,
            },
        )

    def _knowledge_adapter_status(
        self,
        *,
        refresh: bool,
    ) -> tuple[dict[str, Any], str | None]:
        adapter = self._knowledge_adapter
        if adapter is None:
            return (
                {
                    "state": "NOT_CONFIGURED",
                    "vault_revision": None,
                    "last_error_code": "KNOWLEDGE_NOT_CONFIGURED",
                },
                "KNOWLEDGE_NOT_CONFIGURED" if refresh else None,
            )

        refresh_error_code: str | None = None
        if refresh:
            refresh_method = getattr(adapter, "refresh", None)
            if not callable(refresh_method):
                refresh_error_code = "KNOWLEDGE_REFRESH_UNAVAILABLE"
            else:
                try:
                    refresh_method()
                except KnowledgeAdapterError as exc:
                    refresh_error_code = exc.code.value
                except Exception:
                    refresh_error_code = "KNOWLEDGE_REFRESH_FAILED"

        status_method = getattr(adapter, "status", None)
        if not callable(status_method):
            return (
                {
                    "state": "ERROR",
                    "vault_revision": None,
                    "last_error_code": refresh_error_code or "KNOWLEDGE_STATUS_UNAVAILABLE",
                },
                refresh_error_code or "KNOWLEDGE_STATUS_UNAVAILABLE",
            )
        try:
            value = status_method()
        except Exception:
            return (
                {
                    "state": "ERROR",
                    "vault_revision": None,
                    "last_error_code": refresh_error_code or "KNOWLEDGE_STATUS_FAILED",
                },
                refresh_error_code or "KNOWLEDGE_STATUS_FAILED",
            )
        if not isinstance(value, Mapping):
            return (
                {
                    "state": "ERROR",
                    "vault_revision": None,
                    "last_error_code": refresh_error_code or "KNOWLEDGE_STATUS_INVALID",
                },
                refresh_error_code or "KNOWLEDGE_STATUS_INVALID",
            )
        return dict(value), refresh_error_code

    def _fresh_knowledge_vault_revision(self) -> str:
        """Refresh the read-only adapter and return the newly observed Vault revision."""
        adapter = self._knowledge_adapter
        if adapter is None:
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision observation is unavailable",
            )
        refresh_method = getattr(adapter, "refresh", None)
        if not callable(refresh_method):
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision observation is unavailable",
            )
        try:
            refresh_result = refresh_method()
        except KnowledgeAdapterError as exc:
            raise ControlPlaneError(
                "sidecar_unavailable",
                f"fresh Vault revision observation failed: {exc.code.value}",
            ) from None
        except Exception:
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision observation failed",
            ) from None
        if not isinstance(refresh_result, Mapping):
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision observation returned an invalid result",
            )
        revision = refresh_result.get("current_revision")
        if type(revision) is not str or VAULT_REVISION_RE.fullmatch(revision) is None:
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision is unavailable for a human review decision",
            )
        return revision

    def _require_knowledge_review_artifact(
        self,
        review_artifact_identity: str,
    ) -> KnowledgeChangeReviewArtifact:
        with self._knowledge_review_lock:
            artifact = next(
                (
                    candidate
                    for candidate in self._knowledge_reviews
                    if candidate.review_artifact_identity == review_artifact_identity
                ),
                None,
            )
        if artifact is None:
            raise ControlPlaneError(
                "request_not_found",
                "knowledge review artifact was not found",
            )
        return artifact

    def _create_knowledge_review_decision(
        self,
        payload: Mapping[str, Any],
    ) -> ControlPlaneDispatchResult:
        review_artifact_identity = str(payload["review_artifact_identity"])
        artifact = self._require_knowledge_review_artifact(review_artifact_identity)
        if payload["review_contract_version"] != artifact.contract_version:
            raise ControlPlaneError(
                "invalid_payload",
                "knowledge review contract binding mismatch",
            )

        try:
            actor = HumanReviewerMetadata(
                actor_identifier=str(payload["actor_identifier"]),
                display_name=str(payload["actor_display_name"]),
                source=str(payload["actor_source"]),
            )
        except (TypeError, ValueError):
            raise ControlPlaneError(
                "invalid_payload",
                "human reviewer metadata is invalid",
            ) from None

        current_revision = self._fresh_knowledge_vault_revision()
        try:
            decision = create_human_review_decision(
                artifact,
                expected_proposal_id=str(payload["proposal_id"]),
                expected_review_artifact_identity=review_artifact_identity,
                expected_change_identity=payload["change_identity"],
                expected_observed_vault_revision=str(payload["observed_vault_revision"]),
                current_observed_vault_revision=current_revision,
                decision=str(payload["decision"]),
                comment=str(payload["comment"]),
                actor=actor,
            )
        except HumanReviewDecisionRejected as exc:
            code = exc.code.value
            policy_codes = {
                "BLOCKED_APPROVAL_FORBIDDEN",
                "APPROVAL_REQUIRES_CHANGE_IDENTITY",
                "STALE_CURRENT_VAULT_REVISION",
            }
            raise ControlPlaneError(
                "policy_blocked" if code in policy_codes else "invalid_payload",
                f"human review decision rejected: {code}",
            ) from None

        try:
            projection = materialize_json_value(project_human_review_decision(decision))
        except ProjectionRejected as exc:
            self._raise_projection_error(exc)

        with self._knowledge_review_lock:
            existing = self._knowledge_review_decisions.get(decision.decision_identity)
            duplicate = existing is not None
            if existing is not None and existing != decision:
                raise ControlPlaneError(
                    "internal_error",
                    "human review decision identity collision",
                )
            if existing is None:
                if (
                    len(self._knowledge_review_decisions)
                    >= self.limits.maximum_knowledge_review_decisions
                ):
                    raise ControlPlaneError(
                        "busy",
                        "human review decision session capacity is full",
                    )
                self._knowledge_review_decisions[decision.decision_identity] = decision

        return self._result(
            (),
            {
                "contract": KNOWLEDGE_REVIEW_DECISION_CREATE_CONTRACT,
                "command_center_version": KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION,
                "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
                "sidecar_runtime_version": SIDECAR_RUNTIME_VERSION,
                "source": KNOWLEDGE_REVIEW_SOURCE,
                "fixture": False,
                "duplicate": duplicate,
                "current_vault_revision": current_revision,
                "decision": projection,
                "hard_stop": True,
                "vault_modified": False,
                "persistence": False,
                "publication": False,
            },
        )

    @staticmethod
    def _raise_projection_error(error: ProjectionRejected) -> None:
        if error.code is ProjectionRejectionCode.PROJECTION_JSON_LIMIT_EXCEEDED:
            raise ControlPlaneError(
                "payload_too_large",
                "knowledge review projection exceeds the response bound",
            ) from None
        raise ControlPlaneError(
            "internal_error",
            "knowledge review projection failed",
        ) from None

    def bootstrap_snapshot(self) -> dict[str, Any]:
        snapshot = self.status_snapshot()
        snapshot["capabilities"] = list(CONTROL_PLANE_METHODS)
        snapshot["persistence"] = False
        snapshot["models_connected"] = False
        snapshot["provider_registry_available"] = False
        snapshot["harness_registry_available"] = False
        return snapshot

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "protocol": IPC_PROTOCOL,
            "protocol_version": IPC_PROTOCOL_VERSION,
            "sidecar_runtime_version": SIDECAR_RUNTIME_VERSION,
            "capabilities": list(CONTROL_PLANE_METHODS),
            "limits": {
                "maximum_sessions": self.limits.maximum_sessions,
                "maximum_threads_per_session": self.limits.maximum_threads_per_session,
                "maximum_turns_per_thread": self.limits.maximum_turns_per_thread,
                "maximum_prompt_characters": self.limits.maximum_prompt_characters,
                "maximum_events_per_request": self.limits.maximum_events_per_request,
                "maximum_knowledge_review_artifacts": self.limits.maximum_knowledge_review_artifacts,
                "maximum_knowledge_review_page_size": self.limits.maximum_knowledge_review_page_size,
                "maximum_knowledge_review_decisions": self.limits.maximum_knowledge_review_decisions,
            },
            "counts": self._counts(),
            "sidecar_ready": True,
            "persistence": False,
            "models_connected": False,
            "provider_registry_available": False,
            "harness_registry_available": False,
        }

    def begin_knowledge_context(
        self,
        *,
        query: str,
        intent: QueryIntent | str = QueryIntent.AUTO,
        max_context_chars: int = DEFAULT_CONTEXT_CHARS,
        max_results: int = DEFAULT_MAX_RESULTS,
        include_superseded: bool = False,
        turn_id: str | None = None,
        request_id: str | None = None,
    ) -> ControlPlaneDispatchResult:
        lifecycle_id = request_id if request_id is not None else self._knowledge_request_id_factory()
        try:
            request = KnowledgeContextRequest(
                request_id=lifecycle_id,
                query=query,
                intent=intent,
                max_context_chars=max_context_chars,
                max_results=max_results,
                include_superseded=include_superseded,
                turn_id=turn_id,
            )
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "CONTRACT_VALIDATION_ERROR",
                "knowledge context request failed contract validation",
            ) from exc
        if request.request_id in self._knowledge_requests:
            raise ControlPlaneError(
                "KNOWLEDGE_REQUEST_DUPLICATE",
                "knowledge context request identity already exists",
            )
        if request.turn_id is not None and request.turn_id not in self._turns:
            raise ControlPlaneError(
                "KNOWLEDGE_TURN_NOT_FOUND",
                "knowledge context Turn was not found",
            )
        requested = KnowledgeContextResult(
            request_id=request.request_id,
            turn_id=request.turn_id,
            state=KnowledgeContextState.REQUESTED,
        )
        record = _KnowledgeContextRecord(
            request=request,
            result=requested,
            lifecycle=[KnowledgeContextState.REQUESTED],
        )
        self._knowledge_requests[request.request_id] = record
        if request.turn_id is not None:
            turn = self._turns[request.turn_id]
            turn.knowledge_request_id = request.request_id
            self._turn_current_knowledge_request[request.turn_id] = request.request_id
        event = self._knowledge_event(record, "knowledge.context.requested")
        return self._result((event,), self._knowledge_record_snapshot(record))

    def retrieve_knowledge_context(self, request_id: str) -> ControlPlaneDispatchResult:
        record = self._require_knowledge_request(request_id)
        if record.result.state in {KnowledgeContextState.READY, KnowledgeContextState.FAILED}:
            return self._result((), self._knowledge_record_snapshot(record))
        if record.result.state is not KnowledgeContextState.REQUESTED:
            raise ControlPlaneError(
                "KNOWLEDGE_REQUEST_DUPLICATE",
                "knowledge context retrieval is already in progress",
            )
        record.result = KnowledgeContextResult(
            request_id=record.request.request_id,
            turn_id=record.request.turn_id,
            state=KnowledgeContextState.RETRIEVING,
        )
        record.lifecycle.append(KnowledgeContextState.RETRIEVING)
        try:
            if self._knowledge_adapter is None:
                raise KnowledgeAdapterError(
                    code=KnowledgeErrorCode.KNOWLEDGE_NOT_CONFIGURED,
                    message="KnowledgeAdapter is not configured.",
                )
            adapter_result = self._knowledge_adapter.context_preview(
                record.request.query,
                record.request.intent,
                max_context_chars=record.request.max_context_chars,
                max_results=record.request.max_results,
                include_superseded=record.request.include_superseded,
            )
            if record.request.turn_id is not None and (
                self._turn_current_knowledge_request.get(record.request.turn_id)
                != record.request.request_id
            ):
                return self._fail_knowledge_context(
                    record,
                    "KNOWLEDGE_STALE_RESULT",
                    "stale knowledge context result was rejected",
                )
            ready = self._ready_knowledge_result(record.request, adapter_result)
        except KnowledgeAdapterError as exc:
            return self._fail_knowledge_context(record, exc.code.value, exc.message)
        except (TypeError, ValueError, KeyError) as exc:
            return self._fail_knowledge_context(
                record,
                "CONTRACT_VALIDATION_ERROR",
                "KnowledgeAdapter result failed contract validation.",
            )
        except Exception:
            return self._fail_knowledge_context(
                record,
                "KNOWLEDGE_INTERNAL_ERROR",
                "Knowledge context retrieval failed safely.",
            )
        record.result = ready
        record.lifecycle.append(KnowledgeContextState.READY)
        if record.request.turn_id is not None:
            self._turns[record.request.turn_id].knowledge_context = ready
        event = self._knowledge_event(record, "knowledge.context.ready")
        return self._result((event,), self._knowledge_record_snapshot(record))

    def request_knowledge_context(
        self,
        *,
        query: str,
        intent: QueryIntent | str = QueryIntent.AUTO,
        max_context_chars: int = DEFAULT_CONTEXT_CHARS,
        max_results: int = DEFAULT_MAX_RESULTS,
        include_superseded: bool = False,
        turn_id: str | None = None,
        request_id: str | None = None,
    ) -> ControlPlaneDispatchResult:
        requested = self.begin_knowledge_context(
            query=query,
            intent=intent,
            max_context_chars=max_context_chars,
            max_results=max_results,
            include_superseded=include_superseded,
            turn_id=turn_id,
            request_id=request_id,
        )
        lifecycle_id = str(requested.response["request_id"])
        terminal = self.retrieve_knowledge_context(lifecycle_id)
        return self._result(requested.events + terminal.events, terminal.response)

    def knowledge_context_status(self, request_id: str) -> dict[str, Any]:
        return self._knowledge_record_snapshot(self._require_knowledge_request(request_id))

    def turn_knowledge_context(self, turn_id: str) -> dict[str, Any] | None:
        if turn_id not in self._turns:
            raise ControlPlaneError("KNOWLEDGE_TURN_NOT_FOUND", "knowledge context Turn was not found")
        result = self._turns[turn_id].knowledge_context
        return result.to_dict() if result is not None else None

    def desktop_knowledge_preview(
        self,
        *,
        turn_id: str,
        intent: QueryIntent | str,
        max_context_chars: int,
        max_results: int,
    ) -> dict[str, Any]:
        """Trusted desktop preview derived only from the existing Turn prompt."""
        if turn_id not in self._turns:
            raise ControlPlaneError("KNOWLEDGE_TURN_NOT_FOUND", "knowledge preview Turn was not found")
        turn = self._turns[turn_id]
        if turn.state != "RUNNING" or not turn.prompt_text:
            raise ControlPlaneError("KNOWLEDGE_TURN_MISMATCH", "knowledge preview requires a pending Turn")
        requested = self.request_knowledge_context(
            query=turn.prompt_text,
            intent=intent,
            max_context_chars=max_context_chars,
            max_results=max_results,
            turn_id=turn_id,
        )
        if requested.response.get("state") != KnowledgeContextState.READY.value:
            error = requested.response.get("error")
            return {
                "state": KnowledgeInjectionState.FAILED.value,
                "turn_id": turn_id,
                "request_id": requested.response.get("request_id"),
                "injection_id": None,
                "error": dict(error) if isinstance(error, Mapping) else {
                    "code": "KNOWLEDGE_PREVIEW_FAILED",
                    "safe_message": "Project knowledge preview failed safely.",
                },
                "model_dispatched": False,
                "tools_executed": 0,
            }
        prepared = self.prepare_knowledge_injection(
            turn_id,
            str(requested.response["request_id"]),
        )
        record = self._require_knowledge_injection(str(prepared.response["injection_id"]))
        knowledge_record = self._require_knowledge_request(record.envelope.request_id)
        return self._desktop_preview_snapshot(record, knowledge_record.result)

    def desktop_knowledge_decide(
        self,
        *,
        turn_id: str,
        injection_id: str,
        expected_preview_hash: str,
        action: str,
        model_gateway: Any,
        emit_model_event: Callable[[str, str, int, Mapping[str, Any]], None],
    ) -> dict[str, Any]:
        """Trusted desktop-only USER_APPROVAL decision with atomic dispatch."""
        if action not in DESKTOP_KNOWLEDGE_ACTIONS:
            raise ControlPlaneError("KNOWLEDGE_ACTION_INVALID", "desktop knowledge action is invalid")
        with self._knowledge_injection_lock:
            existing = self._desktop_knowledge_receipts.get(injection_id)
            if existing is not None:
                if (
                    existing.turn_id != turn_id
                    or existing.action != action
                    or existing.preview_hash != expected_preview_hash
                ):
                    return self._desktop_stale_response(
                        turn_id=turn_id,
                        injection_id=injection_id,
                        code="KNOWLEDGE_INJECTION_DUPLICATE_ACTION",
                    )
                current = self._knowledge_injections.get(injection_id)
                response = existing.to_dict(duplicate=True)
                if current is not None and current.envelope.state is KnowledgeInjectionState.INJECTED:
                    response["state"] = KnowledgeInjectionState.INJECTED.value
                return response
            if injection_id in self._desktop_knowledge_in_flight:
                return {
                    "state": "DECIDING",
                    "turn_id": turn_id,
                    "injection_id": injection_id,
                    "action": action,
                    "model_dispatched": False,
                    "duplicate": True,
                }
            record = self._require_knowledge_injection(injection_id)
            try:
                self._validate_desktop_decision_identity(
                    record,
                    turn_id=turn_id,
                    expected_preview_hash=expected_preview_hash,
                )
                if action != "CANCEL":
                    self._validate_injection_current(record, turn_id)
            except KnowledgeInjectionContractError as exc:
                self._fail_knowledge_injection(record, exc, None)
                return self._desktop_stale_response(
                    turn_id=turn_id,
                    injection_id=injection_id,
                    code=exc.code,
                )
            self._desktop_knowledge_in_flight.add(injection_id)
            try:
                gateway_payload: Mapping[str, Any] | None = None
                if action != "CANCEL":
                    gateway_payload = model_gateway.bound_turn_payload(self._turns[turn_id].prompt_text)
                decision = (
                    KnowledgeInjectionDecision.INCLUDE
                    if action == "INCLUDE_AND_SEND"
                    else KnowledgeInjectionDecision.REJECT
                )
                try:
                    envelope = decide_envelope(
                        record.envelope,
                        decision=decision,
                        expected_preview_hash=expected_preview_hash,
                        decision_source=KnowledgeInjectionDecisionSource.USER_APPROVAL,
                    )
                except KnowledgeInjectionContractError as exc:
                    self._fail_knowledge_injection(record, exc, None)
                    return self._desktop_stale_response(
                        turn_id=turn_id,
                        injection_id=injection_id,
                        code=exc.code,
                    )
                record = replace(
                    record,
                    envelope=envelope,
                    lifecycle=record.lifecycle + (envelope.state,),
                )
                event_method = (
                    "knowledge.injection.approved"
                    if envelope.state is KnowledgeInjectionState.APPROVED
                    else "knowledge.injection.rejected"
                )
                _, record = self._injection_event(record, event_method)
                if action == "CANCEL":
                    self._finish_pending_turn_without_model(turn_id, "CANCELLED")
                    receipt = _DesktopKnowledgeDecisionReceipt(
                        injection_id=injection_id,
                        turn_id=turn_id,
                        action=action,
                        preview_hash=expected_preview_hash,
                        state=KnowledgeInjectionState.REJECTED.value,
                        model_turn_id=None,
                        model_dispatched=False,
                        knowledge_included=False,
                    )
                    self._desktop_knowledge_receipts[injection_id] = receipt
                    return receipt.to_dict()

                assert gateway_payload is not None

                def tracked_emit(
                    method: str,
                    model_turn_id: str,
                    sequence: int,
                    payload: Mapping[str, Any],
                ) -> None:
                    self._observe_model_event(turn_id, method, payload)
                    emit_model_event(method, model_turn_id, sequence, payload)

                if action == "INCLUDE_AND_SEND":
                    started = self.dispatch_approved_knowledge_turn(
                        injection_id,
                        model_gateway,
                        gateway_payload,
                        tracked_emit,
                        turn_id=turn_id,
                    )
                    state = "DISPATCHING"
                    knowledge_included = True
                else:
                    started = model_gateway.start_turn(gateway_payload, tracked_emit)
                    state = KnowledgeInjectionState.REJECTED.value
                    knowledge_included = False
                receipt = _DesktopKnowledgeDecisionReceipt(
                    injection_id=injection_id,
                    turn_id=turn_id,
                    action=action,
                    preview_hash=expected_preview_hash,
                    state=state,
                    model_turn_id=str(started["turn_id"]),
                    model_dispatched=True,
                    knowledge_included=knowledge_included,
                )
                self._desktop_knowledge_receipts[injection_id] = receipt
                return receipt.to_dict()
            finally:
                self._desktop_knowledge_in_flight.discard(injection_id)

    @staticmethod
    def _desktop_preview_snapshot(
        record: KnowledgeInjectionRecord,
        result: KnowledgeContextResult,
    ) -> dict[str, Any]:
        envelope = record.envelope
        sources: list[dict[str, Any]] = []
        for source_index, source in enumerate(result.sources):
            sections: list[dict[str, Any]] = []
            envelope_source = envelope.sources[source_index]
            for section_index, section in enumerate(source["selected_sections"]):
                content = section["content"]
                expected_hash = envelope_source["selected_sections"][section_index]["content_sha256"]
                actual_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
                if actual_hash != expected_hash:
                    raise ControlPlaneError(
                        "KNOWLEDGE_INJECTION_CONTEXT_MISMATCH",
                        "knowledge preview content does not match the prepared envelope",
                    )
                sections.append(
                    {
                        "heading": section["heading"],
                        "line_start": section["line_start"],
                        "line_end": section["line_end"],
                        "content": content,
                    }
                )
            sources.append(
                {
                    "note_id": source["note_id"],
                    "title": source.get("title", ""),
                    "relative_path": source["relative_path"],
                    "knowledge_layer": source["knowledge_layer"],
                    "evidence_class": source["evidence_class"],
                    "authority": source["authority"],
                    "status": source["status"],
                    "canonical": source["canonical"],
                    "selected_sections": sections,
                }
            )
        return {
            "state": envelope.state.value,
            "turn_id": envelope.turn_id,
            "request_id": envelope.request_id,
            "injection_id": envelope.injection_id,
            "bundle_id": envelope.bundle_id,
            "preview_hash": envelope.preview_hash,
            "vault_revision": envelope.vault_revision,
            "resolved_intent": envelope.resolved_intent.value,
            "source_count": envelope.source_count,
            "total_chars": envelope.total_chars,
            "truncated": envelope.truncated,
            "sources": sources,
            "model_dispatched": False,
            "tools_executed": 0,
        }

    @staticmethod
    def _desktop_stale_response(*, turn_id: str, injection_id: str, code: str) -> dict[str, Any]:
        return {
            "state": "STALE",
            "turn_id": turn_id,
            "injection_id": injection_id,
            "error": {
                "code": code,
                "safe_message": "Project knowledge changed. Refresh the preview.",
            },
            "model_dispatched": False,
            "tools_executed": 0,
        }

    @staticmethod
    def _validate_desktop_decision_identity(
        record: KnowledgeInjectionRecord,
        *,
        turn_id: str,
        expected_preview_hash: str,
    ) -> None:
        verify_envelope_integrity(record.envelope)
        if record.envelope.state is not KnowledgeInjectionState.PREVIEW_READY:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_STATE_INVALID",
                "knowledge preview is no longer pending a decision",
            )
        if record.envelope.turn_id != turn_id:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_MISMATCH",
                "knowledge preview belongs to a different Turn",
            )
        if record.envelope.preview_hash != expected_preview_hash:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_PREVIEW_MISMATCH",
                "knowledge preview hash does not match",
            )

    def _finish_pending_turn_without_model(self, turn_id: str, state: str) -> None:
        turn = self._turns[turn_id]
        turn.state = state
        thread = self._threads[turn.thread_id]
        if thread.active_turn_id == turn_id:
            thread.active_turn_id = None

    def _observe_model_event(
        self,
        control_plane_turn_id: str,
        method: str,
        payload: Mapping[str, Any],
    ) -> None:
        with self._knowledge_injection_lock:
            turn = self._turns.get(control_plane_turn_id)
            if turn is None:
                return
            if method == "model.turn.started":
                turn.model_called = payload.get("model_called") is True
            elif method == "model.turn.completed":
                turn.model_called = payload.get("model_called") is True
                self._finish_pending_turn_without_model(control_plane_turn_id, "COMPLETED")
            elif method == "model.turn.cancelled":
                turn.model_called = payload.get("model_called") is True
                self._finish_pending_turn_without_model(control_plane_turn_id, "CANCELLED")
            elif method in {"model.turn.timed_out", "model.turn.failed"}:
                turn.model_called = payload.get("model_called") is True
                self._finish_pending_turn_without_model(control_plane_turn_id, "FAILED")

    def prepare_knowledge_injection(
        self,
        turn_id: str,
        knowledge_request_id: str,
        *,
        injection_id: str | None = None,
    ) -> ControlPlaneDispatchResult:
        """Prepare an exact preview without causing tools, network, or model calls."""
        with self._knowledge_injection_lock:
            if turn_id not in self._turns:
                raise ControlPlaneError("KNOWLEDGE_TURN_NOT_FOUND", "knowledge injection Turn was not found")
            knowledge_record = self._require_knowledge_request(knowledge_request_id)
            if knowledge_record.result.state is not KnowledgeContextState.READY:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_NOT_READY",
                    "knowledge context must be READY before injection preparation",
                )
            if knowledge_record.request.turn_id != turn_id:
                raise ControlPlaneError("KNOWLEDGE_TURN_MISMATCH", "knowledge request belongs to a different Turn")
            if self._turn_current_knowledge_request.get(turn_id) != knowledge_request_id:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_STALE_REQUEST",
                    "knowledge request is no longer current for the Turn",
                )
            lifecycle_id = injection_id if injection_id is not None else self._knowledge_injection_id_factory()
            if lifecycle_id in self._knowledge_injections:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_DUPLICATE",
                    "knowledge injection identity already exists",
                )
            try:
                envelope = prepare_injection_envelope(
                    injection_id=lifecycle_id,
                    turn_id=turn_id,
                    knowledge_result=knowledge_record.result,
                )
                preview = KnowledgeInjectionPreview.from_envelope(envelope)
                record = KnowledgeInjectionRecord(
                    envelope=envelope,
                    preview=preview,
                    lifecycle=(KnowledgeInjectionState.PREVIEW_READY,),
                )
            except KnowledgeInjectionContractError as exc:
                raise ControlPlaneError(exc.code, exc.safe_message) from exc
            except (TypeError, ValueError, KeyError) as exc:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_CONTRACT_INVALID",
                    "knowledge injection preview failed contract validation",
                ) from exc
            self._knowledge_injections[envelope.injection_id] = record
            event, record = self._injection_event(record, "knowledge.injection.preview_ready")
            return self._result((event,), record.to_dict())

    def decide_knowledge_injection(
        self,
        injection_id: str,
        decision: KnowledgeInjectionDecision | str,
        expected_preview_hash: str,
        decision_source: KnowledgeInjectionDecisionSource | str,
    ) -> ControlPlaneDispatchResult:
        """Apply an explicit decision to the exact prepared preview."""
        try:
            normalized_source = KnowledgeInjectionDecisionSource(decision_source)
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "KNOWLEDGE_INJECTION_DECISION_INVALID",
                "knowledge injection decision source is invalid",
            ) from exc
        if normalized_source is not KnowledgeInjectionDecisionSource.INTERNAL_EXPLICIT_CALL:
            raise ControlPlaneError(
                "KNOWLEDGE_INJECTION_DECISION_SOURCE_FORBIDDEN",
                "USER_APPROVAL is reserved for the trusted desktop decision command",
            )
        with self._knowledge_injection_lock:
            record = self._require_knowledge_injection(injection_id)
            if record.envelope.state is not KnowledgeInjectionState.PREVIEW_READY:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_STATE_INVALID",
                    "knowledge injection decision requires PREVIEW_READY state",
                )
            try:
                normalized_decision = KnowledgeInjectionDecision(decision)
            except (TypeError, ValueError) as exc:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_DECISION_INVALID",
                    "knowledge injection decision is invalid",
                ) from exc
            if normalized_decision is KnowledgeInjectionDecision.INCLUDE:
                try:
                    self._validate_injection_current(record, record.envelope.turn_id)
                except KnowledgeInjectionContractError as exc:
                    return self._fail_knowledge_injection(record, exc, None)
            try:
                envelope = decide_envelope(
                    record.envelope,
                    decision=normalized_decision,
                    expected_preview_hash=expected_preview_hash,
                    decision_source=normalized_source,
                )
            except KnowledgeInjectionContractError as exc:
                return self._fail_knowledge_injection(record, exc, None)
            record = replace(
                record,
                envelope=envelope,
                lifecycle=record.lifecycle + (envelope.state,),
            )
            method = (
                "knowledge.injection.approved"
                if envelope.state is KnowledgeInjectionState.APPROVED
                else "knowledge.injection.rejected"
            )
            event, record = self._injection_event(record, method)
            return self._result((event,), record.to_dict(include_serialized_context=False))

    def knowledge_injection_status(
        self,
        injection_id: str,
        *,
        include_serialized_context: bool = False,
    ) -> dict[str, Any]:
        with self._knowledge_injection_lock:
            return self._require_knowledge_injection(injection_id).to_dict(
                include_serialized_context=include_serialized_context
            )

    def dispatch_approved_knowledge_turn(
        self,
        injection_id: str,
        model_gateway: Any,
        gateway_payload: Mapping[str, Any],
        emit_model_event: Callable[[str, str, int, Mapping[str, Any]], None],
        *,
        turn_id: str | None = None,
        emit_injection_event: Callable[[ControlPlaneEvent], None] | None = None,
    ) -> dict[str, Any]:
        """Dispatch through the existing gateway without exposing Adapter or Vault access."""
        with self._knowledge_injection_lock:
            record = self._require_knowledge_injection(injection_id)
            expected_turn_id = turn_id if turn_id is not None else record.envelope.turn_id
            if record.envelope.state is not KnowledgeInjectionState.APPROVED:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_NOT_APPROVED",
                    "knowledge injection envelope is not APPROVED",
                )
            try:
                self._validate_injection_current(record, expected_turn_id)
                self._validate_gateway_prompt(expected_turn_id, gateway_payload)
            except KnowledgeInjectionContractError as exc:
                failure = self._fail_knowledge_injection(record, exc, emit_injection_event)
                raise ControlPlaneError(exc.code, exc.safe_message, details=failure.response) from exc

        def before_outbound(messages: tuple[dict[str, str], ...]) -> None:
            with self._knowledge_injection_lock:
                current = self._require_knowledge_injection(injection_id)
                try:
                    self._validate_injection_current(current, expected_turn_id)
                    verify_provider_messages(
                        messages,
                        current.envelope,
                        expected_turn_id=expected_turn_id,
                    )
                except (ControlPlaneError, KnowledgeInjectionContractError) as exc:
                    if isinstance(exc, ControlPlaneError):
                        contract_error = KnowledgeInjectionContractError(exc.code, exc.message)
                    else:
                        contract_error = exc
                    self._fail_knowledge_injection(current, contract_error, emit_injection_event)
                    raise contract_error

        def after_outbound(messages: tuple[dict[str, str], ...]) -> None:
            with self._knowledge_injection_lock:
                current = self._require_knowledge_injection(injection_id)
                verify_provider_messages(
                    messages,
                    current.envelope,
                    expected_turn_id=expected_turn_id,
                )
                injected = mark_envelope_injected(current.envelope)
                current = replace(
                    current,
                    envelope=injected,
                    lifecycle=current.lifecycle + (KnowledgeInjectionState.INJECTED,),
                )
                event, current = self._injection_event(current, "knowledge.injection.injected")
                if emit_injection_event is not None:
                    emit_injection_event(event)

        try:
            return model_gateway.start_turn_with_knowledge(
                gateway_payload,
                emit_model_event,
                record.envelope,
                control_plane_turn_id=expected_turn_id,
                before_outbound_request=before_outbound,
                after_outbound_request=after_outbound,
            )
        except KnowledgeInjectionContractError as exc:
            with self._knowledge_injection_lock:
                current = self._require_knowledge_injection(injection_id)
                failure = self._fail_knowledge_injection(current, exc, emit_injection_event)
            raise ControlPlaneError(exc.code, exc.safe_message, details=failure.response) from exc

    def _validate_gateway_prompt(self, turn_id: str, gateway_payload: Mapping[str, Any]) -> None:
        if turn_id not in self._turns:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_NOT_FOUND",
                "knowledge injection Turn was not found",
            )
        prompt = gateway_payload.get("prompt")
        if not isinstance(prompt, str):
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_MISMATCH",
                "model request prompt does not match the knowledge Turn",
            )
        normalized = _normalize_prompt(prompt)
        if hashlib.sha256(normalized.encode("utf-8")).hexdigest() != self._turns[turn_id].prompt_sha256:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_MISMATCH",
                "model request prompt does not match the knowledge Turn",
            )

    def _validate_injection_current(
        self,
        record: KnowledgeInjectionRecord,
        expected_turn_id: str,
    ) -> None:
        envelope = record.envelope
        verify_envelope_integrity(envelope)
        if envelope.turn_id != expected_turn_id:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_MISMATCH",
                "knowledge injection envelope belongs to a different Turn",
            )
        if expected_turn_id not in self._turns:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_NOT_FOUND",
                "knowledge injection Turn was not found",
            )
        if self._turn_current_knowledge_request.get(expected_turn_id) != envelope.request_id:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_STALE_REQUEST",
                "knowledge request is no longer current for the Turn",
            )
        knowledge_record = self._knowledge_requests.get(envelope.request_id)
        if (
            knowledge_record is None
            or knowledge_record.result.state is not KnowledgeContextState.READY
            or knowledge_record.request.turn_id != expected_turn_id
            or knowledge_record.result.bundle_id != envelope.bundle_id
        ):
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_STALE_REQUEST",
                "knowledge request is no longer valid for injection",
            )
        current_revision = self._current_adapter_vault_revision()
        if current_revision != envelope.vault_revision:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_STALE",
                "KnowledgeAdapter Vault revision changed after preview",
            )

    def _current_adapter_vault_revision(self) -> str | None:
        if self._knowledge_adapter is None:
            return None
        status = getattr(self._knowledge_adapter, "status", None)
        if not callable(status):
            return None
        try:
            value = status()
        except Exception:
            return None
        if not isinstance(value, Mapping):
            return None
        revision = value.get("vault_revision")
        return revision if isinstance(revision, str) else None

    def _fail_knowledge_injection(
        self,
        record: KnowledgeInjectionRecord,
        error: KnowledgeInjectionContractError,
        event_sink: Callable[[ControlPlaneEvent], None] | None,
    ) -> ControlPlaneDispatchResult:
        if record.envelope.state is KnowledgeInjectionState.FAILED:
            return self._result((), record.to_dict(include_serialized_context=False))
        failed_envelope = replace(record.envelope, state=KnowledgeInjectionState.FAILED)
        failed = replace(
            record,
            envelope=failed_envelope,
            lifecycle=record.lifecycle + (KnowledgeInjectionState.FAILED,),
            error=KnowledgeInjectionError(
                code=error.code,
                safe_message=_bounded_text(_sanitize_text(error.safe_message), 512),
            ),
        )
        event, failed = self._injection_event(failed, "knowledge.injection.failed")
        if event_sink is not None:
            event_sink(event)
        return self._result((event,), failed.to_dict(include_serialized_context=False))

    def _injection_event(
        self,
        record: KnowledgeInjectionRecord,
        method: str,
    ) -> tuple[ControlPlaneEvent, KnowledgeInjectionRecord]:
        envelope = record.envelope
        payload: dict[str, Any] = {
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "injection_id": envelope.injection_id,
            "request_id": envelope.request_id,
            "turn_id": envelope.turn_id,
            "state": envelope.state.value,
            "bundle_id": envelope.bundle_id,
            "vault_revision": envelope.vault_revision,
            "preview_hash": envelope.preview_hash,
            "context_sha256": envelope.serialized_context_sha256,
            "source_count": envelope.source_count,
        }
        if method == "knowledge.injection.failed" and record.error is not None:
            payload["error_code"] = record.error.code
        event = ControlPlaneEvent(
            method=method,
            sequence=record.next_sequence,
            reply_to=envelope.injection_id,
            payload=payload,
        )
        updated = replace(record, next_sequence=record.next_sequence + 1)
        self._knowledge_injections[envelope.injection_id] = updated
        return event, updated

    def _require_knowledge_injection(self, injection_id: str) -> KnowledgeInjectionRecord:
        if injection_id not in self._knowledge_injections:
            raise ControlPlaneError(
                "KNOWLEDGE_INJECTION_NOT_FOUND",
                "knowledge injection was not found",
            )
        return self._knowledge_injections[injection_id]

    @staticmethod
    def _ready_knowledge_result(
        request: KnowledgeContextRequest,
        adapter_result: Mapping[str, Any],
    ) -> KnowledgeContextResult:
        if not isinstance(adapter_result, Mapping):
            raise ValueError("KnowledgeAdapter context result must be an object")
        sources = adapter_result.get("sources")
        relations = adapter_result.get("context_relations")
        warnings = adapter_result.get("warnings")
        if not isinstance(sources, (list, tuple)):
            raise ValueError("KnowledgeAdapter sources must be a bounded sequence")
        if not isinstance(relations, (list, tuple)):
            raise ValueError("KnowledgeAdapter relations must be a bounded sequence")
        if not isinstance(warnings, (list, tuple)):
            raise ValueError("KnowledgeAdapter warnings must be a bounded sequence")
        return KnowledgeContextResult(
            request_id=request.request_id,
            turn_id=request.turn_id,
            state=KnowledgeContextState.READY,
            vault_revision=adapter_result["vault_revision"],
            bundle_id=adapter_result["bundle_id"],
            resolved_intent=adapter_result["resolved_intent"],
            source_count=len(sources),
            total_chars=adapter_result["total_chars"],
            truncated=adapter_result["truncated"],
            sources=tuple(sources),
            context_relations=tuple(relations),
            warnings=tuple(warnings),
        )

    def _fail_knowledge_context(
        self,
        record: _KnowledgeContextRecord,
        code: str,
        safe_message: str,
    ) -> ControlPlaneDispatchResult:
        error = KnowledgeContextError(
            code=str(code),
            safe_message=_bounded_text(_sanitize_text(str(safe_message)), 512),
        )
        record.result = KnowledgeContextResult(
            request_id=record.request.request_id,
            turn_id=record.request.turn_id,
            state=KnowledgeContextState.FAILED,
            error=error,
        )
        record.lifecycle.append(KnowledgeContextState.FAILED)
        event = self._knowledge_event(record, "knowledge.context.failed")
        return self._result((event,), self._knowledge_record_snapshot(record))

    def _knowledge_event(
        self,
        record: _KnowledgeContextRecord,
        method: str,
    ) -> ControlPlaneEvent:
        payload: dict[str, Any] = {
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "request_id": record.request.request_id,
            "turn_id": record.request.turn_id,
            "state": record.result.state.value,
        }
        if method == "knowledge.context.requested":
            payload["intent"] = record.request.intent.value
        elif method == "knowledge.context.ready":
            payload.update(
                {
                    "bundle_id": record.result.bundle_id,
                    "vault_revision": record.result.vault_revision,
                    "source_count": record.result.source_count,
                    "total_chars": record.result.total_chars,
                    "truncated": record.result.truncated,
                }
            )
        elif method == "knowledge.context.failed":
            assert record.result.error is not None
            payload["error_code"] = record.result.error.code
        else:
            raise ControlPlaneError("internal_error", "unsupported knowledge lifecycle event")
        event = ControlPlaneEvent(
            method=method,
            sequence=record.next_sequence,
            reply_to=record.request.request_id,
            payload=payload,
        )
        record.next_sequence += 1
        return event

    @staticmethod
    def _knowledge_record_snapshot(record: _KnowledgeContextRecord) -> dict[str, Any]:
        return {
            **record.result.to_dict(),
            "request": {
                "request_id": record.request.request_id,
                "turn_id": record.request.turn_id,
                "intent": record.request.intent.value,
                "max_context_chars": record.request.max_context_chars,
                "max_results": record.request.max_results,
                "include_superseded": record.request.include_superseded,
            },
            "lifecycle": [state.value for state in record.lifecycle],
        }

    def _require_knowledge_request(self, request_id: str) -> _KnowledgeContextRecord:
        if request_id not in self._knowledge_requests:
            raise ControlPlaneError(
                "KNOWLEDGE_REQUEST_NOT_FOUND",
                "knowledge context request was not found",
            )
        return self._knowledge_requests[request_id]

    def _create_session(self, payload: Mapping[str, Any], request_id: str) -> ControlPlaneDispatchResult:
        if len(self._sessions) >= self.limits.maximum_sessions:
            raise ControlPlaneError("budget_exceeded", "session limit reached")
        session = _Session(session_id=self._new_id(), title=_normalize_title(str(payload.get("title", "")), self.limits))
        self._sessions[session.session_id] = session
        event = self._event(
            "session.created",
            request_id,
            0,
            session_id=session.session_id,
            state=session.state,
            metadata={"title": session.title},
        )
        return self._result((event,), self._session_summary(session))

    def _close_session(self, session_id: str, request_id: str) -> ControlPlaneDispatchResult:
        session = self._require_session(session_id)
        if session.state == "CLOSED":
            return self._result((), self._session_summary(session))
        for thread_id in session.thread_ids:
            thread = self._threads[thread_id]
            if thread.active_turn_id:
                turn = self._turns[thread.active_turn_id]
                if turn.state == "RUNNING":
                    raise ControlPlaneError("busy", "running turn blocks session close")
        session.state = "CLOSED"
        for thread_id in session.thread_ids:
            thread = self._threads[thread_id]
            if thread.active_turn_id is None:
                thread.state = "CLOSED"
        self._closed_session_ids.append(session.session_id)
        self._closed_session_ids = self._closed_session_ids[-self.limits.maximum_remembered_closed_sessions :]
        event = self._event("session.closed", request_id, 0, session_id=session.session_id, state=session.state)
        return self._result((event,), self._session_summary(session))

    def _create_thread(self, payload: Mapping[str, Any], request_id: str) -> ControlPlaneDispatchResult:
        session = self._require_session(payload["session_id"])
        if session.state != "OPEN":
            raise ControlPlaneError("invalid_payload", "session is closed")
        if len(session.thread_ids) >= self.limits.maximum_threads_per_session:
            raise ControlPlaneError("budget_exceeded", "thread limit reached")
        thread = _Thread(
            thread_id=self._new_id(),
            session_id=session.session_id,
            title=_normalize_title(str(payload.get("title", "")), self.limits),
        )
        self._threads[thread.thread_id] = thread
        session.thread_ids.append(thread.thread_id)
        event = self._event(
            "thread.created",
            request_id,
            0,
            session_id=session.session_id,
            thread_id=thread.thread_id,
            state=thread.state,
            metadata={"title": thread.title},
        )
        return self._result((event,), self._thread_summary(thread))

    def _start_mock_turn(self, payload: Mapping[str, Any], request_id: str) -> ControlPlaneDispatchResult:
        thread = self._require_thread(payload["thread_id"])
        session = self._sessions[thread.session_id]
        if session.state != "OPEN" or thread.state != "ACTIVE":
            raise ControlPlaneError("invalid_payload", "thread is not active")
        if thread.active_turn_id is not None and self._turns[thread.active_turn_id].state == "RUNNING":
            raise ControlPlaneError("busy", "thread already has an active turn")
        if len(thread.turn_ids) >= self.limits.maximum_turns_per_thread:
            raise ControlPlaneError("budget_exceeded", "turn limit reached")
        prompt = _normalize_prompt(str(payload["prompt"]))
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        preview = _bounded_text(str(sanitize_control_plane_value(prompt)), self.limits.maximum_preview_characters)
        turn = _Turn(
            turn_id=self._new_id(),
            thread_id=thread.thread_id,
            state="RUNNING",
            prompt_sha256=prompt_hash,
            prompt_text=prompt,
            prompt_preview=preview,
            prompt_character_count=len(prompt),
        )
        self._turns[turn.turn_id] = turn
        thread.turn_ids.append(turn.turn_id)
        thread.active_turn_id = turn.turn_id
        behavior = str(payload["behavior"])
        events = self._mock_turn_events(session.session_id, thread.thread_id, turn, request_id, behavior)
        if behavior == "complete":
            turn.state = "COMPLETED"
            thread.active_turn_id = None
            response = {
                "turn_id": turn.turn_id,
                "state": turn.state,
                "model_called": False,
                "tools_executed": 0,
                "events_emitted": len(events),
            }
        else:
            response = {
                "turn_id": turn.turn_id,
                "state": turn.state,
                "model_called": False,
                "tools_executed": 0,
                "events_emitted": len(events),
                (
                    "waiting_for_decision"
                    if behavior == "pending_model"
                    else "waiting_for_cancel"
                ): True,
            }
        return self._result(events, response)

    def _cancel_turn(self, payload: Mapping[str, Any], request_id: str) -> ControlPlaneDispatchResult:
        turn = self._require_turn(payload["turn_id"])
        thread = self._threads[turn.thread_id]
        session = self._sessions[thread.session_id]
        if turn.state == "CANCELLED":
            return self._result((), {**self._turn_summary(turn), "already_cancelled": True})
        if turn.state in {"COMPLETED", "FAILED"}:
            return self._result((), {**self._turn_summary(turn), "already_terminal": True})
        if turn.state != "RUNNING":
            raise ControlPlaneError("request_cancelled", "turn is not running")
        turn.state = "CANCELLING"
        turn.state = "CANCELLED"
        thread.active_turn_id = None
        event = self._event(
            "turn.cancelled",
            request_id,
            0,
            session_id=session.session_id,
            thread_id=thread.thread_id,
            turn_id=turn.turn_id,
            state=turn.state,
            metadata={"reason": payload["reason"], "cleanup_tools_executed": 0},
        )
        return self._result((event,), {**self._turn_summary(turn), "events_emitted": 1})

    def _mock_turn_events(
        self,
        session_id: str,
        thread_id: str,
        turn: _Turn,
        request_id: str,
        behavior: str,
    ) -> tuple[ControlPlaneEvent, ...]:
        events: list[ControlPlaneEvent] = []

        def add(method: str, *, item: _Item | None = None, state: str = "", text: str | None = None, metadata: Mapping[str, Any] | None = None) -> None:
            sequence = len(events)
            events.append(
                self._event(
                    method,
                    request_id,
                    sequence,
                    session_id=session_id,
                    thread_id=thread_id,
                    turn_id=turn.turn_id,
                    item_id=item.item_id if item else None,
                    state=state,
                    kind=item.kind if item else None,
                    text=text,
                    metadata=metadata,
                )
            )
            turn.last_sequence = sequence

        add("turn.started", state=turn.state)
        user = self._item(turn, "user_message", "STARTED")
        add("item.started", item=user, state=user.state)
        user.state = "COMPLETED"
        add("item.completed", item=user, state=user.state, metadata={"prompt_preview": turn.prompt_preview})
        if behavior == "pending_model":
            return self._checked_events(tuple(events))
        status = self._item(turn, "status", "STARTED")
        add("item.started", item=status, state=status.state)
        status.state = "COMPLETED"
        status.text = "Control Plane demo - no model inference or tool execution."
        add("item.completed", item=status, state=status.state, text=status.text)
        if behavior == "wait_for_cancel":
            return self._checked_events(tuple(events))
        assistant = self._item(turn, "assistant_message", "STARTED")
        add("item.started", item=assistant, state=assistant.state)
        assistant.state = "STREAMING"
        fragment_one = "Control Plane demo connected. "
        fragment_two = "No language model was called and no tool execution occurred."
        assistant.text += fragment_one
        add("item.delta", item=assistant, state=assistant.state, text=fragment_one)
        assistant.text += fragment_two
        add("item.delta", item=assistant, state=assistant.state, text=fragment_two)
        assistant.state = "COMPLETED"
        add("item.completed", item=assistant, state=assistant.state)
        add("turn.completed", state="COMPLETED", metadata={"model_called": False, "tools_executed": 0})
        return self._checked_events(tuple(events))

    def _item(self, turn: _Turn, kind: str, state: str) -> _Item:
        if len(turn.item_ids) >= self.limits.maximum_items_per_turn:
            raise ControlPlaneError("budget_exceeded", "item limit reached")
        item = _Item(item_id=self._new_id(), turn_id=turn.turn_id, kind=kind, state=state)
        self._items[item.item_id] = item
        turn.item_ids.append(item.item_id)
        return item

    def _event(
        self,
        method: str,
        reply_to: str,
        sequence: int,
        *,
        session_id: str | None = None,
        thread_id: str | None = None,
        turn_id: str | None = None,
        item_id: str | None = None,
        state: str = "",
        kind: str | None = None,
        text: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ControlPlaneEvent:
        payload = {
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "session_id": session_id,
            "thread_id": thread_id,
            "turn_id": turn_id,
            "item_id": item_id,
            "state": state,
            "kind": kind,
            "text": _bounded_text(str(sanitize_control_plane_value(text)), self.limits.maximum_item_delta_characters) if text is not None else None,
            "metadata": _flat_metadata(metadata or {}),
        }
        return ControlPlaneEvent(method=method, sequence=sequence, reply_to=reply_to, payload=payload)

    def _checked_events(self, events: tuple[ControlPlaneEvent, ...]) -> tuple[ControlPlaneEvent, ...]:
        if len(events) > self.limits.maximum_events_per_request:
            raise ControlPlaneError("budget_exceeded", "event limit reached")
        text_total = sum(len(str(event.payload.get("text") or "")) for event in events)
        if text_total > self.limits.maximum_total_event_text_characters:
            raise ControlPlaneError("payload_too_large", "event text limit reached")
        return events

    def _result(self, events: tuple[ControlPlaneEvent, ...], response: Mapping[str, Any]) -> ControlPlaneDispatchResult:
        return ControlPlaneDispatchResult(events=self._checked_events(events), response=dict(response))

    def _require_session(self, session_id: str) -> _Session:
        if session_id not in self._sessions:
            raise ControlPlaneError("request_not_found", "session not found")
        return self._sessions[session_id]

    def _require_thread(self, thread_id: str) -> _Thread:
        if thread_id not in self._threads:
            raise ControlPlaneError("request_not_found", "thread not found")
        return self._threads[thread_id]

    def _require_turn(self, turn_id: str) -> _Turn:
        if turn_id not in self._turns:
            raise ControlPlaneError("request_not_found", "turn not found")
        return self._turns[turn_id]

    def _session_summary(self, session: _Session) -> dict[str, Any]:
        return {"session_id": session.session_id, "state": session.state, "title": session.title, "thread_count": len(session.thread_ids)}

    def _thread_summary(self, thread: _Thread) -> dict[str, Any]:
        return {
            "thread_id": thread.thread_id,
            "session_id": thread.session_id,
            "state": thread.state,
            "title": thread.title,
            "turn_count": len(thread.turn_ids),
            "active_turn_id": thread.active_turn_id,
        }

    def _turn_summary(self, turn: _Turn) -> dict[str, Any]:
        knowledge_summary = None
        if turn.knowledge_context is not None:
            knowledge_summary = {
                "request_id": turn.knowledge_context.request_id,
                "state": turn.knowledge_context.state.value,
                "vault_revision": turn.knowledge_context.vault_revision,
                "bundle_id": turn.knowledge_context.bundle_id,
                "source_count": turn.knowledge_context.source_count,
                "total_chars": turn.knowledge_context.total_chars,
                "truncated": turn.knowledge_context.truncated,
            }
        return {
            "turn_id": turn.turn_id,
            "thread_id": turn.thread_id,
            "state": turn.state,
            "prompt_sha256": turn.prompt_sha256,
            "prompt_preview": turn.prompt_preview,
            "prompt_character_count": turn.prompt_character_count,
            "item_count": len(turn.item_ids),
            "last_sequence": turn.last_sequence,
            "model_called": turn.model_called,
            "tools_executed": turn.tools_executed,
            "knowledge_request_id": turn.knowledge_request_id,
            "knowledge_context": knowledge_summary,
        }

    def _counts(self) -> dict[str, int]:
        with self._knowledge_review_lock:
            review_count = len(self._knowledge_reviews)
            decision_count = len(self._knowledge_review_decisions)
        return {
            "sessions": len(self._sessions),
            "threads": len(self._threads),
            "turns": len(self._turns),
            "active_turns": sum(1 for thread in self._threads.values() if thread.active_turn_id is not None),
            "knowledge_reviews": review_count,
            "human_review_decisions": decision_count,
        }

    def _new_id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not ID_RE.match(value):
            raise ControlPlaneError("internal_error", "invalid generated id")
        return value


def default_control_plane_limits() -> ControlPlaneLimits:
    return ControlPlaneLimits()


def validate_control_plane_payload(method: str, payload: Mapping[str, Any]) -> tuple[str, ...]:
    findings: list[str] = []
    if method not in CONTROL_PLANE_METHODS:
        return ("unsupported_method",)
    if not isinstance(payload, Mapping):
        return ("payload_not_object",)
    schemas: dict[str, set[str]] = {
        "app.bootstrap": set(),
        "app.status": set(),
        "knowledge.review.decision.create": {
            "review_contract_version",
            "proposal_id",
            "review_artifact_identity",
            "change_identity",
            "observed_vault_revision",
            "decision",
            "comment",
            "actor_identifier",
            "actor_display_name",
            "actor_source",
        },
        "knowledge.review.get": {"review_artifact_identity"},
        "knowledge.review.list": {"offset", "limit"},
        "knowledge.review.refresh": set(),
        "knowledge.review.snapshot": set(),
        "session.create": {"title"},
        "session.get": {"session_id"},
        "session.close": {"session_id"},
        "thread.create": {"session_id", "title"},
        "thread.get": {"thread_id"},
        "turn.start_mock": {"thread_id", "prompt", "behavior"},
        "turn.status": {"turn_id"},
        "turn.cancel": {"turn_id", "reason"},
    }
    optional = {"session.create": {"title"}, "thread.create": {"title"}}
    allowed = schemas[method]
    missing = allowed - set(payload) - optional.get(method, set())
    extra = set(payload) - allowed
    findings.extend(f"missing_{key}" for key in sorted(missing))
    findings.extend(f"unknown_{key}" for key in sorted(extra))
    limits = default_control_plane_limits()
    for key in ("session_id", "thread_id", "turn_id"):
        if key in payload and not _valid_id(payload[key]):
            findings.append(f"invalid_{key}")
    if "title" in payload and not _valid_title(payload["title"], limits):
        findings.append("invalid_title")
    if method == "knowledge.review.list":
        offset = payload.get("offset")
        limit = payload.get("limit")
        if type(offset) is not int or not 0 <= offset <= MAX_KNOWLEDGE_REVIEW_ARTIFACTS:
            findings.append("invalid_offset")
        if type(limit) is not int or not 1 <= limit <= MAX_KNOWLEDGE_REVIEW_PAGE_SIZE:
            findings.append("invalid_limit")
    if method == "knowledge.review.get":
        review_identity = payload.get("review_artifact_identity")
        if type(review_identity) is not str or KNOWLEDGE_REVIEW_ID_RE.fullmatch(review_identity) is None:
            findings.append("invalid_review_artifact_identity")
    if method == "knowledge.review.decision.create":
        review_contract_version = payload.get("review_contract_version")
        if review_contract_version != KNOWLEDGE_CHANGE_REVIEW_CONTRACT:
            findings.append("invalid_review_contract_version")
        proposal_id = payload.get("proposal_id")
        if type(proposal_id) is not str or KNOWLEDGE_PROPOSAL_ID_RE.fullmatch(proposal_id) is None:
            findings.append("invalid_proposal_id")
        review_identity = payload.get("review_artifact_identity")
        if type(review_identity) is not str or KNOWLEDGE_REVIEW_ID_RE.fullmatch(review_identity) is None:
            findings.append("invalid_review_artifact_identity")
        change_identity = payload.get("change_identity")
        if change_identity is not None and (
            type(change_identity) is not str
            or KNOWLEDGE_CHANGE_ID_RE.fullmatch(change_identity) is None
        ):
            findings.append("invalid_change_identity")
        observed_revision = payload.get("observed_vault_revision")
        if type(observed_revision) is not str or VAULT_REVISION_RE.fullmatch(observed_revision) is None:
            findings.append("invalid_observed_vault_revision")
        if payload.get("decision") not in tuple(item.value for item in HumanReviewDecisionValue):
            findings.append("invalid_decision")
        decision_value = payload.get("decision")
        comment = payload.get("comment")
        if type(comment) is not str:
            findings.append("invalid_comment")
        else:
            if len(comment) > MAX_COMMENT_CHARS or "\x00" in comment:
                findings.append("invalid_comment")
            try:
                if len(comment.encode("utf-8")) > MAX_COMMENT_UTF8_BYTES:
                    findings.append("invalid_comment")
            except UnicodeEncodeError:
                findings.append("invalid_comment")
            if (
                decision_value == HumanReviewDecisionValue.REQUEST_CHANGES.value
                and not comment.strip()
            ):
                findings.append("request_changes_comment_required")
        actor_values = (
            (
                "actor_identifier",
                MAX_ACTOR_IDENTIFIER_CHARS,
                MAX_ACTOR_IDENTIFIER_UTF8_BYTES,
            ),
            (
                "actor_display_name",
                MAX_ACTOR_DISPLAY_NAME_CHARS,
                MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES,
            ),
            (
                "actor_source",
                MAX_ACTOR_SOURCE_CHARS,
                MAX_ACTOR_SOURCE_UTF8_BYTES,
            ),
        )
        for actor_key, actor_limit, actor_byte_limit in actor_values:
            actor_value = payload.get(actor_key)
            invalid_actor = (
                type(actor_value) is not str
                or not actor_value.strip()
                or "\x00" in actor_value
                or len(actor_value) > actor_limit
            )
            if not invalid_actor:
                try:
                    invalid_actor = len(actor_value.encode("utf-8")) > actor_byte_limit
                except UnicodeEncodeError:
                    invalid_actor = True
            if invalid_actor:
                findings.append(f"invalid_{actor_key}")
        if payload.get("actor_source") != "LOCALCOMET_REVIEW_CENTER":
            findings.append("invalid_actor_source")
    if method == "turn.start_mock":
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or len(_normalize_prompt(prompt)) > limits.maximum_prompt_characters:
            findings.append("invalid_prompt")
        if payload.get("behavior") not in BEHAVIORS:
            findings.append("invalid_behavior")
    if method == "turn.cancel" and payload.get("reason") not in CANCEL_REASONS:
        findings.append("invalid_cancel_reason")
    return tuple(sorted(set(findings)))


def sanitize_control_plane_value(value: object) -> object:
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, Mapping):
        return {str(key): sanitize_control_plane_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [sanitize_control_plane_value(child) for child in value]
    if isinstance(value, tuple):
        return [sanitize_control_plane_value(child) for child in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return "<REDACTED_TEXT>"


def serialize_control_plane_metadata() -> dict[str, Any]:
    limits = default_control_plane_limits()
    return {
        "version": DESKTOP_CONTROL_PLANE_VERSION,
        "protocol": IPC_PROTOCOL,
        "protocol_version": IPC_PROTOCOL_VERSION,
        "methods": list(CONTROL_PLANE_METHODS),
        "events": list(EVENT_METHODS),
        "session_states": list(SESSION_STATES),
        "thread_states": list(THREAD_STATES),
        "turn_states": list(TURN_STATES),
        "item_states": list(ITEM_STATES),
        "item_kinds": list(ITEM_KINDS),
        "limits": {
            "maximum_sessions": limits.maximum_sessions,
            "maximum_threads_per_session": limits.maximum_threads_per_session,
            "maximum_turns_per_thread": limits.maximum_turns_per_thread,
            "maximum_items_per_turn": limits.maximum_items_per_turn,
            "maximum_prompt_characters": limits.maximum_prompt_characters,
            "maximum_events_per_request": limits.maximum_events_per_request,
            "maximum_knowledge_review_artifacts": limits.maximum_knowledge_review_artifacts,
            "maximum_knowledge_review_page_size": limits.maximum_knowledge_review_page_size,
            "maximum_knowledge_review_decisions": limits.maximum_knowledge_review_decisions,
        },
        "persistence": False,
        "models_connected": False,
        "provider_registry_available": False,
        "harness_registry_available": False,
    }


def status() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "desktop_control_plane_status",
        "version": DESKTOP_CONTROL_PLANE_VERSION,
        "methods": list(CONTROL_PLANE_METHODS),
        "persistence": False,
        "models_connected": False,
        "provider_registry_available": False,
        "harness_registry_available": False,
    }


def report() -> dict[str, Any]:
    metadata = serialize_control_plane_metadata()
    return {
        "ok": True,
        "mode": "desktop_control_plane_report",
        "version": DESKTOP_CONTROL_PLANE_VERSION,
        "summary": {
            "methods": len(metadata["methods"]),
            "events": len(metadata["events"]),
            "persistence": False,
            "models_connected": False,
        },
        "metadata": metadata,
    }


def _secure_id() -> str:
    return secrets.token_hex(12)


def _secure_knowledge_request_id() -> str:
    return f"kreq:{uuid.uuid4()}"


def _secure_knowledge_injection_id() -> str:
    return f"kinj:{uuid.uuid4()}"


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(ID_RE.match(value))


def _valid_title(value: object, limits: ControlPlaneLimits) -> bool:
    return isinstance(value, str) and len(_normalize_title(value, limits)) <= limits.maximum_title_characters


def _normalize_title(value: str, limits: ControlPlaneLimits) -> str:
    return _bounded_text(str(sanitize_control_plane_value(" ".join(value.split()))), limits.maximum_title_characters)


def _normalize_prompt(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _sanitize_text(text: str) -> str:
    value = SECRET_RE.sub("<REDACTED_TEXT>", text)
    value = PATH_RE.sub("<USER_PATH>", value)
    if "Traceback" in value:
        value = value.split("Traceback", 1)[0] + "<REDACTED_TEXT>"
    return _bounded_text(value, 4096)


def _flat_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, bool)) or value is None:
            result[str(key)[:64]] = sanitize_control_plane_value(value)
    return result


def _bounded_text(value: str, limit: int) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit]
