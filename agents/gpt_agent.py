from modules.gpt_client import ask_gpt, gpt_status
from config import OPENAI_MODEL


def handle(action: str, data: dict):
    if action == "status":
        return gpt_status()

    if action == "model":
        return f"Текущая GPT-модель: {OPENAI_MODEL}"

    if action == "ask":
        prompt = data.get("prompt", "")

        return ask_gpt(
            prompt,
            max_output_tokens=data.get("max_output_tokens", 3000),
        )

    if action == "ask_code":
        prompt = data.get("prompt", "")

        system = (
            "Ты сильный Python-инженер для проекта LocalComet. "
            "Отвечай по-русски. "
            "Если предлагаешь изменения, объясняй безопасно и структурно. "
            "Не придумывай файлы, если их не видел."
        )

        return ask_gpt(
            prompt,
            system=system,
            max_output_tokens=data.get("max_output_tokens", 4000),
        )

    return "GPT Agent: неизвестное действие."