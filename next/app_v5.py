import sys

from next.goal_manager import analyze_goal
from next.task_planner import create_tasks
from next.task_queue import TaskQueue
from next.observer import observe_page

from core.router import route
from core.planner import plan
from core.executor import execute
from core.state import set_value, get_value
from modules.history_log import append_log
from modules.browser_direct import browser_action_direct_plan


try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


print("=" * 40)
print(" LocalComet v6.02 - Command Center Control Panel ")
print("=" * 40)


SHORTCUTS = {
    "diag": "диагностика",
    "diagnostics": "диагностика",
    "check": "диагностика",

    "lm": "проверь lm studio",
    "lmstudio": "проверь lm studio",
    "api": "проверь lm studio",

    "mem": "проверь память",
    "memory": "проверь память",
    "state": "проверь память",

    "folders": "проверь папки",
    "workspace": "проверь папки",

    "files": "покажи файлы",
    "ls": "покажи файлы",

    "notes": "покажи заметки",
    "note": "прочитай последнюю заметку",

    "reports": "покажи отчеты",
    "report": "покажи отчеты",

    "projects": "открой папку проектов",
    "proj": "открой папку проектов",

    "model": "какая модель",
    "status": "статус",
    "health": "health",
    "project health": "health",
    "health report": "health report",
    "project health report": "health report",
    "regression": "regression suite",
    "regression suite": "regression suite",
    "regression report": "regression report",
    "safe regression": "regression suite",
    "verify": "auto verify",
    "auto verify": "auto verify",
    "auto verification": "auto verify",
    "check all": "auto verify",
    "verify quick": "auto verify",
    "verify full": "auto verify full",
    "auto verify full": "auto verify full",
    "post patch verify": "auto verify full",
    "help": "что ты умеешь",
    "voice status": "voice status",
    "voice test": "voice test",
    "voice last report": "voice last report",

    "last": "последний результат",
    "error": "последняя ошибка",

    "clear note": "очисти блокнот",
    "read note": "покажи что в блокноте",

    "history": "покажи историю",
    "log": "покажи историю",
    "logs": "покажи историю",
    "hist": "покажи историю",

    "backup": "сделай бэкап",
    "bak": "сделай бэкап",
    "clear memory": "очисти память",
    "compact memory": "сожми память",
    "memory size": "размер памяти",

    "self check": "самопроверка проекта",
    "self": "самопроверка проекта",
    "patch": "покажи последний патч",
    "apply patch": "примени последний патч",
    "rollback patch": "откати последний патч",

    "gpt": "gpt статус",
    "gpt status": "gpt статус",
    "gpt model": "gpt модель",

    "gpt browser": "gpt browser status",
    "gpt browser open": "gpt browser open",
    "gpt browser show chat": "gpt browser show chat",
    "gpt browser clear chat": "gpt browser clear chat",
    "gpt browser open project chat": "gpt browser open project chat",
    "gpt browser project chat": "gpt browser open project chat",
    "gpt browser paste": "gpt browser paste request",
    "gpt browser paste request": "gpt browser paste request",
    "gpt browser send": "gpt browser send",
    "gpt browser wait": "gpt browser wait",
    "gpt browser save": "gpt browser save response",
    "gpt browser save response": "gpt browser save response",
    "gpt browser repair": "gpt browser repair response",
    "gpt browser repair response": "gpt browser repair response",
    "gpt browser status": "gpt browser status",
    "gpt browser close": "gpt browser close",
    "gpt browser full cycle": "gpt browser full cycle",
    "gpt browser full apply": "gpt browser full apply",

    "relay": "relay статус",
    "relay status": "relay статус",
    "relay diagnostics": "relay diagnostics",
    "relay diagnostic": "relay diagnostics",
    "relay smoke": "relay smoke",
    "panel relay smoke": "panel relay smoke",
    "relay copy": "relay скопируй запрос",
    "relay open": "relay открой чат",
    "relay paste": "relay скопируй запрос",
    "relay save": "relay забери ответ",
    "relay apply": "relay примени ответ",
    "relay request": "relay покажи запрос",
    "relay response": "relay покажи ответ",
    "relay check": "relay проверь ответ",
    "relay clear": "relay очисти ответ",
    "relay folder": "relay открой папку",
    "relay last": "relay последний запрос",
    "relay last request": "relay последний запрос",
    "relay open request": "relay открой последний запрос",
    "doctor": "error doctor",
    "error doctor": "error doctor",
    "relay doctor": "error doctor",

    "browser last": "browser последний поиск",
    "browser open first": "browser открой первый результат",
    "browser read": "browser прочитай страницу",
    "browser status": "browser статус",
    "browser search": "browser поиск",
    "b last": "browser последний поиск",
    "b first": "browser открой первый результат",
    "b read": "browser прочитай страницу",
    "b status": "browser статус",

    "model test": "stability test",
    "stability test": "stability test",
    "тест стабильности": "тест стабильности",
    "проверка стабильности": "тест стабильности",
    "автотест": "stability test",

    "automation status": "automation status",
    "after patch": "after patch",
    "после патча": "after patch",

    "task status": "task status",
    "task report": "task report",
    "multi task": "multi task",
    "browser batch": "browser batch",
    "browser compare": "browser compare",
    "browser report": "browser report",
    "pc batch": "pc batch",
}


def normalize_shortcut(user_text: str):
    text = str(user_text or "").strip()
    lower = text.lower()

    if lower in SHORTCUTS:
        mapped = SHORTCUTS[lower]
        print(f"SHORTCUT: {text} -> {mapped}")
        return mapped

    return text


def _is_repeat_command(text: str):
    text = str(text or "").lower().strip()

    repeat_words = [
        "повтори",
        "повтори последнюю",
        "повтори последнюю задачу",
        "повтори последнюю цель",
        "еще раз",
        "ещё раз",
    ]

    return any(word == text or word in text for word in repeat_words)


def _is_continue_command(text: str):
    text = str(text or "").lower().strip()

    continue_words = [
        "продолжи",
        "продолжай",
        "дальше",
        "иди дальше",
        "едем дальше",
    ]

    return any(word == text or word in text for word in continue_words)


def _extract_after_markers(text: str, markers: list[str]):
    source = str(text or "").strip()
    lower = source.lower()

    for marker in markers:
        index = lower.find(marker)

        if index != -1:
            return source[index + len(marker):].strip(" :,-—")

    return source.strip()


def _strip_marker(user_text: str, markers: list[str]):
    source = str(user_text or "").strip()
    lower = source.lower()

    for marker in markers:
        if lower.startswith(marker):
            return source[len(marker):].strip(" :,-—")

    return source


def _short_result(result, limit: int = 1500):
    text = str(result or "")

    if len(text) <= limit:
        return text

    return text[:limit] + "\n\n...[результат обрезан для памяти]"


def _run_plan_direct(
    user_text: str,
    planned: dict,
    save_as_real_goal: bool = True,
    write_state: bool = True,
):
    print("\nDIRECT COMMAND")
    print("PLAN:", planned)

    try:
        result = execute(planned)
        print("RESULT:", result)

        tool = planned.get("tool", "unknown")
        action = planned.get("action", "unknown")

        if write_state:
            set_value("last_user_goal", user_text)
            set_value("last_task", user_text)
            set_value("last_route", tool)
            set_value("last_action", action)
            set_value("last_plan", planned)
            set_value("last_result", _short_result(result))

            if save_as_real_goal:
                set_value("last_real_goal", user_text)

        set_value("last_error", "")
        append_log(user_text, planned, result, status="ok")

        print("\nDONE.")
        return True

    except Exception as e:
        print("ERROR:", e)
        set_value("last_error", str(e))
        append_log(user_text, planned, None, status="error", error=str(e))
        return True


def _run_direct_automation_command(user_text: str):
    text = str(user_text or "").lower().strip()

    if text in [
        "automation status",
        "автоматизация статус",
        "статус автоматизации",
        "центр автоматизации",
        "task status",
        "статус задачи",
    ]:
        action = "task_status" if "task" in text or "задач" in text else "status"

        return _run_plan_direct(
            user_text,
            {"tool": "automation", "action": action},
            save_as_real_goal=False,
        )

    if text in [
        "task report",
        "отчет задачи",
        "последний task report",
        "последний отчет задачи",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "automation", "action": "task_report"},
            save_as_real_goal=False,
        )

    if text in [
        "after patch",
        "после патча",
        "проверка после патча",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "automation", "action": "after_patch"},
            save_as_real_goal=False,
        )

    dev_markers = [
        "dev task",
        "задача разработки",
        "dev задача",
    ]

    if any(text.startswith(marker) for marker in dev_markers):
        goal = _strip_marker(user_text, dev_markers)

        if not goal:
            print("Не понял dev task.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "automation",
                "action": "dev_task",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    multi_markers = [
        "multi task",
        "мульти задача",
        "комплексная задача",
    ]

    if any(text.startswith(marker) for marker in multi_markers):
        goal = _strip_marker(user_text, multi_markers)

        if not goal:
            print("Не понял multi task.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "automation",
                "action": "multi_task",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    browser_read_first_markers = [
        "browser read first",
        "браузер прочитай первые",
        "прочитай первые результаты",
    ]

    if any(text.startswith(marker) for marker in browser_read_first_markers):
        goal = _strip_marker(user_text, browser_read_first_markers)
        limit = 3

        for token in text.replace(",", " ").split():
            digits = "".join(ch for ch in token if ch.isdigit())

            if digits:
                limit = max(1, min(int(digits), 5))
                break

        return _run_plan_direct(
            user_text,
            {
                "tool": "automation",
                "action": "browser_read_first",
                "goal": goal,
                "limit": limit,
            },
            save_as_real_goal=False,
        )

    browser_batch_markers = [
        "browser batch",
        "браузер batch",
        "браузер пачка",
    ]

    if any(text.startswith(marker) for marker in browser_batch_markers):
        goal = _strip_marker(user_text, browser_batch_markers)

        if not goal:
            print("Не понял browser batch.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "automation",
                "action": "browser_batch",
                "goal": goal,
                "limit": 3,
            },
            save_as_real_goal=False,
        )

    browser_compare_markers = [
        "browser compare",
        "браузер сравни",
        "сравни в браузере",
    ]

    if any(text.startswith(marker) for marker in browser_compare_markers):
        goal = _strip_marker(user_text, browser_compare_markers)

        if not goal:
            print("Не понял browser compare.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "automation",
                "action": "browser_compare",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    browser_report_markers = [
        "browser report",
        "браузер отчет",
        "отчет по странице",
    ]

    if any(text.startswith(marker) for marker in browser_report_markers):
        goal = _strip_marker(user_text, browser_report_markers)

        return _run_plan_direct(
            user_text,
            {
                "tool": "automation",
                "action": "browser_report",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    browser_markers = [
        "browser task",
        "браузерная задача",
        "браузер задача",
    ]

    if any(text.startswith(marker) for marker in browser_markers):
        goal = _strip_marker(user_text, browser_markers)

        if not goal:
            print("Не понял browser task.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "automation",
                "action": "browser_task",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    pc_batch_markers = [
        "pc batch",
        "пк batch",
        "пк пачка",
        "локальная пачка",
    ]

    if any(text.startswith(marker) for marker in pc_batch_markers):
        goal = _strip_marker(user_text, pc_batch_markers)

        if not goal:
            print("Не понял pc batch.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "automation",
                "action": "pc_batch",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    pc_markers = [
        "pc task",
        "задача пк",
        "пк задача",
        "локальная задача",
    ]

    if any(text.startswith(marker) for marker in pc_markers):
        goal = _strip_marker(user_text, pc_markers)

        if not goal:
            print("Не понял pc task.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "automation",
                "action": "pc_task",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    return False


def _extract_first_int(text: str, default: int = 600):
    for token in str(text or "").replace(",", " ").split():
        digits = "".join(ch for ch in token if ch.isdigit())

        if digits:
            try:
                return max(30, int(digits))
            except Exception:
                pass

    return default


def _run_direct_gpt_browser_command(user_text: str):
    text = str(user_text or "").lower().strip()
    raw_text = str(user_text or "").strip()
    timeout_sec = _extract_first_int(text, default=600)

    set_chat_marker = "gpt browser set chat"

    if text.startswith(set_chat_marker):
        url = raw_text[len(set_chat_marker):].strip(" :,-—")

        return _run_plan_direct(
            user_text,
            {"tool": "gpt_browser", "action": "set_chat", "url": url},
            save_as_real_goal=False,
        )

    if text in [
        "gpt browser show chat",
        "гпт браузер покажи чат",
        "чатгпт браузер покажи чат",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "gpt_browser", "action": "show_chat"},
            save_as_real_goal=False,
        )

    if text in [
        "gpt browser clear chat",
        "гпт браузер очисти чат",
        "чатгпт браузер очисти чат",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "gpt_browser", "action": "clear_chat"},
            save_as_real_goal=False,
        )

    if text in [
        "gpt browser open project chat",
        "gpt browser project chat",
        "гпт браузер открыть чат проекта",
        "чатгпт браузер открыть чат проекта",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "gpt_browser", "action": "open_project_chat"},
            save_as_real_goal=False,
        )

    if text in [
        "gpt browser open",
        "гпт браузер открыть",
        "чатгпт браузер открыть",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "gpt_browser", "action": "open"},
            save_as_real_goal=False,
        )

    if text in [
        "gpt browser paste request",
        "gpt browser paste",
        "гпт браузер вставь запрос",
        "чатгпт браузер вставь запрос",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "gpt_browser", "action": "paste_request"},
            save_as_real_goal=False,
        )

    if text in [
        "gpt browser send",
        "гпт браузер отправь",
        "чатгпт браузер отправь",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "gpt_browser", "action": "send"},
            save_as_real_goal=False,
        )

    if (
        text == "gpt browser wait"
        or text.startswith("gpt browser wait ")
        or text in [
            "гпт браузер жди",
            "чатгпт браузер жди",
        ]
    ):
        return _run_plan_direct(
            user_text,
            {"tool": "gpt_browser", "action": "wait", "timeout_sec": timeout_sec},
            save_as_real_goal=False,
        )

    if text in [
        "gpt browser save response",
        "gpt browser save",
        "гпт браузер сохрани ответ",
        "чатгпт браузер сохрани ответ",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "gpt_browser", "action": "save_response"},
            save_as_real_goal=False,
        )

    if text in [
        "gpt browser repair response",
        "gpt browser repair",
        "гпт браузер почини ответ",
        "чатгпт браузер почини ответ",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "gpt_browser", "action": "repair_response"},
            save_as_real_goal=False,
        )

    if text in [
        "gpt browser status",
        "гпт браузер статус",
        "чатгпт браузер статус",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "gpt_browser", "action": "status"},
            save_as_real_goal=False,
        )

    if text in [
        "gpt browser close",
        "gpt browser shutdown",
        "гпт браузер закрыть",
        "чатгпт браузер закрыть",
        "закрой гпт браузер",
        "закрой чатгпт браузер",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "gpt_browser", "action": "close"},
            save_as_real_goal=False,
        )

    if text == "gpt browser full cycle" or text.startswith("gpt browser full cycle "):
        return _run_plan_direct(
            user_text,
            {"tool": "gpt_browser", "action": "full_cycle", "timeout_sec": timeout_sec},
            save_as_real_goal=False,
        )

    if text == "gpt browser full apply" or text.startswith("gpt browser full apply "):
        return _run_plan_direct(
            user_text,
            {
                "actions": [
                    {"tool": "gpt_browser", "action": "full_cycle", "timeout_sec": timeout_sec},
                    {"tool": "gpt_browser", "action": "close"},
                    {"tool": "chatgpt_relay", "action": "apply_response"},
                    {"tool": "automation", "action": "after_patch"},
                ]
            },
            save_as_real_goal=False,
        )

    return False


def _run_direct_chatgpt_relay_command(user_text: str):
    text = str(user_text or "").lower().strip()

    if _run_direct_gpt_browser_command(user_text):
        return True

    if _run_direct_automation_command(user_text):
        return True

    if text in [
        "relay статус",
        "relay status",
        "статус relay",
        "статус релей",
        "чатгпт релей статус",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "diagnostics"},
            save_as_real_goal=False,
        )

    if text in [
        "relay diagnostics",
        "relay diagnostic",
        "relay диагностика",
        "relay диагностика статуса",
        "диагностика relay",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "diagnostics"},
            save_as_real_goal=False,
        )

    if text in [
        "relay smoke",
        "relay smoke test",
        "relay dry run",
        "panel relay smoke",
        "панель relay smoke",
        "relay смоук",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "smoke"},
            save_as_real_goal=False,
        )

    error_doctor_markers = [
        "error doctor",
        "doctor",
        "relay doctor",
        "relay error doctor",
        "доктор ошибок",
        "доктор ошибки",
        "почини ошибку",
        "исправь ошибку",
        "разбери ошибку",
    ]

    if any(text == marker or text.startswith(marker + " ") for marker in error_doctor_markers):
        goal = _strip_marker(user_text, error_doctor_markers)

        return _run_plan_direct(
            user_text,
            {
                "tool": "chatgpt_relay",
                "action": "error_doctor",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    start_silent_markers = [
        "relay старт тихо",
        "relay тихий старт",
        "relay start silent",
        "relay silent",
        "relay без чата",
        "relay старт без чата",
    ]

    if any(text.startswith(marker) for marker in start_silent_markers):
        goal = _strip_marker(user_text, start_silent_markers)

        if not goal:
            print("Не понял цель relay-запроса.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "chatgpt_relay",
                "action": "start_silent",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    start_markers = [
        "relay старт",
        "relay start",
        "релей старт",
        "чатгпт старт",
    ]

    if any(text.startswith(marker) for marker in start_markers):
        goal = _strip_marker(user_text, start_markers)

        if not goal:
            print("Не понял цель relay-запроса.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "chatgpt_relay",
                "action": "start",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    snapshot_markers = [
        "relay snapshot",
        "relay снапшот",
        "relay сделай snapshot",
        "relay создай snapshot",
        "relay снимок",
    ]

    if any(text.startswith(marker) for marker in snapshot_markers):
        goal = _strip_marker(user_text, snapshot_markers)

        if not goal:
            print("Не понял цель snapshot-запроса.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "chatgpt_relay",
                "action": "create_snapshot",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    create_markers = [
        "relay создай запрос",
        "relay запрос",
        "relay request",
        "релей создай запрос",
        "чатгпт запрос",
    ]

    if any(text.startswith(marker) for marker in create_markers):
        goal = _strip_marker(user_text, create_markers)

        if not goal:
            print("Не понял цель relay-запроса.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "chatgpt_relay",
                "action": "create_request",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    if text in [
        "relay скопируй запрос",
        "relay copy",
        "relay paste",
        "скопируй relay запрос",
        "скопируй запрос relay",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "copy_request"},
            save_as_real_goal=False,
        )

    if text in [
        "relay открой чат",
        "relay open",
        "открой chatgpt",
        "открой чатгпт",
        "открой чат gpt",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "open_chatgpt"},
            save_as_real_goal=False,
        )

    if text in [
        "relay открой папку",
        "relay папка",
        "relay folder",
        "открой папку relay",
        "открой папку релей",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "open_relay_folder"},
            save_as_real_goal=False,
        )

    if text in [
        "relay покажи запрос",
        "relay show request",
        "покажи relay запрос",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "show_request"},
            save_as_real_goal=False,
        )

    if text in [
        "relay последний запрос",
        "relay путь запроса",
        "relay last request",
        "relay last",
        "последний relay запрос",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "last_request_path"},
            save_as_real_goal=False,
        )

    if text in [
        "relay открой последний запрос",
        "relay open request",
        "relay open last request",
        "открой последний relay запрос",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "open_last_request"},
            save_as_real_goal=False,
        )

    if text in [
        "relay забери ответ",
        "relay сохрани ответ",
        "relay save",
        "relay capture",
        "забери ответ relay",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "save_clipboard_response"},
            save_as_real_goal=False,
        )

    if text in [
        "relay покажи ответ",
        "relay show response",
        "покажи relay ответ",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "show_response"},
            save_as_real_goal=False,
        )

    if text in [
        "relay проверь ответ",
        "relay check",
        "relay validate",
        "проверь relay ответ",
        "проверь ответ relay",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "validate_response"},
            save_as_real_goal=False,
        )

    if text in [
        "relay очисти ответ",
        "relay clear",
        "relay clear response",
        "очисти relay ответ",
        "очисти ответ relay",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "clear_response"},
            save_as_real_goal=False,
        )

    if text in [
        "relay импортируй ответ",
        "relay import",
        "импортируй relay ответ",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "import_response_as_patch"},
            save_as_real_goal=False,
        )

    if text in [
        "relay примени ответ",
        "relay apply",
        "примени relay ответ",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "chatgpt_relay", "action": "apply_response"},
            save_as_real_goal=False,
        )

    return False


def _run_direct_gpt_command(user_text: str):
    text = str(user_text or "").lower().strip()

    if text in [
        "gpt статус",
        "gpt status",
        "статус gpt",
        "статус гпт",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "gpt", "action": "status"},
            save_as_real_goal=False,
        )

    if text in [
        "gpt модель",
        "gpt model",
        "модель gpt",
        "модель гпт",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "gpt", "action": "model"},
            save_as_real_goal=False,
        )

    ask_markers = [
        "gpt спроси",
        "гпт спроси",
        "gpt ask",
        "спроси gpt",
        "спроси гпт",
    ]

    if any(text.startswith(marker) for marker in ask_markers):
        prompt = _strip_marker(user_text, ask_markers)

        if not prompt:
            print("Не понял, что спросить у GPT.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "gpt",
                "action": "ask",
                "prompt": prompt,
                "max_output_tokens": 3000,
            },
            save_as_real_goal=False,
        )

    code_markers = [
        "gpt код",
        "гпт код",
        "gpt code",
        "gpt помоги с кодом",
        "гпт помоги с кодом",
    ]

    if any(text.startswith(marker) for marker in code_markers):
        prompt = _strip_marker(user_text, code_markers)

        if not prompt:
            print("Не понял задачу по коду для GPT.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "gpt",
                "action": "ask_code",
                "prompt": prompt,
                "max_output_tokens": 4000,
            },
            save_as_real_goal=False,
        )

    return False


def _run_direct_self_edit_command(user_text: str):
    text = str(user_text or "").lower().strip()

    if text in [
        "самопроверка проекта",
        "проверь код проекта",
        "self check code",
        "self check",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "self_edit", "action": "health"},
            save_as_real_goal=False,
        )

    if text in [
        "покажи последний патч",
        "последний патч",
        "last patch",
        "patch",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "self_edit", "action": "show_last_patch"},
            save_as_real_goal=False,
        )

    if text in [
        "примени последний патч",
        "прими последний патч",
        "apply patch",
        "примени патч",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "self_edit", "action": "apply_last_patch"},
            save_as_real_goal=False,
        )

    if text in [
        "почини последний патч",
        "исправь последний патч",
        "repair patch",
        "fix patch",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "self_edit", "action": "repair_last_patch"},
            save_as_real_goal=False,
        )

    if text in [
        "откати последний патч",
        "rollback patch",
        "откат патча",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "self_edit", "action": "rollback_last_patch"},
            save_as_real_goal=False,
        )

    create_markers = [
        "создай патч",
        "сделай патч",
        "self edit",
        "самоизменение",
        "улучши себя",
        "измени себя",
        "добавь себе",
    ]

    if any(text.startswith(marker) for marker in create_markers):
        goal = _strip_marker(user_text, create_markers)

        if not goal:
            print("Не понял, что менять в проекте.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "self_edit",
                "action": "create_patch",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    auto_markers = [
        "автоизмени себя",
        "автоисправь",
        "auto edit",
        "auto fix",
    ]

    if any(text.startswith(marker) for marker in auto_markers):
        goal = _strip_marker(user_text, auto_markers)

        if not goal:
            print("Не понял цель автоизменения.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "self_edit",
                "action": "auto_edit",
                "goal": goal,
            },
            save_as_real_goal=False,
        )

    return False


def _run_direct_maintenance_command(user_text: str):
    text = str(user_text or "").lower().strip()

    if text in [
        "сделай бэкап",
        "бэкап",
        "backup",
        "сделай backup",
        "создай бэкап",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "maintenance", "action": "backup_project"}
        )

    if text in [
        "открой папку бэкапов",
        "папка бэкапов",
        "backups",
        "open backups",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "maintenance", "action": "open_backups_folder"}
        )

    if text in [
        "размер памяти",
        "memory size",
        "state size",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "maintenance", "action": "memory_size"}
        )

    if text in [
        "очисти память",
        "очистить память",
        "reset memory",
        "clear memory",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "maintenance", "action": "clear_memory"},
            save_as_real_goal=False,
            write_state=False,
        )

    if text in [
        "очисти последний результат",
        "очисти last_result",
        "clear last result",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "maintenance", "action": "clear_last_result"}
        )

    if text in [
        "сожми память",
        "compact memory",
        "сжать память",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "maintenance", "action": "compact_memory"}
        )

    return False


def _run_direct_history_command(user_text: str):
    text = str(user_text or "").lower().strip()

    if text in [
        "покажи историю",
        "история",
        "последние команды",
        "последние действия",
        "history",
        "log",
        "logs",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "history", "action": "show", "limit": 20},
            save_as_real_goal=False,
        )

    if text in [
        "последняя запись истории",
        "последний лог",
        "last log",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "history", "action": "last"},
            save_as_real_goal=False,
        )

    if text in [
        "статистика истории",
        "history stats",
        "log stats",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "history", "action": "stats"},
            save_as_real_goal=False,
        )

    if text in [
        "очисти историю",
        "очистить историю",
        "clear history",
        "clear log",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "history", "action": "clear"},
            save_as_real_goal=False,
        )

    if text in [
        "путь истории",
        "где история",
        "log path",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "history", "action": "path"},
            save_as_real_goal=False,
        )

    return False


def _run_direct_diagnostics_command(user_text: str):
    text = str(user_text or "").lower().strip()

    if text in [
        "health",
        "project health",
        "здоровье проекта",
        "состояние проекта",
        "проверь здоровье проекта",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "system", "action": "health"},
            save_as_real_goal=False,
        )

    if text in [
        "health report",
        "project health report",
        "project health center report",
        "отчет здоровья проекта",
        "отчёт здоровья проекта",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "system", "action": "health_report"},
            save_as_real_goal=False,
        )

    if text in [
        "regression",
        "regression suite",
        "safe regression",
        "regression command suite",
        "регрессия",
        "регрессионная проверка",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "system", "action": "regression_suite"},
            save_as_real_goal=False,
        )

    if text in [
        "regression report",
        "regression suite report",
        "regression command report",
        "отчет регрессии",
        "отчёт регрессии",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "system", "action": "regression_report"},
            save_as_real_goal=False,
        )

    if text in [
        "auto verify",
        "auto verification",
        "verify",
        "verify quick",
        "check all",
        "автопроверка",
        "проверить всё",
        "проверить все",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "system", "action": "auto_verify"},
            save_as_real_goal=False,
        )

    if text in [
        "auto verify full",
        "verify full",
        "post patch verify",
        "full verify",
        "полная автопроверка",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "system", "action": "auto_verify_full"},
            save_as_real_goal=False,
        )

    if text in [
        "диагностика",
        "проверь систему",
        "проверь localcomet",
        "проверь локалкомет",
        "проверка системы",
        "self check",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "diagnostics", "action": "full"}
        )

    if text in [
        "проверь lm studio",
        "проверь lmstudio",
        "статус lm studio",
        "статус lmstudio",
        "проверь модель",
        "проверь api",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "diagnostics", "action": "lmstudio"}
        )

    if text in [
        "проверь папки",
        "проверь workspace",
        "проверь проекты",
        "проверь директории",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "diagnostics", "action": "workspace"}
        )

    if text in [
        "проверь память",
        "проверь state",
        "проверь state.json",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "diagnostics", "action": "memory"}
        )

    if text in [
        "проверь отчеты",
        "проверь отчёты",
        "диагностика отчетов",
        "диагностика отчётов",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "diagnostics", "action": "reports"}
        )

    if text in [
        "проверь файлы",
        "диагностика файлов",
    ]:
        return _run_plan_direct(
            user_text,
            {"tool": "diagnostics", "action": "files"}
        )

    return False


def _format_voice_status_text(status):
    deps = status.get("dependencies", {}) if isinstance(status, dict) else {}
    lines = [
        "Voice status:",
        f"- enabled: {status.get('enabled')}",
        f"- listening: {status.get('listening')}",
        f"- muted: {status.get('muted')}",
        f"- stt_engine: {status.get('stt_engine')}",
        f"- tts_engine: {status.get('tts_engine')}",
        f"- usable_faster_whisper_ru: {deps.get('usable_faster_whisper_ru')}",
        f"- piper_available: {deps.get('piper_available')}",
        f"- usable_stt: {deps.get('usable_stt')}",
        f"- usable_vosk_ru: {deps.get('usable_vosk_ru')}",
        f"- vosk_model_path: {deps.get('vosk_model_path') or 'нет'}",
        f"- usable_tts: {deps.get('usable_tts')}",
        f"- last_report: {status.get('last_report') or 'нет'}",
    ]
    messages = deps.get("messages") or []

    if messages:
        lines.append("")
        lines.append("Messages:")
        lines.extend(f"- {message}" for message in messages)

    return "\n".join(lines)


def _run_direct_voice_command(user_text: str):
    text = str(user_text or "").strip()
    lower = text.lower()

    if lower == "voice status":
        from modules.voice_control import get_voice_status

        print(_format_voice_status_text(get_voice_status()))
        return True

    if lower == "voice test":
        from modules.voice_control import check_voice_dependencies

        deps = check_voice_dependencies()
        print("Voice test:")
        print(f"- usable_stt: {deps.get('usable_stt')}")
        print(f"- usable_tts: {deps.get('usable_tts')}")

        for message in deps.get("messages") or []:
            print(f"- {message}")

        return True

    if lower.startswith("voice speak "):
        from modules.voice_control import speak_text

        phrase = text[len("voice speak "):].strip()
        print(speak_text(phrase, enabled=True))
        return True

    if lower == "voice last report":
        from modules.voice_control import latest_voice_session_report

        report = latest_voice_session_report()
        print(report or "Voice session report пока не найден.")
        return True

    return False


def _run_direct_notepad_command(user_text: str):
    text = str(user_text or "").lower().strip()

    if (
        "очисти блокнот" in text
        or "очистить блокнот" in text
        or "очисти в блокноте" in text
        or "сотри блокнот" in text
    ):
        return _run_plan_direct(
            user_text,
            {"tool": "windows", "action": "clear_notepad"}
        )

    if (
        "покажи что в блокноте" in text
        or "что в блокноте" in text
        or "прочитай блокнот" in text
        or "покажи блокнот" in text
        or "содержимое блокнота" in text
    ):
        return _run_plan_direct(
            user_text,
            {"tool": "windows", "action": "read_notepad"}
        )

    if (
        "открой файл блокнота" in text
        or "открой текущий блокнот" in text
        or "открой notepad file" in text
    ):
        return _run_plan_direct(
            user_text,
            {"tool": "windows", "action": "open_notepad_file"}
        )

    if (
        "добавь в блокнот" in text
        or "добавь в блокноте" in text
        or "добавь строку в блокнот" in text
        or "добавь текст в блокнот" in text
        or "допиши в блокнот" in text
    ):
        content = _extract_after_markers(
            user_text,
            [
                "добавь строку в блокнот",
                "добавь текст в блокнот",
                "добавь в блокноте",
                "добавь в блокнот",
                "допиши в блокнот",
            ]
        )

        if not content:
            print("Не понял, какой текст добавить в Блокнот.")
            return True

        return _run_plan_direct(
            user_text,
            {"tool": "windows", "action": "append_text", "text": content}
        )

    return False


def _run_direct_workspace_command(user_text: str):
    text = str(user_text or "").lower().strip()

    if text in ["открой папку проектов", "открой projects", "папка проектов"]:
        return _run_plan_direct(
            user_text,
            {"tool": "workspace", "action": "open_projects_folder"}
        )

    if text in ["открой папку отчетов", "открой reports", "папка отчетов"]:
        return _run_plan_direct(
            user_text,
            {"tool": "workspace", "action": "open_reports_folder"}
        )

    if text in ["открой папку файлов", "открой files", "папка файлов"]:
        return _run_plan_direct(
            user_text,
            {"tool": "workspace", "action": "open_files_folder"}
        )

    if text in ["покажи отчеты", "список отчетов", "последние отчеты"]:
        return _run_plan_direct(
            user_text,
            {"tool": "workspace", "action": "list_reports"}
        )

    if text in ["открой последний отчет", "открой последний отчёт"]:
        return _run_plan_direct(
            user_text,
            {"tool": "workspace", "action": "open_latest_report"}
        )

    if text in ["покажи заметки", "список заметок", "последние заметки"]:
        return _run_plan_direct(
            user_text,
            {"tool": "workspace", "action": "list_notes"}
        )

    if text in ["прочитай последнюю заметку", "покажи последнюю заметку"]:
        return _run_plan_direct(
            user_text,
            {"tool": "workspace", "action": "read_latest_note"}
        )

    if text in ["покажи файлы", "список файлов"]:
        return _run_plan_direct(
            user_text,
            {"tool": "workspace", "action": "list_files"}
        )

    if text in ["открой последний файл", "открой последний workspace файл"]:
        return _run_plan_direct(
            user_text,
            {"tool": "workspace", "action": "open_last_workspace_file"}
        )

    if text.startswith("создай заметку"):
        content = _extract_after_markers(
            user_text,
            ["создай заметку", "заметка"]
        )

        if not content:
            print("Не понял текст заметки.")
            return True

        return _run_plan_direct(
            user_text,
            {"tool": "workspace", "action": "create_note", "text": content}
        )

    if text.startswith("создай файл"):
        rest = _extract_after_markers(user_text, ["создай файл"])

        lower_rest = rest.lower()

        split_markers = [" с текстом ", " текст: ", " текст "]
        path = rest
        content = ""

        for marker in split_markers:
            idx = lower_rest.find(marker)

            if idx != -1:
                path = rest[:idx].strip(" :,-—")
                content = rest[idx + len(marker):].strip()
                break

        if not path:
            print("Не понял имя файла.")
            return True

        return _run_plan_direct(
            user_text,
            {
                "tool": "workspace",
                "action": "create_text_file",
                "path": path,
                "content": content,
            }
        )

    if text.startswith("прочитай файл"):
        path = _extract_after_markers(user_text, ["прочитай файл"])

        if not path:
            print("Не понял имя файла.")
            return True

        return _run_plan_direct(
            user_text,
            {"tool": "workspace", "action": "read_text_file", "path": path}
        )

    return False


def _run_direct_browser_action_command(user_text: str):
    planned = browser_action_direct_plan(user_text)

    if not planned:
        return False

    return _run_plan_direct(
        user_text,
        planned,
        save_as_real_goal=False,
    )


def _show_last_result():
    last_result = get_value("last_result")

    if not last_result:
        print("Последнего результата пока нет.")
        return

    print("\nПОСЛЕДНИЙ РЕЗУЛЬТАТ:")
    print(last_result)


def _show_last_error():
    last_error = get_value("last_error")

    if not last_error:
        print("Последней ошибки нет.")
        return

    print("\nПОСЛЕДНЯЯ ОШИБКА:")
    print(last_error)


def _run_repeat(max_steps: int = 10):
    last_real_goal = get_value("last_real_goal")

    if not last_real_goal:
        print("Пока нечего повторять. Сначала выполни обычную цель.")
        return

    print(f"\nПОВТОРЯЮ ПОСЛЕДНЮЮ ЦЕЛЬ: {last_real_goal}")
    run_goal(last_real_goal, max_steps=max_steps, save_as_real_goal=False)


def _run_continue(max_steps: int = 10):
    last_route = get_value("last_route")
    last_site = get_value("last_site")
    last_report = get_value("last_report")
    last_windows_app = get_value("last_windows_app")
    last_workspace_file = get_value("last_workspace_file")
    last_real_goal = get_value("last_real_goal")

    if last_workspace_file:
        next_goal = "открой последний файл"
    elif last_windows_app == "notepad":
        next_goal = "покажи что в блокноте"
    elif last_site and last_route in ["project", "codegen", "browser"]:
        next_goal = "улучши последний сайт"
    elif last_report and last_route in ["research", "operator"]:
        next_goal = "покажи последний отчет"
    elif last_real_goal:
        next_goal = last_real_goal
    else:
        print("Пока нечего продолжать. Сначала выполни обычную цель.")
        return

    print(f"\nПРОДОЛЖАЮ: {next_goal}")
    run_goal(next_goal, max_steps=max_steps, save_as_real_goal=False)


def run_direct_command(user_text: str):
    text = str(user_text or "").lower().strip()

    if _run_direct_browser_action_command(user_text):
        return True

    if _run_direct_chatgpt_relay_command(user_text):
        return True

    if _run_direct_gpt_command(user_text):
        return True

    if _run_direct_self_edit_command(user_text):
        return True

    if _run_direct_maintenance_command(user_text):
        return True

    if _run_direct_history_command(user_text):
        return True

    if _run_direct_voice_command(user_text):
        return True

    if _run_direct_diagnostics_command(user_text):
        return True

    if _run_direct_notepad_command(user_text):
        return True

    if _run_direct_workspace_command(user_text):
        return True

    if _is_repeat_command(text):
        _run_repeat()
        return True

    if _is_continue_command(text):
        _run_continue()
        return True

    if text in ["последний результат", "покажи последний результат"]:
        _show_last_result()
        return True

    if text in ["последняя ошибка", "покажи последнюю ошибку"]:
        _show_last_error()
        return True

    route_name = route(user_text)

    if route_name != "system":
        return False

    print("\nDIRECT SYSTEM COMMAND")
    print("ROUTE:", route_name)

    planned = plan(user_text, route_name)
    print("PLAN:", planned)

    if not planned:
        print("PLAN returned None — skipping execute.")
        append_log(user_text, None, "plan returned None", status="error")
        return False

    result = execute(planned)
    print("RESULT:", result)

    set_value("last_user_goal", user_text)
    set_value("last_route", route_name)
    set_value("last_result", _short_result(result))

    append_log(user_text, planned, result, status="ok")

    print("\nDONE.")
    return True


def run_goal(user_goal: str, max_steps: int = 10, save_as_real_goal: bool = True):
    user_goal = user_goal.strip()

    if not user_goal:
        print("Пустая цель. Напиши задачу.")
        return

    if run_direct_command(user_goal):
        return

    set_value("last_user_goal", user_goal)

    if save_as_real_goal:
        set_value("last_real_goal", user_goal)

    goal = analyze_goal(user_goal)

    print("\nGOAL:")
    print(goal)

    queue = TaskQueue()

    if goal.get("type") in ["research", "operator"]:
        tasks = [user_goal]
    else:
        tasks = create_tasks(user_goal)

    if not tasks:
        print("Не удалось создать задачи для цели.")
        set_value("last_error", "Не удалось создать задачи для цели.")
        append_log(user_goal, None, None, status="error", error="Не удалось создать задачи для цели.")
        return

    queue.add_many(tasks)

    print("\nTASKS:")
    for t in tasks:
        print("-", t)

    step = 0

    while queue.has_tasks() and step < max_steps:
        step += 1
        task = queue.next()

        if not task or not task.strip():
            print("Пропущена пустая задача.")
            continue

        print(f"\n--- TASK {step} ---")
        print("TASK:", task)

        try:
            route_name = route(task)
            print("ROUTE:", route_name)

            planned = plan(task, route_name)
            print("PLAN:", planned)

            if not planned:
                print("PLAN returned None — skipping execute.")
                append_log(task, None, "plan returned None", status="error")
                continue

            result = execute(planned)
            print("RESULT:", result)

            set_value("last_task", task)
            set_value("last_route", route_name)
            set_value("last_plan", planned)
            set_value("last_result", _short_result(result))

            append_log(task, planned, result, status="ok")

            if isinstance(result, str) and "TITLE:" in result:
                observation = observe_page(result)
                print("\nOBSERVATION:")
                print(observation)
                set_value("last_observation", _short_result(observation))

        except Exception as e:
            print("ERROR:", e)
            set_value("last_error", str(e))
            append_log(task, None, None, status="error", error=str(e))
            break

    print("\nDONE.")
    print(queue.history())


while True:
    user = input("\nЦель: ").strip()

    if user.lower() in ["exit", "выход"]:
        break

    if not user:
        print("Пусто. Введи цель или напиши exit.")
        continue

    user = normalize_shortcut(user)
    run_goal(user)
