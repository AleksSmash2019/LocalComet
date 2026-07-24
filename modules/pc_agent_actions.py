from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import subprocess

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
ACTIONS_REPORTS_DIR = REPORTS_DIR / "pc_agent_actions"
NOTES_DIR = PROJECTS_DIR / "PCAgent" / "Notes"


APP_ALLOWLIST = {
    "notepad": ["notepad.exe"],
    "блокнот": ["notepad.exe"],
    "calc": ["calc.exe"],
    "calculator": ["calc.exe"],
    "калькулятор": ["calc.exe"],
    "explorer": ["explorer.exe"],
    "проводник": ["explorer.exe"],
    "paint": ["mspaint.exe"],
    "paint.exe": ["mspaint.exe"],
}

FOLDER_ALLOWLIST = {
    "root": ROOT_DIR,
    "проект": ROOT_DIR,
    "projects": PROJECTS_DIR,
    "проекты": PROJECTS_DIR,
    "reports": REPORTS_DIR,
    "отчеты": REPORTS_DIR,
    "selfedit": PROJECTS_DIR / "SelfEdit",
    "relay": PROJECTS_DIR / "ChatGPTRelay",
    "downloads": Path.home() / "Downloads",
    "загрузки": Path.home() / "Downloads",
    "pcagent": PROJECTS_DIR / "PCAgent",
    "pc agent": PROJECTS_DIR / "PCAgent",
    "actions": ACTIONS_REPORTS_DIR,
}

BLOCKED_TERMS = [
    "cmd",
    "powershell",
    "shell",
    "terminal",
    "regedit",
    "registry",
    "format",
    "delete",
    "remove",
    "rmdir",
    "del ",
    "rm -rf",
    "удали",
    "стереть",
    "формат",
    "реестр",
    "пароль",
    "password",
    "token",
    "secret",
    "private key",
    "приватный ключ",
    "оплати",
    "payment",
    "банк",
    "bank",
    "casino",
    "ставка",
    "login",
    "логин",
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _safe_write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _safe_write_text(path: Path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text or ""), encoding="utf-8")
    return str(path)


def classify_action_request(text):
    lower = _norm(text)
    matched = [term for term in BLOCKED_TERMS if term in lower]
    return {
        "safe": not matched,
        "blocked_reason": "Опасные термины: " + ", ".join(matched) if matched else "",
        "matched_terms": matched,
    }


def pc_actions_status():
    payload = {
        "ok": True,
        "mode": "pc_agent_actions",
        "generated_at": _now(),
        "apps": sorted(APP_ALLOWLIST.keys()),
        "folders": sorted(FOLDER_ALLOWLIST.keys()),
        "commands": [
            "pc actions статус",
            "pc actions список",
            "pc actions dry open app <name>",
            "pc actions open app <name>",
            "pc actions dry open folder <name>",
            "pc actions open folder <name>",
            "pc actions note <text>",
            "pc actions report",
        ],
        "last_action": get_value("pc_agent_actions_last_action", ""),
        "last_result": get_value("pc_agent_actions_last_result", ""),
    }
    set_value("pc_agent_actions_status", payload)
    return payload


def format_pc_actions_status(payload=None):
    payload = payload or pc_actions_status()
    lines = [
        "PC Agent Actions Pack:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "Доступные приложения:",
        "- " + ", ".join(payload.get("apps", [])),
        "",
        "Доступные папки:",
        "- " + ", ".join(payload.get("folders", [])),
        "",
        "Команды:",
    ]
    lines.extend("- " + command for command in payload.get("commands", []))
    return "\n".join(lines)


def list_actions():
    return {
        "ok": True,
        "apps": APP_ALLOWLIST,
        "folders": {key: str(value) for key, value in FOLDER_ALLOWLIST.items()},
        "blocked_terms": BLOCKED_TERMS,
        "examples": [
            "pc actions dry open app notepad",
            "pc actions open app notepad",
            "pc actions open folder projects",
            "pc actions note План: проверить агент",
            "pc codex план открыть блокнот и написать заметку",
        ],
    }


def _resolve_app(name):
    key = _norm(name)
    if key not in APP_ALLOWLIST:
        return None
    return APP_ALLOWLIST[key]


def _resolve_folder(name):
    key = _norm(name)
    if key not in FOLDER_ALLOWLIST:
        return None
    path = FOLDER_ALLOWLIST[key]
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return path


def open_app(name, dry_run=True):
    safety = classify_action_request(name)
    command = _resolve_app(name)
    payload = {
        "ok": False,
        "action": "open_app",
        "name": name,
        "dry_run": bool(dry_run),
        "safety": safety,
        "command": command,
    }

    if not safety.get("safe"):
        payload["result"] = "BLOCKED."
        return _remember(payload)

    if not command:
        payload["result"] = "App is not allowlisted."
        payload["allowed"] = sorted(APP_ALLOWLIST.keys())
        return _remember(payload)

    if dry_run:
        payload["ok"] = True
        payload["result"] = "DRY_RUN: приложение не запущено."
        return _remember(payload)

    subprocess.Popen(command, shell=False)
    payload["ok"] = True
    payload["result"] = "Приложение запущено."
    return _remember(payload)


def open_folder(name, dry_run=True):
    safety = classify_action_request(name)
    path = _resolve_folder(name)
    payload = {
        "ok": False,
        "action": "open_folder",
        "name": name,
        "dry_run": bool(dry_run),
        "safety": safety,
        "path": str(path) if path else "",
    }

    if not safety.get("safe"):
        payload["result"] = "BLOCKED."
        return _remember(payload)

    if not path:
        payload["result"] = "Folder is not allowlisted."
        payload["allowed"] = sorted(FOLDER_ALLOWLIST.keys())
        return _remember(payload)

    if dry_run:
        payload["ok"] = True
        payload["result"] = "DRY_RUN: папка не открыта."
        return _remember(payload)

    subprocess.Popen(["explorer.exe", str(path)], shell=False)
    payload["ok"] = True
    payload["result"] = "Папка открыта."
    return _remember(payload)


def create_note(text, dry_run=False):
    safety = classify_action_request(text)
    payload = {
        "ok": False,
        "action": "create_note",
        "dry_run": bool(dry_run),
        "safety": safety,
        "text_preview": str(text or "")[:500],
    }

    if not safety.get("safe"):
        payload["result"] = "BLOCKED."
        return _remember(payload)

    if dry_run:
        payload["ok"] = True
        payload["result"] = "DRY_RUN: заметка не создана."
        return _remember(payload)

    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTES_DIR / f"note_{_stamp()}.md"
    body = "\n".join([
        "# PC Agent Note",
        "",
        f"- generated_at: {_now()}",
        "",
        str(text or "").strip(),
        "",
    ])
    _safe_write_text(path, body)
    payload["ok"] = True
    payload["path"] = str(path)
    payload["result"] = "Заметка создана."
    return _remember(payload)


def create_actions_report(note=""):
    ACTIONS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": pc_actions_status(),
        "last_action": get_value("pc_agent_actions_last_action", ""),
        "last_result": get_value("pc_agent_actions_last_result", ""),
    }

    json_path = ACTIONS_REPORTS_DIR / f"pc_agent_actions_report_{_stamp()}.json"
    md_path = ACTIONS_REPORTS_DIR / f"pc_agent_actions_report_{_stamp()}.md"

    _safe_write_json(json_path, payload)
    md = [
        "# PC Agent Actions Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_pc_actions_status(payload["status"]),
        "```",
        "",
        "## Last Result",
        "",
        "```json",
        json.dumps(payload["last_result"], ensure_ascii=False, indent=2),
        "```",
    ]
    _safe_write_text(md_path, "\n".join(md))

    result = {"ok": True, "report": str(md_path), "json": str(json_path)}
    set_value("pc_agent_actions_last_report", result)
    return result


def _remember(payload):
    set_value("pc_agent_actions_last_action", payload.get("action", "unknown"))
    set_value("pc_agent_actions_last_result", payload)
    return payload


def dispatch_action(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc actions", "pc actions status", "pc actions статус", "pc action status", "actions status"}:
        return pc_actions_status()

    if lower in {"pc actions список", "pc actions list", "pc action list", "список действий"}:
        return list_actions()

    if lower in {"pc actions report", "pc actions отчет", "actions report"}:
        return create_actions_report("manual report from panel chat")

    prefixes = [
        ("pc actions dry open app ", "dry_open_app"),
        ("pc action dry open app ", "dry_open_app"),
        ("pc actions open app ", "open_app"),
        ("pc action open app ", "open_app"),
        ("pc actions dry open folder ", "dry_open_folder"),
        ("pc action dry open folder ", "dry_open_folder"),
        ("pc actions open folder ", "open_folder"),
        ("pc action open folder ", "open_folder"),
        ("pc actions note ", "note"),
        ("pc action note ", "note"),
        ("создай заметку ", "note"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "dry_open_app":
                return open_app(value, dry_run=True)
            if action == "open_app":
                return open_app(value, dry_run=False)
            if action == "dry_open_folder":
                return open_folder(value, dry_run=True)
            if action == "open_folder":
                return open_folder(value, dry_run=False)
            if action == "note":
                return create_note(value, dry_run=False)

    return {
        "ok": False,
        "action": "unknown",
        "result": "Не понял PC Actions команду.",
        "help": list_actions(),
    }


def format_action_result(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)
