import json
from json_repair import repair_json

from core.llm import ask_llm
from modules.files import create_folder, write_file, read_file, list_files


SITE_SYSTEM = """
Ты профессиональный frontend-разработчик.

Создай современный сайт.

Верни строго JSON:

{
  "folder": "SiteName",
  "files": [
    {
      "path": "SiteName/index.html",
      "content": "..."
    },
    {
      "path": "SiteName/style.css",
      "content": "..."
    },
    {
      "path": "SiteName/script.js",
      "content": "..."
    }
  ]
}

Правила:
- Всегда создавай index.html.
- Всегда создавай style.css.
- Желательно создавай script.js.
- Не используй markdown.
- Не объясняй.
- Только JSON.
"""


IMPROVE_SYSTEM = """
Ты профессиональный frontend-разработчик и UI/UX-дизайнер.

Тебе дают HTML и CSS сайта.
Улучши сайт визуально и структурно.

Верни строго JSON:

{
  "files": [
    {
      "path": "FolderName/index.html",
      "content": "..."
    },
    {
      "path": "FolderName/style.css",
      "content": "..."
    }
  ]
}

Правила:
- Не используй markdown.
- Не объясняй.
- Только JSON.
- Сохрани русский язык.
- Сделай дизайн современнее.
- Улучши hero-блок, карточки, кнопки, отступы и адаптивность.
"""


def generate_site(prompt):
    answer = ask_llm(SITE_SYSTEM, prompt, max_tokens=3000)
    answer = answer.replace("```json", "").replace("```", "").strip()

    fixed = repair_json(answer)
    data = json.loads(fixed)

    folder = data["folder"]
    create_folder(folder)

    created = []

    for file in data["files"]:
        write_file(file["path"], file["content"])
        created.append(file["path"])

    return {
        "folder": folder,
        "created": created
    }


def improve_site(folder):
    html_path = f"{folder}/index.html"
    css_path = f"{folder}/style.css"

    html = read_file(html_path)
    css = read_file(css_path)

    prompt = f"""
Folder:
{folder}

HTML:
{html}

CSS:
{css}

Task:
Improve this website design.
"""

    answer = ask_llm(IMPROVE_SYSTEM, prompt, max_tokens=4000)
    answer = answer.replace("```json", "").replace("```", "").strip()

    fixed = repair_json(answer)
    data = json.loads(fixed)

    changed = []

    for file in data["files"]:
        write_file(file["path"], file["content"])
        changed.append(file["path"])

    return {
        "folder": folder,
        "changed": changed
    }