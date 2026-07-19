from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import re
import traceback


from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
UI_DIR = PROJECTS_DIR / "PCAgent" / "UIParser"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "ui_parser_adapter"

UI_ELEMENT_SCHEMA = {
    "version": "localcomet_ui_element_v2",
    "description": "OmniParser-compatible LocalComet UI element schema without requiring heavy parser dependencies.",
    "element": {
        "id": "string",
        "element_type": "window|button|input|text|icon|image|menu|unknown",
        "text": "string",
        "bbox": {"x": "int", "y": "int", "width": "int", "height": "int"},
        "center": {"x": "int", "y": "int"},
        "confidence": "float 0..1",
        "clickable": "bool",
        "source": "desktop_observer|desktop_primitives|screen_parser_adapter|omniparser_future|manual",
        "metadata": "dict",
    },
}

UI_ACTION_SCHEMA = {
    "version": "localcomet_ui_action_suggestion_v1",
    "description": "Safe UI action suggestion. This module never executes clicks or typing.",
    "action": {
        "id": "string",
        "type": "observe|focus_window|dry_click|open_app|web_search|project_edit_request|screen_plan",
        "target": "string",
        "element_id": "string",
        "point": {"x": "int", "y": "int"},
        "confidence": "float 0..1",
        "dry_run_command": "string",
        "confirmed_command": "string",
        "executed": False,
        "safety": "dict",
    },
}

BACKENDS = [
    {
        "id": "desktop_window_parser",
        "name": "Desktop Window Parser",
        "status": "active",
        "description": "Converts Windows/Desktop observer window rectangles into LocalComet UI elements.",
        "requires": [],
    },
    {
        "id": "desktop_observer_screenshot",
        "name": "Desktop Observer Screenshot Metadata",
        "status": "active",
        "description": "Uses existing screenshot metadata/path from desktop_observer for future parser handoff.",
        "requires": [],
    },
    {
        "id": "omniparser_adapter",
        "name": "OmniParser-Compatible Adapter",
        "status": "planned",
        "description": "Future backend: screenshot -> UI element boxes, text labels, icons, and confidence.",
        "requires": ["model weights", "vision dependencies", "explicit install step"],
    },
    {
        "id": "showui_action_adapter",
        "name": "ShowUI/UI-TARS Action Adapter",
        "status": "planned",
        "description": "Future backend: goal + screenshot/elements -> suggested GUI action.",
        "requires": ["visual model", "safety gate", "dry-run executor"],
    },
]

BLOCKED_UI_TERMS = [
    "password",
    "пароль",
    "token",
    "secret",
    "private key",
    "api key",
    "bank",
    "банк",
    "payment",
    "casino",
    "seed phrase",
    "ssh",
]

CLICK_WORDS = ["click", "клик", "нажми", "нажать", "button", "кнопк"]
FOCUS_WORDS = ["focus", "фокус", "переключ", "окно", "window"]
OPEN_WORDS = ["open", "открыть", "запусти", "launch"]
WEB_WORDS = ["web", "google", "интернет", "найди", "поиск", "что такое", "как сделать"]
PROJECT_WORDS = ["проект", "код", "модуль", "patch", "response.json", "исправь", "добавь команду"]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    UI_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _bbox_from_rect(rect):
    rect = rect or {}
    x = _safe_int(rect.get("left", rect.get("x", 0)))
    y = _safe_int(rect.get("top", rect.get("y", 0)))
    width = _safe_int(rect.get("width", 0))
    height = _safe_int(rect.get("height", 0))

    if not width and "right" in rect:
        width = _safe_int(rect.get("right")) - x
    if not height and "bottom" in rect:
        height = _safe_int(rect.get("bottom")) - y

    return {"x": x, "y": y, "width": max(0, width), "height": max(0, height)}


def _center(bbox):
    return {
        "x": int(bbox.get("x", 0) + bbox.get("width", 0) / 2),
        "y": int(bbox.get("y", 0) + bbox.get("height", 0) / 2),
    }


def _safety_for_text(text):
    lower = _norm(text)
    hits = [term for term in BLOCKED_UI_TERMS if term in lower]
    return {
        "safe": not hits,
        "blocked_terms": hits,
        "reason": "" if not hits else "Sensitive UI text/title terms: " + ", ".join(hits),
    }


def _window_to_element(window, index, active=False):
    rect = window.get("rect", {}) if isinstance(window, dict) else {}
    title = str(window.get("title", "") if isinstance(window, dict) else "")
    bbox = _bbox_from_rect(rect)
    safety = _safety_for_text(title)

    element_type = "window"
    clickable = bool(title and bbox.get("width", 0) > 0 and bbox.get("height", 0) > 0 and safety.get("safe"))

    return {
        "id": "active_window" if active else f"window_{index}",
        "element_type": element_type,
        "text": title,
        "bbox": bbox,
        "center": _center(bbox),
        "confidence": 1.0 if active else 0.96,
        "clickable": clickable,
        "source": "desktop_primitives",
        "metadata": {
            "class": window.get("class", "") if isinstance(window, dict) else "",
            "hwnd": window.get("hwnd", "") if isinstance(window, dict) else "",
            "active": bool(active),
            "safety": safety,
        },
    }


def _title_tokens_to_text_elements(window, window_index):
    title = str(window.get("title", "") if isinstance(window, dict) else "").strip()
    if not title:
        return []

    words = [word.strip(" -—_|[](){}") for word in re.split(r"\s+", title) if len(word.strip(" -—_|[](){}")) >= 3]
    words = words[:10]
    rect = _bbox_from_rect(window.get("rect", {}))
    elements = []

    if not words:
        return elements

    token_width = max(32, int(rect.get("width", 0) / max(1, len(words))))
    token_height = 24

    for idx, word in enumerate(words, start=1):
        x = rect.get("x", 0) + (idx - 1) * token_width
        y = rect.get("y", 0)
        bbox = {"x": x, "y": y, "width": min(token_width, 220), "height": token_height}
        elements.append({
            "id": f"window_{window_index}_title_text_{idx}",
            "element_type": "text",
            "text": word,
            "bbox": bbox,
            "center": _center(bbox),
            "confidence": 0.62,
            "clickable": False,
            "source": "screen_parser_adapter",
            "metadata": {
                "parent_window": window.get("title", ""),
                "derived": True,
                "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing.",
            },
        })

    return elements


def _get_desktop_payload():
    errors = []
    payload = {
        "windows_payload": {},
        "screenshot_payload": {},
        "screen_observation": {},
        "errors": errors,
    }

    try:
        from modules.pc_desktop_primitives import list_windows, screenshot_metadata

        payload["windows_payload"] = list_windows()
        payload["screenshot_payload"] = screenshot_metadata()
    except Exception as exc:
        errors.append({"source": "pc_desktop_primitives", "error": str(exc), "traceback": traceback.format_exc()})

    if not payload["windows_payload"].get("windows"):
        try:
            from modules.pc_screen_planner import observe_screen

            observation = observe_screen(save=True)
            payload["screen_observation"] = observation
            result = observation.get("desktop_observer", {}).get("result", {})
            payload["windows_payload"] = {
                "ok": True,
                "active_window": result.get("active_window", {}),
                "windows": result.get("windows", []),
                "count": len(result.get("windows", []) or []),
            }
            payload["screenshot_payload"] = {
                "ok": True,
                "screenshot_path": result.get("screenshot_path", ""),
                "screenshot_error": result.get("screenshot_error", ""),
                "report_path": result.get("report_path", ""),
                "active_window": result.get("active_window", {}),
                "windows_count": len(result.get("windows", []) or []),
            }
        except Exception as exc:
            errors.append({"source": "pc_screen_planner", "error": str(exc), "traceback": traceback.format_exc()})

    return payload


def parse_screen(save=True):
    _ensure_dirs()
    desktop = _get_desktop_payload()
    windows_payload = desktop.get("windows_payload", {}) or {}
    screenshot_payload = desktop.get("screenshot_payload", {}) or {}

    windows = windows_payload.get("windows", []) or []
    active_window = windows_payload.get("active_window", {}) or screenshot_payload.get("active_window", {}) or {}

    elements = []
    if active_window:
        elements.append(_window_to_element(active_window, 0, active=True))

    for index, window in enumerate(windows, start=1):
        elements.append(_window_to_element(window, index, active=False))
        elements.extend(_title_tokens_to_text_elements(window, index))

    payload = {
        "ok": True,
        "mode": "ui_parser_adapter_parse",
        "generated_at": _now(),
        "backend": "desktop_window_parser",
        "omniparser_compatible": True,
        "schema": UI_ELEMENT_SCHEMA,
        "screen": {
            "screenshot_path": screenshot_payload.get("screenshot_path", ""),
            "screenshot_error": screenshot_payload.get("screenshot_error", ""),
            "report_path": screenshot_payload.get("report_path", ""),
            "windows_count": len(windows),
            "active_window_title": active_window.get("title", "") if isinstance(active_window, dict) else "",
        },
        "elements": elements,
        "elements_count": len(elements),
        "warnings": [
            "This is a lightweight adapter. It does not perform OCR yet.",
            "Window rectangles are real; button/input/text elements are heuristic until OmniParser backend is installed.",
            "No click/type action has been executed.",
        ],
        "errors": desktop.get("errors", []),
    }

    if save:
        path = UI_DIR / f"ui_parse_{_stamp()}.json"
        payload["path"] = _write_json(path, payload)

    set_value("ui_parser_last_parse", payload)
    return payload


def elements():
    parsed = parse_screen(save=True)
    payload = {
        "ok": parsed.get("ok", False),
        "mode": "ui_parser_adapter_elements",
        "generated_at": _now(),
        "elements_count": parsed.get("elements_count", 0),
        "elements": parsed.get("elements", []),
        "schema": UI_ELEMENT_SCHEMA,
        "source_parse": parsed.get("path", ""),
    }
    set_value("ui_parser_last_elements", payload)
    return payload


def find_elements(query):
    query = str(query or "").strip()
    lower = _norm(query)
    parsed = parse_screen(save=True)
    found = []

    for element in parsed.get("elements", []):
        text = _norm(element.get("text", ""))
        metadata = _norm(json.dumps(element.get("metadata", {}), ensure_ascii=False))
        if lower and (lower in text or lower in metadata):
            item = dict(element)
            item["match_reason"] = "text_or_metadata_contains_query"
            found.append(item)

    payload = {
        "ok": True,
        "mode": "ui_parser_adapter_find",
        "generated_at": _now(),
        "query": query,
        "matches_count": len(found),
        "matches": found,
        "source_parse": parsed.get("path", ""),
    }
    set_value("ui_parser_last_find", payload)
    return payload


def _extract_after_keywords(goal, keywords):
    lower = _norm(goal)
    for keyword in keywords:
        idx = lower.find(keyword)
        if idx >= 0:
            return str(goal)[idx + len(keyword):].strip(" :,-—")
    return str(goal).strip()


def _best_match_for_goal(goal):
    candidate = _extract_after_keywords(goal, CLICK_WORDS + FOCUS_WORDS)
    if candidate and len(candidate) >= 2:
        result = find_elements(candidate)
        if result.get("matches"):
            return result["matches"][0], result
    result = find_elements(goal)
    if result.get("matches"):
        return result["matches"][0], result
    return {}, result


def suggest_ui_action(goal):
    goal = str(goal or "").strip()
    lower = _norm(goal)

    if not goal:
        return {"ok": False, "error": "empty goal"}

    try:
        from modules.agentos_kernel_blueprint import semantic_firewall

        firewall = semantic_firewall(goal)
    except Exception as exc:
        firewall = {"ok": True, "warning": str(exc)}

    parsed = parse_screen(save=True)
    element, find_payload = _best_match_for_goal(goal)

    suggestions = []

    if not firewall.get("ok", True):
        suggestions.append({
            "id": "blocked_by_semantic_firewall",
            "type": "observe",
            "target": goal,
            "element_id": "",
            "point": {},
            "confidence": 1.0,
            "dry_run_command": "",
            "confirmed_command": "",
            "executed": False,
            "safety": firewall,
        })
    elif any(word in lower for word in CLICK_WORDS):
        if element:
            point = element.get("center", {})
            suggestions.append({
                "id": "suggest_dry_click",
                "type": "dry_click",
                "target": element.get("text", goal),
                "element_id": element.get("id", ""),
                "point": point,
                "confidence": min(0.88, float(element.get("confidence", 0.5))),
                "dry_run_command": f"pc desktop dry click {point.get('x', 0)} {point.get('y', 0)}",
                "confirmed_command": "not available in v6.26; click execution intentionally disabled",
                "executed": False,
                "safety": element.get("metadata", {}).get("safety", {"safe": True}),
            })
        else:
            suggestions.append({
                "id": "suggest_parse_first",
                "type": "observe",
                "target": goal,
                "element_id": "",
                "point": {},
                "confidence": 0.4,
                "dry_run_command": "pc ui parse",
                "confirmed_command": "",
                "executed": False,
                "safety": {"safe": True, "reason": "No matching element found."},
            })
    elif any(word in lower for word in FOCUS_WORDS) and element and element.get("element_type") == "window":
        target = element.get("text", goal)
        suggestions.append({
            "id": "suggest_dry_focus_window",
            "type": "focus_window",
            "target": target,
            "element_id": element.get("id", ""),
            "point": element.get("center", {}),
            "confidence": min(0.9, float(element.get("confidence", 0.5))),
            "dry_run_command": f"pc desktop dry focus {target}",
            "confirmed_command": f"pc desktop focus подтверждаю: {target}",
            "executed": False,
            "safety": element.get("metadata", {}).get("safety", {"safe": True}),
        })
    elif any(word in lower for word in OPEN_WORDS):
        suggestions.append({
            "id": "suggest_open_via_executor",
            "type": "open_app",
            "target": goal,
            "element_id": "",
            "point": {},
            "confidence": 0.76,
            "dry_run_command": f"pc exec dry {goal}",
            "confirmed_command": f"pc exec run подтверждаю: {goal}",
            "executed": False,
            "safety": firewall,
        })
    elif any(word in lower for word in PROJECT_WORDS):
        suggestions.append({
            "id": "suggest_project_edit_request",
            "type": "project_edit_request",
            "target": goal,
            "element_id": "",
            "point": {},
            "confidence": 0.82,
            "dry_run_command": f"pc agents project-profile",
            "confirmed_command": f"pc edit {goal}",
            "executed": False,
            "safety": firewall,
        })
    elif any(word in lower for word in WEB_WORDS):
        suggestions.append({
            "id": "suggest_web_research",
            "type": "web_search",
            "target": goal,
            "element_id": "",
            "point": {},
            "confidence": 0.78,
            "dry_run_command": "",
            "confirmed_command": f"pc web {goal}",
            "executed": False,
            "safety": firewall,
        })
    else:
        suggestions.append({
            "id": "suggest_screen_plan",
            "type": "screen_plan",
            "target": goal,
            "element_id": element.get("id", "") if element else "",
            "point": element.get("center", {}) if element else {},
            "confidence": 0.55,
            "dry_run_command": f"pc screen plan {goal}",
            "confirmed_command": f"pc screen dry {goal}",
            "executed": False,
            "safety": firewall,
        })

    payload = {
        "ok": True,
        "mode": "ui_parser_adapter_suggest",
        "generated_at": _now(),
        "goal": goal,
        "firewall": firewall,
        "screen": parsed.get("screen", {}),
        "elements_count": parsed.get("elements_count", 0),
        "matched_element": element,
        "find": {
            "query": find_payload.get("query", ""),
            "matches_count": find_payload.get("matches_count", 0),
        },
        "suggestions": suggestions,
        "schema": UI_ACTION_SCHEMA,
        "safety": [
            "This module suggests actions only.",
            "No click/type action has been executed.",
            "Use dry-run commands before any confirmed executor action.",
        ],
    }
    set_value("ui_parser_last_suggestion", payload)
    return payload


def backends():
    return {
        "ok": True,
        "mode": "ui_parser_backends",
        "generated_at": _now(),
        "backends": BACKENDS,
        "active_backend": "desktop_window_parser",
        "future_backend": "omniparser_adapter",
    }


def status():
    payload = {
        "ok": True,
        "mode": "ui_parser_adapter",
        "generated_at": _now(),
        "schema_version": UI_ELEMENT_SCHEMA["version"],
        "backends": BACKENDS,
        "last_parse": get_value("ui_parser_last_parse", ""),
        "last_find": get_value("ui_parser_last_find", ""),
        "last_suggestion": get_value("ui_parser_last_suggestion", ""),
        "commands": [
            "pc ui status",
            "pc ui backends",
            "pc ui parse",
            "pc ui elements",
            "pc ui find <text>",
            "pc ui suggest <цель>",
            "pc ui report",
        ],
        "safety": [
            "No OCR dependency is required in v6.26.",
            "No click/type is executed.",
            "Coordinates are for dry-run previews only.",
            "Sensitive UI titles/text are flagged.",
            "Future OmniParser backend must pass the same LocalComet safety gate.",
        ],
    }
    set_value("ui_parser_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    active_backends = [item["id"] for item in payload.get("backends", []) if item.get("status") == "active"]
    lines = [
        "UI Parser Adapter:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- schema_version: {payload.get('schema_version')}",
        f"- active_backends: {', '.join(active_backends)}",
        "",
        "Commands:",
    ]
    lines.extend("- " + command for command in payload.get("commands", []))
    lines.append("")
    lines.append("Safety:")
    lines.extend("- " + item for item in payload.get("safety", []))
    return "\n".join(lines)


def report(note=""):
    _ensure_dirs()
    parsed = parse_screen(save=True)
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "backends": backends(),
        "parse": parsed,
        "last_find": get_value("ui_parser_last_find", ""),
        "last_suggestion": get_value("ui_parser_last_suggestion", ""),
    }

    json_path = REPORTS_DIR / f"ui_parser_adapter_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"ui_parser_adapter_report_{_stamp()}.md"

    _write_json(json_path, payload)

    md = [
        "# UI Parser Adapter Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_status(payload["status"]),
        "```",
        "",
        "## Screen",
        "",
        "```json",
        json.dumps(parsed.get("screen", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Elements count",
        "",
        str(parsed.get("elements_count", 0)),
        "",
        "## Backends",
        "",
        "```json",
        json.dumps(BACKENDS, ensure_ascii=False, indent=2),
        "```",
    ]

    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc ui", "pc ui status", "pc ui статус", "ui status"}:
        return format_status(status())

    if lower in {"pc ui backends", "pc ui backend", "pc ui бэкенды", "ui backends"}:
        return format_payload(backends())

    if lower in {"pc ui parse", "pc ui парс", "pc ui разобрать", "ui parse"}:
        return format_payload(parse_screen(save=True))

    if lower in {"pc ui elements", "pc ui элементы", "ui elements"}:
        return format_payload(elements())

    if lower in {"pc ui report", "pc ui отчет", "pc ui отчёт", "ui report"}:
        return format_payload(report("manual report"))

    prefixes = [
        ("pc ui find ", "find"),
        ("pc ui найти ", "find"),
        ("ui find ", "find"),
        ("pc ui suggest ", "suggest"),
        ("pc ui предложи ", "suggest"),
        ("pc ui предложение ", "suggest"),
        ("ui suggest ", "suggest"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "find":
                return format_payload(find_elements(value))
            if action == "suggest":
                return format_payload(suggest_ui_action(value))

    return format_payload({
        "ok": False,
        "error": "Unknown UI Parser Adapter command.",
        "help": status().get("commands", []),
    })


def is_ui_command(command):
    lower = _norm(command)
    exact = {
        "pc ui",
        "pc ui status",
        "pc ui статус",
        "ui status",
        "pc ui backends",
        "pc ui backend",
        "pc ui бэкенды",
        "ui backends",
        "pc ui parse",
        "pc ui парс",
        "pc ui разобрать",
        "ui parse",
        "pc ui elements",
        "pc ui элементы",
        "ui elements",
        "pc ui report",
        "pc ui отчет",
        "pc ui отчёт",
        "ui report",
    }
    if lower in exact:
        return True

    prefixes = (
        "pc ui find ",
        "pc ui найти ",
        "ui find ",
        "pc ui suggest ",
        "pc ui предложи ",
        "pc ui предложение ",
        "ui suggest ",
    )
    return lower.startswith(prefixes)
