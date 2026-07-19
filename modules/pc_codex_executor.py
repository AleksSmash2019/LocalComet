from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import re
import uuid

from core.state import get_value, set_value

from modules.pc_codex_core import classify_goal, plan as core_plan, dry_run as core_dry_run
from modules.pc_agent_actions import open_app, open_folder, create_note
from modules.pc_agent_knowledge import search_web, format_search_recommendation, create_project_edit_request


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
EXECUTOR_DIR = PROJECTS_DIR / "PCAgent" / "Executor"
QUEUE_DIR = EXECUTOR_DIR / "Queue"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "pc_codex_executor"
CURRENT_QUEUE_FILE = QUEUE_DIR / "current_queue.json"
STOP_FILE = EXECUTOR_DIR / "STOP"

MAX_STEPS_PER_RUN = 5

BLOCKED_ACTIONS = {
    "delete",
    "remove",
    "format",
    "shell",
    "cmd",
    "powershell",
    "registry",
    "credential",
    "password",
    "token",
    "payment",
    "login",
}

APP_ALIASES = {
    "блокнот": "notepad",
    "notepad": "notepad",
    "калькулятор": "calc",
    "calc": "calc",
    "calculator": "calc",
    "проводник": "explorer",
    "explorer": "explorer",
    "paint": "paint",
}

FOLDER_ALIASES = {
    "проект": "projects",
    "проекты": "projects",
    "projects": "projects",
    "отчеты": "reports",
    "отчёты": "reports",
    "reports": "reports",
    "загрузки": "downloads",
    "downloads": "downloads",
    "relay": "relay",
    "selfedit": "selfedit",
    "pcagent": "pcagent",
}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    EXECUTOR_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _read_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _blocked(goal):
    safety = classify_goal(goal)
    lower = _norm(goal)
    direct_hits = [item for item in BLOCKED_ACTIONS if item in lower]
    if direct_hits:
        safety["safe"] = False
        safety["blocked_terms"] = list(set(safety.get("blocked_terms", []) + direct_hits))
        safety["blocked_reason"] = "Опасные действия: " + ", ".join(safety["blocked_terms"])
    return safety


def _find_app(goal):
    lower = _norm(goal)
    for word, app in APP_ALIASES.items():
        if word in lower:
            return app
    return ""


def _find_folder(goal):
    lower = _norm(goal)
    for word, folder in FOLDER_ALIASES.items():
        if word in lower:
            return folder
    return ""


def _looks_like_note(goal):
    lower = _norm(goal)
    return any(x in lower for x in ["заметк", "note ", "запиши", "сохрани текст"])


def _extract_note_text(goal):
    text = str(goal or "").strip()
    for marker in ["заметку", "заметка", "note", "запиши", "сохрани текст"]:
        idx = _norm(text).find(marker)
        if idx >= 0:
            extracted = text[idx + len(marker):].strip(" :,-—")
            return extracted or text
    return text


def _looks_like_web(goal):
    lower = _norm(goal)
    triggers = ["что такое", "как сделать", "найди", "поиск", "интернет", "web", "google", "документация", "ошибка", "почему", "актуаль", "latest"]
    return any(trigger in lower for trigger in triggers)


def _looks_like_project_edit(goal):
    lower = _norm(goal)
    triggers = ["измени проект", "поменяй проект", "доработай проект", "исправь проект", "добавь команду", "создай модуль", "сделай патч", "patch", "response.json"]
    return any(trigger in lower for trigger in triggers)


def build_queue(goal):
    goal = str(goal or "").strip()
    safety = _blocked(goal)
    queue = {
        "ok": safety.get("safe", False),
        "queue_id": str(uuid.uuid4())[:8],
        "created_at": _now(),
        "updated_at": _now(),
        "goal": goal,
        "status": "queued" if safety.get("safe") else "blocked",
        "safety": safety,
        "steps": [],
        "results": [],
    }

    if not goal:
        queue["ok"] = False
        queue["status"] = "blocked"
        queue["safety"] = {"safe": False, "blocked_reason": "empty goal", "blocked_terms": []}
        return queue

    if not safety.get("safe"):
        queue["steps"].append({
            "id": "blocked_1",
            "type": "blocked",
            "action": "none",
            "target": "",
            "status": "blocked",
            "reason": safety.get("blocked_reason", "blocked"),
        })
        return queue

    app = _find_app(goal)
    folder = _find_folder(goal)

    if app:
        queue["steps"].append({
            "id": "open_app_1",
            "type": "desktop",
            "action": "open_app",
            "target": app,
            "status": "pending",
            "confirmed_required": True,
        })

    if folder:
        queue["steps"].append({
            "id": "open_folder_1",
            "type": "desktop",
            "action": "open_folder",
            "target": folder,
            "status": "pending",
            "confirmed_required": True,
        })

    if _looks_like_note(goal):
        queue["steps"].append({
            "id": "create_note_1",
            "type": "file_safe",
            "action": "create_note",
            "target": _extract_note_text(goal),
            "status": "pending",
            "confirmed_required": True,
        })

    if _looks_like_web(goal):
        queue["steps"].append({
            "id": "web_search_1",
            "type": "research",
            "action": "web_search",
            "target": goal,
            "status": "pending",
            "confirmed_required": False,
        })

    if _looks_like_project_edit(goal):
        queue["steps"].append({
            "id": "project_edit_request_1",
            "type": "project_safe",
            "action": "create_project_edit_request",
            "target": goal,
            "status": "pending",
            "confirmed_required": False,
        })

    if not queue["steps"]:
        queue["steps"].append({
            "id": "research_recommendation_1",
            "type": "research",
            "action": "web_search",
            "target": goal,
            "status": "pending",
            "confirmed_required": False,
        })

    return queue


def save_queue(queue):
    _ensure_dirs()
    queue["updated_at"] = _now()
    _write_json(CURRENT_QUEUE_FILE, queue)
    set_value("pc_codex_executor_current_queue", queue)
    return queue


def load_queue():
    _ensure_dirs()
    queue = _read_json(CURRENT_QUEUE_FILE)
    return queue


def status():
    queue = load_queue()
    payload = {
        "ok": True,
        "mode": "pc_codex_executor",
        "generated_at": _now(),
        "queue": queue,
        "stop_requested": STOP_FILE.exists(),
        "commands": [
            "pc exec status",
            "pc exec queue <цель>",
            "pc exec dry <цель>",
            "pc exec run подтверждаю: <цель>",
            "pc exec step",
            "pc exec stop",
            "pc exec clear stop",
            "pc exec report",
        ],
    }
    set_value("pc_codex_executor_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    queue = payload.get("queue") or {}
    lines = [
        "PC Codex Executor:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- stop_requested: {payload.get('stop_requested')}",
        f"- queue_id: {queue.get('queue_id', 'none')}",
        f"- goal: {queue.get('goal', 'none')}",
        f"- status: {queue.get('status', 'idle')}",
        "",
        "Commands:",
    ]
    lines.extend("- " + cmd for cmd in payload.get("commands", []))
    return "\n".join(lines)


def queue_goal(goal):
    planned = core_plan(goal)
    queue = build_queue(goal)
    queue["core_plan"] = planned
    save_queue(queue)
    return queue


def dry_goal(goal):
    planned = core_dry_run(goal)
    queue = build_queue(goal)
    queue["core_dry_run"] = planned
    queue["dry_run"] = True
    dry_results = []
    for step in queue.get("steps", []):
        dry_results.append(_execute_step(step, dry_run=True))
    queue["results"] = dry_results
    queue["status"] = "dry_run_complete" if queue.get("ok") else "blocked"
    save_queue(queue)
    return queue


def _execute_step(step, dry_run=True):
    action = step.get("action")
    target = step.get("target", "")
    payload = {
        "ok": False,
        "at": _now(),
        "step_id": step.get("id"),
        "action": action,
        "target": target,
        "dry_run": bool(dry_run),
    }

    if action == "open_app":
        return open_app(target, dry_run=dry_run)

    if action == "open_folder":
        return open_folder(target, dry_run=dry_run)

    if action == "create_note":
        return create_note(target, dry_run=dry_run)

    if action == "web_search":
        if dry_run:
            payload["ok"] = True
            payload["result"] = "DRY_RUN: web search not executed."
            return payload
        search_payload = search_web(target, max_results=6)
        payload["ok"] = search_payload.get("ok", False)
        payload["result"] = format_search_recommendation(search_payload)
        payload["raw"] = search_payload
        return payload

    if action == "create_project_edit_request":
        if dry_run:
            payload["ok"] = True
            payload["result"] = "DRY_RUN: project edit request not created."
            return payload
        request_payload = create_project_edit_request(target)
        payload.update(request_payload)
        return payload

    payload["result"] = "Unknown action."
    return payload


def run_confirmed(goal):
    raw = str(goal or "").strip()
    if "подтверждаю:" not in _norm(raw):
        return {
            "ok": False,
            "blocked": True,
            "reason": "Нужна явная фраза подтверждения.",
            "example": "pc exec run подтверждаю: открыть блокнот",
        }

    clean_goal = re.sub(r"(?i)подтверждаю\s*:", "", raw, count=1).strip()
    queue = build_queue(clean_goal)

    if not queue.get("ok"):
        save_queue(queue)
        return queue

    if STOP_FILE.exists():
        queue["ok"] = False
        queue["status"] = "stopped"
        queue["results"].append({"ok": False, "result": "STOP file exists. Clear it with: pc exec clear stop"})
        save_queue(queue)
        return queue

    results = []
    executed = 0

    for step in queue.get("steps", []):
        if executed >= MAX_STEPS_PER_RUN:
            results.append({"ok": False, "result": "Max steps per run reached.", "max": MAX_STEPS_PER_RUN})
            break
        if STOP_FILE.exists():
            results.append({"ok": False, "result": "Stopped by STOP file."})
            break

        result = _execute_step(step, dry_run=False)
        results.append(result)
        step["status"] = "done" if result.get("ok") else "failed"
        executed += 1

        if not result.get("ok"):
            break

    queue["results"] = results
    queue["status"] = "complete" if all(item.get("ok") for item in results) else "attention"
    save_queue(queue)
    return queue


def step_current():
    queue = load_queue()
    if not queue:
        return {"ok": False, "error": "No queue. Use: pc exec queue <goal>"}
    if STOP_FILE.exists():
        return {"ok": False, "error": "STOP file exists. Use: pc exec clear stop"}

    for step in queue.get("steps", []):
        if step.get("status") == "pending":
            result = _execute_step(step, dry_run=False)
            step["status"] = "done" if result.get("ok") else "failed"
            queue.setdefault("results", []).append(result)
            queue["status"] = "stepped"
            save_queue(queue)
            return {"ok": result.get("ok"), "queue": queue, "step": step, "result": result}

    queue["status"] = "complete"
    save_queue(queue)
    return {"ok": True, "message": "No pending steps.", "queue": queue}


def request_stop():
    _ensure_dirs()
    STOP_FILE.write_text(_now(), encoding="utf-8")
    return {"ok": True, "stop_requested": True, "path": str(STOP_FILE)}


def clear_stop():
    if STOP_FILE.exists():
        STOP_FILE.unlink()
    return {"ok": True, "stop_requested": False}


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "queue": load_queue(),
    }
    json_path = REPORTS_DIR / f"pc_codex_executor_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"pc_codex_executor_report_{_stamp()}.md"
    _write_json(json_path, payload)
    md = [
        "# PC Codex Executor Report",
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
        "## Queue",
        "",
        "```json",
        json.dumps(payload["queue"], ensure_ascii=False, indent=2),
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

    if lower in {"pc exec", "pc exec status", "pc exec статус", "executor status"}:
        return format_status(status())

    if lower in {"pc exec step", "executor step"}:
        return format_payload(step_current())

    if lower in {"pc exec stop", "executor stop"}:
        return format_payload(request_stop())

    if lower in {"pc exec clear stop", "pc exec clear", "executor clear stop"}:
        return format_payload(clear_stop())

    if lower in {"pc exec report", "pc exec отчет", "executor report"}:
        return format_payload(report("manual report"))

    prefixes = [
        ("pc exec queue ", "queue"),
        ("pc exec очередь ", "queue"),
        ("pc exec dry ", "dry"),
        ("pc exec сухой ", "dry"),
        ("pc exec run ", "run"),
        ("pc exec запуск ", "run"),
        ("executor queue ", "queue"),
        ("executor dry ", "dry"),
        ("executor run ", "run"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "queue":
                return format_payload(queue_goal(value))
            if action == "dry":
                return format_payload(dry_goal(value))
            if action == "run":
                return format_payload(run_confirmed(value))

    return format_payload({"ok": False, "error": "Unknown PC Codex Executor command.", "help": status().get("commands", [])})


def is_executor_command(command):
    lower = _norm(command)
    exact = {
        "pc exec", "pc exec status", "pc exec статус", "executor status",
        "pc exec step", "executor step", "pc exec stop", "executor stop",
        "pc exec clear stop", "pc exec clear", "executor clear stop",
        "pc exec report", "pc exec отчет", "executor report",
    }
    if lower in exact:
        return True
    prefixes = (
        "pc exec queue ", "pc exec очередь ", "pc exec dry ", "pc exec сухой ",
        "pc exec run ", "pc exec запуск ", "executor queue ", "executor dry ", "executor run ",
    )
    return lower.startswith(prefixes)
