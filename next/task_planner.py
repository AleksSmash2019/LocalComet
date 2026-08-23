import json
import sys
from json_repair import repair_json
from core.llm import ask_llm, is_llm_offline_error, format_llm_offline_message


SYSTEM = """
You are LocalComet Task Planner.

Split user goal into executable user-style commands.

Return ONLY valid JSON.

Format:
{
  "tasks": [
    "Изучи аналоги Comet и Claude Code и сделай краткий отчет"
  ]
}

CRITICAL RULES:
- Tasks must be executable by LocalComet.
- Use simple Russian commands.
- Do NOT write abstract tasks.
- Do NOT ask user for more information.

Research rules:
- If user asks to study/research/analyze/compare/find information/make report, return ONE task with the original meaning.
- Research task must include words like "изучи", "сравни", "сделай отчет" or "сделай краткий отчет".
- Do NOT create website tasks for research goals.

Website rules:
- If user asks to create a website, use:
  1. "Создай современный сайт ..."
  2. "Открой сайт"
  3. "Проверь сайт"
  4. "Улучши сайт"

Examples:

User goal:
Изучи аналоги Comet и Claude Code и сделай краткий отчет

Return:
{
  "tasks": [
    "Изучи аналоги Comet и Claude Code и сделай краткий отчет"
  ]
}

User goal:
Создай современный сайт автосервиса с формой заявки, открой его, проверь и улучши дизайн

Return:
{
  "tasks": [
    "Создай современный сайт автосервиса",
    "Открой сайт",
    "Проверь сайт",
    "Улучши сайт"
  ]
}

Do not use markdown.
Do not explain.
Return JSON only.
"""


def create_tasks(goal: str):
    answer = ask_llm(SYSTEM, goal, max_tokens=700)

    if is_llm_offline_error(answer):
        return [format_llm_offline_message()]

    answer = answer.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(repair_json(answer))
    except (ValueError, json.JSONDecodeError) as e:
        print(f"[task_planner] JSON parse error: {str(e)[:200]}", file=sys.stderr)
        return []

    if not isinstance(data, dict):
        return []

    return data.get("tasks", [])
