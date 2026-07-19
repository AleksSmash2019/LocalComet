import re
import subprocess
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value, get_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
WINDOWS_DIR = PROJECTS_DIR / "Windows"


def _ensure_reports_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(text, limit: int = 2500):
    value = str(text or "")

    if len(value) <= limit:
        return value

    return value[:limit] + "\n\n...[обрезано]"


def _has_bad_result(text: str):
    value = str(text or "").lower()

    bad_markers = [
        "неизвестное действие",
        "не удалось",
        "error:",
        "error",
        "ошибка:",
        "ошибка",
        "traceback",
        "unknown",
    ]

    return any(marker in value for marker in bad_markers)


def _extract_limit(text: str, default: int = 3, maximum: int = 5):
    for token in str(text or "").replace(",", " ").split():
        digits = "".join(ch for ch in token if ch.isdigit())

        if digits:
            try:
                return max(1, min(int(digits), maximum))
            except Exception:
                pass

    return default


def _strip_prefix(text: str, prefixes):
    source = str(text or "").strip()
    lower = source.lower()

    for prefix in prefixes:
        if lower.startswith(prefix):
            source = source[len(prefix):].strip(" :,-—")
            break

    return source


def _clean_browser_goal(goal: str):
    text = str(goal or "").strip()

    text = _strip_prefix(
        text,
        [
            "multi task",
            "browser task",
            "browser batch",
            "browser compare",
            "browser report",
            "браузерная задача",
            "браузер задача",
            "комплексная задача",
            "мульти задача",
        ],
    )

    lower = text.lower()

    start_words = [
        "найди ",
        "найти ",
        "поищи ",
        "search ",
        "find ",
    ]

    for word in start_words:
        if lower.startswith(word):
            text = text[len(word):].strip()
            lower = text.lower()
            break

    instruction_markers = [
        ", прочитай",
        " и прочитай",
        ", прочти",
        " и прочти",
        ", открой",
        " и открой",
        ", открыть",
        " и открыть",
        ", сохрани",
        " и сохрани",
        ", сделай отчет",
        " и сделай отчет",
        ", сделай отчёт",
        " и сделай отчёт",
        ", открой папку",
        " и открой папку",
        " прочитай первые",
        " прочти первые",
        " первые 3 результата",
        " первые три результата",
    ]

    lower = text.lower()
    cut_indexes = []

    for marker in instruction_markers:
        index = lower.find(marker)

        if index != -1:
            cut_indexes.append(index)

    if cut_indexes:
        text = text[:min(cut_indexes)].strip(" :,-—")

    cleanup_phrases = [
        "и прочитай",
        "и прочти",
        "прочитай",
        "прочти",
        "сравни",
        "сделай отчет",
        "сделай отчёт",
        "сохрани отчет",
        "сохрани отчёт",
    ]

    for phrase in cleanup_phrases:
        if text.lower().endswith(phrase):
            text = text[: -len(phrase)].strip(" :,-—")

    return text.strip(" :,-—") or str(goal or "").strip()


def _resolve_read_first_query(goal: str):
    raw = str(goal or "").strip()
    lower = raw.lower()

    raw = _strip_prefix(
        raw,
        [
            "browser read first",
            "браузер прочитай первые",
            "прочитай первые результаты",
        ],
    ).strip(" :,-—")

    # Важный фикс v5.36:
    # browser read first 3 раньше превращался в поисковый запрос "3".
    # Если после команды осталась только цифра/лимит, берем last_browser_query.
    only_digits = "".join(ch for ch in raw if ch.isdigit()) == raw.replace(" ", "") and bool(raw.strip())

    if not raw or only_digits or lower in ["3", "first 3", "первые 3", "первые три"]:
        return str(get_value("last_browser_query", "") or "").strip()

    return _clean_browser_goal(raw)


def _split_goal_parts(goal: str):
    text = str(goal or "").strip()
    raw_parts = re.split(r"\s*,\s*|\s*;\s*|\s+\и\s+", text)

    return [part.strip(" :,-—") for part in raw_parts if part.strip(" :,-—")]


def _folder_steps_from_goal(goal: str):
    parts = _split_goal_parts(goal)
    steps = []
    folder_hits = []

    for part in parts:
        lower = part.lower()

        if "отчет" in lower or "отчёт" in lower or "reports" in lower:
            folder_hits.append(part)
            steps.append({
                "name": "open reports folder",
                "func": lambda: _open_folder(REPORTS_DIR),
            })
            continue

        if "проект" in lower or "projects" in lower:
            folder_hits.append(part)
            steps.append({
                "name": "open projects folder",
                "func": lambda: _open_folder(PROJECTS_DIR),
            })
            continue

        if "windows" in lower or "виндовс" in lower:
            folder_hits.append(part)
            steps.append({
                "name": "open windows folder",
                "func": lambda: _open_folder(WINDOWS_DIR),
            })
            continue

    return steps, folder_hits


def _strip_folder_commands(goal: str):
    parts = _split_goal_parts(goal)
    keep = []

    for part in parts:
        lower = part.lower()

        is_folder_part = (
            "папк" in lower
            and (
                "отчет" in lower
                or "отчёт" in lower
                or "reports" in lower
                or "проект" in lower
                or "projects" in lower
                or "windows" in lower
                or "виндовс" in lower
            )
        )

        if is_folder_part:
            continue

        keep.append(part)

    return ", ".join(keep).strip(" :,-—")


def _split_multi_goal(goal: str):
    text = str(goal or "").strip()
    browser_query = ""

    lower = text.lower()

    if any(word in lower for word in ["найди", "поиск", "browser", "браузер", "сайт", "страниц", "прочитай", "прочти"]):
        browser_query = _clean_browser_goal(text)

    pc_goal_parts = []
    folder_steps, folder_hits = _folder_steps_from_goal(text)

    if folder_hits:
        # Для PC-части берем только локальные инструкции, а не весь поисковый запрос.
        pc_goal_parts.extend(folder_hits)

    non_folder = _strip_folder_commands(text)

    # Если задача не является браузерной, можно отправить локальную часть целиком.
    if not browser_query and non_folder:
        pc_goal_parts.append(non_folder)

    # Если явно просили блокнот/написать — добавим эти части, но без browser-поиска.
    for part in _split_goal_parts(text):
        lower_part = part.lower()

        if any(word in lower_part for word in ["блокнот", "notepad", "напиши", "напечатай", "введи", "набери", "калькулятор", "calc"]):
            if part not in pc_goal_parts:
                pc_goal_parts.append(part)

    pc_goal = ", ".join(pc_goal_parts).strip(" :,-—")
    return browser_query, pc_goal


def _dev_task_files_hint(goal: str):
    lower = str(goal or "").lower()

    if any(word in lower for word in [
        "multi task",
        "browser batch",
        "pc batch",
        "task status",
        "task report",
        "automation",
        "автоматизац",
        "direct",
        "after patch",
        "dev task",
        "browser task",
        "pc task",
        "sequential",
        "runner",
        "parser",
        "парсер",
        "цепочк",
    ]):
        return [
            "modules/automation_center.py",
            "agents/automation_agent.py",
            "modules/browser.py",
            "agents/browser_agent.py",
            "agents/windows_agent.py",
            "agents/workspace_agent.py",
            "agents/file_agent.py",
            "core/router.py",
            "core/planner.py",
            "core/executor.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/stability_test.py",
        ]

    if any(word in lower for word in [
        "browser",
        "браузер",
        "вклад",
        "tab",
        "duckduckgo",
        "страниц",
        "читать сайт",
        "читать страницу",
    ]):
        return [
            "modules/browser.py",
            "agents/browser_agent.py",
            "modules/automation_center.py",
            "agents/automation_agent.py",
            "core/router.py",
            "core/planner.py",
            "core/executor.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/stability_test.py",
        ]

    if any(word in lower for word in [
        "relay",
        "релей",
        "chatgpt",
        "request",
        "response",
        "snapshot",
    ]):
        return [
            "modules/chatgpt_relay.py",
            "agents/chatgpt_relay_agent.py",
            "modules/self_edit.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/history_log.py",
        ]

    if any(word in lower for word in [
        "windows",
        "пк",
        "локальн",
        "блокнот",
        "notepad",
        "проводник",
        "файл",
        "папк",
    ]):
        return [
            "agents/windows_agent.py",
            "modules/windows.py",
            "agents/workspace_agent.py",
            "modules/workspace.py",
            "agents/file_agent.py",
            "modules/automation_center.py",
            "next/app_v5.py",
            "core/planner.py",
            "core/router.py",
        ]

    return []


def _save_automation_report(kind: str, title: str, body: str):
    _ensure_reports_dir()

    safe_kind = "".join(ch if ch.isalnum() or ch in ["_", "-"] else "_" for ch in str(kind or "automation"))
    path = REPORTS_DIR / f"{_stamp()}_{safe_kind}.md"

    text = "\n".join([
        f"# {title}",
        "",
        f"- Время: {datetime.now().isoformat(timespec='seconds')}",
        f"- Тип: {kind}",
        "",
        body,
    ])

    path.write_text(text, encoding="utf-8")

    set_value("last_automation_report", str(path))
    set_value("last_task_report", str(path))
    return path


def _save_result(task: str, result: str, kind: str = "automation"):
    set_value("last_automation_task", task)
    set_value("last_automation_result", _short(result))
    report = _save_automation_report(kind, f"Automation: {kind}", result)
    return report


def _run_steps(title: str, steps: list):
    rows = []
    ok_count = 0

    for index, step in enumerate(steps, start=1):
        name = step.get("name", f"step {index}")
        func = step.get("func")

        try:
            result = func()
            has_problem = _has_bad_result(result)
            step_ok = not has_problem

            if step_ok:
                ok_count += 1

            rows.append({
                "index": index,
                "name": name,
                "ok": step_ok,
                "result": _short(result, 3500),
                "error": "Результат содержит маркер проблемы." if has_problem else "",
            })
        except Exception as e:
            rows.append({
                "index": index,
                "name": name,
                "ok": False,
                "result": "",
                "error": _short(e, 2500),
            })

    lines = [
        title,
        f"Шагов успешно: {ok_count}/{len(steps)}",
        "",
        "Шаги:",
    ]

    for row in rows:
        mark = "✅" if row["ok"] else "❌"
        lines.extend([
            "",
            f"{row['index']}. {mark} {row['name']}",
        ])

        if row["result"]:
            lines.extend(["```text", row["result"], "```"])

        if row["error"]:
            lines.extend(["ERROR:", "```text", row["error"], "```"])

    return "\n".join(lines)


def _open_folder(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["explorer", str(path)])
    return f"Открыл папку: {path}"


def automation_status():
    return (
        "Automation Command Center status:\n"
        f"- last_automation_task: {get_value('last_automation_task', 'нет')}\n"
        f"- last_automation_result: {get_value('last_automation_result', 'нет')}\n"
        f"- last_automation_report: {get_value('last_automation_report', 'нет')}\n"
        f"- last_task_report: {get_value('last_task_report', 'нет')}\n"
        f"- last_multi_task: {get_value('last_multi_task', 'нет')}\n"
        f"- last_browser_batch: {get_value('last_browser_batch', 'нет')}\n"
        f"- last_pc_batch: {get_value('last_pc_batch', 'нет')}\n"
        f"- last_stability_score: {get_value('last_stability_score', 'нет')}\n"
        f"- last_stability_report: {get_value('last_stability_report', 'нет')}\n"
        f"- last_error: {get_value('last_error', 'нет')}\n\n"
        "Команды:\n"
        "- dev task <задача разработки>\n"
        "- browser task <что найти/прочитать>\n"
        "- browser batch <запрос>\n"
        "- browser read first 3\n"
        "- browser compare <запрос>\n"
        "- browser report <запрос или текущая страница>\n"
        "- pc task <локальная задача ПК>\n"
        "- pc batch <несколько локальных действий>\n"
        "- multi task <браузер + ПК + отчет>\n"
        "- task status\n"
        "- task report\n"
        "- after patch"
    )


def task_status():
    return automation_status()


def task_report():
    path = get_value("last_task_report", "") or get_value("last_automation_report", "")

    if not path:
        return "Последний task report не найден."

    report_path = Path(path)

    if not report_path.exists():
        return f"Task report не найден: {report_path}"

    text = report_path.read_text(encoding="utf-8", errors="replace")
    return f"Последний task report:\n{report_path}\n\n{_short(text, 5000)}"


def parser_diagnostics():
    old_query = get_value("last_browser_query", "")
    set_value("last_browser_query", "Godot official website")

    read_query = _resolve_read_first_query("3")
    browser_query, pc_goal = _split_multi_goal(
        "найди официальный сайт Python, прочитай первые 3 результата и открой папку отчетов"
    )
    pc_clean = _strip_folder_commands(
        "открой блокнот, напиши тест мультизадачи, открой папку отчетов"
    )
    folder_steps, folder_hits = _folder_steps_from_goal("открой папку отчетов")

    if old_query:
        set_value("last_browser_query", old_query)

    return (
        "Parser diagnostics:\n"
        f"- browser_read_first_query: {read_query}\n"
        f"- multi_browser_query: {browser_query}\n"
        f"- multi_pc_goal: {pc_goal}\n"
        f"- pc_batch_clean_goal: {pc_clean}\n"
        f"- pc_batch_folder_hits: {folder_hits}\n"
        f"- pc_batch_reports_only: {'ok' if folder_steps else 'fail'}"
    )


def dev_task(goal: str):
    goal = str(goal or "").strip()

    if not goal:
        return "Automation: не указана dev task."

    from modules.chatgpt_relay import create_snapshot, copy_request, open_chatgpt

    relay_goal = goal

    files_hint = _dev_task_files_hint(goal)

    if files_hint and "файлы:" not in relay_goal.lower() and "files:" not in relay_goal.lower():
        relay_goal = relay_goal.rstrip() + "\n\nфайлы: " + ", ".join(files_hint)

    if not relay_goal.lower().startswith("сделай "):
        relay_goal = "сделай " + relay_goal

    result_parts = [
        "Dev task запущена.",
        f"Цель разработки: {goal}",
        "",
        "--- SNAPSHOT ---",
        create_snapshot(relay_goal),
        "",
        "--- COPY ---",
        copy_request(),
        "",
        "--- OPEN CHATGPT ---",
        open_chatgpt(),
        "",
        "Следующий шаг:",
        "1. В ChatGPT отправь уже скопированный request.",
        "2. Скачай response.json в папку Relay.",
        "3. Выполни: relay проверь ответ",
        "4. Выполни: relay примени ответ",
        "5. Потом: after patch",
    ]

    result = "\n".join(str(part) for part in result_parts)
    report = _save_result(goal, result, kind="dev_task")

    return result + f"\n\nОтчет automation: {report}"


def _read_first_results(query: str, count: int = 3):
    from agents import browser_agent
    from modules.browser import get_search_result_links, open_url, read_page

    query = _clean_browser_goal(query)
    count = max(1, min(int(count or 3), 5))

    steps = []

    steps.append({
        "name": f"search: {query}",
        "func": lambda: browser_agent.handle("search", {"query": query}),
    })

    pages = []

    def collect_links():
        links = get_search_result_links(limit=count)
        pages.clear()
        pages.extend(links)
        return "\n".join(f"{i + 1}. {item['title']} — {item['url']}" for i, item in enumerate(links)) or "Ссылки не найдены."

    steps.append({"name": f"collect first {count} results", "func": collect_links})

    def make_read_step(position: int):
        def run():
            if position >= len(pages):
                return f"Результат #{position + 1} отсутствует."

            item = pages[position]
            open_result = open_url(item["url"])
            read_result = read_page(limit=2500)

            return (
                f"{open_result}\n\n"
                f"TITLE: {item['title']}\nURL: {item['url']}\n\n"
                f"{read_result}"
            )

        return run

    for i in range(count):
        steps.append({
            "name": f"read result #{i + 1}",
            "func": make_read_step(i),
        })

    output = _run_steps(f"Browser batch: {query}", steps)

    set_value("last_browser_batch", _short(output, 4000))
    set_value("last_multi_task", f"browser batch: {query}")

    report = _save_result(query, output, kind="browser_batch")
    return output + f"\n\nОтчет task: {report}"


def browser_task(goal: str):
    count = 3 if any(word in str(goal).lower() for word in ["3", "несколько", "сравни", "compare", "batch"]) else 1

    if count > 1:
        return _read_first_results(goal, count=count)

    goal = str(goal or "").strip()

    if not goal:
        return "Automation: не указана browser task."

    from agents import browser_agent

    browser_goal = _clean_browser_goal(goal)

    steps = [
        {
            "name": f"search: {browser_goal}",
            "func": lambda: browser_agent.handle("search", {"query": browser_goal}),
        },
        {
            "name": "open first result",
            "func": lambda: browser_agent.handle("open_first_result", {}),
        },
        {
            "name": "read page",
            "func": lambda: browser_agent.handle("read_page", {}),
        },
    ]

    result = _run_steps(f"Browser task: {goal}", steps)
    report = _save_result(goal, result, kind="browser_task")

    return result + f"\n\nОтчет automation: {report}"


def browser_batch(goal: str, count: int = 3):
    return _read_first_results(goal, count=count)


def browser_read_first(goal: str = "", count: int = 3):
    query = _resolve_read_first_query(goal)

    if not query:
        return "Нет last_browser_query. Сначала выполни browser batch <запрос> или найди <запрос>."

    return _read_first_results(query, count=count)


def browser_compare(goal: str):
    query = _clean_browser_goal(goal)
    result = _read_first_results(query, count=3)

    comparison = (
        "\n\n--- COMPARE SUMMARY ---\n"
        "Сравнение сохранено по первым 3 результатам. "
        "Смотри блоки read result #1/#2/#3: сравнивай title, URL и текст страницы. "
        "Для следующего уровня можно добавить LLM-сводку поверх этого отчета."
    )

    output = result + comparison
    set_value("last_browser_batch", _short(output, 4000))
    report = _save_result(query, output, kind="browser_compare")

    return output + f"\n\nОтчет compare: {report}"


def browser_report(goal: str = ""):
    from agents import browser_agent

    if goal:
        result = browser_task(goal)
    else:
        result = browser_agent.handle("read_page", {})

    report = _save_result(goal or "current browser page", result, kind="browser_report")
    return f"Browser report сохранен:\n{report}\n\n{_short(result, 3500)}"


def pc_task(goal: str):
    goal = str(goal or "").strip()

    if not goal:
        return "Automation: не указана pc task."

    from core.router import route
    from core.planner import plan
    from core.executor import execute

    route_name = route(goal)
    planned = plan(goal, route_name)
    result = execute(planned)

    output = (
        "PC task выполнена.\n"
        f"Цель: {goal}\n"
        f"ROUTE: {route_name}\n"
        f"PLAN: {planned}\n\n"
        f"RESULT:\n{result}"
    )

    report = _save_result(goal, output, kind="pc_task")
    set_value("last_pc_batch", _short(output, 4000))

    return output + f"\n\nОтчет automation: {report}"


def pc_batch(goal: str):
    goal = str(goal or "").strip()

    if not goal:
        return "Automation: не указана pc batch."

    steps = []

    clean_pc_goal = _strip_folder_commands(goal)

    if clean_pc_goal:
        steps.append({
            "name": "execute pc task",
            "func": lambda: pc_task(clean_pc_goal),
        })

    folder_steps, _ = _folder_steps_from_goal(goal)
    steps.extend(folder_steps)

    if not steps:
        return "PC batch: не нашел локальные действия."

    output = _run_steps(f"PC batch: {goal}", steps)
    set_value("last_pc_batch", _short(output, 4000))
    report = _save_result(goal, output, kind="pc_batch")

    return output + f"\n\nОтчет task: {report}"


def multi_task(goal: str):
    goal = str(goal or "").strip()

    if not goal:
        return "Automation: не указана multi task."

    browser_query, pc_goal = _split_multi_goal(goal)
    steps = []

    if browser_query:
        steps.append({
            "name": f"browser batch: {browser_query}",
            "func": lambda: browser_batch(browser_query, count=3),
        })

    if pc_goal:
        steps.append({
            "name": f"pc batch: {pc_goal}",
            "func": lambda: pc_batch(pc_goal),
        })

    if not steps:
        steps.append({
            "name": "browser task default",
            "func": lambda: browser_task(goal),
        })

    output = _run_steps(f"Multi task: {goal}", steps)
    set_value("last_multi_task", _short(output, 4000))
    report = _save_result(goal, output, kind="multi_task")

    return output + f"\n\nОтчет multi task: {report}"


def after_patch():
    from modules.auto_verification import format_auto_verification, run_auto_verification

    result = run_auto_verification(mode="post_patch", write_report=True)
    formatted = format_auto_verification(result)

    output = (
        "After Patch проверка выполнена.\n"
        "Запущен Auto Verification после применения патча.\n\n"
        f"{formatted}"
    )

    report = _save_result("after patch", output, kind="after_patch")

    return output + f"\n\nОтчет automation: {report}"


def handle_automation(action: str, data: dict):
    if action == "status":
        return automation_status()

    if action == "task_status":
        return task_status()

    if action == "task_report":
        return task_report()

    if action == "parser_diagnostics":
        return parser_diagnostics()

    if action == "dev_task":
        return dev_task(data.get("goal", ""))

    if action == "browser_task":
        return browser_task(data.get("goal", ""))

    if action == "browser_batch":
        return browser_batch(data.get("goal", ""), data.get("limit", 3))

    if action == "browser_read_first":
        return browser_read_first(data.get("goal", ""), data.get("limit", 3))

    if action == "browser_compare":
        return browser_compare(data.get("goal", ""))

    if action == "browser_report":
        return browser_report(data.get("goal", ""))

    if action == "pc_task":
        return pc_task(data.get("goal", ""))

    if action == "pc_batch":
        return pc_batch(data.get("goal", ""))

    if action == "multi_task":
        return multi_task(data.get("goal", ""))

    if action == "after_patch":
        return after_patch()

    return "Automation Command Center: неизвестное действие."
