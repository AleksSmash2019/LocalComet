
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import json
import re
import uuid

FOCUS_GUARD_VERSION = "v6.47d"
ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
FOCUS_DIR = COMPUTER_USE_DIR / "focus_guard"

TEXT_INPUT_ROLES = {
    "textbox",
    "text",
    "input",
    "edit",
    "editor",
    "searchbox",
    "combobox",
    "textarea",
    "document",
}

TEXT_INPUT_HINTS = {
    "поиск",
    "search",
    "найти",
    "input",
    "field",
    "поле",
    "ввод",
    "textbox",
    "editor",
    "edit",
    "textarea",
    "message",
    "chat",
    "prompt",
    "command",
    "команда",
    "чат",
    "сообщение",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)
    FOCUS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-zа-яё0-9]+", str(text or "").lower(), flags=re.IGNORECASE)


def _role_value(candidate: Dict[str, Any]) -> str:
    raw = candidate.get("role") or ""
    if not raw:
        raw = (candidate.get("raw") or {}).get("role") or (candidate.get("raw") or {}).get("type") or ""
    return str(raw).strip().lower()


def _candidate_text(candidate: Dict[str, Any]) -> str:
    raw = candidate.get("raw") or {}
    values = [
        candidate.get("text", ""),
        candidate.get("element_id", ""),
        candidate.get("role", ""),
        raw.get("text", ""),
        raw.get("label", ""),
        raw.get("name", ""),
        raw.get("title", ""),
        raw.get("placeholder", ""),
        raw.get("value", ""),
        raw.get("automation_id", ""),
        raw.get("class_name", ""),
    ]
    return " ".join(str(value) for value in values if value is not None)


def is_text_input_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    role = _role_value(candidate)
    text = _candidate_text(candidate).lower()
    tokens = set(_tokens(text))
    role_match = any(role_name in role for role_name in TEXT_INPUT_ROLES)
    hint_match = bool(tokens & TEXT_INPUT_HINTS) or any(hint in text for hint in TEXT_INPUT_HINTS)
    bounds = candidate.get("bounds") or {}
    has_bounds = bool(bounds.get("w", 0) and bounds.get("h", 0))

    score = 0.0
    if role_match:
        score += 0.62
    if hint_match:
        score += 0.26
    if has_bounds:
        score += 0.08
    try:
        score += min(0.12, float(candidate.get("score", 0.0)) * 0.12)
    except Exception:
        pass

    return {
        "ok": role_match or hint_match,
        "role_match": role_match,
        "hint_match": hint_match,
        "has_bounds": has_bounds,
        "score": round(min(1.0, score), 4),
        "role": role,
        "text": text,
    }


def find_focus_target(description: str, min_confidence: float = 0.35) -> Dict[str, Any]:
    from modules.computer_use_grounding_ru import find_candidates

    found = find_candidates(description, limit=10)
    candidates = []
    for candidate in found.get("candidates", []):
        input_check = is_text_input_candidate(candidate)
        enriched = dict(candidate)
        enriched["input_check"] = input_check
        enriched["focus_score"] = round(float(candidate.get("score", 0.0)) * 0.65 + float(input_check.get("score", 0.0)) * 0.35, 4)
        candidates.append(enriched)

    candidates.sort(key=lambda item: item.get("focus_score", 0.0), reverse=True)
    best = candidates[0] if candidates else None

    if not best:
        result = {
            "ok": False,
            "mode": "computer_use_focus_target",
            "description": description,
            "reason": "No candidate found for focus target.",
            "candidates": [],
        }
    elif best.get("focus_score", 0.0) < min_confidence:
        result = {
            "ok": False,
            "mode": "computer_use_focus_target",
            "description": description,
            "reason": "Best focus candidate is below confidence threshold.",
            "best": best,
            "candidates": candidates,
            "min_confidence": min_confidence,
        }
    elif not best.get("input_check", {}).get("ok"):
        result = {
            "ok": False,
            "mode": "computer_use_focus_target",
            "description": description,
            "reason": "Best candidate is not recognized as a text input/editor field.",
            "best": best,
            "candidates": candidates,
            "min_confidence": min_confidence,
        }
    else:
        center = best.get("center") or {}
        result = {
            "ok": True,
            "mode": "computer_use_focus_target",
            "version": FOCUS_GUARD_VERSION,
            "description": description,
            "confidence": best.get("focus_score"),
            "candidate_score": best.get("score"),
            "input_score": best.get("input_check", {}).get("score"),
            "element_id": best.get("element_id"),
            "role": best.get("role"),
            "text": best.get("text"),
            "bounds": best.get("bounds"),
            "center": center,
            "target": {
                "element_id": best.get("element_id"),
                "element_description": description,
                "window_title": "",
                "x": center.get("x"),
                "y": center.get("y"),
                "x_norm": None,
                "y_norm": None,
                "bounds": best.get("bounds"),
            },
            "candidate": best,
            "candidates": candidates,
        }

    _ensure_dirs()
    path = FOCUS_DIR / f"focus_target_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    result["artifact"] = _write_json(path, result)
    return result


def plan_focus(description: str, min_confidence: float = 0.35) -> Dict[str, Any]:
    target = find_focus_target(description, min_confidence=min_confidence)
    if not target.get("ok"):
        return {
            "ok": False,
            "mode": "computer_use_focus_plan",
            "description": description,
            "reason": target.get("reason"),
            "target": target,
        }

    action = {
        "kind": "click",
        "target": target["target"],
        "grounded": True,
        "confidence": target["confidence"],
        "element_id": target["element_id"],
        "reason": f"GUI screen focus verified input field before typing: {description}",
        "goal": f"gui screen focus input {description}",
        "modifies_files": False,
        "ui_intent": "guarded_focus_before_type",
        "gui_only": True,
        "file_change_policy": "requires_explicit_modifies_files_true",
    }

    from modules.computer_use_auto_action_ru import auto_policy_for_action
    policy = auto_policy_for_action(action)

    return {
        "ok": bool(policy.get("ok")) and not policy.get("blocked"),
        "mode": "computer_use_focus_plan",
        "version": FOCUS_GUARD_VERSION,
        "description": description,
        "focus_target": target,
        "focus_action": action,
        "policy": policy,
        "can_execute": bool(policy.get("allowed_to_execute")) and not policy.get("requires_confirmation"),
        "requires_confirmation": bool(policy.get("requires_confirmation")),
    }


def focus_element(description: str, simulate: bool = False, min_confidence: float = 0.35) -> Dict[str, Any]:
    plan = plan_focus(description, min_confidence=min_confidence)
    if not plan.get("ok"):
        return {
            "ok": False,
            "mode": "computer_use_focus_element",
            "description": description,
            "reason": plan.get("reason", "focus plan failed"),
            "plan": plan,
        }

    if plan.get("requires_confirmation") or not plan.get("can_execute"):
        return {
            "ok": False,
            "mode": "computer_use_focus_element",
            "description": description,
            "requires_confirmation": plan.get("requires_confirmation"),
            "reason": plan.get("policy", {}).get("reason", "focus action cannot execute"),
            "plan": plan,
        }

    from modules.computer_use_auto_action_ru import execute_gui_action
    execution = execute_gui_action(plan["focus_action"], simulate=simulate)

    try:
        from modules.computer_use_core_ru import observe_screen
        observation = observe_screen()
    except Exception as exc:
        observation = {"ok": False, "mode": "computer_use_focus_observe_error", "error": str(exc)}

    result = {
        "ok": bool(execution.get("ok")),
        "mode": "computer_use_focus_element",
        "version": FOCUS_GUARD_VERSION,
        "description": description,
        "simulated": simulate,
        "plan": plan,
        "execution": execution,
        "after_observation": observation,
        "created_at": _now(),
    }

    _ensure_dirs()
    path = FOCUS_DIR / f"focus_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    result["artifact"] = _write_json(path, result)
    return result


def status() -> Dict[str, Any]:
    _ensure_dirs()
    return {
        "ok": True,
        "mode": "computer_use_focus_guard_status",
        "version": FOCUS_GUARD_VERSION,
        "focus_dir": str(FOCUS_DIR),
        "text_input_roles": sorted(TEXT_INPUT_ROLES),
    }


def report() -> Dict[str, Any]:
    return status()


def is_computer_use_focus_guard_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = [
        "pc computer focus",
        "pc computer simulate focus",
        "pc computer focus target",
        "фокус элемент",
        "найди поле ввода",
    ]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def dispatch(command: str) -> Dict[str, Any]:
    raw = (command or "").strip()
    value = raw.lower()

    if value == "pc computer focus status":
        return status()

    if value.startswith("pc computer focus target "):
        return find_focus_target(raw[len("pc computer focus target "):].strip())

    if value.startswith("найди поле ввода "):
        return find_focus_target(raw[len("найди поле ввода "):].strip())

    if value.startswith("pc computer simulate focus "):
        return focus_element(raw[len("pc computer simulate focus "):].strip(), simulate=True)

    if value.startswith("pc computer focus "):
        return focus_element(raw[len("pc computer focus "):].strip(), simulate=False)

    if value.startswith("фокус элемент "):
        return focus_element(raw[len("фокус элемент "):].strip(), simulate=False)

    return {
        "ok": False,
        "mode": "computer_use_focus_guard_unknown_command",
        "command": command,
    }
