
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import json
import os
import re
import uuid

AUTO_ACTION_VERSION = "v6.55b"
ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
AUTO_ACTION_DIR = COMPUTER_USE_DIR / "auto_actions"
AUTO_POLICY_PATH = COMPUTER_USE_DIR / "auto_action_policy.json"
AUTO_HISTORY_PATH = COMPUTER_USE_DIR / "auto_action_history.json"


FILE_CHANGE_PATTERNS = [
    r"\b(save|write|create|edit|modify|patch|rename|move|copy|overwrite)\b.{0,80}\b(file|folder|directory|response\.json|\.py|\.md|\.txt|\.json|\.yaml|\.toml)\b",
    r"\b(file|folder|directory|response\.json|\.py|\.md|\.txt|\.json|\.yaml|\.toml)\b.{0,80}\b(save|write|create|edit|modify|patch|rename|move|copy|overwrite)\b",
    r"(сохран|запиш|созда[йт]|редакт|измени|патч|переимен|перемести|скопиру).{0,80}(файл|папк|каталог|response\.json|\.py|\.md|\.txt|\.json)",
    r"(файл|папк|каталог|response\.json|\.py|\.md|\.txt|\.json).{0,80}(сохран|запиш|созда[йт]|редакт|измени|патч|переимен|перемести|скопиру)",
]
FILE_CHANGE_NEGATIONS = [
    "non-file",
    "non file",
    "not a file change",
    "without file changes",
    "no file changes",
    "gui only",
    "ui only",
    "без изменения файлов",
    "без изменений файлов",
    "не меняет файлы",
    "не изменяет файлы",
    "только gui",
    "только ui",
]

DANGEROUS_PATTERNS = [
    r"\b(delete|remove|wipe|format|erase|rm\s+-rf|rmdir|del\s+|shutil\.rmtree|os\.remove)\b|удали|удалить|сотри|стереть|формат",
    r"\b(shell|cmd|cmd\.exe|powershell|terminal|bash|zsh|sudo|admin|administrator)\b|терминал|админ|командн",
    r"\b(password|passwd|token|api\s*key|api-key|secret|private\s*key|ssh\s*key|cookie|cookies|browser\s*profile)\b|парол|токен|секрет|куки|профил[ья] браузера",
    r"\b(bank|payment|credit\s*card|paypal|wallet|gambling|casino|betting)\b|банк|плат[её]ж|карта|казино|ставк",
]

AUTO_GUI_KINDS = {"click", "double_click", "type", "hotkey", "scroll", "move", "wait"}
REQUIRES_GROUNDING = {"click", "double_click", "type", "hotkey", "scroll", "move"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    AUTO_ACTION_DIR.mkdir(parents=True, exist_ok=True)
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def default_auto_policy() -> Dict[str, Any]:
    return {
        "version": AUTO_ACTION_VERSION,
        "auto_gui_enabled": True,
        "confirmation_policy": "confirm_only_file_changes_or_dangerous_actions",
        "require_grounding_for_click_type": True,
        "allow_coordinate_click_if_explicit": True,
        "allow_focused_type_if_explicit": True,
        "max_type_chars": 500,
        "allowed_hotkeys": [
            "enter",
            "tab",
            "escape",
            "ctrl+a",
            "ctrl+c",
            "ctrl+v",
            "ctrl+f",
            "alt+tab",
        ],
        "blocked": [
            "file changes require explicit confirmation",
            "dangerous actions are blocked",
            "secrets are blocked",
            "admin/terminal actions are blocked",
        ],
    }


def load_policy() -> Dict[str, Any]:
    _ensure_dirs()
    policy = _load_json(AUTO_POLICY_PATH, {})
    if not policy:
        policy = default_auto_policy()
        _write_json(AUTO_POLICY_PATH, policy)
    return policy


def _matches_any(text: str, patterns: List[str]) -> bool:
    value = str(text or "").lower()
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _has_file_change_intent(text: str) -> bool:
    value = str(text or "").lower()

    if any(marker in value for marker in FILE_CHANGE_NEGATIONS):
        strong_explicit = [
            "modifies_files=true",
            "confirmed file change",
            "write changes to file",
            "save changes to file",
            "edit file",
            "create file",
            "response.json",
        ]
        if not any(marker in value for marker in strong_explicit):
            return False

    return _matches_any(value, FILE_CHANGE_PATTERNS)


def classify_action(action: Dict[str, Any]) -> Dict[str, Any]:
    target = action.get("target") or {}
    ui_intent = str(action.get("ui_intent", "")).strip().lower()
    combined = " ".join([
        str(action.get("kind", "")),
        str(action.get("goal", "")),
        str(action.get("text", "")),
        str(action.get("reason", "")),
        str(ui_intent),
        str(target.get("element_description", "")),
        str(target.get("window_title", "")),
    ])

    dangerous = _matches_any(combined, DANGEROUS_PATTERNS)

    explicit_gui_only = (
        action.get("modifies_files") is False
        and (
            action.get("gui_only") is True
            or ui_intent in {
                "gui_navigation_or_button_click",
                "focus_only",
                "non_file_gui",
                "visual_guarded_non_file_click",
                "visual_guarded_non_file_type",
                "guarded_type_text",
                "guarded_focus_before_type",
                "verified_input_type",
            }
            or (
                str(action.get("file_change_policy", "")).strip().lower() == "requires_explicit_modifies_files_true"
                and action.get("grounded") is True
            )
        )
    )

    if dangerous:
        file_change = bool(action.get("modifies_files")) or _has_file_change_intent(combined)
    elif explicit_gui_only:
        file_change = False
    else:
        file_change = bool(action.get("modifies_files")) or _has_file_change_intent(combined)

    return {
        "dangerous": dangerous,
        "file_change": file_change,
        "requires_confirmation": bool(dangerous or file_change),
        "risk": "blocked" if dangerous else ("medium" if file_change else "low"),
    }


def is_grounded_action(action: Dict[str, Any]) -> bool:
    if bool(action.get("grounded")):
        return True
    target = action.get("target") or {}
    if target.get("element_id") or target.get("element_description"):
        return True
    if target.get("x") is not None and target.get("y") is not None:
        return True
    if action.get("kind") == "type" and bool(action.get("focused_target")):
        return True
    if action.get("kind") == "hotkey":
        return True
    if action.get("kind") == "scroll":
        return True
    return False


def auto_policy_for_action(action: Dict[str, Any]) -> Dict[str, Any]:
    policy = load_policy()
    kind = str(action.get("kind", "")).strip().lower()
    classification = classify_action(action)

    if classification["dangerous"]:
        return {
            "ok": False,
            "blocked": True,
            "allowed_to_execute": False,
            "requires_confirmation": True,
            "risk": "blocked",
            "reason": "Action contains dangerous/sensitive/admin marker and is blocked.",
            "classification": classification,
            "policy": policy,
        }

    if kind not in AUTO_GUI_KINDS:
        return {
            "ok": False,
            "blocked": True,
            "allowed_to_execute": False,
            "requires_confirmation": True,
            "risk": "blocked",
            "reason": f"Unsupported auto GUI action kind: {kind}",
            "classification": classification,
            "policy": policy,
        }

    if classification["file_change"]:
        return {
            "ok": True,
            "blocked": False,
            "allowed_to_execute": False,
            "requires_confirmation": True,
            "risk": "medium",
            "reason": "File-changing action requires explicit confirmation.",
            "classification": classification,
            "policy": policy,
        }

    if kind in REQUIRES_GROUNDING and not is_grounded_action(action):
        return {
            "ok": True,
            "blocked": False,
            "allowed_to_execute": False,
            "requires_confirmation": False,
            "risk": "medium",
            "reason": "GUI action needs element grounding or explicit coordinate/focused target before execution.",
            "classification": classification,
            "policy": policy,
        }

    if kind == "type":
        text = str(action.get("text", ""))
        if len(text) > int(policy.get("max_type_chars", 500)):
            return {
                "ok": True,
                "blocked": False,
                "allowed_to_execute": False,
                "requires_confirmation": True,
                "risk": "medium",
                "reason": "Typing payload is too long and requires confirmation.",
                "classification": classification,
                "policy": policy,
            }

    if kind == "hotkey":
        hotkey = str(action.get("text") or action.get("hotkey") or "").strip().lower()
        if hotkey and hotkey not in policy.get("allowed_hotkeys", []):
            return {
                "ok": True,
                "blocked": False,
                "allowed_to_execute": False,
                "requires_confirmation": True,
                "risk": "medium",
                "reason": f"Hotkey '{hotkey}' is not in the allowlist.",
                "classification": classification,
                "policy": policy,
            }

    return {
        "ok": True,
        "blocked": False,
        "allowed_to_execute": bool(policy.get("auto_gui_enabled", True)),
        "requires_confirmation": False,
        "risk": "low",
        "reason": "Non-file GUI action is allowed to execute automatically.",
        "classification": classification,
        "policy": policy,
    }


def _record_history(action: Dict[str, Any], policy_result: Dict[str, Any], execution: Dict[str, Any]) -> str:
    _ensure_dirs()
    history = _load_json(AUTO_HISTORY_PATH, [])
    row = {
        "created_at": _now(),
        "action": action,
        "policy_result": {
            "ok": policy_result.get("ok"),
            "blocked": policy_result.get("blocked"),
            "allowed_to_execute": policy_result.get("allowed_to_execute"),
            "requires_confirmation": policy_result.get("requires_confirmation"),
            "risk": policy_result.get("risk"),
            "reason": policy_result.get("reason"),
            "classification": policy_result.get("classification"),
        },
        "execution": execution,
    }
    history.append(row)
    if len(history) > 500:
        history = history[-500:]
    _write_json(AUTO_HISTORY_PATH, history)
    artifact = AUTO_ACTION_DIR / f"auto_action_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    _write_json(artifact, row)
    return str(artifact)


def _pyautogui_execute(action: Dict[str, Any]) -> Dict[str, Any]:
    kind = action.get("kind")
    target = action.get("target") or {}
    text = str(action.get("text", ""))
    import pyautogui

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.12

    if kind == "click":
        pyautogui.click(int(target["x"]), int(target["y"]))
        return {"ok": True, "executed": True, "primitive": "click", "target": target}

    if kind == "double_click":
        pyautogui.doubleClick(int(target["x"]), int(target["y"]))
        return {"ok": True, "executed": True, "primitive": "double_click", "target": target}

    if kind == "move":
        pyautogui.moveTo(int(target["x"]), int(target["y"]), duration=0.1)
        return {"ok": True, "executed": True, "primitive": "move", "target": target}

    if kind == "type":
        if not text:
            return {"ok": False, "executed": False, "error": "empty text"}
        if any(ord(ch) > 127 for ch in text):
            return {"ok": False, "executed": False, "error": "unicode typing requires clipboard adapter and is not enabled in v6.47d"}
        pyautogui.write(text, interval=0.01)
        return {"ok": True, "executed": True, "primitive": "type", "char_count": len(text)}

    if kind == "hotkey":
        keys = str(action.get("text") or action.get("hotkey") or "").replace("+", " ").split()
        if not keys:
            return {"ok": False, "executed": False, "error": "empty hotkey"}
        pyautogui.hotkey(*keys)
        return {"ok": True, "executed": True, "primitive": "hotkey", "keys": keys}

    if kind == "scroll":
        amount = int(action.get("amount") or action.get("delta") or 0)
        if amount == 0:
            amount = -3
        pyautogui.scroll(amount)
        return {"ok": True, "executed": True, "primitive": "scroll", "amount": amount}

    if kind == "wait":
        return {"ok": True, "executed": True, "primitive": "wait"}

    return {"ok": False, "executed": False, "error": f"unsupported primitive: {kind}"}


def execute_gui_action(action: Dict[str, Any], simulate: bool = False) -> Dict[str, Any]:
    _ensure_dirs()
    action = dict(action or {})
    action["kind"] = str(action.get("kind", "")).strip().lower()
    policy_result = auto_policy_for_action(action)

    if policy_result.get("blocked"):
        execution = {"ok": False, "executed": False, "blocked": True, "reason": policy_result.get("reason")}
        artifact = _record_history(action, policy_result, execution)
        return execution | {"mode": "computer_use_auto_action", "artifact": artifact, "policy": policy_result}

    if policy_result.get("requires_confirmation"):
        execution = {"ok": False, "executed": False, "requires_confirmation": True, "reason": policy_result.get("reason")}
        artifact = _record_history(action, policy_result, execution)
        return execution | {"mode": "computer_use_auto_action", "artifact": artifact, "policy": policy_result}

    if not policy_result.get("allowed_to_execute"):
        execution = {"ok": False, "executed": False, "reason": policy_result.get("reason")}
        artifact = _record_history(action, policy_result, execution)
        return execution | {"mode": "computer_use_auto_action", "artifact": artifact, "policy": policy_result}

    if simulate or os.environ.get("LOCALCOMET_COMPUTER_USE_SIMULATE") == "1":
        execution = {
            "ok": True,
            "executed": True,
            "simulated": True,
            "primitive": action.get("kind"),
            "message": "Simulated automatic GUI action.",
        }
        artifact = _record_history(action, policy_result, execution)
        return execution | {"mode": "computer_use_auto_action", "artifact": artifact, "policy": policy_result}

    try:
        execution = _pyautogui_execute(action)
    except Exception as exc:
        execution = {"ok": False, "executed": False, "error": str(exc)}

    artifact = _record_history(action, policy_result, execution)
    return execution | {"mode": "computer_use_auto_action", "artifact": artifact, "policy": policy_result}


def parse_auto_command(command: str) -> Dict[str, Any]:
    raw = (command or "").strip()
    lower = raw.lower()

    if lower.startswith("pc computer auto click "):
        tail = raw[len("pc computer auto click "):].strip()
        parts = re.split(r"[,\s]+", tail)
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return {"kind": "click", "target": {"x": int(parts[0]), "y": int(parts[1])}, "grounded": True, "reason": "explicit coordinate auto click"}
        return {"kind": "click", "target": {"element_description": tail}, "grounded": bool(tail), "reason": "explicit element auto click"}

    if lower.startswith("pc computer auto type "):
        text = raw[len("pc computer auto type "):]
        return {"kind": "type", "text": text, "focused_target": True, "grounded": True, "reason": "explicit focused field auto type"}

    if lower.startswith("pc computer auto hotkey "):
        hotkey = raw[len("pc computer auto hotkey "):].strip().lower()
        return {"kind": "hotkey", "text": hotkey, "grounded": True, "reason": "explicit auto hotkey"}

    if lower.startswith("pc computer auto scroll "):
        amount = raw[len("pc computer auto scroll "):].strip()
        try:
            amount_int = int(amount)
        except Exception:
            amount_int = -3
        return {"kind": "scroll", "amount": amount_int, "grounded": True, "reason": "explicit auto scroll"}

    if lower.startswith("pc computer simulate click "):
        tail = raw[len("pc computer simulate click "):].strip()
        parts = re.split(r"[,\s]+", tail)
        x = int(parts[0]) if len(parts) >= 1 and parts[0].isdigit() else 10
        y = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 10
        return {"kind": "click", "target": {"x": x, "y": y}, "grounded": True, "reason": "simulated coordinate click"}

    if lower.startswith("pc computer simulate type "):
        text = raw[len("pc computer simulate type "):]
        return {"kind": "type", "text": text, "focused_target": True, "grounded": True, "reason": "simulated focused type"}

    return {}


def status() -> Dict[str, Any]:
    policy = load_policy()
    history = _load_json(AUTO_HISTORY_PATH, [])
    return {
        "ok": True,
        "mode": "computer_use_auto_action_status",
        "version": AUTO_ACTION_VERSION,
        "policy": policy,
        "history_count": len(history),
    }


def report() -> Dict[str, Any]:
    return status()


def is_auto_action_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = [
        "pc computer auto click",
        "pc computer auto type",
        "pc computer auto hotkey",
        "pc computer auto scroll",
        "pc computer simulate click",
        "pc computer simulate type",
        "computer auto click",
        "авто клик",
        "авто ввод",
    ]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def dispatch(command: str) -> Dict[str, Any]:
    raw = (command or "").strip()
    lower = raw.lower()

    if lower == "pc computer auto status":
        return status()

    if lower.startswith("авто клик "):
        raw = "pc computer auto click " + raw[len("авто клик "):].strip()
    elif lower.startswith("авто ввод "):
        raw = "pc computer auto type " + raw[len("авто ввод "):]

    action = parse_auto_command(raw)
    if not action:
        return {"ok": False, "mode": "computer_use_auto_action_unknown_command", "command": command}

    simulate = lower.startswith("pc computer simulate ")
    return execute_gui_action(action, simulate=simulate)

# BEGIN v6.55b Computer Use Auto Action history write repair
COMPUTER_USE_AUTO_ACTION_HISTORY_WRITE_REPAIR_RU_V655B = "v6.55b robust auto action history writer"


try:
    _record_history_before_v655b
except NameError:
    _record_history_before_v655b = _record_history


def _record_history(action: Dict[str, Any], policy_result: Dict[str, Any], execution: Dict[str, Any]) -> str:
    try:
        return _record_history_before_v655b(action, policy_result, execution)
    except OSError as exc:
        _ensure_dirs()
        recovered_row = {
            "created_at": _now(),
            "action": action,
            "policy_result": {
                "ok": policy_result.get("ok"),
                "blocked": policy_result.get("blocked"),
                "allowed_to_execute": policy_result.get("allowed_to_execute"),
                "requires_confirmation": policy_result.get("requires_confirmation"),
                "risk": policy_result.get("risk"),
                "reason": policy_result.get("reason"),
                "classification": policy_result.get("classification"),
            },
            "execution": dict(execution or {}) | {
                "history_write_recovered": True,
                "history_write_error": str(exc),
            },
        }
        artifact = AUTO_ACTION_DIR / f"auto_action_recovered_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
        try:
            artifact.write_text(json.dumps(recovered_row, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(artifact)
        except Exception:
            fallback = AUTO_ACTION_DIR / f"auto_action_recovered_{uuid.uuid4().hex[:12]}.json"
            try:
                fallback.write_text(json.dumps(recovered_row, ensure_ascii=True, indent=2), encoding="utf-8")
                return str(fallback)
            except Exception as fallback_exc:
                return "history_write_failed:" + str(fallback_exc)


# END v6.55b Computer Use Auto Action history write repair
