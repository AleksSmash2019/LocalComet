
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict
import json
import re
import uuid

TYPE_GUARD_VERSION = "v6.47d"
ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
TYPE_GUARD_DIR = COMPUTER_USE_DIR / "type_guard"

FILE_CHANGE_TEXT_PATTERNS = [
    r"\b(write|save|edit|modify|patch|create|overwrite)\b.{0,80}\b(file|response\.json|\.py|\.md|\.txt|\.json)\b",
    r"\b(file|response\.json|\.py|\.md|\.txt|\.json)\b.{0,80}\b(write|save|edit|modify|patch|create|overwrite)\b",
    r"(запиш|сохран|редакт|измени|созда[йт]|патч).{0,80}(файл|response\.json|\.py|\.md|\.txt|\.json)",
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)
    TYPE_GUARD_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _text_changes_files(text: str) -> bool:
    value = str(text or "").lower()
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in FILE_CHANGE_TEXT_PATTERNS)


def validate_type_text(text: str, allow_unicode: bool = True, max_chars: int = 500) -> Dict[str, Any]:
    value = str(text or "")
    if not value:
        return {
            "ok": False,
            "mode": "computer_use_type_text_validation",
            "reason": "Text is empty.",
            "requires_confirmation": False,
            "blocked": False,
        }

    if len(value) > max_chars:
        return {
            "ok": False,
            "mode": "computer_use_type_text_validation",
            "reason": f"Text length {len(value)} exceeds max_chars={max_chars}.",
            "requires_confirmation": True,
            "blocked": False,
            "char_count": len(value),
        }

    if _text_changes_files(value):
        return {
            "ok": False,
            "mode": "computer_use_type_text_validation",
            "reason": "Text appears to describe file-changing content and requires confirmation.",
            "requires_confirmation": True,
            "blocked": False,
            "char_count": len(value),
        }

    if not allow_unicode and any(ord(ch) > 127 for ch in value):
        return {
            "ok": False,
            "mode": "computer_use_type_text_validation",
            "reason": "Unicode typing requires clipboard/IME adapter and is disabled by current policy.",
            "requires_confirmation": True,
            "blocked": False,
            "char_count": len(value),
        }

    return {
        "ok": True,
        "mode": "computer_use_type_text_validation",
        "reason": "Text is safe for GUI typing.",
        "requires_confirmation": False,
        "blocked": False,
        "char_count": len(value),
        "unicode": any(ord(ch) > 127 for ch in value),
    }


def plan_guarded_type(description: str, text: str, min_confidence: float = 0.35, allow_unicode: bool = True) -> Dict[str, Any]:
    from modules.computer_use_focus_guard_ru import plan_focus

    text_validation = validate_type_text(text, allow_unicode=allow_unicode)
    focus_plan = plan_focus(description, min_confidence=min_confidence)

    if not focus_plan.get("ok"):
        return {
            "ok": False,
            "mode": "computer_use_guarded_type_plan",
            "description": description,
            "text_length": len(text or ""),
            "reason": focus_plan.get("reason", "focus plan failed"),
            "focus_plan": focus_plan,
            "text_validation": text_validation,
        }

    if text_validation.get("blocked"):
        return {
            "ok": False,
            "mode": "computer_use_guarded_type_plan",
            "description": description,
            "text_length": len(text or ""),
            "reason": text_validation.get("reason"),
            "blocked": True,
            "focus_plan": focus_plan,
            "text_validation": text_validation,
        }

    if text_validation.get("requires_confirmation"):
        return {
            "ok": False,
            "mode": "computer_use_guarded_type_plan",
            "description": description,
            "text_length": len(text or ""),
            "reason": text_validation.get("reason"),
            "requires_confirmation": True,
            "focus_plan": focus_plan,
            "text_validation": text_validation,
        }

    target = focus_plan["focus_action"].get("target", {})
    type_action = {
        "kind": "type",
        "target": target,
        "text": text,
        "grounded": True,
        "focused_target": True,
        "confidence": focus_plan.get("focus_target", {}).get("confidence"),
        "element_id": focus_plan.get("focus_target", {}).get("element_id"),
        "reason": f"GUI screen guarded type into verified input field: {description}",
        "goal": f"gui screen type into verified input {description}",
        "modifies_files": False,
        "ui_intent": "verified_input_type",
        "gui_only": True,
        "file_change_policy": "requires_explicit_modifies_files_true",
    }

    from modules.computer_use_auto_action_ru import auto_policy_for_action
    type_policy = auto_policy_for_action(type_action)

    return {
        "ok": bool(type_policy.get("ok")) and not type_policy.get("blocked"),
        "mode": "computer_use_guarded_type_plan",
        "version": TYPE_GUARD_VERSION,
        "description": description,
        "text_length": len(text or ""),
        "focus_plan": focus_plan,
        "type_action": type_action,
        "type_policy": type_policy,
        "text_validation": text_validation,
        "can_execute": bool(focus_plan.get("can_execute")) and bool(type_policy.get("allowed_to_execute")) and not bool(type_policy.get("requires_confirmation")),
        "requires_confirmation": bool(focus_plan.get("requires_confirmation")) or bool(type_policy.get("requires_confirmation")),
    }


def guarded_type(description: str, text: str, simulate: bool = False, min_confidence: float = 0.35, allow_unicode: bool = True) -> Dict[str, Any]:
    plan = plan_guarded_type(description, text, min_confidence=min_confidence, allow_unicode=allow_unicode)
    if not plan.get("ok"):
        result = {
            "ok": False,
            "mode": "computer_use_guarded_type",
            "description": description,
            "text_length": len(text or ""),
            "reason": plan.get("reason", "guarded type plan failed"),
            "requires_confirmation": plan.get("requires_confirmation", False),
            "blocked": plan.get("blocked", False),
            "plan": plan,
        }
        return _save_result("guarded_type_refused", result)

    if plan.get("requires_confirmation") or not plan.get("can_execute"):
        result = {
            "ok": False,
            "mode": "computer_use_guarded_type",
            "description": description,
            "text_length": len(text or ""),
            "requires_confirmation": bool(plan.get("requires_confirmation")),
            "reason": plan.get("type_policy", {}).get("reason", "guarded type cannot execute"),
            "plan": plan,
        }
        return _save_result("guarded_type_requires_confirmation", result)

    from modules.computer_use_visual_guard_ru import guarded_execute

    focus_action = plan["focus_plan"]["focus_action"]
    type_action = plan["type_action"]

    focus_guarded = guarded_execute(focus_action, simulate=simulate)
    type_guarded = guarded_execute(type_action, simulate=simulate)
    observation = type_guarded.get("after", {}).get("observation", {})

    result = {
        "ok": (
            (bool(focus_guarded.get("ok")) or bool(focus_guarded.get("execution", {}).get("simulated")))
            and (bool(type_guarded.get("ok")) or bool(type_guarded.get("execution", {}).get("simulated")))
        ),
        "mode": "computer_use_guarded_type",
        "version": TYPE_GUARD_VERSION,
        "description": description,
        "text_length": len(text or ""),
        "simulated": simulate,
        "plan": plan,
        "focus_execution": focus_guarded.get("execution", {}),
        "type_execution": type_guarded.get("execution", {}),
        "after_observation": observation,
        "focus_visual_guard": focus_guarded,
        "type_visual_guard": type_guarded,
        "next_decision": type_guarded.get("next_decision"),
        "created_at": _now(),
    }
    return _save_result("guarded_type_result", result)


def _save_result(prefix: str, result: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_dirs()
    path = TYPE_GUARD_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    result["artifact"] = _write_json(path, result)
    return result


def status() -> Dict[str, Any]:
    _ensure_dirs()
    return {
        "ok": True,
        "mode": "computer_use_type_guard_status",
        "version": TYPE_GUARD_VERSION,
        "type_guard_dir": str(TYPE_GUARD_DIR),
    }


def report() -> Dict[str, Any]:
    return status()


def is_computer_use_type_guard_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = [
        "pc computer guarded type into",
        "pc computer simulate guarded type into",
        "pc computer plan guarded type into",
        "безопасный ввод в",
    ]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def _split_type_command(raw: str, prefix: str) -> Dict[str, str]:
    tail = raw[len(prefix):].strip()
    if "::" not in tail:
        return {"description": tail, "text": ""}
    description, text = tail.split("::", 1)
    return {"description": description.strip(), "text": text.strip()}


def dispatch(command: str) -> Dict[str, Any]:
    raw = (command or "").strip()
    value = raw.lower()

    if value == "pc computer type guard status":
        return status()

    if value.startswith("pc computer plan guarded type into "):
        parsed = _split_type_command(raw, "pc computer plan guarded type into ")
        return plan_guarded_type(parsed["description"], parsed["text"])

    if value.startswith("pc computer simulate guarded type into "):
        parsed = _split_type_command(raw, "pc computer simulate guarded type into ")
        return guarded_type(parsed["description"], parsed["text"], simulate=True)

    if value.startswith("pc computer guarded type into "):
        parsed = _split_type_command(raw, "pc computer guarded type into ")
        return guarded_type(parsed["description"], parsed["text"], simulate=False)

    if value.startswith("безопасный ввод в "):
        parsed = _split_type_command(raw, "безопасный ввод в ")
        return guarded_type(parsed["description"], parsed["text"], simulate=False)

    return {
        "ok": False,
        "mode": "computer_use_type_guard_unknown_command",
        "command": command,
    }
