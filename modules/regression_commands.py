from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from time import perf_counter

from core.state import set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
REGRESSION_REPORTS_DIR = REPORTS_DIR / "regression_commands"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value, limit=1800):
    text = str(value or "")

    if len(text) <= limit:
        return text

    return text[:limit] + "\n...[обрезано]"


def _case(name, command, runner, expects):
    started = perf_counter()

    try:
        output = str(runner())
        checks = [marker in output for marker in expects]
        ok = all(checks)
        error = ""
    except Exception as exc:
        output = ""
        checks = []
        ok = False
        error = str(exc)

    return {
        "name": name,
        "command": command,
        "ok": ok,
        "expects": list(expects),
        "checks": checks,
        "error": error,
        "duration_sec": round(perf_counter() - started, 3),
        "output": _short(output),
    }


def get_regression_command_cases():
    def system_help():
        from agents import system_agent

        return system_agent.handle("help", {})

    def system_status():
        from agents import system_agent

        return system_agent.handle("status", {})

    def project_health():
        from agents import system_agent

        return system_agent.handle("health", {})

    def relay_status():
        from agents import chatgpt_relay_agent

        return chatgpt_relay_agent.handle("status", {})

    def relay_diagnostics():
        from modules.relay_diagnostics import format_relay_diagnostics_text

        return format_relay_diagnostics_text()

    def browser_plan():
        from agents import browser_agent

        return browser_agent.handle(
            "plan",
            {"task": "найди официальный сайт Python и сделай отчет", "max_steps": 8},
        )

    def browser_autopilot_dry():
        from agents import browser_agent

        return browser_agent.handle(
            "autopilot_dry",
            {"task": "найди официальный сайт Python и сделай отчет", "max_steps": 8},
        )

    def patch_registry_status():
        from modules.patch_registry import short_status

        return short_status()

    def auto_verification_smoke():
        from modules.auto_verification import format_auto_verification, run_auto_verification

        result = run_auto_verification(mode="smoke", write_report=False)
        return format_auto_verification(result)

    def browser_super_plan():
        from agents import browser_agent

        return browser_agent.handle(
            "super_plan",
            {"task": "напиши сайт автосервиса используй платформу Tilda", "max_results": 3},
        )

    def natural_intents_plan():
        from modules.natural_command_intents import natural_command_plan

        commands = [
            "сделай мне сайт на тильде для автосервиса",
            "открой YouTube и найди видео про Python decorators",
            "найди на ютубе ролик про настройку LM Studio",
            "проверь весь проект на наличие ошибок",
            "запусти все проверки проекта",
            "открой github.com",
            "открой официальный сайт Python и кратко прочитай",
            "найди официальный сайт playwright и собери ссылки",
            "сделай скриншот текущей страницы",
            "собери ссылки со страницы",
            "покажи поля ввода на странице",
            "найди текст Python на странице",
            "кликни кнопку Login",
            "введи Ivan в поле Name",
            "нажми Enter",
            "покажи здоровье проекта",
            "сделай regression report",
            "проверь проект быстро",
            "запусти тест стабильности",
            "изучи browser-use и Skyvern и сделай отчет",
            "сравни OpenHands browser-use и Skyvern",
            "найди лучшие платформы для сайта автосервиса",
            "открой github.com и сделай скриншот",
            "открой github.com и собери ссылки",
            "открой github.com и кратко прочитай",
            "открой github.com и проанализируй страницу",
            "проанализируй текущую страницу",
            "сделай браузерный отчет по Python official website",
            "сделай браузерный отчет по текущей странице",
            "проверь сайт github.com",
            "проанализируй сайт github.com",
            "открой github.com и сделай полный отчет",
            "заполни форму: Name=Ivan, Email=ivan@example.com, нажми Enter",
            "открой example.com и заполни форму: Name=Ivan; Email=ivan@example.com",
            "заполни поля: Search=Python и нажми кнопку Submit",
            "заполни форму оплаты: card=4111111111111111, cvv=123",
        ]

        return "\n".join(f"{command} -> {natural_command_plan(command)}" for command in commands)

    def routing_smoke():
        from core.router import route

        return "\n".join(
            [
                f"health={route('health')}",
                f"browser={route('browser plan Python')}",
                f"stability={route('stability test')}",
                f"auto_verify={route('auto verify')}",
            ]
        )

    def voice_smoke():
        from core.planner import plan
        from core.router import route
        from modules.voice_control import check_voice_dependencies, classify_voice_command_safety

        safe = classify_voice_command_safety("status")
        blocked = classify_voice_command_safety("оплати заказ банковской картой")
        deps = check_voice_dependencies()

        return "\n".join(
            [
                f"route_voice={route('voice status')}",
                f"plan_voice={plan('voice status', 'system')}",
                f"safe_voice={safe.get('safe')}",
                f"blocked_voice={blocked.get('safe')}",
                f"usable_stt={deps.get('usable_stt')}",
                f"usable_faster_whisper_ru={deps.get('usable_faster_whisper_ru')}",
                f"piper_available={deps.get('piper_available')}",
                f"usable_vosk_ru={deps.get('usable_vosk_ru')}",
            ]
        )

    return [
        {
            "name": "system help",
            "command": "help",
            "runner": system_help,
            "expects": ["LocalComet сейчас умеет"],
        },
        {
            "name": "system status",
            "command": "status",
            "runner": system_status,
            "expects": [
                "Статус LocalComet",
                "git_safety_status: да",
                "chat_automation_intents: да",
                "russian_control_panel_menu: да",
                "gray_control_panel_theme: да",
                "llm_offline_graceful_error_pack: yes",
                "voice_chat_mode: yes",
                "voice_chat_replies: yes",
                "voice_faster_whisper_ru: yes",
                "voice_piper_tts: yes",
                "voice_vosk_russian_stt: yes",
            ],
        },
        {
            "name": "project health",
            "command": "health",
            "runner": project_health,
            "expects": ["Project Health Center:", "Recommended before commit:"],
        },
        {
            "name": "relay status",
            "command": "relay status",
            "runner": relay_status,
            "expects": ["ChatGPT Relay status"],
        },
        {
            "name": "relay diagnostics",
            "command": "relay diagnostics",
            "runner": relay_diagnostics,
            "expects": ["Relay Diagnostics:"],
        },
        {
            "name": "browser plan",
            "command": "browser plan найди официальный сайт Python и сделай отчет",
            "runner": browser_plan,
            "expects": ["Browser Autopilot Plan", "search"],
        },
        {
            "name": "browser autopilot dry",
            "command": "browser autopilot dry найди официальный сайт Python и сделай отчет",
            "runner": browser_autopilot_dry,
            "expects": ["Browser Autopilot", "dry-run", "Report:"],
        },
        {
            "name": "patch registry status",
            "command": "patch registry status",
            "runner": patch_registry_status,
            "expects": ["Patch Registry:"],
        },
        {
            "name": "auto verification smoke",
            "command": "auto verify smoke",
            "runner": auto_verification_smoke,
            "expects": ["Auto Verification:", "status: ok"],
        },
        {
            "name": "browser super plan",
            "command": "browser super plan сайт на Tilda",
            "runner": browser_super_plan,
            "expects": ["Browser Super Plan:", "open_platform", "tilda.cc"],
        },
        {
            "name": "natural command intents",
            "command": "natural intents smoke",
            "runner": natural_intents_plan,
            "expects": [
                "platform_site_workflow",
                "youtube_search",
                "auto_verify_full",
                "open_url",
                "browser_workflow",
                "screenshot",
                "extract_links",
                "extract_inputs",
                "find_text",
                "click_text",
                "fill_label",
                "press_key",
                "health",
                "regression_report",
                "auto_verify",
                "'tool': 'stability'",
                "research",
                "compare_research",
                "natural open page workflow",
                "page_audit",
                "natural search report workflow",
                "natural current page report workflow",
                "natural page report workflow",
                "browser_sequence",
                "natural form workflow",
                "STOP: form workflow",
            ],
        },
        {
            "name": "routing smoke",
            "command": "route health/browser/stability/auto_verify",
            "runner": routing_smoke,
            "expects": ["health=system", "browser=browser", "stability=stability", "auto_verify=system"],
        },
        {
            "name": "voice smoke",
            "command": "voice status / safety",
            "runner": voice_smoke,
            "expects": [
                "route_voice=system",
                "voice_status",
                "safe_voice=True",
                "blocked_voice=False",
                "usable_faster_whisper_ru=",
                "piper_available=",
                "usable_vosk_ru=",
            ],
        },
    ]


def run_regression_command_suite(write_report=True):
    results = []

    for case in get_regression_command_cases():
        results.append(
            _case(
                case["name"],
                case["command"],
                case["runner"],
                case["expects"],
            )
        )

    passed = sum(1 for item in results if item["ok"])
    total = len(results)
    status = "ok" if passed == total else "failed"
    suite = {
        "status": status,
        "passed": passed,
        "total": total,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "results": results,
    }

    set_value("last_regression_suite_status", status)
    set_value("last_regression_suite_score", f"{passed}/{total}")
    set_value("last_regression_suite_generated_at", suite["generated_at"])

    if write_report:
        suite["report"] = str(write_regression_command_report(suite))

    return suite


def format_regression_command_suite(suite=None):
    suite = suite or run_regression_command_suite(write_report=False)
    lines = [
        "Regression Command Suite:",
        f"- status: {suite.get('status')}",
        f"- score: {suite.get('passed')}/{suite.get('total')}",
        f"- generated_at: {suite.get('generated_at')}",
    ]

    if suite.get("report"):
        lines.append(f"- report: {suite.get('report')}")

    lines.append("")
    lines.append("Checks:")

    for item in suite.get("results", []):
        marker = "OK" if item.get("ok") else "FAIL"
        lines.append(
            f"- [{marker}] {item.get('name')} | {item.get('command')} | {item.get('duration_sec')}s"
        )

        if item.get("error"):
            lines.append(f"  error: {item.get('error')}")

    problems = [item for item in suite.get("results", []) if not item.get("ok")]
    lines.append("")
    lines.append("Problems:")

    if problems:
        for item in problems:
            lines.append(f"- {item.get('name')}: expected {item.get('expects')}")
    else:
        lines.append("- Не обнаружены.")

    return "\n".join(lines)


def write_regression_command_report(suite=None):
    suite = suite or run_regression_command_suite(write_report=False)
    REGRESSION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REGRESSION_REPORTS_DIR / f"regression_commands_{_stamp()}.md"

    lines = ["# Regression Command Suite", "", format_regression_command_suite(suite), ""]

    for item in suite.get("results", []):
        lines.extend(
            [
                f"## {item.get('name')}",
                "",
                f"- command: `{item.get('command')}`",
                f"- ok: {item.get('ok')}",
                f"- duration_sec: {item.get('duration_sec')}",
                "",
                "```text",
                item.get("output", ""),
                "```",
                "",
            ]
        )

    path.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_regression_suite_report", str(path))
    return path


def latest_regression_command_report():
    if not REGRESSION_REPORTS_DIR.exists():
        return None

    reports = [path for path in REGRESSION_REPORTS_DIR.glob("regression_commands_*.md") if path.is_file()]

    if not reports:
        return None

    return max(reports, key=lambda path: path.stat().st_mtime)
