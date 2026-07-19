from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List, Optional

PARALLEL_WORKTREE_VERSION = "v6.73"

ROOT_DIR = get_project_root()
if not ROOT_DIR.exists():
    ROOT_DIR = Path(__file__).resolve().parent.parent

SESSION_DIR = ROOT_DIR / ".localcomet" / "parallel_sessions"
LOCKS_DIR = SESSION_DIR / "locks"
PLANS_DIR = SESSION_DIR / "plans"
ARCHIVE_DIR = SESSION_DIR / "archive"

FORBIDDEN_PATHS = [
    "Projects/Reports/desktop_observer/screenshots",
    "Projects/SelfEdit/opencode_backups",
    "Projects/ComputerUse",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "venv",
    ".venv",
    "node_modules",
    "screenshots",
]


def _ensure_dirs():
    for d in [SESSION_DIR, LOCKS_DIR, PLANS_DIR, ARCHIVE_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _safe_path(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def get_parallel_executor_policy() -> Dict[str, Any]:
    return {
        "version": PARALLEL_WORKTREE_VERSION,
        "policy_name": "Parallel Worktree Executor Protocol",
        "rules": [
            "Two writer sessions must not use the same working directory.",
            "One writer + one reviewer is allowed.",
            "Two writer sessions require separate git worktrees.",
            "Each session must declare allowed paths.",
            "If allowed paths overlap, report conflict.",
            "If a session touches forbidden paths, report HOLD.",
            "Final merge is manual only.",
        ],
        "forbidden_paths": FORBIDDEN_PATHS,
        "generated_at": _now(),
    }


def create_session_plan(session_id: str, task_name: str = "", allowed_paths: Optional[List[str]] = None) -> Dict[str, Any]:
    _ensure_dirs()
    safe_id = _safe_path(session_id)
    plan = {
        "session_id": session_id,
        "safe_id": safe_id,
        "task_name": task_name or "unnamed",
        "allowed_paths": allowed_paths or [],
        "created_at": _now(),
        "status": "planned",
    }
    if allowed_paths:
        for path in allowed_paths:
            normalized = path.replace("\\", "/").lower()
            for forbidden in FORBIDDEN_PATHS:
                if forbidden.lower() in normalized:
                    plan["status"] = "HOLD"
                    plan["hold_reason"] = f"Path '{path}' contains forbidden path '{forbidden}'"
                    break
    plan_path = PLANS_DIR / f"{safe_id}_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan


def validate_session_plan(session_id: str) -> Dict[str, Any]:
    safe_id = _safe_path(session_id)
    plan_path = PLANS_DIR / f"{safe_id}_plan.json"
    if not plan_path.exists():
        return {"ok": False, "error": f"Session plan '{session_id}' not found"}
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    existing_locks = list_active_session_locks()
    conflict = False
    for lock_id, lock_info in existing_locks.items():
        if lock_id != safe_id:
            if lock_info.get("allowed_paths"):
                for path_a in plan.get("allowed_paths", []):
                    for path_b in lock_info.get("allowed_paths", []):
                        if Path(path_a).resolve() == Path(path_b).resolve():
                            conflict = True
                            break
    return {
        "ok": True,
        "session_id": session_id,
        "plan": plan,
        "conflict_detected": conflict,
        "status": "HOLD" if conflict or plan.get("status") == "HOLD" else "safe",
    }


def list_active_session_locks() -> Dict[str, Any]:
    _ensure_dirs()
    locks = {}
    for f in LOCKS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            locks[f.stem] = data
        except Exception:
            pass
    return locks


def check_path_conflicts(session_id: str, proposed_paths: List[str]) -> Dict[str, Any]:
    safe_id = _safe_path(session_id)
    conflicts = []
    for path in proposed_paths:
        resolved = Path(path).resolve()
        normalized = str(resolved).lower()
        for forbidden in FORBIDDEN_PATHS:
            if forbidden.replace("\\", "/").lower() in normalized:
                conflicts.append({"path": path, "reason": f"Contains forbidden path '{forbidden}'", "severity": "HOLD"})
    existing = list_active_session_locks()
    for lock_id, lock_info in existing.items():
        if lock_id != safe_id:
            for lock_path in lock_info.get("allowed_paths", []):
                if Path(lock_path).resolve() == resolved:
                    conflicts.append({"path": path, "reason": f"Path also claimed by session '{lock_id}'", "severity": "conflict"})
    return {"session_id": session_id, "proposed_paths": proposed_paths, "conflicts": conflicts, "conflict_count": len(conflicts)}


def generate_worktree_instructions(session_id: str, branch_name: str = "") -> Dict[str, Any]:
    safe_id = _safe_path(session_id)
    branch = branch_name or f"session/{safe_id}"
    instructions = (
        f"Parallel Worktree Instructions for session '{session_id}':\n"
        f"1. Create a git worktree manually:\n"
        f"   git worktree add ../{safe_id}_worktree {branch}\n"
        f"2. Work in the new worktree directory.\n"
        f"3. Do NOT modify the original working directory simultaneously.\n"
        f"4. After finishing, push/submit for manual merge.\n"
        f"5. Do NOT merge automatically.\n"
        f"6. Declare allowed paths in session plan.\n"
        f"7. Check for path conflicts before starting work."
    )
    return {
        "session_id": session_id,
        "branch": branch,
        "instructions": instructions,
        "auto_executed": False,
        "note": "These instructions are for manual execution only. No automatic git worktree creation.",
    }


def status() -> Dict[str, Any]:
    _ensure_dirs()
    plan_count = len(list(PLANS_DIR.glob("*.json")))
    lock_count = len(list(LOCKS_DIR.glob("*.json")))
    return {
        "ok": True,
        "mode": "parallel_worktree_executor_protocol_status",
        "version": PARALLEL_WORKTREE_VERSION,
        "plans_count": plan_count,
        "locks_count": lock_count,
        "policy": get_parallel_executor_policy(),
    }


def report() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "parallel_worktree_executor_protocol_report",
        "version": PARALLEL_WORKTREE_VERSION,
        "generated_at": _now(),
        "policy": get_parallel_executor_policy(),
        "status": status(),
    }


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"status", "parallel sessions status", "статус параллельных сессий", "pc parallel sessions status"}:
        return status()
    if lower in {"report", "parallel executor protocol", "pc parallel executor protocol"}:
        return report()
    if lower.startswith("план параллельной сессии ") or lower.startswith("parallel session plan "):
        parts = lower.split(" ", 3)
        if len(parts) >= 3:
            session_id = parts[-1]
            return create_session_plan(session_id)
    if lower in {"worktree instructions", "worktree instructions status", "pc worktree instructions"}:
        return generate_worktree_instructions("default")
    return {
        "mode": "parallel_worktree_executor_protocol_unrecognized",
        "version": PARALLEL_WORKTREE_VERSION,
        "result": "Неизвестная команда. Используйте: параллельные сессии статус, parallel sessions status, план параллельной сессии <id>, worktree instructions",
    }
