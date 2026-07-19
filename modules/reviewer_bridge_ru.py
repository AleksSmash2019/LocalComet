from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

REVIEWER_BRIDGE_VERSION = "v6.77"

def _project_root() -> Path:
    for env_name in ("LOCALCOMET_ROOT", "LOCALCOMET_ROOT_DIR"):
        if env_name in os.environ:
            return Path(os.environ[env_name]).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


ROOT_DIR = _project_root()

REVIEWER_DIR = ROOT_DIR / ".localcomet" / "reviewer"
INBOX_DIR = REVIEWER_DIR / "inbox"
OUTBOX_DIR = REVIEWER_DIR / "outbox"
ARCHIVE_DIR = REVIEWER_DIR / "archive"
TEMPLATES_DIR = REVIEWER_DIR / "templates"

_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _ensure_dirs(*directories: Path) -> None:
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _auto_task_id() -> str:
    return "review_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _sanitize_task_id(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return _auto_task_id()

    raw = raw.strip()
    if ".." in raw or "/" in raw or "\\" in raw:
        return _auto_task_id()

    safe = "".join(char if char.isalnum() or char in "-_" else "_" for char in raw)
    safe = safe.strip(" ._-")
    safe = safe[:80]

    if not safe:
        return _auto_task_id()

    if safe.upper() in _WINDOWS_RESERVED_NAMES:
        safe = f"review_{safe.lower()}"

    return safe


def _candidate_paths(task_id: str) -> tuple[Path, Path, Path]:
    inbox_root = INBOX_DIR.resolve()
    paths = (
        INBOX_DIR / f"{task_id}_review_prompt.md",
        INBOX_DIR / f"{task_id}_validation_snapshot.json",
        INBOX_DIR / f"{task_id}_instructions.md",
    )

    for path in paths:
        if path.resolve().parent != inbox_root:
            raise ValueError("Reviewer path escaped the inbox directory.")

    return paths


def _allocate_task_id(requested: str) -> str:
    base = _sanitize_task_id(requested)
    candidate = base
    index = 2

    while any(path.exists() for path in _candidate_paths(candidate)):
        candidate = f"{base}_{index}"
        index += 1

    return candidate


def collect_validation_snapshot() -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {}

    try:
        from modules.computer_use_core_ru import dispatch as computer_use_dispatch

        result = computer_use_dispatch("pc computer contracts")
        summary = result.get("summary", {})
        snapshot["contracts"] = {
            "passed": summary.get("passed"),
            "total": summary.get("total"),
            "ok": result.get("ok"),
        }
    except Exception as exc:
        snapshot["contracts"] = {"error": f"{type(exc).__name__}: {exc}"}

    try:
        from modules.strict_project_stability_ru import dispatch as stability_dispatch

        result = stability_dispatch("проверь проект")
        snapshot["strict"] = {
            "ok": result.get("ok"),
            "hard_failures": result.get("hard_failures"),
            "warnings": result.get("warnings"),
        }
    except Exception as exc:
        snapshot["strict"] = {"error": f"{type(exc).__name__}: {exc}"}

    try:
        from modules.screenshot_capture_policy_ru import (
            is_screenshot_capture_enabled,
            should_allow_screenshot_write,
        )

        snapshot["screenshot"] = {
            "enabled": is_screenshot_capture_enabled(),
            "allow_write": should_allow_screenshot_write(),
        }
    except Exception as exc:
        snapshot["screenshot"] = {"error": f"{type(exc).__name__}: {exc}"}

    try:
        from modules.development_safety_orchestrator_ru import collect_diff_risk_snapshot

        snapshot["diff_risk"] = collect_diff_risk_snapshot()
    except Exception as exc:
        snapshot["diff_risk"] = {"error": f"{type(exc).__name__}: {exc}"}

    return snapshot


def _build_reviewer_prompt(task_id: str, patch_summary: str, snapshot: Dict[str, Any]) -> str:
    contracts = snapshot.get("contracts", {})
    strict = snapshot.get("strict", {})
    screenshot = snapshot.get("screenshot", {})
    diff_risk = snapshot.get("diff_risk", {})

    return "\n".join(
        [
            f"# Review Request: {task_id}",
            "",
            "## Patch Summary",
            patch_summary or "No summary provided.",
            "",
            "## Validation Snapshot",
            f"- Contracts: {contracts.get('passed')}/{contracts.get('total')} PASS (ok={contracts.get('ok')})",
            f"- Strict: ok={strict.get('ok')} hf={strict.get('hard_failures')} w={strict.get('warnings')}",
            f"- Screenshot enabled: {screenshot.get('enabled')}",
            f"- Screenshot allow_write: {screenshot.get('allow_write')}",
            f"- Diff risk verdict: {diff_risk.get('verdict')}",
            f"- Changed files: {diff_risk.get('source_changed')} source, {diff_risk.get('total_changed')} tracked",
            "",
            "## Expected Verdict Format",
            "Respond with exactly one of:",
            "- ACCEPT GREEN (all gates PASS, diff guard GREEN)",
            "- HOLD (gates PASS but diff guard requires review)",
            "- REJECT (gates FAIL or screenshot policy changed)",
            "",
            "## Rule",
            "Do not accept unless contracts, strict, screenshot policy, and diff guard are GREEN.",
            "",
        ]
    )


def _write_exclusive(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def create_reviewer_request(task_id: str = "", patch_summary: str = "") -> Dict[str, Any]:
    _ensure_dirs(INBOX_DIR)
    allocated_id = _allocate_task_id(task_id)
    snapshot = collect_validation_snapshot()
    prompt = _build_reviewer_prompt(allocated_id, patch_summary, snapshot)
    prompt_path, snapshot_path, instructions_path = _candidate_paths(allocated_id)

    created: list[Path] = []
    try:
        _write_exclusive(prompt_path, prompt)
        created.append(prompt_path)

        _write_exclusive(
            snapshot_path,
            json.dumps(snapshot, ensure_ascii=False, indent=2),
        )
        created.append(snapshot_path)

        instructions = (
            f"Instructions for task {allocated_id}:\n"
            f"1. Read the review prompt at {prompt_path.name}\n"
            f"2. Review the validation snapshot at {snapshot_path.name}\n"
            "3. Write your verdict to the outbox with task_id in filename.\n"
            "4. Verdict must be one of: ACCEPT GREEN, HOLD, REJECT.\n"
            "5. Do NOT auto-apply patches.\n"
        )
        _write_exclusive(instructions_path, instructions)
        created.append(instructions_path)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise

    return {
        "ok": True,
        "mode": "reviewer_request_created",
        "version": REVIEWER_BRIDGE_VERSION,
        "task_id": allocated_id,
        "files_created": [str(path) for path in (prompt_path, snapshot_path, instructions_path)],
        "note": "Review request created without overwriting existing artifacts.",
    }


def read_reviewer_verdict(task_id: str) -> Dict[str, Any]:
    safe_id = _sanitize_task_id(task_id)
    outbox_files = sorted(OUTBOX_DIR.glob(f"*{safe_id}*.md")) + sorted(
        OUTBOX_DIR.glob(f"*{safe_id}*.json")
    )

    if not outbox_files:
        return {
            "ok": True,
            "verdict_found": False,
            "note": "No verdict file found in outbox for this task_id.",
        }

    latest = max(outbox_files, key=lambda path: path.stat().st_mtime)
    text = latest.read_text(encoding="utf-8")
    return {
        "ok": True,
        "verdict_found": True,
        "task_id": safe_id,
        "file": str(latest),
        "text": text,
        "classification": classify_reviewer_verdict(text),
    }


def classify_reviewer_verdict(text: str) -> Dict[str, Any]:
    lower = str(text or "").lower()
    has_accept = "accept green" in lower
    has_hold = "hold" in lower
    has_reject = "reject" in lower

    if has_accept and not has_hold and not has_reject:
        return {"verdict": "ACCEPT_GREEN"}
    if has_hold and not has_accept and not has_reject:
        return {"verdict": "HOLD"}
    if has_reject and not has_accept and not has_hold:
        return {"verdict": "REJECT"}
    if sum((has_accept, has_hold, has_reject)) > 1:
        return {"verdict": "CONTRADICTORY"}
    return {"verdict": "UNKNOWN"}


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "reviewer_bridge_status",
        "version": REVIEWER_BRIDGE_VERSION,
        "inbox_count": len(list(INBOX_DIR.glob("*_review_prompt.md"))),
        "outbox_count": len(list(OUTBOX_DIR.glob("*"))),
        "template_count": len(list(TEMPLATES_DIR.glob("*"))),
    }


def report() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "reviewer_bridge_report",
        "version": REVIEWER_BRIDGE_VERSION,
        "generated_at": _now(),
        "status": status(),
    }


def is_reviewer_bridge_command(command: str = "") -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    return (
        lower in {
            "status",
            "reviewer bridge status",
            "статус ревью",
            "pc reviewer bridge status",
            "report",
            "reviewer bridge report",
            "pc reviewer bridge report",
        }
        or lower == "создай запрос ревью"
        or lower.startswith("создай запрос ревью ")
        or lower == "reviewer bridge create"
        or lower.startswith("reviewer bridge create ")
    )


def dispatch(command: str = "") -> Dict[str, Any]:
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")

    if lower in {
        "status",
        "reviewer bridge status",
        "статус ревью",
        "pc reviewer bridge status",
    }:
        return status()

    if lower in {"report", "reviewer bridge report", "pc reviewer bridge report"}:
        return report()

    prefixes = ("создай запрос ревью", "reviewer bridge create")
    for prefix in prefixes:
        if lower == prefix:
            return create_reviewer_request("")
        if lower.startswith(prefix + " "):
            return create_reviewer_request(text[len(prefix) :].strip())

    return {
        "ok": False,
        "mode": "reviewer_bridge_unrecognized",
        "version": REVIEWER_BRIDGE_VERSION,
        "result": (
            "Неизвестная команда. Используйте: создай запрос ревью [task_id], "
            "reviewer bridge create [task_id], статус ревью, reviewer bridge status"
        ),
    }
