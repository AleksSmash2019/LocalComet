from modules.browser import (
    search,
    open_url,
    open_local_site,
    read_page,
    click_text,
    click_first_link,
    ensure_search_page,
    browser_status,
)
from modules.browser_actions import (
    browser_action_status,
    click_by_text,
    click_selector,
    close_current_tab,
    extract_inputs,
    extract_links,
    fill_by_label,
    fill_selector,
    find_text_on_page,
    list_tabs,
    open_new_tab,
    press_key,
    screenshot_page,
    summarize_page,
    switch_tab,
    wait_page,
)
from modules.browser_task_runner import run_browser_steps, run_browser_workflow
from modules.browser_autopilot import (
    build_browser_autopilot_plan,
    format_browser_autopilot_plan,
    latest_browser_autopilot_report,
    observe_browser_page,
    run_browser_autopilot,
)
from modules.browser_super import (
    build_browser_super_plan,
    format_browser_super_plan,
    latest_browser_super_report,
    run_browser_research,
    run_browser_super,
    run_form_map,
    run_page_audit,
    run_platform_site_workflow,
    run_site_workflow,
    run_youtube_search,
)
from core.state import get_value, set_value


def _short(text, limit: int = 1500):
    value = str(text or "")

    if len(value) <= limit:
        return value

    return value[:limit] + "\n\n...[обрезано]"


def _save_browser_state(action: str, result: str = ""):
    set_value("last_browser_action", action)
    set_value("last_browser_result", _short(result))
    return result


def _save_browser_error(error):
    set_value("last_browser_error", str(error or ""))


def _friendly_browser_action_result(action: str, result: str):
    text = str(result or "").strip()
    hint = "Сначала выполни: browser search <запрос>, потом browser open first."

    if action == "extract_links" and text == "[]":
        return f"Ссылки не найдены, потому что страница пустая или на ней нет ссылок.\n{hint}"

    if action == "extract_inputs" and text == "[]":
        return f"Поля ввода не найдены, потому что страница пустая или на ней нет форм.\n{hint}"

    if action == "summarize" and "URL: about:blank" in text:
        return f"Summary недоступен, потому что страница пустая.\n{hint}"

    return result


def browser_last_search():
    query = get_value("last_browser_query", "")
    result = get_value("last_browser_result", "")
    action = get_value("last_browser_action", "")
    current_url = get_value("current_url", "")

    if not query and not result:
        return (
            "Последний browser-поиск не найден.\n"
            "Сначала выполни: найди <запрос>\n"
            "Или: browser search <запрос>"
        )

    return (
        "Последний browser-поиск:\n"
        f"- query: {query or 'нет'}\n"
        f"- action: {action or 'нет'}\n"
        f"- current_url: {current_url or 'нет'}\n"
        f"- result: {result or 'нет'}\n\n"
        "Дальше можно:\n"
        "- browser open first\n"
        "- browser read\n"
        "- browser status"
    )


def browser_open_first_result():
    query = get_value("last_browser_query", "")

    try:
        if query:
            ensure_search_page(query)

        result = click_first_link()
        set_value("last_browser_action", "open_first_result")
        set_value("last_browser_result", _short(result))

        if query:
            return (
                f"Открыл первый результат для прошлого поиска: {query}\n\n"
                f"{result}\n\n"
                "Дальше можно: browser read"
            )

        return (
            "Открыл первый результат на текущей странице.\n\n"
            f"{result}\n\n"
            "Дальше можно: browser read"
        )

    except Exception as e:
        _save_browser_error(e)
        return (
            "Не удалось открыть первый результат.\n"
            f"Ошибка: {e}\n\n"
            "Что сделать:\n"
            "1. Повтори поиск: найди <запрос>\n"
            "2. Потом: browser open first\n"
            "3. Или проверь: browser status"
        )


def browser_read_current_page():
    try:
        result = read_page()
        set_value("last_browser_action", "read_page")
        set_value("last_browser_result", _short(result))
        return result

    except Exception as e:
        _save_browser_error(e)
        query = get_value("last_browser_query", "")

        if query:
            try:
                ensure_search_page(query)
                result = read_page()
                set_value("last_browser_action", "read_page_recovered")
                set_value("last_browser_result", _short(result))
                return (
                    "Браузер был восстановлен по последнему поиску.\n\n"
                    f"{result}"
                )
            except Exception as second:
                _save_browser_error(second)
                return (
                    "Не удалось прочитать страницу даже после восстановления браузера.\n"
                    f"Ошибка: {second}"
                )

        return (
            "Не удалось прочитать страницу.\n"
            f"Ошибка: {e}\n"
            "Нет last_browser_query для восстановления."
        )


def browser_status_text():
    return browser_status()


def handle(action: str, data: dict):
    if action in ["super_plan", "browser_super_plan"]:
        task = data.get("task") or data.get("goal") or ""
        plan = build_browser_super_plan(task, mode="dry_run", max_results=data.get("max_results", 3))
        result = format_browser_super_plan(plan)
        return _save_browser_state("browser_super_plan", result)

    if action in ["super_run", "browser_super", "browser_super_run"]:
        task = data.get("task") or data.get("goal") or ""
        result = run_browser_super(task, mode="execute", max_results=data.get("max_results", 3))
        return _save_browser_state("browser_super_run", result)

    if action in ["research", "deep_research", "compare_research"]:
        task = data.get("task") or data.get("query") or data.get("goal") or ""
        result = run_browser_research(task, max_results=data.get("max_results", 3))
        return _save_browser_state("browser_research", result)

    if action in ["page_audit", "audit_page"]:
        task = data.get("task") or data.get("goal") or "current page"
        result = run_page_audit(task)
        return _save_browser_state("browser_page_audit", result)

    if action in ["form_map", "forms_map", "form_audit"]:
        task = data.get("task") or data.get("goal") or "current page"
        result = run_form_map(task)
        return _save_browser_state("browser_form_map", result)

    if action in ["build_site", "site_workflow", "platform_site_workflow"]:
        task = data.get("task") or data.get("prompt") or data.get("goal") or ""
        result = run_platform_site_workflow(task)
        return _save_browser_state("browser_platform_site_workflow", result)

    if action in ["youtube_search", "open_youtube_search"]:
        query = data.get("query") or data.get("task") or data.get("goal") or ""
        result = run_youtube_search(query)
        return _save_browser_state("browser_youtube_search", result)

    if action in ["local_site_workflow"]:
        task = data.get("task") or data.get("prompt") or data.get("goal") or ""
        result = run_site_workflow(task, improve=bool(data.get("improve")), force_local=True)
        return _save_browser_state("browser_local_site_workflow", result)

    if action in ["super_last_report", "browser_super_last_report"]:
        report = latest_browser_super_report()

        if not report:
            return _save_browser_state("browser_super_last_report", "Browser Super report пока не найден.")

        return _save_browser_state("browser_super_last_report", f"Browser Super last report:\n{report}")

    if action in ["observe", "browser_observe"]:
        result = observe_browser_page()
        return _save_browser_state("browser_observe", result)

    if action in ["plan", "autopilot_plan", "browser_plan"]:
        task = data.get("task") or data.get("goal") or ""
        plan = build_browser_autopilot_plan(task, mode="dry_run", max_steps=data.get("max_steps", 8))
        result = format_browser_autopilot_plan(plan)
        return _save_browser_state("browser_autopilot_plan", result)

    if action in ["autopilot", "autopilot_run", "browser_task"]:
        task = data.get("task") or data.get("goal") or ""
        result = run_browser_autopilot(task, mode="execute", max_steps=data.get("max_steps", 8))
        return _save_browser_state("browser_autopilot_run", result)

    if action in ["autopilot_dry", "dry_run"]:
        task = data.get("task") or data.get("goal") or ""
        result = run_browser_autopilot(task, mode="dry_run", max_steps=data.get("max_steps", 8))
        return _save_browser_state("browser_autopilot_dry", result)

    if action in ["autopilot_last_report", "last_autopilot_report"]:
        report = latest_browser_autopilot_report()

        if not report:
            return _save_browser_state("browser_autopilot_last_report", "Browser Autopilot report пока не найден.")

        return _save_browser_state("browser_autopilot_last_report", f"Browser Autopilot last report:\n{report}")

    if action == "search":
        query = data.get("query", "").strip()

        if not query:
            return "Browser Agent: пустой поисковый запрос."

        set_value("last_browser_query", query)
        result = search(query)
        _save_browser_state("search", result)

        return (
            f"{result}\n\n"
            "Поиск сохранен.\n"
            "Дальше можно:\n"
            "- browser open first\n"
            "- browser read\n"
            "- browser last\n"
            "- browser status"
        )

    if action == "open_url":
        result = open_url(data["url"])
        return _save_browser_state("open_url", result)

    if action == "open_local_site":
        folder = data.get("folder") or get_value("last_site")

        if not folder:
            return "Не знаю, какой сайт открыть."

        result = open_local_site(folder)
        return _save_browser_state("open_local_site", result)

    if action in ["read_page", "read_current_page", "browser_read"]:
        return browser_read_current_page()

    if action == "click_text":
        result = _friendly_browser_action_result("click_text", click_by_text(data.get("text", "")))
        return _save_browser_state("click_text", result)

    if action in ["click_first_link", "open_first_result", "browser_open_first"]:
        return browser_open_first_result()

    if action in ["last_search", "browser_last"]:
        return browser_last_search()

    if action in ["status", "browser_status"]:
        return browser_status_text()

    if action == "action_status":
        return _save_browser_state("action_status", browser_action_status())

    if action == "screenshot":
        result = _friendly_browser_action_result("screenshot", screenshot_page())
        return _save_browser_state("screenshot", result)

    if action == "find_text":
        text = data.get("text", "")
        result = _friendly_browser_action_result("find_text", find_text_on_page(text))
        return _save_browser_state("find_text", result)

    if action == "click_text":
        text = data.get("text", "")
        result = click_by_text(text)
        return _save_browser_state("click_text", result)

    if action == "click_selector":
        selector = data.get("selector", "")
        result = click_selector(selector)
        return _save_browser_state("click_selector", result)

    if action == "fill_label":
        result = fill_by_label(data.get("label", ""), data.get("value", ""))
        return _save_browser_state("fill_label", result)

    if action == "fill_selector":
        result = fill_selector(data.get("selector", ""), data.get("value", ""))
        return _save_browser_state("fill_selector", result)

    if action == "press_key":
        result = press_key(data.get("key", "Enter"))
        return _save_browser_state("press_key", result)

    if action == "wait":
        result = wait_page(data.get("ms", 1000))
        return _save_browser_state("wait", result)

    if action == "extract_links":
        result = _friendly_browser_action_result("extract_links", extract_links(data.get("limit", 20)))
        return _save_browser_state("extract_links", result)

    if action == "extract_inputs":
        result = _friendly_browser_action_result("extract_inputs", extract_inputs(data.get("limit", 30)))
        return _save_browser_state("extract_inputs", result)

    if action == "summarize":
        result = _friendly_browser_action_result("summarize", summarize_page(data.get("limit", 4000)))
        return _save_browser_state("summarize", result)

    if action == "open_new_tab":
        result = open_new_tab(data.get("url", ""))
        return _save_browser_state("open_new_tab", result)

    if action == "list_tabs":
        result = list_tabs()
        return _save_browser_state("list_tabs", result)

    if action == "switch_tab":
        result = switch_tab(data.get("index", 0))
        return _save_browser_state("switch_tab", result)

    if action == "close_tab":
        result = close_current_tab()
        return _save_browser_state("close_tab", result)

    if action == "browser_sequence":
        result = run_browser_steps(data.get("steps", []))
        return _save_browser_state("browser_sequence", result)

    if action in ["workflow", "run_workflow", "browser_workflow"]:
        steps = data.get("steps", [])
        title = data.get("title", "browser workflow")
        result = run_browser_workflow(steps, title)
        return _save_browser_state("browser_workflow", result)

    return "Browser Agent: неизвестное действие."
