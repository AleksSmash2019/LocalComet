from modules.history_log import (
    show_history,
    show_last_log,
    show_history_stats,
    clear_history,
    get_log_path,
)


def handle(action: str, data: dict):
    if action == "show":
        return show_history(data.get("limit", 20))

    if action == "last":
        return show_last_log()

    if action == "stats":
        return show_history_stats()

    if action == "clear":
        return clear_history()

    if action == "path":
        return get_log_path()

    return "History Agent: неизвестное действие."