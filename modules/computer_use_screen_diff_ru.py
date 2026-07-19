
from __future__ import annotations

from typing import Any, Dict
import hashlib
import json

SCREEN_DIFF_VERSION = "v6.47d"


def stable_digest(payload: Any) -> str:
    try:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        text = str(payload)
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def diff_summary(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    before_digest = stable_digest(before)
    after_digest = stable_digest(after)
    changed = before_digest != after_digest
    return {
        "ok": True,
        "mode": "computer_use_screen_diff_summary",
        "version": SCREEN_DIFF_VERSION,
        "before_digest": before_digest,
        "after_digest": after_digest,
        "changed": changed,
        "decision": "replan" if changed else "continue",
    }


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "computer_use_screen_diff_status",
        "version": SCREEN_DIFF_VERSION,
    }


def report() -> Dict[str, Any]:
    return status()


def is_computer_use_screen_diff_command(command: str) -> bool:
    return (command or "").strip().lower() in {"pc computer screen diff status", "pc computer diff status"}


def dispatch(command: str) -> Dict[str, Any]:
    if is_computer_use_screen_diff_command(command):
        return status()
    return {
        "ok": False,
        "mode": "computer_use_screen_diff_unknown_command",
        "command": command,
    }
