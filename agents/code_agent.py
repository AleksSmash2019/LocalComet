from modules.codegen import generate_site, improve_site
from modules.browser import open_local_site
from modules.state_store import set_value, get_value


def handle(action: str, data: dict):
    if action == "generate_site":
        prompt = data.get("prompt")
        if not prompt:
            return "Code Agent: нет prompt для генерации сайта."
        site = generate_site(prompt)
        folder = site.get("folder")
        if not folder:
            return "Code Agent: generate_site не вернул folder."

        set_value("last_site", folder)

        print("Создан сайт:")
        for file in site.get("created", []):
            print(file)

        return open_local_site(folder)

    if action == "improve_site":
        folder = data.get("folder") or get_value("last_site")

        if not folder:
            return "Не знаю, какой сайт улучшать."

        result = improve_site(folder)
        result_folder = result.get("folder")
        if not result_folder:
            return "Code Agent: improve_site не вернул folder."

        set_value("last_site", result_folder)

        print("Улучшены файлы:")
        for file in result.get("changed", []):
            print(file)

        return open_local_site(result_folder)

    return "Code Agent: неизвестное действие."