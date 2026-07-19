from modules.files import create_folder, write_file, read_file, list_files, delete_path


def handle(action: str, data: dict):
    if action == "create_folder":
        return create_folder(data["path"])

    if action == "write_file":
        return write_file(data["path"], data["content"])

    if action == "read_file":
        return read_file(data["path"])

    if action == "list_files":
        return list_files(data.get("path", ""))

    if action == "delete_path":
        return delete_path(data["path"])

    return "File Agent: неизвестное действие."