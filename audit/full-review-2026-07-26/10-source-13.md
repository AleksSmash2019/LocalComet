# Полный исходный код (продолжение)

### ПУТЬ: modules/computer_use_focus_guard_ru.py (346 строк, 11519 байт)

````python

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
````

### ПУТЬ: modules/computer_use_full_control_mission_ru.py (1272 строк, 54797 байт)

````python
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
````

### ПУТЬ: modules/computer_use_grounding_ru.py (429 строк, 14924 байт)

````python

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
import json
import math
import re
import uuid

GROUNDING_VERSION = "v6.47d"
ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
GROUNDING_DIR = COMPUTER_USE_DIR / "grounding"
LATEST_UI_MAP_PATH = COMPUTER_USE_DIR / "latest_ui_map.json"


ROLE_SYNONYMS = {
    "button": {"button", "btn", "кнопка", "нажми", "click", "клик"},
    "textbox": {"textbox", "input", "edit", "field", "поле", "ввод", "поиск", "search", "editor"},
    "tab": {"tab", "вкладка"},
    "menu": {"menu", "меню"},
    "checkbox": {"checkbox", "check", "чекбокс", "галочка"},
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)
    GROUNDING_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
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


def _tokens(text: str) -> List[str]:
    value = str(text or "").lower().replace("_", " ").replace("-", " ")
    return re.findall(r"[a-zа-яё0-9]+", value, flags=re.IGNORECASE)


def _norm(text: str) -> str:
    return " ".join(_tokens(text))


def _element_text(element: Dict[str, Any]) -> str:
    fields = [
        "text", "label", "name", "title", "value", "placeholder", "automation_id",
        "id", "element_id", "role", "type", "class_name", "description",
    ]
    values = []
    for field in fields:
        value = element.get(field)
        if value is not None:
            values.append(str(value))
    return " ".join(values)


def _extract_bounds(element: Dict[str, Any]) -> Dict[str, int]:
    raw = element.get("bounds") or element.get("rect") or element.get("box") or {}
    if isinstance(raw, list) and len(raw) >= 4:
        x, y, w, h = raw[:4]
        return {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
    if not isinstance(raw, dict):
        raw = {}

    def first(*names: str, default: int = 0) -> int:
        for name in names:
            if name in raw and raw[name] is not None:
                try:
                    return int(float(raw[name]))
                except Exception:
                    pass
            if name in element and element[name] is not None:
                try:
                    return int(float(element[name]))
                except Exception:
                    pass
        return default

    left = first("x", "left")
    top = first("y", "top")
    width = first("w", "width")
    height = first("h", "height")
    right = first("right", default=left + width)
    bottom = first("bottom", default=top + height)

    if width <= 0 and right > left:
        width = right - left
    if height <= 0 and bottom > top:
        height = bottom - top

    return {"x": left, "y": top, "w": max(0, width), "h": max(0, height)}


def _center(bounds: Dict[str, int]) -> Dict[str, int]:
    return {
        "x": int(bounds.get("x", 0) + bounds.get("w", 0) / 2),
        "y": int(bounds.get("y", 0) + bounds.get("h", 0) / 2),
    }


def _extract_elements(payload: Any) -> List[Dict[str, Any]]:
    elements: List[Dict[str, Any]] = []
    if isinstance(payload, dict):
        for key in ("elements", "ui_elements", "items", "nodes"):
            value = payload.get(key)
            if isinstance(value, list):
                elements.extend(item for item in value if isinstance(item, dict))
        backend = payload.get("backend")
        if isinstance(backend, dict):
            elements.extend(_extract_elements(backend))
        ui_map = payload.get("ui_map")
        if isinstance(ui_map, dict):
            elements.extend(_extract_elements(ui_map))
    elif isinstance(payload, list):
        elements.extend(item for item in payload if isinstance(item, dict))

    deduped = []
    seen = set()
    for item in elements:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def _candidate_paths() -> List[Path]:
    paths: List[Path] = []
    if LATEST_UI_MAP_PATH.exists():
        paths.append(LATEST_UI_MAP_PATH)

    runs_dir = COMPUTER_USE_DIR / "runs"
    if runs_dir.exists():
        paths.extend(sorted(runs_dir.glob("run_*/steps/step_*_ui_map.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20])

    return paths


def load_latest_ui_map() -> Dict[str, Any]:
    _ensure_dirs()
    for path in _candidate_paths():
        payload = _read_json(path, {})
        elements = _extract_elements(payload)
        if elements or path == LATEST_UI_MAP_PATH:
            return {
                "ok": True,
                "mode": "computer_use_grounding_load_ui_map",
                "ui_map_path": str(path),
                "payload": payload,
                "elements": elements,
                "element_count": len(elements),
            }

    return {
        "ok": False,
        "mode": "computer_use_grounding_load_ui_map",
        "ui_map_path": "",
        "payload": {},
        "elements": [],
        "element_count": 0,
        "error": "No UI map found. Run pc computer map or pc computer loop first.",
    }


def score_element(description: str, element: Dict[str, Any]) -> Dict[str, Any]:
    query_tokens = set(_tokens(description))
    text_value = _element_text(element)
    element_tokens = set(_tokens(text_value))
    role = str(element.get("role") or element.get("type") or "").lower()

    if not query_tokens:
        overlap_score = 0.0
    else:
        overlap = query_tokens & element_tokens
        overlap_score = len(overlap) / max(1, len(query_tokens))

    substring_score = 0.0
    normalized_description = _norm(description)
    normalized_element = _norm(text_value)
    if normalized_description and normalized_description in normalized_element:
        substring_score = 0.35
    elif normalized_element and normalized_element in normalized_description:
        substring_score = 0.2

    role_score = 0.0
    for canonical_role, words in ROLE_SYNONYMS.items():
        if canonical_role in role or any(word in query_tokens for word in words):
            if canonical_role in role:
                role_score = max(role_score, 0.18)

    bounds = _extract_bounds(element)
    bounds_score = 0.08 if bounds.get("w", 0) > 0 and bounds.get("h", 0) > 0 else 0.0

    try:
        source_conf = float(element.get("confidence", element.get("score", 0.5)))
    except Exception:
        source_conf = 0.5
    source_score = max(0.0, min(1.0, source_conf)) * 0.12

    exact_id_score = 0.0
    element_id = str(element.get("element_id") or element.get("id") or element.get("automation_id") or "").lower()
    if element_id and any(token in element_id for token in query_tokens):
        exact_id_score = 0.18

    total = min(1.0, overlap_score * 0.55 + substring_score + role_score + bounds_score + source_score + exact_id_score)

    return {
        "score": round(total, 4),
        "overlap_score": round(overlap_score, 4),
        "substring_score": round(substring_score, 4),
        "role_score": round(role_score, 4),
        "bounds_score": round(bounds_score, 4),
        "source_score": round(source_score, 4),
        "exact_id_score": round(exact_id_score, 4),
        "bounds": bounds,
        "center": _center(bounds),
        "element_text": text_value,
    }


def find_candidates(description: str, limit: int = 8) -> Dict[str, Any]:
    loaded = load_latest_ui_map()
    elements = loaded.get("elements", [])
    candidates = []
    for index, element in enumerate(elements):
        scored = score_element(description, element)
        candidate = {
            "rank": 0,
            "index": index,
            "score": scored["score"],
            "element_id": element.get("element_id") or element.get("id") or element.get("automation_id") or f"el_{index:03d}",
            "role": element.get("role") or element.get("type") or "",
            "text": element.get("text") or element.get("label") or element.get("name") or element.get("title") or "",
            "bounds": scored["bounds"],
            "center": scored["center"],
            "source": element.get("source", ""),
            "raw": element,
            "score_details": scored,
        }
        candidates.append(candidate)

    candidates.sort(key=lambda item: item["score"], reverse=True)
    for rank, candidate in enumerate(candidates, start=1):
        candidate["rank"] = rank

    path = GROUNDING_DIR / f"find_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    payload = {
        "ok": True,
        "mode": "computer_use_find_candidates",
        "version": GROUNDING_VERSION,
        "description": description,
        "ui_map_path": loaded.get("ui_map_path", ""),
        "element_count": len(elements),
        "candidates": candidates[:limit],
        "created_at": _now(),
    }
    artifact = _write_json(path, payload)
    payload["artifact"] = artifact
    return payload


def ground_element(description: str, min_confidence: float = 0.35) -> Dict[str, Any]:
    found = find_candidates(description, limit=8)
    candidates = found.get("candidates", [])
    best = candidates[0] if candidates else None

    if not best:
        result = {
            "ok": False,
            "mode": "computer_use_ground_element",
            "description": description,
            "reason": "No UI candidates found.",
            "candidates": [],
            "min_confidence": min_confidence,
        }
    elif float(best.get("score", 0.0)) < float(min_confidence):
        result = {
            "ok": False,
            "mode": "computer_use_ground_element",
            "description": description,
            "reason": "Best candidate is below confidence threshold.",
            "best": best,
            "candidates": candidates,
            "min_confidence": min_confidence,
        }
    else:
        bounds = best.get("bounds") or {}
        center = best.get("center") or {}
        result = {
            "ok": True,
            "mode": "computer_use_ground_element",
            "version": GROUNDING_VERSION,
            "description": description,
            "confidence": best["score"],
            "element_id": best["element_id"],
            "role": best.get("role", ""),
            "text": best.get("text", ""),
            "bounds": bounds,
            "center": center,
            "target": {
                "element_id": best["element_id"],
                "element_description": description,
                "window_title": "",
                "x": center.get("x"),
                "y": center.get("y"),
                "x_norm": None,
                "y_norm": None,
                "bounds": bounds,
            },
            "candidate": best,
            "candidates": candidates,
        }

    path = GROUNDING_DIR / f"ground_element_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    result["artifact"] = _write_json(path, result)
    return result


def build_grounded_action(description: str, kind: str = "click", text: str = "", min_confidence: float = 0.35) -> Dict[str, Any]:
    grounded = ground_element(description, min_confidence=min_confidence)
    if not grounded.get("ok"):
        return {
            "ok": False,
            "mode": "computer_use_grounded_action",
            "description": description,
            "kind": kind,
            "reason": grounded.get("reason"),
            "grounding": grounded,
        }

    action = {
        "kind": kind,
        "target": grounded["target"],
        "text": text,
        "grounded": True,
        "confidence": grounded["confidence"],
        "element_id": grounded["element_id"],
        "reason": f"Grounded {kind} action for element: {description}",
    }

    if kind == "type":
        action["focused_target"] = True

    return {
        "ok": True,
        "mode": "computer_use_grounded_action",
        "description": description,
        "kind": kind,
        "action": action,
        "grounding": grounded,
    }


def status() -> Dict[str, Any]:
    loaded = load_latest_ui_map()
    return {
        "ok": True,
        "mode": "computer_use_grounding_status",
        "version": GROUNDING_VERSION,
        "ui_map_path": loaded.get("ui_map_path", ""),
        "element_count": loaded.get("element_count", 0),
        "grounding_dir": str(GROUNDING_DIR),
    }


def report() -> Dict[str, Any]:
    return status()


def is_computer_use_grounding_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = [
        "pc computer find",
        "pc computer ground",
        "computer find",
        "computer ground",
        "найди элемент",
        "заземли элемент",
    ]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def dispatch(command: str) -> Dict[str, Any]:
    raw = (command or "").strip()
    value = raw.lower()

    if value in {"pc computer grounding status", "computer grounding status"}:
        return status()

    if value.startswith("pc computer find "):
        return find_candidates(raw[len("pc computer find "):].strip())

    if value.startswith("computer find "):
        return find_candidates(raw[len("computer find "):].strip())

    if value.startswith("найди элемент "):
        return find_candidates(raw[len("найди элемент "):].strip())

    if value.startswith("pc computer ground "):
        return ground_element(raw[len("pc computer ground "):].strip())

    if value.startswith("computer ground "):
        return ground_element(raw[len("computer ground "):].strip())

    if value.startswith("заземли элемент "):
        return ground_element(raw[len("заземли элемент "):].strip())

    return {
        "ok": False,
        "mode": "computer_use_grounding_unknown_command",
        "command": command,
    }
````

### ПУТЬ: modules/computer_use_loop_ru.py (269 строк, 14735 байт)

````python

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import time

from modules.computer_use_schema_ru import compact_state, latest_run_id, load_run, make_action, new_run_state, now_iso, safe_json_load, save_run
from modules.computer_use_safety_ru import redact_text, safety_check_action, safety_check_goal
from modules.computer_use_trace_ru import build_replay_summary, save_step_artifact, write_event, write_run_report

LOOP_VERSION = "v6.47d"


def start_run(goal: str, max_steps: int = 8) -> Dict[str, Any]:
    clean_goal = redact_text((goal or "").strip())
    safety = safety_check_goal(clean_goal)
    if not safety["ok"]:
        return {"ok": False, "mode": "computer_use_run_blocked", "blocked": True, "goal": clean_goal, "reason": safety["reason"], "problem_types": safety["problem_types"]}
    state = new_run_state(clean_goal, max_steps)
    save_run(state)
    write_event(state["run_id"], "computer_run_started", {"goal": clean_goal, "max_steps": max_steps})
    return {"ok": True, "mode": "computer_use_run_started", "run_id": state["run_id"], "state": state}


def _core_observe() -> Dict[str, Any]:
    try:
        from modules.computer_use_core_ru import observe_screen
        result = observe_screen()
        return result if isinstance(result, dict) else {"ok": False, "error": "observe returned non-dict"}
    except Exception as exc:
        return {"ok": False, "mode": "computer_use_observe_fallback", "error": str(exc), "limitations": [str(exc)]}


def _core_map() -> Dict[str, Any]:
    try:
        from modules.computer_use_core_ru import build_ui_map
        result = build_ui_map()
        return result if isinstance(result, dict) else {"ok": False, "error": "map returned non-dict"}
    except Exception as exc:
        return {"ok": False, "mode": "computer_use_map_fallback", "error": str(exc), "elements": [], "limitations": [str(exc)]}


def observe_for_run(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_observation", "error": "no run"}
    state = load_run(rid)
    step = int(state.get("step") or 0) + 1
    state["step"] = step
    state["phase"] = "observing"
    save_run(state)
    observed = _core_observe()
    observation = {"ok": True, "mode": "computer_use_observation", "run_id": rid, "step": step, "created_at": now_iso(), "backend": observed}
    path = save_step_artifact(rid, step, "observation", observation)
    state["latest_observation_path"] = path
    state["phase"] = "mapping_ui"
    save_run(state)
    write_event(rid, "screen_observed", {"step": step, "observation_path": path, "backend_ok": observed.get("ok")})
    return observation | {"observation_path": path}


def build_ui_map_for_run(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_ui_map", "error": "no run"}
    state = load_run(rid)
    step = int(state.get("step") or 1)
    mapped = _core_map()
    ui_map = {"ok": True, "mode": "computer_use_ui_map", "run_id": rid, "step": step, "created_at": now_iso(), "backend": mapped, "elements": mapped.get("elements", []) if isinstance(mapped.get("elements", []), list) else []}
    path = save_step_artifact(rid, step, "ui_map", ui_map)
    state["latest_ui_map_path"] = path
    state["phase"] = "thinking"
    save_run(state)
    write_event(rid, "ui_map_built", {"step": step, "ui_map_path": path, "element_count": len(ui_map["elements"])})
    return ui_map | {"ui_map_path": path, "element_count": len(ui_map["elements"])}


def propose_next_action(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_decision", "error": "no run"}
    state = load_run(rid)
    step = int(state.get("step") or 1)
    goal = (state.get("goal") or "").lower()

    if step >= int(state.get("max_steps") or 8):
        action = make_action(rid, step, "ask_user", "Достигнут лимит шагов. Нужна новая инструкция.", "medium", False, True)
    elif any(word in goal for word in ["готово", "done", "finish", "заверши"]):
        action = make_action(rid, step, "done", "Цель похожа на завершение.", "low", True, False)
    elif any(word in goal for word in ["клик", "click", "нажми", "введи", "type", "hotkey", "scroll", "прокрути"]):
        action = make_action(rid, step, "ask_user", "Запрошено интерактивное действие. v6.47d может выполнить grounded non-file click/type автоматически.", "medium", False, True, {"element_description": "уточнить элемент"})
    else:
        action = make_action(rid, step, "ask_user", "Экран и UI map собраны. Нужен выбор конкретного следующего безопасного действия.", "medium", False, True)

    safety = safety_check_action(action)
    action["risk"] = safety.get("risk", action["risk"])
    action["requires_confirmation"] = safety.get("requires_confirmation", True)
    action["allowed_to_execute"] = bool(safety.get("allowed_to_execute")) and not action["requires_confirmation"]
    action["safety_notes"] = safety.get("notes", []) + [safety.get("reason", "")]
    decision = {"ok": not safety.get("blocked", False), "mode": "computer_use_decision", "run_id": rid, "step": step, "action": action, "safety": safety, "requires_confirmation": action["requires_confirmation"], "allowed_to_execute": action["allowed_to_execute"]}
    path = save_step_artifact(rid, step, "decision", decision)
    state["latest_decision_path"] = path
    state["pending_action_id"] = action["action_id"]
    state["pending_confirmation"] = action["requires_confirmation"]
    state["phase"] = "waiting_confirmation" if action["requires_confirmation"] else "ready_to_execute"
    state["next_safe_action"] = f"pc computer approve {action['action_id']}" if action["requires_confirmation"] else "pc computer step"
    save_run(state)
    write_event(rid, "decision_proposed", {"step": step, "decision_path": path, "action": action, "safety": safety})
    return decision | {"decision_path": path}


def run_goal_loop(goal: str, max_steps: int = 8, require_confirmation: bool = True) -> Dict[str, Any]:
    started = start_run(goal, max_steps)
    if not started.get("ok"):
        return started
    rid = started["run_id"]
    observation = observe_for_run(rid)
    ui_map = build_ui_map_for_run(rid)
    decision = propose_next_action(rid)
    report_result = write_run_report(rid)
    state = load_run(rid)
    return {"ok": True, "mode": "computer_use_loop_started", "run_id": rid, "state": compact_state(state), "observation": observation, "ui_map": ui_map, "decision": decision, "report": report_result.get("report"), "next_safe_action": state.get("next_safe_action")}


def approve_action(action_id: str, run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_approve", "error": "no run"}
    state = load_run(rid)
    decision = safe_json_load(Path(state.get("latest_decision_path", "")), {})
    action = decision.get("action") or {}
    if action.get("action_id") != action_id:
        return {"ok": False, "mode": "computer_use_approve", "error": "action id mismatch", "expected": action.get("action_id"), "received": action_id}
    safety = safety_check_action(action)
    if safety.get("blocked"):
        state["phase"] = "blocked"
        state["status"] = "blocked"
        save_run(state)
        return {"ok": False, "mode": "computer_use_approve", "blocked": True, "safety": safety}
    action["confirmed"] = True
    action["confirmed_at"] = now_iso()
    decision["action"] = action
    decision["confirmed"] = True
    Path(state["latest_decision_path"]).write_text(__import__("json").dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    state["pending_confirmation"] = False
    state["phase"] = "approved"
    state["next_safe_action"] = "pc computer step"
    save_run(state)
    write_event(rid, "action_confirmed", {"action_id": action_id})
    return {"ok": True, "mode": "computer_use_approve", "run_id": rid, "action_id": action_id, "confirmed": True}


def execute_one_step(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_step", "error": "no run"}
    state = load_run(rid)
    decision = safe_json_load(Path(state.get("latest_decision_path", "")), {})
    action = decision.get("action") or {}
    if not action:
        observe_for_run(rid)
        build_ui_map_for_run(rid)
        return propose_next_action(rid)
    if action.get("requires_confirmation") and not action.get("confirmed"):
        state["phase"] = "waiting_confirmation"
        state["pending_confirmation"] = True
        save_run(state)
        return {"ok": False, "mode": "computer_use_step_waiting_confirmation", "pending_action_id": action.get("action_id"), "next_safe_action": f"pc computer approve {action.get('action_id')}"}

    kind = action.get("kind")
    if kind in {"click", "double_click", "type", "hotkey", "scroll", "move"}:
        from modules.computer_use_auto_action_ru import execute_gui_action
        auto_result = execute_gui_action(action, simulate=bool(action.get("simulate")))
        ok = bool(auto_result.get("ok"))
        result = {"ok": ok, "mode": "computer_use_action_result", "run_id": rid, "step": state.get("step"), "action_id": action.get("action_id"), "action_kind": kind, "executed": bool(auto_result.get("executed")), "message": auto_result.get("message") or auto_result.get("reason") or "auto GUI action processed", "auto_result": auto_result, "created_at": now_iso()}
    else:
        ok = kind in {"observe", "screenshot", "wait", "done"}
        if kind == "wait":
            time.sleep(0.2)
        if kind == "done":
            state["phase"] = "done"
            state["status"] = "done"
        result = {"ok": ok, "mode": "computer_use_action_result", "run_id": rid, "step": state.get("step"), "action_id": action.get("action_id"), "action_kind": kind, "executed": ok, "message": "v6.47d limited non-GUI primitive execution", "created_at": now_iso()}
    result_path = save_step_artifact(rid, int(state.get("step") or 1), "result", result)
    state["latest_result_path"] = result_path
    state["pending_action_id"] = ""
    state["pending_confirmation"] = False
    if state.get("status") != "done":
        observe_for_run(rid)
        build_ui_map_for_run(rid)
        propose_next_action(rid)
    save_run(load_run(rid) | {"latest_result_path": result_path})
    write_event(rid, "action_executed", result)
    write_run_report(rid)
    return result | {"result_path": result_path, "state": compact_state(load_run(rid))}


def stop_run(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_stop", "error": "no run"}
    state = load_run(rid)
    state["phase"] = "stopped"
    state["status"] = "stopped"
    state["stopped"] = True
    state["next_safe_action"] = "pc computer report"
    save_run(state)
    write_event(rid, "run_stopped", {})
    write_run_report(rid)
    return {"ok": True, "mode": "computer_use_stop", "run_id": rid, "state": compact_state(state)}


def latest_run() -> Dict[str, Any]:
    rid = latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_latest", "error": "no runs"}
    return {"ok": True, "mode": "computer_use_latest", "state": compact_state(load_run(rid)), "replay": build_replay_summary(rid)}


def list_runs() -> Dict[str, Any]:
    from modules.computer_use_schema_ru import RUNS_DIR
    rows = [compact_state(load_run(path.parent.name)) for path in sorted(RUNS_DIR.glob("run_*/run.json"))[-20:]]
    return {"ok": True, "mode": "computer_use_runs", "runs": rows, "latest_run_id": latest_run_id()}


def status() -> Dict[str, Any]:
    return {"ok": True, "mode": "computer_use_loop_status", "version": LOOP_VERSION, "latest_run_id": latest_run_id(), "state": compact_state(load_run()) if latest_run_id() else {}}


def report() -> Dict[str, Any]:
    rid = latest_run_id()
    if not rid:
        return {"ok": True, "mode": "computer_use_loop_report", "version": LOOP_VERSION, "latest_run_id": ""}
    rep = write_run_report(rid)
    return {"ok": True, "mode": "computer_use_loop_report", "version": LOOP_VERSION, "latest_run_id": rid, "report": rep.get("report"), "state": compact_state(load_run(rid))}


def is_computer_use_loop_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = ["pc computer loop", "pc computer step", "pc computer approve", "pc computer resume", "pc computer runs", "pc computer latest", "pc computer replay", "цикл computer use", "шаг computer use", "одобри действие", "последний computer use"]
    return any(value == p or value.startswith(p + " ") for p in prefixes)


def dispatch(command: str) -> Dict[str, Any]:
    raw = (command or "").strip()
    value = raw.lower()
    if value.startswith("pc computer loop "):
        return run_goal_loop(raw[len("pc computer loop "):].strip())
    if value.startswith("цикл computer use "):
        return run_goal_loop(raw[len("цикл computer use "):].strip())
    if value in {"pc computer step", "шаг computer use"}:
        return execute_one_step()
    if value.startswith("pc computer approve "):
        return approve_action(raw[len("pc computer approve "):].strip())
    if value.startswith("одобри действие "):
        return approve_action(raw[len("одобри действие "):].strip())
    if value in {"pc computer resume"}:
        return execute_one_step()
    if value in {"pc computer runs"}:
        return list_runs()
    if value in {"pc computer latest", "последний computer use"}:
        return latest_run()
    if value.startswith("pc computer replay"):
        parts = raw.split()
        return build_replay_summary(parts[-1] if len(parts) >= 4 else "")
    if value in {"pc computer report", "отчёт computer use"}:
        return report()
    return {"ok": False, "mode": "computer_use_loop_unknown_command", "command": command}
````

### ПУТЬ: modules/computer_use_multistep_loop_ru.py (1098 строк, 42616 байт)

````python
from __future__ import annotations

import json
import re
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

MULTISTEP_LOOP_VERSION = "v6.48i"
MODULE_NAME = "computer_use_multistep_loop_ru"


@dataclass
class UiCandidate:
    text: str
    role: str
    source_path: str
    bounds: dict[str, Any]
    raw: dict[str, Any]
    confidence: float = 0.0


@dataclass
class PlannedAction:
    kind: str
    target: str
    text: str
    confidence: float
    reason: str
    candidate: dict[str, Any] | None


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _json_default(value: Any) -> str:
    return str(value)


def _safe_json_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default),
        encoding="utf-8",
    )


def _safe_json_read(path: Path, fallback: Any) -> Any:
    try:
        if not path.exists():
            return fallback
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return fallback
        return json.loads(text)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": str(path)}


def _append_event(run_dir: Path, event: dict[str, Any]) -> None:
    event = dict(event)
    event.setdefault("timestamp", datetime.now().isoformat(timespec="seconds"))
    path = run_dir / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True, default=_json_default))
        handle.write("\n")


def _project_status() -> dict[str, Any]:
    try:
        from modules.project_paths import status

        result = status()
        if isinstance(result, dict):
            return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": False, "error": "project_paths.status unavailable"}


def _root() -> Path:
    status = _project_status()
    root_value = status.get("root")
    if root_value:
        return Path(root_value)
    return Path.cwd()


def _computer_use_dir() -> Path:
    status = _project_status()
    value = status.get("computer_use_dir")
    if value:
        return Path(value)
    return _root() / "Projects" / "ComputerUse"


def _latest_ui_map_path() -> Path:
    status = _project_status()
    value = status.get("computer_use_latest_ui_map_path")
    if value:
        return Path(value)
    return _computer_use_dir() / "latest_ui_map.json"


def _runs_dir() -> Path:
    return _computer_use_dir() / "multistep_runs"


def _latest_run_pointer() -> Path:
    return _runs_dir() / "latest_run.json"


def _stop_file() -> Path:
    return _runs_dir() / "stop_requested.json"


def _normalize(text: Any) -> str:
    value = str(text or "").casefold()
    value = value.replace("ё", "е")
    value = re.sub(r"[^0-9a-zа-я_:\-\s]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _looks_destructive_or_sensitive(text: str) -> bool:
    lowered = _normalize(text)
    markers = [
        "powershell",
        "cmd",
        "terminal",
        "shell",
        "sudo",
        "admin",
        "удали",
        "удалить",
        "delete",
        "wipe",
        "format",
        "rm ",
        "rmdir",
        "del ",
        "token",
        "api key",
        "apikey",
        "private key",
        "ssh",
        "cookie",
        "cookies",
        "browser profile",
        "password",
        "пароль",
        "секрет",
        "ключ",
        "банк",
        "bank",
        "payment",
        "casino",
        "gambling",
    ]
    return any(marker in lowered for marker in markers)


def _looks_file_changing(text: str) -> bool:
    lowered = _normalize(text)
    markers = [
        "write changes",
        "save file",
        "response json",
        "response.json",
        "запиши файл",
        "сохрани файл",
        "измени файл",
        "перезапиши",
        "создай файл",
        "create file",
        "modify file",
        "delete file",
        "удали файл",
        "patch",
        "installer",
    ]
    return any(marker in lowered for marker in markers)


def _safety_check_goal(goal: str) -> dict[str, Any]:
    try:
        from modules.computer_use_safety_ru import safety_check_goal

        result = safety_check_goal(goal)
        if isinstance(result, dict):
            return result
    except Exception as exc:
        if _looks_destructive_or_sensitive(goal):
            return {
                "ok": False,
                "blocked": True,
                "risk": "blocked",
                "reason": "fallback blocked dangerous or sensitive marker after safety module error: " + str(exc),
                "problem_types": ["fallback_block"],
            }
        return {"ok": True, "blocked": False, "risk": "unknown", "warning": str(exc)}
    if _looks_destructive_or_sensitive(goal):
        return {
            "ok": False,
            "blocked": True,
            "risk": "blocked",
            "reason": "fallback blocked dangerous or sensitive marker",
            "problem_types": ["fallback_block"],
        }
    return {"ok": True, "blocked": False, "risk": "unknown"}


def _iter_dict_nodes(value: Any, path: str = "$") -> list[tuple[str, dict[str, Any]]]:
    nodes: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, dict):
        nodes.append((path, value))
        for key, child in value.items():
            nodes.extend(_iter_dict_nodes(child, path + "." + str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            nodes.extend(_iter_dict_nodes(child, path + "[" + str(index) + "]"))
    return nodes


def _first_text(data: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)) and str(value).strip():
            return str(value).strip()
    return ""


def _extract_bounds(data: dict[str, Any]) -> dict[str, Any]:
    direct: dict[str, Any] = {}
    for key in ("x", "y", "width", "height", "left", "top", "right", "bottom"):
        if key in data and isinstance(data.get(key), (int, float, str)):
            direct[key] = data.get(key)
    for key in ("bounds", "bbox", "rect", "rectangle"):
        value = data.get(key)
        if isinstance(value, dict):
            for bkey in ("x", "y", "width", "height", "left", "top", "right", "bottom"):
                if bkey in value:
                    direct[bkey] = value.get(bkey)
        elif isinstance(value, list) and len(value) >= 4:
            direct["x"] = value[0]
            direct["y"] = value[1]
            direct["width"] = value[2]
            direct["height"] = value[3]
    return direct


def extract_candidates(ui_map: Any) -> list[dict[str, Any]]:
    candidates: list[UiCandidate] = []
    text_keys = [
        "text",
        "title",
        "name",
        "label",
        "caption",
        "value",
        "automation_id",
        "automationId",
        "id",
        "control",
        "control_text",
    ]
    role_keys = ["role", "type", "control_type", "controlType", "class_name", "className", "kind"]
    for path, node in _iter_dict_nodes(ui_map):
        text = _first_text(node, text_keys)
        role = _first_text(node, role_keys)
        bounds = _extract_bounds(node)
        if not text and not role:
            continue
        if not text and role:
            continue
        if len(text) > 180:
            continue
        candidates.append(
            UiCandidate(
                text=text,
                role=role,
                source_path=path,
                bounds=bounds,
                raw={key: node.get(key) for key in set(text_keys + role_keys) if key in node},
            )
        )
    unique: dict[tuple[str, str, str], UiCandidate] = {}
    for item in candidates:
        key = (_normalize(item.text), _normalize(item.role), item.source_path)
        unique[key] = item
    return [asdict(item) for item in unique.values()]


def _read_ui_map() -> dict[str, Any]:
    path = _latest_ui_map_path()
    data = _safe_json_read(path, {})
    candidates = extract_candidates(data)
    return {
        "ok": bool(candidates) or isinstance(data, dict),
        "path": str(path),
        "raw": data,
        "candidates": candidates,
        "candidate_count": len(candidates),
    }


def _strip_command_prefix(goal: str) -> str:
    value = _normalize(goal)
    prefixes = [
        "pc computer run loop",
        "pc computer simulate loop",
        "цикл computer use",
        "симуляция цикла computer use",
        "computer use",
        "pc computer",
    ]
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix) :].strip()
    return value


def _action_kind(goal: str) -> str:
    value = _normalize(goal)
    type_markers = ["type", "search", "введи", "напечатай", "поиск", "найди"]
    click_markers = ["click", "open", "press", "нажми", "клик", "кликни", "открой", "выбери"]
    if "::" in goal and any(marker in value for marker in type_markers):
        return "type"
    if any(marker in value for marker in click_markers):
        return "click"
    return "unknown"


def _target_words(goal: str) -> str:
    value = _strip_command_prefix(goal)
    remove_words = [
        "click",
        "open",
        "press",
        "button",
        "element",
        "нажми",
        "клик",
        "кликни",
        "открой",
        "выбери",
        "кнопку",
        "кнопка",
        "элемент",
        "меню",
        "по",
        "на",
    ]
    words = [word for word in value.split() if word not in remove_words]
    return " ".join(words).strip()


def _score_candidate_for_goal(candidate: dict[str, Any], goal: str, target: str) -> float:
    text = _normalize(candidate.get("text"))
    role = _normalize(candidate.get("role"))
    full = (text + " " + role).strip()
    normalized_goal = _normalize(goal)
    normalized_target = _normalize(target)
    if not text:
        return 0.0
    if text in normalized_goal:
        return 0.97
    if normalized_target and normalized_target in full:
        return 0.94
    if normalized_target and full in normalized_target and len(full) >= 3:
        return 0.91
    target_words = [word for word in normalized_target.split() if len(word) >= 3]
    if target_words:
        matched = sum(1 for word in target_words if word in full)
        ratio = matched / max(1, len(target_words))
        if ratio >= 0.67:
            return 0.66 + min(0.22, ratio * 0.22)
    if "button" in role or "кноп" in role:
        goal_words = [word for word in normalized_goal.split() if len(word) >= 4]
        if goal_words and any(word in text for word in goal_words):
            return 0.68
    return 0.0


def _best_candidate(candidates: list[dict[str, Any]], goal: str, target: str) -> tuple[dict[str, Any] | None, float]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for candidate in candidates:
        score = _score_candidate_for_goal(candidate, goal, target)
        updated = dict(candidate)
        updated["confidence"] = round(score, 4)
        scored.append((score, updated))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if not scored:
        return None, 0.0
    return scored[0][1], scored[0][0]


def _parse_type_goal(goal: str) -> tuple[str, str]:
    left, right = goal.split("::", 1)
    target = _target_words(left)
    normalized = _normalize(target)
    if "поиск" in normalized or "search" in normalized:
        target = "Поиск"
    target = target.strip() or "Поиск"
    text = right.strip()
    return target, text


def _candidate_summaries(candidates: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for candidate in candidates[:limit]:
        result.append(
            {
                "text": candidate.get("text", ""),
                "role": candidate.get("role", ""),
                "confidence": candidate.get("confidence", 0.0),
                "source_path": candidate.get("source_path", ""),
                "bounds": candidate.get("bounds", {}),
            }
        )
    return result


def decide_next_action(goal: str, ui_observation: dict[str, Any]) -> dict[str, Any]:
    candidates = ui_observation.get("candidates", [])
    kind = _action_kind(goal)
    if kind == "type":
        if "::" not in goal:
            return {
                "ok": False,
                "decision": "ask_user",
                "reason": "Для ввода нужен формат: цель :: текст",
                "candidates": _candidate_summaries(candidates),
            }
        target, text = _parse_type_goal(goal)
        candidate, confidence = _best_candidate(candidates, goal, target)
        if candidate is None or confidence < 0.62:
            return {
                "ok": False,
                "decision": "ask_user",
                "reason": "Низкая уверенность grounding для поля ввода",
                "target": target,
                "candidates": _candidate_summaries(candidates),
            }
        return {
            "ok": True,
            "decision": "action",
            "action": asdict(
                PlannedAction(
                    kind="type",
                    target=target,
                    text=text,
                    confidence=round(confidence, 4),
                    reason="deterministic type rule with explicit :: payload",
                    candidate=candidate,
                )
            ),
        }
    if kind == "click":
        target = _target_words(goal)
        candidate, confidence = _best_candidate(candidates, goal, target)
        if candidate is None or confidence < 0.62:
            return {
                "ok": False,
                "decision": "ask_user",
                "reason": "Низкая уверенность grounding для клика",
                "target": target,
                "candidates": _candidate_summaries(candidates),
            }
        return {
            "ok": True,
            "decision": "action",
            "action": asdict(
                PlannedAction(
                    kind="click",
                    target=str(candidate.get("text") or target),
                    text="",
                    confidence=round(confidence, 4),
                    reason="deterministic click/open rule matched candidate text",
                    candidate=candidate,
                )
            ),
        }
    return {
        "ok": False,
        "decision": "ask_user",
        "reason": "Не найдено безопасное детерминированное действие",
        "candidates": _candidate_summaries(candidates),
    }


def _call_click_element(target: str, simulate: bool) -> dict[str, Any]:
    module_names = [
        "modules.computer_use_auto_action_ru",
        "modules.computer_use_click_planner_ru",
        "modules.computer_use_core_ru",
    ]
    last_error = ""
    for module_name in module_names:
        try:
            module = import_module(module_name)
            func = getattr(module, "click_element", None)
            if callable(func):
                result = func(target, simulate=simulate)
                if isinstance(result, dict):
                    return result
                return {"ok": bool(result), "result": result}
        except Exception as exc:
            last_error = module_name + ": " + str(exc)
    if simulate:
        return {
            "ok": True,
            "mode": "click_element_simulated_by_multistep_loop",
            "target": target,
            "simulate": True,
            "warning": last_error,
        }
    return {
        "ok": False,
        "mode": "click_element_unavailable",
        "target": target,
        "simulate": False,
        "error": last_error or "click_element function not found",
    }


def _call_guarded_type(target: str, text: str, simulate: bool) -> dict[str, Any]:
    module_names = [
        "modules.computer_use_type_guard_ru",
        "modules.computer_use_auto_action_ru",
        "modules.computer_use_core_ru",
    ]
    last_error = ""
    for module_name in module_names:
        try:
            module = import_module(module_name)
            func = getattr(module, "guarded_type", None)
            if callable(func):
                result = func(target, text, simulate=simulate)
                if isinstance(result, dict):
                    return result
                return {"ok": bool(result), "result": result}
        except Exception as exc:
            last_error = module_name + ": " + str(exc)
    if simulate:
        return {
            "ok": True,
            "mode": "guarded_type_simulated_by_multistep_loop",
            "target": target,
            "text": text,
            "simulate": True,
            "warning": last_error,
        }
    return {
        "ok": False,
        "mode": "guarded_type_unavailable",
        "target": target,
        "text": text,
        "simulate": False,
        "error": last_error or "guarded_type function not found",
    }


def import_module(name: str) -> Any:
    import importlib

    return importlib.import_module(name)


def execute_planned_action(action: dict[str, Any], simulate: bool) -> dict[str, Any]:
    kind = action.get("kind")
    target = str(action.get("target") or "").strip()
    text = str(action.get("text") or "")
    if not target:
        return {"ok": False, "status": "error", "reason": "empty target"}
    if kind == "type":
        if _looks_file_changing(text):
            return {
                "ok": False,
                "status": "requires_confirmation",
                "requires_confirmation": True,
                "reason": "typed payload appears to change files and needs explicit confirmation",
                "target": target,
            }
        return _call_guarded_type(target, text, simulate=simulate)
    if kind == "click":
        return _call_click_element(target, simulate=simulate)
    return {"ok": False, "status": "error", "reason": "unsupported action kind: " + str(kind)}


def visual_guard_compare(before_observation: dict[str, Any], after_observation: dict[str, Any], action_result: dict[str, Any]) -> dict[str, Any]:
    before_count = int(before_observation.get("candidate_count") or 0)
    after_count = int(after_observation.get("candidate_count") or 0)
    if action_result.get("requires_confirmation") or action_result.get("status") == "requires_confirmation":
        decision = "ask_user"
        reason = "action requires explicit confirmation"
    elif not action_result.get("ok"):
        decision = "stop"
        reason = "action failed"
    elif before_count == 0 and after_count == 0:
        decision = "ask_user"
        reason = "no UI candidates before or after action"
    else:
        decision = "done"
        reason = "deterministic one-action loop completed"
    return {
        "ok": decision in {"done", "replan", "ask_user"},
        "mode": "computer_use_visual_guard_record",
        "version": MULTISTEP_LOOP_VERSION,
        "decision": decision,
        "reason": reason,
        "before_candidate_count": before_count,
        "after_candidate_count": after_count,
    }


def _make_run(goal: str, simulate: bool, max_steps: int) -> tuple[str, Path, dict[str, Any]]:
    run_id = "run_" + _now_stamp()
    run_dir = _runs_dir() / run_id
    (run_dir / "steps").mkdir(parents=True, exist_ok=True)
    data = {
        "ok": True,
        "mode": "computer_use_multistep_loop",
        "version": MULTISTEP_LOOP_VERSION,
        "run_id": run_id,
        "goal": goal,
        "simulate": bool(simulate),
        "max_steps": max_steps,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "created",
        "outcome": "running",
        "steps": [],
        "run_dir": str(run_dir),
    }
    _safe_json_write(run_dir / "run.json", data)
    _safe_json_write(_latest_run_pointer(), {"run_id": run_id, "run_dir": str(run_dir), "updated_at": data["updated_at"]})
    return run_id, run_dir, data


def _write_report(run_dir: Path, run_data: dict[str, Any]) -> str:
    lines = [
        "# Computer Use Multi-Step Loop Report",
        "",
        "- Version: " + str(run_data.get("version")),
        "- Run ID: " + str(run_data.get("run_id")),
        "- Status: " + str(run_data.get("status")),
        "- Outcome: " + str(run_data.get("outcome")),
        "- Simulate: " + str(run_data.get("simulate")),
        "- Goal: " + str(run_data.get("goal")),
        "- Steps: " + str(len(run_data.get("steps", []))),
        "",
        "## Steps",
    ]
    for step in run_data.get("steps", []):
        lines.append("")
        lines.append("### Step " + str(step.get("step_index")))
        lines.append("- Decision: " + str(step.get("decision", {}).get("decision")))
        action = step.get("action")
        if isinstance(action, dict):
            lines.append("- Action: " + str(action.get("kind")) + " -> " + str(action.get("target")))
        result = step.get("action_result")
        if isinstance(result, dict):
            lines.append("- Result ok: " + str(result.get("ok")))
            lines.append("- Result status: " + str(result.get("status", result.get("mode", ""))))
        visual = step.get("visual_guard")
        if isinstance(visual, dict):
            lines.append("- Visual guard: " + str(visual.get("decision")) + " / " + str(visual.get("reason")))
    report_path = run_dir / "report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(report_path)


def _finish_run(run_dir: Path, run_data: dict[str, Any], status: str, outcome: str, reason: str) -> dict[str, Any]:
    run_data["status"] = status
    run_data["outcome"] = outcome
    run_data["reason"] = reason
    run_data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    report = _write_report(run_dir, run_data)
    run_data["report"] = report
    _safe_json_write(run_dir / "run.json", run_data)
    _safe_json_write(_latest_run_pointer(), {"run_id": run_data.get("run_id"), "run_dir": str(run_dir), "updated_at": run_data["updated_at"]})
    _append_event(run_dir, {"event": "finish", "status": status, "outcome": outcome, "reason": reason})
    result = dict(run_data)
    result["ok"] = outcome in {"done", "requires_confirmation", "ask_user", "blocked", "stopped"}
    return result


def run_loop(goal: str, simulate: bool = False, max_steps: int = 3, max_failures: int = 1) -> dict[str, Any]:
    goal = str(goal or "").strip()
    if not goal:
        return {
            "ok": False,
            "mode": "computer_use_multistep_loop",
            "version": MULTISTEP_LOOP_VERSION,
            "status": "rejected",
            "outcome": "ask_user",
            "reason": "empty goal",
        }
    max_steps = max(1, min(int(max_steps), 8))
    max_failures = max(1, min(int(max_failures), 5))
    safety = _safety_check_goal(goal)
    if safety.get("blocked") or safety.get("ok") is False and safety.get("risk") == "blocked":
        run_id, run_dir, run_data = _make_run(goal, simulate, max_steps)
        run_data["safety"] = safety
        return _finish_run(run_dir, run_data, "blocked", "blocked", str(safety.get("reason", "blocked by safety policy")))
    if _action_kind(goal) == "type":
        parsed_target, parsed_text = _parse_type_goal(goal) if "::" in goal else ("", "")
        if _looks_file_changing(parsed_text):
            run_id, run_dir, run_data = _make_run(goal, simulate, max_steps)
            run_data["safety"] = safety
            run_data["steps"].append(
                {
                    "step_index": 0,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "observation": {"ok": None, "candidate_count": None, "candidates": []},
                    "decision": {
                        "ok": False,
                        "decision": "requires_confirmation",
                        "reason": "typed payload appears to change files and needs explicit confirmation before grounding",
                        "target": parsed_target,
                    },
                    "action": {
                        "kind": "type",
                        "target": parsed_target,
                        "text": parsed_text,
                        "confidence": 0.0,
                        "reason": "confirmation gate before UI grounding",
                        "candidate": None,
                    },
                    "action_result": {
                        "ok": False,
                        "status": "requires_confirmation",
                        "requires_confirmation": True,
                        "reason": "typed payload appears to change files and needs explicit confirmation",
                        "target": parsed_target,
                    },
                    "visual_guard": {
                        "ok": True,
                        "mode": "computer_use_visual_guard_record",
                        "version": MULTISTEP_LOOP_VERSION,
                        "decision": "ask_user",
                        "reason": "action requires explicit confirmation",
                    },
                }
            )
            return _finish_run(run_dir, run_data, "needs_confirmation", "requires_confirmation", "typed payload appears to change files and needs explicit confirmation")
    run_id, run_dir, run_data = _make_run(goal, simulate, max_steps)
    run_data["safety"] = safety
    _append_event(run_dir, {"event": "start", "run_id": run_id, "simulate": simulate, "goal": goal})
    failures = 0
    for step_index in range(1, max_steps + 1):
        if _stop_file().exists():
            stop_data = _safe_json_read(_stop_file(), {})
            return _finish_run(run_dir, run_data, "stopped", "stopped", "stop requested: " + str(stop_data.get("reason", "")))
        before = _read_ui_map()
        decision = decide_next_action(goal, before)
        step: dict[str, Any] = {
            "step_index": step_index,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "observation": {
                "ok": before.get("ok"),
                "path": before.get("path"),
                "candidate_count": before.get("candidate_count"),
                "candidates": _candidate_summaries(before.get("candidates", []), limit=8),
            },
            "decision": decision,
            "action": None,
            "action_result": None,
            "visual_guard": None,
        }
        if decision.get("decision") == "ask_user":
            step["visual_guard"] = {
                "ok": True,
                "mode": "computer_use_visual_guard_record",
                "version": MULTISTEP_LOOP_VERSION,
                "decision": "ask_user",
                "reason": decision.get("reason", "low confidence"),
            }
            run_data["steps"].append(step)
            _safe_json_write(run_dir / "steps" / ("step_" + str(step_index).zfill(3) + ".json"), step)
            _append_event(run_dir, {"event": "step", "step": step_index, "decision": "ask_user", "reason": decision.get("reason")})
            return _finish_run(run_dir, run_data, "needs_user", "ask_user", str(decision.get("reason", "low confidence")))
        if not decision.get("ok"):
            failures += 1
            step["action_result"] = {"ok": False, "status": "decision_failed", "reason": decision.get("reason", "decision failed")}
            run_data["steps"].append(step)
            _safe_json_write(run_dir / "steps" / ("step_" + str(step_index).zfill(3) + ".json"), step)
            _append_event(run_dir, {"event": "step", "step": step_index, "decision": "failed", "failures": failures})
            if failures >= max_failures:
                return _finish_run(run_dir, run_data, "failed", "error", "max failures reached")
            continue
        action = decision.get("action")
        if not isinstance(action, dict):
            failures += 1
            step["action_result"] = {"ok": False, "status": "missing_action"}
            run_data["steps"].append(step)
            _safe_json_write(run_dir / "steps" / ("step_" + str(step_index).zfill(3) + ".json"), step)
            if failures >= max_failures:
                return _finish_run(run_dir, run_data, "failed", "error", "missing action")
            continue
        step["action"] = action
        action_result = execute_planned_action(action, simulate=simulate)
        step["action_result"] = action_result
        after = _read_ui_map()
        visual = visual_guard_compare(before, after, action_result)
        step["visual_guard"] = visual
        run_data["steps"].append(step)
        _safe_json_write(run_dir / "steps" / ("step_" + str(step_index).zfill(3) + ".json"), step)
        _append_event(
            run_dir,
            {
                "event": "step",
                "step": step_index,
                "decision": decision.get("decision"),
                "action_kind": action.get("kind"),
                "action_target": action.get("target"),
                "action_ok": action_result.get("ok"),
                "visual_guard_decision": visual.get("decision"),
            },
        )
        if action_result.get("requires_confirmation") or action_result.get("status") == "requires_confirmation":
            return _finish_run(run_dir, run_data, "needs_confirmation", "requires_confirmation", str(action_result.get("reason", "confirmation required")))
        if visual.get("decision") == "ask_user":
            return _finish_run(run_dir, run_data, "needs_user", "ask_user", str(visual.get("reason", "visual guard asks user")))
        if visual.get("decision") == "stop":
            return _finish_run(run_dir, run_data, "stopped", "stopped", str(visual.get("reason", "visual guard stop")))
        if visual.get("decision") == "replan":
            continue
        return _finish_run(run_dir, run_data, "done", "done", "one deterministic action completed")
    return _finish_run(run_dir, run_data, "stopped", "stopped", "max_steps reached")


def status() -> dict[str, Any]:
    runs = _runs_dir()
    pointer = _safe_json_read(_latest_run_pointer(), {})
    stop_requested = _stop_file().exists()
    latest = latest_run()
    return {
        "ok": True,
        "mode": "computer_use_multistep_loop_status",
        "version": MULTISTEP_LOOP_VERSION,
        "runs_dir": str(runs),
        "latest_pointer": pointer,
        "latest_run_id": latest.get("run_id") if isinstance(latest, dict) else "",
        "latest_status": latest.get("status") if isinstance(latest, dict) else "",
        "latest_outcome": latest.get("outcome") if isinstance(latest, dict) else "",
        "stop_requested": stop_requested,
    }


def latest_run() -> dict[str, Any]:
    pointer = _safe_json_read(_latest_run_pointer(), {})
    run_dir = pointer.get("run_dir") if isinstance(pointer, dict) else ""
    if run_dir:
        data = _safe_json_read(Path(run_dir) / "run.json", {})
        if isinstance(data, dict) and data:
            data.setdefault("ok", True)
            data.setdefault("mode", "computer_use_multistep_loop_latest")
            return data
    return {
        "ok": False,
        "mode": "computer_use_multistep_loop_latest",
        "version": MULTISTEP_LOOP_VERSION,
        "reason": "no latest run",
    }


def latest_report() -> dict[str, Any]:
    data = latest_run()
    report_path = data.get("report") if isinstance(data, dict) else ""
    if report_path and Path(report_path).exists():
        return {
            "ok": True,
            "mode": "computer_use_multistep_loop_report",
            "version": MULTISTEP_LOOP_VERSION,
            "report": report_path,
            "content": Path(report_path).read_text(encoding="utf-8"),
        }
    return {
        "ok": False,
        "mode": "computer_use_multistep_loop_report",
        "version": MULTISTEP_LOOP_VERSION,
        "reason": "no report available",
        "latest": data,
    }


def request_stop(reason: str = "user requested stop") -> dict[str, Any]:
    data = {
        "ok": True,
        "mode": "computer_use_multistep_loop_stop",
        "version": MULTISTEP_LOOP_VERSION,
        "reason": str(reason or "user requested stop"),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    _safe_json_write(_stop_file(), data)
    return data


def clear_stop_request() -> dict[str, Any]:
    path = _stop_file()
    existed = path.exists()
    if existed:
        cleared_path = path.with_name(path.name + ".cleared_" + _now_stamp())
        path.rename(cleared_path)
    return {
        "ok": True,
        "mode": "computer_use_multistep_loop_clear_stop",
        "version": MULTISTEP_LOOP_VERSION,
        "existed": existed,
    }


def handle_dispatch_command(command: str) -> dict[str, Any]:
    raw = str(command or "").strip()
    lowered = _normalize(raw)
    prefixes_run = ["pc computer run loop", "цикл computer use"]
    prefixes_sim = ["pc computer simulate loop", "симуляция цикла computer use"]
    if lowered in {"pc computer loop status", "статус цикла computer use"}:
        result = status()
        result["handled"] = True
        return result
    if lowered in {"pc computer loop latest", "последний цикл computer use"}:
        result = latest_run()
        result["handled"] = True
        return result
    if lowered in {"pc computer loop report", "отчет цикла computer use", "отчёт цикла computer use"}:
        result = latest_report()
        result["handled"] = True
        return result
    if lowered in {"pc computer loop stop", "останови цикл computer use"}:
        result = request_stop("dispatch command: " + raw)
        result["handled"] = True
        return result
    for prefix in prefixes_sim:
        if lowered.startswith(prefix):
            goal = raw[len(prefix) :].strip()
            result = run_loop(goal, simulate=True)
            result["handled"] = True
            return result
    for prefix in prefixes_run:
        if lowered.startswith(prefix):
            goal = raw[len(prefix) :].strip()
            result = run_loop(goal, simulate=False)
            result["handled"] = True
            return result
    return {"handled": False, "ok": False, "mode": "computer_use_multistep_loop_dispatch", "reason": "not a multistep loop command"}


def _synthetic_ui_map() -> dict[str, Any]:
    return {
        "ok": True,
        "source": "computer_use_multistep_loop_ru self check",
        "elements": [
            {
                "text": "Сохранить",
                "role": "button",
                "x": 20,
                "y": 20,
                "width": 140,
                "height": 36,
                "automation_id": "btn_save",
            },
            {
                "text": "Поиск",
                "role": "edit",
                "x": 20,
                "y": 80,
                "width": 260,
                "height": 32,
                "automation_id": "input_search",
            },
            {
                "text": "Отмена",
                "role": "button",
                "x": 180,
                "y": 20,
                "width": 120,
                "height": 36,
                "automation_id": "btn_cancel",
            },
        ],
    }


def _backup_latest_ui_map() -> tuple[Path, Path | None, bool]:
    latest = _latest_ui_map_path()
    existed = latest.exists()
    backup = None
    if existed:
        backup = latest.with_name(latest.name + ".v648i_multistep_backup")
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(latest.read_bytes())
    return latest, backup, existed


def _restore_latest_ui_map(latest: Path, backup: Path | None, existed: bool) -> None:
    if existed and backup is not None and backup.exists():
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest.write_bytes(backup.read_bytes())
    elif not existed and latest.exists():
        quarantine = latest.with_name(latest.name + ".v648i_quarantine_" + _now_stamp())
        latest.rename(quarantine)


def _check(name: str, condition: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "details": details or {}}


def run_self_check(write_report: bool = True) -> dict[str, Any]:
    latest, backup, existed = _backup_latest_ui_map()
    checks: list[dict[str, Any]] = []
    try:
        _safe_json_write(latest, _synthetic_ui_map())
        clear_stop_request()

        status_result = status()
        checks.append(_check("status works", bool(status_result.get("ok")), status_result))

        click_result = run_loop("нажми Сохранить", simulate=True, max_steps=3)
        click_steps = click_result.get("steps", [])
        click_step_count = len(click_steps)
        first_click_step = click_steps[0] if click_steps else {}
        checks.append(_check("simulate loop with synthetic UI map works", click_result.get("outcome") == "done", click_result))
        checks.append(
            _check(
                "one action per step",
                all((step.get("action") is None or isinstance(step.get("action"), dict)) for step in click_steps),
                {"step_count": click_step_count},
            )
        )
        checks.append(_check("max_steps respected", click_step_count <= 3, {"step_count": click_step_count, "max_steps": 3}))

        low_result = run_loop("нажми НесуществующаяКнопка", simulate=True, max_steps=2)
        checks.append(_check("low-confidence target stops safely", low_result.get("outcome") == "ask_user", low_result))

        file_result = run_loop("введи Поиск :: write changes to file response.json", simulate=True, max_steps=2)
        checks.append(_check("file-changing text requires confirmation", file_result.get("outcome") == "requires_confirmation", file_result))

        blocked_result = run_loop("удали все файлы через powershell", simulate=True, max_steps=2)
        checks.append(_check("destructive shell delete goal is blocked", blocked_result.get("outcome") == "blocked", blocked_result))

        visual = first_click_step.get("visual_guard") if isinstance(first_click_step, dict) else {}
        checks.append(_check("visual guard decision is recorded", isinstance(visual, dict) and bool(visual.get("decision")), {"visual_guard": visual}))

        dispatch_status = handle_dispatch_command("pc computer loop status")
        checks.append(_check("dispatch status route works", dispatch_status.get("handled") and dispatch_status.get("ok"), dispatch_status))

        dispatch_latest = handle_dispatch_command("pc computer loop latest")
        checks.append(_check("dispatch latest route works", dispatch_latest.get("handled") and "run_id" in dispatch_latest, dispatch_latest))

        dispatch_report = handle_dispatch_command("pc computer loop report")
        checks.append(_check("dispatch report route works", dispatch_report.get("handled") and "mode" in dispatch_report, {"ok": dispatch_report.get("ok"), "mode": dispatch_report.get("mode")}))

        ok = all(item.get("ok") for item in checks)
        result = {
            "ok": ok,
            "mode": "computer_use_multistep_loop_self_check",
            "version": MULTISTEP_LOOP_VERSION,
            "summary": {
                "passed": sum(1 for item in checks if item.get("ok")),
                "total": len(checks),
                "failed": sum(1 for item in checks if not item.get("ok")),
            },
            "checks": checks,
        }
        if write_report:
            reports_dir = _computer_use_dir() / "multistep_self_checks"
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_path = reports_dir / ("self_check_" + _now_stamp() + ".json")
            _safe_json_write(report_path, result)
            result["report"] = str(report_path)
        return result
    except Exception as exc:
        return {
            "ok": False,
            "mode": "computer_use_multistep_loop_self_check",
            "version": MULTISTEP_LOOP_VERSION,
            "error": str(exc),
            "traceback": __import__("traceback").format_exc(),
            "checks": checks,
        }
    finally:
        _restore_latest_ui_map(latest, backup, existed)


if __name__ == "__main__":
    outcome = run_self_check(write_report=True)
    print(json.dumps(outcome, ensure_ascii=False, indent=2, sort_keys=True))
    if not outcome.get("ok"):
        raise SystemExit(1)
````

### ПУТЬ: modules/computer_use_observe_vision_ru.py (517 строк, 19996 байт)

````python

from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


VERSION = "v6.54b"
FEATURE_NAME = "Computer Use Observe/Vision Upgrade RU"

ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = ROOT / "Projects"
COMPUTER_USE_DIR = PROJECTS_DIR / "ComputerUse"
VISION_REPORTS_DIR = COMPUTER_USE_DIR / "observe_vision_reports"
LATEST_OBSERVATION_FILE = VISION_REPORTS_DIR / "latest_observation.json"
LATEST_REPORT_FILE = VISION_REPORTS_DIR / "latest_observation.md"


def _now() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    VISION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (VISION_REPORTS_DIR / "snapshots").mkdir(parents=True, exist_ok=True)


def _safe_json_read(path: Path) -> Tuple[bool, Any, str]:
    try:
        if not path.exists():
            return False, None, "missing"
        return True, json.loads(path.read_text(encoding="utf-8")), "ok"
    except Exception as exc:
        return False, None, str(exc)


def _safe_json_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _candidate_ui_map_paths() -> List[Path]:
    return [
        COMPUTER_USE_DIR / "latest_ui_map.json",
        COMPUTER_USE_DIR / "ui_maps" / "latest_ui_map.json",
        COMPUTER_USE_DIR / "runtime" / "latest_ui_map.json",
        PROJECTS_DIR / "Reports" / "computer_use" / "latest_ui_map.json",
    ]


def _load_latest_ui_map() -> Dict[str, Any]:
    for path in _candidate_ui_map_paths():
        ok, data, message = _safe_json_read(path)
        if ok and isinstance(data, dict):
            data.setdefault("_source", str(path))
            return data
    return {
        "_source": "none",
        "ok": False,
        "elements": [],
        "windows": [],
        "message": "latest UI map was not found; observe/vision will use desktop observer if available and synthetic-safe fallback otherwise",
    }


def _flatten_elements(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        result: List[Dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, list):
                result.extend(_flatten_elements(item))
        return result
    if isinstance(value, dict):
        for key in ("elements", "items", "nodes", "controls", "children"):
            if key in value:
                return _flatten_elements(value.get(key))
    return []


def _normalize_text(value: Any) -> str:
    return str(value or "").replace("\n", " ").replace("\r", " ").strip()


def _element_label(element: Dict[str, Any]) -> str:
    for key in ("label", "text", "name", "title", "automation_id", "id", "value", "placeholder"):
        text = _normalize_text(element.get(key))
        if text:
            return text
    return ""


def _element_role(element: Dict[str, Any]) -> str:
    for key in ("role", "type", "control_type", "class_name", "kind"):
        text = _normalize_text(element.get(key))
        if text:
            return text.lower()
    return ""


def _rect_value(element: Dict[str, Any]) -> Dict[str, Any]:
    rect = element.get("rect") or element.get("bbox") or element.get("bounds") or element.get("box") or {}
    if isinstance(rect, dict):
        return dict(rect)
    if isinstance(rect, (list, tuple)) and len(rect) >= 4:
        return {"x": rect[0], "y": rect[1], "width": rect[2], "height": rect[3]}
    return {}


def _ui_map_quality(ui_map: Dict[str, Any]) -> Dict[str, Any]:
    elements = _flatten_elements(ui_map)
    labels = [_element_label(item) for item in elements]
    roles = [_element_role(item) for item in elements]
    clickable = 0
    inputs = 0
    visible = 0
    for item, role in zip(elements, roles):
        label = _element_label(item).lower()
        if item.get("visible", True) is not False:
            visible += 1
        if any(word in role for word in ("button", "menu", "link", "tab", "item")) or bool(item.get("clickable")):
            clickable += 1
        if any(word in role for word in ("edit", "input", "text", "search", "combobox")) or "поиск" in label or "search" in label:
            inputs += 1
    return {
        "source": ui_map.get("_source", "unknown"),
        "element_count": len(elements),
        "visible_count": visible,
        "label_count": len([label for label in labels if label]),
        "clickable_count": clickable,
        "input_count": inputs,
        "has_elements": bool(elements),
    }


def _desktop_observe_snapshot() -> Dict[str, Any]:
    try:
        from modules.desktop_observer import observe_desktop

        observed = observe_desktop(write_report=True)
        if isinstance(observed, dict):
            return {
                "ok": bool(observed.get("ok", True)),
                "source": "desktop_observer",
                "payload": observed,
            }
        return {
            "ok": True,
            "source": "desktop_observer",
            "payload": {"text": str(observed)},
        }
    except Exception as exc:
        return {
            "ok": False,
            "source": "desktop_observer_unavailable",
            "error": str(exc),
        }


def _active_window_from_snapshot(snapshot: Dict[str, Any], ui_map: Dict[str, Any]) -> Dict[str, Any]:
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
    for key in ("active_window", "window", "foreground_window", "focused_window"):
        value = payload.get(key)
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str) and value.strip():
            return {"title": value.strip()}
    windows = ui_map.get("windows")
    if isinstance(windows, list) and windows:
        first = windows[0]
        if isinstance(first, dict):
            return dict(first)
        return {"title": str(first)}
    return {"title": "unknown", "app": "unknown"}


def _fingerprint_observation(ui_quality: Dict[str, Any], active_window: Dict[str, Any]) -> str:
    payload = {
        "active_window": active_window,
        "quality": {
            "element_count": ui_quality.get("element_count"),
            "label_count": ui_quality.get("label_count"),
            "clickable_count": ui_quality.get("clickable_count"),
            "input_count": ui_quality.get("input_count"),
            "source": ui_quality.get("source"),
        },
    }
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    import hashlib

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _load_previous_observation() -> Dict[str, Any]:
    ok, data, message = _safe_json_read(LATEST_OBSERVATION_FILE)
    if ok and isinstance(data, dict):
        return data
    return {}


def _stuck_status(current_fingerprint: str, previous: Dict[str, Any]) -> Dict[str, Any]:
    previous_fingerprint = str(previous.get("fingerprint") or "")
    repeat_count = 0
    if previous_fingerprint and previous_fingerprint == current_fingerprint:
        repeat_count = int(previous.get("repeat_count", 0) or 0) + 1
    return {
        "fingerprint": current_fingerprint,
        "previous_fingerprint": previous_fingerprint,
        "repeat_count": repeat_count,
        "possibly_stuck": repeat_count >= 2,
    }


def _score_candidate(goal: str, element: Dict[str, Any]) -> Dict[str, Any]:
    label = _element_label(element)
    role = _element_role(element)
    text = f"{label} {role}".lower()
    goal_lower = goal.lower()
    tokens = [token for token in re_split_words(goal_lower) if len(token) >= 3]
    matches = [token for token in tokens if token in text]
    exact = bool(label and label.lower() in goal_lower)
    role_bonus = 0.0
    if any(word in goal_lower for word in ("нажми", "click", "клик", "открой")) and any(word in role for word in ("button", "link", "menu", "tab")):
        role_bonus += 0.18
    if any(word in goal_lower for word in ("введи", "напиши", "type", "search", "поиск")) and any(word in role for word in ("edit", "input", "text", "search")):
        role_bonus += 0.18
    score = min(0.99, (0.18 * len(matches)) + (0.28 if exact else 0.0) + role_bonus)
    return {
        "label": label,
        "role": role,
        "rect": _rect_value(element),
        "score": round(score, 3),
        "matched_tokens": matches,
        "exact_label_in_goal": exact,
    }


def re_split_words(text: str) -> List[str]:
    result: List[str] = []
    current: List[str] = []
    for char in text:
        if char.isalnum() or char in "_-":
            current.append(char)
        elif current:
            result.append("".join(current))
            current = []
    if current:
        result.append("".join(current))
    return result


def find_target_candidates(goal: str, ui_map: Optional[Dict[str, Any]] = None, limit: int = 8) -> List[Dict[str, Any]]:
    ui_map = ui_map if isinstance(ui_map, dict) else _load_latest_ui_map()
    scored: List[Dict[str, Any]] = []
    for element in _flatten_elements(ui_map):
        candidate = _score_candidate(str(goal or ""), element)
        if candidate["score"] > 0 or candidate["label"]:
            scored.append(candidate)
    scored.sort(key=lambda item: (item.get("score", 0), bool(item.get("rect"))), reverse=True)
    return scored[:limit]


def _write_markdown_report(payload: Dict[str, Any], path: Path) -> None:
    lines = [
        f"# {FEATURE_NAME}",
        "",
        f"- version: {VERSION}",
        f"- timestamp: {payload.get('timestamp')}",
        f"- ok: {payload.get('ok')}",
        f"- mode: {payload.get('mode')}",
        "",
        "## Active Window",
        "```json",
        json.dumps(payload.get("active_window", {}), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## UI Map Quality",
        "```json",
        json.dumps(payload.get("ui_map_quality", {}), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Stuck Detection",
        "```json",
        json.dumps(payload.get("stuck", {}), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
    ]
    if payload.get("goal"):
        lines.extend([
            "## Goal Candidates",
            "```json",
            json.dumps(payload.get("target_candidates", []), ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
        ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def observe_screen_vision(goal: str = "", write_report: bool = True, simulate: bool = False) -> Dict[str, Any]:
    _ensure_dirs()
    if simulate:
        ui_map = {
            "_source": "synthetic_self_check",
            "elements": [
                {"label": "Сохранить", "role": "button", "rect": {"x": 100, "y": 80, "width": 90, "height": 24}},
                {"label": "Поиск", "role": "edit", "rect": {"x": 200, "y": 80, "width": 180, "height": 24}},
                {"label": "Отмена", "role": "button", "rect": {"x": 390, "y": 80, "width": 80, "height": 24}},
            ],
            "windows": [{"title": "Synthetic LocalComet", "app": "LocalComet"}],
        }
        desktop_snapshot = {"ok": True, "source": "synthetic", "payload": {"active_window": {"title": "Synthetic LocalComet", "app": "LocalComet"}}}
    else:
        ui_map = _load_latest_ui_map()
        desktop_snapshot = _desktop_observe_snapshot()
    ui_quality = _ui_map_quality(ui_map)
    active_window = _active_window_from_snapshot(desktop_snapshot, ui_map)
    fingerprint = _fingerprint_observation(ui_quality, active_window)
    previous = _load_previous_observation()
    stuck = _stuck_status(fingerprint, previous)
    candidates = find_target_candidates(goal, ui_map) if goal else []
    payload: Dict[str, Any] = {
        "ok": True,
        "handled": True,
        "mode": "computer_use_observe_vision",
        "version": VERSION,
        "feature": FEATURE_NAME,
        "timestamp": _iso_now(),
        "goal": goal,
        "desktop_snapshot": desktop_snapshot,
        "active_window": active_window,
        "ui_map_quality": ui_quality,
        "target_candidates": candidates,
        "fingerprint": fingerprint,
        "repeat_count": stuck.get("repeat_count", 0),
        "stuck": stuck,
        "next_decision": "continue" if not stuck.get("possibly_stuck") else "replan_or_ask_user",
        "report": "",
    }
    if write_report:
        stamp = _now()
        json_report = VISION_REPORTS_DIR / f"observe_vision_{stamp}.json"
        md_report = VISION_REPORTS_DIR / f"observe_vision_{stamp}.md"
        payload["report"] = str(md_report)
        _safe_json_write(json_report, payload)
        _safe_json_write(LATEST_OBSERVATION_FILE, payload)
        _write_markdown_report(payload, md_report)
        LATEST_REPORT_FILE.write_text(md_report.read_text(encoding="utf-8"), encoding="utf-8")
    return payload


def get_latest_observation() -> Dict[str, Any]:
    _ensure_dirs()
    ok, data, message = _safe_json_read(LATEST_OBSERVATION_FILE)
    if ok and isinstance(data, dict):
        data["handled"] = True
        return data
    return {
        "ok": False,
        "handled": True,
        "mode": "computer_use_observe_vision_latest",
        "version": VERSION,
        "error": message,
        "report": str(LATEST_REPORT_FILE),
    }


def get_status() -> Dict[str, Any]:
    latest = get_latest_observation()
    return {
        "ok": True,
        "handled": True,
        "mode": "computer_use_observe_vision_status",
        "version": VERSION,
        "feature": FEATURE_NAME,
        "reports_dir": str(VISION_REPORTS_DIR),
        "latest_exists": bool(LATEST_OBSERVATION_FILE.exists()),
        "latest_ok": bool(latest.get("ok")),
        "latest_timestamp": latest.get("timestamp"),
        "latest_stuck": latest.get("stuck", {}),
    }


def get_capabilities() -> Dict[str, Any]:
    return {
        "ok": True,
        "handled": True,
        "mode": "computer_use_observe_vision_capabilities",
        "version": VERSION,
        "commands": [
            "pc computer vision status",
            "pc computer vision observe",
            "pc computer vision observe <goal>",
            "pc computer vision latest",
            "pc computer vision report",
            "наблюдай экран",
            "осмотр экрана",
            "статус зрения",
        ],
        "outputs": [
            "active_window",
            "ui_map_quality",
            "target_candidates",
            "fingerprint",
            "stuck detection",
            "markdown/json reports",
        ],
    }


def _is_command(command: str) -> bool:
    lower = str(command or "").lower().replace("ё", "е").strip()
    if lower in {
        "pc computer vision",
        "pc computer vision status",
        "pc computer observe vision",
        "pc computer vision observe",
        "pc computer vision latest",
        "pc computer vision report",
        "статус зрения",
        "наблюдай экран",
        "осмотр экрана",
        "последний осмотр экрана",
        "отчет зрения",
        "возможности зрения",
    }:
        return True
    prefixes = (
        "pc computer vision observe ",
        "pc computer observe vision ",
        "наблюдай экран ",
        "осмотр экрана ",
    )
    return lower.startswith(prefixes)


def handle_dispatch_command(command: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е").strip()
    if not _is_command(text):
        return {"handled": False}
    if lower in {"pc computer vision", "возможности зрения"}:
        return get_capabilities()
    if lower in {"pc computer vision status", "статус зрения"}:
        return get_status()
    if lower in {"pc computer vision latest", "последний осмотр экрана"}:
        return get_latest_observation()
    if lower in {"pc computer vision report", "отчет зрения"}:
        latest = get_latest_observation()
        return {
            "ok": bool(latest.get("ok")),
            "handled": True,
            "mode": "computer_use_observe_vision_report",
            "version": VERSION,
            "report": latest.get("report") or str(LATEST_REPORT_FILE),
            "latest": latest,
        }
    goal = ""
    for prefix in ("pc computer vision observe", "pc computer observe vision", "наблюдай экран", "осмотр экрана"):
        prefix_norm = prefix.lower().replace("ё", "е")
        if lower.startswith(prefix_norm):
            goal = text[len(prefix):].strip(" :,-—")
            break
    return observe_screen_vision(goal=goal, write_report=True, simulate=False)


def run_self_check(write_report: bool = True) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details})

    try:
        observed = observe_screen_vision(goal="нажми Сохранить", write_report=write_report, simulate=True)
        add("synthetic observe ok", bool(observed.get("ok")), observed.get("mode"))
        quality = observed.get("ui_map_quality", {})
        add("synthetic ui map has elements", int(quality.get("element_count", 0) or 0) >= 3, quality)
        candidates = observed.get("target_candidates", [])
        add("target candidates produced", bool(candidates), candidates[:2])
        add("best candidate references save", bool(candidates and "сохран" in str(candidates[0].get("label", "")).lower()), candidates[:2])
        latest = get_latest_observation()
        add("latest observation readable", bool(latest.get("ok")), latest.get("mode"))
        status = get_status()
        add("status ok", bool(status.get("ok")), status)
        capabilities = get_capabilities()
        add("capabilities ok", bool(capabilities.get("ok") and capabilities.get("commands")), capabilities.get("commands"))
        no_public_dispatch = "dispatch" not in globals()
        add("no public dispatch export", no_public_dispatch, sorted([key for key in globals() if key == "dispatch"]))
    except Exception as exc:
        add("self check exception", False, traceback.format_exc())

    failed = len([item for item in checks if not item.get("ok")])
    result = {
        "ok": failed == 0,
        "handled": True,
        "mode": "computer_use_observe_vision_self_check",
        "version": VERSION,
        "summary": {"passed": len(checks) - failed, "total": len(checks), "failed": failed},
        "checks": checks,
        "report": "",
    }
    if write_report:
        _ensure_dirs()
        report = VISION_REPORTS_DIR / f"observe_vision_self_check_{_now()}.json"
        _safe_json_write(report, result)
        result["report"] = str(report)
    return result
````

### ПУТЬ: modules/computer_use_real_actions_ru.py (800 строк, 30158 байт)

````python
from __future__ import annotations

import json
import os
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REAL_ACTIONS_VERSION = "v6.53"
REAL_ACTIONS_NAME = "Computer Use Real Actions Upgrade RU"

try:
    from modules.project_paths import get_project_root
    ROOT_DIR = get_project_root()
except Exception:
    ROOT_DIR = Path(__file__).resolve().parents[1]
    if not ROOT_DIR.exists():
        ROOT_DIR = Path(__file__).resolve().parents[1]

PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "computer_use_real_actions"
COMPUTER_USE_DIR = PROJECTS_DIR / "ComputerUse"


ALLOWED_APPS = {
    "notepad": {"command": "notepad.exe", "aliases": ["notepad", "блокнот", "заметки", "note", "notes"]},
    "calc": {"command": "calc.exe", "aliases": ["calc", "calculator", "калькулятор"]},
    "mspaint": {"command": "mspaint.exe", "aliases": ["paint", "mspaint", "рисование", "пейнт"]},
    "explorer": {"command": "explorer.exe", "aliases": ["explorer", "проводник", "файлы"]},
}

FOLDER_ALIASES = {
    "project": ["проект", "localagent", "workspace", "рабочая папка"],
    "projects": ["projects", "проекты"],
    "reports": ["reports", "отчеты", "отчёты"],
    "relay": ["relay", "chatgptrelay", "response"],
    "downloads": ["downloads", "загрузки"],
}

KEY_ALIASES = {
    "enter": "enter",
    "энтэр": "enter",
    "ввод": "enter",
    "tab": "tab",
    "таб": "tab",
    "escape": "esc",
    "esc": "esc",
    "backspace": "backspace",
    "space": "space",
    "пробел": "space",
    "delete": "delete",
    "del": "delete",
    "home": "home",
    "end": "end",
}

VK = {
    "ctrl": 0x11,
    "control": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "tab": 0x09,
    "enter": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "a": 0x41,
    "c": 0x43,
    "s": 0x53,
    "v": 0x56,
    "x": 0x58,
    "z": 0x5A,
    "y": 0x59,
    "n": 0x4E,
    "o": 0x4F,
    "p": 0x50,
    "f": 0x46,
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(value: Any) -> str:
    return str(value or "").lower().replace("ё", "е").strip()


def _safe_preview(value: Any, limit: int = 700) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[trimmed]"


def _ensure_dirs() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text), encoding="utf-8")
    return str(path)


def _contains_secret_text(text: str) -> bool:
    lowered = _norm(text)
    secret_markers = [
        "password",
        "passwd",
        "api key",
        "api-key",
        "apikey",
        "private key",
        "ssh key",
        "token",
        "secret",
        "cookie",
        "cookies",
        "browser profile",
        "seed phrase",
        "парол",
        "токен",
        "секрет",
        "приватный ключ",
        "куки",
        "профиль браузера",
    ]
    return any(marker in lowered for marker in secret_markers)


def _blocked_goal(goal: str) -> Tuple[bool, str]:
    lowered = _norm(goal)
    blocks = [
        ("destructive_delete", r"\b(rm\s+-rf|rmdir|del\s+|format|wipe|erase)\b|удали|удалить|сотри|стереть"),
        ("terminal_admin", r"\b(powershell|cmd\.exe|cmd|bash|zsh|sudo|terminal|administrator|admin)\b|терминал|командн|админ"),
        ("secrets", r"\b(password|passwd|token|api\s*key|api-key|private\s*key|ssh\s*key|cookie|cookies|browser\s*profile)\b|парол|токен|секрет|куки|профил"),
        ("payment", r"\b(bank|payment|credit\s*card|paypal|wallet|casino|gambling|betting)\b|банк|платеж|платеж|карта|казино|ставк"),
    ]
    for reason, pattern in blocks:
        if re.search(pattern, lowered):
            return True, reason
    return False, ""


def _resolve_app(goal: str) -> str:
    lowered = _norm(goal)
    if not any(marker in lowered for marker in ["открой", "запусти", "open", "launch", "start"]):
        return ""
    for app_id, info in ALLOWED_APPS.items():
        aliases = info.get("aliases", [])
        if any(alias in lowered for alias in aliases):
            return app_id
    return ""


def _resolve_folder(goal: str) -> str:
    lowered = _norm(goal)
    if not any(marker in lowered for marker in ["открой", "покажи", "open", "folder", "папк"]):
        return ""
    for folder_id, aliases in FOLDER_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return folder_id
    return ""


def resolve_folder_path(folder_id: str) -> Path:
    folder = _norm(folder_id)
    if folder == "project":
        return ROOT_DIR
    if folder == "projects":
        return PROJECTS_DIR
    if folder == "reports":
        return PROJECTS_DIR / "Reports"
    if folder == "relay":
        return PROJECTS_DIR / "ChatGPTRelay"
    if folder == "downloads":
        return Path.home() / "Downloads"
    return ROOT_DIR


def _strip_quotes(text: str) -> str:
    cleaned = str(text or "").strip()
    pairs = [('"', '"'), ("'", "'"), ("«", "»"), ("“", "”"), ("`", "`")]
    changed = True
    while changed and len(cleaned) >= 2:
        changed = False
        for left, right in pairs:
            if cleaned.startswith(left) and cleaned.endswith(right):
                cleaned = cleaned[len(left):-len(right)].strip()
                changed = True
                break
    return cleaned


def _extract_text_payload(goal: str) -> str:
    raw = str(goal or "").strip()
    if "::" in raw:
        return _strip_quotes(raw.split("::", 1)[1].strip())
    lowered = _norm(raw)
    markers = [
        "напиши ",
        "введи ",
        "напечатай ",
        "набери ",
        "type ",
        "write ",
        "print ",
        "paste ",
        "вставь ",
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
    payload = raw[best_index + len(best_marker):].strip()
    lowered_payload = _norm(payload)
    cut_markers = [
        " после этого ",
        " затем ",
        " потом ",
        " и нажми ",
        " and press ",
        " and hit ",
    ]
    for marker in cut_markers:
        pos = lowered_payload.find(marker.strip())
        if pos > 0:
            payload = payload[:pos].strip()
            break
    return _strip_quotes(payload)


def _extract_type_target(goal: str) -> str:
    lowered = _norm(goal)
    explicit_patterns = [
        r"(?:в поле|ввод в|введи в|напиши в)\s+([a-zа-я0-9 _.\-]{2,80})",
        r"(?:поле|input|field)\s+([a-zа-я0-9 _.\-]{2,80})",
    ]
    stop_words = [
        " напиши ",
        " введи ",
        " напечатай ",
        " набери ",
        " type ",
        " write ",
        " paste ",
        " вставь ",
        " ::",
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, lowered)
        if match:
            target = match.group(1).strip(" :,-—")
            for marker in stop_words:
                pos = target.find(marker.strip())
                if pos > 0:
                    target = target[:pos].strip(" :,-—")
            if target:
                if "поиск" in target or "search" in target:
                    return "Поиск"
                if "чат" in target or "chat" in target:
                    return "чат"
                return target
    if "поиск" in lowered or "search" in lowered:
        return "Поиск"
    if "чат" in lowered or "chat" in lowered:
        return "чат"
    return "active_window"


def _extract_click_target(goal: str) -> str:
    raw = str(goal or "").strip()
    lowered = _norm(raw)
    markers = [
        "кликни по ",
        "нажми на ",
        "нажми кнопку ",
        "кнопку ",
        "click ",
        "press button ",
        "button ",
    ]
    for marker in markers:
        index = lowered.find(marker)
        if index >= 0:
            target = raw[index + len(marker):].strip(" :,-—")
            for cut in [" затем ", " потом ", " после этого ", " and "]:
                cut_pos = _norm(target).find(cut.strip())
                if cut_pos > 0:
                    target = target[:cut_pos].strip()
            return _strip_quotes(target)
    return ""


def _extract_key(goal: str) -> str:
    lowered = _norm(goal)
    for alias, key in KEY_ALIASES.items():
        if ("нажми " + alias) in lowered or ("press " + alias) in lowered or lowered.endswith(alias):
            return key
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
        "ctrl+c": ["ctrl", "c"],
        "ctrl c": ["ctrl", "c"],
        "alt+tab": ["alt", "tab"],
        "alt tab": ["alt", "tab"],
        "shift+tab": ["shift", "tab"],
        "shift tab": ["shift", "tab"],
    }
    for marker, keys in known.items():
        if marker in lowered:
            return keys
    return []


def _scroll_direction(goal: str) -> int:
    lowered = _norm(goal)
    if "прокрути вниз" in lowered or "scroll down" in lowered:
        return -1
    if "прокрути вверх" in lowered or "scroll up" in lowered:
        return 1
    return 0


def build_real_action_plan(goal: str, max_steps: int = 16) -> Dict[str, Any]:
    goal = str(goal or "").strip()
    blocked, reason = _blocked_goal(goal)
    if blocked:
        return {
            "ok": False,
            "mode": "computer_use_real_action_plan",
            "version": REAL_ACTIONS_VERSION,
            "blocked": True,
            "reason": reason,
            "actions": [],
        }

    actions: List[Dict[str, Any]] = []
    lowered = _norm(goal)

    app_id = _resolve_app(goal)
    if app_id:
        actions.append({
            "kind": "open_app",
            "target": app_id,
            "confidence": 0.96,
            "reason": "allowlisted app resolved from user goal",
            "real_action": True,
        })
        actions.append({
            "kind": "wait_for_window",
            "target": app_id,
            "seconds": 0.8,
            "confidence": 0.88,
            "reason": "wait for launched app to become ready",
            "real_action": True,
        })

    folder_id = _resolve_folder(goal)
    if folder_id:
        actions.append({
            "kind": "open_folder",
            "target": folder_id,
            "confidence": 0.94,
            "reason": "allowlisted folder resolved from user goal",
            "real_action": True,
        })
        actions.append({
            "kind": "wait_for_window",
            "target": folder_id,
            "seconds": 0.5,
            "confidence": 0.84,
            "reason": "wait for folder window",
            "real_action": True,
        })

    click_target = _extract_click_target(goal)
    double_click = any(marker in lowered for marker in ["двойной клик", "double click", "double-click"])
    if click_target:
        actions.append({
            "kind": "double_click_element" if double_click else "click_element",
            "target": click_target,
            "confidence": 0.82,
            "reason": "click target extracted and delegated to grounded click planner",
            "real_action": True,
        })

    text_payload = _extract_text_payload(goal)
    if text_payload:
        target = _extract_type_target(goal)
        if target and target != "active_window":
            actions.append({
                "kind": "type_element",
                "target": target,
                "text": text_payload,
                "confidence": 0.86,
                "reason": "typed payload with target field detected",
                "real_action": True,
            })
        else:
            actions.append({
                "kind": "paste_text",
                "target": "active_window",
                "text": text_payload,
                "confidence": 0.88 if app_id else 0.74,
                "reason": "typed payload extracted for active window paste",
                "real_action": True,
            })

    hotkey = _extract_hotkey(goal)
    if hotkey:
        actions.append({
            "kind": "hotkey",
            "target": "+".join(hotkey),
            "keys": hotkey,
            "confidence": 0.88,
            "reason": "known hotkey extracted from user goal",
            "real_action": True,
        })

    key = _extract_key(goal)
    if key and not hotkey:
        actions.append({
            "kind": "press_key",
            "target": key,
            "key": key,
            "confidence": 0.86,
            "reason": "single key press extracted from user goal",
            "real_action": True,
        })

    scroll = _scroll_direction(goal)
    if scroll:
        actions.append({
            "kind": "scroll",
            "target": "active_window",
            "direction": "up" if scroll > 0 else "down",
            "clicks": 4,
            "confidence": 0.84,
            "reason": "scroll command extracted from user goal",
            "real_action": True,
        })

    if not actions:
        actions.append({
            "kind": "delegate_multistep",
            "target": "screen",
            "goal": goal,
            "confidence": 0.72,
            "reason": "fallback to existing grounded multistep loop",
            "real_action": False,
        })

    for index, action in enumerate(actions[:max_steps], start=1):
        action["index"] = index

    return {
        "ok": True,
        "mode": "computer_use_real_action_plan",
        "version": REAL_ACTIONS_VERSION,
        "goal": goal,
        "actions": actions[:max_steps],
        "summary": {
            "total": len(actions[:max_steps]),
            "real_actions": sum(1 for item in actions[:max_steps] if item.get("real_action")),
            "fallback_actions": sum(1 for item in actions[:max_steps] if not item.get("real_action")),
        },
    }


def _vk_code(key: str) -> Optional[int]:
    lowered = _norm(key)
    if lowered in VK:
        return VK[lowered]
    if len(lowered) == 1 and "a" <= lowered <= "z":
        return ord(lowered.upper())
    return None


def press_hotkey(keys: List[str], simulate: bool = False) -> Dict[str, Any]:
    normalized = [_norm(key) for key in keys if _norm(key)]
    if not normalized:
        return {"ok": False, "status": "error", "reason": "empty hotkey"}
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_hotkey", "keys": normalized}
    if os.name != "nt":
        return {"ok": False, "status": "unsupported", "reason": "real hotkey supports Windows in this build", "keys": normalized}
    try:
        import ctypes
        user32 = ctypes.windll.user32
        key_up = 0x0002
        codes = []
        for key in normalized:
            code = _vk_code(key)
            if code is None:
                return {"ok": False, "status": "error", "reason": "unsupported key: " + key, "keys": normalized}
            codes.append(code)
        for code in codes:
            user32.keybd_event(code, 0, 0, 0)
            time.sleep(0.025)
        for code in reversed(codes):
            user32.keybd_event(code, 0, key_up, 0)
            time.sleep(0.025)
        return {"ok": True, "status": "executed", "mode": "computer_use_real_hotkey", "keys": normalized}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "keys": normalized}


def press_key(key: str, simulate: bool = False) -> Dict[str, Any]:
    normalized = _norm(key)
    if not normalized:
        return {"ok": False, "status": "error", "reason": "empty key"}
    return press_hotkey([normalized], simulate=simulate)


def set_clipboard_text(text: str) -> Dict[str, Any]:
    if _contains_secret_text(text):
        return {"ok": False, "status": "requires_confirmation", "requires_confirmation": True, "reason": "clipboard payload appears to contain secret markers"}
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return {"ok": True, "status": "clipboard_set", "text_preview": _safe_preview(text, 160)}
    except Exception as exc:
        return {"ok": False, "status": "clipboard_error", "reason": str(exc)}


def paste_text(text: str, simulate: bool = False) -> Dict[str, Any]:
    text = str(text or "")
    if _contains_secret_text(text):
        return {"ok": False, "status": "requires_confirmation", "requires_confirmation": True, "reason": "text appears to contain secret markers"}
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_paste_text", "text_preview": _safe_preview(text, 300)}
    clip = set_clipboard_text(text)
    if not clip.get("ok"):
        return clip
    hotkey = press_hotkey(["ctrl", "v"], simulate=False)
    hotkey["clipboard"] = clip
    hotkey["mode"] = "computer_use_real_paste_text"
    return hotkey


def open_app(app_id: str, simulate: bool = False) -> Dict[str, Any]:
    app_id = _norm(app_id)
    if app_id not in ALLOWED_APPS:
        return {"ok": False, "status": "blocked", "reason": "app is not allowlisted", "app": app_id}
    command = str(ALLOWED_APPS[app_id].get("command") or "")
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_open_app", "app": app_id, "command": command}
    try:
        try:
            from modules.pc_agent_actions import open_app as pc_open_app
            result = pc_open_app(app_id, dry_run=False)
            if isinstance(result, dict) and result.get("ok"):
                result["mode"] = "computer_use_real_open_app"
                result["app"] = app_id
                return result
        except Exception:
            pass
        if hasattr(os, "startfile"):
            os.startfile(command)
            return {"ok": True, "status": "executed", "mode": "computer_use_real_open_app", "app": app_id, "command": command}
        return {"ok": False, "status": "unsupported", "reason": "app launch fallback requires Windows os.startfile", "app": app_id}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "app": app_id}


def open_folder(folder_id: str, simulate: bool = False) -> Dict[str, Any]:
    path = resolve_folder_path(folder_id)
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_open_folder", "folder": str(folder_id), "path": str(path)}
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(path))
            return {"ok": True, "status": "executed", "mode": "computer_use_real_open_folder", "folder": str(folder_id), "path": str(path)}
        return {"ok": False, "status": "unsupported", "reason": "folder open requires Windows os.startfile", "path": str(path)}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "path": str(path)}


def click_element(target: str, simulate: bool = False, double: bool = False) -> Dict[str, Any]:
    target = str(target or "").strip()
    if not target:
        return {"ok": False, "status": "error", "reason": "empty click target"}
    try:
        from modules.computer_use_click_planner_ru import click_element as guarded_click
        first = guarded_click(target, simulate=simulate)
        if not double:
            first["mode"] = "computer_use_real_click_element"
            return first
        if not first.get("ok") and not first.get("simulated"):
            first["mode"] = "computer_use_real_double_click_element"
            return first
        second = guarded_click(target, simulate=simulate)
        return {
            "ok": bool(first.get("ok")) and bool(second.get("ok")),
            "status": "simulated" if simulate else "executed",
            "mode": "computer_use_real_double_click_element",
            "target": target,
            "first": first,
            "second": second,
        }
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "target": target}


def type_element(target: str, text: str, simulate: bool = False) -> Dict[str, Any]:
    target = str(target or "").strip() or "active_window"
    if target == "active_window":
        return paste_text(text, simulate=simulate)
    try:
        from modules.computer_use_type_guard_ru import guarded_type
        result = guarded_type(target, str(text or ""), simulate=simulate)
        result["mode"] = "computer_use_real_type_element"
        return result
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "target": target, "text_preview": _safe_preview(text, 120)}


def scroll(direction: str = "down", clicks: int = 4, simulate: bool = False) -> Dict[str, Any]:
    direction = _norm(direction)
    clicks = max(1, min(int(clicks or 4), 15))
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_scroll", "direction": direction, "clicks": clicks}
    if os.name != "nt":
        return {"ok": False, "status": "unsupported", "reason": "real scroll supports Windows in this build"}
    try:
        import ctypes
        user32 = ctypes.windll.user32
        wheel_delta = 120 * clicks
        if direction == "down":
            wheel_delta = -wheel_delta
        user32.mouse_event(0x0800, 0, 0, wheel_delta, 0)
        return {"ok": True, "status": "executed", "mode": "computer_use_real_scroll", "direction": direction, "clicks": clicks}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "direction": direction}


def wait_for_window(seconds: float = 0.6, simulate: bool = False) -> Dict[str, Any]:
    seconds = max(0.0, min(float(seconds or 0.6), 5.0))
    if not simulate:
        time.sleep(seconds)
    return {"ok": True, "status": "simulated" if simulate else "executed", "mode": "computer_use_real_wait", "seconds": seconds}


def execute_real_action(action: Dict[str, Any], simulate: bool = False, mission_goal: str = "") -> Dict[str, Any]:
    kind = str(action.get("kind") or "").strip()
    try:
        if kind == "open_app":
            return open_app(str(action.get("target") or ""), simulate=simulate)
        if kind == "open_folder":
            return open_folder(str(action.get("target") or ""), simulate=simulate)
        if kind == "wait_for_window" or kind == "wait":
            return wait_for_window(float(action.get("seconds") or 0.6), simulate=simulate)
        if kind == "paste_text":
            return paste_text(str(action.get("text") or ""), simulate=simulate)
        if kind == "type_element":
            return type_element(str(action.get("target") or ""), str(action.get("text") or ""), simulate=simulate)
        if kind == "click_element":
            return click_element(str(action.get("target") or ""), simulate=simulate, double=False)
        if kind == "double_click_element":
            return click_element(str(action.get("target") or ""), simulate=simulate, double=True)
        if kind == "hotkey":
            return press_hotkey(list(action.get("keys") or []), simulate=simulate)
        if kind == "press_key":
            return press_key(str(action.get("key") or action.get("target") or ""), simulate=simulate)
        if kind == "scroll":
            return scroll(str(action.get("direction") or "down"), int(action.get("clicks") or 4), simulate=simulate)
        if kind == "delegate_multistep":
            from modules.computer_use_multistep_loop_ru import run_loop
            result = run_loop(str(action.get("goal") or mission_goal), simulate=simulate, max_steps=1, max_failures=1)
            result.setdefault("status", result.get("outcome") or "returned")
            return result
        return {"ok": False, "status": "error", "reason": "unknown real action kind: " + kind}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "traceback": traceback.format_exc(), "action": action}


def get_real_action_capabilities() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "computer_use_real_action_capabilities",
        "version": REAL_ACTIONS_VERSION,
        "actions": [
            "open_app",
            "open_folder",
            "click_element",
            "double_click_element",
            "type_element",
            "paste_text",
            "hotkey",
            "press_key",
            "scroll",
            "wait_for_window",
            "delegate_multistep",
        ],
        "app_allowlist": sorted(ALLOWED_APPS.keys()),
        "folder_allowlist": sorted(FOLDER_ALIASES.keys()),
        "notes": [
            "Real GUI actions are functionality-first for normal GUI tasks.",
            "Hard gates still block destructive, terminal/admin, secret, payment, and browser-profile flows.",
        ],
    }


def run_self_check(write_report: bool = True) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details if details is not None else {}})

    blocked, reason = _blocked_goal("удали все файлы через powershell")
    add("hard gate blocks destructive terminal goal", blocked and reason in {"destructive_delete", "terminal_admin"}, {"blocked": blocked, "reason": reason})

    plan = build_real_action_plan("открой блокнот и напиши hello и нажми enter", max_steps=8)
    kinds = [item.get("kind") for item in plan.get("actions", [])]
    add("plan includes open app paste and key", plan.get("ok") and "open_app" in kinds and "paste_text" in kinds and "press_key" in kinds, {"kinds": kinds})

    click_plan = build_real_action_plan("кликни по Сохранить", max_steps=4)
    add("plan supports grounded click element", click_plan.get("ok") and any(item.get("kind") == "click_element" for item in click_plan.get("actions", [])), click_plan)

    type_plan = build_real_action_plan("в поле Поиск напиши hello", max_steps=4)
    add("plan supports targeted type element", type_plan.get("ok") and any(item.get("kind") == "type_element" for item in type_plan.get("actions", [])), type_plan)

    scroll_plan = build_real_action_plan("прокрути вниз", max_steps=4)
    add("plan supports scroll", scroll_plan.get("ok") and any(item.get("kind") == "scroll" for item in scroll_plan.get("actions", [])), scroll_plan)

    open_sim = execute_real_action({"kind": "open_app", "target": "notepad"}, simulate=True)
    add("simulate open app executes", open_sim.get("ok") and open_sim.get("status") == "simulated", open_sim)

    paste_sim = execute_real_action({"kind": "paste_text", "text": "hello"}, simulate=True)
    add("simulate paste executes", paste_sim.get("ok") and paste_sim.get("status") == "simulated", paste_sim)

    caps = get_real_action_capabilities()
    add("capabilities expose real actions", caps.get("ok") and "open_app" in caps.get("actions", []) and "scroll" in caps.get("actions", []), caps)

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    payload = {
        "ok": summary["failed"] == 0,
        "mode": "computer_use_real_actions_self_check",
        "version": REAL_ACTIONS_VERSION,
        "summary": summary,
        "checks": checks,
    }
    if write_report:
        _ensure_dirs()
        path = REPORTS_DIR / ("real_actions_self_check_" + _stamp() + ".json")
        _write_json(path, payload)
        payload["report"] = str(path)
    return payload


def format_result(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
````

### ПУТЬ: modules/computer_use_safety_ru.py (92 строк, 5344 байт)

````python

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
````

### ПУТЬ: modules/computer_use_schema_ru.py (169 строк, 5631 байт)

````python

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json
import uuid

SCHEMA_VERSION = "v6.47d"
ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
RUNS_DIR = COMPUTER_USE_DIR / "runs"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_dirs() -> None:
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def make_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()


def safe_json_load(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def safe_json_dump(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def run_dir(run_id: str) -> Path:
    ensure_dirs()
    return RUNS_DIR / run_id


def steps_dir(run_id: str) -> Path:
    return run_dir(run_id) / "steps"


def screenshots_dir(run_id: str) -> Path:
    return run_dir(run_id) / "screenshots"


def reports_dir(run_id: str) -> Path:
    return run_dir(run_id) / "reports"


def events_path(run_id: str) -> Path:
    return run_dir(run_id) / "events.jsonl"


def run_state_path(run_id: str) -> Path:
    return run_dir(run_id) / "run.json"


def latest_run_id() -> str:
    ensure_dirs()
    runs = sorted(path.parent.name for path in RUNS_DIR.glob("run_*/run.json"))
    return runs[-1] if runs else ""


def load_run(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    return safe_json_load(run_state_path(rid), {}) if rid else {}


def save_run(state: Dict[str, Any]) -> str:
    state["updated_at"] = now_iso()
    return safe_json_dump(run_state_path(state["run_id"]), state)


def default_plan(goal: str) -> List[str]:
    return [
        f"Понять цель: {(goal or '').strip()}",
        "Наблюдать экран.",
        "Построить UI map.",
        "Предложить одно следующее действие.",
        "Проверить безопасность.",
        "Остановиться на подтверждении, если действие рискованное.",
        "После выполнения снова наблюдать экран.",
        "Записать replay/report.",
    ]


def make_action(run_id: str, step: int, kind: str, reason: str, risk: str = "low", allowed_to_execute: bool = False, requires_confirmation: bool = True, target: Dict[str, Any] | None = None, text: str = "") -> Dict[str, Any]:
    return {
        "action_id": f"act_{step:03d}_{uuid.uuid4().hex[:6]}",
        "run_id": run_id,
        "step": step,
        "kind": (kind or "").strip().lower().replace("-", "_"),
        "target": target or {"element_id": "", "element_description": "", "window_title": "", "x": None, "y": None, "x_norm": None, "y_norm": None},
        "text": text,
        "reason": reason,
        "risk": risk,
        "requires_confirmation": requires_confirmation,
        "allowed_to_execute": allowed_to_execute,
        "created_at": now_iso(),
        "safety_notes": [],
    }


def compact_state(state: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "run_id", "goal", "phase", "status", "step", "max_steps", "pending_action_id",
        "pending_confirmation", "latest_observation_path", "latest_ui_map_path",
        "latest_decision_path", "latest_result_path", "latest_report_path", "next_safe_action",
    ]
    return {key: state.get(key, "") for key in keys}


def new_run_state(goal: str, max_steps: int = 8) -> Dict[str, Any]:
    run_id = make_id("run")
    return {
        "run_id": run_id,
        "goal": goal,
        "phase": "created",
        "status": "running",
        "step": 0,
        "max_steps": max(1, int(max_steps or 8)),
        "consecutive_failures": 0,
        "paused": False,
        "stopped": False,
        "pending_action_id": "",
        "pending_confirmation": False,
        "latest_observation_path": "",
        "latest_ui_map_path": "",
        "latest_decision_path": "",
        "latest_result_path": "",
        "latest_report_path": "",
        "next_safe_action": "pc computer step",
        "plan": default_plan(goal),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def status() -> Dict[str, Any]:
    ensure_dirs()
    return {"ok": True, "mode": "computer_use_schema_status", "version": SCHEMA_VERSION, "runs_dir": str(RUNS_DIR)}


def report() -> Dict[str, Any]:
    return {"ok": True, "mode": "computer_use_schema_report", "latest_run_id": latest_run_id(), "latest_run": compact_state(load_run()) if latest_run_id() else {}}


def is_computer_use_schema_command(command: str) -> bool:
    return (command or "").strip().lower() in {"pc computer schema", "computer schema"}


def dispatch(command: str) -> Dict[str, Any]:
    return report() if is_computer_use_schema_command(command) else {"ok": False, "mode": "computer_use_schema_unknown_command", "command": command}
````

### ПУТЬ: modules/computer_use_screen_diff_ru.py (57 строк, 1594 байт)

````python

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
````

### ПУТЬ: modules/computer_use_test_fixtures_ru.py (176 строк, 5992 байт)

````python

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator
import json
import uuid

from modules.project_paths import (
    PROJECT_PATHS_VERSION,
    computer_use_latest_ui_map_path,
    computer_use_test_fixtures_dir,
    ensure_dirs,
)


TEST_FIXTURES_VERSION = "v6.47i"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def canonical_ui_map() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "computer_use_contract_synthetic_ui_map",
        "version": TEST_FIXTURES_VERSION,
        "created_at": _now(),
        "source": "computer_use_test_fixtures_ru",
        "elements": [
            {
                "element_id": "btn_save",
                "role": "button",
                "text": "Сохранить",
                "bounds": {"x": 100, "y": 200, "w": 120, "h": 40},
                "confidence": 0.95,
                "source": "contract_fixture",
            },
            {
                "element_id": "field_search",
                "role": "textbox",
                "text": "Поиск",
                "bounds": {"x": 20, "y": 50, "w": 300, "h": 30},
                "confidence": 0.92,
                "source": "contract_fixture",
            },
            {
                "element_id": "field_chat",
                "role": "editor",
                "text": "Сообщение",
                "bounds": {"x": 40, "y": 310, "w": 520, "h": 90},
                "confidence": 0.88,
                "source": "contract_fixture",
            },
        ],
        "limitations": [],
    }


def write_fixture_file(name: str = "canonical_ui_map", payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    fixture_dir = computer_use_test_fixtures_dir()
    ensure_dirs([fixture_dir])
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name).strip("_") or "fixture"
    path = fixture_dir / f"{safe_name}.json"
    data = payload or canonical_ui_map()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "mode": "computer_use_write_fixture_file",
        "version": TEST_FIXTURES_VERSION,
        "path": str(path),
        "element_count": len(data.get("elements", [])),
    }


def _read_bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


@contextmanager
def temporary_latest_ui_map(payload: Dict[str, Any] | None = None, label: str = "contract") -> Iterator[Dict[str, Any]]:
    latest_path = computer_use_latest_ui_map_path()
    ensure_dirs([latest_path.parent, computer_use_test_fixtures_dir()])

    existed_before = latest_path.exists()
    original_bytes = _read_bytes(latest_path)
    data = payload or canonical_ui_map()
    data = dict(data)
    data["fixture_label"] = label
    data["fixture_started_at"] = _now()

    latest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    fixture_path = computer_use_test_fixtures_dir() / f"latest_ui_map_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    fixture_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    info = {
        "ok": True,
        "mode": "temporary_latest_ui_map",
        "version": TEST_FIXTURES_VERSION,
        "latest_path": str(latest_path),
        "fixture_path": str(fixture_path),
        "existed_before": existed_before,
        "element_count": len(data.get("elements", [])),
    }

    try:
        yield info
    finally:
        if existed_before and original_bytes is not None:
            latest_path.write_bytes(original_bytes)
        elif latest_path.exists():
            latest_path.unlink()


@contextmanager
def temporary_synthetic_ui_map(label: str = "contract") -> Iterator[Dict[str, Any]]:
    with temporary_latest_ui_map(canonical_ui_map(), label=label) as info:
        yield info


def verify_restore_behavior() -> Dict[str, Any]:
    latest_path = computer_use_latest_ui_map_path()
    existed_before = latest_path.exists()
    before_bytes = latest_path.read_bytes() if existed_before else None

    with temporary_synthetic_ui_map(label="restore_check") as info:
        during = json.loads(latest_path.read_text(encoding="utf-8"))
        if len(during.get("elements", [])) < 2:
            return {
                "ok": False,
                "mode": "computer_use_fixture_restore_check",
                "reason": "fixture was not written correctly",
                "info": info,
            }

    existed_after = latest_path.exists()
    after_bytes = latest_path.read_bytes() if existed_after else None

    restored = (existed_before == existed_after) and (before_bytes == after_bytes)
    return {
        "ok": restored,
        "mode": "computer_use_fixture_restore_check",
        "version": TEST_FIXTURES_VERSION,
        "existed_before": existed_before,
        "existed_after": existed_after,
        "restored": restored,
        "latest_path": str(latest_path),
    }


def status() -> Dict[str, Any]:
    fixture_dir = computer_use_test_fixtures_dir()
    latest_path = computer_use_latest_ui_map_path()
    return {
        "ok": True,
        "mode": "computer_use_test_fixtures_status",
        "version": TEST_FIXTURES_VERSION,
        "project_paths_version": PROJECT_PATHS_VERSION,
        "fixture_dir": str(fixture_dir),
        "latest_path": str(latest_path),
        "latest_exists": latest_path.exists(),
    }


def report() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "computer_use_test_fixtures_report",
        "status": status(),
        "restore_check": verify_restore_behavior(),
    }
````

### ПУТЬ: modules/computer_use_trace_ru.py (122 строк, 5304 байт)

````python

from __future__ import annotations

from typing import Any, Dict, List
import json

from modules.computer_use_schema_ru import events_path, latest_run_id, load_run, now_iso, reports_dir, run_dir, safe_json_dump, save_run, steps_dir

TRACE_VERSION = "v6.43"


def write_event(run_id: str, event_type: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_event_write", "error": "no run"}
    path = events_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"created_at": now_iso(), "run_id": rid, "event_type": event_type, "payload": payload or {}}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    state = load_run(rid)
    if state:
        state["events_count"] = int(state.get("events_count") or 0) + 1
        save_run(state)
    return {"ok": True, "mode": "computer_use_event_write", "event": event, "path": str(path)}


def save_step_artifact(run_id: str, step: int, artifact_type: str, payload: Dict[str, Any]) -> str:
    return safe_json_dump(steps_dir(run_id) / f"step_{step:03d}_{artifact_type}.json", payload)


def read_events(run_id: str = "", limit: int = 200) -> List[Dict[str, Any]]:
    rid = run_id or latest_run_id()
    if not rid:
        return []
    path = events_path(rid)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"event_type": "broken_event", "raw": line})
    return rows[-limit:]


def build_replay_summary(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_replay_summary", "error": "no runs"}
    return {"ok": True, "mode": "computer_use_replay_summary", "run_id": rid, "run_dir": str(run_dir(rid)), "events_path": str(events_path(rid)), "state": load_run(rid), "events": read_events(rid, 50)}


def write_run_report(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_report", "error": "no runs"}
    state = load_run(rid)
    path = reports_dir(rid) / "report.md"
    events = read_events(rid, 500)
    lines = [
        "# Computer Use Run Report",
        "",
        f"- generated_at: {now_iso()}",
        f"- run_id: {rid}",
        f"- goal: {state.get('goal', '')}",
        f"- phase: {state.get('phase', '')}",
        f"- status: {state.get('status', '')}",
        f"- step: {state.get('step', '')}",
        f"- pending_action_id: {state.get('pending_action_id', '')}",
        f"- pending_confirmation: {state.get('pending_confirmation', '')}",
        f"- latest_observation_path: {state.get('latest_observation_path', '')}",
        f"- latest_ui_map_path: {state.get('latest_ui_map_path', '')}",
        f"- latest_decision_path: {state.get('latest_decision_path', '')}",
        f"- latest_result_path: {state.get('latest_result_path', '')}",
        "",
        "## Events",
        "",
    ]
    for event in events:
        compact = json.dumps(event.get("payload") or {}, ensure_ascii=False)
        if len(compact) > 600:
            compact = compact[:600] + "..."
        lines.append(f"- {event.get('created_at', '')} `{event.get('event_type', '')}`")
        lines.append(f"  - payload: {compact}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    state["latest_report_path"] = str(path)
    save_run(state)
    return {"ok": True, "mode": "computer_use_report", "run_id": rid, "report": str(path), "state": state}


def latest_trace() -> Dict[str, Any]:
    rid = latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_latest_trace", "error": "no runs"}
    return {"ok": True, "mode": "computer_use_latest_trace", "run_id": rid, "state": load_run(rid), "events": read_events(rid, 30), "events_path": str(events_path(rid))}


def status() -> Dict[str, Any]:
    return {"ok": True, "mode": "computer_use_trace_status", "version": TRACE_VERSION, "latest_run_id": latest_run_id()}


def report() -> Dict[str, Any]:
    return latest_trace()


def is_computer_use_trace_command(command: str) -> bool:
    value = (command or "").strip().lower()
    return value in {"pc computer trace", "pc computer latest", "pc computer replay", "computer trace", "computer latest"}


def dispatch(command: str) -> Dict[str, Any]:
    value = (command or "").strip().lower()
    if value in {"pc computer trace", "computer trace", "pc computer latest", "computer latest"}:
        return latest_trace()
    if value.startswith("pc computer replay"):
        return build_replay_summary((command or "").strip().split()[-1] if len((command or "").strip().split()) >= 4 else "")
    if value in {"pc computer report", "отчёт computer use"}:
        return write_run_report()
    return {"ok": False, "mode": "computer_use_trace_unknown_command", "command": command}
````

### ПУТЬ: modules/computer_use_type_guard_ru.py (296 строк, 11481 байт)

````python

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
````

### ПУТЬ: modules/computer_use_visual_guard_ru.py (419 строк, 15830 байт)

````python

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import json
import re
import uuid

VISUAL_GUARD_VERSION = "v6.47d"
ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
VISUAL_GUARD_DIR = COMPUTER_USE_DIR / "visual_guard"
LATEST_UI_MAP_PATH = COMPUTER_USE_DIR / "latest_ui_map.json"

DIALOG_MARKERS = {
    "ok", "cancel", "yes", "no", "apply", "close", "retry", "abort", "ignore",
    "ок", "отмена", "да", "нет", "применить", "закрыть", "повторить", "ошибка",
    "error", "warning", "confirm", "confirmation", "dialog", "modal",
}

ERROR_MARKERS = {
    "error", "failed", "exception", "traceback", "warning", "denied", "blocked",
    "ошибка", "сбой", "не удалось", "исключение", "предупреждение", "запрещено", "заблокировано",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_GUARD_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
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


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-zа-яё0-9]+", str(text or "").lower(), flags=re.IGNORECASE)


def _extract_observation_summary(observation: Dict[str, Any]) -> Dict[str, Any]:
    data = observation or {}
    backend = data.get("backend") if isinstance(data.get("backend"), dict) else {}
    desktop_probe = backend.get("desktop_probe") if isinstance(backend.get("desktop_probe"), dict) else {}

    active_window = (
        data.get("active_window")
        or backend.get("active_window")
        or backend.get("window")
        or desktop_probe.get("active_window")
        or desktop_probe.get("window")
        or ""
    )
    screenshot_path = (
        data.get("screenshot_path")
        or backend.get("screenshot_path")
        or backend.get("path")
        or desktop_probe.get("screenshot_path")
        or desktop_probe.get("path")
        or ""
    )
    screenshot_hash = (
        data.get("screenshot_hash")
        or data.get("hash")
        or backend.get("screenshot_hash")
        or backend.get("hash")
        or desktop_probe.get("screenshot_hash")
        or desktop_probe.get("hash")
        or ""
    )
    screen_size = data.get("screen_size") or backend.get("screen_size") or desktop_probe.get("screen_size") or {}
    limitations = []
    for source in (data, backend, desktop_probe):
        value = source.get("limitations") if isinstance(source, dict) else None
        if isinstance(value, list):
            limitations.extend(str(item) for item in value)

    return {
        "active_window": str(active_window or ""),
        "screenshot_path": str(screenshot_path or ""),
        "screenshot_hash": str(screenshot_hash or ""),
        "screen_size": screen_size if isinstance(screen_size, dict) else {},
        "limitations": limitations,
    }


def _load_current_ui_map() -> Dict[str, Any]:
    if LATEST_UI_MAP_PATH.exists():
        payload = _read_json(LATEST_UI_MAP_PATH, {})
        elements = []
        if isinstance(payload, dict):
            raw = payload.get("elements") or payload.get("ui_elements") or []
            if isinstance(raw, list):
                elements = [item for item in raw if isinstance(item, dict)]
        return {
            "ok": True,
            "ui_map_path": str(LATEST_UI_MAP_PATH),
            "element_count": len(elements),
            "elements": elements,
            "payload": payload,
        }
    return {
        "ok": False,
        "ui_map_path": "",
        "element_count": 0,
        "elements": [],
        "payload": {},
    }


def _ui_map_element_count(ui_map: Dict[str, Any]) -> int:
    if not isinstance(ui_map, dict):
        return 0
    if isinstance(ui_map.get("elements"), list):
        return len([item for item in ui_map.get("elements", []) if isinstance(item, dict)])
    if isinstance(ui_map.get("ui_elements"), list):
        return len([item for item in ui_map.get("ui_elements", []) if isinstance(item, dict)])
    try:
        return int(ui_map.get("element_count") or 0)
    except Exception:
        return 0


def _preserve_previous_useful_ui_map(previous_ui_map: Dict[str, Any], new_ui_map: Dict[str, Any]) -> Dict[str, Any]:
    previous_count = _ui_map_element_count(previous_ui_map)
    new_count = _ui_map_element_count(new_ui_map)

    if previous_count > 0 and new_count == 0:
        preserved = dict(previous_ui_map)
        preserved["preserved_by_visual_guard"] = True
        preserved["preservation_reason"] = "build_ui_map returned zero elements; kept previous non-empty UI map for grounding stability"
        preserved["previous_element_count"] = previous_count
        preserved["discarded_empty_ui_map"] = new_ui_map
        try:
            LATEST_UI_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = preserved.get("payload") if isinstance(preserved.get("payload"), dict) else preserved
            if isinstance(payload, dict) and "elements" not in payload and isinstance(preserved.get("elements"), list):
                payload = dict(payload)
                payload["elements"] = preserved.get("elements", [])
            LATEST_UI_MAP_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return preserved

    return new_ui_map


def _element_text_blob(elements: List[Dict[str, Any]]) -> str:
    fields = ["text", "label", "name", "title", "role", "type", "value", "placeholder", "description"]
    parts: List[str] = []
    for element in elements[:250]:
        for field in fields:
            value = element.get(field)
            if value is not None:
                parts.append(str(value))
    return " ".join(parts).lower()


def classify_ui_markers(ui_map: Dict[str, Any]) -> Dict[str, Any]:
    elements = ui_map.get("elements") if isinstance(ui_map.get("elements"), list) else []
    blob = _element_text_blob(elements)
    tokens = set(_tokens(blob))
    dialog_hits = sorted((tokens & DIALOG_MARKERS) | {marker for marker in DIALOG_MARKERS if marker in blob})
    error_hits = sorted((tokens & ERROR_MARKERS) | {marker for marker in ERROR_MARKERS if marker in blob})
    return {
        "dialog_like": bool(dialog_hits),
        "error_like": bool(error_hits),
        "dialog_hits": dialog_hits[:20],
        "error_hits": error_hits[:20],
        "element_count": len(elements),
    }


def compare_observations(before: Dict[str, Any], after: Dict[str, Any], before_ui_map: Dict[str, Any] | None = None, after_ui_map: Dict[str, Any] | None = None) -> Dict[str, Any]:
    before_summary = _extract_observation_summary(before)
    after_summary = _extract_observation_summary(after)
    before_map = before_ui_map or {}
    after_map = after_ui_map or {}
    before_markers = classify_ui_markers(before_map)
    after_markers = classify_ui_markers(after_map)

    same_window = bool(before_summary["active_window"] and before_summary["active_window"] == after_summary["active_window"])
    window_changed = bool(before_summary["active_window"] and after_summary["active_window"] and before_summary["active_window"] != after_summary["active_window"])

    before_hash = before_summary.get("screenshot_hash", "")
    after_hash = after_summary.get("screenshot_hash", "")
    hash_changed = bool(before_hash and after_hash and before_hash != after_hash)
    hash_same = bool(before_hash and after_hash and before_hash == after_hash)

    before_count = int(before_map.get("element_count") or len(before_map.get("elements") or []) or 0)
    after_count = int(after_map.get("element_count") or len(after_map.get("elements") or []) or 0)
    element_delta = after_count - before_count
    element_delta_abs = abs(element_delta)

    changed_signals = 0
    if window_changed:
        changed_signals += 2
    if hash_changed:
        changed_signals += 2
    if element_delta_abs >= 3:
        changed_signals += 1
    if after_markers["dialog_like"] and not before_markers["dialog_like"]:
        changed_signals += 2
    if after_markers["error_like"] and not before_markers["error_like"]:
        changed_signals += 3

    stable_signals = 0
    if same_window:
        stable_signals += 1
    if hash_same:
        stable_signals += 1
    if element_delta_abs <= 2:
        stable_signals += 1

    if after_markers["error_like"]:
        decision = "stop"
        reason = "Error-like markers appeared after action."
    elif after_markers["dialog_like"] and not before_markers["dialog_like"]:
        decision = "ask_user"
        reason = "Dialog-like UI appeared after action."
    elif window_changed:
        decision = "replan"
        reason = "Active window changed after action."
    elif changed_signals >= 2:
        decision = "replan"
        reason = "Screen/UI changed enough to require replanning."
    elif stable_signals >= 2:
        decision = "continue"
        reason = "Screen appears stable after action."
    else:
        decision = "observe_again"
        reason = "Not enough evidence; observe once more."

    return {
        "ok": True,
        "mode": "computer_use_visual_compare",
        "version": VISUAL_GUARD_VERSION,
        "before": before_summary,
        "after": after_summary,
        "same_window": same_window,
        "window_changed": window_changed,
        "hash_changed": hash_changed,
        "hash_same": hash_same,
        "before_element_count": before_count,
        "after_element_count": after_count,
        "element_delta": element_delta,
        "changed_signals": changed_signals,
        "stable_signals": stable_signals,
        "before_markers": before_markers,
        "after_markers": after_markers,
        "decision": decision,
        "reason": reason,
    }


def observe_with_ui_map(label: str = "") -> Dict[str, Any]:
    observation = {}
    previous_ui_map = _load_current_ui_map()
    try:
        from modules.computer_use_core_ru import observe_screen, build_ui_map
        observation = observe_screen()
        fresh_ui_map = build_ui_map()
        ui_map = _preserve_previous_useful_ui_map(previous_ui_map, fresh_ui_map)
    except Exception as exc:
        observation = {
            "ok": False,
            "mode": "computer_use_visual_observe_error",
            "error": str(exc),
            "limitations": [str(exc)],
        }
        ui_map = previous_ui_map if _ui_map_element_count(previous_ui_map) > 0 else _load_current_ui_map()

    result = {
        "ok": True,
        "mode": "computer_use_visual_observe",
        "version": VISUAL_GUARD_VERSION,
        "label": label,
        "created_at": _now(),
        "observation": observation,
        "observation_summary": _extract_observation_summary(observation),
        "ui_map": ui_map,
        "ui_map_preserved": bool(isinstance(ui_map, dict) and ui_map.get("preserved_by_visual_guard")),
        "ui_markers": classify_ui_markers(ui_map),
    }
    _ensure_dirs()
    path = VISUAL_GUARD_DIR / f"visual_observe_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    result["artifact"] = _write_json(path, result)
    return result


def guarded_execute(action: Dict[str, Any], simulate: bool = False, before: Dict[str, Any] | None = None) -> Dict[str, Any]:
    before_snapshot = before or observe_with_ui_map("before_action")

    from modules.computer_use_auto_action_ru import execute_gui_action
    execution = execute_gui_action(action, simulate=simulate)

    after_snapshot = observe_with_ui_map("after_action")
    comparison = compare_observations(
        before_snapshot.get("observation", before_snapshot),
        after_snapshot.get("observation", after_snapshot),
        before_snapshot.get("ui_map", {}),
        after_snapshot.get("ui_map", {}),
    )

    result = {
        "ok": bool(execution.get("ok")),
        "mode": "computer_use_visual_guarded_execute",
        "version": VISUAL_GUARD_VERSION,
        "simulated": simulate,
        "action": action,
        "before": before_snapshot,
        "execution": execution,
        "after": after_snapshot,
        "comparison": comparison,
        "next_decision": comparison.get("decision"),
        "reason": comparison.get("reason"),
        "created_at": _now(),
    }
    _ensure_dirs()
    path = VISUAL_GUARD_DIR / f"visual_guarded_execute_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    result["artifact"] = _write_json(path, result)
    return result


def visual_guard_latest() -> Dict[str, Any]:
    _ensure_dirs()
    artifacts = sorted(VISUAL_GUARD_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not artifacts:
        return {
            "ok": False,
            "mode": "computer_use_visual_guard_latest",
            "error": "No visual guard artifacts yet.",
            "visual_guard_dir": str(VISUAL_GUARD_DIR),
        }
    payload = _read_json(artifacts[0], {})
    return {
        "ok": True,
        "mode": "computer_use_visual_guard_latest",
        "artifact": str(artifacts[0]),
        "payload": payload,
    }


def status() -> Dict[str, Any]:
    _ensure_dirs()
    return {
        "ok": True,
        "mode": "computer_use_visual_guard_status",
        "version": VISUAL_GUARD_VERSION,
        "visual_guard_dir": str(VISUAL_GUARD_DIR),
    }


def report() -> Dict[str, Any]:
    latest = visual_guard_latest()
    return {
        "ok": True,
        "mode": "computer_use_visual_guard_report",
        "version": VISUAL_GUARD_VERSION,
        "status": status(),
        "latest": latest,
    }


def is_computer_use_visual_guard_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = [
        "pc computer visual status",
        "pc computer visual observe",
        "pc computer visual latest",
        "pc computer visual compare",
        "pc computer visual guard",
        "визуальная проверка",
    ]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def dispatch(command: str) -> Dict[str, Any]:
    raw = (command or "").strip()
    value = raw.lower()

    if value == "pc computer visual status":
        return status()

    if value.startswith("pc computer visual observe"):
        label = raw[len("pc computer visual observe"):].strip() or "manual"
        return observe_with_ui_map(label)

    if value == "pc computer visual latest":
        return visual_guard_latest()

    if value == "pc computer visual compare":
        latest = visual_guard_latest()
        return latest

    if value.startswith("визуальная проверка"):
        return observe_with_ui_map("manual_ru")

    return {
        "ok": False,
        "mode": "computer_use_visual_guard_unknown_command",
        "command": command,
    }
````

### ПУТЬ: modules/confirmed_app_actions_ru.py (319 строк, 11595 байт)

````python
from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List

CONFIRMED_APP_ACTIONS_VERSION = "v6.72"

ROOT_DIR = get_project_root()
if not ROOT_DIR.exists():
    ROOT_DIR = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _normalize(text: str) -> str:
    return str(text or "").strip().lower().replace("ё", "е")


def _exec_calc():
    return subprocess.Popen(["calc.exe"], shell=False)


def _exec_notepad():
    return subprocess.Popen(["notepad.exe"], shell=False)


def _exec_explorer():
    return subprocess.Popen(["explorer.exe"], shell=False)


def _exec_browser():
    import webbrowser
    webbrowser.open("https://www.google.com")


_APPS = [
    {
        "id": "browser",
        "title": "Default web browser",
        "aliases": ["браузер", "browser", "default browser"],
        "confirm_commands": [
            "подтвердить открыть браузер",
            "confirm open browser",
            "подтвердить запустить браузер",
        ],
        "method_desc": "Python webbrowser.open",
        "execute": _exec_browser,
    },
    {
        "id": "calculator",
        "title": "Windows Calculator",
        "aliases": ["калькулятор", "calculator", "calc"],
        "confirm_commands": [
            "подтвердить открыть калькулятор",
            "confirm open calculator",
            "подтвердить запустить калькулятор",
        ],
        "method_desc": "subprocess.Popen(['calc.exe'], shell=False)",
        "execute": _exec_calc,
    },
    {
        "id": "notepad",
        "title": "Windows Notepad",
        "aliases": ["блокнот", "notepad"],
        "confirm_commands": [
            "подтвердить открыть блокнот",
            "confirm open notepad",
            "подтвердить запустить блокнот",
        ],
        "method_desc": "subprocess.Popen(['notepad.exe'], shell=False)",
        "execute": _exec_notepad,
    },
    {
        "id": "explorer",
        "title": "Windows File Explorer",
        "aliases": ["проводник", "explorer", "file explorer"],
        "confirm_commands": [
            "подтвердить открыть проводник",
            "confirm open explorer",
            "подтвердить запустить проводник",
        ],
        "method_desc": "subprocess.Popen(['explorer.exe'], shell=False)",
        "execute": _exec_explorer,
    },
]


def is_plain_app_goal(command: str) -> Dict[str, Any]:
    lower = _normalize(command)
    if not lower:
        return {"is_goal": False}
    open_verbs = ["открой ", "открыть ", "open "]
    for verb in open_verbs:
        v = verb.rstrip()
        if lower == v:
            continue
        if lower.startswith(verb):
            target = lower[len(verb):].strip()
            for app in _APPS:
                if target == app["id"] or target in app["aliases"]:
                    first_alias = app["aliases"][0]
                    return {
                        "is_goal": True,
                        "app_id": app["id"],
                        "app_title": app["title"],
                        "confirmation_required": True,
                        "real_action": False,
                        "confirmation_message": (
                            f"Требуется подтверждение: открыть {first_alias}?"
                            f" Напиши: подтвердить открыть {first_alias}"
                        ),
                        "confirm_command": f"подтвердить открыть {first_alias}",
                    }
    return {"is_goal": False}


def is_confirmed_app_action_command(command: str) -> bool:
    lower = _normalize(command)
    if not lower:
        return False
    for app in _APPS:
        for cc in app["confirm_commands"]:
            if lower == _normalize(cc):
                return True
    return False


def run_confirmed_app_action(command: str) -> Dict[str, Any]:
    lower = _normalize(command)
    for app in _APPS:
        for cc in app["confirm_commands"]:
            if lower == _normalize(cc):
                try:
                    proc = app["execute"]()
                    opened = proc is not None
                    message = (
                        f"Выполнено: {app['title']} открыт по вашему подтверждению.\n"
                        f"Действие было разрешено (allowlisted).\n"
                        f"Метод: {app['method_desc']}"
                    )
                    return {
                        "mode": "confirmed_app_action",
                        "route": "confirmed_app_actions",
                        "version": CONFIRMED_APP_ACTIONS_VERSION,
                        "real_action": True,
                        "app_id": app["id"],
                        "app_title": app["title"],
                        "method": app["method_desc"],
                        "opened": opened,
                        "message": message,
                        "result": {
                            "command": "allowlisted_app_action",
                            "action": f"open_{app['id']}",
                            "method": app["method_desc"],
                            "opened": opened,
                            "note": "Только разрешённые действия. Полный Computer Use не включён.",
                        },
                    }
                except Exception as exc:
                    return {
                        "mode": "confirmed_app_action_error",
                        "route": "confirmed_app_actions",
                        "version": CONFIRMED_APP_ACTIONS_VERSION,
                        "real_action": False,
                        "app_id": app["id"],
                        "app_title": app["title"],
                        "error": str(exc),
                        "message": f"Ошибка: не удалось открыть {app['title']}: {exc}",
                        "result": {
                            "command": "allowlisted_app_action_failed",
                            "action": f"open_{app['id']}",
                            "error": str(exc),
                            "note": "Allowlisted action failed.",
                        },
                    }
    return {
        "mode": "confirmed_app_action_error",
        "route": "confirmed_app_actions",
        "version": CONFIRMED_APP_ACTIONS_VERSION,
        "real_action": False,
        "result": {"error": "No matching confirmed app action found"},
    }


def get_allowlist() -> List[Dict[str, Any]]:
    return [
        {
            "app_id": app["id"],
            "app_title": app["title"],
            "confirm_commands": app["confirm_commands"],
            "method": app["method_desc"],
        }
        for app in _APPS
    ]


def is_direct_allowlisted_app_command(command: str) -> Dict[str, Any]:
    lower = _normalize(command)
    if not lower:
        return {"is_direct": False}
    open_verbs = ["открой ", "открыть ", "open "]
    for verb in open_verbs:
        v = verb.rstrip()
        if lower == v:
            continue
        if lower.startswith(verb):
            target = lower[len(verb):].strip()
            for app in _APPS:
                if target == app["id"] or target in app["aliases"]:
                    return {
                        "is_direct": True,
                        "app_id": app["id"],
                        "app_title": app["title"],
                        "method": app["method_desc"],
                        "execute": app["execute"],
                    }
    return {"is_direct": False}


def run_direct_allowlisted_app_action(command: str):
    info = is_direct_allowlisted_app_command(command)
    if not info.get("is_direct"):
        return {
            "mode": "direct_app_action_error",
            "route": "confirmed_app_actions",
            "version": CONFIRMED_APP_ACTIONS_VERSION,
            "real_action": False,
            "result": {"error": "Not a direct allowlisted app command"},
        }
    app_id = info["app_id"]
    app_title = info["app_title"]
    method = info["method"]
    execute = info["execute"]
    try:
        result = execute()
        opened = True
        message = (
            f"Выполнено: {app_title} открыт.\n"
            f"Действие было разрешено (allowlisted).\n"
            f"Метод: {method}"
        )
        return {
            "mode": "direct_app_action",
            "route": "confirmed_app_actions",
            "version": CONFIRMED_APP_ACTIONS_VERSION,
            "real_action": True,
            "app_id": app_id,
            "app_title": app_title,
            "method": method,
            "opened": opened,
            "message": message,
            "result": {
                "command": "direct_allowlisted_app_action",
                "action": f"open_{app_id}",
                "method": method,
                "opened": opened,
                "note": "Прямое разрешённое действие. Подтверждение не требовалось.",
            },
        }
    except Exception as exc:
        return {
            "mode": "direct_app_action_error",
            "route": "confirmed_app_actions",
            "version": CONFIRMED_APP_ACTIONS_VERSION,
            "real_action": False,
            "app_id": app_id,
            "app_title": app_title,
            "error": str(exc),
            "message": f"Ошибка: не удалось открыть {app_title}: {exc}",
            "result": {
                "command": "direct_allowlisted_app_action_failed",
                "action": f"open_{app_id}",
                "error": str(exc),
                "note": "Direct allowlisted action failed.",
            },
        }


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = _normalize(command)
    if lower in {"status", "pc confirmed actions status"}:
        return status()
    if lower in {"report", "pc confirmed actions report"}:
        return report()
    if is_confirmed_app_action_command(lower):
        return run_confirmed_app_action(lower)
    return {
        "mode": "confirmed_app_actions_unrecognized",
        "version": CONFIRMED_APP_ACTIONS_VERSION,
        "result": "Неизвестная команда. Используйте: pc confirmed actions status, pc confirmed actions report",
    }


def status() -> Dict[str, Any]:
    allowlist = get_allowlist()
    return {
        "ok": True,
        "mode": "confirmed_app_actions_status",
        "version": CONFIRMED_APP_ACTIONS_VERSION,
        "total_actions": len(allowlist),
        "actions": [a["app_id"] for a in allowlist],
    }


def report() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "confirmed_app_actions_report",
        "version": CONFIRMED_APP_ACTIONS_VERSION,
        "generated_at": _now(),
        "allowlist": get_allowlist(),
        "status": status(),
        "note": "All app actions are allowlisted and require explicit confirmation. Only fixed methods allowed: subprocess.Popen with shell=False.",
    }
````

### ПУТЬ: modules/context_pack_ru.py (245 строк, 9874 байт)

````python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


CONTEXT_PACK_VERSION = "v6.64"
CONTEXT_PACK_NAME = "LocalComet Context Pack Generator RU"

ROOT_PATH = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_PATH / ".localcomet" / "agent"
CONTEXT_PACK_JSON = OUTPUT_DIR / "context_pack.json"
CONTEXT_PACK_MD = OUTPUT_DIR / "context_pack.md"
SCHEMA_PATH = ROOT_PATH / ".localcomet" / "agent" / "run_manifest.schema.json"
AGENTS_MD_PATH = ROOT_PATH / "AGENTS.md"
OPERATING_LAYER_PATH = ROOT_PATH / "docs" / "agent_operating_layer.md"
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_line_with(path: Path, pattern: str) -> str:
    try:
        for line in path.read_text(encoding="utf-8").split("\n"):
            if pattern in line:
                return line.strip()
    except Exception:
        pass
    return ""


def _extract_green_baseline() -> Dict[str, Any]:
    baseline = {
        "version": "unknown",
        "strict_project_stability": "unknown",
        "functional": "unknown",
        "contracts": "unknown",
        "hard_failures": "unknown",
        "warnings": "unknown",
    }
    try:
        text = AGENTS_MD_PATH.read_text(encoding="utf-8")
        for line in text.split("\n"):
            if "LOCALCOMET_VERSION" in line:
                baseline["version"] = line.split("=")[-1].strip()
            if "strict_project_stability:" in line:
                baseline["strict_project_stability"] = line.split(":")[-1].strip().split(",")[0]
            if "hard_failures=" in line:
                for p in line.split(","):
                    p = p.strip()
                    if "hard_failures=" in p:
                        baseline["hard_failures"] = p.split("=")[-1]
                    if "warnings=" in p:
                        baseline["warnings"] = p.split("=")[-1]
            if "functional:" in line:
                baseline["functional"] = line.split(":")[-1].strip()
            if "contracts:" in line:
                baseline["contracts"] = line.split(":")[-1].strip()
    except Exception:
        pass
    return baseline


def _detect_base_version() -> str:
    line = _read_line_with(CONTROL_PANEL_PATH, "LOCALCOMET_VERSION")
    if "=" in line:
        return line.split("=")[-1].strip().strip("\"'")
    return "unknown"


def generate() -> Dict[str, Any]:
    baseline = _extract_green_baseline()
    base_version = _detect_base_version()
    schema_ok = SCHEMA_PATH.exists() and SCHEMA_PATH.is_file()
    agents_lines = []
    try:
        agents_lines = AGENTS_MD_PATH.read_text(encoding="utf-8").split("\n")[:5]
    except Exception:
        pass
    ol_lines = []
    if OPERATING_LAYER_PATH.exists():
        try:
            ol_lines = OPERATING_LAYER_PATH.read_text(encoding="utf-8").split("\n")[:3]
        except Exception:
            pass

    return {
        "project_name": "LocalComet / LocalAgent",
        "base_version": base_version,
        "current_green_baseline": baseline,
        "task_goal": "",
        "timestamp": _now(),
        "allowed_files": [],
        "forbidden_files": [],
        "validation_commands": [
            "python -m py_compile <changed_python_file>",
            "python -m py_compile LocalComet_Control_Panel.py",
            "python tools\\localcomet_preflight_audit.py --include-tools",
            "python -c \"from modules.computer_use_core_ru import dispatch; r=dispatch('pc computer contracts'); print(r); assert r['ok']\"",
            "python -c \"from modules.strict_project_stability_ru import dispatch; r=dispatch('\\u043f\\u0440\\u043e\\u0432\\u0435\\u0440\\u044c \\u043f\\u0440\\u043e\\u0435\\u043a\\u0442'); assert r['ok'] and r['summary']['hard_failures'] == 0 and r['summary']['warnings'] == 0\"",
        ],
        "required_final_report_fields": [
            "files_changed",
            "backup_path",
            "tests_run",
            "test_results",
            "first_failing_error",
            "rollback_instructions",
            "project_is_green",
        ],
        "stability_policy": "Only GREEN is acceptable. If any gate fails, revert or fix before proceeding.",
        "relay_installer_policy": "For architecture-only edits (docs, schemas, skills, config), do NOT use the Relay installer workflow. Use direct file writes. The Relay installer workflow is for product changes only.",
        "notes_for_opencode": "",
        "agents_md_reference": {
            "path": str(AGENTS_MD_PATH.relative_to(ROOT_PATH)),
            "first_lines": "\n".join(agents_lines),
        },
        "operating_layer_reference": {
            "path": str(OPERATING_LAYER_PATH.relative_to(ROOT_PATH)) if OPERATING_LAYER_PATH.exists() else "",
            "exists": OPERATING_LAYER_PATH.exists(),
            "first_lines": "\n".join(ol_lines),
        },
        "schema_validated": {
            "path": str(SCHEMA_PATH.relative_to(ROOT_PATH)),
            "exists": schema_ok,
        },
    }


def _write_context_pack(payload: Dict[str, Any]) -> Dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_PACK_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# LocalComet Context Pack",
        "",
        f"- project_name: {payload.get('project_name')}",
        f"- base_version: {payload.get('base_version')}",
        f"- generated_at: {payload.get('timestamp')}",
        "",
        "## Current GREEN Baseline",
        "",
    ]
    bl = payload.get("current_green_baseline", {})
    if isinstance(bl, dict):
        for k, v in bl.items():
            lines.append(f"- {k}: {v}")
    lines.append("")
    lines.extend(["## Task Goal", "", f"{payload.get('task_goal', '')}", ""])
    lines.extend(["## Allowed Files", ""])
    for af in payload.get("allowed_files", []):
        lines.append(f"- {af}")
    lines.append("")
    lines.extend(["## Forbidden Files", ""])
    for ff in payload.get("forbidden_files", []):
        lines.append(f"- {ff}")
    lines.append("")
    lines.extend(["## Validation Commands", ""])
    for vc in payload.get("validation_commands", []):
        lines.append(f"```powershell\n{vc}\n```")
    lines.append("")
    lines.extend(["## Required Final Report Fields", ""])
    for rf in payload.get("required_final_report_fields", []):
        lines.append(f"- {rf}")
    lines.append("")
    lines.extend(["## Stability Policy", "", payload.get("stability_policy", ""), ""])
    lines.extend(["## Relay Installer Policy", "", payload.get("relay_installer_policy", ""), ""])
    lines.extend(["## Notes for OpenCode", "", payload.get("notes_for_opencode", ""), ""])
    lines.extend(["## References", ""])
    ref = payload.get("agents_md_reference", {})
    if isinstance(ref, dict) and ref.get("path"):
        lines.append(f"- AGENTS.md: {ref['path']}")
        first = ref.get("first_lines", "")
        if first:
            lines.append("  ```text")
            lines.append(f"  {first}")
            lines.append("  ```")
    lines.append("")
    ref2 = payload.get("operating_layer_reference", {})
    if isinstance(ref2, dict) and ref2.get("exists"):
        lines.append(f"- docs/agent_operating_layer.md: {ref2['path']}")
        first = ref2.get("first_lines", "")
        if first:
            lines.append("  ```text")
            lines.append(f"  {first}")
            lines.append("  ```")
    lines.append("")
    sv = payload.get("schema_validated", {})
    if isinstance(sv, dict):
        lines.append(f"- run_manifest.schema.json: {sv.get('path', '')} (exists: {sv.get('exists', False)})")
    lines.append("")
    CONTEXT_PACK_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(CONTEXT_PACK_JSON.relative_to(ROOT_PATH)), "md": str(CONTEXT_PACK_MD.relative_to(ROOT_PATH))}


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "context_pack_status",
        "version": CONTEXT_PACK_VERSION,
        "json_exists": CONTEXT_PACK_JSON.exists(),
        "md_exists": CONTEXT_PACK_MD.exists(),
    }


def report() -> Dict[str, Any]:
    payload = generate()
    paths = _write_context_pack(payload)
    return {
        "ok": True,
        "mode": "context_pack_report",
        "version": CONTEXT_PACK_VERSION,
        "generated_at": _now(),
        "paths": paths,
    }


def is_context_pack_command(command: str) -> bool:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    return lowered in {
        "localcomet agent context pack",
        "agent context pack",
        "context pack",
    } or lowered.startswith("localcomet agent context pack ")


def dispatch(command: str) -> Dict[str, Any]:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    if lowered in {"localcomet agent context pack", "agent context pack", "context pack"}:
        result = report()
        return {"ok": True, "handled": True, "mode": "context_pack_generated", "version": CONTEXT_PACK_VERSION, "paths": result.get("paths", {})}
    if lowered.startswith("localcomet agent context pack "):
        result = report()
        return {"ok": True, "handled": True, "mode": "context_pack_generated", "version": CONTEXT_PACK_VERSION, "paths": result.get("paths", {})}
    if lowered in {"localcomet agent context pack status", "agent context pack status", "context pack status"}:
        return status()
    return {"ok": False, "mode": "context_pack_unknown", "version": CONTEXT_PACK_VERSION, "command": command, "hint": "Use: localcomet agent context pack"}


if __name__ == "__main__":
    result = dispatch("localcomet agent context pack")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
````

### ПУТЬ: modules/debug_package_ru.py (207 строк, 7868 байт)

````python
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List


DEBUG_PACKAGE_VERSION = "v6.58"
DEBUG_PACKAGE_NAME = "LocalComet Debug Package Collector RU"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / "AGENTS.md").exists() or (candidate / "LocalComet_Control_Panel.py").exists():
            return candidate
    return get_project_root()


def _packages_dir() -> Path:
    path = _root() / "Projects" / "Reports" / "debug_packages"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_rel(path: Path) -> str:
    try:
        return str(path.relative_to(_root())).replace("\\", "/")
    except Exception:
        return path.name


def _add_if_exists(zipf: zipfile.ZipFile, path: Path, added: List[str]) -> None:
    try:
        if path.exists() and path.is_file():
            arcname = _safe_rel(path)
            zipf.write(path, arcname)
            added.append(arcname)
    except Exception:
        pass


def _latest_in(folder: Path, pattern: str) -> Path | None:
    if not folder.exists():
        return None
    items = [p for p in folder.glob(pattern) if p.is_file()]
    if not items:
        return None
    try:
        return max(items, key=lambda p: p.stat().st_mtime)
    except Exception:
        return items[-1]


def _collect_candidates() -> List[Path]:
    root = _root()
    candidates: List[Path] = [
        root / "Projects" / "ChatGPTRelay" / "response.json",
        root / "Projects" / "ChatGPTRelay" / "selected_response_source.txt",
        root / "Projects" / "Reports" / "patch_panel_ux" / "latest_patch_panel_ux_report.md",
        root / "Projects" / "Reports" / "patch_panel_ux" / "latest_patch_panel_ux_report.json",
        root / "Projects" / "Reports" / "developer_velocity" / "latest_first_failure.md",
        root / "Projects" / "Reports" / "developer_velocity" / "latest_first_failure.json",
        root / "Projects" / "Reports" / "patch_event_timeline" / "latest_patch_event_timeline.md",
        root / "Projects" / "Reports" / "patch_event_timeline" / "latest_patch_event_timeline.json",
        root / "Projects" / "Reports" / "green_gate_status" / "latest_green_gate_status.md",
        root / "Projects" / "Reports" / "green_gate_status" / "latest_green_gate_status.json",
    ]
    latest_folders = [
        (root / "Projects" / "Reports" / "strict_project_stability", "*.md"),
        (root / "Projects" / "Reports" / "localcomet_functional_tests", "*.md"),
        (root / "Projects" / "Reports" / "computer_use_contracts", "*.json"),
        (root / "Projects" / "Reports" / "auto_verification", "*.md"),
    ]
    for folder, pattern in latest_folders:
        latest = _latest_in(folder, pattern)
        if latest:
            candidates.append(latest)
    return candidates


def create_debug_package(write_report: bool = True) -> Dict[str, Any]:
    from modules.first_failure_extractor_ru import find_latest_failure
    from modules.patch_event_timeline_ru import build_latest_timeline
    from modules.green_gate_status_ru import get_green_gate_status

    failure = find_latest_failure(write_report=True)
    timeline = build_latest_timeline(write_report=True)
    green = get_green_gate_status(write_report=True)

    package_path = _packages_dir() / f"localcomet_debug_package_{_stamp()}.zip"
    latest_package = _packages_dir() / "latest_localcomet_debug_package.zip"
    added: List[str] = []
    manifest: Dict[str, Any] = {
        "ok": True,
        "mode": "debug_package",
        "version": DEBUG_PACKAGE_VERSION,
        "created_at": _now(),
        "package": str(package_path),
        "first_failure": failure.get("failure", {}),
        "timeline_summary": timeline.get("summary", {}),
        "green_gate": {
            "clean_green": green.get("clean_green"),
            "recommendation": green.get("recommendation"),
            "strict_summary": green.get("strict", {}).get("summary", {}),
        },
        "files": [],
    }

    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for path in _collect_candidates():
            _add_if_exists(zipf, path, added)
        manifest["files"] = added
        zipf.writestr("debug_package_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))

    try:
        latest_package.write_bytes(package_path.read_bytes())
    except Exception:
        pass

    manifest["files"] = added
    manifest["package"] = str(package_path)
    manifest["latest_package"] = str(latest_package)
    if write_report:
        paths = _write_reports(manifest)
        manifest["report"] = str(paths["md"])
        manifest["json"] = str(paths["json"])
    return manifest


def _write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    out = _packages_dir()
    json_path = out / f"debug_package_{_stamp()}.json"
    md_path = out / f"debug_package_{_stamp()}.md"
    latest_json = out / "latest_debug_package.json"
    latest_md = out / "latest_debug_package.md"
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json_path.write_text(text, encoding="utf-8")
    latest_json.write_text(text, encoding="utf-8")
    lines = [
        "# LocalComet Debug Package",
        "",
        f"- version: {payload.get('version')}",
        f"- package: {payload.get('package')}",
        f"- latest_package: {payload.get('latest_package')}",
        f"- files: {len(payload.get('files', []))}",
        "",
        "## First failure",
        "",
        "```json",
        json.dumps(payload.get("first_failure", {}), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Green gate",
        "",
        "```json",
        json.dumps(payload.get("green_gate", {}), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
    ]
    md = "\n".join(lines)
    md_path.write_text(md, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")
    return {"json": json_path, "md": md_path}


def status(command: str = "status") -> Dict[str, Any]:
    latest = _packages_dir() / "latest_localcomet_debug_package.zip"
    return {
        "ok": True,
        "mode": "debug_package_status",
        "version": DEBUG_PACKAGE_VERSION,
        "latest_package": str(latest),
        "latest_exists": latest.exists(),
        "commands": ["debug пакет", "debug package", "собрать debug пакет"],
    }


def report(command: str = "report") -> Dict[str, Any]:
    return create_debug_package(write_report=True)


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"debug пакет", "собрать debug пакет", "debug package", "debug pack", "пакет отладки"}:
        payload = create_debug_package(write_report=True)
        payload["handled"] = True
        return payload
    if lower in {"status", "статус", "debug package status"}:
        payload = status(command)
        payload["handled"] = True
        return payload
    if lower in {"report", "отчет", "debug package report"}:
        payload = report(command)
        payload["handled"] = True
        return payload
    return {"ok": False, "handled": False, "mode": "debug_package", "reason": "unknown command"}
````

### ПУТЬ: modules/desktop_action_planner.py (237 строк, 7537 байт)

````python
import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value
from modules.desktop_observer import observe_desktop


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "desktop_action_planner"


DANGEROUS_MARKERS = [
    "delete",
    "remove",
    "erase",
    "удали",
    "удалить",
    "сотри",
    "оплат",
    "платеж",
    "платёж",
    "карта",
    "cvv",
    "card",
    "payment",
    "pay ",
    "buy ",
    "checkout",
    "password",
    "пароль",
    "api key",
    "token",
    "confirm",
    "подтверди",
    "submit",
    "отправь форму",
]

ACTION_MARKERS = [
    "click",
    "клик",
    "нажми",
    "press",
    "type",
    "введи",
    "напиши",
    "send",
    "отправь",
    "open",
    "открой",
]


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _contains_any(text, markers):
    lower = str(text or "").lower()
    return [marker for marker in markers if marker in lower]


def _risk_for_goal(goal):
    dangerous = _contains_any(goal, DANGEROUS_MARKERS)
    action_words = _contains_any(goal, ACTION_MARKERS)

    if dangerous:
        return "blocked", "high", dangerous

    if action_words:
        return "needs_confirmation", "medium", action_words

    return "draft", "low", []


def _suggest_steps(goal, observation, status):
    active = observation.get("active_window") or {}
    active_title = active.get("title") or "текущее активное окно"
    goal_text = str(goal or "").strip()

    if status == "blocked":
        return [
            "Остановиться: задача содержит опасные маркеры.",
            "Попросить пользователя уточнить безопасную цель.",
            "Не выполнять клики, ввод текста, отправку форм или подтверждения.",
        ]

    steps = [
        f"Проверить, что активное окно подходит для цели: {active_title}.",
        f"Сверить цель пользователя: {goal_text or 'цель не указана'}.",
        "Если окно не то, попросить пользователя открыть нужное приложение или вкладку.",
        "Перед любым кликом/вводом показать пользователю план и дождаться подтверждения.",
    ]

    lower = goal_text.lower()

    if any(word in lower for word in ["найди", "search", "поиск", "найти"]):
        steps.append("Для поиска: сначала определить поле поиска, затем предложить текст запроса.")

    if any(word in lower for word in ["напиши", "введи", "type"]):
        steps.append("Для ввода текста: показать точный текст и целевое поле до выполнения.")

    if any(word in lower for word in ["клик", "нажми", "click"]):
        steps.append("Для клика: назвать видимую кнопку/элемент и риск действия.")

    return steps


def _write_report(result):
    _ensure_dir()
    path = REPORTS_DIR / f"desktop_action_plan_{_stamp()}.md"
    observation = result.get("observation") or {}
    active = observation.get("active_window") or {}
    windows = observation.get("windows") or []

    lines = [
        "# Desktop Action Plan",
        "",
        f"- created_at: {result.get('created_at')}",
        f"- goal: {result.get('goal') or 'нет'}",
        f"- status: {result.get('status')}",
        f"- risk_level: {result.get('risk_level')}",
        f"- blocked_markers: {', '.join(result.get('markers') or []) or 'нет'}",
        f"- observation_report: {observation.get('report_path') or 'нет'}",
        f"- screenshot: {observation.get('screenshot_path') or 'нет'}",
        "",
        "## Active Window",
        "",
        f"- title: {active.get('title') or 'нет'}",
        f"- class: {active.get('class') or 'нет'}",
        f"- rect: `{json.dumps(active.get('rect') or {}, ensure_ascii=False)}`",
        "",
        "## Visible Windows",
        "",
    ]

    if windows:
        for index, window in enumerate(windows[:15], start=1):
            lines.append(f"{index}. `{window.get('title') or 'нет'}`")
    else:
        lines.append("- нет")

    lines.extend([
        "",
        "## Proposed Safe Steps",
        "",
    ])

    for index, step in enumerate(result.get("steps") or [], start=1):
        lines.append(f"{index}. {step}")

    lines.extend([
        "",
        "## Safety",
        "",
        "- This planner does not click.",
        "- This planner does not type.",
        "- This planner does not press hotkeys.",
        "- Execution must be a separate confirmed step.",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def plan_desktop_action(goal, write_report=True):
    goal = str(goal or "").strip()
    observation = observe_desktop(write_report=True)
    status, risk_level, markers = _risk_for_goal(goal)
    steps = _suggest_steps(goal, observation, status)

    result = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "status": status,
        "risk_level": risk_level,
        "markers": markers,
        "observation": observation,
        "steps": steps,
        "report_path": "",
    }

    if write_report:
        result["report_path"] = _write_report(result)

    try:
        set_value("desktop_action_planner: да", "да")
        set_value("last_desktop_action_plan_goal", goal)
        set_value("last_desktop_action_plan_status", status)
        set_value("last_desktop_action_plan_risk", risk_level)
        set_value("last_desktop_action_plan_report", result.get("report_path") or "")
    except Exception:
        pass

    return result


def format_desktop_action_plan(result):
    observation = result.get("observation") or {}
    active = observation.get("active_window") or {}
    lines = [
        "Desktop Action Planner:",
        f"- goal: {result.get('goal') or 'нет'}",
        f"- status: {result.get('status')}",
        f"- risk_level: {result.get('risk_level')}",
        f"- active_window: {active.get('title') or 'нет'}",
        f"- screenshot: {observation.get('screenshot_path') or 'нет'}",
        f"- observation_report: {observation.get('report_path') or 'нет'}",
        f"- plan_report: {result.get('report_path') or 'нет'}",
        "",
        "Plan:",
    ]

    for index, step in enumerate(result.get("steps") or [], start=1):
        lines.append(f"{index}. {step}")

    if result.get("status") == "blocked":
        lines.extend([
            "",
            "STOP: план заблокирован safety guard. Автодействия не выполнялись.",
        ])

    return "\n".join(lines)


def latest_desktop_action_plan_report():
    if not REPORTS_DIR.exists():
        return ""

    reports = sorted(REPORTS_DIR.glob("desktop_action_plan_*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(reports[0]) if reports else ""
````

### ПУТЬ: modules/desktop_control_plane_ru.py (2347 строк, 100516 байт)

````python
from __future__ import annotations

import hashlib
import re
import secrets
import threading
import uuid
from dataclasses import dataclass, field, fields, replace
from typing import Any, Callable, Mapping

from modules.knowledge_contract_ru import (
    DEFAULT_CONTEXT_CHARS,
    DEFAULT_MAX_RESULTS,
    KnowledgeAdapterError,
    KnowledgeContextError,
    KnowledgeContextRequest,
    KnowledgeContextResult,
    KnowledgeContextState,
    KnowledgeErrorCode,
    QueryIntent,
)
from modules.knowledge_injection_ru import (
    KnowledgeInjectionContractError,
    KnowledgeInjectionDecision,
    KnowledgeInjectionDecisionSource,
    KnowledgeInjectionEnvelope,
    KnowledgeInjectionError,
    KnowledgeInjectionPreview,
    KnowledgeInjectionRecord,
    KnowledgeInjectionState,
    decide_envelope,
    mark_envelope_injected,
    prepare_injection_envelope,
    verify_envelope_integrity,
    verify_provider_messages,
)
from modules.knowledge_change_proposal_ru import KnowledgeChangeProposal, ValidationResult
from modules.knowledge_change_review_ru import (
    CONTRACT_VERSION as KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
    CurrentKnowledgeState,
    KnowledgeChangeReviewArtifact,
    ReviewStatus,
    analyze_review,
)
from modules.knowledge_change_review_decision_ru import (
    CONTRACT_VERSION as HUMAN_REVIEW_DECISION_CONTRACT,
    MAX_ACTOR_DISPLAY_NAME_CHARS,
    MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES,
    MAX_ACTOR_IDENTIFIER_CHARS,
    MAX_ACTOR_IDENTIFIER_UTF8_BYTES,
    MAX_ACTOR_SOURCE_CHARS,
    MAX_ACTOR_SOURCE_UTF8_BYTES,
    MAX_COMMENT_CHARS,
    MAX_COMMENT_UTF8_BYTES,
    HumanReviewDecision,
    HumanReviewDecisionRejected,
    HumanReviewDecisionValue,
    HumanReviewerMetadata,
    create_human_review_decision,
)
from modules.knowledge_review_ui_projection_ru import (
    ProjectionRejected,
    ProjectionRejectionCode,
    materialize_json_value,
    project_human_review_decision,
    project_knowledge_change_review,
    project_knowledge_change_review_summary,
)


DESKTOP_CONTROL_PLANE_VERSION = "v6.84.6"
IPC_PROTOCOL = "localcomet.ipc"
IPC_PROTOCOL_VERSION = "1.0"
SIDECAR_RUNTIME_VERSION = "v6.84.3"
KNOWLEDGE_CONTEXT_CONTROL_PLANE_RELEASE = "v6.84.5.1e5"
KNOWLEDGE_INJECTION_CONTROL_PLANE_RELEASE = "v6.84.5.1e6"
KNOWLEDGE_REVIEW_LIST_CONTRACT = "localcomet.knowledge-review-list/1.0"
KNOWLEDGE_REVIEW_GET_CONTRACT = "localcomet.knowledge-review-get/1.0"
KNOWLEDGE_REVIEW_SNAPSHOT_CONTRACT = "localcomet.knowledge-review-snapshot/1.0"
KNOWLEDGE_REVIEW_REFRESH_CONTRACT = "localcomet.knowledge-review-refresh/1.0"
KNOWLEDGE_REVIEW_DECISION_CREATE_CONTRACT = (
    "localcomet.knowledge-review-decision-create/1.0"
)
KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION = "v6.84.6"
KNOWLEDGE_REVIEW_SOURCE = "LOCAL_CONTROL_PLANE"
MAX_KNOWLEDGE_REVIEW_ARTIFACTS = 128
MAX_KNOWLEDGE_REVIEW_PAGE_SIZE = 50
MAX_KNOWLEDGE_REVIEW_DECISIONS = 128
MAX_REVIEW_ACTIVITY_ITEMS = 128

SESSION_STATES = ("OPEN", "CLOSED")
THREAD_STATES = ("ACTIVE", "CLOSED")
TURN_STATES = ("CREATED", "RUNNING", "CANCELLING", "CANCELLED", "COMPLETED", "FAILED")
ITEM_STATES = ("STARTED", "STREAMING", "COMPLETED", "FAILED")
ITEM_KINDS = (
    "approval_request",
    "assistant_message",
    "reasoning",
    "status",
    "tool_proposal",
    "tool_result",
    "user_message",
    "verification_result",
)
GENERATED_ITEM_KINDS = ("assistant_message", "status", "user_message")
CONTROL_PLANE_METHODS = (
    "app.bootstrap",
    "app.status",
    "knowledge.review.decision.create",
    "knowledge.review.get",
    "knowledge.review.list",
    "knowledge.review.refresh",
    "knowledge.review.snapshot",
    "session.close",
    "session.create",
    "session.get",
    "thread.create",
    "thread.get",
    "turn.cancel",
    "turn.start_mock",
    "turn.status",
)
SUPPORTED_METHODS = tuple(sorted(CONTROL_PLANE_METHODS + ("app.health", "app.shutdown")))
EVENT_METHODS = (
    "item.completed",
    "item.delta",
    "item.started",
    "knowledge.context.failed",
    "knowledge.context.ready",
    "knowledge.context.requested",
    "session.closed",
    "session.created",
    "sidecar.status",
    "thread.created",
    "turn.cancelled",
    "turn.completed",
    "turn.failed",
    "turn.started",
)
CANCEL_REASONS = ("timeout", "user_requested", "window_closing")
BEHAVIORS = ("complete", "pending_model", "wait_for_cancel")
DESKTOP_KNOWLEDGE_ACTIONS = (
    "CANCEL",
    "INCLUDE_AND_SEND",
    "REJECT_AND_SEND_WITHOUT_KNOWLEDGE",
)
ID_RE = re.compile(r"^[0-9a-f]{24}$")
KNOWLEDGE_REVIEW_ID_RE = re.compile(r"^kreview:[0-9a-f]{64}$")
KNOWLEDGE_PROPOSAL_ID_RE = re.compile(r"^kprop:[0-9a-f]{64}$")
KNOWLEDGE_CHANGE_ID_RE = re.compile(r"^kchange:[0-9a-f]{64}$")
KNOWLEDGE_DECISION_ID_RE = re.compile(r"^kdecision:[0-9a-f]{64}$")
VAULT_REVISION_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SECRET_RE = re.compile(
    r"(?i)(sk-[A-Za-z0-9_\-]{8,}|bearer\s+[A-Za-z0-9._\-]{8,}|"
    r"(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s'\";]{6,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----|"
    r"Traceback \(most recent call last\):.*)",
    re.DOTALL,
)
_WINDOWS_USER_PATH_RE = r"[A-Z]:" + r"\\Users\\" + r"[^\\\s]+"
_POSIX_HOME_PATH_RE = "/" + "home" + r"/[^/\s]+"
_MAC_USER_PATH_RE = "/" + "Users" + r"/[^/\s]+"
_UNC_PATH_RE = r"\\\\" + r"[^\\\s]+" + r"\\" + r"[^\\\s]+"
PATH_RE = re.compile(
    r"(?i)("
    + "|".join(
        (
            _WINDOWS_USER_PATH_RE,
            _POSIX_HOME_PATH_RE,
            _MAC_USER_PATH_RE,
            _UNC_PATH_RE,
        )
    )
    + r")"
)


class ControlPlaneError(Exception):
    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.message = _bounded_text(message, 512)
        self.details = dict(details or {})


@dataclass(frozen=True, slots=True)
class ControlPlaneLimits:
    maximum_sessions: int = 16
    maximum_threads_per_session: int = 32
    maximum_turns_per_thread: int = 64
    maximum_items_per_turn: int = 128
    maximum_title_characters: int = 120
    maximum_prompt_characters: int = 8192
    maximum_preview_characters: int = 512
    maximum_item_delta_characters: int = 65536
    maximum_events_per_request: int = 64
    maximum_total_event_text_characters: int = 1_048_576
    maximum_response_json_size: int = 1_048_576
    maximum_remembered_closed_sessions: int = 16
    maximum_knowledge_review_artifacts: int = MAX_KNOWLEDGE_REVIEW_ARTIFACTS
    maximum_knowledge_review_page_size: int = MAX_KNOWLEDGE_REVIEW_PAGE_SIZE
    maximum_knowledge_review_decisions: int = MAX_KNOWLEDGE_REVIEW_DECISIONS

    def __post_init__(self) -> None:
        hard_maximums = {
            "maximum_sessions": 64,
            "maximum_threads_per_session": 128,
            "maximum_turns_per_thread": 256,
            "maximum_items_per_turn": 512,
            "maximum_prompt_characters": 32768,
            "maximum_events_per_request": 256,
            "maximum_total_event_text_characters": 4_194_304,
            "maximum_knowledge_review_artifacts": MAX_KNOWLEDGE_REVIEW_ARTIFACTS,
            "maximum_knowledge_review_page_size": MAX_KNOWLEDGE_REVIEW_PAGE_SIZE,
            "maximum_knowledge_review_decisions": MAX_KNOWLEDGE_REVIEW_DECISIONS,
        }
        for item in fields(self):
            name = item.name
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            hard = hard_maximums.get(name)
            if hard is not None and value > hard:
                raise ValueError(f"{name} exceeds hard maximum")


@dataclass(frozen=True, slots=True)
class ControlPlaneEvent:
    method: str
    sequence: int
    reply_to: str
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ControlPlaneDispatchResult:
    events: tuple[ControlPlaneEvent, ...]
    response: Mapping[str, Any]


@dataclass(slots=True)
class _Session:
    session_id: str
    title: str
    state: str = "OPEN"
    thread_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _Thread:
    thread_id: str
    session_id: str
    title: str
    state: str = "ACTIVE"
    turn_ids: list[str] = field(default_factory=list)
    active_turn_id: str | None = None


@dataclass(slots=True)
class _Turn:
    turn_id: str
    thread_id: str
    state: str
    prompt_sha256: str
    prompt_text: str
    prompt_preview: str
    prompt_character_count: int
    item_ids: list[str] = field(default_factory=list)
    last_sequence: int = -1
    model_called: bool = False
    tools_executed: int = 0
    knowledge_request_id: str | None = None
    knowledge_context: KnowledgeContextResult | None = None


@dataclass(slots=True)
class _Item:
    item_id: str
    turn_id: str
    kind: str
    state: str
    text: str = ""


@dataclass(slots=True)
class _KnowledgeContextRecord:
    request: KnowledgeContextRequest
    result: KnowledgeContextResult
    lifecycle: list[KnowledgeContextState]
    next_sequence: int = 0


@dataclass(frozen=True, slots=True)
class _DesktopKnowledgeDecisionReceipt:
    injection_id: str
    turn_id: str
    action: str
    preview_hash: str
    state: str
    model_turn_id: str | None
    model_dispatched: bool
    knowledge_included: bool

    def to_dict(self, *, duplicate: bool = False) -> dict[str, Any]:
        return {
            "injection_id": self.injection_id,
            "turn_id": self.turn_id,
            "action": self.action,
            "preview_hash": self.preview_hash,
            "state": self.state,
            "decision_source": KnowledgeInjectionDecisionSource.USER_APPROVAL.value,
            "model_turn_id": self.model_turn_id,
            "model_dispatched": self.model_dispatched,
            "knowledge_included": self.knowledge_included,
            "duplicate": duplicate,
        }


class DesktopControlPlane:
    def __init__(
        self,
        *,
        limits: ControlPlaneLimits | None = None,
        id_factory: Callable[[], str] | None = None,
        knowledge_adapter: Any | None = None,
        knowledge_request_id_factory: Callable[[], str] | None = None,
        knowledge_injection_id_factory: Callable[[], str] | None = None,
        knowledge_reviews: (
            list[KnowledgeChangeReviewArtifact]
            | tuple[KnowledgeChangeReviewArtifact, ...]
            | None
        ) = None,
    ) -> None:
        self.limits = limits or default_control_plane_limits()
        self._id_factory = id_factory or _secure_id
        self._knowledge_adapter = knowledge_adapter
        self._knowledge_request_id_factory = knowledge_request_id_factory or _secure_knowledge_request_id
        self._knowledge_injection_id_factory = knowledge_injection_id_factory or _secure_knowledge_injection_id
        self._sessions: dict[str, _Session] = {}
        self._threads: dict[str, _Thread] = {}
        self._turns: dict[str, _Turn] = {}
        self._items: dict[str, _Item] = {}
        self._knowledge_requests: dict[str, _KnowledgeContextRecord] = {}
        self._turn_current_knowledge_request: dict[str, str] = {}
        self._knowledge_injections: dict[str, KnowledgeInjectionRecord] = {}
        self._knowledge_injection_lock = threading.RLock()
        self._desktop_knowledge_receipts: dict[str, _DesktopKnowledgeDecisionReceipt] = {}
        self._desktop_knowledge_in_flight: set[str] = set()
        self._closed_session_ids: list[str] = []
        self._knowledge_review_lock = threading.RLock()
        self._knowledge_reviews = self._snapshot_knowledge_reviews(knowledge_reviews)
        self._knowledge_review_decisions: dict[str, HumanReviewDecision] = {}

    def dispatch(self, method: str, payload: Mapping[str, Any], *, request_id: str) -> ControlPlaneDispatchResult:
        findings = validate_control_plane_payload(method, payload)
        if findings:
            raise ControlPlaneError("invalid_payload", findings[0])
        if method == "app.bootstrap":
            return self._result((), self.bootstrap_snapshot())
        if method == "app.status":
            return self._result((), self.status_snapshot())
        if method == "knowledge.review.list":
            return self._list_knowledge_reviews(payload)
        if method == "knowledge.review.get":
            return self._get_knowledge_review(str(payload["review_artifact_identity"]))
        if method == "knowledge.review.snapshot":
            return self._knowledge_review_snapshot(refresh=False)
        if method == "knowledge.review.refresh":
            return self._knowledge_review_snapshot(refresh=True)
        if method == "knowledge.review.decision.create":
            return self._create_knowledge_review_decision(payload)
        if method == "session.create":
            return self._create_session(payload, request_id)
        if method == "session.get":
            return self._result((), self._session_summary(self._require_session(payload["session_id"])))
        if method == "session.close":
            return self._close_session(str(payload["session_id"]), request_id)
        if method == "thread.create":
            return self._create_thread(payload, request_id)
        if method == "thread.get":
            return self._result((), self._thread_summary(self._require_thread(payload["thread_id"])))
        if method == "turn.start_mock":
            return self._start_mock_turn(payload, request_id)
        if method == "turn.status":
            return self._result((), self._turn_summary(self._require_turn(payload["turn_id"])))
        if method == "turn.cancel":
            return self._cancel_turn(payload, request_id)
        raise ControlPlaneError("unsupported_method", "unsupported control-plane method")

    def _snapshot_knowledge_reviews(
        self,
        knowledge_reviews: (
            list[KnowledgeChangeReviewArtifact]
            | tuple[KnowledgeChangeReviewArtifact, ...]
            | None
        ),
    ) -> tuple[KnowledgeChangeReviewArtifact, ...]:
        if knowledge_reviews is None:
            source: list[KnowledgeChangeReviewArtifact] | tuple[KnowledgeChangeReviewArtifact, ...] = ()
        elif type(knowledge_reviews) not in (list, tuple):
            raise TypeError("knowledge_reviews must be an exact list or tuple")
        else:
            source = knowledge_reviews
        if len(source) > self.limits.maximum_knowledge_review_artifacts:
            raise ValueError("knowledge_reviews exceeds artifact limit")
        snapshot = tuple(source)
        identities: set[str] = set()
        for artifact in snapshot:
            if type(artifact) is not KnowledgeChangeReviewArtifact:
                raise TypeError("knowledge_reviews entries must be exact KnowledgeChangeReviewArtifact")
            identity = artifact.review_artifact_identity
            if identity in identities:
                raise ValueError("duplicate review_artifact_identity")
            identities.add(identity)
        return tuple(sorted(snapshot, key=lambda artifact: artifact.review_artifact_identity))

    def produce_knowledge_review(
        self,
        proposal: KnowledgeChangeProposal,
        validation_result: ValidationResult,
        current_state: CurrentKnowledgeState,
    ) -> KnowledgeChangeReviewArtifact:
        """Produce and retain one real e9b artifact for trusted in-process callers."""
        if type(proposal) is not KnowledgeChangeProposal:
            raise TypeError("proposal must be the exact KnowledgeChangeProposal type")
        if type(validation_result) is not ValidationResult:
            raise TypeError("validation_result must be the exact ValidationResult type")
        if type(current_state) is not CurrentKnowledgeState:
            raise TypeError("current_state must be the exact CurrentKnowledgeState type")

        artifact = analyze_review(proposal, validation_result, current_state)
        if type(artifact) is not KnowledgeChangeReviewArtifact:
            raise TypeError("analyze_review must return the exact KnowledgeChangeReviewArtifact type")

        with self._knowledge_review_lock:
            existing = next(
                (
                    candidate
                    for candidate in self._knowledge_reviews
                    if candidate.review_artifact_identity == artifact.review_artifact_identity
                ),
                None,
            )
            if existing is not None:
                if existing == artifact:
                    return existing
                raise ValueError("review_artifact_identity collision with unequal artifact")
            if len(self._knowledge_reviews) >= self.limits.maximum_knowledge_review_artifacts:
                raise ValueError("knowledge review artifact limit reached")
            self._knowledge_reviews = tuple(
                sorted(
                    (*self._knowledge_reviews, artifact),
                    key=lambda candidate: candidate.review_artifact_identity,
                )
            )
            return artifact

    def _list_knowledge_reviews(
        self,
        payload: Mapping[str, Any],
    ) -> ControlPlaneDispatchResult:
        offset = int(payload["offset"])
        limit = int(payload["limit"])
        if offset > self.limits.maximum_knowledge_review_artifacts:
            raise ControlPlaneError("invalid_payload", "invalid_offset")
        if limit > self.limits.maximum_knowledge_review_page_size:
            raise ControlPlaneError("invalid_payload", "invalid_limit")
        with self._knowledge_review_lock:
            review_snapshot = self._knowledge_reviews
        total_count = len(review_snapshot)
        selected = review_snapshot[offset:offset + limit]
        try:
            items = [
                materialize_json_value(project_knowledge_change_review_summary(artifact))
                for artifact in selected
            ]
        except ProjectionRejected as exc:
            self._raise_projection_error(exc)
        returned_count = len(items)
        next_offset_value = offset + returned_count
        truncated = next_offset_value < total_count
        response = {
            "contract": KNOWLEDGE_REVIEW_LIST_CONTRACT,
            "source": KNOWLEDGE_REVIEW_SOURCE,
            "fixture": False,
            "offset": offset,
            "limit": limit,
            "total_count": total_count,
            "returned_count": returned_count,
            "truncated": truncated,
            "next_offset": next_offset_value if truncated else None,
            "items": items,
        }
        return self._result((), response)

    def _get_knowledge_review(
        self,
        review_artifact_identity: str,
    ) -> ControlPlaneDispatchResult:
        with self._knowledge_review_lock:
            review_snapshot = self._knowledge_reviews
        artifact = next(
            (
                candidate
                for candidate in review_snapshot
                if candidate.review_artifact_identity == review_artifact_identity
            ),
            None,
        )
        if artifact is None:
            raise ControlPlaneError("request_not_found", "knowledge review artifact was not found")
        try:
            projection = materialize_json_value(project_knowledge_change_review(artifact))
        except ProjectionRejected as exc:
            self._raise_projection_error(exc)
        return self._result(
            (),
            {
                "contract": KNOWLEDGE_REVIEW_GET_CONTRACT,
                "source": KNOWLEDGE_REVIEW_SOURCE,
                "fixture": False,
                "projection": projection,
            },
        )

    def _knowledge_review_snapshot(self, *, refresh: bool) -> ControlPlaneDispatchResult:
        adapter_status, refresh_error_code = self._knowledge_adapter_status(refresh=refresh)
        current_revision = adapter_status.get("vault_revision")
        if type(current_revision) is not str or VAULT_REVISION_RE.fullmatch(current_revision) is None:
            current_revision = None
        adapter_state = adapter_status.get("state")
        if type(adapter_state) is not str:
            adapter_state = "NOT_CONFIGURED"
        last_error_code = adapter_status.get("last_error_code")
        if type(last_error_code) is not str:
            last_error_code = refresh_error_code

        with self._knowledge_review_lock:
            review_snapshot = self._knowledge_reviews
            decision_snapshot = tuple(self._knowledge_review_decisions.values())

        review_states: list[dict[str, Any]] = []
        stale_count = 0
        blocked_count = 0
        for artifact in review_snapshot:
            stale = (
                artifact.observed_vault_revision != current_revision
                if current_revision is not None
                else None
            )
            if stale is True:
                stale_count += 1
            if artifact.status is ReviewStatus.BLOCKED:
                blocked_count += 1
            review_states.append(
                {
                    "review_artifact_identity": artifact.review_artifact_identity,
                    "status": artifact.status.value,
                    "stale": stale,
                }
            )

        contract = (
            KNOWLEDGE_REVIEW_REFRESH_CONTRACT
            if refresh
            else KNOWLEDGE_REVIEW_SNAPSHOT_CONTRACT
        )
        return self._result(
            (),
            {
                "contract": contract,
                "command_center_version": KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION,
                "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
                "sidecar_runtime_version": SIDECAR_RUNTIME_VERSION,
                "source": KNOWLEDGE_REVIEW_SOURCE,
                "fixture": False,
                "refresh_requested": refresh,
                "refresh_succeeded": refresh and refresh_error_code is None,
                "current_vault_revision": current_revision,
                "freshness_known": current_revision is not None,
                "knowledge_state": _bounded_text(adapter_state, 64),
                "last_error_code": (
                    _bounded_text(last_error_code, 64)
                    if type(last_error_code) is str
                    else None
                ),
                "inbox_count": len(review_snapshot),
                "stale_count": stale_count,
                "blocked_count": blocked_count,
                "session_decision_count": len(decision_snapshot),
                "review_states": review_states,
                "hard_stop": True,
                "persistence": False,
                "vault_write_authority": False,
                "publication_authority": False,
            },
        )

    def _knowledge_adapter_status(
        self,
        *,
        refresh: bool,
    ) -> tuple[dict[str, Any], str | None]:
        adapter = self._knowledge_adapter
        if adapter is None:
            return (
                {
                    "state": "NOT_CONFIGURED",
                    "vault_revision": None,
                    "last_error_code": "KNOWLEDGE_NOT_CONFIGURED",
                },
                "KNOWLEDGE_NOT_CONFIGURED" if refresh else None,
            )

        refresh_error_code: str | None = None
        if refresh:
            refresh_method = getattr(adapter, "refresh", None)
            if not callable(refresh_method):
                refresh_error_code = "KNOWLEDGE_REFRESH_UNAVAILABLE"
            else:
                try:
                    refresh_method()
                except KnowledgeAdapterError as exc:
                    refresh_error_code = exc.code.value
                except Exception:
                    refresh_error_code = "KNOWLEDGE_REFRESH_FAILED"

        status_method = getattr(adapter, "status", None)
        if not callable(status_method):
            return (
                {
                    "state": "ERROR",
                    "vault_revision": None,
                    "last_error_code": refresh_error_code or "KNOWLEDGE_STATUS_UNAVAILABLE",
                },
                refresh_error_code or "KNOWLEDGE_STATUS_UNAVAILABLE",
            )
        try:
            value = status_method()
        except Exception:
            return (
                {
                    "state": "ERROR",
                    "vault_revision": None,
                    "last_error_code": refresh_error_code or "KNOWLEDGE_STATUS_FAILED",
                },
                refresh_error_code or "KNOWLEDGE_STATUS_FAILED",
            )
        if not isinstance(value, Mapping):
            return (
                {
                    "state": "ERROR",
                    "vault_revision": None,
                    "last_error_code": refresh_error_code or "KNOWLEDGE_STATUS_INVALID",
                },
                refresh_error_code or "KNOWLEDGE_STATUS_INVALID",
            )
        return dict(value), refresh_error_code

    def _fresh_knowledge_vault_revision(self) -> str:
        """Refresh the read-only adapter and return the newly observed Vault revision."""
        adapter = self._knowledge_adapter
        if adapter is None:
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision observation is unavailable",
            )
        refresh_method = getattr(adapter, "refresh", None)
        if not callable(refresh_method):
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision observation is unavailable",
            )
        try:
            refresh_result = refresh_method()
        except KnowledgeAdapterError as exc:
            raise ControlPlaneError(
                "sidecar_unavailable",
                f"fresh Vault revision observation failed: {exc.code.value}",
            ) from None
        except Exception:
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision observation failed",
            ) from None
        if not isinstance(refresh_result, Mapping):
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision observation returned an invalid result",
            )
        revision = refresh_result.get("current_revision")
        if type(revision) is not str or VAULT_REVISION_RE.fullmatch(revision) is None:
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision is unavailable for a human review decision",
            )
        return revision

    def _require_knowledge_review_artifact(
        self,
        review_artifact_identity: str,
    ) -> KnowledgeChangeReviewArtifact:
        with self._knowledge_review_lock:
            artifact = next(
                (
                    candidate
                    for candidate in self._knowledge_reviews
                    if candidate.review_artifact_identity == review_artifact_identity
                ),
                None,
            )
        if artifact is None:
            raise ControlPlaneError(
                "request_not_found",
                "knowledge review artifact was not found",
            )
        return artifact

    def _create_knowledge_review_decision(
        self,
        payload: Mapping[str, Any],
    ) -> ControlPlaneDispatchResult:
        review_artifact_identity = str(payload["review_artifact_identity"])
        artifact = self._require_knowledge_review_artifact(review_artifact_identity)
        if payload["review_contract_version"] != artifact.contract_version:
            raise ControlPlaneError(
                "invalid_payload",
                "knowledge review contract binding mismatch",
            )

        try:
            actor = HumanReviewerMetadata(
                actor_identifier=str(payload["actor_identifier"]),
                display_name=str(payload["actor_display_name"]),
                source=str(payload["actor_source"]),
            )
        except (TypeError, ValueError):
            raise ControlPlaneError(
                "invalid_payload",
                "human reviewer metadata is invalid",
            ) from None

        current_revision = self._fresh_knowledge_vault_revision()
        try:
            decision = create_human_review_decision(
                artifact,
                expected_proposal_id=str(payload["proposal_id"]),
                expected_review_artifact_identity=review_artifact_identity,
                expected_change_identity=payload["change_identity"],
                expected_observed_vault_revision=str(payload["observed_vault_revision"]),
                current_observed_vault_revision=current_revision,
                decision=str(payload["decision"]),
                comment=str(payload["comment"]),
                actor=actor,
            )
        except HumanReviewDecisionRejected as exc:
            code = exc.code.value
            policy_codes = {
                "BLOCKED_APPROVAL_FORBIDDEN",
                "APPROVAL_REQUIRES_CHANGE_IDENTITY",
                "STALE_CURRENT_VAULT_REVISION",
            }
            raise ControlPlaneError(
                "policy_blocked" if code in policy_codes else "invalid_payload",
                f"human review decision rejected: {code}",
            ) from None

        try:
            projection = materialize_json_value(project_human_review_decision(decision))
        except ProjectionRejected as exc:
            self._raise_projection_error(exc)

        with self._knowledge_review_lock:
            existing = self._knowledge_review_decisions.get(decision.decision_identity)
            duplicate = existing is not None
            if existing is not None and existing != decision:
                raise ControlPlaneError(
                    "internal_error",
                    "human review decision identity collision",
                )
            if existing is None:
                if (
                    len(self._knowledge_review_decisions)
                    >= self.limits.maximum_knowledge_review_decisions
                ):
                    raise ControlPlaneError(
                        "busy",
                        "human review decision session capacity is full",
                    )
                self._knowledge_review_decisions[decision.decision_identity] = decision

        return self._result(
            (),
            {
                "contract": KNOWLEDGE_REVIEW_DECISION_CREATE_CONTRACT,
                "command_center_version": KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION,
                "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
                "sidecar_runtime_version": SIDECAR_RUNTIME_VERSION,
                "source": KNOWLEDGE_REVIEW_SOURCE,
                "fixture": False,
                "duplicate": duplicate,
                "current_vault_revision": current_revision,
                "decision": projection,
                "hard_stop": True,
                "vault_modified": False,
                "persistence": False,
                "publication": False,
            },
        )

    @staticmethod
    def _raise_projection_error(error: ProjectionRejected) -> None:
        if error.code is ProjectionRejectionCode.PROJECTION_JSON_LIMIT_EXCEEDED:
            raise ControlPlaneError(
                "payload_too_large",
                "knowledge review projection exceeds the response bound",
            ) from None
        raise ControlPlaneError(
            "internal_error",
            "knowledge review projection failed",
        ) from None

    def bootstrap_snapshot(self) -> dict[str, Any]:
        snapshot = self.status_snapshot()
        snapshot["capabilities"] = list(CONTROL_PLANE_METHODS)
        snapshot["persistence"] = False
        snapshot["models_connected"] = False
        snapshot["provider_registry_available"] = False
        snapshot["harness_registry_available"] = False
        return snapshot

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "protocol": IPC_PROTOCOL,
            "protocol_version": IPC_PROTOCOL_VERSION,
            "sidecar_runtime_version": SIDECAR_RUNTIME_VERSION,
            "capabilities": list(CONTROL_PLANE_METHODS),
            "limits": {
                "maximum_sessions": self.limits.maximum_sessions,
                "maximum_threads_per_session": self.limits.maximum_threads_per_session,
                "maximum_turns_per_thread": self.limits.maximum_turns_per_thread,
                "maximum_prompt_characters": self.limits.maximum_prompt_characters,
                "maximum_events_per_request": self.limits.maximum_events_per_request,
                "maximum_knowledge_review_artifacts": self.limits.maximum_knowledge_review_artifacts,
                "maximum_knowledge_review_page_size": self.limits.maximum_knowledge_review_page_size,
                "maximum_knowledge_review_decisions": self.limits.maximum_knowledge_review_decisions,
            },
            "counts": self._counts(),
            "sidecar_ready": True,
            "persistence": False,
            "models_connected": False,
            "provider_registry_available": False,
            "harness_registry_available": False,
        }

    def begin_knowledge_context(
        self,
        *,
        query: str,
        intent: QueryIntent | str = QueryIntent.AUTO,
        max_context_chars: int = DEFAULT_CONTEXT_CHARS,
        max_results: int = DEFAULT_MAX_RESULTS,
        include_superseded: bool = False,
        turn_id: str | None = None,
        request_id: str | None = None,
    ) -> ControlPlaneDispatchResult:
        lifecycle_id = request_id if request_id is not None else self._knowledge_request_id_factory()
        try:
            request = KnowledgeContextRequest(
                request_id=lifecycle_id,
                query=query,
                intent=intent,
                max_context_chars=max_context_chars,
                max_results=max_results,
                include_superseded=include_superseded,
                turn_id=turn_id,
            )
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "CONTRACT_VALIDATION_ERROR",
                "knowledge context request failed contract validation",
            ) from exc
        if request.request_id in self._knowledge_requests:
            raise ControlPlaneError(
                "KNOWLEDGE_REQUEST_DUPLICATE",
                "knowledge context request identity already exists",
            )
        if request.turn_id is not None and request.turn_id not in self._turns:
            raise ControlPlaneError(
                "KNOWLEDGE_TURN_NOT_FOUND",
                "knowledge context Turn was not found",
            )
        requested = KnowledgeContextResult(
            request_id=request.request_id,
            turn_id=request.turn_id,
            state=KnowledgeContextState.REQUESTED,
        )
        record = _KnowledgeContextRecord(
            request=request,
            result=requested,
            lifecycle=[KnowledgeContextState.REQUESTED],
        )
        self._knowledge_requests[request.request_id] = record
        if request.turn_id is not None:
            turn = self._turns[request.turn_id]
            turn.knowledge_request_id = request.request_id
            self._turn_current_knowledge_request[request.turn_id] = request.request_id
        event = self._knowledge_event(record, "knowledge.context.requested")
        return self._result((event,), self._knowledge_record_snapshot(record))

    def retrieve_knowledge_context(self, request_id: str) -> ControlPlaneDispatchResult:
        record = self._require_knowledge_request(request_id)
        if record.result.state in {KnowledgeContextState.READY, KnowledgeContextState.FAILED}:
            return self._result((), self._knowledge_record_snapshot(record))
        if record.result.state is not KnowledgeContextState.REQUESTED:
            raise ControlPlaneError(
                "KNOWLEDGE_REQUEST_DUPLICATE",
                "knowledge context retrieval is already in progress",
            )
        record.result = KnowledgeContextResult(
            request_id=record.request.request_id,
            turn_id=record.request.turn_id,
            state=KnowledgeContextState.RETRIEVING,
        )
        record.lifecycle.append(KnowledgeContextState.RETRIEVING)
        try:
            if self._knowledge_adapter is None:
                raise KnowledgeAdapterError(
                    code=KnowledgeErrorCode.KNOWLEDGE_NOT_CONFIGURED,
                    message="KnowledgeAdapter is not configured.",
                )
            adapter_result = self._knowledge_adapter.context_preview(
                record.request.query,
                record.request.intent,
                max_context_chars=record.request.max_context_chars,
                max_results=record.request.max_results,
                include_superseded=record.request.include_superseded,
            )
            if record.request.turn_id is not None and (
                self._turn_current_knowledge_request.get(record.request.turn_id)
                != record.request.request_id
            ):
                return self._fail_knowledge_context(
                    record,
                    "KNOWLEDGE_STALE_RESULT",
                    "stale knowledge context result was rejected",
                )
            ready = self._ready_knowledge_result(record.request, adapter_result)
        except KnowledgeAdapterError as exc:
            return self._fail_knowledge_context(record, exc.code.value, exc.message)
        except (TypeError, ValueError, KeyError) as exc:
            return self._fail_knowledge_context(
                record,
                "CONTRACT_VALIDATION_ERROR",
                "KnowledgeAdapter result failed contract validation.",
            )
        except Exception:
            return self._fail_knowledge_context(
                record,
                "KNOWLEDGE_INTERNAL_ERROR",
                "Knowledge context retrieval failed safely.",
            )
        record.result = ready
        record.lifecycle.append(KnowledgeContextState.READY)
        if record.request.turn_id is not None:
            self._turns[record.request.turn_id].knowledge_context = ready
        event = self._knowledge_event(record, "knowledge.context.ready")
        return self._result((event,), self._knowledge_record_snapshot(record))

    def request_knowledge_context(
        self,
        *,
        query: str,
        intent: QueryIntent | str = QueryIntent.AUTO,
        max_context_chars: int = DEFAULT_CONTEXT_CHARS,
        max_results: int = DEFAULT_MAX_RESULTS,
        include_superseded: bool = False,
        turn_id: str | None = None,
        request_id: str | None = None,
    ) -> ControlPlaneDispatchResult:
        requested = self.begin_knowledge_context(
            query=query,
            intent=intent,
            max_context_chars=max_context_chars,
            max_results=max_results,
            include_superseded=include_superseded,
            turn_id=turn_id,
            request_id=request_id,
        )
        lifecycle_id = str(requested.response["request_id"])
        terminal = self.retrieve_knowledge_context(lifecycle_id)
        return self._result(requested.events + terminal.events, terminal.response)

    def knowledge_context_status(self, request_id: str) -> dict[str, Any]:
        return self._knowledge_record_snapshot(self._require_knowledge_request(request_id))

    def turn_knowledge_context(self, turn_id: str) -> dict[str, Any] | None:
        if turn_id not in self._turns:
            raise ControlPlaneError("KNOWLEDGE_TURN_NOT_FOUND", "knowledge context Turn was not found")
        result = self._turns[turn_id].knowledge_context
        return result.to_dict() if result is not None else None

    def desktop_knowledge_preview(
        self,
        *,
        turn_id: str,
        intent: QueryIntent | str,
        max_context_chars: int,
        max_results: int,
    ) -> dict[str, Any]:
        """Trusted desktop preview derived only from the existing Turn prompt."""
        if turn_id not in self._turns:
            raise ControlPlaneError("KNOWLEDGE_TURN_NOT_FOUND", "knowledge preview Turn was not found")
        turn = self._turns[turn_id]
        if turn.state != "RUNNING" or not turn.prompt_text:
            raise ControlPlaneError("KNOWLEDGE_TURN_MISMATCH", "knowledge preview requires a pending Turn")
        requested = self.request_knowledge_context(
            query=turn.prompt_text,
            intent=intent,
            max_context_chars=max_context_chars,
            max_results=max_results,
            turn_id=turn_id,
        )
        if requested.response.get("state") != KnowledgeContextState.READY.value:
            error = requested.response.get("error")
            return {
                "state": KnowledgeInjectionState.FAILED.value,
                "turn_id": turn_id,
                "request_id": requested.response.get("request_id"),
                "injection_id": None,
                "error": dict(error) if isinstance(error, Mapping) else {
                    "code": "KNOWLEDGE_PREVIEW_FAILED",
                    "safe_message": "Project knowledge preview failed safely.",
                },
                "model_dispatched": False,
                "tools_executed": 0,
            }
        prepared = self.prepare_knowledge_injection(
            turn_id,
            str(requested.response["request_id"]),
        )
        record = self._require_knowledge_injection(str(prepared.response["injection_id"]))
        knowledge_record = self._require_knowledge_request(record.envelope.request_id)
        return self._desktop_preview_snapshot(record, knowledge_record.result)

    def desktop_knowledge_decide(
        self,
        *,
        turn_id: str,
        injection_id: str,
        expected_preview_hash: str,
        action: str,
        model_gateway: Any,
        emit_model_event: Callable[[str, str, int, Mapping[str, Any]], None],
    ) -> dict[str, Any]:
        """Trusted desktop-only USER_APPROVAL decision with atomic dispatch."""
        if action not in DESKTOP_KNOWLEDGE_ACTIONS:
            raise ControlPlaneError("KNOWLEDGE_ACTION_INVALID", "desktop knowledge action is invalid")
        with self._knowledge_injection_lock:
            existing = self._desktop_knowledge_receipts.get(injection_id)
            if existing is not None:
                if (
                    existing.turn_id != turn_id
                    or existing.action != action
                    or existing.preview_hash != expected_preview_hash
                ):
                    return self._desktop_stale_response(
                        turn_id=turn_id,
                        injection_id=injection_id,
                        code="KNOWLEDGE_INJECTION_DUPLICATE_ACTION",
                    )
                current = self._knowledge_injections.get(injection_id)
                response = existing.to_dict(duplicate=True)
                if current is not None and current.envelope.state is KnowledgeInjectionState.INJECTED:
                    response["state"] = KnowledgeInjectionState.INJECTED.value
                return response
            if injection_id in self._desktop_knowledge_in_flight:
                return {
                    "state": "DECIDING",
                    "turn_id": turn_id,
                    "injection_id": injection_id,
                    "action": action,
                    "model_dispatched": False,
                    "duplicate": True,
                }
            record = self._require_knowledge_injection(injection_id)
            try:
                self._validate_desktop_decision_identity(
                    record,
                    turn_id=turn_id,
                    expected_preview_hash=expected_preview_hash,
                )
                if action != "CANCEL":
                    self._validate_injection_current(record, turn_id)
            except KnowledgeInjectionContractError as exc:
                self._fail_knowledge_injection(record, exc, None)
                return self._desktop_stale_response(
                    turn_id=turn_id,
                    injection_id=injection_id,
                    code=exc.code,
                )
            self._desktop_knowledge_in_flight.add(injection_id)
            try:
                gateway_payload: Mapping[str, Any] | None = None
                if action != "CANCEL":
                    gateway_payload = model_gateway.bound_turn_payload(self._turns[turn_id].prompt_text)
                decision = (
                    KnowledgeInjectionDecision.INCLUDE
                    if action == "INCLUDE_AND_SEND"
                    else KnowledgeInjectionDecision.REJECT
                )
                try:
                    envelope = decide_envelope(
                        record.envelope,
                        decision=decision,
                        expected_preview_hash=expected_preview_hash,
                        decision_source=KnowledgeInjectionDecisionSource.USER_APPROVAL,
                    )
                except KnowledgeInjectionContractError as exc:
                    self._fail_knowledge_injection(record, exc, None)
                    return self._desktop_stale_response(
                        turn_id=turn_id,
                        injection_id=injection_id,
                        code=exc.code,
                    )
                record = replace(
                    record,
                    envelope=envelope,
                    lifecycle=record.lifecycle + (envelope.state,),
                )
                event_method = (
                    "knowledge.injection.approved"
                    if envelope.state is KnowledgeInjectionState.APPROVED
                    else "knowledge.injection.rejected"
                )
                _, record = self._injection_event(record, event_method)
                if action == "CANCEL":
                    self._finish_pending_turn_without_model(turn_id, "CANCELLED")
                    receipt = _DesktopKnowledgeDecisionReceipt(
                        injection_id=injection_id,
                        turn_id=turn_id,
                        action=action,
                        preview_hash=expected_preview_hash,
                        state=KnowledgeInjectionState.REJECTED.value,
                        model_turn_id=None,
                        model_dispatched=False,
                        knowledge_included=False,
                    )
                    self._desktop_knowledge_receipts[injection_id] = receipt
                    return receipt.to_dict()

                assert gateway_payload is not None

                def tracked_emit(
                    method: str,
                    model_turn_id: str,
                    sequence: int,
                    payload: Mapping[str, Any],
                ) -> None:
                    self._observe_model_event(turn_id, method, payload)
                    emit_model_event(method, model_turn_id, sequence, payload)

                if action == "INCLUDE_AND_SEND":
                    started = self.dispatch_approved_knowledge_turn(
                        injection_id,
                        model_gateway,
                        gateway_payload,
                        tracked_emit,
                        turn_id=turn_id,
                    )
                    state = "DISPATCHING"
                    knowledge_included = True
                else:
                    started = model_gateway.start_turn(gateway_payload, tracked_emit)
                    state = KnowledgeInjectionState.REJECTED.value
                    knowledge_included = False
                receipt = _DesktopKnowledgeDecisionReceipt(
                    injection_id=injection_id,
                    turn_id=turn_id,
                    action=action,
                    preview_hash=expected_preview_hash,
                    state=state,
                    model_turn_id=str(started["turn_id"]),
                    model_dispatched=True,
                    knowledge_included=knowledge_included,
                )
                self._desktop_knowledge_receipts[injection_id] = receipt
                return receipt.to_dict()
            finally:
                self._desktop_knowledge_in_flight.discard(injection_id)

    @staticmethod
    def _desktop_preview_snapshot(
        record: KnowledgeInjectionRecord,
        result: KnowledgeContextResult,
    ) -> dict[str, Any]:
        envelope = record.envelope
        sources: list[dict[str, Any]] = []
        for source_index, source in enumerate(result.sources):
            sections: list[dict[str, Any]] = []
            envelope_source = envelope.sources[source_index]
            for section_index, section in enumerate(source["selected_sections"]):
                content = section["content"]
                expected_hash = envelope_source["selected_sections"][section_index]["content_sha256"]
                actual_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
                if actual_hash != expected_hash:
                    raise ControlPlaneError(
                        "KNOWLEDGE_INJECTION_CONTEXT_MISMATCH",
                        "knowledge preview content does not match the prepared envelope",
                    )
                sections.append(
                    {
                        "heading": section["heading"],
                        "line_start": section["line_start"],
                        "line_end": section["line_end"],
                        "content": content,
                    }
                )
            sources.append(
                {
                    "note_id": source["note_id"],
                    "title": source.get("title", ""),
                    "relative_path": source["relative_path"],
                    "knowledge_layer": source["knowledge_layer"],
                    "evidence_class": source["evidence_class"],
                    "authority": source["authority"],
                    "status": source["status"],
                    "canonical": source["canonical"],
                    "selected_sections": sections,
                }
            )
        return {
            "state": envelope.state.value,
            "turn_id": envelope.turn_id,
            "request_id": envelope.request_id,
            "injection_id": envelope.injection_id,
            "bundle_id": envelope.bundle_id,
            "preview_hash": envelope.preview_hash,
            "vault_revision": envelope.vault_revision,
            "resolved_intent": envelope.resolved_intent.value,
            "source_count": envelope.source_count,
            "total_chars": envelope.total_chars,
            "truncated": envelope.truncated,
            "sources": sources,
            "model_dispatched": False,
            "tools_executed": 0,
        }

    @staticmethod
    def _desktop_stale_response(*, turn_id: str, injection_id: str, code: str) -> dict[str, Any]:
        return {
            "state": "STALE",
            "turn_id": turn_id,
            "injection_id": injection_id,
            "error": {
                "code": code,
                "safe_message": "Project knowledge changed. Refresh the preview.",
            },
            "model_dispatched": False,
            "tools_executed": 0,
        }

    @staticmethod
    def _validate_desktop_decision_identity(
        record: KnowledgeInjectionRecord,
        *,
        turn_id: str,
        expected_preview_hash: str,
    ) -> None:
        verify_envelope_integrity(record.envelope)
        if record.envelope.state is not KnowledgeInjectionState.PREVIEW_READY:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_STATE_INVALID",
                "knowledge preview is no longer pending a decision",
            )
        if record.envelope.turn_id != turn_id:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_MISMATCH",
                "knowledge preview belongs to a different Turn",
            )
        if record.envelope.preview_hash != expected_preview_hash:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_PREVIEW_MISMATCH",
                "knowledge preview hash does not match",
            )

    def _finish_pending_turn_without_model(self, turn_id: str, state: str) -> None:
        turn = self._turns[turn_id]
        turn.state = state
        thread = self._threads[turn.thread_id]
        if thread.active_turn_id == turn_id:
            thread.active_turn_id = None

    def _observe_model_event(
        self,
        control_plane_turn_id: str,
        method: str,
        payload: Mapping[str, Any],
    ) -> None:
        with self._knowledge_injection_lock:
            turn = self._turns.get(control_plane_turn_id)
            if turn is None:
                return
            if method == "model.turn.started":
                turn.model_called = payload.get("model_called") is True
            elif method == "model.turn.completed":
                turn.model_called = payload.get("model_called") is True
                self._finish_pending_turn_without_model(control_plane_turn_id, "COMPLETED")
            elif method == "model.turn.cancelled":
                turn.model_called = payload.get("model_called") is True
                self._finish_pending_turn_without_model(control_plane_turn_id, "CANCELLED")
            elif method in {"model.turn.timed_out", "model.turn.failed"}:
                turn.model_called = payload.get("model_called") is True
                self._finish_pending_turn_without_model(control_plane_turn_id, "FAILED")

    def prepare_knowledge_injection(
        self,
        turn_id: str,
        knowledge_request_id: str,
        *,
        injection_id: str | None = None,
    ) -> ControlPlaneDispatchResult:
        """Prepare an exact preview without causing tools, network, or model calls."""
        with self._knowledge_injection_lock:
            if turn_id not in self._turns:
                raise ControlPlaneError("KNOWLEDGE_TURN_NOT_FOUND", "knowledge injection Turn was not found")
            knowledge_record = self._require_knowledge_request(knowledge_request_id)
            if knowledge_record.result.state is not KnowledgeContextState.READY:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_NOT_READY",
                    "knowledge context must be READY before injection preparation",
                )
            if knowledge_record.request.turn_id != turn_id:
                raise ControlPlaneError("KNOWLEDGE_TURN_MISMATCH", "knowledge request belongs to a different Turn")
            if self._turn_current_knowledge_request.get(turn_id) != knowledge_request_id:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_STALE_REQUEST",
                    "knowledge request is no longer current for the Turn",
                )
            lifecycle_id = injection_id if injection_id is not None else self._knowledge_injection_id_factory()
            if lifecycle_id in self._knowledge_injections:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_DUPLICATE",
                    "knowledge injection identity already exists",
                )
            try:
                envelope = prepare_injection_envelope(
                    injection_id=lifecycle_id,
                    turn_id=turn_id,
                    knowledge_result=knowledge_record.result,
                )
                preview = KnowledgeInjectionPreview.from_envelope(envelope)
                record = KnowledgeInjectionRecord(
                    envelope=envelope,
                    preview=preview,
                    lifecycle=(KnowledgeInjectionState.PREVIEW_READY,),
                )
            except KnowledgeInjectionContractError as exc:
                raise ControlPlaneError(exc.code, exc.safe_message) from exc
            except (TypeError, ValueError, KeyError) as exc:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_CONTRACT_INVALID",
                    "knowledge injection preview failed contract validation",
                ) from exc
            self._knowledge_injections[envelope.injection_id] = record
            event, record = self._injection_event(record, "knowledge.injection.preview_ready")
            return self._result((event,), record.to_dict())

    def decide_knowledge_injection(
        self,
        injection_id: str,
        decision: KnowledgeInjectionDecision | str,
        expected_preview_hash: str,
        decision_source: KnowledgeInjectionDecisionSource | str,
    ) -> ControlPlaneDispatchResult:
        """Apply an explicit decision to the exact prepared preview."""
        try:
            normalized_source = KnowledgeInjectionDecisionSource(decision_source)
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "KNOWLEDGE_INJECTION_DECISION_INVALID",
                "knowledge injection decision source is invalid",
            ) from exc
        if normalized_source is not KnowledgeInjectionDecisionSource.INTERNAL_EXPLICIT_CALL:
            raise ControlPlaneError(
                "KNOWLEDGE_INJECTION_DECISION_SOURCE_FORBIDDEN",
                "USER_APPROVAL is reserved for the trusted desktop decision command",
            )
        with self._knowledge_injection_lock:
            record = self._require_knowledge_injection(injection_id)
            if record.envelope.state is not KnowledgeInjectionState.PREVIEW_READY:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_STATE_INVALID",
                    "knowledge injection decision requires PREVIEW_READY state",
                )
            try:
                normalized_decision = KnowledgeInjectionDecision(decision)
            except (TypeError, ValueError) as exc:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_DECISION_INVALID",
                    "knowledge injection decision is invalid",
                ) from exc
            if normalized_decision is KnowledgeInjectionDecision.INCLUDE:
                try:
                    self._validate_injection_current(record, record.envelope.turn_id)
                except KnowledgeInjectionContractError as exc:
                    return self._fail_knowledge_injection(record, exc, None)
            try:
                envelope = decide_envelope(
                    record.envelope,
                    decision=normalized_decision,
                    expected_preview_hash=expected_preview_hash,
                    decision_source=normalized_source,
                )
            except KnowledgeInjectionContractError as exc:
                return self._fail_knowledge_injection(record, exc, None)
            record = replace(
                record,
                envelope=envelope,
                lifecycle=record.lifecycle + (envelope.state,),
            )
            method = (
                "knowledge.injection.approved"
                if envelope.state is KnowledgeInjectionState.APPROVED
                else "knowledge.injection.rejected"
            )
            event, record = self._injection_event(record, method)
            return self._result((event,), record.to_dict(include_serialized_context=False))

    def knowledge_injection_status(
        self,
        injection_id: str,
        *,
        include_serialized_context: bool = False,
    ) -> dict[str, Any]:
        with self._knowledge_injection_lock:
            return self._require_knowledge_injection(injection_id).to_dict(
                include_serialized_context=include_serialized_context
            )

    def dispatch_approved_knowledge_turn(
        self,
        injection_id: str,
        model_gateway: Any,
        gateway_payload: Mapping[str, Any],
        emit_model_event: Callable[[str, str, int, Mapping[str, Any]], None],
        *,
        turn_id: str | None = None,
        emit_injection_event: Callable[[ControlPlaneEvent], None] | None = None,
    ) -> dict[str, Any]:
        """Dispatch through the existing gateway without exposing Adapter or Vault access."""
        with self._knowledge_injection_lock:
            record = self._require_knowledge_injection(injection_id)
            expected_turn_id = turn_id if turn_id is not None else record.envelope.turn_id
            if record.envelope.state is not KnowledgeInjectionState.APPROVED:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_NOT_APPROVED",
                    "knowledge injection envelope is not APPROVED",
                )
            try:
                self._validate_injection_current(record, expected_turn_id)
                self._validate_gateway_prompt(expected_turn_id, gateway_payload)
            except KnowledgeInjectionContractError as exc:
                failure = self._fail_knowledge_injection(record, exc, emit_injection_event)
                raise ControlPlaneError(exc.code, exc.safe_message, details=failure.response) from exc

        def before_outbound(messages: tuple[dict[str, str], ...]) -> None:
            with self._knowledge_injection_lock:
                current = self._require_knowledge_injection(injection_id)
                try:
                    self._validate_injection_current(current, expected_turn_id)
                    verify_provider_messages(
                        messages,
                        current.envelope,
                        expected_turn_id=expected_turn_id,
                    )
                except (ControlPlaneError, KnowledgeInjectionContractError) as exc:
                    if isinstance(exc, ControlPlaneError):
                        contract_error = KnowledgeInjectionContractError(exc.code, exc.message)
                    else:
                        contract_error = exc
                    self._fail_knowledge_injection(current, contract_error, emit_injection_event)
                    raise contract_error

        def after_outbound(messages: tuple[dict[str, str], ...]) -> None:
            with self._knowledge_injection_lock:
                current = self._require_knowledge_injection(injection_id)
                verify_provider_messages(
                    messages,
                    current.envelope,
                    expected_turn_id=expected_turn_id,
                )
                injected = mark_envelope_injected(current.envelope)
                current = replace(
                    current,
                    envelope=injected,
                    lifecycle=current.lifecycle + (KnowledgeInjectionState.INJECTED,),
                )
                event, current = self._injection_event(current, "knowledge.injection.injected")
                if emit_injection_event is not None:
                    emit_injection_event(event)

        try:
            return model_gateway.start_turn_with_knowledge(
                gateway_payload,
                emit_model_event,
                record.envelope,
                control_plane_turn_id=expected_turn_id,
                before_outbound_request=before_outbound,
                after_outbound_request=after_outbound,
            )
        except KnowledgeInjectionContractError as exc:
            with self._knowledge_injection_lock:
                current = self._require_knowledge_injection(injection_id)
                failure = self._fail_knowledge_injection(current, exc, emit_injection_event)
            raise ControlPlaneError(exc.code, exc.safe_message, details=failure.response) from exc

    def _validate_gateway_prompt(self, turn_id: str, gateway_payload: Mapping[str, Any]) -> None:
        if turn_id not in self._turns:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_NOT_FOUND",
                "knowledge injection Turn was not found",
            )
        prompt = gateway_payload.get("prompt")
        if not isinstance(prompt, str):
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_MISMATCH",
                "model request prompt does not match the knowledge Turn",
            )
        normalized = _normalize_prompt(prompt)
        if hashlib.sha256(normalized.encode("utf-8")).hexdigest() != self._turns[turn_id].prompt_sha256:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_MISMATCH",
                "model request prompt does not match the knowledge Turn",
            )

    def _validate_injection_current(
        self,
        record: KnowledgeInjectionRecord,
        expected_turn_id: str,
    ) -> None:
        envelope = record.envelope
        verify_envelope_integrity(envelope)
        if envelope.turn_id != expected_turn_id:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_MISMATCH",
                "knowledge injection envelope belongs to a different Turn",
            )
        if expected_turn_id not in self._turns:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_NOT_FOUND",
                "knowledge injection Turn was not found",
            )
        if self._turn_current_knowledge_request.get(expected_turn_id) != envelope.request_id:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_STALE_REQUEST",
                "knowledge request is no longer current for the Turn",
            )
        knowledge_record = self._knowledge_requests.get(envelope.request_id)
        if (
            knowledge_record is None
            or knowledge_record.result.state is not KnowledgeContextState.READY
            or knowledge_record.request.turn_id != expected_turn_id
            or knowledge_record.result.bundle_id != envelope.bundle_id
        ):
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_STALE_REQUEST",
                "knowledge request is no longer valid for injection",
            )
        current_revision = self._current_adapter_vault_revision()
        if current_revision != envelope.vault_revision:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_STALE",
                "KnowledgeAdapter Vault revision changed after preview",
            )

    def _current_adapter_vault_revision(self) -> str | None:
        if self._knowledge_adapter is None:
            return None
        status = getattr(self._knowledge_adapter, "status", None)
        if not callable(status):
            return None
        try:
            value = status()
        except Exception:
            return None
        if not isinstance(value, Mapping):
            return None
        revision = value.get("vault_revision")
        return revision if isinstance(revision, str) else None

    def _fail_knowledge_injection(
        self,
        record: KnowledgeInjectionRecord,
        error: KnowledgeInjectionContractError,
        event_sink: Callable[[ControlPlaneEvent], None] | None,
    ) -> ControlPlaneDispatchResult:
        if record.envelope.state is KnowledgeInjectionState.FAILED:
            return self._result((), record.to_dict(include_serialized_context=False))
        failed_envelope = replace(record.envelope, state=KnowledgeInjectionState.FAILED)
        failed = replace(
            record,
            envelope=failed_envelope,
            lifecycle=record.lifecycle + (KnowledgeInjectionState.FAILED,),
            error=KnowledgeInjectionError(
                code=error.code,
                safe_message=_bounded_text(_sanitize_text(error.safe_message), 512),
            ),
        )
        event, failed = self._injection_event(failed, "knowledge.injection.failed")
        if event_sink is not None:
            event_sink(event)
        return self._result((event,), failed.to_dict(include_serialized_context=False))

    def _injection_event(
        self,
        record: KnowledgeInjectionRecord,
        method: str,
    ) -> tuple[ControlPlaneEvent, KnowledgeInjectionRecord]:
        envelope = record.envelope
        payload: dict[str, Any] = {
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "injection_id": envelope.injection_id,
            "request_id": envelope.request_id,
            "turn_id": envelope.turn_id,
            "state": envelope.state.value,
            "bundle_id": envelope.bundle_id,
            "vault_revision": envelope.vault_revision,
            "preview_hash": envelope.preview_hash,
            "context_sha256": envelope.serialized_context_sha256,
            "source_count": envelope.source_count,
        }
        if method == "knowledge.injection.failed" and record.error is not None:
            payload["error_code"] = record.error.code
        event = ControlPlaneEvent(
            method=method,
            sequence=record.next_sequence,
            reply_to=envelope.injection_id,
            payload=payload,
        )
        updated = replace(record, next_sequence=record.next_sequence + 1)
        self._knowledge_injections[envelope.injection_id] = updated
        return event, updated

    def _require_knowledge_injection(self, injection_id: str) -> KnowledgeInjectionRecord:
        if injection_id not in self._knowledge_injections:
            raise ControlPlaneError(
                "KNOWLEDGE_INJECTION_NOT_FOUND",
                "knowledge injection was not found",
            )
        return self._knowledge_injections[injection_id]

    @staticmethod
    def _ready_knowledge_result(
        request: KnowledgeContextRequest,
        adapter_result: Mapping[str, Any],
    ) -> KnowledgeContextResult:
        if not isinstance(adapter_result, Mapping):
            raise ValueError("KnowledgeAdapter context result must be an object")
        sources = adapter_result.get("sources")
        relations = adapter_result.get("context_relations")
        warnings = adapter_result.get("warnings")
        if not isinstance(sources, (list, tuple)):
            raise ValueError("KnowledgeAdapter sources must be a bounded sequence")
        if not isinstance(relations, (list, tuple)):
            raise ValueError("KnowledgeAdapter relations must be a bounded sequence")
        if not isinstance(warnings, (list, tuple)):
            raise ValueError("KnowledgeAdapter warnings must be a bounded sequence")
        return KnowledgeContextResult(
            request_id=request.request_id,
            turn_id=request.turn_id,
            state=KnowledgeContextState.READY,
            vault_revision=adapter_result["vault_revision"],
            bundle_id=adapter_result["bundle_id"],
            resolved_intent=adapter_result["resolved_intent"],
            source_count=len(sources),
            total_chars=adapter_result["total_chars"],
            truncated=adapter_result["truncated"],
            sources=tuple(sources),
            context_relations=tuple(relations),
            warnings=tuple(warnings),
        )

    def _fail_knowledge_context(
        self,
        record: _KnowledgeContextRecord,
        code: str,
        safe_message: str,
    ) -> ControlPlaneDispatchResult:
        error = KnowledgeContextError(
            code=str(code),
            safe_message=_bounded_text(_sanitize_text(str(safe_message)), 512),
        )
        record.result = KnowledgeContextResult(
            request_id=record.request.request_id,
            turn_id=record.request.turn_id,
            state=KnowledgeContextState.FAILED,
            error=error,
        )
        record.lifecycle.append(KnowledgeContextState.FAILED)
        event = self._knowledge_event(record, "knowledge.context.failed")
        return self._result((event,), self._knowledge_record_snapshot(record))

    def _knowledge_event(
        self,
        record: _KnowledgeContextRecord,
        method: str,
    ) -> ControlPlaneEvent:
        payload: dict[str, Any] = {
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "request_id": record.request.request_id,
            "turn_id": record.request.turn_id,
            "state": record.result.state.value,
        }
        if method == "knowledge.context.requested":
            payload["intent"] = record.request.intent.value
        elif method == "knowledge.context.ready":
            payload.update(
                {
                    "bundle_id": record.result.bundle_id,
                    "vault_revision": record.result.vault_revision,
                    "source_count": record.result.source_count,
                    "total_chars": record.result.total_chars,
                    "truncated": record.result.truncated,
                }
            )
        elif method == "knowledge.context.failed":
            assert record.result.error is not None
            payload["error_code"] = record.result.error.code
        else:
            raise ControlPlaneError("internal_error", "unsupported knowledge lifecycle event")
        event = ControlPlaneEvent(
            method=method,
            sequence=record.next_sequence,
            reply_to=record.request.request_id,
            payload=payload,
        )
        record.next_sequence += 1
        return event

    @staticmethod
    def _knowledge_record_snapshot(record: _KnowledgeContextRecord) -> dict[str, Any]:
        return {
            **record.result.to_dict(),
            "request": {
                "request_id": record.request.request_id,
                "turn_id": record.request.turn_id,
                "intent": record.request.intent.value,
                "max_context_chars": record.request.max_context_chars,
                "max_results": record.request.max_results,
                "include_superseded": record.request.include_superseded,
            },
            "lifecycle": [state.value for state in record.lifecycle],
        }

    def _require_knowledge_request(self, request_id: str) -> _KnowledgeContextRecord:
        if request_id not in self._knowledge_requests:
            raise ControlPlaneError(
                "KNOWLEDGE_REQUEST_NOT_FOUND",
                "knowledge context request was not found",
            )
        return self._knowledge_requests[request_id]

    def _create_session(self, payload: Mapping[str, Any], request_id: str) -> ControlPlaneDispatchResult:
        if len(self._sessions) >= self.limits.maximum_sessions:
            raise ControlPlaneError("budget_exceeded", "session limit reached")
        session = _Session(session_id=self._new_id(), title=_normalize_title(str(payload.get("title", "")), self.limits))
        self._sessions[session.session_id] = session
        event = self._event(
            "session.created",
            request_id,
            0,
            session_id=session.session_id,
            state=session.state,
            metadata={"title": session.title},
        )
        return self._result((event,), self._session_summary(session))

    def _close_session(self, session_id: str, request_id: str) -> ControlPlaneDispatchResult:
        session = self._require_session(session_id)
        if session.state == "CLOSED":
            return self._result((), self._session_summary(session))
        for thread_id in session.thread_ids:
            thread = self._threads[thread_id]
            if thread.active_turn_id:
                turn = self._turns[thread.active_turn_id]
                if turn.state == "RUNNING":
                    raise ControlPlaneError("busy", "running turn blocks session close")
        session.state = "CLOSED"
        for thread_id in session.thread_ids:
            thread = self._threads[thread_id]
            if thread.active_turn_id is None:
                thread.state = "CLOSED"
        self._closed_session_ids.append(session.session_id)
        self._closed_session_ids = self._closed_session_ids[-self.limits.maximum_remembered_closed_sessions :]
        event = self._event("session.closed", request_id, 0, session_id=session.session_id, state=session.state)
        return self._result((event,), self._session_summary(session))

    def _create_thread(self, payload: Mapping[str, Any], request_id: str) -> ControlPlaneDispatchResult:
        session = self._require_session(payload["session_id"])
        if session.state != "OPEN":
            raise ControlPlaneError("invalid_payload", "session is closed")
        if len(session.thread_ids) >= self.limits.maximum_threads_per_session:
            raise ControlPlaneError("budget_exceeded", "thread limit reached")
        thread = _Thread(
            thread_id=self._new_id(),
            session_id=session.session_id,
            title=_normalize_title(str(payload.get("title", "")), self.limits),
        )
        self._threads[thread.thread_id] = thread
        session.thread_ids.append(thread.thread_id)
        event = self._event(
            "thread.created",
            request_id,
            0,
            session_id=session.session_id,
            thread_id=thread.thread_id,
            state=thread.state,
            metadata={"title": thread.title},
        )
        return self._result((event,), self._thread_summary(thread))

    def _start_mock_turn(self, payload: Mapping[str, Any], request_id: str) -> ControlPlaneDispatchResult:
        thread = self._require_thread(payload["thread_id"])
        session = self._sessions[thread.session_id]
        if session.state != "OPEN" or thread.state != "ACTIVE":
            raise ControlPlaneError("invalid_payload", "thread is not active")
        if thread.active_turn_id is not None and self._turns[thread.active_turn_id].state == "RUNNING":
            raise ControlPlaneError("busy", "thread already has an active turn")
        if len(thread.turn_ids) >= self.limits.maximum_turns_per_thread:
            raise ControlPlaneError("budget_exceeded", "turn limit reached")
        prompt = _normalize_prompt(str(payload["prompt"]))
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        preview = _bounded_text(str(sanitize_control_plane_value(prompt)), self.limits.maximum_preview_characters)
        turn = _Turn(
            turn_id=self._new_id(),
            thread_id=thread.thread_id,
            state="RUNNING",
            prompt_sha256=prompt_hash,
            prompt_text=prompt,
            prompt_preview=preview,
            prompt_character_count=len(prompt),
        )
        self._turns[turn.turn_id] = turn
        thread.turn_ids.append(turn.turn_id)
        thread.active_turn_id = turn.turn_id
        behavior = str(payload["behavior"])
        events = self._mock_turn_events(session.session_id, thread.thread_id, turn, request_id, behavior)
        if behavior == "complete":
            turn.state = "COMPLETED"
            thread.active_turn_id = None
            response = {
                "turn_id": turn.turn_id,
                "state": turn.state,
                "model_called": False,
                "tools_executed": 0,
                "events_emitted": len(events),
            }
        else:
            response = {
                "turn_id": turn.turn_id,
                "state": turn.state,
                "model_called": False,
                "tools_executed": 0,
                "events_emitted": len(events),
                (
                    "waiting_for_decision"
                    if behavior == "pending_model"
                    else "waiting_for_cancel"
                ): True,
            }
        return self._result(events, response)

    def _cancel_turn(self, payload: Mapping[str, Any], request_id: str) -> ControlPlaneDispatchResult:
        turn = self._require_turn(payload["turn_id"])
        thread = self._threads[turn.thread_id]
        session = self._sessions[thread.session_id]
        if turn.state == "CANCELLED":
            return self._result((), {**self._turn_summary(turn), "already_cancelled": True})
        if turn.state in {"COMPLETED", "FAILED"}:
            return self._result((), {**self._turn_summary(turn), "already_terminal": True})
        if turn.state != "RUNNING":
            raise ControlPlaneError("request_cancelled", "turn is not running")
        turn.state = "CANCELLING"
        turn.state = "CANCELLED"
        thread.active_turn_id = None
        event = self._event(
            "turn.cancelled",
            request_id,
            0,
            session_id=session.session_id,
            thread_id=thread.thread_id,
            turn_id=turn.turn_id,
            state=turn.state,
            metadata={"reason": payload["reason"], "cleanup_tools_executed": 0},
        )
        return self._result((event,), {**self._turn_summary(turn), "events_emitted": 1})

    def _mock_turn_events(
        self,
        session_id: str,
        thread_id: str,
        turn: _Turn,
        request_id: str,
        behavior: str,
    ) -> tuple[ControlPlaneEvent, ...]:
        events: list[ControlPlaneEvent] = []

        def add(method: str, *, item: _Item | None = None, state: str = "", text: str | None = None, metadata: Mapping[str, Any] | None = None) -> None:
            sequence = len(events)
            events.append(
                self._event(
                    method,
                    request_id,
                    sequence,
                    session_id=session_id,
                    thread_id=thread_id,
                    turn_id=turn.turn_id,
                    item_id=item.item_id if item else None,
                    state=state,
                    kind=item.kind if item else None,
                    text=text,
                    metadata=metadata,
                )
            )
            turn.last_sequence = sequence

        add("turn.started", state=turn.state)
        user = self._item(turn, "user_message", "STARTED")
        add("item.started", item=user, state=user.state)
        user.state = "COMPLETED"
        add("item.completed", item=user, state=user.state, metadata={"prompt_preview": turn.prompt_preview})
        if behavior == "pending_model":
            return self._checked_events(tuple(events))
        status = self._item(turn, "status", "STARTED")
        add("item.started", item=status, state=status.state)
        status.state = "COMPLETED"
        status.text = "Control Plane demo - no model inference or tool execution."
        add("item.completed", item=status, state=status.state, text=status.text)
        if behavior == "wait_for_cancel":
            return self._checked_events(tuple(events))
        assistant = self._item(turn, "assistant_message", "STARTED")
        add("item.started", item=assistant, state=assistant.state)
        assistant.state = "STREAMING"
        fragment_one = "Control Plane demo connected. "
        fragment_two = "No language model was called and no tool execution occurred."
        assistant.text += fragment_one
        add("item.delta", item=assistant, state=assistant.state, text=fragment_one)
        assistant.text += fragment_two
        add("item.delta", item=assistant, state=assistant.state, text=fragment_two)
        assistant.state = "COMPLETED"
        add("item.completed", item=assistant, state=assistant.state)
        add("turn.completed", state="COMPLETED", metadata={"model_called": False, "tools_executed": 0})
        return self._checked_events(tuple(events))

    def _item(self, turn: _Turn, kind: str, state: str) -> _Item:
        if len(turn.item_ids) >= self.limits.maximum_items_per_turn:
            raise ControlPlaneError("budget_exceeded", "item limit reached")
        item = _Item(item_id=self._new_id(), turn_id=turn.turn_id, kind=kind, state=state)
        self._items[item.item_id] = item
        turn.item_ids.append(item.item_id)
        return item

    def _event(
        self,
        method: str,
        reply_to: str,
        sequence: int,
        *,
        session_id: str | None = None,
        thread_id: str | None = None,
        turn_id: str | None = None,
        item_id: str | None = None,
        state: str = "",
        kind: str | None = None,
        text: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ControlPlaneEvent:
        payload = {
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "session_id": session_id,
            "thread_id": thread_id,
            "turn_id": turn_id,
            "item_id": item_id,
            "state": state,
            "kind": kind,
            "text": _bounded_text(str(sanitize_control_plane_value(text)), self.limits.maximum_item_delta_characters) if text is not None else None,
            "metadata": _flat_metadata(metadata or {}),
        }
        return ControlPlaneEvent(method=method, sequence=sequence, reply_to=reply_to, payload=payload)

    def _checked_events(self, events: tuple[ControlPlaneEvent, ...]) -> tuple[ControlPlaneEvent, ...]:
        if len(events) > self.limits.maximum_events_per_request:
            raise ControlPlaneError("budget_exceeded", "event limit reached")
        text_total = sum(len(str(event.payload.get("text") or "")) for event in events)
        if text_total > self.limits.maximum_total_event_text_characters:
            raise ControlPlaneError("payload_too_large", "event text limit reached")
        return events

    def _result(self, events: tuple[ControlPlaneEvent, ...], response: Mapping[str, Any]) -> ControlPlaneDispatchResult:
        return ControlPlaneDispatchResult(events=self._checked_events(events), response=dict(response))

    def _require_session(self, session_id: str) -> _Session:
        if session_id not in self._sessions:
            raise ControlPlaneError("request_not_found", "session not found")
        return self._sessions[session_id]

    def _require_thread(self, thread_id: str) -> _Thread:
        if thread_id not in self._threads:
            raise ControlPlaneError("request_not_found", "thread not found")
        return self._threads[thread_id]

    def _require_turn(self, turn_id: str) -> _Turn:
        if turn_id not in self._turns:
            raise ControlPlaneError("request_not_found", "turn not found")
        return self._turns[turn_id]

    def _session_summary(self, session: _Session) -> dict[str, Any]:
        return {"session_id": session.session_id, "state": session.state, "title": session.title, "thread_count": len(session.thread_ids)}

    def _thread_summary(self, thread: _Thread) -> dict[str, Any]:
        return {
            "thread_id": thread.thread_id,
            "session_id": thread.session_id,
            "state": thread.state,
            "title": thread.title,
            "turn_count": len(thread.turn_ids),
            "active_turn_id": thread.active_turn_id,
        }

    def _turn_summary(self, turn: _Turn) -> dict[str, Any]:
        knowledge_summary = None
        if turn.knowledge_context is not None:
            knowledge_summary = {
                "request_id": turn.knowledge_context.request_id,
                "state": turn.knowledge_context.state.value,
                "vault_revision": turn.knowledge_context.vault_revision,
                "bundle_id": turn.knowledge_context.bundle_id,
                "source_count": turn.knowledge_context.source_count,
                "total_chars": turn.knowledge_context.total_chars,
                "truncated": turn.knowledge_context.truncated,
            }
        return {
            "turn_id": turn.turn_id,
            "thread_id": turn.thread_id,
            "state": turn.state,
            "prompt_sha256": turn.prompt_sha256,
            "prompt_preview": turn.prompt_preview,
            "prompt_character_count": turn.prompt_character_count,
            "item_count": len(turn.item_ids),
            "last_sequence": turn.last_sequence,
            "model_called": turn.model_called,
            "tools_executed": turn.tools_executed,
            "knowledge_request_id": turn.knowledge_request_id,
            "knowledge_context": knowledge_summary,
        }

    def _counts(self) -> dict[str, int]:
        with self._knowledge_review_lock:
            review_count = len(self._knowledge_reviews)
            decision_count = len(self._knowledge_review_decisions)
        return {
            "sessions": len(self._sessions),
            "threads": len(self._threads),
            "turns": len(self._turns),
            "active_turns": sum(1 for thread in self._threads.values() if thread.active_turn_id is not None),
            "knowledge_reviews": review_count,
            "human_review_decisions": decision_count,
        }

    def _new_id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not ID_RE.match(value):
            raise ControlPlaneError("internal_error", "invalid generated id")
        return value


def default_control_plane_limits() -> ControlPlaneLimits:
    return ControlPlaneLimits()


def validate_control_plane_payload(method: str, payload: Mapping[str, Any]) -> tuple[str, ...]:
    findings: list[str] = []
    if method not in CONTROL_PLANE_METHODS:
        return ("unsupported_method",)
    if not isinstance(payload, Mapping):
        return ("payload_not_object",)
    schemas: dict[str, set[str]] = {
        "app.bootstrap": set(),
        "app.status": set(),
        "knowledge.review.decision.create": {
            "review_contract_version",
            "proposal_id",
            "review_artifact_identity",
            "change_identity",
            "observed_vault_revision",
            "decision",
            "comment",
            "actor_identifier",
            "actor_display_name",
            "actor_source",
        },
        "knowledge.review.get": {"review_artifact_identity"},
        "knowledge.review.list": {"offset", "limit"},
        "knowledge.review.refresh": set(),
        "knowledge.review.snapshot": set(),
        "session.create": {"title"},
        "session.get": {"session_id"},
        "session.close": {"session_id"},
        "thread.create": {"session_id", "title"},
        "thread.get": {"thread_id"},
        "turn.start_mock": {"thread_id", "prompt", "behavior"},
        "turn.status": {"turn_id"},
        "turn.cancel": {"turn_id", "reason"},
    }
    optional = {"session.create": {"title"}, "thread.create": {"title"}}
    allowed = schemas[method]
    missing = allowed - set(payload) - optional.get(method, set())
    extra = set(payload) - allowed
    findings.extend(f"missing_{key}" for key in sorted(missing))
    findings.extend(f"unknown_{key}" for key in sorted(extra))
    limits = default_control_plane_limits()
    for key in ("session_id", "thread_id", "turn_id"):
        if key in payload and not _valid_id(payload[key]):
            findings.append(f"invalid_{key}")
    if "title" in payload and not _valid_title(payload["title"], limits):
        findings.append("invalid_title")
    if method == "knowledge.review.list":
        offset = payload.get("offset")
        limit = payload.get("limit")
        if type(offset) is not int or not 0 <= offset <= MAX_KNOWLEDGE_REVIEW_ARTIFACTS:
            findings.append("invalid_offset")
        if type(limit) is not int or not 1 <= limit <= MAX_KNOWLEDGE_REVIEW_PAGE_SIZE:
            findings.append("invalid_limit")
    if method == "knowledge.review.get":
        review_identity = payload.get("review_artifact_identity")
        if type(review_identity) is not str or KNOWLEDGE_REVIEW_ID_RE.fullmatch(review_identity) is None:
            findings.append("invalid_review_artifact_identity")
    if method == "knowledge.review.decision.create":
        review_contract_version = payload.get("review_contract_version")
        if review_contract_version != KNOWLEDGE_CHANGE_REVIEW_CONTRACT:
            findings.append("invalid_review_contract_version")
        proposal_id = payload.get("proposal_id")
        if type(proposal_id) is not str or KNOWLEDGE_PROPOSAL_ID_RE.fullmatch(proposal_id) is None:
            findings.append("invalid_proposal_id")
        review_identity = payload.get("review_artifact_identity")
        if type(review_identity) is not str or KNOWLEDGE_REVIEW_ID_RE.fullmatch(review_identity) is None:
            findings.append("invalid_review_artifact_identity")
        change_identity = payload.get("change_identity")
        if change_identity is not None and (
            type(change_identity) is not str
            or KNOWLEDGE_CHANGE_ID_RE.fullmatch(change_identity) is None
        ):
            findings.append("invalid_change_identity")
        observed_revision = payload.get("observed_vault_revision")
        if type(observed_revision) is not str or VAULT_REVISION_RE.fullmatch(observed_revision) is None:
            findings.append("invalid_observed_vault_revision")
        if payload.get("decision") not in tuple(item.value for item in HumanReviewDecisionValue):
            findings.append("invalid_decision")
        decision_value = payload.get("decision")
        comment = payload.get("comment")
        if type(comment) is not str:
            findings.append("invalid_comment")
        else:
            if len(comment) > MAX_COMMENT_CHARS or "\x00" in comment:
                findings.append("invalid_comment")
            try:
                if len(comment.encode("utf-8")) > MAX_COMMENT_UTF8_BYTES:
                    findings.append("invalid_comment")
            except UnicodeEncodeError:
                findings.append("invalid_comment")
            if (
                decision_value == HumanReviewDecisionValue.REQUEST_CHANGES.value
                and not comment.strip()
            ):
                findings.append("request_changes_comment_required")
        actor_values = (
            (
                "actor_identifier",
                MAX_ACTOR_IDENTIFIER_CHARS,
                MAX_ACTOR_IDENTIFIER_UTF8_BYTES,
            ),
            (
                "actor_display_name",
                MAX_ACTOR_DISPLAY_NAME_CHARS,
                MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES,
            ),
            (
                "actor_source",
                MAX_ACTOR_SOURCE_CHARS,
                MAX_ACTOR_SOURCE_UTF8_BYTES,
            ),
        )
        for actor_key, actor_limit, actor_byte_limit in actor_values:
            actor_value = payload.get(actor_key)
            invalid_actor = (
                type(actor_value) is not str
                or not actor_value.strip()
                or "\x00" in actor_value
                or len(actor_value) > actor_limit
            )
            if not invalid_actor:
                try:
                    invalid_actor = len(actor_value.encode("utf-8")) > actor_byte_limit
                except UnicodeEncodeError:
                    invalid_actor = True
            if invalid_actor:
                findings.append(f"invalid_{actor_key}")
        if payload.get("actor_source") != "LOCALCOMET_REVIEW_CENTER":
            findings.append("invalid_actor_source")
    if method == "turn.start_mock":
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or len(_normalize_prompt(prompt)) > limits.maximum_prompt_characters:
            findings.append("invalid_prompt")
        if payload.get("behavior") not in BEHAVIORS:
            findings.append("invalid_behavior")
    if method == "turn.cancel" and payload.get("reason") not in CANCEL_REASONS:
        findings.append("invalid_cancel_reason")
    return tuple(sorted(set(findings)))


def sanitize_control_plane_value(value: object) -> object:
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, Mapping):
        return {str(key): sanitize_control_plane_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [sanitize_control_plane_value(child) for child in value]
    if isinstance(value, tuple):
        return [sanitize_control_plane_value(child) for child in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return "<REDACTED_TEXT>"


def serialize_control_plane_metadata() -> dict[str, Any]:
    limits = default_control_plane_limits()
    return {
        "version": DESKTOP_CONTROL_PLANE_VERSION,
        "protocol": IPC_PROTOCOL,
        "protocol_version": IPC_PROTOCOL_VERSION,
        "methods": list(CONTROL_PLANE_METHODS),
        "events": list(EVENT_METHODS),
        "session_states": list(SESSION_STATES),
        "thread_states": list(THREAD_STATES),
        "turn_states": list(TURN_STATES),
        "item_states": list(ITEM_STATES),
        "item_kinds": list(ITEM_KINDS),
        "limits": {
            "maximum_sessions": limits.maximum_sessions,
            "maximum_threads_per_session": limits.maximum_threads_per_session,
            "maximum_turns_per_thread": limits.maximum_turns_per_thread,
            "maximum_items_per_turn": limits.maximum_items_per_turn,
            "maximum_prompt_characters": limits.maximum_prompt_characters,
            "maximum_events_per_request": limits.maximum_events_per_request,
            "maximum_knowledge_review_artifacts": limits.maximum_knowledge_review_artifacts,
            "maximum_knowledge_review_page_size": limits.maximum_knowledge_review_page_size,
            "maximum_knowledge_review_decisions": limits.maximum_knowledge_review_decisions,
        },
        "persistence": False,
        "models_connected": False,
        "provider_registry_available": False,
        "harness_registry_available": False,
    }


def status() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "desktop_control_plane_status",
        "version": DESKTOP_CONTROL_PLANE_VERSION,
        "methods": list(CONTROL_PLANE_METHODS),
        "persistence": False,
        "models_connected": False,
        "provider_registry_available": False,
        "harness_registry_available": False,
    }


def report() -> dict[str, Any]:
    metadata = serialize_control_plane_metadata()
    return {
        "ok": True,
        "mode": "desktop_control_plane_report",
        "version": DESKTOP_CONTROL_PLANE_VERSION,
        "summary": {
            "methods": len(metadata["methods"]),
            "events": len(metadata["events"]),
            "persistence": False,
            "models_connected": False,
        },
        "metadata": metadata,
    }


def _secure_id() -> str:
    return secrets.token_hex(12)


def _secure_knowledge_request_id() -> str:
    return f"kreq:{uuid.uuid4()}"


def _secure_knowledge_injection_id() -> str:
    return f"kinj:{uuid.uuid4()}"


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(ID_RE.match(value))


def _valid_title(value: object, limits: ControlPlaneLimits) -> bool:
    return isinstance(value, str) and len(_normalize_title(value, limits)) <= limits.maximum_title_characters


def _normalize_title(value: str, limits: ControlPlaneLimits) -> str:
    return _bounded_text(str(sanitize_control_plane_value(" ".join(value.split()))), limits.maximum_title_characters)


def _normalize_prompt(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _sanitize_text(text: str) -> str:
    value = SECRET_RE.sub("<REDACTED_TEXT>", text)
    value = PATH_RE.sub("<USER_PATH>", value)
    if "Traceback" in value:
        value = value.split("Traceback", 1)[0] + "<REDACTED_TEXT>"
    return _bounded_text(value, 4096)


def _flat_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, bool)) or value is None:
            result[str(key)[:64]] = sanitize_control_plane_value(value)
    return result


def _bounded_text(value: str, limit: int) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit]
````

