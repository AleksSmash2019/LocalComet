from core.llm import ask_llm, is_llm_offline_error, format_llm_offline_message
from json_repair import repair_json
import json


SYSTEM = """
You are LocalComet Goal Manager.

Analyze the user's goal and return ONLY valid JSON.

Format:
{
  "goal": "short goal name",
  "type": "website|research|operator|browser|windows|files|code|unknown",
  "success_criteria": [
    "criterion 1",
    "criterion 2",
    "criterion 3"
  ]
}

Rules:
- If the user asks to find several options, compare options, choose the best, pick the best, rank tools, or make a top list, type must be "operator".
- If the user asks to study, research, analyze, find information, or make a report, type must be "research".
- If the user asks to create/generate/improve a website, type must be "website".
- Keep goal short.
- Success criteria must be concrete.
- Do not use markdown.
- Do not explain.
"""


def analyze_goal(user_goal: str):
    answer = ask_llm(SYSTEM, user_goal, max_tokens=700)

    if is_llm_offline_error(answer):
        return {
            "goal": "LLM offline",
            "type": "unknown",
            "success_criteria": [format_llm_offline_message()],
        }

    answer = answer.replace("```json", "").replace("```", "").strip()

    data = json.loads(repair_json(answer))

    return {
        "goal": data.get("goal", user_goal),
        "type": data.get("type", "unknown"),
        "success_criteria": data.get("success_criteria", [])
    }
