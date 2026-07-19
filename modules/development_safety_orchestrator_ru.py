from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

DEVELOPMENT_SAFETY_VERSION = "v6.77"

def _project_root() -> Path:
    for env_name in ("LOCALCOMET_ROOT", "LOCALCOMET_ROOT_DIR"):
        if env_name in os.environ:
            return Path(os.environ[env_name]).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


ROOT_DIR = _project_root()

_SOURCE_SUFFIXES = {
    ".py",
    ".pyw",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ps1",
    ".md",
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT_DIR),
        check=False,
    )


def _parse_status_line(line: str) -> Dict[str, Any]:
    if len(line) < 3:
        return {
            "raw": line,
            "xy": "",
            "path": line.strip(),
            "staged": False,
            "unstaged": False,
            "deleted": False,
        }

    xy = line[:2]
    path = line[3:].strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1].strip()

    return {
        "raw": line,
        "xy": xy,
        "path": path,
        "staged": xy[0] not in {" ", "?"},
        "unstaged": xy[1] not in {" ", "?"},
        "deleted": "D" in xy,
    }


def _git_status_snapshot() -> Dict[str, Any]:
    try:
        result = _run_git("status", "--short", "--untracked-files=no")
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "untracked_ignored_for_risk": True,
        }

    if result.returncode != 0:
        return {
            "ok": False,
            "error": result.stderr.strip() or f"git status exited with {result.returncode}",
            "untracked_ignored_for_risk": True,
        }

    raw_lines = [line for line in result.stdout.splitlines() if line.strip()]
    entries = [_parse_status_line(line) for line in raw_lines]
    tracked_paths = [entry["path"] for entry in entries]
    source_paths = [
        path
        for path in tracked_paths
        if Path(path).suffix.lower() in _SOURCE_SUFFIXES
    ]
    deleted_files = [entry["path"] for entry in entries if entry["deleted"]]

    return {
        "ok": True,
        "total_changed": len(entries),
        "tracked_changed": len(entries),
        "staged_changed": sum(1 for entry in entries if entry["staged"]),
        "unstaged_changed": sum(1 for entry in entries if entry["unstaged"]),
        "untracked": None,
        "untracked_ignored_for_risk": True,
        "source_changed": len(source_paths),
        "source_paths": source_paths,
        "deleted": deleted_files,
        "lines": raw_lines,
        "entries": entries,
    }


def _gate_snapshot() -> Dict[str, Any]:
    result: Dict[str, Any] = {"contracts": {}, "strict": {}}

    try:
        from modules.computer_use_core_ru import dispatch as computer_use_dispatch

        response = computer_use_dispatch("pc computer contracts")
        summary = response.get("summary", {})
        result["contracts"] = {
            "passed": summary.get("passed"),
            "total": summary.get("total"),
            "ok": response.get("ok"),
        }
    except Exception as exc:
        result["contracts"] = {"error": f"{type(exc).__name__}: {exc}", "ok": False}

    try:
        from modules.strict_project_stability_ru import dispatch as stability_dispatch

        response = stability_dispatch("проверь проект")
        result["strict"] = {
            "ok": response.get("ok"),
            "hard_failures": response.get("hard_failures"),
            "warnings": response.get("warnings"),
        }
    except Exception as exc:
        result["strict"] = {"error": f"{type(exc).__name__}: {exc}", "ok": False}

    return result


def _normalize_allow_write(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("allow", False))
    return bool(value)


def _screenshot_policy_snapshot() -> Dict[str, Any]:
    try:
        from modules.screenshot_capture_policy_ru import (
            is_screenshot_capture_enabled,
            should_allow_screenshot_write,
        )

        raw_allow_write = should_allow_screenshot_write()
        return {
            "ok": True,
            "capture_enabled": bool(is_screenshot_capture_enabled()),
            "allow_write": _normalize_allow_write(raw_allow_write),
            "allow_write_raw": raw_allow_write,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _diff_risk_snapshot(git_data: Dict[str, Any]) -> Dict[str, Any]:
    if not git_data.get("ok"):
        return {
            "total_changed": 0,
            "source_changed": 0,
            "deleted_source_count": 0,
            "deleted_files": [],
            "risky_paths": [],
            "untracked_ignored_for_risk": True,
            "verdict": "HOLD_REVIEW_REQUIRED",
            "error": git_data.get("error", "Unable to read tracked Git status."),
        }

    total = int(git_data.get("tracked_changed", 0))
    source = int(git_data.get("source_changed", 0))
    deleted = list(git_data.get("deleted", []))
    risky_paths: list[str] = []

    keywords = {
        "screenshot",
        "backup",
        "venv",
        "node_modules",
        ".git",
        "credentials",
        ".env",
        "secret",
    }

    for path in (entry.get("path", "") for entry in git_data.get("entries", [])):
        lower_path = path.lower()
        if any(keyword in lower_path for keyword in keywords):
            risky_paths.append(path)

    verdict = "GREEN_TO_CONTINUE"
    if source >= 9 or total >= 16:
        verdict = "HOLD"
    if source > 15:
        verdict = "HOLD_REVIEW_REQUIRED"
    if total > 50:
        verdict = "REJECT_RECOVERY_REQUIRED"
    if deleted:
        verdict = "HOLD_REVIEW_REQUIRED"
    if risky_paths and verdict == "GREEN_TO_CONTINUE":
        verdict = "HOLD"

    return {
        "total_changed": total,
        "source_changed": source,
        "deleted_source_count": len(deleted),
        "deleted_files": deleted,
        "risky_paths": risky_paths,
        "untracked_ignored_for_risk": True,
        "verdict": verdict,
    }


def collect_git_status_snapshot() -> Dict[str, Any]:
    return _git_status_snapshot()


def collect_gate_snapshot() -> Dict[str, Any]:
    return _gate_snapshot()


def collect_screenshot_policy_snapshot() -> Dict[str, Any]:
    return _screenshot_policy_snapshot()


def collect_diff_risk_snapshot() -> Dict[str, Any]:
    git_data = _git_status_snapshot()
    result = _diff_risk_snapshot(git_data)
    result["mode"] = "development_safety_diff_snapshot"
    result["version"] = DEVELOPMENT_SAFETY_VERSION
    return result


def evaluate_development_safety() -> Dict[str, Any]:
    git_data = _git_status_snapshot()
    gates = _gate_snapshot()
    screenshot = _screenshot_policy_snapshot()
    diff = _diff_risk_snapshot(git_data)

    contracts_ok = gates.get("contracts", {}).get("ok") is True
    strict_ok = gates.get("strict", {}).get("ok") is True
    gates_ok = contracts_ok and strict_ok

    screenshot_ok = (
        screenshot.get("ok") is True
        and screenshot.get("capture_enabled") is False
        and screenshot.get("allow_write") is False
    )

    if not git_data.get("ok") or not screenshot.get("ok"):
        overall = "HOLD_REVIEW_REQUIRED"
    elif screenshot_ok and gates_ok and diff.get("verdict") == "GREEN_TO_CONTINUE":
        overall = "GREEN_TO_CONTINUE"
    elif not gates_ok:
        overall = "HOLD_REVIEW_REQUIRED"
    elif not screenshot_ok:
        overall = "REJECT_RECOVERY_REQUIRED"
    else:
        overall = diff.get("verdict", "HOLD")

    return {
        "ok": True,
        "mode": "development_safety_evaluation",
        "version": DEVELOPMENT_SAFETY_VERSION,
        "generated_at": _now(),
        "git_status": git_data,
        "gates": gates,
        "screenshot_policy": screenshot,
        "diff_risk": diff,
        "overall_verdict": overall,
    }


def _lightweight_status() -> Dict[str, Any]:
    git_data = _git_status_snapshot()
    screenshot = _screenshot_policy_snapshot()
    diff = _diff_risk_snapshot(git_data)

    contracts_skip = {
        "ok": None,
        "executed": False,
        "reason": "not_run_in_lightweight_status",
    }
    strict_skip = {
        "ok": None,
        "executed": False,
        "reason": "not_run_in_lightweight_status",
    }

    if not git_data.get("ok") or not screenshot.get("ok"):
        overall = "HOLD_REVIEW_REQUIRED"
    elif screenshot.get("capture_enabled") or screenshot.get("allow_write"):
        overall = "REJECT_RECOVERY_REQUIRED"
    else:
        overall = diff.get("verdict", "HOLD")

    return {
        "ok": True,
        "mode": "development_safety_evaluation",
        "version": DEVELOPMENT_SAFETY_VERSION,
        "generated_at": _now(),
        "lightweight": True,
        "git_status": git_data,
        "gates": {
            "contracts": contracts_skip,
            "strict": strict_skip,
        },
        "screenshot_policy": screenshot,
        "diff_risk": diff,
        "overall_verdict": overall,
    }


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "development_safety_orchestrator_status",
        "version": DEVELOPMENT_SAFETY_VERSION,
        "evaluation": _lightweight_status(),
    }


def report() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "development_safety_orchestrator_report",
        "version": DEVELOPMENT_SAFETY_VERSION,
        "generated_at": _now(),
        "status": {
            "ok": True,
            "mode": "development_safety_orchestrator_status",
            "version": DEVELOPMENT_SAFETY_VERSION,
            "evaluation": evaluate_development_safety(),
        },
    }


def is_development_safety_command(command: str = "") -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {
        "status",
        "development safety status",
        "dev safety status",
        "статус разработки",
        "pc dev safety status",
        "report",
        "pc dev safety report",
        "preflight audit",
        "pc preflight audit",
        "diff limit status",
        "pc diff limit status",
        "opencode recovery status",
        "pc opencode recovery status",
    }


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")

    if lower in {
        "status",
        "development safety status",
        "dev safety status",
        "статус разработки",
        "pc dev safety status",
    }:
        return status()

    if lower in {"report", "pc dev safety report"}:
        return report()

    if lower in {"preflight audit", "pc preflight audit"}:
        return evaluate_development_safety()

    if lower in {"diff limit status", "pc diff limit status"}:
        return collect_diff_risk_snapshot()

    if lower in {"opencode recovery status", "pc opencode recovery status"}:
        return evaluate_development_safety()

    return {
        "ok": False,
        "mode": "development_safety_orchestrator_unrecognized",
        "version": DEVELOPMENT_SAFETY_VERSION,
        "result": (
            "Неизвестная команда. Используйте: статус разработки, "
            "development safety status, preflight audit, diff limit status, "
            "opencode recovery status"
        ),
    }
