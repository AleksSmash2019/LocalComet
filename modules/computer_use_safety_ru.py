
from __future__ import annotations

from typing import Any, Dict, List
import re

SAFETY_VERSION = "v6.47d"

BLOCKS = [
    ("destructive_delete", r"удали|удалить|сотри|стереть|\b(delete|remove|wipe|format|erase|rm\s+-rf|rmdir|del\s+|shutil\.rmtree|os\.remove)\b"),
    ("shell_terminal", r"терминал|командн|админ|\b(shell|cmd|cmd\.exe|powershell|terminal|bash|zsh|sudo|admin|administrator)\b"),
    ("secrets", r"парол|токен|секрет|куки|профил[ья] браузера|\b(password|passwd|token|api\s*key|api-key|secret|private\s*key|ssh\s*key|cookie|cookies|browser\s*profile)\b"),
    ("banking_payment", r"банк|плат[её]ж|карта|казино|ставк|\b(bank|payment|credit\s*card|paypal|wallet|gambling|casino|betting)\b"),
    ("install_deploy", r"\b(npm|deploy|backend|docker|kubectl|helm|pip install)\b"),
]

ALLOWED_EXECUTION_KINDS_V643 = {"observe", "screenshot", "wait", "ask_user", "done", "focus_window"}
PROPOSAL_ONLY_KINDS_V643 = {"click", "double_click", "type", "hotkey", "scroll", "drag", "move", "keypress"}


def _find_problems(text: str) -> List[Dict[str, str]]:
    value = (text or "").lower()
    result = []
    for problem_type, pattern in BLOCKS:
        if re.search(pattern, value, flags=re.IGNORECASE):
            result.append({"type": problem_type, "reason": f"blocked marker: {problem_type}"})
    return result


def redact_text(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"(?i)(api[_\-\s]*key\s*[:=]\s*)[^\s]+", r"\1[REDACTED_SECRET]", value)
    value = re.sub(r"(?i)(token\s*[:=]\s*)[^\s]+", r"\1[REDACTED_SECRET]", value)
    value = re.sub(r"(?i)(password\s*[:=]\s*)[^\s]+", r"\1[REDACTED_SECRET]", value)
    value = re.sub(r"(?i)(private\s*key\s*[:=]\s*)[^\n]+", r"\1[REDACTED_SECRET]", value)
    return value


def safety_check_goal(goal: str) -> Dict[str, Any]:
    problems = _find_problems(goal)
    if problems:
        return {"ok": False, "blocked": True, "risk": "blocked", "reason": "; ".join(p["reason"] for p in problems), "problem_types": [p["type"] for p in problems]}
    return {"ok": True, "blocked": False, "risk": "low", "reason": "goal allowed for safe planning", "problem_types": []}


def safety_check_action(action: Dict[str, Any]) -> Dict[str, Any]:
    kind = str((action or {}).get("kind", "")).strip().lower()
    target = (action or {}).get("target") or {}
    text = " ".join([str(action.get("reason", "")), str(action.get("text", "")), str(target.get("element_description", "")), str(target.get("window_title", ""))])
    problems = _find_problems(text)

    if problems:
        return {"ok": False, "blocked": True, "risk": "blocked", "allowed_to_execute": False, "requires_confirmation": True, "reason": "; ".join(p["reason"] for p in problems), "problem_types": [p["type"] for p in problems], "notes": []}

    if kind in PROPOSAL_ONLY_KINDS_V643:
        try:
            from modules.computer_use_auto_action_ru import auto_policy_for_action
            auto = auto_policy_for_action(action)
            return {
                "ok": auto.get("ok", True),
                "blocked": auto.get("blocked", False),
                "risk": auto.get("risk", "low"),
                "allowed_to_execute": auto.get("allowed_to_execute", False),
                "requires_confirmation": auto.get("requires_confirmation", False),
                "reason": auto.get("reason", "automatic GUI policy"),
                "problem_types": auto.get("classification", {}).get("problem_types", []),
                "notes": ["v6.47d: non-file grounded GUI click/type may run automatically"],
            }
        except Exception as exc:
            return {"ok": True, "blocked": False, "risk": "medium", "allowed_to_execute": False, "requires_confirmation": False, "reason": f"auto policy unavailable: {exc}", "problem_types": [], "notes": ["fallback: action needs grounding"]}

    if kind not in ALLOWED_EXECUTION_KINDS_V643:
        return {"ok": False, "blocked": True, "risk": "blocked", "allowed_to_execute": False, "requires_confirmation": True, "reason": f"unsupported action kind: {kind}", "problem_types": ["unsupported_action_kind"], "notes": []}

    requires_confirmation = kind not in {"observe", "screenshot", "wait", "done"}
    return {"ok": True, "blocked": False, "risk": "medium" if requires_confirmation else "low", "allowed_to_execute": True, "requires_confirmation": requires_confirmation, "reason": "allowed by conservative v6.43 policy", "problem_types": [], "notes": []}


def status() -> Dict[str, Any]:
    return {"ok": True, "mode": "computer_use_safety_status", "version": SAFETY_VERSION, "allowed_execution_kinds": sorted(ALLOWED_EXECUTION_KINDS_V643), "proposal_only_kinds": sorted(PROPOSAL_ONLY_KINDS_V643)}


def report() -> Dict[str, Any]:
    return status()


def is_computer_use_safety_command(command: str) -> bool:
    return (command or "").strip().lower() in {"pc computer safety", "computer safety", "безопасность computer use"}


def dispatch(command: str) -> Dict[str, Any]:
    return report() if is_computer_use_safety_command(command) else {"ok": False, "mode": "computer_use_safety_unknown_command", "command": command}
