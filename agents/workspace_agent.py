from modules.workspace import (
    open_projects_folder,
    open_reports_folder,
    open_files_folder,
    list_reports,
    open_latest_report,
    create_note,
    list_notes,
    read_latest_note,
    create_text_file,
    read_text_file,
    list_files,
    open_last_workspace_file,
)


def handle(action: str, data: dict):
    if action == "open_projects_folder":
        return open_projects_folder()

    if action == "open_reports_folder":
        return open_reports_folder()

    if action == "open_files_folder":
        return open_files_folder()

    if action == "list_reports":
        return list_reports()

    if action == "open_latest_report":
        return open_latest_report()

    if action == "create_note":
        return create_note(data.get("text", ""))

    if action == "list_notes":
        return list_notes()

    if action == "read_latest_note":
        return read_latest_note()

    if action == "create_text_file":
        return create_text_file(
            data.get("path", "file.txt"),
            data.get("content", "")
        )

    if action == "read_text_file":
        return read_text_file(data.get("path", ""))

    if action == "list_files":
        return list_files()

    if action == "open_last_workspace_file":
        return open_last_workspace_file()

    return "Workspace Agent: неизвестное действие."