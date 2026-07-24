from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from modules.autonomy_policy_ru import (
    ActionProposal,
    AutonomyPolicy,
    BudgetUsage,
    KillSwitchStatus,
    PolicyDecisionType,
    evaluate_action_proposal,
    inspect_kill_switches,
    resolve_project_root,
    serialize_policy_decision,
    validate_target_path,
)

AUTONOMOUS_ACTION_EXECUTOR_VERSION = "v6.84"
APPROVAL_SCOPE_SINGLE_ACTION = "SINGLE_ACTION"
SUPPORTED_OPERATIONS = (
    "read_file",
    "list_directory",
    "search_text",
    "syntax_check",
    "run_allowlisted_test",
    "create_temp_file",
    "write_allowlisted_file",
    "apply_exact_patch",
)
UNSUPPORTED_OPERATIONS = {
    "arbitrary_command", "delete", "download", "install", "kill_switch_change",
    "move", "network", "policy_change", "powershell", "privilege_escalation",
    "registry", "rename", "scheduled_task", "service", "shell", "upload",
}
STATUS_VALUES = ("SUCCESS", "DENIED", "FAILED", "TIMEOUT", "ROLLED_BACK")
OPERATION_ACTIONS = {
    "read_file": {"inspect"},
    "list_directory": {"inspect"},
    "search_text": {"analyze"},
    "syntax_check": {"analyze", "verify"},
    "run_allowlisted_test": {"test"},
    "create_temp_file": {"create_temp"},
    "write_allowlisted_file": {"create_file", "edit_file"},
    "apply_exact_patch": {"apply_patch", "edit_file"},
}
_ZERO_SHA = "0" * 64
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_TOKEN_RE = re.compile(
    "|".join((
        r"sk" + r"-[A-Za-z0-9_\-]{8,}",
        r"ghp" + r"_[A-Za-z0-9_]{8,}",
        r"(?i:bearer\s+[A-Za-z0-9._\-]{8,})",
        r"(?i:(authorization\s*:\s*)[^\r\n]+)",
        r"(?i:((?:pass" + r"word|passwd)\s*[:=]\s*)[^\s'\";]{6,})",
        r"(?i:((?:api[_-]?key|token|sec" + r"ret)\s*[:=]\s*)[^\s'\";]{8,})",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    )),
    re.DOTALL,
)
_USER_PATH_RE = re.compile(
    r"(?i)([A-Z]:\\Us" + r"ers\\[^\\\s]+|/ho" + r"me/[^/\s]+|/Us" + r"ers/[^/\s]+|\\\\[^\\\s]+\\[^\\\s]+)"
)


class ExecutorValidationError(ValueError):
    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


@dataclass(frozen=True)
class ExecutorConfig:
    root: Path
    temporary_roots: tuple[Path, ...] = field(default_factory=tuple)
    write_allowlist: tuple[str, ...] = field(default_factory=tuple)
    test_allowlist: tuple[str, ...] = field(default_factory=tuple)
    max_read_bytes: int = 262_144
    max_write_bytes: int = 1_048_576
    max_directory_entries: int = 500
    max_search_files: int = 200
    max_search_bytes: int = 2_097_152
    max_search_matches: int = 200
    max_subprocess_output_bytes: int = 1_000_000
    default_timeout_seconds: float = 30.0
    max_timeout_seconds: float = 300.0
    allow_test_execution: bool = False
    allow_project_writes: bool = False
    allow_temp_writes: bool = False

    def __post_init__(self) -> None:
        root = Path(self.root).expanduser().resolve()
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "temporary_roots", tuple(sorted(Path(p).expanduser().resolve() for p in self.temporary_roots)))
        object.__setattr__(self, "write_allowlist", _normalize_allowlist(root, self.write_allowlist))
        object.__setattr__(self, "test_allowlist", _normalize_allowlist(root, self.test_allowlist))
        for name, maximum, allow_zero in (
            ("max_read_bytes", 10 * 1024 * 1024, False),
            ("max_write_bytes", 10 * 1024 * 1024, False),
            ("max_directory_entries", 10_000, False),
            ("max_search_files", 5_000, False),
            ("max_search_bytes", 100 * 1024 * 1024, False),
            ("max_search_matches", 10_000, False),
            ("max_subprocess_output_bytes", 10 * 1024 * 1024, False),
        ):
            object.__setattr__(self, name, _int_limit(getattr(self, name), maximum, allow_zero, name))
        object.__setattr__(self, "default_timeout_seconds", _float_limit(self.default_timeout_seconds, 900.0, False, "default_timeout_seconds"))
        object.__setattr__(self, "max_timeout_seconds", _float_limit(self.max_timeout_seconds, 900.0, False, "max_timeout_seconds"))
        if self.default_timeout_seconds > self.max_timeout_seconds:
            raise ValueError("default_timeout_seconds_out_of_bounds")
        for name in ("allow_test_execution", "allow_project_writes", "allow_temp_writes"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name}_not_bool")


@dataclass(frozen=True)
class ExecutableAction:
    proposal: ActionProposal
    operation: str
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalGrant:
    action_id: str
    action_fingerprint: str
    granted: bool
    scope: str = APPROVAL_SCOPE_SINGLE_ACTION


@dataclass(frozen=True)
class ActionResult:
    action_id: str
    action_type: str
    operation: str
    status: str
    ok: bool
    executed: bool
    target: str
    action_fingerprint: str
    approval: Mapping[str, bool]
    policy: Mapping[str, Any]
    timing: Mapping[str, Any]
    bytes_read: int = 0
    bytes_written: int = 0
    original_sha256: str | None = None
    result_sha256: str | None = None
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False
    rollback_performed: bool = False
    error_category: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


def default_executor_config(root: str | Path | None = None) -> ExecutorConfig:
    return ExecutorConfig(root=resolve_project_root(root))


def executor_config_from_dict(data: Mapping[str, Any]) -> ExecutorConfig:
    allowed = set(ExecutorConfig.__dataclass_fields__)
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError("unknown_configuration_key")
    return ExecutorConfig(**dict(data))


def validate_executor_config(config: ExecutorConfig) -> tuple[str, ...]:
    findings: list[str] = []
    if not config.root.exists() or not config.root.is_dir():
        findings.append("invalid_root")
    for rel in (*config.write_allowlist, *config.test_allowlist):
        data = validate_target_path(config.root, rel)
        if not data.get("ok"):
            findings.append("invalid_allowlist")
        if data.get("protected"):
            findings.append("protected_allowlist")
    if len(config.write_allowlist) != len(set(config.write_allowlist)):
        findings.append("duplicate_write_allowlist")
    if len(config.test_allowlist) != len(set(config.test_allowlist)):
        findings.append("duplicate_test_allowlist")
    for temp in config.temporary_roots:
        if not temp.exists() or not temp.is_dir():
            findings.append("invalid_temporary_root")
        if _has_symlink_component(temp, stop_before=temp.parent):
            findings.append("temporary_root_symlink")
    return tuple(sorted(set(findings)))


def serialize_executor_config(config: ExecutorConfig) -> dict[str, Any]:
    return {
        "mode": "autonomous_executor_config",
        "version": AUTONOMOUS_ACTION_EXECUTOR_VERSION,
        "root": "<PROJECT_ROOT>",
        "temporary_roots": [_display_temp_root(config, p) for p in config.temporary_roots],
        "write_allowlist": list(config.write_allowlist),
        "test_allowlist": list(config.test_allowlist),
        "limits": {
            "max_directory_entries": config.max_directory_entries,
            "max_read_bytes": config.max_read_bytes,
            "max_search_bytes": config.max_search_bytes,
            "max_search_files": config.max_search_files,
            "max_search_matches": config.max_search_matches,
            "max_subprocess_output_bytes": config.max_subprocess_output_bytes,
            "max_timeout_seconds": config.max_timeout_seconds,
            "max_write_bytes": config.max_write_bytes,
            "default_timeout_seconds": config.default_timeout_seconds,
        },
        "permissions": {
            "allow_project_writes": config.allow_project_writes,
            "allow_temp_writes": config.allow_temp_writes,
            "allow_test_execution": config.allow_test_execution,
        },
    }


def compute_action_fingerprint(action: ExecutableAction, config: ExecutorConfig) -> str:
    target = _target_info(config, action.proposal.target)
    canonical = {
        "version": AUTONOMOUS_ACTION_EXECUTOR_VERSION,
        "action_id": str(action.proposal.action_id),
        "action_type": str(action.proposal.action_type),
        "operation": str(action.operation),
        "target": target["display"],
        "expected_original_sha256": action.proposal.expected_original_sha256,
        "estimates": {
            "changed_files": action.proposal.estimated_changed_files,
            "changed_lines": action.proposal.estimated_changed_lines,
            "output_bytes": action.proposal.estimated_output_bytes,
            "subprocesses": action.proposal.estimated_subprocesses,
        },
        "parameters": _canonical_json(action.parameters),
    }
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_approval_grant(action: ExecutableAction, config: ExecutorConfig, approval: ApprovalGrant | None) -> dict[str, Any]:
    expected = compute_action_fingerprint(action, config)
    result = {"required": True, "provided": approval is not None, "valid": False, "reason": None}
    if approval is None:
        result["reason"] = "approval_required"
        return result
    if approval.granted is not True:
        result["reason"] = "approval_not_granted"
    elif approval.scope != APPROVAL_SCOPE_SINGLE_ACTION:
        result["reason"] = "approval_scope_mismatch"
    elif approval.action_id != action.proposal.action_id:
        result["reason"] = "approval_action_mismatch"
    elif not _SHA_RE.match(str(approval.action_fingerprint)):
        result["reason"] = "approval_fingerprint_invalid"
    elif approval.action_fingerprint != expected:
        result["reason"] = "approval_fingerprint_mismatch"
    else:
        result["valid"] = True
    return result


def execute_action(
    policy: AutonomyPolicy,
    action: ExecutableAction,
    *,
    config: ExecutorConfig | None = None,
    usage: BudgetUsage | None = None,
    kill_switch: KillSwitchStatus | None = None,
    approval: ApprovalGrant | None = None,
    now: Any = None,
    monotonic: Any = None,
) -> ActionResult:
    clock = _Clock(now, monotonic)
    started_at, start_mono = clock.start()
    cfg = config or default_executor_config(policy.allowed_roots[0] if getattr(policy, "allowed_roots", ()) else None)
    policy_payload: dict[str, Any] = {}
    fingerprint = ""
    display = "<PROJECT_ROOT>"
    approval_payload = {"required": False, "provided": approval is not None, "valid": False}
    try:
        config_findings = validate_executor_config(cfg)
        if config_findings:
            return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "invalid_configuration", warnings=config_findings)
        validation = _validate_action(action)
        if validation:
            return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, validation)
        target = _target_info(cfg, action.proposal.target)
        display = target["display"]
        fingerprint = compute_action_fingerprint(action, cfg)
        if not target["ok"]:
            category = "protected_path" if target["protected"] else "unsafe_path"
            return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category, warnings=target["reasons"])
        switch = kill_switch if kill_switch is not None else inspect_kill_switches(cfg.root)
        decision = evaluate_action_proposal(policy, action.proposal, usage=usage, kill_switch=switch)
        policy_payload = _sanitize_json(serialize_policy_decision(decision))
        if switch.active:
            return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "kill_switch_active")
        if decision.decision == PolicyDecisionType.BLOCK or not decision.budget.get("within_limits", True):
            category = "budget_exceeded" if not decision.budget.get("within_limits", True) else "policy_blocked"
            return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category)
        approval_required = decision.approval_required or action.operation in {"run_allowlisted_test", "create_temp_file", "write_allowlisted_file", "apply_exact_patch"}
        approval_payload = {"required": approval_required, "provided": approval is not None, "valid": not approval_required}
        if approval_required:
            grant = validate_approval_grant(action, cfg, approval)
            approval_payload = {"required": True, "provided": bool(grant["provided"]), "valid": bool(grant["valid"])}
            if not grant["valid"]:
                category = "approval_required" if not grant["provided"] else "approval_mismatch"
                return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category)
        target = _target_info(cfg, action.proposal.target)
        if not target["ok"]:
            category = "protected_path" if target["protected"] else "unsafe_path"
            return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category, warnings=target["reasons"])
        return _execute_operation(policy, action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    except ExecutorValidationError as exc:
        return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, exc.category)
    except Exception:
        return _finish(action, "FAILED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "internal_error")


def serialize_action_result(result: ActionResult) -> dict[str, Any]:
    return {
        "mode": "autonomous_action_result",
        "version": AUTONOMOUS_ACTION_EXECUTOR_VERSION,
        "action_id": result.action_id,
        "action_type": result.action_type,
        "operation": result.operation,
        "status": result.status,
        "ok": result.ok,
        "executed": result.executed,
        "target": result.target,
        "action_fingerprint": result.action_fingerprint,
        "approval": dict(result.approval),
        "policy": _sanitize_json(result.policy),
        "timing": dict(result.timing),
        "bytes_read": result.bytes_read,
        "bytes_written": result.bytes_written,
        "original_sha256": result.original_sha256,
        "result_sha256": result.result_sha256,
        "stdout": _redact(result.stdout),
        "stderr": _redact(result.stderr),
        "output_truncated": result.output_truncated,
        "rollback_performed": result.rollback_performed,
        "error_category": result.error_category,
        "details": _sanitize_json(result.details),
        "warnings": sorted(set(result.warnings)),
    }


def _execute_operation(policy: AutonomyPolicy, action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    op = action.operation
    if op == "read_file":
        return _read_file(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "list_directory":
        return _list_directory(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "search_text":
        return _search_text(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "syntax_check":
        return _syntax_check(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "run_allowlisted_test":
        return _run_allowlisted_test(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "create_temp_file":
        return _create_temp_file(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "write_allowlisted_file":
        return _write_allowlisted_file(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "apply_exact_patch":
        return _apply_exact_patch(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "unsupported_operation")


def _read_file(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    path = target["path"]
    if not path.exists():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_missing")
    if not path.is_file():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "binary_file" if path.is_dir() else "unsafe_path")
    size = path.stat().st_size
    if size > cfg.max_read_bytes:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "size_limit")
    data = path.read_bytes()
    if _looks_binary(data):
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "binary_file")
    text, encoding = _decode_text(data)
    details = {"content": _redact(text), "encoding": encoding}
    return _finish(action, "SUCCESS", True, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, None, bytes_read=len(data), original_sha256=_sha256_bytes(data), result_sha256=_sha256_bytes(data), details=details)


def _list_directory(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    path = target["path"]
    include_hidden = bool(action.parameters.get("include_hidden", True))
    if not path.exists():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_missing")
    if not path.is_dir():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "unsupported_parameters")
    entries = []
    for child in path.iterdir():
        if not include_hidden and child.name.startswith("."):
            continue
        if len(entries) >= cfg.max_directory_entries:
            return _finish(action, "DENIED", False, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "size_limit")
        rel = _rel(cfg.root, child)
        if rel and validate_target_path(cfg.root, rel).get("protected"):
            continue
        entries.append({"name": child.name, "path": _display(rel), "type": _entry_type(child), "symlink": child.is_symlink()})
    entries.sort(key=lambda item: item["name"].lower())
    return _finish(action, "SUCCESS", True, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, None, details={"entries": entries})


def _search_text(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    query = str(action.parameters.get("query", ""))
    if not query or len(query) > 256:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "unsupported_parameters")
    path = target["path"]
    if not path.exists():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_missing")
    case_sensitive = bool(action.parameters.get("case_sensitive", False))
    max_depth = int(action.parameters.get("max_depth", 8))
    needle = query if case_sensitive else query.casefold()
    matches: list[dict[str, Any]] = []
    scanned_files = 0
    scanned_bytes = 0
    roots = [path] if path.is_dir() else [path.parent]
    for base in roots:
        for current, dirs, files in os.walk(base):
            cur_path = Path(current)
            rel_current = _rel(cfg.root, cur_path)
            if rel_current and validate_target_path(cfg.root, rel_current).get("protected"):
                dirs[:] = []
                continue
            depth = len(Path(rel_current).parts) - len(Path(_rel(cfg.root, path)).parts) if rel_current else 0
            if depth >= max_depth:
                dirs[:] = []
            dirs[:] = sorted(d for d in dirs if not (cur_path / d).is_symlink())
            for name in sorted(files):
                file_path = cur_path / name
                if file_path.is_symlink():
                    continue
                rel = _rel(cfg.root, file_path)
                if not rel or validate_target_path(cfg.root, rel).get("protected"):
                    continue
                if not path.is_dir() and file_path != path:
                    continue
                scanned_files += 1
                if scanned_files > cfg.max_search_files:
                    return _finish(action, "DENIED", False, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "size_limit", details={"matches": matches})
                data = file_path.read_bytes()[: cfg.max_read_bytes + 1]
                scanned_bytes += len(data)
                if scanned_bytes > cfg.max_search_bytes:
                    return _finish(action, "DENIED", False, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "size_limit", details={"matches": matches})
                if _looks_binary(data):
                    continue
                text, _ = _decode_text(data[: cfg.max_read_bytes])
                for line_no, line in enumerate(text.splitlines(), 1):
                    hay = line if case_sensitive else line.casefold()
                    if needle in hay:
                        matches.append({"file": _display(rel), "line": line_no, "text": _redact(line)})
                        if len(matches) >= cfg.max_search_matches:
                            return _finish(action, "SUCCESS", True, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, None, output_truncated=True, details={"matches": matches, "scanned_files": scanned_files})
    return _finish(action, "SUCCESS", True, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, None, details={"matches": matches, "scanned_files": scanned_files})


def _syntax_check(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    path = target["path"]
    if path.suffix != ".py":
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "unsupported_parameters")
    if not path.exists():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_missing")
    data = path.read_bytes()
    if len(data) > cfg.max_read_bytes:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "size_limit")
    text, _ = _decode_text(data)
    details: dict[str, Any] = {"syntax_ok": True, "filename": target["display"]}
    category = None
    try:
        ast.parse(text, filename=target["display"])
    except SyntaxError as exc:
        details.update({"syntax_ok": False, "line": exc.lineno, "column": exc.offset, "message": "syntax_error"})
        category = "syntax_error"
    return _finish(action, "SUCCESS" if category is None else "FAILED", category is None, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category, bytes_read=len(data), details=details)


def _run_allowlisted_test(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    rel = target["relative"]
    path = target["path"]
    if not cfg.allow_test_execution:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "test_not_allowlisted")
    if rel not in cfg.test_allowlist:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "test_not_allowlisted")
    if not rel.startswith("tools/") or not Path(rel).name.startswith("test_") or path.suffix != ".py":
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "test_not_allowlisted")
    if path.is_symlink() or not path.is_file():
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "unsafe_path")
    if rel not in _manifest_tests(cfg.root):
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "test_not_allowlisted")
    timeout = _timeout(action.parameters.get("timeout_seconds", cfg.default_timeout_seconds), cfg)
    env = _subprocess_env()
    try:
        proc = subprocess.Popen([sys.executable, rel], cwd=str(cfg.root), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", shell=False, env=env)
        stdout, stderr, timed_out, output_limited = _communicate_bounded(proc, timeout, cfg.max_subprocess_output_bytes)
    except Exception:
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "subprocess_failed")
    if timed_out:
        return _finish(action, "TIMEOUT", False, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "timeout", stdout=stdout, stderr=stderr, output_truncated=True, details={"exit_code": None, "descendant_process_containment": "direct_child_only"})
    category = "output_limit" if output_limited else ("subprocess_failed" if proc.returncode else None)
    status = "FAILED" if category else "SUCCESS"
    return _finish(action, status, category is None, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category, stdout=stdout, stderr=stderr, output_truncated=output_limited, details={"exit_code": proc.returncode, "descendant_process_containment": "direct_child_only"})


def _create_temp_file(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    if not cfg.allow_temp_writes:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_not_allowlisted")
    if not any(_is_relative_to(target["path"], temp) for temp in cfg.temporary_roots):
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_not_allowlisted")
    return _write_new(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)


def _write_allowlisted_file(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    if not cfg.allow_project_writes or target["relative"] not in cfg.write_allowlist:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_not_allowlisted")
    if action.proposal.action_type == "create_file":
        return _write_new(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    return _replace_existing(action, cfg, target, str(action.parameters.get("content", "")), fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)


def _apply_exact_patch(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    if not cfg.allow_project_writes or target["relative"] not in cfg.write_allowlist:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_not_allowlisted")
    old = str(action.parameters.get("old_text", ""))
    new = str(action.parameters.get("new_text", ""))
    if not old or old == new:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "unsupported_parameters")
    path = target["path"]
    if not path.exists():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_missing")
    data = path.read_bytes()
    text, _ = _decode_text(data)
    count = text.count(old)
    if count == 0:
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "patch_not_found")
    if count > 1:
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "patch_not_unique")
    return _replace_existing(action, cfg, target, text.replace(old, new, 1), fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)


def _write_new(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    path = target["path"]
    content = str(action.parameters.get("content", ""))
    problem = _validate_write_target(path, target, cfg, content, must_exist=False)
    if problem:
        return _finish(action, "DENIED" if problem in {"size_limit", "secret_content", "target_exists"} else "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, problem)
    return _atomic_write(action, cfg, target, content.encode("utf-8"), None, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)


def _replace_existing(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], content: str, fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    path = target["path"]
    problem = _validate_write_target(path, target, cfg, content, must_exist=True)
    if problem:
        return _finish(action, "DENIED" if problem in {"size_limit", "secret_content", "target_changed"} else "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, problem)
    original = path.read_bytes()
    original_hash = _sha256_bytes(original)
    if action.proposal.expected_original_sha256 != original_hash:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "hash_mismatch", original_sha256=original_hash)
    return _atomic_write(action, cfg, target, content.encode("utf-8"), original, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)


def _atomic_write(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], data: bytes, original: bytes | None, fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    path = target["path"]
    tmp = path.with_name(f".{path.name}.localcomet-v684-{os.getpid()}.tmp")
    result_hash = _sha256_bytes(data)
    original_hash = _sha256_bytes(original) if original is not None else None
    original_mode = path.stat().st_mode if path.exists() else None
    try:
        with open(tmp, "xb") as handle:
            handle.write(data)
        os.replace(tmp, path)
        if original_mode is not None:
            try:
                os.chmod(path, original_mode)
            except OSError:
                pass
        if _sha256_file(path) != result_hash:
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
                if original_mode is not None:
                    try:
                        os.chmod(path, original_mode)
                    except OSError:
                        pass
            rolled_hash = None if original is None or not path.exists() else _sha256_file(path)
            category = "rollback_failed" if original is not None and rolled_hash != original_hash else "verification_failed"
            return _finish(action, "ROLLED_BACK", False, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category, bytes_written=len(data), original_sha256=original_hash, result_sha256=result_hash, rollback_performed=True)
        return _finish(action, "SUCCESS", True, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, None, bytes_written=len(data), original_sha256=original_hash, result_sha256=result_hash)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        return _finish(action, "FAILED", False, bool(tmp.exists()), target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "write_failed", original_sha256=original_hash)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def _validate_write_target(path: Path, target: Mapping[str, Any], cfg: ExecutorConfig, content: str, *, must_exist: bool) -> str | None:
    if _has_symlink_component(path.parent, stop_before=cfg.root.parent) or path.is_symlink():
        return "unsafe_path"
    if not path.parent.exists():
        return "target_missing"
    if must_exist and not path.exists():
        return "target_missing"
    if not must_exist and path.exists():
        return "target_exists"
    data = content.encode("utf-8")
    if len(data) > cfg.max_write_bytes:
        return "size_limit"
    if _contains_secret(content):
        return "secret_content"
    return None


def _finish(action: ExecutableAction, status: str, ok: bool, executed: bool, target: str, fingerprint: str, approval: Mapping[str, bool], policy: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float, error_category: str | None, *, bytes_read: int = 0, bytes_written: int = 0, original_sha256: str | None = None, result_sha256: str | None = None, stdout: str = "", stderr: str = "", output_truncated: bool = False, rollback_performed: bool = False, details: Mapping[str, Any] | None = None, warnings: tuple[str, ...] | list[str] = ()) -> ActionResult:
    finished_at, duration = clock.finish(start_mono)
    return ActionResult(
        action_id=str(action.proposal.action_id),
        action_type=str(action.proposal.action_type),
        operation=str(action.operation),
        status=status if status in STATUS_VALUES else "FAILED",
        ok=ok and status == "SUCCESS",
        executed=executed,
        target=_redact(target),
        action_fingerprint=fingerprint,
        approval=dict(approval),
        policy=policy,
        timing={"started_at": started_at, "finished_at": finished_at, "duration_seconds": duration},
        bytes_read=bytes_read,
        bytes_written=bytes_written,
        original_sha256=original_sha256,
        result_sha256=result_sha256,
        stdout=_redact(stdout),
        stderr=_redact(stderr),
        output_truncated=output_truncated,
        rollback_performed=rollback_performed,
        error_category=error_category,
        details=_sanitize_json(details or {}),
        warnings=tuple(sorted(set(str(w) for w in warnings))),
    )


def _validate_action(action: ExecutableAction) -> str | None:
    if action.operation not in SUPPORTED_OPERATIONS:
        return "unsupported_operation"
    if action.operation in UNSUPPORTED_OPERATIONS:
        return "unsupported_operation"
    if str(action.proposal.action_type) not in OPERATION_ACTIONS[action.operation]:
        return "invalid_action"
    if action.proposal.requires_network or action.proposal.requires_elevation:
        return "invalid_action"
    if not _parameters_safe(action.parameters):
        return "unsupported_parameters"
    allowed_keys = {
        "read_file": set(),
        "list_directory": {"include_hidden"},
        "search_text": {"query", "case_sensitive", "max_depth"},
        "syntax_check": set(),
        "run_allowlisted_test": {"timeout_seconds"},
        "create_temp_file": {"content"},
        "write_allowlisted_file": {"content"},
        "apply_exact_patch": {"old_text", "new_text"},
    }[action.operation]
    if set(action.parameters) - allowed_keys:
        return "unsupported_parameters"
    if "include_hidden" in action.parameters and not isinstance(action.parameters["include_hidden"], bool):
        return "unsupported_parameters"
    if "case_sensitive" in action.parameters and not isinstance(action.parameters["case_sensitive"], bool):
        return "unsupported_parameters"
    if "max_depth" in action.parameters and (isinstance(action.parameters["max_depth"], bool) or not isinstance(action.parameters["max_depth"], int) or action.parameters["max_depth"] < 0 or action.parameters["max_depth"] > 20):
        return "unsupported_parameters"
    if "timeout_seconds" in action.parameters and (isinstance(action.parameters["timeout_seconds"], bool) or not isinstance(action.parameters["timeout_seconds"], (int, float))):
        return "unsupported_parameters"
    for name in ("content", "old_text", "new_text", "query"):
        if name in action.parameters and not isinstance(action.parameters[name], str):
            return "unsupported_parameters"
    if action.operation in {"create_temp_file", "write_allowlisted_file"} and "content" not in action.parameters:
        return "unsupported_parameters"
    if action.operation == "apply_exact_patch" and not {"old_text", "new_text"} <= set(action.parameters):
        return "unsupported_parameters"
    return None


def _parameters_safe(value: Any, depth: int = 0) -> bool:
    if depth > 5:
        return False
    if value is None or isinstance(value, (str, int, bool)):
        return len(str(value)) <= 4096
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, (bytes, bytearray, Path)) or callable(value):
        return False
    if isinstance(value, (list, tuple)):
        return len(value) <= 50 and all(_parameters_safe(v, depth + 1) for v in value)
    if isinstance(value, Mapping):
        return len(value) <= 50 and all(isinstance(k, str) and len(k) <= 128 and _parameters_safe(v, depth + 1) for k, v in value.items())
    return False


def _target_info(config: ExecutorConfig, raw: str | Path) -> dict[str, Any]:
    data = validate_target_path(config.root, raw)
    rel = str(data.get("relative_path", ""))
    path = config.root.joinpath(*Path(rel).parts) if rel else config.root
    reasons = list(data.get("reasons", ()))
    if data.get("ok"):
        if _has_symlink_component(path if path.exists() else path.parent, stop_before=config.root.parent):
            reasons.append("symlink_escape")
        try:
            resolved = path.resolve(strict=False)
            if not _is_relative_to(resolved, config.root):
                reasons.append("target_escapes_root")
        except Exception:
            reasons.append("target_resolution_failed")
    ok = bool(data.get("ok")) and not reasons
    return {"ok": ok, "path": path, "relative": rel, "display": _display(rel), "protected": bool(data.get("protected")), "reasons": tuple(sorted(set(reasons)))}


def _normalize_allowlist(root: Path, values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        data = validate_target_path(root, value)
        if not data.get("ok") or data.get("protected"):
            raise ValueError("invalid_allowlist")
        normalized.append(str(data["relative_path"]))
    return tuple(sorted(set(normalized), key=str.lower))


def _int_limit(value: Any, maximum: int, allow_zero: bool, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name}_invalid")
    if value < 0 or (not allow_zero and value == 0) or value > maximum:
        raise ValueError(f"{name}_out_of_bounds")
    return value


def _float_limit(value: Any, maximum: float, allow_zero: bool, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name}_invalid")
    if value < 0 or (not allow_zero and value == 0) or value > maximum:
        raise ValueError(f"{name}_out_of_bounds")
    return float(value)


def _canonical_json(value: Any) -> Any:
    json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return value


def _decode_text(data: bytes) -> tuple[str, str]:
    try:
        if data.startswith(b"\xef\xbb\xbf"):
            return data.decode("utf-8-sig"), "utf-8-sig"
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError as exc:
        raise ExecutorValidationError("encoding_error") from exc


def _looks_binary(data: bytes) -> bool:
    return b"\x00" in data[:4096]


def _contains_secret(text: str) -> bool:
    return bool(_TOKEN_RE.search(text))


def _redact(text: Any) -> str:
    value = str(text)
    value = _TOKEN_RE.sub(lambda m: "<PRIVATE_KEY>" if "PRIVATE KEY" in m.group(0).upper() else "<REDACTED_SECRET>", value)
    return _USER_PATH_RE.sub("<USER_PATH>", value)


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, str):
        return _redact(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _sanitize_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_json(v) for v in value]
    return _redact(value)


def _sha256_bytes(data: bytes | None) -> str:
    return hashlib.sha256(data or b"").hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        if os.name == "nt":
            return str(child.resolve(strict=False)).lower().startswith(str(parent.resolve(strict=False)).lower().rstrip("\\/") + os.sep)
        return False


def _has_symlink_component(path: Path, *, stop_before: Path) -> bool:
    path = path.absolute()
    stop = stop_before.resolve(strict=False)
    current = path
    while True:
        try:
            if current.exists() and current.is_symlink():
                return True
        except OSError:
            return True
        if current == stop or current.parent == current:
            return False
        current = current.parent


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return ""


def _display(rel: str) -> str:
    return "<PROJECT_ROOT>" + (f"/{rel}" if rel else "")


def _display_temp_root(config: ExecutorConfig, path: Path) -> str:
    rel = _rel(config.root, path)
    return _display(rel) if rel else "<TEMP_ROOT>"


def _entry_type(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    return "other"


def _bounded(text: str, limit: int) -> str:
    data = text.encode("utf-8", "replace")
    if len(data) <= limit:
        return _redact(text)
    return _redact(data[:limit].decode("utf-8", "replace"))


def _communicate_bounded(proc: subprocess.Popen[str], timeout: float, output_limit: int) -> tuple[str, str, bool, bool]:
    lock = threading.Lock()
    chunks = {"stdout": [], "stderr": []}
    used = {"bytes": 0}
    flags = {"limited": False}

    def reader(name: str, stream: Any) -> None:
        try:
            while True:
                data = stream.read(4096)
                if not data:
                    break
                raw = data.encode("utf-8", "replace")
                with lock:
                    remaining = max(0, output_limit - used["bytes"])
                    if remaining:
                        chunks[name].append(raw[:remaining].decode("utf-8", "replace"))
                    used["bytes"] += len(raw)
                    if used["bytes"] > output_limit and not flags["limited"]:
                        flags["limited"] = True
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        break
        except Exception:
            with lock:
                flags["limited"] = True
                try:
                    proc.kill()
                except Exception:
                    pass

    threads = []
    for name, stream in (("stdout", proc.stdout), ("stderr", proc.stderr)):
        if stream is not None:
            thread = threading.Thread(target=reader, args=(name, stream), daemon=True)
            thread.start()
            threads.append(thread)
    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            proc.kill()
        except Exception:
            pass
        proc.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=5)
    return "".join(chunks["stdout"]), "".join(chunks["stderr"]), timed_out, flags["limited"]


def _timeout(value: Any, config: ExecutorConfig) -> float:
    timeout = _float_limit(value, config.max_timeout_seconds, False, "timeout_seconds")
    return min(timeout, config.max_timeout_seconds)


def _manifest_tests(root: Path) -> set[str]:
    try:
        data = json.loads((root / "localcomet_runtime_manifest.json").read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {str(item).replace("\\", "/") for item in data.get("tests", [])}


def _subprocess_env() -> dict[str, str]:
    env = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    for key in ("SystemRoot", "WINDIR", "TEMP", "TMP"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


class _Clock:
    def __init__(self, now: Any, monotonic: Any):
        self.now = now
        self.monotonic = monotonic

    def _now(self) -> str:
        value = self.now() if callable(self.now) else self.now
        if value is None:
            return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ExecutorValidationError("invalid_action")
            return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return str(value)

    def _mono(self) -> float:
        return float(self.monotonic() if callable(self.monotonic) else time.perf_counter())

    def start(self) -> tuple[str, float]:
        return self._now(), self._mono()

    def finish(self, start: float) -> tuple[str, float]:
        return self._now(), max(0.0, round(self._mono() - start, 6))
