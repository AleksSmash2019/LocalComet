from modules.files import create_folder, write_file, read_file, list_files, delete_path


def handle(action: str, data: dict):
    if action == "create_folder":
        path = data.get("path")
        if not path:
            return "File Agent: нет path для создания папки."
        return create_folder(path)

    if action == "write_file":
        path = data.get("path")
        content = data.get("content")
        if not path:
            return "File Agent: нет path для записи файла."
        if content is None:
            return "File Agent: нет content для записи файла."
        return write_file(path, content)

    if action == "read_file":
        path = data.get("path")
        if not path:
            return "File Agent: нет path для чтения файла."
        return read_file(path)

    if action == "list_files":
        return list_files(data.get("path", ""))

    if action == "delete_path":
        path = data.get("path")
        if not path:
            return "File Agent: нет path для удаления."
        return delete_path(path)

    return "File Agent: неизвестное действие."