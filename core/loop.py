from core.router import route
from core.planner import plan
from core.executor import execute
from core.llm import ask_llm


REVIEW_SYSTEM = """
You are LocalComet Task Reviewer.

Decide if the task is finished.

Return ONLY valid JSON.

Format:
{"done": true, "message": "Готово"}

or

{"done": false, "next_step": "Открой сайт AutoServicePro"}

Never use markdown.
Never explain.
"""


def run_loop(task: str, max_steps: int = 5):
    import json
    from json_repair import repair_json

    history = []
    current_task = task

    for step in range(1, max_steps + 1):
        print(f"\n--- STEP {step} ---")
        print("TASK:", current_task)

        try:
            route_name = route(current_task)
            print("ROUTE:", route_name)

            plan_result = plan(current_task, route_name)
            print("PLAN:", plan_result)

            result = execute(plan_result)
            print("RESULT:", result)

        except Exception as e:
            error_text = f"Шаг упал с ошибкой: {e}"
            print("STEP ERROR:", error_text)
            return error_text

        history.append({
            "step": step,
            "task": current_task,
            "route": route_name,
            "plan": plan_result,
            "result": str(result)
        })

        review_prompt = f"""
Original task:
{task}

History:
{history}

Question:
Is the original task finished?
If not, provide one next concrete user-style command for the agent.
"""

        try:
            review = ask_llm(REVIEW_SYSTEM, review_prompt, max_tokens=300)
            review = review.replace("```json", "").replace("```", "").strip()
            review_data = json.loads(repair_json(review))
        except Exception as e:
            print("REVIEW ERROR:", e)
            return "Задача выполнена частично, но проверка результата сломалась."

        print("REVIEW:", review_data)

        if review_data.get("done") is True:
            return review_data.get("message", "Готово")

        current_task = review_data.get("next_step", "")

        if not current_task:
            return "Остановлено: нет следующего шага."

    return "Остановлено: достигнут лимит шагов."