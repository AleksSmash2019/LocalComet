import json
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.llm import ask_llm
from core.state import get_value, set_value
from modules import browser_actions
from modules.browser import get_search_result_links, open_local_site, open_url, read_page, search
from modules.browser_autopilot import is_browser_task_safe, observe_browser_page
from modules.codegen import generate_site, improve_site


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "browser_super"

RESEARCH_SYSTEM = """
Ты Browser Research Agent уровня Perplexity/Comet.

Собери краткий, полезный ответ по источникам.
Пиши по-русски.
Не выдумывай факты.
Если данных мало, скажи это.
В конце добавь Sources с номерами и URL.
"""


PAGE_AUDIT_SYSTEM = """
Ты браузерный UX/research аналитик.

Проанализируй страницу по данным наблюдения.
Дай короткий список:
- что это за страница;
- ключевые элементы;
- полезные действия;
- риски/проблемы;
- следующий лучший шаг.
"""

PLATFORM_SITE_SYSTEM = """
Ты Browser Platform Site Operator.

Пользователь хочет сделать сайт на внешней платформе-конструкторе.
Подготовь практический build kit для работы в браузере:
- структура страниц;
- секции первого экрана и ниже;
- точные тексты для вставки;
- CTA;
- поля формы;
- SEO title/description;
- список изображений/ассетов;
- пошаговые действия на платформе.

Не проси пароли и оплату.
Не обещай публикацию без ручного подтверждения пользователя.
Пиши по-русски, кратко и прикладно.
"""

PLATFORM_URLS = {
    "tilda": "https://tilda.cc/",
    "тильда": "https://tilda.cc/",
    "тильде": "https://tilda.cc/",
    "тильду": "https://tilda.cc/",
    "tilde": "https://tilda.cc/",
    "wix": "https://www.wix.com/",
    "викс": "https://www.wix.com/",
    "webflow": "https://webflow.com/",
    "вебфлоу": "https://webflow.com/",
    "framer": "https://www.framer.com/",
    "фреймер": "https://www.framer.com/",
    "carrd": "https://carrd.co/",
    "readymag": "https://readymag.com/",
    "wordpress": "https://wordpress.com/",
    "wordpress.com": "https://wordpress.com/",
    "вордпресс": "https://wordpress.com/",
    "вордпресе": "https://wordpress.com/",
    "вордпрессе": "https://wordpress.com/",
    "notion": "https://www.notion.so/",
}


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_reports_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _short(value, limit=5000):
    text = str(value or "")

    if len(text) <= limit:
        return text

    return text[:limit] + "\n...[обрезано]"


def _clean_task(task):
    return str(task or "").strip(" \n\t:,-—")


def _strip_prefix(text, prefixes):
    source = _clean_task(text)
    lower = source.lower()

    for prefix in prefixes:
        if lower.startswith(prefix):
            return source[len(prefix):].strip(" :,-—")

    return source


def _extract_platform(task):
    text = _clean_task(task)
    lower = text.lower()

    for name in PLATFORM_URLS:
        if name in lower:
            return name

    markers = [
        "используй платформу",
        "на платформе",
        "через платформу",
        "use platform",
        "platform",
    ]

    for marker in markers:
        index = lower.find(marker)

        if index == -1:
            continue

        value = text[index + len(marker):].strip(" :,-—")
        value = re.split(r"[,.;\n]| и | with | для ", value, maxsplit=1)[0].strip()
        return value[:80] or "static html/css/js"

    if "react" in lower:
        return "React-style static prototype"

    if "tailwind" in lower:
        return "Tailwind-style static HTML/CSS"

    if "wordpress" in lower:
        return "WordPress-like landing prototype"

    return "static html/css/js"


def _platform_url(platform):
    key = str(platform or "").strip().lower()
    return PLATFORM_URLS.get(key, "")


def _is_external_platform(platform):
    return bool(_platform_url(platform))


def _research_query(task):
    return _strip_prefix(
        task,
        [
            "browser deep research",
            "browser research",
            "browser compare",
            "браузер исследуй",
            "браузер сравни",
            "исследуй",
            "изучи",
            "сравни",
            "найди",
        ],
    )


def _site_prompt(task):
    text = _strip_prefix(
        task,
        [
            "browser site workflow",
            "browser build site",
            "browser напиши сайт",
            "browser создай сайт",
            "напиши сайт",
            "создай сайт",
            "сделай сайт",
        ],
    )
    platform = _extract_platform(task)

    return (
        f"{text}\n\n"
        f"Platform / style target: {platform}\n"
        "Сделай локальный статический сайт с index.html, style.css и script.js. "
        "Дизайн должен быть готов к просмотру в браузере, с адаптивностью, формой/CTA если уместно."
    ).strip()


def classify_browser_super_task(task):
    lower = _clean_task(task).lower()
    site_request = any(marker in lower for marker in ["сайт", "лендинг", "site", "landing"])
    site_action = any(marker in lower for marker in ["сделай", "создай", "напиши", "собери", "построй", "разработай", "build", "create", "make"])
    platform = _extract_platform(task)

    if (
        any(marker in lower for marker in ["build site", "site workflow", "напиши сайт", "создай сайт", "сделай сайт", "используй платформу"])
        or (site_request and site_action and _is_external_platform(platform))
    ):
        return "site_workflow"

    if any(marker in lower for marker in ["page audit", "audit page", "аудит страницы", "проверь текущую страницу"]):
        return "page_audit"

    if any(marker in lower for marker in ["form map", "forms map", "карта форм", "поля формы", "form audit"]):
        return "form_map"

    if any(marker in lower for marker in ["compare", "сравни", "versus", " vs "]):
        return "compare_research"

    if any(marker in lower for marker in ["research", "deep research", "исследуй", "изучи", "перплексити", "perplexity"]):
        return "research"

    return "smart_browser"


def build_browser_super_plan(task, mode="dry_run", max_results=3):
    task = _clean_task(task)
    mode = "execute" if str(mode or "").lower() in ["execute", "run"] else "dry_run"
    kind = classify_browser_super_task(task)

    try:
        max_results = max(1, min(int(max_results or 3), 5))
    except Exception:
        max_results = 3

    safe, reason = is_browser_task_safe(task)

    if not safe:
        return {
            "task": task,
            "kind": kind,
            "mode": mode,
            "max_results": max_results,
            "blocked_reason": reason,
            "steps": [],
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    if kind == "site_workflow":
        platform = _extract_platform(task)

        if _is_external_platform(platform):
            steps = [
                {"action": "generate_platform_build_kit", "args": {"platform": platform}},
                {"action": "open_platform", "args": {"url": _platform_url(platform)}},
                {"action": "observe_platform_page"},
                {"action": "map_visible_forms"},
                {"action": "save_report"},
            ]
        else:
            steps = [
                {"action": "generate_local_site", "args": {"platform": platform}},
                {"action": "open_local_site"},
                {"action": "read_page"},
                {"action": "screenshot"},
                {"action": "save_report"},
            ]
    elif kind in ["research", "compare_research", "smart_browser"]:
        query = _research_query(task)
        steps = [
            {"action": "search", "args": {"query": query}},
            {"action": "collect_results", "args": {"limit": max_results}},
            {"action": "read_sources", "args": {"limit": max_results}},
            {"action": "synthesize_with_sources"},
            {"action": "save_report"},
        ]
    elif kind == "page_audit":
        steps = [
            {"action": "observe"},
            {"action": "summarize"},
            {"action": "extract_links"},
            {"action": "extract_inputs"},
            {"action": "screenshot"},
            {"action": "save_report"},
        ]
    elif kind == "form_map":
        steps = [
            {"action": "observe"},
            {"action": "extract_inputs"},
            {"action": "extract_buttons"},
            {"action": "save_report"},
        ]
    else:
        steps = [{"action": "observe"}, {"action": "save_report"}]

    return {
        "task": task,
        "kind": kind,
        "mode": mode,
        "max_results": max_results,
        "blocked_reason": "",
        "steps": steps,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def format_browser_super_plan(plan):
    lines = [
        "Browser Super Plan:",
        f"- task: {plan.get('task')}",
        f"- kind: {plan.get('kind')}",
        f"- mode: {plan.get('mode')}",
        f"- max_results: {plan.get('max_results')}",
        f"- blocked_reason: {plan.get('blocked_reason') or 'нет'}",
        "",
        "Steps:",
    ]

    for index, step in enumerate(plan.get("steps", []), start=1):
        lines.append(f"{index}. {step.get('action')} {step.get('args') or {}}")

    return "\n".join(lines)


def _report_path(kind):
    _ensure_reports_dir()
    safe_kind = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(kind or "browser_super")).strip("_")
    return REPORTS_DIR / f"{safe_kind}_{_stamp()}.md"


def _write_report(kind, title, task, sections, status="ok"):
    path = _report_path(kind)
    lines = [
        f"# {title}",
        "",
        f"- status: {status}",
        f"- task: {task}",
        f"- generated_at: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]

    for heading, body in sections:
        lines.extend([
            f"## {heading}",
            "",
            str(body or "нет"),
            "",
        ])

    path.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_browser_super_report", str(path))
    set_value("last_browser_super_status", status)
    set_value("last_browser_super_task", task)
    return path


def _synthesize_research(task, sources):
    source_text = []

    for index, item in enumerate(sources, start=1):
        source_text.append(
            f"[{index}] {item.get('title')}\nURL: {item.get('url')}\nTEXT:\n{_short(item.get('text'), 2200)}"
        )

    prompt = (
        f"Task:\n{task}\n\n"
        "Sources:\n"
        + "\n\n".join(source_text)
    )

    try:
        return ask_llm(RESEARCH_SYSTEM, prompt, max_tokens=2200, timeout=180, use_context=False)
    except Exception as exc:
        fallback = ["Не удалось синтезировать LLM-ответ, показываю собранные источники.", f"Ошибка: {exc}", ""]

        for index, item in enumerate(sources, start=1):
            fallback.append(f"[{index}] {item.get('title')} — {item.get('url')}")

        return "\n".join(fallback)


def _generate_platform_build_kit(task, platform):
    prompt = (
        f"Platform: {platform}\n"
        f"Task:\n{task}\n\n"
        "Сделай build kit так, чтобы пользователь мог быстро собрать сайт прямо в конструкторе."
    )

    try:
        return ask_llm(PLATFORM_SITE_SYSTEM, prompt, max_tokens=2400, timeout=180, use_context=False)
    except Exception as exc:
        return (
            f"LLM build kit failed: {exc}\n\n"
            "Fallback build kit:\n"
            "- Page: Главная\n"
            "- Sections: hero, преимущества, услуги/продукт, кейсы, форма заявки, контакты\n"
            "- CTA: Оставить заявку\n"
            "- Form fields: имя, телефон/email, комментарий\n"
            "- SEO: укажи название услуги, город/нишу и главный оффер."
        )


def run_platform_site_workflow(task):
    task = _clean_task(task)
    platform = _extract_platform(task)
    url = _platform_url(platform)

    if not url:
        return run_site_workflow(task, improve=False, force_local=True)

    safe, reason = is_browser_task_safe(task)

    if not safe:
        return f"STOP: Browser Platform Workflow blocked.\nПричина: {reason}"

    build_kit = _generate_platform_build_kit(task, platform)
    open_result = open_url(url)

    try:
        observation = observe_browser_page()
    except Exception as exc:
        observation = f"Observe failed: {exc}"

    try:
        inputs = browser_actions.extract_inputs(limit=30)
    except Exception as exc:
        inputs = f"Inputs extraction failed: {exc}"

    try:
        screenshot = browser_actions.screenshot_page()
    except Exception as exc:
        screenshot = f"Screenshot failed: {exc}"

    next_steps = (
        "Safe next steps:\n"
        "1. Если платформа просит логин/пароль — войди вручную.\n"
        "2. Потом выполни: browser form map\n"
        "3. Для вставки текстов используй build kit из отчёта.\n"
        "4. Публикацию, оплату, покупку домена и ввод персональных данных подтверждай вручную.\n"
        "5. Для продолжения на открытой странице: browser page audit или browser click <текст>."
    )

    report = _write_report(
        "browser_platform_site_workflow",
        "Browser Platform Site Workflow",
        task,
        [
            ("Platform", f"{platform}\n{url}"),
            ("Build Kit", build_kit),
            ("Open result", open_result),
            ("Observation", f"```json\n{observation}\n```"),
            ("Visible forms / controls", f"```text\n{inputs}\n```"),
            ("Screenshot", screenshot),
            ("Next safe actions", next_steps),
        ],
    )

    set_value("last_browser_platform", platform)
    set_value("last_browser_platform_url", url)
    set_value("last_browser_platform_site_workflow_report", str(report))

    return (
        "Browser Platform Site Workflow готов.\n"
        f"Platform: {platform}\n"
        f"URL: {url}\n"
        f"Report: {report}\n\n"
        f"{next_steps}"
    )


def run_youtube_search(query):
    query = _clean_task(query)

    if not query:
        open_result = open_url("https://www.youtube.com/")
        return f"YouTube открыт.\n{open_result}"

    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    open_result = open_url(url)

    try:
        observation = observe_browser_page()
    except Exception as exc:
        observation = f"Observe failed: {exc}"

    try:
        links = browser_actions.extract_links(limit=20)
    except Exception as exc:
        links = f"Links extraction failed: {exc}"

    try:
        screenshot = browser_actions.screenshot_page()
    except Exception as exc:
        screenshot = f"Screenshot failed: {exc}"

    report = _write_report(
        "browser_youtube_search",
        "Browser YouTube Search",
        query,
        [
            ("Open result", open_result),
            ("Observation", f"```json\n{observation}\n```"),
            ("Links", f"```text\n{links}\n```"),
            ("Screenshot", screenshot),
            ("Next actions", "Можно продолжить: browser click <название видео> или browser page audit."),
        ],
    )

    set_value("last_browser_youtube_query", query)
    set_value("last_browser_youtube_report", str(report))

    return (
        "YouTube search готов.\n"
        f"Query: {query}\n"
        f"URL: {url}\n"
        f"Report: {report}\n\n"
        "Дальше можно: browser click <название видео>"
    )


def run_browser_research(task, max_results=3):
    task = _clean_task(task)
    query = _research_query(task)

    if not query:
        return "Browser Research: пустой запрос."

    safe, reason = is_browser_task_safe(task)

    if not safe:
        return f"STOP: Browser Research blocked.\nПричина: {reason}"

    search_result = search(query)
    links = get_search_result_links(limit=max_results)
    sources = []

    for link in links[:max_results]:
        url = link.get("url", "")

        try:
            open_url(url)
            page_text = read_page(limit=4500)
        except Exception as exc:
            page_text = f"Не удалось прочитать источник: {exc}"

        sources.append({
            "title": link.get("title", ""),
            "url": url,
            "text": page_text,
        })

    answer = _synthesize_research(task, sources)
    report = _write_report(
        "browser_research",
        "Browser Research Report",
        task,
        [
            ("Search", search_result),
            ("Answer", answer),
            ("Sources", "\n".join(f"- [{i}] {item.get('title')} — {item.get('url')}" for i, item in enumerate(sources, start=1))),
        ],
        status="ok" if sources else "empty",
    )

    set_value("last_browser_research_report", str(report))
    set_value("last_browser_research_query", query)

    return (
        "Browser Research завершен.\n"
        f"Query: {query}\n"
        f"Sources: {len(sources)}\n"
        f"Report: {report}\n\n"
        f"{_short(answer, 2500)}"
    )


def run_page_audit(task="current page"):
    task = _clean_task(task) or "current page"
    observation = observe_browser_page()
    summary = browser_actions.summarize_page()
    links = browser_actions.extract_links(limit=15)
    inputs = browser_actions.extract_inputs(limit=20)
    screenshot = browser_actions.screenshot_page()

    prompt = (
        f"Task:\n{task}\n\n"
        f"Observation:\n{observation}\n\n"
        f"Summary:\n{summary}\n\n"
        f"Links:\n{links}\n\n"
        f"Inputs:\n{inputs}"
    )

    try:
        audit = ask_llm(PAGE_AUDIT_SYSTEM, prompt, max_tokens=1200, timeout=120, use_context=False)
    except Exception as exc:
        audit = f"LLM audit failed: {exc}\n\nSummary:\n{summary}"

    report = _write_report(
        "browser_page_audit",
        "Browser Page Audit",
        task,
        [
            ("Audit", audit),
            ("Observation", f"```json\n{observation}\n```"),
            ("Links", f"```text\n{links}\n```"),
            ("Inputs", f"```text\n{inputs}\n```"),
            ("Screenshot", screenshot),
        ],
    )

    set_value("last_browser_page_audit_report", str(report))
    return f"Browser Page Audit готов.\nReport: {report}\n\n{_short(audit, 2200)}"


def run_form_map(task="current page"):
    task = _clean_task(task) or "current page"
    observation = observe_browser_page()
    inputs = browser_actions.extract_inputs(limit=40)
    buttons = "Используй browser observe/page audit для кнопок, если нужно больше контекста."

    report = _write_report(
        "browser_form_map",
        "Browser Form Map",
        task,
        [
            ("Inputs", f"```text\n{inputs}\n```"),
            ("Observation", f"```json\n{observation}\n```"),
            ("Buttons / next actions", buttons),
        ],
    )

    set_value("last_browser_form_map_report", str(report))
    return f"Browser Form Map готов.\nReport: {report}\n\nInputs:\n{_short(inputs, 2200)}"


def run_site_workflow(task, improve=False, force_local=False):
    task = _clean_task(task)
    prompt = _site_prompt(task)
    platform = _extract_platform(task)

    if _is_external_platform(platform) and not force_local:
        return run_platform_site_workflow(task)

    safe, reason = is_browser_task_safe(task)

    if not safe:
        return f"STOP: Browser Site Workflow blocked.\nПричина: {reason}"

    site = generate_site(prompt)
    folder = site.get("folder", "")
    set_value("last_site", folder)

    open_result = open_local_site(folder)
    read_result = read_page(limit=2500)
    screenshot = browser_actions.screenshot_page()
    improve_result = "не запускалось"

    if improve:
        try:
            improved = improve_site(folder)
            improve_result = json.dumps(improved, ensure_ascii=False, indent=2)
            open_result = open_local_site(folder)
            read_result = read_page(limit=2500)
            screenshot = browser_actions.screenshot_page()
        except Exception as exc:
            improve_result = f"Improve failed: {exc}"

    report = _write_report(
        "browser_site_workflow",
        "Browser Site Workflow",
        task,
        [
            ("Platform", platform),
            ("Generated files", "\n".join(f"- {path}" for path in site.get("created", []))),
            ("Open result", open_result),
            ("Read result", f"```text\n{_short(read_result, 2500)}\n```"),
            ("Improve result", improve_result),
            ("Screenshot", screenshot),
        ],
    )

    set_value("last_browser_site_workflow_report", str(report))
    return (
        "Browser Site Workflow готов.\n"
        f"Platform: {platform}\n"
        f"Site folder: {folder}\n"
        f"Report: {report}\n\n"
        f"{open_result}"
    )


def run_browser_super(task, mode="execute", max_results=3):
    plan = build_browser_super_plan(task, mode=mode, max_results=max_results)

    if plan.get("blocked_reason"):
        return f"STOP: Browser Super blocked.\nПричина: {plan.get('blocked_reason')}"

    if plan.get("mode") == "dry_run":
        report = _write_report(
            "browser_super_plan",
            "Browser Super Plan",
            plan.get("task", ""),
            [("Plan", f"```json\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n```")],
            status="dry_run",
        )
        return f"{format_browser_super_plan(plan)}\n\nReport: {report}"

    kind = plan.get("kind")

    if kind in ["research", "compare_research", "smart_browser"]:
        return run_browser_research(plan.get("task", ""), max_results=plan.get("max_results", 3))

    if kind == "page_audit":
        return run_page_audit(plan.get("task", ""))

    if kind == "form_map":
        return run_form_map(plan.get("task", ""))

    if kind == "site_workflow":
        return run_site_workflow(plan.get("task", ""), improve="улучши" in plan.get("task", "").lower())

    return run_page_audit(plan.get("task", ""))


def latest_browser_super_report():
    path = str(get_value("last_browser_super_report", "") or "").strip()

    if path:
        candidate = Path(path)

        if candidate.exists() and candidate.is_file():
            return candidate

    if not REPORTS_DIR.exists():
        return None

    reports = [path for path in REPORTS_DIR.glob("*.md") if path.is_file()]

    if not reports:
        return None

    return max(reports, key=lambda path: path.stat().st_mtime)
