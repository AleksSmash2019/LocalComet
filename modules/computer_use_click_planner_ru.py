
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict
import json
import uuid

CLICK_PLANNER_VERSION = "v6.47d"
ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
PLANNER_DIR = COMPUTER_USE_DIR / "click_planner"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)
    PLANNER_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _observe_result() -> Dict[str, Any]:
    try:
        from modules.computer_use_core_ru import observe_screen
        result = observe_screen()
        return result if isinstance(result, dict) else {"ok": False, "error": "observe returned non-dict"}
    except Exception as exc:
        return {"ok": False, "mode": "computer_use_observe_after_action_error", "error": str(exc)}


def _save_plan(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_dirs()
    path = PLANNER_DIR / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    payload["artifact"] = _write_json(path, payload)
    return payload


def plan_click_element(description: str, min_confidence: float = 0.35) -> Dict[str, Any]:
    from modules.computer_use_grounding_ru import build_grounded_action

    grounded_action = build_grounded_action(description, kind="click", min_confidence=min_confidence)
    if not grounded_action.get("ok"):
        return _save_plan("click_plan_failed", {
            "ok": False,
            "mode": "computer_use_click_plan",
            "description": description,
            "reason": grounded_action.get("reason"),
            "grounded_action": grounded_action,
        })

    action = grounded_action["action"]
    action["reason"] = f"GUI-only non-file visual guarded click on grounded UI element: {description}"
    action["goal"] = f"gui-only non-file click element {description}"
    action["modifies_files"] = False
    action["ui_intent"] = "visual_guarded_non_file_click"
    action["gui_only"] = True
    action["file_change_policy"] = "requires_explicit_modifies_files_true"

    from modules.computer_use_auto_action_ru import auto_policy_for_action
    policy = auto_policy_for_action(action)

    return _save_plan("click_plan", {
        "ok": bool(policy.get("ok")) and not policy.get("blocked"),
        "mode": "computer_use_click_plan",
        "description": description,
        "action": action,
        "grounding": grounded_action["grounding"],
        "policy": policy,
        "can_execute": bool(policy.get("allowed_to_execute")) and not policy.get("requires_confirmation"),
        "requires_confirmation": bool(policy.get("requires_confirmation")),
        "created_at": _now(),
    })


def click_element(description: str, simulate: bool = False, min_confidence: float = 0.35) -> Dict[str, Any]:
    plan = plan_click_element(description, min_confidence=min_confidence)
    if not plan.get("ok"):
        return {
            "ok": False,
            "mode": "computer_use_click_element",
            "description": description,
            "plan": plan,
            "reason": plan.get("reason", "click plan failed"),
        }

    if plan.get("requires_confirmation"):
        return {
            "ok": False,
            "mode": "computer_use_click_element",
            "description": description,
            "requires_confirmation": True,
            "plan": plan,
            "reason": plan.get("policy", {}).get("reason", "confirmation required"),
        }

    if not plan.get("can_execute"):
        return {
            "ok": False,
            "mode": "computer_use_click_element",
            "description": description,
            "plan": plan,
            "reason": plan.get("policy", {}).get("reason", "action cannot execute yet"),
        }

    from modules.computer_use_visual_guard_ru import guarded_execute
    guarded = guarded_execute(plan["action"], simulate=simulate)
    observation = guarded.get("after", {}).get("observation", {})

    result = {
        "ok": bool(guarded.get("ok")),
        "mode": "computer_use_click_element",
        "description": description,
        "simulated": simulate,
        "plan": plan,
        "execution": guarded.get("execution", {}),
        "after_observation": observation,
        "visual_guard": guarded,
        "next_decision": guarded.get("next_decision"),
        "created_at": _now(),
    }
    return _save_plan("click_result", result)


def plan_type_into(description: str, text: str, min_confidence: float = 0.35) -> Dict[str, Any]:
    from modules.computer_use_grounding_ru import build_grounded_action

    grounded_action = build_grounded_action(description, kind="type", text=text, min_confidence=min_confidence)
    if not grounded_action.get("ok"):
        return _save_plan("type_plan_failed", {
            "ok": False,
            "mode": "computer_use_type_plan",
            "description": description,
            "text_length": len(text or ""),
            "reason": grounded_action.get("reason"),
            "grounded_action": grounded_action,
        })

    action = grounded_action["action"]
    action["reason"] = f"Type into grounded UI element: {description}"
    action["goal"] = f"type into element {description}"
    action["focused_target"] = True
    action["modifies_files"] = False

    from modules.computer_use_auto_action_ru import auto_policy_for_action
    policy = auto_policy_for_action(action)

    return _save_plan("type_plan", {
        "ok": bool(policy.get("ok")) and not policy.get("blocked"),
        "mode": "computer_use_type_plan",
        "description": description,
        "text_length": len(text or ""),
        "action": action,
        "grounding": grounded_action["grounding"],
        "policy": policy,
        "can_execute": bool(policy.get("allowed_to_execute")) and not policy.get("requires_confirmation"),
        "requires_confirmation": bool(policy.get("requires_confirmation")),
        "created_at": _now(),
    })


def type_into(description: str, text: str, simulate: bool = False, min_confidence: float = 0.35) -> Dict[str, Any]:
    plan = plan_type_into(description, text, min_confidence=min_confidence)
    if not plan.get("ok"):
        return {
            "ok": False,
            "mode": "computer_use_type_into",
            "description": description,
            "plan": plan,
            "reason": plan.get("reason", "type plan failed"),
        }

    if plan.get("requires_confirmation"):
        return {
            "ok": False,
            "mode": "computer_use_type_into",
            "description": description,
            "requires_confirmation": True,
            "plan": plan,
            "reason": plan.get("policy", {}).get("reason", "confirmation required"),
        }

    if not plan.get("can_execute"):
        return {
            "ok": False,
            "mode": "computer_use_type_into",
            "description": description,
            "plan": plan,
            "reason": plan.get("policy", {}).get("reason", "action cannot execute yet"),
        }

    from modules.computer_use_visual_guard_ru import guarded_execute

    focus_action = {
        "kind": "click",
        "target": plan["action"].get("target", {}),
        "grounded": True,
        "reason": f"GUI-only non-file focus target before typing: {description}",
        "modifies_files": False,
        "ui_intent": "guarded_focus_before_type",
        "gui_only": True,
        "file_change_policy": "requires_explicit_modifies_files_true",
    }
    focus_guarded = guarded_execute(focus_action, simulate=simulate)
    type_guarded = guarded_execute(plan["action"], simulate=simulate)
    observation = type_guarded.get("after", {}).get("observation", {})

    result = {
        "ok": bool(focus_guarded.get("ok")) and bool(type_guarded.get("ok")),
        "mode": "computer_use_type_into",
        "description": description,
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
    return _save_plan("type_result", result)


def hotkey_safe(hotkey: str, simulate: bool = False) -> Dict[str, Any]:
    action = {
        "kind": "hotkey",
        "text": hotkey.strip().lower(),
        "grounded": True,
        "reason": f"Safe hotkey request: {hotkey}",
        "modifies_files": False,
    }
    from modules.computer_use_auto_action_ru import auto_policy_for_action, execute_gui_action

    policy = auto_policy_for_action(action)
    if policy.get("requires_confirmation") or not policy.get("allowed_to_execute"):
        return _save_plan("hotkey_refused", {
            "ok": False,
            "mode": "computer_use_hotkey_safe",
            "hotkey": hotkey,
            "policy": policy,
            "reason": policy.get("reason"),
        })

    execution = execute_gui_action(action, simulate=simulate)
    observation = _observe_result()
    return _save_plan("hotkey_result", {
        "ok": bool(execution.get("ok")),
        "mode": "computer_use_hotkey_safe",
        "hotkey": hotkey,
        "simulated": simulate,
        "policy": policy,
        "execution": execution,
        "after_observation": observation,
    })


def status() -> Dict[str, Any]:
    _ensure_dirs()
    return {
        "ok": True,
        "mode": "computer_use_click_planner_status",
        "version": CLICK_PLANNER_VERSION,
        "planner_dir": str(PLANNER_DIR),
    }


def report() -> Dict[str, Any]:
    return status()


def is_computer_use_click_planner_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = [
        "pc computer click element",
        "pc computer simulate click element",
        "pc computer type into",
        "pc computer simulate type into",
        "pc computer hotkey safe",
        "pc computer simulate hotkey safe",
        "кликни элемент",
        "введи в элемент",
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

    if value == "pc computer click planner status":
        return status()

    if value.startswith("pc computer simulate click element "):
        return click_element(raw[len("pc computer simulate click element "):].strip(), simulate=True)

    if value.startswith("pc computer click element "):
        return click_element(raw[len("pc computer click element "):].strip(), simulate=False)

    if value.startswith("кликни элемент "):
        return click_element(raw[len("кликни элемент "):].strip(), simulate=False)

    if value.startswith("pc computer simulate type into "):
        parsed = _split_type_command(raw, "pc computer simulate type into ")
        return type_into(parsed["description"], parsed["text"], simulate=True)

    if value.startswith("pc computer type into "):
        parsed = _split_type_command(raw, "pc computer type into ")
        return type_into(parsed["description"], parsed["text"], simulate=False)

    if value.startswith("введи в элемент "):
        parsed = _split_type_command(raw, "введи в элемент ")
        return type_into(parsed["description"], parsed["text"], simulate=False)

    if value.startswith("pc computer simulate hotkey safe "):
        return hotkey_safe(raw[len("pc computer simulate hotkey safe "):].strip(), simulate=True)

    if value.startswith("pc computer hotkey safe "):
        return hotkey_safe(raw[len("pc computer hotkey safe "):].strip(), simulate=False)

    return {
        "ok": False,
        "mode": "computer_use_click_planner_unknown_command",
        "command": command,
    }
