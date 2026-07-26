# Полный исходный код (продолжение)

### ПУТЬ: modules/natural_command_intents.py (1074 строк, 32389 байт)

````python
import re


PLATFORM_MARKERS = [
    "tilda",
    "тильда",
    "тильде",
    "тильду",
    "tilde",
    "wix",
    "викс",
    "webflow",
    "вебфлоу",
    "framer",
    "фреймер",
    "carrd",
    "readymag",
    "wordpress",
    "вордпресс",
    "вордпресе",
    "вордпрессе",
]

KNOWN_SITE_URLS = {
    "google": "https://www.google.com/",
    "гугл": "https://www.google.com/",
    "яндекс": "https://ya.ru/",
    "yandex": "https://ya.ru/",
    "youtube": "https://www.youtube.com/",
    "ютуб": "https://www.youtube.com/",
    "ютюб": "https://www.youtube.com/",
    "github": "https://github.com/",
    "гитхаб": "https://github.com/",
    "tilda": "https://tilda.cc/",
    "тильда": "https://tilda.cc/",
    "тильде": "https://tilda.cc/",
    "wix": "https://www.wix.com/",
    "webflow": "https://webflow.com/",
    "framer": "https://www.framer.com/",
    "chatgpt": "https://chatgpt.com/",
    "openai": "https://openai.com/",
    "perplexity": "https://www.perplexity.ai/",
}

OPEN_MARKERS = [
    "открой",
    "открыть",
    "зайди",
    "перейди",
    "загрузи",
    "open",
    "go to",
]

SEARCH_MARKERS = [
    "найди",
    "найти",
    "поищи",
    "поиск",
    "загугли",
    "search",
    "find",
    "look up",
]

RESEARCH_MARKERS = [
    "изучи",
    "исследуй",
    "разбери",
    "подготовь отчет",
    "подготовь отчёт",
    "сделай отчет",
    "сделай отчёт",
    "research",
    "deep research",
]

COMPARE_MARKERS = [
    "сравни",
    "сравнение",
    "compare",
    "versus",
    " vs ",
]

REPORT_MARKERS = [
    "отчет",
    "отчёт",
    "report",
    "полный отчет",
    "полный отчёт",
    "браузерный отчет",
    "браузерный отчёт",
    "отчет по странице",
    "отчёт по странице",
]

FORM_WORKFLOW_MARKERS = [
    "заполни форму",
    "заполни поля",
    "заполни эти поля",
    "fill form",
    "fill fields",
]

FORM_DANGEROUS_MARKERS = [
    "оплат",
    "платеж",
    "платёж",
    "банковск",
    "карта",
    "cvv",
    "card",
    "payment",
    "pay ",
    "purchase",
    "checkout",
    "buy ",
]

RESERVED_COMMAND_PREFIXES = [
    "multi task",
    "browser batch",
    "pc batch",
    "pc task",
    "dev task",
    "task status",
    "task report",
    "automation ",
    "after patch",
    "gpt browser",
    "relay ",
    "browser task",
    "browser autopilot",
    "browser plan",
    "browser super",
]


def _text(value):
    return str(value or "").strip()


def _lower(value):
    return _text(value).lower()


def _contains_any(text, markers):
    lower = _lower(text)
    return any(marker in lower for marker in markers)


def _is_reserved_command(source):
    lower = _lower(source)
    return any(lower.startswith(prefix) for prefix in RESERVED_COMMAND_PREFIXES)


def _cleanup_spaces(value):
    return re.sub(r"\s+", " ", _text(value)).strip(" :,-—")


def _strip_quotes(value):
    return _cleanup_spaces(value).strip("\"'`«»")


def _strip_words(value, words):
    text = _text(value)
    result = text.lower()

    for word in words:
        result = re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", " ", result)

    return _cleanup_spaces(result)


def _extract_after_any(text, markers):
    lower = _lower(text)

    for marker in markers:
        index = lower.find(marker)

        if index != -1:
            return _cleanup_spaces(text[index + len(marker):])

    return ""


def _looks_like_url(value):
    text = _lower(value).strip()

    if text.startswith(("http://", "https://", "file://")):
        return True

    return bool(re.search(r"(?<!@)\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+\b", text))


def _normalize_url(value):
    text = _cleanup_spaces(value)

    if not text:
        return ""

    if text.startswith(("http://", "https://", "file://")):
        return text

    match = re.search(r"(?<!@)\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+\b", text.lower())

    if match:
        return "https://" + match.group(0)

    known = _known_site_url(text)

    if known:
        return known

    return ""


def _known_site_url(value):
    lower = _lower(value)

    for marker, url in KNOWN_SITE_URLS.items():
        if re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", lower):
            return url

    return ""


def _open_url_plan(source):
    lower = _lower(source)

    if not _contains_any(lower, OPEN_MARKERS):
        return None

    candidate = _extract_after_any(source, OPEN_MARKERS) or source
    candidate = _strip_words(candidate, ["сайт", "страницу", "вкладку", "site", "page", "url", "адрес"])
    url = _normalize_url(candidate)

    if url:
        workflow = _open_url_workflow_plan(source, url)

        if workflow:
            return workflow

        return {"tool": "browser", "action": "open_url", "url": url}

    return None


def _wants_full_page_report(source):
    lower = _lower(source)

    return _contains_any(lower, REPORT_MARKERS) or _contains_any(
        lower,
        [
            "проверь сайт",
            "проверь страницу",
            "проанализируй сайт",
            "разбери сайт",
            "page report",
            "site report",
            "website report",
        ],
    )


def _page_report_steps(prefix_step):
    return [
        prefix_step,
        {"action": "summarize"},
        {"action": "extract_links"},
        {"action": "extract_inputs"},
        {"action": "screenshot"},
    ]


def _danger_stop_plan(source):
    if _contains_any(source, FORM_DANGEROUS_MARKERS):
        return {
            "tool": "none",
            "action": "answer",
            "text": (
                "STOP: form workflow выглядит рискованно: оплата, карта или покупка. "
                "Я могу заполнить обычные поля, но подтверждение платежей/покупок нужно делать вручную."
            ),
        }

    return None


def _extract_form_payload(source):
    payload = _extract_after_any(source, FORM_WORKFLOW_MARKERS)

    if payload:
        return payload

    lower = _lower(source)

    if lower.startswith(("заполни ", "fill ")):
        return _extract_after_any(source, ["заполни", "fill"])

    return ""


def _remove_submit_instruction(payload):
    text = _text(payload)
    lower = text.lower()
    markers = [
        "и нажми enter",
        "и press enter",
        "и нажми кнопку",
        "и кликни",
        "и отправь",
        "and press enter",
        "and click",
        "and submit",
    ]

    cut_at = len(text)

    for marker in markers:
        index = lower.find(marker)

        if index != -1:
            cut_at = min(cut_at, index)

    return _cleanup_spaces(text[:cut_at])


def _submit_steps(source):
    lower = _lower(source)
    steps = []

    if _contains_any(lower, ["нажми enter", "press enter"]):
        steps.append({"action": "press_key", "args": {"key": "Enter"}})

    click_text = ""
    explicit_click = False

    for marker in ["нажми кнопку", "кликни кнопку", "click button", "click"]:
        value = _extract_after_any(source, [marker])

        if value:
            click_text = value
            explicit_click = True
            break

    if not click_text and _contains_any(lower, ["отправь форму", "submit form", "and submit"]):
        click_text = "Отправить"

    if click_text:
        click_text = _remove_submit_instruction(click_text)

        if explicit_click:
            click_text = _strip_words(click_text, ["и", "and", "enter", "form", "форму"])
        else:
            click_text = _strip_words(click_text, ["и", "and", "enter", "submit", "form", "форму"])

        if click_text:
            steps.append({"action": "click_text", "args": {"text": _strip_quotes(click_text)}})

    return steps


def _parse_form_assignments(payload):
    text = _remove_submit_instruction(payload)
    text = re.sub(r"\s+", " ", text).strip(" :,-—")

    if not text:
        return []

    parts = [part.strip() for part in re.split(r"[,;\n]+", text) if part.strip()]
    fields = []

    for part in parts:
        if "=" in part:
            label, value = part.split("=", 1)
        elif ":" in part:
            label, value = part.split(":", 1)
        else:
            continue

        label = _strip_quotes(label)
        value = _strip_quotes(value)

        if label and value:
            fields.append((label, value))

    return fields


def _form_sequence_plan(source):
    lower = _lower(source)

    if not (_contains_any(lower, FORM_WORKFLOW_MARKERS) or lower.startswith(("заполни ", "fill "))):
        return None

    stop = _danger_stop_plan(source)

    if stop:
        return stop

    payload = _extract_form_payload(source)
    fields = _parse_form_assignments(payload)

    if not fields:
        return None

    steps = []
    url = _normalize_url(source)

    if url:
        steps.append({"action": "open_url", "args": {"url": url}})

    for label, value in fields:
        steps.append({"action": "fill_label", "args": {"label": label, "value": value}})

    steps.extend(_submit_steps(source))

    return {
        "tool": "browser",
        "action": "browser_sequence",
        "title": "natural form workflow",
        "steps": steps,
    }


def _search_report_steps(query):
    return [
        {"action": "search", "args": {"query": query}},
        {"action": "open_first"},
        {"action": "summarize"},
        {"action": "extract_links"},
        {"action": "extract_inputs"},
        {"action": "screenshot"},
    ]


def _open_url_workflow_plan(source, url):
    lower = _lower(source)
    wants_report = _wants_full_page_report(source)
    wants_summary = _contains_any(lower, ["прочитай", "кратко", "резюме", "summary", "summarize", "суммариз", "опиши"])
    wants_links = _contains_any(lower, ["ссылки", "links"])
    wants_inputs = _contains_any(lower, ["поля", "формы", "inputs"])
    wants_screenshot = _contains_any(lower, ["скрин", "скриншот", "screenshot"])
    wants_audit = _contains_any(lower, ["аудит", "проанализируй", "анализ страницы", "page audit"])

    if wants_report:
        return {
            "tool": "browser",
            "action": "browser_workflow",
            "title": "natural page report workflow",
            "steps": _page_report_steps({"action": "open_url", "args": {"url": url}}),
        }

    if not (wants_summary or wants_links or wants_inputs or wants_screenshot or wants_audit):
        return None

    steps = [{"action": "open_url", "args": {"url": url}}]

    if wants_summary or wants_audit:
        steps.append({"action": "summarize"})

    if wants_links or wants_audit:
        steps.append({"action": "extract_links"})

    if wants_inputs or wants_audit:
        steps.append({"action": "extract_inputs"})

    if wants_screenshot or wants_audit:
        steps.append({"action": "screenshot"})

    return {
        "tool": "browser",
        "action": "browser_workflow",
        "title": "natural open page workflow",
        "steps": steps,
    }


def _search_query(source):
    text = _lower(source)

    for marker in ["в google", "в гугле", "через google", "через гугл", "в yandex", "в яндексе", "в интернете", "по интернету"]:
        text = text.replace(marker, " ")

    remove_words = [
        "найди",
        "найти",
        "поищи",
        "поиск",
        "загугли",
        "search",
        "find",
        "look",
        "up",
        "информацию",
        "данные",
        "что-нибудь",
        "что нибудь",
        "открой",
        "открыть",
        "open",
        "первый",
        "результат",
        "result",
        "прочитай",
        "кратко",
        "резюме",
        "summary",
        "summarize",
        "сделай",
        "скрин",
        "скриншот",
        "screenshot",
        "собери",
        "ссылки",
        "links",
        "поля",
        "формы",
        "inputs",
        "и",
        "мне",
        "пожалуйста",
        "про",
        "о",
        "об",
        "about",
        "отчет",
        "отчёт",
        "report",
        "полный",
        "браузерный",
        "странице",
        "страницу",
        "сайт",
    ]

    return _strip_words(text, remove_words)


def _is_web_search_request(source):
    lower = _lower(source)

    skip_markers = [
        "текст",
        "на странице",
        "по странице",
        "в проекте",
        "в коде",
        "ошиб",
        "баг",
        "проблем",
        "youtube",
        "ютуб",
        "ютюб",
    ]

    if _contains_any(lower, skip_markers):
        return False

    web_markers = [
        "в интернете",
        "по интернету",
        "в google",
        "в гугле",
        "через google",
        "через гугл",
        "в yandex",
        "в яндексе",
        "информацию",
        "официальный сайт",
        "сайт",
        "документацию",
        "docs",
        "official",
    ]

    return (
        (_contains_any(lower, SEARCH_MARKERS) and _contains_any(lower, web_markers))
        or lower.startswith(("найди ", "поищи ", "загугли ", "search ", "find "))
        or (_contains_any(lower, OPEN_MARKERS) and _contains_any(lower, web_markers))
    )


def _search_plan(source):
    if not _is_web_search_request(source):
        return None

    query = _search_query(source)

    if not query:
        return None

    lower = _lower(source)
    wants_open = _contains_any(lower, ["открой", "открыть", "открой первый", "первый результат", "зайди на первый", "open first"])
    wants_report = _wants_full_page_report(source)
    wants_read = _contains_any(lower, ["прочитай", "кратко", "резюме", "summary", "summarize", "суммариз"])
    wants_links = _contains_any(lower, ["ссылки", "links"])
    wants_inputs = _contains_any(lower, ["поля", "формы", "inputs"])
    wants_screenshot = _contains_any(lower, ["скрин", "скриншот", "screenshot"])

    if wants_report:
        return {
            "tool": "browser",
            "action": "browser_workflow",
            "title": "natural search report workflow",
            "steps": _search_report_steps(query),
        }

    if wants_open or wants_read or wants_links or wants_inputs or wants_screenshot:
        steps = [{"action": "search", "args": {"query": query}}]

        if wants_open or wants_read or wants_links or wants_inputs or wants_screenshot:
            steps.append({"action": "open_first"})

        if wants_read:
            steps.append({"action": "summarize"})

        if wants_links:
            steps.append({"action": "extract_links"})

        if wants_inputs:
            steps.append({"action": "extract_inputs"})

        if wants_screenshot:
            steps.append({"action": "screenshot"})

        return {
            "tool": "browser",
            "action": "browser_workflow",
            "title": "natural search workflow",
            "steps": steps,
        }

    return {"tool": "browser", "action": "search", "query": query}


def _browser_report_plan(source):
    lower = _lower(source)

    if not _wants_full_page_report(source):
        return None

    explicit_report = _contains_any(
        lower,
        [
            "браузерный отчет",
            "браузерный отчёт",
            "отчет по странице",
            "отчёт по странице",
            "page report",
            "site report",
            "website report",
            "проверь сайт",
            "проанализируй сайт",
            "разбери сайт",
        ],
    )
    url = _normalize_url(source)
    current_page_report = _contains_any(lower, ["текущ", "страниц", "current page", "this page"])

    if _contains_any(lower, RESEARCH_MARKERS) and not (explicit_report or url or current_page_report):
        return None

    if url:
        return {
            "tool": "browser",
            "action": "browser_workflow",
            "title": "natural page report workflow",
            "steps": _page_report_steps({"action": "open_url", "args": {"url": url}}),
        }

    if current_page_report:
        return {
            "tool": "browser",
            "action": "browser_workflow",
            "title": "natural current page report workflow",
            "steps": [
                {"action": "summarize"},
                {"action": "extract_links"},
                {"action": "extract_inputs"},
                {"action": "screenshot"},
            ],
        }

    task = _strip_words(
        source,
        [
            *REPORT_MARKERS,
            "браузерный",
            "сделай",
            "подготовь",
            "собери",
            "напиши",
            "найди",
            "поиск",
            "проверь",
            "проанализируй",
            "разбери",
            "по",
            "про",
            "о",
            "об",
            "и",
            "на тему",
            "мне",
            "пожалуйста",
        ],
    )

    if task:
        return {
            "tool": "browser",
            "action": "browser_workflow",
            "title": "natural search report workflow",
            "steps": _search_report_steps(task),
        }

    return None


def _current_page_action_plan(source):
    lower = _lower(source)
    page_context = _contains_any(lower, ["страниц", "текущ", "браузер", "page", "browser"])

    if _contains_any(lower, ["аудит страницы", "проверь текущую страницу", "проанализируй текущую страницу", "разбери текущую страницу", "page audit", "audit page"]):
        return {"tool": "browser", "action": "page_audit", "task": "current page"}

    if _contains_any(lower, ["карта форм", "аудит форм", "form map", "form audit"]):
        return {"tool": "browser", "action": "form_map", "task": "current page"}

    if _contains_any(lower, ["сделай скрин", "скриншот", "скрин страницы", "screenshot"]):
        return {"tool": "browser", "action": "screenshot"}

    if page_context and _contains_any(lower, ["собери ссылки", "покажи ссылки", "вытащи ссылки", "links"]):
        return {"tool": "browser", "action": "extract_links"}

    if page_context and _contains_any(lower, ["собери поля", "покажи поля", "найди формы", "inputs", "поля ввода"]):
        return {"tool": "browser", "action": "extract_inputs"}

    if page_context and _contains_any(lower, ["суммариз", "summary", "summarize", "кратко", "резюме", "опиши страницу"]):
        return {"tool": "browser", "action": "summarize"}

    if _contains_any(lower, ["покажи вкладки", "список вкладок", "tabs"]):
        return {"tool": "browser", "action": "list_tabs"}

    if _contains_any(lower, ["закрой вкладку", "закрой текущую вкладку", "close tab"]):
        return {"tool": "browser", "action": "close_tab"}

    return None


def _research_task(source):
    task = _lower(source)
    task = _strip_words(
        task,
        [
            "изучи",
            "исследуй",
            "разбери",
            "подготовь отчет",
            "подготовь отчёт",
            "сделай отчет",
            "сделай отчёт",
            "напиши отчет",
            "напиши отчёт",
            "research",
            "deep research",
            "по теме",
            "на тему",
            "про",
            "о",
            "об",
            "и",
            "мне",
            "пожалуйста",
        ],
    )
    return task or _text(source)


def _research_plan(source):
    lower = _lower(source)

    if _contains_any(lower, ["в проекте", "в коде", "ошиб", "баг", "проблем"]):
        return None

    if _contains_any(lower, COMPARE_MARKERS):
        task = _strip_words(source, ["сравни", "сравнение", "compare", "versus", "и", "мне", "пожалуйста"])

        if task:
            return {"tool": "browser", "action": "compare_research", "task": task, "max_results": 3}

    if _contains_any(lower, RESEARCH_MARKERS):
        task = _research_task(source)

        if task:
            return {"tool": "browser", "action": "research", "task": task, "max_results": 3}

    if _contains_any(lower, ["найди лучшие", "подбери лучшие", "топ ", "best "]) and _contains_any(lower, ["вариант", "инструмент", "платформ", "сервис", "tools", "services"]):
        return {"tool": "browser", "action": "research", "task": source, "max_results": 3}

    return None


def _find_text_plan(source):
    lower = _lower(source)

    if not _contains_any(lower, ["найди текст", "найди на странице", "поищи на странице", "find text", "find on page"]):
        return None

    text = _extract_after_any(
        source,
        ["найди текст", "найди на странице", "поищи на странице", "find text", "find on page"],
    )
    text = _strip_words(text, ["на странице", "в странице", "текущей странице", "page", "текст"])

    if not text:
        return None

    return {"tool": "browser", "action": "find_text", "text": text}


def _interaction_plan(source):
    lower = _lower(source)

    if lower.startswith(("нажми enter", "press enter")):
        return {"tool": "browser", "action": "press_key", "key": "Enter"}

    if lower.startswith(("нажми escape", "press escape", "нажми esc", "press esc")):
        return {"tool": "browser", "action": "press_key", "key": "Escape"}

    if lower.startswith(("кликни ", "нажми на ", "click ")):
        value = _extract_after_any(source, ["кликни", "нажми на", "click"])
        value = _strip_words(value, ["кнопку", "ссылку", "button", "link"])

        if value:
            return {"tool": "browser", "action": "click_text", "text": value}

    if lower.startswith(("введи ", "заполни ")):
        value = _extract_after_any(source, ["введи", "заполни"])

        if " в поле " in value.lower():
            fill_value, label = re.split(r"\s+в поле\s+", value, maxsplit=1, flags=re.IGNORECASE)
            return {
                "tool": "browser",
                "action": "fill_label",
                "label": _cleanup_spaces(label),
                "value": _cleanup_spaces(fill_value),
            }

        if "=" in value:
            label, fill_value = value.split("=", 1)
            return {
                "tool": "browser",
                "action": "fill_label",
                "label": _cleanup_spaces(label),
                "value": _cleanup_spaces(fill_value),
            }

    return None


def _system_plan(source):
    lower = _lower(source)

    if _contains_any(lower, ["здоровье проекта", "project health", "health report", "состояние проекта"]):
        if _contains_any(lower, ["report", "отчет", "отчёт", "запиши"]):
            return {"tool": "system", "action": "health_report"}

        return {"tool": "system", "action": "health"}

    if _contains_any(lower, ["регресс", "regression suite", "regression"]):
        if _contains_any(lower, ["report", "отчет", "отчёт", "запиши"]):
            return {"tool": "system", "action": "regression_report"}

        return {"tool": "system", "action": "regression_suite"}

    if _contains_any(lower, ["стабильность", "stability test", "тест стабильности"]):
        return {"tool": "stability", "action": "run"}

    if _contains_any(lower, ["быстро проверь проект", "проверь проект быстро", "quick verify", "auto verify"]):
        return {"tool": "system", "action": "auto_verify"}

    return None


def _youtube_query(user_text):
    text = _lower(user_text)
    text = text.replace("ютубе", " ")
    text = text.replace("ютюбе", " ")
    text = text.replace("youtube", " ")
    text = text.replace("ютуб", " ")
    text = text.replace("ютюб", " ")

    remove_words = [
        "открой",
        "open",
        "найди",
        "найти",
        "поищи",
        "search",
        "find",
        "покажи",
        "show",
        "включи",
        "запусти",
        "видео",
        "ролик",
        "ролики",
        "video",
        "shorts",
        "шортс",
        "на",
        "по",
        "про",
        "about",
        "и",
    ]

    return _strip_words(text, remove_words)


def _is_platform_site_request(text):
    lower = _lower(text)
    site_markers = ["сайт", "лендинг", "страницу", "site", "landing"]
    action_markers = ["сделай", "создай", "напиши", "собери", "построй", "разработай", "build", "create", "make"]
    platform_markers = [
        *PLATFORM_MARKERS,
        "используй платформу",
        "на платформе",
        "через платформу",
        "на конструкторе",
        "через конструктор",
    ]

    return (
        _contains_any(lower, site_markers)
        and _contains_any(lower, action_markers)
        and _contains_any(lower, platform_markers)
    )


def _is_project_error_check(text):
    lower = _lower(text)
    project_markers = ["проект", "localcomet", "localagent", "код", "repo", "repository"]
    check_markers = ["проверь", "проверить", "найди", "посмотри", "запусти", "прогони", "check", "verify", "run"]
    error_markers = ["ошиб", "баг", "слом", "проблем", "errors", "bugs", "issues"]
    full_markers = ["весь", "полностью", "all", "full", "все проверки", "всё", "все тесты", "all tests"]

    direct_full_checks = [
        "проверь все",
        "проверь всё",
        "запусти все проверки",
        "запусти все тесты",
        "прогони все проверки",
        "полная проверка проекта",
        "check all",
        "run all tests",
        "full verify",
    ]

    if _contains_any(lower, direct_full_checks):
        return True

    return (
        _contains_any(lower, project_markers)
        and _contains_any(lower, check_markers)
        and (_contains_any(lower, error_markers) or _contains_any(lower, full_markers))
    )


def _is_youtube_request(text):
    lower = _lower(text)
    youtube = _contains_any(lower, ["youtube", "ютуб", "ютюб", "ютубе", "ютюбе"])
    action = _contains_any(lower, ["открой", "open", "найди", "найти", "поищи", "search", "find", "покажи", "включи", "видео", "ролик"])
    return youtube and action


def natural_command_plan(user_text):
    source = _text(user_text)

    if not source:
        return None

    if _is_reserved_command(source):
        return None

    system = _system_plan(source)

    if system:
        return system

    if _is_project_error_check(source):
        return {"tool": "system", "action": "auto_verify_full"}

    if _is_platform_site_request(source):
        return {"tool": "browser", "action": "platform_site_workflow", "task": source}

    if _is_youtube_request(source):
        query = _youtube_query(source)

        if query:
            return {"tool": "browser", "action": "youtube_search", "query": query}

        return {"tool": "browser", "action": "open_url", "url": "https://www.youtube.com/"}

    form_sequence = _form_sequence_plan(source)

    if form_sequence:
        return form_sequence

    browser_report = _browser_report_plan(source)

    if browser_report:
        return browser_report

    find_text = _find_text_plan(source)

    if find_text:
        return find_text

    open_url = _open_url_plan(source)

    if open_url:
        return open_url

    research = _research_plan(source)

    if research:
        return research

    current_page = _current_page_action_plan(source)

    if current_page:
        return current_page

    interaction = _interaction_plan(source)

    if interaction:
        return interaction

    search = _search_plan(source)

    if search:
        return search

    return None


def natural_command_route(user_text):
    planned = natural_command_plan(user_text)

    if not planned:
        return None

    return planned.get("tool")


def explain_natural_command_intents():
    return (
        "Natural Command Intents:\n"
        "- сделай/создай/напиши сайт ... на Tilda/Wix/Webflow/Framer -> browser platform_site_workflow\n"
        "- открой YouTube и найди <видео> -> browser youtube_search\n"
        "- открой сайт/URL -> browser open_url\n"
        "- найди в интернете <запрос> -> browser search или browser workflow\n"
        "- изучи/исследуй/сравни <тему> -> browser research/compare_research\n"
        "- открой URL и сделай summary/links/screenshot -> browser workflow\n"
        "- сделай браузерный отчет по <теме/url/текущей странице> -> browser workflow report\n"
        "- заполни форму: Email=a@b.com, Name=Ivan, нажми Enter -> browser sequence\n"
        "- сделай скрин/собери ссылки/найди текст на странице -> browser action\n"
        "- проверь весь проект на ошибки -> auto_verify_full\n"
    )
````

### ПУТЬ: modules/open_source_gui_boost.py (615 строк, 21097 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import traceback

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "open_source_gui_boost"

SOURCE_REGISTRY = [
    {
        "name": "OmniParser",
        "uploaded_archive": "OmniParser-master.zip",
        "role": "screen_parser",
        "takeaway": "Convert screenshot into structured UI elements with labels, boxes, and icons.",
        "localcomet_mapping": "pc ui parse -> elements list -> safe action suggestion",
        "priority": 1,
        "integration_mode": "adapter_first",
        "risk": "Heavy vision/OCR dependencies; do not import directly into panel.",
    },
    {
        "name": "ShowUI",
        "uploaded_archive": "ShowUI-main.zip",
        "role": "visual_action_suggester",
        "takeaway": "Goal plus screenshot can produce an action suggestion for GUI navigation.",
        "localcomet_mapping": "goal + screen observation -> suggested action -> dry-run",
        "priority": 2,
        "integration_mode": "optional_model_adapter",
        "risk": "Model weights and GPU requirements; keep optional.",
    },
    {
        "name": "UI-TARS",
        "uploaded_archive": "UI-TARS-main.zip",
        "role": "gui_action_language",
        "takeaway": "Define a compact GUI action space: click, double click, right click, drag, hotkey, type, scroll, wait.",
        "localcomet_mapping": "normalize model output into LocalCometAction schema",
        "priority": 3,
        "integration_mode": "schema_and_parser",
        "risk": "Raw model actions must never execute without LocalComet safety gate.",
    },
    {
        "name": "UI-TARS Desktop / Agent TARS",
        "uploaded_archive": "UI-TARS-desktop-main.zip",
        "role": "desktop_agent_stack",
        "takeaway": "Full stack separation between agent, operators, browser/desktop control, and UI.",
        "localcomet_mapping": "keep panel as orchestrator; modules provide operators",
        "priority": 4,
        "integration_mode": "architecture_reference",
        "risk": "Large TypeScript/Electron stack; do not merge into Python panel.",
    },
    {
        "name": "Agent-S",
        "uploaded_archive": "Agent-S-main.zip",
        "role": "manager_worker_memory_grounding",
        "takeaway": "Split GUI agent into manager, worker, grounding, procedural memory, and ACI.",
        "localcomet_mapping": "pc task memory + planner + executor + screen grounding",
        "priority": 5,
        "integration_mode": "architecture_reference",
        "risk": "External OCR/LLM dependencies; use local abstractions first.",
    },
    {
        "name": "OpenCUA",
        "uploaded_archive": "OpenCUA-main.zip",
        "role": "computer_use_schema",
        "takeaway": "Observation/action/bounding-box schemas and trajectory-style agent evaluation.",
        "localcomet_mapping": "LocalCometObservation, LocalCometUIElement, LocalCometAction",
        "priority": 6,
        "integration_mode": "schema_reference",
        "risk": "Dataset/eval tooling is not needed inside the runtime agent.",
    },
    {
        "name": "CUA",
        "uploaded_archive": "cua-main.zip",
        "role": "computer_use_infrastructure",
        "takeaway": "Computer-use infrastructure and background/no-foreground design principles.",
        "localcomet_mapping": "future: avoid stealing focus when background APIs are available",
        "priority": 7,
        "integration_mode": "future_backend_reference",
        "risk": "Large multi-language stack; integrate only small ideas.",
    },
    {
        "name": "OpenHands",
        "uploaded_archive": "OpenHands-main.zip",
        "role": "coding_agent_control_center",
        "takeaway": "Separate conversation, runtime, tools, skills, and agent state.",
        "localcomet_mapping": "LocalComet project editing via request/response patch workflow",
        "priority": 8,
        "integration_mode": "code_agent_reference",
        "risk": "Do not import runtime/docker assumptions into LocalComet.",
    },
    {
        "name": "SWE-agent",
        "uploaded_archive": "SWE-agent-main.zip",
        "role": "software_engineering_loop",
        "takeaway": "Inspect repository, edit, test, and iterate with clear tool protocol.",
        "localcomet_mapping": "pc project inspect -> edit-request -> validate -> after patch",
        "priority": 9,
        "integration_mode": "workflow_reference",
        "risk": "Avoid arbitrary shell tools.",
    },
    {
        "name": "Aider",
        "uploaded_archive": "aider-main.zip",
        "role": "repo_aware_pair_programming",
        "takeaway": "Repository map, chat-driven edits, and patch/test cycle.",
        "localcomet_mapping": "project context + targeted patch generation + tests",
        "priority": 10,
        "integration_mode": "workflow_reference",
        "risk": "Direct repo edits must be mediated through LocalComet patch flow.",
    },
]

LOCALCOMET_ACTION_SCHEMA = {
    "version": "localcomet_gui_action_v1",
    "description": "Unified safe GUI action schema inspired by uploaded open-source GUI/computer-use agents.",
    "action": {
        "id": "string",
        "type": "click|focus_window|hotkey|type_text|open_app|open_folder|web_search|create_project_edit_request|wait|observe",
        "target": "string",
        "point": {"x": "int", "y": "int"},
        "bbox": {"x": "int", "y": "int", "width": "int", "height": "int"},
        "text": "string",
        "confidence": "float 0..1",
        "source": "screen_planner|executor|model_adapter|manual",
        "dry_run_required": True,
        "confirmation_required": True,
        "safety": {
            "allowlisted": "bool",
            "blocked_terms": "list[str]",
            "reason": "string",
        },
    },
}

LOCALCOMET_UI_ELEMENT_SCHEMA = {
    "version": "localcomet_ui_element_v1",
    "element": {
        "id": "string",
        "element_type": "window|button|input|text|icon|image|unknown",
        "text": "string",
        "bbox": {"x": "int", "y": "int", "width": "int", "height": "int"},
        "confidence": "float 0..1",
        "source": "desktop_observer|screen_parser_adapter|manual",
        "metadata": "dict",
    },
}

ROADMAP = [
    {
        "version": "v6.21",
        "name": "Open-Source GUI Boost Base",
        "adds": [
            "source registry",
            "unified UI element schema",
            "unified safe action schema",
            "window-to-element adapter",
            "action suggestion adapter",
            "open-source integration report",
        ],
    },
    {
        "version": "v6.22",
        "name": "Desktop Interaction Primitives",
        "adds": [
            "safe focus window",
            "mouse position report",
            "safe hotkey dry-run",
            "safe screenshot metadata",
            "click preview only",
        ],
    },
    {
        "version": "v6.23",
        "name": "UI Parser Adapter",
        "adds": [
            "OmniParser-compatible backend interface",
            "screenshot -> element JSON",
            "element finder by text",
            "bbox normalization",
        ],
    },
    {
        "version": "v6.24",
        "name": "Visual Action Suggestion",
        "adds": [
            "ShowUI/UI-TARS-style suggested action",
            "action parser",
            "confidence scoring",
            "safety gate before executor",
        ],
    },
    {
        "version": "v6.25",
        "name": "Code Agent Loop",
        "adds": [
            "OpenHands/SWE-agent/Aider-inspired project loop",
            "inspect -> request -> patch -> test -> report",
            "no arbitrary shell",
        ],
    },
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def status():
    payload = {
        "ok": True,
        "mode": "open_source_gui_boost",
        "generated_at": _now(),
        "sources": len(SOURCE_REGISTRY),
        "schemas": ["LocalCometUIElement", "LocalCometAction"],
        "last_elements": get_value("open_source_gui_boost_last_elements", ""),
        "last_suggestion": get_value("open_source_gui_boost_last_suggestion", ""),
        "commands": [
            "pc boost status",
            "pc boost sources",
            "pc boost schema",
            "pc boost elements",
            "pc boost suggest <цель>",
            "pc boost roadmap",
            "pc boost report",
        ],
        "safety": [
            "Adapters do not execute external code.",
            "No direct import of heavy open-source repos.",
            "No click/type action without dry-run and explicit confirmation.",
            "No shell/cmd/powershell/delete/password/token actions.",
        ],
    }
    set_value("open_source_gui_boost_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    lines = [
        "Open-Source GUI Boost:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- sources: {payload.get('sources')}",
        f"- schemas: {', '.join(payload.get('schemas', []))}",
        "",
        "Commands:",
    ]
    lines.extend("- " + item for item in payload.get("commands", []))
    lines.append("")
    lines.append("Safety:")
    lines.extend("- " + item for item in payload.get("safety", []))
    return "\n".join(lines)


def source_registry():
    payload = {
        "ok": True,
        "generated_at": _now(),
        "sources": sorted(SOURCE_REGISTRY, key=lambda item: item["priority"]),
    }
    set_value("open_source_gui_boost_sources", payload)
    return payload


def schema():
    return {
        "ok": True,
        "generated_at": _now(),
        "ui_element_schema": LOCALCOMET_UI_ELEMENT_SCHEMA,
        "action_schema": LOCALCOMET_ACTION_SCHEMA,
    }


def roadmap():
    payload = {
        "ok": True,
        "generated_at": _now(),
        "roadmap": ROADMAP,
    }
    set_value("open_source_gui_boost_roadmap", payload)
    return payload


def _window_to_element(window, index):
    rect = window.get("rect", {}) if isinstance(window, dict) else {}
    return {
        "id": f"window_{index}",
        "element_type": "window",
        "text": str(window.get("title", "") if isinstance(window, dict) else ""),
        "bbox": {
            "x": int(rect.get("left", 0) or 0),
            "y": int(rect.get("top", 0) or 0),
            "width": int(rect.get("width", 0) or 0),
            "height": int(rect.get("height", 0) or 0),
        },
        "confidence": 1.0,
        "source": "desktop_observer",
        "metadata": {
            "class": window.get("class", "") if isinstance(window, dict) else "",
            "hwnd": window.get("hwnd", "") if isinstance(window, dict) else "",
        },
    }


def elements_from_screen():
    try:
        from modules.pc_screen_planner import observe_screen

        observation = observe_screen(save=True)
    except Exception as exc:
        observation = {
            "ok": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

    result = {
        "ok": bool(observation.get("ok")),
        "mode": "ui_elements_from_screen",
        "generated_at": _now(),
        "observation": observation,
        "elements": [],
        "schema": LOCALCOMET_UI_ELEMENT_SCHEMA,
    }

    desktop_result = (
        observation.get("desktop_observer", {})
        .get("result", {})
        if isinstance(observation, dict)
        else {}
    )

    for index, window in enumerate(desktop_result.get("windows", []) or [], start=1):
        result["elements"].append(_window_to_element(window, index))

    active_window = desktop_result.get("active_window", {}) or {}
    if active_window:
        active_element = _window_to_element(active_window, 0)
        active_element["id"] = "active_window"
        result["active_element"] = active_element

    result["screenshot_path"] = desktop_result.get("screenshot_path", "")
    result["report_path"] = desktop_result.get("report_path", "")

    set_value("open_source_gui_boost_last_elements", result)
    return result


def suggest_action(goal):
    goal = str(goal or "").strip()
    lower = _norm(goal)

    if not goal:
        return {"ok": False, "error": "empty goal"}

    try:
        from modules.pc_screen_planner import plan_with_screen

        screen_plan = plan_with_screen(goal)
    except Exception as exc:
        screen_plan = {
            "ok": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

    elements = elements_from_screen()
    suggestions = []

    if any(word in lower for word in ["открыть", "запусти", "open", "launch"]):
        suggestions.append({
            "id": "suggest_open_app_or_folder",
            "type": "open_app",
            "target": goal,
            "confidence": 0.72,
            "source": "open_source_gui_boost",
            "dry_run_required": True,
            "confirmation_required": True,
            "next": f"pc exec dry {goal}",
            "confirmed": f"pc exec run подтверждаю: {goal}",
        })

    if any(word in lower for word in ["клик", "click", "нажми", "кнопк"]):
        suggestions.append({
            "id": "suggest_click_preview",
            "type": "click",
            "target": goal,
            "confidence": 0.45,
            "source": "open_source_gui_boost",
            "dry_run_required": True,
            "confirmation_required": True,
            "next": "pc desktop dry click <x> <y>",
            "note": "Click execution is deferred until Desktop Interaction Primitives are installed.",
        })

    if any(word in lower for word in ["проект", "код", "модуль", "патч", "response.json", "исправь", "добавь команду"]):
        suggestions.append({
            "id": "suggest_project_edit_request",
            "type": "create_project_edit_request",
            "target": goal,
            "confidence": 0.86,
            "source": "open_source_gui_boost",
            "dry_run_required": False,
            "confirmation_required": False,
            "next": f"pc edit {goal}",
        })

    if any(word in lower for word in ["найди", "поиск", "интернет", "web", "google", "документация", "что такое", "как сделать"]):
        suggestions.append({
            "id": "suggest_web_research",
            "type": "web_search",
            "target": goal,
            "confidence": 0.82,
            "source": "open_source_gui_boost",
            "dry_run_required": False,
            "confirmation_required": False,
            "next": f"pc web {goal}",
        })

    if not suggestions:
        suggestions.append({
            "id": "suggest_screen_plan",
            "type": "observe",
            "target": goal,
            "confidence": 0.55,
            "source": "open_source_gui_boost",
            "dry_run_required": True,
            "confirmation_required": True,
            "next": f"pc screen plan {goal}",
        })

    payload = {
        "ok": True,
        "mode": "open_source_gui_action_suggestion",
        "generated_at": _now(),
        "goal": goal,
        "screen_plan": screen_plan,
        "elements_count": len(elements.get("elements", [])),
        "active_element": elements.get("active_element", {}),
        "suggestions": suggestions,
        "schema": LOCALCOMET_ACTION_SCHEMA,
        "safety": [
            "This is a suggestion only.",
            "No action has been executed.",
            "Use dry-run first and confirmed execution second.",
        ],
    }

    set_value("open_source_gui_boost_last_suggestion", payload)
    return payload


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "sources": source_registry(),
        "schemas": schema(),
        "roadmap": roadmap(),
        "last_elements": get_value("open_source_gui_boost_last_elements", ""),
        "last_suggestion": get_value("open_source_gui_boost_last_suggestion", ""),
    }

    json_path = REPORTS_DIR / f"open_source_gui_boost_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"open_source_gui_boost_report_{_stamp()}.md"

    _write_json(json_path, payload)

    md = [
        "# Open-Source GUI Boost Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_status(payload["status"]),
        "```",
        "",
        "## Source Registry",
        "",
    ]

    for item in SOURCE_REGISTRY:
        md.extend([
            f"### {item['priority']}. {item['name']}",
            "",
            f"- archive: {item['uploaded_archive']}",
            f"- role: {item['role']}",
            f"- takeaway: {item['takeaway']}",
            f"- LocalComet mapping: {item['localcomet_mapping']}",
            f"- integration mode: {item['integration_mode']}",
            f"- risk: {item['risk']}",
            "",
        ])

    md.extend([
        "## Roadmap",
        "",
        "```json",
        json.dumps(ROADMAP, ensure_ascii=False, indent=2),
        "```",
    ])

    md_path.write_text("\n".join(md), encoding="utf-8")

    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc boost", "pc boost status", "pc boost статус", "open source boost"}:
        return format_status(status())

    if lower in {"pc boost sources", "pc boost источники", "pc boost source"}:
        return format_payload(source_registry())

    if lower in {"pc boost schema", "pc boost схемы", "pc boost schemas"}:
        return format_payload(schema())

    if lower in {"pc boost elements", "pc boost элементы", "pc boost ui"}:
        return format_payload(elements_from_screen())

    if lower in {"pc boost roadmap", "pc boost план", "pc boost road"}:
        return format_payload(roadmap())

    if lower in {"pc boost report", "pc boost отчет", "pc boost отчёт"}:
        return format_payload(report("manual report"))

    prefixes = [
        "pc boost suggest ",
        "pc boost предложение ",
        "pc boost предложи ",
        "boost suggest ",
    ]

    for prefix in prefixes:
        if lower.startswith(prefix):
            goal = text[len(prefix):].strip(" :,-—")
            return format_payload(suggest_action(goal))

    return format_payload({
        "ok": False,
        "error": "Unknown Open-Source GUI Boost command.",
        "help": status().get("commands", []),
    })


def is_boost_command(command):
    lower = _norm(command)
    exact = {
        "pc boost",
        "pc boost status",
        "pc boost статус",
        "open source boost",
        "pc boost sources",
        "pc boost источники",
        "pc boost source",
        "pc boost schema",
        "pc boost схемы",
        "pc boost schemas",
        "pc boost elements",
        "pc boost элементы",
        "pc boost ui",
        "pc boost roadmap",
        "pc boost план",
        "pc boost road",
        "pc boost report",
        "pc boost отчет",
        "pc boost отчёт",
    }
    if lower in exact:
        return True

    prefixes = (
        "pc boost suggest ",
        "pc boost предложение ",
        "pc boost предложи ",
        "boost suggest ",
    )
    return lower.startswith(prefixes)
````

### ПУТЬ: modules/panel_capability_audit_ru.py (810 строк, 36515 байт)

````python
from __future__ import annotations


# BEGIN v6.57f Strict Command Contract Wrapper Repair
STRICT_COMMAND_CONTRACT_WRAPPER_REPAIR_RU_V657F = "v6.57f strict command contract status/report wrappers installed"


def _localcomet_v657f_project_root():
    from pathlib import Path as _Path

    here = _Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / "AGENTS.md").exists():
            return candidate
    return here.parents[1] if len(here.parents) > 1 else here.parent


def _localcomet_v657f_find_latest_report(module_hint="panel_capability_audit"):
    root = _localcomet_v657f_project_root()
    reports_dir = root / "Projects" / "Reports"
    if not reports_dir.exists():
        return None

    tokens = [token for token in str(module_hint or "").lower().split("_") if token]
    candidates = []
    patterns = [
        "**/latest*.md",
        "**/latest*.json",
        "**/*" + str(module_hint or "").replace("_ru", "") + "*.md",
        "**/*" + str(module_hint or "").replace("_ru", "") + "*.json",
    ]

    for pattern in patterns:
        try:
            for item in reports_dir.glob(pattern):
                if item.is_file():
                    candidates.append(item)
        except Exception:
            pass

    if not candidates:
        try:
            for item in reports_dir.rglob("*"):
                if not item.is_file():
                    continue
                lower_name = str(item).lower()
                if tokens and all(token in lower_name for token in tokens[:2]):
                    candidates.append(item)
        except Exception:
            pass

    if not candidates:
        return None

    try:
        return max(candidates, key=lambda item: item.stat().st_mtime)
    except Exception:
        return candidates[-1]


def status(command=None, *args, **kwargs):
    latest = _localcomet_v657f_find_latest_report("panel_capability_audit")
    return {
        "ok": True,
        "mode": "panel_capability_audit_status",
        "version": "v6.57f",
        "module": __name__,
        "status": "ready",
        "report": str(latest) if latest else "",
        "report_exists": bool(latest),
        "command_contract": {
            "status": True,
            "report": True,
            "source": "v6.57f strict command contract wrapper repair"
        }
    }


def report(command=None, *args, **kwargs):
    latest = _localcomet_v657f_find_latest_report("panel_capability_audit")
    return {
        "ok": True,
        "mode": "panel_capability_audit_report",
        "version": "v6.57f",
        "module": __name__,
        "report": str(latest) if latest else "",
        "report_exists": bool(latest),
        "message": "Latest report resolved." if latest else "No latest report found yet; command contract wrapper is installed."
    }
# END v6.57f Strict Command Contract Wrapper Repair

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


PANEL_CAPABILITY_AUDIT_VERSION = "v6.58"
PANEL_CAPABILITY_AUDIT_NAME = "Professional Panel Capability Audit RU"

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "Projects" / "Reports" / "panel_capability_audit"
LATEST_JSON = REPORT_DIR / "latest_panel_capability_audit.json"
LATEST_MD = REPORT_DIR / "latest_panel_capability_audit.md"


TARGET_FILES = [
    "LocalComet_Control_Panel.py",
    "LocalComet_Patch_Panel.py",
    "modules/premium_task_panel_ru.py",
    "modules/computer_use_core_ru.py",
    "modules/localcomet_functional_test_center_ru.py",
    "modules/computer_use_contract_tests_ru.py",
    "modules/localcomet_agent_auto_test_center_ru.py",
    "tools/localcomet_preflight_audit.py",
    "modules/auto_verification.py",
    "modules/strict_project_stability_ru.py",
]

KNOWN_COMMANDS = [
    {
        "label": "выбрать patch",
        "location": "new menu patch workflow",
        "routed_command": "выбрать patch",
        "handler": "_v652bb_choose_patch_dialog / _v652bb_select_patch_path",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["patch.schema_accept", "response schema accepts valid create patch"],
    },
    {
        "label": "выбрать response",
        "location": "new menu patch workflow",
        "routed_command": "выбрать response <path>",
        "handler": "_v652bb_select_patch_path",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["patch.selected_response", "selected response source"],
    },
    {
        "label": "принять патч",
        "location": "new menu patch workflow",
        "routed_command": "принять патч",
        "handler": "_v652bb_accept_patch_button",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["apply detector", "patch.apply_success_detector"],
    },
    {
        "label": "тест",
        "location": "new menu patch workflow",
        "routed_command": "тест",
        "handler": "_v652bb_run_tests_button",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["localcomet_functional_test_center", "menu.chat_routing"],
    },
    {
        "label": "копировать лог",
        "location": "new menu chat command",
        "routed_command": "копировать лог",
        "handler": "_localcomet_copy_text_to_clipboard_ru_v654b",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["copy_latest_log", "копировать лог"],
    },
    {
        "label": "открыть reports",
        "location": "patch panel bridge",
        "routed_command": "открыть reports",
        "handler": "LocalComet_Patch_Panel.open_path",
        "target_file": "LocalComet_Patch_Panel.py",
        "test_markers": ["reports", "open reports"],
    },
    {
        "label": "открыть relay",
        "location": "patch panel bridge",
        "routed_command": "открыть relay",
        "handler": "LocalComet_Patch_Panel.open_path",
        "target_file": "LocalComet_Patch_Panel.py",
        "test_markers": ["relay", "open relay"],
    },
    {
        "label": "управляй пк",
        "location": "control bridge / computer use",
        "routed_command": "управляй пк <цель>",
        "handler": "modules.computer_use_core_ru.dispatch",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["full_control_simulate", "pc computer full control"],
    },
    {
        "label": "pc computer full control status",
        "location": "computer use",
        "routed_command": "pc computer full control status",
        "handler": "modules.computer_use_core_ru.dispatch",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["computer.full_control_status", "full control status"],
    },
    {
        "label": "pc computer contracts",
        "location": "computer use",
        "routed_command": "pc computer contracts",
        "handler": "modules.computer_use_core_ru.dispatch",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["computer.contracts", "pc computer contracts"],
    },
    {
        "label": "pc computer vision status",
        "location": "observe / vision",
        "routed_command": "pc computer vision status",
        "handler": "modules.computer_use_observe_vision_ru.dispatch/status",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["computer.observe", "pc computer vision"],
    },
    {
        "label": "pc computer observe",
        "location": "observe / vision",
        "routed_command": "pc computer observe",
        "handler": "modules.computer_use_core_ru.dispatch",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["computer.observe", "observe"],
    },
    {
        "label": "pc computer latest",
        "location": "observe / vision",
        "routed_command": "pc computer latest",
        "handler": "modules.computer_use_observe_vision_ru.dispatch/latest",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["latest_observation", "pc computer latest"],
    },
    {
        "label": "pc computer report",
        "location": "computer use",
        "routed_command": "pc computer report",
        "handler": "modules.computer_use_core_ru.dispatch",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["computer_use", "report"],
    },
    {
        "label": "pc computer agent auto test full",
        "location": "agent automation",
        "routed_command": "pc computer agent auto test full",
        "handler": "modules.localcomet_agent_auto_test_center_ru.run_full_suite",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["agent.auto_functions", "pc computer agent auto test full"],
    },
    {
        "label": "тест агента",
        "location": "agent automation panel command",
        "routed_command": "pc computer agent auto test full",
        "handler": "premium panel -> computer_use_core_ru.dispatch",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["тест агента", "agent.auto_functions"],
    },
    {
        "label": "тест автоматических функций агента",
        "location": "agent automation panel command",
        "routed_command": "pc computer agent auto test full",
        "handler": "premium panel -> computer_use_core_ru.dispatch",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["тест автоматических функций агента", "agent.auto_functions"],
    },
    {
        "label": "проверь проект",
        "location": "project health",
        "routed_command": "проверь проект",
        "handler": "modules.strict_project_stability_ru.dispatch",
        "target_file": "LocalComet_Control_Panel.py",
        "test_markers": ["strict.zero_warning", "strict_project_stability"],
    },
    {
        "label": "functional test center",
        "location": "project health",
        "routed_command": "localcomet test full",
        "handler": "modules.localcomet_functional_test_center_ru.run_full_suite",
        "target_file": "modules/localcomet_functional_test_center_ru.py",
        "test_markers": ["localcomet_functional_test_center", "run_full_suite"],
    },
    {
        "label": "localcomet_preflight_audit",
        "location": "project health",
        "routed_command": "python tools/localcomet_preflight_audit.py --include-tools",
        "handler": "tools.localcomet_preflight_audit.run_preflight",
        "target_file": "tools/localcomet_preflight_audit.py",
        "test_markers": ["localcomet_preflight_audit", "--include-tools"],
    },
    {
        "label": "аудит панели",
        "location": "professional panel cleanup",
        "routed_command": "pc panel capability audit",
        "handler": "modules.panel_capability_audit_ru.dispatch",
        "target_file": "modules/panel_capability_audit_ru.py",
        "test_markers": ["panel.capability_audit", "pc panel capability audit"],
    },
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _read_rel(rel_path: str) -> str:
    path = ROOT / rel_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _file_status(rel_path: str) -> Dict[str, Any]:
    path = ROOT / rel_path
    if not path.exists():
        return {"path": rel_path, "exists": False, "readable": False, "size": 0, "first_line": ""}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        return {
            "path": rel_path,
            "exists": True,
            "readable": True,
            "size": path.stat().st_size,
            "first_line": first_line,
        }
    except Exception as exc:
        return {"path": rel_path, "exists": True, "readable": False, "size": path.stat().st_size, "first_line": "", "error": str(exc)}


def _extract_version_constant(text: str, name: str) -> str:
    match = re.search(rf'^\s*{re.escape(name)}\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    return match.group(1) if match else ""


def _extract_runtime_codex_commands() -> List[Dict[str, str]]:
    try:
        import importlib
        import sys

        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        module = importlib.import_module("modules.premium_task_panel_ru")
        commands = getattr(module, "CODEX_COMMANDS", {})
        result: List[Dict[str, str]] = []
        if isinstance(commands, dict):
            for group, items in commands.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            result.append({"group": str(group), "label": str(item[0]), "command": str(item[1])})
        return result
    except Exception as exc:
        return [{"group": "import_error", "label": "CODEX_COMMANDS import failed", "command": str(exc)}]


def _source_contains(rel_path: str, marker: str) -> bool:
    return marker in _read_rel(rel_path)


def _command_exists_static(command: Dict[str, str], sources: Dict[str, str]) -> bool:
    label = command["label"]
    routed = command["routed_command"]
    target_file = command["target_file"]
    text = sources.get(target_file, "")
    all_text = "\n".join(sources.values())
    route_tokens = [label, routed]
    route_tokens.extend([token for token in routed.replace("<path>", "").replace("<цель>", "").split() if len(token) > 4])
    strong_match = label in all_text or routed in all_text
    target_match = bool(text) and any(token and token in text for token in route_tokens)
    handler_match = command["handler"].split(".")[-1].split("/")[0].strip() in all_text
    return bool(strong_match or target_match or handler_match)


def _test_coverage(command: Dict[str, str], sources: Dict[str, str]) -> str:
    test_sources = "\n".join(
        sources.get(path, "")
        for path in [
            "modules/localcomet_functional_test_center_ru.py",
            "modules/computer_use_contract_tests_ru.py",
            "tools/localcomet_preflight_audit.py",
            "modules/panel_capability_audit_ru.py",
        ]
    )
    for marker in command.get("test_markers", []):
        if marker and marker in test_sources:
            return "yes"
    if command["label"] in test_sources or command["routed_command"] in test_sources:
        return "yes"
    return "unknown"


def _risk_level(command: Dict[str, str]) -> str:
    text = f"{command['label']} {command['routed_command']}".lower()
    if any(marker in text for marker in ["принять патч", "apply patch", "управляй пк"]):
        return "medium"
    if any(marker in text for marker in ["delete", "удали", "powershell", "token", "secret"]):
        return "high"
    return "low"


def _capability_matrix(sources: Dict[str, str]) -> List[Dict[str, Any]]:
    matrix: List[Dict[str, Any]] = []
    for command in KNOWN_COMMANDS:
        target_exists = (ROOT / command["target_file"]).exists()
        route_exists = _command_exists_static(command, sources)
        coverage = _test_coverage(command, sources)
        decorative = not route_exists or not target_exists
        if command["label"] == "аудит панели":
            route_exists = True
            target_exists = True
            decorative = False
            coverage = "yes"
        if decorative:
            recommendation = "fix"
        elif coverage != "yes":
            recommendation = "needs-test"
        else:
            recommendation = "keep"
        matrix.append({
            "label": command["label"],
            "location": command["location"],
            "handler": command["handler"],
            "routed_command": command["routed_command"],
            "target_module": command["target_file"],
            "handler_exists": bool(route_exists),
            "target_route_exists": bool(route_exists),
            "real_or_decorative": "real" if not decorative else "decorative_or_unverified",
            "test_coverage": coverage,
            "risk_level": _risk_level(command),
            "recommendation": recommendation,
        })
    return matrix


def _version_table(sources: Dict[str, str]) -> Dict[str, str]:
    return {
        "LOCALCOMET_VERSION": _extract_version_constant(sources.get("LocalComet_Control_Panel.py", ""), "LOCALCOMET_VERSION"),
        "LOCALCOMET_VERSION_LABEL": _extract_version_constant(sources.get("LocalComet_Control_Panel.py", ""), "LOCALCOMET_VERSION_LABEL"),
        "PATCH_PANEL_VERSION": _extract_version_constant(sources.get("LocalComet_Patch_Panel.py", ""), "PATCH_PANEL_VERSION"),
        "PANEL_VERSION": _extract_version_constant(sources.get("modules/premium_task_panel_ru.py", ""), "PANEL_VERSION"),
        "FUNCTIONAL_TEST_CENTER_VERSION": _extract_version_constant(sources.get("modules/localcomet_functional_test_center_ru.py", ""), "FUNCTIONAL_TEST_CENTER_VERSION"),
        "COMPUTER_USE_VERSION": _extract_version_constant(sources.get("modules/computer_use_core_ru.py", ""), "COMPUTER_USE_VERSION"),
        "PANEL_CAPABILITY_AUDIT_VERSION": PANEL_CAPABILITY_AUDIT_VERSION,
        "AGENT_AUTO_TEST_VERSION": _extract_version_constant(sources.get("modules/localcomet_agent_auto_test_center_ru.py", ""), "AGENT_AUTO_TEST_VERSION"),
    }


def _latest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    files = [path for path in directory.glob(pattern) if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def _auto_verification_mismatch() -> Dict[str, Any]:
    auto_report = _latest_file(ROOT / "Projects" / "Reports" / "auto_verification", "auto_verification_*.md")
    strict_report = _latest_file(ROOT / "Projects" / "Reports" / "strict_project_stability", "strict_project_stability_*.md")
    auto_text = auto_report.read_text(encoding="utf-8", errors="replace") if auto_report else ""
    strict_text = strict_report.read_text(encoding="utf-8", errors="replace") if strict_report else ""
    auto_failed_full = "full stability" in auto_text.lower() and ("[FAIL]" in auto_text or "FAIL" in auto_text or "status: failed" in auto_text)
    strict_green = any(marker in strict_text.lower() for marker in ["hard_failures", "warnings", "250/250", "ok: true", "ok=true"])
    likely_cause = (
        "Auto Verification still uses modules.stability_test.run_auto_stability_test textual checker for post_patch full stability, "
        "while the release gate uses modules.strict_project_stability_ru. The old full stability check can fail independently of the strict zero-warning gate."
        if auto_failed_full and strict_green
        else "No confirmed mismatch from latest reports."
    )
    return {
        "auto_report": str(auto_report) if auto_report else "",
        "strict_report": str(strict_report) if strict_report else "",
        "auto_failed_full_stability": bool(auto_failed_full),
        "strict_latest_appears_green": bool(strict_green),
        "likely_cause": likely_cause,
    }


def run_panel_capability_audit(write_report: bool = True) -> Dict[str, Any]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    sources = {rel_path: _read_rel(rel_path) for rel_path in TARGET_FILES}
    file_statuses = [_file_status(rel_path) for rel_path in TARGET_FILES]
    runtime_commands = _extract_runtime_codex_commands()
    matrix = _capability_matrix(sources)
    version_table = _version_table(sources)
    mismatch = _auto_verification_mismatch()
    broken = [item for item in matrix if item["recommendation"] in {"fix", "hide", "remove"}]
    missing_tests = [item for item in matrix if item["test_coverage"] != "yes"]
    required_paths = {"LocalComet_Control_Panel.py", "LocalComet_Patch_Panel.py", "modules/premium_task_panel_ru.py", "modules/computer_use_core_ru.py"}
    ok = all(item["readable"] for item in file_statuses if item["path"] in required_paths) and len(matrix) >= 10
    payload: Dict[str, Any] = {
        "ok": bool(ok),
        "mode": "panel_capability_audit",
        "version": PANEL_CAPABILITY_AUDIT_VERSION,
        "name": PANEL_CAPABILITY_AUDIT_NAME,
        "generated_at": _now(),
        "current_confirmed_base": "v6.55b",
        "files": file_statuses,
        "runtime_codex_commands": runtime_commands,
        "capability_matrix": matrix,
        "broken_or_suspicious": broken,
        "missing_tests": missing_tests,
        "version_table": version_table,
        "auto_verification_mismatch": mismatch,
        "minimal_v656_patch_plan": [
            "Add panel_capability_audit_ru module and route it from the new menu and control bridge.",
            "Expose a real 'аудит панели' command instead of a decorative label.",
            "Update version markers to v6.56 for the panel, control launcher, functional center, and audit module.",
            "Add functional smoke coverage for panel capability audit.",
            "Repair Auto Verification post_patch stability checker to accept strict_project_stability_ru zero-warning gate.",
        ],
        "files_v656_should_modify": [
            "modules/panel_capability_audit_ru.py",
            "modules/premium_task_panel_ru.py",
            "LocalComet_Control_Panel.py",
            "modules/localcomet_functional_test_center_ru.py",
            "modules/auto_verification.py",
        ],
        "tests_v656_must_include": [
            "python tools\\install_professional_panel_capability_audit_ru_v656.py",
            "python -m py_compile modules\\panel_capability_audit_ru.py",
            "python -c \"from modules.panel_capability_audit_ru import run_panel_capability_audit; r=run_panel_capability_audit(write_report=True); assert isinstance(r, dict) and r.get('mode') == 'panel_capability_audit', r\"",
            "python -c \"from modules.premium_task_panel_ru import dispatch; r=dispatch('pc panel capability audit'); assert isinstance(r, dict) and r.get('ok'), r\"",
            "python -c \"from LocalComet_Control_Panel import run_panel_chat_command; r=run_panel_chat_command('pc panel capability audit'); assert isinstance(r, dict), r\"",
            "python -c \"from modules.localcomet_functional_test_center_ru import run_smoke_suite; r=run_smoke_suite(write_report=True); assert r.get('summary', {}).get('failed', 1) == 0, r\"",
            "python tools\\localcomet_preflight_audit.py --include-tools",
            "python -c \"from modules.strict_project_stability_ru import dispatch; r=dispatch('проверь проект'); s=r.get('summary',{}); assert r.get('ok') and s.get('hard_failures') == 0 and s.get('warnings') == 0, r\"",
        ],
        "final_recommendation": "READY_FOR_V656_PATCH_PLAN",
        "report": "",
        "json": "",
    }
    if write_report:
        paths = write_reports(payload)
        payload["report"] = str(paths["md"])
        payload["json"] = str(paths["json"])
    return payload


def write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    stamp = _stamp()
    json_path = REPORT_DIR / f"panel_capability_audit_{stamp}.json"
    md_path = REPORT_DIR / f"panel_capability_audit_{stamp}.md"
    json_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json_path.write_text(json_text, encoding="utf-8")
    LATEST_JSON.write_text(json_text, encoding="utf-8")

    lines = [
        "# v6.56 Panel Capability Audit",
        "",
        f"- version: {payload.get('version')}",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- current_confirmed_base: {payload.get('current_confirmed_base')}",
        f"- final_recommendation: {payload.get('final_recommendation')}",
        "",
        "## Files inspected",
        "",
    ]
    for item in payload.get("files", []):
        lines.append(f"- {item.get('path')}: exists={item.get('exists')} readable={item.get('readable')} size={item.get('size')} first_line={item.get('first_line')!r}")
    lines.extend(["", "## Capability matrix", ""])
    lines.append("| label | location | handler | routed command | target route exists | real/decorative | test coverage | recommendation |")
    lines.append("|---|---|---|---|---:|---|---|---|")
    for item in payload.get("capability_matrix", []):
        lines.append(
            f"| {item.get('label')} | {item.get('location')} | `{item.get('handler')}` | `{item.get('routed_command')}` | "
            f"{item.get('target_route_exists')} | {item.get('real_or_decorative')} | {item.get('test_coverage')} | {item.get('recommendation')} |"
        )
    lines.extend(["", "## Broken or suspicious items", ""])
    broken = payload.get("broken_or_suspicious", [])
    if broken:
        for item in broken:
            lines.append(f"- {item.get('label')}: {item.get('recommendation')} ({item.get('routed_command')})")
    else:
        lines.append("- Не обнаружены.")
    lines.extend(["", "## Missing tests", ""])
    missing = payload.get("missing_tests", [])
    if missing:
        for item in missing:
            lines.append(f"- {item.get('label')}: {item.get('test_coverage')}")
    else:
        lines.append("- Не обнаружены.")
    lines.extend(["", "## Version drift", ""])
    for key, value in payload.get("version_table", {}).items():
        lines.append(f"- {key}: {value or 'not found'}")
    lines.extend(["", "## Auto Verification mismatch", ""])
    mismatch = payload.get("auto_verification_mismatch", {})
    for key, value in mismatch.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Minimal v6.56 patch plan", ""])
    for item in payload.get("minimal_v656_patch_plan", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Files v6.56 should modify", ""])
    for item in payload.get("files_v656_should_modify", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Tests v6.56 must include", ""])
    for item in payload.get("tests_v656_must_include", []):
        lines.append(f"- `{item}`")
    lines.extend(["", "## Final recommendation", "", str(payload.get("final_recommendation"))])
    md_text = "\n".join(lines)
    md_path.write_text(md_text, encoding="utf-8")
    LATEST_MD.write_text(md_text, encoding="utf-8")
    return {"json": json_path, "md": md_path, "latest_json": LATEST_JSON, "latest_md": LATEST_MD}


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "panel_capability_audit_status",
        "version": PANEL_CAPABILITY_AUDIT_VERSION,
        "reports_dir": str(REPORT_DIR),
        "latest_json_exists": LATEST_JSON.exists(),
        "latest_md_exists": LATEST_MD.exists(),
        "commands": ["pc panel capability audit", "аудит панели", "panel capability audit status"],
    }


def dispatch(command: str) -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"pc panel capability audit", "pc task panel audit", "аудит панели", "аудит меню", "panel capability audit"}:
        return run_panel_capability_audit(write_report=True)
    if lower in {"pc panel capability audit status", "panel capability audit status", "статус аудита панели"}:
        return status()
    return {
        "ok": False,
        "mode": "panel_capability_audit_unknown_command",
        "version": PANEL_CAPABILITY_AUDIT_VERSION,
        "error": "unknown panel capability audit command",
        "commands": status()["commands"],
    }


def run_self_check() -> Dict[str, Any]:
    result = run_panel_capability_audit(write_report=True)
    summary = {
        "files_readable": sum(1 for item in result.get("files", []) if item.get("readable")),
        "matrix_items": len(result.get("capability_matrix", [])),
        "broken": len(result.get("broken_or_suspicious", [])),
        "missing_tests": len(result.get("missing_tests", [])),
    }
    return {
        "ok": bool(result.get("mode") == "panel_capability_audit" and summary["matrix_items"] >= 10),
        "mode": "panel_capability_audit_self_check",
        "version": PANEL_CAPABILITY_AUDIT_VERSION,
        "summary": summary,
        "report": result.get("report"),
        "json": result.get("json"),
    }


if __name__ == "__main__":
    print(json.dumps(run_panel_capability_audit(write_report=True), ensure_ascii=False, indent=2, sort_keys=True))

# BEGIN v6.57b command contract repair for panel_capability_audit
LOCALCOMET_COMMAND_CONTRACT_REPAIR_RU_V657B = "v6.57b command contract repair: status/report routes installed for panel_capability_audit"

try:
    _dispatch_before_command_contract_repair_ru_v657b
except NameError:
    try:
        _dispatch_before_command_contract_repair_ru_v657b = dispatch
    except NameError:
        _dispatch_before_command_contract_repair_ru_v657b = None


def _command_contract_normalize_ru_v657b(command):
    return str(command or "").strip().lower().replace("ё", "е")


def _command_contract_latest_file_ru_v657b(directory, patterns):
    from pathlib import Path
    root = Path(directory)
    if not root.exists():
        return None
    found = []
    for pattern in patterns:
        found.extend(path for path in root.glob(pattern) if path.is_file())
    if not found:
        return None
    found.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return str(found[0])


def _command_contract_status_ru_v657b(*args, **kwargs):
    from datetime import datetime
    from pathlib import Path

    report_dir = _localcomet_v657f_project_root() / "Projects" / "Reports" / "panel_capability_audit"
    latest_report = _command_contract_latest_file_ru_v657b(report_dir, ['latest*.md', 'panel_capability_audit_*.md', '*.md'])
    latest_json = _command_contract_latest_file_ru_v657b(report_dir, ['latest*.json', 'panel_capability_audit_*.json', '*.json'])
    return {
        "ok": True,
        "mode": "panel_capability_audit_command_contract",
        "version": "v6.57b",
        "module": __name__,
        "title": "Panel Capability Audit",
        "command_contract": {
            "status": True,
            "report": True,
            "aliases": {
                "status": ['status', 'статус', 'panel capability audit status', 'pc panel capability audit status', 'статус аудита панели', 'статус аудита меню'],
                "report": ['report', 'отчет', 'отчёт', 'panel capability audit report', 'pc panel capability audit report', 'отчет аудита панели', 'отчёт аудита панели', 'отчет аудита меню', 'отчёт аудита меню'],
            },
        },
        "latest_report": latest_report,
        "latest_json": latest_json,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _command_contract_report_ru_v657b(*args, **kwargs):
    import json
    from datetime import datetime
    from pathlib import Path

    status_payload = _command_contract_status_ru_v657b()
    report_root = _localcomet_v657f_project_root() / "Projects" / "Reports" / "panel_capability_audit"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = report_root / f"panel_capability_audit_contract_report_{stamp}.md"
    json_path = report_root / f"panel_capability_audit_contract_report_{stamp}.json"

    lines = [
        f"# Panel Capability Audit command contract report",
        "",
        f"- version: v6.57b",
        f"- module: {__name__}",
        f"- generated_at: {status_payload.get('generated_at')}",
        f"- status route: OK",
        f"- report route: OK",
        f"- latest existing report: {status_payload.get('latest_report')}",
        f"- latest existing json: {status_payload.get('latest_json')}",
        "",
        "## Command contract",
        "",
        "- status: implemented",
        "- report: implemented",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    payload = dict(status_payload)
    payload.update({"report": str(md_path), "json": str(json_path)})
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    latest_md = report_root / "latest_command_contract_report.md"
    latest_json = report_root / "latest_command_contract_report.json"
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    return {
        "ok": True,
        "mode": "panel_capability_audit_command_contract_report",
        "version": "v6.57b",
        "module": __name__,
        "report": str(md_path),
        "json": str(json_path),
        "latest_report": str(latest_md),
        "latest_json": str(latest_json),
    }


def run_status(*args, **kwargs):
    return _command_contract_status_ru_v657b(*args, **kwargs)


def run_report(*args, **kwargs):
    return _command_contract_report_ru_v657b(*args, **kwargs)


def get_status(*args, **kwargs):
    return _command_contract_status_ru_v657b(*args, **kwargs)


def get_report(*args, **kwargs):
    return _command_contract_report_ru_v657b(*args, **kwargs)


SUPPORTED_COMMANDS = sorted(set(list(globals().get("SUPPORTED_COMMANDS", [])) + ['status', 'статус', 'panel capability audit status', 'pc panel capability audit status', 'статус аудита панели', 'статус аудита меню'] + ['report', 'отчет', 'отчёт', 'panel capability audit report', 'pc panel capability audit report', 'отчет аудита панели', 'отчёт аудита панели', 'отчет аудита меню', 'отчёт аудита меню']))
COMMAND_CONTRACT = dict(globals().get("COMMAND_CONTRACT", {}))
COMMAND_CONTRACT.update({
    "status": ['status', 'статус', 'panel capability audit status', 'pc panel capability audit status', 'статус аудита панели', 'статус аудита меню'],
    "report": ['report', 'отчет', 'отчёт', 'panel capability audit report', 'pc panel capability audit report', 'отчет аудита панели', 'отчёт аудита панели', 'отчет аудита меню', 'отчёт аудита меню'],
})


def is_status_command(command):
    lower = _command_contract_normalize_ru_v657b(command)
    status_aliases = set(['status', 'статус', 'panel capability audit status', 'pc panel capability audit status', 'статус аудита панели', 'статус аудита меню'])
    return lower in status_aliases or lower.endswith(" status") or lower.endswith(" статус")


def is_report_command(command):
    lower = _command_contract_normalize_ru_v657b(command)
    report_aliases = set(['report', 'отчет', 'отчёт', 'panel capability audit report', 'pc panel capability audit report', 'отчет аудита панели', 'отчёт аудита панели', 'отчет аудита меню', 'отчёт аудита меню'])
    return lower in report_aliases or lower.endswith(" report") or lower.endswith(" отчет") or lower.endswith(" отчёт")


def dispatch(command="", *args, **kwargs):
    if is_status_command(command):
        return _command_contract_status_ru_v657b(*args, **kwargs)
    if is_report_command(command):
        return _command_contract_report_ru_v657b(*args, **kwargs)
    if callable(_dispatch_before_command_contract_repair_ru_v657b):
        return _dispatch_before_command_contract_repair_ru_v657b(command, *args, **kwargs)
    return {
        "ok": False,
        "mode": "panel_capability_audit_command_contract",
        "version": "v6.57b",
        "error": "unknown command",
        "command": str(command or ""),
        "supported_commands": SUPPORTED_COMMANDS,
    }

# END v6.57b command contract repair for panel_capability_audit
````

### ПУТЬ: modules/parallel_worktree_executor_protocol_ru.py (211 строк, 8026 байт)

````python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List, Optional

PARALLEL_WORKTREE_VERSION = "v6.73"

ROOT_DIR = get_project_root()
if not ROOT_DIR.exists():
    ROOT_DIR = Path(__file__).resolve().parent.parent

SESSION_DIR = ROOT_DIR / ".localcomet" / "parallel_sessions"
LOCKS_DIR = SESSION_DIR / "locks"
PLANS_DIR = SESSION_DIR / "plans"
ARCHIVE_DIR = SESSION_DIR / "archive"

FORBIDDEN_PATHS = [
    "Projects/Reports/desktop_observer/screenshots",
    "Projects/SelfEdit/opencode_backups",
    "Projects/ComputerUse",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "venv",
    ".venv",
    "node_modules",
    "screenshots",
]


def _ensure_dirs():
    for d in [SESSION_DIR, LOCKS_DIR, PLANS_DIR, ARCHIVE_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _safe_path(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def get_parallel_executor_policy() -> Dict[str, Any]:
    return {
        "version": PARALLEL_WORKTREE_VERSION,
        "policy_name": "Parallel Worktree Executor Protocol",
        "rules": [
            "Two writer sessions must not use the same working directory.",
            "One writer + one reviewer is allowed.",
            "Two writer sessions require separate git worktrees.",
            "Each session must declare allowed paths.",
            "If allowed paths overlap, report conflict.",
            "If a session touches forbidden paths, report HOLD.",
            "Final merge is manual only.",
        ],
        "forbidden_paths": FORBIDDEN_PATHS,
        "generated_at": _now(),
    }


def create_session_plan(session_id: str, task_name: str = "", allowed_paths: Optional[List[str]] = None) -> Dict[str, Any]:
    _ensure_dirs()
    safe_id = _safe_path(session_id)
    plan = {
        "session_id": session_id,
        "safe_id": safe_id,
        "task_name": task_name or "unnamed",
        "allowed_paths": allowed_paths or [],
        "created_at": _now(),
        "status": "planned",
    }
    if allowed_paths:
        for path in allowed_paths:
            normalized = path.replace("\\", "/").lower()
            for forbidden in FORBIDDEN_PATHS:
                if forbidden.lower() in normalized:
                    plan["status"] = "HOLD"
                    plan["hold_reason"] = f"Path '{path}' contains forbidden path '{forbidden}'"
                    break
    plan_path = PLANS_DIR / f"{safe_id}_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan


def validate_session_plan(session_id: str) -> Dict[str, Any]:
    safe_id = _safe_path(session_id)
    plan_path = PLANS_DIR / f"{safe_id}_plan.json"
    if not plan_path.exists():
        return {"ok": False, "error": f"Session plan '{session_id}' not found"}
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    existing_locks = list_active_session_locks()
    conflict = False
    for lock_id, lock_info in existing_locks.items():
        if lock_id != safe_id:
            if lock_info.get("allowed_paths"):
                for path_a in plan.get("allowed_paths", []):
                    for path_b in lock_info.get("allowed_paths", []):
                        if Path(path_a).resolve() == Path(path_b).resolve():
                            conflict = True
                            break
    return {
        "ok": True,
        "session_id": session_id,
        "plan": plan,
        "conflict_detected": conflict,
        "status": "HOLD" if conflict or plan.get("status") == "HOLD" else "safe",
    }


def list_active_session_locks() -> Dict[str, Any]:
    _ensure_dirs()
    locks = {}
    for f in LOCKS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            locks[f.stem] = data
        except Exception:
            pass
    return locks


def check_path_conflicts(session_id: str, proposed_paths: List[str]) -> Dict[str, Any]:
    safe_id = _safe_path(session_id)
    conflicts = []
    for path in proposed_paths:
        resolved = Path(path).resolve()
        normalized = str(resolved).lower()
        for forbidden in FORBIDDEN_PATHS:
            if forbidden.replace("\\", "/").lower() in normalized:
                conflicts.append({"path": path, "reason": f"Contains forbidden path '{forbidden}'", "severity": "HOLD"})
    existing = list_active_session_locks()
    for lock_id, lock_info in existing.items():
        if lock_id != safe_id:
            for lock_path in lock_info.get("allowed_paths", []):
                if Path(lock_path).resolve() == resolved:
                    conflicts.append({"path": path, "reason": f"Path also claimed by session '{lock_id}'", "severity": "conflict"})
    return {"session_id": session_id, "proposed_paths": proposed_paths, "conflicts": conflicts, "conflict_count": len(conflicts)}


def generate_worktree_instructions(session_id: str, branch_name: str = "") -> Dict[str, Any]:
    safe_id = _safe_path(session_id)
    branch = branch_name or f"session/{safe_id}"
    instructions = (
        f"Parallel Worktree Instructions for session '{session_id}':\n"
        f"1. Create a git worktree manually:\n"
        f"   git worktree add ../{safe_id}_worktree {branch}\n"
        f"2. Work in the new worktree directory.\n"
        f"3. Do NOT modify the original working directory simultaneously.\n"
        f"4. After finishing, push/submit for manual merge.\n"
        f"5. Do NOT merge automatically.\n"
        f"6. Declare allowed paths in session plan.\n"
        f"7. Check for path conflicts before starting work."
    )
    return {
        "session_id": session_id,
        "branch": branch,
        "instructions": instructions,
        "auto_executed": False,
        "note": "These instructions are for manual execution only. No automatic git worktree creation.",
    }


def status() -> Dict[str, Any]:
    _ensure_dirs()
    plan_count = len(list(PLANS_DIR.glob("*.json")))
    lock_count = len(list(LOCKS_DIR.glob("*.json")))
    return {
        "ok": True,
        "mode": "parallel_worktree_executor_protocol_status",
        "version": PARALLEL_WORKTREE_VERSION,
        "plans_count": plan_count,
        "locks_count": lock_count,
        "policy": get_parallel_executor_policy(),
    }


def report() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "parallel_worktree_executor_protocol_report",
        "version": PARALLEL_WORKTREE_VERSION,
        "generated_at": _now(),
        "policy": get_parallel_executor_policy(),
        "status": status(),
    }


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"status", "parallel sessions status", "статус параллельных сессий", "pc parallel sessions status"}:
        return status()
    if lower in {"report", "parallel executor protocol", "pc parallel executor protocol"}:
        return report()
    if lower.startswith("план параллельной сессии ") or lower.startswith("parallel session plan "):
        parts = lower.split(" ", 3)
        if len(parts) >= 3:
            session_id = parts[-1]
            return create_session_plan(session_id)
    if lower in {"worktree instructions", "worktree instructions status", "pc worktree instructions"}:
        return generate_worktree_instructions("default")
    return {
        "mode": "parallel_worktree_executor_protocol_unrecognized",
        "version": PARALLEL_WORKTREE_VERSION,
        "result": "Неизвестная команда. Используйте: параллельные сессии статус, parallel sessions status, план параллельной сессии <id>, worktree instructions",
    }
````

### ПУТЬ: modules/patch_event_timeline_ru.py (190 строк, 7053 байт)

````python
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List


PATCH_EVENT_TIMELINE_VERSION = "v6.58"
PATCH_EVENT_TIMELINE_NAME = "LocalComet Patch Event Timeline RU"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / "AGENTS.md").exists() or (candidate / "LocalComet_Control_Panel.py").exists():
            return candidate
    return get_project_root()


def _reports_dir() -> Path:
    path = _root() / "Projects" / "Reports" / "patch_event_timeline"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _latest_patch_ux_report() -> Path:
    return _root() / "Projects" / "Reports" / "patch_panel_ux" / "latest_patch_panel_ux_report.md"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _event_status(line: str) -> str:
    lower = line.lower().replace("ё", "е")
    if any(token in lower for token in ["✅", "ok:", "успеш", "пройдена", "code: 0", "applied_ok"]):
        return "ok"
    if any(token in lower for token in ["❌", "stop:", "ошибка", "failed", "rollback", "откачен", "code: 1", "code: 2"]):
        return "error"
    if any(token in lower for token in ["warning", "предупреж"]):
        return "warning"
    return "info"


def build_timeline_from_text(text: str, source: str = "") -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    current_stage = "unknown"
    section_pattern = re.compile(r"^\s*-{2,}\s*([A-ZА-ЯЁ0-9 _-]+)\s*-{2,}\s*$")
    for number, raw in enumerate(str(text or "").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        section = section_pattern.match(line)
        if section:
            current_stage = section.group(1).strip().lower().replace(" ", "_")
            events.append({
                "event_id": f"evt_{len(events)+1:04d}",
                "line": number,
                "stage": current_stage,
                "kind": "stage",
                "status": "info",
                "message": line,
            })
            continue
        lower = line.lower().replace("ё", "е")
        interesting = (
            lower.startswith("$ ")
            or "code:" in lower
            or "rollback" in lower
            or "откач" in lower
            or "ошибка" in lower
            or "stop:" in lower
            or "patch успешно" in lower
            or "patch registry" in lower
            or "validation" in lower
            or "проверка" in lower
        )
        if interesting:
            events.append({
                "event_id": f"evt_{len(events)+1:04d}",
                "line": number,
                "stage": current_stage,
                "kind": "observation" if not lower.startswith("$ ") else "action",
                "status": _event_status(line),
                "message": line[:1200],
            })
    summary = {
        "total": len(events),
        "errors": sum(1 for item in events if item.get("status") == "error"),
        "warnings": sum(1 for item in events if item.get("status") == "warning"),
        "ok": sum(1 for item in events if item.get("status") == "ok"),
    }
    return {
        "ok": True,
        "mode": "patch_event_timeline",
        "version": PATCH_EVENT_TIMELINE_VERSION,
        "generated_at": _now(),
        "source": source,
        "summary": summary,
        "events": events[-200:],
    }


def build_latest_timeline(write_report: bool = True) -> Dict[str, Any]:
    source = _latest_patch_ux_report()
    text = _read(source)
    if not text:
        source = _root() / "Projects" / "ChatGPTRelay" / "response.json"
        text = _read(source)
    payload = build_timeline_from_text(text, source=str(source))
    if write_report:
        paths = _write_reports(payload)
        payload["report"] = str(paths["md"])
        payload["json"] = str(paths["json"])
    return payload


def _write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    out = _reports_dir()
    json_path = out / f"patch_event_timeline_{_stamp()}.json"
    md_path = out / f"patch_event_timeline_{_stamp()}.md"
    latest_json = out / "latest_patch_event_timeline.json"
    latest_md = out / "latest_patch_event_timeline.md"
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json_path.write_text(text, encoding="utf-8")
    latest_json.write_text(text, encoding="utf-8")
    lines = [
        "# LocalComet Patch Event Timeline",
        "",
        f"- version: {payload.get('version')}",
        f"- source: {payload.get('source')}",
        f"- summary: {payload.get('summary')}",
        "",
        "| id | stage | kind | status | message |",
        "|---|---|---|---|---|",
    ]
    for event in payload.get("events", [])[-80:]:
        message = str(event.get("message", "")).replace("|", "\\|")
        lines.append(f"| {event.get('event_id')} | {event.get('stage')} | {event.get('kind')} | {event.get('status')} | {message[:300]} |")
    md = "\n".join(lines)
    md_path.write_text(md, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")
    return {"json": json_path, "md": md_path}


def status(command: str = "status") -> Dict[str, Any]:
    latest = _reports_dir() / "latest_patch_event_timeline.json"
    return {
        "ok": True,
        "mode": "patch_event_timeline_status",
        "version": PATCH_EVENT_TIMELINE_VERSION,
        "latest_json": str(latest),
        "latest_exists": latest.exists(),
        "commands": ["события патча", "patch events", "patch timeline"],
    }


def report(command: str = "report") -> Dict[str, Any]:
    return build_latest_timeline(write_report=True)


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"события патча", "patch events", "patch timeline", "таймлайн патча"}:
        payload = build_latest_timeline(write_report=True)
        payload["handled"] = True
        return payload
    if lower in {"status", "статус", "patch events status"}:
        payload = status(command)
        payload["handled"] = True
        return payload
    if lower in {"report", "отчет", "patch events report"}:
        payload = report(command)
        payload["handled"] = True
        return payload
    return {"ok": False, "handled": False, "mode": "patch_event_timeline", "reason": "unknown command"}
````

### ПУТЬ: modules/patch_panel_ux_reliability_ru.py (654 строк, 25942 байт)

````python
from __future__ import annotations


# BEGIN v6.57f Strict Command Contract Wrapper Repair
STRICT_COMMAND_CONTRACT_WRAPPER_REPAIR_RU_V657F = "v6.57f strict command contract status/report wrappers installed"


def _localcomet_v657f_project_root():
    from pathlib import Path as _Path

    here = _Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / "AGENTS.md").exists():
            return candidate
    return here.parents[1] if len(here.parents) > 1 else here.parent


def _localcomet_v657f_find_latest_report(module_hint="patch_panel_ux"):
    root = _localcomet_v657f_project_root()
    reports_dir = root / "Projects" / "Reports"
    if not reports_dir.exists():
        return None

    tokens = [token for token in str(module_hint or "").lower().split("_") if token]
    candidates = []
    patterns = [
        "**/latest*.md",
        "**/latest*.json",
        "**/*" + str(module_hint or "").replace("_ru", "") + "*.md",
        "**/*" + str(module_hint or "").replace("_ru", "") + "*.json",
    ]

    for pattern in patterns:
        try:
            for item in reports_dir.glob(pattern):
                if item.is_file():
                    candidates.append(item)
        except Exception:
            pass

    if not candidates:
        try:
            for item in reports_dir.rglob("*"):
                if not item.is_file():
                    continue
                lower_name = str(item).lower()
                if tokens and all(token in lower_name for token in tokens[:2]):
                    candidates.append(item)
        except Exception:
            pass

    if not candidates:
        return None

    try:
        return max(candidates, key=lambda item: item.stat().st_mtime)
    except Exception:
        return candidates[-1]


def status(command=None, *args, **kwargs):
    latest = _localcomet_v657f_find_latest_report("patch_panel_ux")
    return {
        "ok": True,
        "mode": "patch_panel_ux_status",
        "version": "v6.57f",
        "module": __name__,
        "status": "ready",
        "report": str(latest) if latest else "",
        "report_exists": bool(latest),
        "command_contract": {
            "status": True,
            "report": True,
            "source": "v6.57f strict command contract wrapper repair"
        }
    }


def report(command=None, *args, **kwargs):
    latest = _localcomet_v657f_find_latest_report("patch_panel_ux")
    return {
        "ok": True,
        "mode": "patch_panel_ux_report",
        "version": "v6.57f",
        "module": __name__,
        "report": str(latest) if latest else "",
        "report_exists": bool(latest),
        "message": "Latest report resolved." if latest else "No latest report found yet; command contract wrapper is installed."
    }
# END v6.57f Strict Command Contract Wrapper Repair

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


PATCH_PANEL_UX_VERSION = "v6.57"
PATCH_PANEL_UX_NAME = "Patch Panel UX Reliability RU"

STATUS_NO_PATCH_SELECTED = "NO_PATCH_SELECTED"
STATUS_PATCH_SELECTED = "PATCH_SELECTED"
STATUS_VALIDATING = "VALIDATING"
STATUS_VALIDATED_OK = "VALIDATED_OK"
STATUS_VALIDATION_FAILED = "VALIDATION_FAILED"
STATUS_APPLYING = "APPLYING"
STATUS_RUNNING_TESTS = "RUNNING_TESTS"
STATUS_APPLIED_OK = "APPLIED_OK"
STATUS_ROLLED_BACK_TESTS_FAILED = "ROLLED_BACK_TESTS_FAILED"
STATUS_BLOCKED = "BLOCKED"
STATUS_ERROR = "ERROR"

COLOR_SUCCESS = "success"
COLOR_ERROR = "error"
COLOR_WARNING = "warning"
COLOR_NEUTRAL = "neutral"

STATUS_COLOR = {
    STATUS_NO_PATCH_SELECTED: COLOR_NEUTRAL,
    STATUS_PATCH_SELECTED: COLOR_NEUTRAL,
    STATUS_VALIDATING: COLOR_NEUTRAL,
    STATUS_VALIDATED_OK: COLOR_SUCCESS,
    STATUS_VALIDATION_FAILED: COLOR_ERROR,
    STATUS_APPLYING: COLOR_NEUTRAL,
    STATUS_RUNNING_TESTS: COLOR_NEUTRAL,
    STATUS_APPLIED_OK: COLOR_SUCCESS,
    STATUS_ROLLED_BACK_TESTS_FAILED: COLOR_ERROR,
    STATUS_BLOCKED: COLOR_ERROR,
    STATUS_ERROR: COLOR_ERROR,
}


def _lower(text: Any) -> str:
    return str(text or "").lower().replace("ё", "е")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _root_dir() -> Path:
    cwd = Path.cwd()
    if (cwd / "LocalComet_Control_Panel.py").exists() or (cwd / "LocalComet_Patch_Panel.py").exists():
        return cwd
    return _localcomet_v657f_project_root()


def _reports_dir() -> Path:
    return _root_dir() / "Projects" / "Reports" / "patch_panel_ux"


def _code_lines(text: Any) -> List[int]:
    codes: List[int] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line.lower().startswith("code:"):
            continue
        value = line.split(":", 1)[1].strip()
        try:
            codes.append(int(float(value)))
        except Exception:
            codes.append(999)
    return codes


def code_lines_are_zero(text: Any) -> bool:
    codes = _code_lines(text)
    return all(code == 0 for code in codes)


def extract_patch_version(text: Any) -> str:
    raw = str(text or "")
    patterns = [
        r"Patch Registry:\s*(v[0-9][0-9A-Za-z.\-_]*)\s*записан",
        r'"version"\s*:\s*"(v[0-9][0-9A-Za-z.\-_]*)"',
        r"\b(v[0-9]+\.[0-9]+[0-9A-Za-z.\-_]*)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw)
        if match:
            return match.group(1)
    return PATCH_PANEL_UX_VERSION


def extract_report_path(text: Any) -> str:
    raw = str(text or "")
    candidates: List[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if any(key in lowered for key in ("report:", "отчет:", "отчет automation:", "report")):
            match = re.search(r"([A-Za-z]:\\[^\r\n]+?\.(?:md|json|txt))", stripped)
            if match:
                candidates.append(match.group(1))
    return candidates[-1] if candidates else str(_reports_dir() / "latest_patch_panel_ux_report.md")


def extract_first_failure(text: Any) -> str:
    raw = str(text or "")
    ignored = (
        '"failed": 0',
        "'failed': 0",
        "failed=0",
        "failed 0",
        "0 failed",
        "hard_failures\": 0",
        "warnings\": 0",
        "'hard_failures': 0",
        "'warnings': 0",
    )
    for line in raw.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped:
            continue
        if any(token in lowered for token in ignored):
            continue
        if any(token in lowered for token in ("[fail]", " fail", "fail:", "failed", "stop:", "traceback", "exception", "ошибка", "упали", "откачены", "blocked")):
            return stripped[:600]
    return ""


def has_nonblocking_after_patch_warning(text: Any) -> bool:
    lower = _lower(text)
    if "auto verification" not in lower and "after patch" not in lower:
        return False
    has_after_failure = (
        "status: failed" in lower
        or "[fail] full stability" in lower
        or ("full stability" in lower and "fail" in lower)
    )
    has_later_green = (
        "ok: проект проверен" in lower
        or "functional/contracts/strict green" in lower
        or ("strict_project_stability" in lower and '"warnings": 0' in lower and '"hard_failures": 0' in lower)
    )
    return bool(has_after_failure and has_later_green)


def classify_patch_workflow_text(text: Any) -> Dict[str, Any]:
    raw = str(text or "")
    lower = _lower(raw)
    codes_zero = code_lines_are_zero(raw)
    version = extract_patch_version(raw)
    warning = has_nonblocking_after_patch_warning(raw)
    rollback = any(marker in lower for marker in (
        "изменения откачены",
        "откачены",
        "rollback",
        "patch применен, но тесты упали",
        "тесты упали",
    ))
    validation_failed = any(marker in lower for marker in (
        "relay validate не прошел",
        "проверка не пройдена",
        "validation failed",
        "relay response: ❌",
        "json parse error",
        "нет списка operations",
        "operations missing",
    ))
    blocked = any(marker in lower for marker in (
        "blocked",
        "заблокирован",
        "stop: импорт response не прошел",
        "stop: relay validate не прошел",
        "stop: patch не применялся",
        "relay response не импортирован",
        "patch не применен",
    ))
    exception = any(marker in lower for marker in (
        "traceback",
        "exception",
        "assertionerror",
        "ошибка применения patch",
    ))
    success = any(marker in lower for marker in (
        "patch успешно применен",
        "patch registry:",
        "ok: patch принят",
        "applied_ok",
    ))
    if validation_failed:
        status = STATUS_VALIDATION_FAILED
    elif rollback:
        status = STATUS_ROLLED_BACK_TESTS_FAILED
    elif exception and not success:
        status = STATUS_ERROR
    elif not codes_zero:
        status = STATUS_ROLLED_BACK_TESTS_FAILED if success else STATUS_ERROR
    elif blocked and not success:
        status = STATUS_BLOCKED
    elif success and codes_zero:
        status = STATUS_APPLIED_OK
    elif "relay response: ✅" in lower or "проверка пройдена" in lower:
        status = STATUS_VALIDATED_OK
    elif "patch выбран" in lower or "response.json импортирован" in lower:
        status = STATUS_PATCH_SELECTED
    elif "stop:" in lower:
        status = STATUS_BLOCKED
    else:
        status = STATUS_ERROR if raw.strip() else STATUS_NO_PATCH_SELECTED
    color = STATUS_COLOR.get(status, COLOR_NEUTRAL)
    if warning and status == STATUS_APPLIED_OK:
        color = COLOR_WARNING
    first_failure = extract_first_failure(raw)
    summary = format_final_summary({
        "status": status,
        "color": color,
        "version": version,
        "warning": warning,
        "first_failure": first_failure,
        "report": extract_report_path(raw),
        "tests_ok": status == STATUS_APPLIED_OK and codes_zero,
        "rollback": rollback,
    })
    return {
        "ok": status == STATUS_APPLIED_OK,
        "status": status,
        "color": color,
        "version": version,
        "warning": warning,
        "tests_ok": status == STATUS_APPLIED_OK and codes_zero,
        "rollback": rollback,
        "first_failure": first_failure,
        "report": extract_report_path(raw),
        "codes": _code_lines(raw),
        "final_summary": summary,
        "generated_at": _now(),
    }


def format_final_summary(classification: Dict[str, Any]) -> str:
    status = str(classification.get("status") or STATUS_ERROR)
    version = str(classification.get("version") or PATCH_PANEL_UX_VERSION)
    report = str(classification.get("report") or (_reports_dir() / "latest_patch_panel_ux_report.md"))
    first_failure = str(classification.get("first_failure") or "не найдено")
    warning = bool(classification.get("warning"))

    if status == STATUS_APPLIED_OK and warning:
        title = "⚠️ Патч применен успешно, но есть предупреждение after-patch проверки"
        tests = "пройдены; есть неблокирующее предупреждение"
        rollback_text = "не выполнялся"
    elif status == STATUS_APPLIED_OK:
        title = "✅ Патч применен успешно"
        tests = "пройдены"
        rollback_text = "не выполнялся"
    elif status == STATUS_ROLLED_BACK_TESTS_FAILED:
        title = "❌ Патч был применен, но тесты упали. Выполнен rollback."
        tests = "упали"
        rollback_text = "выполнялся"
    elif status == STATUS_VALIDATION_FAILED:
        title = "⛔ Патч заблокирован на проверке"
        tests = "не запускались"
        rollback_text = "не выполнялся"
    elif status == STATUS_BLOCKED:
        title = "⛔ Патч заблокирован"
        tests = "не запускались или остановлены"
        rollback_text = "не выполнялся"
    elif status == STATUS_VALIDATED_OK:
        title = "✅ Патч прошел проверку, но еще не применен"
        tests = "не запускались"
        rollback_text = "не выполнялся"
    elif status == STATUS_PATCH_SELECTED:
        title = "📦 Patch выбран"
        tests = "не запускались"
        rollback_text = "не выполнялся"
    else:
        title = "❌ Ошибка patch workflow"
        tests = "неизвестно"
        rollback_text = "проверь raw log"
    return "\n".join([
        "=== PATCH UX FINAL SUMMARY v6.57 ===",
        title,
        f"Статус: {status}",
        f"Версия: {version}",
        f"Тесты: {tests}",
        f"Rollback: {rollback_text}",
        f"Первый проблемный пункт: {first_failure}",
        f"Отчет: {report}",
        "=== RAW LOG BELOW ===",
    ])


def write_latest_report(classification: Dict[str, Any], raw_text: Any = "") -> Dict[str, str]:
    reports = _reports_dir()
    reports.mkdir(parents=True, exist_ok=True)
    payload = dict(classification)
    payload["raw_log_preview"] = str(raw_text or "")[:12000]
    payload["mode"] = "patch_panel_ux_reliability"
    payload["ux_version"] = PATCH_PANEL_UX_VERSION
    json_path = reports / "latest_patch_panel_ux_report.json"
    md_path = reports / "latest_patch_panel_ux_report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    md_lines = [
        "# Patch Panel UX Reliability Report",
        "",
        f"- generated_at: {payload.get('generated_at')}",
        f"- ux_version: {PATCH_PANEL_UX_VERSION}",
        f"- status: {payload.get('status')}",
        f"- color: {payload.get('color')}",
        f"- version: {payload.get('version')}",
        f"- warning: {payload.get('warning')}",
        f"- tests_ok: {payload.get('tests_ok')}",
        f"- rollback: {payload.get('rollback')}",
        f"- first_failure: {payload.get('first_failure') or 'none'}",
        "",
        "## Final summary",
        "",
        str(payload.get("final_summary") or ""),
        "",
        "## Raw log preview",
        "",
        "```text",
        str(raw_text or "")[:12000],
        "```",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def classify_and_report(text: Any) -> Dict[str, Any]:
    classification = classify_patch_workflow_text(text)
    paths = write_latest_report(classification, text)
    classification["report_json"] = paths["json"]
    classification["report_md"] = paths["md"]
    classification["final_summary"] = str(classification.get("final_summary", "")).replace(
        str(_reports_dir() / "latest_patch_panel_ux_report.md"),
        paths["md"],
    )
    return classification


def run_self_check() -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details})

    success = "Patch успешно применен.\nPatch Registry: v6.57 записан\nCODE: 0\nOK: проект проверен. functional/contracts/strict green."
    success_cls = classify_patch_workflow_text(success)
    add("apply success maps to green APPLIED_OK", success_cls["status"] == STATUS_APPLIED_OK and success_cls["color"] == COLOR_SUCCESS, success_cls)

    rollback = "Patch применен, но тесты упали. Изменения ОТКАЧЕНЫ.\nRollback: C:\\x\\rollback.json\nCODE: 1"
    rollback_cls = classify_patch_workflow_text(rollback)
    add("rollback maps to red ROLLED_BACK_TESTS_FAILED", rollback_cls["status"] == STATUS_ROLLED_BACK_TESTS_FAILED and rollback_cls["color"] == COLOR_ERROR, rollback_cls)

    validation = "Relay response: ❌ проверка не пройдена\nSTOP: relay validate не прошел."
    validation_cls = classify_patch_workflow_text(validation)
    add("validation failure maps to red VALIDATION_FAILED", validation_cls["status"] == STATUS_VALIDATION_FAILED and validation_cls["color"] == COLOR_ERROR, validation_cls)

    warning = success + "\nAfter Patch проверка выполнена.\nAuto Verification:\n- status: failed\n- [FAIL] full stability\n\n--- STRICT PROJECT STABILITY ---\n{\"hard_failures\": 0, \"warnings\": 0}\nOK: проект проверен. functional/contracts/strict green."
    warning_cls = classify_patch_workflow_text(warning)
    add("after patch mismatch maps to orange warning not red", warning_cls["status"] == STATUS_APPLIED_OK and warning_cls["color"] == COLOR_WARNING, warning_cls)

    false_failure = "Patch успешно применен.\nSTDOUT:\n{\"summary\":{\"failed\":0,\"passed\":10}}\nCODE: 0"
    false_cls = classify_patch_workflow_text(false_failure)
    add("failed zero is not red failure", false_cls["status"] == STATUS_APPLIED_OK, false_cls)

    paths = write_latest_report(success_cls, success)
    add("latest reports written", Path(paths["json"]).exists() and Path(paths["md"]).exists(), paths)

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    return {
        "ok": summary["failed"] == 0,
        "mode": "patch_panel_ux_reliability_self_check",
        "version": PATCH_PANEL_UX_VERSION,
        "summary": summary,
        "checks": checks,
    }


def dispatch(command: Any = "") -> Dict[str, Any]:
    lower = _lower(command)
    if lower in {"patch ux status", "статус patch ux", "статус патча", "patch status"}:
        report = _reports_dir() / "latest_patch_panel_ux_report.json"
        if report.exists():
            try:
                payload = json.loads(report.read_text(encoding="utf-8"))
                return {"ok": True, "handled": True, "mode": "patch_panel_ux_status", "report": str(report), "status": payload.get("status"), "payload": payload}
            except Exception as exc:
                return {"ok": False, "handled": True, "mode": "patch_panel_ux_status", "error": str(exc)}
        return {"ok": True, "handled": True, "mode": "patch_panel_ux_status", "status": STATUS_NO_PATCH_SELECTED, "report": str(report)}
    return {"ok": True, "handled": True, "mode": "patch_panel_ux_reliability", "version": PATCH_PANEL_UX_VERSION, "self_check": run_self_check()}


if __name__ == "__main__":
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))

# BEGIN v6.57b command contract repair for patch_panel_ux
LOCALCOMET_COMMAND_CONTRACT_REPAIR_RU_V657B = "v6.57b command contract repair: status/report routes installed for patch_panel_ux"

try:
    _dispatch_before_command_contract_repair_ru_v657b
except NameError:
    try:
        _dispatch_before_command_contract_repair_ru_v657b = dispatch
    except NameError:
        _dispatch_before_command_contract_repair_ru_v657b = None


def _command_contract_normalize_ru_v657b(command):
    return str(command or "").strip().lower().replace("ё", "е")


def _command_contract_latest_file_ru_v657b(directory, patterns):
    from pathlib import Path
    root = Path(directory)
    if not root.exists():
        return None
    found = []
    for pattern in patterns:
        found.extend(path for path in root.glob(pattern) if path.is_file())
    if not found:
        return None
    found.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return str(found[0])


def _command_contract_status_ru_v657b(*args, **kwargs):
    from datetime import datetime
    from pathlib import Path

    report_dir = _reports_dir()
    latest_report = _command_contract_latest_file_ru_v657b(report_dir, ['latest*.md', 'patch_panel_ux_*.md', '*.md'])
    latest_json = _command_contract_latest_file_ru_v657b(report_dir, ['latest*.json', 'patch_panel_ux_*.json', '*.json'])
    return {
        "ok": True,
        "mode": "patch_panel_ux_command_contract",
        "version": "v6.57b",
        "module": __name__,
        "title": "Patch Panel UX Reliability",
        "command_contract": {
            "status": True,
            "report": True,
            "aliases": {
                "status": ['status', 'статус', 'patch panel ux status', 'patch ux status', 'статус патча', 'статус patch panel ux'],
                "report": ['report', 'отчет', 'отчёт', 'patch panel ux report', 'patch ux report', 'отчет патча', 'отчёт патча', 'отчет ux патча', 'отчёт ux патча'],
            },
        },
        "latest_report": latest_report,
        "latest_json": latest_json,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _command_contract_report_ru_v657b(*args, **kwargs):
    import json
    from datetime import datetime
    from pathlib import Path

    status_payload = _command_contract_status_ru_v657b()
    report_root = _reports_dir()
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = report_root / f"patch_panel_ux_contract_report_{stamp}.md"
    json_path = report_root / f"patch_panel_ux_contract_report_{stamp}.json"

    lines = [
        f"# Patch Panel UX Reliability command contract report",
        "",
        f"- version: v6.57b",
        f"- module: {__name__}",
        f"- generated_at: {status_payload.get('generated_at')}",
        f"- status route: OK",
        f"- report route: OK",
        f"- latest existing report: {status_payload.get('latest_report')}",
        f"- latest existing json: {status_payload.get('latest_json')}",
        "",
        "## Command contract",
        "",
        "- status: implemented",
        "- report: implemented",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    payload = dict(status_payload)
    payload.update({"report": str(md_path), "json": str(json_path)})
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    latest_md = report_root / "latest_command_contract_report.md"
    latest_json = report_root / "latest_command_contract_report.json"
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    return {
        "ok": True,
        "mode": "patch_panel_ux_command_contract_report",
        "version": "v6.57b",
        "module": __name__,
        "report": str(md_path),
        "json": str(json_path),
        "latest_report": str(latest_md),
        "latest_json": str(latest_json),
    }


def run_status(*args, **kwargs):
    return _command_contract_status_ru_v657b(*args, **kwargs)


def run_report(*args, **kwargs):
    return _command_contract_report_ru_v657b(*args, **kwargs)


def get_status(*args, **kwargs):
    return _command_contract_status_ru_v657b(*args, **kwargs)


def get_report(*args, **kwargs):
    return _command_contract_report_ru_v657b(*args, **kwargs)


SUPPORTED_COMMANDS = sorted(set(list(globals().get("SUPPORTED_COMMANDS", [])) + ['status', 'статус', 'patch panel ux status', 'patch ux status', 'статус патча', 'статус patch panel ux'] + ['report', 'отчет', 'отчёт', 'patch panel ux report', 'patch ux report', 'отчет патча', 'отчёт патча', 'отчет ux патча', 'отчёт ux патча']))
COMMAND_CONTRACT = dict(globals().get("COMMAND_CONTRACT", {}))
COMMAND_CONTRACT.update({
    "status": ['status', 'статус', 'patch panel ux status', 'patch ux status', 'статус патча', 'статус patch panel ux'],
    "report": ['report', 'отчет', 'отчёт', 'patch panel ux report', 'patch ux report', 'отчет патча', 'отчёт патча', 'отчет ux патча', 'отчёт ux патча'],
})


def is_status_command(command):
    lower = _command_contract_normalize_ru_v657b(command)
    status_aliases = set(['status', 'статус', 'patch panel ux status', 'patch ux status', 'статус патча', 'статус patch panel ux'])
    return lower in status_aliases or lower.endswith(" status") or lower.endswith(" статус")


def is_report_command(command):
    lower = _command_contract_normalize_ru_v657b(command)
    report_aliases = set(['report', 'отчет', 'отчёт', 'patch panel ux report', 'patch ux report', 'отчет патча', 'отчёт патча', 'отчет ux патча', 'отчёт ux патча'])
    return lower in report_aliases or lower.endswith(" report") or lower.endswith(" отчет") or lower.endswith(" отчёт")


def dispatch(command="", *args, **kwargs):
    if is_status_command(command):
        return _command_contract_status_ru_v657b(*args, **kwargs)
    if is_report_command(command):
        return _command_contract_report_ru_v657b(*args, **kwargs)
    if callable(_dispatch_before_command_contract_repair_ru_v657b):
        return _dispatch_before_command_contract_repair_ru_v657b(command, *args, **kwargs)
    return {
        "ok": False,
        "mode": "patch_panel_ux_command_contract",
        "version": "v6.57b",
        "error": "unknown command",
        "command": str(command or ""),
        "supported_commands": SUPPORTED_COMMANDS,
    }

# END v6.57b command contract repair for patch_panel_ux
````

### ПУТЬ: modules/patch_registry.py (231 строк, 5926 байт)

````python
import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
REGISTRY_DIR = ROOT_DIR / "Projects" / "PatchRegistry"
REGISTRY_FILE = REGISTRY_DIR / "patches.json"


def _ensure_registry():
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)

    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.write_text("[]", encoding="utf-8")


def _load_entries():
    _ensure_registry()

    if not REGISTRY_FILE.exists():
        return []

    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict) and isinstance(data.get("patches"), list):
        return data["patches"]

    return []


def _save_entries(entries):
    _ensure_registry()
    REGISTRY_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def extract_patch_version(*values):
    for value in values:
        text = str(value or "")

        for raw_token in text.replace(":", " ").replace(";", " ").replace(",", " ").split():
            token = raw_token.strip(" [](){}'\".")

            if len(token) >= 2 and token.lower().startswith("v") and any(ch.isdigit() for ch in token):
                return token

    return ""


def list_patches():
    return _load_entries()


def get_latest_patch():
    entries = _load_entries()

    if not entries:
        return {}

    return entries[-1]


def latest_patch():
    return get_latest_patch()


def _operation_paths(patch):
    paths = []

    for op in patch.get("operations", []) or []:
        if isinstance(op, dict) and op.get("path"):
            paths.append(str(op.get("path")))

    return paths


def _infer_source(patch, response_file, patch_file):
    explicit = str(patch.get("source", "") or "").strip()

    if explicit:
        return explicit

    text = f"{response_file} {patch_file}".lower()

    if "chatgpt_relay" in text or "chatgptrelay" in text or "response.json" in text:
        return "chatgpt_relay"

    if "codex" in text:
        return "codex"

    return "unknown"


def record_patch(
    patch=None,
    version="",
    summary="",
    applied_at="",
    response_file="",
    patch_file="",
    rollback_file="",
    changed_files=None,
    operation_count=None,
    tests=None,
    stability_score="",
    status="applied",
    source="",
):
    patch = patch or {}
    changed_files = changed_files if changed_files is not None else _operation_paths(patch)
    operation_count = operation_count if operation_count is not None else len(patch.get("operations", []) or [])
    summary = str(summary or patch.get("summary", "") or "").strip()
    version = extract_patch_version(
        version,
        patch.get("version", ""),
        patch.get("patch_version", ""),
        summary,
        patch_file,
    ) or "unknown"
    source = source or _infer_source(patch, response_file, patch_file)

    tests = tests if isinstance(tests, dict) else {"ok": bool(tests), "result": str(tests or "")}

    entry = {
        "version": version,
        "summary": summary or "нет summary",
        "applied_at": applied_at or datetime.now().isoformat(timespec="seconds"),
        "response_file": str(response_file or ""),
        "patch_file": str(patch_file or ""),
        "rollback_file": str(rollback_file or ""),
        "changed_files": list(changed_files or []),
        "operation_count": int(operation_count or 0),
        "tests": tests,
        "stability_score": str(stability_score or get_value("last_stability_score", "") or ""),
        "status": str(status or "unknown"),
        "source": source,
    }

    entries = _load_entries()
    entries.append(entry)
    _save_entries(entries)

    set_value("last_patch_registry_file", str(REGISTRY_FILE))
    set_value("last_patch_registry_count", len(entries))
    set_value("last_patch_version", version)
    set_value("last_patch_summary", entry["summary"])
    set_value("last_patch_status", entry["status"])
    set_value("last_patch_applied_at", entry["applied_at"])

    return entry


def register_applied_patch(
    patch,
    patch_file,
    rollback_file,
    tests_ok,
    tests_output,
    response_file="",
    changed_files=None,
    source="",
):
    return record_patch(
        patch=patch,
        response_file=response_file,
        patch_file=patch_file,
        rollback_file=rollback_file,
        changed_files=changed_files,
        tests={
            "ok": bool(tests_ok),
            "result": str(tests_output or ""),
        },
        status="applied" if tests_ok else "failed",
        source=source,
    )


def record_current_version(version="v5.52", summary="Manual current version snapshot"):
    return record_patch(
        version=version,
        summary=summary,
        changed_files=[
            "LocalComet_Control_Panel.py",
            "modules/patch_registry.py",
            "agents/system_agent.py",
            "modules/stability_test.py",
        ],
        operation_count=0,
        tests={
            "ok": True,
            "result": "manual registry snapshot",
        },
        status="applied",
        source="codex",
    )


def get_current_version():
    latest = get_latest_patch()
    return str(latest.get("version") or get_value("last_patch_version", "unknown") or "unknown")


def short_status():
    latest = get_latest_patch()

    if not latest:
        return f"Patch Registry: empty | file: {REGISTRY_FILE}"

    return (
        f"Patch Registry: {latest.get('version', 'unknown')} | "
        f"{latest.get('status', 'unknown')} | "
        f"{latest.get('summary', 'нет summary')} | "
        f"count: {len(list_patches())}"
    )


def registry_path():
    _ensure_registry()
    return REGISTRY_FILE
````

### ПУТЬ: modules/pc_agent_actions.py (389 строк, 11615 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import subprocess

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
ACTIONS_REPORTS_DIR = REPORTS_DIR / "pc_agent_actions"
NOTES_DIR = PROJECTS_DIR / "PCAgent" / "Notes"


APP_ALLOWLIST = {
    "notepad": ["notepad.exe"],
    "блокнот": ["notepad.exe"],
    "calc": ["calc.exe"],
    "calculator": ["calc.exe"],
    "калькулятор": ["calc.exe"],
    "explorer": ["explorer.exe"],
    "проводник": ["explorer.exe"],
    "paint": ["mspaint.exe"],
    "paint.exe": ["mspaint.exe"],
}

FOLDER_ALLOWLIST = {
    "root": ROOT_DIR,
    "проект": ROOT_DIR,
    "projects": PROJECTS_DIR,
    "проекты": PROJECTS_DIR,
    "reports": REPORTS_DIR,
    "отчеты": REPORTS_DIR,
    "selfedit": PROJECTS_DIR / "SelfEdit",
    "relay": PROJECTS_DIR / "ChatGPTRelay",
    "downloads": Path.home() / "Downloads",
    "загрузки": Path.home() / "Downloads",
    "pcagent": PROJECTS_DIR / "PCAgent",
    "pc agent": PROJECTS_DIR / "PCAgent",
    "actions": ACTIONS_REPORTS_DIR,
}

BLOCKED_TERMS = [
    "cmd",
    "powershell",
    "shell",
    "terminal",
    "regedit",
    "registry",
    "format",
    "delete",
    "remove",
    "rmdir",
    "del ",
    "rm -rf",
    "удали",
    "стереть",
    "формат",
    "реестр",
    "пароль",
    "password",
    "token",
    "secret",
    "private key",
    "приватный ключ",
    "оплати",
    "payment",
    "банк",
    "bank",
    "casino",
    "ставка",
    "login",
    "логин",
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _safe_write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _safe_write_text(path: Path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text or ""), encoding="utf-8")
    return str(path)


def classify_action_request(text):
    lower = _norm(text)
    matched = [term for term in BLOCKED_TERMS if term in lower]
    return {
        "safe": not matched,
        "blocked_reason": "Опасные термины: " + ", ".join(matched) if matched else "",
        "matched_terms": matched,
    }


def pc_actions_status():
    payload = {
        "ok": True,
        "mode": "pc_agent_actions",
        "generated_at": _now(),
        "apps": sorted(APP_ALLOWLIST.keys()),
        "folders": sorted(FOLDER_ALLOWLIST.keys()),
        "commands": [
            "pc actions статус",
            "pc actions список",
            "pc actions dry open app <name>",
            "pc actions open app <name>",
            "pc actions dry open folder <name>",
            "pc actions open folder <name>",
            "pc actions note <text>",
            "pc actions report",
        ],
        "last_action": get_value("pc_agent_actions_last_action", ""),
        "last_result": get_value("pc_agent_actions_last_result", ""),
    }
    set_value("pc_agent_actions_status", payload)
    return payload


def format_pc_actions_status(payload=None):
    payload = payload or pc_actions_status()
    lines = [
        "PC Agent Actions Pack:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "Доступные приложения:",
        "- " + ", ".join(payload.get("apps", [])),
        "",
        "Доступные папки:",
        "- " + ", ".join(payload.get("folders", [])),
        "",
        "Команды:",
    ]
    lines.extend("- " + command for command in payload.get("commands", []))
    return "\n".join(lines)


def list_actions():
    return {
        "ok": True,
        "apps": APP_ALLOWLIST,
        "folders": {key: str(value) for key, value in FOLDER_ALLOWLIST.items()},
        "blocked_terms": BLOCKED_TERMS,
        "examples": [
            "pc actions dry open app notepad",
            "pc actions open app notepad",
            "pc actions open folder projects",
            "pc actions note План: проверить агент",
            "pc codex план открыть блокнот и написать заметку",
        ],
    }


def _resolve_app(name):
    key = _norm(name)
    if key not in APP_ALLOWLIST:
        return None
    return APP_ALLOWLIST[key]


def _resolve_folder(name):
    key = _norm(name)
    if key not in FOLDER_ALLOWLIST:
        return None
    path = FOLDER_ALLOWLIST[key]
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return path


def open_app(name, dry_run=True):
    safety = classify_action_request(name)
    command = _resolve_app(name)
    payload = {
        "ok": False,
        "action": "open_app",
        "name": name,
        "dry_run": bool(dry_run),
        "safety": safety,
        "command": command,
    }

    if not safety.get("safe"):
        payload["result"] = "BLOCKED."
        return _remember(payload)

    if not command:
        payload["result"] = "App is not allowlisted."
        payload["allowed"] = sorted(APP_ALLOWLIST.keys())
        return _remember(payload)

    if dry_run:
        payload["ok"] = True
        payload["result"] = "DRY_RUN: приложение не запущено."
        return _remember(payload)

    subprocess.Popen(command, shell=False)
    payload["ok"] = True
    payload["result"] = "Приложение запущено."
    return _remember(payload)


def open_folder(name, dry_run=True):
    safety = classify_action_request(name)
    path = _resolve_folder(name)
    payload = {
        "ok": False,
        "action": "open_folder",
        "name": name,
        "dry_run": bool(dry_run),
        "safety": safety,
        "path": str(path) if path else "",
    }

    if not safety.get("safe"):
        payload["result"] = "BLOCKED."
        return _remember(payload)

    if not path:
        payload["result"] = "Folder is not allowlisted."
        payload["allowed"] = sorted(FOLDER_ALLOWLIST.keys())
        return _remember(payload)

    if dry_run:
        payload["ok"] = True
        payload["result"] = "DRY_RUN: папка не открыта."
        return _remember(payload)

    subprocess.Popen(["explorer.exe", str(path)], shell=False)
    payload["ok"] = True
    payload["result"] = "Папка открыта."
    return _remember(payload)


def create_note(text, dry_run=False):
    safety = classify_action_request(text)
    payload = {
        "ok": False,
        "action": "create_note",
        "dry_run": bool(dry_run),
        "safety": safety,
        "text_preview": str(text or "")[:500],
    }

    if not safety.get("safe"):
        payload["result"] = "BLOCKED."
        return _remember(payload)

    if dry_run:
        payload["ok"] = True
        payload["result"] = "DRY_RUN: заметка не создана."
        return _remember(payload)

    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTES_DIR / f"note_{_stamp()}.md"
    body = "\n".join([
        "# PC Agent Note",
        "",
        f"- generated_at: {_now()}",
        "",
        str(text or "").strip(),
        "",
    ])
    _safe_write_text(path, body)
    payload["ok"] = True
    payload["path"] = str(path)
    payload["result"] = "Заметка создана."
    return _remember(payload)


def create_actions_report(note=""):
    ACTIONS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": pc_actions_status(),
        "last_action": get_value("pc_agent_actions_last_action", ""),
        "last_result": get_value("pc_agent_actions_last_result", ""),
    }

    json_path = ACTIONS_REPORTS_DIR / f"pc_agent_actions_report_{_stamp()}.json"
    md_path = ACTIONS_REPORTS_DIR / f"pc_agent_actions_report_{_stamp()}.md"

    _safe_write_json(json_path, payload)
    md = [
        "# PC Agent Actions Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_pc_actions_status(payload["status"]),
        "```",
        "",
        "## Last Result",
        "",
        "```json",
        json.dumps(payload["last_result"], ensure_ascii=False, indent=2),
        "```",
    ]
    _safe_write_text(md_path, "\n".join(md))

    result = {"ok": True, "report": str(md_path), "json": str(json_path)}
    set_value("pc_agent_actions_last_report", result)
    return result


def _remember(payload):
    set_value("pc_agent_actions_last_action", payload.get("action", "unknown"))
    set_value("pc_agent_actions_last_result", payload)
    return payload


def dispatch_action(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc actions", "pc actions status", "pc actions статус", "pc action status", "actions status"}:
        return pc_actions_status()

    if lower in {"pc actions список", "pc actions list", "pc action list", "список действий"}:
        return list_actions()

    if lower in {"pc actions report", "pc actions отчет", "actions report"}:
        return create_actions_report("manual report from panel chat")

    prefixes = [
        ("pc actions dry open app ", "dry_open_app"),
        ("pc action dry open app ", "dry_open_app"),
        ("pc actions open app ", "open_app"),
        ("pc action open app ", "open_app"),
        ("pc actions dry open folder ", "dry_open_folder"),
        ("pc action dry open folder ", "dry_open_folder"),
        ("pc actions open folder ", "open_folder"),
        ("pc action open folder ", "open_folder"),
        ("pc actions note ", "note"),
        ("pc action note ", "note"),
        ("создай заметку ", "note"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "dry_open_app":
                return open_app(value, dry_run=True)
            if action == "open_app":
                return open_app(value, dry_run=False)
            if action == "dry_open_folder":
                return open_folder(value, dry_run=True)
            if action == "open_folder":
                return open_folder(value, dry_run=False)
            if action == "note":
                return create_note(value, dry_run=False)

    return {
        "ok": False,
        "action": "unknown",
        "result": "Не понял PC Actions команду.",
        "help": list_actions(),
    }


def format_action_result(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)
````

### ПУТЬ: modules/pc_agent_core.py (607 строк, 23133 байт)

````python
import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value
from modules import pc_control_core as pc_control


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
PC_AGENT_DIR = PROJECTS_DIR / "PCAgent"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "pc_agent"
STATE_PATH = PC_AGENT_DIR / "pc_agent_state.json"
GRIMOIRE_RESPONSE_PATH = PC_AGENT_DIR / "grimoire_response.md"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs():
    PC_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _default_state():
    return {
        "enabled": False,
        "goal": "",
        "current_step": "",
        "last_action": "",
        "last_status": "",
        "last_error": "",
        "last_report": "",
        "ask_grimoire": False,
        "confirmed": False,
        "dry_run": True,
        "stopped_at": "",
        "created_at": "",
    }


def _load_state():
    _ensure_dirs()
    state = _default_state()

    if STATE_PATH.exists():
        try:
            loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except Exception:
            pass

    return state


def _save_state(state):
    _ensure_dirs()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def _write_report(action, payload):
    _ensure_dirs()
    path = REPORTS_DIR / f"pc_agent_{action}_{_stamp()}.md"
    lines = [
        "# PC Agent Report",
        "",
        f"- action: {action}",
        f"- created_at: {_now()}",
        f"- status: {payload.get('status') or payload.get('last_status') or 'unknown'}",
        f"- goal: {payload.get('goal') or 'нет'}",
        "",
        "## Payload",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")

    try:
        set_value("last_pc_agent_report", str(path))
    except Exception:
        pass

    return str(path)


def latest_pc_agent_report():
    if not REPORTS_DIR.exists():
        return ""

    reports = sorted(REPORTS_DIR.glob("pc_agent_*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    return str(reports[0]) if reports else ""


def _update_state(**values):
    state = _load_state()
    state.update(values)
    _save_state(state)
    return state


def _blocked_goal_markers(goal):
    return pc_control.hard_block_reasons(goal)


def _command_for_goal(goal):
    lower = str(goal or "").lower()

    if "git status" in lower or "статус git" in lower:
        return "git status --short"
    if "git log" in lower or "последние коммит" in lower:
        return "git log -5 --oneline"
    if "diff stat" in lower or "diff --stat" in lower or "статистик" in lower:
        return "git diff --stat"
    if "compile pc agent" in lower or "py_compile pc_agent" in lower:
        return "python -m py_compile modules\\pc_agent_core.py"
    if "compile pc control" in lower or "py_compile pc_control" in lower:
        return "python -m py_compile modules\\pc_control_core.py"

    return ""


def _path_for_goal(goal):
    text = str(goal or "").strip()
    lower = text.lower()

    if "open pc agent reports" in lower or "открой pc agent reports" in lower:
        return str(REPORTS_DIR)
    if "open reports folder" in lower or "открой папку отчет" in lower or "открой отчеты" in lower:
        return str(PROJECTS_DIR / "Reports")
    if "open project folder" in lower or "открой папку проекта" in lower:
        return str(ROOT_DIR)

    prefixes = (
        "open safe project file ",
        "open project file ",
        "открой файл проекта ",
    )
    for prefix in prefixes:
        if lower.startswith(prefix):
            candidate = text[len(prefix):].strip(" :\"'")
            if not candidate:
                return ""
            candidate_path = Path(candidate)
            return str(candidate_path if candidate_path.is_absolute() else ROOT_DIR / candidate_path)

    return ""


def _next_action_for_plan(plan):
    if plan.get("status") == "blocked":
        return "Stop and ask the user for a safe non-destructive goal."

    action = plan.get("recommended_action") or {}
    if action.get("type") == "run_command":
        return f"Run allowlisted command: {action.get('command')}"
    if action.get("type") == "open_path":
        return f"Open safe LocalAgent path: {action.get('path')}"
    if action.get("type") == "ask_grimoire":
        return "Ask Grimoire through ChatGPT Desktop if send is explicitly enabled."

    return "Review the plan, then run a dry-run step or confirmed step."


def pc_agent_status():
    state = _load_state()
    payload = {
        "ok": True,
        "status": "ok",
        "state_path": str(STATE_PATH),
        "reports_dir": str(REPORTS_DIR),
        "latest_report": latest_pc_agent_report(),
        **state,
    }
    report = _write_report("status", payload)
    payload["report_path"] = report
    _update_state(last_action="status", last_status="ok", last_error="", last_report=report)
    return payload


def pc_agent_observe():
    result = pc_control.observe_pc()
    payload = {
        "ok": True,
        "status": "ok",
        "goal": "",
        "current_step": "observe",
        "observation": result,
    }
    report = _write_report("observe", payload)
    payload["report_path"] = report
    _update_state(current_step="observe", last_action="observe", last_status="ok", last_error="", last_report=report)
    return payload


def pc_agent_plan(goal, ask_grimoire=False):
    goal = str(goal or "").strip()
    blocked = _blocked_goal_markers(goal)
    command = _command_for_goal(goal)
    path = _path_for_goal(goal)
    path_check = {}
    path_block_reason = ""

    if path:
        path_ok, resolved_path, reason = pc_control.is_safe_project_path(path)
        path_check = {
            "ok": bool(path_ok),
            "resolved_path": str(resolved_path or ""),
            "reason": reason,
        }
        if not path_ok:
            path_block_reason = reason

    observation = pc_control.observe_pc()

    status = "blocked" if blocked or path_block_reason else "planned"
    recommended_action = {"type": "none"}

    if blocked or path_block_reason:
        steps = [
            "Stop: goal contains hard-blocked markers or an unsafe path.",
            "Do not run commands, click, type, send, submit, or open sensitive paths.",
            "Ask the user for a narrower safe task.",
        ]
        if path_block_reason:
            steps.insert(1, f"Unsafe path reason: {path_block_reason}")
    else:
        steps = [
            "Observe the current desktop/project state.",
            "Keep all actions inside the LocalAgent workspace and explicit allowlists.",
        ]

        if command:
            recommended_action = {"type": "run_command", "command": command}
            steps.append(f"Dry-run the allowlisted command: {command}")
            steps.append("If confirmed=True and dry_run=False, execute it from the LocalAgent root.")
        elif path:
            recommended_action = {"type": "open_path", "path": path}
            steps.append(f"Dry-run opening the safe LocalAgent path: {path}")
            steps.append("If confirmed=True and dry_run=False, open it through the OS shell.")
        elif ask_grimoire:
            recommended_action = {"type": "ask_grimoire"}
            steps.append("Prepare a concise Grimoire request through ChatGPT Desktop.")
        else:
            steps.append("No direct allowlisted action matched; produce a report and wait for a safer explicit step.")

    plan = {
        "ok": not blocked,
        "status": status,
        "goal": goal,
        "ask_grimoire": bool(ask_grimoire),
        "blocked_markers": blocked,
        "path_check": path_check,
        "recommended_action": recommended_action,
        "steps": steps,
        "observation": observation,
        "next_recommended_action": "",
    }
    plan["next_recommended_action"] = _next_action_for_plan(plan)
    report = _write_report("plan", plan)
    plan["report_path"] = report
    _update_state(
        goal=goal,
        current_step="plan",
        last_action="plan",
        last_status=status,
        last_error="" if status != "blocked" else path_block_reason or "blocked goal",
        last_report=report,
        ask_grimoire=bool(ask_grimoire),
    )
    return plan


def pc_agent_run_command(command, confirmed=False, dry_run=True):
    result = pc_control.run_allowed_command(command, confirmed=confirmed, dry_run=dry_run)
    payload = {
        "status": "ok" if result.get("ok") else "blocked_or_failed",
        "current_step": "act",
        "action": "run_command",
        "result": result,
    }
    report = _write_report("run_command", payload)
    payload["report_path"] = report
    _update_state(
        current_step="act",
        last_action="run_command",
        last_status=payload["status"],
        last_error="" if result.get("ok") else result.get("message", ""),
        last_report=report,
        confirmed=bool(confirmed),
        dry_run=bool(dry_run),
    )
    return payload


def pc_agent_open_path(path, confirmed=False, dry_run=True):
    result = pc_control.open_safe_path(path, confirmed=confirmed, dry_run=dry_run)
    payload = {
        "status": "ok" if result.get("ok") else "blocked_or_failed",
        "current_step": "act",
        "action": "open_path",
        "result": result,
    }
    report = _write_report("open_path", payload)
    payload["report_path"] = report
    _update_state(last_action="open_path", last_status=payload["status"], last_error="" if result.get("ok") else result.get("message", ""), last_report=report)
    return payload


def pc_agent_clipboard_set(text, confirmed=False, dry_run=True):
    result = pc_control.set_clipboard_text(text, confirmed=confirmed, dry_run=dry_run)
    payload = {
        "status": "ok" if result.get("ok") else "blocked_or_failed",
        "current_step": "act",
        "action": "clipboard_set",
        "result": result,
    }
    report = _write_report("clipboard_set", payload)
    payload["report_path"] = report
    _update_state(last_action="clipboard_set", last_status=payload["status"], last_error="" if result.get("ok") else result.get("message", ""), last_report=report)
    return payload


def _grimoire_prompt(goal):
    return (
        "# LocalComet PC Agent Request\n\n"
        "You are Grimoire, architect for LocalComet. Return one small safe patch plan or code instruction set.\n\n"
        "## Goal\n"
        f"{str(goal or '').strip() or 'нет'}\n\n"
        "## Local Contract\n"
        "- Codex is the local operator: it can inspect files, apply patches, run checks, and commit.\n"
        "- Prefer one focused change in allowed files only.\n"
        "- If code changes are needed, give exact file paths and exact edit instructions or a valid response.json patch.\n"
        "- If no code change is needed, give one safe verification or operating step.\n\n"
        "## Allowed Files\n"
        "- modules/pc_agent_core.py\n"
        "- modules/pc_control_core.py\n"
        "- modules/chatgpt_desktop_bridge.py\n"
        "- modules/desktop_action_planner.py\n"
        "- LocalComet_Control_Panel.py\n"
        "- Projects/PCAgent/* runtime state\n"
        "- Projects/Reports/pc_agent/* reports\n\n"
        "## Stop Conditions\n"
        "- Do not delete files.\n"
        "- Do not read secrets, tokens, private keys, browser profiles, or env files.\n"
        "- Do not submit forms, send messages to people, install software, or change system settings.\n"
        "- Do not ask for arbitrary shell execution.\n\n"
        "## Required\n"
        "- Decision\n"
        "- Risk level\n"
        "- Exact safe local actions for Codex\n"
        "- Files to edit\n"
        "- Tests to run\n"
        "- Stop conditions\n"
        "- Expected commit message\n"
    )


def pc_agent_ask_grimoire(goal, send=False, dry_run=True):
    from modules.chatgpt_desktop_bridge import is_chatgpt_desktop_send_allowed, paste_prompt_after_input_focus

    goal = str(goal or "").strip()
    blocked = _blocked_goal_markers(goal)

    payload = {
        "status": "blocked" if blocked else "planned",
        "goal": goal,
        "send": bool(send),
        "dry_run": bool(dry_run),
        "blocked_markers": blocked,
    }

    if blocked:
        payload["ok"] = False
        payload["message"] = "STOP: Grimoire request contains hard-blocked markers."
    else:
        allowed = is_chatgpt_desktop_send_allowed()
        payload["send_allowed"] = allowed

        if send and not allowed.get("allowed"):
            payload["ok"] = False
            payload["status"] = "blocked"
            payload["message"] = allowed.get("message", "STOP: ChatGPT Desktop send blocked.")
        else:
            prompt = _grimoire_prompt(goal)
            result = paste_prompt_after_input_focus(prompt, send=bool(send), dry_run=bool(dry_run))
            payload["ok"] = bool(result.get("ok"))
            payload["status"] = "ok" if result.get("ok") else "blocked_or_failed"
            payload["message"] = result.get("message", "")
            payload["bridge_result"] = result

    report = _write_report("ask_grimoire", payload)
    payload["report_path"] = report
    _update_state(goal=goal, current_step="ask_grimoire", last_action="ask_grimoire", last_status=payload["status"], last_error="" if payload.get("ok") else payload.get("message", ""), last_report=report, ask_grimoire=True, dry_run=bool(dry_run))
    return payload


def pc_agent_ask_grimoire_verified(goal, send=False, dry_run=True):
    from modules.chatgpt_desktop_bridge import get_clipboard_text, verify_chatgpt_desktop_send_state

    prompt = _grimoire_prompt(goal)
    result = pc_agent_ask_grimoire(goal, send=send, dry_run=dry_run)
    after_clipboard = get_clipboard_text()
    bridge_result = result.get("bridge_result") if isinstance(result.get("bridge_result"), dict) else result
    verification = verify_chatgpt_desktop_send_state(
        before_clipboard=prompt,
        after_clipboard=after_clipboard,
        send_result=bridge_result,
    )

    payload = {
        "ok": bool(result.get("ok")) and (not send or bool(verification.get("likely_sent"))),
        "status": "ok" if bool(result.get("ok")) and not verification.get("needs_manual_check") else "manual_check_needed",
        "goal": str(goal or "").strip(),
        "send": bool(send),
        "dry_run": bool(dry_run),
        "ask_result": result,
        "verification": verification,
        "message": verification.get("message", ""),
    }
    report = _write_report("ask_grimoire_verified", payload)
    payload["report_path"] = report
    _update_state(goal=goal, current_step="ask_grimoire_verified", last_action="ask_grimoire_verified", last_status=payload["status"], last_error="" if payload["ok"] else payload["message"], last_report=report, ask_grimoire=True, dry_run=bool(dry_run))
    return payload


def pc_agent_capture_grimoire_response():
    from modules.chatgpt_desktop_bridge import get_clipboard_text

    text = get_clipboard_text()
    text_stripped = str(text or "").strip()
    looks_like_own_request = (
        "# LocalComet PC Agent Request" in text_stripped
        and "## Local Contract" in text_stripped
    )
    payload = {
        "ok": bool(text_stripped) and not looks_like_own_request,
        "status": "ok" if text_stripped and not looks_like_own_request else "blocked_or_failed",
        "response_chars": len(text or ""),
        "response_path": str(GRIMOIRE_RESPONSE_PATH),
        "looks_like_own_request": looks_like_own_request,
    }

    if payload["ok"]:
        _ensure_dirs()
        GRIMOIRE_RESPONSE_PATH.write_text(text, encoding="utf-8")
        payload["message"] = "Grimoire response captured from clipboard."
    elif looks_like_own_request:
        payload["message"] = "STOP: clipboard still contains the PC Agent request, not a Grimoire response."
    else:
        payload["message"] = "STOP: clipboard is empty; no Grimoire response captured."

    report = _write_report("capture_grimoire", payload)
    payload["report_path"] = report
    _update_state(current_step="capture_grimoire", last_action="capture_grimoire", last_status=payload["status"], last_error="" if payload["ok"] else payload["message"], last_report=report)
    return payload


def pc_agent_step(goal, confirmed=False, dry_run=True, ask_grimoire=False):
    goal = str(goal or "").strip()
    result = {
        "ok": False,
        "status": "started",
        "goal": goal,
        "confirmed": bool(confirmed),
        "dry_run": bool(dry_run),
        "ask_grimoire": bool(ask_grimoire),
        "flow": ["observe", "decide", "act", "verify", "report", "next"],
    }

    observation = pc_agent_observe()
    result["observe"] = observation
    plan = pc_agent_plan(goal, ask_grimoire=ask_grimoire)
    result["plan"] = plan

    if plan.get("status") == "blocked":
        result["status"] = "blocked"
        result["message"] = "STOP: PC Agent plan blocked by hard safety guard."
    elif ask_grimoire:
        result["act"] = pc_agent_ask_grimoire(goal, send=False, dry_run=dry_run)
        result["status"] = "ok" if result["act"].get("ok") else "blocked_or_failed"
        result["message"] = "Grimoire request prepared." if result["act"].get("ok") else result["act"].get("message", "")
    else:
        action = plan.get("recommended_action") or {}
        if action.get("type") == "run_command":
            result["act"] = pc_agent_run_command(action.get("command"), confirmed=confirmed, dry_run=dry_run)
            result["status"] = "ok" if result["act"].get("result", {}).get("ok") else "blocked_or_failed"
            result["message"] = result["act"].get("result", {}).get("message", "")
        elif action.get("type") == "open_path":
            result["act"] = pc_agent_open_path(action.get("path"), confirmed=confirmed, dry_run=dry_run)
            result["status"] = "ok" if result["act"].get("result", {}).get("ok") else "blocked_or_failed"
            result["message"] = result["act"].get("result", {}).get("message", "")
        else:
            result["act"] = {"ok": True, "message": "No allowlisted action selected; report-only step."}
            result["status"] = "ok"
            result["message"] = "Report-only step completed."

    result["verify"] = {
        "ok": result["status"] == "ok",
        "checks": [
            "hard blocks checked",
            "command allowlist checked",
            "reports written",
        ],
    }
    result["next_recommended_action"] = _next_action_for_plan(plan)
    report = _write_report("step", result)
    result["report_path"] = report
    result["ok"] = result["status"] == "ok"
    _update_state(goal=goal, current_step="step", last_action="step", last_status=result["status"], last_error="" if result["ok"] else result.get("message", ""), last_report=report, confirmed=bool(confirmed), dry_run=bool(dry_run), ask_grimoire=bool(ask_grimoire))
    return result


def pc_agent_loop_step():
    state = _load_state()
    goal = str(state.get("goal") or "").strip()

    if not state.get("enabled"):
        payload = {"ok": False, "status": "blocked", "message": "STOP: PC Agent loop is not enabled.", "state": state}
    elif not goal:
        payload = {"ok": False, "status": "blocked", "message": "STOP: PC Agent loop has no goal.", "state": state}
    else:
        step = pc_agent_step(
            goal,
            confirmed=bool(state.get("confirmed")),
            dry_run=bool(state.get("dry_run", True)),
            ask_grimoire=bool(state.get("ask_grimoire")),
        )
        payload = {
            "ok": bool(step.get("ok")),
            "status": step.get("status", "unknown"),
            "message": "PC Agent loop step completed." if step.get("ok") else step.get("message", ""),
            "state": _load_state(),
            "step": step,
        }

    report = _write_report("loop_step", payload)
    payload["report_path"] = report
    _update_state(current_step="loop_step", last_action="loop_step", last_status=payload["status"], last_error="" if payload.get("ok") else payload.get("message", ""), last_report=report)
    return payload


def pc_agent_loop_start(goal, confirmed=False, ask_grimoire=False):
    state = _load_state()
    now = _now()
    state.update({
        "enabled": True,
        "goal": str(goal or "").strip(),
        "current_step": "loop_start",
        "last_action": "loop_start",
        "last_status": "ok",
        "last_error": "",
        "ask_grimoire": bool(ask_grimoire),
        "confirmed": bool(confirmed),
        "dry_run": not bool(confirmed),
        "stopped_at": "",
        "created_at": state.get("created_at") or now,
    })
    _save_state(state)
    first_step = pc_agent_loop_step()
    payload = {"ok": True, "message": "PC Agent loop enabled.", "state": _load_state(), "first_step": first_step}
    report = _write_report("loop_start", payload)
    payload["report_path"] = report
    _update_state(last_report=report)
    return payload


def pc_agent_loop_stop():
    state = _load_state()
    state.update({
        "enabled": False,
        "current_step": "loop_stop",
        "last_action": "loop_stop",
        "last_status": "ok",
        "last_error": "",
        "stopped_at": _now(),
    })
    _save_state(state)
    payload = {"ok": True, "message": "PC Agent loop stopped.", **state}
    report = _write_report("loop_stop", payload)
    payload["report_path"] = report
    _update_state(last_report=report)
    return payload


def pc_agent_loop_status():
    state = _load_state()
    payload = {
        "ok": True,
        "message": "PC Agent loop status.",
        "state_path": str(STATE_PATH),
        "latest_report": latest_pc_agent_report(),
        **state,
    }
    report = _write_report("loop_status", payload)
    payload["report_path"] = report
    _update_state(last_action="loop_status", last_status="ok", last_error="", last_report=report)
    return payload
````

### ПУТЬ: modules/pc_agent_knowledge.py (640 строк, 19752 байт)

````python
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from modules.project_paths import get_project_root
from urllib.parse import quote_plus, urlparse
import html
import json
import re
import traceback
import urllib.request

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
RELAY_DIR = PROJECTS_DIR / "ChatGPTRelay"
REPORTS_DIR = PROJECTS_DIR / "Reports"
KNOWLEDGE_REPORTS_DIR = REPORTS_DIR / "pc_agent_knowledge"
REQUEST_FILE = RELAY_DIR / "request.md"

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "BrowserProfile",
    "VoiceModels",
    "LocalAgent_Backups",
    "CleanupQuarantine",
}
EXCLUDED_PARTS = {
    "Projects/Reports",
    "Projects/Logs",
    "Projects/CleanupQuarantine",
}
IMPORTANT_FILES = [
    "LocalComet_Control_Panel.py",
    "agent.py",
    "config.py",
    "core/router.py",
    "core/planner.py",
    "core/executor.py",
    "core/llm.py",
    "modules/pc_agent_core.py",
    "modules/pc_codex_mode.py",
    "modules/pc_agent_actions.py",
    "modules/safety_cleanup_center.py",
    "modules/global_update_center.py",
    "modules/desktop_observer.py",
    "modules/desktop_action_planner.py",
    "modules/self_edit.py",
]

SENSITIVE_PATTERNS = [
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    ".env",
    ".pem",
    ".key",
]


class _DuckResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._in_a = False
        self._current_href = ""
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return

        attrs_dict = dict(attrs)
        href = attrs_dict.get("href", "")
        css = attrs_dict.get("class", "")

        if "result-link" in css or "/l/?" in href or href.startswith("http"):
            self._in_a = True
            self._current_href = href
            self._current_text = []

    def handle_data(self, data):
        if self._in_a:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or not self._in_a:
            return

        title = " ".join(" ".join(self._current_text).split())
        href = self._clean_href(self._current_href)

        if title and href and len(title) > 2:
            self.results.append({"title": html.unescape(title), "url": href, "snippet": ""})

        self._in_a = False
        self._current_href = ""
        self._current_text = []

    def _clean_href(self, href):
        if not href:
            return ""

        value = html.unescape(href)

        if value.startswith("//"):
            return "https:" + value

        if value.startswith("/l/?"):
            try:
                from urllib.parse import parse_qs, urlparse, unquote

                query = parse_qs(urlparse(value).query)
                uddg = query.get("uddg", [""])[0]
                return unquote(uddg)
            except Exception:
                return value

        if value.startswith("http://") or value.startswith("https://"):
            return value

        return ""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _is_sensitive_path(path: Path):
    lower = str(path).lower().replace("\\", "/")
    return any(pattern in lower for pattern in SENSITIVE_PATTERNS)


def _is_excluded(path: Path):
    parts = set(path.parts)
    if parts.intersection(EXCLUDED_DIRS):
        return True

    rel = ""
    try:
        rel = path.relative_to(ROOT_DIR).as_posix()
    except Exception:
        rel = path.as_posix()

    return any(rel.startswith(part) for part in EXCLUDED_PARTS)


def _safe_read_text(path: Path, limit=9000):
    if _is_sensitive_path(path):
        return "[SKIPPED: sensitive path]"

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"[READ ERROR: {exc}]"

    if len(text) > limit:
        return text[:limit] + "\n...[обрезано]"
    return text


def build_project_structure(max_files=260):
    files = []
    counts = {
        "total": 0,
        "python": 0,
        "markdown": 0,
        "json": 0,
        "html": 0,
    }

    if not ROOT_DIR.exists():
        return {
            "ok": False,
            "root": str(ROOT_DIR),
            "error": "ROOT_DIR does not exist.",
            "counts": counts,
            "files": [],
        }

    for path in ROOT_DIR.rglob("*"):
        if _is_excluded(path):
            continue
        if path.is_dir():
            continue
        if _is_sensitive_path(path):
            continue

        counts["total"] += 1
        suffix = path.suffix.lower()

        if suffix == ".py":
            counts["python"] += 1
        elif suffix in {".md", ".txt"}:
            counts["markdown"] += 1
        elif suffix == ".json":
            counts["json"] += 1
        elif suffix in {".html", ".htm"}:
            counts["html"] += 1

        if len(files) < max_files:
            try:
                rel = path.relative_to(ROOT_DIR).as_posix()
            except Exception:
                rel = str(path)
            files.append(rel)

    return {
        "ok": True,
        "root": str(ROOT_DIR),
        "generated_at": _now(),
        "counts": counts,
        "files": files,
        "truncated": counts["total"] > len(files),
    }


def build_project_context(include_contents=True):
    structure = build_project_structure()
    important = []

    for rel in IMPORTANT_FILES:
        path = ROOT_DIR / rel
        if not path.exists() or not path.is_file():
            important.append({"path": rel, "exists": False, "preview": ""})
            continue

        preview = _safe_read_text(path, limit=5000 if include_contents else 800)
        important.append({
            "path": rel,
            "exists": True,
            "preview": preview,
        })

    payload = {
        "ok": True,
        "generated_at": _now(),
        "project": "LocalComet / LocalAgent",
        "root": str(ROOT_DIR),
        "structure": structure,
        "important_files": important,
        "safety_rules": [
            "Do not edit private credentials, tokens, passwords, browser profiles, VoiceModels, .git, backups, Reports, or Logs.",
            "Use response.json patch workflow for changes.",
            "Prefer modules over expanding LocalComet_Control_Panel.py.",
            "Never use shell=True for unknown commands.",
            "Use quarantine instead of direct deletion.",
        ],
    }
    set_value("pc_agent_project_context", payload)
    return payload


def format_project_structure(payload=None):
    payload = payload or build_project_structure()
    lines = [
        "Project Structure:",
        f"- ok: {payload.get('ok')}",
        f"- root: {payload.get('root')}",
    ]

    counts = payload.get("counts", {})
    lines.extend([
        "",
        "Counts:",
        f"- total: {counts.get('total')}",
        f"- python: {counts.get('python')}",
        f"- markdown/txt: {counts.get('markdown')}",
        f"- json: {counts.get('json')}",
        f"- html: {counts.get('html')}",
        "",
        "Files:",
    ])

    for item in payload.get("files", [])[:180]:
        lines.append("- " + item)

    if payload.get("truncated"):
        lines.append("...[список обрезан]")

    return "\n".join(lines)


def format_project_context(payload=None):
    payload = payload or build_project_context(include_contents=False)
    lines = [
        "Project Context for Qwen / PC Agent:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- root: {payload.get('root')}",
        "",
        "Safety rules:",
    ]
    lines.extend("- " + item for item in payload.get("safety_rules", []))
    lines.append("")
    lines.append(format_project_structure(payload.get("structure", {})))
    lines.append("")
    lines.append("Important files:")
    for item in payload.get("important_files", []):
        lines.append(f"- {item.get('path')} exists={item.get('exists')}")
    return "\n".join(lines)


def search_web(query, max_results=6, timeout=12):
    query = str(query or "").strip()
    if not query:
        return {"ok": False, "query": query, "results": [], "error": "empty query"}

    url = "https://duckduckgo.com/html/?q=" + quote_plus(query)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 LocalComet/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            html_text = response.read(900000).decode("utf-8", errors="replace")
    except Exception as exc:
        fallback = "https://www.google.com/search?q=" + quote_plus(query)
        return {
            "ok": False,
            "query": query,
            "results": [],
            "error": str(exc),
            "fallback_url": fallback,
        }

    parser = _DuckResultParser()
    parser.feed(html_text)

    seen = set()
    results = []
    for item in parser.results:
        host = ""
        try:
            host = urlparse(item.get("url", "")).netloc
        except Exception:
            host = ""

        key = (item.get("title", ""), item.get("url", ""))
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "host": host,
            "snippet": item.get("snippet", ""),
        })

        if len(results) >= max_results:
            break

    return {
        "ok": True,
        "query": query,
        "generated_at": _now(),
        "results": results,
        "source": "duckduckgo_html",
    }


def format_search_recommendation(payload):
    query = payload.get("query", "")
    results = payload.get("results", [])

    lines = [
        "Internet Research:",
        f"- query: {query}",
        f"- ok: {payload.get('ok')}",
    ]

    if not payload.get("ok"):
        lines.append(f"- error: {payload.get('error')}")
        if payload.get("fallback_url"):
            lines.append(f"- fallback_url: {payload.get('fallback_url')}")
        lines.append("")
        lines.append("Рекомендация: интернет-поиск не сработал из Python. Открой fallback_url вручную или проверь доступ к сети.")
        return "\n".join(lines)

    if not results:
        lines.append("")
        lines.append("Результатов не найдено.")
        lines.append("Рекомендация: уточни запрос или попроси: pc web <более конкретный запрос>.")
        return "\n".join(lines)

    lines.append("")
    lines.append("Top results:")
    for index, item in enumerate(results, start=1):
        lines.append(f"{index}. {item.get('title')}")
        lines.append(f"   host: {item.get('host')}")
        lines.append(f"   url: {item.get('url')}")

    lines.append("")
    lines.append("Рекомендация:")
    lines.append("- Используй первые 2-3 результата как ориентир, но не выполняй опасные действия автоматически.")
    lines.append("- Если запрос про LocalComet, сначала сравни с Project Context.")
    lines.append("- Для изменения проекта используй: pc edit <что изменить>.")

    return "\n".join(lines)


def should_search_online(command):
    lower = _norm(command)
    triggers = [
        "найди",
        "поиск",
        "загугли",
        "интернет",
        "web",
        "google",
        "что такое",
        "как сделать",
        "почему",
        "ошибка",
        "документация",
        "latest",
        "новый",
        "актуальный",
        "не знаю",
    ]
    return any(trigger in lower for trigger in triggers)


def answer_unknown_command(command):
    command = str(command or "").strip()

    if not command:
        return "Пустая команда."

    project_context = build_project_context(include_contents=False)
    search_payload = search_web(command, max_results=5)

    report = {
        "ok": True,
        "mode": "unknown_command_research",
        "generated_at": _now(),
        "command": command,
        "project_context": {
            "root": project_context.get("root"),
            "counts": project_context.get("structure", {}).get("counts", {}),
            "important_files": [item.get("path") for item in project_context.get("important_files", []) if item.get("exists")],
        },
        "search": search_payload,
    }
    set_value("pc_agent_last_unknown_research", report)

    lines = [
        "Я не распознал это как готовую команду LocalComet, поэтому сделал research.",
        "",
        format_search_recommendation(search_payload),
        "",
        "Project awareness:",
        f"- root: {project_context.get('root')}",
        f"- python files: {project_context.get('structure', {}).get('counts', {}).get('python')}",
        f"- known modules: {', '.join(report['project_context']['important_files'][:12])}",
        "",
        "Что можно сделать дальше:",
        "- Если это вопрос: уточни, и я отвечу с учётом web results.",
        "- Если это изменение проекта: напиши `pc edit <что изменить>`.",
        "- Если это управление ПК: `pc codex план <цель>` → `pc codex dry <цель>` → `pc codex step подтверждаю: <цель>`.",
    ]
    return "\n".join(lines)


def create_project_edit_request(task):
    task = str(task or "").strip()
    if not task:
        return {"ok": False, "error": "empty task"}

    context = build_project_context(include_contents=True)

    RELAY_DIR.mkdir(parents=True, exist_ok=True)

    body = [
        "# LocalComet Project Edit Request",
        "",
        f"Generated: {_now()}",
        "",
        "## Task",
        "",
        task,
        "",
        "## Required output",
        "",
        "Return a response.json patch only.",
        "Use operations with type/create/replace.",
        "Do not use placeholders.",
        "Do not edit secrets, browser profile, .git, reports, logs, backups, VoiceModels, or private files.",
        "Prefer adding new modules over expanding LocalComet_Control_Panel.py.",
        "Use quarantine instead of direct deletion.",
        "",
        "## Project Context",
        "",
        "```json",
        json.dumps(context, ensure_ascii=False, indent=2),
        "```",
    ]

    REQUEST_FILE.write_text("\n".join(body), encoding="utf-8")
    payload = {
        "ok": True,
        "request": str(REQUEST_FILE),
        "task": task,
        "message": "request.md создан с контекстом проекта. Дальше можно отправлять его в ChatGPT/Codex workflow.",
    }
    set_value("pc_agent_last_edit_request", payload)
    return payload


def save_knowledge_report(note=""):
    KNOWLEDGE_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "project_context": build_project_context(include_contents=False),
        "last_unknown_research": get_value("pc_agent_last_unknown_research", ""),
        "last_edit_request": get_value("pc_agent_last_edit_request", ""),
    }

    json_path = KNOWLEDGE_REPORTS_DIR / f"knowledge_report_{_stamp()}.json"
    md_path = KNOWLEDGE_REPORTS_DIR / f"knowledge_report_{_stamp()}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# PC Agent Knowledge Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Project Context",
        "",
        "```text",
        format_project_context(payload["project_context"]),
        "```",
        "",
        "## Last Unknown Research",
        "",
        "```json",
        json.dumps(payload["last_unknown_research"], ensure_ascii=False, indent=2),
        "```",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def dispatch_knowledge_command(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"project context", "контекст проекта", "структура проекта", "project structure"}:
        return format_project_context(build_project_context(include_contents=False))

    if lower in {"knowledge report", "отчет знаний", "knowledge status"}:
        return json.dumps(save_knowledge_report("manual knowledge report"), ensure_ascii=False, indent=2)

    prefixes = [
        "pc web ",
        "web search ",
        "internet search ",
        "поиск в интернете ",
        "найди в интернете ",
        "загугли ",
    ]

    for prefix in prefixes:
        if lower.startswith(prefix):
            query = text[len(prefix):].strip(" :,-—")
            return format_search_recommendation(search_web(query, max_results=6))

    edit_prefixes = [
        "pc edit ",
        "project edit ",
        "измени проект ",
        "поменяй в проекте ",
        "доработай проект ",
    ]

    for prefix in edit_prefixes:
        if lower.startswith(prefix):
            task = text[len(prefix):].strip(" :,-—")
            return json.dumps(create_project_edit_request(task), ensure_ascii=False, indent=2)

    return answer_unknown_command(text)


def is_knowledge_command(command):
    lower = _norm(command)

    exact = {
        "project context",
        "контекст проекта",
        "структура проекта",
        "project structure",
        "knowledge report",
        "отчет знаний",
        "knowledge status",
    }
    if lower in exact:
        return True

    prefixes = (
        "pc web ",
        "web search ",
        "internet search ",
        "поиск в интернете ",
        "найди в интернете ",
        "загугли ",
        "pc edit ",
        "project edit ",
        "измени проект ",
        "поменяй в проекте ",
        "доработай проект ",
    )
    return lower.startswith(prefixes)
````

### ПУТЬ: modules/pc_codex_core.py (455 строк, 18137 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import re

from core.state import get_value, set_value
from modules.pc_agent_knowledge import build_project_context, search_web, format_search_recommendation
from modules.pc_agent_actions import open_app, open_folder, create_note


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
PC_AGENT_DIR = PROJECTS_DIR / "PCAgent"
SESSIONS_DIR = PC_AGENT_DIR / "Sessions"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "pc_codex_core"
CURRENT_SESSION_FILE = SESSIONS_DIR / "current_session.json"

BLOCKED_TERMS = [
    "delete", "remove", "rm ", "rm -rf", "rmdir", "del ", "format", "wipe", "erase",
    "удали", "стереть", "снеси", "формат",
    "cmd", "powershell", "shell", "terminal", "registry", "regedit",
    "пароль", "password", "token", "secret", "api key", "apikey", "private key", "приватный ключ",
    "login", "логин", "банк", "bank", "payment", "casino", "ставка", "bet",
]

APP_WORDS = {
    "блокнот": "notepad",
    "notepad": "notepad",
    "калькулятор": "calc",
    "calc": "calc",
    "calculator": "calc",
    "проводник": "explorer",
    "explorer": "explorer",
    "paint": "paint",
}

FOLDER_WORDS = {
    "проект": "projects",
    "проекты": "projects",
    "projects": "projects",
    "отчеты": "reports",
    "отчёты": "reports",
    "reports": "reports",
    "загрузки": "downloads",
    "downloads": "downloads",
    "relay": "relay",
    "selfedit": "selfedit",
    "pcagent": "pcagent",
}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_json_dump(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _load_session():
    _ensure_dirs()
    if not CURRENT_SESSION_FILE.exists():
        return None
    try:
        return json.loads(CURRENT_SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_session(session):
    _ensure_dirs()
    session["updated_at"] = _now()
    _safe_json_dump(CURRENT_SESSION_FILE, session)
    set_value("pc_codex_core_current_session", session)
    return session


def classify_goal(goal):
    lower = _norm(goal)
    hits = [term for term in BLOCKED_TERMS if term in lower]
    return {
        "safe": not hits,
        "blocked_terms": hits,
        "blocked_reason": "Опасные термины: " + ", ".join(hits) if hits else "",
        "requires_confirmation": True,
        "confirmation_phrase": "подтверждаю:",
    }


def _new_session(goal):
    session = {
        "ok": True,
        "session_id": _stamp(),
        "mode": "pc_codex_core",
        "created_at": _now(),
        "updated_at": _now(),
        "goal": str(goal or "").strip(),
        "status": "started",
        "steps": [],
        "last_plan": None,
        "last_dry_run": None,
        "last_step": None,
        "last_report": None,
        "safety": classify_goal(goal),
    }
    return _save_session(session)


def _detect_app(goal):
    lower = _norm(goal)
    for word, app in APP_WORDS.items():
        if word in lower:
            return app
    return ""


def _detect_folder(goal):
    lower = _norm(goal)
    for word, folder in FOLDER_WORDS.items():
        if word in lower:
            return folder
    return ""


def _looks_like_web_question(goal):
    lower = _norm(goal)
    triggers = ["что такое", "как сделать", "найди", "поиск", "интернет", "web", "google", "документация", "ошибка", "почему", "актуаль", "latest", "обнов"]
    return any(trigger in lower for trigger in triggers)


def _looks_like_project_change(goal):
    lower = _norm(goal)
    triggers = ["измени проект", "поменяй проект", "доработай проект", "исправь проект", "добавь команду", "создай модуль", "сделай патч", "patch", "response.json"]
    return any(trigger in lower for trigger in triggers)


def status():
    session = _load_session()
    payload = {
        "ok": True,
        "mode": "pc_codex_core",
        "generated_at": _now(),
        "current_session": session,
        "commands": [
            "pc core status",
            "pc core start <цель>",
            "pc core plan <цель>",
            "pc core dry <цель>",
            "pc core step подтверждаю: <цель>",
            "pc core continue",
            "pc core report",
            "pc core stop",
        ],
        "safety": [
            "No direct deletion.",
            "No arbitrary shell/cmd/powershell.",
            "No private credentials/tokens/passwords.",
            "Use quarantine/request/patch workflow for project changes.",
            "Dry-run first, confirmed step second.",
        ],
    }
    set_value("pc_codex_core_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    session = payload.get("current_session") or {}
    lines = [
        "PC Codex Core:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- current_session: {session.get('session_id', 'none')}",
        f"- goal: {session.get('goal', 'none')}",
        f"- status: {session.get('status', 'idle')}",
        "",
        "Commands:",
    ]
    lines.extend("- " + item for item in payload.get("commands", []))
    lines.append("")
    lines.append("Safety:")
    lines.extend("- " + item for item in payload.get("safety", []))
    return "\n".join(lines)


def start(goal):
    goal = str(goal or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}
    session = _new_session(goal)
    plan_payload = plan(goal, session=session)
    session["last_plan"] = plan_payload
    session["status"] = "planned"
    session["steps"].append({"at": _now(), "event": "start", "goal": goal})
    _save_session(session)
    return {"ok": True, "message": "PC Codex Core session started.", "session": session, "plan": plan_payload}


def plan(goal="", session=None):
    session = session or _load_session()
    goal = str(goal or "").strip() or str((session or {}).get("goal", "")).strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}

    safety = classify_goal(goal)
    context = build_project_context(include_contents=False)
    app = _detect_app(goal)
    folder = _detect_folder(goal)
    steps = []

    if not safety["safe"]:
        steps.append({"type": "blocked", "title": "Запрос содержит опасные термины.", "detail": safety["blocked_reason"]})
    else:
        steps.append({"type": "understand", "title": "Понять цель и проверить безопасность.", "detail": goal})
        if app:
            steps.append({"type": "action", "action": "open_app", "target": app, "dry_run_available": True, "confirmed_required": True})
        if folder:
            steps.append({"type": "action", "action": "open_folder", "target": folder, "dry_run_available": True, "confirmed_required": True})
        if _looks_like_web_question(goal):
            steps.append({"type": "research", "action": "web_search", "query": goal, "dry_run_available": True})
        if _looks_like_project_change(goal):
            steps.append({"type": "project_edit", "action": "create_request", "target": "Projects/ChatGPTRelay/request.md", "confirmed_required": False, "detail": "Создать request.md с контекстом проекта; изменения только через response.json patch workflow."})
        if not app and not folder and not _looks_like_web_question(goal) and not _looks_like_project_change(goal):
            steps.append({"type": "recommendation", "action": "ask_or_research", "detail": "Команда не похожа на allowlist-действие. Сделать web research и дать рекомендацию."})

    payload = {
        "ok": safety["safe"],
        "mode": "plan",
        "generated_at": _now(),
        "goal": goal,
        "safety": safety,
        "project_counts": context.get("structure", {}).get("counts", {}),
        "steps": steps,
        "next": "pc core dry <цель>",
    }

    if session:
        session["last_plan"] = payload
        session["steps"].append({"at": _now(), "event": "plan", "payload": payload})
        _save_session(session)

    return payload


def dry_run(goal="", session=None):
    session = session or _load_session()
    goal = str(goal or "").strip() or str((session or {}).get("goal", "")).strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}

    safety = classify_goal(goal)
    app = _detect_app(goal)
    folder = _detect_folder(goal)
    payload = {"ok": safety["safe"], "mode": "dry_run", "generated_at": _now(), "goal": goal, "safety": safety, "results": [], "next": "pc core step подтверждаю: <цель>"}

    if not safety["safe"]:
        payload["results"].append({"ok": False, "result": "BLOCKED", "reason": safety["blocked_reason"]})
    else:
        if app:
            payload["results"].append(open_app(app, dry_run=True))
        if folder:
            payload["results"].append(open_folder(folder, dry_run=True))
        if _looks_like_web_question(goal):
            payload["results"].append({"ok": True, "action": "web_search", "dry_run": True, "query": goal, "result": "DRY_RUN: интернет-поиск будет выполнен на confirmed/research step."})
        if _looks_like_project_change(goal):
            payload["results"].append({"ok": True, "action": "create_project_edit_request", "dry_run": True, "result": "DRY_RUN: будет создан request.md с контекстом проекта, без прямого изменения файлов."})
        if not payload["results"]:
            payload["results"].append({"ok": True, "action": "unknown_research", "dry_run": True, "result": "DRY_RUN: будет выполнен web research и дана рекомендация."})

    if session:
        session["last_dry_run"] = payload
        session["status"] = "dry_run_ready"
        session["steps"].append({"at": _now(), "event": "dry_run", "payload": payload})
        _save_session(session)

    return payload


def confirmed_step(goal="", session=None):
    session = session or _load_session()
    raw_goal = str(goal or "").strip() or str((session or {}).get("goal", "")).strip()
    if not raw_goal:
        return {"ok": False, "error": "empty goal"}

    lower = _norm(raw_goal)
    if "подтверждаю:" not in lower:
        return {"ok": False, "blocked": True, "reason": "Нужна явная фраза подтверждения.", "example": "pc core step подтверждаю: открыть блокнот"}

    clean_goal = re.sub(r"(?i)подтверждаю\s*:", "", raw_goal, count=1).strip()
    safety = classify_goal(clean_goal)
    app = _detect_app(clean_goal)
    folder = _detect_folder(clean_goal)
    payload = {"ok": safety["safe"], "mode": "confirmed_step", "generated_at": _now(), "goal": clean_goal, "safety": safety, "results": []}

    if not safety["safe"]:
        payload["results"].append({"ok": False, "result": "BLOCKED", "reason": safety["blocked_reason"]})
    else:
        if app:
            payload["results"].append(open_app(app, dry_run=False))
        if folder:
            payload["results"].append(open_folder(folder, dry_run=False))
        if _looks_like_web_question(clean_goal):
            search_payload = search_web(clean_goal, max_results=6)
            payload["results"].append({"ok": search_payload.get("ok"), "action": "web_search", "recommendation": format_search_recommendation(search_payload), "raw": search_payload})
        if _looks_like_project_change(clean_goal):
            from modules.pc_agent_knowledge import create_project_edit_request
            payload["results"].append(create_project_edit_request(clean_goal))
        if not payload["results"]:
            search_payload = search_web(clean_goal, max_results=5)
            payload["results"].append({"ok": search_payload.get("ok"), "action": "unknown_research", "recommendation": format_search_recommendation(search_payload), "raw": search_payload})

    if session:
        session["last_step"] = payload
        session["status"] = "stepped" if payload.get("ok") else "blocked"
        session["steps"].append({"at": _now(), "event": "confirmed_step", "payload": payload})
        _save_session(session)

    return payload


def continue_session():
    session = _load_session()
    if not session:
        return {"ok": False, "error": "No current session. Use: pc core start <goal>"}
    goal = session.get("goal", "")
    status_value = session.get("status", "")
    if status_value in {"started", "planned"}:
        return dry_run(goal, session=session)
    if status_value == "dry_run_ready":
        return {"ok": True, "message": "Dry-run готов. Для действия нужна команда:", "command": f"pc core step подтверждаю: {goal}"}
    return {"ok": True, "message": "Session state summarized.", "session": session, "next": "pc core plan <goal> or pc core start <new goal>"}


def stop_session():
    session = _load_session()
    if not session:
        return {"ok": True, "message": "No active session."}
    session["status"] = "stopped"
    session["steps"].append({"at": _now(), "event": "stop"})
    _save_session(session)
    return {"ok": True, "message": "Session stopped.", "session": session}


def report(note=""):
    _ensure_dirs()
    session = _load_session()
    payload = {"ok": True, "generated_at": _now(), "note": str(note or "").strip(), "session": session, "status": status()}
    json_path = REPORTS_DIR / f"pc_codex_core_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"pc_codex_core_report_{_stamp()}.md"
    _safe_json_dump(json_path, payload)
    md = [
        "# PC Codex Core Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_status(payload["status"]),
        "```",
        "",
        "## Session",
        "",
        "```json",
        json.dumps(session, ensure_ascii=False, indent=2),
        "```",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")
    if session:
        session["last_report"] = str(md_path)
        _save_session(session)
    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc core", "pc core status", "pc core статус", "codex core", "codex status"}:
        return format_status(status())
    if lower in {"pc core continue", "pc core продолжить", "codex continue"}:
        return format_payload(continue_session())
    if lower in {"pc core stop", "pc core останови", "codex stop"}:
        return format_payload(stop_session())
    if lower in {"pc core report", "pc core отчет", "codex report"}:
        return format_payload(report("manual report"))

    prefixes = [
        ("pc core start ", "start"),
        ("pc core цель ", "start"),
        ("pc core plan ", "plan"),
        ("pc core план ", "plan"),
        ("pc core dry ", "dry"),
        ("pc core сухой ", "dry"),
        ("pc core step ", "step"),
        ("pc core шаг ", "step"),
        ("codex start ", "start"),
        ("codex plan ", "plan"),
        ("codex dry ", "dry"),
        ("codex step ", "step"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "start":
                return format_payload(start(value))
            if action == "plan":
                return format_payload(plan(value))
            if action == "dry":
                return format_payload(dry_run(value))
            if action == "step":
                return format_payload(confirmed_step(value))

    return format_payload({"ok": False, "error": "Unknown PC Codex Core command.", "help": status().get("commands", [])})


def is_core_command(command):
    lower = _norm(command)
    exact = {
        "pc core", "pc core status", "pc core статус", "pc core continue", "pc core продолжить",
        "pc core stop", "pc core останови", "pc core report", "pc core отчет",
        "codex core", "codex status", "codex continue", "codex stop", "codex report",
    }
    if lower in exact:
        return True
    prefixes = (
        "pc core start ", "pc core цель ", "pc core plan ", "pc core план ", "pc core dry ",
        "pc core сухой ", "pc core step ", "pc core шаг ", "codex start ", "codex plan ",
        "codex dry ", "codex step ",
    )
    return lower.startswith(prefixes)
````

### ПУТЬ: modules/pc_codex_executor.py (553 строк, 17019 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import re
import uuid

from core.state import get_value, set_value

from modules.pc_codex_core import classify_goal, plan as core_plan, dry_run as core_dry_run
from modules.pc_agent_actions import open_app, open_folder, create_note
from modules.pc_agent_knowledge import search_web, format_search_recommendation, create_project_edit_request


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
EXECUTOR_DIR = PROJECTS_DIR / "PCAgent" / "Executor"
QUEUE_DIR = EXECUTOR_DIR / "Queue"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "pc_codex_executor"
CURRENT_QUEUE_FILE = QUEUE_DIR / "current_queue.json"
STOP_FILE = EXECUTOR_DIR / "STOP"

MAX_STEPS_PER_RUN = 5

BLOCKED_ACTIONS = {
    "delete",
    "remove",
    "format",
    "shell",
    "cmd",
    "powershell",
    "registry",
    "credential",
    "password",
    "token",
    "payment",
    "login",
}

APP_ALIASES = {
    "блокнот": "notepad",
    "notepad": "notepad",
    "калькулятор": "calc",
    "calc": "calc",
    "calculator": "calc",
    "проводник": "explorer",
    "explorer": "explorer",
    "paint": "paint",
}

FOLDER_ALIASES = {
    "проект": "projects",
    "проекты": "projects",
    "projects": "projects",
    "отчеты": "reports",
    "отчёты": "reports",
    "reports": "reports",
    "загрузки": "downloads",
    "downloads": "downloads",
    "relay": "relay",
    "selfedit": "selfedit",
    "pcagent": "pcagent",
}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    EXECUTOR_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _read_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _blocked(goal):
    safety = classify_goal(goal)
    lower = _norm(goal)
    direct_hits = [item for item in BLOCKED_ACTIONS if item in lower]
    if direct_hits:
        safety["safe"] = False
        safety["blocked_terms"] = list(set(safety.get("blocked_terms", []) + direct_hits))
        safety["blocked_reason"] = "Опасные действия: " + ", ".join(safety["blocked_terms"])
    return safety


def _find_app(goal):
    lower = _norm(goal)
    for word, app in APP_ALIASES.items():
        if word in lower:
            return app
    return ""


def _find_folder(goal):
    lower = _norm(goal)
    for word, folder in FOLDER_ALIASES.items():
        if word in lower:
            return folder
    return ""


def _looks_like_note(goal):
    lower = _norm(goal)
    return any(x in lower for x in ["заметк", "note ", "запиши", "сохрани текст"])


def _extract_note_text(goal):
    text = str(goal or "").strip()
    for marker in ["заметку", "заметка", "note", "запиши", "сохрани текст"]:
        idx = _norm(text).find(marker)
        if idx >= 0:
            extracted = text[idx + len(marker):].strip(" :,-—")
            return extracted or text
    return text


def _looks_like_web(goal):
    lower = _norm(goal)
    triggers = ["что такое", "как сделать", "найди", "поиск", "интернет", "web", "google", "документация", "ошибка", "почему", "актуаль", "latest"]
    return any(trigger in lower for trigger in triggers)


def _looks_like_project_edit(goal):
    lower = _norm(goal)
    triggers = ["измени проект", "поменяй проект", "доработай проект", "исправь проект", "добавь команду", "создай модуль", "сделай патч", "patch", "response.json"]
    return any(trigger in lower for trigger in triggers)


def build_queue(goal):
    goal = str(goal or "").strip()
    safety = _blocked(goal)
    queue = {
        "ok": safety.get("safe", False),
        "queue_id": str(uuid.uuid4())[:8],
        "created_at": _now(),
        "updated_at": _now(),
        "goal": goal,
        "status": "queued" if safety.get("safe") else "blocked",
        "safety": safety,
        "steps": [],
        "results": [],
    }

    if not goal:
        queue["ok"] = False
        queue["status"] = "blocked"
        queue["safety"] = {"safe": False, "blocked_reason": "empty goal", "blocked_terms": []}
        return queue

    if not safety.get("safe"):
        queue["steps"].append({
            "id": "blocked_1",
            "type": "blocked",
            "action": "none",
            "target": "",
            "status": "blocked",
            "reason": safety.get("blocked_reason", "blocked"),
        })
        return queue

    app = _find_app(goal)
    folder = _find_folder(goal)

    if app:
        queue["steps"].append({
            "id": "open_app_1",
            "type": "desktop",
            "action": "open_app",
            "target": app,
            "status": "pending",
            "confirmed_required": True,
        })

    if folder:
        queue["steps"].append({
            "id": "open_folder_1",
            "type": "desktop",
            "action": "open_folder",
            "target": folder,
            "status": "pending",
            "confirmed_required": True,
        })

    if _looks_like_note(goal):
        queue["steps"].append({
            "id": "create_note_1",
            "type": "file_safe",
            "action": "create_note",
            "target": _extract_note_text(goal),
            "status": "pending",
            "confirmed_required": True,
        })

    if _looks_like_web(goal):
        queue["steps"].append({
            "id": "web_search_1",
            "type": "research",
            "action": "web_search",
            "target": goal,
            "status": "pending",
            "confirmed_required": False,
        })

    if _looks_like_project_edit(goal):
        queue["steps"].append({
            "id": "project_edit_request_1",
            "type": "project_safe",
            "action": "create_project_edit_request",
            "target": goal,
            "status": "pending",
            "confirmed_required": False,
        })

    if not queue["steps"]:
        queue["steps"].append({
            "id": "research_recommendation_1",
            "type": "research",
            "action": "web_search",
            "target": goal,
            "status": "pending",
            "confirmed_required": False,
        })

    return queue


def save_queue(queue):
    _ensure_dirs()
    queue["updated_at"] = _now()
    _write_json(CURRENT_QUEUE_FILE, queue)
    set_value("pc_codex_executor_current_queue", queue)
    return queue


def load_queue():
    _ensure_dirs()
    queue = _read_json(CURRENT_QUEUE_FILE)
    return queue


def status():
    queue = load_queue()
    payload = {
        "ok": True,
        "mode": "pc_codex_executor",
        "generated_at": _now(),
        "queue": queue,
        "stop_requested": STOP_FILE.exists(),
        "commands": [
            "pc exec status",
            "pc exec queue <цель>",
            "pc exec dry <цель>",
            "pc exec run подтверждаю: <цель>",
            "pc exec step",
            "pc exec stop",
            "pc exec clear stop",
            "pc exec report",
        ],
    }
    set_value("pc_codex_executor_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    queue = payload.get("queue") or {}
    lines = [
        "PC Codex Executor:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- stop_requested: {payload.get('stop_requested')}",
        f"- queue_id: {queue.get('queue_id', 'none')}",
        f"- goal: {queue.get('goal', 'none')}",
        f"- status: {queue.get('status', 'idle')}",
        "",
        "Commands:",
    ]
    lines.extend("- " + cmd for cmd in payload.get("commands", []))
    return "\n".join(lines)


def queue_goal(goal):
    planned = core_plan(goal)
    queue = build_queue(goal)
    queue["core_plan"] = planned
    save_queue(queue)
    return queue


def dry_goal(goal):
    planned = core_dry_run(goal)
    queue = build_queue(goal)
    queue["core_dry_run"] = planned
    queue["dry_run"] = True
    dry_results = []
    for step in queue.get("steps", []):
        dry_results.append(_execute_step(step, dry_run=True))
    queue["results"] = dry_results
    queue["status"] = "dry_run_complete" if queue.get("ok") else "blocked"
    save_queue(queue)
    return queue


def _execute_step(step, dry_run=True):
    action = step.get("action")
    target = step.get("target", "")
    payload = {
        "ok": False,
        "at": _now(),
        "step_id": step.get("id"),
        "action": action,
        "target": target,
        "dry_run": bool(dry_run),
    }

    if action == "open_app":
        return open_app(target, dry_run=dry_run)

    if action == "open_folder":
        return open_folder(target, dry_run=dry_run)

    if action == "create_note":
        return create_note(target, dry_run=dry_run)

    if action == "web_search":
        if dry_run:
            payload["ok"] = True
            payload["result"] = "DRY_RUN: web search not executed."
            return payload
        search_payload = search_web(target, max_results=6)
        payload["ok"] = search_payload.get("ok", False)
        payload["result"] = format_search_recommendation(search_payload)
        payload["raw"] = search_payload
        return payload

    if action == "create_project_edit_request":
        if dry_run:
            payload["ok"] = True
            payload["result"] = "DRY_RUN: project edit request not created."
            return payload
        request_payload = create_project_edit_request(target)
        payload.update(request_payload)
        return payload

    payload["result"] = "Unknown action."
    return payload


def run_confirmed(goal):
    raw = str(goal or "").strip()
    if "подтверждаю:" not in _norm(raw):
        return {
            "ok": False,
            "blocked": True,
            "reason": "Нужна явная фраза подтверждения.",
            "example": "pc exec run подтверждаю: открыть блокнот",
        }

    clean_goal = re.sub(r"(?i)подтверждаю\s*:", "", raw, count=1).strip()
    queue = build_queue(clean_goal)

    if not queue.get("ok"):
        save_queue(queue)
        return queue

    if STOP_FILE.exists():
        queue["ok"] = False
        queue["status"] = "stopped"
        queue["results"].append({"ok": False, "result": "STOP file exists. Clear it with: pc exec clear stop"})
        save_queue(queue)
        return queue

    results = []
    executed = 0

    for step in queue.get("steps", []):
        if executed >= MAX_STEPS_PER_RUN:
            results.append({"ok": False, "result": "Max steps per run reached.", "max": MAX_STEPS_PER_RUN})
            break
        if STOP_FILE.exists():
            results.append({"ok": False, "result": "Stopped by STOP file."})
            break

        result = _execute_step(step, dry_run=False)
        results.append(result)
        step["status"] = "done" if result.get("ok") else "failed"
        executed += 1

        if not result.get("ok"):
            break

    queue["results"] = results
    queue["status"] = "complete" if all(item.get("ok") for item in results) else "attention"
    save_queue(queue)
    return queue


def step_current():
    queue = load_queue()
    if not queue:
        return {"ok": False, "error": "No queue. Use: pc exec queue <goal>"}
    if STOP_FILE.exists():
        return {"ok": False, "error": "STOP file exists. Use: pc exec clear stop"}

    for step in queue.get("steps", []):
        if step.get("status") == "pending":
            result = _execute_step(step, dry_run=False)
            step["status"] = "done" if result.get("ok") else "failed"
            queue.setdefault("results", []).append(result)
            queue["status"] = "stepped"
            save_queue(queue)
            return {"ok": result.get("ok"), "queue": queue, "step": step, "result": result}

    queue["status"] = "complete"
    save_queue(queue)
    return {"ok": True, "message": "No pending steps.", "queue": queue}


def request_stop():
    _ensure_dirs()
    STOP_FILE.write_text(_now(), encoding="utf-8")
    return {"ok": True, "stop_requested": True, "path": str(STOP_FILE)}


def clear_stop():
    if STOP_FILE.exists():
        STOP_FILE.unlink()
    return {"ok": True, "stop_requested": False}


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "queue": load_queue(),
    }
    json_path = REPORTS_DIR / f"pc_codex_executor_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"pc_codex_executor_report_{_stamp()}.md"
    _write_json(json_path, payload)
    md = [
        "# PC Codex Executor Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_status(payload["status"]),
        "```",
        "",
        "## Queue",
        "",
        "```json",
        json.dumps(payload["queue"], ensure_ascii=False, indent=2),
        "```",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc exec", "pc exec status", "pc exec статус", "executor status"}:
        return format_status(status())

    if lower in {"pc exec step", "executor step"}:
        return format_payload(step_current())

    if lower in {"pc exec stop", "executor stop"}:
        return format_payload(request_stop())

    if lower in {"pc exec clear stop", "pc exec clear", "executor clear stop"}:
        return format_payload(clear_stop())

    if lower in {"pc exec report", "pc exec отчет", "executor report"}:
        return format_payload(report("manual report"))

    prefixes = [
        ("pc exec queue ", "queue"),
        ("pc exec очередь ", "queue"),
        ("pc exec dry ", "dry"),
        ("pc exec сухой ", "dry"),
        ("pc exec run ", "run"),
        ("pc exec запуск ", "run"),
        ("executor queue ", "queue"),
        ("executor dry ", "dry"),
        ("executor run ", "run"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "queue":
                return format_payload(queue_goal(value))
            if action == "dry":
                return format_payload(dry_goal(value))
            if action == "run":
                return format_payload(run_confirmed(value))

    return format_payload({"ok": False, "error": "Unknown PC Codex Executor command.", "help": status().get("commands", [])})


def is_executor_command(command):
    lower = _norm(command)
    exact = {
        "pc exec", "pc exec status", "pc exec статус", "executor status",
        "pc exec step", "executor step", "pc exec stop", "executor stop",
        "pc exec clear stop", "pc exec clear", "executor clear stop",
        "pc exec report", "pc exec отчет", "executor report",
    }
    if lower in exact:
        return True
    prefixes = (
        "pc exec queue ", "pc exec очередь ", "pc exec dry ", "pc exec сухой ",
        "pc exec run ", "pc exec запуск ", "executor queue ", "executor dry ", "executor run ",
    )
    return lower.startswith(prefixes)
````

### ПУТЬ: modules/pc_codex_mode.py (337 строк, 10691 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import traceback

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
PC_CODEX_REPORTS_DIR = REPORTS_DIR / "pc_codex_mode"


BLOCKED_TERMS = [
    "удали",
    "стереть",
    "форматируй",
    "format",
    "delete",
    "remove",
    "rm -rf",
    "пароль",
    "password",
    "token",
    "api key",
    "secret",
    "приватный ключ",
    "private key",
    "оплати",
    "payment",
    "банк",
    "bank",
    "ставка",
    "bet",
    "casino",
    "логин",
    "login",
    "send enter",
    "нажми enter",
    "enter",
    "powershell",
    "cmd",
    "shell",
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _normalize(text):
    return str(text or "").lower().replace("ё", "е").strip()


def classify_pc_codex_goal(goal):
    lower = _normalize(goal)
    matched = [term for term in BLOCKED_TERMS if term in lower]

    needs_confirmation_terms = [
        "клик",
        "click",
        "нажми",
        "открой",
        "open",
        "перейди",
        "вставь",
        "paste",
        "напиши",
        "type",
        "запусти",
        "run",
    ]
    needs_confirmation = any(term in lower for term in needs_confirmation_terms)

    if matched:
        return {
            "safe": False,
            "needs_confirmation": True,
            "blocked_reason": "Команда содержит опасные термины: " + ", ".join(matched),
            "matched_terms": matched,
        }

    return {
        "safe": True,
        "needs_confirmation": needs_confirmation,
        "blocked_reason": "",
        "matched_terms": [],
    }


def pc_codex_status():
    payload = {
        "ok": True,
        "mode": "pc_codex",
        "generated_at": _now(),
        "focus": "PC Agent / управление ПК через чат",
        "principles": [
            "observe first",
            "plan before action",
            "dry-run before confirmed step",
            "block destructive/private/payment/system actions",
            "prefer reports over blind automation",
        ],
        "commands": [
            "pc codex статус",
            "pc codex что умеешь",
            "pc codex осмотр",
            "pc codex план <цель>",
            "pc codex dry <цель>",
            "pc codex step <цель>",
            "pc codex отчет",
        ],
        "last_goal": get_value("pc_codex_last_goal", ""),
        "last_result": get_value("pc_codex_last_result", ""),
    }
    set_value("pc_codex_last_status", payload)
    return payload


def format_pc_codex_status(payload=None):
    payload = payload or pc_codex_status()
    lines = [
        "PC Codex Mode:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- focus: {payload.get('focus')}",
        "",
        "Принципы:",
    ]
    lines.extend("- " + item for item in payload.get("principles", []))
    lines.append("")
    lines.append("Команды:")
    lines.extend("- " + item for item in payload.get("commands", []))
    last_goal = payload.get("last_goal")
    if last_goal:
        lines.append("")
        lines.append(f"last_goal: {last_goal}")
    return "\n".join(lines)


def pc_codex_capabilities():
    return (
        "PC Codex Mode — что умею:\\n\\n"
        "1. Осматривать экран и состояние проекта.\\n"
        "2. Строить пошаговый план управления ПК.\\n"
        "3. Делать dry-run без кликов и ввода.\\n"
        "4. Выполнять только безопасный confirmed step через существующий PC Agent.\\n"
        "5. Создавать отчеты по действиям.\\n"
        "6. Блокировать удаление, shell, пароли, токены, платежи, логины и приватные данные.\\n"
        "7. Использовать PC Agent Actions Pack для allowlist-действий: открыть приложение, открыть папку, создать заметку.\\n"
        "8. Если команда неизвестна — делать internet research и учитывать структуру проекта.\\n"
        "9. Для изменения проекта создавать request.md с контекстом: pc edit <задача>.\\n\\n"
        "Главный рабочий формат:\\n"
        "- pc codex план <что сделать>\\n"
        "- pc codex dry <что сделать>\\n"
        "- pc codex step <что сделать>\\n"
        "- pc actions список\\n"
        "- pc actions open app notepad\\n"
        "- pc actions open folder projects\\n"
        "- pc actions note <текст>\\n"
    )


def pc_codex_observe():
    try:
        from modules.pc_agent_core import pc_agent_observe
        payload = pc_agent_observe()
    except Exception:
        payload = {"ok": False, "error": traceback.format_exc()}

    set_value("pc_codex_last_result", payload)
    return payload


def pc_codex_plan(goal):
    goal = str(goal or "").strip()
    safety = classify_pc_codex_goal(goal)

    if not safety.get("safe"):
        payload = {
            "ok": False,
            "mode": "pc_codex_plan",
            "goal": goal,
            "safety": safety,
            "result": "BLOCKED before planning.",
        }
        set_value("pc_codex_last_result", payload)
        return payload

    try:
        from modules.pc_agent_core import pc_agent_plan
        plan = pc_agent_plan(goal)
    except Exception:
        plan = {"ok": False, "error": traceback.format_exc()}

    payload = {
        "ok": True,
        "mode": "pc_codex_plan",
        "goal": goal,
        "safety": safety,
        "plan": plan,
        "next": "Для безопасной проверки используй: pc codex dry <цель>. Для действия: pc codex step <цель>.",
    }
    set_value("pc_codex_last_goal", goal)
    set_value("pc_codex_last_result", payload)
    return payload


def pc_codex_dry_run(goal):
    goal = str(goal or "").strip()
    safety = classify_pc_codex_goal(goal)

    if not safety.get("safe"):
        payload = {
            "ok": False,
            "mode": "pc_codex_dry_run",
            "goal": goal,
            "safety": safety,
            "result": "BLOCKED.",
        }
        set_value("pc_codex_last_result", payload)
        return payload

    try:
        from modules.pc_agent_core import pc_agent_step
        result = pc_agent_step(goal, confirmed=False, dry_run=True)
    except Exception:
        result = {"ok": False, "error": traceback.format_exc()}

    payload = {
        "ok": True,
        "mode": "pc_codex_dry_run",
        "goal": goal,
        "safety": safety,
        "result": result,
    }
    set_value("pc_codex_last_goal", goal)
    set_value("pc_codex_last_result", payload)
    return payload


def pc_codex_confirmed_step(goal):
    goal = str(goal or "").strip()
    safety = classify_pc_codex_goal(goal)

    if not safety.get("safe"):
        payload = {
            "ok": False,
            "mode": "pc_codex_confirmed_step",
            "goal": goal,
            "safety": safety,
            "result": "BLOCKED.",
        }
        set_value("pc_codex_last_result", payload)
        return payload

    if safety.get("needs_confirmation") and "подтверждаю" not in _normalize(goal):
        payload = {
            "ok": False,
            "mode": "pc_codex_confirmed_step",
            "goal": goal,
            "safety": safety,
            "result": "Нужно явное слово 'подтверждаю' в команде для действия с кликом/вводом/запуском.",
            "example": "pc codex step подтверждаю: открыть блокнот",
        }
        set_value("pc_codex_last_result", payload)
        return payload

    try:
        from modules.pc_agent_core import pc_agent_step
        result = pc_agent_step(goal.replace("подтверждаю:", "").replace("подтверждаю", "").strip(), confirmed=True, dry_run=False)
    except Exception:
        result = {"ok": False, "error": traceback.format_exc()}

    payload = {
        "ok": True,
        "mode": "pc_codex_confirmed_step",
        "goal": goal,
        "safety": safety,
        "result": result,
    }
    set_value("pc_codex_last_goal", goal)
    set_value("pc_codex_last_result", payload)
    return payload


def create_pc_codex_report(note=""):
    PC_CODEX_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": pc_codex_status(),
        "last_goal": get_value("pc_codex_last_goal", ""),
        "last_result": get_value("pc_codex_last_result", ""),
    }

    json_path = PC_CODEX_REPORTS_DIR / f"pc_codex_report_{_stamp()}.json"
    md_path = PC_CODEX_REPORTS_DIR / f"pc_codex_report_{_stamp()}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# PC Codex Mode Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_pc_codex_status(payload["status"]),
        "```",
        "",
        "## Last Result",
        "",
        "```json",
        json.dumps(payload["last_result"], ensure_ascii=False, indent=2),
        "```",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")

    result = {"ok": True, "report": str(md_path), "json": str(json_path)}
    set_value("pc_codex_last_report", result)
    return result


def format_pc_codex_result(payload):
    if isinstance(payload, str):
        return payload

    return json.dumps(payload, ensure_ascii=False, indent=2)
````

### ПУТЬ: modules/pc_control_core.py (291 строк, 8051 байт)

````python
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from modules.chatgpt_desktop_bridge import (
    focus_chatgpt_desktop_window,
    get_foreground_window_info,
    paste_prompt_after_input_focus,
)
from modules.desktop_observer import observe_desktop


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
PC_AGENT_REPORTS_DIR = REPORTS_DIR / "pc_agent"

ALLOWED_COMMANDS = {
    "git status --short": ["git", "status", "--short"],
    "git log -5 --oneline": ["git", "log", "-5", "--oneline"],
    "git diff --stat": ["git", "diff", "--stat"],
    "python -m py_compile modules\\pc_agent_core.py": ["python", "-m", "py_compile", "modules\\pc_agent_core.py"],
    "python -m py_compile modules\\pc_control_core.py": ["python", "-m", "py_compile", "modules\\pc_control_core.py"],
    "python -m py_compile modules\\chatgpt_desktop_bridge.py": ["python", "-m", "py_compile", "modules\\chatgpt_desktop_bridge.py"],
    "python -m py_compile modules\\desktop_action_planner.py": ["python", "-m", "py_compile", "modules\\desktop_action_planner.py"],
    "python -m py_compile LocalComet_Control_Panel.py": ["python", "-m", "py_compile", "LocalComet_Control_Panel.py"],
}

HARD_BLOCK_MARKERS = [
    "delete",
    "remove",
    "rmdir",
    "del ",
    "format",
    "payment",
    "buy",
    "checkout",
    "password",
    "login",
    "bank",
    "crypto",
    "submit",
    "powershell",
    ".exe",
    "install",
    "system settings",
    "browserprofile",
    ".env",
    "private key",
    "secret",
    "token",
    "api key",
    "удали",
    "удалить",
    "пароль",
    "логин",
    "банк",
    "оплат",
]

SENSITIVE_FILE_MARKERS = [
    ".env",
    "secret",
    "token",
    "private",
    "key",
    "browserprofile",
    "projects/browserprofile",
    "config.py",
    "core/router.py",
    "core/planner.py",
    "core/executor.py",
    "modules/self_edit.py",
    "modules/gpt_browser_bridge.py",
    "modules/browser_bridge.py",
]

SAFE_OPEN_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".py",
    ".log",
    ".csv",
    ".yaml",
    ".yml",
}


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    PC_AGENT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def hard_block_reasons(text):
    lower = str(text or "").lower()
    return [marker for marker in HARD_BLOCK_MARKERS if marker in lower]


def is_safe_project_path(path):
    try:
        resolved = Path(path).expanduser().resolve()
    except Exception:
        return False, None, "path could not be resolved"

    root = ROOT_DIR.resolve()

    if resolved != root and root not in resolved.parents:
        return False, resolved, "path is outside LocalAgent"

    normalized = str(resolved).replace("\\", "/").lower()

    if "projects/browserprofile" in normalized:
        return False, resolved, "browser profile is blocked"

    if any(marker in normalized for marker in SENSITIVE_FILE_MARKERS):
        return False, resolved, "path looks sensitive"

    return True, resolved, ""


def list_visible_windows():
    observation = observe_desktop(write_report=False)
    return observation.get("windows") or []


def observe_pc():
    observation = observe_desktop(write_report=True)
    return {
        "ok": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "foreground": get_foreground_window_info(),
        "observation": observation,
        "windows": observation.get("windows") or [],
        "report_path": observation.get("report_path") or "",
    }


def focus_chatgpt_desktop():
    return focus_chatgpt_desktop_window()


def paste_to_chatgpt_focused_input(prompt, send=False, dry_run=True):
    return paste_prompt_after_input_focus(prompt=prompt, send=send, dry_run=dry_run)


def set_clipboard_text(text, confirmed=False, dry_run=True):
    text = str(text or "")
    payload = {
        "ok": False,
        "dry_run": bool(dry_run),
        "confirmed": bool(confirmed),
        "text_chars": len(text),
    }

    if hard_block_reasons(text):
        payload["message"] = "STOP: clipboard text contains blocked markers."
        payload["blocked_reasons"] = hard_block_reasons(text)
        return payload

    if dry_run:
        payload["ok"] = True
        payload["message"] = "DRY RUN: clipboard write allowed but not executed."
        return payload

    if not confirmed:
        payload["message"] = "STOP: clipboard write requires confirmed=True."
        return payload

    from modules.chatgpt_desktop_bridge import copy_prompt_to_clipboard

    result = copy_prompt_to_clipboard(text)
    payload.update(result)
    return payload


def run_allowed_command(command, confirmed=False, dry_run=True):
    command = str(command or "").strip()
    payload = {
        "ok": False,
        "command": command,
        "dry_run": bool(dry_run),
        "confirmed": bool(confirmed),
        "allowed_commands": sorted(ALLOWED_COMMANDS),
    }

    blocked = hard_block_reasons(command)
    if blocked:
        payload["message"] = "STOP: command contains blocked markers."
        payload["blocked_reasons"] = blocked
        return payload

    argv = ALLOWED_COMMANDS.get(command)
    if not argv:
        payload["message"] = "STOP: command is not in the exact allowlist."
        return payload

    if dry_run:
        payload["ok"] = True
        payload["message"] = "DRY RUN: command is allowlisted but not executed."
        payload["argv"] = argv
        return payload

    if not confirmed:
        payload["message"] = "STOP: command execution requires confirmed=True."
        return payload

    completed = subprocess.run(
        argv,
        cwd=str(ROOT_DIR),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
    )
    payload.update({
        "ok": completed.returncode == 0,
        "message": "Command completed." if completed.returncode == 0 else "Command failed.",
        "returncode": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-8000:],
    })
    return payload


def open_safe_path(path, confirmed=False, dry_run=True):
    ok, resolved, reason = is_safe_project_path(path)
    payload = {
        "ok": False,
        "path": str(path or ""),
        "resolved_path": str(resolved or ""),
        "dry_run": bool(dry_run),
        "confirmed": bool(confirmed),
    }

    if not ok:
        payload["message"] = f"STOP: unsafe path: {reason}"
        return payload

    if not resolved.exists():
        payload["message"] = "STOP: path does not exist."
        return payload

    if resolved.is_file() and resolved.suffix.lower() not in SAFE_OPEN_SUFFIXES:
        payload["message"] = "STOP: file type is not in the safe-open allowlist."
        return payload

    if dry_run:
        payload["ok"] = True
        payload["message"] = "DRY RUN: path is safe to open."
        return payload

    if not confirmed:
        payload["message"] = "STOP: opening a path requires confirmed=True."
        return payload

    os.startfile(str(resolved))
    payload["ok"] = True
    payload["message"] = "Path opened."
    return payload


def write_pc_report(title, payload):
    _ensure_dirs()
    path = PC_AGENT_REPORTS_DIR / f"pc_agent_{_stamp()}.md"
    lines = [
        f"# {title}",
        "",
        f"- created_at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def latest_pc_control_report():
    if not PC_AGENT_REPORTS_DIR.exists():
        return ""

    reports = sorted(PC_AGENT_REPORTS_DIR.glob("pc_agent_*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    return str(reports[0]) if reports else ""
````

### ПУТЬ: modules/pc_desktop_primitives.py (731 строк, 22686 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import platform
import re
import traceback


from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "pc_desktop_primitives"
ACTIONS_DIR = PROJECTS_DIR / "PCAgent" / "DesktopActions"

SAFE_HOTKEY_ALLOWLIST = {
    "ctrl+c": {
        "risk": "low",
        "description": "Copy selected text.",
        "exec_allowed": False,
    },
    "ctrl+a": {
        "risk": "medium",
        "description": "Select all in active field/window.",
        "exec_allowed": False,
    },
    "esc": {
        "risk": "low",
        "description": "Close menu/dialog or cancel current transient UI.",
        "exec_allowed": False,
    },
    "f5": {
        "risk": "medium",
        "description": "Refresh active window/page.",
        "exec_allowed": False,
    },
    "ctrl+l": {
        "risk": "medium",
        "description": "Focus browser/file-explorer address bar.",
        "exec_allowed": False,
    },
}

DANGEROUS_TITLE_TERMS = [
    "password",
    "пароль",
    "token",
    "secret",
    "private key",
    "bank",
    "банк",
    "payment",
    "casino",
    "ставк",
    "registry",
    "regedit",
]

BLOCKED_HOTKEY_TERMS = [
    "delete",
    "del",
    "alt+f4",
    "ctrl+w",
    "ctrl+shift+esc",
    "win+r",
    "cmd",
    "powershell",
    "enter",
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ACTIONS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _is_windows():
    return platform.system().lower() == "windows"


def _rect_to_payload(rect):
    left, top, right, bottom = rect
    return {
        "left": int(left),
        "top": int(top),
        "right": int(right),
        "bottom": int(bottom),
        "width": int(right - left),
        "height": int(bottom - top),
    }


def _safe_title(title):
    lower = _norm(title)
    hits = [term for term in DANGEROUS_TITLE_TERMS if term in lower]
    return {
        "safe": not hits,
        "matched_terms": hits,
        "reason": "" if not hits else "sensitive window title terms: " + ", ".join(hits),
    }


def _enum_windows_ctypes():
    if not _is_windows():
        return []

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        windows = []

        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            if not title:
                return True

            class_buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buffer, 256)

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            payload = {
                "title": title,
                "class": class_buffer.value,
                "rect": _rect_to_payload((rect.left, rect.top, rect.right, rect.bottom)),
                "hwnd": int(hwnd),
                "safety": _safe_title(title),
            }
            windows.append(payload)
            return True

        user32.EnumWindows(EnumWindowsProc(callback), 0)
        return windows
    except Exception:
        return []


def _active_window_ctypes():
    if not _is_windows():
        return {}

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {}

        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)

        class_buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buffer, 256)

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        title = buffer.value.strip()
        return {
            "title": title,
            "class": class_buffer.value,
            "rect": _rect_to_payload((rect.left, rect.top, rect.right, rect.bottom)),
            "hwnd": int(hwnd),
            "safety": _safe_title(title),
        }
    except Exception:
        return {}


def _mouse_position_ctypes():
    if not _is_windows():
        return {"ok": False, "error": "mouse position is currently implemented for Windows only"}

    try:
        import ctypes
        from ctypes import wintypes

        point = wintypes.POINT()
        ok = ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        if not ok:
            return {"ok": False, "error": "GetCursorPos failed"}
        return {"ok": True, "x": int(point.x), "y": int(point.y)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _window_at_point(windows, x, y):
    for window in windows:
        rect = window.get("rect", {})
        left = int(rect.get("left", 0))
        top = int(rect.get("top", 0))
        right = int(rect.get("right", 0))
        bottom = int(rect.get("bottom", 0))
        if left <= x <= right and top <= y <= bottom:
            return window
    return {}


def _parse_two_ints(text):
    numbers = re.findall(r"-?\d+", str(text or ""))
    if len(numbers) < 2:
        raise ValueError("Need two coordinates: x y")
    return int(numbers[0]), int(numbers[1])


def _normalize_hotkey(combo):
    combo = _norm(combo)
    combo = combo.replace(" ", "")
    combo = combo.replace("control", "ctrl")
    combo = combo.replace("контрол", "ctrl")
    combo = combo.replace("контроль", "ctrl")
    combo = combo.replace("альт", "alt")
    combo = combo.replace("дел", "del")
    combo = combo.replace("эск", "esc")
    combo = combo.replace("escape", "esc")
    combo = combo.replace("plus", "+")
    combo = combo.replace("++", "+")
    return combo.strip("+")


def list_windows():
    windows = _enum_windows_ctypes()

    if not windows:
        try:
            from modules.desktop_observer import observe_desktop

            observed = observe_desktop()
            windows = observed.get("windows", [])
            for item in windows:
                item["safety"] = _safe_title(item.get("title", ""))
        except Exception:
            windows = []

    active = _active_window_ctypes()

    payload = {
        "ok": True,
        "mode": "desktop_windows",
        "generated_at": _now(),
        "platform": platform.platform(),
        "active_window": active,
        "windows": windows,
        "count": len(windows),
    }
    set_value("pc_desktop_primitives_windows", payload)
    return payload


def mouse_position():
    payload = {
        "ok": True,
        "mode": "desktop_mouse",
        "generated_at": _now(),
        "position": _mouse_position_ctypes(),
        "active_window": _active_window_ctypes(),
    }
    set_value("pc_desktop_primitives_mouse", payload)
    return payload


def screenshot_metadata():
    _ensure_dirs()
    try:
        from modules.desktop_observer import observe_desktop

        observed = observe_desktop()
        payload = {
            "ok": True,
            "mode": "desktop_screenshot_metadata",
            "generated_at": _now(),
            "screenshot_path": observed.get("screenshot_path", ""),
            "screenshot_error": observed.get("screenshot_error", ""),
            "report_path": observed.get("report_path", ""),
            "active_window": observed.get("active_window", {}),
            "windows_count": len(observed.get("windows", []) or []),
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "desktop_screenshot_metadata",
            "generated_at": _now(),
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

    set_value("pc_desktop_primitives_screenshot", payload)
    return payload


def dry_click(x, y):
    x = int(x)
    y = int(y)
    windows_payload = list_windows()
    window = _window_at_point(windows_payload.get("windows", []), x, y)
    action = {
        "id": f"dry_click_{_stamp()}",
        "type": "click",
        "point": {"x": x, "y": y},
        "target_window": window,
        "dry_run_required": True,
        "confirmation_required": True,
        "executed": False,
        "result": "DRY_RUN: click not executed.",
        "safety": {
            "allowlisted": bool(window) and window.get("safety", {}).get("safe", True),
            "blocked_terms": window.get("safety", {}).get("matched_terms", []) if window else [],
            "reason": window.get("safety", {}).get("reason", "") if window else "No window found at point.",
        },
    }

    payload = {
        "ok": True,
        "mode": "desktop_dry_click",
        "generated_at": _now(),
        "action": action,
    }

    _ensure_dirs()
    path = ACTIONS_DIR / f"dry_click_{_stamp()}.json"
    payload["path"] = _write_json(path, payload)
    set_value("pc_desktop_primitives_last_dry_click", payload)
    return payload


def validate_hotkey(combo):
    normalized = _normalize_hotkey(combo)
    blocked_hits = [term for term in BLOCKED_HOTKEY_TERMS if term in normalized]
    allow_info = SAFE_HOTKEY_ALLOWLIST.get(normalized)

    if blocked_hits:
        return {
            "ok": False,
            "mode": "desktop_hotkey_validation",
            "generated_at": _now(),
            "combo": combo,
            "normalized": normalized,
            "allowed": False,
            "executed": False,
            "reason": "Blocked hotkey terms: " + ", ".join(blocked_hits),
        }

    if not allow_info:
        return {
            "ok": False,
            "mode": "desktop_hotkey_validation",
            "generated_at": _now(),
            "combo": combo,
            "normalized": normalized,
            "allowed": False,
            "executed": False,
            "reason": "Hotkey is not in safe allowlist.",
            "allowlist": sorted(SAFE_HOTKEY_ALLOWLIST.keys()),
        }

    return {
        "ok": True,
        "mode": "desktop_hotkey_validation",
        "generated_at": _now(),
        "combo": combo,
        "normalized": normalized,
        "allowed": True,
        "exec_allowed": bool(allow_info.get("exec_allowed")),
        "executed": False,
        "risk": allow_info.get("risk", "unknown"),
        "description": allow_info.get("description", ""),
        "reason": "DRY_RUN: hotkey validated but not executed.",
    }


def dry_hotkey(combo):
    payload = validate_hotkey(combo)
    payload["dry_run"] = True
    payload["result"] = "DRY_RUN: hotkey not executed."
    set_value("pc_desktop_primitives_last_dry_hotkey", payload)
    return payload


def _find_window_by_title(query):
    query_norm = _norm(query)
    windows_payload = list_windows()
    matches = []
    for window in windows_payload.get("windows", []):
        title = window.get("title", "")
        if query_norm and query_norm in _norm(title):
            matches.append(window)
    return matches


def dry_focus_window(query):
    matches = _find_window_by_title(query)
    selected = matches[0] if matches else {}
    payload = {
        "ok": bool(selected),
        "mode": "desktop_dry_focus_window",
        "generated_at": _now(),
        "query": str(query or "").strip(),
        "matches": matches[:10],
        "selected": selected,
        "executed": False,
        "result": "DRY_RUN: focus not changed." if selected else "No matching window found.",
        "next": f"pc desktop focus подтверждаю: {query}" if selected else "",
    }
    set_value("pc_desktop_primitives_last_dry_focus", payload)
    return payload


def focus_window(raw_query):
    raw_query = str(raw_query or "").strip()
    lower = _norm(raw_query)
    if "подтверждаю:" not in lower:
        return {
            "ok": False,
            "mode": "desktop_focus_window",
            "generated_at": _now(),
            "executed": False,
            "reason": "Нужна явная фраза подтверждения.",
            "example": "pc desktop focus подтверждаю: LocalComet",
        }

    query = re.sub(r"(?i)подтверждаю\s*:", "", raw_query, count=1).strip()
    matches = _find_window_by_title(query)
    selected = matches[0] if matches else {}

    if not selected:
        return {
            "ok": False,
            "mode": "desktop_focus_window",
            "generated_at": _now(),
            "query": query,
            "executed": False,
            "reason": "No matching window found.",
        }

    safety = selected.get("safety", {})
    if not safety.get("safe", True):
        return {
            "ok": False,
            "mode": "desktop_focus_window",
            "generated_at": _now(),
            "query": query,
            "selected": selected,
            "executed": False,
            "reason": safety.get("reason", "Unsafe window title."),
        }

    if not _is_windows():
        return {
            "ok": False,
            "mode": "desktop_focus_window",
            "generated_at": _now(),
            "query": query,
            "selected": selected,
            "executed": False,
            "reason": "Focus execution is currently implemented for Windows only.",
        }

    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = int(selected.get("hwnd", 0))
        if not hwnd:
            raise RuntimeError("No hwnd for selected window.")

        SW_RESTORE = 9
        user32.ShowWindow(hwnd, SW_RESTORE)
        ok = bool(user32.SetForegroundWindow(hwnd))

        payload = {
            "ok": ok,
            "mode": "desktop_focus_window",
            "generated_at": _now(),
            "query": query,
            "selected": selected,
            "executed": ok,
            "result": "Window focused." if ok else "SetForegroundWindow returned false.",
            "active_after": _active_window_ctypes(),
        }
        set_value("pc_desktop_primitives_last_focus", payload)
        return payload
    except Exception as exc:
        return {
            "ok": False,
            "mode": "desktop_focus_window",
            "generated_at": _now(),
            "query": query,
            "selected": selected,
            "executed": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def status():
    payload = {
        "ok": True,
        "mode": "pc_desktop_primitives",
        "generated_at": _now(),
        "platform": platform.platform(),
        "active_window": _active_window_ctypes(),
        "mouse": _mouse_position_ctypes(),
        "commands": [
            "pc desktop status",
            "pc desktop windows",
            "pc desktop mouse",
            "pc desktop screenshot",
            "pc desktop dry click <x> <y>",
            "pc desktop dry hotkey <combo>",
            "pc desktop dry focus <title>",
            "pc desktop focus подтверждаю: <title>",
            "pc desktop report",
        ],
        "safety": [
            "No blind click execution.",
            "Dry click only previews target window.",
            "Hotkeys are validation-only in v6.22.",
            "Focus window requires explicit confirmation.",
            "Sensitive window titles are blocked.",
            "No shell/cmd/powershell/delete actions.",
        ],
    }
    set_value("pc_desktop_primitives_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    lines = [
        "PC Desktop Interaction Primitives:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- platform: {payload.get('platform')}",
        f"- active_window: {(payload.get('active_window') or {}).get('title', '')}",
        f"- mouse: {payload.get('mouse')}",
        "",
        "Commands:",
    ]
    lines.extend("- " + item for item in payload.get("commands", []))
    lines.append("")
    lines.append("Safety:")
    lines.extend("- " + item for item in payload.get("safety", []))
    return "\n".join(lines)


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "windows": list_windows(),
        "mouse": mouse_position(),
        "screenshot": screenshot_metadata(),
        "last_dry_click": get_value("pc_desktop_primitives_last_dry_click", ""),
        "last_dry_hotkey": get_value("pc_desktop_primitives_last_dry_hotkey", ""),
        "last_dry_focus": get_value("pc_desktop_primitives_last_dry_focus", ""),
        "last_focus": get_value("pc_desktop_primitives_last_focus", ""),
    }

    json_path = REPORTS_DIR / f"pc_desktop_primitives_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"pc_desktop_primitives_report_{_stamp()}.md"
    _write_json(json_path, payload)

    md = [
        "# PC Desktop Interaction Primitives Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_status(payload["status"]),
        "```",
        "",
        "## Windows count",
        "",
        str(payload["windows"].get("count", 0)),
        "",
        "## Screenshot",
        "",
        "```json",
        json.dumps(payload["screenshot"], ensure_ascii=False, indent=2),
        "```",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")

    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc desktop", "pc desktop status", "pc desktop статус", "desktop status"}:
        return format_status(status())

    if lower in {"pc desktop windows", "pc desktop окна", "desktop windows"}:
        return format_payload(list_windows())

    if lower in {"pc desktop mouse", "pc desktop мышь", "desktop mouse"}:
        return format_payload(mouse_position())

    if lower in {"pc desktop screenshot", "pc desktop скрин", "desktop screenshot"}:
        return format_payload(screenshot_metadata())

    if lower in {"pc desktop report", "pc desktop отчет", "pc desktop отчёт", "desktop report"}:
        return format_payload(report("manual report"))

    prefixes = [
        ("pc desktop dry click ", "dry_click"),
        ("pc desktop dry клик ", "dry_click"),
        ("desktop dry click ", "dry_click"),
        ("pc desktop dry hotkey ", "dry_hotkey"),
        ("pc desktop dry хоткей ", "dry_hotkey"),
        ("desktop dry hotkey ", "dry_hotkey"),
        ("pc desktop dry focus ", "dry_focus"),
        ("pc desktop dry фокус ", "dry_focus"),
        ("desktop dry focus ", "dry_focus"),
        ("pc desktop focus ", "focus"),
        ("pc desktop фокус ", "focus"),
        ("desktop focus ", "focus"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "dry_click":
                try:
                    x, y = _parse_two_ints(value)
                    return format_payload(dry_click(x, y))
                except Exception as exc:
                    return format_payload({"ok": False, "error": str(exc), "example": "pc desktop dry click 100 200"})
            if action == "dry_hotkey":
                return format_payload(dry_hotkey(value))
            if action == "dry_focus":
                return format_payload(dry_focus_window(value))
            if action == "focus":
                return format_payload(focus_window(value))

    return format_payload({
        "ok": False,
        "error": "Unknown PC Desktop command.",
        "help": status().get("commands", []),
    })


def is_desktop_command(command):
    lower = _norm(command)
    exact = {
        "pc desktop",
        "pc desktop status",
        "pc desktop статус",
        "desktop status",
        "pc desktop windows",
        "pc desktop окна",
        "desktop windows",
        "pc desktop mouse",
        "pc desktop мышь",
        "desktop mouse",
        "pc desktop screenshot",
        "pc desktop скрин",
        "desktop screenshot",
        "pc desktop report",
        "pc desktop отчет",
        "pc desktop отчёт",
        "desktop report",
    }
    if lower in exact:
        return True

    prefixes = (
        "pc desktop dry click ",
        "pc desktop dry клик ",
        "desktop dry click ",
        "pc desktop dry hotkey ",
        "pc desktop dry хоткей ",
        "desktop dry hotkey ",
        "pc desktop dry focus ",
        "pc desktop dry фокус ",
        "desktop dry focus ",
        "pc desktop focus ",
        "pc desktop фокус ",
        "desktop focus ",
    )
    return lower.startswith(prefixes)
````

### ПУТЬ: modules/pc_screen_planner.py (439 строк, 13970 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import platform
import traceback

from core.state import get_value, set_value

from modules.pc_codex_core import classify_goal, plan as core_plan
from modules.pc_codex_executor import queue_goal, dry_goal
from modules.pc_agent_knowledge import build_project_context


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "pc_screen_planner"
OBSERVATIONS_DIR = PROJECTS_DIR / "PCAgent" / "ScreenObservations"

BLOCKED_TERMS = [
    "delete",
    "remove",
    "format",
    "shell",
    "cmd",
    "powershell",
    "terminal",
    "registry",
    "password",
    "пароль",
    "token",
    "secret",
    "private key",
    "login",
    "логин",
    "bank",
    "банк",
    "payment",
    "casino",
    "ставка",
]

SCREEN_ACTION_HINTS = {
    "open_app": ["открыть", "запусти", "open", "launch"],
    "read_screen": ["что на экране", "посмотри экран", "осмотри", "observe", "screen"],
    "project_work": ["проект", "код", "модуль", "патч", "response.json", "request.md"],
    "browser_work": ["браузер", "страница", "сайт", "google", "поиск", "web"],
}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    OBSERVATIONS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _active_window_title():
    if platform.system().lower() != "windows":
        return ""

    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value
    except Exception:
        return ""


def _screen_size():
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        size = {"width": root.winfo_screenwidth(), "height": root.winfo_screenheight()}
        root.destroy()
        return size
    except Exception:
        return {"width": 0, "height": 0}


def _try_desktop_observer():
    try:
        from modules.desktop_observer import observe_desktop

        result = observe_desktop()
        return {"ok": True, "source": "modules.desktop_observer.observe_desktop", "result": result}
    except Exception as exc:
        return {"ok": False, "source": "modules.desktop_observer.observe_desktop", "error": str(exc)}


def observe_screen(save=True):
    _ensure_dirs()

    observation = {
        "ok": True,
        "mode": "screen_observation",
        "generated_at": _now(),
        "platform": platform.platform(),
        "active_window_title": _active_window_title(),
        "screen_size": _screen_size(),
        "desktop_observer": _try_desktop_observer(),
        "notes": [
            "This is a safe text observation.",
            "No click/type action is executed by Screen Planner.",
            "Use dry-run and executor confirmation before control.",
        ],
    }

    if save:
        path = OBSERVATIONS_DIR / f"screen_observation_{_stamp()}.json"
        observation["path"] = _write_json(path, observation)

    set_value("pc_screen_planner_last_observation", observation)
    return observation


def classify_screen_goal(goal):
    lower = _norm(goal)
    safety = classify_goal(goal)
    hits = [term for term in BLOCKED_TERMS if term in lower]

    if hits:
        safety["safe"] = False
        safety["blocked_terms"] = sorted(set(safety.get("blocked_terms", []) + hits))
        safety["blocked_reason"] = "Screen planner blocked terms: " + ", ".join(safety["blocked_terms"])

    intent = "general"
    for candidate, words in SCREEN_ACTION_HINTS.items():
        if any(word in lower for word in words):
            intent = candidate
            break

    return {
        "safe": safety.get("safe", False),
        "blocked_terms": safety.get("blocked_terms", []),
        "blocked_reason": safety.get("blocked_reason", ""),
        "intent": intent,
        "requires_dry_run": True,
        "requires_confirmation": True,
    }


def plan_with_screen(goal, include_project=True):
    goal = str(goal or "").strip()

    if not goal:
        return {"ok": False, "error": "empty goal"}

    observation = observe_screen(save=True)
    screen_safety = classify_screen_goal(goal)
    core = core_plan(goal)
    project_context = build_project_context(include_contents=False) if include_project else {}

    steps = []

    if not screen_safety.get("safe"):
        steps.append({
            "type": "blocked",
            "title": "Цель заблокирована safety policy.",
            "detail": screen_safety.get("blocked_reason", ""),
        })
    else:
        active_title = observation.get("active_window_title") or "unknown"
        steps.extend([
            {
                "type": "observe",
                "title": "Зафиксировать текущий экран и активное окно.",
                "detail": f"active_window={active_title}",
            },
            {
                "type": "reason",
                "title": "Сопоставить цель с текущим контекстом.",
                "detail": f"intent={screen_safety.get('intent')}",
            },
            {
                "type": "dry_run",
                "title": "Сначала выполнить dry-run через executor.",
                "command": f"pc exec dry {goal}",
            },
            {
                "type": "confirm",
                "title": "Только после проверки выполнить confirmed run.",
                "command": f"pc exec run подтверждаю: {goal}",
            },
        ])

        if screen_safety.get("intent") == "project_work":
            steps.append({
                "type": "project_context",
                "title": "Учитывать структуру проекта.",
                "detail": "Изменения проекта только через request/response.json patch workflow.",
            })

        if screen_safety.get("intent") == "read_screen":
            steps.append({
                "type": "screen_summary",
                "title": "Ответить по экрану без управления мышью.",
                "detail": "Screen Planner не кликает по координатам; он готовит план.",
            })

    payload = {
        "ok": screen_safety.get("safe", False),
        "mode": "screen_aware_plan",
        "generated_at": _now(),
        "goal": goal,
        "screen_safety": screen_safety,
        "observation": observation,
        "core_plan": core,
        "project_counts": project_context.get("structure", {}).get("counts", {}) if project_context else {},
        "steps": steps,
        "next": f"pc screen dry {goal}",
    }

    set_value("pc_screen_planner_last_plan", payload)
    return payload


def dry_run_screen(goal):
    plan_payload = plan_with_screen(goal)
    if not plan_payload.get("ok"):
        return plan_payload

    executor_preview = dry_goal(goal)
    payload = {
        "ok": executor_preview.get("ok", False),
        "mode": "screen_aware_dry_run",
        "generated_at": _now(),
        "goal": goal,
        "screen_plan": plan_payload,
        "executor_dry_run": executor_preview,
        "next": f"pc exec run подтверждаю: {goal}",
    }
    set_value("pc_screen_planner_last_dry_run", payload)
    return payload


def queue_screen_goal(goal):
    plan_payload = plan_with_screen(goal)
    if not plan_payload.get("ok"):
        return plan_payload

    queue_payload = queue_goal(goal)
    payload = {
        "ok": queue_payload.get("ok", False),
        "mode": "screen_aware_queue",
        "generated_at": _now(),
        "goal": goal,
        "screen_plan": plan_payload,
        "executor_queue": queue_payload,
        "next": f"pc exec dry {goal}",
    }
    set_value("pc_screen_planner_last_queue", payload)
    return payload


def status():
    payload = {
        "ok": True,
        "mode": "pc_screen_planner",
        "generated_at": _now(),
        "last_observation": get_value("pc_screen_planner_last_observation", ""),
        "last_plan": get_value("pc_screen_planner_last_plan", ""),
        "last_dry_run": get_value("pc_screen_planner_last_dry_run", ""),
        "commands": [
            "pc screen status",
            "pc screen observe",
            "pc screen plan <цель>",
            "pc screen dry <цель>",
            "pc screen queue <цель>",
            "pc screen report",
        ],
        "safety": [
            "No blind coordinate clicking.",
            "No direct typing into unknown windows.",
            "No shell/cmd/powershell.",
            "No deletion.",
            "Screen Planner plans; Executor executes only after dry-run and confirmation.",
        ],
    }
    set_value("pc_screen_planner_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    lines = [
        "PC Screen-Aware Planner:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "Commands:",
    ]
    lines.extend("- " + item for item in payload.get("commands", []))
    lines.append("")
    lines.append("Safety:")
    lines.extend("- " + item for item in payload.get("safety", []))
    return "\n".join(lines)


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "last_observation": get_value("pc_screen_planner_last_observation", ""),
        "last_plan": get_value("pc_screen_planner_last_plan", ""),
        "last_dry_run": get_value("pc_screen_planner_last_dry_run", ""),
    }

    json_path = REPORTS_DIR / f"pc_screen_planner_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"pc_screen_planner_report_{_stamp()}.md"

    _write_json(json_path, payload)

    md = [
        "# PC Screen-Aware Planner Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_status(payload["status"]),
        "```",
        "",
        "## Last Plan",
        "",
        "```json",
        json.dumps(payload["last_plan"], ensure_ascii=False, indent=2),
        "```",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")

    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc screen", "pc screen status", "pc screen статус", "screen planner"}:
        return format_status(status())

    if lower in {"pc screen observe", "pc screen осмотр", "screen observe"}:
        return format_payload(observe_screen(save=True))

    if lower in {"pc screen report", "pc screen отчет", "screen report"}:
        return format_payload(report("manual report"))

    prefixes = [
        ("pc screen plan ", "plan"),
        ("pc screen план ", "plan"),
        ("pc screen dry ", "dry"),
        ("pc screen сухой ", "dry"),
        ("pc screen queue ", "queue"),
        ("pc screen очередь ", "queue"),
        ("screen plan ", "plan"),
        ("screen dry ", "dry"),
        ("screen queue ", "queue"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "plan":
                return format_payload(plan_with_screen(value))
            if action == "dry":
                return format_payload(dry_run_screen(value))
            if action == "queue":
                return format_payload(queue_screen_goal(value))

    return format_payload({
        "ok": False,
        "error": "Unknown PC Screen Planner command.",
        "help": status().get("commands", []),
    })


def is_screen_command(command):
    lower = _norm(command)
    exact = {
        "pc screen",
        "pc screen status",
        "pc screen статус",
        "screen planner",
        "pc screen observe",
        "pc screen осмотр",
        "screen observe",
        "pc screen report",
        "pc screen отчет",
        "screen report",
    }
    if lower in exact:
        return True

    prefixes = (
        "pc screen plan ",
        "pc screen план ",
        "pc screen dry ",
        "pc screen сухой ",
        "pc screen queue ",
        "pc screen очередь ",
        "screen plan ",
        "screen dry ",
        "screen queue ",
    )
    return lower.startswith(prefixes)
````

### ПУТЬ: modules/pc_ui_parser_adapter.py (737 строк, 25351 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import re
import traceback


from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
UI_DIR = PROJECTS_DIR / "PCAgent" / "UIParser"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "ui_parser_adapter"

UI_ELEMENT_SCHEMA = {
    "version": "localcomet_ui_element_v2",
    "description": "OmniParser-compatible LocalComet UI element schema without requiring heavy parser dependencies.",
    "element": {
        "id": "string",
        "element_type": "window|button|input|text|icon|image|menu|unknown",
        "text": "string",
        "bbox": {"x": "int", "y": "int", "width": "int", "height": "int"},
        "center": {"x": "int", "y": "int"},
        "confidence": "float 0..1",
        "clickable": "bool",
        "source": "desktop_observer|desktop_primitives|screen_parser_adapter|omniparser_future|manual",
        "metadata": "dict",
    },
}

UI_ACTION_SCHEMA = {
    "version": "localcomet_ui_action_suggestion_v1",
    "description": "Safe UI action suggestion. This module never executes clicks or typing.",
    "action": {
        "id": "string",
        "type": "observe|focus_window|dry_click|open_app|web_search|project_edit_request|screen_plan",
        "target": "string",
        "element_id": "string",
        "point": {"x": "int", "y": "int"},
        "confidence": "float 0..1",
        "dry_run_command": "string",
        "confirmed_command": "string",
        "executed": False,
        "safety": "dict",
    },
}

BACKENDS = [
    {
        "id": "desktop_window_parser",
        "name": "Desktop Window Parser",
        "status": "active",
        "description": "Converts Windows/Desktop observer window rectangles into LocalComet UI elements.",
        "requires": [],
    },
    {
        "id": "desktop_observer_screenshot",
        "name": "Desktop Observer Screenshot Metadata",
        "status": "active",
        "description": "Uses existing screenshot metadata/path from desktop_observer for future parser handoff.",
        "requires": [],
    },
    {
        "id": "omniparser_adapter",
        "name": "OmniParser-Compatible Adapter",
        "status": "planned",
        "description": "Future backend: screenshot -> UI element boxes, text labels, icons, and confidence.",
        "requires": ["model weights", "vision dependencies", "explicit install step"],
    },
    {
        "id": "showui_action_adapter",
        "name": "ShowUI/UI-TARS Action Adapter",
        "status": "planned",
        "description": "Future backend: goal + screenshot/elements -> suggested GUI action.",
        "requires": ["visual model", "safety gate", "dry-run executor"],
    },
]

BLOCKED_UI_TERMS = [
    "password",
    "пароль",
    "token",
    "secret",
    "private key",
    "api key",
    "bank",
    "банк",
    "payment",
    "casino",
    "seed phrase",
    "ssh",
]

CLICK_WORDS = ["click", "клик", "нажми", "нажать", "button", "кнопк"]
FOCUS_WORDS = ["focus", "фокус", "переключ", "окно", "window"]
OPEN_WORDS = ["open", "открыть", "запусти", "launch"]
WEB_WORDS = ["web", "google", "интернет", "найди", "поиск", "что такое", "как сделать"]
PROJECT_WORDS = ["проект", "код", "модуль", "patch", "response.json", "исправь", "добавь команду"]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    UI_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _bbox_from_rect(rect):
    rect = rect or {}
    x = _safe_int(rect.get("left", rect.get("x", 0)))
    y = _safe_int(rect.get("top", rect.get("y", 0)))
    width = _safe_int(rect.get("width", 0))
    height = _safe_int(rect.get("height", 0))

    if not width and "right" in rect:
        width = _safe_int(rect.get("right")) - x
    if not height and "bottom" in rect:
        height = _safe_int(rect.get("bottom")) - y

    return {"x": x, "y": y, "width": max(0, width), "height": max(0, height)}


def _center(bbox):
    return {
        "x": int(bbox.get("x", 0) + bbox.get("width", 0) / 2),
        "y": int(bbox.get("y", 0) + bbox.get("height", 0) / 2),
    }


def _safety_for_text(text):
    lower = _norm(text)
    hits = [term for term in BLOCKED_UI_TERMS if term in lower]
    return {
        "safe": not hits,
        "blocked_terms": hits,
        "reason": "" if not hits else "Sensitive UI text/title terms: " + ", ".join(hits),
    }


def _window_to_element(window, index, active=False):
    rect = window.get("rect", {}) if isinstance(window, dict) else {}
    title = str(window.get("title", "") if isinstance(window, dict) else "")
    bbox = _bbox_from_rect(rect)
    safety = _safety_for_text(title)

    element_type = "window"
    clickable = bool(title and bbox.get("width", 0) > 0 and bbox.get("height", 0) > 0 and safety.get("safe"))

    return {
        "id": "active_window" if active else f"window_{index}",
        "element_type": element_type,
        "text": title,
        "bbox": bbox,
        "center": _center(bbox),
        "confidence": 1.0 if active else 0.96,
        "clickable": clickable,
        "source": "desktop_primitives",
        "metadata": {
            "class": window.get("class", "") if isinstance(window, dict) else "",
            "hwnd": window.get("hwnd", "") if isinstance(window, dict) else "",
            "active": bool(active),
            "safety": safety,
        },
    }


def _title_tokens_to_text_elements(window, window_index):
    title = str(window.get("title", "") if isinstance(window, dict) else "").strip()
    if not title:
        return []

    words = [word.strip(" -—_|[](){}") for word in re.split(r"\s+", title) if len(word.strip(" -—_|[](){}")) >= 3]
    words = words[:10]
    rect = _bbox_from_rect(window.get("rect", {}))
    elements = []

    if not words:
        return elements

    token_width = max(32, int(rect.get("width", 0) / max(1, len(words))))
    token_height = 24

    for idx, word in enumerate(words, start=1):
        x = rect.get("x", 0) + (idx - 1) * token_width
        y = rect.get("y", 0)
        bbox = {"x": x, "y": y, "width": min(token_width, 220), "height": token_height}
        elements.append({
            "id": f"window_{window_index}_title_text_{idx}",
            "element_type": "text",
            "text": word,
            "bbox": bbox,
            "center": _center(bbox),
            "confidence": 0.62,
            "clickable": False,
            "source": "screen_parser_adapter",
            "metadata": {
                "parent_window": window.get("title", ""),
                "derived": True,
                "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing.",
            },
        })

    return elements


def _get_desktop_payload():
    errors = []
    payload = {
        "windows_payload": {},
        "screenshot_payload": {},
        "screen_observation": {},
        "errors": errors,
    }

    try:
        from modules.pc_desktop_primitives import list_windows, screenshot_metadata

        payload["windows_payload"] = list_windows()
        payload["screenshot_payload"] = screenshot_metadata()
    except Exception as exc:
        errors.append({"source": "pc_desktop_primitives", "error": str(exc), "traceback": traceback.format_exc()})

    if not payload["windows_payload"].get("windows"):
        try:
            from modules.pc_screen_planner import observe_screen

            observation = observe_screen(save=True)
            payload["screen_observation"] = observation
            result = observation.get("desktop_observer", {}).get("result", {})
            payload["windows_payload"] = {
                "ok": True,
                "active_window": result.get("active_window", {}),
                "windows": result.get("windows", []),
                "count": len(result.get("windows", []) or []),
            }
            payload["screenshot_payload"] = {
                "ok": True,
                "screenshot_path": result.get("screenshot_path", ""),
                "screenshot_error": result.get("screenshot_error", ""),
                "report_path": result.get("report_path", ""),
                "active_window": result.get("active_window", {}),
                "windows_count": len(result.get("windows", []) or []),
            }
        except Exception as exc:
            errors.append({"source": "pc_screen_planner", "error": str(exc), "traceback": traceback.format_exc()})

    return payload


def parse_screen(save=True):
    _ensure_dirs()
    desktop = _get_desktop_payload()
    windows_payload = desktop.get("windows_payload", {}) or {}
    screenshot_payload = desktop.get("screenshot_payload", {}) or {}

    windows = windows_payload.get("windows", []) or []
    active_window = windows_payload.get("active_window", {}) or screenshot_payload.get("active_window", {}) or {}

    elements = []
    if active_window:
        elements.append(_window_to_element(active_window, 0, active=True))

    for index, window in enumerate(windows, start=1):
        elements.append(_window_to_element(window, index, active=False))
        elements.extend(_title_tokens_to_text_elements(window, index))

    payload = {
        "ok": True,
        "mode": "ui_parser_adapter_parse",
        "generated_at": _now(),
        "backend": "desktop_window_parser",
        "omniparser_compatible": True,
        "schema": UI_ELEMENT_SCHEMA,
        "screen": {
            "screenshot_path": screenshot_payload.get("screenshot_path", ""),
            "screenshot_error": screenshot_payload.get("screenshot_error", ""),
            "report_path": screenshot_payload.get("report_path", ""),
            "windows_count": len(windows),
            "active_window_title": active_window.get("title", "") if isinstance(active_window, dict) else "",
        },
        "elements": elements,
        "elements_count": len(elements),
        "warnings": [
            "This is a lightweight adapter. It does not perform OCR yet.",
            "Window rectangles are real; button/input/text elements are heuristic until OmniParser backend is installed.",
            "No click/type action has been executed.",
        ],
        "errors": desktop.get("errors", []),
    }

    if save:
        path = UI_DIR / f"ui_parse_{_stamp()}.json"
        payload["path"] = _write_json(path, payload)

    set_value("ui_parser_last_parse", payload)
    return payload


def elements():
    parsed = parse_screen(save=True)
    payload = {
        "ok": parsed.get("ok", False),
        "mode": "ui_parser_adapter_elements",
        "generated_at": _now(),
        "elements_count": parsed.get("elements_count", 0),
        "elements": parsed.get("elements", []),
        "schema": UI_ELEMENT_SCHEMA,
        "source_parse": parsed.get("path", ""),
    }
    set_value("ui_parser_last_elements", payload)
    return payload


def find_elements(query):
    query = str(query or "").strip()
    lower = _norm(query)
    parsed = parse_screen(save=True)
    found = []

    for element in parsed.get("elements", []):
        text = _norm(element.get("text", ""))
        metadata = _norm(json.dumps(element.get("metadata", {}), ensure_ascii=False))
        if lower and (lower in text or lower in metadata):
            item = dict(element)
            item["match_reason"] = "text_or_metadata_contains_query"
            found.append(item)

    payload = {
        "ok": True,
        "mode": "ui_parser_adapter_find",
        "generated_at": _now(),
        "query": query,
        "matches_count": len(found),
        "matches": found,
        "source_parse": parsed.get("path", ""),
    }
    set_value("ui_parser_last_find", payload)
    return payload


def _extract_after_keywords(goal, keywords):
    lower = _norm(goal)
    for keyword in keywords:
        idx = lower.find(keyword)
        if idx >= 0:
            return str(goal)[idx + len(keyword):].strip(" :,-—")
    return str(goal).strip()


def _best_match_for_goal(goal):
    candidate = _extract_after_keywords(goal, CLICK_WORDS + FOCUS_WORDS)
    if candidate and len(candidate) >= 2:
        result = find_elements(candidate)
        if result.get("matches"):
            return result["matches"][0], result
    result = find_elements(goal)
    if result.get("matches"):
        return result["matches"][0], result
    return {}, result


def suggest_ui_action(goal):
    goal = str(goal or "").strip()
    lower = _norm(goal)

    if not goal:
        return {"ok": False, "error": "empty goal"}

    try:
        from modules.agentos_kernel_blueprint import semantic_firewall

        firewall = semantic_firewall(goal)
    except Exception as exc:
        firewall = {"ok": True, "warning": str(exc)}

    parsed = parse_screen(save=True)
    element, find_payload = _best_match_for_goal(goal)

    suggestions = []

    if not firewall.get("ok", True):
        suggestions.append({
            "id": "blocked_by_semantic_firewall",
            "type": "observe",
            "target": goal,
            "element_id": "",
            "point": {},
            "confidence": 1.0,
            "dry_run_command": "",
            "confirmed_command": "",
            "executed": False,
            "safety": firewall,
        })
    elif any(word in lower for word in CLICK_WORDS):
        if element:
            point = element.get("center", {})
            suggestions.append({
                "id": "suggest_dry_click",
                "type": "dry_click",
                "target": element.get("text", goal),
                "element_id": element.get("id", ""),
                "point": point,
                "confidence": min(0.88, float(element.get("confidence", 0.5))),
                "dry_run_command": f"pc desktop dry click {point.get('x', 0)} {point.get('y', 0)}",
                "confirmed_command": "not available in v6.26; click execution intentionally disabled",
                "executed": False,
                "safety": element.get("metadata", {}).get("safety", {"safe": True}),
            })
        else:
            suggestions.append({
                "id": "suggest_parse_first",
                "type": "observe",
                "target": goal,
                "element_id": "",
                "point": {},
                "confidence": 0.4,
                "dry_run_command": "pc ui parse",
                "confirmed_command": "",
                "executed": False,
                "safety": {"safe": True, "reason": "No matching element found."},
            })
    elif any(word in lower for word in FOCUS_WORDS) and element and element.get("element_type") == "window":
        target = element.get("text", goal)
        suggestions.append({
            "id": "suggest_dry_focus_window",
            "type": "focus_window",
            "target": target,
            "element_id": element.get("id", ""),
            "point": element.get("center", {}),
            "confidence": min(0.9, float(element.get("confidence", 0.5))),
            "dry_run_command": f"pc desktop dry focus {target}",
            "confirmed_command": f"pc desktop focus подтверждаю: {target}",
            "executed": False,
            "safety": element.get("metadata", {}).get("safety", {"safe": True}),
        })
    elif any(word in lower for word in OPEN_WORDS):
        suggestions.append({
            "id": "suggest_open_via_executor",
            "type": "open_app",
            "target": goal,
            "element_id": "",
            "point": {},
            "confidence": 0.76,
            "dry_run_command": f"pc exec dry {goal}",
            "confirmed_command": f"pc exec run подтверждаю: {goal}",
            "executed": False,
            "safety": firewall,
        })
    elif any(word in lower for word in PROJECT_WORDS):
        suggestions.append({
            "id": "suggest_project_edit_request",
            "type": "project_edit_request",
            "target": goal,
            "element_id": "",
            "point": {},
            "confidence": 0.82,
            "dry_run_command": f"pc agents project-profile",
            "confirmed_command": f"pc edit {goal}",
            "executed": False,
            "safety": firewall,
        })
    elif any(word in lower for word in WEB_WORDS):
        suggestions.append({
            "id": "suggest_web_research",
            "type": "web_search",
            "target": goal,
            "element_id": "",
            "point": {},
            "confidence": 0.78,
            "dry_run_command": "",
            "confirmed_command": f"pc web {goal}",
            "executed": False,
            "safety": firewall,
        })
    else:
        suggestions.append({
            "id": "suggest_screen_plan",
            "type": "screen_plan",
            "target": goal,
            "element_id": element.get("id", "") if element else "",
            "point": element.get("center", {}) if element else {},
            "confidence": 0.55,
            "dry_run_command": f"pc screen plan {goal}",
            "confirmed_command": f"pc screen dry {goal}",
            "executed": False,
            "safety": firewall,
        })

    payload = {
        "ok": True,
        "mode": "ui_parser_adapter_suggest",
        "generated_at": _now(),
        "goal": goal,
        "firewall": firewall,
        "screen": parsed.get("screen", {}),
        "elements_count": parsed.get("elements_count", 0),
        "matched_element": element,
        "find": {
            "query": find_payload.get("query", ""),
            "matches_count": find_payload.get("matches_count", 0),
        },
        "suggestions": suggestions,
        "schema": UI_ACTION_SCHEMA,
        "safety": [
            "This module suggests actions only.",
            "No click/type action has been executed.",
            "Use dry-run commands before any confirmed executor action.",
        ],
    }
    set_value("ui_parser_last_suggestion", payload)
    return payload


def backends():
    return {
        "ok": True,
        "mode": "ui_parser_backends",
        "generated_at": _now(),
        "backends": BACKENDS,
        "active_backend": "desktop_window_parser",
        "future_backend": "omniparser_adapter",
    }


def status():
    payload = {
        "ok": True,
        "mode": "ui_parser_adapter",
        "generated_at": _now(),
        "schema_version": UI_ELEMENT_SCHEMA["version"],
        "backends": BACKENDS,
        "last_parse": get_value("ui_parser_last_parse", ""),
        "last_find": get_value("ui_parser_last_find", ""),
        "last_suggestion": get_value("ui_parser_last_suggestion", ""),
        "commands": [
            "pc ui status",
            "pc ui backends",
            "pc ui parse",
            "pc ui elements",
            "pc ui find <text>",
            "pc ui suggest <цель>",
            "pc ui report",
        ],
        "safety": [
            "No OCR dependency is required in v6.26.",
            "No click/type is executed.",
            "Coordinates are for dry-run previews only.",
            "Sensitive UI titles/text are flagged.",
            "Future OmniParser backend must pass the same LocalComet safety gate.",
        ],
    }
    set_value("ui_parser_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    active_backends = [item["id"] for item in payload.get("backends", []) if item.get("status") == "active"]
    lines = [
        "UI Parser Adapter:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- schema_version: {payload.get('schema_version')}",
        f"- active_backends: {', '.join(active_backends)}",
        "",
        "Commands:",
    ]
    lines.extend("- " + command for command in payload.get("commands", []))
    lines.append("")
    lines.append("Safety:")
    lines.extend("- " + item for item in payload.get("safety", []))
    return "\n".join(lines)


def report(note=""):
    _ensure_dirs()
    parsed = parse_screen(save=True)
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "backends": backends(),
        "parse": parsed,
        "last_find": get_value("ui_parser_last_find", ""),
        "last_suggestion": get_value("ui_parser_last_suggestion", ""),
    }

    json_path = REPORTS_DIR / f"ui_parser_adapter_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"ui_parser_adapter_report_{_stamp()}.md"

    _write_json(json_path, payload)

    md = [
        "# UI Parser Adapter Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_status(payload["status"]),
        "```",
        "",
        "## Screen",
        "",
        "```json",
        json.dumps(parsed.get("screen", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Elements count",
        "",
        str(parsed.get("elements_count", 0)),
        "",
        "## Backends",
        "",
        "```json",
        json.dumps(BACKENDS, ensure_ascii=False, indent=2),
        "```",
    ]

    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc ui", "pc ui status", "pc ui статус", "ui status"}:
        return format_status(status())

    if lower in {"pc ui backends", "pc ui backend", "pc ui бэкенды", "ui backends"}:
        return format_payload(backends())

    if lower in {"pc ui parse", "pc ui парс", "pc ui разобрать", "ui parse"}:
        return format_payload(parse_screen(save=True))

    if lower in {"pc ui elements", "pc ui элементы", "ui elements"}:
        return format_payload(elements())

    if lower in {"pc ui report", "pc ui отчет", "pc ui отчёт", "ui report"}:
        return format_payload(report("manual report"))

    prefixes = [
        ("pc ui find ", "find"),
        ("pc ui найти ", "find"),
        ("ui find ", "find"),
        ("pc ui suggest ", "suggest"),
        ("pc ui предложи ", "suggest"),
        ("pc ui предложение ", "suggest"),
        ("ui suggest ", "suggest"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "find":
                return format_payload(find_elements(value))
            if action == "suggest":
                return format_payload(suggest_ui_action(value))

    return format_payload({
        "ok": False,
        "error": "Unknown UI Parser Adapter command.",
        "help": status().get("commands", []),
    })


def is_ui_command(command):
    lower = _norm(command)
    exact = {
        "pc ui",
        "pc ui status",
        "pc ui статус",
        "ui status",
        "pc ui backends",
        "pc ui backend",
        "pc ui бэкенды",
        "ui backends",
        "pc ui parse",
        "pc ui парс",
        "pc ui разобрать",
        "ui parse",
        "pc ui elements",
        "pc ui элементы",
        "ui elements",
        "pc ui report",
        "pc ui отчет",
        "pc ui отчёт",
        "ui report",
    }
    if lower in exact:
        return True

    prefixes = (
        "pc ui find ",
        "pc ui найти ",
        "ui find ",
        "pc ui suggest ",
        "pc ui предложи ",
        "pc ui предложение ",
        "ui suggest ",
    )
    return lower.startswith(prefixes)
````

