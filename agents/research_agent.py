from modules.codegen import format_sources_text
from modules.research import make_research_report
from modules.report_opener import open_report, open_last_report, read_last_report, remember_report


def handle(action: str, data: dict):
    if action == "make_report":
        query = data.get("query") or data.get("prompt")

        if not query:
            return "Research Agent: нет запроса для поиска."

        result = make_research_report(query)

        report_path = result.get("path")
        if not report_path:
            return "Research Agent: отчёт не вернул path."
        report_text = result.get("report")
        if not report_text:
            return "Research Agent: отчёт не вернул report."

        remember_report(report_path)

        sources = result.get("sources", [])
        sources_text = format_sources_text(sources, fallback="Источники не найдены.")

        search_queries = result.get("search_queries", [])
        search_queries_text = "\n".join([f"- {q}" for q in search_queries])

        opened = open_report(report_path)

        return (
            "Отчет создан:\n"
            + report_path
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
            + report_text
        )

    if action == "open_last_report":
        return open_last_report()

    if action == "read_last_report":
        return read_last_report()

    return "Research Agent: неизвестное действие."