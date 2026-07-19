from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import traceback

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "open_source_gui_boost"

SOURCE_REGISTRY = [
    {
        "name": "OmniParser",
        "uploaded_archive": "OmniParser-master.zip",
        "role": "screen_parser",
        "takeaway": "Convert screenshot into structured UI elements with labels, boxes, and icons.",
        "localcomet_mapping": "pc ui parse -> elements list -> safe action suggestion",
        "priority": 1,
        "integration_mode": "adapter_first",
        "risk": "Heavy vision/OCR dependencies; do not import directly into panel.",
    },
    {
        "name": "ShowUI",
        "uploaded_archive": "ShowUI-main.zip",
        "role": "visual_action_suggester",
        "takeaway": "Goal plus screenshot can produce an action suggestion for GUI navigation.",
        "localcomet_mapping": "goal + screen observation -> suggested action -> dry-run",
        "priority": 2,
        "integration_mode": "optional_model_adapter",
        "risk": "Model weights and GPU requirements; keep optional.",
    },
    {
        "name": "UI-TARS",
        "uploaded_archive": "UI-TARS-main.zip",
        "role": "gui_action_language",
        "takeaway": "Define a compact GUI action space: click, double click, right click, drag, hotkey, type, scroll, wait.",
        "localcomet_mapping": "normalize model output into LocalCometAction schema",
        "priority": 3,
        "integration_mode": "schema_and_parser",
        "risk": "Raw model actions must never execute without LocalComet safety gate.",
    },
    {
        "name": "UI-TARS Desktop / Agent TARS",
        "uploaded_archive": "UI-TARS-desktop-main.zip",
        "role": "desktop_agent_stack",
        "takeaway": "Full stack separation between agent, operators, browser/desktop control, and UI.",
        "localcomet_mapping": "keep panel as orchestrator; modules provide operators",
        "priority": 4,
        "integration_mode": "architecture_reference",
        "risk": "Large TypeScript/Electron stack; do not merge into Python panel.",
    },
    {
        "name": "Agent-S",
        "uploaded_archive": "Agent-S-main.zip",
        "role": "manager_worker_memory_grounding",
        "takeaway": "Split GUI agent into manager, worker, grounding, procedural memory, and ACI.",
        "localcomet_mapping": "pc task memory + planner + executor + screen grounding",
        "priority": 5,
        "integration_mode": "architecture_reference",
        "risk": "External OCR/LLM dependencies; use local abstractions first.",
    },
    {
        "name": "OpenCUA",
        "uploaded_archive": "OpenCUA-main.zip",
        "role": "computer_use_schema",
        "takeaway": "Observation/action/bounding-box schemas and trajectory-style agent evaluation.",
        "localcomet_mapping": "LocalCometObservation, LocalCometUIElement, LocalCometAction",
        "priority": 6,
        "integration_mode": "schema_reference",
        "risk": "Dataset/eval tooling is not needed inside the runtime agent.",
    },
    {
        "name": "CUA",
        "uploaded_archive": "cua-main.zip",
        "role": "computer_use_infrastructure",
        "takeaway": "Computer-use infrastructure and background/no-foreground design principles.",
        "localcomet_mapping": "future: avoid stealing focus when background APIs are available",
        "priority": 7,
        "integration_mode": "future_backend_reference",
        "risk": "Large multi-language stack; integrate only small ideas.",
    },
    {
        "name": "OpenHands",
        "uploaded_archive": "OpenHands-main.zip",
        "role": "coding_agent_control_center",
        "takeaway": "Separate conversation, runtime, tools, skills, and agent state.",
        "localcomet_mapping": "LocalComet project editing via request/response patch workflow",
        "priority": 8,
        "integration_mode": "code_agent_reference",
        "risk": "Do not import runtime/docker assumptions into LocalComet.",
    },
    {
        "name": "SWE-agent",
        "uploaded_archive": "SWE-agent-main.zip",
        "role": "software_engineering_loop",
        "takeaway": "Inspect repository, edit, test, and iterate with clear tool protocol.",
        "localcomet_mapping": "pc project inspect -> edit-request -> validate -> after patch",
        "priority": 9,
        "integration_mode": "workflow_reference",
        "risk": "Avoid arbitrary shell tools.",
    },
    {
        "name": "Aider",
        "uploaded_archive": "aider-main.zip",
        "role": "repo_aware_pair_programming",
        "takeaway": "Repository map, chat-driven edits, and patch/test cycle.",
        "localcomet_mapping": "project context + targeted patch generation + tests",
        "priority": 10,
        "integration_mode": "workflow_reference",
        "risk": "Direct repo edits must be mediated through LocalComet patch flow.",
    },
]

LOCALCOMET_ACTION_SCHEMA = {
    "version": "localcomet_gui_action_v1",
    "description": "Unified safe GUI action schema inspired by uploaded open-source GUI/computer-use agents.",
    "action": {
        "id": "string",
        "type": "click|focus_window|hotkey|type_text|open_app|open_folder|web_search|create_project_edit_request|wait|observe",
        "target": "string",
        "point": {"x": "int", "y": "int"},
        "bbox": {"x": "int", "y": "int", "width": "int", "height": "int"},
        "text": "string",
        "confidence": "float 0..1",
        "source": "screen_planner|executor|model_adapter|manual",
        "dry_run_required": True,
        "confirmation_required": True,
        "safety": {
            "allowlisted": "bool",
            "blocked_terms": "list[str]",
            "reason": "string",
        },
    },
}

LOCALCOMET_UI_ELEMENT_SCHEMA = {
    "version": "localcomet_ui_element_v1",
    "element": {
        "id": "string",
        "element_type": "window|button|input|text|icon|image|unknown",
        "text": "string",
        "bbox": {"x": "int", "y": "int", "width": "int", "height": "int"},
        "confidence": "float 0..1",
        "source": "desktop_observer|screen_parser_adapter|manual",
        "metadata": "dict",
    },
}

ROADMAP = [
    {
        "version": "v6.21",
        "name": "Open-Source GUI Boost Base",
        "adds": [
            "source registry",
            "unified UI element schema",
            "unified safe action schema",
            "window-to-element adapter",
            "action suggestion adapter",
            "open-source integration report",
        ],
    },
    {
        "version": "v6.22",
        "name": "Desktop Interaction Primitives",
        "adds": [
            "safe focus window",
            "mouse position report",
            "safe hotkey dry-run",
            "safe screenshot metadata",
            "click preview only",
        ],
    },
    {
        "version": "v6.23",
        "name": "UI Parser Adapter",
        "adds": [
            "OmniParser-compatible backend interface",
            "screenshot -> element JSON",
            "element finder by text",
            "bbox normalization",
        ],
    },
    {
        "version": "v6.24",
        "name": "Visual Action Suggestion",
        "adds": [
            "ShowUI/UI-TARS-style suggested action",
            "action parser",
            "confidence scoring",
            "safety gate before executor",
        ],
    },
    {
        "version": "v6.25",
        "name": "Code Agent Loop",
        "adds": [
            "OpenHands/SWE-agent/Aider-inspired project loop",
            "inspect -> request -> patch -> test -> report",
            "no arbitrary shell",
        ],
    },
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def status():
    payload = {
        "ok": True,
        "mode": "open_source_gui_boost",
        "generated_at": _now(),
        "sources": len(SOURCE_REGISTRY),
        "schemas": ["LocalCometUIElement", "LocalCometAction"],
        "last_elements": get_value("open_source_gui_boost_last_elements", ""),
        "last_suggestion": get_value("open_source_gui_boost_last_suggestion", ""),
        "commands": [
            "pc boost status",
            "pc boost sources",
            "pc boost schema",
            "pc boost elements",
            "pc boost suggest <цель>",
            "pc boost roadmap",
            "pc boost report",
        ],
        "safety": [
            "Adapters do not execute external code.",
            "No direct import of heavy open-source repos.",
            "No click/type action without dry-run and explicit confirmation.",
            "No shell/cmd/powershell/delete/password/token actions.",
        ],
    }
    set_value("open_source_gui_boost_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    lines = [
        "Open-Source GUI Boost:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- sources: {payload.get('sources')}",
        f"- schemas: {', '.join(payload.get('schemas', []))}",
        "",
        "Commands:",
    ]
    lines.extend("- " + item for item in payload.get("commands", []))
    lines.append("")
    lines.append("Safety:")
    lines.extend("- " + item for item in payload.get("safety", []))
    return "\n".join(lines)


def source_registry():
    payload = {
        "ok": True,
        "generated_at": _now(),
        "sources": sorted(SOURCE_REGISTRY, key=lambda item: item["priority"]),
    }
    set_value("open_source_gui_boost_sources", payload)
    return payload


def schema():
    return {
        "ok": True,
        "generated_at": _now(),
        "ui_element_schema": LOCALCOMET_UI_ELEMENT_SCHEMA,
        "action_schema": LOCALCOMET_ACTION_SCHEMA,
    }


def roadmap():
    payload = {
        "ok": True,
        "generated_at": _now(),
        "roadmap": ROADMAP,
    }
    set_value("open_source_gui_boost_roadmap", payload)
    return payload


def _window_to_element(window, index):
    rect = window.get("rect", {}) if isinstance(window, dict) else {}
    return {
        "id": f"window_{index}",
        "element_type": "window",
        "text": str(window.get("title", "") if isinstance(window, dict) else ""),
        "bbox": {
            "x": int(rect.get("left", 0) or 0),
            "y": int(rect.get("top", 0) or 0),
            "width": int(rect.get("width", 0) or 0),
            "height": int(rect.get("height", 0) or 0),
        },
        "confidence": 1.0,
        "source": "desktop_observer",
        "metadata": {
            "class": window.get("class", "") if isinstance(window, dict) else "",
            "hwnd": window.get("hwnd", "") if isinstance(window, dict) else "",
        },
    }


def elements_from_screen():
    try:
        from modules.pc_screen_planner import observe_screen

        observation = observe_screen(save=True)
    except Exception as exc:
        observation = {
            "ok": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

    result = {
        "ok": bool(observation.get("ok")),
        "mode": "ui_elements_from_screen",
        "generated_at": _now(),
        "observation": observation,
        "elements": [],
        "schema": LOCALCOMET_UI_ELEMENT_SCHEMA,
    }

    desktop_result = (
        observation.get("desktop_observer", {})
        .get("result", {})
        if isinstance(observation, dict)
        else {}
    )

    for index, window in enumerate(desktop_result.get("windows", []) or [], start=1):
        result["elements"].append(_window_to_element(window, index))

    active_window = desktop_result.get("active_window", {}) or {}
    if active_window:
        active_element = _window_to_element(active_window, 0)
        active_element["id"] = "active_window"
        result["active_element"] = active_element

    result["screenshot_path"] = desktop_result.get("screenshot_path", "")
    result["report_path"] = desktop_result.get("report_path", "")

    set_value("open_source_gui_boost_last_elements", result)
    return result


def suggest_action(goal):
    goal = str(goal or "").strip()
    lower = _norm(goal)

    if not goal:
        return {"ok": False, "error": "empty goal"}

    try:
        from modules.pc_screen_planner import plan_with_screen

        screen_plan = plan_with_screen(goal)
    except Exception as exc:
        screen_plan = {
            "ok": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

    elements = elements_from_screen()
    suggestions = []

    if any(word in lower for word in ["открыть", "запусти", "open", "launch"]):
        suggestions.append({
            "id": "suggest_open_app_or_folder",
            "type": "open_app",
            "target": goal,
            "confidence": 0.72,
            "source": "open_source_gui_boost",
            "dry_run_required": True,
            "confirmation_required": True,
            "next": f"pc exec dry {goal}",
            "confirmed": f"pc exec run подтверждаю: {goal}",
        })

    if any(word in lower for word in ["клик", "click", "нажми", "кнопк"]):
        suggestions.append({
            "id": "suggest_click_preview",
            "type": "click",
            "target": goal,
            "confidence": 0.45,
            "source": "open_source_gui_boost",
            "dry_run_required": True,
            "confirmation_required": True,
            "next": "pc desktop dry click <x> <y>",
            "note": "Click execution is deferred until Desktop Interaction Primitives are installed.",
        })

    if any(word in lower for word in ["проект", "код", "модуль", "патч", "response.json", "исправь", "добавь команду"]):
        suggestions.append({
            "id": "suggest_project_edit_request",
            "type": "create_project_edit_request",
            "target": goal,
            "confidence": 0.86,
            "source": "open_source_gui_boost",
            "dry_run_required": False,
            "confirmation_required": False,
            "next": f"pc edit {goal}",
        })

    if any(word in lower for word in ["найди", "поиск", "интернет", "web", "google", "документация", "что такое", "как сделать"]):
        suggestions.append({
            "id": "suggest_web_research",
            "type": "web_search",
            "target": goal,
            "confidence": 0.82,
            "source": "open_source_gui_boost",
            "dry_run_required": False,
            "confirmation_required": False,
            "next": f"pc web {goal}",
        })

    if not suggestions:
        suggestions.append({
            "id": "suggest_screen_plan",
            "type": "observe",
            "target": goal,
            "confidence": 0.55,
            "source": "open_source_gui_boost",
            "dry_run_required": True,
            "confirmation_required": True,
            "next": f"pc screen plan {goal}",
        })

    payload = {
        "ok": True,
        "mode": "open_source_gui_action_suggestion",
        "generated_at": _now(),
        "goal": goal,
        "screen_plan": screen_plan,
        "elements_count": len(elements.get("elements", [])),
        "active_element": elements.get("active_element", {}),
        "suggestions": suggestions,
        "schema": LOCALCOMET_ACTION_SCHEMA,
        "safety": [
            "This is a suggestion only.",
            "No action has been executed.",
            "Use dry-run first and confirmed execution second.",
        ],
    }

    set_value("open_source_gui_boost_last_suggestion", payload)
    return payload


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "sources": source_registry(),
        "schemas": schema(),
        "roadmap": roadmap(),
        "last_elements": get_value("open_source_gui_boost_last_elements", ""),
        "last_suggestion": get_value("open_source_gui_boost_last_suggestion", ""),
    }

    json_path = REPORTS_DIR / f"open_source_gui_boost_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"open_source_gui_boost_report_{_stamp()}.md"

    _write_json(json_path, payload)

    md = [
        "# Open-Source GUI Boost Report",
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
        "## Source Registry",
        "",
    ]

    for item in SOURCE_REGISTRY:
        md.extend([
            f"### {item['priority']}. {item['name']}",
            "",
            f"- archive: {item['uploaded_archive']}",
            f"- role: {item['role']}",
            f"- takeaway: {item['takeaway']}",
            f"- LocalComet mapping: {item['localcomet_mapping']}",
            f"- integration mode: {item['integration_mode']}",
            f"- risk: {item['risk']}",
            "",
        ])

    md.extend([
        "## Roadmap",
        "",
        "```json",
        json.dumps(ROADMAP, ensure_ascii=False, indent=2),
        "```",
    ])

    md_path.write_text("\n".join(md), encoding="utf-8")

    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc boost", "pc boost status", "pc boost статус", "open source boost"}:
        return format_status(status())

    if lower in {"pc boost sources", "pc boost источники", "pc boost source"}:
        return format_payload(source_registry())

    if lower in {"pc boost schema", "pc boost схемы", "pc boost schemas"}:
        return format_payload(schema())

    if lower in {"pc boost elements", "pc boost элементы", "pc boost ui"}:
        return format_payload(elements_from_screen())

    if lower in {"pc boost roadmap", "pc boost план", "pc boost road"}:
        return format_payload(roadmap())

    if lower in {"pc boost report", "pc boost отчет", "pc boost отчёт"}:
        return format_payload(report("manual report"))

    prefixes = [
        "pc boost suggest ",
        "pc boost предложение ",
        "pc boost предложи ",
        "boost suggest ",
    ]

    for prefix in prefixes:
        if lower.startswith(prefix):
            goal = text[len(prefix):].strip(" :,-—")
            return format_payload(suggest_action(goal))

    return format_payload({
        "ok": False,
        "error": "Unknown Open-Source GUI Boost command.",
        "help": status().get("commands", []),
    })


def is_boost_command(command):
    lower = _norm(command)
    exact = {
        "pc boost",
        "pc boost status",
        "pc boost статус",
        "open source boost",
        "pc boost sources",
        "pc boost источники",
        "pc boost source",
        "pc boost schema",
        "pc boost схемы",
        "pc boost schemas",
        "pc boost elements",
        "pc boost элементы",
        "pc boost ui",
        "pc boost roadmap",
        "pc boost план",
        "pc boost road",
        "pc boost report",
        "pc boost отчет",
        "pc boost отчёт",
    }
    if lower in exact:
        return True

    prefixes = (
        "pc boost suggest ",
        "pc boost предложение ",
        "pc boost предложи ",
        "boost suggest ",
    )
    return lower.startswith(prefixes)
