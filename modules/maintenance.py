import zipfile
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import load_state, save_state, STATE_FILE


ROOT_DIR = get_project_root()
BACKUPS_DIR = Path.home() / "Documents" / "LocalAgent_Backups"


def _short(value, limit: int = 500):
    text = str(value or "")

    if len(text) > limit:
        return text[:limit] + "... [обрезано]"

    return text


def memory_size():
    if not STATE_FILE.exists():
        return "state.json не найден."

    size_kb = STATE_FILE.stat().st_size / 1024

    state = load_state()
    keys = list(state.keys())

    lines = [
        "Размер памяти LocalComet:",
        f"- Файл: {STATE_FILE}",
        f"- Размер: {size_kb:.2f} KB",
        f"- Ключей: {len(keys)}",
        "",
        "Ключи:",
    ]

    for key in keys:
        value = state.get(key)
        value_text = _short(value, 120)
        lines.append(f"- {key}: {value_text}")

    return "\n".join(lines)


def clear_memory():
    save_state({})
    return "Память LocalComet очищена. state.json теперь пустой."


def clear_last_result():
    state = load_state()

    removed = []

    for key in ["last_result", "last_error", "last_observation"]:
        if key in state:
            state.pop(key)
            removed.append(key)

    save_state(state)

    if not removed:
        return "last_result / last_error / last_observation уже пустые."

    return "Очищены ключи: " + ", ".join(removed)


def compact_memory(limit: int = 800):
    state = load_state()

    if not state:
        return "Память пустая, сжимать нечего."

    changed = []

    for key, value in list(state.items()):
        if isinstance(value, str) and len(value) > limit:
            state[key] = value[:limit] + "\n\n...[обрезано compact_memory]"
            changed.append(key)

    save_state(state)

    if not changed:
        return "Память уже компактная. Ничего не обрезано."

    return "Сжаты ключи памяти: " + ", ".join(changed)


def backup_project():
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUPS_DIR / f"LocalAgent_backup_{stamp}.zip"

    skip_parts = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
    }

    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in ROOT_DIR.rglob("*"):
            if any(part in skip_parts for part in path.parts):
                continue

            if path.is_file():
                arcname = path.relative_to(ROOT_DIR)
                zf.write(path, arcname)

    return f"Бэкап создан: {backup_path}"


def open_backups_folder():
    import subprocess

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["explorer", str(BACKUPS_DIR)])

    return f"Открыл папку бэкапов: {BACKUPS_DIR}"