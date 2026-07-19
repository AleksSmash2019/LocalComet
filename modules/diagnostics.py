from pathlib import Path
from modules.project_paths import get_project_root
from datetime import datetime
import requests

from config import MODEL, LMSTUDIO_API
from core.state import load_state, get_value, STATE_FILE


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
NOTES_DIR = PROJECTS_DIR / "Notes"
FILES_DIR = PROJECTS_DIR / "Files"
WINDOWS_DIR = PROJECTS_DIR / "Windows"
MEMORY_DIR = ROOT_DIR / "memory"


def _models_url():
    return LMSTUDIO_API.replace("/chat/completions", "/models")


def _short_text(value, limit: int = 500):
    text = str(value)

    if len(text) > limit:
        return text[:limit] + "... [обрезано]"

    return text


def check_lmstudio():
    url = _models_url()

    lines = [
        "## Проверка LM Studio",
        "",
        f"- API chat: {LMSTUDIO_API}",
        f"- API models: {url}",
        f"- MODEL в config.py: {MODEL}",
        "",
    ]

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        data = response.json()
        models = data.get("data", [])

        ids = [m.get("id") for m in models if m.get("id")]

        lines.append("Статус: ✅ LM Studio API отвечает.")
        lines.append("")
        lines.append("Доступные модели:")

        if ids:
            for model_id in ids:
                mark = "✅" if model_id == MODEL else "-"
                lines.append(f"{mark} {model_id}")
        else:
            lines.append("- Модели не найдены.")

        if MODEL in ids:
            lines.append("")
            lines.append(f"Итог: ✅ текущая модель `{MODEL}` доступна.")
        else:
            lines.append("")
            lines.append(f"Итог: ⚠️ текущая модель `{MODEL}` НЕ найдена в списке /v1/models.")

    except Exception as e:
        lines.append("Статус: ❌ LM Studio API не отвечает.")
        lines.append("")
        lines.append(f"Ошибка: {e}")
        lines.append("")
        lines.append("Что проверить:")
        lines.append("1. Открыт ли LM Studio.")
        lines.append("2. Запущен ли Local Server.")
        lines.append("3. Загружена ли модель.")
        lines.append("4. Порт должен быть 1234.")

    return "\n".join(lines)


def check_workspace():
    dirs = [
        ("ROOT", ROOT_DIR),
        ("Projects", PROJECTS_DIR),
        ("Reports", REPORTS_DIR),
        ("Notes", NOTES_DIR),
        ("Files", FILES_DIR),
        ("Windows", WINDOWS_DIR),
        ("memory", MEMORY_DIR),
    ]

    lines = [
        "## Проверка папок LocalComet",
        "",
    ]

    for name, path in dirs:
        if path.exists():
            lines.append(f"✅ {name}: {path}")
        else:
            lines.append(f"❌ {name}: {path}")

    return "\n".join(lines)


def check_memory():
    state = load_state()

    lines = [
        "## Проверка памяти LocalComet",
        "",
        f"STATE_FILE: {STATE_FILE}",
        "",
    ]

    if STATE_FILE.exists():
        lines.append("Статус: ✅ state.json найден.")
    else:
        lines.append("Статус: ⚠️ state.json пока не создан.")

    if not state:
        lines.append("")
        lines.append("Память пустая.")
        return "\n".join(lines)

    lines.append("")
    lines.append("Ключи памяти:")

    for key, value in state.items():
        value_text = _short_text(value, limit=500)
        lines.append(f"- {key}: {value_text}")

    return "\n".join(lines)


def check_reports():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    reports = sorted(
        REPORTS_DIR.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    lines = [
        "## Проверка отчетов",
        "",
        f"Папка: {REPORTS_DIR}",
        f"Всего отчетов: {len(reports)}",
        "",
    ]

    if not reports:
        lines.append("Отчетов пока нет.")
        return "\n".join(lines)

    lines.append("Последние отчеты:")

    for report in reports[:10]:
        modified = datetime.fromtimestamp(report.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"- {report.name} — {modified}")

    lines.append("")
    lines.append(f"last_report в памяти: {get_value('last_report', 'нет')}")

    return "\n".join(lines)


def check_files():
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    WINDOWS_DIR.mkdir(parents=True, exist_ok=True)

    notes = list(NOTES_DIR.glob("*.md"))
    files = [p for p in FILES_DIR.rglob("*") if p.is_file()]
    windows_files = [p for p in WINDOWS_DIR.rglob("*") if p.is_file()]

    lines = [
        "## Проверка файлов Workspace",
        "",
        f"Заметок: {len(notes)}",
        f"Файлов в Projects/Files: {len(files)}",
        f"Файлов в Projects/Windows: {len(windows_files)}",
        "",
        f"last_workspace_file: {get_value('last_workspace_file', 'нет')}",
        f"last_windows_file: {get_value('last_windows_file', 'нет')}",
    ]

    if files:
        lines.append("")
        lines.append("Последние файлы:")

        sorted_files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

        for file in sorted_files[:10]:
            lines.append(f"- {file.relative_to(FILES_DIR)}")

    return "\n".join(lines)


def check_last_error():
    last_error = get_value("last_error")

    if not last_error:
        return "Последней ошибки нет."

    return "Последняя ошибка:\n" + str(last_error)


def full_diagnostics():
    sections = [
        "# Диагностика LocalComet",
        "",
        check_lmstudio(),
        "",
        check_workspace(),
        "",
        check_memory(),
        "",
        check_reports(),
        "",
        check_files(),
        "",
        "## Последняя ошибка",
        "",
        check_last_error(),
    ]

    return "\n".join(sections)