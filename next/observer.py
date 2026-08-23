import json
import sys
from json_repair import repair_json
from core.llm import ask_llm


SYSTEM = """
You are LocalComet Observer.

Analyze website/page text and return ONLY valid JSON.

Format:
{
  "summary": "short summary",
  "good": [
    "what is good"
  ],
  "problems": [
    "what is missing or weak"
  ],
  "score": 1
}

Rules:
- score must be from 1 to 10.
- problems must be concrete.
- do not use markdown.
- do not explain.
"""


def observe_page(page_text: str):
    answer = ask_llm(SYSTEM, page_text, max_tokens=800)
    answer = answer.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(repair_json(answer))
    except (ValueError, json.JSONDecodeError) as e:
        print(f"[observer] JSON parse error: {str(e)[:200]}", file=sys.stderr)
        return {"summary": "", "good": [], "problems": [], "score": 0}

    if not isinstance(data, dict):
        return {"summary": "", "good": [], "problems": [], "score": 0}

    return {
        "summary": data.get("summary", ""),
        "good": data.get("good", []),
        "problems": data.get("problems", []),
        "score": data.get("score", 0)
    }