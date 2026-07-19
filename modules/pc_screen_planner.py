from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import platform
import traceback

from core.state import get_value, set_value

from modules.pc_codex_core import classify_goal, plan as core_plan
from modules.pc_codex_executor import queue_goal, dry_goal
from modules.pc_agent_knowledge import build_project_context


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "pc_screen_planner"
OBSERVATIONS_DIR = PROJECTS_DIR / "PCAgent" / "ScreenObservations"

BLOCKED_TERMS = [
    "delete",
    "remove",
    "format",
    "shell",
    "cmd",
    "powershell",
    "terminal",
    "registry",
    "password",
    "пароль",
    "token",
    "secret",
    "private key",
    "login",
    "логин",
    "bank",
    "банк",
    "payment",
    "casino",
    "ставка",
]

SCREEN_ACTION_HINTS = {
    "open_app": ["открыть", "запусти", "open", "launch"],
    "read_screen": ["что на экране", "посмотри экран", "осмотри", "observe", "screen"],
    "project_work": ["проект", "код", "модуль", "патч", "response.json", "request.md"],
    "browser_work": ["браузер", "страница", "сайт", "google", "поиск", "web"],
}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    OBSERVATIONS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _active_window_title():
    if platform.system().lower() != "windows":
        return ""

    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value
    except Exception:
        return ""


def _screen_size():
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        size = {"width": root.winfo_screenwidth(), "height": root.winfo_screenheight()}
        root.destroy()
        return size
    except Exception:
        return {"width": 0, "height": 0}


def _try_desktop_observer():
    try:
        from modules.desktop_observer import observe_desktop

        result = observe_desktop()
        return {"ok": True, "source": "modules.desktop_observer.observe_desktop", "result": result}
    except Exception as exc:
        return {"ok": False, "source": "modules.desktop_observer.observe_desktop", "error": str(exc)}


def observe_screen(save=True):
    _ensure_dirs()

    observation = {
        "ok": True,
        "mode": "screen_observation",
        "generated_at": _now(),
        "platform": platform.platform(),
        "active_window_title": _active_window_title(),
        "screen_size": _screen_size(),
        "desktop_observer": _try_desktop_observer(),
        "notes": [
            "This is a safe text observation.",
            "No click/type action is executed by Screen Planner.",
            "Use dry-run and executor confirmation before control.",
        ],
    }

    if save:
        path = OBSERVATIONS_DIR / f"screen_observation_{_stamp()}.json"
        observation["path"] = _write_json(path, observation)

    set_value("pc_screen_planner_last_observation", observation)
    return observation


def classify_screen_goal(goal):
    lower = _norm(goal)
    safety = classify_goal(goal)
    hits = [term for term in BLOCKED_TERMS if term in lower]

    if hits:
        safety["safe"] = False
        safety["blocked_terms"] = sorted(set(safety.get("blocked_terms", []) + hits))
        safety["blocked_reason"] = "Screen planner blocked terms: " + ", ".join(safety["blocked_terms"])

    intent = "general"
    for candidate, words in SCREEN_ACTION_HINTS.items():
        if any(word in lower for word in words):
            intent = candidate
            break

    return {
        "safe": safety.get("safe", False),
        "blocked_terms": safety.get("blocked_terms", []),
        "blocked_reason": safety.get("blocked_reason", ""),
        "intent": intent,
        "requires_dry_run": True,
        "requires_confirmation": True,
    }


def plan_with_screen(goal, include_project=True):
    goal = str(goal or "").strip()

    if not goal:
        return {"ok": False, "error": "empty goal"}

    observation = observe_screen(save=True)
    screen_safety = classify_screen_goal(goal)
    core = core_plan(goal)
    project_context = build_project_context(include_contents=False) if include_project else {}

    steps = []

    if not screen_safety.get("safe"):
        steps.append({
            "type": "blocked",
            "title": "Цель заблокирована safety policy.",
            "detail": screen_safety.get("blocked_reason", ""),
        })
    else:
        active_title = observation.get("active_window_title") or "unknown"
        steps.extend([
            {
                "type": "observe",
                "title": "Зафиксировать текущий экран и активное окно.",
                "detail": f"active_window={active_title}",
            },
            {
                "type": "reason",
                "title": "Сопоставить цель с текущим контекстом.",
                "detail": f"intent={screen_safety.get('intent')}",
            },
            {
                "type": "dry_run",
                "title": "Сначала выполнить dry-run через executor.",
                "command": f"pc exec dry {goal}",
            },
            {
                "type": "confirm",
                "title": "Только после проверки выполнить confirmed run.",
                "command": f"pc exec run подтверждаю: {goal}",
            },
        ])

        if screen_safety.get("intent") == "project_work":
            steps.append({
                "type": "project_context",
                "title": "Учитывать структуру проекта.",
                "detail": "Изменения проекта только через request/response.json patch workflow.",
            })

        if screen_safety.get("intent") == "read_screen":
            steps.append({
                "type": "screen_summary",
                "title": "Ответить по экрану без управления мышью.",
                "detail": "Screen Planner не кликает по координатам; он готовит план.",
            })

    payload = {
        "ok": screen_safety.get("safe", False),
        "mode": "screen_aware_plan",
        "generated_at": _now(),
        "goal": goal,
        "screen_safety": screen_safety,
        "observation": observation,
        "core_plan": core,
        "project_counts": project_context.get("structure", {}).get("counts", {}) if project_context else {},
        "steps": steps,
        "next": f"pc screen dry {goal}",
    }

    set_value("pc_screen_planner_last_plan", payload)
    return payload


def dry_run_screen(goal):
    plan_payload = plan_with_screen(goal)
    if not plan_payload.get("ok"):
        return plan_payload

    executor_preview = dry_goal(goal)
    payload = {
        "ok": executor_preview.get("ok", False),
        "mode": "screen_aware_dry_run",
        "generated_at": _now(),
        "goal": goal,
        "screen_plan": plan_payload,
        "executor_dry_run": executor_preview,
        "next": f"pc exec run подтверждаю: {goal}",
    }
    set_value("pc_screen_planner_last_dry_run", payload)
    return payload


def queue_screen_goal(goal):
    plan_payload = plan_with_screen(goal)
    if not plan_payload.get("ok"):
        return plan_payload

    queue_payload = queue_goal(goal)
    payload = {
        "ok": queue_payload.get("ok", False),
        "mode": "screen_aware_queue",
        "generated_at": _now(),
        "goal": goal,
        "screen_plan": plan_payload,
        "executor_queue": queue_payload,
        "next": f"pc exec dry {goal}",
    }
    set_value("pc_screen_planner_last_queue", payload)
    return payload


def status():
    payload = {
        "ok": True,
        "mode": "pc_screen_planner",
        "generated_at": _now(),
        "last_observation": get_value("pc_screen_planner_last_observation", ""),
        "last_plan": get_value("pc_screen_planner_last_plan", ""),
        "last_dry_run": get_value("pc_screen_planner_last_dry_run", ""),
        "commands": [
            "pc screen status",
            "pc screen observe",
            "pc screen plan <цель>",
            "pc screen dry <цель>",
            "pc screen queue <цель>",
            "pc screen report",
        ],
        "safety": [
            "No blind coordinate clicking.",
            "No direct typing into unknown windows.",
            "No shell/cmd/powershell.",
            "No deletion.",
            "Screen Planner plans; Executor executes only after dry-run and confirmation.",
        ],
    }
    set_value("pc_screen_planner_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    lines = [
        "PC Screen-Aware Planner:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "Commands:",
    ]
    lines.extend("- " + item for item in payload.get("commands", []))
    lines.append("")
    lines.append("Safety:")
    lines.extend("- " + item for item in payload.get("safety", []))
    return "\n".join(lines)


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "last_observation": get_value("pc_screen_planner_last_observation", ""),
        "last_plan": get_value("pc_screen_planner_last_plan", ""),
        "last_dry_run": get_value("pc_screen_planner_last_dry_run", ""),
    }

    json_path = REPORTS_DIR / f"pc_screen_planner_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"pc_screen_planner_report_{_stamp()}.md"

    _write_json(json_path, payload)

    md = [
        "# PC Screen-Aware Planner Report",
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
        "## Last Plan",
        "",
        "```json",
        json.dumps(payload["last_plan"], ensure_ascii=False, indent=2),
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

    if lower in {"pc screen", "pc screen status", "pc screen статус", "screen planner"}:
        return format_status(status())

    if lower in {"pc screen observe", "pc screen осмотр", "screen observe"}:
        return format_payload(observe_screen(save=True))

    if lower in {"pc screen report", "pc screen отчет", "screen report"}:
        return format_payload(report("manual report"))

    prefixes = [
        ("pc screen plan ", "plan"),
        ("pc screen план ", "plan"),
        ("pc screen dry ", "dry"),
        ("pc screen сухой ", "dry"),
        ("pc screen queue ", "queue"),
        ("pc screen очередь ", "queue"),
        ("screen plan ", "plan"),
        ("screen dry ", "dry"),
        ("screen queue ", "queue"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "plan":
                return format_payload(plan_with_screen(value))
            if action == "dry":
                return format_payload(dry_run_screen(value))
            if action == "queue":
                return format_payload(queue_screen_goal(value))

    return format_payload({
        "ok": False,
        "error": "Unknown PC Screen Planner command.",
        "help": status().get("commands", []),
    })


def is_screen_command(command):
    lower = _norm(command)
    exact = {
        "pc screen",
        "pc screen status",
        "pc screen статус",
        "screen planner",
        "pc screen observe",
        "pc screen осмотр",
        "screen observe",
        "pc screen report",
        "pc screen отчет",
        "screen report",
    }
    if lower in exact:
        return True

    prefixes = (
        "pc screen plan ",
        "pc screen план ",
        "pc screen dry ",
        "pc screen сухой ",
        "pc screen queue ",
        "pc screen очередь ",
        "screen plan ",
        "screen dry ",
        "screen queue ",
    )
    return lower.startswith(prefixes)
