from modules.research import make_research_report
from modules.report_opener import open_report, open_last_report, read_last_report, remember_report


def handle(action: str, data: dict):
    if action == "make_report":
        query = data.get("query") or data.get("prompt")

        if not query:
            return "Research Agent: нет запроса для поиска."

        result = make_research_report(query)

        remember_report(result["path"])

        sources = result.get("sources", [])
        source_lines = []

        for i, source in enumerate(sources[:8], start=1):
            source_lines.append(
                f"{i}. {source.get('title', 'Без названия')}\n"
                f"   {source.get('url', '')}"
            )

        sources_text = "\n".join(source_lines) if source_lines else "Источники не найдены."

        search_queries = result.get("search_queries", [])
        search_queries_text = "\n".join([f"- {q}" for q in search_queries])

        opened = open_report(result["path"])

        return (
            "Отчет создан:\n"
            + result["path"]
            + "\n\n"
            + opened
            + "\n\n"
            + "Поисковые запросы:\n"
            + search_queries_text
            + "\n\n"
            + f"Открыто источников: {result.get('collected_count', 0)}\n\n"
            + "Источники:\n"
            + sources_text
            + "\n\n"
            + result["report"]
        )

    if action == "open_last_report":
        return open_last_report()

    if action == "read_last_report":
        return read_last_report()

    return "Research Agent: неизвестное действие."