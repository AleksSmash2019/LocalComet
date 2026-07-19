import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import get_value, set_value
from modules.browser import (
    click_first_link,
    ensure_search_page,
    get_active_page_for_actions,
    get_browser_pages_for_actions,
    open_url,
    set_active_page_for_actions,
)


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports"
ACTION_REPORTS_DIR = REPORTS_DIR / "browser_actions"
SCREENSHOTS_DIR = REPORTS_DIR / "browser_screenshots"
BLANK_PAGE_MESSAGE = (
    "Страница пустая. Сначала выполни: browser search <запрос>, потом browser open first."
)

DANGEROUS_MARKERS = [
    "оплатить",
    "купить",
    "заказать",
    "удалить",
    "подтвердить",
    "отправить заявку",
    "ставка",
    "поставить",
    "перевести деньги",
    "login submit",
    "password",
    "card",
    "cvv",
    "bank",
    "kaspi",
    "parimatch",
    "gambling",
    "betting",
]


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    ACTION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def _short(text, limit=1800):
    text = str(text or "")

    if len(text) <= limit:
        return text

    return text[:limit] + "\n...[обрезано]"


def _is_dangerous_browser_action(text):
    lower = str(text or "").lower()
    return any(marker in lower for marker in DANGEROUS_MARKERS)


def _stop_if_dangerous(text):
    if _is_dangerous_browser_action(text):
        return "STOP: действие требует ручного подтверждения пользователя."

    return ""


def _page_state(page):
    if page is None:
        return "нет"

    try:
        return "закрыта" if page.is_closed() else "открыта"
    except Exception:
        return "ошибка"


def _is_blank_url(value):
    return str(value or "").strip().lower() in ["", "about:blank", "нет", "none", "null"]


def _safe_page_url(page):
    try:
        return str(page.url or "").strip()
    except Exception:
        return ""


def _safe_page_title(page):
    try:
        return str(page.title() or "").strip()
    except Exception:
        return ""


def _safe_body_text(page):
    try:
        return str(page.locator("body").inner_text(timeout=2000) or "").strip()
    except Exception:
        return ""


def _is_blank_page(page):
    page_url = _safe_page_url(page)
    current_url = str(get_value("current_url", "") or "").strip()

    if _is_blank_url(page_url):
        return True

    if _is_blank_url(current_url) and not page_url:
        return True

    return not _safe_page_title(page) and not _safe_body_text(page)


def _ensure_action_page(page=None, recover=True):
    if page is None:
        page = get_active_page_for_actions()

    if not _is_blank_page(page):
        page_url = _safe_page_url(page)

        if page_url:
            set_value("current_url", page_url)

        return page

    if not recover:
        return BLANK_PAGE_MESSAGE

    query = str(get_value("last_browser_query", "") or "").strip()

    if not query:
        return BLANK_PAGE_MESSAGE

    try:
        ensure_search_page(query)
        click_first_link()
        recovered_page = get_active_page_for_actions()

        if not _is_blank_page(recovered_page):
            recovered_url = _safe_page_url(recovered_page)

            if recovered_url:
                set_value("current_url", recovered_url)

            set_value("last_browser_action_recovery", f"recovered_from_query: {query}")
            return recovered_page

        return (
            "Страница пустая. Попытка восстановления по last_browser_query не дала "
            f"содержимого: {query}. Повтори: browser search <запрос>, потом browser open first."
        )
    except Exception as e:
        set_value("last_browser_error", str(e))
        return (
            "Страница пустая. Не удалось восстановить страницу по last_browser_query: "
            f"{query}. Ошибка: {e}\n"
            "Сначала выполни: browser search <запрос>, потом browser open first."
        )


def _blank_action_message(action, reason=""):
    reason = str(reason or BLANK_PAGE_MESSAGE)
    messages = {
        "summarize": "Summary недоступен, потому что страница пустая.",
        "links": "Ссылки не найдены, потому что страница пустая.",
        "inputs": "Поля ввода не найдены, потому что страница пустая.",
        "find_text": "Текст не найден, потому что страница пустая.",
        "click_text": "Клик не выполнен, потому что страница пустая.",
        "screenshot": "Скриншот не сделан, потому что страница пустая.",
    }
    return f"{messages.get(action, 'Browser action остановлен, потому что страница пустая.')}\n{reason}"


def _action_page_or_stop(page, action):
    ready = _ensure_action_page(page)

    if isinstance(ready, str):
        return None, _blank_action_message(action, ready)

    return ready, ""


def _remember(action, result="", error="", screenshot_path=""):
    set_value("last_browser_action", action)
    set_value("last_browser_result", _short(result))
    set_value("last_browser_error", str(error or ""))

    if screenshot_path:
        set_value("last_browser_screenshot", str(screenshot_path))


def _save_action_report(action, url_before, url_after, result, screenshot_path="", error=""):
    _ensure_dirs()
    path = ACTION_REPORTS_DIR / f"browser_action_{_stamp()}.md"
    lines = [
        "# Browser Action Report",
        "",
        f"- started_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- action: {action}",
        f"- url_before: {url_before}",
        f"- url_after: {url_after}",
        f"- screenshot_path: {screenshot_path or 'нет'}",
        f"- errors: {error or 'нет'}",
        "",
        "## Result",
        "```text",
        str(result or ""),
        "```",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_browser_action_report", str(path))
    return path


def _run_action(action, func, safety_text=""):
    stop = _stop_if_dangerous(safety_text)

    if stop:
        _remember(action, stop, stop)
        return stop

    page = None
    url_before = get_value("current_url", "нет")

    try:
        page = get_active_page_for_actions()
        if page.url:
            url_before = page.url
        result, screenshot_path = func(page)
        url_after = page.url if page is not None else url_before
        set_value("current_url", url_after)
        _remember(action, result, "", screenshot_path)
        _save_action_report(action, url_before, url_after, result, screenshot_path)
        return result
    except Exception as e:
        url_after = ""
        try:
            url_after = page.url if page is not None else url_before
        except Exception:
            url_after = url_before

        error = str(e)
        _remember(action, "", error)
        _save_action_report(action, url_before, url_after, "", error=error)
        return f"Browser action failed: {action}\nОшибка: {error}"


def browser_action_status():
    def run(page):
        title = ""
        current_url = get_value("current_url", "нет")

        try:
            title = page.title()
            current_url = page.url or current_url
        except Exception:
            pass

        result = (
            "Browser Action status:\n"
            f"- page: {_page_state(page)}\n"
            f"- current_url: {current_url}\n"
            f"- title: {title or 'нет'}\n"
            f"- last_browser_query: {get_value('last_browser_query', 'нет')}\n"
            f"- last_browser_action: {get_value('last_browser_action', 'нет')}\n"
            f"- last_browser_error: {get_value('last_browser_error', 'нет') or 'нет'}"
        )
        return result, ""

    return _run_action("action_status", run)


def screenshot_page():
    def run(page):
        page, stop = _action_page_or_stop(page, "screenshot")

        if stop:
            return stop, ""

        _ensure_dirs()
        path = SCREENSHOTS_DIR / f"browser_{_stamp()}.png"
        page.screenshot(path=str(path), full_page=True)
        return f"Screenshot сохранен:\n{path}", str(path)

    return _run_action("screenshot", run)


def find_text_on_page(text):
    def run(page):
        page, stop = _action_page_or_stop(page, "find_text")

        if stop:
            return f"{stop}\nЗапрошенный текст: {text}", ""

        body = page.locator("body").inner_text(timeout=10000)
        lower = body.lower()
        needle = str(text or "").lower()
        index = lower.find(needle)

        if index < 0:
            return f"Текст не найден: {text}", ""

        start = max(0, index - 160)
        end = min(len(body), index + len(str(text)) + 160)
        return f"Текст найден: {text}\n\nКонтекст:\n{body[start:end]}", ""

    return _run_action("find_text", run, text)


def click_by_text(text):
    def run(page):
        page, stop = _action_page_or_stop(page, "click_text")

        if stop:
            return f"{stop}\nТекст для клика: {text}", ""

        page.get_by_text(str(text or ""), exact=False).first.click(timeout=7000)
        page.wait_for_timeout(500)
        return f"Клик по тексту выполнен: {text}", ""

    return _run_action("click_text", run, text)


def click_selector(selector):
    def run(page):
        page.locator(str(selector or "")).first.click(timeout=7000)
        page.wait_for_timeout(500)
        return f"Клик по selector выполнен: {selector}", ""

    return _run_action("click_selector", run, selector)


def fill_by_label(label, value):
    safety_text = f"{label} {value}"

    def run(page):
        target = str(label or "").strip()
        value_text = str(value or "")
        locators = [
            lambda: page.get_by_label(target, exact=False),
            lambda: page.get_by_placeholder(target, exact=False),
            lambda: page.locator(f'[aria-label*="{target}" i]'),
            lambda: page.locator(f'input[name*="{target}" i], textarea[name*="{target}" i]'),
            lambda: page.locator(f'input[id*="{target}" i], textarea[id*="{target}" i]'),
        ]

        last_error = ""

        for locator_factory in locators:
            try:
                locator = locator_factory().first
                locator.fill(value_text, timeout=5000)
                return f"Поле заполнено: {label}", ""
            except Exception as e:
                last_error = str(e)

        raise RuntimeError(f"Поле не найдено: {label}. Последняя ошибка: {last_error}")

    return _run_action("fill_label", run, safety_text)


def fill_selector(selector, value):
    safety_text = f"{selector} {value}"

    def run(page):
        page.locator(str(selector or "")).first.fill(str(value or ""), timeout=7000)
        return f"Поле selector заполнено: {selector}", ""

    return _run_action("fill_selector", run, safety_text)


def press_key(key):
    def run(page):
        key_text = str(key or "Enter").strip() or "Enter"
        page.keyboard.press(key_text)
        page.wait_for_timeout(300)
        return f"Клавиша нажата: {key_text}", ""

    return _run_action("press_key", run, key)


def wait_page(ms=1000):
    try:
        ms = int(ms)
    except Exception:
        ms = 1000

    ms = max(0, min(ms, 30000))

    def run(page):
        page.wait_for_timeout(ms)
        return f"Ожидание выполнено: {ms} ms", ""

    return _run_action("wait", run)


def extract_links(limit=20):
    limit = max(1, min(int(limit or 20), 100))

    def run(page):
        page, stop = _action_page_or_stop(page, "links")

        if stop:
            set_value("last_browser_links", [])
            return stop, ""

        links = page.locator("a").evaluate_all(
            """
            (els, limit) => els.slice(0, limit).map(a => ({
                text: (a.innerText || a.textContent || '').trim().slice(0, 160),
                href: a.href || ''
            }))
            """,
            limit,
        )
        set_value("last_browser_links", links)

        if not links:
            return f"Ссылки не найдены на текущей странице.\nURL: {_safe_page_url(page) or 'нет'}", ""

        return json.dumps(links, ensure_ascii=False, indent=2), ""

    return _run_action("extract_links", run)


def extract_inputs(limit=30):
    limit = max(1, min(int(limit or 30), 100))

    def run(page):
        page, stop = _action_page_or_stop(page, "inputs")

        if stop:
            set_value("last_browser_inputs", [])
            return stop, ""

        inputs = page.locator("input, textarea, select, button").evaluate_all(
            """
            (els, limit) => els.slice(0, limit).map(el => ({
                tag: el.tagName.toLowerCase(),
                type: el.getAttribute('type') || '',
                placeholder: el.getAttribute('placeholder') || '',
                aria_label: el.getAttribute('aria-label') || '',
                name: el.getAttribute('name') || '',
                id: el.getAttribute('id') || '',
                text: (el.innerText || el.value || '').trim().slice(0, 120)
            }))
            """,
            limit,
        )
        set_value("last_browser_inputs", inputs)

        if not inputs:
            return f"Поля ввода не найдены на текущей странице.\nURL: {_safe_page_url(page) or 'нет'}", ""

        return json.dumps(inputs, ensure_ascii=False, indent=2), ""

    return _run_action("extract_inputs", run)


def summarize_page(limit=4000):
    def run(page):
        page, stop = _action_page_or_stop(page, "summarize")

        if stop:
            return stop, ""

        title = page.title()
        url = page.url
        headings = page.locator("h1, h2").evaluate_all(
            "els => els.slice(0, 12).map(el => (el.innerText || '').trim()).filter(Boolean)"
        )
        links = page.locator("a").evaluate_all(
            "els => els.slice(0, 10).map(a => ({text:(a.innerText||'').trim().slice(0,120), href:a.href||''}))"
        )
        text = page.locator("body").inner_text(timeout=10000)

        if not title.strip() and not text.strip():
            return _blank_action_message("summarize"), ""

        result = (
            f"URL: {url}\n"
            f"TITLE: {title}\n\n"
            f"HEADINGS:\n" + "\n".join(f"- {item}" for item in headings) + "\n\n"
            f"LINKS:\n" + "\n".join(f"- {item.get('text')}: {item.get('href')}" for item in links) + "\n\n"
            f"TEXT:\n{text[:limit]}"
        )
        return result, ""

    return _run_action("summarize", run)


def open_new_tab(url):
    def run(page):
        if not str(url or "").startswith(("http://", "https://", "file://")):
            raise ValueError("Новая вкладка требует полный URL http/https/file.")

        new_page = page.context.new_page()
        new_page.goto(url, wait_until="domcontentloaded", timeout=30000)
        set_active_page_for_actions(len(page.context.pages) - 1)
        return f"Открыта новая вкладка:\n{url}", ""

    return _run_action("open_new_tab", run, url)


def list_tabs():
    try:
        pages = get_browser_pages_for_actions()
        tabs = []

        for index, page in enumerate(pages):
            try:
                tabs.append({
                    "index": index,
                    "title": page.title(),
                    "url": page.url,
                })
            except Exception:
                tabs.append({"index": index, "title": "ошибка", "url": ""})

        set_value("last_browser_tabs", tabs)
        return json.dumps(tabs, ensure_ascii=False, indent=2)
    except Exception as e:
        _remember("list_tabs", "", e)
        return f"Не удалось получить вкладки: {e}"


def switch_tab(index):
    try:
        index = int(index)
        page = set_active_page_for_actions(index)
        result = f"Переключено на вкладку {index}:\n{page.url}"
        _remember("switch_tab", result)
        return result
    except Exception as e:
        _remember("switch_tab", "", e)
        return f"Не удалось переключить вкладку: {e}"


def close_current_tab():
    try:
        pages = get_browser_pages_for_actions()

        if len(pages) <= 1:
            return "Закрытие отменено: открыта только одна вкладка."

        current = get_active_page_for_actions()
        index = pages.index(current) if current in pages else len(pages) - 1
        current.close()
        next_index = max(0, min(index - 1, len(pages) - 2))
        page = set_active_page_for_actions(next_index)
        result = f"Текущая вкладка закрыта. Активна вкладка {next_index}:\n{page.url}"
        _remember("close_tab", result)
        return result
    except Exception as e:
        _remember("close_tab", "", e)
        return f"Не удалось закрыть вкладку: {e}"
