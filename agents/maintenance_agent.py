from modules.maintenance import (
    memory_size,
    clear_memory,
    clear_last_result,
    compact_memory,
    backup_project,
    open_backups_folder,
)


def handle(action: str, data: dict):
    if action == "memory_size":
        return memory_size()

    if action == "clear_memory":
        return clear_memory()

    if action == "clear_last_result":
        return clear_last_result()

    if action == "compact_memory":
        return compact_memory()

    if action == "backup_project":
        return backup_project()

    if action == "open_backups_folder":
        return open_backups_folder()

    return "Maintenance Agent: неизвестное действие."