import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
LOGS_DIR = PROJECTS_DIR / "Logs"
ACTIONS_LOG = LOGS_DIR / "actions.jsonl"


def _ensure_logs_dir():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _short(value, limit: int = 1200):
    text = str(value or "")

    if len(text) > limit:
        return text[:limit] + "... [обрезано]"

    return text


def append_log(user_text: str, plan=None, result=None, status: str = "ok", error=None):
    _ensure_logs_dir()

    tool = None
    action = None

    if isinstance(plan, dict):
        tool = plan.get("tool")
        action = plan.get("action")

        if "actions" in plan:
            tool = "multi"
            action = "actions"

    elif isinstance(plan, list):
        tool = "multi"
        action = "list"

    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "user_text": str(user_text or ""),
        "tool": tool,
        "action": action,
        "status": status,
        "plan": plan,
        "result": _short(result),
        "error": _short(error),
    }

    with ACTIONS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def _read_records():
    _ensure_logs_dir()

    if not ACTIONS_LOG.exists():
        return []

    records = []

    for line in ACTIONS_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            records.append(json.loads(line))
        except Exception:
            records.append({
                "time": "unknown",
                "user_text": "bad log line",
                "tool": "unknown",
                "action": "unknown",
                "status": "error",
                "result": line,
                "error": "Не удалось разобрать строку JSONL",
            })

    return records


def show_history(limit: int = 20):
    records = _read_records()

    if not records:
        return "История действий пока пустая."

    recent = records[-limit:]
    lines = [f"Последние действия ({len(recent)}):"]

    for i, item in enumerate(recent, start=1):
        time = item.get("time", "unknown")
        user_text = item.get("user_text", "")
        tool = item.get("tool", "unknown")
        action = item.get("action", "unknown")
        status = item.get("status", "unknown")

        lines.append(
            f"{i}. [{time}] {status} | {tool}.{action} | {user_text}"
        )

    return "\n".join(lines)


def show_last_log():
    records = _read_records()

    if not records:
        return "История действий пока пустая."

    item = records[-1]

    return (
        "Последняя запись истории:\n"
        + json.dumps(item, ensure_ascii=False, indent=2)
    )


def show_history_stats():
    records = _read_records()

    if not records:
        return "История действий пока пустая."

    total = len(records)
    errors = len([r for r in records if r.get("status") == "error"])

    by_tool = {}

    for item in records:
        tool = item.get("tool") or "unknown"
        by_tool[tool] = by_tool.get(tool, 0) + 1

    lines = [
        "Статистика истории:",
        f"- Всего записей: {total}",
        f"- Ошибок: {errors}",
        "",
        "По инструментам:",
    ]

    for tool, count in sorted(by_tool.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"- {tool}: {count}")

    return "\n".join(lines)


def clear_history():
    _ensure_logs_dir()

    if ACTIONS_LOG.exists():
        ACTIONS_LOG.unlink()

    return f"История очищена: {ACTIONS_LOG}"


def get_log_path():
    _ensure_logs_dir()
    return str(ACTIONS_LOG)