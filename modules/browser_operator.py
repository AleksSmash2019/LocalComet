import re
import json
from datetime import datetime
from json_repair import repair_json

from core.llm import ask_llm
from modules.browser import search, get_search_result_links, open_url, read_page
from modules.files import create_folder, write_file


USER_PC_PROFILE = """
Известный ПК пользователя:
- CPU: Intel Core i7-14700KF
- GPU: GeForce RTX 5070 12 GB
- RAM: 32 GB DDR5
- ОС: Windows
- Пользователь запускает локальные модели через LM Studio
"""


QUERY_SYSTEM = """
Ты Browser Operator Query Planner.

Твоя задача — превратить цель пользователя в 2-4 поисковых запроса.

Верни только JSON.

Формат:
{
  "queries": [
    "query 1",
    "query 2",
    "query 3"
  ]
}

Правила:
- Если пользователь просит найти варианты, сравнить и выбрать лучший — делай запросы под сравнение.
- Если пользователь спрашивает про локальные LLM для ПК — ищи именно модели, а не программы.
- Для локальных LLM добавляй: GGUF, LM Studio, 12GB VRAM, RTX, benchmarks.
- Если пользователь спрашивает про AI browser — добавляй Comet AI browser alternatives.
- Если пользователь спрашивает про Claude Code — добавляй Claude Code alternatives.
- Запросы должны быть короткие.
- Не используй markdown.
- Не объясняй.
"""


EXTRACT_SYSTEM = """
Ты Browser Operator Extractor.

Тебе дают текст одной страницы.
Нужно вытащить конкретные варианты, которые подходят под запрос пользователя.

Верни только JSON.

Формат:
{
  "items": [
    {
      "name": "Название",
      "category": "Категория",
      "pros": ["плюс 1", "плюс 2"],
      "cons": ["минус 1"],
      "best_for": "для кого подходит",
      "notes": "важная заметка"
    }
  ]
}

Строгие правила:
- Не выдумывай варианты, которых нет в тексте.
- Если пользователь ищет локальные LLM, извлекай только МОДЕЛИ.
- Если пользователь ищет локальные LLM, НЕ извлекай программы/платформы: LM Studio, Ollama, AnythingLLM, GPT4All, llama.cpp, Open WebUI, Jan.
- Если страница про инструменты запуска, бери только названия моделей, если они есть.
- Если страница мусорная или вариантов нет, верни {"items":[]}.
- Максимум 8 вариантов с одной страницы.
- Не используй markdown.
- Не объясняй.
"""


FINAL_SYSTEM = """
Ты Browser Operator.

Твоя задача — сравнить найденные варианты и выбрать лучший под задачу пользователя.

Верни обычный текст, не JSON.

Структура:

# Сравнение вариантов

## Задача
...

## Найденные варианты
...

## Таблица сравнения
...

## Лучший выбор
...

## Почему именно он
...

## Альтернативы
...

## Что сделать дальше
...

Правила:
- Пиши на русском.
- Будь практичным.
- Не выдумывай факты, которых нет в найденных данных.
- Если данных мало, честно напиши.
- Если задача связана с локальными LLM, учитывай железо пользователя.
- Если задача связана с локальными LLM, НЕ выбирай программу вместо модели.
- Если задача связана с локальными LLM, лучший выбор должен быть именно LLM-моделью.
- Для RTX 5070 12 GB нормально рассматривать 7B, 8B, 12B, 14B модели в GGUF Q4/Q5.
- Обязательно выбери лучший вариант, если данных достаточно.
- Обязательно закончи разделом "Что сделать дальше".
"""


BAD_LOCAL_LLM_TOOLS = [
    "lm studio",
    "ollama",
    "anythingllm",
    "gpt4all",
    "llama.cpp",
    "open webui",
    "jan",
    "koboldcpp",
    "text generation webui",
    "hugging face",
    "huggingface",
]


KNOWN_LOCAL_MODEL_PATTERNS = [
    "qwen",
    "qwen2.5",
    "qwen3",
    "qwen coder",
    "qwen2.5-coder",
    "gemma",
    "gemma 2",
    "gemma 3",
    "llama",
    "llama 3",
    "llama 3.1",
    "llama 3.2",
    "mistral",
    "mistral nemo",
    "mistral small",
    "deepseek",
    "deepseek coder",
    "deepseek r1",
    "phi",
    "phi-4",
    "mixtral",
    "starcoder",
    "starcoder2",
    "codellama",
    "nous hermes",
    "hermes",
    "zephyr",
    "openchat",
    "yi",
]


def _safe_filename(text: str):
    text = text.lower()
    text = re.sub(r"[^a-zа-я0-9]+", "_", text)
    text = text.strip("_")
    return text[:50] or "operator_report"


def _is_local_llm_goal(goal: str):
    text = goal.lower()

    return (
        "llm" in text
        or "локальн" in text and "модел" in text
        or "нейросет" in text and "пк" in text
        or "lm studio" in text
    )


def _target_count(goal: str):
    text = goal.lower()

    match = re.search(r"\b(\d{1,2})\b", text)

    if match:
        value = int(match.group(1))
        return max(1, min(value, 10))

    if "пять" in text:
        return 5

    if "три" in text:
        return 3

    if "топ" in text or "лучших" in text:
        return 5

    return 5


def _make_search_queries(goal: str):
    if _is_local_llm_goal(goal):
        return [
            "best local LLM models GGUF 12GB VRAM LM Studio",
            "best GGUF models RTX 12GB VRAM Qwen Gemma Llama Mistral",
            "best local coding LLM Qwen Coder DeepSeek Coder GGUF",
            "local LLM benchmark 7B 14B GGUF LM Studio",
        ]

    try:
        answer = ask_llm(QUERY_SYSTEM, goal, max_tokens=700)
        answer = answer.replace("```json", "").replace("```", "").strip()

        data = json.loads(repair_json(answer))
        queries = data.get("queries", [])

        if isinstance(queries, list) and queries:
            return queries[:4]

    except Exception:
        pass

    return [
        goal,
        f"{goal} comparison",
        f"{goal} best options",
    ]


def _collect_links(query: str, limit=4):
    search(query, engine="duckduckgo")
    links = get_search_result_links(limit=limit)

    if not links:
        search(query, engine="bing")
        links = get_search_result_links(limit=limit)

    return links


def _is_bad_local_llm_item(name: str):
    name = name.lower().strip()

    for bad in BAD_LOCAL_LLM_TOOLS:
        if bad in name:
            return True

    return False


def _normalize_item_name(name: str):
    name = name.strip()
    name = re.sub(r"\s+", " ", name)
    return name


def _extract_items(goal: str, source: dict):
    title = source.get("title", "")
    url = source.get("url", "")
    text = source.get("text", "")

    target_count = _target_count(goal)
    local_llm_goal = _is_local_llm_goal(goal)

    extra_rules = ""

    if local_llm_goal:
        extra_rules = """
Дополнительные правила для локальных LLM:
- Извлекай только названия моделей.
- Примеры моделей: Qwen, Qwen2.5-Coder, Qwen3, Gemma, Llama, Mistral, DeepSeek, Phi, Mixtral, StarCoder, Hermes, Zephyr.
- Не извлекай оболочки и программы: LM Studio, Ollama, AnythingLLM, GPT4All, llama.cpp, Open WebUI.
"""

    prompt = f"""
Цель пользователя:
{goal}

Нужно найти примерно {target_count} вариантов.

Источник:
{title}
{url}

Текст страницы:
{text[:6000]}

{extra_rules}

Вытащи конкретные варианты из источника.
"""

    try:
        answer = ask_llm(EXTRACT_SYSTEM, prompt, max_tokens=1800)
        answer = answer.replace("```json", "").replace("```", "").strip()

        data = json.loads(repair_json(answer))
        items = data.get("items", [])

        if not isinstance(items, list):
            return []

        cleaned = []

        for item in items:
            if not isinstance(item, dict):
                continue

            name = _normalize_item_name(item.get("name", ""))

            if not name:
                continue

            if local_llm_goal and _is_bad_local_llm_item(name):
                continue

            item["name"] = name
            item["source_title"] = title
            item["source_url"] = url
            cleaned.append(item)

        return cleaned

    except Exception:
        return []


def _keyword_candidates_from_sources(goal: str, sources: list):
    if not _is_local_llm_goal(goal):
        return []

    full_text = ""

    for source in sources:
        full_text += "\n" + source.get("title", "")
        full_text += "\n" + source.get("text", "")

    lower_text = full_text.lower()

    candidates = []

    model_map = [
        {
            "name": "Qwen2.5-Coder",
            "keywords": ["qwen2.5-coder", "qwen 2.5 coder", "qwen coder"],
            "best_for": "кодинг, локальный агент, работа с проектами",
        },
        {
            "name": "Qwen3",
            "keywords": ["qwen3", "qwen 3"],
            "best_for": "универсальные задачи, рассуждение, чат",
        },
        {
            "name": "Gemma 3",
            "keywords": ["gemma 3", "gemma3"],
            "best_for": "русский/английский чат, общее использование",
        },
        {
            "name": "Llama 3.1 / 3.2",
            "keywords": ["llama 3.1", "llama 3.2", "llama3.1", "llama3.2"],
            "best_for": "универсальное использование и совместимость",
        },
        {
            "name": "Mistral Nemo / Mistral Small",
            "keywords": ["mistral nemo", "mistral small"],
            "best_for": "быстрый локальный чат и баланс качества/скорости",
        },
        {
            "name": "DeepSeek Coder",
            "keywords": ["deepseek coder", "deepseek-coder"],
            "best_for": "программирование и работа с кодом",
        },
        {
            "name": "DeepSeek R1 Distill",
            "keywords": ["deepseek r1", "deepseek-r1", "r1 distill"],
            "best_for": "рассуждения и сложная логика",
        },
        {
            "name": "Phi-4",
            "keywords": ["phi-4", "phi 4"],
            "best_for": "лёгкая быстрая модель для повседневных задач",
        },
        {
            "name": "Hermes 2 Pro",
            "keywords": ["hermes 2 pro", "nous hermes", "hermes"],
            "best_for": "универсальный чат и инструкции",
        },
        {
            "name": "Zephyr 7B",
            "keywords": ["zephyr 7b", "zephyr"],
            "best_for": "лёгкий чат-помощник",
        },
    ]

    for model in model_map:
        found = False

        for keyword in model["keywords"]:
            if keyword.lower() in lower_text:
                found = True
                break

        if not found:
            continue

        candidates.append({
            "name": model["name"],
            "category": "Локальная LLM-модель",
            "pros": [
                "Найдена в источниках по локальным LLM",
                "Подходит для запуска через LM Studio/GGUF при наличии подходящей квантизации"
            ],
            "cons": [
                "Точные требования зависят от размера модели и квантизации"
            ],
            "best_for": model["best_for"],
            "notes": "Кандидат извлечен по упоминаниям в найденных источниках",
            "source_title": "Извлечено из найденных источников",
            "source_url": "multiple_sources"
        })

    return candidates


def _deduplicate_items(items: list, local_llm_goal: bool):
    result = []
    seen = set()

    for item in items:
        name = _normalize_item_name(item.get("name", ""))

        if not name:
            continue

        if local_llm_goal and _is_bad_local_llm_item(name):
            continue

        key = name.lower()

        if key in seen:
            continue

        seen.add(key)
        item["name"] = name
        result.append(item)

    return result


def _fallback_report(goal: str, search_queries: list, sources: list, items: list):
    lines = []

    lines.append("# Сравнение вариантов")
    lines.append("")
    lines.append("## Задача")
    lines.append(goal)
    lines.append("")
    lines.append("## Поисковые запросы")

    for q in search_queries:
        lines.append(f"- {q}")

    lines.append("")
    lines.append("## Источники")

    if not sources:
        lines.append("Источники не найдены.")
    else:
        for i, source in enumerate(sources, start=1):
            lines.append(f"{i}. {source.get('title', 'Без названия')}")
            lines.append(f"   {source.get('url', '')}")

    lines.append("")
    lines.append("## Найденные варианты")

    if not items:
        lines.append("Варианты не удалось надежно извлечь из источников.")
    else:
        for i, item in enumerate(items, start=1):
            lines.append(f"{i}. {item.get('name', 'Без названия')}")
            lines.append(f"   Для кого: {item.get('best_for', '')}")
            lines.append(f"   Источник: {item.get('source_url', '')}")

    lines.append("")
    lines.append("## Лучший выбор")
    lines.append("Автоматически выбрать лучший вариант не удалось — данных недостаточно.")
    lines.append("")
    lines.append("## Что сделать дальше")
    lines.append("- Повторить запрос более конкретно.")
    lines.append("- Проверить найденные источники вручную.")
    lines.append("- Использовать более сильную локальную модель для сравнения.")

    return "\n".join(lines)


def make_operator_report(goal: str):
    create_folder("Reports")

    target_count = _target_count(goal)
    local_llm_goal = _is_local_llm_goal(goal)

    search_queries = _make_search_queries(goal)

    all_links = []
    seen_urls = set()

    for query in search_queries:
        links = _collect_links(query, limit=5)

        for link in links:
            url = link.get("url")

            if not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)
            all_links.append(link)

            if len(all_links) >= 10:
                break

        if len(all_links) >= 10:
            break

    collected_sources = []

    for link in all_links[:7]:
        try:
            open_url(link["url"])
            text = read_page(limit=6500)

            collected_sources.append({
                "title": link.get("title", ""),
                "url": link.get("url", ""),
                "text": text
            })

        except Exception as e:
            collected_sources.append({
                "title": link.get("title", ""),
                "url": link.get("url", ""),
                "text": f"Не удалось открыть источник: {e}"
            })

    extracted_items = []

    for source in collected_sources:
        items = _extract_items(goal, source)
        extracted_items.extend(items)

    keyword_items = _keyword_candidates_from_sources(goal, collected_sources)
    extracted_items.extend(keyword_items)

    extracted_items = _deduplicate_items(extracted_items, local_llm_goal)

    hardware_context = ""

    if local_llm_goal:
        hardware_context = USER_PC_PROFILE

    items_text = json.dumps(extracted_items[:25], ensure_ascii=False, indent=2)

    sources_text = ""

    for i, source in enumerate(collected_sources, start=1):
        sources_text += f"""
SOURCE {i}
TITLE: {source.get("title", "")}
URL: {source.get("url", "")}

---
"""

    extra_final_rules = ""

    if local_llm_goal:
        extra_final_rules = f"""
Дополнительные правила:
- Пользователь просил примерно {target_count} локальных LLM.
- В итоговом списке должны быть именно модели, а не платформы.
- Не называй LM Studio, Ollama, AnythingLLM, GPT4All лучшей LLM — это инструменты/оболочки.
- Для RTX 5070 12 GB лучше рекомендовать модели 7B-14B в GGUF Q4/Q5.
- Если среди кандидатов есть Qwen2.5-Coder/Qwen Coder и задача связана с агентом/кодом, оцени его высоко.
"""

    prompt = f"""
Цель пользователя:
{goal}

Контекст пользователя:
{hardware_context}

Поисковые запросы:
{search_queries}

Источники:
{sources_text}

Извлеченные варианты:
{items_text}

{extra_final_rules}

Сравни варианты и выбери лучший.
"""

    try:
        report = ask_llm(FINAL_SYSTEM, prompt, max_tokens=4000)
    except Exception as e:
        report = f"Ошибка генерации сравнения: {e}"

    if not report or not report.strip():
        report = _fallback_report(goal, search_queries, collected_sources, extracted_items)

    if "## Что сделать дальше" not in report:
        report += """

## Что сделать дальше
- Проверить источники вручную.
- Повторить сравнение более точным запросом.
- Протестировать лучший вариант на практике.
"""

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = _safe_filename(goal)
    path = f"Reports/{stamp}_{name}_comparison.md"

    write_file(path, report)

    return {
        "path": path,
        "report": report,
        "sources": all_links,
        "search_queries": search_queries,
        "items": extracted_items,
        "collected_count": len(collected_sources),
        "target_count": target_count
    }