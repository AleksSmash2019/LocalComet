from modules.codegen import generate_site, improve_site
from modules.browser import open_local_site, read_page
from core.state import set_value, get_value


def handle(action: str, data: dict):
    if action == "create_project_site":
        prompt = data.get("prompt", "Создай современный сайт")
        site = generate_site(prompt)

        set_value("last_site", site["folder"])

        print("Создан проект:")
        for file in site["created"]:
            print(file)

        return open_local_site(site["folder"])

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
        set_value("last_site", result["folder"])

        print("Улучшены файлы:")
        for file in result["changed"]:
            print(file)

        return open_local_site(result["folder"])

    return "Project Agent: неизвестное действие."