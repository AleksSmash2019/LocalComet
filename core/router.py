from core.state import get_value
from modules.natural_command_intents import natural_command_route


def route(user_text: str) -> str:
    text = str(user_text or "").lower().strip()

    if text in ["voice status", "voice test", "voice last report"] or text.startswith("voice speak "):
        return "system"

    natural_route = natural_command_route(user_text)

    if natural_route:
        return natural_route

    last_windows_app = get_value("last_windows_app")

    system_words = [
        "что ты умеешь",
        "помощь",
        "help",
        "status",
        "статус",
        "память",
        "relay status",
        "relay diagnostics",
        "relay smoke",
        "panel relay smoke",
        "patch registry",
        "rollback",
        "after patch",
        "voice status",
        "voice test",
        "voice speak",
        "voice last report",
        "health",
        "project health",
        "health report",
        "regression",
        "regression suite",
        "regression report",
        "safe regression",
        "auto verify",
        "auto verification",
        "verify full",
        "verify quick",
        "check all",
        "post patch verify",
        "автопроверка",
        "проверить всё",
        "регрессия",
        "регрессионная проверка",
        "здоровье проекта",
        "состояние проекта",
        "последние действия",
        "что было последним",
        "последняя модель",
        "какая модель",
        "текущая модель",
    ]

    windows_type_words = [
        "напиши",
        "напечатай",
        "введи",
        "набери",
        "вставь",
        "напечатать",
        "ввести",
        "написать",
    ]

    windows_open_words = [
        "калькулятор",
        "блокнот",
        "notepad",
        "calc",
        "calculator",
        "chrome",
        "хром",
        "paint",
        "пейнт",
        "проводник",
        "explorer",
        "приложение",
        "программу",
    ]

    operator_words = [
        "сравни и выбери",
        "выбери лучший",
        "выбери лучшую",
        "выбери лучшее",
        "найди 5",
        "найди пять",
        "топ",
        "лучшие варианты",
        "лучшие локальные",
        "подбери",
        "сравни варианты",
        "что лучше",
    ]

    report_words = [
        "открой последний отчет",
        "покажи последний отчет",
        "прочитай последний отчет",
        "открой отчет",
        "покажи отчет",
        "последний отчет",
    ]

    research_words = [
        "сделай отчет",
        "создай отчет",
        "собери отчет",
        "подготовь отчет",
        "изучи",
        "проанализируй",
        "исследуй",
        "найди информацию",
        "собери информацию",
    ]

    project_words = [
        "создай современный сайт",
        "сделай современный сайт",
        "создай проект сайта",
        "сайт с формой",
        "сайт с каталогом",
        "сайт компании",
        "сайт логистической",
        "сайт автосервиса",
        "сайт автомойки",
        "проверь и улучши",
    ]

    codegen_words = [
        "создай сайт",
        "сделай сайт",
        "сгенерируй сайт",
        "лендинг",
        "визитку",
        "улучши сайт",
        "улучшить сайт",
        "переделай сайт",
        "редизайн",
        "улучши дизайн",
    ]

    file_words = [
        "создай папку",
        "создай файл",
        "покажи файлы",
        "прочитай файл",
        "удали файл",
        "удали папку",
    ]

    browser_words = [
        "найди",
        "поиск",
        "гугл",
        "google",
        "страницу",
        "браузер",
        "browser",
        "browser last",
        "browser workflow",
        "browser open first",
        "browser read",
        "browser status",
        "статус браузера",
        "состояние браузера",
        "последний поиск",
        "покажи последний поиск",
        "youtube",
        "ютуб",
        "прочитай страницу",
        "открой первый результат",
        "первый результат",
        "открой сайт",
        "открыть сайт",
        "открой созданный сайт",
        "проверь сайт",
        "проверить сайт",
        "проверь страницу",
        "browser screenshot",
        "browser скрин",
        "browser find text",
        "browser найди текст",
        "browser click",
        "browser клик",
        "browser fill",
        "browser введи",
        "browser press",
        "browser нажми",
        "browser links",
        "browser inputs",
        "browser summarize",
        "browser summary",
        "browser tabs",
        "browser new tab",
        "browser switch tab",
        "browser close tab",
        "browser action status",
        "browser research",
        "browser deep research",
        "browser compare",
        "browser page audit",
        "browser form map",
        "browser build site",
        "browser site workflow",
        "browser super",
        "браузер исследуй",
        "браузер аудит",
        "карта форм",
        "аудит страницы",
        "напиши сайт",
        "создай сайт на tilda",
        "сайт на tilda",
        "тильда",
        "используй платформу",
        "browser steps",
        "browser sequence",
    ]

    stability_words = [
        "model test",
        "stability test",
        "тест стабильности",
        "проверка стабильности",
        "автотест",
        "auto stability",
        "auto stability test",
    ]

    gpt_browser_words = [
        "gpt browser",
        "gpt browser close",
        "close gpt browser",
        "гпт браузер",
        "гпт браузер закрыть",
        "закрой гпт браузер",
        "чатгпт браузер",
        "чатгпт браузер закрыть",
        "закрой чатгпт браузер",
        "chatgpt browser",
    ]

    automation_words = [
        "dev task",
        "browser task",
        "browser batch",
        "browser read first",
        "browser compare",
        "browser report",
        "pc task",
        "pc batch",
        "multi task",
        "task status",
        "task report",
        "automation status",
        "after patch",
        "центр автоматизации",
        "автоматизация статус",
        "задача разработки",
        "браузерная задача",
        "задача пк",
        "после патча",
        "комплексная задача",
        "мульти задача",
    ]

    browser_autopilot_words = [
        "browser autopilot",
        "browser task",
        "browser observe",
        "browser plan",
        "браузер autopilot",
        "браузер план",
        "браузер наблюдай",
        "browser research",
        "browser deep research",
        "browser compare",
        "browser page audit",
        "browser form map",
        "browser build site",
        "browser site workflow",
        "browser super",
        "браузер исследуй",
        "браузер аудит",
        "аудит страницы",
        "карта форм",
        "напиши сайт",
        "сайт на tilda",
        "сайт на тильда",
        "тильда",
        "используй платформу",
    ]

    if any(word in text for word in gpt_browser_words):
        return "gpt_browser"

    if any(word in text for word in browser_autopilot_words):
        return "browser"

    if any(word in text for word in automation_words):
        return "automation"

    if any(word in text for word in stability_words):
        return "stability"

    if any(word in text for word in system_words):
        return "system"

    if any(word in text for word in windows_open_words):
        return "windows"

    if last_windows_app and any(word in text for word in windows_type_words):
        return "windows"

    if any(word in text for word in operator_words):
        return "operator"

    if any(word in text for word in report_words):
        return "research"

    if any(word in text for word in research_words):
        return "research"

    if any(word in text for word in project_words):
        return "project"

    if any(word in text for word in codegen_words):
        return "codegen"

    if any(word in text for word in file_words):
        return "files"

    if any(word in text for word in browser_words):
        return "browser"

    return "unknown"
