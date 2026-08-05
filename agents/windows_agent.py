from modules.windows import (
    open_app,
    type_text,
    append_text,
    read_notepad,
    clear_notepad,
    open_notepad_file,
)

from modules.state_store import set_value, get_value


def _normalize_app(app: str):
    app = str(app or "").strip().lower()

    aliases = {
        "блокнот": "notepad",
        "notepad": "notepad",
        "ноутпад": "notepad",
        "калькулятор": "calc",
        "calc": "calc",
        "calculator": "calc",
        "проводник": "explorer",
        "explorer": "explorer",
        "paint": "mspaint",
        "паинт": "mspaint",
        "пейнт": "mspaint",
    }

    return aliases.get(app, app)


def handle(action: str, data: dict):
    if action == "open_app":
        app = _normalize_app(data.get("app"))

        if not app:
            return "Windows Agent: не указано приложение."

        result = open_app(app)

        set_value("last_windows_app", app)
        set_value("last_windows_action", "open_app")

        return result

    if action == "type_text":
        text = data.get("text")

        if not text:
            return "Windows Agent: не указан текст для ввода."

        last_app = get_value("last_windows_app")

        result = type_text(text)

        set_value("last_windows_action", "type_text")
        set_value("last_windows_text", text)

        if last_app:
            return f"{result} Последнее активное приложение: {last_app}"

        return result

    if action == "append_text":
        text = data.get("text")

        if not text:
            return "Windows Agent: не указан текст для добавления."

        result = append_text(text)

        set_value("last_windows_action", "append_text")
        set_value("last_windows_text", text)
        set_value("last_windows_app", "notepad")

        return result

    if action == "read_notepad":
        set_value("last_windows_action", "read_notepad")
        set_value("last_windows_app", "notepad")

        return read_notepad()

    if action == "clear_notepad":
        set_value("last_windows_action", "clear_notepad")
        set_value("last_windows_app", "notepad")

        return clear_notepad()

    if action == "open_notepad_file":
        set_value("last_windows_action", "open_notepad_file")
        set_value("last_windows_app", "notepad")

        return open_notepad_file()

    return "Windows Agent: неизвестное действие."