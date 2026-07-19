import re
import json
from datetime import datetime
from json_repair import repair_json

from core.llm import ask_llm
from modules.browser import search, read_page, open_url, get_search_result_links
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
Ты Research Query Planner.

Твоя задача — превратить запрос пользователя в 2-4 точных поисковых запроса.

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
- Если пользователь пишет Comet, уточняй как "Perplexity Comet browser" или "Comet AI browser".
- Если пользователь пишет Claude Code, уточняй как "Claude Code alternatives".
- Если пользователь спрашивает про локальные LLM для ПК, добавляй запросы про LM Studio, llama.cpp, Ollama, VRAM requirements.
- Запросы должны быть короткие и поисковые.
- Не используй markdown.
- Не объясняй.
"""


SOURCE_SUMMARY_SYSTEM = """
Ты Research Source Summarizer.

Тебе дают текст одной страницы.
Сделай короткое резюме источника.

Верни обычный текст, не JSON.

Структура:

Источник:
...

Полезные факты:
- ...
- ...
- ...

Ограничения источника:
- ...

Правила:
- Пиши на русском.
- Не выдумывай.
- Если текст мусорный, captcha или мало данных — так и напиши.
- Максимум 10 коротких пунктов.
"""


FINAL_REPORT_SYSTEM = """
Ты Research Agent.

Твоя задача — сделать полезный финальный отчет по кратким резюме источников.

Верни обычный текст, не JSON.

Структура отчета:

# Краткий отчет

## Тема
...

## Найденные источники
...

## Главное
...

## Сравнение
...

## Выводы
...

## Что стоит сделать дальше
...

Правила:
- Пиши на русском.
- Не пиши воду.
- Не выдумывай факты, если их нет в данных.
- Если данных мало, честно укажи это.
- Делай отчет прикладным.
- Для локальных LLM учитывай железо пользователя.
- Обязательно закончи разделом "Что стоит сделать дальше".
"""


def _safe_filename(text: str):
    text = text.lower()
    text = re.sub(r"[^a-zа-я0-9]+", "_", text)
    text = text.strip("_")
    return text[:50] or "report"


def _make_search_queries(query: str):
    try:
        answer = ask_llm(QUERY_SYSTEM, query, max_tokens=700)
        answer = answer.replace("```json", "").replace("```", "").strip()

        data = json.loads(repair_json(answer))
        queries = data.get("queries", [])

        if isinstance(queries, list) and queries:
            return queries[:4]

    except Exception:
        pass

    return [
        query,
        f"{query} alternatives",
        f"{query} comparison",
    ]


def _collect_links_for_query(query: str, limit=4):
    search(query, engine="duckduckgo")
    links = get_search_result_links(limit=limit)

    if not links:
        search(query, engine="bing")
        links = get_search_result_links(limit=limit)

    return links


def _summarize_source(query: str, source: dict):
    title = source.get("title", "")
    url = source.get("url", "")
    text = source.get("text", "")

    prompt = f"""
Запрос пользователя:
{query}

Название источника:
{title}

URL:
{url}

Текст источника:
{text[:5000]}

Сделай краткое резюме этого источника.
"""

    try:
        summary = ask_llm(SOURCE_SUMMARY_SYSTEM, prompt, max_tokens=900)
    except Exception as e:
        summary = f"Не удалось сделать резюме источника: {e}"

    if not summary or not summary.strip():
        summary = f"""
Источник:
{title}
{url}

Полезные факты:
- Модель не смогла сформировать резюме.
- Источник был найден и открыт, но анализ не выполнен.

Ограничения источника:
- Требуется ручная проверка.
"""

    return summary.strip()


def _fallback_report(query: str, collected: list, search_queries: list):
    lines = []

    lines.append("# Краткий отчет")
    lines.append("")
    lines.append("## Тема")
    lines.append(query)
    lines.append("")
    lines.append("## Поисковые запросы")

    for q in search_queries:
        lines.append(f"- {q}")

    lines.append("")
    lines.append("## Найденные источники")

    if not collected:
        lines.append("Источники не найдены.")
    else:
        for i, item in enumerate(collected, start=1):
            lines.append(f"{i}. {item.get('title', 'Без названия')}")
            lines.append(f"   {item.get('url', '')}")

    lines.append("")
    lines.append("## Главное")
    lines.append("Поиск источников выполнен, но финальный анализ не был сформирован моделью.")
    lines.append("")
    lines.append("## Выводы")
    lines.append("Нужно повторить исследование или уменьшить объем данных для модели.")
    lines.append("")
    lines.append("## Что стоит сделать дальше")
    lines.append("- Повторить поиск более точным запросом.")
    lines.append("- Проверить найденные источники вручную.")
    lines.append("- Использовать более сильную локальную модель для финального анализа.")

    return "\n".join(lines)


def make_research_report(query: str):
    create_folder("Reports")

    search_queries = _make_search_queries(query)

    all_links = []
    seen_urls = set()

    for search_query in search_queries:
        links = _collect_links_for_query(search_query, limit=4)

        for link in links:
            url = link.get("url")

            if not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)
            all_links.append(link)

            if len(all_links) >= 8:
                break

        if len(all_links) >= 8:
            break

    collected = []

    for link in all_links[:6]:
        try:
            open_url(link["url"])
            text = read_page(limit=5000)

            collected.append({
                "title": link["title"],
                "url": link["url"],
                "text": text
            })

        except Exception as e:
            collected.append({
                "title": link["title"],
                "url": link["url"],
                "text": f"Не удалось открыть источник: {e}"
            })

    if not collected:
        page_text = read_page(limit=5000)
        collected.append({
            "title": "Страница поиска",
            "url": "search_results",
            "text": page_text
        })

    source_summaries = []

    for item in collected:
        summary = _summarize_source(query, item)

        source_summaries.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "summary": summary
        })

    summaries_text = ""

    for i, item in enumerate(source_summaries, start=1):
        summaries_text += f"""
SOURCE SUMMARY {i}
TITLE: {item.get("title", "")}
URL: {item.get("url", "")}
SUMMARY:
{item.get("summary", "")}

---
"""

    hardware_context = ""

    if "пк" in query.lower() or "pc" in query.lower() or "llm" in query.lower():
        hardware_context = USER_PC_PROFILE

    prompt = f"""
Запрос пользователя:
{query}

Контекст пользователя:
{hardware_context}

Поисковые запросы:
{search_queries}

Краткие резюме источников:
{summaries_text}

Сделай финальный краткий отчет.
"""

    try:
        report = ask_llm(FINAL_REPORT_SYSTEM, prompt, max_tokens=3200)
    except Exception as e:
        report = f"Ошибка генерации отчета: {e}"

    if not report or not report.strip():
        report = _fallback_report(query, collected, search_queries)

    if "## Что стоит сделать дальше" not in report:
        report += """

## Что стоит сделать дальше
- Проверить найденные источники вручную.
- Повторить исследование с более точным запросом.
- Использовать более сильную локальную модель для финального анализа.
"""

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = _safe_filename(query)
    path = f"Reports/{stamp}_{name}.md"

    write_file(path, report)

    return {
        "path": path,
        "report": report,
        "sources": all_links,
        "search_queries": search_queries,
        "source_summaries": source_summaries,
        "collected_count": len(collected)
    }