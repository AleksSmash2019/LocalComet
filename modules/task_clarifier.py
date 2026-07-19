from core.state import set_value
from modules import gpt_browser_bridge


FINAL_GOAL_MARKERS = [
    "ФИНАЛЬНАЯ УТОЧНЕННАЯ ЗАДАЧА:",
    "УЛУЧШЕННАЯ ЗАДАЧА:",
    "Улучшенная задача:",
    "Финальная задача:",
]


def _build_prompt(goal: str):
    return f"""
Ты помогаешь уточнять dev task для локального Python-проекта LocalComet.

ВАЖНО:
- Это НЕ запрос на patch.
- Не создавай response.json.
- Не создавай JSON patch.
- Не применяй изменения.
- Твоя задача — уточнить формулировку будущей задачи разработки.

Исходная задача пользователя:
{goal}

Верни ответ строго в таком формате:

ПОНИМАНИЕ:
кратко, что нужно сделать

ВОПРОСЫ/РИСКИ:
- что может быть неясно
- где возможны ошибки

ФАЙЛЫ:
- какие файлы вероятно менять

ФИНАЛЬНАЯ УТОЧНЕННАЯ ЗАДАЧА:
одна цельная формулировка dev task, которую можно вставить в LocalComet

КОНЕЦ
""".strip()


def extract_goal(answer: str):
    text = str(answer or "")

    for marker in FINAL_GOAL_MARKERS:
        index = text.find(marker)

        if index == -1:
            continue

        goal = text[index + len(marker):].strip()

        for end_marker in ["\nКОНЕЦ", "\nВОПРОСЫ", "\nФАЙЛЫ", "\nПОНИМАНИЕ"]:
            end_index = goal.find(end_marker)

            if end_index != -1:
                goal = goal[:end_index].strip()

        goal = goal.strip(" \n\r\t:-—")

        if goal:
            return goal

    return ""


def clarify_dev_task(goal: str, timeout_sec: int = 300):
    goal = str(goal or "").strip()

    if len(goal) < 20:
        result = {
            "ok": False,
            "answer": "STOP: задача слишком короткая для уточнения. Нужно минимум 20 символов.",
            "extracted_goal": "",
        }
        return result

    prompt = _build_prompt(goal)

    open_result = gpt_browser_bridge.open_chatgpt()
    paste_result = gpt_browser_bridge.paste_text(prompt)
    send_result = gpt_browser_bridge.send_prompt()
    wait_result = gpt_browser_bridge.wait_response(timeout_sec=int(timeout_sec or 300))
    answer = gpt_browser_bridge.read_last_assistant_message(limit=8000)

    extracted_goal = extract_goal(answer)

    if not extracted_goal:
        extracted_goal = goal

    set_value("last_task_clarifier_source_goal", goal)
    set_value("last_task_clarifier_answer", answer)
    set_value("last_task_clarifier_goal", extracted_goal)
    set_value("last_task_clarifier_open_result", open_result)
    set_value("last_task_clarifier_paste_result", paste_result)
    set_value("last_task_clarifier_send_result", send_result)
    set_value("last_task_clarifier_wait_result", wait_result)

    ok = "STOP:" not in str(answer)

    return {
        "ok": ok,
        "answer": answer,
        "extracted_goal": extracted_goal,
        "open_result": open_result,
        "paste_result": paste_result,
        "send_result": send_result,
        "wait_result": wait_result,
    }
