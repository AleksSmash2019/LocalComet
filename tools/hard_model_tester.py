import sys
import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


from core.llm import ask_llm
from config import MODEL


REPORTS_DIR = PROJECT_ROOT / "Projects" / "Reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


TESTS = [
    {
        "name": "operator_planner_strict",
        "type": "json",
        "system": """
You are LocalComet Browser Operator Planner.
Return ONLY valid JSON.
Do not use markdown.
Do not explain.

Available action:
{"tool":"operator","action":"compare_and_choose","query":"..."}
""",
        "user": """
User:
найди 5 лучших локальных LLM для моего ПК, сравни и выбери лучшую

Return the correct tool action.
"""
    },
    {
        "name": "research_planner_report_memory",
        "type": "json",
        "system": """
You are LocalComet Research Planner.
Return ONLY valid JSON.
Do not use markdown.
Do not explain.

Available actions:
{"tool":"research","action":"make_report","query":"..."}
{"tool":"research","action":"open_last_report"}
{"tool":"research","action":"read_last_report"}
""",
        "user": """
User:
покажи последний отчет

Return the correct action.
"""
    },
    {
        "name": "extract_llm_models_only",
        "type": "json_items",
        "system": """
Ты Browser Operator Extractor.

Верни только JSON.
Не используй markdown.
Не объясняй.

Формат:
{
  "items": [
    {
      "name": "Название",
      "category": "Категория",
      "pros": ["..."],
      "cons": ["..."],
      "best_for": "...",
      "notes": "..."
    }
  ]
}

Правила:
- Пользователь ищет локальные LLM.
- Извлекай только МОДЕЛИ.
- Не извлекай программы/платформы: LM Studio, Ollama, AnythingLLM, GPT4All, llama.cpp, Open WebUI.
""",
        "user": """
Цель:
найди 5 лучших локальных LLM для моего ПК

Текст страницы:
Лучшие инструменты для локального ИИ: LM Studio, Ollama, AnythingLLM, GPT4All.
Популярные модели: Qwen2.5-Coder-14B, Qwen3-14B, Gemma 3 12B, Llama 3.1 8B, Mistral Nemo 12B.
Для кодинга часто используют DeepSeek Coder и Qwen Coder.
"""
    },
    {
        "name": "multi_action_project",
        "type": "json_list",
        "system": """
You are LocalComet Project Planner.
Return ONLY valid JSON.
Do not use markdown.
Do not explain.

Available actions:
{"tool":"project","action":"create_project_site","prompt":"..."}
{"tool":"project","action":"review_site"}
{"tool":"project","action":"improve_last_site"}

If the request contains create + check + improve, return a LIST of actions.
""",
        "user": """
User:
создай современный сайт автосервиса с формой заявки, проверь и улучши
"""
    },
    {
        "name": "no_hallucination_choice",
        "type": "text",
        "system": """
Ты аналитик.
Сравни варианты только на основе данных.
Если данных мало, честно скажи.
Не выдумывай несуществующие модели.
""",
        "user": """
Данные:
1. Qwen2.5-Coder-14B — хорош для кода, работает в GGUF.
2. Gemma 3 12B — универсальная модель.
3. LM Studio — программа для запуска моделей.
4. Ollama — программа для запуска моделей.

Вопрос:
Какая лучшая LLM для LocalComet?
"""
    }
]


def clean_json_text(text: str):
    return (
        text.strip()
        .replace("```json", "")
        .replace("```python", "")
        .replace("```", "")
        .strip()
    )


def has_markdown_fence(text: str):
    return "```" in text


def parse_json(text: str):
    cleaned = clean_json_text(text)
    return json.loads(cleaned)


def score_answer(test: dict, answer: str):
    test_type = test["type"]
    score = 10
    issues = []

    if not answer or not answer.strip():
        return 0, ["Пустой ответ"]

    if has_markdown_fence(answer):
        score -= 3
        issues.append("Есть markdown-блоки ```")

    if test_type == "json":
        try:
            data = parse_json(answer)
            issues.append("JSON валидный")

            if not isinstance(data, dict):
                score -= 3
                issues.append("JSON не dict")

        except Exception:
            score -= 7
            issues.append("JSON невалидный")

    if test_type == "json_list":
        try:
            data = parse_json(answer)
            issues.append("JSON валидный")

            if not isinstance(data, list):
                score -= 5
                issues.append("Ожидался список действий")

            if isinstance(data, list) and len(data) < 3:
                score -= 2
                issues.append("Слишком мало действий")

        except Exception:
            score -= 7
            issues.append("JSON невалидный")

    if test_type == "json_items":
        try:
            data = parse_json(answer)
            items = data.get("items", [])

            issues.append("JSON валидный")

            names = [
                str(item.get("name", "")).lower()
                for item in items
                if isinstance(item, dict)
            ]

            bad_tools = [
                "lm studio",
                "ollama",
                "anythingllm",
                "gpt4all",
                "llama.cpp",
                "open webui",
            ]

            for bad in bad_tools:
                if any(bad in name for name in names):
                    score -= 4
                    issues.append(f"Ошибочно извлек платформу: {bad}")

            if len(items) < 5:
                score -= 2
                issues.append("Извлечено меньше 5 моделей")

            if any("qwen" in name for name in names):
                issues.append("Qwen найден")

            if any("gemma" in name for name in names):
                issues.append("Gemma найден")

        except Exception:
            score -= 7
            issues.append("JSON items невалидный")

    if test_type == "text":
        lower = answer.lower()

        if "lm studio" in lower and "лучш" in lower:
            score -= 3
            issues.append("Может путать платформу с моделью")

        if "qwen2.5-coder" in lower or "qwen" in lower:
            issues.append("Qwen выбран/упомянут")

        if len(answer) < 200:
            score -= 2
            issues.append("Слишком короткий анализ")

    score = max(0, min(score, 10))
    return score, issues


def run_tests():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"hard_model_test_{stamp}.md"

    total_score = 0

    lines = []
    lines.append("# Hard Model Test")
    lines.append("")
    lines.append(f"MODEL: {MODEL}")
    lines.append("")

    for test in TESTS:
        print("=" * 40)
        print("TEST:", test["name"])

        try:
            answer = ask_llm(
                test["system"],
                test["user"],
                max_tokens=1600
            )
        except Exception as e:
            answer = f"ERROR: {e}"

        score, issues = score_answer(test, answer)
        total_score += score

        lines.append(f"## TEST: {test['name']}")
        lines.append("")
        lines.append(f"Score: {score}/10")
        lines.append("")
        lines.append("Issues:")
        for issue in issues:
            lines.append(f"- {issue}")
        lines.append("")
        lines.append("### Answer")
        lines.append("")
        lines.append("```text")
        lines.append(answer)
        lines.append("```")
        lines.append("")

        print("SCORE:", f"{score}/10")
        print("ISSUES:")
        for issue in issues:
            print("-", issue)

        print()
        print(answer[:900])
        print()

    average = total_score / len(TESTS)

    lines.insert(3, f"AVERAGE SCORE: {average:.1f}/10")
    lines.insert(4, "")

    path.write_text("\n".join(lines), encoding="utf-8")

    print("=" * 40)
    print("СРЕДНИЙ БАЛЛ:", f"{average:.1f}/10")
    print("Тест сохранен:")
    print(path)


if __name__ == "__main__":
    run_tests()