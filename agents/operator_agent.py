from modules.browser_operator import make_operator_report
from modules.codegen import format_sources_text
from modules.local_llm_picker import make_local_llm_picker_report
from modules.report_opener import open_report, remember_report


def _is_localcomet_llm_request(text: str):
    text = str(text or "").lower()

    has_localcomet = "localcomet" in text or "локалкомет" in text or "локал комет" in text

    has_model_words = (
        "llm" in text
        or "модель" in text
        or "модели" in text
        or "нейросет" in text
        or "квен" in text
        or "qwen" in text
        or "gemma" in text
        or "llama" in text
    )

    has_choose_words = (
        "лучш" in text
        or "выбери" in text
        or "сравни" in text
        or "подбери" in text
        or "какую" in text
        or "какой" in text
    )

    return has_localcomet and has_model_words and has_choose_words


def handle(action: str, data: dict):
    if action == "compare_and_choose":
        query = data.get("query") or data.get("prompt")

        if not query:
            return "Operator Agent: нет задачи для сравнения."

        if _is_localcomet_llm_request(query):
            result = make_local_llm_picker_report(query)
        else:
            result = make_operator_report(query)

        report_path = result.get("path")
        if not report_path:
            return "Operator Agent: отчёт не вернул path."
        report_text = result.get("report")
        if not report_text:
            return "Operator Agent: отчёт не вернул report."

        remember_report(report_path)
        opened = open_report(report_path)

        sources = result.get("sources", [])
        sources_text = format_sources_text(sources, fallback="Источники не использовались.")

        search_queries = result.get("search_queries", [])
        search_queries_text = "\n".join([f"- {q}" for q in search_queries]) if search_queries else "Поиск не выполнялся."

        return (
            "Сравнение создано:\n"
            + report_path
            + "\n\n"
            + opened
            + "\n\n"
            + "Поисковые запросы:\n"
            + search_queries_text
            + "\n\n"
            + f"Открыто источников: {result.get('collected_count', 0)}\n"
            + f"Извлечено вариантов: {len(result.get('items', []))}\n\n"
            + "Источники:\n"
            + sources_text
            + "\n\n"
            + report_text
        )

    return "Operator Agent: неизвестное действие."