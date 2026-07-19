import threading
import urllib.parse
from pathlib import Path
from modules.project_paths import projects_dir

from playwright.sync_api import sync_playwright

from core.state import set_value, get_value


_playwright = None
_browser = None
_page = None
_owner_thread_id = None

PROJECTS_DIR = projects_dir()


def _remember_error(error):
    text = str(error or "")
    set_value("last_browser_error", text)
    return text


def _clear_error():
    set_value("last_browser_error", "")


def _is_closed_error(error):
    text = str(error or "").lower()

    markers = [
        "target page, context or browser has been closed",
        "browser has been closed",
        "context has been closed",
        "target closed",
        "page closed",
        "closed",
        "cannot switch to a different thread",
        "greenlet",
    ]

    return any(marker in text for marker in markers)


def _reset_browser(stop_playwright: bool = False, reason: str = ""):
    global _playwright, _browser, _page, _owner_thread_id

    errors = []

    try:
        if _page is not None:
            _page.close()
    except Exception as e:
        errors.append(f"page.close: {e}")

    try:
        if _browser is not None:
            _browser.close()
    except Exception as e:
        errors.append(f"browser.close: {e}")

    if stop_playwright:
        try:
            if _playwright is not None:
                _playwright.stop()
        except Exception as e:
            errors.append(f"playwright.stop: {e}")

        _playwright = None
        _owner_thread_id = None

    _page = None
    _browser = None

    set_value("last_browser_thread_reset_reason", str(reason or "reset_browser"))
    set_value("last_browser_thread_reset_errors", "\n".join(errors))
    set_value("last_browser_owner_thread_id", str(_owner_thread_id or ""))

    return errors


def _ensure_thread_owner():
    global _owner_thread_id

    current_thread_id = threading.get_ident()

    if _owner_thread_id is None:
        _owner_thread_id = current_thread_id
        set_value("last_browser_owner_thread_id", str(_owner_thread_id))
        return

    if _owner_thread_id != current_thread_id:
        old_thread_id = _owner_thread_id
        _reset_browser(
            stop_playwright=True,
            reason=f"thread_changed old={old_thread_id} new={current_thread_id}",
        )
        _owner_thread_id = current_thread_id
        set_value("last_browser_owner_thread_id", str(_owner_thread_id))


def close_browser_for_test():
    _reset_browser(stop_playwright=True, reason="close_browser_for_test")
    set_value("last_browser_error", "")
    return "Browser test: браузер программно закрыт полностью."


def _get_page(force_new: bool = False):
    global _playwright, _browser, _page, _owner_thread_id

    _ensure_thread_owner()

    if force_new:
        _reset_browser(stop_playwright=True, reason="force_new")
        _ensure_thread_owner()

    if _playwright is None:
        _playwright = sync_playwright().start()
        _owner_thread_id = threading.get_ident()
        set_value("last_browser_owner_thread_id", str(_owner_thread_id))

    try:
        if _browser is None or not _browser.is_connected():
            _browser = _playwright.chromium.launch(headless=False)
    except Exception:
        _reset_browser(stop_playwright=True, reason="browser_connection_failed")
        _ensure_thread_owner()
        _playwright = sync_playwright().start()
        _owner_thread_id = threading.get_ident()
        set_value("last_browser_owner_thread_id", str(_owner_thread_id))
        _browser = _playwright.chromium.launch(headless=False)

    try:
        if _page is None or _page.is_closed():
            _page = _browser.new_page()
    except Exception:
        _reset_browser(stop_playwright=True, reason="page_recreate_failed")
        _ensure_thread_owner()
        _playwright = sync_playwright().start()
        _owner_thread_id = threading.get_ident()
        set_value("last_browser_owner_thread_id", str(_owner_thread_id))
        _browser = _playwright.chromium.launch(headless=False)
        _page = _browser.new_page()

    return _page


def get_active_page_for_actions():
    return _get_page()


def get_browser_pages_for_actions():
    page = _get_page()
    return page.context.pages


def set_active_page_for_actions(index: int):
    global _page

    pages = get_browser_pages_for_actions()

    if index < 0 or index >= len(pages):
        raise IndexError(f"Нет вкладки с индексом {index}")

    _page = pages[index]
    _page.bring_to_front()
    set_value("current_url", _page.url)
    return _page


def _safe_page_call(func, recovery=None):
    try:
        _clear_error()
        return func(_get_page())
    except Exception as e:
        _remember_error(e)

        if not _is_closed_error(e):
            raise

        _reset_browser(stop_playwright=True, reason=f"recoverable_error: {e}")

        if recovery is not None:
            return recovery(_get_page())

        return func(_get_page())


def _duckduckgo_url(query):
    q = urllib.parse.quote_plus(str(query or ""))
    return f"https://duckduckgo.com/html/?q={q}"


def _search_url(query, engine="duckduckgo"):
    q = urllib.parse.quote_plus(str(query or ""))

    if engine == "bing":
        return f"https://www.bing.com/search?q={q}"

    return _duckduckgo_url(query)


def _goto_search_page(page, query, engine="duckduckgo"):
    url = _search_url(query, engine=engine)
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)

    set_value("last_browser_query", query)
    set_value("current_url", url)
    return url


def ensure_search_page(query=None):
    query = str(query or get_value("last_browser_query", "") or "").strip()

    if not query:
        return "Нет last_browser_query. Сначала выполни поиск."

    def run(page):
        url = _goto_search_page(page, query)
        return f"Открыл страницу поиска DuckDuckGo заново:\n{url}"

    return _safe_page_call(run)


def open_url(url):
    if not url:
        return "URL пустой."

    if not (
        url.startswith("http://")
        or url.startswith("https://")
        or url.startswith("file://")
    ):
        return open_local_site(url)

    def run(page):
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)
        set_value("current_url", url)
        return f"Открыл: {url}"

    return _safe_page_call(run)


def open_local_site(folder):
    file_path = PROJECTS_DIR / folder / "index.html"

    if not file_path.exists():
        return f"index.html не найден: {file_path}"

    url = file_path.resolve().as_uri()

    def run(page):
        page.goto(url, wait_until="domcontentloaded")
        set_value("current_url", url)
        return f"Открыл локальный сайт: {file_path}"

    return _safe_page_call(run)


def search(query, engine="duckduckgo"):
    query = str(query or "").strip()

    if not query:
        return "Поисковый запрос пустой."

    def run(page):
        _goto_search_page(page, query, engine=engine)
        return f"Ищу через {engine}: {query}"

    return _safe_page_call(run)


def read_page(limit=4000):
    def run(page):
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)

        title = page.title()
        current_url = page.url
        set_value("current_url", current_url)

        try:
            text = page.locator("body").inner_text(timeout=10000)
        except Exception as e:
            text = f"Не удалось прочитать страницу: {e}"
            _remember_error(e)

        return f"URL: {current_url}\nTITLE: {title}\n\n{text[:limit]}"

    def recovery(page):
        query = get_value("last_browser_query", "")

        if query:
            _goto_search_page(page, query)
            page.wait_for_timeout(1000)

        return run(page)

    return _safe_page_call(run, recovery=recovery)


def _normalize_result_url(href):
    if not href:
        return None

    if href.startswith("//"):
        href = "https:" + href

    parsed = urllib.parse.urlparse(href)
    query = urllib.parse.parse_qs(parsed.query)

    if "uddg" in query:
        href = urllib.parse.unquote(query["uddg"][0])

    bad_parts = [
        "duckduckgo.com/html",
        "duckduckgo.com/y.js",
        "google.com/search",
        "accounts.google",
        "bing.com/search",
        "youtube.com",
        "javascript:",
        "mailto:",
    ]

    if not href.startswith("http"):
        return None

    if any(bad in href for bad in bad_parts):
        return None

    return href


def get_search_result_links(limit=5):
    def run(page):
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)

        raw_links = page.locator("a").evaluate_all(
            """
            els => els.map(a => ({
                text: (a.innerText || '').trim(),
                href: a.href || ''
            }))
            """
        )

        clean = []
        seen = set()

        for item in raw_links:
            title = item.get("text", "").strip()
            href = item.get("href", "").strip()

            url = _normalize_result_url(href)

            if not url:
                continue

            if url in seen:
                continue

            if len(title) < 5:
                continue

            seen.add(url)

            clean.append({
                "title": title[:120],
                "url": url
            })

            if len(clean) >= limit:
                break

        return clean

    def recovery(page):
        query = get_value("last_browser_query", "")

        if query:
            _goto_search_page(page, query)

        return run(page)

    return _safe_page_call(run, recovery=recovery)


def click_text(text):
    def run(page):
        page.get_by_text(text, exact=False).first.click(timeout=7000)
        set_value("current_url", page.url)
        return f"Кликнул: {text}"

    return _safe_page_call(run)


def click_first_link():
    def run(page):
        links = get_search_result_links(limit=1)

        if not links:
            query = get_value("last_browser_query", "")

            if query:
                _goto_search_page(page, query)
                links = get_search_result_links(limit=1)

        if not links:
            raise Exception("Не нашел подходящую ссылку результата.")

        url = links[0]["url"]
        title = links[0]["title"]

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)

        set_value("current_url", url)

        return f"Открыл первый результат: {title}\n{url}"

    def recovery(page):
        query = get_value("last_browser_query", "")

        if query:
            _goto_search_page(page, query)

        return run(page)

    return _safe_page_call(run, recovery=recovery)


def browser_status():
    current_url = get_value("current_url", "нет")
    query = get_value("last_browser_query", "нет")
    error = get_value("last_browser_error", "нет")
    owner_thread = get_value("last_browser_owner_thread_id", "нет")
    reset_reason = get_value("last_browser_thread_reset_reason", "нет")

    page_state = "нет"

    try:
        page = _get_page()
        page_state = "открыта" if not page.is_closed() else "закрыта"
        if page.url:
            current_url = page.url
            set_value("current_url", current_url)
    except Exception as e:
        page_state = "ошибка"
        _remember_error(e)

    return (
        "Browser status:\n"
        f"- page: {page_state}\n"
        f"- current_url: {current_url}\n"
        f"- last_browser_query: {query}\n"
        f"- last_browser_error: {error or 'нет'}\n"
        f"- last_browser_owner_thread_id: {owner_thread}\n"
        f"- last_browser_thread_reset_reason: {reset_reason}"
    )
