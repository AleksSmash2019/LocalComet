import subprocess
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value, get_value
from modules.report_opener import open_last_report


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
NOTES_DIR = PROJECTS_DIR / "Notes"
FILES_DIR = PROJECTS_DIR / "Files"


def _ensure_dirs():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)


def _open_folder(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["explorer", str(path)])
    return f"Открыл папку: {path}"


def _safe_file_path(path: str):
    _ensure_dirs()

    raw = str(path or "").strip().replace("\\", "/")

    if not raw:
        return None, "Не указан путь файла."

    if ":" in raw or raw.startswith("/") or ".." in raw.split("/"):
        return None, "Небезопасный путь файла."

    file_path = FILES_DIR / raw

    if not file_path.suffix:
        file_path = file_path.with_suffix(".txt")

    file_path.parent.mkdir(parents=True, exist_ok=True)

    return file_path, None


def open_projects_folder():
    return _open_folder(PROJECTS_DIR)


def open_reports_folder():
    return _open_folder(REPORTS_DIR)


def open_files_folder():
    return _open_folder(FILES_DIR)


def list_reports(limit: int = 10):
    _ensure_dirs()

    reports = sorted(
        REPORTS_DIR.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not reports:
        return "Отчетов пока нет."

    lines = [f"Последние отчеты ({min(limit, len(reports))}):"]

    for i, report in enumerate(reports[:limit], start=1):
        lines.append(f"{i}. {report.name}")

    return "\n".join(lines)


def open_latest_report():
    return open_last_report()


def create_note(text: str):
    _ensure_dirs()

    text = str(text or "").strip()

    if not text:
        return "Нет текста для заметки."

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    note_path = NOTES_DIR / f"note_{stamp}.md"

    content = "# Заметка LocalComet\n\n" + text + "\n"
    note_path.write_text(content, encoding="utf-8")

    set_value("last_note", str(note_path))
    set_value("last_workspace_file", str(note_path))

    return f"Заметка создана: {note_path}"


def list_notes(limit: int = 10):
    _ensure_dirs()

    notes = sorted(
        NOTES_DIR.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not notes:
        return "Заметок пока нет."

    lines = [f"Последние заметки ({min(limit, len(notes))}):"]

    for i, note in enumerate(notes[:limit], start=1):
        lines.append(f"{i}. {note.name}")

    return "\n".join(lines)


def read_latest_note():
    _ensure_dirs()

    notes = sorted(
        NOTES_DIR.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not notes:
        return "Заметок пока нет."

    latest = notes[0]
    text = latest.read_text(encoding="utf-8")

    set_value("last_note", str(latest))
    set_value("last_workspace_file", str(latest))

    return f"Последняя заметка:\n{latest}\n\n{text}"


def create_text_file(path: str, content: str):
    file_path, error = _safe_file_path(path)

    if error:
        return error

    content = str(content or "")

    file_path.write_text(content, encoding="utf-8")

    set_value("last_workspace_file", str(file_path))

    return f"Файл создан: {file_path}"


def read_text_file(path: str):
    file_path, error = _safe_file_path(path)

    if error:
        return error

    if not file_path.exists():
        return f"Файл не найден: {file_path}"

    text = file_path.read_text(encoding="utf-8")

    set_value("last_workspace_file", str(file_path))

    return f"Содержимое файла:\n{file_path}\n\n{text}"


def list_files(limit: int = 20):
    _ensure_dirs()

    files = sorted(
        [p for p in FILES_DIR.rglob("*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not files:
        return "Файлов в Projects/Files пока нет."

    lines = [f"Файлы в Projects/Files ({min(limit, len(files))}):"]

    for i, file in enumerate(files[:limit], start=1):
        rel = file.relative_to(FILES_DIR)
        lines.append(f"{i}. {rel}")

    return "\n".join(lines)


def open_last_workspace_file():
    last_file = get_value("last_workspace_file")

    if not last_file:
        return "Последний workspace-файл не найден."

    path = Path(last_file)

    if not path.exists():
        return f"Файл не найден: {path}"

    subprocess.Popen(["notepad", str(path)])

    return f"Открыл файл: {path}"