from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


FULL_CONTROL_VERSION = "v6.53"
FULL_CONTROL_NAME = "Computer Use Full Control Mission Real Actions RU"

try:
    from modules.project_paths import get_project_root
    ROOT_DIR = get_project_root()
except Exception:
    ROOT_DIR = Path(__file__).resolve().parents[1]
    if not ROOT_DIR.exists():
        ROOT_DIR = Path(__file__).resolve().parents[1]

PROJECTS_DIR = ROOT_DIR / "Projects"
COMPUTER_USE_DIR = PROJECTS_DIR / "ComputerUse"
MISSION_DIR = COMPUTER_USE_DIR / "full_control_missions"
LATEST_POINTER_FILE = MISSION_DIR / "latest_full_control_mission.json"
STOP_REQUEST_FILE = MISSION_DIR / "full_control_stop_requested.json"


APP_ALIASES = {
    "notepad": "notepad",
    "блокнот": "блокнот",
    "заметки": "блокнот",
    "calc": "calc",
    "calculator": "calculator",
    "калькулятор": "калькулятор",
    "paint": "paint",
    "рисование": "paint",
    "проводник": "explorer",
    "explorer": "explorer",
}

FOLDER_ALIASES = {
    "проект": "проект",
    "projects": "projects",
    "проекты": "проекты",
    "reports": "reports",
    "отчеты": "отчеты",
    "отчёты": "отчеты",
    "relay": "relay",
    "downloads": "downloads",
    "загрузки": "downloads",
}

HARD_BLOCK_PATTERNS = [
    ("destructive_delete", r"удали|удалить|сотри|стереть|\b(delete|remove|wipe|format|erase|rm\s+-rf|rmdir|del\s+|shutil\.rmtree|os\.remove)\b"),
    ("shell_terminal", r"терминал|командн|админ|\b(shell|cmd|cmd\.exe|powershell|terminal|bash|zsh|sudo|administrator)\b"),
    ("secrets", r"парол|токен|секрет|куки|профил[ья] браузера|seed phrase|\b(password|passwd|token|api\s*key|api-key|secret|private\s*key|ssh\s*key|cookie|cookies|browser\s*profile)\b"),
    ("banking_payment", r"банк|плат[её]ж|карта|казино|ставк|\b(bank|payment|credit\s*card|paypal|wallet|gambling|casino|betting)\b"),
]

FILE_CHANGE_MARKERS = [
    "response.json",
    "request.md",
    ".py",
    ".json",
    ".yaml",
    ".toml",
    "project file",
    "файл проекта",
    "патч",
    "patch",
    "commit",
    "repo",
    "repository",
]

SECRET_MARKERS = [
    "password",
    "passwd",
    "token",
    "api key",
    "api-key",
    "private key",
    "ssh key",
    "cookie",
    "пароль",
    "токен",
    "секрет",
    "приватный ключ",
    "куки",
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _norm(text: Any) -> str:
    return " ".join(str(text or "").lower().replace("ё", "е").strip().split())


def _safe_text(value: Any, limit: int = 8000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[truncated]"


def _ensure_dirs() -> None:
    MISSION_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default
    return default


def _append_event(run_dir: Path, event: Dict[str, Any]) -> None:
    payload = dict(event)
    payload.setdefault("timestamp", _now())
    path = run_dir / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text or ""), encoding="utf-8")
    return str(path)


def _goal_after_prefix(raw: str, prefixes: List[str]) -> str:
    normalized_raw = _norm(raw)
    raw_text = str(raw or "").strip()
    for prefix in prefixes:
        normalized_prefix = _norm(prefix)
        if normalized_raw == normalized_prefix:
            return ""
        if normalized_raw.startswith(normalized_prefix + " "):
            return raw_text[len(prefix):].strip(" :,-—")
    return ""


def _hard_gate(goal: str) -> Dict[str, Any]:
    lowered = _norm(goal)
    problems = []
    for problem_type, pattern in HARD_BLOCK_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            problems.append(problem_type)
    if problems:
        return {
            "ok": False,
            "blocked": True,
            "risk": "blocked",
            "reason": "blocked marker: " + "; blocked marker: ".join(problems),
            "problem_types": problems,
        }
    try:
        from modules.computer_use_safety_ru import safety_check_goal
        base = safety_check_goal(goal)
        if isinstance(base, dict) and base.get("blocked"):
            return base
    except Exception:
        pass
    return {
        "ok": True,
        "blocked": False,
        "risk": "low",
        "reason": "functionality-first goal allowed by hard gates",
        "problem_types": [],
    }


def _text_has_secret(text: str) -> bool:
    lowered = _norm(text)
    return any(marker in lowered for marker in SECRET_MARKERS)


def _payload_requires_confirmation(goal: str) -> Tuple[bool, str]:
    payload = _extract_text_to_type(goal)
    lowered_goal = _norm(goal)
    lowered_payload = _norm(payload)
    if any(marker in lowered_goal or marker in lowered_payload for marker in FILE_CHANGE_MARKERS):
        return True, "file/project-changing text requires explicit confirmation"
    if _text_has_secret(payload):
        return True, "typed payload appears to contain a secret"
    return False, ""


def _new_mission(goal: str, simulate: bool, max_steps: int, confidence_threshold: float) -> Tuple[str, Path, Dict[str, Any]]:
    _ensure_dirs()
    mission_id = "mission_" + _stamp()
    run_dir = MISSION_DIR / mission_id
    for child in ("steps", "screenshots", "ui_maps", "diffs"):
        (run_dir / child).mkdir(parents=True, exist_ok=True)
    mission = {
        "ok": True,
        "handled": True,
        "mode": "computer_use_full_control_mission",
        "version": FULL_CONTROL_VERSION,
        "name": FULL_CONTROL_NAME,
        "mission_id": mission_id,
        "goal": str(goal or "").strip(),
        "simulate": bool(simulate),
        "max_steps": int(max_steps),
        "confidence_threshold": float(confidence_threshold),
        "status": "running",
        "outcome": "running",
        "created_at": _now(),
        "updated_at": _now(),
        "run_dir": str(run_dir),
        "steps": [],
        "plan": [],
        "observations": [],
    }
    _write_json(run_dir / "mission.json", mission)
    _write_json(LATEST_POINTER_FILE, {"mission_id": mission_id, "run_dir": str(run_dir), "updated_at": _now()})
    _append_event(run_dir, {"event": "mission_created", "goal": goal, "simulate": bool(simulate), "max_steps": int(max_steps)})
    return mission_id, run_dir, mission


def _finish(run_dir: Path, mission: Dict[str, Any], status: str, outcome: str, reason: str = "") -> Dict[str, Any]:
    mission["status"] = status
    mission["outcome"] = outcome
    mission["reason"] = str(reason or "")
    mission["updated_at"] = _now()
    mission["ok"] = outcome not in {"blocked", "error"}
    _write_json(run_dir / "mission.json", mission)
    report = _write_report(run_dir, mission)
    mission["report"] = report
    _write_json(run_dir / "mission.json", mission)
    _write_json(LATEST_POINTER_FILE, {"mission_id": mission.get("mission_id"), "run_dir": str(run_dir), "updated_at": _now()})
    _append_event(run_dir, {"event": "mission_finished", "status": status, "outcome": outcome, "reason": reason})
    return dict(mission)


def _write_report(run_dir: Path, mission: Dict[str, Any]) -> str:
    lines = [
        "# Computer Use Full Control Mission",
        "",
        f"- version: {FULL_CONTROL_VERSION}",
        f"- mission_id: {mission.get('mission_id')}",
        f"- status: {mission.get('status')}",
        f"- outcome: {mission.get('outcome')}",
        f"- simulate: {mission.get('simulate')}",
        f"- goal: {mission.get('goal')}",
        f"- reason: {mission.get('reason', '')}",
        f"- max_steps: {mission.get('max_steps')}",
        f"- confidence_threshold: {mission.get('confidence_threshold')}",
        "",
        "## Plan",
    ]
    for action in mission.get("plan", []):
        lines.append(f"- {action.get('index')}: {action.get('kind')} target={action.get('target')} confidence={action.get('confidence')} reason={action.get('reason')}")
    lines.extend(["", "## Steps"])
    for step in mission.get("steps", []):
        action = step.get("planned_action") or {}
        execution = step.get("execution") or {}
        lines.append(
            f"- step {step.get('step_index')}: {action.get('kind')} -> "
            f"{execution.get('status')} ok={execution.get('ok')} next={step.get('next_decision')}"
        )
        if execution.get("reason"):
            lines.append(f"  - reason: {execution.get('reason')}")
    return _write_text(run_dir / "report.md", "\n".join(lines) + "\n")


def _active_window_from_observation(observation: Dict[str, Any]) -> str:
    for path in [
        ("active_window",),
        ("active_window_title",),
        ("desktop_observer", "result", "active_window", "title"),
        ("desktop_observer", "result", "active_window", "class"),
        ("desktop", "active_window", "title"),
    ]:
        current: Any = observation
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if current:
            return str(current)
    return ""


def _observe(run_dir: Path, step_index: int, phase: str) -> Dict[str, Any]:
    observation: Dict[str, Any] = {
        "ok": True,
        "mode": "computer_use_full_control_observation",
        "version": FULL_CONTROL_VERSION,
        "timestamp": _now(),
        "phase": phase,
        "active_window": "",
        "screen_size": {},
        "screenshot_path": "",
        "ui_map_path": "",
        "ui_element_count": 0,
        "limitations": [],
    }
    try:
        from modules.desktop_observer import observe_desktop
        desktop = observe_desktop(write_report=True)
        observation["desktop"] = desktop
        if isinstance(desktop, dict):
            active = desktop.get("active_window")
            if isinstance(active, dict):
                observation["active_window"] = str(active.get("title") or active.get("class") or "")
            observation["screenshot_path"] = str(desktop.get("screenshot_path") or desktop.get("screenshot") or desktop.get("path") or "")
            if isinstance(desktop.get("screen_size"), dict):
                observation["screen_size"] = desktop.get("screen_size")
    except Exception as exc:
        observation["limitations"].append("desktop_observer unavailable: " + str(exc))
    try:
        from modules.pc_ui_parser_adapter import parse_screen
        ui_map = parse_screen()
        observation["ui_map"] = ui_map
        if isinstance(ui_map, dict):
            elements = ui_map.get("elements") or ui_map.get("ui_elements") or []
            if isinstance(elements, list):
                observation["ui_element_count"] = len(elements)
    except Exception as exc:
        observation["limitations"].append("ui_parser unavailable: " + str(exc))
    observation["active_window"] = observation.get("active_window") or _active_window_from_observation(observation)
    path = run_dir / "ui_maps" / f"observation_{str(step_index).zfill(3)}_{phase}.json"
    observation["ui_map_path"] = _write_json(path, observation)
    return observation


def _observation_signature(observation: Dict[str, Any]) -> str:
    active = str(observation.get("active_window") or "")
    count = str(observation.get("ui_element_count") or 0)
    screenshot = str(observation.get("screenshot_path") or "")
    return active + "|" + count + "|" + Path(screenshot).name


def _extract_app(goal: str) -> str:
    lowered = _norm(goal)
    if not any(word in lowered for word in ("открой", "запусти", "open", "launch", "start")):
        return ""
    for alias, app in APP_ALIASES.items():
        if alias in lowered:
            return app
    return ""


def _extract_folder(goal: str) -> str:
    lowered = _norm(goal)
    if not any(word in lowered for word in ("открой папку", "открой каталог", "open folder", "open directory")):
        return ""
    for alias, folder in FOLDER_ALIASES.items():
        if alias in lowered:
            return folder
    return ""


def _strip_quotes(text: str) -> str:
    value = str(text or "").strip()
    pairs = [("\"", "\""), ("'", "'"), ("«", "»"), ("“", "”")]
    for left, right in pairs:
        if value.startswith(left) and value.endswith(right) and len(value) >= 2:
            return value[1:-1].strip()
    return value


def _extract_text_to_type(goal: str) -> str:
    raw = str(goal or "").strip()
    if "::" in raw:
        return _strip_quotes(raw.split("::", 1)[1].strip())
    lowered = raw.lower().replace("ё", "е")
    markers = [
        "напиши ",
        "введи ",
        "напечатай ",
        "набери ",
        "type ",
        "write ",
        "print ",
    ]
    best_index = -1
    best_marker = ""
    for marker in markers:
        index = lowered.find(marker)
        if index >= 0 and (best_index < 0 or index < best_index):
            best_index = index
            best_marker = marker
    if best_index < 0:
        return ""
    text = raw[best_index + len(best_marker):].strip()
    for cut in [" после этого ", " затем ", " потом "]:
        pos = text.lower().replace("ё", "е").find(cut.strip())
        if pos > 0:
            text = text[:pos].strip()
    if text.lower().startswith("текст "):
        text = text[6:].strip()
    return _strip_quotes(text)


def _extract_note_text(goal: str) -> str:
    lowered = _norm(goal)
    if "создай заметку" not in lowered and "create note" not in lowered:
        return ""
    raw = str(goal or "").strip()
    for marker in ("создай заметку", "create note"):
        pos = raw.lower().replace("ё", "е").find(marker)
        if pos >= 0:
            return _strip_quotes(raw[pos + len(marker):].strip(" :,-—"))
    return ""


def _extract_hotkey(goal: str) -> List[str]:
    lowered = _norm(goal)
    known = {
        "ctrl+s": ["ctrl", "s"],
        "ctrl s": ["ctrl", "s"],
        "ctrl+v": ["ctrl", "v"],
        "ctrl v": ["ctrl", "v"],
        "ctrl+a": ["ctrl", "a"],
        "ctrl a": ["ctrl", "a"],
        "alt+tab": ["alt", "tab"],
        "alt tab": ["alt", "tab"],
        "enter": ["enter"],
        "нажми enter": ["enter"],
        "escape": ["esc"],
        "esc": ["esc"],
        "tab": ["tab"],
    }
    for marker, keys in known.items():
        if marker in lowered:
            return keys
    return []


def _extract_click_target(goal: str) -> str:
    raw = str(goal or "").strip()
    lowered = raw.lower().replace("ё", "е")
    for marker in ("нажми ", "кликни ", "click "):
        pos = lowered.find(marker)
        if pos >= 0:
            return raw[pos + len(marker):].strip(" :,-—")
    return ""


def _plan_actions(goal: str, max_steps: int) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    note_text = _extract_note_text(goal)
    if note_text:
        actions.append({
            "kind": "create_note",
            "target": "PCAgent/Notes",
            "text": note_text,
            "confidence": 0.93,
            "reason": "user explicitly asked to create a note",
        })
    folder = _extract_folder(goal)
    if folder:
        actions.append({
            "kind": "open_folder",
            "target": folder,
            "confidence": 0.92,
            "reason": "folder alias resolved from goal",
        })
    app = _extract_app(goal)
    if app:
        actions.append({
            "kind": "open_app",
            "target": app,
            "confidence": 0.95,
            "reason": "allowlisted application resolved from goal",
        })
        actions.append({
            "kind": "wait",
            "target": "foreground app",
            "seconds": 0.8,
            "confidence": 0.86,
            "reason": "wait for app window after launch",
        })
    text_to_type = _extract_text_to_type(goal)
    if text_to_type:
        actions.append({
            "kind": "paste_text",
            "target": "active_window",
            "text": text_to_type,
            "confidence": 0.89 if app else 0.74,
            "reason": "text payload extracted from user goal",
        })
    hotkey = _extract_hotkey(goal)
    if hotkey:
        actions.append({
            "kind": "hotkey",
            "target": "+".join(hotkey),
            "keys": hotkey,
            "confidence": 0.86,
            "reason": "known hotkey extracted from goal",
        })
    click_target = _extract_click_target(goal)
    if click_target and not text_to_type:
        actions.append({
            "kind": "delegate_multistep",
            "target": click_target,
            "goal": goal,
            "confidence": 0.78,
            "reason": "click target should be grounded by existing UI map/multistep loop",
        })
    if not actions:
        actions.append({
            "kind": "delegate_multistep",
            "target": "screen",
            "goal": goal,
            "confidence": 0.70,
            "reason": "fallback to existing grounded multistep loop",
        })
    for index, action in enumerate(actions[:max_steps], start=1):
        action["index"] = index
    return actions[:max_steps]


def _keyboard_vk(key: str) -> Optional[int]:
    mapping = {
        "ctrl": 0x11,
        "control": 0x11,
        "shift": 0x10,
        "alt": 0x12,
        "enter": 0x0D,
        "return": 0x0D,
        "tab": 0x09,
        "esc": 0x1B,
        "escape": 0x1B,
        "space": 0x20,
        "backspace": 0x08,
        "delete": 0x2E,
        "left": 0x25,
        "up": 0x26,
        "right": 0x27,
        "down": 0x28,
    }
    lowered = str(key or "").lower().strip()
    if lowered in mapping:
        return mapping[lowered]
    if len(lowered) == 1 and "a" <= lowered <= "z":
        return ord(lowered.upper())
    if len(lowered) == 1 and "0" <= lowered <= "9":
        return ord(lowered)
    return None


def _press_hotkey(keys: List[str], simulate: bool) -> Dict[str, Any]:
    keys = [str(key).strip().lower() for key in keys if str(key).strip()]
    if not keys:
        return {"ok": False, "status": "error", "reason": "empty hotkey"}
    if simulate:
        return {"ok": True, "status": "simulated", "keys": keys}
    if os.name != "nt":
        return {"ok": False, "status": "unsupported", "reason": "real hotkey currently supports Windows only", "keys": keys}
    try:
        import ctypes
        user32 = ctypes.windll.user32
        keybd_event = user32.keybd_event
        key_up = 0x0002
        vk_codes = []
        for key in keys:
            vk = _keyboard_vk(key)
            if vk is None:
                return {"ok": False, "status": "error", "reason": "unsupported key: " + key, "keys": keys}
            vk_codes.append(vk)
        for vk in vk_codes:
            keybd_event(vk, 0, 0, 0)
            time.sleep(0.03)
        for vk in reversed(vk_codes):
            keybd_event(vk, 0, key_up, 0)
            time.sleep(0.03)
        return {"ok": True, "status": "executed", "keys": keys}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "keys": keys}


def _set_clipboard_text(text: str) -> Dict[str, Any]:
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return {"ok": True, "status": "clipboard_set"}
    except Exception as exc:
        return {"ok": False, "status": "clipboard_error", "reason": str(exc)}


def _paste_text(text: str, simulate: bool) -> Dict[str, Any]:
    if _text_has_secret(text):
        return {"ok": False, "status": "requires_confirmation", "requires_confirmation": True, "reason": "text appears to contain secret markers"}
    if simulate:
        return {"ok": True, "status": "simulated", "text_preview": _safe_text(text, 400)}
    clip = _set_clipboard_text(text)
    if not clip.get("ok"):
        return clip
    hotkey = _press_hotkey(["ctrl", "v"], simulate=False)
    hotkey["clipboard"] = clip
    return hotkey


def _execute_action(action: Dict[str, Any], simulate: bool, mission_goal: str) -> Dict[str, Any]:
    kind = str(action.get("kind") or "").strip()
    try:
        if kind == "open_app":
            from modules.pc_agent_actions import open_app
            result = open_app(str(action.get("target") or ""), dry_run=simulate)
            result.setdefault("status", "simulated" if simulate else "executed")
            return result
        if kind == "open_folder":
            from modules.pc_agent_actions import open_folder
            result = open_folder(str(action.get("target") or ""), dry_run=simulate)
            result.setdefault("status", "simulated" if simulate else "executed")
            return result
        if kind == "create_note":
            from modules.pc_agent_actions import create_note
            result = create_note(str(action.get("text") or ""), dry_run=simulate)
            result.setdefault("status", "simulated" if simulate else "executed")
            return result
        if kind == "wait":
            seconds = max(0.0, min(float(action.get("seconds") or 0.5), 5.0))
            if not simulate:
                time.sleep(seconds)
            return {"ok": True, "status": "simulated" if simulate else "executed", "seconds": seconds}
        if kind == "paste_text":
            return _paste_text(str(action.get("text") or ""), simulate=simulate)
        if kind == "hotkey":
            return _press_hotkey(list(action.get("keys") or []), simulate=simulate)
        if kind == "delegate_multistep":
            from modules.computer_use_multistep_loop_ru import run_loop
            result = run_loop(str(action.get("goal") or mission_goal), simulate=simulate, max_steps=1, max_failures=1)
            result.setdefault("status", result.get("outcome") or "returned")
            return result
        return {"ok": False, "status": "error", "reason": "unknown action kind: " + kind}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "action": action}


def _visual_decision(before: Dict[str, Any], after: Dict[str, Any], execution: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
    if execution.get("requires_confirmation") or execution.get("status") == "requires_confirmation":
        return {"ok": True, "decision": "requires_confirmation", "reason": execution.get("reason", "confirmation required")}
    if not execution.get("ok"):
        return {"ok": False, "decision": "replan", "reason": execution.get("reason", "execution failed")}
    before_sig = _observation_signature(before)
    after_sig = _observation_signature(after)
    if before_sig != after_sig:
        return {"ok": True, "decision": "continue", "reason": "screen/window state changed", "before": before_sig, "after": after_sig}
    kind = str(action.get("kind") or "")
    if kind in {"open_app", "open_folder", "paste_text", "hotkey", "create_note"}:
        return {"ok": True, "decision": "continue", "reason": "action executed; no visual change requirement for this primitive", "signature": after_sig}
    return {"ok": True, "decision": "replan", "reason": "no observable change after action", "signature": after_sig}


def stop_requested() -> bool:
    return STOP_REQUEST_FILE.exists()


def request_stop(reason: str = "user requested stop") -> Dict[str, Any]:
    _ensure_dirs()
    payload = {
        "ok": True,
        "handled": True,
        "mode": "computer_use_full_control_stop",
        "version": FULL_CONTROL_VERSION,
        "reason": str(reason or "user requested stop"),
        "timestamp": _now(),
    }
    _write_json(STOP_REQUEST_FILE, payload)
    return payload


def clear_stop_request() -> Dict[str, Any]:
    existed = STOP_REQUEST_FILE.exists()
    cleared_path = ""
    if existed:
        cleared = STOP_REQUEST_FILE.with_name(STOP_REQUEST_FILE.name + ".cleared_" + _stamp())
        STOP_REQUEST_FILE.rename(cleared)
        cleared_path = str(cleared)
    return {
        "ok": True,
        "handled": True,
        "mode": "computer_use_full_control_clear_stop",
        "version": FULL_CONTROL_VERSION,
        "existed": existed,
        "cleared_path": cleared_path,
    }


def run_full_control_mission(goal: str, simulate: bool = False, max_steps: int = 12, confidence_threshold: float = 0.62) -> Dict[str, Any]:
    goal = str(goal or "").strip()
    if not goal:
        return {"ok": False, "handled": True, "mode": "computer_use_full_control_mission", "version": FULL_CONTROL_VERSION, "status": "rejected", "outcome": "ask_user", "reason": "empty goal"}
    max_steps = max(1, min(int(max_steps), 24))
    confidence_threshold = max(0.0, min(float(confidence_threshold), 0.95))

    mission_id, run_dir, mission = _new_mission(goal, simulate=simulate, max_steps=max_steps, confidence_threshold=confidence_threshold)
    try:
        gate = _hard_gate(goal)
        mission["safety"] = gate
        if gate.get("blocked"):
            return _finish(run_dir, mission, "blocked", "blocked", str(gate.get("reason", "blocked by hard gate")))

        needs_confirmation, confirmation_reason = _payload_requires_confirmation(goal)
        if needs_confirmation:
            return _finish(run_dir, mission, "needs_user", "requires_confirmation", confirmation_reason)

        actions = _plan_actions(goal, max_steps=max_steps)
        mission["plan"] = actions
        _write_json(run_dir / "plan.json", {"version": FULL_CONTROL_VERSION, "actions": actions})
        if not actions:
            return _finish(run_dir, mission, "needs_user", "ask_user", "no action plan produced")

        seen_action_signatures: Dict[str, int] = {}
        for step_index, action in enumerate(actions, start=1):
            if stop_requested():
                return _finish(run_dir, mission, "stopped", "stopped", "stop request is active")
            confidence = float(action.get("confidence") or 0.0)
            if confidence < confidence_threshold:
                return _finish(run_dir, mission, "needs_user", "ask_user", "action confidence below threshold: " + str(confidence))

            action_signature = str(action.get("kind")) + "|" + str(action.get("target")) + "|" + str(action.get("text", ""))[:80]
            seen_action_signatures[action_signature] = seen_action_signatures.get(action_signature, 0) + 1
            if seen_action_signatures[action_signature] > 2:
                return _finish(run_dir, mission, "needs_user", "ask_user", "stuck detection: repeated action signature")

            before = _observe(run_dir, step_index, "before")
            execution = _execute_action(action, simulate=simulate, mission_goal=goal)
            after = _observe(run_dir, step_index, "after")
            visual = _visual_decision(before, after, execution, action)
            next_decision = visual.get("decision", "continue")
            step = {
                "step_index": step_index,
                "timestamp": _now(),
                "observation_summary": {
                    "active_window_before": before.get("active_window", ""),
                    "active_window_after": after.get("active_window", ""),
                    "ui_elements_before": before.get("ui_element_count", 0),
                    "ui_elements_after": after.get("ui_element_count", 0),
                },
                "active_window": after.get("active_window", ""),
                "ui_map_summary": {
                    "before_path": before.get("ui_map_path", ""),
                    "after_path": after.get("ui_map_path", ""),
                },
                "planned_action": action,
                "grounded_target": {
                    "target": action.get("target"),
                    "confidence": confidence,
                    "source": action.get("reason", ""),
                },
                "confidence": confidence,
                "safety_decision": gate,
                "execution": execution,
                "visual_state_diff": visual,
                "next_decision": next_decision,
            }
            mission.setdefault("steps", []).append(step)
            _write_json(run_dir / "steps" / ("step_" + str(step_index).zfill(3) + ".json"), step)
            _append_event(run_dir, {"event": "step", "step_index": step_index, "action": action, "execution_ok": execution.get("ok"), "next_decision": next_decision})
            _write_json(run_dir / "mission.json", mission)

            if execution.get("requires_confirmation") or next_decision == "requires_confirmation":
                return _finish(run_dir, mission, "needs_user", "requires_confirmation", str(execution.get("reason") or visual.get("reason") or "confirmation required"))
            if next_decision == "stop":
                return _finish(run_dir, mission, "stopped", "stopped", str(visual.get("reason", "visual guard stop")))
            if not execution.get("ok") and action.get("kind") != "delegate_multistep":
                return _finish(run_dir, mission, "needs_user", "ask_user", str(execution.get("reason", "action failed")))
            if action.get("kind") == "delegate_multistep" and execution.get("outcome") in {"ask_user", "blocked", "requires_confirmation"}:
                return _finish(run_dir, mission, str(execution.get("status") or "needs_user"), str(execution.get("outcome")), str(execution.get("reason", "")))
        return _finish(run_dir, mission, "done", "done", "full control mission completed planned action budget")
    except Exception as exc:
        mission["error"] = str(exc)
        return _finish(run_dir, mission, "error", "error", str(exc))


def status() -> Dict[str, Any]:
    _ensure_dirs()
    pointer = _read_json(LATEST_POINTER_FILE, {})
    latest_data = {}
    if isinstance(pointer, dict) and pointer.get("run_dir"):
        latest_data = _read_json(Path(str(pointer.get("run_dir"))) / "mission.json", {})
    return {
        "ok": True,
        "handled": True,
        "mode": "computer_use_full_control_status",
        "version": FULL_CONTROL_VERSION,
        "missions_dir": str(MISSION_DIR),
        "latest_pointer": pointer,
        "latest_mission_id": latest_data.get("mission_id") or pointer.get("mission_id"),
        "latest_status": latest_data.get("status"),
        "latest_outcome": latest_data.get("outcome"),
        "stop_requested": stop_requested(),
    }


def latest_mission() -> Dict[str, Any]:
    pointer = _read_json(LATEST_POINTER_FILE, {})
    if not isinstance(pointer, dict) or not pointer.get("run_dir"):
        return {"ok": False, "handled": True, "mode": "computer_use_full_control_latest", "version": FULL_CONTROL_VERSION, "reason": "no full control mission recorded"}
    mission = _read_json(Path(str(pointer.get("run_dir"))) / "mission.json", {})
    if not isinstance(mission, dict) or not mission:
        return {"ok": False, "handled": True, "mode": "computer_use_full_control_latest", "version": FULL_CONTROL_VERSION, "reason": "latest mission missing", "latest_pointer": pointer}
    mission["handled"] = True
    return mission


def latest_report() -> Dict[str, Any]:
    latest = latest_mission()
    if not latest.get("ok"):
        return latest
    report_path = Path(str(latest.get("run_dir"))) / "report.md"
    if not report_path.exists():
        _write_report(report_path.parent, latest)
    return {
        "ok": True,
        "handled": True,
        "mode": "computer_use_full_control_report",
        "version": FULL_CONTROL_VERSION,
        "mission_id": latest.get("mission_id"),
        "report": str(report_path),
        "content": _safe_text(report_path.read_text(encoding="utf-8", errors="replace"), 5000),
    }


def _command_goal(raw: str, prefixes: List[str]) -> str:
    return _goal_after_prefix(raw, prefixes)


def is_full_control_command(command: str) -> bool:
    lowered = _norm(command)
    exact = {
        "pc computer full control status",
        "pc computer full control latest",
        "pc computer full control report",
        "pc computer full control stop",
        "pc computer full control clear stop",
        "статус управления пк",
        "последнее управление пк",
        "отчет управления пк",
        "отчёт управления пк",
        "останови управление пк",
    }
    if lowered in exact:
        return True
    prefixes = [
        "управляй пк",
        "сделай на компьютере",
        "агент пк",
        "computer use",
        "pc computer full control",
        "pc computer full control simulate",
        "pc computer agent mission",
        "pc computer agent simulate",
    ]
    return any(lowered == _norm(prefix) or lowered.startswith(_norm(prefix) + " ") for prefix in prefixes)


def handle_dispatch_command(command: str) -> Dict[str, Any]:
    raw = str(command or "").strip()
    lowered = _norm(raw)
    if lowered in {"pc computer full control status", "статус управления пк"}:
        return status()
    if lowered in {"pc computer full control latest", "последнее управление пк"}:
        return latest_mission()
    if lowered in {"pc computer full control report", "отчет управления пк", "отчёт управления пк"}:
        return latest_report()
    if lowered in {"pc computer full control stop", "останови управление пк"}:
        return request_stop("dispatch command: " + raw)
    if lowered == "pc computer full control clear stop":
        return clear_stop_request()

    simulate_prefixes = [
        "pc computer full control simulate",
        "pc computer agent simulate",
        "симуляция управления пк",
    ]
    for prefix in simulate_prefixes:
        goal = _command_goal(raw, [prefix])
        if goal:
            return run_full_control_mission(goal, simulate=True, max_steps=12)

    run_prefixes = [
        "управляй пк",
        "сделай на компьютере",
        "агент пк",
        "computer use",
        "pc computer full control",
        "pc computer agent mission",
    ]
    for prefix in run_prefixes:
        goal = _command_goal(raw, [prefix])
        if goal:
            return run_full_control_mission(goal, simulate=False, max_steps=12)

    return {
        "ok": False,
        "handled": False,
        "mode": "computer_use_full_control_mission",
        "version": FULL_CONTROL_VERSION,
        "reason": "not a full control command",
    }


def run_self_check(write_report: bool = True) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details if details is not None else {}})

    blocked = run_full_control_mission("удали все файлы через powershell", simulate=True, max_steps=3)
    add("hard gate blocks destructive shell goal", blocked.get("outcome") == "blocked", {"outcome": blocked.get("outcome"), "reason": blocked.get("reason")})

    confirmation = run_full_control_mission("введи Поиск :: write changes to file response.json", simulate=True, max_steps=3)
    add("file-changing typed payload requires confirmation", confirmation.get("outcome") == "requires_confirmation", {"outcome": confirmation.get("outcome"), "reason": confirmation.get("reason")})

    sample = run_full_control_mission("открой блокнот и напиши hello", simulate=True, max_steps=6)
    add("simulate open app and type text completes", sample.get("outcome") == "done" and len(sample.get("steps", [])) >= 2, {"outcome": sample.get("outcome"), "steps": len(sample.get("steps", [])), "report": sample.get("report")})

    status_result = status()
    add("status route works", status_result.get("ok") and status_result.get("mode") == "computer_use_full_control_status", status_result)

    dispatch_sim = handle_dispatch_command("pc computer full control simulate открой блокнот и напиши hello")
    add("dispatch simulate full control handled", dispatch_sim.get("handled") and dispatch_sim.get("outcome") == "done", {"outcome": dispatch_sim.get("outcome"), "steps": len(dispatch_sim.get("steps", []))})

    add("управляй пк command is recognized", is_full_control_command("управляй пк открой блокнот"), {})
    add("module has no public dispatch export", "dispatch" not in globals(), {})

    latest = latest_report()
    add("latest report is available", latest.get("ok") and Path(str(latest.get("report", ""))).exists(), {"report": latest.get("report")})

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    payload = {
        "ok": summary["failed"] == 0,
        "mode": "computer_use_full_control_self_check",
        "version": FULL_CONTROL_VERSION,
        "summary": summary,
        "checks": checks,
    }
    if write_report:
        report_dir = MISSION_DIR / "self_checks"
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / ("self_check_" + _stamp() + ".json")
        _write_json(path, payload)
        payload["report"] = str(path)
    return payload

# BEGIN LOCALCOMET V6.53 COMPUTER USE REAL ACTIONS UPGRADE RU

FULL_CONTROL_VERSION = "v6.53"
FULL_CONTROL_REAL_ACTIONS_UPGRADE_RU_V653 = "v6.53 real GUI action planner/executor upgrade"


def _localcomet_real_actions_capabilities_ru_v653() -> Dict[str, Any]:
    try:
        from modules.computer_use_real_actions_ru import get_real_action_capabilities
        caps = get_real_action_capabilities()
        caps["handled"] = True
        return caps
    except Exception as exc:
        return {
            "ok": False,
            "handled": True,
            "mode": "computer_use_real_action_capabilities",
            "version": FULL_CONTROL_VERSION,
            "reason": str(exc),
        }


def _plan_actions(goal: str, max_steps: int) -> List[Dict[str, Any]]:
    try:
        from modules.computer_use_real_actions_ru import build_real_action_plan
        plan = build_real_action_plan(goal, max_steps=max_steps)
        if plan.get("blocked"):
            return [{
                "kind": "blocked_by_real_action_gate",
                "target": "goal",
                "confidence": 1.0,
                "reason": str(plan.get("reason") or "blocked"),
                "index": 1,
            }]
        actions = list(plan.get("actions") or [])
        if actions:
            for index, action in enumerate(actions[:max_steps], start=1):
                action["index"] = index
            return actions[:max_steps]
    except Exception:
        pass

    actions: List[Dict[str, Any]] = []
    note_text = _extract_note_text(goal)
    if note_text:
        actions.append({
            "kind": "create_note",
            "target": "PCAgent/Notes",
            "text": note_text,
            "confidence": 0.93,
            "reason": "user explicitly asked to create a note",
        })
    folder = _extract_folder(goal)
    if folder:
        actions.append({
            "kind": "open_folder",
            "target": folder,
            "confidence": 0.92,
            "reason": "folder alias resolved from goal",
        })
    app = _extract_app(goal)
    if app:
        actions.append({
            "kind": "open_app",
            "target": app,
            "confidence": 0.95,
            "reason": "allowlisted application resolved from goal",
        })
        actions.append({
            "kind": "wait_for_window",
            "target": app,
            "seconds": 0.8,
            "confidence": 0.86,
            "reason": "wait for app window after launch",
        })
    text_to_type = _extract_text_to_type(goal)
    if text_to_type:
        actions.append({
            "kind": "paste_text",
            "target": "active_window",
            "text": text_to_type,
            "confidence": 0.89 if app else 0.74,
            "reason": "text payload extracted from user goal",
        })
    hotkey = _extract_hotkey(goal)
    if hotkey:
        actions.append({
            "kind": "hotkey",
            "target": "+".join(hotkey),
            "keys": hotkey,
            "confidence": 0.86,
            "reason": "known hotkey extracted from goal",
        })
    click_target = _extract_click_target(goal)
    if click_target and not text_to_type:
        actions.append({
            "kind": "delegate_multistep",
            "target": click_target,
            "goal": goal,
            "confidence": 0.78,
            "reason": "click target should be grounded by existing UI map/multistep loop",
        })
    if not actions:
        actions.append({
            "kind": "delegate_multistep",
            "target": "screen",
            "goal": goal,
            "confidence": 0.70,
            "reason": "fallback to existing grounded multistep loop",
        })
    for index, action in enumerate(actions[:max_steps], start=1):
        action["index"] = index
    return actions[:max_steps]


def _execute_action(action: Dict[str, Any], simulate: bool, mission_goal: str) -> Dict[str, Any]:
    kind = str(action.get("kind") or "").strip()
    if kind == "blocked_by_real_action_gate":
        return {
            "ok": False,
            "status": "blocked",
            "blocked": True,
            "reason": str(action.get("reason") or "blocked by real action gate"),
        }
    try:
        from modules.computer_use_real_actions_ru import execute_real_action
        real_result = execute_real_action(action, simulate=simulate, mission_goal=mission_goal)
        if isinstance(real_result, dict) and real_result.get("status") != "error":
            return real_result
    except Exception:
        pass

    try:
        if kind == "open_app":
            from modules.pc_agent_actions import open_app
            result = open_app(str(action.get("target") or ""), dry_run=simulate)
            result.setdefault("status", "simulated" if simulate else "executed")
            return result
        if kind == "open_folder":
            from modules.pc_agent_actions import open_folder
            result = open_folder(str(action.get("target") or ""), dry_run=simulate)
            result.setdefault("status", "simulated" if simulate else "executed")
            return result
        if kind == "create_note":
            from modules.pc_agent_actions import create_note
            result = create_note(str(action.get("text") or ""), dry_run=simulate)
            result.setdefault("status", "simulated" if simulate else "executed")
            return result
        if kind in {"wait", "wait_for_window"}:
            seconds = max(0.0, min(float(action.get("seconds") or 0.5), 5.0))
            if not simulate:
                time.sleep(seconds)
            return {"ok": True, "status": "simulated" if simulate else "executed", "seconds": seconds}
        if kind == "paste_text":
            return _paste_text(str(action.get("text") or ""), simulate=simulate)
        if kind == "hotkey":
            return _press_hotkey(list(action.get("keys") or []), simulate=simulate)
        if kind == "delegate_multistep":
            from modules.computer_use_multistep_loop_ru import run_loop
            result = run_loop(str(action.get("goal") or mission_goal), simulate=simulate, max_steps=1, max_failures=1)
            result.setdefault("status", result.get("outcome") or "returned")
            return result
        return {"ok": False, "status": "error", "reason": "unknown action kind: " + kind}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "action": action}


def _visual_decision(before: Dict[str, Any], after: Dict[str, Any], execution: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
    if execution.get("requires_confirmation") or execution.get("status") == "requires_confirmation":
        return {"ok": True, "decision": "requires_confirmation", "reason": execution.get("reason", "confirmation required")}
    if execution.get("blocked") or execution.get("status") == "blocked":
        return {"ok": False, "decision": "blocked", "reason": execution.get("reason", "blocked")}
    if not execution.get("ok"):
        return {"ok": False, "decision": "replan", "reason": execution.get("reason", "execution failed")}
    before_sig = _observation_signature(before)
    after_sig = _observation_signature(after)
    if before_sig != after_sig:
        return {"ok": True, "decision": "continue", "reason": "screen/window state changed", "before": before_sig, "after": after_sig}
    kind = str(action.get("kind") or "")
    if kind in {"open_app", "open_folder", "paste_text", "type_element", "click_element", "double_click_element", "hotkey", "press_key", "scroll", "wait_for_window", "wait", "create_note"}:
        return {"ok": True, "decision": "continue", "reason": "real action executed; no visual change required for this primitive", "signature": after_sig}
    return {"ok": True, "decision": "replan", "reason": "no observable change after action", "signature": after_sig}


_LOCALCOMET_FULL_CONTROL_HANDLE_BEFORE_REAL_ACTIONS_RU_V653 = globals().get("handle_dispatch_command")
_LOCALCOMET_FULL_CONTROL_IS_BEFORE_REAL_ACTIONS_RU_V653 = globals().get("is_full_control_command")


def is_full_control_command(command: str) -> bool:
    lowered = _norm(command)
    if lowered in {
        "pc computer real actions",
        "pc computer real actions status",
        "pc computer real actions capabilities",
        "возможности управления пк",
        "статус real actions",
    }:
        return True
    if callable(_LOCALCOMET_FULL_CONTROL_IS_BEFORE_REAL_ACTIONS_RU_V653):
        return bool(_LOCALCOMET_FULL_CONTROL_IS_BEFORE_REAL_ACTIONS_RU_V653(command))
    return False


def handle_dispatch_command(command: str) -> Dict[str, Any]:
    raw = str(command or "").strip()
    lowered = _norm(raw)
    if lowered in {
        "pc computer real actions",
        "pc computer real actions status",
        "pc computer real actions capabilities",
        "возможности управления пк",
        "статус real actions",
    }:
        return _localcomet_real_actions_capabilities_ru_v653()

    if callable(_LOCALCOMET_FULL_CONTROL_HANDLE_BEFORE_REAL_ACTIONS_RU_V653):
        result = _LOCALCOMET_FULL_CONTROL_HANDLE_BEFORE_REAL_ACTIONS_RU_V653(command)
        if isinstance(result, dict):
            if result.get("mode") in {"computer_use_full_control_mission", "computer_use_full_control_status", "computer_use_full_control_latest", "computer_use_full_control_report"}:
                result["version"] = FULL_CONTROL_VERSION
            return result
    return {
        "ok": False,
        "handled": False,
        "mode": "computer_use_full_control_mission",
        "version": FULL_CONTROL_VERSION,
        "reason": "not a full control command",
    }


def run_self_check(write_report: bool = True) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details if details is not None else {}})

    try:
        from modules.computer_use_real_actions_ru import build_real_action_plan, execute_real_action, run_self_check as real_actions_self_check
        real_check = real_actions_self_check(write_report=write_report)
        add("real actions self check", real_check.get("ok") and real_check.get("summary", {}).get("failed") == 0, real_check)

        plan = build_real_action_plan("открой блокнот и напиши hello и нажми enter", max_steps=8)
        kinds = [item.get("kind") for item in plan.get("actions", [])]
        add("full control uses real action planner", plan.get("ok") and "open_app" in kinds and "paste_text" in kinds and "press_key" in kinds, {"kinds": kinds})

        simulated_key = execute_real_action({"kind": "press_key", "key": "enter"}, simulate=True)
        add("real press key simulation", simulated_key.get("ok") and simulated_key.get("status") == "simulated", simulated_key)
    except Exception as exc:
        add("real actions integration exception", False, {"error": str(exc)})

    blocked = run_full_control_mission("удали все файлы через powershell", simulate=True, max_steps=3)
    add("hard gate blocks destructive shell goal", blocked.get("outcome") == "blocked", {"outcome": blocked.get("outcome"), "reason": blocked.get("reason")})

    confirmation = run_full_control_mission("введи Поиск :: write changes to file response.json", simulate=True, max_steps=3)
    add("file-changing typed payload requires confirmation", confirmation.get("outcome") == "requires_confirmation", {"outcome": confirmation.get("outcome"), "reason": confirmation.get("reason")})

    sample = run_full_control_mission("открой блокнот и напиши hello и нажми enter", simulate=True, max_steps=8)
    sample_kinds = [step.get("planned_action", {}).get("kind") for step in sample.get("steps", [])]
    add("simulate open app type key completes", sample.get("outcome") == "done" and {"open_app", "paste_text", "press_key"}.issubset(set(sample_kinds)), {"outcome": sample.get("outcome"), "kinds": sample_kinds, "steps": len(sample.get("steps", [])), "report": sample.get("report")})

    click_sample = run_full_control_mission("кликни по Сохранить", simulate=True, max_steps=4)
    click_kinds = [step.get("planned_action", {}).get("kind") for step in click_sample.get("steps", [])]
    add("simulate grounded click action route", click_sample.get("outcome") in {"done", "ask_user"} and "click_element" in click_kinds, {"outcome": click_sample.get("outcome"), "kinds": click_kinds})

    scroll_sample = run_full_control_mission("прокрути вниз", simulate=True, max_steps=3)
    scroll_kinds = [step.get("planned_action", {}).get("kind") for step in scroll_sample.get("steps", [])]
    add("simulate scroll action route", scroll_sample.get("outcome") == "done" and "scroll" in scroll_kinds, {"outcome": scroll_sample.get("outcome"), "kinds": scroll_kinds})

    status_result = status()
    add("status route works", status_result.get("ok") and status_result.get("mode") == "computer_use_full_control_status", status_result)

    dispatch_sim = handle_dispatch_command("pc computer full control simulate открой блокнот и напиши hello и нажми enter")
    add("dispatch simulate full control handled", dispatch_sim.get("handled") and dispatch_sim.get("outcome") == "done", {"outcome": dispatch_sim.get("outcome"), "steps": len(dispatch_sim.get("steps", []))})

    caps = handle_dispatch_command("pc computer real actions")
    add("real action capabilities route handled", caps.get("handled") and caps.get("ok") and "open_app" in caps.get("actions", []), caps)

    add("управляй пк command is recognized", is_full_control_command("управляй пк открой блокнот"), {})
    add("module has no public dispatch export", "dispatch" not in globals(), {})

    latest = latest_report()
    add("latest report is available", latest.get("ok") and Path(str(latest.get("report", ""))).exists(), {"report": latest.get("report")})

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    payload = {
        "ok": summary["failed"] == 0,
        "mode": "computer_use_full_control_self_check",
        "version": FULL_CONTROL_VERSION,
        "summary": summary,
        "checks": checks,
    }
    if write_report:
        report_dir = MISSION_DIR / "self_checks"
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / ("self_check_" + _stamp() + ".json")
        _write_json(path, payload)
        payload["report"] = str(path)
    return payload

# END LOCALCOMET V6.53 COMPUTER USE REAL ACTIONS UPGRADE RU
