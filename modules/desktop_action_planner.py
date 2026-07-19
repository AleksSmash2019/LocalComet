import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value
from modules.desktop_observer import observe_desktop


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "desktop_action_planner"


DANGEROUS_MARKERS = [
    "delete",
    "remove",
    "erase",
    "удали",
    "удалить",
    "сотри",
    "оплат",
    "платеж",
    "платёж",
    "карта",
    "cvv",
    "card",
    "payment",
    "pay ",
    "buy ",
    "checkout",
    "password",
    "пароль",
    "api key",
    "token",
    "confirm",
    "подтверди",
    "submit",
    "отправь форму",
]

ACTION_MARKERS = [
    "click",
    "клик",
    "нажми",
    "press",
    "type",
    "введи",
    "напиши",
    "send",
    "отправь",
    "open",
    "открой",
]


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _contains_any(text, markers):
    lower = str(text or "").lower()
    return [marker for marker in markers if marker in lower]


def _risk_for_goal(goal):
    dangerous = _contains_any(goal, DANGEROUS_MARKERS)
    action_words = _contains_any(goal, ACTION_MARKERS)

    if dangerous:
        return "blocked", "high", dangerous

    if action_words:
        return "needs_confirmation", "medium", action_words

    return "draft", "low", []


def _suggest_steps(goal, observation, status):
    active = observation.get("active_window") or {}
    active_title = active.get("title") or "текущее активное окно"
    goal_text = str(goal or "").strip()

    if status == "blocked":
        return [
            "Остановиться: задача содержит опасные маркеры.",
            "Попросить пользователя уточнить безопасную цель.",
            "Не выполнять клики, ввод текста, отправку форм или подтверждения.",
        ]

    steps = [
        f"Проверить, что активное окно подходит для цели: {active_title}.",
        f"Сверить цель пользователя: {goal_text or 'цель не указана'}.",
        "Если окно не то, попросить пользователя открыть нужное приложение или вкладку.",
        "Перед любым кликом/вводом показать пользователю план и дождаться подтверждения.",
    ]

    lower = goal_text.lower()

    if any(word in lower for word in ["найди", "search", "поиск", "найти"]):
        steps.append("Для поиска: сначала определить поле поиска, затем предложить текст запроса.")

    if any(word in lower for word in ["напиши", "введи", "type"]):
        steps.append("Для ввода текста: показать точный текст и целевое поле до выполнения.")

    if any(word in lower for word in ["клик", "нажми", "click"]):
        steps.append("Для клика: назвать видимую кнопку/элемент и риск действия.")

    return steps


def _write_report(result):
    _ensure_dir()
    path = REPORTS_DIR / f"desktop_action_plan_{_stamp()}.md"
    observation = result.get("observation") or {}
    active = observation.get("active_window") or {}
    windows = observation.get("windows") or []

    lines = [
        "# Desktop Action Plan",
        "",
        f"- created_at: {result.get('created_at')}",
        f"- goal: {result.get('goal') or 'нет'}",
        f"- status: {result.get('status')}",
        f"- risk_level: {result.get('risk_level')}",
        f"- blocked_markers: {', '.join(result.get('markers') or []) or 'нет'}",
        f"- observation_report: {observation.get('report_path') or 'нет'}",
        f"- screenshot: {observation.get('screenshot_path') or 'нет'}",
        "",
        "## Active Window",
        "",
        f"- title: {active.get('title') or 'нет'}",
        f"- class: {active.get('class') or 'нет'}",
        f"- rect: `{json.dumps(active.get('rect') or {}, ensure_ascii=False)}`",
        "",
        "## Visible Windows",
        "",
    ]

    if windows:
        for index, window in enumerate(windows[:15], start=1):
            lines.append(f"{index}. `{window.get('title') or 'нет'}`")
    else:
        lines.append("- нет")

    lines.extend([
        "",
        "## Proposed Safe Steps",
        "",
    ])

    for index, step in enumerate(result.get("steps") or [], start=1):
        lines.append(f"{index}. {step}")

    lines.extend([
        "",
        "## Safety",
        "",
        "- This planner does not click.",
        "- This planner does not type.",
        "- This planner does not press hotkeys.",
        "- Execution must be a separate confirmed step.",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def plan_desktop_action(goal, write_report=True):
    goal = str(goal or "").strip()
    observation = observe_desktop(write_report=True)
    status, risk_level, markers = _risk_for_goal(goal)
    steps = _suggest_steps(goal, observation, status)

    result = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "status": status,
        "risk_level": risk_level,
        "markers": markers,
        "observation": observation,
        "steps": steps,
        "report_path": "",
    }

    if write_report:
        result["report_path"] = _write_report(result)

    try:
        set_value("desktop_action_planner: да", "да")
        set_value("last_desktop_action_plan_goal", goal)
        set_value("last_desktop_action_plan_status", status)
        set_value("last_desktop_action_plan_risk", risk_level)
        set_value("last_desktop_action_plan_report", result.get("report_path") or "")
    except Exception:
        pass

    return result


def format_desktop_action_plan(result):
    observation = result.get("observation") or {}
    active = observation.get("active_window") or {}
    lines = [
        "Desktop Action Planner:",
        f"- goal: {result.get('goal') or 'нет'}",
        f"- status: {result.get('status')}",
        f"- risk_level: {result.get('risk_level')}",
        f"- active_window: {active.get('title') or 'нет'}",
        f"- screenshot: {observation.get('screenshot_path') or 'нет'}",
        f"- observation_report: {observation.get('report_path') or 'нет'}",
        f"- plan_report: {result.get('report_path') or 'нет'}",
        "",
        "Plan:",
    ]

    for index, step in enumerate(result.get("steps") or [], start=1):
        lines.append(f"{index}. {step}")

    if result.get("status") == "blocked":
        lines.extend([
            "",
            "STOP: план заблокирован safety guard. Автодействия не выполнялись.",
        ])

    return "\n".join(lines)


def latest_desktop_action_plan_report():
    if not REPORTS_DIR.exists():
        return ""

    reports = sorted(REPORTS_DIR.glob("desktop_action_plan_*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(reports[0]) if reports else ""
