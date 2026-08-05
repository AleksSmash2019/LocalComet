from modules.codegen import generate_site, improve_site
from modules.browser import open_local_site, read_page
from modules.state_store import set_value, get_value


def handle(action: str, data: dict):
    if action == "create_project_site":
        prompt = data.get("prompt", "Создай современный сайт")
        site = generate_site(prompt)
        folder = site.get("folder")
        if not folder:
            return "Project Agent: generate_site не вернул folder."

        set_value("last_site", folder)

        print("Создан проект:")
        for file in site.get("created", []):
            print(file)

        return open_local_site(folder)

    if action == "review_site":
        folder = data.get("folder") or get_value("last_site")
        if not folder:
            return "Не знаю, какой сайт проверять."

        open_local_site(folder)
        return read_page()

    if action == "improve_last_site":
        folder = data.get("folder") or get_value("last_site")
        if not folder:
            return "Не знаю, какой сайт улучшать."

        result = improve_site(folder)
        result_folder = result.get("folder")
        if not result_folder:
            return "Project Agent: improve_site не вернул folder."
        set_value("last_site", result_folder)

        print("Улучшены файлы:")
        for file in result.get("changed", []):
            print(file)

        return open_local_site(result_folder)

    return "Project Agent: неизвестное действие."