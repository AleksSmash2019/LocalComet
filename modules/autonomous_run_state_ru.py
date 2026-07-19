from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from modules.autonomy_policy_ru import (
    ActionProposal,
    BudgetUsage,
    KillSwitchStatus,
    PolicyDecision,
    PolicyDecisionType,
    RiskLevel,
    evaluate_action_proposal,
)

AUTONOMOUS_RUN_STATE_VERSION = "v6.83"

class RunStateValidationError(ValueError):
    pass

class RunStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

TERMINAL_STATUSES = {RunStatus.FAILED, RunStatus.COMPLETED, RunStatus.CANCELLED}
ALLOWED_TRANSITIONS = {
    RunStatus.CREATED: (RunStatus.PLANNING, RunStatus.CANCELLED),
    RunStatus.PLANNING: (RunStatus.WAITING_APPROVAL, RunStatus.RUNNING, RunStatus.PAUSED, RunStatus.FAILED, RunStatus.CANCELLED),
    RunStatus.WAITING_APPROVAL: (RunStatus.RUNNING, RunStatus.PAUSED, RunStatus.FAILED, RunStatus.CANCELLED),
    RunStatus.RUNNING: (RunStatus.VERIFYING, RunStatus.WAITING_APPROVAL, RunStatus.PAUSED, RunStatus.FAILED, RunStatus.CANCELLED),
    RunStatus.VERIFYING: (RunStatus.RUNNING, RunStatus.WAITING_APPROVAL, RunStatus.PAUSED, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED),
    RunStatus.PAUSED: (RunStatus.PLANNING, RunStatus.WAITING_APPROVAL, RunStatus.RUNNING, RunStatus.FAILED, RunStatus.CANCELLED),
    RunStatus.FAILED: (),
    RunStatus.COMPLETED: (),
    RunStatus.CANCELLED: (),
}
_RUN_ID_RE = re.compile(r"^[0-9a-f]{24}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_STEP_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_SECRET_MARKERS = ("sk-", "ghp_", "password", "passwd", r"bearer\s+", "private key", "token=", "sec" + "ret=")
_SECRET_RE = re.compile("(?i)(" + "|".join(_SECRET_MARKERS) + ")")

@dataclass(frozen=True)
class AutonomousRunState:
    run_id: str
    status: RunStatus | str
    goal_hash: str
    current_step: str | None
    completed_steps: tuple[str, ...]
    failed_steps: tuple[str, ...]
    actions_used: int
    writes_used: int
    changed_files_used: int
    changed_lines_used: int
    subprocesses_used: int
    output_bytes_used: int
    replans_used: int
    started_at: str
    updated_at: str
    termination_reason: str | None = None
    pause_reason: str | None = None
    approval_required: bool = False
    last_action_id: str | None = None

def normalize_goal(goal: str) -> str:
    text = " ".join(str(goal or "").split())
    if not text:
        raise RunStateValidationError("empty_goal")
    if len(text) > 4000:
        raise RunStateValidationError("goal_too_long")
    return text

def compute_goal_hash(goal: str) -> str:
    return hashlib.sha256(normalize_goal(goal).encode("utf-8")).hexdigest()

def _normalize_nonce(session_nonce: str) -> str:
    text = " ".join(str(session_nonce or "").split())
    if not text:
        raise RunStateValidationError("empty_session_nonce")
    if len(text) > 256:
        raise RunStateValidationError("session_nonce_too_long")
    return text

def compute_run_id(goal: str, session_nonce: str) -> str:
    goal_hash = compute_goal_hash(goal)
    source = AUTONOMOUS_RUN_STATE_VERSION + "\n" + goal_hash + "\n" + _normalize_nonce(session_nonce)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:24]

def _format_dt(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RunStateValidationError("naive_datetime")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _parse_dt(text: str) -> datetime:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception as exc:
        raise RunStateValidationError("invalid_timestamp") from exc

def _coerce_now(now: datetime | str | None) -> str:
    if now is None:
        return _format_dt(datetime.now(timezone.utc))
    if isinstance(now, datetime):
        return _format_dt(now)
    text = str(now)
    parsed = _parse_dt(text)
    return _format_dt(parsed)

def _require_monotonic(previous: str, new: str) -> None:
    if _parse_dt(new) < _parse_dt(previous):
        raise RunStateValidationError("timestamp_not_monotonic")

def _sanitize_reason(reason: str | None, *, required: bool = False) -> str | None:
    if reason is None:
        if required:
            raise RunStateValidationError("reason_required")
        return None
    text = " ".join(str(reason).split())
    if not text and required:
        raise RunStateValidationError("reason_required")
    if len(text) > 160:
        raise RunStateValidationError("reason_too_long")
    if _SECRET_RE.search(text):
        raise RunStateValidationError("unsafe_reason")
    return text or None

def _safe_step(step_id: str) -> str:
    text = str(step_id or "")
    if not _STEP_RE.match(text):
        raise RunStateValidationError("unsafe_step_id")
    return text

def create_run_state(goal: str, session_nonce: str, now: datetime | str | None = None) -> AutonomousRunState:
    stamp = _coerce_now(now)
    return AutonomousRunState(
        run_id=compute_run_id(goal, session_nonce),
        status=RunStatus.CREATED,
        goal_hash=compute_goal_hash(goal),
        current_step=None,
        completed_steps=(),
        failed_steps=(),
        actions_used=0,
        writes_used=0,
        changed_files_used=0,
        changed_lines_used=0,
        subprocesses_used=0,
        output_bytes_used=0,
        replans_used=0,
        started_at=stamp,
        updated_at=stamp,
    )

def validate_run_state(state: AutonomousRunState) -> tuple[str, ...]:
    findings: list[str] = []
    status = state.status if isinstance(state.status, RunStatus) else RunStatus(state.status) if str(state.status) in RunStatus._value2member_map_ else None
    if not _RUN_ID_RE.match(str(state.run_id)):
        findings.append("invalid_run_id")
    if not _SHA_RE.match(str(state.goal_hash)):
        findings.append("invalid_goal_hash")
    if status is None:
        findings.append("invalid_status")
    for name in ("actions_used", "writes_used", "changed_files_used", "changed_lines_used", "subprocesses_used", "output_bytes_used", "replans_used"):
        value = getattr(state, name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            findings.append(f"{name}_invalid")
    completed = tuple(state.completed_steps)
    failed = tuple(state.failed_steps)
    if tuple(sorted(set(completed))) != completed:
        findings.append("completed_steps_not_sorted_unique")
    if tuple(sorted(set(failed))) != failed:
        findings.append("failed_steps_not_sorted_unique")
    if set(completed) & set(failed):
        findings.append("step_completed_and_failed")
    for step in (*completed, *failed, *((state.current_step,) if state.current_step else ())):
        if step and not _STEP_RE.match(step):
            findings.append("unsafe_step_id")
    if state.current_step and state.current_step in completed:
        findings.append("current_step_already_completed")
    if status in TERMINAL_STATUSES and state.current_step is not None:
        findings.append("terminal_has_current_step")
    if status not in TERMINAL_STATUSES and state.termination_reason is not None:
        findings.append("non_terminal_has_termination_reason")
    if status != RunStatus.PAUSED and state.pause_reason is not None:
        findings.append("non_paused_has_pause_reason")
    if (status == RunStatus.WAITING_APPROVAL) != bool(state.approval_required):
        findings.append("approval_required_inconsistent")
    try:
        _require_monotonic(state.started_at, state.updated_at)
    except RunStateValidationError:
        findings.append("timestamps_not_monotonic")
    for reason in (state.termination_reason, state.pause_reason):
        if reason and _SECRET_RE.search(reason):
            findings.append("unsafe_reason")
    return tuple(sorted(set(findings)))

def transition_run_state(state: AutonomousRunState, new_status: RunStatus | str, *, now: datetime | str | None = None, current_step: str | None = None, reason: str | None = None, approval_required: bool | None = None) -> AutonomousRunState:
    current = state.status if isinstance(state.status, RunStatus) else RunStatus(str(state.status))
    target = new_status if isinstance(new_status, RunStatus) else RunStatus(str(new_status))
    if target == current or target not in ALLOWED_TRANSITIONS[current]:
        raise RunStateValidationError("invalid_transition")
    stamp = _coerce_now(now)
    _require_monotonic(state.updated_at, stamp)
    pause_reason = _sanitize_reason(reason, required=(target == RunStatus.PAUSED)) if target == RunStatus.PAUSED else None
    termination = _sanitize_reason(reason, required=False) if target in TERMINAL_STATUSES else None
    step = None if target in TERMINAL_STATUSES else (_safe_step(current_step) if current_step else state.current_step)
    if target == RunStatus.WAITING_APPROVAL and approval_required is False:
        raise RunStateValidationError("approval_required_inconsistent")
    if target != RunStatus.WAITING_APPROVAL and approval_required is True:
        raise RunStateValidationError("approval_required_inconsistent")
    waiting = bool(approval_required) if approval_required is not None else target == RunStatus.WAITING_APPROVAL
    return replace(state, status=target, current_step=step, updated_at=stamp, termination_reason=termination, pause_reason=pause_reason, approval_required=waiting)

def record_completed_step(state: AutonomousRunState, step_id: str, *, now: datetime | str | None = None) -> AutonomousRunState:
    step = _safe_step(step_id)
    if step in state.completed_steps:
        raise RunStateValidationError("duplicate_completed_step")
    if step in state.failed_steps:
        raise RunStateValidationError("step_already_failed")
    stamp = _coerce_now(now)
    _require_monotonic(state.updated_at, stamp)
    completed = tuple(sorted((*state.completed_steps, step)))
    current = None if state.current_step == step else state.current_step
    return replace(state, completed_steps=completed, current_step=current, updated_at=stamp)

def record_failed_step(state: AutonomousRunState, step_id: str, sanitized_reason: str, *, now: datetime | str | None = None) -> AutonomousRunState:
    step = _safe_step(step_id)
    _sanitize_reason(sanitized_reason, required=True)
    if step in state.failed_steps:
        raise RunStateValidationError("duplicate_failed_step")
    if step in state.completed_steps:
        raise RunStateValidationError("step_already_completed")
    stamp = _coerce_now(now)
    _require_monotonic(state.updated_at, stamp)
    return replace(state, failed_steps=tuple(sorted((*state.failed_steps, step))), updated_at=stamp)

def _inc(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 1_000_000_000:
        raise RunStateValidationError("invalid_increment")
    return value

def consume_run_budget(state: AutonomousRunState, *, actions: int = 0, writes: int = 0, changed_files: int = 0, changed_lines: int = 0, subprocesses: int = 0, output_bytes: int = 0, replans: int = 0, now: datetime | str | None = None) -> AutonomousRunState:
    stamp = _coerce_now(now)
    _require_monotonic(state.updated_at, stamp)
    return replace(
        state,
        actions_used=state.actions_used + _inc(actions),
        writes_used=state.writes_used + _inc(writes),
        changed_files_used=state.changed_files_used + _inc(changed_files),
        changed_lines_used=state.changed_lines_used + _inc(changed_lines),
        subprocesses_used=state.subprocesses_used + _inc(subprocesses),
        output_bytes_used=state.output_bytes_used + _inc(output_bytes),
        replans_used=state.replans_used + _inc(replans),
        updated_at=stamp,
    )

def serialize_run_state(state: AutonomousRunState) -> dict[str, Any]:
    return {
        "mode": "autonomous_run_state",
        "version": AUTONOMOUS_RUN_STATE_VERSION,
        "run_id": state.run_id,
        "status": str(state.status.value if isinstance(state.status, RunStatus) else state.status),
        "goal_hash": state.goal_hash,
        "current_step": state.current_step,
        "completed_steps": list(state.completed_steps),
        "failed_steps": list(state.failed_steps),
        "actions_used": state.actions_used,
        "writes_used": state.writes_used,
        "changed_files_used": state.changed_files_used,
        "changed_lines_used": state.changed_lines_used,
        "subprocesses_used": state.subprocesses_used,
        "output_bytes_used": state.output_bytes_used,
        "replans_used": state.replans_used,
        "started_at": state.started_at,
        "updated_at": state.updated_at,
        "termination_reason": state.termination_reason,
        "pause_reason": state.pause_reason,
        "approval_required": state.approval_required,
        "last_action_id": state.last_action_id,
    }

def policy_decision_for_run(policy: Any, state: AutonomousRunState, proposal: ActionProposal, kill_switch: KillSwitchStatus | None = None) -> PolicyDecision:
    usage = BudgetUsage(
        actions_used=state.actions_used,
        changed_files_used=state.changed_files_used,
        changed_lines_used=state.changed_lines_used,
        subprocesses_used=state.subprocesses_used,
        output_bytes_used=state.output_bytes_used,
        replans_used=state.replans_used,
    )
    decision = evaluate_action_proposal(policy, proposal, usage=usage, kill_switch=kill_switch)
    status = state.status if isinstance(state.status, RunStatus) else RunStatus(str(state.status))
    reasons = set(decision.reasons)
    if status in TERMINAL_STATUSES:
        reasons.add("run_terminal")
    if status == RunStatus.PAUSED:
        reasons.add("run_paused")
    if status == RunStatus.WAITING_APPROVAL and decision.approval_required:
        reasons.add("run_waiting_approval")
    if reasons != set(decision.reasons):
        return replace(decision, decision=PolicyDecisionType.BLOCK, allowed=False, approval_required=True, risk=max(decision.risk, RiskLevel.HIGH, key=lambda r: ("LOW", "MEDIUM", "HIGH", "CRITICAL").index(r.value)), reasons=tuple(sorted(reasons)))
    return decision
