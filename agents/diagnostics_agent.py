from modules.diagnostics import (
    full_diagnostics,
    check_lmstudio,
    check_workspace,
    check_memory,
    check_reports,
    check_files,
    check_last_error,
)


def handle(action: str, data: dict):
    if action == "full":
        return full_diagnostics()

    if action == "lmstudio":
        return check_lmstudio()

    if action == "workspace":
        return check_workspace()

    if action == "memory":
        return check_memory()

    if action == "reports":
        return check_reports()

    if action == "files":
        return check_files()

    if action == "last_error":
        return check_last_error()

    return "Diagnostics Agent: неизвестное действие."