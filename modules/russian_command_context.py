from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
CONTEXT_REPORTS_DIR = REPORTS_DIR / "russian_command_context"
FEATURE_INVENTORY = PROJECTS_DIR / "FeatureVerification" / "feature_inventory_last_ok.json"


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(text, limit=3400):
    value = str(text or "")
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...[обрезано]"


def _load_feature_totals():
    if not FEATURE_INVENTORY.exists():
        return {}
    try:
        data = json.loads(FEATURE_INVENTORY.read_text(encoding="utf-8"))
        return data.get("totals", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def normalize_russian_agent_command(text):
    raw = str(text or "").strip()
    lower = raw.lower().replace("ё", "е")

    if not raw:
        return ""

    if lower.startswith(("pc ", "premium ", "native ", "task panel")):
        return raw

    feature_phrases = (
        "проверь новые функции",
        "проверить новые функции",
        "проверка новых функций",
        "автопроверка функций",
        "проверь функции",
        "проверить функции",
        "проверь введенные функции",
        "проверь внедренные функции",
        "проверь текущие функции",
    )
    if any(phrase in lower for phrase in feature_phrases):
        return "pc verify features"

    if "статус проверки" in lower or "статус функций" in lower:
        return "pc verify status"

    if "отчет проверки" in lower or "отчёт проверки" in lower:
        return "pc verify report"

    if "контекст" in lower and ("команд" in lower or "агент" in lower or "рус" in lower):
        return "pc context status"

    if lower.startswith(("объясни команду", "объяснить команду", "что значит команда")):
        return "pc context explain " + raw

    return ""


def explain_russian_intent(text):
    raw = str(text or "").strip()
    lower = raw.lower().replace("ё", "е")
    suggested = normalize_russian_agent_command(raw)

    intent = "chat"
    confidence = 0.35
    notes = []

    if suggested.startswith("pc verify"):
        intent = "feature_verification"
        confidence = 0.92
        notes.append("Запрос похож на проверку новых/изменённых функций проекта.")
    elif suggested.startswith("pc context"):
        intent = "command_context"
        confidence = 0.88
        notes.append("Запрос похож на работу с русским контекстом команд.")
    elif lower.startswith("pc "):
        intent = "direct_command"
        confidence = 0.95
        notes.append("Команда уже записана в формате pc.")
    elif any(word in lower for word in ["сделай", "создай", "исправь", "улучши", "добавь", "проверь", "проанализируй"]):
        intent = "task_request"
        confidence = 0.72
        notes.append("Похоже на задачу; в режиме Чат лучше предложить безопасную команду, а не запускать автоматически.")
    else:
        notes.append("Похоже на обычный чат; router запускать не нужно.")

    return {
        "ok": True,
        "mode": "russian_command_intent",
        "generated_at": _now(),
        "input": raw,
        "intent": intent,
        "confidence": confidence,
        "suggested_command": suggested,
        "router_allowed_by_default": False,
        "notes": notes,
    }


def build_russian_agent_context(message="", limit=5200):
    totals = _load_feature_totals()
    explained = explain_russian_intent(message)

    lines = [
        "Русский контекст LocalComet:",
        "",
        "Главное правило:",
        "- В режиме «Чат» обычный русский текст не запускает router/research.",
        "- В режиме «Команда» точные pc-команды отправляются в router.",
        "- Явный запуск из чата: `выполни: <задача>`.",
        "",
        "Новые команды проверки функций:",
        "- `pc verify features` — найти новые/изменённые функции, собрать inventory и выполнить автопроверку.",
        "- `pc verify status` — показать состояние feature verification.",
        "- `pc verify report` — создать отчёт проверки функций.",
        "",
        "Новые команды контекста:",
        "- `pc context status` — статус русского контекста.",
        "- `pc context explain <текст>` — объяснить намерение русской команды.",
        "- `pc context normalize <текст>` — предложить pc-команду.",
        "",
        "Понимание текущего сообщения:",
        f"- intent: {explained.get('intent')}",
        f"- confidence: {explained.get('confidence')}",
        f"- suggested_command: {explained.get('suggested_command') or 'нет'}",
        "",
        "Feature inventory:",
        f"- files: {totals.get('files', 'нет baseline')}",
        f"- functions: {totals.get('functions', 'нет baseline')}",
        f"- classes: {totals.get('classes', 'нет baseline')}",
        f"- command_modules: {totals.get('command_modules', 'нет baseline')}",
        "",
        "Как отвечать пользователю:",
        "- Если он просто общается — отвечай как обычный агент.",
        "- Если он просит проверить новые функции — предложи или используй `pc verify features` только при явном запуске.",
        "- Если он просит выполнить действие — не говори, что уже выполнил; предложи безопасную команду.",
        "- Отвечай по-русски и без JSON, если пользователь явно не просит технический отчёт.",
    ]

    return _short("\n".join(lines), limit)


def status():
    totals = _load_feature_totals()
    return {
        "ok": True,
        "mode": "russian_command_context_status",
        "generated_at": _now(),
        "language": "ru",
        "context_for_agent_commands": True,
        "plain_chat_router_disabled": True,
        "feature_verification_commands": True,
        "feature_inventory_totals": totals,
        "commands": [
            "pc context status",
            "pc context report",
            "pc context explain <текст>",
            "pc context normalize <текст>",
            "pc verify features",
        ],
    }


def report():
    CONTEXT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CONTEXT_REPORTS_DIR / f"russian_command_context_{_stamp()}.md"
    lines = [
        "# Russian Command Context",
        "",
        build_russian_agent_context("проверь новые функции", limit=9000),
        "",
        "## Status",
        "",
        "```json",
        json.dumps(status(), ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "ok": True,
        "mode": "russian_command_context_report",
        "generated_at": _now(),
        "report": str(path),
    }


def dispatch(command):
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")

    if lower in {"pc context", "pc context status", "контекст команд", "статус контекста"}:
        return json.dumps(status(), ensure_ascii=False, indent=2)

    if lower in {"pc context report", "отчет контекста", "отчёт контекста"}:
        return json.dumps(report(), ensure_ascii=False, indent=2)

    if lower.startswith("pc context explain "):
        payload = explain_russian_intent(text[len("pc context explain "):])
        return json.dumps(payload, ensure_ascii=False, indent=2)

    if lower.startswith("pc context normalize "):
        source = text[len("pc context normalize "):]
        return json.dumps(
            {
                "ok": True,
                "mode": "russian_command_context_normalize",
                "generated_at": _now(),
                "input": source,
                "suggested_command": normalize_russian_agent_command(source),
                "intent": explain_russian_intent(source),
            },
            ensure_ascii=False,
            indent=2,
        )

    return json.dumps(
        {
            "ok": False,
            "mode": "russian_command_context_unknown_command",
            "generated_at": _now(),
            "error": "Неизвестная команда русского контекста.",
            "commands": status().get("commands", []),
        },
        ensure_ascii=False,
        indent=2,
    )


def is_russian_command_context_command(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower.startswith("pc context") or lower in {
        "контекст команд",
        "статус контекста",
        "отчет контекста",
        "отчёт контекста",
    }
