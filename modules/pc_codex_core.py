from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import re

from core.state import get_value, set_value
from modules.pc_agent_knowledge import build_project_context, search_web, format_search_recommendation
from modules.pc_agent_actions import open_app, open_folder, create_note


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
PC_AGENT_DIR = PROJECTS_DIR / "PCAgent"
SESSIONS_DIR = PC_AGENT_DIR / "Sessions"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "pc_codex_core"
CURRENT_SESSION_FILE = SESSIONS_DIR / "current_session.json"

BLOCKED_TERMS = [
    "delete", "remove", "rm ", "rm -rf", "rmdir", "del ", "format", "wipe", "erase",
    "удали", "стереть", "снеси", "формат",
    "cmd", "powershell", "shell", "terminal", "registry", "regedit",
    "пароль", "password", "token", "secret", "api key", "apikey", "private key", "приватный ключ",
    "login", "логин", "банк", "bank", "payment", "casino", "ставка", "bet",
]

APP_WORDS = {
    "блокнот": "notepad",
    "notepad": "notepad",
    "калькулятор": "calc",
    "calc": "calc",
    "calculator": "calc",
    "проводник": "explorer",
    "explorer": "explorer",
    "paint": "paint",
}

FOLDER_WORDS = {
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
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_json_dump(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _load_session():
    _ensure_dirs()
    if not CURRENT_SESSION_FILE.exists():
        return None
    try:
        return json.loads(CURRENT_SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_session(session):
    _ensure_dirs()
    session["updated_at"] = _now()
    _safe_json_dump(CURRENT_SESSION_FILE, session)
    set_value("pc_codex_core_current_session", session)
    return session


def classify_goal(goal):
    lower = _norm(goal)
    hits = [term for term in BLOCKED_TERMS if term in lower]
    return {
        "safe": not hits,
        "blocked_terms": hits,
        "blocked_reason": "Опасные термины: " + ", ".join(hits) if hits else "",
        "requires_confirmation": True,
        "confirmation_phrase": "подтверждаю:",
    }


def _new_session(goal):
    session = {
        "ok": True,
        "session_id": _stamp(),
        "mode": "pc_codex_core",
        "created_at": _now(),
        "updated_at": _now(),
        "goal": str(goal or "").strip(),
        "status": "started",
        "steps": [],
        "last_plan": None,
        "last_dry_run": None,
        "last_step": None,
        "last_report": None,
        "safety": classify_goal(goal),
    }
    return _save_session(session)


def _detect_app(goal):
    lower = _norm(goal)
    for word, app in APP_WORDS.items():
        if word in lower:
            return app
    return ""


def _detect_folder(goal):
    lower = _norm(goal)
    for word, folder in FOLDER_WORDS.items():
        if word in lower:
            return folder
    return ""


def _looks_like_web_question(goal):
    lower = _norm(goal)
    triggers = ["что такое", "как сделать", "найди", "поиск", "интернет", "web", "google", "документация", "ошибка", "почему", "актуаль", "latest", "обнов"]
    return any(trigger in lower for trigger in triggers)


def _looks_like_project_change(goal):
    lower = _norm(goal)
    triggers = ["измени проект", "поменяй проект", "доработай проект", "исправь проект", "добавь команду", "создай модуль", "сделай патч", "patch", "response.json"]
    return any(trigger in lower for trigger in triggers)


def status():
    session = _load_session()
    payload = {
        "ok": True,
        "mode": "pc_codex_core",
        "generated_at": _now(),
        "current_session": session,
        "commands": [
            "pc core status",
            "pc core start <цель>",
            "pc core plan <цель>",
            "pc core dry <цель>",
            "pc core step подтверждаю: <цель>",
            "pc core continue",
            "pc core report",
            "pc core stop",
        ],
        "safety": [
            "No direct deletion.",
            "No arbitrary shell/cmd/powershell.",
            "No private credentials/tokens/passwords.",
            "Use quarantine/request/patch workflow for project changes.",
            "Dry-run first, confirmed step second.",
        ],
    }
    set_value("pc_codex_core_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    session = payload.get("current_session") or {}
    lines = [
        "PC Codex Core:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- current_session: {session.get('session_id', 'none')}",
        f"- goal: {session.get('goal', 'none')}",
        f"- status: {session.get('status', 'idle')}",
        "",
        "Commands:",
    ]
    lines.extend("- " + item for item in payload.get("commands", []))
    lines.append("")
    lines.append("Safety:")
    lines.extend("- " + item for item in payload.get("safety", []))
    return "\n".join(lines)


def start(goal):
    goal = str(goal or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}
    session = _new_session(goal)
    plan_payload = plan(goal, session=session)
    session["last_plan"] = plan_payload
    session["status"] = "planned"
    session["steps"].append({"at": _now(), "event": "start", "goal": goal})
    _save_session(session)
    return {"ok": True, "message": "PC Codex Core session started.", "session": session, "plan": plan_payload}


def plan(goal="", session=None):
    session = session or _load_session()
    goal = str(goal or "").strip() or str((session or {}).get("goal", "")).strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}

    safety = classify_goal(goal)
    context = build_project_context(include_contents=False)
    app = _detect_app(goal)
    folder = _detect_folder(goal)
    steps = []

    if not safety["safe"]:
        steps.append({"type": "blocked", "title": "Запрос содержит опасные термины.", "detail": safety["blocked_reason"]})
    else:
        steps.append({"type": "understand", "title": "Понять цель и проверить безопасность.", "detail": goal})
        if app:
            steps.append({"type": "action", "action": "open_app", "target": app, "dry_run_available": True, "confirmed_required": True})
        if folder:
            steps.append({"type": "action", "action": "open_folder", "target": folder, "dry_run_available": True, "confirmed_required": True})
        if _looks_like_web_question(goal):
            steps.append({"type": "research", "action": "web_search", "query": goal, "dry_run_available": True})
        if _looks_like_project_change(goal):
            steps.append({"type": "project_edit", "action": "create_request", "target": "Projects/ChatGPTRelay/request.md", "confirmed_required": False, "detail": "Создать request.md с контекстом проекта; изменения только через response.json patch workflow."})
        if not app and not folder and not _looks_like_web_question(goal) and not _looks_like_project_change(goal):
            steps.append({"type": "recommendation", "action": "ask_or_research", "detail": "Команда не похожа на allowlist-действие. Сделать web research и дать рекомендацию."})

    payload = {
        "ok": safety["safe"],
        "mode": "plan",
        "generated_at": _now(),
        "goal": goal,
        "safety": safety,
        "project_counts": context.get("structure", {}).get("counts", {}),
        "steps": steps,
        "next": "pc core dry <цель>",
    }

    if session:
        session["last_plan"] = payload
        session["steps"].append({"at": _now(), "event": "plan", "payload": payload})
        _save_session(session)

    return payload


def dry_run(goal="", session=None):
    session = session or _load_session()
    goal = str(goal or "").strip() or str((session or {}).get("goal", "")).strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}

    safety = classify_goal(goal)
    app = _detect_app(goal)
    folder = _detect_folder(goal)
    payload = {"ok": safety["safe"], "mode": "dry_run", "generated_at": _now(), "goal": goal, "safety": safety, "results": [], "next": "pc core step подтверждаю: <цель>"}

    if not safety["safe"]:
        payload["results"].append({"ok": False, "result": "BLOCKED", "reason": safety["blocked_reason"]})
    else:
        if app:
            payload["results"].append(open_app(app, dry_run=True))
        if folder:
            payload["results"].append(open_folder(folder, dry_run=True))
        if _looks_like_web_question(goal):
            payload["results"].append({"ok": True, "action": "web_search", "dry_run": True, "query": goal, "result": "DRY_RUN: интернет-поиск будет выполнен на confirmed/research step."})
        if _looks_like_project_change(goal):
            payload["results"].append({"ok": True, "action": "create_project_edit_request", "dry_run": True, "result": "DRY_RUN: будет создан request.md с контекстом проекта, без прямого изменения файлов."})
        if not payload["results"]:
            payload["results"].append({"ok": True, "action": "unknown_research", "dry_run": True, "result": "DRY_RUN: будет выполнен web research и дана рекомендация."})

    if session:
        session["last_dry_run"] = payload
        session["status"] = "dry_run_ready"
        session["steps"].append({"at": _now(), "event": "dry_run", "payload": payload})
        _save_session(session)

    return payload


def confirmed_step(goal="", session=None):
    session = session or _load_session()
    raw_goal = str(goal or "").strip() or str((session or {}).get("goal", "")).strip()
    if not raw_goal:
        return {"ok": False, "error": "empty goal"}

    lower = _norm(raw_goal)
    if "подтверждаю:" not in lower:
        return {"ok": False, "blocked": True, "reason": "Нужна явная фраза подтверждения.", "example": "pc core step подтверждаю: открыть блокнот"}

    clean_goal = re.sub(r"(?i)подтверждаю\s*:", "", raw_goal, count=1).strip()
    safety = classify_goal(clean_goal)
    app = _detect_app(clean_goal)
    folder = _detect_folder(clean_goal)
    payload = {"ok": safety["safe"], "mode": "confirmed_step", "generated_at": _now(), "goal": clean_goal, "safety": safety, "results": []}

    if not safety["safe"]:
        payload["results"].append({"ok": False, "result": "BLOCKED", "reason": safety["blocked_reason"]})
    else:
        if app:
            payload["results"].append(open_app(app, dry_run=False))
        if folder:
            payload["results"].append(open_folder(folder, dry_run=False))
        if _looks_like_web_question(clean_goal):
            search_payload = search_web(clean_goal, max_results=6)
            payload["results"].append({"ok": search_payload.get("ok"), "action": "web_search", "recommendation": format_search_recommendation(search_payload), "raw": search_payload})
        if _looks_like_project_change(clean_goal):
            from modules.pc_agent_knowledge import create_project_edit_request
            payload["results"].append(create_project_edit_request(clean_goal))
        if not payload["results"]:
            search_payload = search_web(clean_goal, max_results=5)
            payload["results"].append({"ok": search_payload.get("ok"), "action": "unknown_research", "recommendation": format_search_recommendation(search_payload), "raw": search_payload})

    if session:
        session["last_step"] = payload
        session["status"] = "stepped" if payload.get("ok") else "blocked"
        session["steps"].append({"at": _now(), "event": "confirmed_step", "payload": payload})
        _save_session(session)

    return payload


def continue_session():
    session = _load_session()
    if not session:
        return {"ok": False, "error": "No current session. Use: pc core start <goal>"}
    goal = session.get("goal", "")
    status_value = session.get("status", "")
    if status_value in {"started", "planned"}:
        return dry_run(goal, session=session)
    if status_value == "dry_run_ready":
        return {"ok": True, "message": "Dry-run готов. Для действия нужна команда:", "command": f"pc core step подтверждаю: {goal}"}
    return {"ok": True, "message": "Session state summarized.", "session": session, "next": "pc core plan <goal> or pc core start <new goal>"}


def stop_session():
    session = _load_session()
    if not session:
        return {"ok": True, "message": "No active session."}
    session["status"] = "stopped"
    session["steps"].append({"at": _now(), "event": "stop"})
    _save_session(session)
    return {"ok": True, "message": "Session stopped.", "session": session}


def report(note=""):
    _ensure_dirs()
    session = _load_session()
    payload = {"ok": True, "generated_at": _now(), "note": str(note or "").strip(), "session": session, "status": status()}
    json_path = REPORTS_DIR / f"pc_codex_core_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"pc_codex_core_report_{_stamp()}.md"
    _safe_json_dump(json_path, payload)
    md = [
        "# PC Codex Core Report",
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
        "## Session",
        "",
        "```json",
        json.dumps(session, ensure_ascii=False, indent=2),
        "```",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")
    if session:
        session["last_report"] = str(md_path)
        _save_session(session)
    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc core", "pc core status", "pc core статус", "codex core", "codex status"}:
        return format_status(status())
    if lower in {"pc core continue", "pc core продолжить", "codex continue"}:
        return format_payload(continue_session())
    if lower in {"pc core stop", "pc core останови", "codex stop"}:
        return format_payload(stop_session())
    if lower in {"pc core report", "pc core отчет", "codex report"}:
        return format_payload(report("manual report"))

    prefixes = [
        ("pc core start ", "start"),
        ("pc core цель ", "start"),
        ("pc core plan ", "plan"),
        ("pc core план ", "plan"),
        ("pc core dry ", "dry"),
        ("pc core сухой ", "dry"),
        ("pc core step ", "step"),
        ("pc core шаг ", "step"),
        ("codex start ", "start"),
        ("codex plan ", "plan"),
        ("codex dry ", "dry"),
        ("codex step ", "step"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "start":
                return format_payload(start(value))
            if action == "plan":
                return format_payload(plan(value))
            if action == "dry":
                return format_payload(dry_run(value))
            if action == "step":
                return format_payload(confirmed_step(value))

    return format_payload({"ok": False, "error": "Unknown PC Codex Core command.", "help": status().get("commands", [])})


def is_core_command(command):
    lower = _norm(command)
    exact = {
        "pc core", "pc core status", "pc core статус", "pc core continue", "pc core продолжить",
        "pc core stop", "pc core останови", "pc core report", "pc core отчет",
        "codex core", "codex status", "codex continue", "codex stop", "codex report",
    }
    if lower in exact:
        return True
    prefixes = (
        "pc core start ", "pc core цель ", "pc core plan ", "pc core план ", "pc core dry ",
        "pc core сухой ", "pc core step ", "pc core шаг ", "codex start ", "codex plan ",
        "codex dry ", "codex step ",
    )
    return lower.startswith(prefixes)
