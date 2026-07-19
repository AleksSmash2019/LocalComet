from config import LMSTUDIO_API
from core.state import get_value, set_value


DEFAULT_PROVIDER = "lmstudio"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/chat"


def get_provider_config():
    provider_name = str(get_value("llm_provider_name", DEFAULT_PROVIDER) or DEFAULT_PROVIDER).strip().lower()

    if provider_name not in ["lmstudio", "ollama"]:
        provider_name = DEFAULT_PROVIDER

    return {
        "provider_name": provider_name,
        "lmstudio_url": str(get_value("llm_provider_lmstudio_url", LMSTUDIO_API) or LMSTUDIO_API),
        "ollama_url": str(get_value("llm_provider_ollama_url", DEFAULT_OLLAMA_URL) or DEFAULT_OLLAMA_URL),
    }


def set_provider(provider_name: str):
    provider_name = str(provider_name or "").strip().lower()

    if provider_name not in ["lmstudio", "ollama"]:
        return f"Unknown provider: {provider_name or 'empty'}"

    set_value("llm_provider_name", provider_name)
    return f"LLM provider set: {provider_name}"


def provider_status():
    config = get_provider_config()
    provider_name = config["provider_name"]
    url = config["lmstudio_url"] if provider_name == "lmstudio" else config["ollama_url"]

    return {
        "provider_name": provider_name,
        "active_url": url,
        "lmstudio_url": config["lmstudio_url"],
        "ollama_url": config["ollama_url"],
        "llm_provider_foundation": "да",
    }


def short_status():
    status = provider_status()
    return f"{status['provider_name']} ({status['active_url']})"
