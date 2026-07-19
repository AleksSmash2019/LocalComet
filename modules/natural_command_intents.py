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
