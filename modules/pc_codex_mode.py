from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import traceback

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
PC_CODEX_REPORTS_DIR = REPORTS_DIR / "pc_codex_mode"


BLOCKED_TERMS = [
    "удали",
    "стереть",
    "форматируй",
    "format",
    "delete",
    "remove",
    "rm -rf",
    "пароль",
    "password",
    "token",
    "api key",
    "secret",
    "приватный ключ",
    "private key",
    "оплати",
    "payment",
    "банк",
    "bank",
    "ставка",
    "bet",
    "casino",
    "логин",
    "login",
    "send enter",
    "нажми enter",
    "enter",
    "powershell",
    "cmd",
    "shell",
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _normalize(text):
    return str(text or "").lower().replace("ё", "е").strip()


def classify_pc_codex_goal(goal):
    lower = _normalize(goal)
    matched = [term for term in BLOCKED_TERMS if term in lower]

    needs_confirmation_terms = [
        "клик",
        "click",
        "нажми",
        "открой",
        "open",
        "перейди",
        "вставь",
        "paste",
        "напиши",
        "type",
        "запусти",
        "run",
    ]
    needs_confirmation = any(term in lower for term in needs_confirmation_terms)

    if matched:
        return {
            "safe": False,
            "needs_confirmation": True,
            "blocked_reason": "Команда содержит опасные термины: " + ", ".join(matched),
            "matched_terms": matched,
        }

    return {
        "safe": True,
        "needs_confirmation": needs_confirmation,
        "blocked_reason": "",
        "matched_terms": [],
    }


def pc_codex_status():
    payload = {
        "ok": True,
        "mode": "pc_codex",
        "generated_at": _now(),
        "focus": "PC Agent / управление ПК через чат",
        "principles": [
            "observe first",
            "plan before action",
            "dry-run before confirmed step",
            "block destructive/private/payment/system actions",
            "prefer reports over blind automation",
        ],
        "commands": [
            "pc codex статус",
            "pc codex что умеешь",
            "pc codex осмотр",
            "pc codex план <цель>",
            "pc codex dry <цель>",
            "pc codex step <цель>",
            "pc codex отчет",
        ],
        "last_goal": get_value("pc_codex_last_goal", ""),
        "last_result": get_value("pc_codex_last_result", ""),
    }
    set_value("pc_codex_last_status", payload)
    return payload


def format_pc_codex_status(payload=None):
    payload = payload or pc_codex_status()
    lines = [
        "PC Codex Mode:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- focus: {payload.get('focus')}",
        "",
        "Принципы:",
    ]
    lines.extend("- " + item for item in payload.get("principles", []))
    lines.append("")
    lines.append("Команды:")
    lines.extend("- " + item for item in payload.get("commands", []))
    last_goal = payload.get("last_goal")
    if last_goal:
        lines.append("")
        lines.append(f"last_goal: {last_goal}")
    return "\n".join(lines)


def pc_codex_capabilities():
    return (
        "PC Codex Mode — что умею:\\n\\n"
        "1. Осматривать экран и состояние проекта.\\n"
        "2. Строить пошаговый план управления ПК.\\n"
        "3. Делать dry-run без кликов и ввода.\\n"
        "4. Выполнять только безопасный confirmed step через существующий PC Agent.\\n"
        "5. Создавать отчеты по действиям.\\n"
        "6. Блокировать удаление, shell, пароли, токены, платежи, логины и приватные данные.\\n"
        "7. Использовать PC Agent Actions Pack для allowlist-действий: открыть приложение, открыть папку, создать заметку.\\n"
        "8. Если команда неизвестна — делать internet research и учитывать структуру проекта.\\n"
        "9. Для изменения проекта создавать request.md с контекстом: pc edit <задача>.\\n\\n"
        "Главный рабочий формат:\\n"
        "- pc codex план <что сделать>\\n"
        "- pc codex dry <что сделать>\\n"
        "- pc codex step <что сделать>\\n"
        "- pc actions список\\n"
        "- pc actions open app notepad\\n"
        "- pc actions open folder projects\\n"
        "- pc actions note <текст>\\n"
    )


def pc_codex_observe():
    try:
        from modules.pc_agent_core import pc_agent_observe
        payload = pc_agent_observe()
    except Exception:
        payload = {"ok": False, "error": traceback.format_exc()}

    set_value("pc_codex_last_result", payload)
    return payload


def pc_codex_plan(goal):
    goal = str(goal or "").strip()
    safety = classify_pc_codex_goal(goal)

    if not safety.get("safe"):
        payload = {
            "ok": False,
            "mode": "pc_codex_plan",
            "goal": goal,
            "safety": safety,
            "result": "BLOCKED before planning.",
        }
        set_value("pc_codex_last_result", payload)
        return payload

    try:
        from modules.pc_agent_core import pc_agent_plan
        plan = pc_agent_plan(goal)
    except Exception:
        plan = {"ok": False, "error": traceback.format_exc()}

    payload = {
        "ok": True,
        "mode": "pc_codex_plan",
        "goal": goal,
        "safety": safety,
        "plan": plan,
        "next": "Для безопасной проверки используй: pc codex dry <цель>. Для действия: pc codex step <цель>.",
    }
    set_value("pc_codex_last_goal", goal)
    set_value("pc_codex_last_result", payload)
    return payload


def pc_codex_dry_run(goal):
    goal = str(goal or "").strip()
    safety = classify_pc_codex_goal(goal)

    if not safety.get("safe"):
        payload = {
            "ok": False,
            "mode": "pc_codex_dry_run",
            "goal": goal,
            "safety": safety,
            "result": "BLOCKED.",
        }
        set_value("pc_codex_last_result", payload)
        return payload

    try:
        from modules.pc_agent_core import pc_agent_step
        result = pc_agent_step(goal, confirmed=False, dry_run=True)
    except Exception:
        result = {"ok": False, "error": traceback.format_exc()}

    payload = {
        "ok": True,
        "mode": "pc_codex_dry_run",
        "goal": goal,
        "safety": safety,
        "result": result,
    }
    set_value("pc_codex_last_goal", goal)
    set_value("pc_codex_last_result", payload)
    return payload


def pc_codex_confirmed_step(goal):
    goal = str(goal or "").strip()
    safety = classify_pc_codex_goal(goal)

    if not safety.get("safe"):
        payload = {
            "ok": False,
            "mode": "pc_codex_confirmed_step",
            "goal": goal,
            "safety": safety,
            "result": "BLOCKED.",
        }
        set_value("pc_codex_last_result", payload)
        return payload

    if safety.get("needs_confirmation") and "подтверждаю" not in _normalize(goal):
        payload = {
            "ok": False,
            "mode": "pc_codex_confirmed_step",
            "goal": goal,
            "safety": safety,
            "result": "Нужно явное слово 'подтверждаю' в команде для действия с кликом/вводом/запуском.",
            "example": "pc codex step подтверждаю: открыть блокнот",
        }
        set_value("pc_codex_last_result", payload)
        return payload

    try:
        from modules.pc_agent_core import pc_agent_step
        result = pc_agent_step(goal.replace("подтверждаю:", "").replace("подтверждаю", "").strip(), confirmed=True, dry_run=False)
    except Exception:
        result = {"ok": False, "error": traceback.format_exc()}

    payload = {
        "ok": True,
        "mode": "pc_codex_confirmed_step",
        "goal": goal,
        "safety": safety,
        "result": result,
    }
    set_value("pc_codex_last_goal", goal)
    set_value("pc_codex_last_result", payload)
    return payload


def create_pc_codex_report(note=""):
    PC_CODEX_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": pc_codex_status(),
        "last_goal": get_value("pc_codex_last_goal", ""),
        "last_result": get_value("pc_codex_last_result", ""),
    }

    json_path = PC_CODEX_REPORTS_DIR / f"pc_codex_report_{_stamp()}.json"
    md_path = PC_CODEX_REPORTS_DIR / f"pc_codex_report_{_stamp()}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# PC Codex Mode Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_pc_codex_status(payload["status"]),
        "```",
        "",
        "## Last Result",
        "",
        "```json",
        json.dumps(payload["last_result"], ensure_ascii=False, indent=2),
        "```",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")

    result = {"ok": True, "report": str(md_path), "json": str(json_path)}
    set_value("pc_codex_last_report", result)
    return result


def format_pc_codex_result(payload):
    if isinstance(payload, str):
        return payload

    return json.dumps(payload, ensure_ascii=False, indent=2)
