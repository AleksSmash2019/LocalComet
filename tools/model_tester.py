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
        "name": "json_planning",
        "type": "json",
        "system": """
Ты LocalComet Planner.
Верни только JSON.
Не используй markdown.
""",
        "user": """
Пользователь сказал:
найди 5 лучших локальных LLM для моего ПК, сравни и выбери лучшую

Верни JSON в формате:
{"tool":"operator","action":"compare_and_choose","query":"..."}
"""
    },
    {
        "name": "code_fix",
        "type": "code",
        "system": """
Ты опытный Python-разработчик.
Исправь ошибку и верни только исправленный код.
Не используй markdown.
Не используй ```python.
""",
        "user": """
Исправь код:

def hello()
    print("hello")
"""
    },
    {
        "name": "research_summary",
        "type": "text",
        "system": """
Ты Research Agent.
Сделай краткий отчет на русском.
Пиши структурно, но без воды.
""",
        "user": """
Сравни Qwen3-14B, Qwen2.5-Coder-14B и Gemma 3 12B для локального агента на ПК с RTX 5070 12GB и 32GB RAM.
"""
    },
    {
        "name": "strict_json",
        "type": "json",
        "system": """
Ты строгий JSON генератор.
Верни только JSON.
Не используй markdown.
Не используй ```json.
""",
        "user": """
Создай план из 3 шагов для задачи:
создать отчет, открыть отчет, показать последний отчет

Формат:
{"tasks":["...","...","..."]}
"""
    }
]


def has_markdown_fence(text: str):
    return "```" in text


def is_valid_json(text: str):
    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        json.loads(cleaned)
        return True
    except Exception:
        return False


def score_answer(test_type: str, answer: str):
    score = 10
    issues = []

    if not answer or not answer.strip():
        return 0, ["Пустой ответ"]

    if has_markdown_fence(answer):
        score -= 3
        issues.append("Использует markdown-блоки ```")

    if test_type == "json":
        if not is_valid_json(answer):
            score -= 5
            issues.append("JSON невалидный")
        else:
            issues.append("JSON валидный")

    if test_type == "code":
        if "def hello():" not in answer:
            score -= 4
            issues.append("Код исправлен неочевидно или неправильно")
        else:
            issues.append("Код исправлен")

        if "```" in answer:
            score -= 2
            issues.append("Код завернут в markdown")

    if test_type == "text":
        if len(answer) < 300:
            score -= 3
            issues.append("Ответ слишком короткий")

        if "Qwen" not in answer and "Gemma" not in answer:
            score -= 3
            issues.append("Не упомянуты ключевые модели")

    score = max(0, min(score, 10))
    return score, issues


def run_tests():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"model_test_{stamp}.md"

    total_score = 0

    lines = []
    lines.append("# Model Test")
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
                max_tokens=1200
            )
        except Exception as e:
            answer = f"ERROR: {e}"

        score, issues = score_answer(test["type"], answer)
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
        print(answer[:700])
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