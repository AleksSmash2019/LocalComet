from pathlib import Path
from modules.project_paths import get_project_root, projects_dir

from config import MODEL, LMSTUDIO_API
from core.state import load_state, get_value
from modules.git_status import short_status as git_short_status
from modules.llm_provider import provider_status
from modules.patch_registry import short_status as patch_registry_short_status
from modules.project_health import format_project_health_text, write_project_health_report
from modules.regression_commands import format_regression_command_suite, run_regression_command_suite
from modules.auto_verification import format_auto_verification, run_auto_verification
from modules.voice_control import (
    check_voice_dependencies,
    get_voice_status,
    latest_voice_session_report,
    speak_text,
)


PROJECTS_DIR = projects_dir()
REPORTS_DIR = PROJECTS_DIR / "Reports"
WINDOWS_DIR = PROJECTS_DIR / "Windows"
CONTROL_PANEL_FILE = get_project_root() / "LocalComet_Control_Panel.py"
PATCH_REGISTRY_FILE = PROJECTS_DIR / "PatchRegistry" / "patches.json"


def _get_latest_report():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    reports = list(REPORTS_DIR.glob("*.md"))

    if not reports:
        return None

    latest = max(reports, key=lambda p: p.stat().st_mtime)
    return latest


def _format_state():
    state = load_state()

    if not state:
        return "Память LocalComet пока пустая."

    lines = ["Память LocalComet:"]

    for key, value in state.items():
        value_text = str(value)

        if len(value_text) > 500:
            value_text = value_text[:500] + "... [обрезано]"

        lines.append(f"- {key}: {value_text}")

    return "\n".join(lines)


def show_help():
    return """LocalComet сейчас умеет:

Быстрые команды:
- diag — диагностика
- lm — проверить LM Studio
- mem — проверить память
- files — показать файлы
- notes — показать заметки
- reports — показать отчеты
- projects — открыть папку проектов
- model — текущая модель
- help — что умеет агент
- health — краткая сводка здоровья проекта
- health report — записать markdown report Project Health Center
- regression suite — безопасная проверка основных команд
- regression report — записать markdown report Regression Command Suite
- auto verify — один безопасный прогон основных проверок
- auto verify full — полный прогон перед commit/после patch
- history — история действий
- backup — сделать бэкап проекта
- Button Control Panel — кнопочная панель управления LocalComet
- Patch Registry — история применённых patch
- CodexBridge — безопасная подготовка prompt для Codex

Windows:
- открой блокнот
- напиши привет
- очисти блокнот
- покажи что в блокноте
- добавь в блокнот новая строка
- открой калькулятор
- открой проводник

Workspace:
- создай заметку ...
- покажи заметки
- прочитай последнюю заметку
- создай файл test.txt с текстом привет
- прочитай файл test.txt
- покажи файлы
- открой папку проектов
- открой папку отчетов
- открой последний файл

Браузер:
- найди информацию
- открой сайт
- открой первый результат
- прочитай страницу
- browser last
- browser open first
- browser read
- browser status

Отчеты:
- изучи тему и сделай отчет
- покажи последний отчет
- открой последний отчет

Operator:
- найди 5 вариантов, сравни и выбери лучший
- найди лучшие локальные LLM для LocalComet

Сайты:
- создай сайт
- создай современный сайт
- открой созданный сайт
- проверь сайт
- улучши сайт

Диагностика:
- диагностика
- проверь lm studio
- проверь папки
- проверь память
- проверь файлы
- последняя ошибка

История:
- history
- history stats
- путь истории
- последняя запись истории
- очисти историю

Обслуживание:
- backup
- открой папку бэкапов
- размер памяти
- очисти память
- очисти последний результат
- сожми память

Self-Edit:
- самопроверка проекта
- создай патч ...
- покажи последний патч
- примени последний патч
- откати последний патч

ChatGPT Relay:
- relay статус
- relay diagnostics
- relay smoke
- panel relay smoke
- relay старт ...
- relay старт тихо ...
- relay создай запрос ...
- relay snapshot ...
- error doctor
- doctor
- relay скопируй запрос
- relay открой чат
- relay открой папку
- relay последний запрос
- relay открой последний запрос
- relay забери ответ
- relay проверь ответ
- relay примени ответ
- relay очисти ответ
- relay покажи запрос
- relay покажи ответ
- надежный ручной режим: загрузи request.md сюда в ChatGPT и получи response.json файлом
- Button Control Panel: двойной клик по LocalComet_Control_Panel.py для кнопок dev/relay/after patch
- Control Panel Comfort Pack: многострочный dev task, буфер, обычный ChatGPT, Downloads, импорт+проверка, применить+after patch, полный цикл после скачивания response
- One Click Relay Workflow: кнопки Создать request + открыть ChatGPT, Открыть этот чат ChatGPT, Скачать response -> полный цикл
- Chat URL Settings Panel: ссылка ChatGPT редактируется прямо в панели и сохраняется в gpt_browser_chat_url
- Safe Full Cycle Guards: полный цикл останавливается при ошибке импорта/validate/apply, импортирует только response*.json, есть ручной выбор response.json и очистка response/bad_response/raw
- True Auto Relay Cycle: кнопка АВТО dev -> ChatGPT -> скачать -> validate -> apply -> after patch
- Auto Relay Reliability Pack: STEP N/M логирование, retry, auto-run отчет, screenshot ошибки, timeout 300/600/900/1200 и защита от двойного запуска
- Auto Dev Task Clarifier: авто-уточнение поля Dev task через GPT с debounce, ручным принятием и запуском автоцикла с уточненной задачей
- GPT Browser Thread Affinity Fix: Playwright context/page сбрасываются при смене потока, чтобы не ловить cannot switch to a different thread
- Response Freshness Guard: автоцикл принимает только response*.json с meta.cycle_id текущего запуска и архивирует старые Downloads artifacts
- UX Grouped Control Panel: кнопки панели разделены на Разработка, Автоцикл, GPT/Relay, Patch и Диагностика
- Safe Auto Cycle + UX Panel: главный автоцикл вынесен вверх, добавлена строка статусов Relay/GPT/response/cycle_id/patch
- Browser Thread Affinity Fix: обычный browser module сбрасывает Playwright при смене потока и больше не падает на cannot switch to a different thread
- Compact UI + Patch Version Bar: компактная панель с постоянной строкой Patch/version/summary/status/cycle_id/response
- Panel + ChatGPT Relay Diagnostics Pack: безопасные кнопки Relay status, Relay smoke и Open last relay report без auto-apply
- panel_relay_diagnostics_pack: да
- relay_diagnostics: да
- relay_smoke_test: да
- relay_dry_run_safe: да
- Control Panel UI Rework Pack: вкладки Dashboard, Patch / Relay, Browser, Autopilot, Tests, Reports / Tools и Logs
- control_panel_ui_rework_pack: да
- control_panel_tabs: да
- compact_dashboard: да
- organized_relay_tab: да
- organized_browser_tab: да
- organized_autopilot_tab: да
- Panel Chat Commands Pack: вкладка Chat / Commands позволяет писать команды и общаться с локальной моделью прямо в панели
- control_panel_chat_commands: да
- panel_chat_with_model: да
- panel_text_command_input: да
- Chat Automation Intents Pack: живые фразы в чате превращаются в browser/system actions без точных CLI-команд
- chat_automation_intents: да
- natural_open_url_intent: да
- natural_search_workflow: да
- natural_page_actions: да
- natural_project_checks: да
- natural_browser_interactions: да
- Chat Research Workflow Intents Pack: живые фразы для research/compare/page workflow в браузере
- chat_research_workflow_intents: да
- natural_research_intent: да
- natural_compare_intent: да
- natural_open_page_workflow: да
- Browser Mission Report Intents Pack: чатовые фразы собирают browser workflow reports по теме, URL или текущей странице
- browser_mission_report_intents: да
- natural_browser_report_workflow: да
- natural_site_check_workflow: да
- Natural Form Workflow Intents Pack: чатовые фразы заполняют несколько полей формы одной browser sequence
- natural_form_workflow_intents: да
- natural_form_fill_sequence: да
- natural_form_submit_guard: да
- Russian Control Panel Menu Pack: вкладки, группы и основные кнопки панели переведены на русский
- russian_control_panel_menu: да
- control_panel_russian_labels: да
- russian_command_center_ui: да
- Gray Control Panel Theme Pack: меню и кнопки панели получили мягкую серую полупрозрачную тему
- gray_control_panel_theme: да
- translucent_gray_button_style: да
- control_panel_theme_smoke: да
- LLM Offline Graceful Error Pack: короткая подсказка вместо traceback, если LM Studio Local Server выключен
- llm_offline_graceful_error_pack: yes
- llm_connection_error_handling: yes
- lmstudio_offline_hint: yes
- Voice Mode Control Panel Pack: push-to-talk, command preview, safety guard, TTS и voice reports
- voice status
- voice test
- voice speak <text>
- voice last report
- voice_mode_panel_pack: yes
- voice_chat_mode: yes
- voice_chat_replies: yes
- voice_continuous_dialogue: yes
- voice_faster_whisper_ru: yes
- voice_piper_tts: yes
- voice_vosk_russian_stt: yes
- voice_push_to_talk: yes
- voice_command_safety_guard: yes
- voice_tts: yes
- voice_session_reports: yes
- Project Health Center Pack: команда health показывает Git, patch, relay, browser, reports, stability и last_error
- project_health_center_pack: да
- project_health_command: да
- project_health_report: да
- safe_health_checks: да
- Regression Command Suite: безопасно проверяет help/status/health/relay/browser/autopilot routing без GUI и patch apply
- regression_command_suite_pack: да
- regression_command_suite: да
- regression_command_report: да
- safe_regression_commands: да
- Auto Verification Pack: одна команда запускает py_compile, LM/model smoke, health, regression и full/post-patch stability
- auto_verification_pack: да
- auto_verify_command: да
- auto_verify_after_patch: да
- auto_verify_reports: да

GPT Browser Bridge:
- GPT Browser test OK
- gpt browser set chat <url> — сохранить конкретный ChatGPT Project chat URL в state как gpt_browser_chat_url
- gpt browser show chat — показать сохраненный Project chat URL
- gpt browser clear chat — очистить сохраненный Project chat URL
- gpt browser open project chat — открыть сохраненный Project chat
- gpt browser open — открыть saved_chat_url, если он сохранен, иначе https://chatgpt.com/
- gpt browser paste request — вставить последний request.md в поле ChatGPT + инструкцию: главный результат — скачиваемый файл response.json; fallback — JSON-only текст
- gpt browser send — отправить запрос
- gpt browser wait — дождаться стабилизации ответа, по умолчанию 600 секунд
- gpt browser wait 600 — ждать указанное число секунд
- gpt browser save response — сначала импортировать скачанный response.json из фиксированной папки Downloads, затем fallback: извлечь JSON patch из текста
- Reject Empty Patch: response.json с operations: [] и summary-подтверждением считается bad_response.json
- gpt browser repair response — восстановить response.json из gpt_browser_last_answer.txt или response_raw.md
- gpt browser downloads — показать фиксированную папку загрузок GPT Browser
- gpt browser open downloads — открыть фиксированную папку загрузок
- gpt browser import downloaded response — импортировать свежий скачанный response.json в Relay
- gpt browser status — статус браузерного GPT-моста
- gpt browser close — закрыть Playwright context/browser и освободить Projects/BrowserProfile
- gpt browser full cycle — open -> paste -> send -> wait 600 -> save -> relay validate
- gpt browser full apply — full cycle -> gpt browser close -> relay apply -> after patch
- gpt browser download_latest_response_artifact — скачать/найти свежий response*.json из ChatGPT
- gpt browser true_auto_relay_cycle — полный автоматический safe relay cycle
- gpt browser paste_text/read_last_assistant_message — служебные функции для уточнения задач без patch

BrowserProfile Ignore Pack:
- Projects/BrowserProfile не читается self-edit и не должен попадать в backup/rollback/relay apply/tests
- relay apply автоматически закрывает GPT Browser Bridge перед применением ответа

Ручной список файлов для relay:
- relay snapshot задача файлы: modules/a.py, agents/b.py

Doctor Path Fix:
- error doctor больше не берет кривые пути из last_result/логов

Browser Follow:
- browser last показывает последний browser-поиск
- browser open first открывает первый результат текущего поиска
- browser read читает текущую страницу

Browser Recovery:
- browser open first восстанавливает закрытый браузер по last_browser_query
- browser read восстанавливает закрытый браузер и читает страницу
- browser status показывает current_url, last_browser_query и last_browser_error

Browser Action Operator:
- direct commands: browser summarize, browser links, browser inputs, browser screenshot, browser find text <text>
- browser screenshot
- browser click <text>
- browser fill <label>=<value>
- browser press Enter
- browser links
- browser inputs
- browser summarize
- browser tabs
- browser new tab <url>
- browser switch tab <n>
- browser close tab

Browser Action Auto Recovery:
- если страница пустая, агент восстанавливает страницу по last_browser_query или подсказывает search/open first

Browser Multi-Step Workflow Pack:
- browser_multi_step_workflow_pack: да
- browser_workflow_runner: да
- browser_workflow_reports: да

Browser Autopilot Operator Pack:
- browser plan <task>
- browser autopilot dry <task>
- browser autopilot run <task>
- browser task <task>
- browser observe
- browser autopilot last report
- browser_autopilot_operator_pack: да
- browser_autopilot_plan: да
- browser_autopilot_run: да
- browser_autopilot_dry_run: да
- browser_autopilot_safety_guard: да
- browser_autopilot_reports: да
- browser_observe: да

Browser Super Operator Pack:
- browser research <topic> — Perplexity-style research with sources
- browser compare <topic> — сравнение по веб-источникам
- browser page audit — анализ текущей страницы
- browser form map — карта видимых форм/полей
- browser build site <prompt> / напиши сайт ... используй платформу Tilda — платформенный site workflow
- открой YouTube и найди <видео> — открыть результаты YouTube в браузере
- проверь весь проект на ошибки — полный Auto Verification
- browser super plan <task> — безопасный план без действий
- живые команды: открой github.com, найди официальный сайт Python и кратко прочитай, собери ссылки со страницы
- research-фразы: изучи <тему> и сделай отчет, сравни <A> и <B>, открой <url> и собери ссылки/скриншот
- browser report-фразы: сделай браузерный отчет по <теме>, проверь сайт <url>, сделай отчет по текущей странице
- form-фразы: заполни форму: Name=Ivan, Email=a@b.com, нажми Enter
- browser_super_operator_pack: да
- browser_research_reports: да
- browser_platform_site_workflow: да
- browser_youtube_search: да
- natural_command_intents: да
- browser_page_audit: да
- browser_form_map: да
- browser_super_safety_guard: да

Auto Stability Test:
- model test
- stability test
- тест стабильности

Automation Command Center:
- dev task ... — DIRECT создание relay snapshot по задаче разработки
- browser task ... — DIRECT поиск, открытие первого результата и чтение страницы
- pc task ... — DIRECT локальная задача через windows/workspace/files
- automation status — DIRECT статус автоматизации
- after patch — DIRECT запуск model test после патча

Browser + PC Multi Task:
- multi task ... — браузер + ПК + отчет одной командой
- browser batch ... — поиск, чтение первых 3 результатов и отчет
- browser read first N — прочитать первые N результатов прошлого поиска
- browser compare ... — сравнить первые 3 результата
- browser report ... — сохранить отчет по странице/поиску
- pc batch ... — несколько локальных действий подряд
- task status — статус последней большой задачи
- task report — показать последний отчет задачи

Multi Task Parser Fix:
- browser read first 3 берет last_browser_query, а не ищет "3"
- multi task разделяет browser-запрос и PC-команду
- pc batch сам открывает Reports/Projects/Windows без windows open_folder
- sequential runner помечает шаг как failed, если в результате есть маркер ошибки

Audit Hygiene:
- успешные DIRECT-команды очищают устаревший last_error
- dev task добавляет file hints для browser/automation/relay/windows задач
- browser task чистит запрос от служебных слов "найди" и "прочитай"

Системные:
- статус
- память
- последние действия
- последний результат
- повтори
- продолжи
"""


def show_status():
    latest_report = _get_latest_report()

    last_report = get_value("last_report", "нет")
    last_site = get_value("last_site", "нет")
    last_windows_app = get_value("last_windows_app", "нет")
    last_windows_file = get_value("last_windows_file", "нет")
    last_windows_text = get_value("last_windows_text", "нет")
    last_real_goal = get_value("last_real_goal", "нет")
    last_task = get_value("last_task", "нет")
    last_route = get_value("last_route", "нет")
    last_action = get_value("last_action", "нет")
    last_error = get_value("last_error", "нет")
    last_stability_score = get_value("last_stability_score", "нет")
    last_stability_report = get_value("last_stability_report", "нет")
    last_automation_task = get_value("last_automation_task", "нет")
    last_automation_report = get_value("last_automation_report", "нет")
    last_multi_task = get_value("last_multi_task", "нет")
    last_task_report = get_value("last_task_report", "нет")
    last_browser_batch = get_value("last_browser_batch", "нет")
    last_pc_batch = get_value("last_pc_batch", "нет")
    last_gpt_browser_action = get_value("last_gpt_browser_action", "нет")
    last_gpt_browser_response = get_value("last_gpt_browser_response", "нет")
    last_gpt_browser_error = get_value("last_gpt_browser_error", "нет")
    gpt_browser_chat_url = get_value("gpt_browser_chat_url", "нет")
    last_gpt_browser_response_mode = get_value("last_gpt_browser_response_mode", "file_response_json_first")
    last_gpt_browser_response_mode = get_value("last_gpt_browser_response_mode", "file_response_json_first")
    last_true_auto_relay_report = get_value("last_true_auto_relay_report", "нет")
    last_true_auto_relay_screenshot = get_value("last_true_auto_relay_screenshot", "нет")
    last_relay_diagnostics_report = get_value("last_relay_diagnostics_report", "нет")
    last_relay_diagnostics_status = get_value("last_relay_diagnostics_status", "нет")
    last_task_clarifier_answer = get_value("last_task_clarifier_answer", "нет")
    last_task_clarifier_goal = get_value("last_task_clarifier_goal", "нет")
    last_gpt_browser_owner_thread_id = get_value("last_gpt_browser_owner_thread_id", "нет")
    last_gpt_browser_thread_reset_reason = get_value("last_gpt_browser_thread_reset_reason", "нет")
    last_true_auto_cycle_id = get_value("last_true_auto_cycle_id", "нет")
    last_true_auto_imported_cycle_id = get_value("last_true_auto_imported_cycle_id", "нет")
    last_browser_owner_thread_id = get_value("last_browser_owner_thread_id", "нет")
    last_browser_thread_reset_reason = get_value("last_browser_thread_reset_reason", "нет")
    last_browser_action = get_value("last_browser_action", "нет")
    last_browser_screenshot = get_value("last_browser_screenshot", "нет")
    last_browser_error = get_value("last_browser_error", "нет")
    last_browser_task_report = get_value("last_browser_task_report", "нет")
    last_browser_workflow_report = get_value("last_browser_workflow_report", "нет")
    last_browser_workflow_status = get_value("last_browser_workflow_status", "нет")
    last_browser_autopilot_report = get_value("last_browser_autopilot_report", "нет")
    last_browser_autopilot_status = get_value("last_browser_autopilot_status", "нет")
    last_browser_autopilot_task = get_value("last_browser_autopilot_task", "нет")
    last_browser_autopilot_mode = get_value("last_browser_autopilot_mode", "нет")
    last_browser_super_report = get_value("last_browser_super_report", "нет")
    last_browser_super_status = get_value("last_browser_super_status", "нет")
    last_browser_super_task = get_value("last_browser_super_task", "нет")
    last_browser_platform = get_value("last_browser_platform", "нет")
    last_browser_platform_url = get_value("last_browser_platform_url", "нет")
    last_browser_youtube_query = get_value("last_browser_youtube_query", "нет")
    last_browser_youtube_report = get_value("last_browser_youtube_report", "нет")
    voice_status = get_voice_status()
    voice_deps = voice_status.get("dependencies", {})
    last_voice_session_report = latest_voice_session_report() or "нет"
    last_patch_version = get_value("last_patch_version", "нет")
    last_patch_summary = get_value("last_patch_summary", "нет")
    last_patch_status = get_value("last_patch_status", "нет")
    last_patch_registry_file = get_value("last_patch_registry_file", str(PATCH_REGISTRY_FILE))
    last_patch_registry_count = get_value("last_patch_registry_count", "0")
    last_patch_applied_at = get_value("last_patch_applied_at", "нет")
    last_project_health_report = get_value("last_project_health_report", "нет")
    last_project_health_status = get_value("last_project_health_status", "нет")
    last_project_health_generated_at = get_value("last_project_health_generated_at", "нет")
    last_regression_suite_report = get_value("last_regression_suite_report", "нет")
    last_regression_suite_status = get_value("last_regression_suite_status", "нет")
    last_regression_suite_score = get_value("last_regression_suite_score", "нет")
    last_regression_suite_generated_at = get_value("last_regression_suite_generated_at", "нет")
    last_auto_verification_report = get_value("last_auto_verification_report", "нет")
    last_auto_verification_status = get_value("last_auto_verification_status", "нет")
    last_auto_verification_score = get_value("last_auto_verification_score", "нет")
    last_auto_verification_mode = get_value("last_auto_verification_mode", "нет")
    last_auto_verification_generated_at = get_value("last_auto_verification_generated_at", "нет")
    provider = provider_status()
    git_status_text = git_short_status()
    patch_registry_status = patch_registry_short_status()

    latest_report_text = str(latest_report) if latest_report else "нет"

    return f"""Статус LocalComet:

Модель:
- MODEL: {MODEL}
- API: {LMSTUDIO_API}

Последние данные:
- last_real_goal: {last_real_goal}
- last_task: {last_task}
- last_route: {last_route}
- last_action: {last_action}
- last_report: {last_report}
- latest_report_file: {latest_report_text}
- last_site: {last_site}
- last_windows_app: {last_windows_app}
- last_windows_file: {last_windows_file}
- last_windows_text: {last_windows_text}
- last_error: {last_error}
- last_stability_score: {last_stability_score}
- last_stability_report: {last_stability_report}
- last_automation_task: {last_automation_task}
- last_automation_report: {last_automation_report}
- last_multi_task: {last_multi_task}
- last_task_report: {last_task_report}
- last_browser_batch: {last_browser_batch}
- last_pc_batch: {last_pc_batch}
- last_gpt_browser_action: {last_gpt_browser_action}
- last_gpt_browser_response: {last_gpt_browser_response}
- last_gpt_browser_error: {last_gpt_browser_error}
- gpt_browser_chat_url: {gpt_browser_chat_url}
- last_gpt_browser_response_mode: {last_gpt_browser_response_mode}
- reliable_manual_relay_mode: request.md сюда в ChatGPT -> response.json файлом -> relay проверь ответ
- reject_empty_confirmation_patch: да
- auto_download_response_json: fixed_downloads_import
- button_control_panel: {CONTROL_PANEL_FILE}
- button_control_panel_exists: {CONTROL_PANEL_FILE.exists()}
- control_panel_comfort_pack: да
- one_click_relay_workflow: да
- chat_url_settings_panel: да
- safe_full_cycle_guards: да
- true_auto_relay_cycle: да
- auto_relay_reliability_pack: да
- control_panel_ui_rework_pack: да
- control_panel_tabs: да
- compact_dashboard: да
- organized_relay_tab: да
- organized_browser_tab: да
- organized_autopilot_tab: да
- control_panel_chat_commands: да
- panel_chat_with_model: да
- panel_text_command_input: да
- chat_automation_intents: да
- natural_open_url_intent: да
- natural_search_workflow: да
- natural_page_actions: да
- natural_project_checks: да
- natural_browser_interactions: да
- chat_research_workflow_intents: да
- natural_research_intent: да
- natural_compare_intent: да
- natural_open_page_workflow: да
- browser_mission_report_intents: да
- natural_browser_report_workflow: да
- natural_site_check_workflow: да
- natural_form_workflow_intents: да
- natural_form_fill_sequence: да
- natural_form_submit_guard: да
- russian_control_panel_menu: да
- control_panel_russian_labels: да
- russian_command_center_ui: да
- gray_control_panel_theme: да
- translucent_gray_button_style: да
- control_panel_theme_smoke: да
- project_health_center_pack: да
- project_health_command: да
- project_health_report: да
- safe_health_checks: да
- last_project_health_report: {last_project_health_report}
- last_project_health_status: {last_project_health_status}
- last_project_health_generated_at: {last_project_health_generated_at}
- regression_command_suite_pack: да
- regression_command_suite: да
- regression_command_report: да
- safe_regression_commands: да
- last_regression_suite_report: {last_regression_suite_report}
- last_regression_suite_status: {last_regression_suite_status}
- last_regression_suite_score: {last_regression_suite_score}
- last_regression_suite_generated_at: {last_regression_suite_generated_at}
- auto_verification_pack: да
- auto_verify_command: да
- auto_verify_after_patch: да
- auto_verify_reports: да
- last_auto_verification_report: {last_auto_verification_report}
- last_auto_verification_status: {last_auto_verification_status}
- last_auto_verification_score: {last_auto_verification_score}
- last_auto_verification_mode: {last_auto_verification_mode}
- last_auto_verification_generated_at: {last_auto_verification_generated_at}
- panel_relay_diagnostics_pack: да
- relay_diagnostics: да
- relay_smoke_test: да
- relay_dry_run_safe: да
- last_true_auto_relay_report: {last_true_auto_relay_report}
- last_true_auto_relay_screenshot: {last_true_auto_relay_screenshot}
- last_relay_diagnostics_report: {last_relay_diagnostics_report}
- last_relay_diagnostics_status: {last_relay_diagnostics_status}
- auto_dev_task_clarifier: да
- last_task_clarifier_answer: {str(last_task_clarifier_answer)[:500]}
- last_task_clarifier_goal: {last_task_clarifier_goal}
- gpt_browser_thread_affinity_fix: да
- last_gpt_browser_owner_thread_id: {last_gpt_browser_owner_thread_id}
- last_gpt_browser_thread_reset_reason: {last_gpt_browser_thread_reset_reason}
- response_freshness_guard: да
- ux_grouped_control_panel: да
- safe_auto_cycle_ux_panel: да
- last_true_auto_cycle_id: {last_true_auto_cycle_id}
- last_true_auto_imported_cycle_id: {last_true_auto_imported_cycle_id}
- browser_thread_affinity_fix: да
- last_browser_owner_thread_id: {last_browser_owner_thread_id}
- last_browser_thread_reset_reason: {last_browser_thread_reset_reason}
- browser_action_operator_pack: да
- browser_direct_action_routing_fix: да
- browser_action_auto_recovery: да
- browser_screenshot_action: да
- browser_extract_links_inputs: да
- browser_task_runner: да
- browser_action_safety_guard: да
- last_browser_action: {last_browser_action}
- last_browser_screenshot: {last_browser_screenshot}
- last_browser_error: {last_browser_error}
- last_browser_task_report: {last_browser_task_report}
- browser_multi_step_workflow_pack: да
- browser_workflow_runner: да
- browser_workflow_reports: да
- last_browser_workflow_report: {last_browser_workflow_report}
- last_browser_workflow_status: {last_browser_workflow_status}
- browser_autopilot_operator_pack: да
- browser_autopilot_plan: да
- browser_autopilot_run: да
- browser_autopilot_dry_run: да
- browser_autopilot_safety_guard: да
- browser_autopilot_reports: да
- browser_observe: да
- last_browser_autopilot_report: {last_browser_autopilot_report}
- last_browser_autopilot_status: {last_browser_autopilot_status}
- last_browser_autopilot_task: {last_browser_autopilot_task}
- last_browser_autopilot_mode: {last_browser_autopilot_mode}
- browser_super_operator_pack: да
- browser_research_reports: да
- browser_platform_site_workflow: да
- browser_youtube_search: да
- natural_command_intents: да
- browser_page_audit: да
- browser_form_map: да
- browser_super_safety_guard: да
- last_browser_super_report: {last_browser_super_report}
- last_browser_super_status: {last_browser_super_status}
- last_browser_super_task: {last_browser_super_task}
- last_browser_platform: {last_browser_platform}
- last_browser_platform_url: {last_browser_platform_url}
- last_browser_youtube_query: {last_browser_youtube_query}
- last_browser_youtube_report: {last_browser_youtube_report}
- compact_ui_patch_version_bar: да
- project_boost_pack: да
- dashboard_readability_pack: да
- patch_registry: да
- patch_registry_manual_snapshot: да
- patch_registry_file: {last_patch_registry_file}
- patch_registry_count: {last_patch_registry_count}
- patch_registry_status: {patch_registry_status}
- last_patch_version: {last_patch_version}
- last_patch_summary: {str(last_patch_summary)[:500]}
- last_patch_status: {last_patch_status}
- last_patch_applied_at: {last_patch_applied_at}
- stability_test_modes: да
- error_doctor_fix_request: да
- llm_provider_foundation: да
- llm_offline_graceful_error_pack: yes
- llm_connection_error_handling: yes
- lmstudio_offline_hint: yes
- voice_mode_panel_pack: yes
- voice_chat_mode: yes
- voice_chat_replies: yes
- voice_continuous_dialogue: yes
- voice_faster_whisper_ru: yes
- voice_piper_tts: yes
- voice_vosk_russian_stt: yes
- voice_push_to_talk: yes
- voice_command_safety_guard: yes
- voice_tts: yes
- voice_session_reports: yes
- voice_available: {voice_status.get('enabled')}
- voice_stt_available: {voice_deps.get('usable_stt')}
- voice_faster_whisper_ru_available: {voice_deps.get('usable_faster_whisper_ru')}
- voice_piper_available: {voice_deps.get('piper_available')}
- voice_vosk_ru_available: {voice_deps.get('usable_vosk_ru')}
- voice_vosk_model_path: {voice_deps.get('vosk_model_path') or 'нет'}
- voice_tts_available: {voice_deps.get('usable_tts')}
- last_voice_session_report: {last_voice_session_report}
- llm_provider_name: {provider.get('provider_name')}
- llm_provider_active_url: {provider.get('active_url')}
- codex_bridge_foundation: да
- git_safety_status: да
- git_status: {git_status_text}

Папки:
- Projects: {PROJECTS_DIR}
- Reports: {REPORTS_DIR}
- Windows: {WINDOWS_DIR}
"""


def show_recent():
    latest_report = _get_latest_report()

    lines = ["Последние действия / артефакты:"]

    lines.append(f"- Последняя реальная цель: {get_value('last_real_goal', 'нет')}")
    lines.append(f"- Последняя задача: {get_value('last_task', 'нет')}")
    lines.append(f"- Последний route: {get_value('last_route', 'нет')}")
    lines.append(f"- Последний action: {get_value('last_action', 'нет')}")
    lines.append(f"- Последний отчет в памяти: {get_value('last_report', 'нет')}")
    lines.append(f"- Последний найденный отчет: {latest_report if latest_report else 'нет'}")
    lines.append(f"- Последний сайт: {get_value('last_site', 'нет')}")
    lines.append(f"- Последнее Windows-приложение: {get_value('last_windows_app', 'нет')}")
    lines.append(f"- Последний Windows-файл: {get_value('last_windows_file', 'нет')}")
    lines.append(f"- Последний введенный текст: {get_value('last_windows_text', 'нет')}")
    lines.append(f"- Последняя ошибка: {get_value('last_error', 'нет')}")

    return "\n".join(lines)


def handle(action: str, data: dict):
    if action == "help":
        return show_help()

    if action == "status":
        return show_status()

    if action in ["health", "project_health"]:
        return format_project_health_text()

    if action in ["health_report", "project_health_report"]:
        path = write_project_health_report()
        return f"Project Health report создан:\n{path}\n\n{format_project_health_text()}"

    if action in ["regression", "regression_suite"]:
        suite = run_regression_command_suite(write_report=False)
        return format_regression_command_suite(suite)

    if action in ["regression_report", "regression_suite_report"]:
        suite = run_regression_command_suite(write_report=True)
        return format_regression_command_suite(suite)

    if action in ["auto_verify", "auto_verification", "verify", "verify_quick"]:
        result = run_auto_verification(mode="quick", write_report=True)
        return format_auto_verification(result)

    if action in ["auto_verify_full", "verify_full", "auto_verification_full"]:
        result = run_auto_verification(mode="full", write_report=True)
        return format_auto_verification(result)

    if action in ["auto_verify_post_patch", "verify_post_patch"]:
        result = run_auto_verification(mode="post_patch", write_report=True)
        return format_auto_verification(result)

    if action == "voice_status":
        status = get_voice_status()
        deps = status.get("dependencies", {})
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
            f"- last_report: {latest_voice_session_report() or 'нет'}",
        ]
        messages = deps.get("messages") or []

        if messages:
            lines.append("")
            lines.append("Messages:")
            lines.extend(f"- {message}" for message in messages)

        return "\n".join(lines)

    if action == "voice_test":
        deps = check_voice_dependencies()
        lines = [
            "Voice test:",
            f"- usable_stt: {deps.get('usable_stt')}",
            f"- usable_tts: {deps.get('usable_tts')}",
        ]
        lines.extend(f"- {message}" for message in deps.get("messages") or [])
        return "\n".join(lines)

    if action == "voice_speak":
        return f"Voice speak result: {speak_text(data.get('text', ''), enabled=True)}"

    if action == "voice_last_report":
        return latest_voice_session_report() or "Voice session report пока не найден."

    if action == "memory":
        return _format_state()

    if action == "recent":
        return show_recent()

    if action == "model":
        return f"Текущая модель LocalComet: {MODEL}"

    return "System Agent: неизвестное действие."
