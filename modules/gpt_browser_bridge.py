import json
import os
import threading
import time
from pathlib import Path
from modules.project_paths import get_project_root

import pyperclip
from json_repair import repair_json
from playwright.sync_api import sync_playwright

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
PROFILE_DIR = PROJECTS_DIR / "BrowserProfile"
RELAY_DIR = PROJECTS_DIR / "ChatGPTRelay"
REQUEST_PATH = RELAY_DIR / "request.md"
RESPONSE_PATH = RELAY_DIR / "response.json"
RAW_ANSWER_PATH = RELAY_DIR / "gpt_browser_last_answer.txt"
RAW_RESPONSE_PATH = RELAY_DIR / "response_raw.md"
ERROR_REPORT_PATH = RELAY_DIR / "gpt_browser_response_error.md"
DOWNLOADS_DIR = RELAY_DIR / "Downloads"
BAD_RESPONSE_PATH = RELAY_DIR / "bad_response.json"

STRICT_JSON_INSTRUCTION = """
ВАЖНО ДЛЯ ОТВЕТА:
ГЛАВНЫЙ РЕЗУЛЬТАТ — создай скачиваемый файл response.json.
Файл response.json должен содержать строго валидный JSON с полями summary, operations, tests.
Не выводи большой JSON patch обычным текстом в чат, если можешь создать файл response.json.

Если создание файла response.json недоступно, верни ТОЛЬКО валидный JSON текстом:
- без markdown;
- без ```json;
- без объяснений до/после JSON;
- ответ должен начинаться с { и заканчиваться };
- JSON обязан содержать поля summary, operations, tests.

Не пиши вступление.
Не пиши "я вижу", "готово", "думал", пояснения или комментарии.
""".strip()

CHATGPT_URL = "https://chatgpt.com/"
GPT_BROWSER_CHAT_URL_KEY = "gpt_browser_chat_url"

_playwright = None
_context = None
_page = None
_owner_thread_id = None


def _remember_error(error):
    text = str(error or "")
    set_value("last_gpt_browser_error", text)
    return text


def _clear_error():
    set_value("last_gpt_browser_error", "")


def _saved_chat_url():
    return str(get_value(GPT_BROWSER_CHAT_URL_KEY, "") or "").strip()


def _target_chat_url():
    saved_chat_url = _saved_chat_url()
    return saved_chat_url if saved_chat_url else CHATGPT_URL


def set_chat_url(url):
    try:
        _clear_error()
        saved_chat_url = str(url or "").strip()

        if not saved_chat_url:
            raise ValueError("URL не указан.")

        if not saved_chat_url.startswith(("https://chatgpt.com/", "http://chatgpt.com/")):
            raise ValueError("Нужен URL chatgpt.com.")

        set_value(GPT_BROWSER_CHAT_URL_KEY, saved_chat_url)
        set_value("last_gpt_browser_action", "set_chat")
        set_value("last_gpt_browser_saved_chat_url", saved_chat_url)

        return (
            "GPT Browser Bridge: saved_chat_url сохранен.\n"
            f"saved_chat_url: {saved_chat_url}"
        )

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: не удалось сохранить saved_chat_url.\nОшибка: {e}"


def show_chat_url():
    saved_chat_url = _saved_chat_url()

    if not saved_chat_url:
        return "GPT Browser Bridge: saved_chat_url не задан."

    return f"GPT Browser Bridge saved_chat_url:\n{saved_chat_url}"


def clear_chat_url():
    set_value(GPT_BROWSER_CHAT_URL_KEY, "")
    set_value("last_gpt_browser_action", "clear_chat")
    set_value("last_gpt_browser_saved_chat_url", "")
    return "GPT Browser Bridge: saved_chat_url очищен."


def open_project_chat():
    saved_chat_url = _saved_chat_url()

    if not saved_chat_url:
        return "GPT Browser Bridge: saved_chat_url не задан. Сначала выполни: gpt browser set chat <url>"

    return open_chatgpt()


def _ensure_dirs():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    RELAY_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)



def _launch_persistent_context():
    """Launch visible browser with fixed downloads folder.

    Preference order:
    1. Installed Google Chrome
    2. Installed Microsoft Edge
    3. Playwright bundled Chromium
    """
    _ensure_dirs()

    base_kwargs = {
        "user_data_dir": str(PROFILE_DIR),
        "headless": False,
        "viewport": {"width": 1400, "height": 900},
        "accept_downloads": True,
        "downloads_path": str(DOWNLOADS_DIR),
        "args": [
            "--disable-blink-features=AutomationControlled",
        ],
    }

    last_error = None

    for channel, label in [
        ("chrome", "chrome"),
        ("msedge", "msedge"),
        (None, "chromium"),
    ]:
        try:
            kwargs = dict(base_kwargs)

            if channel:
                kwargs["channel"] = channel

            context = _playwright.chromium.launch_persistent_context(**kwargs)
            set_value("last_gpt_browser_engine", label)
            set_value("last_gpt_browser_downloads_dir", str(DOWNLOADS_DIR))
            return context

        except Exception as e:
            last_error = e
            set_value(f"last_gpt_browser_{label}_launch_error", str(e))

    raise RuntimeError(f"Не удалось открыть Chrome/Edge/Chromium: {last_error}")


def reset_bridge_state(reason=""):
    """Force reset Playwright globals without raising.

    Playwright sync objects are thread-affine. If a page/context/playwright was
    created in another thread, reusing it from the auto-cycle worker can fail
    with: cannot switch to a different thread.
    """
    global _playwright, _context, _page, _owner_thread_id

    errors = []

    try:
        if _page is not None:
            _page.close()
    except Exception as e:
        errors.append(f"page.close: {e}")

    try:
        if _context is not None:
            _context.close()
    except Exception as e:
        errors.append(f"context.close: {e}")

    try:
        if _playwright is not None:
            _playwright.stop()
    except Exception as e:
        errors.append(f"playwright.stop: {e}")

    _page = None
    _context = None
    _playwright = None
    _owner_thread_id = None

    set_value("last_gpt_browser_thread_reset_reason", str(reason or "manual_reset"))
    set_value("last_gpt_browser_thread_reset_errors", "\n".join(errors))
    set_value("last_gpt_browser_thread_reset_time", str(time.time()))

    if errors:
        return "GPT Browser Bridge: state reset выполнен с ошибками закрытия.\n" + "\n".join(errors)

    return "GPT Browser Bridge: state reset выполнен."


def _ensure_thread_owner():
    global _owner_thread_id

    current_thread_id = threading.get_ident()

    if _owner_thread_id is None:
        _owner_thread_id = current_thread_id
        set_value("last_gpt_browser_owner_thread_id", str(_owner_thread_id))
        return

    if _owner_thread_id != current_thread_id:
        old_thread_id = _owner_thread_id
        reset_bridge_state(
            f"thread_changed old={old_thread_id} new={current_thread_id}"
        )
        _owner_thread_id = current_thread_id
        set_value("last_gpt_browser_owner_thread_id", str(_owner_thread_id))


def _get_page(force_new: bool = False):
    global _playwright, _context, _page, _owner_thread_id

    _ensure_dirs()
    _ensure_thread_owner()

    if force_new:
        reset_bridge_state("force_new")
        _ensure_thread_owner()

    if _playwright is None:
        _playwright = sync_playwright().start()
        _owner_thread_id = threading.get_ident()
        set_value("last_gpt_browser_owner_thread_id", str(_owner_thread_id))

    if _context is None:
        _context = _launch_persistent_context()

    if _page is None or _page.is_closed():
        if _context.pages:
            _page = _context.pages[0]
        else:
            _page = _context.new_page()

    return _page


def close_bridge():
    global _playwright, _context, _page, _owner_thread_id

    closed = []
    errors = []

    try:
        if _page is not None and not _page.is_closed():
            _page.close()
            closed.append("page")
    except Exception as e:
        errors.append(f"page: {e}")

    try:
        if _context is not None:
            _context.close()
            closed.append("context")
    except Exception as e:
        errors.append(f"context: {e}")

    try:
        if _playwright is not None:
            _playwright.stop()
            closed.append("playwright")
    except Exception as e:
        errors.append(f"playwright: {e}")

    _page = None
    _context = None
    _playwright = None
    _owner_thread_id = None

    if closed:
        result = "GPT Browser Bridge: закрыт, BrowserProfile освобожден. Закрыто: " + ", ".join(closed)
    else:
        result = "GPT Browser Bridge: активный браузерный контекст не найден."

    if errors:
        result += "\nОшибки закрытия проигнорированы:\n" + "\n".join(errors)

    set_value("last_gpt_browser_action", "close")
    set_value("last_gpt_browser_close_result", result)
    set_value("last_gpt_browser_owner_thread_id", "")
    return result


def open_chatgpt():
    try:
        _clear_error()
        page = _get_page()
        saved_chat_url = _saved_chat_url()
        page.goto(_target_chat_url(), wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        set_value("last_gpt_browser_url", page.url)
        set_value("last_gpt_browser_action", "open")
        set_value("last_gpt_browser_profile", str(PROFILE_DIR))
        set_value("last_gpt_browser_saved_chat_url", saved_chat_url)

        return (
            "GPT Browser Bridge: ChatGPT открыт.\n"
            f"URL: {page.url}\n"
            f"saved_chat_url: {saved_chat_url if saved_chat_url else 'нет'}\n"
            f"Profile: {PROFILE_DIR}\n\n"
            "Если видишь экран входа — войди вручную один раз. Профиль сохранится."
        )

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: не удалось открыть ChatGPT.\nОшибка: {e}"


def _latest_request_path():
    candidates = [
        get_value("last_relay_dated_request", ""),
        get_value("last_relay_request", ""),
        get_value("last_relay_request_path", ""),
        get_value("last_request_path", ""),
        str(REQUEST_PATH),
    ]

    for candidate in candidates:
        if not candidate:
            continue

        path = Path(str(candidate))

        if path.exists() and path.is_file():
            return path

    dated_dir = RELAY_DIR / "Requests"

    if dated_dir.exists():
        requests = list(dated_dir.glob("request_*.md"))

        if requests:
            return max(requests, key=lambda p: p.stat().st_mtime)

    return REQUEST_PATH


def _find_prompt_input(page):
    selectors = [
        "[data-testid='prompt-textarea']",
        "textarea[data-testid='prompt-textarea']",
        "div[contenteditable='true']",
        "textarea",
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector).last
            locator.wait_for(timeout=5000)
            return locator
        except Exception:
            continue

    raise RuntimeError("Не нашел поле ввода ChatGPT.")


def paste_text(text: str):
    try:
        _clear_error()
        page = _get_page()
        saved_chat_url = _saved_chat_url()

        if "chatgpt.com" not in page.url:
            page.goto(_target_chat_url(), wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
        elif saved_chat_url and not page.url.startswith(saved_chat_url):
            page.goto(saved_chat_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

        value = str(text or "").strip()

        if not value:
            return "GPT Browser Bridge: paste_text получил пустой текст."

        pyperclip.copy(value)
        prompt = _find_prompt_input(page)
        prompt.click(timeout=7000)
        page.keyboard.press("Control+V")
        page.wait_for_timeout(1000)

        set_value("last_gpt_browser_action", "paste_text")
        set_value("last_gpt_browser_url", page.url)
        set_value("last_gpt_browser_saved_chat_url", saved_chat_url)
        set_value("last_gpt_browser_paste_text_len", str(len(value)))

        return (
            "GPT Browser Bridge: произвольный текст вставлен в ChatGPT.\n"
            f"URL: {page.url}\n"
            f"Символов: {len(value)}"
        )

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: не удалось вставить произвольный текст.\nОшибка: {e}"


def read_last_assistant_message(limit: int = 8000):
    try:
        _clear_error()
        page = _get_page()
        text = _last_assistant_text(page)
        text = str(text or "")

        if limit:
            text = text[:int(limit)]

        RAW_ANSWER_PATH.write_text(text, encoding="utf-8", errors="replace")
        set_value("last_gpt_browser_action", "read_last_assistant_message")
        set_value("last_gpt_browser_last_assistant_message", text[:4000])
        set_value("last_gpt_browser_last_answer_path", str(RAW_ANSWER_PATH))

        return text

    except Exception as e:
        _remember_error(e)
        return f"STOP: GPT Browser Bridge не смог прочитать последний assistant message.\nОшибка: {e}"


def clarify_task_prompt(text: str, timeout_sec: int = 300):
    from modules.task_clarifier import clarify_dev_task

    return clarify_dev_task(text, timeout_sec=timeout_sec)


def _active_cycle_instruction():
    cycle_id = str(get_value("last_true_auto_cycle_id", "") or "").strip()

    if not cycle_id:
        return ""

    goal_preview = str(get_value("last_true_auto_relay_goal", "") or "").strip()[:500]
    cycle_id_json = json.dumps(cycle_id, ensure_ascii=False)
    goal_preview_json = json.dumps(goal_preview, ensure_ascii=False)

    return f"""
FRESHNESS GUARD ДЛЯ АВТОЦИКЛА:
Это текущий auto-cycle request.
Обязательно добавь в корень JSON поле meta:

"meta": {{
  "cycle_id": {cycle_id_json},
  "goal_preview": {goal_preview_json}
}}

Правила:
- meta.cycle_id должен быть ровно: {cycle_id}
- meta.goal_preview должен кратко отражать текущую задачу.
- Не используй старые cycle_id из предыдущих сообщений.
- Не отдавай старый response_vXXX.json.
- Если создаешь файл, имя может быть response_{cycle_id}.json.
- JSON без правильного meta.cycle_id будет отклонен и patch не применится.
""".strip()

def paste_request():
    try:
        _clear_error()
        page = _get_page()
        saved_chat_url = _saved_chat_url()

        if "chatgpt.com" not in page.url:
            page.goto(_target_chat_url(), wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
        elif saved_chat_url and not page.url.startswith(saved_chat_url):
            page.goto(saved_chat_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

        request_path = _latest_request_path()

        if not request_path.exists():
            return f"GPT Browser Bridge: request.md не найден: {request_path}"

        original_text = request_path.read_text(encoding="utf-8", errors="replace")
        freshness_instruction = _active_cycle_instruction()
        parts = [original_text.rstrip(), STRICT_JSON_INSTRUCTION]

        if freshness_instruction:
            parts.append(freshness_instruction)

        text = "\n\n".join(parts) + "\n"
        pyperclip.copy(text)

        prompt = _find_prompt_input(page)
        prompt.click(timeout=7000)
        page.keyboard.press("Control+V")
        page.wait_for_timeout(1000)

        set_value("last_gpt_browser_request", str(request_path))
        set_value("last_gpt_browser_action", "paste_request")
        set_value("last_gpt_browser_url", page.url)
        set_value("last_gpt_browser_saved_chat_url", saved_chat_url)
        set_value("last_gpt_browser_strict_instruction", "true")
        set_value("last_gpt_browser_response_mode", "file_response_json_first")
        set_value("last_gpt_browser_active_cycle_id", str(get_value("last_true_auto_cycle_id", "") or ""))

        return (
            "GPT Browser Bridge: request вставлен в ChatGPT.\n"
            f"Файл: {request_path}\n"
            f"URL: {page.url}\n"
            f"saved_chat_url: {saved_chat_url if saved_chat_url else 'нет'}\n"
            f"Символов исходно: {len(original_text)}\n"
            f"Символов вставлено: {len(text)}\n"
            "Добавлена инструкция: главный результат — скачиваемый файл response.json; fallback — JSON-only текст.\n"
            "Добавлен Response Freshness Guard: meta.cycle_id для текущего автоцикла, если cycle_id активен.\n"
            "Автоскачивание файла пока не выполняется.\n\n"
            "Дальше: gpt browser send"
        )

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: не удалось вставить request.\nОшибка: {e}"


def send_prompt():
    try:
        _clear_error()
        page = _get_page()

        selectors = [
            "button[data-testid='send-button']",
            "button[aria-label*='Send']",
            "button[aria-label*='Отправить']",
            "button:has-text('Send')",
            "button:has-text('Отправить')",
        ]

        for selector in selectors:
            try:
                button = page.locator(selector).last
                button.click(timeout=3000)
                set_value("last_gpt_browser_action", "send")
                set_value("last_gpt_browser_send_time_epoch", str(time.time()))
                return "GPT Browser Bridge: запрос отправлен."
            except Exception:
                continue

        page.keyboard.press("Enter")
        set_value("last_gpt_browser_action", "send_enter")
        set_value("last_gpt_browser_send_time_epoch", str(time.time()))
        return "GPT Browser Bridge: запрос отправлен через Enter."

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: не удалось отправить запрос.\nОшибка: {e}"


def _main_text(page):
    try:
        return page.locator("main").inner_text(timeout=10000)
    except Exception:
        return page.locator("body").inner_text(timeout=10000)


def wait_response(timeout_sec: int = 600, stable_rounds: int = 5):
    try:
        _clear_error()
        page = _get_page()

        last_text = ""
        stable = 0
        started = time.time()

        while time.time() - started < timeout_sec:
            text = _main_text(page)

            if text == last_text:
                stable += 1
            else:
                stable = 0
                last_text = text

            stop_visible = False

            for selector in [
                "button[aria-label*='Stop']",
                "button[aria-label*='Остановить']",
                "button:has-text('Stop')",
                "button:has-text('Остановить')",
            ]:
                try:
                    if page.locator(selector).last.is_visible(timeout=500):
                        stop_visible = True
                        break
                except Exception:
                    pass

            if stable >= stable_rounds and not stop_visible:
                set_value("last_gpt_browser_action", "wait_done")
                set_value("last_gpt_browser_wait_seconds", str(int(time.time() - started)))
                set_value("last_gpt_browser_wait_timeout", str(timeout_sec))
                return (
                    "GPT Browser Bridge: ответ выглядит завершенным.\n"
                    f"Ожидание: {int(time.time() - started)} сек.\n"
                    f"Лимит: {timeout_sec} сек."
                )

            time.sleep(2)

        raise TimeoutError(f"Ответ не стабилизировался за {timeout_sec} сек.")

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: ожидание ответа завершилось ошибкой.\nОшибка: {e}"


def _last_assistant_text(page):
    selectors = [
        "[data-message-author-role='assistant']",
        "article",
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector)
            count = locator.count()

            if count:
                text = locator.nth(count - 1).inner_text(timeout=10000)

                if text.strip():
                    return text
        except Exception:
            continue

    return _main_text(page)


def _json_candidates_by_balance(raw: str):
    source = str(raw or "")
    starts = [i for i, ch in enumerate(source) if ch == "{"]

    for start in reversed(starts):
        depth = 0
        in_string = False
        escaped = False

        for index in range(start, len(source)):
            ch = source[index]

            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1

                if depth == 0:
                    yield source[start:index + 1]
                    break


def _json_candidates_from_fences(raw: str):
    text = str(raw or "")
    parts = text.split("```")

    for part in reversed(parts):
        clean = part.strip()

        if clean.lower().startswith("json"):
            clean = clean[4:].strip()

        if clean.startswith("{") and clean.endswith("}"):
            yield clean


def _looks_like_patch(data):
    return (
        isinstance(data, dict)
        and "summary" in data
        and "operations" in data
        and "tests" in data
        and isinstance(data.get("operations"), list)
        and isinstance(data.get("tests"), list)
    )


def _try_parse_patch(candidate: str):
    errors = []

    for payload in [candidate, repair_json(candidate)]:
        try:
            data = json.loads(payload)

            if _looks_like_patch(data):
                return data, ""
        except Exception as e:
            errors.append(str(e))

    return None, " | ".join(errors[-3:])


def _extract_json_patch(text: str):
    raw = str(text or "").strip()
    raw = raw.replace("```json", "```").replace("```JSON", "```")

    errors = []
    candidates = []

    candidates.extend(_json_candidates_from_fences(raw))
    candidates.extend(_json_candidates_by_balance(raw))

    # Последняя попытка: весь текст через json_repair.
    candidates.append(raw)

    seen = set()

    for candidate in candidates:
        candidate = str(candidate or "").strip()

        if not candidate or candidate in seen:
            continue

        seen.add(candidate)

        if "summary" not in candidate and "operations" not in candidate:
            continue

        data, error = _try_parse_patch(candidate)

        if data is not None:
            return data

        if error:
            errors.append(error)

    raise ValueError(
        "В ответе не найден валидный JSON patch с summary/operations/tests. "
        + ("Ошибки парсинга: " + " || ".join(errors[-5:]) if errors else "")
    )


def _save_error_report(source: str, error):
    _ensure_dirs()

    lines = [
        "# GPT Browser Response Parse Error",
        "",
        f"- Ошибка: {error}",
        f"- raw_answer: {RAW_ANSWER_PATH}",
        f"- response_raw: {RAW_RESPONSE_PATH}",
        f"- response_json: {RESPONSE_PATH}",
        "",
        "## Что делать",
        "- Выполни: gpt browser repair response",
        "- Если снова ошибка — открой raw файл и проверь, есть ли там JSON.",
        "",
        "## Начало сырого ответа",
        "```text",
        str(source or "")[:5000],
        "```",
    ]

    ERROR_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_gpt_browser_error_report", str(ERROR_REPORT_PATH))
    return ERROR_REPORT_PATH



CONFIRMATION_SUMMARY_MARKERS = [
    "принято",
    "готово",
    "буду делать",
    "буду создавать",
    "буду по возможности",
    "дальше для localcomet",
    "дальше для localagent",
    "создавать скачиваемый файл",
    "не выводить большой json",
    "acknowledged",
    "accepted",
]


def _summary_looks_like_confirmation(summary):
    text = str(summary or "").lower()
    return any(marker in text for marker in CONFIRMATION_SUMMARY_MARKERS)


def _is_empty_confirmation_patch(data):
    return (
        isinstance(data, dict)
        and isinstance(data.get("operations"), list)
        and not data.get("operations")
        and _summary_looks_like_confirmation(data.get("summary", ""))
    )


def _write_bad_response(reason, data):
    _ensure_dirs()

    payload = {
        "reason": str(reason),
        "patch": data,
    }

    BAD_RESPONSE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_value("last_gpt_browser_bad_response", str(BAD_RESPONSE_PATH))
    set_value("last_gpt_browser_bad_response_reason", str(reason))

    return BAD_RESPONSE_PATH


def _schema_errors(data):
    errors = []

    if not isinstance(data, dict):
        return ["patch должен быть JSON object"]

    if not isinstance(data.get("summary"), str):
        errors.append("summary должен быть строкой")

    if not isinstance(data.get("operations"), list):
        errors.append("operations должен быть списком")

    if not isinstance(data.get("tests"), list):
        errors.append("tests должен быть списком")

    if _is_empty_confirmation_patch(data):
        errors.append(
            "operations пустой, а summary похож на подтверждение вместо patch. "
            "Такой response.json считается bad_response."
        )

    for index, operation in enumerate(data.get("operations", []), start=1):
        if not isinstance(operation, dict):
            errors.append(f"операция #{index} не является объектом")
            continue

        op_type = operation.get("type")
        path = operation.get("path")

        if not isinstance(op_type, str) or not op_type:
            errors.append(f"операция #{index}: нет type")

        if not isinstance(path, str) or not path:
            errors.append(f"операция #{index}: нет path")

        if op_type == "replace":
            if "old" not in operation:
                errors.append(f"операция #{index}: replace без old")
            if "new" not in operation:
                errors.append(f"операция #{index}: replace без new")

        if op_type in ["create", "write"]:
            if "content" not in operation:
                errors.append(f"операция #{index}: {op_type} без content")

    return errors


def _load_patch_from_text(text):
    last_error = None

    for payload in [text, repair_json(text)]:
        try:
            data = json.loads(payload)
            errors = _schema_errors(data)

            if not errors:
                return data, []

            last_error = "; ".join(errors)

        except Exception as e:
            last_error = str(e)

    return None, [last_error or "не удалось распарсить JSON"]


def _download_files():
    _ensure_dirs()

    if not DOWNLOADS_DIR.exists():
        return []

    return sorted(
        [path for path in DOWNLOADS_DIR.rglob("*") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _download_file_is_fresh(path):
    try:
        send_time = float(get_value("last_gpt_browser_send_time_epoch", "0") or "0")
    except Exception:
        send_time = 0.0

    if send_time <= 0:
        return True

    try:
        return path.stat().st_mtime >= send_time - 5
    except Exception:
        return True


def _import_downloaded_response_data():
    _ensure_dirs()

    files = _download_files()

    if not files:
        raise FileNotFoundError(f"В папке загрузок нет файлов: {DOWNLOADS_DIR}")

    invalid_reports = []

    for path in files[:20]:
        if not _download_file_is_fresh(path):
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            invalid_reports.append(f"{path.name}: не удалось прочитать: {e}")
            continue

        data, errors = _load_patch_from_text(text)

        if data is not None:
            return data, path

        invalid_reports.append(f"{path.name}: {'; '.join(errors)}")

    BAD_RESPONSE_PATH.write_text(
        "\\n".join(invalid_reports) if invalid_reports else "Нет свежего валидного response.json",
        encoding="utf-8",
    )

    raise ValueError(
        "Не найден свежий валидный downloaded response.json. "
        f"bad_response: {BAD_RESPONSE_PATH}"
    )


def import_downloaded_response():
    try:
        _clear_error()
        data, source_path = _import_downloaded_response_data()

        set_value("last_gpt_browser_action", "import_downloaded_response")
        set_value("last_gpt_browser_downloaded_response", str(source_path))

        result = _save_patch_data(data)

        return (
            "GPT Browser Bridge: downloaded response импортирован.\\n"
            f"Источник: {source_path}\\n"
            f"Скопировано в: {RESPONSE_PATH}\\n\\n"
            + result
        )

    except Exception as e:
        _remember_error(e)
        return (
            "GPT Browser Bridge: не удалось импортировать downloaded response.\\n"
            f"Ошибка: {e}\\n"
            f"Папка загрузок: {DOWNLOADS_DIR}\\n"
            f"bad_response: {BAD_RESPONSE_PATH if BAD_RESPONSE_PATH.exists() else 'нет'}"
        )


def downloads_status():
    _ensure_dirs()
    files = _download_files()

    lines = [
        "GPT Browser downloads:",
        f"- downloads_dir: {DOWNLOADS_DIR}",
        f"- exists: {DOWNLOADS_DIR.exists()}",
        f"- files: {len(files)}",
    ]

    for path in files[:10]:
        try:
            rel = path.relative_to(DOWNLOADS_DIR)
        except Exception:
            rel = path.name

        lines.append(
            f"- {rel} | {path.stat().st_size} bytes | {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(path.stat().st_mtime))}"
        )

    return "\\n".join(lines)


def open_downloads():
    _ensure_dirs()

    try:
        if hasattr(os, "startfile"):
            os.startfile(str(DOWNLOADS_DIR))
            return f"GPT Browser Bridge: открыта папка загрузок: {DOWNLOADS_DIR}"

        return f"GPT Browser Bridge downloads folder: {DOWNLOADS_DIR}"

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: не удалось открыть папку загрузок.\\nОшибка: {e}"


def _save_patch_data(data):
    errors = _schema_errors(data)

    if errors:
        bad_path = _write_bad_response("; ".join(errors), data)
        raise ValueError(
            "JSON patch не прошел schema guard: "
            + "; ".join(errors)
            + f" | bad_response: {bad_path}"
        )

    RESPONSE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_value("last_gpt_browser_response", str(RESPONSE_PATH))
    set_value("last_relay_response", str(RESPONSE_PATH))

    return (
        "GPT Browser Bridge: response.json сохранен.\n"
        f"Файл: {RESPONSE_PATH}\n"
        f"Summary: {data.get('summary', 'нет')}\n"
        f"Операций: {len(data.get('operations', []))}\n\n"
        "Дальше: relay проверь ответ"
    )


def save_response():
    try:
        _clear_error()

        try:
            data, source_path = _import_downloaded_response_data()
            set_value("last_gpt_browser_action", "save_response_from_download")
            set_value("last_gpt_browser_downloaded_response", str(source_path))

            result = _save_patch_data(data)

            return (
                "GPT Browser Bridge: response.json сохранен из скачанного файла.\n"
                f"Источник: {source_path}\n\n"
                + result
            )
        except Exception as download_error:
            set_value("last_gpt_browser_download_import_error", str(download_error))

        page = _get_page()

        answer_text = _last_assistant_text(page)
        RAW_ANSWER_PATH.write_text(answer_text, encoding="utf-8")
        RAW_RESPONSE_PATH.write_text(answer_text, encoding="utf-8")

        data = _extract_json_patch(answer_text)

        set_value("last_gpt_browser_action", "save_response")
        set_value("last_gpt_browser_raw_answer", str(RAW_ANSWER_PATH))

        return _save_patch_data(data)

    except Exception as e:
        _remember_error(e)

        source = ""

        try:
            if RAW_ANSWER_PATH.exists():
                source = RAW_ANSWER_PATH.read_text(encoding="utf-8", errors="replace")
        except Exception:
            source = ""

        report = _save_error_report(source, e)

        return (
            "GPT Browser Bridge: не удалось сохранить response.json.\n"
            f"Ошибка: {e}\n"
            f"Сырой ответ сохранен: {RAW_ANSWER_PATH if RAW_ANSWER_PATH.exists() else 'нет'}\n"
            f"Error report: {report}\n\n"
            "Попробуй: gpt browser repair response"
        )


def repair_response():
    try:
        _clear_error()
        _ensure_dirs()

        sources = [
            RAW_ANSWER_PATH,
            RAW_RESPONSE_PATH,
        ]

        last_error = None

        for path in sources:
            if not path.exists() or not path.is_file():
                continue

            text = path.read_text(encoding="utf-8", errors="replace")

            try:
                data = _extract_json_patch(text)
                set_value("last_gpt_browser_action", "repair_response")
                set_value("last_gpt_browser_raw_answer", str(path))
                return (
                    "GPT Browser Bridge: response.json восстановлен из сырого ответа.\n"
                    f"Источник: {path}\n"
                    + _save_patch_data(data)
                )
            except Exception as e:
                last_error = e
                continue

        if last_error:
            raise last_error

        raise FileNotFoundError(
            f"Не найден сырой ответ: {RAW_ANSWER_PATH} или {RAW_RESPONSE_PATH}"
        )

    except Exception as e:
        _remember_error(e)
        report = _save_error_report("", e)

        return (
            "GPT Browser Bridge: repair response не смог восстановить JSON.\n"
            f"Ошибка: {e}\n"
            f"Error report: {report}"
        )


def status():
    page_url = "нет"
    page_state = "нет"
    saved_chat_url = _saved_chat_url()

    try:
        if _page is not None and not _page.is_closed():
            page_url = _page.url
            page_state = "открыта"
        else:
            page_state = "закрыта"
    except Exception as e:
        page_state = f"ошибка: {e}"

    return (
        "GPT Browser Bridge status:\n"
        f"- profile: {PROFILE_DIR}\n"
        f"- engine: {get_value('last_gpt_browser_engine', 'нет')}\n"
        f"- downloads_dir: {DOWNLOADS_DIR}\n"
        f"- downloads_exists: {DOWNLOADS_DIR.exists()}\n"
        f"- saved_chat_url: {saved_chat_url if saved_chat_url else 'нет'}\n"
        f"- request: {_latest_request_path()}\n"
        f"- response: {RESPONSE_PATH}\n"
        f"- response_exists: {RESPONSE_PATH.exists()}\n"
        f"- raw_answer: {RAW_ANSWER_PATH}\n"
        f"- error_report: {ERROR_REPORT_PATH}\n"
        f"- page: {page_state}\n"
        f"- url: {page_url}\n"
        f"- default_wait_timeout: 600\n"
        f"- response_mode: {get_value('last_gpt_browser_response_mode', 'file_response_json_first')}\n"
        f"- auto_download_response_json: fixed_downloads_import\n"
        f"- last_download_import_error: {get_value('last_gpt_browser_download_import_error', 'нет')}\n"
        f"- last_action: {get_value('last_gpt_browser_action', 'нет')}\n"
        f"- last_error: {get_value('last_gpt_browser_error', 'нет')}"
    )


def download_latest_response_artifact(timeout_sec: int = 900):
    from modules.true_auto_relay import download_latest_response_artifact as _download

    return _download(timeout_sec=timeout_sec)


def true_auto_relay_cycle(goal: str = "", timeout_sec: int = 900):
    from modules.true_auto_relay import true_auto_relay_cycle as _cycle

    return _cycle(goal=goal, timeout_sec=timeout_sec)


def full_cycle(timeout_sec: int = 600):
    from agents import chatgpt_relay_agent

    parts = [
        "--- OPEN ---",
        open_chatgpt(),
        "",
        "--- PASTE REQUEST ---",
        paste_request(),
        "",
        "--- SEND ---",
        send_prompt(),
        "",
        "--- WAIT ---",
        wait_response(timeout_sec=timeout_sec),
        "",
        "--- SAVE RESPONSE ---",
        save_response(),
        "",
        "--- RELAY VALIDATE ---",
        chatgpt_relay_agent.handle("validate_response", {}),
    ]

    return "\n".join(str(part) for part in parts)


def full_apply(timeout_sec: int = 600):
    from agents import chatgpt_relay_agent
    from agents import automation_agent

    cycle_result = full_cycle(timeout_sec=timeout_sec)
    validate_result = chatgpt_relay_agent.handle("validate_response", {})

    parts = [
        "--- FULL CYCLE ---",
        cycle_result,
        "",
        "--- VALIDATE AGAIN ---",
        validate_result,
    ]

    if "✅" not in str(validate_result) and "проверка пройдена" not in str(validate_result).lower():
        parts.extend([
            "",
            "FULL APPLY остановлен: relay validate не прошел.",
        ])
        return "\n".join(parts)

    close_result = close_bridge()
    apply_result = chatgpt_relay_agent.handle("apply_response", {})
    after_result = automation_agent.handle("after_patch", {})

    parts.extend([
        "",
        "--- GPT BROWSER CLOSE ---",
        close_result,
        "",
        "--- RELAY APPLY ---",
        apply_result,
        "",
        "--- AFTER PATCH ---",
        after_result,
    ])

    return "\n".join(str(part) for part in parts)
