import requests

from config import LMSTUDIO_API, MODEL

try:
    from core.project_context import build_system_prompt
except Exception:
    build_system_prompt = None


def _apply_no_think(user_text: str):
    text = str(user_text or "").strip()

    lower = text.lower()

    if "/think" in lower or "/no_think" in lower:
        return text

    return text + "\n\n/no_think"


LLM_OFFLINE_ERROR_PREFIX = "LLM_OFFLINE_ERROR:"


def format_llm_offline_message(error=None):
    return (
        "LLM server is offline. Start LM Studio Local Server at "
        "http://127.0.0.1:1234 and try again."
    )


def is_llm_offline_error(value):
    text = str(value or "")
    return text.startswith(LLM_OFFLINE_ERROR_PREFIX) or text == format_llm_offline_message()


def ask_llm(
    system,
    user,
    max_tokens=400,
    use_context=False,
    no_think=True,
    temperature=0.1,
    timeout=300
):
    """
    Главная функция запроса к LM Studio.

    По умолчанию:
    - НЕ добавляет Global Project Context
    - добавляет /no_think для Qwen3
    - держит низкую temperature для стабильного JSON

    use_context=True включать только там, где реально нужен контекст LocalComet:
    - финальные отчеты
    - анализ проекта
    - объяснения пользователю

    Для planner/router/extractor лучше оставлять use_context=False.
    """

    if use_context and build_system_prompt:
        full_system = build_system_prompt(system)
    else:
        full_system = system

    final_user = _apply_no_think(user) if no_think else user

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": full_system
            },
            {
                "role": "user",
                "content": final_user
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    try:
        response = requests.post(
            LMSTUDIO_API,
            json=payload,
            timeout=timeout
        )

        response.raise_for_status()

        data = response.json()

        return data["choices"][0]["message"]["content"]
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.RequestException,
    ) as e:
        return format_llm_offline_message(e)
