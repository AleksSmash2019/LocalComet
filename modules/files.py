from pathlib import Path
from modules.project_paths import projects_dir
import shutil

BASE_DIR = projects_dir()
BASE_DIR.mkdir(parents=True, exist_ok=True)


def safe_path(path: str) -> Path:
    target = (BASE_DIR / path).resolve()

    if not str(target).startswith(str(BASE_DIR.resolve())):
        raise ValueError("Запрещенный путь за пределами Projects.")

    return target


def create_folder(path: str):
    target = safe_path(path)
    target.mkdir(parents=True, exist_ok=True)
    return f"Папка создана: {target}"


def write_file(path: str, content: str):
    target = safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Файл создан: {target}"


def read_file(path: str):
    target = safe_path(path)

    if not target.exists():
        return f"Файл не найден: {target}"

    return target.read_text(encoding="utf-8")


def list_files(path: str = ""):
    target = safe_path(path)

    if not target.exists():
        return f"Папка не найдена: {target}"

    items = []
    for item in target.iterdir():
        kind = "DIR " if item.is_dir() else "FILE"
        items.append(f"{kind}: {item.name}")

    return "\n".join(items) if items else "Папка пустая."


def delete_path(path: str):
    target = safe_path(path)

    if not target.exists():
        return f"Не найдено: {target}"

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    return f"Удалено: {target}"