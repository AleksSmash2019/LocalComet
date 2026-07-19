import json
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from config import MODEL, LMSTUDIO_API
from core.state import set_value, get_value


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports"


def _ensure_reports_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value, limit: int = 1800):
    text = str(value or "")

    if len(text) <= limit:
        return text

    return text[:limit] + "\n...[обрезано]"


def _ok_text(value):
    text = str(value or "").lower()

    bad_markers = [
        "error:",
        "ошибка:",
        "traceback",
        "не удалось",
        "unknown",
        "неизвестное действие",
        "target page, context or browser has been closed",
    ]

    return bool(text.strip()) and not any(marker in text for marker in bad_markers)


def _run_case(name, func, checker=None):
    started = datetime.now().isoformat(timespec="seconds")

    try:
        result = func()

        if checker is None:
            passed = _ok_text(result)
        else:
            passed = bool(checker(result))

        return {
            "name": name,
            "passed": passed,
            "result": _short(result),
            "error": "",
            "time": started,
        }

    except Exception as e:
        return {
            "name": name,
            "passed": False,
            "result": "",
            "error": _short(traceback.format_exc()),
            "time": started,
        }


def _finish_cases(cases, mode: str):
    score = sum(1 for case in cases if case["passed"])

    if score == len(cases):
        level = "отличная"
    elif score >= max(1, int(len(cases) * 0.7)):
        level = "хорошая"
    elif score >= max(1, int(len(cases) * 0.5)):
        level = "средняя"
    else:
        level = "плохая"

    problems = [
        f"{case['name']}: {case['error'] or case['result']}"
        for case in cases
        if not case["passed"]
    ]

    report_path = _save_report(cases, score, level, problems)
    set_value("last_stability_mode", mode)

    lines = [
        f"{mode.title()} Stability Test завершен.",
        f"Итог: {score}/{len(cases)}",
        f"Стабильность: {level}",
        f"Отчет: {report_path}",
        "",
        "Проверки:",
    ]

    for case in cases:
        mark = "[OK]" if case["passed"] else "[FAIL]"
        lines.append(f"- {mark} {case['name']}")

    lines.append("")
    lines.append("Проблемы:")

    if problems:
        for problem in problems:
            lines.append("- " + _short(problem, 400))
    else:
        lines.append("- Не обнаружены.")

    return "\n".join(lines)


def _help_status_case():
    def check_help_status():
        from agents import system_agent

        help_text = system_agent.handle("help", {})
        status_text = system_agent.handle("status", {})

        ui_markers = [
            "control_panel_ui_rework_pack: да",
            "control_panel_tabs: да",
            "compact_dashboard: да",
            "organized_relay_tab: да",
            "organized_browser_tab: да",
            "organized_autopilot_tab: да",
            "control_panel_chat_commands: да",
            "panel_chat_with_model: да",
            "panel_text_command_input: да",
            "russian_control_panel_menu: да",
            "control_panel_russian_labels: да",
            "russian_command_center_ui: да",
            "gray_control_panel_theme: да",
            "translucent_gray_button_style: да",
            "control_panel_theme_smoke: да",
        ]

        chat_automation_markers = [
            "chat_automation_intents: да",
            "natural_open_url_intent: да",
            "natural_search_workflow: да",
            "natural_page_actions: да",
            "natural_project_checks: да",
            "natural_browser_interactions: да",
            "chat_research_workflow_intents: да",
            "natural_research_intent: да",
            "natural_compare_intent: да",
            "natural_open_page_workflow: да",
            "browser_mission_report_intents: да",
            "natural_browser_report_workflow: да",
            "natural_site_check_workflow: да",
            "natural_form_workflow_intents: да",
            "natural_form_fill_sequence: да",
            "natural_form_submit_guard: да",
        ]

        health_markers = [
            "project_health_center_pack: да",
            "project_health_command: да",
            "project_health_report: да",
            "safe_health_checks: да",
        ]

        regression_markers = [
            "regression_command_suite_pack: да",
            "regression_command_suite: да",
            "regression_command_report: да",
            "safe_regression_commands: да",
        ]

        auto_verification_markers = [
            "auto_verification_pack: да",
            "auto_verify_command: да",
            "auto_verify_after_patch: да",
            "auto_verify_reports: да",
        ]

        browser_super_markers = [
            "browser_super_operator_pack: да",
            "browser_research_reports: да",
            "browser_platform_site_workflow: да",
            "browser_youtube_search: да",
            "natural_command_intents: да",
            "browser_page_audit: да",
            "browser_form_map: да",
            "browser_super_safety_guard: да",
        ]

        markers = [
            "project_boost_pack: да",
            "dashboard_readability_pack: да",
            "patch_registry: да",
            "patch_registry_manual_snapshot: да",
            "compact_ui_patch_version_bar: да",
            "stability_test_modes: да",
            "error_doctor_fix_request: да",
            "llm_provider_foundation: да",
            "llm_offline_graceful_error_pack: yes",
            "llm_connection_error_handling: yes",
            "lmstudio_offline_hint: yes",
            "voice_mode_panel_pack: yes",
            "voice_chat_mode: yes",
            "voice_chat_replies: yes",
            "voice_continuous_dialogue: yes",
            "voice_faster_whisper_ru: yes",
            "voice_piper_tts: yes",
            "voice_vosk_russian_stt: yes",
            "voice_push_to_talk: yes",
            "voice_command_safety_guard: yes",
            "voice_tts: yes",
            "voice_session_reports: yes",
            "codex_bridge_foundation: да",
            "git_safety_status: да",
            *ui_markers,
            *chat_automation_markers,
            *health_markers,
            *regression_markers,
            *auto_verification_markers,
            *browser_super_markers,
            "panel_relay_diagnostics_pack: да",
            "relay_diagnostics: да",
            "relay_smoke_test: да",
            "relay_dry_run_safe: да",
            "browser_action_operator_pack: да",
            "browser_direct_action_routing_fix: да",
            "browser_action_auto_recovery: да",
            "browser_screenshot_action: да",
            "browser_extract_links_inputs: да",
            "browser_task_runner: да",
            "browser_action_safety_guard: да",
            "browser_multi_step_workflow_pack: да",
            "browser_workflow_runner: да",
            "browser_workflow_reports: да",
            "browser_autopilot_operator_pack: да",
            "browser_autopilot_plan: да",
            "browser_autopilot_run: да",
            "browser_autopilot_dry_run: да",
            "browser_autopilot_safety_guard: да",
            "browser_autopilot_reports: да",
            "browser_observe: да",
        ]

        lines = [
            "HELP OK: " + str("LocalComet сейчас умеет" in help_text),
            "STATUS OK: " + str("Статус LocalComet" in status_text),
        ]

        for marker in markers:
            lines.append(marker + " status -> " + str(marker in status_text))

        for marker in ui_markers:
            lines.append(marker + " help -> " + str(marker in help_text))

        for marker in chat_automation_markers:
            lines.append(marker + " help -> " + str(marker in help_text))

        for marker in health_markers:
            lines.append(marker + " help -> " + str(marker in help_text))

        for marker in regression_markers:
            lines.append(marker + " help -> " + str(marker in help_text))

        for marker in auto_verification_markers:
            lines.append(marker + " help -> " + str(marker in help_text))

        for marker in browser_super_markers:
            lines.append(marker + " help -> " + str(marker in help_text))

        return "\n".join(lines)

    return _run_case(
        "help/status markers",
        check_help_status,
        lambda r: (
            "HELP OK: True" in r
            and "STATUS OK: True" in r
            and "False" not in r
        ),
    )


def _memory_case():
    def check_memory():
        from agents import system_agent

        return system_agent.handle("memory", {})

    return _run_case("memory", check_memory, lambda r: bool(str(r).strip()))


def _py_compile_case():
    files = [
        "LocalComet_Control_Panel.py",
        "next/app_v5.py",
        "core/llm.py",
        "modules/voice_control.py",
        "modules/patch_registry.py",
        "modules/llm_provider.py",
        "modules/git_status.py",
        "modules/codex_bridge.py",
        "modules/project_health.py",
        "modules/regression_commands.py",
        "modules/auto_verification.py",
        "modules/relay_diagnostics.py",
        "modules/browser.py",
        "modules/browser_direct.py",
        "modules/browser_super.py",
        "modules/natural_command_intents.py",
        "modules/browser_actions.py",
        "modules/browser_task_runner.py",
        "modules/browser_autopilot.py",
        "modules/stability_test.py",
        "modules/self_edit.py",
        "agents/browser_agent.py",
        "agents/system_agent.py",
        "core/router.py",
        "core/planner.py",
    ]

    def check_py_compile():
        result = subprocess.run(
            ["python", "-m", "py_compile"] + files,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )

        return (
            f"CODE: {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    return _run_case("py_compile key files", check_py_compile, lambda r: "CODE: 0" in r)


def _relay_status_case():
    def check_relay_status():
        from agents import chatgpt_relay_agent

        return chatgpt_relay_agent.handle("status", {})

    return _run_case("relay status", check_relay_status, lambda r: "ChatGPT Relay status" in r)


def _project_health_case():
    def check_project_health():
        from agents import system_agent
        from core.router import route
        from modules import project_health

        health = project_health.get_project_health()
        text = project_health.format_project_health_text(health)
        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})
        agent_text = system_agent.handle("health", {})

        checks = [
            callable(project_health.get_project_health),
            callable(project_health.format_project_health_text),
            callable(project_health.write_project_health_report),
            isinstance(health, dict),
            health.get("status") in ["ok", "attention"],
            "Project Health Center:" in text,
            "Recommended before commit:" in text,
            "Project Health Center:" in agent_text,
            route("health") == "system",
            route("project health") == "system",
            "project_health_center_pack: да" in status_text,
            "project_health_command: да" in status_text,
            "project_health_report: да" in status_text,
            "safe_health_checks: да" in status_text,
            "project_health_center_pack: да" in help_text,
            "project_health_command: да" in help_text,
            "health report" in help_text,
        ]

        return "\n".join(f"project_health_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "project health center",
        check_project_health,
        lambda r: "False" not in r and "project_health_check_17: True" in r,
    )


def _regression_command_suite_case():
    def check_regression_command_suite():
        from agents import system_agent
        from core.router import route
        from modules import regression_commands

        suite = regression_commands.run_regression_command_suite(write_report=False)
        text = regression_commands.format_regression_command_suite(suite)
        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})
        agent_text = system_agent.handle("regression_suite", {})

        checks = [
            callable(regression_commands.get_regression_command_cases),
            callable(regression_commands.run_regression_command_suite),
            callable(regression_commands.format_regression_command_suite),
            callable(regression_commands.write_regression_command_report),
            suite.get("status") == "ok",
            suite.get("passed") == suite.get("total"),
            "Regression Command Suite:" in text,
            "Problems:" in text,
            "Regression Command Suite:" in agent_text,
            route("regression suite") == "system",
            route("regression report") == "system",
            "regression_command_suite_pack: да" in status_text,
            "regression_command_suite: да" in status_text,
            "regression_command_report: да" in status_text,
            "safe_regression_commands: да" in status_text,
            "regression_command_suite_pack: да" in help_text,
            "regression suite" in help_text,
        ]

        return "\n".join(f"regression_suite_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "regression command suite",
        check_regression_command_suite,
        lambda r: "False" not in r and "regression_suite_check_17: True" in r,
    )


def _auto_verification_case():
    def check_auto_verification():
        from agents import system_agent
        from core.router import route
        from modules import auto_verification

        result = auto_verification.run_auto_verification(mode="smoke", write_report=False)
        text = auto_verification.format_auto_verification(result)
        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})
        agent_text = system_agent.handle("auto_verify", {})

        checks = [
            callable(auto_verification.get_auto_verification_files),
            callable(auto_verification.run_auto_verification),
            callable(auto_verification.format_auto_verification),
            callable(auto_verification.write_auto_verification_report),
            callable(auto_verification.latest_auto_verification_report),
            result.get("status") == "ok",
            result.get("passed") == result.get("total"),
            "Auto Verification:" in text,
            "Auto Verification:" in agent_text,
            route("auto verify") == "system",
            route("verify full") == "system",
            "auto_verification_pack: да" in status_text,
            "auto_verify_command: да" in status_text,
            "auto_verify_after_patch: да" in status_text,
            "auto_verify_reports: да" in status_text,
            "auto_verification_pack: да" in help_text,
            "auto verify" in help_text,
        ]

        return "\n".join(f"auto_verify_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "auto verification foundation",
        check_auto_verification,
        lambda r: "False" not in r and "auto_verify_check_17: True" in r,
    )


def _relay_diagnostics_case():
    def check_relay_diagnostics():
        from agents import chatgpt_relay_agent, system_agent
        from modules import relay_diagnostics

        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})
        diagnostics = relay_diagnostics.get_relay_diagnostics()
        diagnostics_text = relay_diagnostics.format_relay_diagnostics_text(diagnostics)
        app_text = (ROOT_DIR / "next" / "app_v5.py").read_text(encoding="utf-8", errors="replace")

        checks = [
            callable(relay_diagnostics.get_relay_diagnostics),
            callable(relay_diagnostics.format_relay_diagnostics_text),
            callable(relay_diagnostics.run_relay_smoke_test),
            "Relay Diagnostics:" in diagnostics_text,
            "panel_relay_diagnostics_pack: да" in status_text,
            "relay_diagnostics: да" in status_text,
            "relay_smoke_test: да" in status_text,
            "relay_dry_run_safe: да" in status_text,
            "panel_relay_diagnostics_pack: да" in help_text,
            "relay_diagnostics: да" in help_text,
            "relay_smoke_test: да" in help_text,
            "relay_dry_run_safe: да" in help_text,
            "relay diagnostics" in help_text,
            "relay smoke" in help_text,
            "relay diagnostics" in app_text,
            "relay smoke" in app_text,
            "panel relay smoke" in app_text,
            "Relay Diagnostics:" in chatgpt_relay_agent.handle("diagnostics", {}),
        ]

        return "\n".join(f"relay_diag_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "relay diagnostics foundation",
        check_relay_diagnostics,
        lambda r: "False" not in r and "relay_diag_check_18: True" in r,
    )


def _patch_registry_case():
    def check_patch_registry():
        from modules.patch_registry import short_status

        return short_status()

    return _run_case("patch registry status", check_patch_registry, lambda r: "Patch Registry:" in r)


def _browser_action_foundation_case():
    def check_browser_actions():
        import modules.browser_actions as browser_actions
        import modules.browser_task_runner as browser_task_runner

        checks = [
            callable(browser_actions.browser_action_status),
            callable(browser_actions.screenshot_page),
            callable(browser_actions.extract_links),
            callable(browser_actions.extract_inputs),
            callable(browser_actions.summarize_page),
            callable(browser_task_runner.run_browser_steps),
            callable(browser_task_runner.run_browser_workflow),
            browser_actions._is_dangerous_browser_action("купить и оплатить"),
        ]

        return "\n".join(f"check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "browser action foundation",
        check_browser_actions,
        lambda r: "False" not in r and "check_8: True" in r,
    )


def _browser_direct_routing_case():
    def check_browser_direct_routing():
        from core.router import route
        from core.planner import plan
        from modules.browser_direct import browser_action_direct_plan

        commands = {
            "browser summarize": "summarize",
            "browser links": "extract_links",
            "browser inputs": "extract_inputs",
        }

        lines = []

        for command, expected_action in commands.items():
            routed = route(command)
            planned_default = plan(command)
            planned_browser = plan(command, "browser")
            direct = browser_action_direct_plan(command)
            lines.append(
                f"{command}: route={routed}; "
                f"plan={planned_default.get('action')}; "
                f"browser_plan={planned_browser.get('action')}; "
                f"direct={direct.get('action') if direct else 'none'}; "
                f"ok={routed == 'browser' and planned_default.get('action') == expected_action and planned_browser.get('action') == expected_action and direct and direct.get('action') == expected_action}"
            )

        return "\n".join(lines)

    return _run_case(
        "browser direct action routing",
        check_browser_direct_routing,
        lambda r: "ok=False" not in r and "browser summarize" in r and "browser links" in r and "browser inputs" in r,
    )


def _browser_action_auto_recovery_case():
    def check_browser_action_auto_recovery():
        import modules.browser_actions as browser_actions

        class BlankPage:
            url = "about:blank"

        old_get_page = browser_actions.get_active_page_for_actions
        old_save_report = browser_actions._save_action_report
        old_query = get_value("last_browser_query", "")
        old_current_url = get_value("current_url", "")

        try:
            set_value("last_browser_query", "")
            set_value("current_url", "about:blank")
            browser_actions.get_active_page_for_actions = lambda: BlankPage()
            browser_actions._save_action_report = lambda *args, **kwargs: ""

            helper_blank = browser_actions._is_blank_page(BlankPage())
            helper_stop = browser_actions._ensure_action_page(BlankPage(), recover=False)
            summary = browser_actions.summarize_page()
            links = browser_actions.extract_links()
            inputs = browser_actions.extract_inputs()

            return "\n".join([
                "helper_blank: " + str(helper_blank),
                "helper_stop_has_hint: " + str("browser search <запрос>" in helper_stop),
                "summary_has_hint: " + str("Страница пустая" in summary and "URL: about:blank" not in summary),
                "links_not_empty_json: " + str(links.strip() != "[]" and "Страница пустая" in links),
                "inputs_not_empty_json: " + str(inputs.strip() != "[]" and "Страница пустая" in inputs),
            ])
        finally:
            browser_actions.get_active_page_for_actions = old_get_page
            browser_actions._save_action_report = old_save_report
            set_value("last_browser_query", old_query)
            set_value("current_url", old_current_url)

    return _run_case(
        "browser action auto recovery",
        check_browser_action_auto_recovery,
        lambda r: "False" not in r and "helper_blank: True" in r,
    )


def _browser_autopilot_case():
    def check_browser_autopilot():
        from agents import system_agent
        from core.router import route
        from modules.browser_autopilot import (
            build_browser_autopilot_plan,
            format_browser_autopilot_plan,
            is_browser_task_safe,
            observe_browser_page,
            run_browser_autopilot,
        )
        from modules.browser_direct import browser_action_direct_plan

        help_text = system_agent.handle("help", {})
        status_text = system_agent.handle("status", {})
        unsafe_ok, unsafe_reason = is_browser_task_safe("оплати заказ банковской картой")
        safe_plan = build_browser_autopilot_plan("найди официальный сайт Python и сделай отчет", mode="dry_run", max_steps=8)
        blocked_plan = build_browser_autopilot_plan("оплати заказ банковской картой", mode="dry_run", max_steps=8)
        direct_plan = browser_action_direct_plan("browser plan найди официальный сайт Python и сделай отчет")
        direct_dry = browser_action_direct_plan("browser autopilot dry найди официальный сайт Python и сделай отчет")
        direct_task = browser_action_direct_plan("browser task проанализируй текущую страницу и собери ссылки")

        checks = [
            callable(build_browser_autopilot_plan),
            callable(run_browser_autopilot),
            callable(is_browser_task_safe),
            callable(observe_browser_page),
            callable(format_browser_autopilot_plan),
            unsafe_ok is False and bool(unsafe_reason),
            bool(safe_plan.get("steps")),
            bool(blocked_plan.get("blocked_reason")),
            route("browser autopilot dry найди Python") == "browser",
            route("browser task проанализируй текущую страницу") == "browser",
            direct_plan and direct_plan.get("action") == "plan",
            direct_dry and direct_dry.get("action") == "autopilot_dry",
            direct_task and direct_task.get("action") == "browser_task",
            "browser_autopilot_operator_pack: да" in status_text,
            "browser_autopilot_plan: да" in status_text,
            "browser_autopilot_run: да" in status_text,
            "browser_autopilot_dry_run: да" in status_text,
            "browser_autopilot_safety_guard: да" in status_text,
            "browser_autopilot_reports: да" in status_text,
            "browser_observe: да" in status_text,
            "browser plan <task>" in help_text,
            "browser autopilot dry <task>" in help_text,
            "browser task <task>" in help_text,
        ]

        return "\n".join(f"browser_autopilot_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "browser autopilot foundation",
        check_browser_autopilot,
        lambda r: "False" not in r and "browser_autopilot_check_23: True" in r,
    )


def _browser_super_case():
    def check_browser_super():
        from agents import browser_agent, system_agent
        from core.planner import plan
        from core.router import route
        from modules.browser_direct import browser_action_direct_plan
        from modules.browser_super import (
            build_browser_super_plan,
            classify_browser_super_task,
            format_browser_super_plan,
        )
        from modules.natural_command_intents import natural_command_plan, natural_command_route

        help_text = system_agent.handle("help", {})
        status_text = system_agent.handle("status", {})
        platform_task = "напиши сайт автосервиса используй платформу Tilda"
        platform_plan = build_browser_super_plan(platform_task, mode="dry_run", max_results=3)
        research_plan = build_browser_super_plan("исследуй browser-use и Skyvern", mode="dry_run", max_results=3)
        direct_research = browser_action_direct_plan("browser research лучшие конструкторы сайтов")
        direct_site = browser_action_direct_plan("browser build site сайт автосервиса используй платформу Tilda")
        agent_plan_text = browser_agent.handle("super_plan", {"task": platform_task})
        planner_result = plan(platform_task, "browser")
        natural_tilda = natural_command_plan("сделай мне сайт на тильде для автосервиса")
        natural_youtube = natural_command_plan("открой YouTube и найди видео про Python decorators")
        natural_youtube_ru = natural_command_plan("найди на ютубе ролик про настройку LM Studio")
        natural_project_check = natural_command_plan("проверь весь проект на наличие ошибок")
        natural_project_checks = natural_command_plan("запусти все проверки проекта")

        checks = [
            classify_browser_super_task(platform_task) == "site_workflow",
            platform_plan.get("kind") == "site_workflow",
            any(step.get("action") == "open_platform" for step in platform_plan.get("steps", [])),
            "tilda.cc" in str(platform_plan).lower(),
            research_plan.get("kind") in ["research", "smart_browser"],
            "Browser Super Plan:" in format_browser_super_plan(platform_plan),
            "Browser Super Plan:" in agent_plan_text,
            route("browser research лучшие ai браузеры") == "browser",
            route(platform_task) == "browser",
            direct_research and direct_research.get("action") == "research",
            direct_site and direct_site.get("action") == "platform_site_workflow",
            planner_result.get("tool") == "browser",
            planner_result.get("action") == "platform_site_workflow",
            natural_tilda and natural_tilda.get("action") == "platform_site_workflow",
            natural_youtube and natural_youtube.get("action") == "youtube_search",
            natural_youtube_ru and natural_youtube_ru.get("action") == "youtube_search",
            natural_project_check and natural_project_check.get("action") == "auto_verify_full",
            natural_project_checks and natural_project_checks.get("action") == "auto_verify_full",
            natural_command_route("проверь весь проект на наличие ошибок") == "system",
            "browser_super_operator_pack: да" in status_text,
            "browser_research_reports: да" in status_text,
            "browser_platform_site_workflow: да" in status_text,
            "browser_youtube_search: да" in status_text,
            "natural_command_intents: да" in status_text,
            "browser_page_audit: да" in status_text,
            "browser_form_map: да" in status_text,
            "browser_super_safety_guard: да" in status_text,
            "browser_super_operator_pack: да" in help_text,
            "browser_youtube_search: да" in help_text,
            "natural_command_intents: да" in help_text,
            "browser research <topic>" in help_text,
            "browser build site <prompt>" in help_text,
        ]

        return "\n".join(f"browser_super_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "browser super operator foundation",
        check_browser_super,
        lambda r: "False" not in r and "browser_super_check_32: True" in r,
    )


def _chat_automation_intents_case():
    def check_chat_automation_intents():
        from agents import system_agent
        from core.planner import plan
        from core.router import route
        from modules.natural_command_intents import natural_command_plan, natural_command_route

        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})

        cases = [
            ("открой github.com", "browser", "open_url"),
            ("открой сайт гугл", "browser", "open_url"),
            ("открой официальный сайт Python и кратко прочитай", "browser", "browser_workflow"),
            ("найди в интернете browser-use github и открой первый результат", "browser", "browser_workflow"),
            ("найди официальный сайт playwright и собери ссылки", "browser", "browser_workflow"),
            ("сделай скриншот текущей страницы", "browser", "screenshot"),
            ("собери ссылки со страницы", "browser", "extract_links"),
            ("покажи поля ввода на странице", "browser", "extract_inputs"),
            ("найди текст Python на странице", "browser", "find_text"),
            ("кликни кнопку Login", "browser", "click_text"),
            ("введи Ivan в поле Name", "browser", "fill_label"),
            ("нажми Enter", "browser", "press_key"),
            ("покажи здоровье проекта", "system", "health"),
            ("сделай regression report", "system", "regression_report"),
            ("проверь проект быстро", "system", "auto_verify"),
            ("запусти тест стабильности", "stability", "run"),
            ("изучи browser-use и Skyvern и сделай отчет", "browser", "research"),
            ("сравни OpenHands browser-use и Skyvern", "browser", "compare_research"),
            ("найди лучшие платформы для сайта автосервиса", "browser", "research"),
            ("открой github.com и сделай скриншот", "browser", "browser_workflow"),
            ("открой github.com и собери ссылки", "browser", "browser_workflow"),
            ("открой github.com и кратко прочитай", "browser", "browser_workflow"),
            ("открой github.com и проанализируй страницу", "browser", "browser_workflow"),
            ("проанализируй текущую страницу", "browser", "page_audit"),
            ("сделай браузерный отчет по Python official website", "browser", "browser_workflow"),
            ("сделай браузерный отчет по текущей странице", "browser", "browser_workflow"),
            ("проверь сайт github.com", "browser", "browser_workflow"),
            ("проанализируй сайт github.com", "browser", "browser_workflow"),
            ("открой github.com и сделай полный отчет", "browser", "browser_workflow"),
            ("заполни форму: Name=Ivan, Email=ivan@example.com, нажми Enter", "browser", "browser_sequence"),
            ("открой example.com и заполни форму: Name=Ivan; Email=ivan@example.com", "browser", "browser_sequence"),
            ("заполни поля: Search=Python и нажми кнопку Submit", "browser", "browser_sequence"),
            ("заполни форму оплаты: card=4111111111111111, cvv=123", "none", "answer"),
        ]

        checks = []

        for command, expected_tool, expected_action in cases:
            planned = natural_command_plan(command) or {}
            checks.append(
                planned.get("tool") == expected_tool
                and planned.get("action") == expected_action
                and natural_command_route(command) == expected_tool
                and route(command) == expected_tool
                and plan(command).get("action") == expected_action
            )

        workflow = natural_command_plan("открой официальный сайт Python и кратко прочитай") or {}
        workflow_steps = workflow.get("steps", [])
        search_report = natural_command_plan("сделай браузерный отчет по Python official website") or {}
        search_report_steps = search_report.get("steps", [])
        page_report = natural_command_plan("проверь сайт github.com") or {}
        page_report_steps = page_report.get("steps", [])
        form_sequence = natural_command_plan("заполни форму: Name=Ivan, Email=ivan@example.com, нажми Enter") or {}
        form_steps = form_sequence.get("steps", [])
        form_with_url = natural_command_plan("открой example.com и заполни форму: Name=Ivan; Email=ivan@example.com") or {}
        form_url_steps = form_with_url.get("steps", [])
        form_submit = natural_command_plan("заполни поля: Search=Python и нажми кнопку Submit") or {}
        form_submit_steps = form_submit.get("steps", [])
        form_stop = natural_command_plan("заполни форму оплаты: card=4111111111111111, cvv=123") or {}

        checks.extend([
            natural_command_plan("multi task найди Python и открой папку отчетов") is None,
            natural_command_route("multi task найди Python и открой папку отчетов") is None,
            natural_command_plan("browser batch Godot") is None,
            natural_command_plan("dev task улучши браузер") is None,
            any(step.get("action") == "search" for step in workflow_steps),
            any(step.get("action") == "open_first" for step in workflow_steps),
            any(step.get("action") == "summarize" for step in workflow_steps),
            search_report.get("title") == "natural search report workflow",
            any(step.get("action") == "open_first" for step in search_report_steps),
            any(step.get("action") == "extract_inputs" for step in search_report_steps),
            page_report.get("title") == "natural page report workflow",
            any(step.get("action") == "open_url" for step in page_report_steps),
            any(step.get("action") == "screenshot" for step in page_report_steps),
            form_sequence.get("title") == "natural form workflow",
            len([step for step in form_steps if step.get("action") == "fill_label"]) == 2,
            any(step.get("action") == "press_key" for step in form_steps),
            any(step.get("action") == "open_url" for step in form_url_steps),
            any(step.get("action") == "click_text" for step in form_submit_steps),
            form_stop.get("tool") == "none" and "STOP: form workflow" in form_stop.get("text", ""),
            "chat_automation_intents: да" in status_text,
            "natural_open_url_intent: да" in status_text,
            "natural_search_workflow: да" in status_text,
            "natural_page_actions: да" in status_text,
            "natural_project_checks: да" in status_text,
            "natural_browser_interactions: да" in status_text,
            "chat_research_workflow_intents: да" in status_text,
            "natural_research_intent: да" in status_text,
            "natural_compare_intent: да" in status_text,
            "natural_open_page_workflow: да" in status_text,
            "browser_mission_report_intents: да" in status_text,
            "natural_browser_report_workflow: да" in status_text,
            "natural_site_check_workflow: да" in status_text,
            "natural_form_workflow_intents: да" in status_text,
            "natural_form_fill_sequence: да" in status_text,
            "natural_form_submit_guard: да" in status_text,
            "chat_automation_intents: да" in help_text,
            "natural_search_workflow: да" in help_text,
            "chat_research_workflow_intents: да" in help_text,
            "browser_mission_report_intents: да" in help_text,
            "natural_form_workflow_intents: да" in help_text,
        ])

        return "\n".join(f"chat_automation_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "chat automation intents",
        check_chat_automation_intents,
        lambda r: "False" not in r and "chat_automation_check_73: True" in r,
    )


def _russian_control_panel_menu_case():
    def check_russian_control_panel_menu():
        from agents import system_agent

        panel_text = (ROOT_DIR / "LocalComet_Control_Panel.py").read_text(encoding="utf-8", errors="replace")
        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})

        labels = [
            "Обзор",
            "Чат / команды",
            "Патчи / Relay",
            "Браузер",
            "Автопилот",
            "Проверки",
            "Отчеты / инструменты",
            "Логи",
            "Главные действия",
            "Создать request",
            "Применить",
            "Открыть отчет",
            "Очистить лог",
        ]

        checks = [
            "Русское меню панели" in panel_text,
            all(label in panel_text for label in labels),
            "russian_control_panel_menu: да" in status_text,
            "control_panel_russian_labels: да" in status_text,
            "russian_command_center_ui: да" in status_text,
            "gray_control_panel_theme: да" in status_text,
            "translucent_gray_button_style: да" in status_text,
            "control_panel_theme_smoke: да" in status_text,
            "russian_control_panel_menu: да" in help_text,
            "control_panel_russian_labels: да" in help_text,
            "russian_command_center_ui: да" in help_text,
            "gray_control_panel_theme: да" in help_text,
            "translucent_gray_button_style: да" in help_text,
            "control_panel_theme_smoke: да" in help_text,
            "PANEL_BG" in panel_text,
            "PANEL_BUTTON_ACTIVE" in panel_text,
            "_configure_gray_theme" in panel_text,
            'style.theme_use("clam")' in panel_text,
            'root.attributes("-alpha", 0.98)' in panel_text,
        ]

        return "\n".join(f"russian_menu_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "russian control panel menu",
        check_russian_control_panel_menu,
        lambda r: "False" not in r and "russian_menu_check_18: True" in r,
    )


def _control_panel_init_smoke_case():
    def check_control_panel_init_smoke():
        import tkinter as tk
        import LocalComet_Control_Panel as panel

        root = tk.Tk()
        root.withdraw()

        try:
            app = panel.LocalCometControlPanel(root)
            root.update_idletasks()

            tab_count = app.notebook.index("end")
            tab_texts = [
                str(app.notebook.tab(index, "text"))
                for index in range(tab_count)
            ]
            required_tabs = [
                "🚀 Command Center",
                "Обзор",
                "Чат / команды",
                "Патчи / Relay",
                "Браузер",
                "Автопилот",
                "Voice",
                "Проверки",
                "Отчеты / инструменты",
                "Логи",
            ]

            checks = [
                panel.LOCALCOMET_VERSION == "v6.02",
                "Command Center Control Panel" in panel.LOCALCOMET_VERSION_LABEL,
                tab_count >= len(required_tabs),
                tab_texts[0] == "🚀 Command Center",
                all(tab in tab_texts for tab in required_tabs),
                hasattr(app, "quick_goal_text") and app.quick_goal_text is not None,
                app.output is not None,
                app.chat_input is not None,
                callable(getattr(app, "refresh_statuses", None)),
                app.dashboard_status_line_var.get().startswith("статус:"),
                callable(getattr(app, "quick_create_request_and_open_chatgpt", None)),
                callable(getattr(app, "import_and_validate", None)),
            ]

            lines = [
                "tab_count: " + str(tab_count),
                "tabs: " + " | ".join(tab_texts),
            ]
            lines.extend(f"panel_init_check_{index}: {value}" for index, value in enumerate(checks, start=1))
            return "\n".join(lines)
        finally:
            root.destroy()

    return _run_case(
        "control panel init smoke",
        check_control_panel_init_smoke,
        lambda r: "False" not in r and "panel_init_check_12: True" in r,
    )



def _llm_offline_graceful_error_case():
    def check_llm_offline_graceful_error():
        from agents import system_agent
        from core import llm

        message = llm.format_llm_offline_message()
        checks = [
            hasattr(llm, "format_llm_offline_message"),
            hasattr(llm, "is_llm_offline_error"),
            "LM Studio Local Server" in message,
            "http://127.0.0.1:1234" in message,
            llm.is_llm_offline_error(message),
            "llm_offline_graceful_error_pack: yes" in system_agent.handle("status", {}),
            "llm_connection_error_handling: yes" in system_agent.handle("status", {}),
            "lmstudio_offline_hint: yes" in system_agent.handle("help", {}),
        ]
        return "\n".join(f"llm_offline_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "llm offline graceful error",
        check_llm_offline_graceful_error,
        lambda r: "False" not in r and "llm_offline_check_8: True" in r,
    )


def _voice_mode_foundation_case():
    def check_voice_mode_foundation():
        from agents import system_agent
        from core.planner import plan
        from core.router import route
        from modules import voice_control

        safe = voice_control.classify_voice_command_safety("status")
        blocked = voice_control.classify_voice_command_safety("оплати заказ банковской картой")
        deps = voice_control.check_voice_dependencies()
        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})
        checks = [
            hasattr(voice_control, "check_voice_dependencies"),
            hasattr(voice_control, "transcribe_once"),
            hasattr(voice_control, "speak_text"),
            hasattr(voice_control, "classify_voice_command_safety"),
            safe.get("safe") is True,
            blocked.get("safe") is False,
            blocked.get("needs_confirmation") is True,
            isinstance(deps, dict),
            route("voice status") == "system",
            plan("voice status", "system").get("action") == "voice_status",
            "voice_mode_panel_pack: yes" in status_text,
            "voice_chat_mode: yes" in status_text,
            "voice_chat_replies: yes" in status_text,
            "voice_continuous_dialogue: yes" in status_text,
            "voice_faster_whisper_ru: yes" in status_text,
            "voice_piper_tts: yes" in status_text,
            "voice_vosk_russian_stt: yes" in status_text,
            "voice_push_to_talk: yes" in help_text,
            "voice_command_safety_guard: yes" in status_text,
            "voice_tts: yes" in status_text,
            "voice_session_reports: yes" in status_text,
            "usable_vosk_ru" in deps,
            "vosk_model_path" in deps,
            "usable_faster_whisper_ru" in deps,
            "piper_available" in deps,
        ]
        return "\n".join(f"voice_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "voice mode foundation",
        check_voice_mode_foundation,
        lambda r: "False" not in r and "voice_check_25: True" in r,
    )


def run_fast_stability_test():
    cases = [
        _help_status_case(),
        _llm_offline_graceful_error_case(),
        _voice_mode_foundation_case(),
        _memory_case(),
        _py_compile_case(),
        _project_health_case(),
        _regression_command_suite_case(),
        _auto_verification_case(),
        _relay_status_case(),
        _relay_diagnostics_case(),
        _patch_registry_case(),
        _browser_action_foundation_case(),
        _browser_direct_routing_case(),
        _browser_action_auto_recovery_case(),
        _browser_autopilot_case(),
        _browser_super_case(),
        _chat_automation_intents_case(),
        _russian_control_panel_menu_case(),
        _control_panel_init_smoke_case(),
    ]

    return _finish_cases(cases, "fast")


def run_normal_stability_test():
    cases = [
        _help_status_case(),
        _llm_offline_graceful_error_case(),
        _voice_mode_foundation_case(),
        _memory_case(),
        _py_compile_case(),
        _project_health_case(),
        _regression_command_suite_case(),
        _auto_verification_case(),
        _relay_status_case(),
        _relay_diagnostics_case(),
        _patch_registry_case(),
        _browser_action_foundation_case(),
        _browser_direct_routing_case(),
        _browser_action_auto_recovery_case(),
        _browser_autopilot_case(),
        _browser_super_case(),
        _chat_automation_intents_case(),
        _russian_control_panel_menu_case(),
        _control_panel_init_smoke_case(),
    ]

    def check_router():
        from core.router import route

        return (
            f"browser={route('найди официальный сайт Python')}\n"
            f"stability={route('stability test')}\n"
            f"automation={route('automation status')}"
        )

    cases.append(_run_case("router", check_router, lambda r: "browser" in r and "stability" in r and "automation" in r))

    def check_planner():
        from core.planner import plan

        return json.dumps(
            {
                "stability": plan("stability test", "stability"),
                "automation": plan("automation status", "automation"),
                "gpt_browser": plan("gpt browser status", "gpt_browser"),
            },
            ensure_ascii=False,
        )

    cases.append(_run_case("planner", check_planner, lambda r: '"tool": "stability"' in r and '"tool": "automation"' in r))

    def check_browser_status():
        from agents import browser_agent

        return browser_agent.handle("status", {})

    cases.append(_run_case("browser status", check_browser_status, lambda r: "Browser status" in r))

    return _finish_cases(cases, "normal")


def run_full_stability_test():
    cases = [
        _help_status_case(),
        _llm_offline_graceful_error_case(),
        _voice_mode_foundation_case(),
        _memory_case(),
        _py_compile_case(),
        _project_health_case(),
        _regression_command_suite_case(),
        _auto_verification_case(),
        _relay_status_case(),
        _relay_diagnostics_case(),
        _patch_registry_case(),
        _browser_action_foundation_case(),
        _browser_direct_routing_case(),
        _browser_action_auto_recovery_case(),
        _browser_autopilot_case(),
        _browser_super_case(),
        _chat_automation_intents_case(),
        _russian_control_panel_menu_case(),
        _control_panel_init_smoke_case(),
    ]

    def check_router():
        from core.router import route

        commands = {
            "найди официальный сайт Python": "browser",
            "stability test": "stability",
            "automation status": "automation",
            "auto verify": "system",
            "regression suite": "system",
            "health": "system",
        }

        lines = []

        for command, expected in commands.items():
            routed = route(command)
            lines.append(f"{command}: route={routed}; expected={expected}; ok={routed == expected}")

        return "\n".join(lines)

    cases.append(
        _run_case(
            "router coverage",
            check_router,
            lambda r: "ok=False" not in r and "stability test" in r,
        )
    )

    def check_planner():
        from core.planner import plan

        checks = [
            plan("stability test", "stability").get("tool") == "stability",
            plan("automation status", "automation").get("tool") == "automation",
            plan("gpt browser status", "gpt_browser").get("tool") == "gpt_browser",
            plan("auto verify", "system").get("tool") == "system",
            plan("regression suite", "system").get("tool") == "system",
            plan("health", "system").get("tool") == "system",
        ]

        return "\n".join(f"planner_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    cases.append(
        _run_case(
            "planner coverage",
            check_planner,
            lambda r: "False" not in r and "planner_check_6: True" in r,
        )
    )

    def check_browser_status():
        from agents import browser_agent

        return browser_agent.handle("status", {})

    cases.append(
        _run_case(
            "browser status",
            check_browser_status,
            lambda r: "Browser status" in r,
        )
    )

    def check_command_center_module():
        from modules.command_center_ui import build_command_center

        panel_text = (ROOT_DIR / "LocalComet_Control_Panel.py").read_text(encoding="utf-8", errors="replace")
        ui_text = (ROOT_DIR / "modules" / "command_center_ui.py").read_text(encoding="utf-8", errors="replace")

        checks = [
            callable(build_command_center),
            "build_command_center" in panel_text,
            "modules.command_center_ui" in panel_text,
            "🚀 Command Center" in panel_text,
            "Command Center" in ui_text,
            "REQUEST + CHATGPT" in ui_text or "NEXT ACTION" in ui_text,
            "STATUS" in ui_text or "STATUS CARDS" in ui_text,
            "WORKFLOW" in ui_text,
        ]

        return "\n".join(f"command_center_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    cases.append(
        _run_case(
            "command center module",
            check_command_center_module,
            lambda r: "False" not in r and "command_center_check_8: True" in r,
        )
    )

    return _finish_cases(cases, "full")



def _save_report(cases, score, level, problems):
    _ensure_reports_dir()

    path = REPORTS_DIR / f"{_stamp()}_auto_stability_test.md"
    total = len(cases)

    lines = [
        "# LocalComet Auto Stability Test",
        "",
        f"- Время: {datetime.now().isoformat(timespec='seconds')}",
        f"- MODEL: {MODEL}",
        f"- API: {LMSTUDIO_API}",
        f"- Итог: {score}/{total}",
        f"- Стабильность: {level}",
        "",
        "## Проблемы",
    ]

    if problems:
        for problem in problems:
            lines.append(f"- {problem}")
    else:
        lines.append("- Не обнаружены.")

    lines.extend(["", "## Проверки"])

    for index, case in enumerate(cases, start=1):
        mark = "[OK]" if case["passed"] else "[FAIL]"

        lines.extend([
            "",
            f"### {index}. {mark} {case['name']}",
            "",
            "**Result:**",
            "```text",
            str(case.get("result") or "нет"),
            "```",
        ])

        if case.get("error"):
            lines.extend([
                "",
                "**Error:**",
                "```text",
                str(case.get("error")),
                "```",
            ])

    path.write_text("\n".join(lines), encoding="utf-8")

    set_value("last_stability_report", str(path))
    set_value("last_stability_score", str(score))
    set_value("last_stability_level", level)
    set_value("last_stability_problems", problems)

    return path


def run_auto_stability_test():
    cases = []

    def check_help_status():
        from agents import system_agent

        help_text = system_agent.handle("help", {})
        status_text = system_agent.handle("status", {})

        return (
            "HELP OK: " + str("LocalComet сейчас умеет" in help_text) + "\n"
            "STATUS OK: " + str("Статус LocalComet" in status_text) + "\n"
            "FILE RESPONSE PROMPT OK: " + str("скачиваемый файл response.json" in help_text) + "\n"
            "MANUAL RELAY MODE OK: " + str("надежный ручной режим" in help_text) + "\n"
            "REJECT EMPTY PATCH OK: " + str("reject_empty_confirmation_patch" in status_text) + "\n"
            "RESPONSE MODE STATUS OK: " + str("last_gpt_browser_response_mode" in status_text) + "\n"
            "BUTTON PANEL HELP OK: " + str("LocalComet_Control_Panel.py" in help_text) + "\n"
            "BUTTON PANEL STATUS OK: " + str("button_control_panel" in status_text) + "\n"
            "COMFORT PACK OK: " + str("control_panel_comfort_pack" in status_text) + "\n"
            "ONE CLICK WORKFLOW OK: " + str("one_click_relay_workflow" in status_text) + "\n"
            "CHAT URL SETTINGS OK: " + str("chat_url_settings_panel" in status_text) + "\n"
            "SAFE FULL CYCLE OK: " + str("safe_full_cycle_guards" in status_text) + "\n"
            "TRUE AUTO RELAY OK: " + str("true_auto_relay_cycle" in status_text) + "\n"
            "AUTO RELAY RELIABILITY OK: " + str("auto_relay_reliability_pack" in status_text) + "\n"
            "AUTO DEV TASK CLARIFIER OK: " + str("auto_dev_task_clarifier" in status_text) + "\n"
            "GPT BROWSER THREAD FIX OK: " + str("gpt_browser_thread_affinity_fix" in status_text) + "\n"
            "RESPONSE FRESHNESS GUARD OK: " + str("response_freshness_guard" in status_text) + "\n"
            "UX GROUPED CONTROL PANEL OK: " + str("ux_grouped_control_panel" in status_text) + "\n"
            "SAFE AUTO CYCLE UX PANEL OK: " + str("safe_auto_cycle_ux_panel" in status_text) + "\n"
            "CONTROL PANEL UI REWORK PACK OK: " + str("control_panel_ui_rework_pack: да" in status_text) + "\n"
            "CONTROL PANEL TABS OK: " + str("control_panel_tabs: да" in status_text) + "\n"
            "COMPACT DASHBOARD OK: " + str("compact_dashboard: да" in status_text) + "\n"
            "ORGANIZED RELAY TAB OK: " + str("organized_relay_tab: да" in status_text) + "\n"
            "ORGANIZED BROWSER TAB OK: " + str("organized_browser_tab: да" in status_text) + "\n"
            "ORGANIZED AUTOPILOT TAB OK: " + str("organized_autopilot_tab: да" in status_text) + "\n"
            "PANEL CHAT COMMANDS OK: " + str("control_panel_chat_commands: да" in status_text) + "\n"
            "PANEL CHAT WITH MODEL OK: " + str("panel_chat_with_model: да" in status_text) + "\n"
            "PANEL TEXT COMMAND INPUT OK: " + str("panel_text_command_input: да" in status_text) + "\n"
            "RUSSIAN CONTROL PANEL MENU OK: " + str("russian_control_panel_menu: да" in status_text) + "\n"
            "CONTROL PANEL RUSSIAN LABELS OK: " + str("control_panel_russian_labels: да" in status_text) + "\n"
            "RUSSIAN COMMAND CENTER UI OK: " + str("russian_command_center_ui: да" in status_text) + "\n"
            "GRAY CONTROL PANEL THEME OK: " + str("gray_control_panel_theme: да" in status_text) + "\n"
            "TRANSLUCENT GRAY BUTTON STYLE OK: " + str("translucent_gray_button_style: да" in status_text) + "\n"
            "CONTROL PANEL THEME SMOKE OK: " + str("control_panel_theme_smoke: да" in status_text) + "\n"
            "LLM OFFLINE GRACEFUL ERROR PACK OK: " + str("llm_offline_graceful_error_pack: yes" in status_text) + "\n"
            "LLM CONNECTION ERROR HANDLING OK: " + str("llm_connection_error_handling: yes" in status_text) + "\n"
            "LMSTUDIO OFFLINE HINT OK: " + str("lmstudio_offline_hint: yes" in status_text and "lmstudio_offline_hint: yes" in help_text) + "\n"
            "VOICE MODE PANEL PACK OK: " + str("voice_mode_panel_pack: yes" in status_text) + "\n"
            "VOICE CHAT MODE OK: " + str("voice_chat_mode: yes" in status_text) + "\n"
            "VOICE CHAT REPLIES OK: " + str("voice_chat_replies: yes" in status_text) + "\n"
            "VOICE CONTINUOUS DIALOGUE OK: " + str("voice_continuous_dialogue: yes" in status_text) + "\n"
            "VOICE FASTER WHISPER RU OK: " + str("voice_faster_whisper_ru: yes" in status_text) + "\n"
            "VOICE PIPER TTS OK: " + str("voice_piper_tts: yes" in status_text) + "\n"
            "VOICE VOSK RUSSIAN STT OK: " + str("voice_vosk_russian_stt: yes" in status_text) + "\n"
            "VOICE PUSH TO TALK OK: " + str("voice_push_to_talk: yes" in status_text and "voice_push_to_talk: yes" in help_text) + "\n"
            "VOICE COMMAND SAFETY GUARD OK: " + str("voice_command_safety_guard: yes" in status_text) + "\n"
            "VOICE TTS OK: " + str("voice_tts: yes" in status_text) + "\n"
            "VOICE SESSION REPORTS OK: " + str("voice_session_reports: yes" in status_text) + "\n"
            "CHAT AUTOMATION INTENTS OK: " + str("chat_automation_intents: да" in status_text) + "\n"
            "NATURAL OPEN URL INTENT OK: " + str("natural_open_url_intent: да" in status_text) + "\n"
            "NATURAL SEARCH WORKFLOW OK: " + str("natural_search_workflow: да" in status_text) + "\n"
            "NATURAL PAGE ACTIONS OK: " + str("natural_page_actions: да" in status_text) + "\n"
            "NATURAL PROJECT CHECKS OK: " + str("natural_project_checks: да" in status_text) + "\n"
            "NATURAL BROWSER INTERACTIONS OK: " + str("natural_browser_interactions: да" in status_text) + "\n"
            "CHAT RESEARCH WORKFLOW INTENTS OK: " + str("chat_research_workflow_intents: да" in status_text) + "\n"
            "NATURAL RESEARCH INTENT OK: " + str("natural_research_intent: да" in status_text) + "\n"
            "NATURAL COMPARE INTENT OK: " + str("natural_compare_intent: да" in status_text) + "\n"
            "NATURAL OPEN PAGE WORKFLOW OK: " + str("natural_open_page_workflow: да" in status_text) + "\n"
            "BROWSER MISSION REPORT INTENTS OK: " + str("browser_mission_report_intents: да" in status_text) + "\n"
            "NATURAL BROWSER REPORT WORKFLOW OK: " + str("natural_browser_report_workflow: да" in status_text) + "\n"
            "NATURAL SITE CHECK WORKFLOW OK: " + str("natural_site_check_workflow: да" in status_text) + "\n"
            "NATURAL FORM WORKFLOW INTENTS OK: " + str("natural_form_workflow_intents: да" in status_text) + "\n"
            "NATURAL FORM FILL SEQUENCE OK: " + str("natural_form_fill_sequence: да" in status_text) + "\n"
            "NATURAL FORM SUBMIT GUARD OK: " + str("natural_form_submit_guard: да" in status_text) + "\n"
            "PROJECT HEALTH CENTER PACK OK: " + str("project_health_center_pack: да" in status_text) + "\n"
            "PROJECT HEALTH COMMAND OK: " + str("project_health_command: да" in status_text) + "\n"
            "PROJECT HEALTH REPORT OK: " + str("project_health_report: да" in status_text) + "\n"
            "SAFE HEALTH CHECKS OK: " + str("safe_health_checks: да" in status_text) + "\n"
            "REGRESSION COMMAND SUITE PACK OK: " + str("regression_command_suite_pack: да" in status_text) + "\n"
            "REGRESSION COMMAND SUITE OK: " + str("regression_command_suite: да" in status_text) + "\n"
            "REGRESSION COMMAND REPORT OK: " + str("regression_command_report: да" in status_text) + "\n"
            "SAFE REGRESSION COMMANDS OK: " + str("safe_regression_commands: да" in status_text) + "\n"
            "AUTO VERIFICATION PACK OK: " + str("auto_verification_pack: да" in status_text) + "\n"
            "AUTO VERIFY COMMAND OK: " + str("auto_verify_command: да" in status_text) + "\n"
            "AUTO VERIFY AFTER PATCH OK: " + str("auto_verify_after_patch: да" in status_text) + "\n"
            "AUTO VERIFY REPORTS OK: " + str("auto_verify_reports: да" in status_text) + "\n"
            "PROJECT HEALTH HELP OK: " + str(
                "Project Health Center Pack" in help_text
                and "project_health_center_pack: да" in help_text
                and "health report" in help_text
            ) + "\n"
            "REGRESSION COMMAND HELP OK: " + str(
                "Regression Command Suite" in help_text
                and "regression_command_suite_pack: да" in help_text
                and "regression report" in help_text
            ) + "\n"
            "AUTO VERIFICATION HELP OK: " + str(
                "Auto Verification Pack" in help_text
                and "auto_verification_pack: да" in help_text
                and "auto verify" in help_text
            ) + "\n"
            "CONTROL PANEL UI REWORK HELP OK: " + str(
                "Control Panel UI Rework Pack" in help_text
                and "control_panel_tabs: да" in help_text
                and "organized_autopilot_tab: да" in help_text
            ) + "\n"
            "BROWSER THREAD FIX OK: " + str("browser_thread_affinity_fix" in status_text) + "\n"
            "COMPACT UI PATCH VERSION BAR OK: " + str("compact_ui_patch_version_bar" in status_text) + "\n\n"
            "PATCH REGISTRY OK: " + str("patch_registry: да" in status_text) + "\n"
            "PROJECT BOOST PACK OK: " + str("project_boost_pack: да" in status_text) + "\n"
            "STABILITY TEST MODES OK: " + str("stability_test_modes: да" in status_text) + "\n"
            "ERROR DOCTOR FIX REQUEST OK: " + str("error_doctor_fix_request: да" in status_text) + "\n"
            "LLM PROVIDER FOUNDATION OK: " + str("llm_provider_foundation: да" in status_text) + "\n"
            "CODEX BRIDGE FOUNDATION OK: " + str("codex_bridge_foundation: да" in status_text) + "\n"
            "GIT SAFETY STATUS OK: " + str("git_safety_status: да" in status_text) + "\n"
            "PANEL RELAY DIAGNOSTICS PACK OK: " + str("panel_relay_diagnostics_pack: да" in status_text) + "\n"
            "RELAY DIAGNOSTICS OK: " + str("relay_diagnostics: да" in status_text) + "\n"
            "RELAY SMOKE TEST OK: " + str("relay_smoke_test: да" in status_text) + "\n"
            "RELAY DRY RUN SAFE OK: " + str("relay_dry_run_safe: да" in status_text) + "\n"
            "BROWSER ACTION OPERATOR OK: " + str("browser_action_operator_pack: да" in status_text) + "\n"
            "BROWSER DIRECT ACTION ROUTING FIX OK: " + str("browser_direct_action_routing_fix: да" in status_text) + "\n"
            "BROWSER ACTION AUTO RECOVERY OK: " + str("browser_action_auto_recovery: да" in status_text) + "\n"
            "BROWSER SCREENSHOT ACTION OK: " + str("browser_screenshot_action: да" in status_text) + "\n"
            "BROWSER EXTRACT LINKS INPUTS OK: " + str("browser_extract_links_inputs: да" in status_text) + "\n"
            "BROWSER TASK RUNNER OK: " + str("browser_task_runner: да" in status_text) + "\n"
            "BROWSER ACTION SAFETY GUARD OK: " + str("browser_action_safety_guard: да" in status_text) + "\n"
            "BROWSER MULTI STEP WORKFLOW PACK OK: " + str("browser_multi_step_workflow_pack: да" in status_text) + "\n"
            "BROWSER WORKFLOW RUNNER OK: " + str("browser_workflow_runner: да" in status_text) + "\n"
            "BROWSER WORKFLOW REPORTS OK: " + str("browser_workflow_reports: да" in status_text) + "\n"
            "BROWSER AUTOPILOT OPERATOR PACK OK: " + str("browser_autopilot_operator_pack: да" in status_text) + "\n"
            "BROWSER AUTOPILOT PLAN OK: " + str("browser_autopilot_plan: да" in status_text) + "\n"
            "BROWSER AUTOPILOT RUN OK: " + str("browser_autopilot_run: да" in status_text) + "\n"
            "BROWSER AUTOPILOT DRY RUN OK: " + str("browser_autopilot_dry_run: да" in status_text) + "\n"
            "BROWSER AUTOPILOT SAFETY GUARD OK: " + str("browser_autopilot_safety_guard: да" in status_text) + "\n"
            "BROWSER AUTOPILOT REPORTS OK: " + str("browser_autopilot_reports: да" in status_text) + "\n"
            "BROWSER OBSERVE OK: " + str("browser_observe: да" in status_text) + "\n"
            "BROWSER SUPER OPERATOR PACK OK: " + str("browser_super_operator_pack: да" in status_text) + "\n"
            "BROWSER RESEARCH REPORTS OK: " + str("browser_research_reports: да" in status_text) + "\n"
            "BROWSER PLATFORM SITE WORKFLOW OK: " + str("browser_platform_site_workflow: да" in status_text) + "\n"
            "BROWSER YOUTUBE SEARCH OK: " + str("browser_youtube_search: да" in status_text) + "\n"
            "NATURAL COMMAND INTENTS OK: " + str("natural_command_intents: да" in status_text) + "\n"
            "BROWSER PAGE AUDIT OK: " + str("browser_page_audit: да" in status_text) + "\n"
            "BROWSER FORM MAP OK: " + str("browser_form_map: да" in status_text) + "\n"
            "BROWSER SUPER SAFETY GUARD OK: " + str("browser_super_safety_guard: да" in status_text) + "\n"
            "BROWSER SUPER HELP OK: " + str(
                "Browser Super Operator Pack" in help_text
                and "browser_super_operator_pack: да" in help_text
                and "browser research <topic>" in help_text
            ) + "\n"
            + help_text[:4000]
            + "\n\n"
            + status_text[:4000]
        )

    cases.append(_run_case(
        "help/status",
        check_help_status,
        lambda r: (
            "HELP OK: True" in r
            and "STATUS OK: True" in r
            and "FILE RESPONSE PROMPT OK: True" in r
            and "MANUAL RELAY MODE OK: True" in r
            and "REJECT EMPTY PATCH OK: True" in r
            and "RESPONSE MODE STATUS OK: True" in r
            and "BUTTON PANEL HELP OK: True" in r
            and "BUTTON PANEL STATUS OK: True" in r
            and "COMFORT PACK OK: True" in r
            and "ONE CLICK WORKFLOW OK: True" in r
            and "CHAT URL SETTINGS OK: True" in r
            and "SAFE FULL CYCLE OK: True" in r
            and "TRUE AUTO RELAY OK: True" in r
            and "AUTO RELAY RELIABILITY OK: True" in r
            and "AUTO DEV TASK CLARIFIER OK: True" in r
            and "GPT BROWSER THREAD FIX OK: True" in r
            and "RESPONSE FRESHNESS GUARD OK: True" in r
            and "UX GROUPED CONTROL PANEL OK: True" in r
            and "SAFE AUTO CYCLE UX PANEL OK: True" in r
            and "CONTROL PANEL UI REWORK PACK OK: True" in r
            and "CONTROL PANEL TABS OK: True" in r
            and "COMPACT DASHBOARD OK: True" in r
            and "ORGANIZED RELAY TAB OK: True" in r
            and "ORGANIZED BROWSER TAB OK: True" in r
            and "ORGANIZED AUTOPILOT TAB OK: True" in r
            and "PANEL CHAT COMMANDS OK: True" in r
            and "PANEL CHAT WITH MODEL OK: True" in r
            and "PANEL TEXT COMMAND INPUT OK: True" in r
            and "RUSSIAN CONTROL PANEL MENU OK: True" in r
            and "CONTROL PANEL RUSSIAN LABELS OK: True" in r
            and "RUSSIAN COMMAND CENTER UI OK: True" in r
            and "GRAY CONTROL PANEL THEME OK: True" in r
            and "TRANSLUCENT GRAY BUTTON STYLE OK: True" in r
            and "CONTROL PANEL THEME SMOKE OK: True" in r
            and "LLM OFFLINE GRACEFUL ERROR PACK OK: True" in r
            and "LLM CONNECTION ERROR HANDLING OK: True" in r
            and "LMSTUDIO OFFLINE HINT OK: True" in r
            and "VOICE MODE PANEL PACK OK: True" in r
            and "VOICE CHAT MODE OK: True" in r
            and "VOICE CHAT REPLIES OK: True" in r
            and "VOICE CONTINUOUS DIALOGUE OK: True" in r
            and "VOICE FASTER WHISPER RU OK: True" in r
            and "VOICE PIPER TTS OK: True" in r
            and "VOICE VOSK RUSSIAN STT OK: True" in r
            and "VOICE PUSH TO TALK OK: True" in r
            and "VOICE COMMAND SAFETY GUARD OK: True" in r
            and "VOICE TTS OK: True" in r
            and "VOICE SESSION REPORTS OK: True" in r
            and "CHAT AUTOMATION INTENTS OK: True" in r
            and "NATURAL OPEN URL INTENT OK: True" in r
            and "NATURAL SEARCH WORKFLOW OK: True" in r
            and "NATURAL PAGE ACTIONS OK: True" in r
            and "NATURAL PROJECT CHECKS OK: True" in r
            and "NATURAL BROWSER INTERACTIONS OK: True" in r
            and "CHAT RESEARCH WORKFLOW INTENTS OK: True" in r
            and "NATURAL RESEARCH INTENT OK: True" in r
            and "NATURAL COMPARE INTENT OK: True" in r
            and "NATURAL OPEN PAGE WORKFLOW OK: True" in r
            and "BROWSER MISSION REPORT INTENTS OK: True" in r
            and "NATURAL BROWSER REPORT WORKFLOW OK: True" in r
            and "NATURAL SITE CHECK WORKFLOW OK: True" in r
            and "NATURAL FORM WORKFLOW INTENTS OK: True" in r
            and "NATURAL FORM FILL SEQUENCE OK: True" in r
            and "NATURAL FORM SUBMIT GUARD OK: True" in r
            and "PROJECT HEALTH CENTER PACK OK: True" in r
            and "PROJECT HEALTH COMMAND OK: True" in r
            and "PROJECT HEALTH REPORT OK: True" in r
            and "SAFE HEALTH CHECKS OK: True" in r
            and "PROJECT HEALTH HELP OK: True" in r
            and "REGRESSION COMMAND SUITE PACK OK: True" in r
            and "REGRESSION COMMAND SUITE OK: True" in r
            and "REGRESSION COMMAND REPORT OK: True" in r
            and "SAFE REGRESSION COMMANDS OK: True" in r
            and "REGRESSION COMMAND HELP OK: True" in r
            and "AUTO VERIFICATION PACK OK: True" in r
            and "AUTO VERIFY COMMAND OK: True" in r
            and "AUTO VERIFY AFTER PATCH OK: True" in r
            and "AUTO VERIFY REPORTS OK: True" in r
            and "AUTO VERIFICATION HELP OK: True" in r
            and "CONTROL PANEL UI REWORK HELP OK: True" in r
            and "BROWSER THREAD FIX OK: True" in r
            and "COMPACT UI PATCH VERSION BAR OK: True" in r
            and "PATCH REGISTRY OK: True" in r
            and "PROJECT BOOST PACK OK: True" in r
            and "STABILITY TEST MODES OK: True" in r
            and "ERROR DOCTOR FIX REQUEST OK: True" in r
            and "LLM PROVIDER FOUNDATION OK: True" in r
            and "CODEX BRIDGE FOUNDATION OK: True" in r
            and "GIT SAFETY STATUS OK: True" in r
            and "PANEL RELAY DIAGNOSTICS PACK OK: True" in r
            and "RELAY DIAGNOSTICS OK: True" in r
            and "RELAY SMOKE TEST OK: True" in r
            and "RELAY DRY RUN SAFE OK: True" in r
            and "BROWSER ACTION OPERATOR OK: True" in r
            and "BROWSER DIRECT ACTION ROUTING FIX OK: True" in r
            and "BROWSER ACTION AUTO RECOVERY OK: True" in r
            and "BROWSER SCREENSHOT ACTION OK: True" in r
            and "BROWSER EXTRACT LINKS INPUTS OK: True" in r
            and "BROWSER TASK RUNNER OK: True" in r
            and "BROWSER ACTION SAFETY GUARD OK: True" in r
            and "BROWSER MULTI STEP WORKFLOW PACK OK: True" in r
            and "BROWSER WORKFLOW RUNNER OK: True" in r
            and "BROWSER WORKFLOW REPORTS OK: True" in r
            and "BROWSER AUTOPILOT OPERATOR PACK OK: True" in r
            and "BROWSER AUTOPILOT PLAN OK: True" in r
            and "BROWSER AUTOPILOT RUN OK: True" in r
            and "BROWSER AUTOPILOT DRY RUN OK: True" in r
            and "BROWSER AUTOPILOT SAFETY GUARD OK: True" in r
            and "BROWSER AUTOPILOT REPORTS OK: True" in r
            and "BROWSER OBSERVE OK: True" in r
            and "BROWSER SUPER OPERATOR PACK OK: True" in r
            and "BROWSER RESEARCH REPORTS OK: True" in r
            and "BROWSER PLATFORM SITE WORKFLOW OK: True" in r
            and "BROWSER YOUTUBE SEARCH OK: True" in r
            and "NATURAL COMMAND INTENTS OK: True" in r
            and "BROWSER PAGE AUDIT OK: True" in r
            and "BROWSER FORM MAP OK: True" in r
            and "BROWSER SUPER SAFETY GUARD OK: True" in r
            and "BROWSER SUPER HELP OK: True" in r
        ),
    ))

    def check_memory():
        from agents import system_agent

        return system_agent.handle("memory", {})

    cases.append(_run_case("memory", check_memory, lambda r: bool(str(r).strip())))
    cases.append(_llm_offline_graceful_error_case())
    cases.append(_voice_mode_foundation_case())
    cases.append(_project_health_case())
    cases.append(_regression_command_suite_case())
    cases.append(_auto_verification_case())
    cases.append(_browser_super_case())
    cases.append(_chat_automation_intents_case())
    cases.append(_russian_control_panel_menu_case())
    cases.append(_control_panel_init_smoke_case())

    def check_router():
        from core.router import route

        browser_route = route("найди официальный сайт Python")
        stability_route = route("stability test")
        automation_status_route = route("automation status")
        after_patch_route = route("after patch")
        dev_task_route = route("dev task улучши браузер")
        browser_task_route = route("browser task найди Python")
        browser_batch_route = route("browser batch Godot")
        browser_compare_route = route("browser compare local llm")
        browser_research_route = route("browser research local llm")
        browser_tilda_route = route("напиши сайт автосервиса используй платформу Tilda")
        pc_task_route = route("pc task открой блокнот")
        pc_batch_route = route("pc batch открой блокнот")
        multi_task_route = route("multi task найди Python и открой папку отчетов")
        task_status_route = route("task status")
        gpt_browser_route = route("gpt browser status")
        gpt_browser_close_route = route("gpt browser close")

        return (
            f"route('gpt browser status') = {gpt_browser_route}\n"
            f"route('gpt browser close') = {gpt_browser_close_route}\n"
            f"route('найди официальный сайт Python') = {browser_route}\n"
            f"route('stability test') = {stability_route}\n"
            f"route('automation status') = {automation_status_route}\n"
            f"route('after patch') = {after_patch_route}\n"
            f"route('dev task ...') = {dev_task_route}\n"
            f"route('browser task ...') = {browser_task_route}\n"
            f"route('browser batch ...') = {browser_batch_route}\n"
            f"route('browser compare ...') = {browser_compare_route}\n"
            f"route('browser research ...') = {browser_research_route}\n"
            f"route('Tilda site ...') = {browser_tilda_route}\n"
            f"route('pc task ...') = {pc_task_route}\n"
            f"route('pc batch ...') = {pc_batch_route}\n"
            f"route('multi task ...') = {multi_task_route}\n"
            f"route('task status') = {task_status_route}"
        )

    cases.append(_run_case(
        "router",
        check_router,
        lambda r: (
            "route('gpt browser status') = gpt_browser" in r
            and "route('gpt browser close') = gpt_browser" in r
            and "route('найди официальный сайт Python') = browser" in r
            and "route('stability test') = stability" in r
            and "route('automation status') = automation" in r
            and "route('after patch') = automation" in r
            and "route('dev task ...') = automation" in r
            and "route('browser task ...') = browser" in r
            and "route('browser batch ...') = automation" in r
            and "route('browser compare ...') = browser" in r
            and "route('browser research ...') = browser" in r
            and "route('Tilda site ...') = browser" in r
            and "route('pc task ...') = automation" in r
            and "route('pc batch ...') = automation" in r
            and "route('multi task ...') = automation" in r
            and "route('task status') = automation" in r
        ),
    ))

    def check_planner():
        from core.planner import plan

        browser_plan = plan("browser last", "browser")
        stability_plan = plan("stability test", "stability")
        automation_status_plan = plan("automation status", "automation")
        automation_after_patch_plan = plan("after patch", "automation")
        automation_dev_plan = plan("dev task улучши браузер", "automation")
        automation_multi_plan = plan("multi task найди Python и открой папку отчетов", "automation")
        automation_browser_batch_plan = plan("browser batch Godot", "automation")
        automation_pc_batch_plan = plan("pc batch открой блокнот", "automation")
        gpt_browser_plan = plan("gpt browser status", "gpt_browser")
        gpt_browser_wait_plan = plan("gpt browser wait 600", "gpt_browser")
        gpt_browser_repair_plan = plan("gpt browser repair response", "gpt_browser")
        gpt_browser_close_plan = plan("gpt browser close", "gpt_browser")
        gpt_browser_full_apply_plan = plan("gpt browser full apply", "gpt_browser")

        return json.dumps(
            {
                "gpt_browser_plan": gpt_browser_plan,
                "gpt_browser_wait_plan": gpt_browser_wait_plan,
                "gpt_browser_repair_plan": gpt_browser_repair_plan,
                "gpt_browser_close_plan": gpt_browser_close_plan,
                "gpt_browser_full_apply_plan": gpt_browser_full_apply_plan,
                "browser_plan": browser_plan,
                "stability_plan": stability_plan,
                "automation_status_plan": automation_status_plan,
                "automation_after_patch_plan": automation_after_patch_plan,
                "automation_dev_plan": automation_dev_plan,
                "automation_multi_plan": automation_multi_plan,
                "automation_browser_batch_plan": automation_browser_batch_plan,
                "automation_pc_batch_plan": automation_pc_batch_plan,
            },
            ensure_ascii=False,
            indent=2,
        )

    cases.append(_run_case(
        "planner",
        check_planner,
        lambda r: (
            '"tool": "gpt_browser"' in r
            and '"action": "repair_response"' in r
            and '"action": "close"' in r
            and '"tool": "chatgpt_relay"' in r
            and '"timeout_sec": 600' in r
            and '"tool": "browser"' in r
            and '"tool": "stability"' in r
            and r.count('"tool": "automation"') >= 6
            and '"action": "dev_task"' in r
            and '"action": "after_patch"' in r
            and '"action": "status"' in r
            and '"action": "multi_task"' in r
            and '"action": "browser_batch"' in r
            and '"action": "pc_batch"' in r
        ),
    ))

    def check_browser_search():
        from agents import browser_agent

        return browser_agent.handle("search", {"query": "Python official website"})

    cases.append(_run_case(
        "browser search",
        check_browser_search,
        lambda r: "Поиск сохранен" in r or "Ищу через" in r,
    ))

    def check_browser_last():
        from agents import browser_agent

        return browser_agent.handle("last_search", {})

    cases.append(_run_case(
        "browser last",
        check_browser_last,
        lambda r: "Python official website" in r and "Последний browser-поиск" in r,
    ))

    def check_browser_open_first_hard():
        from agents import browser_agent
        from modules.browser import close_browser_for_test

        close_browser_for_test()
        return browser_agent.handle("open_first_result", {})

    cases.append(_run_case(
        "browser open first hard recovery",
        check_browser_open_first_hard,
        lambda r: "Открыл первый результат" in r and "Не удалось" not in r,
    ))

    def check_browser_read_hard():
        from agents import browser_agent
        from modules.browser import close_browser_for_test

        close_browser_for_test()
        return browser_agent.handle("read_page", {})

    cases.append(_run_case(
        "browser read hard recovery",
        check_browser_read_hard,
        lambda r: ("URL:" in r and "TITLE:" in r) or "Браузер был восстановлен" in r,
    ))

    def check_browser_status():
        from agents import browser_agent

        return browser_agent.handle("status", {})

    cases.append(_run_case(
        "browser status",
        check_browser_status,
        lambda r: "current_url" in r and "last_browser_query" in r and "last_browser_error" in r,
    ))

    def check_relay_status():
        from agents import chatgpt_relay_agent
        from agents import automation_agent
        from agents import system_agent

        relay_status = chatgpt_relay_agent.handle("status", {})
        automation_status = automation_agent.handle("status", {})
        parser_status = automation_agent.handle("parser_diagnostics", {})
        system_status = system_agent.handle("status", {})

        try:
            from agents import gpt_browser_agent
            gpt_browser_status = gpt_browser_agent.handle("status", {})
        except Exception as e:
            gpt_browser_status = f"GPT Browser status error: {e}"

        return (
            str(relay_status)
            + "\n\n--- AUTOMATION STATUS ---\n"
            + str(automation_status)
            + "\n\n--- PARSER DIAGNOSTICS ---\n"
            + str(parser_status)
            + "\n\n--- GPT BROWSER STATUS ---\n"
            + str(gpt_browser_status)
            + "\n\n--- SYSTEM STATUS ---\n"
            + str(system_status)
        )

    cases.append(_run_case(
        "relay/automation/parser status",
        check_relay_status,
        lambda r: (
            "ChatGPT Relay status" in r
            and "request.md" in r
            and "Automation Command Center status" in r
            and "dev task" in r
            and "browser_read_first_query: Godot official website" in r
            and "multi_browser_query: официальный сайт Python" in r
            and "multi_pc_goal: открой папку отчетов" in r
            and "pc_batch_reports_only: ok" in r
            and "GPT Browser Bridge status" in r
            and "default_wait_timeout: 600" in r
            and "response_mode:" in r
            and "fixed_downloads_import" in r
            and "reliable_manual_relay_mode" in r
            and "reject_empty_confirmation_patch" in r
        ),
    ))

    def check_browser_profile_ignore():
        from modules.browser_profile_ignore import is_browser_profile_path

        lock_path = ROOT_DIR / "Projects" / "BrowserProfile" / "SingletonLock"
        normal_path = ROOT_DIR / "modules" / "stability_test.py"

        return (
            f"browserprofile_ignore_ok: {is_browser_profile_path(lock_path)}\n"
            f"normal_file_ignore_ok: {not is_browser_profile_path(normal_path)}"
        )

    cases.append(_run_case(
        "browser profile ignore guard",
        check_browser_profile_ignore,
        lambda r: "browserprofile_ignore_ok: True" in r and "normal_file_ignore_ok: True" in r,
    ))

    score = sum(1 for case in cases if case["passed"])
    total = len(cases)

    if score == total:
        level = "отличная"
    elif score >= max(1, int(total * 0.7)):
        level = "хорошая"
    elif score >= max(1, int(total * 0.5)):
        level = "средняя"
    else:
        level = "плохая"

    problems = [
        f"{case['name']}: {case['error'] or case['result']}"
        for case in cases
        if not case["passed"]
    ]

    report_path = _save_report(cases, score, level, problems)

    lines = [
        "Auto Stability Test завершен.",
        f"Итог: {score}/{total}",
        f"Стабильность: {level}",
        f"Отчет: {report_path}",
        "",
        "Проверки:",
    ]

    for case in cases:
        mark = "[OK]" if case["passed"] else "[FAIL]"
        lines.append(f"- {mark} {case['name']}")

    lines.append("")
    lines.append("Проблемы:")

    if problems:
        for problem in problems:
            lines.append("- " + _short(problem, 400))
    else:
        lines.append("- Не обнаружены.")

    return "\n".join(lines)
