import subprocess
import time
from pathlib import Path
from modules.project_paths import projects_dir

from core.state import get_value, set_value


PROJECTS_DIR = projects_dir()
WINDOWS_DIR = PROJECTS_DIR / "Windows"
NOTEPAD_FILE = WINDOWS_DIR / "notepad_current.txt"


APP_COMMANDS = {
    "notepad": "notepad",
    "calc": "calc",
    "calculator": "calc",
    "mspaint": "mspaint",
    "paint": "mspaint",
    "chrome": "chrome",
    "explorer": "explorer",
}


def _normalize_app(app: str):
    app = str(app or "").strip().lower()

    aliases = {
        "блокнот": "notepad",
        "notepad": "notepad",
        "ноутпад": "notepad",

        "калькулятор": "calc",
        "calculator": "calc",
        "calc": "calc",

        "paint": "mspaint",
        "паинт": "mspaint",
        "пейнт": "mspaint",
        "mspaint": "mspaint",

        "chrome": "chrome",
        "хром": "chrome",

        "explorer": "explorer",
        "проводник": "explorer",
    }

    return aliases.get(app, app)


def _ensure_windows_dir():
    WINDOWS_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_notepad_file():
    _ensure_windows_dir()

    if not NOTEPAD_FILE.exists():
        NOTEPAD_FILE.write_text("", encoding="utf-8")

    set_value("last_windows_file", str(NOTEPAD_FILE))


def _open_notepad_file():
    _ensure_notepad_file()

    subprocess.Popen(["notepad", str(NOTEPAD_FILE)])
    time.sleep(1)

    set_value("last_windows_app", "notepad")
    set_value("last_windows_file", str(NOTEPAD_FILE))

    return f"Открыл Блокнот с файлом: {NOTEPAD_FILE}"


def _write_to_notepad_file(text: str):
    _ensure_notepad_file()

    NOTEPAD_FILE.write_text(text, encoding="utf-8")

    subprocess.Popen(["notepad", str(NOTEPAD_FILE)])
    time.sleep(1)

    set_value("last_windows_app", "notepad")
    set_value("last_windows_file", str(NOTEPAD_FILE))
    set_value("last_windows_text", text)

    return f"Текст записан в Блокнот: {text}"


def _append_to_notepad_file(text: str):
    _ensure_notepad_file()

    current = NOTEPAD_FILE.read_text(encoding="utf-8")

    if current.strip():
        new_text = current.rstrip() + "\n" + text
    else:
        new_text = text

    NOTEPAD_FILE.write_text(new_text, encoding="utf-8")

    subprocess.Popen(["notepad", str(NOTEPAD_FILE)])
    time.sleep(1)

    set_value("last_windows_app", "notepad")
    set_value("last_windows_file", str(NOTEPAD_FILE))
    set_value("last_windows_text", text)

    return f"Текст добавлен в Блокнот: {text}"


def _read_notepad_file():
    _ensure_notepad_file()

    text = NOTEPAD_FILE.read_text(encoding="utf-8")

    set_value("last_windows_app", "notepad")
    set_value("last_windows_file", str(NOTEPAD_FILE))

    if not text.strip():
        return "Блокнот пустой."

    return "Содержимое Блокнота:\n" + text


def _clear_notepad_file():
    _ensure_notepad_file()

    NOTEPAD_FILE.write_text("", encoding="utf-8")

    subprocess.Popen(["notepad", str(NOTEPAD_FILE)])
    time.sleep(1)

    set_value("last_windows_app", "notepad")
    set_value("last_windows_file", str(NOTEPAD_FILE))
    set_value("last_windows_text", "")

    return "Блокнот очищен."


def open_app(app: str):
    app = _normalize_app(app)

    try:
        if app == "notepad":
            return _open_notepad_file()

        command = APP_COMMANDS.get(app, app)

        subprocess.Popen(command, shell=True)
        time.sleep(1)

        set_value("last_windows_app", app)

        return f"Открыл: {app}"

    except Exception as e:
        return f"Ошибка открытия приложения {app}: {e}"


def type_text(text: str):
    text = str(text or "").strip()

    if not text:
        return "Нет текста для ввода."

    last_app = get_value("last_windows_app") or "notepad"
    last_app = _normalize_app(last_app)

    if last_app == "notepad":
        return _write_to_notepad_file(text)

    return (
        f"Для приложения {last_app} прямой ввод пока нестабилен. "
        f"Для Блокнота текст записывается через файл."
    )


def append_text(text: str):
    text = str(text or "").strip()

    if not text:
        return "Нет текста для добавления."

    return _append_to_notepad_file(text)


def read_notepad():
    return _read_notepad_file()


def clear_notepad():
    return _clear_notepad_file()


def open_notepad_file():
    return _open_notepad_file()