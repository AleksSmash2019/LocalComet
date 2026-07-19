import os
import json
import requests

from config import OPENAI_MODEL, OPENAI_RESPONSES_API


def _get_api_key():
    key = os.getenv("OPENAI_API_KEY", "").strip()

    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY не найден.\n"
            "Проверь, что ты выполнил:\n"
            'setx OPENAI_API_KEY "твой_ключ"\n'
            "После setx нужно полностью закрыть PowerShell и открыть заново."
        )

    return key


def _extract_output_text(data: dict):
    if not isinstance(data, dict):
        return str(data)

    direct = data.get("output_text")

    if direct:
        return str(direct)

    output = data.get("output", [])

    parts = []

    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue

            content = item.get("content", [])

            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue

                    block_type = block.get("type")

                    if block_type in ["output_text", "text"]:
                        text = block.get("text", "")

                        if text:
                            parts.append(str(text))

            text = item.get("text")

            if text:
                parts.append(str(text))

    if parts:
        return "\n".join(parts)

    return json.dumps(data, ensure_ascii=False, indent=2)


def ask_gpt(
    prompt: str,
    system: str = None,
    model: str = None,
    max_output_tokens: int = 3000,
):
    prompt = str(prompt or "").strip()

    if not prompt:
        return "GPT: пустой prompt."

    api_key = _get_api_key()
    selected_model = model or OPENAI_MODEL

    instructions = system or (
        "Ты GPT-мозг для локального Python-агента LocalComet. "
        "Отвечай по-русски, практично, без воды. "
        "Если речь про код — давай точные действия и безопасные решения."
    )

    payload = {
        "model": selected_model,
        "instructions": instructions,
        "input": prompt,
        "max_output_tokens": max_output_tokens,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            OPENAI_RESPONSES_API,
            headers=headers,
            json=payload,
            timeout=300,
        )

        if response.status_code >= 400:
            return (
                "GPT API ошибка.\n"
                f"HTTP: {response.status_code}\n"
                f"Ответ: {response.text[:3000]}"
            )

        data = response.json()
        return _extract_output_text(data)

    except Exception as e:
        return f"GPT request error: {e}"


def gpt_status():
    key = os.getenv("OPENAI_API_KEY", "").strip()

    if key:
        safe_key = key[:10] + "..." + key[-4:] if len(key) > 18 else "ключ найден"
        key_status = f"✅ OPENAI_API_KEY найден: {safe_key}"
    else:
        key_status = "❌ OPENAI_API_KEY не найден"

    return (
        "GPT Bridge status:\n"
        f"- {key_status}\n"
        f"- OPENAI_MODEL: {OPENAI_MODEL}\n"
        f"- API: {OPENAI_RESPONSES_API}"
    )