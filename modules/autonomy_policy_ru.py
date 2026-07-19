from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

AUTONOMY_POLICY_VERSION = "v6.83"

class _StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value

class AutonomyLevel(_StrEnum):
    LEVEL_0_INSPECT_ONLY = "LEVEL_0_INSPECT_ONLY"
    LEVEL_1_PLAN_ONLY = "LEVEL_1_PLAN_ONLY"
    LEVEL_2_SAFE_AUTOMATION = "LEVEL_2_SAFE_AUTOMATION"
    LEVEL_3_CONTROLLED_EDIT = "LEVEL_3_CONTROLLED_EDIT"
    LEVEL_4_BOUNDED_FULL_AUTONOMY = "LEVEL_4_BOUNDED_FULL_AUTONOMY"

class ActionType(_StrEnum):
    inspect = "inspect"
    analyze = "analyze"
    plan = "plan"
    test = "test"
    verify = "verify"
    create_temp = "create_temp"
    create_file = "create_file"
    edit_file = "edit_file"
    apply_patch = "apply_patch"
    execute_allowlisted = "execute_allowlisted"
    delete = "delete"
    move = "move"
    install = "install"
    network = "network"
    credential_access = "credential_access"
    secret_extraction = "secret_extraction"
    privilege_escalation = "privilege_escalation"
    persistence = "persistence"
    security_bypass = "security_bypass"
    system_change = "system_change"
    policy_change = "policy_change"
    kill_switch_change = "kill_switch_change"
    unknown = "unknown"

class RiskLevel(_StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class PolicyDecisionType(_StrEnum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    BLOCK = "BLOCK"

class KillSwitchMode(_StrEnum):
    NONE = "NONE"
    PAUSE = "PAUSE"
    DISABLE = "DISABLE"
    STOP_FILE = "STOP_FILE"

_LOW = {ActionType.inspect, ActionType.analyze, ActionType.plan, ActionType.verify}
_MEDIUM = {ActionType.test, ActionType.create_temp, ActionType.create_file, ActionType.edit_file, ActionType.apply_patch}
_HIGH = {ActionType.execute_allowlisted, ActionType.move, ActionType.delete, ActionType.install, ActionType.network, ActionType.system_change, ActionType.policy_change, ActionType.kill_switch_change}
_CRITICAL = {ActionType.credential_access, ActionType.secret_extraction, ActionType.privilege_escalation, ActionType.persistence, ActionType.security_bypass}
_PERMANENT = _CRITICAL | {ActionType.kill_switch_change}
_DEFAULT_BLOCKED = tuple(sorted(a.value for a in (
    ActionType.credential_access, ActionType.delete, ActionType.install, ActionType.kill_switch_change,
    ActionType.network, ActionType.persistence, ActionType.policy_change, ActionType.privilege_escalation,
    ActionType.secret_extraction, ActionType.security_bypass, ActionType.system_change,
)))
_PROTECTED = (".git", ".incident_backup", ".localcomet/reviewer", ".localcomet/policies", ".tmp", "__pycache__", ".localcomet/autonomy/STOP")
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_STEP_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")

def _as_enum(enum: type[_StrEnum], value: Any) -> _StrEnum | None:
    try:
        return value if isinstance(value, enum) else enum(str(value))
    except Exception:
        return None

def _finite_number(value: Any, *, allow_zero: bool, maximum: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name}_invalid")
    if value < 0 or (not allow_zero and value == 0) or value > maximum:
        raise ValueError(f"{name}_out_of_bounds")
    return float(value)

def _int_limit(value: Any, *, allow_zero: bool, maximum: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name}_invalid")
    if value < 0 or (not allow_zero and value == 0) or value > maximum:
        raise ValueError(f"{name}_out_of_bounds")
    return value

@dataclass(frozen=True)
class AutonomyBudget:
    max_actions: int = 50
    max_runtime_seconds: float = 900.0
    max_changed_files: int = 5
    max_changed_lines: int = 500
    max_subprocesses: int = 20
    max_output_bytes: int = 1_000_000
    max_replans: int = 3

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_actions", _int_limit(self.max_actions, allow_zero=False, maximum=1000, name="max_actions"))
        object.__setattr__(self, "max_runtime_seconds", _finite_number(self.max_runtime_seconds, allow_zero=False, maximum=86400, name="max_runtime_seconds"))
        object.__setattr__(self, "max_changed_files", _int_limit(self.max_changed_files, allow_zero=True, maximum=100, name="max_changed_files"))
        object.__setattr__(self, "max_changed_lines", _int_limit(self.max_changed_lines, allow_zero=True, maximum=50000, name="max_changed_lines"))
        object.__setattr__(self, "max_subprocesses", _int_limit(self.max_subprocesses, allow_zero=True, maximum=500, name="max_subprocesses"))
        object.__setattr__(self, "max_output_bytes", _int_limit(self.max_output_bytes, allow_zero=True, maximum=100_000_000, name="max_output_bytes"))
        object.__setattr__(self, "max_replans", _int_limit(self.max_replans, allow_zero=True, maximum=20, name="max_replans"))

@dataclass(frozen=True)
class BudgetUsage:
    actions_used: int = 0
    runtime_seconds_used: float = 0.0
    changed_files_used: int = 0
    changed_lines_used: int = 0
    subprocesses_used: int = 0
    output_bytes_used: int = 0
    replans_used: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "actions_used", _int_limit(self.actions_used, allow_zero=True, maximum=1_000_000, name="actions_used"))
        object.__setattr__(self, "runtime_seconds_used", _finite_number(self.runtime_seconds_used, allow_zero=True, maximum=1_000_000, name="runtime_seconds_used"))
        for name in ("changed_files_used", "changed_lines_used", "subprocesses_used", "output_bytes_used", "replans_used"):
            object.__setattr__(self, name, _int_limit(getattr(self, name), allow_zero=True, maximum=1_000_000_000, name=name))

@dataclass(frozen=True)
class AutonomyPolicy:
    version: str = AUTONOMY_POLICY_VERSION
    level: AutonomyLevel | str = AutonomyLevel.LEVEL_1_PLAN_ONLY
    allowed_roots: tuple[Path, ...] = field(default_factory=tuple)
    temporary_roots: tuple[Path, ...] = field(default_factory=tuple)
    allowed_actions: tuple[str, ...] = ("analyze", "inspect", "plan", "verify")
    blocked_actions: tuple[str, ...] = _DEFAULT_BLOCKED
    budgets: AutonomyBudget = field(default_factory=AutonomyBudget)
    required_approval_for_writes: bool = True
    required_approval_for_execute: bool = True
    required_approval_for_network: bool = True
    required_approval_for_delete: bool = True
    protected_relative_paths: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_roots", tuple(Path(p) for p in self.allowed_roots))
        object.__setattr__(self, "temporary_roots", tuple(Path(p) for p in self.temporary_roots))
        object.__setattr__(self, "allowed_actions", tuple(sorted(str(a) for a in self.allowed_actions)))
        object.__setattr__(self, "blocked_actions", tuple(sorted(str(a) for a in self.blocked_actions)))
        object.__setattr__(self, "protected_relative_paths", tuple(sorted(str(p).replace("\\", "/").strip("/") for p in self.protected_relative_paths if str(p).strip())))

@dataclass(frozen=True)
class ActionProposal:
    action_id: str
    action_type: str
    target: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    read_only: bool = True
    reversible: bool = True
    expected_original_sha256: str | None = None
    estimated_changed_files: int = 0
    estimated_changed_lines: int = 0
    estimated_subprocesses: int = 0
    estimated_output_bytes: int = 0
    requires_network: bool = False
    requires_elevation: bool = False

@dataclass(frozen=True)
class KillSwitchStatus:
    active: bool = False
    mode: KillSwitchMode | str = KillSwitchMode.NONE
    reason: str | None = None

@dataclass(frozen=True)
class PolicyDecision:
    action_id: str
    decision: PolicyDecisionType
    allowed: bool
    approval_required: bool
    risk: RiskLevel
    normalized_target: str
    reasons: tuple[str, ...]
    budget: Mapping[str, Any]
    kill_switch: KillSwitchStatus

def default_autonomy_budget() -> AutonomyBudget:
    return AutonomyBudget()

def resolve_project_root(root: str | Path | None = None) -> Path:
    value = root if root is not None else os.environ.get("LOCALCOMET_ROOT") or os.environ.get("LOCALCOMET_ROOT_DIR")
    if value is None or str(value).strip() == "":
        value = Path(__file__).resolve().parents[1]
    return Path(value).expanduser().resolve()

def default_autonomy_policy(root: str | Path | None = None) -> AutonomyPolicy:
    return AutonomyPolicy(allowed_roots=(resolve_project_root(root),), budgets=default_autonomy_budget())

def _relative_display(root: Path, target: Path | None, rel: str = "") -> str:
    return "<PROJECT_ROOT>" + (f"/{rel}" if rel else "")

def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        if os.name == "nt":
            return str(child).lower().startswith(str(parent).lower().rstrip("\\/") + os.sep)
        return False

def validate_target_path(root: str | Path, target: str | Path) -> dict[str, Any]:
    text = str(target)
    reasons: list[str] = []
    if not text.strip():
        reasons.append("empty_target")
    if "\x00" in text:
        reasons.append("nul_target")
    if text.startswith(("\\\\", "//")):
        reasons.append("unc_target")
    if re.match(r"^[A-Za-z]:(?![\\/])", text) or re.match(r"^[A-Za-z]:[\\/]", text):
        reasons.append("windows_absolute_or_drive_target")
    if text.startswith(("/", "\\")):
        reasons.append("absolute_target")
    normalized = text.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        reasons.append("traversal_target")
    if any(p.split(".")[0].upper() in _RESERVED for p in parts):
        reasons.append("reserved_device_target")
    root_path = Path(root).expanduser().resolve()
    rel = "/".join(parts)
    candidate = root_path.joinpath(*parts) if parts else root_path
    try:
        resolved = candidate.resolve(strict=False)
        if not _is_relative_to(resolved, root_path):
            reasons.append("target_escapes_root")
    except Exception:
        reasons.append("target_resolution_failed")
    protected = is_protected_target(root_path, rel) if rel else False
    if protected:
        reasons.append("protected_target")
    return {
        "ok": not reasons,
        "normalized_target": _relative_display(root_path, candidate, rel if not reasons or protected else ""),
        "relative_path": rel,
        "protected": protected,
        "reasons": tuple(sorted(set(reasons))),
    }

def is_protected_target(root: str | Path, target: str | Path) -> bool:
    rel = str(target).replace("\\", "/").strip("/")
    protected = {p.lower() for p in (*_PROTECTED,)}
    rel_lower = rel.lower()
    return any(rel_lower == p or rel_lower.startswith(p + "/") for p in protected)

def _risk_for(action: ActionType | None) -> RiskLevel:
    if action in _CRITICAL:
        return RiskLevel.CRITICAL
    if action in _HIGH:
        return RiskLevel.HIGH
    if action in _MEDIUM:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW

def _json_safe(value: Any, depth: int = 0) -> bool:
    if depth > 5:
        return False
    if value is None or isinstance(value, (str, int, float, bool)):
        return not (isinstance(value, float) and not math.isfinite(value)) and len(str(value)) <= 2048
    if isinstance(value, (list, tuple)):
        return len(value) <= 50 and all(_json_safe(v, depth + 1) for v in value)
    if isinstance(value, dict):
        return len(value) <= 50 and all(isinstance(k, str) and len(k) <= 128 and _json_safe(v, depth + 1) for k, v in value.items())
    return False

def validate_autonomy_policy(policy: AutonomyPolicy) -> tuple[str, ...]:
    findings: list[str] = []
    if policy.version != AUTONOMY_POLICY_VERSION:
        findings.append("invalid_policy_version")
    if _as_enum(AutonomyLevel, policy.level) is None:
        findings.append("unknown_autonomy_level")
    for action in (*policy.allowed_actions, *policy.blocked_actions):
        if _as_enum(ActionType, action) is None:
            findings.append("unknown_action_type")
    if not policy.allowed_roots:
        findings.append("missing_allowed_root")
    for flag in ("required_approval_for_writes", "required_approval_for_execute", "required_approval_for_network", "required_approval_for_delete"):
        if not isinstance(getattr(policy, flag), bool):
            findings.append(f"{flag}_not_bool")
    return tuple(sorted(set(findings)))

def _proposal_findings(proposal: ActionProposal, level: AutonomyLevel) -> tuple[list[str], ActionType | None]:
    reasons: list[str] = []
    action = _as_enum(ActionType, proposal.action_type)
    if action is None or action == ActionType.unknown:
        reasons.append("unknown_action_type")
    if not _ID_RE.match(str(proposal.action_id)):
        reasons.append("malformed_action_id")
    if not _json_safe(dict(proposal.arguments)):
        reasons.append("malformed_arguments")
    for name in ("estimated_changed_files", "estimated_changed_lines", "estimated_subprocesses", "estimated_output_bytes"):
        try:
            _int_limit(getattr(proposal, name), allow_zero=True, maximum=1_000_000_000, name=name)
        except ValueError:
            reasons.append(f"{name}_invalid")
    if proposal.read_only and (proposal.estimated_changed_files or proposal.estimated_changed_lines):
        reasons.append("read_only_has_write_estimate")
    if proposal.requires_elevation:
        reasons.append("requires_elevation")
    if action in {ActionType.create_file, ActionType.edit_file, ActionType.apply_patch} and level in {AutonomyLevel.LEVEL_3_CONTROLLED_EDIT, AutonomyLevel.LEVEL_4_BOUNDED_FULL_AUTONOMY}:
        if not proposal.expected_original_sha256 or not _SHA_RE.match(proposal.expected_original_sha256):
            reasons.append("expected_original_sha256_required")
    if proposal.expected_original_sha256 is not None and not _SHA_RE.match(proposal.expected_original_sha256):
        reasons.append("invalid_expected_original_sha256")
    return reasons, action

def evaluate_budget(budget: AutonomyBudget, usage: BudgetUsage, proposal: ActionProposal | None = None) -> dict[str, Any]:
    add_actions = 1 if proposal else 0
    add_changed_files = int(getattr(proposal, "estimated_changed_files", 0) or 0)
    add_changed_lines = int(getattr(proposal, "estimated_changed_lines", 0) or 0)
    add_subprocesses = int(getattr(proposal, "estimated_subprocesses", 0) or 0)
    add_output = int(getattr(proposal, "estimated_output_bytes", 0) or 0)
    projected = {
        "actions": usage.actions_used + add_actions,
        "runtime_seconds": usage.runtime_seconds_used,
        "changed_files": usage.changed_files_used + add_changed_files,
        "changed_lines": usage.changed_lines_used + add_changed_lines,
        "subprocesses": usage.subprocesses_used + add_subprocesses,
        "output_bytes": usage.output_bytes_used + add_output,
        "replans": usage.replans_used,
    }
    limits = {
        "actions": budget.max_actions,
        "runtime_seconds": budget.max_runtime_seconds,
        "changed_files": budget.max_changed_files,
        "changed_lines": budget.max_changed_lines,
        "subprocesses": budget.max_subprocesses,
        "output_bytes": budget.max_output_bytes,
        "replans": budget.max_replans,
    }
    exceeded = sorted(k for k, v in projected.items() if v > limits[k])
    return {
        "within_limits": not exceeded,
        "exceeded": exceeded,
        "remaining_actions": max(0, budget.max_actions - projected["actions"]),
        "remaining_runtime_seconds": max(0.0, float(budget.max_runtime_seconds - projected["runtime_seconds"])),
        "remaining_changed_files": max(0, budget.max_changed_files - projected["changed_files"]),
        "remaining_changed_lines": max(0, budget.max_changed_lines - projected["changed_lines"]),
        "remaining_subprocesses": max(0, budget.max_subprocesses - projected["subprocesses"]),
        "remaining_output_bytes": max(0, budget.max_output_bytes - projected["output_bytes"]),
        "remaining_replans": max(0, budget.max_replans - projected["replans"]),
    }

def inspect_kill_switches(root: str | Path | None = None, environ: Mapping[str, str] | None = None) -> KillSwitchStatus:
    env = os.environ if environ is None else environ
    truthy = {"1", "true", "yes", "on"}
    if str(env.get("LOCALCOMET_AUTONOMY_DISABLED", "")).strip().lower() in truthy:
        return KillSwitchStatus(True, KillSwitchMode.DISABLE, "autonomy_disabled")
    root_path = resolve_project_root(root)
    stop_path = root_path / ".localcomet" / "autonomy" / "STOP"
    try:
        if stop_path.exists():
            reason = "stop_file_symlink" if stop_path.is_symlink() else "stop_file_present"
            return KillSwitchStatus(True, KillSwitchMode.STOP_FILE, reason)
    except Exception:
        return KillSwitchStatus(True, KillSwitchMode.STOP_FILE, "stop_file_check_failed")
    if str(env.get("LOCALCOMET_AUTONOMY_PAUSE", "")).strip().lower() in truthy:
        return KillSwitchStatus(True, KillSwitchMode.PAUSE, "autonomy_paused")
    return KillSwitchStatus(False, KillSwitchMode.NONE, None)

def evaluate_action_proposal(policy: AutonomyPolicy, proposal: ActionProposal, usage: BudgetUsage | None = None, kill_switch: KillSwitchStatus | None = None) -> PolicyDecision:
    usage = usage or BudgetUsage()
    kill_switch = kill_switch or KillSwitchStatus()
    level = _as_enum(AutonomyLevel, policy.level) or AutonomyLevel.LEVEL_1_PLAN_ONLY
    reasons = list(validate_autonomy_policy(policy))
    p_reasons, action = _proposal_findings(proposal, level)
    reasons.extend(p_reasons)
    target_info = validate_target_path(policy.allowed_roots[0], proposal.target) if policy.allowed_roots else {"ok": False, "normalized_target": "<PROJECT_ROOT>", "reasons": ("missing_allowed_root",)}
    reasons.extend(str(r) for r in target_info.get("reasons", ()))
    budget = evaluate_budget(policy.budgets, usage, proposal)
    if not budget["within_limits"]:
        reasons.extend(f"budget_{item}_exceeded" for item in budget["exceeded"])
    risk = _risk_for(action)
    if action in _PERMANENT or str(proposal.action_type) in policy.blocked_actions:
        reasons.append("permanent_block")
    if proposal.requires_network and (policy.required_approval_for_network or ActionType.network.value in policy.blocked_actions):
        reasons.append("network_unsupported")
    if kill_switch.active:
        reasons.append("kill_switch_active")
    if level == AutonomyLevel.LEVEL_0_INSPECT_ONLY and (action not in {ActionType.inspect, ActionType.analyze} or not proposal.read_only):
        reasons.append("level_0_inspect_only")
    if level == AutonomyLevel.LEVEL_1_PLAN_ONLY and action != ActionType.plan:
        reasons.append("level_plan_only_execution_disabled")
    if level == AutonomyLevel.LEVEL_2_SAFE_AUTOMATION and action in {ActionType.create_file, ActionType.edit_file, ActionType.apply_patch, ActionType.delete, ActionType.install, ActionType.network, ActionType.system_change}:
        reasons.append("level_2_action_not_executable")
    approval = False
    if action in {ActionType.test, ActionType.create_temp, ActionType.create_file, ActionType.edit_file, ActionType.apply_patch, ActionType.execute_allowlisted, ActionType.delete, ActionType.move, ActionType.network}:
        approval = True
    blocked = bool(reasons) and any(r not in {"approval_required"} for r in reasons)
    if risk == RiskLevel.CRITICAL or kill_switch.active or not budget["within_limits"]:
        blocked = True
    decision = PolicyDecisionType.BLOCK if blocked else (PolicyDecisionType.REQUIRE_APPROVAL if approval else PolicyDecisionType.ALLOW)
    return PolicyDecision(
        action_id=str(proposal.action_id),
        decision=decision,
        allowed=decision == PolicyDecisionType.ALLOW,
        approval_required=decision == PolicyDecisionType.REQUIRE_APPROVAL or approval,
        risk=risk,
        normalized_target=str(target_info.get("normalized_target", "<PROJECT_ROOT>")),
        reasons=tuple(sorted(set(reasons))),
        budget=budget,
        kill_switch=kill_switch,
    )

def serialize_policy(policy: AutonomyPolicy) -> dict[str, Any]:
    return {
        "mode": "autonomy_policy",
        "version": policy.version,
        "level": str(policy.level),
        "allowed_roots": ["<PROJECT_ROOT>" for _ in policy.allowed_roots],
        "temporary_roots": ["<TEMP_ROOT>" for _ in policy.temporary_roots],
        "allowed_actions": sorted(policy.allowed_actions),
        "blocked_actions": sorted(policy.blocked_actions),
        "budgets": {
            "max_actions": policy.budgets.max_actions,
            "max_changed_files": policy.budgets.max_changed_files,
            "max_changed_lines": policy.budgets.max_changed_lines,
            "max_output_bytes": policy.budgets.max_output_bytes,
            "max_replans": policy.budgets.max_replans,
            "max_runtime_seconds": policy.budgets.max_runtime_seconds,
            "max_subprocesses": policy.budgets.max_subprocesses,
        },
        "approval": {
            "required_for_delete": policy.required_approval_for_delete,
            "required_for_execute": policy.required_approval_for_execute,
            "required_for_network": policy.required_approval_for_network,
            "required_for_writes": policy.required_approval_for_writes,
        },
        "protected_relative_paths": sorted(policy.protected_relative_paths),
    }

def serialize_policy_decision(decision: PolicyDecision) -> dict[str, Any]:
    return {
        "mode": "autonomy_policy_decision",
        "version": AUTONOMY_POLICY_VERSION,
        "action_id": decision.action_id,
        "decision": decision.decision.value,
        "allowed": decision.allowed,
        "approval_required": decision.approval_required,
        "risk": decision.risk.value,
        "normalized_target": decision.normalized_target,
        "reasons": list(decision.reasons),
        "budget": {k: decision.budget[k] for k in ("within_limits", "remaining_actions", "remaining_runtime_seconds", "remaining_changed_files", "remaining_changed_lines", "remaining_subprocesses", "remaining_output_bytes", "remaining_replans")},
        "kill_switch": {"active": decision.kill_switch.active, "mode": str(decision.kill_switch.mode), "reason": decision.kill_switch.reason},
    }
