import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import get_value, set_value
from modules import browser_actions
from modules.browser import click_first_link, get_active_page_for_actions, search


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "browser_autopilot"

SAFETY_MARKERS = [
    "оплатить",
    "купить",
    "оформить заказ",
    "добавить в корзину",
    "корзину",
    "ставка",
    "поставить",
    "банк",
    "банков",
    "кредит",
    "пароль",
    "логин",
    "войти",
    "зарегистрироваться",
    "2fa",
    "sms",
    "удалить аккаунт",
    "отправь деньги",
    "checkout",
    "pay",
    "buy",
    "order",
    "cart",
    "bet",
    "casino",
    "bank",
    "password",
    "login",
    "sign in",
    "sign up",
    "delete account",
    "delete my account",
    "delete your account",
    "remove my account",
    "close my account",
    "deactivate account",
    "account deletion",
    "удалить мой аккаунт",
    "удалить учетную запись",
    "удалить учётную запись",
    "удалить профиль",
]


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_reports_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _report_path():
    _ensure_reports_dir()
    base = REPORTS_DIR / f"browser_autopilot_{_stamp()}.md"

    if not base.exists():
        return base

    for index in range(1, 100):
        candidate = REPORTS_DIR / f"browser_autopilot_{_stamp()}_{index:02d}.md"

        if not candidate.exists():
            return candidate

    return base


def _short(text, limit=3000):
    value = str(text or "")

    if len(value) <= limit:
        return value

    return value[:limit] + "\n...[обрезано]"


def _contains_any(text, markers):
    lower = str(text or "").lower()
    return any(marker in lower for marker in markers)


def is_browser_task_safe(task: str):
    lower = str(task or "").lower()

    for marker in SAFETY_MARKERS:
        if marker in lower:
            return False, f"Задача заблокирована safety guard: найден опасный маркер '{marker}'."

    return True, ""


def _clean_query(task: str):
    text = str(task or "").strip()
    lower = text.lower()

    prefixes = [
        "найди информацию про",
        "найди информацию о",
        "найди",
        "поиск",
        "исследуй",
        "изучи",
        "сравни",
        "на текущем сайте найди",
        "введи",
        "найди поле поиска и введи",
    ]

    for prefix in prefixes:
        if lower.startswith(prefix):
            text = text[len(prefix):].strip(" :,-")
            break

    remove_parts = [
        "и сделай отчет",
        "и сделай отчёт",
        "и собери ссылки",
        "и собери ссылку",
        "и сравни первые результаты",
        "сделай отчет",
        "сделай отчёт",
        "собери ссылки",
        "собери результаты",
    ]

    lower = text.lower()

    for part in remove_parts:
        index = lower.find(part)

        if index != -1:
            text = text[:index].strip(" :,-")
            lower = text.lower()

    return text.strip() or str(task or "").strip()


def _click_target(task: str):
    text = str(task or "").strip()
    lower = text.lower()

    markers = [
        "нажми ссылку",
        "кликни по",
        "кликни",
        "нажми",
        "открой",
    ]

    for marker in markers:
        if lower.startswith(marker):
            return text[len(marker):].strip(" :,-")

    return text


def _step(action, args=None):
    return {"action": action, "args": args or {}}


def _base_plan(task, mode, max_steps, steps, blocked_reason=""):
    return {
        "task": str(task or "").strip(),
        "mode": mode,
        "max_steps": int(max_steps),
        "steps": steps[: int(max_steps)],
        "blocked_reason": blocked_reason,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_browser_autopilot_plan(task: str, mode="dry_run", max_steps=8):
    task = str(task or "").strip()
    mode = "execute" if str(mode or "").lower() == "execute" else "dry_run"

    try:
        max_steps = max(1, min(int(max_steps or 8), 20))
    except Exception:
        max_steps = 8

    safe, reason = is_browser_task_safe(task)

    if not safe:
        return _base_plan(task, mode, max_steps, [], blocked_reason=reason)

    lower = task.lower()
    query = _clean_query(task)

    if "открой первый результат" in lower or "open first" in lower:
        steps = [
            _step("observe"),
            _step("open_first"),
            _step("summarize"),
            _step("screenshot"),
            _step("save_report"),
        ]
        return _base_plan(task, mode, max_steps, steps)

    if (
        "на текущем сайте" in lower
        or "поиск сайта" in lower
        or "поле поиска" in lower
        or lower.startswith("введи ")
    ):
        steps = [
            _step("observe"),
            _step("inputs"),
            _step("fill_search_field", {"query": query}),
            _step("press_enter"),
            _step("wait", {"ms": 1500}),
            _step("summarize"),
            _step("screenshot"),
            _step("save_report"),
        ]
        return _base_plan(task, mode, max_steps, steps)

    if _contains_any(lower, ["нажми", "кликни", "click "]):
        steps = [
            _step("observe"),
            _step("click_text", {"text": _click_target(task)}),
            _step("wait", {"ms": 1000}),
            _step("summarize"),
            _step("screenshot"),
            _step("save_report"),
        ]
        return _base_plan(task, mode, max_steps, steps)

    if _contains_any(lower, ["собери", "извлеки", "таблиц", "цены", "цену", "карточк", "заголовки"]):
        steps = [
            _step("observe"),
            _step("extract_links"),
            _step("extract_cards_or_text_blocks"),
            _step("screenshot"),
            _step("save_report"),
        ]
        return _base_plan(task, mode, max_steps, steps)

    if _contains_any(lower, ["текущ", "страниц"]) and "найди" not in lower:
        steps = [
            _step("observe"),
            _step("summarize"),
            _step("extract_links"),
            _step("extract_inputs"),
            _step("screenshot"),
            _step("save_report"),
        ]
        return _base_plan(task, mode, max_steps, steps)

    if _contains_any(lower, ["найди", "поиск", "изучи", "исследуй", "сравни"]):
        steps = [
            _step("search", {"query": query}),
            _step("open_first"),
            _step("summarize"),
            _step("extract_links"),
            _step("screenshot"),
            _step("save_report"),
        ]
        return _base_plan(task, mode, max_steps, steps)

    steps = [
        _step("observe"),
        _step("summarize"),
        _step("extract_links"),
        _step("extract_inputs"),
        _step("screenshot"),
        _step("save_report"),
    ]
    return _base_plan(task, mode, max_steps, steps)


def _safe_eval(page, script, default):
    try:
        return page.locator("body").evaluate(script)
    except Exception:
        return default


def observe_browser_page():
    try:
        page = get_active_page_for_actions()
        current_url = str(page.url or "")
        title = str(page.title() or "")

        headings = page.locator("h1, h2").evaluate_all(
            "els => els.slice(0, 10).map(el => (el.innerText || '').trim()).filter(Boolean)"
        )
        links = page.locator("a").evaluate_all(
            "els => els.slice(0, 10).map(a => ({text:(a.innerText||a.textContent||'').trim().slice(0,100), href:a.href||''}))"
        )
        inputs = page.locator("input, textarea, select, button").evaluate_all(
            "els => els.slice(0, 10).map(el => ({tag:el.tagName.toLowerCase(), type:el.getAttribute('type')||'', placeholder:el.getAttribute('placeholder')||'', name:el.getAttribute('name')||'', text:(el.innerText||el.value||'').trim().slice(0,80)}))"
        )
        body_text = _safe_eval(page, "body => (body.innerText || '').trim().slice(0, 1200)", "")

        observation = {
            "current_url": current_url,
            "title": title,
            "headings": headings,
            "visible_links": links,
            "inputs": inputs,
            "short_text": body_text,
        }

        return json.dumps(observation, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Browser observe failed: {e}"


def _extract_text_blocks():
    try:
        page = get_active_page_for_actions()
        blocks = page.locator("article, section, main, li, .card, [class*='card'], [class*='product']").evaluate_all(
            """
            els => els.slice(0, 20).map(el => (el.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 300)).filter(Boolean)
            """
        )

        if not blocks:
            text = page.locator("body").inner_text(timeout=5000)
            blocks = [line.strip() for line in text.splitlines() if len(line.strip()) > 20][:20]

        return json.dumps(blocks, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Не удалось извлечь текстовые блоки: {e}"


def _fill_search_field(query):
    query = str(query or "").strip()

    if not query:
        return "STOP: нечего вводить в поле поиска."

    attempts = []

    for label in ["Search", "Поиск", "search"]:
        result = browser_actions.fill_by_label(label, query)
        attempts.append(result)
        text = str(result)

        if "Поле заполнено" in text and "не найдено" not in text.lower():
            return text

    return attempts[-1] if attempts else "STOP: поле поиска не найдено."


def _step_failed(result):
    lower = str(result or "").lower()
    return any(marker in lower for marker in ["stop:", "failed", "ошибка", "не удалось", "не найдено"])


def _execute_step(step):
    action = str(step.get("action", "") or "").strip()
    args = step.get("args", {}) or {}

    if action == "observe":
        return observe_browser_page()

    if action == "search":
        return search(args.get("query", ""))

    if action == "open_first":
        return click_first_link()

    if action == "summarize":
        return browser_actions.summarize_page()

    if action in ["links", "extract_links"]:
        return browser_actions.extract_links()

    if action in ["inputs", "extract_inputs"]:
        return browser_actions.extract_inputs()

    if action == "click_text":
        return browser_actions.click_by_text(args.get("text", ""))

    if action == "fill_search_field":
        return _fill_search_field(args.get("query", ""))

    if action == "press_enter":
        return browser_actions.press_key("Enter")

    if action == "wait":
        return browser_actions.wait_page(args.get("ms", 1000))

    if action == "screenshot":
        return browser_actions.screenshot_page()

    if action == "extract_cards_or_text_blocks":
        return _extract_text_blocks()

    if action == "save_report":
        return "Report will be saved after autopilot completes."

    return f"Unknown browser autopilot step: {action}"


def _extract_screenshot_path(result):
    for line in str(result or "").splitlines():
        clean = line.strip()

        if clean.lower().endswith(".png") and ":" in clean:
            return clean

        if clean.lower().endswith(".png"):
            return clean

    return ""


def _save_report(plan, step_results, observations, screenshots, errors, final_result):
    path = _report_path()

    lines = [
        "# Browser Autopilot Report",
        "",
        "## Summary",
        "",
        f"- status: {final_result.get('status')}",
        f"- created_at: {plan.get('created_at')}",
        f"- steps_planned: {len(plan.get('steps', []))}",
        f"- steps_run: {len(step_results)}",
        "",
        "## Task",
        "",
        str(plan.get("task") or ""),
        "",
        "## Mode",
        "",
        str(plan.get("mode") or ""),
        "",
        "## Safety",
        "",
        f"- blocked_reason: {plan.get('blocked_reason') or 'нет'}",
        "",
        "## Plan",
        "",
        "```json",
        json.dumps(plan, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Step results",
        "",
    ]

    for item in step_results:
        lines.extend([
            f"### Step {item.get('index')}: {item.get('action')}",
            "",
            "```text",
            _short(item.get("result"), 4000),
            "```",
            "",
        ])

    lines.extend(["## Page observations", ""])

    for item in observations:
        lines.extend([
            f"### Observation after step {item.get('step')}",
            "",
            "```text",
            _short(item.get("observation"), 2500),
            "```",
            "",
        ])

    lines.extend(["## Screenshots", ""])

    if screenshots:
        lines.extend(f"- {path}" for path in screenshots)
    else:
        lines.append("- нет")

    lines.extend(["", "## Errors / recovery", ""])

    if errors:
        lines.extend(f"- {item}" for item in errors)
    else:
        lines.append("- нет")

    lines.extend([
        "",
        "## Final result",
        "",
        json.dumps(final_result, ensure_ascii=False, indent=2),
        "",
        "## Next suggested actions",
        "",
        "- Проверь report и screenshot.",
        "- Для опасных действий выполни ручное подтверждение вне Autopilot.",
        "- Если шаг не сработал, попробуй browser observe или уточни задачу.",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _remember_report(path, status, plan):
    set_value("last_browser_autopilot_report", str(path))
    set_value("last_browser_autopilot_status", status)
    set_value("last_browser_autopilot_task", plan.get("task", ""))
    set_value("last_browser_autopilot_mode", plan.get("mode", ""))


def run_browser_autopilot(task: str, mode="execute", max_steps=8):
    mode = "dry_run" if str(mode or "").lower() == "dry_run" else "execute"
    plan = build_browser_autopilot_plan(task, mode=mode, max_steps=max_steps)
    step_results = []
    observations = []
    screenshots = []
    errors = []

    if plan.get("blocked_reason"):
        final = {"status": "blocked", "reason": plan.get("blocked_reason")}
        report_path = _save_report(plan, step_results, observations, screenshots, errors, final)
        _remember_report(report_path, "blocked", plan)
        return f"STOP: Browser Autopilot blocked.\nПричина: {plan.get('blocked_reason')}\nReport: {report_path}"

    if mode == "dry_run":
        final = {"status": "dry_run", "message": "План построен, браузерные действия не выполнялись."}
        report_path = _save_report(plan, step_results, observations, screenshots, errors, final)
        _remember_report(report_path, "dry_run", plan)
        return (
            "Browser Autopilot dry-run завершен.\n"
            f"Steps: {len(plan.get('steps', []))}\n"
            f"Report: {report_path}"
        )

    for index, step in enumerate(plan.get("steps", [])[: int(plan.get("max_steps", 8))], start=1):
        action = step.get("action", "unknown")

        try:
            result = _execute_step(step)

            if _step_failed(result) and action not in ["save_report"]:
                errors.append(f"Step {index} failed, retry after wait: {action}")
                browser_actions.wait_page(1000)
                retry_result = _execute_step(step)
                result = str(result) + "\n\n--- RETRY ---\n" + str(retry_result)

                if _step_failed(retry_result):
                    fallback = browser_actions.screenshot_page()
                    errors.append(f"Step {index} still failed, screenshot fallback executed.")
                    result = str(result) + "\n\n--- FALLBACK SCREENSHOT ---\n" + str(fallback)

            screenshot_path = _extract_screenshot_path(result)

            if screenshot_path:
                screenshots.append(screenshot_path)

            step_results.append({
                "index": index,
                "action": action,
                "result": str(result),
            })

            if action not in ["observe", "save_report"]:
                observations.append({
                    "step": index,
                    "observation": observe_browser_page(),
                })

        except Exception as e:
            errors.append(f"Step {index} exception in {action}: {e}")
            step_results.append({
                "index": index,
                "action": action,
                "result": f"ERROR: {e}",
            })
            break

    status = "failed" if errors else "success"
    final = {"status": status, "errors": errors[-5:]}
    report_path = _save_report(plan, step_results, observations, screenshots, errors, final)
    _remember_report(report_path, status, plan)

    return (
        f"Browser Autopilot {status}.\n"
        f"Task: {plan.get('task')}\n"
        f"Steps run: {len(step_results)}/{len(plan.get('steps', []))}\n"
        f"Report: {report_path}"
    )


def format_browser_autopilot_plan(plan):
    lines = [
        "Browser Autopilot Plan:",
        f"- task: {plan.get('task')}",
        f"- mode: {plan.get('mode')}",
        f"- max_steps: {plan.get('max_steps')}",
        f"- blocked_reason: {plan.get('blocked_reason') or 'нет'}",
        "",
        "Steps:",
    ]

    for index, step in enumerate(plan.get("steps", []), start=1):
        lines.append(f"{index}. {step.get('action')} {step.get('args') or {}}")

    return "\n".join(lines)


def latest_browser_autopilot_report():
    path = str(get_value("last_browser_autopilot_report", "") or "").strip()

    if path:
        p = Path(path)

        if p.exists() and p.is_file():
            return p

    if not REPORTS_DIR.exists():
        return None

    reports = [p for p in REPORTS_DIR.glob("browser_autopilot_*.md") if p.is_file()]

    if not reports:
        return None

    return max(reports, key=lambda p: p.stat().st_mtime)
