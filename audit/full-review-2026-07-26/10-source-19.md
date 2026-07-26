# Полный исходный код (продолжение)

### ПУТЬ: modules/task_clarifier.py (113 строк, 3520 байт)

````python
from core.state import set_value
from modules import gpt_browser_bridge


FINAL_GOAL_MARKERS = [
    "ФИНАЛЬНАЯ УТОЧНЕННАЯ ЗАДАЧА:",
    "УЛУЧШЕННАЯ ЗАДАЧА:",
    "Улучшенная задача:",
    "Финальная задача:",
]


def _build_prompt(goal: str):
    return f"""
Ты помогаешь уточнять dev task для локального Python-проекта LocalComet.

ВАЖНО:
- Это НЕ запрос на patch.
- Не создавай response.json.
- Не создавай JSON patch.
- Не применяй изменения.
- Твоя задача — уточнить формулировку будущей задачи разработки.

Исходная задача пользователя:
{goal}

Верни ответ строго в таком формате:

ПОНИМАНИЕ:
кратко, что нужно сделать

ВОПРОСЫ/РИСКИ:
- что может быть неясно
- где возможны ошибки

ФАЙЛЫ:
- какие файлы вероятно менять

ФИНАЛЬНАЯ УТОЧНЕННАЯ ЗАДАЧА:
одна цельная формулировка dev task, которую можно вставить в LocalComet

КОНЕЦ
""".strip()


def extract_goal(answer: str):
    text = str(answer or "")

    for marker in FINAL_GOAL_MARKERS:
        index = text.find(marker)

        if index == -1:
            continue

        goal = text[index + len(marker):].strip()

        for end_marker in ["\nКОНЕЦ", "\nВОПРОСЫ", "\nФАЙЛЫ", "\nПОНИМАНИЕ"]:
            end_index = goal.find(end_marker)

            if end_index != -1:
                goal = goal[:end_index].strip()

        goal = goal.strip(" \n\r\t:-—")

        if goal:
            return goal

    return ""


def clarify_dev_task(goal: str, timeout_sec: int = 300):
    goal = str(goal or "").strip()

    if len(goal) < 20:
        result = {
            "ok": False,
            "answer": "STOP: задача слишком короткая для уточнения. Нужно минимум 20 символов.",
            "extracted_goal": "",
        }
        return result

    prompt = _build_prompt(goal)

    open_result = gpt_browser_bridge.open_chatgpt()
    paste_result = gpt_browser_bridge.paste_text(prompt)
    send_result = gpt_browser_bridge.send_prompt()
    wait_result = gpt_browser_bridge.wait_response(timeout_sec=int(timeout_sec or 300))
    answer = gpt_browser_bridge.read_last_assistant_message(limit=8000)

    extracted_goal = extract_goal(answer)

    if not extracted_goal:
        extracted_goal = goal

    set_value("last_task_clarifier_source_goal", goal)
    set_value("last_task_clarifier_answer", answer)
    set_value("last_task_clarifier_goal", extracted_goal)
    set_value("last_task_clarifier_open_result", open_result)
    set_value("last_task_clarifier_paste_result", paste_result)
    set_value("last_task_clarifier_send_result", send_result)
    set_value("last_task_clarifier_wait_result", wait_result)

    ok = "STOP:" not in str(answer)

    return {
        "ok": ok,
        "answer": answer,
        "extracted_goal": extracted_goal,
        "open_result": open_result,
        "paste_result": paste_result,
        "send_result": send_result,
        "wait_result": wait_result,
    }
````

### ПУТЬ: modules/task_contract_registry_ru.py (851 строк, 35592 байт)

````python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List, Optional

TASK_CONTRACT_REGISTRY_VERSION = "v6.76a"

ROOT_DIR = get_project_root()
if not ROOT_DIR.exists():
    ROOT_DIR = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _registry() -> List[Dict[str, Any]]:
    return [
        {
            "id": "screenshot_status",
            "title": "Screenshot status",
            "aliases": [
                "статус скриншотов",
                "status screenshots",
                "screenshot storage status",
            ],
            "category": "safety_status",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "read-only storage status report",
            "required_gates": ["py_compile"],
            "evidence_files": [
                "modules/screenshot_capture_policy_ru.py",
            ],
            "notes": "Enabled_by_default=False by v6.65b policy gate",
        },
        {
            "id": "working_directory_guard",
            "title": "Working directory guard",
            "aliases": [
                "проверь рабочую папку",
                "working directory guard",
            ],
            "category": "safety_validation",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "read-only CWD validation against project root",
            "required_gates": ["py_compile"],
            "evidence_files": [
                "modules/working_directory_guard_ru.py",
            ],
            "notes": "",
        },
        {
            "id": "strict_project_stability",
            "title": "Strict project stability",
            "aliases": [
                "проверь проект",
            ],
            "category": "validation_gate",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "True [] []",
            "required_gates": ["py_compile", "strict_expected"],
            "evidence_files": [
                "modules/strict_project_stability_ru.py",
            ],
            "notes": "326/326 score target. v6.65e routed directly to strict_project_stability_ru (~2s)",
        },
        {
            "id": "computer_use_contracts",
            "title": "Computer Use contracts",
            "aliases": [
                "pc computer contracts",
                "pc computer contract",
                "computer use contracts",
                "контракты computer use",
            ],
            "category": "validation_gate",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "80/80 PASS",
            "required_gates": ["py_compile", "contract_expected"],
            "evidence_files": [
                "modules/computer_use_contract_tests_ru.py",
            ],
            "notes": "Runs 80 contract_* test functions",
        },
        {
            "id": "functional_tests",
            "title": "Functional tests",
            "aliases": [
                "functional tests",
                "run functional tests",
                "localcomet test full",
                "полный тест",
            ],
            "category": "validation_gate",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "45/45 PASS",
            "required_gates": ["py_compile", "functional_expected"],
            "evidence_files": [
                "modules/localcomet_functional_test_center_ru.py",
            ],
            "notes": "Risk LOW/MEDIUM because suite can take time. Smoke: 34, Full: 45",
        },
        {
            "id": "computer_use_simulate_browser",
            "title": "Computer Use simulate browser",
            "aliases": [
                "pc computer full control simulate открой браузер",
            ],
            "category": "computer_use_dry_run",
            "risk_class": "MEDIUM",
            "approval_required": False,
            "real_action": False,
            "simulate_only": True,
            "allowed_real_action": None,
            "expected_behavior": "simulate=True, dry-run only, no browser opened",
            "required_gates": ["py_compile", "simulate_only"],
            "evidence_files": [
                "modules/computer_use_core_ru.py",
                "modules/premium_task_panel_ru.py",
            ],
            "notes": "dry_run_action returns allowed_to_execute=False",
        },
        {
            "id": "plain_browser_open_request",
            "title": "Direct browser open request",
            "aliases": [
                "открой браузер",
            ],
            "category": "direct_allowlisted_real_action",
            "risk_class": "MEDIUM",
            "approval_required": False,
            "real_action": True,
            "simulate_only": False,
            "allowed_real_action": "Python webbrowser.open (fixed URL only)",
            "expected_behavior": "opens default browser directly, no confirmation prompt, no arbitrary URL handling",
            "required_gates": ["py_compile", "allowlisted_method", "no_user_input_executed"],
            "evidence_files": [
                "LocalComet_Control_Panel.py",
                "modules/confirmed_app_actions_ru.py",
            ],
            "notes": "v6.72: direct allowlisted command. No confirmation required. User_input_executed: False. Fixed method only.",
        },
        {
            "id": "confirmed_browser_open_action",
            "title": "Confirmed browser open action",
            "aliases": [
                "подтвердить открыть браузер",
                "confirm open browser",
                "подтвердить запустить браузер",
            ],
            "category": "allowlisted_real_action",
            "risk_class": "MEDIUM",
            "approval_required": False,
            "real_action": True,
            "simulate_only": False,
            "allowed_real_action": "Python webbrowser.open only",
            "expected_behavior": "opens default browser via webbrowser module, real_action=True",
            "required_gates": ["py_compile", "allowlisted_method"],
            "evidence_files": [
                "LocalComet_Control_Panel.py",
            ],
            "notes": "Allowlist-protected: only this specific method can execute real desktop actions",
        },
        {
            "id": "ordinary_russian_text",
            "title": "Ordinary Russian text",
            "aliases": [
                "почему не работает",
                "привет",
                "здравствуй",
            ],
            "examples": [
                "почему не работает",
                "привет",
                "здравствуй",
                "как дела",
            ],
            "category": "chat_fallback",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "new_menu_only route, premium_task_panel_ru local chat, must NOT route to Computer Use",
            "required_gates": ["py_compile", "must_not_route_to_computer_use"],
            "evidence_files": [
                "modules/premium_task_panel_ru.py",
            ],
            "notes": "Fallback to _local_chat_reply or _ask_local_llm_chat",
        },
        {
            "id": "app_harness_status",
            "title": "App Harness registry status",
            "aliases": [
                "app harness status",
                "реестр приложений",
                "app registry",
            ],
            "category": "app_harness_query",
            "risk_class": "MEDIUM",
            "approval_required": False,
            "real_action": False,
            "simulate_only": True,
            "allowed_real_action": None,
            "expected_behavior": "read-only registry summary, dry-run plan only",
            "required_gates": ["py_compile", "dry_run_only"],
            "evidence_files": [
                "modules/app_harness_registry_ru.py",
            ],
            "notes": "v6.68 — no real app launches enabled",
        },
        {
            "id": "app_harness_plan_calculator",
            "title": "App Harness plan calculator",
            "aliases": [
                "app harness plan calculator",
                "app harness plan калькулятор",
                "план запуска калькулятор",
                "план запуска calc",
            ],
            "category": "app_harness_dry_run_plan",
            "risk_class": "MEDIUM",
            "approval_required": False,
            "real_action": False,
            "simulate_only": True,
            "allowed_real_action": None,
            "expected_behavior": "dry-run plan only, no real launch",
            "required_gates": ["py_compile", "dry_run_only"],
            "evidence_files": [
                "modules/app_harness_registry_ru.py",
            ],
            "notes": "v6.68 — requires future explicit allowlist patch for real launch",
        },
        {
            "id": "app_harness_plan_explorer",
            "title": "App Harness plan explorer",
            "aliases": [
                "app harness plan explorer",
                "app harness plan проводник",
                "план запуска проводник",
                "план запуска explorer",
            ],
            "category": "app_harness_dry_run_plan",
            "risk_class": "MEDIUM",
            "approval_required": False,
            "real_action": False,
            "simulate_only": True,
            "allowed_real_action": None,
            "expected_behavior": "dry-run plan only, no real launch",
            "required_gates": ["py_compile", "dry_run_only"],
            "evidence_files": [
                "modules/app_harness_registry_ru.py",
            ],
            "notes": "v6.68 — requires future explicit allowlist patch for real launch",
        },
        {
            "id": "app_harness_plan_notepad",
            "title": "App Harness plan notepad",
            "aliases": [
                "app harness plan notepad",
                "app harness plan блокнот",
                "план запуска блокнот",
                "план запуска notepad",
            ],
            "category": "app_harness_dry_run_plan",
            "risk_class": "MEDIUM",
            "approval_required": False,
            "real_action": False,
            "simulate_only": True,
            "allowed_real_action": None,
            "expected_behavior": "dry-run plan only, no real launch",
            "required_gates": ["py_compile", "dry_run_only"],
            "evidence_files": [
                "modules/app_harness_registry_ru.py",
            ],
            "notes": "v6.68 — requires future explicit allowlist patch for real launch",
        },
        {
            "id": "plain_calculator_open_request",
            "title": "Direct calculator open request",
            "aliases": [
                "открой калькулятор",
                "открыть калькулятор",
                "open calculator",
            ],
            "category": "direct_allowlisted_real_action",
            "risk_class": "MEDIUM",
            "approval_required": False,
            "real_action": True,
            "simulate_only": False,
            "allowed_real_action": "subprocess.Popen(['calc.exe'], shell=False)",
            "expected_behavior": "opens Windows Calculator directly, no confirmation prompt, no arbitrary shell execution",
            "required_gates": ["py_compile", "allowlisted_method", "no_user_input_executed"],
            "evidence_files": [
                "LocalComet_Control_Panel.py",
                "modules/confirmed_app_actions_ru.py",
            ],
            "notes": "v6.72: direct allowlisted command. No confirmation required. User_input_executed: False. Fixed method only.",
        },
        {
            "id": "confirmed_calculator_open_action",
            "title": "Confirmed calculator open action",
            "aliases": [
                "подтвердить открыть калькулятор",
                "confirm open calculator",
                "подтвердить запустить калькулятор",
            ],
            "category": "allowlisted_real_action",
            "risk_class": "MEDIUM",
            "approval_required": False,
            "real_action": True,
            "simulate_only": False,
            "allowed_real_action": "subprocess.Popen(['calc.exe'], shell=False)",
            "expected_behavior": "opens Windows Calculator via subprocess, real_action=True, no arbitrary shell execution",
            "required_gates": ["py_compile", "allowlisted_method"],
            "evidence_files": [
                "modules/confirmed_app_actions_ru.py",
            ],
            "notes": "Allowlist-protected: only fixed method subprocess.Popen(['calc.exe'], shell=False) can execute. No user input injected.",
        },
        {
            "id": "plain_notepad_open_request",
            "title": "Direct notepad open request",
            "aliases": [
                "открой блокнот",
                "открыть блокнот",
                "open notepad",
            ],
            "category": "direct_allowlisted_real_action",
            "risk_class": "MEDIUM",
            "approval_required": False,
            "real_action": True,
            "simulate_only": False,
            "allowed_real_action": "subprocess.Popen(['notepad.exe'], shell=False)",
            "expected_behavior": "opens Windows Notepad directly, no confirmation prompt, no typing, no file operations",
            "required_gates": ["py_compile", "allowlisted_method", "no_user_input_executed"],
            "evidence_files": [
                "LocalComet_Control_Panel.py",
                "modules/confirmed_app_actions_ru.py",
            ],
            "notes": "v6.72: direct allowlisted command. No confirmation required. User_input_executed: False. Fixed method only.",
        },
        {
            "id": "confirmed_notepad_open_action",
            "title": "Confirmed notepad open action",
            "aliases": [
                "подтвердить открыть блокнот",
                "confirm open notepad",
                "подтвердить запустить блокнот",
            ],
            "category": "allowlisted_real_action",
            "risk_class": "MEDIUM",
            "approval_required": False,
            "real_action": True,
            "simulate_only": False,
            "allowed_real_action": "subprocess.Popen(['notepad.exe'], shell=False)",
            "expected_behavior": "opens Windows Notepad via subprocess, real_action=True, no arbitrary shell execution",
            "required_gates": ["py_compile", "allowlisted_method"],
            "evidence_files": [
                "modules/confirmed_app_actions_ru.py",
            ],
            "notes": "Allowlist-protected: only fixed method subprocess.Popen(['notepad.exe'], shell=False) can execute. No user input injected.",
        },
        {
            "id": "plain_explorer_open_request",
            "title": "Direct explorer open request",
            "aliases": [
                "открой проводник",
                "открыть проводник",
                "open explorer",
            ],
            "category": "direct_allowlisted_real_action",
            "risk_class": "MEDIUM",
            "approval_required": False,
            "real_action": True,
            "simulate_only": False,
            "allowed_real_action": "subprocess.Popen(['explorer.exe'], shell=False)",
            "expected_behavior": "opens Windows File Explorer directly, no confirmation prompt, no path navigation, no file operations",
            "required_gates": ["py_compile", "allowlisted_method", "no_user_input_executed"],
            "evidence_files": [
                "LocalComet_Control_Panel.py",
                "modules/confirmed_app_actions_ru.py",
            ],
            "notes": "v6.72: direct allowlisted command. No confirmation required. User_input_executed: False. Fixed method only.",
        },
        {
            "id": "confirmed_explorer_open_action",
            "title": "Confirmed explorer open action",
            "aliases": [
                "подтвердить открыть проводник",
                "confirm open explorer",
                "подтвердить запустить проводник",
            ],
            "category": "allowlisted_real_action",
            "risk_class": "MEDIUM",
            "approval_required": False,
            "real_action": True,
            "simulate_only": False,
            "allowed_real_action": "subprocess.Popen(['explorer.exe'], shell=False)",
            "expected_behavior": "opens Windows File Explorer via subprocess, real_action=True, no arbitrary shell execution",
            "required_gates": ["py_compile", "allowlisted_method"],
            "evidence_files": [
                "modules/confirmed_app_actions_ru.py",
            ],
            "notes": "Allowlist-protected: only fixed method subprocess.Popen(['explorer.exe'], shell=False) can execute. No user input injected.",
        },
        {
            "id": "parallel_session_status",
            "title": "Parallel session status",
            "aliases": [
                "parallel sessions status",
                "статус параллельных сессий",
            ],
            "category": "development_safety_query",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "read-only parallel session status report from .localcomet/parallel_sessions/",
            "required_gates": ["py_compile"],
            "evidence_files": [
                "modules/parallel_worktree_executor_protocol_ru.py",
            ],
            "notes": "v6.73 — parallel sessions registry read-only query",
        },
        {
            "id": "parallel_session_execute",
            "title": "Parallel session execute plan",
            "aliases": [
                "parallel session execute",
                "выполнить параллельную сессию",
            ],
            "category": "development_safety_execute_plan",
            "risk_class": "MEDIUM",
            "approval_required": True,
            "real_action": False,
            "simulate_only": True,
            "allowed_real_action": None,
            "expected_behavior": "creates a plan file under .localcomet/parallel_sessions/ but does not execute real worktree commands",
            "required_gates": ["py_compile", "dry_run_only"],
            "evidence_files": [
                "modules/parallel_worktree_executor_protocol_ru.py",
            ],
            "notes": "v6.73 — future real execution blocked behind allowlist patch. Currently writes plan only.",
        },
        {
            "id": "parallel_session_policy",
            "title": "Parallel session policy",
            "aliases": [
                "parallel session policy",
                "политика параллельных сессий",
            ],
            "category": "development_safety_policy",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "read-only parallel session policy description",
            "required_gates": ["py_compile"],
            "evidence_files": [
                "modules/parallel_worktree_executor_protocol_ru.py",
            ],
            "notes": "v6.73 — policy docs for concurrent/serial worktree operations",
        },
        {
            "id": "development_safety_status",
            "title": "Development safety status",
            "aliases": [
                "dev safety status",
                "development safety status",
                "статус разработки",
                "статус безопасности разработки",
            ],
            "category": "development_safety_query",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "read-only safety gate status, git status snapshot, diff risk level",
            "required_gates": ["py_compile"],
            "evidence_files": [
                "modules/development_safety_orchestrator_ru.py",
            ],
            "notes": "v6.74 — orchestrator reports gate states without executing real changes",
        },
        {
            "id": "development_safety_evaluate",
            "title": "Development safety evaluate",
            "aliases": [
                "dev safety evaluate",
                "preflight audit",
                "оценить безопасность разработки",
            ],
            "category": "development_safety_evaluate",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "read-only safety evaluation: git status, diff size, gate snapshot comparison",
            "required_gates": ["py_compile"],
            "evidence_files": [
                "modules/development_safety_orchestrator_ru.py",
            ],
            "notes": "v6.74 — no file changes, no shell commands executed",
        },
        {
            "id": "development_safety_diff",
            "title": "Development safety diff limit",
            "aliases": [
                "development safety diff",
                "diff limit status",
                "статус лимита diff",
            ],
            "category": "development_safety_query",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "read-only diff size report against configured limit",
            "required_gates": ["py_compile"],
            "evidence_files": [
                "modules/development_safety_orchestrator_ru.py",
            ],
            "notes": "v6.74 — no git diff executed outside safe bounds check",
        },
        {
            "id": "reviewer_bridge_create",
            "title": "Reviewer bridge create",
            "aliases": [
                "reviewer bridge create",
                "создай запрос ревью",
                "создать ревью",
                "create review",
            ],
            "category": "reviewer_bridge_write",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "creates a review request JSON file under .localcomet/reviewer/, no shell execution",
            "required_gates": ["py_compile"],
            "evidence_files": [
                "modules/reviewer_bridge_ru.py",
            ],
            "notes": "v6.75 — writes to .localcomet/reviewer/ only. No real code review. No shell commands.",
        },
        {
            "id": "reviewer_bridge_status",
            "title": "Reviewer bridge status",
            "aliases": [
                "reviewer bridge status",
                "статус ревью",
                "review status",
            ],
            "category": "reviewer_bridge_query",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "read-only review request listing from .localcomet/reviewer/",
            "required_gates": ["py_compile"],
            "evidence_files": [
                "modules/reviewer_bridge_ru.py",
            ],
            "notes": "v6.75 — reads existing review request files, no file changes",
        },
        {
            "id": "reviewer_bridge_verdict",
            "title": "Reviewer bridge verdict",
            "aliases": [
                "reviewer bridge verdict",
                "вердикт ревью",
                "review verdict",
            ],
            "category": "reviewer_bridge_query",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "read-only verdict summary from review request files",
            "required_gates": ["py_compile"],
            "evidence_files": [
                "modules/reviewer_bridge_ru.py",
            ],
            "notes": "v6.75 — reads verdict from existing review JSON files only",
        },
        {
            "id": "executor_adapter_status",
            "title": "Executor adapter status",
            "aliases": [
                "executor adapter status",
                "статус адаптеров исполнителя",
                "executor registry",
            ],
            "category": "executor_registry_query",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "read-only registry summary of all executor adapters (available, future, manual)",
            "required_gates": ["py_compile"],
            "evidence_files": [
                "modules/executor_adapter_registry_ru.py",
            ],
            "notes": "v6.76 — adapter registry query, no real executor spawning",
        },
        {
            "id": "executor_adapter_recommend",
            "title": "Executor adapter recommend",
            "aliases": [
                "recommend executor",
                "рекомендовать исполнителя",
                "recommend adapter",
            ],
            "category": "executor_registry_query",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "read-only recommendation of best executor adapter based on task type",
            "required_gates": ["py_compile"],
            "evidence_files": [
                "modules/executor_adapter_registry_ru.py",
            ],
            "notes": "v6.76 — returns recommendation string only, no executor activation",
        },
        {
            "id": "opencode_recovery_status",
            "title": "OpenCode recovery status",
            "aliases": [
                "opencode recovery status",
                "статус восстановления opencode",
            ],
            "category": "executor_registry_query",
            "risk_class": "LOW",
            "approval_required": False,
            "real_action": False,
            "simulate_only": False,
            "allowed_real_action": None,
            "expected_behavior": "read-only recovery status report from executor adapter registry",
            "required_gates": ["py_compile"],
            "evidence_files": [
                "modules/executor_adapter_registry_ru.py",
            ],
            "notes": "v6.76 — reads .localcomet/executor_adapter/recovery_status.json if available",
        },
    ]


def get_task_contract_registry() -> List[Dict[str, Any]]:
    return _registry()


def get_task_contract(command: str) -> Optional[Dict[str, Any]]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    for entry in _registry():
        for alias in entry.get("aliases", []):
            if lower == alias.strip().lower().replace("ё", "е"):
                return entry
            if entry.get("id") == "ordinary_russian_text":
                for example in entry.get("examples", []):
                    if lower == example.strip().lower().replace("ё", "е"):
                        return entry
    return None


def classify_task_contract(command: str) -> Dict[str, Any]:
    contract = get_task_contract(command)
    if contract:
        return {
            "ok": True,
            "id": contract["id"],
            "title": contract["title"],
            "risk_class": contract["risk_class"],
            "approval_required": contract["approval_required"],
            "real_action": contract["real_action"],
            "simulate_only": contract["simulate_only"],
            "evidence_files": contract["evidence_files"],
        }
    return {
        "ok": False,
        "id": None,
        "risk_class": "UNKNOWN",
        "approval_required": None,
        "real_action": None,
        "simulate_only": None,
        "evidence_files": [],
    }


def _match_registry_command(command: str) -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {
        "task contract registry",
        "реестр контрактов задач",
    }:
        return True
    if lower.startswith("контракт команды ") or lower.startswith("contract for "):
        return True
    return False


def _run_registry_command(command: str) -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    commands = []
    if lower in {"task contract registry", "реестр контрактов задач"}:
        registry = _registry()
        summary = {
            "total_entries": len(registry),
            "risk_classes": {},
            "approval_required_count": 0,
            "real_action_count": 0,
            "simulate_only_count": 0,
            "aliases_covered": sum(len(e.get("aliases", [])) for e in registry),
        }
        for entry in registry:
            rc = entry["risk_class"]
            summary["risk_classes"][rc] = summary["risk_classes"].get(rc, 0) + 1
            if entry["approval_required"]:
                summary["approval_required_count"] += 1
            if entry["real_action"]:
                summary["real_action_count"] += 1
            if entry["simulate_only"]:
                summary["simulate_only_count"] += 1
        return {
            "mode": "task_contract_registry_summary",
            "version": TASK_CONTRACT_REGISTRY_VERSION,
            "summary": summary,
            "entries": [
                {
                    "id": e["id"],
                    "title": e["title"],
                    "risk_class": e["risk_class"],
                    "approval_required": e["approval_required"],
                    "real_action": e["real_action"],
                }
                for e in registry
            ],
        }
    if lower.startswith("контракт команды "):
        target_command = lower[len("контракт команды "):].strip()
        contract = get_task_contract(target_command)
        if contract:
            return {
                "mode": "task_contract_detail",
                "version": TASK_CONTRACT_REGISTRY_VERSION,
                "contract": contract,
                "classification": classify_task_contract(target_command),
            }
        return {
            "mode": "task_contract_not_found",
            "version": TASK_CONTRACT_REGISTRY_VERSION,
            "query": target_command,
            "result": "Контракт не найден для указанной команды",
        }
    if lower.startswith("contract for "):
        target_command = lower[len("contract for "):].strip()
        contract = get_task_contract(target_command)
        if contract:
            return {
                "mode": "task_contract_detail",
                "version": TASK_CONTRACT_REGISTRY_VERSION,
                "contract": contract,
                "classification": classify_task_contract(target_command),
            }
        return {
            "mode": "task_contract_not_found",
            "version": TASK_CONTRACT_REGISTRY_VERSION,
            "query": target_command,
            "result": "No contract found for the specified command",
        }
    return {
        "mode": "task_contract_registry_error",
        "version": TASK_CONTRACT_REGISTRY_VERSION,
        "result": "Unknown registry command",
    }


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"status", "pc task contract registry status"}:
        return status()
    if lower in {"report", "pc task contract registry report"}:
        return report()
    if _match_registry_command(lower):
        return _run_registry_command(lower)
    return {
        "mode": "task_contract_registry_unrecognized",
        "version": TASK_CONTRACT_REGISTRY_VERSION,
        "result": "Команда не распознана. Используйте: реестр контрактов задач, task contract registry, контракт команды <команда>",
    }


def status() -> Dict[str, Any]:
    registry = _registry()
    return {
        "ok": True,
        "mode": "task_contract_registry_status",
        "version": TASK_CONTRACT_REGISTRY_VERSION,
        "total_entries": len(registry),
        "aliases_covered": sum(len(e.get("aliases", [])) for e in registry),
        "risk_classes": sorted(set(e["risk_class"] for e in registry)),
        "approval_required_count": sum(1 for e in registry if e["approval_required"]),
        "real_action_count": sum(1 for e in registry if e["real_action"]),
        "simulate_only_count": sum(1 for e in registry if e["simulate_only"]),
    }


def report() -> Dict[str, Any]:
    registry = _registry()
    return {
        "ok": True,
        "mode": "task_contract_registry_report",
        "version": TASK_CONTRACT_REGISTRY_VERSION,
        "generated_at": _now(),
        "entries": registry,
        "status": status(),
    }
````

### ПУТЬ: modules/task_planner_orchestrator_ru.py (462 строк, 16815 байт)

````python
from __future__ import annotations

import hashlib
import re
from typing import Any


TASK_PLANNER_VERSION = "v6.82"

_MODE = "explainable_task_plan"
_PREFIXES = (
    "спланируй задачу",
    "план задачи",
    "task plan",
)
_INTENT_ORDER = (
    "inspect",
    "explain",
    "analyze",
    "test",
    "edit",
    "create",
    "execute",
    "install",
    "delete",
    "move",
    "network",
    "credential",
    "security_bypass",
    "system_change",
    "mixed",
    "unknown",
)
_READ_ONLY_ACTIONS = {"inspect", "explain", "analyze"}
_APPROVAL_ACTIONS = {
    "test",
    "edit",
    "create",
    "execute",
    "install",
    "delete",
    "move",
    "network",
    "credential",
    "security_bypass",
    "system_change",
}
_CRITICAL_ACTIONS = {"credential", "security_bypass", "system_change"}
_HIGH_ACTIONS = {"execute", "install", "delete", "move", "network"}
_MEDIUM_ACTIONS = {"test", "edit", "create"}
_SAFE_FILE_PREFIXES = ("agents/", "core/", "docs/", "modules/", "next/", "tools/")
_SAFE_FILE_RE = re.compile(
    r"(?<![A-Za-z0-9_./\\-])((?:agents|core|docs|modules|next|tools)[/\\][A-Za-z0-9_./\\-]+\.[A-Za-z0-9_]+)"
)
_DANGEROUS_PATH_PATTERNS = (
    re.compile(r"(?i)(?:^|\s)\.\.[/\\]"),
    re.compile(r"(?i)\b[A-Z]:[/\\]"),
    re.compile(r"(?i)(?:^|\s)//[^/\s]+/"),
    re.compile(r"(?i)(?:^|\s)\\\\[^\\\s]+\\"),
    re.compile(r"(?i)(?:^|\s)/(?:etc|bin|sbin|usr|var|root|home|Users)(?:/|\s|$)"),
    re.compile(r"(?i)(?:^|\s)~[/\\]"),
)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
    re.IGNORECASE | re.DOTALL,
)
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_PRIVATE_KEY_RE, "<PRIVATE_KEY>"),
    (re.compile(r"(?i)\bauthorization\s*:\s*[^\s]+(?:\s+[^\s]+)?"), "Authorization: <REDACTED_TOKEN>"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{6,}"), "Bearer [REDACTED: secret in modules/task_planner_orchestrator_ru.py:70]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "<REDACTED_TOKEN>"),
    (re.compile(r"\bghp_[A-Za-z0-9_]{8,}\b"), "<REDACTED_TOKEN>"),
    (re.compile(r"(?i)\b[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY|ACCESS_KEY)\s*=\s*[^\s]+"), "<REDACTED_SECRET>"),
    (re.compile(r"(?i)\b(password|passwd|pwd|пароль)\s*[:=]\s*[^\s]+"), r"\1=<REDACTED_PASSWORD>"),
    (re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+(?:\\[^\s]*)?"), "<USER_PATH>"),
    (re.compile(r"(?i)\b[A-Z]:/Users/[^/\s]+(?:/[^\s]*)?"), "<USER_PATH>"),
    (re.compile(r"(?i)(?<!\S)/(?:home|Users)/[^/\s]+(?:/[^\s]*)?"), "<USER_PATH>"),
    (re.compile(r"(?i)(?<!\S)~[/\\][^\s]+"), "<USER_PATH>"),
    (re.compile(r"(?i)\\\\[^\\\s]+\\[^\\\s]+\\(?:Users\\)?[^\\\s]+(?:\\[^\s]*)?"), "<USER_PATH>"),
)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _normalize_key(value: Any) -> str:
    return _normalize_text(value).lower().replace("ё", "е")


def _redact(text: str) -> str:
    redacted = str(text or "")
    for pattern, replacement in _REDACTIONS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _preview(text: str) -> str:
    redacted = _redact(text)
    suffix = " <TRUNCATED>"
    if len(redacted) <= 300:
        return redacted
    return redacted[: 300 - len(suffix)].rstrip() + suffix


def _language(text: str) -> str:
    has_ru = any("а" <= char <= "я" or char == "ё" for char in text.lower())
    has_en = any("a" <= char <= "z" for char in text.lower())
    if has_ru and has_en:
        return "mixed"
    if has_ru:
        return "ru"
    if has_en:
        return "en"
    return "unknown"


def _base_schema(ok: bool) -> dict[str, Any]:
    return {
        "mode": _MODE,
        "version": TASK_PLANNER_VERSION,
        "ok": ok,
        "request": {
            "preview": "",
            "sha256": "",
            "language": "unknown",
            "normalized_length": 0,
        },
        "intent": {
            "category": "unknown",
            "read_only": True,
            "requested_actions": [],
        },
        "risk": {
            "level": "LOW",
            "reasons": [],
            "blocked": False,
        },
        "contract": {
            "goal": "",
            "inputs": [],
            "constraints": [],
            "success_criteria": [],
        },
        "context": {
            "required_files": [],
            "required_capabilities": [],
            "missing_information": [],
        },
        "steps": [],
        "approval": {
            "required": False,
            "reason": "",
            "execution_allowed": False,
        },
        "execution": {
            "performed": False,
            "writes": 0,
            "commands_run": 0,
            "network_requests": 0,
        },
        "warnings": [],
    }


def _match_prefix(command: str) -> tuple[bool, str, str]:
    normalized = _normalize_text(command)
    lowered = normalized.lower().replace("ё", "е")
    for prefix in _PREFIXES:
        normalized_prefix = prefix.replace("ё", "е")
        if lowered == normalized_prefix:
            return False, prefix, ""
        marker = normalized_prefix + " "
        if lowered.startswith(marker):
            return True, prefix, normalized[len(marker) :].strip()
    return False, "", ""


def is_task_plan_command(command: str = "") -> bool:
    matched, _prefix, request = _match_prefix(command)
    return matched and bool(request)


def parse_task_request(command: str) -> dict[str, Any]:
    matched, prefix, body = _match_prefix(command)
    if not matched or not body:
        return {
            "ok": False,
            "prefix": prefix,
            "normalized": "",
            "preview": "",
            "sha256": "",
            "language": "unknown",
            "normalized_length": 0,
            "warnings": ["empty_or_unrecognized_task_request"],
        }
    normalized = _normalize_text(body)
    return {
        "ok": True,
        "prefix": prefix,
        "normalized": normalized,
        "preview": _preview(normalized),
        "sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "language": _language(normalized),
        "normalized_length": len(normalized),
        "warnings": [],
    }


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _detect_actions(text: str) -> list[str]:
    lowered = text.lower().replace("ё", "е")
    actions: set[str] = set()
    if _contains_any(lowered, ("объяс", "explain", "describe", "поясн")):
        actions.add("explain")
    if _contains_any(lowered, ("анализ", "analyze", "analyse", "static analysis", "разбор")):
        actions.add("analyze")
    if _contains_any(lowered, ("провер", "inspect", "review", "read-only", "без изменений", "without changes")):
        actions.add("inspect")
    if _contains_any(lowered, ("тест", "test", "regression", "validation suite")):
        actions.add("test")
    if _contains_any(lowered, ("редакт", "исправ", "patch", "edit", "modify", "change source", "изменить")) and "без изменений" not in lowered:
        actions.add("edit")
    if _contains_any(lowered, ("создай", "создать", "create", "new file", "add file")):
        actions.add("create")
    if _contains_any(lowered, ("execute", "run command", "shell", "subprocess", "запусти команд", "выполни команд", "запустить скрипт")):
        actions.add("execute")
    if _contains_any(lowered, ("install", "pip install", "npm install", "установи", "установить пакет")):
        actions.add("install")
    if _contains_any(lowered, ("delete", "remove file", "удали", "удалить", "стереть", "destroy")):
        actions.add("delete")
    if _contains_any(lowered, ("move", "rename", "перемести", "перенеси", "переимен")):
        actions.add("move")
    if _contains_any(lowered, ("network", "download", "upload", "http://", "https://", "интернет", "скачай", "web request")):
        actions.add("network")
    if _contains_any(lowered, ("password", "credential", "secret", "token", "api key", "private key", "парол", "секрет", "ключ")):
        actions.add("credential")
    if _contains_any(lowered, ("disable safety", "отключить защит", "bypass approval", "обойти", "kill switch", "антивирус", "firewall")):
        actions.add("security_bypass")
    if _contains_any(lowered, ("admin", "administrator", "privilege", "elevat", "registry", "scheduled task", "startup", "service", "system32", "c:\\windows", "/etc/", "автозагруз", "служб")):
        actions.add("system_change")
    if not actions:
        actions.add("unknown")
    return sorted(actions)


def _has_dangerous_path(text: str) -> bool:
    return any(pattern.search(text) for pattern in _DANGEROUS_PATH_PATTERNS)


def _safe_required_files(text: str) -> list[str]:
    files: set[str] = set()
    for match in _SAFE_FILE_RE.finditer(text):
        candidate = match.group(1).replace("\\", "/").strip("./")
        if (
            candidate.startswith(_SAFE_FILE_PREFIXES)
            and ".." not in candidate.split("/")
            and ":" not in candidate
            and not candidate.startswith(("/", "~"))
        ):
            files.add(candidate)
    return sorted(files)[:20]


def classify_task_risk(request: dict) -> dict[str, Any]:
    normalized = str(request.get("normalized") or "")
    actions = [item for item in request.get("actions", []) if item in _INTENT_ORDER]
    if not actions:
        actions = _detect_actions(normalized)
    reasons: list[str] = []
    warnings: list[str] = []
    blocked = False
    level = "LOW"

    if any(action in _CRITICAL_ACTIONS for action in actions):
        level = "CRITICAL"
        blocked = True
        reasons.append("critical_safety_or_credential_request")
    elif any(action in _HIGH_ACTIONS for action in actions):
        level = "HIGH"
        reasons.append("high_risk_future_action")
    elif any(action in _MEDIUM_ACTIONS for action in actions):
        level = "MEDIUM"
        reasons.append("future_project_change_or_test")
    else:
        reasons.append("read_only_planning_or_analysis")

    if _has_dangerous_path(normalized):
        warnings.append("dangerous_path_text_redacted")
        reasons.append("dangerous_path_like_text")
        lower = normalized.lower().replace("ё", "е")
        if _contains_any(lower, ("system32", "c:\\windows", "/etc/", "~/.ssh", "id_rsa")):
            level = "CRITICAL"
            blocked = True

    if "unknown" in actions and len(actions) == 1:
        reasons.append("intent_requires_clarification")

    return {
        "level": level,
        "reasons": sorted(set(reasons)),
        "blocked": blocked,
        "warnings": sorted(set(warnings)),
    }


def _category(actions: list[str]) -> str:
    bounded = [action for action in actions if action in _INTENT_ORDER and action != "unknown"]
    if len(bounded) == 1:
        return bounded[0]
    if len(bounded) > 1:
        return "mixed"
    return "unknown"


def _capabilities(actions: list[str]) -> list[str]:
    caps: set[str] = set()
    if {"inspect", "explain", "analyze"} & set(actions):
        caps.update({"source_inspection", "static_analysis"})
    if "test" in actions:
        caps.add("test_execution")
    if "edit" in actions:
        caps.add("controlled_edit")
    if "create" in actions:
        caps.add("file_creation")
    if "network" in actions:
        caps.add("network_access")
    if "install" in actions:
        caps.add("package_management")
    if {"credential", "security_bypass", "system_change"} & set(actions):
        caps.add("security_review")
    if "explain" in actions:
        caps.add("documentation")
    if not caps:
        caps.add("unknown")
    return sorted(caps)


def _missing_information(actions: list[str], required_files: list[str]) -> list[str]:
    missing: list[str] = []
    if "unknown" in actions:
        missing.append("clarify requested outcome")
    if {"edit", "create", "test"} & set(actions) and not required_files:
        missing.append("explicit safe project target")
    return missing[:10]


def _step(step_id: int, title: str, description: str, action_type: str, read_only: bool, approval: bool, blocked: bool, depends_on: list[str], verification: str) -> dict[str, Any]:
    return {
        "id": f"step_{step_id:02d}",
        "title": title,
        "description": description,
        "action_type": action_type,
        "read_only": read_only,
        "requires_approval": approval,
        "blocked": blocked,
        "depends_on": depends_on,
        "verification": verification,
    }


def _steps(actions: list[str], risk: dict[str, Any]) -> list[dict[str, Any]]:
    result = [
        _step(1, "Inspect request", "Classify the task and identify safe context.", "inspect", True, False, False, [], "Intent and risk are documented."),
    ]
    if risk.get("blocked") is True:
        result.append(
            _step(2, "Stop blocked request", "Do not plan execution for blocked or unsafe content.", "stop", True, True, True, ["step_01"], "Blocked status is explicit.")
        )
        return result

    if any(action in actions for action in ("analyze", "inspect", "explain", "unknown")):
        result.append(
            _step(2, "Analyze safely", "Prepare a read-only explanation or inspection path.", "analyze", True, False, False, ["step_01"], "No write or execution step is included.")
        )
    next_id = len(result) + 1
    for action in ("test", "edit", "create", "execute"):
        if action in actions and len(result) < 11:
            result.append(
                _step(next_id, f"Plan {action}", f"Describe the future {action} action without performing it.", action, False, True, False, [result[-1]["id"]], "Approval is required before action.")
            )
            next_id += 1
    if len(result) < 12:
        result.append(
            _step(next_id, "Verify plan", "Confirm schema, approvals and safety constraints.", "verify", True, False, False, [result[-1]["id"]], "Plan remains deterministic and non-executing.")
        )
    return result[:12]


def build_task_plan(command: str) -> dict[str, Any]:
    parsed = parse_task_request(command)
    if not parsed.get("ok"):
        result = _base_schema(False)
        result["warnings"] = list(parsed.get("warnings", []))
        return result

    normalized = str(parsed["normalized"])
    actions = _detect_actions(normalized)
    parsed["actions"] = actions
    risk = classify_task_risk(parsed)
    required_files = _safe_required_files(normalized)
    approval_required = bool(set(actions) & _APPROVAL_ACTIONS or risk["level"] in {"HIGH", "CRITICAL"})
    preview = str(parsed["preview"])
    constraints = [
        "no execution in v6.82",
        "no filesystem writes",
        "approval required for future actions",
        "stay inside the project root",
        "respect Safety and protected paths",
    ]

    result = _base_schema(True)
    result["request"] = {
        "preview": preview,
        "sha256": str(parsed["sha256"]),
        "language": str(parsed["language"]),
        "normalized_length": int(parsed["normalized_length"]),
    }
    result["intent"] = {
        "category": _category(actions),
        "read_only": not bool(set(actions) & _APPROVAL_ACTIONS),
        "requested_actions": actions,
    }
    result["risk"] = {
        "level": str(risk["level"]),
        "reasons": list(risk["reasons"]),
        "blocked": bool(risk["blocked"]),
    }
    result["contract"] = {
        "goal": preview[:300],
        "inputs": ["task_request"],
        "constraints": constraints,
        "success_criteria": [
            "plan schema is complete",
            "risk and approval are explicit",
            "no execution is performed",
        ],
    }
    result["context"] = {
        "required_files": required_files,
        "required_capabilities": _capabilities(actions),
        "missing_information": _missing_information(actions, required_files),
    }
    result["steps"] = _steps(actions, risk)
    result["approval"] = {
        "required": approval_required,
        "reason": "future_action_requires_approval" if approval_required else "",
        "execution_allowed": False,
    }
    result["warnings"] = sorted(set(list(parsed.get("warnings", [])) + list(risk.get("warnings", []))))
    return result


def dispatch(command: str) -> dict[str, Any]:
    if not is_task_plan_command(command):
        result = _base_schema(False)
        result["warnings"] = ["unknown_task_plan_command"]
        return result
    return build_task_plan(command)
````

### ПУТЬ: modules/true_auto_relay.py (695 строк, 23058 байт)

````python
import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value, get_value
from modules import gpt_browser_bridge


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports"
RESPONSE_GLOB = "response*.json"


def _short(text, limit: int = 1800):
    value = str(text or "")

    if len(value) <= limit:
        return value

    return value[:limit] + "\n...[обрезано]"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _cycle_id():
    return "auto_" + _stamp()


def _new_report_path():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR / f"true_auto_relay_{_stamp()}.md"


def _new_screenshot_path():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR / f"true_auto_relay_error_{_stamp()}.png"


def _downloads_dir():
    downloads_dir = getattr(gpt_browser_bridge, "DOWNLOADS_DIR")
    downloads_dir.mkdir(parents=True, exist_ok=True)
    return downloads_dir


def _archive_old_downloads(cycle_id: str):
    downloads_dir = _downloads_dir()
    archive_dir = downloads_dir / "Archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    moved = []

    for path in sorted(downloads_dir.glob(RESPONSE_GLOB)):
        if not path.is_file():
            continue

        target = archive_dir / f"{cycle_id}_{path.stat().st_mtime_ns}_{path.name}"

        try:
            shutil.move(str(path), str(target))
            moved.append(f"{path.name} -> {target.name}")
        except Exception as e:
            moved.append(f"НЕ ПЕРЕНЕСЕН: {path.name} -> {e}")

    set_value("last_true_auto_archived_downloads", "\n".join(moved))
    return moved


def _save_report(lines, report_path):
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(str(line) for line in lines), encoding="utf-8")
    set_value("last_true_auto_relay_report", str(report_path))
    return report_path


def _save_screenshot():
    screenshot_path = _new_screenshot_path()

    try:
        page = gpt_browser_bridge._get_page()
        page.screenshot(path=str(screenshot_path), full_page=True)
        set_value("last_true_auto_relay_screenshot", str(screenshot_path))
        return str(screenshot_path)
    except Exception as e:
        set_value("last_true_auto_relay_screenshot_error", str(e))
        return ""


def _stop(lines, report_path, message, make_screenshot=True):
    set_value("last_true_auto_patch_status", "stopped")
    lines.append("")
    lines.append(message)

    if make_screenshot:
        screenshot = _save_screenshot()

        if screenshot:
            lines.append(f"Screenshot: {screenshot}")
        else:
            lines.append("Screenshot: не удалось сделать screenshot текущей страницы.")

    saved = _save_report(lines, report_path)
    lines.append(f"Log: {saved}")
    return "\n".join(lines)


def _patch_is_valid(data):
    return (
        isinstance(data, dict)
        and isinstance(data.get("summary"), str)
        and isinstance(data.get("operations"), list)
        and len(data.get("operations", [])) > 0
        and isinstance(data.get("tests"), list)
    )


def _patch_cycle_id(data):
    if not isinstance(data, dict):
        return ""

    meta = data.get("meta")

    if isinstance(meta, dict):
        return str(meta.get("cycle_id", "") or "").strip()

    return ""


def _read_patch(path: Path, expected_cycle_id: str = ""):
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    data = json.loads(raw)

    if not _patch_is_valid(data):
        raise ValueError("JSON есть, но это не рабочий patch: нужны summary, operations > 0, tests.")

    expected_cycle_id = str(expected_cycle_id or "").strip()

    if expected_cycle_id:
        actual_cycle_id = _patch_cycle_id(data)

        if actual_cycle_id != expected_cycle_id:
            raise ValueError(
                "response freshness guard: meta.cycle_id не совпадает. "
                f"expected={expected_cycle_id}; actual={actual_cycle_id or 'нет'}"
            )

    return data


def _latest_valid_response_file(since_epoch: float = 0, expected_cycle_id: str = ""):
    downloads_dir = _downloads_dir()

    candidates = sorted(
        [path for path in downloads_dir.glob(RESPONSE_GLOB) if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for path in candidates:
        if since_epoch and path.stat().st_mtime < since_epoch:
            continue

        try:
            _read_patch(path, expected_cycle_id=expected_cycle_id)
            return path
        except Exception as e:
            set_value("last_true_auto_rejected_response", f"{path}: {e}")
            continue

    return None


def _safe_filename(name: str):
    value = str(name or "").strip().replace("\\", "_").replace("/", "_")

    if not value:
        value = f"response_artifact_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    if not value.lower().endswith(".json"):
        value += ".json"

    if not value.lower().startswith("response"):
        value = "response_" + value

    return value


def _assistant_scopes(page):
    scopes = []

    for selector in [
        "[data-message-author-role='assistant']",
        "article",
    ]:
        try:
            locator = page.locator(selector)
            count = locator.count()

            if count:
                scopes.append(locator.nth(count - 1))
        except Exception:
            continue

    scopes.append(page)
    return scopes


def _try_download_from_page(page, timeout_ms: int = 12000, expected_cycle_id: str = ""):
    downloads_dir = _downloads_dir()

    selectors = [
        "a[download]",
        "a[href*='download']",
        "a[href*='response']",
        "button[data-testid*='download']",
        "[data-testid*='download']",
        "button:has-text('Download')",
        "button:has-text('Скачать')",
        "a:has-text('response.json')",
        "button:has-text('response.json')",
        "text=response.json",
    ]

    errors = []

    for scope in _assistant_scopes(page):
        for selector in selectors:
            try:
                locator = scope.locator(selector)
                count = min(locator.count(), 8)

                for index in range(count):
                    item = locator.nth(index)

                    try:
                        with page.expect_download(timeout=timeout_ms) as download_info:
                            item.click(timeout=5000)

                        download = download_info.value
                        suggested = _safe_filename(download.suggested_filename)
                        target = downloads_dir / suggested
                        download.save_as(str(target))

                        try:
                            data = _read_patch(target, expected_cycle_id=expected_cycle_id)
                        except Exception as e:
                            errors.append(f"{selector}[{index}]: скачан невалидный/устаревший файл {target.name}: {e}")
                            continue

                        set_value("last_true_auto_downloaded_response", str(target))
                        set_value("last_true_auto_downloaded_cycle_id", _patch_cycle_id(data))
                        return target

                    except Exception as e:
                        errors.append(f"{selector}[{index}]: {e}")
                        continue

            except Exception as e:
                errors.append(f"{selector}: {e}")
                continue

    set_value("last_true_auto_download_errors", "\n".join(errors[-20:]))
    return None


def download_latest_response_artifact(timeout_sec: int = 900, expected_cycle_id: str = ""):
    """Try to download or locate the newest valid response*.json artifact from ChatGPT.

    Returns a human-readable result with OK/STOP prefix and saves the found path in state.
    """
    started = time.time()
    timeout_sec = max(10, int(timeout_sec or 900))
    expected_cycle_id = str(expected_cycle_id or "").strip()

    try:
        downloads_dir = _downloads_dir()

        before_existing = _latest_valid_response_file(
            since_epoch=started - 2,
            expected_cycle_id=expected_cycle_id,
        )

        if before_existing:
            data = _read_patch(before_existing, expected_cycle_id=expected_cycle_id)
            actual_cycle_id = _patch_cycle_id(data)
            set_value("last_true_auto_downloaded_response", str(before_existing))
            return (
                "OK: найден свежий response*.json в Downloads.\n"
                f"Файл: {before_existing}\n"
                f"expected cycle_id: {expected_cycle_id or 'не задан'}\n"
                f"actual cycle_id: {actual_cycle_id or 'нет'}"
            )

        page = gpt_browser_bridge._get_page()

        clicked = _try_download_from_page(
            page,
            expected_cycle_id=expected_cycle_id,
        )

        if clicked:
            data = _read_patch(clicked, expected_cycle_id=expected_cycle_id)
            actual_cycle_id = _patch_cycle_id(data)
            return (
                "OK: response artifact скачан из ChatGPT.\n"
                f"Файл: {clicked}\n"
                f"expected cycle_id: {expected_cycle_id or 'не задан'}\n"
                f"actual cycle_id: {actual_cycle_id or 'нет'}"
            )

        while time.time() - started < timeout_sec:
            found = _latest_valid_response_file(
                since_epoch=started - 2,
                expected_cycle_id=expected_cycle_id,
            )

            if found:
                data = _read_patch(found, expected_cycle_id=expected_cycle_id)
                actual_cycle_id = _patch_cycle_id(data)
                set_value("last_true_auto_downloaded_response", str(found))
                return (
                    "OK: найден скачанный response*.json.\n"
                    f"Файл: {found}\n"
                    f"expected cycle_id: {expected_cycle_id or 'не задан'}\n"
                    f"actual cycle_id: {actual_cycle_id or 'нет'}"
                )

            time.sleep(2)

        return (
            "STOP: не удалось скачать или найти свежий response*.json с нужным cycle_id.\n"
            f"Папка Downloads: {downloads_dir}\n"
            f"expected cycle_id: {expected_cycle_id or 'не задан'}\n"
            "Дальше: проверь, создал ли ChatGPT новый файл именно для текущего auto-cycle."
        )

    except Exception as e:
        set_value("last_true_auto_download_error", str(e))
        return f"STOP: ошибка download_latest_response_artifact.\nОшибка: {e}"


def _extract_ok_path(result: str):
    text = str(result or "")

    if not text.lstrip().startswith("OK:"):
        return None

    for line in text.splitlines():
        clean = line.strip()

        if clean.lower().startswith("файл:"):
            return Path(clean.split(":", 1)[1].strip())

    return None


def import_response_file(path: Path, expected_cycle_id: str = ""):
    path = Path(path)

    if not path.exists() or not path.is_file():
        return f"STOP: response file не найден:\n{path}"

    try:
        data = _read_patch(path, expected_cycle_id=expected_cycle_id)
    except Exception as e:
        return f"STOP: response file не прошел JSON patch/freshness проверку.\nФайл: {path}\nОшибка: {e}"

    response_path = getattr(gpt_browser_bridge, "RESPONSE_PATH")
    response_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, response_path)

    actual_cycle_id = _patch_cycle_id(data)
    set_value("last_true_auto_imported_response", str(response_path))
    set_value("last_true_auto_imported_cycle_id", actual_cycle_id)

    return (
        "OK: response импортирован в Relay.\n"
        f"Источник: {path}\n"
        f"Цель: {response_path}\n"
        f"Summary: {data.get('summary')}\n"
        f"Операций: {len(data.get('operations', []))}\n"
        f"expected cycle_id: {expected_cycle_id or 'не задан'}\n"
        f"actual cycle_id: {actual_cycle_id or 'нет'}"
    )


def _ok(text):
    return str(text or "").lstrip().startswith("OK:")


def _generic_ok(text):
    lower = str(text or "").lower()

    bad = [
        "stop:",
        "ошибка",
        "не удалось",
        "traceback",
        "failed",
        "unknown",
        "неизвестное действие",
    ]

    return bool(str(text or "").strip()) and not any(marker in lower for marker in bad)


def _validate_ok(text):
    lower = str(text or "").lower()

    bad = [
        "stop:",
        "ошибка",
        "не удалось",
        "отклонен",
        "не пройд",
        "пустой",
        "применять нечего",
        "нет списка operations",
        "не найден",
    ]

    return (
        ("✅" in str(text) or "проверка пройдена" in lower)
        and not any(marker in lower for marker in bad)
    )


def _apply_ok(text):
    lower = str(text or "").lower()

    bad = [
        "patch не применен",
        "не применен",
        "ошибка",
        "не удалось",
        "stop:",
        "failed",
    ]

    return (
        ("patch успешно применен" in lower or "успешно применен" in lower)
        and not any(marker in lower for marker in bad)
    )


def _run_step_with_retry(lines, report_path, step_no, total_steps, title, func, checker=_generic_ok, retries=2):
    attempts = max(1, int(retries or 0) + 1)
    last_result = ""

    for attempt in range(1, attempts + 1):
        lines.append("")
        lines.append(f"STEP {step_no}/{total_steps} TRY {attempt}/{attempts}: {title}")

        try:
            result = func()
        except Exception as e:
            result = f"STOP: exception in {title}: {e}"

        last_result = str(result)
        lines.append(last_result)

        if checker(last_result):
            if attempt > 1:
                lines.append(f"STEP {step_no}/{total_steps} RECOVERED: {title}")
            lines.append(f"STEP {step_no}/{total_steps} OK: {title}")
            _save_report(lines, report_path)
            return True, last_result

        if attempt < attempts:
            lines.append(f"STEP {step_no}/{total_steps} retry через 2 сек: {title}")
            _save_report(lines, report_path)
            time.sleep(2)

    lines.append(f"STEP {step_no}/{total_steps} STOP: {title}")
    _save_report(lines, report_path)
    return False, last_result


def _download_and_import(expected_cycle_id: str = ""):
    from agents import gpt_browser_agent

    download_result = download_latest_response_artifact(
        timeout_sec=45,
        expected_cycle_id=expected_cycle_id,
    )

    if _ok(download_result):
        path = _extract_ok_path(download_result)

        if path:
            import_result = import_response_file(path, expected_cycle_id=expected_cycle_id)

            if _ok(import_result):
                return download_result + "\n\n" + import_result

            return download_result + "\n\n" + import_result

    save_result = gpt_browser_agent.handle("save_response", {})
    save_lower = str(save_result).lower()

    if "response.json сохранен" in save_lower or "response.json импортирован" in save_lower:
        response_path = getattr(gpt_browser_bridge, "RESPONSE_PATH")

        try:
            data = _read_patch(response_path, expected_cycle_id=expected_cycle_id)
            actual_cycle_id = _patch_cycle_id(data)
            return (
                "OK: fallback save_response сработал и прошел freshness guard.\n"
                + str(save_result)
                + f"\nexpected cycle_id: {expected_cycle_id or 'не задан'}"
                + f"\nactual cycle_id: {actual_cycle_id or 'нет'}"
            )
        except Exception as e:
            return (
                str(save_result)
                + "\n\nSTOP: fallback save_response получил response.json, но freshness guard не прошел.\n"
                + f"expected cycle_id: {expected_cycle_id or 'не задан'}\n"
                + f"Ошибка: {e}"
            )

    return (
        str(download_result)
        + "\n\n--- FALLBACK SAVE_RESPONSE ---\n"
        + str(save_result)
        + "\n\nSTOP: не удалось получить рабочий свежий response.json."
    )


def true_auto_relay_cycle(goal: str = "", timeout_sec: int = 900):
    """Full automatic safe Relay cycle with retries, report and screenshot on STOP."""
    from agents import automation_agent
    from agents import chatgpt_relay_agent
    from agents import gpt_browser_agent

    goal = str(goal or "").strip()
    timeout_sec = max(60, int(timeout_sec or 900))
    total_steps = 10
    report_path = _new_report_path()
    cycle_id = _cycle_id()

    lines = [
        "# TRUE AUTO RELAY CYCLE",
        "",
        f"- started: {datetime.now().isoformat(timespec='seconds')}",
        f"- timeout_sec: {timeout_sec}",
        f"- cycle_id: {cycle_id}",
        f"- goal: {goal}",
        "",
    ]

    set_value("last_true_auto_cycle_id", cycle_id)
    set_value("last_true_auto_relay_report", str(report_path))
    set_value("last_true_auto_relay_screenshot", "")
    set_value("last_true_auto_patch_status", "running")

    if not goal:
        return _stop(
            lines,
            report_path,
            "STEP 1/10 STOP: dev task пустой. Введи задачу в поле Dev task.",
            make_screenshot=False,
        )

    set_value("last_true_auto_relay_goal", goal)
    _save_report(lines, report_path)

    archived = _archive_old_downloads(cycle_id)
    lines.append("Response Freshness Guard: включен.")
    lines.append(f"Expected cycle_id: {cycle_id}")
    lines.append(
        "Archived old Downloads response*.json: "
        + (str(len(archived)) if archived else "0")
    )
    _save_report(lines, report_path)

    try:
        gpt_browser_bridge.reset_bridge_state("true_auto_relay_start")
        lines.append("GPT Browser Bridge reset before auto-cycle: OK")
        _save_report(lines, report_path)
    except Exception as e:
        lines.append(f"GPT Browser Bridge reset before auto-cycle: failed but ignored: {e}")
        _save_report(lines, report_path)

    ok, dev_result = _run_step_with_retry(
        lines,
        report_path,
        1,
        total_steps,
        "создать request.md через dev task",
        lambda: automation_agent.handle("dev_task", {"goal": goal}),
        checker=lambda r: (
            ("request.md" in str(r) or "Relay-запрос создан" in str(r))
            and _generic_ok(r)
        ),
        retries=0,
    )

    if not ok:
        return _stop(lines, report_path, "STEP 1/10 STOP: dev task не создал request.md.")

    retry_steps = [
        (2, "открыть ChatGPT", lambda: gpt_browser_agent.handle("open", {})),
        (3, "вставить request.md", lambda: gpt_browser_agent.handle("paste_request", {})),
        (4, "отправить request", lambda: gpt_browser_agent.handle("send", {})),
        (5, "дождаться ответа ChatGPT", lambda: gpt_browser_agent.handle("wait", {"timeout_sec": timeout_sec})),
        (6, f"скачать/импортировать response*.json для cycle_id {cycle_id}", lambda: _download_and_import(cycle_id)),
    ]

    for step_no, title, func in retry_steps:
        ok, result = _run_step_with_retry(
            lines,
            report_path,
            step_no,
            total_steps,
            title,
            func,
            checker=_generic_ok if step_no != 6 else _ok,
            retries=2,
        )

        if not ok:
            return _stop(lines, report_path, f"STEP {step_no}/{total_steps} STOP: {title}. Patch не применен.")

    ok, validate_result = _run_step_with_retry(
        lines,
        report_path,
        7,
        total_steps,
        "relay validate",
        lambda: chatgpt_relay_agent.handle("validate_response", {}),
        checker=_validate_ok,
        retries=0,
    )

    if not ok:
        return _stop(
            lines,
            report_path,
            "STEP 7/10 STOP: relay validate не прошел. GPT Browser не закрыт, patch не применен.",
        )

    ok, close_result = _run_step_with_retry(
        lines,
        report_path,
        8,
        total_steps,
        "закрыть GPT Browser",
        lambda: gpt_browser_agent.handle("close", {}),
        checker=_generic_ok,
        retries=0,
    )

    if not ok:
        return _stop(lines, report_path, "STEP 8/10 STOP: GPT Browser не закрыт. Patch не применен.")

    ok, apply_result = _run_step_with_retry(
        lines,
        report_path,
        9,
        total_steps,
        "применить response patch",
        lambda: chatgpt_relay_agent.handle("apply_response", {}),
        checker=_apply_ok,
        retries=0,
    )

    if not ok:
        return _stop(lines, report_path, "STEP 9/10 STOP: apply не прошел. after patch не запущен.")

    ok, after_result = _run_step_with_retry(
        lines,
        report_path,
        10,
        total_steps,
        "after patch",
        lambda: automation_agent.handle("after_patch", {}),
        checker=_generic_ok,
        retries=0,
    )

    if not ok:
        return _stop(lines, report_path, "STEP 10/10 STOP: after patch завершился ошибкой.")

    lines.append("")
    lines.append("OK: TRUE AUTO RELAY CYCLE завершен.")
    lines.append(f"Log: {report_path}")

    _save_report(lines, report_path)
    set_value("last_true_auto_relay_result", _short("\n".join(lines), 4000))

    return "\n".join(lines)
````

### ПУТЬ: modules/voice.py (0 строк, 0 байт)

````python

````

### ПУТЬ: modules/voice_control.py (694 строк, 24404 байт)

````python
from datetime import datetime
import json
import os
from pathlib import Path
from modules.project_paths import get_project_root
import queue
import subprocess
import tempfile
import time
import wave

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "voice_sessions"
VOICE_MODELS_DIR = ROOT_DIR / "Projects" / "VoiceModels"
DEFAULT_VOSK_MODEL_DIR = VOICE_MODELS_DIR / "vosk-model-small-ru-0.22"
DEFAULT_WHISPER_MODEL_SIZE = "medium"
DEFAULT_PIPER_EXE = Path.home() / "Documents" / "piper" / "piper.exe"
DEFAULT_PIPER_VOICE = Path.home() / "Documents" / "piper" / "ru_RU-dmitri-medium.onnx"

VOICE_DEPENDENCY_HINT = (
    "Voice dependencies are not installed. Install SpeechRecognition and PyAudio "
    "for microphone input, and pyttsx3 for local TTS."
)

_LISTENING = False
_MUTED = bool(get_value("voice_tts_muted", False))
_WHISPER_MODEL = None


DANGEROUS_TERMS = [
    "оплатить",
    "оплати",
    "купить",
    "купи",
    "оформить заказ",
    "добавить в корзину",
    "корзина",
    "заказ",
    "ставка",
    "поставить ставку",
    "казино",
    "банк",
    "кредит",
    "пароль",
    "логин",
    "войти",
    "зарегистрироваться",
    "2fa",
    "смс",
    "sms",
    "удалить аккаунт",
    "закрыть аккаунт",
    "отправь деньги",
    "переведи деньги",
    "kaspi",
    "банковская карта",
    "pay",
    "buy",
    "order",
    "checkout",
    "cart",
    "bet",
    "casino",
    "bank",
    "password",
    "login",
    "sign in",
    "sign up",
    "delete account",
    "close account",
    "send money",
    "transfer money",
    "credit card",
]


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _import_ok(module_name):
    try:
        __import__(module_name)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _windows_sapi_available():
    try:
        import win32com.client  # noqa: F401

        return True, ""
    except Exception as exc:
        return False, str(exc)


def _windows_sapi_recognition_available():
    try:
        import win32com.client

        win32com.client.Dispatch("SAPI.SpSharedRecognizer")
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _find_vosk_model():
    configured = str(get_value("voice_vosk_model_path", "") or "").strip()

    candidates = []

    if configured:
        candidates.append(Path(configured))

    candidates.append(DEFAULT_VOSK_MODEL_DIR)

    if VOICE_MODELS_DIR.exists():
        candidates.extend(sorted(VOICE_MODELS_DIR.glob("vosk-model*ru*")))
        candidates.extend(sorted(VOICE_MODELS_DIR.glob("*ru*")))

    for path in candidates:
        if path.exists() and path.is_dir() and (path / "conf").exists():
            return path

    return None


def _piper_paths():
    exe = Path(str(get_value("voice_piper_exe", str(DEFAULT_PIPER_EXE)) or DEFAULT_PIPER_EXE))
    voice = Path(str(get_value("voice_piper_voice", str(DEFAULT_PIPER_VOICE)) or DEFAULT_PIPER_VOICE))
    return exe, voice


def _piper_available():
    exe, voice = _piper_paths()
    return bool(exe.exists() and voice.exists()), exe, voice


def check_voice_dependencies():
    faster_whisper_ok, faster_whisper_error = _import_ok("faster_whisper")
    numpy_ok, numpy_error = _import_ok("numpy")
    speech_ok, speech_error = _import_ok("speech_recognition")
    sphinx_ok, sphinx_error = _import_ok("pocketsphinx")
    vosk_ok, vosk_error = _import_ok("vosk")
    sounddevice_ok, sounddevice_error = _import_ok("sounddevice")
    tts_ok, tts_error = _import_ok("pyttsx3")
    pyaudio_ok, pyaudio_error = _import_ok("pyaudio")
    sapi_ok, sapi_error = _windows_sapi_available()
    sapi_stt_ok, sapi_stt_error = _windows_sapi_recognition_available()
    vosk_model = _find_vosk_model()
    vosk_usable = bool(vosk_ok and sounddevice_ok and vosk_model)
    piper_ok, piper_exe, piper_voice = _piper_available()
    faster_whisper_usable = bool(faster_whisper_ok and sounddevice_ok and numpy_ok)

    messages = []

    if not faster_whisper_ok:
        messages.append(f"faster-whisper unavailable: {faster_whisper_error}")

    if not numpy_ok:
        messages.append(f"numpy unavailable: {numpy_error}")

    if not vosk_ok:
        messages.append(f"Vosk unavailable: {vosk_error}")

    if not sounddevice_ok:
        messages.append(f"sounddevice unavailable: {sounddevice_error}")

    if vosk_ok and sounddevice_ok and not vosk_model:
        messages.append(
            "Russian Vosk model not found. Put a Vosk Russian model folder into "
            f"{VOICE_MODELS_DIR}, for example vosk-model-small-ru-0.22."
        )

    if not speech_ok:
        messages.append(f"SpeechRecognition unavailable: {speech_error}")

    if not pyaudio_ok:
        messages.append(f"PyAudio unavailable: {pyaudio_error}")

    if not tts_ok and not sapi_ok:
        messages.append(f"TTS unavailable: pyttsx3={tts_error}; Windows SAPI={sapi_error}")

    if not piper_ok:
        messages.append(f"Piper TTS unavailable: exe={piper_exe.exists()} voice={piper_voice.exists()}")

    if speech_ok and pyaudio_ok and not sphinx_ok:
        messages.append(f"Offline Sphinx STT unavailable: {sphinx_error}")

    if sapi_stt_ok and not vosk_usable and (not speech_ok or not pyaudio_ok or not sphinx_ok):
        messages.append("Windows SAPI speech recognition fallback is available for Push to talk.")

    if not sapi_stt_ok and (not speech_ok or not pyaudio_ok):
        messages.append(VOICE_DEPENDENCY_HINT)

    if sapi_ok and not sapi_stt_ok:
        messages.append(f"Windows SAPI recognition unavailable: {sapi_stt_error}")

    return {
        "speech_recognition_available": speech_ok,
        "pocketsphinx_available": sphinx_ok,
        "faster_whisper_available": faster_whisper_ok,
        "numpy_available": numpy_ok,
        "usable_faster_whisper_ru": faster_whisper_usable,
        "faster_whisper_model_size": str(get_value("voice_whisper_model_size", DEFAULT_WHISPER_MODEL_SIZE) or DEFAULT_WHISPER_MODEL_SIZE),
        "vosk_available": vosk_ok,
        "sounddevice_available": sounddevice_ok,
        "vosk_model_path": str(vosk_model) if vosk_model else "",
        "usable_vosk_ru": vosk_usable,
        "piper_available": piper_ok,
        "piper_exe": str(piper_exe),
        "piper_voice": str(piper_voice),
        "pyttsx3_available": tts_ok,
        "pyaudio_available": pyaudio_ok,
        "windows_sapi_available": sapi_ok,
        "windows_sapi_stt_available": sapi_stt_ok,
        "usable_stt": bool(faster_whisper_usable or vosk_usable or (speech_ok and pyaudio_ok and sphinx_ok) or sapi_stt_ok),
        "usable_tts": bool(piper_ok or tts_ok or sapi_ok),
        "messages": messages,
    }


def get_voice_status():
    deps = check_voice_dependencies()
    return {
        "enabled": bool(deps.get("usable_stt") or deps.get("usable_tts")),
        "listening": _LISTENING,
        "muted": bool(get_value("voice_tts_muted", _MUTED)),
        "stt_engine": (
            "Faster-Whisper Russian offline"
            if deps.get("usable_faster_whisper_ru")
            else (
                "Vosk Russian offline"
                if deps.get("usable_vosk_ru")
                else (
                    "SpeechRecognition + PyAudio + PocketSphinx"
                    if deps.get("speech_recognition_available") and deps.get("pyaudio_available") and deps.get("pocketsphinx_available")
                    else ("Windows SAPI" if deps.get("windows_sapi_stt_available") else "unavailable")
                )
            )
        ),
        "tts_engine": (
            "Piper ru_RU dmitri medium"
            if deps.get("piper_available")
            else ("pyttsx3" if deps.get("pyttsx3_available") else ("Windows SAPI" if deps.get("windows_sapi_available") else "unavailable"))
        ),
        "last_transcript": get_value("last_voice_transcript", ""),
        "last_error": get_value("last_voice_error", ""),
        "last_report": get_value("last_voice_session_report", ""),
        "dependencies": deps,
    }


def transcribe_once(timeout=5, phrase_time_limit=10, language="ru-RU"):
    global _LISTENING

    deps = check_voice_dependencies()

    if not deps.get("usable_stt"):
        message = (
            VOICE_DEPENDENCY_HINT
            + " Offline STT also needs pocketsphinx. Audio was not sent to external services."
        )
        set_value("last_voice_error", message)
        return {"ok": False, "text": "", "error": message, "engine": "unavailable"}

    if deps.get("usable_faster_whisper_ru"):
        return _transcribe_once_faster_whisper(timeout=timeout, phrase_time_limit=phrase_time_limit)

    if deps.get("usable_vosk_ru"):
        return _transcribe_once_vosk(timeout=timeout, phrase_time_limit=phrase_time_limit)

    if deps.get("windows_sapi_stt_available") and not (
        deps.get("speech_recognition_available") and deps.get("pyaudio_available") and deps.get("pocketsphinx_available")
    ):
        return _transcribe_once_windows_sapi(timeout=timeout, phrase_time_limit=phrase_time_limit)

    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        _LISTENING = True

        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)

        text = recognizer.recognize_sphinx(audio, language=language)
        set_value("last_voice_transcript", text)
        set_value("last_voice_error", "")
        return {"ok": True, "text": text, "error": None, "engine": "SpeechRecognition/PocketSphinx"}
    except Exception as exc:
        message = f"Voice recognition failed: {exc}"
        set_value("last_voice_error", message)
        return {"ok": False, "text": "", "error": message, "engine": "SpeechRecognition"}
    finally:
        _LISTENING = False


def _get_whisper_model():
    global _WHISPER_MODEL

    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel

        model_size = str(get_value("voice_whisper_model_size", DEFAULT_WHISPER_MODEL_SIZE) or DEFAULT_WHISPER_MODEL_SIZE)
        _WHISPER_MODEL = WhisperModel(model_size, device="cpu", compute_type="int8")

    return _WHISPER_MODEL


def _transcribe_once_faster_whisper(timeout=5, phrase_time_limit=10, samplerate=16000):
    global _LISTENING

    try:
        import numpy as np
        import sounddevice as sd

        seconds = max(1, int(phrase_time_limit or timeout or 7))
        _LISTENING = True
        audio = sd.rec(
            int(seconds * samplerate),
            samplerate=samplerate,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        _LISTENING = False
        audio = audio.flatten()
        rms_level = float(np.sqrt(np.mean(audio ** 2))) if audio.size else 0.0

        if rms_level < 0.001:
            message = (
                "Microphone signal is almost silent. Check the selected Windows input device "
                "and microphone volume."
            )
            set_value("last_voice_error", message)
            return {"ok": False, "text": "", "error": message, "engine": "Faster-Whisper Russian offline"}

        model = _get_whisper_model()
        segments, _info = model.transcribe(
            audio,
            language="ru",
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300),
            condition_on_previous_text=False,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()

        if text:
            set_value("last_voice_transcript", text)
            set_value("last_voice_error", "")
            return {"ok": True, "text": text, "error": None, "engine": "Faster-Whisper Russian offline"}

        message = f"No Russian speech recognized by Faster-Whisper. Microphone rms={rms_level:.4f}."
        set_value("last_voice_error", message)
        return {"ok": False, "text": "", "error": message, "engine": "Faster-Whisper Russian offline"}
    except Exception as exc:
        message = f"Faster-Whisper recognition failed: {exc}"
        set_value("last_voice_error", message)
        return {"ok": False, "text": "", "error": message, "engine": "Faster-Whisper Russian offline"}
    finally:
        _LISTENING = False


def _transcribe_once_vosk(timeout=5, phrase_time_limit=10, samplerate=16000):
    global _LISTENING

    try:
        import sounddevice as sd
        from vosk import KaldiRecognizer, Model

        model_path = _find_vosk_model()

        if not model_path:
            message = (
                "Russian Vosk model not found. Put a Vosk Russian model folder into "
                f"{VOICE_MODELS_DIR}, for example vosk-model-small-ru-0.22."
            )
            set_value("last_voice_error", message)
            return {"ok": False, "text": "", "error": message, "engine": "Vosk Russian offline"}

        audio_queue = queue.Queue()
        recognizer = KaldiRecognizer(Model(str(model_path)), int(samplerate))

        def callback(indata, frames, time_info, status):
            if status:
                set_value("last_voice_error", str(status))
            audio_queue.put(bytes(indata))

        _LISTENING = True
        deadline = time.monotonic() + max(1, int(timeout or 5)) + max(1, int(phrase_time_limit or 10))

        with sd.RawInputStream(
            samplerate=int(samplerate),
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=callback,
        ):
            while _LISTENING and time.monotonic() < deadline:
                try:
                    data = audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    payload = json.loads(recognizer.Result() or "{}")
                    text = str(payload.get("text", "") or "").strip()

                    if text:
                        set_value("last_voice_transcript", text)
                        set_value("last_voice_error", "")
                        return {"ok": True, "text": text, "error": None, "engine": "Vosk Russian offline"}

        payload = json.loads(recognizer.FinalResult() or "{}")
        text = str(payload.get("text", "") or "").strip()

        if text:
            set_value("last_voice_transcript", text)
            set_value("last_voice_error", "")
            return {"ok": True, "text": text, "error": None, "engine": "Vosk Russian offline"}

        message = "No Russian speech recognized by Vosk. Check microphone input and speak closer to the mic."
        set_value("last_voice_error", message)
        return {"ok": False, "text": "", "error": message, "engine": "Vosk Russian offline"}
    except Exception as exc:
        message = f"Vosk recognition failed: {exc}"
        set_value("last_voice_error", message)
        return {"ok": False, "text": "", "error": message, "engine": "Vosk Russian offline"}
    finally:
        _LISTENING = False


def _transcribe_once_windows_sapi(timeout=5, phrase_time_limit=10):
    global _LISTENING

    try:
        import pythoncom
        import win32com.client

        class RecognitionEvents:
            text = ""
            error = ""

            def OnRecognition(self, stream_number, stream_position, recognition_type, result):
                try:
                    self.text = result.PhraseInfo.GetText()
                except Exception as exc:
                    self.error = str(exc)

        def listen_with_context(context_factory):
            context_raw = context_factory()
            context = win32com.client.WithEvents(context_raw, RecognitionEvents)
            grammar = context_raw.CreateGrammar()
            grammar.DictationSetState(1)

            try:
                deadline = time.monotonic() + max(1, int(timeout or 5)) + max(1, int(phrase_time_limit or 10))

                while _LISTENING and time.monotonic() < deadline and not getattr(context, "text", ""):
                    pythoncom.PumpWaitingMessages()
                    time.sleep(0.05)

                text = str(getattr(context, "text", "") or "").strip()
                error = str(getattr(context, "error", "") or "").strip()
                return text, error
            finally:
                try:
                    grammar.DictationSetState(0)
                except Exception:
                    pass

        pythoncom.CoInitialize()
        _LISTENING = True

        try:
            try:
                text, error = listen_with_context(lambda: win32com.client.Dispatch("SAPI.SpSharedRecoContext"))
                engine = "Windows SAPI Shared"
            except Exception as shared_exc:
                recognizer = win32com.client.Dispatch("SAPI.SpInprocRecognizer")
                text, error = listen_with_context(recognizer.CreateRecoContext)
                engine = f"Windows SAPI InProc after shared failed: {shared_exc}"

            if text:
                set_value("last_voice_transcript", text)
                set_value("last_voice_error", "")
                return {"ok": True, "text": text, "error": None, "engine": engine}

            message = error or "No speech recognized by Windows SAPI. Check microphone and Windows speech language settings."
            set_value("last_voice_error", message)
            return {"ok": False, "text": "", "error": message, "engine": engine}
        finally:
            _LISTENING = False
            pythoncom.CoUninitialize()
    except Exception as exc:
        message = f"Windows SAPI recognition failed: {exc}"
        set_value("last_voice_error", message)
        _LISTENING = False
        return {"ok": False, "text": "", "error": message, "engine": "Windows SAPI"}


def stop_listening():
    global _LISTENING
    _LISTENING = False

    try:
        import sounddevice as sd

        sd.stop()
    except Exception:
        pass

    return {"ok": True, "listening": False}


def speak_text(text, enabled=True):
    if not enabled or bool(get_value("voice_tts_muted", False)):
        return {"ok": False, "error": "TTS is muted.", "engine": "muted"}

    value = str(text or "").strip()

    if not value:
        return {"ok": False, "error": "Nothing to speak.", "engine": "none"}

    deps = check_voice_dependencies()

    if deps.get("piper_available"):
        exe, voice = _piper_paths()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = tmp.name

        try:
            import numpy as np
            import sounddevice as sd

            subprocess.run(
                [str(exe), "--model", str(voice), "--output_file", out_path],
                input=value[:1200].encode("utf-8"),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            with wave.open(out_path, "rb") as wf:
                audio_data = wf.readframes(wf.getnframes())
                audio_np = np.frombuffer(audio_data, dtype=np.int16)
                sd.play(audio_np, samplerate=wf.getframerate())
                sd.wait()

            return {"ok": True, "error": None, "engine": "Piper ru_RU dmitri medium"}
        except Exception as exc:
            set_value("last_voice_error", str(exc))
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

    if deps.get("pyttsx3_available"):
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.say(value[:1200])
            engine.runAndWait()
            return {"ok": True, "error": None, "engine": "pyttsx3"}
        except Exception as exc:
            set_value("last_voice_error", str(exc))

    if deps.get("windows_sapi_available"):
        try:
            import win32com.client

            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak(value[:1200])
            return {"ok": True, "error": None, "engine": "Windows SAPI"}
        except Exception as exc:
            set_value("last_voice_error", str(exc))
            return {"ok": False, "error": f"TTS failed: {exc}", "engine": "Windows SAPI"}

    message = "Local TTS is unavailable. Install pyttsx3 or enable Windows SAPI support."
    set_value("last_voice_error", message)
    return {"ok": False, "error": message, "engine": "unavailable"}


def classify_voice_command_safety(text):
    lower = str(text or "").lower()
    matched = [term for term in DANGEROUS_TERMS if term in lower]

    if matched:
        return {
            "safe": False,
            "needs_confirmation": True,
            "blocked_reason": "Voice command requires typed confirmation because it may be risky.",
            "matched_terms": matched,
        }

    return {
        "safe": True,
        "needs_confirmation": False,
        "blocked_reason": "",
        "matched_terms": [],
    }


def save_voice_session_report(
    transcript="",
    safety=None,
    command_result="",
    errors=None,
    status=None,
):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"voice_session_{_stamp()}.md"
    safety = safety or classify_voice_command_safety(transcript)
    status = status or get_voice_status()
    errors = errors or []

    lines = [
        "# Voice Session",
        "",
        "## Summary",
        f"- created_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- safe: {safety.get('safe')}",
        f"- needs_confirmation: {safety.get('needs_confirmation')}",
        "",
        "## Voice status",
    ]

    for key, value in status.items():
        if key != "dependencies":
            lines.append(f"- {key}: {value}")

    lines.extend([
        "",
        "## Transcript",
        str(transcript or "нет"),
        "",
        "## Safety classification",
        f"- blocked_reason: {safety.get('blocked_reason') or 'нет'}",
        f"- matched_terms: {', '.join(safety.get('matched_terms') or []) or 'нет'}",
        "",
        "## Command result",
        str(command_result or "нет"),
        "",
        "## Errors",
    ])

    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- нет")

    lines.extend([
        "",
        "## Next steps",
        "- Проверь transcript перед выполнением risky-команд.",
        "- Для опасных действий используй ручное typed confirmation вне Voice Mode.",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_voice_session_report", str(path))
    set_value("last_voice_transcript", str(transcript or ""))
    set_value("last_voice_result", str(command_result or ""))
    set_value("last_voice_error", "\n".join(errors) if errors else "")
    return path


def latest_voice_session_report():
    path = str(get_value("last_voice_session_report", "") or "").strip()

    if path and Path(path).exists():
        return path

    if not REPORTS_DIR.exists():
        return ""

    reports = list(REPORTS_DIR.glob("voice_session_*.md"))

    if not reports:
        return ""

    return str(max(reports, key=lambda item: item.stat().st_mtime))


def set_tts_muted(muted=True):
    set_value("voice_tts_muted", bool(muted))
    return bool(muted)
````

### ПУТЬ: modules/windows.py (199 строк, 4838 байт)

````python
import subprocess
import time
from pathlib import Path
from modules.project_paths import projects_dir

from core.state import get_value, set_value


PROJECTS_DIR = projects_dir()
WINDOWS_DIR = PROJECTS_DIR / "Windows"
NOTEPAD_FILE = WINDOWS_DIR / "notepad_current.txt"


APP_COMMANDS = {
    "notepad": "notepad",
    "calc": "calc",
    "calculator": "calc",
    "mspaint": "mspaint",
    "paint": "mspaint",
    "chrome": "chrome",
    "explorer": "explorer",
}


def _normalize_app(app: str):
    app = str(app or "").strip().lower()

    aliases = {
        "блокнот": "notepad",
        "notepad": "notepad",
        "ноутпад": "notepad",

        "калькулятор": "calc",
        "calculator": "calc",
        "calc": "calc",

        "paint": "mspaint",
        "паинт": "mspaint",
        "пейнт": "mspaint",
        "mspaint": "mspaint",

        "chrome": "chrome",
        "хром": "chrome",

        "explorer": "explorer",
        "проводник": "explorer",
    }

    return aliases.get(app, app)


def _ensure_windows_dir():
    WINDOWS_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_notepad_file():
    _ensure_windows_dir()

    if not NOTEPAD_FILE.exists():
        NOTEPAD_FILE.write_text("", encoding="utf-8")

    set_value("last_windows_file", str(NOTEPAD_FILE))


def _open_notepad_file():
    _ensure_notepad_file()

    subprocess.Popen(["notepad", str(NOTEPAD_FILE)])
    time.sleep(1)

    set_value("last_windows_app", "notepad")
    set_value("last_windows_file", str(NOTEPAD_FILE))

    return f"Открыл Блокнот с файлом: {NOTEPAD_FILE}"


def _write_to_notepad_file(text: str):
    _ensure_notepad_file()

    NOTEPAD_FILE.write_text(text, encoding="utf-8")

    subprocess.Popen(["notepad", str(NOTEPAD_FILE)])
    time.sleep(1)

    set_value("last_windows_app", "notepad")
    set_value("last_windows_file", str(NOTEPAD_FILE))
    set_value("last_windows_text", text)

    return f"Текст записан в Блокнот: {text}"


def _append_to_notepad_file(text: str):
    _ensure_notepad_file()

    current = NOTEPAD_FILE.read_text(encoding="utf-8")

    if current.strip():
        new_text = current.rstrip() + "\n" + text
    else:
        new_text = text

    NOTEPAD_FILE.write_text(new_text, encoding="utf-8")

    subprocess.Popen(["notepad", str(NOTEPAD_FILE)])
    time.sleep(1)

    set_value("last_windows_app", "notepad")
    set_value("last_windows_file", str(NOTEPAD_FILE))
    set_value("last_windows_text", text)

    return f"Текст добавлен в Блокнот: {text}"


def _read_notepad_file():
    _ensure_notepad_file()

    text = NOTEPAD_FILE.read_text(encoding="utf-8")

    set_value("last_windows_app", "notepad")
    set_value("last_windows_file", str(NOTEPAD_FILE))

    if not text.strip():
        return "Блокнот пустой."

    return "Содержимое Блокнота:\n" + text


def _clear_notepad_file():
    _ensure_notepad_file()

    NOTEPAD_FILE.write_text("", encoding="utf-8")

    subprocess.Popen(["notepad", str(NOTEPAD_FILE)])
    time.sleep(1)

    set_value("last_windows_app", "notepad")
    set_value("last_windows_file", str(NOTEPAD_FILE))
    set_value("last_windows_text", "")

    return "Блокнот очищен."


def open_app(app: str):
    app = _normalize_app(app)

    try:
        if app == "notepad":
            return _open_notepad_file()

        command = APP_COMMANDS.get(app, app)

        subprocess.Popen(command, shell=True)
        time.sleep(1)

        set_value("last_windows_app", app)

        return f"Открыл: {app}"

    except Exception as e:
        return f"Ошибка открытия приложения {app}: {e}"


def type_text(text: str):
    text = str(text or "").strip()

    if not text:
        return "Нет текста для ввода."

    last_app = get_value("last_windows_app") or "notepad"
    last_app = _normalize_app(last_app)

    if last_app == "notepad":
        return _write_to_notepad_file(text)

    return (
        f"Для приложения {last_app} прямой ввод пока нестабилен. "
        f"Для Блокнота текст записывается через файл."
    )


def append_text(text: str):
    text = str(text or "").strip()

    if not text:
        return "Нет текста для добавления."

    return _append_to_notepad_file(text)


def read_notepad():
    return _read_notepad_file()


def clear_notepad():
    return _clear_notepad_file()


def open_notepad_file():
    return _open_notepad_file()
````

### ПУТЬ: modules/working_directory_guard_ru.py (151 строк, 5218 байт)

````python
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Dict, Any

ROOT_DIR = get_project_root()


def get_project_root_indicators() -> Dict[str, Any]:
    """Проверяет основные индикаторы корня проекта LocalAgent."""
    indicators = {
        "localcomet_control_panel_exists": False,
        "modules_directory_exists": False,
        "agents_md_exists": False,
    }
    
    try:
        indicators["localcomet_control_panel_exists"] = (
            ROOT_DIR / "LocalComet_Control_Panel.py"
        ).exists()
    except Exception:
        pass
    
    try:
        indicators["modules_directory_exists"] = (
            ROOT_DIR / "modules"
        ).exists()
    except Exception:
        pass
    
    try:
        indicators["agents_md_exists"] = (
            ROOT_DIR / "AGENTS.md"
        ).exists()
    except Exception:
        pass
    
    return indicators


def check_working_directory() -> Dict[str, Any]:
    """Проверяет, запущена ли команда из корня проекта LocalAgent."""
    try:
        current_path = Path.cwd()
        indicators = get_project_root_indicators()
        
        if indicators["localcomet_control_panel_exists"] and \
           indicators["modules_directory_exists"] and \
           indicators["agents_md_exists"]:
            return {
                "ok": True,
                "mode": "working_directory_guard",
                "version": "v6.65b",
                "message": "Команда запущена из корня проекта LocalAgent.",
                "current_directory": str(current_path),
                "project_root": str(ROOT_DIR),
                "indicators": indicators,
            }
        else:
            return {
                "ok": False,
                "mode": "working_directory_guard",
                "version": "v6.65b",
                "message": (
                    "Команда запущена не из корня проекта LocalAgent. "
                    f'Выполни: cd "{ROOT_DIR}"'
                ),
                "current_directory": str(current_path),
                "project_root": str(ROOT_DIR),
                "indicators": indicators,
                "error": "wrong_directory",
                "suggestion": f'cd "{ROOT_DIR}"',
            }
    except Exception as exc:
        return {
            "ok": False,
            "mode": "working_directory_guard",
            "version": "v6.65b",
            "message": f"Ошибка при проверке рабочей директории: {str(exc)}",
            "current_directory": str(Path.cwd()),
            "project_root": str(ROOT_DIR),
            "indicators": {},
            "error": "exception",
            "exception": str(exc),
        }


def status() -> Dict[str, Any]:
    """Возвращает статус модуля."""
    return get_status()


def report() -> Dict[str, Any]:
    """Возвращает отчёт о проверке рабочей директории."""
    return check_working_directory()


def dispatch(command: str) -> Dict[str, Any]:
    """Обработчик команд для маршрутизации."""
    normalized = str(command or "").strip().lower().replace("ё", "е")
    
    if normalized in {
        "проверь рабочую папку",
        "проверь рабочую папу",
        "working directory guard",
        "проверь рабочую директорию",
        "working dir guard",
    }:
        return {
            "mode": "command",
            "route": "modules.working_directory_guard_ru",
            "plan": {"tool": "modules.working_directory_guard_ru", "action": "dispatch"},
            "result": check_working_directory(),
        }
    
    return {
        "ok": False,
        "mode": "working_directory_guard",
        "version": "v6.65b",
        "message": f"Неизвестная команда: {command}",
    }


def is_working_directory_guard_command(command: str) -> bool:
    """Проверяет, является ли команда командой проверки рабочей директории."""
    if not isinstance(command, str):
        return False
    
    normalized = command.strip().lower().replace("ё", "е")
    return normalized in {
        "проверь рабочую папку",
        "проверь рабочую папу",
        "working directory guard",
        "проверь рабочую директорию",
        "working dir guard",
    }


def get_status() -> Dict[str, Any]:
    """Возвращает статус модуля."""
    return {
        "module": "working_directory_guard_ru",
        "version": "v6.65b",
        "status": "ready",
        "commands": [
            "проверь рабочую папу",
            "working directory guard",
            "проверь рабочую директорию",
            "working dir guard",
        ],
        "description": "Гарантирует, что команды LocalComet запускаются из корня проекта.",
    }
````

### ПУТЬ: modules/workspace.py (213 строк, 5287 байт)

````python
import subprocess
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value, get_value
from modules.report_opener import open_last_report


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
NOTES_DIR = PROJECTS_DIR / "Notes"
FILES_DIR = PROJECTS_DIR / "Files"


def _ensure_dirs():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)


def _open_folder(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["explorer", str(path)])
    return f"Открыл папку: {path}"


def _safe_file_path(path: str):
    _ensure_dirs()

    raw = str(path or "").strip().replace("\\", "/")

    if not raw:
        return None, "Не указан путь файла."

    if ":" in raw or raw.startswith("/") or ".." in raw.split("/"):
        return None, "Небезопасный путь файла."

    file_path = FILES_DIR / raw

    if not file_path.suffix:
        file_path = file_path.with_suffix(".txt")

    file_path.parent.mkdir(parents=True, exist_ok=True)

    return file_path, None


def open_projects_folder():
    return _open_folder(PROJECTS_DIR)


def open_reports_folder():
    return _open_folder(REPORTS_DIR)


def open_files_folder():
    return _open_folder(FILES_DIR)


def list_reports(limit: int = 10):
    _ensure_dirs()

    reports = sorted(
        REPORTS_DIR.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not reports:
        return "Отчетов пока нет."

    lines = [f"Последние отчеты ({min(limit, len(reports))}):"]

    for i, report in enumerate(reports[:limit], start=1):
        lines.append(f"{i}. {report.name}")

    return "\n".join(lines)


def open_latest_report():
    return open_last_report()


def create_note(text: str):
    _ensure_dirs()

    text = str(text or "").strip()

    if not text:
        return "Нет текста для заметки."

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    note_path = NOTES_DIR / f"note_{stamp}.md"

    content = "# Заметка LocalComet\n\n" + text + "\n"
    note_path.write_text(content, encoding="utf-8")

    set_value("last_note", str(note_path))
    set_value("last_workspace_file", str(note_path))

    return f"Заметка создана: {note_path}"


def list_notes(limit: int = 10):
    _ensure_dirs()

    notes = sorted(
        NOTES_DIR.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not notes:
        return "Заметок пока нет."

    lines = [f"Последние заметки ({min(limit, len(notes))}):"]

    for i, note in enumerate(notes[:limit], start=1):
        lines.append(f"{i}. {note.name}")

    return "\n".join(lines)


def read_latest_note():
    _ensure_dirs()

    notes = sorted(
        NOTES_DIR.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not notes:
        return "Заметок пока нет."

    latest = notes[0]
    text = latest.read_text(encoding="utf-8")

    set_value("last_note", str(latest))
    set_value("last_workspace_file", str(latest))

    return f"Последняя заметка:\n{latest}\n\n{text}"


def create_text_file(path: str, content: str):
    file_path, error = _safe_file_path(path)

    if error:
        return error

    content = str(content or "")

    file_path.write_text(content, encoding="utf-8")

    set_value("last_workspace_file", str(file_path))

    return f"Файл создан: {file_path}"


def read_text_file(path: str):
    file_path, error = _safe_file_path(path)

    if error:
        return error

    if not file_path.exists():
        return f"Файл не найден: {file_path}"

    text = file_path.read_text(encoding="utf-8")

    set_value("last_workspace_file", str(file_path))

    return f"Содержимое файла:\n{file_path}\n\n{text}"


def list_files(limit: int = 20):
    _ensure_dirs()

    files = sorted(
        [p for p in FILES_DIR.rglob("*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not files:
        return "Файлов в Projects/Files пока нет."

    lines = [f"Файлы в Projects/Files ({min(limit, len(files))}):"]

    for i, file in enumerate(files[:limit], start=1):
        rel = file.relative_to(FILES_DIR)
        lines.append(f"{i}. {rel}")

    return "\n".join(lines)


def open_last_workspace_file():
    last_file = get_value("last_workspace_file")

    if not last_file:
        return "Последний workspace-файл не найден."

    path = Path(last_file)

    if not path.exists():
        return f"Файл не найден: {path}"

    subprocess.Popen(["notepad", str(path)])

    return f"Открыл файл: {path}"
````

### ПУТЬ: modules/workspace_policy.py (129 строк, 4414 байт)

````python
"""Workspace confinement policy for LocalComet.

A reusable security primitive that confines filesystem operations to a single
confirmed workspace. Mirrors the Rust workspace.rs authority on the Python side
and aligns with modules/files.py safe_path() confinement.

NOTE on product wiring: the desktop sidecar currently performs no filesystem
operations (files.* methods are unsupported_method), so this policy is a
foundation primitive plus the reference implementation for workspace.set
handling. The desktop's authoritative workspace boundary is the Rust approval
scope (src-tauri/src/workspace.rs + approval_commands.rs::set_workspace).
"""

from __future__ import annotations

import hashlib
from pathlib import Path


class WorkspacePolicyError(Exception):
    """Raised when a workspace path is invalid or a path escapes confinement."""


class WorkspacePolicy:
    def __init__(self, canonical_path: str, digest: str, session_id: str):
        resolved = Path(canonical_path).resolve()
        if not resolved.exists():
            raise WorkspacePolicyError(f"workspace does not exist: {resolved}")
        if not resolved.is_dir():
            raise WorkspacePolicyError(f"workspace is not a directory: {resolved}")
        self._path = resolved
        self._digest = digest
        self._session_id = session_id

    @property
    def canonical_path(self) -> str:
        return str(self._path)

    @property
    def digest(self) -> str:
        return self._digest

    @property
    def session_id(self) -> str:
        return self._session_id

    def validate_path(self, requested: "str | Path") -> Path:
        """Return the resolved path if inside the workspace, else raise.

        Resolution happens before the containment check so symlink/junction
        escape is caught (the resolved target, not the raw string, is tested).
        """
        target = Path(requested).resolve()
        try:
            target.relative_to(self._path)
        except ValueError as exc:
            raise WorkspacePolicyError(
                f"path {target} is outside workspace {self._path}"
            ) from exc
        return target

    def is_within(self, requested: "str | Path") -> bool:
        try:
            self.validate_path(requested)
            return True
        except WorkspacePolicyError:
            return False


def workspace_digest(canonical_path: str) -> str:
    return hashlib.sha256(str(canonical_path).encode("utf-8")).hexdigest()


def make_policy(canonical_path: str, session_id: str) -> WorkspacePolicy:
    return WorkspacePolicy(canonical_path, workspace_digest(canonical_path), session_id)


def _self_test() -> int:
    import tempfile

    failures = []

    def check(condition: bool, label: str) -> None:
        if not condition:
            failures.append(label)

    with tempfile.TemporaryDirectory(prefix="lc_ws_a_") as ws_a, tempfile.TemporaryDirectory(
        prefix="lc_ws_b_"
    ) as ws_b:
        policy = make_policy(ws_a, session_id="0" * 64)
        check(policy.canonical_path == str(Path(ws_a).resolve()), "canonical_path")
        check(len(policy.digest) == 64, "digest length")

        inside = Path(ws_a) / "file.txt"
        inside.write_text("x", encoding="utf-8")
        check(policy.is_within(inside), "inside path accepted")
        check(policy.validate_path(inside) == inside.resolve(), "validate_path returns resolved")

        outside = Path(ws_b) / "other.txt"
        check(not policy.is_within(outside), "outside path rejected")
        try:
            policy.validate_path(outside)
            failures.append("validate_path did not raise for outside path")
        except WorkspacePolicyError:
            pass

        # Traversal escape must be rejected after resolution.
        traversal = Path(ws_a) / ".." / Path(ws_b).name / "escape.txt"
        check(not policy.is_within(traversal), "traversal escape rejected")

    # Non-existent workspace must fail closed.
    try:
        make_policy(str(Path(tempfile.gettempdir()) / "lc_nonexistent_ws_zzz"), "1" * 64)
        failures.append("non-existent workspace did not raise")
    except WorkspacePolicyError:
        pass

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("OK: workspace_policy self-test passed")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_self_test())
````

### ПУТЬ: next/app_v5.py (2039 строк, 61029 байт)

````python
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
````

### ПУТЬ: next/goal_manager.py (59 строк, 1847 байт)

````python
from core.llm import ask_llm, is_llm_offline_error, format_llm_offline_message
from json_repair import repair_json
import json
import sys


SYSTEM = """
You are LocalComet Goal Manager.

Analyze the user's goal and return ONLY valid JSON.

Format:
{
  "goal": "short goal name",
  "type": "website|research|operator|browser|windows|files|code|unknown",
  "success_criteria": [
    "criterion 1",
    "criterion 2",
    "criterion 3"
  ]
}

Rules:
- If the user asks to find several options, compare options, choose the best, pick the best, rank tools, or make a top list, type must be "operator".
- If the user asks to study, research, analyze, find information, or make a report, type must be "research".
- If the user asks to create/generate/improve a website, type must be "website".
- Keep goal short.
- Success criteria must be concrete.
- Do not use markdown.
- Do not explain.
"""


def analyze_goal(user_goal: str):
    answer = ask_llm(SYSTEM, user_goal, max_tokens=700)

    if is_llm_offline_error(answer):
        return {
            "goal": "LLM offline",
            "type": "unknown",
            "success_criteria": [format_llm_offline_message()],
        }

    answer = answer.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(repair_json(answer))
    except (ValueError, json.JSONDecodeError) as e:
        print(f"[goal_manager] JSON parse error: {str(e)[:200]}", file=sys.stderr)
        return {"goal": user_goal, "type": "unknown", "success_criteria": []}

    if not isinstance(data, dict):
        return {"goal": user_goal, "type": "unknown", "success_criteria": []}

    return {
        "goal": data.get("goal", user_goal),
        "type": data.get("type", "unknown"),
        "success_criteria": data.get("success_criteria", [])
    }
````

### ПУТЬ: next/observer.py (50 строк, 1204 байт)

````python
import json
import sys
from json_repair import repair_json
from core.llm import ask_llm


SYSTEM = """
You are LocalComet Observer.

Analyze website/page text and return ONLY valid JSON.

Format:
{
  "summary": "short summary",
  "good": [
    "what is good"
  ],
  "problems": [
    "what is missing or weak"
  ],
  "score": 1
}

Rules:
- score must be from 1 to 10.
- problems must be concrete.
- do not use markdown.
- do not explain.
"""


def observe_page(page_text: str):
    answer = ask_llm(SYSTEM, page_text, max_tokens=800)
    answer = answer.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(repair_json(answer))
    except (ValueError, json.JSONDecodeError) as e:
        print(f"[observer] JSON parse error: {str(e)[:200]}", file=sys.stderr)
        return {"summary": "", "good": [], "problems": [], "score": 0}

    if not isinstance(data, dict):
        return {"summary": "", "good": [], "problems": [], "score": 0}

    return {
        "summary": data.get("summary", ""),
        "good": data.get("good", []),
        "problems": data.get("problems", []),
        "score": data.get("score", 0)
    }
````

### ПУТЬ: next/task_planner.py (87 строк, 2362 байт)

````python
import json
import sys
from json_repair import repair_json
from core.llm import ask_llm, is_llm_offline_error, format_llm_offline_message


SYSTEM = """
You are LocalComet Task Planner.

Split user goal into executable user-style commands.

Return ONLY valid JSON.

Format:
{
  "tasks": [
    "Изучи аналоги Comet и Claude Code и сделай краткий отчет"
  ]
}

CRITICAL RULES:
- Tasks must be executable by LocalComet.
- Use simple Russian commands.
- Do NOT write abstract tasks.
- Do NOT ask user for more information.

Research rules:
- If user asks to study/research/analyze/compare/find information/make report, return ONE task with the original meaning.
- Research task must include words like "изучи", "сравни", "сделай отчет" or "сделай краткий отчет".
- Do NOT create website tasks for research goals.

Website rules:
- If user asks to create a website, use:
  1. "Создай современный сайт ..."
  2. "Открой сайт"
  3. "Проверь сайт"
  4. "Улучши сайт"

Examples:

User goal:
Изучи аналоги Comet и Claude Code и сделай краткий отчет

Return:
{
  "tasks": [
    "Изучи аналоги Comet и Claude Code и сделай краткий отчет"
  ]
}

User goal:
Создай современный сайт автосервиса с формой заявки, открой его, проверь и улучши дизайн

Return:
{
  "tasks": [
    "Создай современный сайт автосервиса",
    "Открой сайт",
    "Проверь сайт",
    "Улучши сайт"
  ]
}

Do not use markdown.
Do not explain.
Return JSON only.
"""


def create_tasks(goal: str):
    answer = ask_llm(SYSTEM, goal, max_tokens=700)

    if is_llm_offline_error(answer):
        return [format_llm_offline_message()]

    answer = answer.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(repair_json(answer))
    except (ValueError, json.JSONDecodeError) as e:
        print(f"[task_planner] JSON parse error: {str(e)[:200]}", file=sys.stderr)
        return []

    if not isinstance(data, dict):
        return []

    return data.get("tasks", [])
````

### ПУТЬ: next/task_queue.py (29 строк, 672 байт)

````python
class TaskQueue:
    def __init__(self):
        self.tasks = []
        self.done = []

    def add(self, task: str):
        if task and task not in self.tasks and task not in self.done:
            self.tasks.append(task)

    def add_many(self, tasks):
        for task in tasks:
            self.add(task)

    def next(self):
        if not self.tasks:
            return None

        task = self.tasks.pop(0)
        self.done.append(task)
        return task

    def has_tasks(self):
        return len(self.tasks) > 0

    def history(self):
        return {
            "pending": self.tasks,
            "done": self.done
        }
````

### ПУТЬ: Python/pythoncore-3.14-64/Lib/abc.py (188 строк, 6726 байт)

````python
# Copyright 2007 Google, Inc. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

"""Abstract Base Classes (ABCs) according to PEP 3119."""


def abstractmethod(funcobj):
    """A decorator indicating abstract methods.

    Requires that the metaclass is ABCMeta or derived from it.  A
    class that has a metaclass derived from ABCMeta cannot be
    instantiated unless all of its abstract methods are overridden.
    The abstract methods can be called using any of the normal
    'super' call mechanisms.  abstractmethod() may be used to declare
    abstract methods for properties and descriptors.

    Usage:

        class C(metaclass=ABCMeta):
            @abstractmethod
            def my_abstract_method(self, arg1, arg2, argN):
                ...
    """
    funcobj.__isabstractmethod__ = True
    return funcobj


class abstractclassmethod(classmethod):
    """A decorator indicating abstract classmethods.

    Deprecated, use 'classmethod' with 'abstractmethod' instead:

        class C(ABC):
            @classmethod
            @abstractmethod
            def my_abstract_classmethod(cls, ...):
                ...

    """

    __isabstractmethod__ = True

    def __init__(self, callable):
        callable.__isabstractmethod__ = True
        super().__init__(callable)


class abstractstaticmethod(staticmethod):
    """A decorator indicating abstract staticmethods.

    Deprecated, use 'staticmethod' with 'abstractmethod' instead:

        class C(ABC):
            @staticmethod
            @abstractmethod
            def my_abstract_staticmethod(...):
                ...

    """

    __isabstractmethod__ = True

    def __init__(self, callable):
        callable.__isabstractmethod__ = True
        super().__init__(callable)


class abstractproperty(property):
    """A decorator indicating abstract properties.

    Deprecated, use 'property' with 'abstractmethod' instead:

        class C(ABC):
            @property
            @abstractmethod
            def my_abstract_property(self):
                ...

    """

    __isabstractmethod__ = True


try:
    from _abc import (get_cache_token, _abc_init, _abc_register,
                      _abc_instancecheck, _abc_subclasscheck, _get_dump,
                      _reset_registry, _reset_caches)
except ImportError:
    from _py_abc import ABCMeta, get_cache_token
    ABCMeta.__module__ = 'abc'
else:
    class ABCMeta(type):
        """Metaclass for defining Abstract Base Classes (ABCs).

        Use this metaclass to create an ABC.  An ABC can be subclassed
        directly, and then acts as a mix-in class.  You can also register
        unrelated concrete classes (even built-in classes) and unrelated
        ABCs as 'virtual subclasses' -- these and their descendants will
        be considered subclasses of the registering ABC by the built-in
        issubclass() function, but the registering ABC won't show up in
        their MRO (Method Resolution Order) nor will method
        implementations defined by the registering ABC be callable (not
        even via super()).
        """
        def __new__(mcls, name, bases, namespace, /, **kwargs):
            cls = super().__new__(mcls, name, bases, namespace, **kwargs)
            _abc_init(cls)
            return cls

        def register(cls, subclass):
            """Register a virtual subclass of an ABC.

            Returns the subclass, to allow usage as a class decorator.
            """
            return _abc_register(cls, subclass)

        def __instancecheck__(cls, instance):
            """Override for isinstance(instance, cls)."""
            return _abc_instancecheck(cls, instance)

        def __subclasscheck__(cls, subclass):
            """Override for issubclass(subclass, cls)."""
            return _abc_subclasscheck(cls, subclass)

        def _dump_registry(cls, file=None):
            """Debug helper to print the ABC registry."""
            print(f"Class: {cls.__module__}.{cls.__qualname__}", file=file)
            print(f"Inv. counter: {get_cache_token()}", file=file)
            (_abc_registry, _abc_cache, _abc_negative_cache,
             _abc_negative_cache_version) = _get_dump(cls)
            print(f"_abc_registry: {_abc_registry!r}", file=file)
            print(f"_abc_cache: {_abc_cache!r}", file=file)
            print(f"_abc_negative_cache: {_abc_negative_cache!r}", file=file)
            print(f"_abc_negative_cache_version: {_abc_negative_cache_version!r}",
                  file=file)

        def _abc_registry_clear(cls):
            """Clear the registry (for debugging or testing)."""
            _reset_registry(cls)

        def _abc_caches_clear(cls):
            """Clear the caches (for debugging or testing)."""
            _reset_caches(cls)


def update_abstractmethods(cls):
    """Recalculate the set of abstract methods of an abstract class.

    If a class has had one of its abstract methods implemented after the
    class was created, the method will not be considered implemented until
    this function is called. Alternatively, if a new abstract method has been
    added to the class, it will only be considered an abstract method of the
    class after this function is called.

    This function should be called before any use is made of the class,
    usually in class decorators that add methods to the subject class.

    Returns cls, to allow usage as a class decorator.

    If cls is not an instance of ABCMeta, does nothing.
    """
    if not hasattr(cls, '__abstractmethods__'):
        # We check for __abstractmethods__ here because cls might by a C
        # implementation or a python implementation (especially during
        # testing), and we want to handle both cases.
        return cls

    abstracts = set()
    # Check the existing abstract methods of the parents, keep only the ones
    # that are not implemented.
    for scls in cls.__bases__:
        for name in getattr(scls, '__abstractmethods__', ()):
            value = getattr(cls, name, None)
            if getattr(value, "__isabstractmethod__", False):
                abstracts.add(name)
    # Also add any other newly added abstract methods.
    for name, value in cls.__dict__.items():
        if getattr(value, "__isabstractmethod__", False):
            abstracts.add(name)
    cls.__abstractmethods__ = frozenset(abstracts)
    return cls


class ABC(metaclass=ABCMeta):
    """Helper class that provides a standard way to create an ABC using
    inheritance.
    """
    __slots__ = ()
````

### ПУТЬ: Python/pythoncore-3.14-64/Lib/annotationlib.py (1197 строк, 45617 байт)

````python
"""Helpers for introspecting and wrapping annotations."""

import ast
import builtins
import enum
import keyword
import sys
import types

__all__ = [
    "Format",
    "ForwardRef",
    "call_annotate_function",
    "call_evaluate_function",
    "get_annotate_from_class_namespace",
    "get_annotations",
    "annotations_to_string",
    "type_repr",
]


class Format(enum.IntEnum):
    VALUE = 1
    VALUE_WITH_FAKE_GLOBALS = 2
    FORWARDREF = 3
    STRING = 4


_sentinel = object()
# Following `NAME_ERROR_MSG` in `ceval_macros.h`:
_NAME_ERROR_MSG = "name '{name:.200}' is not defined"


# Slots shared by ForwardRef and _Stringifier. The __forward__ names must be
# preserved for compatibility with the old typing.ForwardRef class. The remaining
# names are private.
_SLOTS = (
    "__forward_is_argument__",
    "__forward_is_class__",
    "__forward_module__",
    "__weakref__",
    "__arg__",
    "__globals__",
    "__extra_names__",
    "__code__",
    "__ast_node__",
    "__cell__",
    "__owner__",
    "__stringifier_dict__",
    "__resolved_str_cache__",
)


class ForwardRef:
    """Wrapper that holds a forward reference.

    Constructor arguments:
    * arg: a string representing the code to be evaluated.
    * module: the module where the forward reference was created.
      Must be a string, not a module object.
    * owner: The owning object (module, class, or function).
    * is_argument: Does nothing, retained for compatibility.
    * is_class: True if the forward reference was created in class scope.

    """

    __slots__ = _SLOTS

    def __init__(
        self,
        arg,
        *,
        module=None,
        owner=None,
        is_argument=True,
        is_class=False,
    ):
        if not isinstance(arg, str):
            raise TypeError(f"Forward reference must be a string -- got {arg!r}")

        self.__arg__ = arg
        self.__forward_is_argument__ = is_argument
        self.__forward_is_class__ = is_class
        self.__forward_module__ = module
        self.__owner__ = owner
        # These are always set to None here but may be non-None if a ForwardRef
        # is created through __class__ assignment on a _Stringifier object.
        self.__globals__ = None
        # This may be either a cell object (for a ForwardRef referring to a single name)
        # or a dict mapping cell names to cell objects (for a ForwardRef containing references
        # to multiple names).
        self.__cell__ = None
        self.__extra_names__ = None
        # These are initially None but serve as a cache and may be set to a non-None
        # value later.
        self.__code__ = None
        self.__ast_node__ = None
        self.__resolved_str_cache__ = None

    def __init_subclass__(cls, /, *args, **kwds):
        raise TypeError("Cannot subclass ForwardRef")

    def evaluate(
        self,
        *,
        globals=None,
        locals=None,
        type_params=None,
        owner=None,
        format=Format.VALUE,
    ):
        """Evaluate the forward reference and return the value.

        If the forward reference cannot be evaluated, raise an exception.
        """
        match format:
            case Format.STRING:
                return self.__resolved_str__
            case Format.VALUE:
                is_forwardref_format = False
            case Format.FORWARDREF:
                is_forwardref_format = True
            case _:
                raise NotImplementedError(format)
        if isinstance(self.__cell__, types.CellType):
            try:
                return self.__cell__.cell_contents
            except ValueError:
                pass
        if owner is None:
            owner = self.__owner__

        if globals is None and self.__forward_module__ is not None:
            globals = getattr(
                sys.modules.get(self.__forward_module__, None), "__dict__", None
            )
        if globals is None:
            globals = self.__globals__
        if globals is None:
            if isinstance(owner, type):
                module_name = getattr(owner, "__module__", None)
                if module_name:
                    module = sys.modules.get(module_name, None)
                    if module:
                        globals = getattr(module, "__dict__", None)
            elif isinstance(owner, types.ModuleType):
                globals = getattr(owner, "__dict__", None)
            elif callable(owner):
                globals = getattr(owner, "__globals__", None)

        # If we pass None to eval() below, the globals of this module are used.
        if globals is None:
            globals = {}

        if type_params is None and owner is not None:
            type_params = getattr(owner, "__type_params__", None)

        if locals is None:
            locals = {}
            if isinstance(owner, type):
                locals.update(vars(owner))
        elif (
            type_params is not None
            or isinstance(self.__cell__, dict)
            or self.__extra_names__
        ):
            # Create a new locals dict if necessary,
            # to avoid mutating the argument.
            locals = dict(locals)

        # "Inject" type parameters into the local namespace
        # (unless they are shadowed by assignments *in* the local namespace),
        # as a way of emulating annotation scopes when calling `eval()`
        if type_params is not None:
            for param in type_params:
                locals.setdefault(param.__name__, param)

        # Similar logic can be used for nonlocals, which should not
        # override locals.
        if isinstance(self.__cell__, dict):
            for cell_name, cell in self.__cell__.items():
                try:
                    cell_value = cell.cell_contents
                except ValueError:
                    pass
                else:
                    locals.setdefault(cell_name, cell_value)

        if self.__extra_names__:
            locals.update(self.__extra_names__)

        arg = self.__forward_arg__
        if arg.isidentifier() and not keyword.iskeyword(arg):
            if arg in locals:
                return locals[arg]
            elif arg in globals:
                return globals[arg]
            elif hasattr(builtins, arg):
                return getattr(builtins, arg)
            elif is_forwardref_format:
                return self
            else:
                raise NameError(_NAME_ERROR_MSG.format(name=arg), name=arg)
        else:
            code = self.__forward_code__
            try:
                return eval(code, globals=globals, locals=locals)
            except Exception:
                if not is_forwardref_format:
                    raise

            # All variables, in scoping order, should be checked before
            # triggering __missing__ to create a _Stringifier.
            new_locals = _StringifierDict(
                {**builtins.__dict__, **globals, **locals},
                globals=globals,
                owner=owner,
                is_class=self.__forward_is_class__,
                format=format,
            )
            try:
                result = eval(code, globals=globals, locals=new_locals)
            except Exception:
                return self
            else:
                new_locals.transmogrify(self.__cell__)
                return result

    def _evaluate(self, globalns, localns, type_params=_sentinel, *, recursive_guard):
        import typing
        import warnings

        if type_params is _sentinel:
            typing._deprecation_warning_for_no_type_params_passed(
                "typing.ForwardRef._evaluate"
            )
            type_params = ()
        warnings._deprecated(
            "ForwardRef._evaluate",
            "{name} is a private API and is retained for compatibility, but will be removed"
            " in Python 3.16. Use ForwardRef.evaluate() or typing.evaluate_forward_ref() instead.",
            remove=(3, 16),
        )
        return typing.evaluate_forward_ref(
            self,
            globals=globalns,
            locals=localns,
            type_params=type_params,
            _recursive_guard=recursive_guard,
        )

    @property
    def __forward_arg__(self):
        if self.__arg__ is not None:
            return self.__arg__
        if self.__ast_node__ is not None:
            self.__arg__ = ast.unparse(self.__ast_node__)
            return self.__arg__
        raise AssertionError(
            "Attempted to access '__forward_arg__' on an uninitialized ForwardRef"
        )

    @property
    def __resolved_str__(self):
        # __forward_arg__ with any names from __extra_names__ replaced
        # with the type_repr of the value they represent
        if self.__resolved_str_cache__ is None:
            resolved_str = self.__forward_arg__
            names = self.__extra_names__

            if names:
                visitor = _ExtraNameFixer(names)
                ast_expr = ast.parse(resolved_str, mode="eval").body
                node = visitor.visit(ast_expr)
                resolved_str = ast.unparse(node)

            self.__resolved_str_cache__ = resolved_str

        return self.__resolved_str_cache__

    @property
    def __forward_code__(self):
        if self.__code__ is not None:
            return self.__code__
        arg = self.__forward_arg__
        try:
            self.__code__ = compile(_rewrite_star_unpack(arg), "<string>", "eval")
        except SyntaxError:
            raise SyntaxError(f"Forward reference must be an expression -- got {arg!r}")
        return self.__code__

    def __eq__(self, other):
        if not isinstance(other, ForwardRef):
            return NotImplemented
        return (
            self.__forward_arg__ == other.__forward_arg__
            and self.__forward_module__ == other.__forward_module__
            # Use "is" here because we use id() for this in __hash__
            # because dictionaries are not hashable.
            and self.__globals__ is other.__globals__
            and self.__forward_is_class__ == other.__forward_is_class__
            # Two separate cells are always considered unequal in forward refs.
            and (
                {name: id(cell) for name, cell in self.__cell__.items()}
                == {name: id(cell) for name, cell in other.__cell__.items()}
                if isinstance(self.__cell__, dict) and isinstance(other.__cell__, dict)
                else self.__cell__ is other.__cell__
            )
            and self.__owner__ == other.__owner__
            and (
                (tuple(sorted(self.__extra_names__.items())) if self.__extra_names__ else None) ==
                (tuple(sorted(other.__extra_names__.items())) if other.__extra_names__ else None)
            )
        )

    def __hash__(self):
        return hash((
            self.__forward_arg__,
            self.__forward_module__,
            id(self.__globals__),  # dictionaries are not hashable, so hash by identity
            self.__forward_is_class__,
            (  # cells are not hashable as well
                tuple(sorted([(name, id(cell)) for name, cell in self.__cell__.items()]))
                if isinstance(self.__cell__, dict) else id(self.__cell__),
            ),
            self.__owner__,
            tuple(sorted(self.__extra_names__.items())) if self.__extra_names__ else None,
        ))

    def __or__(self, other):
        return types.UnionType[self, other]

    def __ror__(self, other):
        return types.UnionType[other, self]

    def __repr__(self):
        extra = []
        if self.__forward_module__ is not None:
            extra.append(f", module={self.__forward_module__!r}")
        if self.__forward_is_class__:
            extra.append(", is_class=True")
        if self.__owner__ is not None:
            extra.append(f", owner={self.__owner__!r}")
        return f"ForwardRef({self.__resolved_str__!r}{''.join(extra)})"


_Template = type(t"")


class _Stringifier:
    # Must match the slots on ForwardRef, so we can turn an instance of one into an
    # instance of the other in place.
    __slots__ = _SLOTS

    def __init__(
        self,
        node,
        globals=None,
        owner=None,
        is_class=False,
        cell=None,
        *,
        stringifier_dict,
        extra_names=None,
    ):
        # Either an AST node or a simple str (for the common case where a ForwardRef
        # represent a single name).
        assert isinstance(node, (ast.AST, str))
        self.__arg__ = None
        self.__forward_is_argument__ = False
        self.__forward_is_class__ = is_class
        self.__forward_module__ = None
        self.__code__ = None
        self.__ast_node__ = node
        self.__globals__ = globals
        self.__extra_names__ = extra_names
        self.__cell__ = cell
        self.__owner__ = owner
        self.__stringifier_dict__ = stringifier_dict
        self.__resolved_str_cache__ = None  # Needed for ForwardRef

    def __convert_to_ast(self, other):
        if isinstance(other, _Stringifier):
            if isinstance(other.__ast_node__, str):
                return ast.Name(id=other.__ast_node__), other.__extra_names__
            return other.__ast_node__, other.__extra_names__
        elif type(other) is _Template:
            return _template_to_ast(other), None
        elif (
            # In STRING format we don't bother with the create_unique_name() dance;
            # it's better to emit the repr() of the object instead of an opaque name.
            self.__stringifier_dict__.format == Format.STRING
            or other is None
            or type(other) in (str, int, float, bool, complex)
        ):
            return ast.Constant(value=other), None
        elif type(other) is dict:
            extra_names = {}
            keys = []
            values = []
            for key, value in other.items():
                new_key, new_extra_names = self.__convert_to_ast(key)
                if new_extra_names is not None:
                    extra_names.update(new_extra_names)
                keys.append(new_key)
                new_value, new_extra_names = self.__convert_to_ast(value)
                if new_extra_names is not None:
                    extra_names.update(new_extra_names)
                values.append(new_value)
            return ast.Dict(keys, values), extra_names
        elif type(other) in (list, tuple, set):
            extra_names = {}
            elts = []
            for elt in other:
                new_elt, new_extra_names = self.__convert_to_ast(elt)
                if new_extra_names is not None:
                    extra_names.update(new_extra_names)
                elts.append(new_elt)
            ast_class = {list: ast.List, tuple: ast.Tuple, set: ast.Set}[type(other)]
            return ast_class(elts), extra_names
        else:
            name = self.__stringifier_dict__.create_unique_name()
            return ast.Name(id=name), {name: other}

    def __convert_to_ast_getitem(self, other):
        if isinstance(other, slice):
            extra_names = {}

            def conv(obj):
                if obj is None:
                    return None
                new_obj, new_extra_names = self.__convert_to_ast(obj)
                if new_extra_names is not None:
                    extra_names.update(new_extra_names)
                return new_obj

            return ast.Slice(
                lower=conv(other.start),
                upper=conv(other.stop),
                step=conv(other.step),
            ), extra_names
        else:
            return self.__convert_to_ast(other)

    def __get_ast(self):
        node = self.__ast_node__
        if isinstance(node, str):
            return ast.Name(id=node)
        return node

    def __make_new(self, node, extra_names=None):
        new_extra_names = {}
        if self.__extra_names__ is not None:
            new_extra_names.update(self.__extra_names__)
        if extra_names is not None:
            new_extra_names.update(extra_names)
        stringifier = _Stringifier(
            node,
            self.__globals__,
            self.__owner__,
            self.__forward_is_class__,
            stringifier_dict=self.__stringifier_dict__,
            extra_names=new_extra_names or None,
        )
        self.__stringifier_dict__.stringifiers.append(stringifier)
        return stringifier

    # Must implement this since we set __eq__. We hash by identity so that
    # stringifiers in dict keys are kept separate.
    def __hash__(self):
        return id(self)

    def __getitem__(self, other):
        # Special case, to avoid stringifying references to class-scoped variables
        # as '__classdict__["x"]'.
        if self.__ast_node__ == "__classdict__":
            raise KeyError
        if isinstance(other, tuple):
            extra_names = {}
            elts = []
            for elt in other:
                new_elt, new_extra_names = self.__convert_to_ast_getitem(elt)
                if new_extra_names is not None:
                    extra_names.update(new_extra_names)
                elts.append(new_elt)
            other = ast.Tuple(elts)
        else:
            other, extra_names = self.__convert_to_ast_getitem(other)
        assert isinstance(other, ast.AST), repr(other)
        return self.__make_new(ast.Subscript(self.__get_ast(), other), extra_names)

    def __getattr__(self, attr):
        return self.__make_new(ast.Attribute(self.__get_ast(), attr))

    def __call__(self, *args, **kwargs):
        extra_names = {}
        ast_args = []
        for arg in args:
            new_arg, new_extra_names = self.__convert_to_ast(arg)
            if new_extra_names is not None:
                extra_names.update(new_extra_names)
            ast_args.append(new_arg)
        ast_kwargs = []
        for key, value in kwargs.items():
            new_value, new_extra_names = self.__convert_to_ast(value)
            if new_extra_names is not None:
                extra_names.update(new_extra_names)
            ast_kwargs.append(ast.keyword(key, new_value))
        return self.__make_new(ast.Call(self.__get_ast(), ast_args, ast_kwargs), extra_names)

    def __iter__(self):
        yield self.__make_new(ast.Starred(self.__get_ast()))

    def __repr__(self):
        if isinstance(self.__ast_node__, str):
            return self.__ast_node__
        return ast.unparse(self.__ast_node__)

    def __format__(self, format_spec):
        raise TypeError("Cannot stringify annotation containing string formatting")

    def _make_binop(op: ast.AST):
        def binop(self, other):
            rhs, extra_names = self.__convert_to_ast(other)
            return self.__make_new(
                ast.BinOp(self.__get_ast(), op, rhs), extra_names
            )

        return binop

    __add__ = _make_binop(ast.Add())
    __sub__ = _make_binop(ast.Sub())
    __mul__ = _make_binop(ast.Mult())
    __matmul__ = _make_binop(ast.MatMult())
    __truediv__ = _make_binop(ast.Div())
    __mod__ = _make_binop(ast.Mod())
    __lshift__ = _make_binop(ast.LShift())
    __rshift__ = _make_binop(ast.RShift())
    __or__ = _make_binop(ast.BitOr())
    __xor__ = _make_binop(ast.BitXor())
    __and__ = _make_binop(ast.BitAnd())
    __floordiv__ = _make_binop(ast.FloorDiv())
    __pow__ = _make_binop(ast.Pow())

    del _make_binop

    def _make_rbinop(op: ast.AST):
        def rbinop(self, other):
            new_other, extra_names = self.__convert_to_ast(other)
            return self.__make_new(
                ast.BinOp(new_other, op, self.__get_ast()), extra_names
            )

        return rbinop

    __radd__ = _make_rbinop(ast.Add())
    __rsub__ = _make_rbinop(ast.Sub())
    __rmul__ = _make_rbinop(ast.Mult())
    __rmatmul__ = _make_rbinop(ast.MatMult())
    __rtruediv__ = _make_rbinop(ast.Div())
    __rmod__ = _make_rbinop(ast.Mod())
    __rlshift__ = _make_rbinop(ast.LShift())
    __rrshift__ = _make_rbinop(ast.RShift())
    __ror__ = _make_rbinop(ast.BitOr())
    __rxor__ = _make_rbinop(ast.BitXor())
    __rand__ = _make_rbinop(ast.BitAnd())
    __rfloordiv__ = _make_rbinop(ast.FloorDiv())
    __rpow__ = _make_rbinop(ast.Pow())

    del _make_rbinop

    def _make_compare(op):
        def compare(self, other):
            rhs, extra_names = self.__convert_to_ast(other)
            return self.__make_new(
                ast.Compare(
                    left=self.__get_ast(),
                    ops=[op],
                    comparators=[rhs],
                ),
                extra_names,
            )

        return compare

    __lt__ = _make_compare(ast.Lt())
    __le__ = _make_compare(ast.LtE())
    __eq__ = _make_compare(ast.Eq())
    __ne__ = _make_compare(ast.NotEq())
    __gt__ = _make_compare(ast.Gt())
    __ge__ = _make_compare(ast.GtE())

    del _make_compare

    def _make_unary_op(op):
        def unary_op(self):
            return self.__make_new(ast.UnaryOp(op, self.__get_ast()))

        return unary_op

    __invert__ = _make_unary_op(ast.Invert())
    __pos__ = _make_unary_op(ast.UAdd())
    __neg__ = _make_unary_op(ast.USub())

    del _make_unary_op


def _template_to_ast_constructor(template):
    """Convert a `template` instance to a non-literal AST."""
    args = []
    for part in template:
        match part:
            case str():
                args.append(ast.Constant(value=part))
            case _:
                interp = ast.Call(
                    func=ast.Name(id="Interpolation"),
                    args=[
                        ast.Constant(value=part.value),
                        ast.Constant(value=part.expression),
                        ast.Constant(value=part.conversion),
                        ast.Constant(value=part.format_spec),
                    ]
                )
                args.append(interp)
    return ast.Call(func=ast.Name(id="Template"), args=args, keywords=[])


def _template_to_ast_literal(template, parsed):
    """Convert a `template` instance to a t-string literal AST."""
    values = []
    interp_count = 0
    for part in template:
        match part:
            case str():
                values.append(ast.Constant(value=part))
            case _:
                interp = ast.Interpolation(
                    str=part.expression,
                    value=parsed[interp_count],
                    conversion=ord(part.conversion) if part.conversion else -1,
                    format_spec=ast.Constant(value=part.format_spec)
                    if part.format_spec
                    else None,
                )
                values.append(interp)
                interp_count += 1
    return ast.TemplateStr(values=values)


def _template_to_ast(template):
    """Make a best-effort conversion of a `template` instance to an AST."""
    # gh-138558: Not all Template instances can be represented as t-string
    # literals. Return the most accurate AST we can. See issue for details.

    # If any expr is empty or whitespace only, we cannot convert to a literal.
    if any(part.expression.strip() == "" for part in template.interpolations):
        return _template_to_ast_constructor(template)

    try:
        # Wrap in parens to allow whitespace inside interpolation curly braces
        parsed = tuple(
            ast.parse(f"({part.expression})", mode="eval").body
            for part in template.interpolations
        )
    except SyntaxError:
        return _template_to_ast_constructor(template)

    return _template_to_ast_literal(template, parsed)


class _StringifierDict(dict):
    def __init__(self, namespace, *, globals=None, owner=None, is_class=False, format):
        super().__init__(namespace)
        self.namespace = namespace
        self.globals = globals
        self.owner = owner
        self.is_class = is_class
        self.stringifiers = []
        self.next_id = 1
        self.format = format

    def __missing__(self, key):
        fwdref = _Stringifier(
            key,
            globals=self.globals,
            owner=self.owner,
            is_class=self.is_class,
            stringifier_dict=self,
        )
        self.stringifiers.append(fwdref)
        return fwdref

    def transmogrify(self, cell_dict):
        for obj in self.stringifiers:
            obj.__class__ = ForwardRef
            obj.__stringifier_dict__ = None  # not needed for ForwardRef
            if isinstance(obj.__ast_node__, str):
                obj.__arg__ = obj.__ast_node__
                obj.__ast_node__ = None
            if cell_dict is not None and obj.__cell__ is None:
                obj.__cell__ = cell_dict

    def create_unique_name(self):
        name = f"__annotationlib_name_{self.next_id}__"
        self.next_id += 1
        return name


def call_evaluate_function(evaluate, format, *, owner=None):
    """Call an evaluate function. Evaluate functions are normally generated for
    the value of type aliases and the bounds, constraints, and defaults of
    type parameter objects.
    """
    return call_annotate_function(evaluate, format, owner=owner, _is_evaluate=True)


def call_annotate_function(annotate, format, *, owner=None, _is_evaluate=False):
    """Call an __annotate__ function. __annotate__ functions are normally
    generated by the compiler to defer the evaluation of annotations. They
    can be called with any of the format arguments in the Format enum, but
    compiler-generated __annotate__ functions only support the VALUE format.
    This function provides additional functionality to call __annotate__
    functions with the FORWARDREF and STRING formats.

    *annotate* must be an __annotate__ function, which takes a single argument
    and returns a dict of annotations.

    *format* must be a member of the Format enum or one of the corresponding
    integer values.

    *owner* can be the object that owns the annotations (i.e., the module,
    class, or function that the __annotate__ function derives from). With the
    FORWARDREF format, it is used to provide better evaluation capabilities
    on the generated ForwardRef objects.

    """
    if format == Format.VALUE_WITH_FAKE_GLOBALS:
        raise ValueError("The VALUE_WITH_FAKE_GLOBALS format is for internal use only")
    try:
        return annotate(format)
    except NotImplementedError:
        pass
    if format == Format.STRING:
        # STRING is implemented by calling the annotate function in a special
        # environment where every name lookup results in an instance of _Stringifier.
        # _Stringifier supports every dunder operation and returns a new _Stringifier.
        # At the end, we get a dictionary that mostly contains _Stringifier objects (or
        # possibly constants if the annotate function uses them directly). We then
        # convert each of those into a string to get an approximation of the
        # original source.

        # Attempt to call with VALUE_WITH_FAKE_GLOBALS to check if it is implemented
        # See: https://github.com/python/cpython/issues/138764
        # Only fail on NotImplementedError
        try:
            annotate(Format.VALUE_WITH_FAKE_GLOBALS)
        except NotImplementedError:
            # Both STRING and VALUE_WITH_FAKE_GLOBALS are not implemented: fallback to VALUE
            return annotations_to_string(annotate(Format.VALUE))
        except Exception:
            pass

        globals = _StringifierDict({}, format=format)
        is_class = isinstance(owner, type)
        closure, _ = _build_closure(
            annotate, owner, is_class, globals, allow_evaluation=False
        )
        func = types.FunctionType(
            annotate.__code__,
            globals,
            closure=closure,
            argdefs=annotate.__defaults__,
            kwdefaults=annotate.__kwdefaults__,
        )
        annos = func(Format.VALUE_WITH_FAKE_GLOBALS)
        if _is_evaluate:
            return _stringify_single(annos)
        return {
            key: _stringify_single(val)
            for key, val in annos.items()
        }
    elif format == Format.FORWARDREF:
        # FORWARDREF is implemented similarly to STRING, but there are two changes,
        # at the beginning and the end of the process.
        # First, while STRING uses an empty dictionary as the namespace, so that all
        # name lookups result in _Stringifier objects, FORWARDREF uses the globals
        # and builtins, so that defined names map to their real values.
        # Second, instead of returning strings, we want to return either real values
        # or ForwardRef objects. To do this, we keep track of all _Stringifier objects
        # created while the annotation is being evaluated, and at the end we convert
        # them all to ForwardRef objects by assigning to __class__. To make this
        # technique work, we have to ensure that the _Stringifier and ForwardRef
        # classes share the same attributes.
        # We use this technique because while the annotations are being evaluated,
        # we want to support all operations that the language allows, including even
        # __getattr__ and __eq__, and return new _Stringifier objects so we can accurately
        # reconstruct the source. But in the dictionary that we eventually return, we
        # want to return objects with more user-friendly behavior, such as an __eq__
        # that returns a bool and an defined set of attributes.
        namespace = {**annotate.__builtins__, **annotate.__globals__}
        is_class = isinstance(owner, type)
        globals = _StringifierDict(
            namespace,
            globals=annotate.__globals__,
            owner=owner,
            is_class=is_class,
            format=format,
        )
        closure, cell_dict = _build_closure(
            annotate, owner, is_class, globals, allow_evaluation=True
        )
        func = types.FunctionType(
            annotate.__code__,
            globals,
            closure=closure,
            argdefs=annotate.__defaults__,
            kwdefaults=annotate.__kwdefaults__,
        )
        try:
            result = func(Format.VALUE_WITH_FAKE_GLOBALS)
        except NotImplementedError:
            # FORWARDREF and VALUE_WITH_FAKE_GLOBALS not supported, fall back to VALUE
            return annotate(Format.VALUE)
        except Exception:
            pass
        else:
            globals.transmogrify(cell_dict)
            return result

        # Try again, but do not provide any globals. This allows us to return
        # a value in certain cases where an exception gets raised during evaluation.
        globals = _StringifierDict(
            {},
            globals=annotate.__globals__,
            owner=owner,
            is_class=is_class,
            format=format,
        )
        closure, cell_dict = _build_closure(
            annotate, owner, is_class, globals, allow_evaluation=False
        )
        func = types.FunctionType(
            annotate.__code__,
            globals,
            closure=closure,
            argdefs=annotate.__defaults__,
            kwdefaults=annotate.__kwdefaults__,
        )
        result = func(Format.VALUE_WITH_FAKE_GLOBALS)
        globals.transmogrify(cell_dict)
        if _is_evaluate:
            if isinstance(result, ForwardRef):
                return result.evaluate(format=Format.FORWARDREF)
            else:
                return result
        else:
            return {
                key: (
                    val.evaluate(format=Format.FORWARDREF)
                    if isinstance(val, ForwardRef)
                    else val
                )
                for key, val in result.items()
            }
    elif format == Format.VALUE:
        # Should be impossible because __annotate__ functions must not raise
        # NotImplementedError for this format.
        raise RuntimeError("annotate function does not support VALUE format")
    else:
        raise ValueError(f"Invalid format: {format!r}")


def _build_closure(annotate, owner, is_class, stringifier_dict, *, allow_evaluation):
    if not annotate.__closure__:
        return None, None
    new_closure = []
    cell_dict = {}
    for name, cell in zip(annotate.__code__.co_freevars, annotate.__closure__, strict=True):
        cell_dict[name] = cell
        new_cell = None
        if allow_evaluation:
            try:
                cell.cell_contents
            except ValueError:
                pass
            else:
                new_cell = cell
        if new_cell is None:
            fwdref = _Stringifier(
                name,
                cell=cell,
                owner=owner,
                globals=annotate.__globals__,
                is_class=is_class,
                stringifier_dict=stringifier_dict,
            )
            stringifier_dict.stringifiers.append(fwdref)
            new_cell = types.CellType(fwdref)
        new_closure.append(new_cell)
    return tuple(new_closure), cell_dict


def _stringify_single(anno):
    if anno is ...:
        return "..."
    # We have to handle str specially to support PEP 563 stringified annotations.
    elif isinstance(anno, str):
        return anno
    elif isinstance(anno, _Template):
        return ast.unparse(_template_to_ast(anno))
    else:
        return repr(anno)


def get_annotate_from_class_namespace(obj):
    """Retrieve the annotate function from a class namespace dictionary.

    Return None if the namespace does not contain an annotate function.
    This is useful in metaclass ``__new__`` methods to retrieve the annotate function.
    """
    try:
        return obj["__annotate__"]
    except KeyError:
        return obj.get("__annotate_func__", None)


def get_annotations(
    obj, *, globals=None, locals=None, eval_str=False, format=Format.VALUE
):
    """Compute the annotations dict for an object.

    obj may be a callable, class, module, or other object with
    __annotate__ or __annotations__ attributes.
    Passing any other object raises TypeError.

    The *format* parameter controls the format in which annotations are returned,
    and must be a member of the Format enum or its integer equivalent.
    For the VALUE format, the __annotations__ is tried first; if it
    does not exist, the __annotate__ function is called. The
    FORWARDREF format uses __annotations__ if it exists and can be
    evaluated, and otherwise falls back to calling the __annotate__ function.
    The STRING format tries __annotate__ first, and falls back to
    using __annotations__, stringified using annotations_to_string().

    This function handles several details for you:

      * If eval_str is true, values of type str will
        be un-stringized using eval().  This is intended
        for use with stringized annotations
        ("from __future__ import annotations").
      * If obj doesn't have an annotations dict, returns an
        empty dict.  (Functions and methods always have an
        annotations dict; classes, modules, and other types of
        callables may not.)
      * Ignores inherited annotations on classes.  If a class
        doesn't have its own annotations dict, returns an empty dict.
      * All accesses to object members and dict values are done
        using getattr() and dict.get() for safety.
      * Always, always, always returns a freshly-created dict.

    eval_str controls whether or not values of type str are replaced
    with the result of calling eval() on those values:

      * If eval_str is true, eval() is called on values of type str.
      * If eval_str is false (the default), values of type str are unchanged.

    globals and locals are passed in to eval(); see the documentation
    for eval() for more information.  If either globals or locals is
    None, this function may replace that value with a context-specific
    default, contingent on type(obj):

      * If obj is a module, globals defaults to obj.__dict__.
      * If obj is a class, globals defaults to
        sys.modules[obj.__module__].__dict__ and locals
        defaults to the obj class namespace.
      * If obj is a callable, globals defaults to obj.__globals__,
        although if obj is a wrapped function (using
        functools.update_wrapper()) it is first unwrapped.
    """
    if eval_str and format != Format.VALUE:
        raise ValueError("eval_str=True is only supported with format=Format.VALUE")

    match format:
        case Format.VALUE:
            # For VALUE, we first look at __annotations__
            ann = _get_dunder_annotations(obj)

            # If it's not there, try __annotate__ instead
            if ann is None:
                ann = _get_and_call_annotate(obj, format)
        case Format.FORWARDREF:
            # For FORWARDREF, we use __annotations__ if it exists
            try:
                ann = _get_dunder_annotations(obj)
            except Exception:
                pass
            else:
                if ann is not None:
                    return dict(ann)

            # But if __annotations__ threw a NameError, we try calling __annotate__
            ann = _get_and_call_annotate(obj, format)
            if ann is None:
                # If that didn't work either, we have a very weird object: evaluating
                # __annotations__ threw NameError and there is no __annotate__. In that case,
                # we fall back to trying __annotations__ again.
                ann = _get_dunder_annotations(obj)
        case Format.STRING:
            # For STRING, we try to call __annotate__
            ann = _get_and_call_annotate(obj, format)
            if ann is not None:
                return dict(ann)
            # But if we didn't get it, we use __annotations__ instead.
            ann = _get_dunder_annotations(obj)
            if ann is not None:
                return annotations_to_string(ann)
        case Format.VALUE_WITH_FAKE_GLOBALS:
            raise ValueError("The VALUE_WITH_FAKE_GLOBALS format is for internal use only")
        case _:
            raise ValueError(f"Unsupported format {format!r}")

    if ann is None:
        if isinstance(obj, type) or callable(obj):
            return {}
        raise TypeError(f"{obj!r} does not have annotations")

    if not ann:
        return {}

    if not eval_str:
        return dict(ann)

    if globals is None or locals is None:
        if isinstance(obj, type):
            # class
            obj_globals = None
            module_name = getattr(obj, "__module__", None)
            if module_name:
                module = sys.modules.get(module_name, None)
                if module:
                    obj_globals = getattr(module, "__dict__", None)
            obj_locals = dict(vars(obj))
            unwrap = obj
        elif isinstance(obj, types.ModuleType):
            # module
            obj_globals = getattr(obj, "__dict__")
            obj_locals = None
            unwrap = None
        elif callable(obj):
            # this includes types.Function, types.BuiltinFunctionType,
            # types.BuiltinMethodType, functools.partial, functools.singledispatch,
            # "class funclike" from Lib/test/test_inspect... on and on it goes.
            obj_globals = getattr(obj, "__globals__", None)
            obj_locals = None
            unwrap = obj
        else:
            obj_globals = obj_locals = unwrap = None

        if unwrap is not None:
            # Use an id-based visited set to detect cycles in the __wrapped__
            # and functools.partial.func chain (e.g. f.__wrapped__ = f).
            # On cycle detection we stop and use whatever __globals__ we have
            # found so far, mirroring the approach of inspect.unwrap().
            _seen_ids = {id(unwrap)}
            while True:
                if hasattr(unwrap, "__wrapped__"):
                    candidate = unwrap.__wrapped__
                    if id(candidate) in _seen_ids:
                        break
                    _seen_ids.add(id(candidate))
                    unwrap = candidate
                    continue
                if functools := sys.modules.get("functools"):
                    if isinstance(unwrap, functools.partial):
                        candidate = unwrap.func
                        if id(candidate) in _seen_ids:
                            break
                        _seen_ids.add(id(candidate))
                        unwrap = candidate
                        continue
                break
            if hasattr(unwrap, "__globals__"):
                obj_globals = unwrap.__globals__

        if globals is None:
            globals = obj_globals
        if locals is None:
            locals = obj_locals

    # "Inject" type parameters into the local namespace
    # (unless they are shadowed by assignments *in* the local namespace),
    # as a way of emulating annotation scopes when calling `eval()`
    if type_params := getattr(obj, "__type_params__", ()):
        if locals is None:
            locals = {}
        locals = {param.__name__: param for param in type_params} | locals

    return_value = {
        key: value if not isinstance(value, str)
        else eval(_rewrite_star_unpack(value), globals, locals)
        for key, value in ann.items()
    }
    return return_value


def type_repr(value):
    """Convert a Python value to a format suitable for use with the STRING format.

    This is intended as a helper for tools that support the STRING format but do
    not have access to the code that originally produced the annotations. It uses
    repr() for most objects.

    """
    if isinstance(value, (type, types.FunctionType, types.BuiltinFunctionType)):
        if value.__module__ == "builtins":
            return value.__qualname__
        return f"{value.__module__}.{value.__qualname__}"
    elif isinstance(value, _Template):
        tree = _template_to_ast(value)
        return ast.unparse(tree)
    if value is ...:
        return "..."
    return repr(value)


def annotations_to_string(annotations):
    """Convert an annotation dict containing values to approximately the STRING format.

    Always returns a fresh a dictionary.
    """
    return {
        n: t if isinstance(t, str) else type_repr(t)
        for n, t in annotations.items()
    }


def _rewrite_star_unpack(arg):
    """If the given argument annotation expression is a star unpack e.g. `'*Ts'`
       rewrite it to a valid expression.
       """
    if arg.lstrip().startswith("*"):
        return f"({arg},)[0]"  # E.g. (*Ts,)[0] or (*tuple[int, int],)[0]
    else:
        return arg


def _get_and_call_annotate(obj, format):
    """Get the __annotate__ function and call it.

    May not return a fresh dictionary.
    """
    annotate = getattr(obj, "__annotate__", None)
    if annotate is not None:
        ann = call_annotate_function(annotate, format, owner=obj)
        if not isinstance(ann, dict):
            raise ValueError(f"{obj!r}.__annotate__ returned a non-dict")
        return ann
    return None


_BASE_GET_ANNOTATIONS = type.__dict__["__annotations__"].__get__


def _get_dunder_annotations(obj):
    """Return the annotations for an object, checking that it is a dictionary.

    Does not return a fresh dictionary.
    """
    # This special case is needed to support types defined under
    # from __future__ import annotations, where accessing the __annotations__
    # attribute directly might return annotations for the wrong class.
    if isinstance(obj, type):
        try:
            ann = _BASE_GET_ANNOTATIONS(obj)
        except AttributeError:
            # For static types, the descriptor raises AttributeError.
            return None
    else:
        ann = getattr(obj, "__annotations__", None)
        if ann is None:
            return None

    if not isinstance(ann, dict):
        raise ValueError(f"{obj!r}.__annotations__ is neither a dict nor None")
    return ann


class _ExtraNameFixer(ast.NodeTransformer):
    """Fixer for __extra_names__ items in ForwardRef __repr__ and string evaluation"""
    def __init__(self, extra_names):
        self.extra_names = extra_names

    def visit_Name(self, node: ast.Name):
        if (new_name := self.extra_names.get(node.id, _sentinel)) is not _sentinel:
            node = ast.Name(id=type_repr(new_name))
        return node
````

### ПУТЬ: Python/pythoncore-3.14-64/Lib/antigravity.py (17 строк, 517 байт)

````python

import webbrowser
import hashlib

webbrowser.open("https://xkcd.com/353/")

def geohash(latitude, longitude, datedow):
    '''Compute geohash() using the Munroe algorithm.

    >>> geohash(37.421542, -122.085589, b'2005-05-26-10458.68')
    37.857713 -122.544543

    '''
    # https://xkcd.com/426/
    h = hashlib.md5(datedow, usedforsecurity=False).hexdigest()
    p, q = [('%f' % float.fromhex('0.' + x)) for x in (h[:16], h[16:32])]
    print('%d%s %d%s' % (latitude, p[1:], longitude, q[1:]))
````

### ПУТЬ: Python/pythoncore-3.14-64/Lib/argparse.py (2786 строк, 109441 байт)

````python
# Author: Steven J. Bethard <steven.bethard@gmail.com>.
# New maintainer as of 29 August 2019:  Raymond Hettinger <raymond.hettinger@gmail.com>

"""Command-line parsing library

This module is an optparse-inspired command-line parsing library that:

    - handles both optional and positional arguments
    - produces highly informative usage messages
    - supports parsers that dispatch to sub-parsers

The following is a simple usage example that sums integers from the
command-line and writes the result to a file::

    parser = argparse.ArgumentParser(
        description='sum the integers at the command line')
    parser.add_argument(
        'integers', metavar='int', nargs='+', type=int,
        help='an integer to be summed')
    parser.add_argument(
        '--log',
        help='the file where the sum should be written')
    args = parser.parse_args()
    with (open(args.log, 'w') if args.log is not None
          else contextlib.nullcontext(sys.stdout)) as log:
        log.write('%s' % sum(args.integers))

The module contains the following public classes:

    - ArgumentParser -- The main entry point for command-line parsing. As the
        example above shows, the add_argument() method is used to populate
        the parser with actions for optional and positional arguments. Then
        the parse_args() method is invoked to convert the args at the
        command-line into an object with attributes.

    - ArgumentError -- The exception raised by ArgumentParser objects when
        there are errors with the parser's actions. Errors raised while
        parsing the command-line are caught by ArgumentParser and emitted
        as command-line messages.

    - FileType -- A factory for defining types of files to be created. As the
        example above shows, instances of FileType are typically passed as
        the type= argument of add_argument() calls. Deprecated since
        Python 3.14.

    - Action -- The base class for parser actions. Typically actions are
        selected by passing strings like 'store_true' or 'append_const' to
        the action= argument of add_argument(). However, for greater
        customization of ArgumentParser actions, subclasses of Action may
        be defined and passed as the action= argument.

    - HelpFormatter, RawDescriptionHelpFormatter, RawTextHelpFormatter,
        ArgumentDefaultsHelpFormatter -- Formatter classes which
        may be passed as the formatter_class= argument to the
        ArgumentParser constructor. HelpFormatter is the default,
        RawDescriptionHelpFormatter and RawTextHelpFormatter tell the parser
        not to change the formatting for help text, and
        ArgumentDefaultsHelpFormatter adds information about argument defaults
        to the help.

All other classes in this module are considered implementation details.
(Also note that HelpFormatter and RawDescriptionHelpFormatter are only
considered public as object names -- the API of the formatter objects is
still considered an implementation detail.)
"""

__version__ = '1.1'
__all__ = [
    'ArgumentParser',
    'ArgumentError',
    'ArgumentTypeError',
    'BooleanOptionalAction',
    'FileType',
    'HelpFormatter',
    'ArgumentDefaultsHelpFormatter',
    'RawDescriptionHelpFormatter',
    'RawTextHelpFormatter',
    'MetavarTypeHelpFormatter',
    'Namespace',
    'Action',
    'ONE_OR_MORE',
    'OPTIONAL',
    'PARSER',
    'REMAINDER',
    'SUPPRESS',
    'ZERO_OR_MORE',
]


import os as _os
import re as _re
import sys as _sys

from gettext import gettext as _, ngettext

SUPPRESS = '==SUPPRESS=='

OPTIONAL = '?'
ZERO_OR_MORE = '*'
ONE_OR_MORE = '+'
PARSER = 'A...'
REMAINDER = '...'
_UNRECOGNIZED_ARGS_ATTR = '_unrecognized_args'

# =============================
# Utility functions and classes
# =============================

class _AttributeHolder(object):
    """Abstract base class that provides __repr__.

    The __repr__ method returns a string in the format::
        ClassName(attr=name, attr=name, ...)
    The attributes are determined either by a class-level attribute,
    '_kwarg_names', or by inspecting the instance __dict__.
    """

    def __repr__(self):
        type_name = type(self).__name__
        arg_strings = []
        star_args = {}
        for arg in self._get_args():
            arg_strings.append(repr(arg))
        for name, value in self._get_kwargs():
            if name.isidentifier():
                arg_strings.append('%s=%r' % (name, value))
            else:
                star_args[name] = value
        if star_args:
            arg_strings.append('**%s' % repr(star_args))
        return '%s(%s)' % (type_name, ', '.join(arg_strings))

    def _get_kwargs(self):
        return list(self.__dict__.items())

    def _get_args(self):
        return []


def _copy_items(items):
    if items is None:
        return []
    # The copy module is used only in the 'append' and 'append_const'
    # actions, and it is needed only when the default value isn't a list.
    # Delay its import for speeding up the common case.
    if type(items) is list:
        return items[:]
    import copy
    return copy.copy(items)


def _identity(value):
    return value


# ===============
# Formatting Help
# ===============


class HelpFormatter(object):
    """Formatter for generating usage messages and argument help strings.

    Only the name of this class is considered a public API. All the methods
    provided by the class are considered an implementation detail.
    """

    def __init__(
        self,
        prog,
        indent_increment=2,
        max_help_position=24,
        width=None,
        color=True,
    ):
        # default setting for width
        if width is None:
            import shutil
            width = shutil.get_terminal_size().columns
            width -= 2

        self._set_color(color)
        self._prog = prog
        self._indent_increment = indent_increment
        self._max_help_position = min(max_help_position,
                                      max(width - 20, indent_increment * 2))
        self._width = width

        self._current_indent = 0
        self._level = 0
        self._action_max_length = 0

        self._root_section = self._Section(self, None)
        self._current_section = self._root_section

        self._whitespace_matcher = _re.compile(r'\s+', _re.ASCII)
        self._long_break_matcher = _re.compile(r'\n\n\n+')

    def _set_color(self, color):
        from _colorize import can_colorize, decolor, get_theme

        if color and can_colorize():
            self._theme = get_theme(force_color=True).argparse
            self._decolor = decolor
        else:
            self._theme = get_theme(force_no_color=True).argparse
            self._decolor = _identity

    # ===============================
    # Section and indentation methods
    # ===============================

    def _indent(self):
        self._current_indent += self._indent_increment
        self._level += 1

    def _dedent(self):
        self._current_indent -= self._indent_increment
        assert self._current_indent >= 0, 'Indent decreased below 0.'
        self._level -= 1

    class _Section(object):

        def __init__(self, formatter, parent, heading=None):
            self.formatter = formatter
            self.parent = parent
            self.heading = heading
            self.items = []

        def format_help(self):
            # format the indented section
            if self.parent is not None:
                self.formatter._indent()
            join = self.formatter._join_parts
            item_help = join([func(*args) for func, args in self.items])
            if self.parent is not None:
                self.formatter._dedent()

            # return nothing if the section was empty
            if not item_help:
                return ''

            # add the heading if the section was non-empty
            if self.heading is not SUPPRESS and self.heading is not None:
                current_indent = self.formatter._current_indent
                heading_text = _('%(heading)s:') % dict(heading=self.heading)
                t = self.formatter._theme
                heading = (
                    f'{" " * current_indent}'
                    f'{t.heading}{heading_text}{t.reset}\n'
                )
            else:
                heading = ''

            # join the section-initial newline, the heading and the help
            return join(['\n', heading, item_help, '\n'])

    def _add_item(self, func, args):
        self._current_section.items.append((func, args))

    # ========================
    # Message building methods
    # ========================

    def start_section(self, heading):
        self._indent()
        section = self._Section(self, self._current_section, heading)
        self._add_item(section.format_help, [])
        self._current_section = section

    def end_section(self):
        self._current_section = self._current_section.parent
        self._dedent()

    def add_text(self, text):
        if text is not SUPPRESS and text is not None:
            self._add_item(self._format_text, [text])

    def add_usage(self, usage, actions, groups, prefix=None):
        if usage is not SUPPRESS:
            args = usage, actions, groups, prefix
            self._add_item(self._format_usage, args)

    def add_argument(self, action):
        if action.help is not SUPPRESS:

            # find all invocations
            get_invocation = lambda x: self._decolor(self._format_action_invocation(x))
            invocation_lengths = [len(get_invocation(action)) + self._current_indent]
            for subaction in self._iter_indented_subactions(action):
                invocation_lengths.append(len(get_invocation(subaction)) + self._current_indent)

            # update the maximum item length
            action_length = max(invocation_lengths)
            self._action_max_length = max(self._action_max_length,
                                          action_length)

            # add the item to the list
            self._add_item(self._format_action, [action])

    def add_arguments(self, actions):
        for action in actions:
            self.add_argument(action)

    # =======================
    # Help-formatting methods
    # =======================

    def format_help(self):
        help = self._root_section.format_help()
        if help:
            help = self._long_break_matcher.sub('\n\n', help)
            help = help.strip('\n') + '\n'
        return help

    def _join_parts(self, part_strings):
        return ''.join([part
                        for part in part_strings
                        if part and part is not SUPPRESS])

    def _format_usage(self, usage, actions, groups, prefix):
        t = self._theme

        if prefix is None:
            prefix = _('usage: ')

        # if usage is specified, use that
        if usage is not None:
            usage = (
                t.prog_extra
                + usage
                % {"prog": f"{t.prog}{self._prog}{t.reset}{t.prog_extra}"}
                + t.reset
            )

        # if no optionals or positionals are available, usage is just prog
        elif usage is None and not actions:
            usage = f"{t.prog}{self._prog}{t.reset}"

        # if optionals and positionals are available, calculate usage
        elif usage is None:
            prog = '%(prog)s' % dict(prog=self._prog)

            parts, pos_start = self._get_actions_usage_parts(actions, groups)
            # build full usage string
            usage = ' '.join(filter(None, [prog, *parts]))

            # wrap the usage parts if it's too long
            text_width = self._width - self._current_indent
            if len(prefix) + len(self._decolor(usage)) > text_width:

                # break usage into wrappable parts
                opt_parts = parts[:pos_start]
                pos_parts = parts[pos_start:]

                # helper for wrapping lines
                def get_lines(parts, indent, prefix=None):
                    lines = []
                    line = []
                    indent_length = len(indent)
                    if prefix is not None:
                        line_len = len(prefix) - 1
                    else:
                        line_len = indent_length - 1
                    for part in parts:
                        part_len = len(self._decolor(part))
                        if line_len + 1 + part_len > text_width and line:
                            lines.append(indent + ' '.join(line))
                            line = []
                            line_len = indent_length - 1
                        line.append(part)
                        line_len += part_len + 1
                    if line:
                        lines.append(indent + ' '.join(line))
                    if prefix is not None:
                        lines[0] = lines[0][indent_length:]
                    return lines

                # if prog is short, follow it with optionals or positionals
                prog_len = len(self._decolor(prog))
                if len(prefix) + prog_len <= 0.75 * text_width:
                    indent = ' ' * (len(prefix) + prog_len + 1)
                    if opt_parts:
                        lines = get_lines([prog] + opt_parts, indent, prefix)
                        lines.extend(get_lines(pos_parts, indent))
                    elif pos_parts:
                        lines = get_lines([prog] + pos_parts, indent, prefix)
                    else:
                        lines = [prog]

                # if prog is long, put it on its own line
                else:
                    indent = ' ' * len(prefix)
                    parts = opt_parts + pos_parts
                    lines = get_lines(parts, indent)
                    if len(lines) > 1:
                        lines = []
                        lines.extend(get_lines(opt_parts, indent))
                        lines.extend(get_lines(pos_parts, indent))
                    lines = [prog] + lines

                # join lines into usage
                usage = '\n'.join(lines)

            usage = usage.removeprefix(prog)
            usage = f"{t.prog}{prog}{t.reset}{usage}"

        # prefix with 'usage:'
        return f'{t.usage}{prefix}{t.reset}{usage}\n\n'

    def _is_long_option(self, string):
        return len(string) > 2

    def _get_actions_usage_parts(self, actions, groups):
        """Get usage parts with split index for optionals/positionals.

        Returns (parts, pos_start) where pos_start is the index in parts
        where positionals begin.
        This preserves mutually exclusive group formatting across the
        optionals/positionals boundary (gh-75949).
        """
        actions = [action for action in actions if action.help is not SUPPRESS]
        # group actions by mutually exclusive groups
        action_groups = dict.fromkeys(actions)
        for group in groups:
            for action in group._group_actions:
                if action in action_groups:
                    action_groups[action] = group
        # positional arguments keep their position
        positionals = []
        for action in actions:
            if not action.option_strings:
                group = action_groups.pop(action)
                if group:
                    group_actions = [
                        action2 for action2 in group._group_actions
                        if action2.option_strings and
                           action_groups.pop(action2, None)
                    ] + [action]
                    positionals.append((group.required, group_actions))
                else:
                    positionals.append((None, [action]))
        # the remaining optional arguments are sorted by the position of
        # the first option in the group
        optionals = []
        for action in actions:
            if action.option_strings and action in action_groups:
                group = action_groups.pop(action)
                if group:
                    group_actions = [action] + [
                        action2 for action2 in group._group_actions
                        if action2.option_strings and
                           action_groups.pop(action2, None)
                    ]
                    optionals.append((group.required, group_actions))
                else:
                    optionals.append((None, [action]))

        # collect all actions format strings
        parts = []
        t = self._theme
        pos_start = None
        for i, (required, group) in enumerate(optionals + positionals):
            start = len(parts)
            if i == len(optionals):
                pos_start = start
            in_group = len(group) > 1
            for action in group:
                # produce all arg strings
                if not action.option_strings:
                    default = self._get_default_metavar_for_positional(action)
                    part = self._format_args(action, default)
                    # if it's in a group, strip the outer []
                    if in_group:
                        if part[0] == '[' and part[-1] == ']':
                            part = part[1:-1]
                    part = t.summary_action + part + t.reset

                # produce the first way to invoke the option in brackets
                else:
                    option_string = action.option_strings[0]
                    if self._is_long_option(option_string):
                        option_color = t.summary_long_option
                    else:
                        option_color = t.summary_short_option

                    # if the Optional doesn't take a value, format is:
                    #    -s or --long
                    if action.nargs == 0:
                        part = action.format_usage()
                        part = f"{option_color}{part}{t.reset}"

                    # if the Optional takes a value, format is:
                    #    -s ARGS or --long ARGS
                    else:
                        default = self._get_default_metavar_for_optional(action)
                        args_string = self._format_args(action, default)
                        part = (
                            f"{option_color}{option_string} "
                            f"{t.summary_label}{args_string}{t.reset}"
                        )

                    # make it look optional if it's not required or in a group
                    if not (action.required or required or in_group):
                        part = '[%s]' % part

                # add the action string to the list
                parts.append(part)

            if in_group:
                parts[start] = ('(' if required else '[') + parts[start]
                for i in range(start, len(parts) - 1):
                    parts[i] += ' |'
                parts[-1] += ')' if required else ']'

        if pos_start is None:
            pos_start = len(parts)
        return parts, pos_start

    def _format_text(self, text):
        if '%(prog)' in text:
            text = text % dict(prog=self._prog)
        text_width = max(self._width - self._current_indent, 11)
        indent = ' ' * self._current_indent
        return self._fill_text(text, text_width, indent) + '\n\n'

    def _format_action(self, action):
        # determine the required width and the entry label
        help_position = min(self._action_max_length + 2,
                            self._max_help_position)
        help_width = max(self._width - help_position, 11)
        action_width = help_position - self._current_indent - 2
        action_header = self._format_action_invocation(action)
        action_header_no_color = self._decolor(action_header)

        # no help; start on same line and add a final newline
        if not action.help:
            tup = self._current_indent, '', action_header
            action_header = '%*s%s\n' % tup

        # short action name; start on the same line and pad two spaces
        elif len(action_header_no_color) <= action_width:
            # calculate widths without color codes
            action_header_color = action_header
            tup = self._current_indent, '', action_width, action_header_no_color
            action_header = '%*s%-*s  ' % tup
            # swap in the colored header
            action_header = action_header.replace(
                action_header_no_color, action_header_color
            )
            indent_first = 0

        # long action name; start on the next line
        else:
            tup = self._current_indent, '', action_header
            action_header = '%*s%s\n' % tup
            indent_first = help_position

        # collect the pieces of the action help
        parts = [action_header]

        # if there was help for the action, add lines of help text
        if action.help and action.help.strip():
            help_text = self._expand_help(action)
            if help_text:
                help_lines = self._split_lines(help_text, help_width)
                parts.append('%*s%s\n' % (indent_first, '', help_lines[0]))
                for line in help_lines[1:]:
                    parts.append('%*s%s\n' % (help_position, '', line))

        # or add a newline if the description doesn't end with one
        elif not action_header.endswith('\n'):
            parts.append('\n')

        # if there are any sub-actions, add their help as well
        for subaction in self._iter_indented_subactions(action):
            parts.append(self._format_action(subaction))

        # return a single string
        return self._join_parts(parts)

    def _format_action_invocation(self, action):
        t = self._theme

        if not action.option_strings:
            default = self._get_default_metavar_for_positional(action)
            return (
                t.action
                + ' '.join(self._metavar_formatter(action, default)(1))
                + t.reset
            )

        else:

            def color_option_strings(strings):
                parts = []
                for s in strings:
                    if self._is_long_option(s):
                        parts.append(f"{t.long_option}{s}{t.reset}")
                    else:
                        parts.append(f"{t.short_option}{s}{t.reset}")
                return parts

            # if the Optional doesn't take a value, format is:
            #    -s, --long
            if action.nargs == 0:
                option_strings = color_option_strings(action.option_strings)
                return ', '.join(option_strings)

            # if the Optional takes a value, format is:
            #    -s, --long ARGS
            else:
                default = self._get_default_metavar_for_optional(action)
                option_strings = color_option_strings(action.option_strings)
                args_string = (
                    f"{t.label}{self._format_args(action, default)}{t.reset}"
                )
                return ', '.join(option_strings) + ' ' + args_string

    def _metavar_formatter(self, action, default_metavar):
        if action.metavar is not None:
            result = action.metavar
        elif action.choices is not None:
            result = '{%s}' % ','.join(map(str, action.choices))
        else:
            result = default_metavar

        def format(tuple_size):
            if isinstance(result, tuple):
                return result
            else:
                return (result, ) * tuple_size
        return format

    def _format_args(self, action, default_metavar):
        get_metavar = self._metavar_formatter(action, default_metavar)
        if action.nargs is None:
            result = '%s' % get_metavar(1)
        elif action.nargs == OPTIONAL:
            result = '[%s]' % get_metavar(1)
        elif action.nargs == ZERO_OR_MORE:
            metavar = get_metavar(1)
            if len(metavar) == 2:
                result = '[%s [%s ...]]' % metavar
            else:
                result = '[%s ...]' % metavar
        elif action.nargs == ONE_OR_MORE:
            result = '%s [%s ...]' % get_metavar(2)
        elif action.nargs == REMAINDER:
            result = '...'
        elif action.nargs == PARSER:
            result = '%s ...' % get_metavar(1)
        elif action.nargs == SUPPRESS:
            result = ''
        else:
            try:
                formats = ['%s' for _ in range(action.nargs)]
            except TypeError:
                raise ValueError("invalid nargs value") from None
            result = ' '.join(formats) % get_metavar(action.nargs)
        return result

    def _expand_help(self, action):
        help_string = self._get_help_string(action)
        if '%' not in help_string:
            return help_string
        params = dict(vars(action), prog=self._prog)
        for name in list(params):
            value = params[name]
            if value is SUPPRESS:
                del params[name]
            elif hasattr(value, '__name__'):
                params[name] = value.__name__
        if params.get('choices') is not None:
            params['choices'] = ', '.join(map(str, params['choices']))
        return help_string % params

    def _iter_indented_subactions(self, action):
        try:
            get_subactions = action._get_subactions
        except AttributeError:
            pass
        else:
            self._indent()
            yield from get_subactions()
            self._dedent()

    def _split_lines(self, text, width):
        text = self._whitespace_matcher.sub(' ', text).strip()
        # The textwrap module is used only for formatting help.
        # Delay its import for speeding up the common usage of argparse.
        import textwrap
        return textwrap.wrap(text, width)

    def _fill_text(self, text, width, indent):
        text = self._whitespace_matcher.sub(' ', text).strip()
        import textwrap
        return textwrap.fill(text, width,
                             initial_indent=indent,
                             subsequent_indent=indent)

    def _get_help_string(self, action):
        return action.help

    def _get_default_metavar_for_optional(self, action):
        return action.dest.upper()

    def _get_default_metavar_for_positional(self, action):
        return action.dest


class RawDescriptionHelpFormatter(HelpFormatter):
    """Help message formatter which retains any formatting in descriptions.

    Only the name of this class is considered a public API. All the methods
    provided by the class are considered an implementation detail.
    """

    def _fill_text(self, text, width, indent):
        return ''.join(indent + line for line in text.splitlines(keepends=True))


class RawTextHelpFormatter(RawDescriptionHelpFormatter):
    """Help message formatter which retains formatting of all help text.

    Only the name of this class is considered a public API. All the methods
    provided by the class are considered an implementation detail.
    """

    def _split_lines(self, text, width):
        return text.splitlines()


class ArgumentDefaultsHelpFormatter(HelpFormatter):
    """Help message formatter which adds default values to argument help.

    Only the name of this class is considered a public API. All the methods
    provided by the class are considered an implementation detail.
    """

    def _get_help_string(self, action):
        help = action.help
        if help is None:
            help = ''

        if (
            '%(default)' not in help
            and action.default is not SUPPRESS
            and not action.required
        ):
            defaulting_nargs = (OPTIONAL, ZERO_OR_MORE)
            if action.option_strings or action.nargs in defaulting_nargs:
                help += _(' (default: %(default)s)')
        return help



class MetavarTypeHelpFormatter(HelpFormatter):
    """Help message formatter which uses the argument 'type' as the default
    metavar value (instead of the argument 'dest')

    Only the name of this class is considered a public API. All the methods
    provided by the class are considered an implementation detail.
    """

    def _get_default_metavar_for_optional(self, action):
        return action.type.__name__

    def _get_default_metavar_for_positional(self, action):
        return action.type.__name__


# =====================
# Options and Arguments
# =====================

def _get_action_name(argument):
    if argument is None:
        return None
    elif argument.option_strings:
        return '/'.join(argument.option_strings)
    elif argument.metavar not in (None, SUPPRESS):
        metavar = argument.metavar
        if not isinstance(metavar, tuple):
            return metavar
        if argument.nargs == ZERO_OR_MORE and len(metavar) == 2:
            return '%s[, %s]' % metavar
        elif argument.nargs == ONE_OR_MORE:
            return '%s[, %s]' % metavar
        else:
            return ', '.join(metavar)
    elif argument.dest not in (None, SUPPRESS):
        return argument.dest
    elif argument.choices:
        return '{%s}' % ','.join(map(str, argument.choices))
    else:
        return None


class ArgumentError(Exception):
    """An error from creating or using an argument (optional or positional).

    The string value of this exception is the message, augmented with
    information about the argument that caused it.
    """

    def __init__(self, argument, message):
        self.argument_name = _get_action_name(argument)
        self.message = message

    def __str__(self):
        if self.argument_name is None:
            format = '%(message)s'
        else:
            format = _('argument %(argument_name)s: %(message)s')
        return format % dict(message=self.message,
                             argument_name=self.argument_name)


class ArgumentTypeError(Exception):
    """An error from trying to convert a command line string to a type."""
    pass


# ==============
# Action classes
# ==============

class Action(_AttributeHolder):
    """Information about how to convert command line strings to Python objects.

    Action objects are used by an ArgumentParser to represent the information
    needed to parse a single argument from one or more strings from the
    command line. The keyword arguments to the Action constructor are also
    all attributes of Action instances.

    Keyword Arguments:

        - option_strings -- A list of command-line option strings which
            should be associated with this action.

        - dest -- The name of the attribute to hold the created object(s)

        - nargs -- The number of command-line arguments that should be
            consumed. By default, one argument will be consumed and a single
            value will be produced.  Other values include:
                - N (an integer) consumes N arguments (and produces a list)
                - '?' consumes zero or one arguments
                - '*' consumes zero or more arguments (and produces a list)
                - '+' consumes one or more arguments (and produces a list)
            Note that the difference between the default and nargs=1 is that
            with the default, a single value will be produced, while with
            nargs=1, a list containing a single value will be produced.

        - const -- The value to be produced if the option is specified and the
            option uses an action that takes no values.

        - default -- The value to be produced if the option is not specified.

        - type -- A callable that accepts a single string argument, and
            returns the converted value.  The standard Python types str, int,
            float, and complex are useful examples of such callables.  If None,
            str is used.

        - choices -- A container of values that should be allowed. If not None,
            after a command-line argument has been converted to the appropriate
            type, an exception will be raised if it is not a member of this
            collection.

        - required -- True if the action must always be specified at the
            command line. This is only meaningful for optional command-line
            arguments.

        - help -- The help string describing the argument.

        - metavar -- The name to be used for the option's argument with the
            help string. If None, the 'dest' value will be used as the name.
    """

    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=None,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None,
                 deprecated=False):
        self.option_strings = option_strings
        self.dest = dest
        self.nargs = nargs
        self.const = const
        self.default = default
        self.type = type
        self.choices = choices
        self.required = required
        self.help = help
        self.metavar = metavar
        self.deprecated = deprecated

    def _get_kwargs(self):
        names = [
            'option_strings',
            'dest',
            'nargs',
            'const',
            'default',
            'type',
            'choices',
            'required',
            'help',
            'metavar',
            'deprecated',
        ]
        return [(name, getattr(self, name)) for name in names]

    def format_usage(self):
        return self.option_strings[0]

    def __call__(self, parser, namespace, values, option_string=None):
        raise NotImplementedError('.__call__() not defined')


class BooleanOptionalAction(Action):
    def __init__(self,
                 option_strings,
                 dest,
                 default=None,
                 required=False,
                 help=None,
                 deprecated=False):

        _option_strings = []
        for option_string in option_strings:
            _option_strings.append(option_string)

            if option_string.startswith('--'):
                if option_string.startswith('--no-'):
                    raise ValueError(f'invalid option name {option_string!r} '
                                     f'for BooleanOptionalAction')
                option_string = '--no-' + option_string[2:]
                _option_strings.append(option_string)

        super().__init__(
            option_strings=_option_strings,
            dest=dest,
            nargs=0,
            default=default,
            required=required,
            help=help,
            deprecated=deprecated)


    def __call__(self, parser, namespace, values, option_string=None):
        if option_string in self.option_strings:
            setattr(namespace, self.dest, not option_string.startswith('--no-'))

    def format_usage(self):
        return ' | '.join(self.option_strings)


class _StoreAction(Action):

    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=None,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None,
                 deprecated=False):
        if nargs == 0:
            raise ValueError('nargs for store actions must be != 0; if you '
                             'have nothing to store, actions such as store '
                             'true or store const may be more appropriate')
        if const is not None and nargs != OPTIONAL:
            raise ValueError('nargs must be %r to supply const' % OPTIONAL)
        super(_StoreAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar,
            deprecated=deprecated)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)


class _StoreConstAction(Action):

    def __init__(self,
                 option_strings,
                 dest,
                 const=None,
                 default=None,
                 required=False,
                 help=None,
                 metavar=None,
                 deprecated=False):
        super(_StoreConstAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            const=const,
            default=default,
            required=required,
            help=help,
            deprecated=deprecated)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, self.const)


class _StoreTrueAction(_StoreConstAction):

    def __init__(self,
                 option_strings,
                 dest,
                 default=False,
                 required=False,
                 help=None,
                 deprecated=False):
        super(_StoreTrueAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            const=True,
            deprecated=deprecated,
            required=required,
            help=help,
            default=default)


class _StoreFalseAction(_StoreConstAction):

    def __init__(self,
                 option_strings,
                 dest,
                 default=True,
                 required=False,
                 help=None,
                 deprecated=False):
        super(_StoreFalseAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            const=False,
            default=default,
            required=required,
            help=help,
            deprecated=deprecated)


class _AppendAction(Action):

    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=None,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None,
                 deprecated=False):
        if nargs == 0:
            raise ValueError('nargs for append actions must be != 0; if arg '
                             'strings are not supplying the value to append, '
                             'the append const action may be more appropriate')
        if const is not None and nargs != OPTIONAL:
            raise ValueError('nargs must be %r to supply const' % OPTIONAL)
        super(_AppendAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar,
            deprecated=deprecated)

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, None)
        items = _copy_items(items)
        items.append(values)
        setattr(namespace, self.dest, items)


class _AppendConstAction(Action):

    def __init__(self,
                 option_strings,
                 dest,
                 const=None,
                 default=None,
                 required=False,
                 help=None,
                 metavar=None,
                 deprecated=False):
        super(_AppendConstAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            const=const,
            default=default,
            required=required,
            help=help,
            metavar=metavar,
            deprecated=deprecated)

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, None)
        items = _copy_items(items)
        items.append(self.const)
        setattr(namespace, self.dest, items)


class _CountAction(Action):

    def __init__(self,
                 option_strings,
                 dest,
                 default=None,
                 required=False,
                 help=None,
                 deprecated=False):
        super(_CountAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            default=default,
            required=required,
            help=help,
            deprecated=deprecated)

    def __call__(self, parser, namespace, values, option_string=None):
        count = getattr(namespace, self.dest, None)
        if count is None:
            count = 0
        setattr(namespace, self.dest, count + 1)


class _HelpAction(Action):

    def __init__(self,
                 option_strings,
                 dest=SUPPRESS,
                 default=SUPPRESS,
                 help=None,
                 deprecated=False):
        super(_HelpAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
            deprecated=deprecated)

    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_help()
        parser.exit()


class _VersionAction(Action):

    def __init__(self,
                 option_strings,
                 version=None,
                 dest=SUPPRESS,
                 default=SUPPRESS,
                 help=None,
                 deprecated=False):
        if help is None:
            help = _("show program's version number and exit")
        super(_VersionAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help)
        self.version = version

    def __call__(self, parser, namespace, values, option_string=None):
        version = self.version
        if version is None:
            version = parser.version
        formatter = parser._get_formatter()
        formatter.add_text(version)
        parser._print_message(formatter.format_help(), _sys.stdout)
        parser.exit()


class _SubParsersAction(Action):

    class _ChoicesPseudoAction(Action):

        def __init__(self, name, aliases, help):
            metavar = dest = name
            if aliases:
                metavar += ' (%s)' % ', '.join(aliases)
            sup = super(_SubParsersAction._ChoicesPseudoAction, self)
            sup.__init__(option_strings=[], dest=dest, help=help,
                         metavar=metavar)

    def __init__(self,
                 option_strings,
                 prog,
                 parser_class,
                 dest=SUPPRESS,
                 required=False,
                 help=None,
                 metavar=None):

        self._prog_prefix = prog
        self._parser_class = parser_class
        self._name_parser_map = {}
        self._choices_actions = []
        self._deprecated = set()
        self._color = True

        super(_SubParsersAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=PARSER,
            choices=self._name_parser_map,
            required=required,
            help=help,
            metavar=metavar)

    def add_parser(self, name, *, deprecated=False, **kwargs):
        # set prog from the existing prefix
        if kwargs.get('prog') is None:
            kwargs['prog'] = '%s %s' % (self._prog_prefix, name)

        # set color
        if kwargs.get('color') is None:
            kwargs['color'] = self._color

        aliases = kwargs.pop('aliases', ())

        if name in self._name_parser_map:
            raise ValueError(f'conflicting subparser: {name}')
        for alias in aliases:
            if alias in self._name_parser_map:
                raise ValueError(f'conflicting subparser alias: {alias}')

        # create a pseudo-action to hold the choice help
        if 'help' in kwargs:
            help = kwargs.pop('help')
            choice_action = self._ChoicesPseudoAction(name, aliases, help)
            self._choices_actions.append(choice_action)
        else:
            choice_action = None

        # create the parser and add it to the map
        parser = self._parser_class(**kwargs)
        if choice_action is not None:
            parser._check_help(choice_action)
        self._name_parser_map[name] = parser

        # make parser available under aliases also
        for alias in aliases:
            self._name_parser_map[alias] = parser

        if deprecated:
            self._deprecated.add(name)
            self._deprecated.update(aliases)

        return parser

    def _get_subactions(self):
        return self._choices_actions

    def __call__(self, parser, namespace, values, option_string=None):
        parser_name = values[0]
        arg_strings = values[1:]

        # set the parser name if requested
        if self.dest is not SUPPRESS:
            setattr(namespace, self.dest, parser_name)

        # select the parser
        try:
            subparser = self._name_parser_map[parser_name]
        except KeyError:
            args = {'parser_name': parser_name,
                    'choices': ', '.join(self._name_parser_map)}
            msg = _('unknown parser %(parser_name)r (choices: %(choices)s)') % args
            raise ArgumentError(self, msg)

        if parser_name in self._deprecated:
            parser._warning(_("command '%(parser_name)s' is deprecated") %
                            {'parser_name': parser_name})

        # parse all the remaining options into the namespace
        # store any unrecognized options on the object, so that the top
        # level parser can decide what to do with them

        # In case this subparser defines new defaults, we parse them
        # in a new namespace object and then update the original
        # namespace for the relevant parts.
        subnamespace, arg_strings = subparser.parse_known_args(arg_strings, None)
        for key, value in vars(subnamespace).items():
            setattr(namespace, key, value)

        if arg_strings:
            if not hasattr(namespace, _UNRECOGNIZED_ARGS_ATTR):
                setattr(namespace, _UNRECOGNIZED_ARGS_ATTR, [])
            getattr(namespace, _UNRECOGNIZED_ARGS_ATTR).extend(arg_strings)

class _ExtendAction(_AppendAction):
    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, None)
        items = _copy_items(items)
        items.extend(values)
        setattr(namespace, self.dest, items)

# ==============
# Type classes
# ==============

class FileType(object):
    """Deprecated factory for creating file object types

    Instances of FileType are typically passed as type= arguments to the
    ArgumentParser add_argument() method.

    Keyword Arguments:
        - mode -- A string indicating how the file is to be opened. Accepts the
            same values as the builtin open() function.
        - bufsize -- The file's desired buffer size. Accepts the same values as
            the builtin open() function.
        - encoding -- The file's encoding. Accepts the same values as the
            builtin open() function.
        - errors -- A string indicating how encoding and decoding errors are to
            be handled. Accepts the same value as the builtin open() function.
    """

    def __init__(self, mode='r', bufsize=-1, encoding=None, errors=None):
        import warnings
        warnings.warn(
            "FileType is deprecated. Simply open files after parsing arguments.",
            category=PendingDeprecationWarning,
            stacklevel=2
        )
        self._mode = mode
        self._bufsize = bufsize
        self._encoding = encoding
        self._errors = errors

    def __call__(self, string):
        # the special argument "-" means sys.std{in,out}
        if string == '-':
            if 'r' in self._mode:
                return _sys.stdin.buffer if 'b' in self._mode else _sys.stdin
            elif any(c in self._mode for c in 'wax'):
                return _sys.stdout.buffer if 'b' in self._mode else _sys.stdout
            else:
                msg = _('argument "-" with mode %r') % self._mode
                raise ValueError(msg)

        # all other arguments are used as file names
        try:
            return open(string, self._mode, self._bufsize, self._encoding,
                        self._errors)
        except OSError as e:
            args = {'filename': string, 'error': e}
            message = _("can't open '%(filename)s': %(error)s")
            raise ArgumentTypeError(message % args)

    def __repr__(self):
        args = self._mode, self._bufsize
        kwargs = [('encoding', self._encoding), ('errors', self._errors)]
        args_str = ', '.join([repr(arg) for arg in args if arg != -1] +
                             ['%s=%r' % (kw, arg) for kw, arg in kwargs
                              if arg is not None])
        return '%s(%s)' % (type(self).__name__, args_str)

# ===========================
# Optional and Positional Parsing
# ===========================

class Namespace(_AttributeHolder):
    """Simple object for storing attributes.

    Implements equality by attribute names and values, and provides a simple
    string representation.
    """

    def __init__(self, **kwargs):
        for name in kwargs:
            setattr(self, name, kwargs[name])

    def __eq__(self, other):
        if not isinstance(other, Namespace):
            return NotImplemented
        return vars(self) == vars(other)

    def __contains__(self, key):
        return key in self.__dict__


class _ActionsContainer(object):

    def __init__(self,
                 description,
                 prefix_chars,
                 argument_default,
                 conflict_handler):
        super(_ActionsContainer, self).__init__()

        self.description = description
        self.argument_default = argument_default
        self.prefix_chars = prefix_chars
        self.conflict_handler = conflict_handler

        # set up registries
        self._registries = {}

        # register actions
        self.register('action', None, _StoreAction)
        self.register('action', 'store', _StoreAction)
        self.register('action', 'store_const', _StoreConstAction)
        self.register('action', 'store_true', _StoreTrueAction)
        self.register('action', 'store_false', _StoreFalseAction)
        self.register('action', 'append', _AppendAction)
        self.register('action', 'append_const', _AppendConstAction)
        self.register('action', 'count', _CountAction)
        self.register('action', 'help', _HelpAction)
        self.register('action', 'version', _VersionAction)
        self.register('action', 'parsers', _SubParsersAction)
        self.register('action', 'extend', _ExtendAction)

        # raise an exception if the conflict handler is invalid
        self._get_handler()

        # action storage
        self._actions = []
        self._option_string_actions = {}

        # groups
        self._action_groups = []
        self._mutually_exclusive_groups = []

        # defaults storage
        self._defaults = {}

        # determines whether an "option" looks like a negative number
        self._negative_number_matcher = _re.compile(r'-\.?\d')

        # whether or not there are any optionals that look like negative
        # numbers -- uses a list so it can be shared and edited
        self._has_negative_number_optionals = []

    # ====================
    # Registration methods
    # ====================

    def register(self, registry_name, value, object):
        registry = self._registries.setdefault(registry_name, {})
        registry[value] = object

    def _registry_get(self, registry_name, value, default=None):
        return self._registries[registry_name].get(value, default)

    # ==================================
    # Namespace default accessor methods
    # ==================================

    def set_defaults(self, **kwargs):
        self._defaults.update(kwargs)

        # if these defaults match any existing arguments, replace
        # the previous default on the object with the new one
        for action in self._actions:
            if action.dest in kwargs:
                action.default = kwargs[action.dest]

    def get_default(self, dest):
        for action in self._actions:
            if action.dest == dest and action.default is not None:
                return action.default
        return self._defaults.get(dest, None)


    # =======================
    # Adding argument actions
    # =======================

    def add_argument(self, *args, **kwargs):
        """
        add_argument(dest, ..., name=value, ...)
        add_argument(option_string, option_string, ..., name=value, ...)
        """

        # if no positional args are supplied or only one is supplied and
        # it doesn't look like an option string, parse a positional
        # argument
        chars = self.prefix_chars
        if not args or len(args) == 1 and args[0][0] not in chars:
            if args and 'dest' in kwargs:
                raise TypeError('dest supplied twice for positional argument,'
                                ' did you mean metavar?')
            kwargs = self._get_positional_kwargs(*args, **kwargs)

        # otherwise, we're adding an optional argument
        else:
            kwargs = self._get_optional_kwargs(*args, **kwargs)

        # if no default was supplied, use the parser-level default
        if 'default' not in kwargs:
            dest = kwargs['dest']
            if dest in self._defaults:
                kwargs['default'] = self._defaults[dest]
            elif self.argument_default is not None:
                kwargs['default'] = self.argument_default

        # create the action object, and add it to the parser
        action_name = kwargs.get('action')
        action_class = self._pop_action_class(kwargs)
        if not callable(action_class):
            raise ValueError(f'unknown action {action_class!r}')
        action = action_class(**kwargs)

        # raise an error if action for positional argument does not
        # consume arguments
        if not action.option_strings and action.nargs == 0:
            raise ValueError(f'action {action_name!r} is not valid for positional arguments')

        # raise an error if the action type is not callable
        type_func = self._registry_get('type', action.type, action.type)
        if not callable(type_func):
            raise TypeError(f'{type_func!r} is not callable')

        if type_func is FileType:
            raise TypeError(f'{type_func!r} is a FileType class object, '
                            f'instance of it must be passed')

        # raise an error if the metavar does not match the type
        if hasattr(self, "_get_validation_formatter"):
            formatter = self._get_validation_formatter()
            try:
                formatter._format_args(action, None)
            except TypeError:
                raise ValueError("length of metavar tuple does not match nargs")
        self._check_help(action)
        return self._add_action(action)

    def add_argument_group(self, *args, **kwargs):
        group = _ArgumentGroup(self, *args, **kwargs)
        self._action_groups.append(group)
        return group

    def add_mutually_exclusive_group(self, **kwargs):
        group = _MutuallyExclusiveGroup(self, **kwargs)
        self._mutually_exclusive_groups.append(group)
        return group

    def _add_action(self, action):
        # resolve any conflicts
        self._check_conflict(action)

        # add to actions list
        self._actions.append(action)
        action.container = self

        # index the action by any option strings it has
        for option_string in action.option_strings:
            self._option_string_actions[option_string] = action

        # set the flag if any option strings look like negative numbers
        for option_string in action.option_strings:
            if self._negative_number_matcher.match(option_string):
                if not self._has_negative_number_optionals:
                    self._has_negative_number_optionals.append(True)

        # return the created action
        return action

    def _remove_action(self, action):
        self._actions.remove(action)

    def _add_container_actions(self, container):
        # collect groups by titles
        title_group_map = {}
        for group in self._action_groups:
            if group.title in title_group_map:
                # This branch could happen if a derived class added
                # groups with duplicated titles in __init__
                msg = f'cannot merge actions - two groups are named {group.title!r}'
                raise ValueError(msg)
            title_group_map[group.title] = group

        # map each action to its group
        group_map = {}
        for group in container._action_groups:

            # if a group with the title exists, use that, otherwise
            # create a new group matching the container's group
            if group.title not in title_group_map:
                title_group_map[group.title] = self.add_argument_group(
                    title=group.title,
                    description=group.description,
                    conflict_handler=group.conflict_handler)

            # map the actions to their new group
            for action in group._group_actions:
                group_map[action] = title_group_map[group.title]

        # add container's mutually exclusive groups
        # NOTE: if add_mutually_exclusive_group ever gains title= and
        # description= then this code will need to be expanded as above
        for group in container._mutually_exclusive_groups:
            if group._container is container:
                cont = self
            else:
                cont = title_group_map[group._container.title]
            mutex_group = cont.add_mutually_exclusive_group(
                required=group.required)

            # map the actions to their new mutex group
            for action in group._group_actions:
                group_map[action] = mutex_group

        # add all actions to this container or their group
        for action in container._actions:
            group_map.get(action, self)._add_action(action)

    def _get_positional_kwargs(self, dest, **kwargs):
        # make sure required is not specified
        if 'required' in kwargs:
            msg = "'required' is an invalid argument for positionals"
            raise TypeError(msg)

        # mark positional arguments as required if at least one is
        # always required
        nargs = kwargs.get('nargs')
        if nargs == 0:
            raise ValueError('nargs for positionals must be != 0')
        if nargs not in [OPTIONAL, ZERO_OR_MORE, REMAINDER, SUPPRESS]:
            kwargs['required'] = True

        # return the keyword arguments with no option strings
        return dict(kwargs, dest=dest, option_strings=[])

    def _get_optional_kwargs(self, *args, **kwargs):
        # determine short and long option strings
        option_strings = []
        long_option_strings = []
        for option_string in args:
            # error on strings that don't start with an appropriate prefix
            if not option_string[0] in self.prefix_chars:
                raise ValueError(
                    f'invalid option string {option_string!r}: '
                    f'must start with a character {self.prefix_chars!r}')

            # strings starting with two prefix characters are long options
            option_strings.append(option_string)
            if len(option_string) > 1 and option_string[1] in self.prefix_chars:
                long_option_strings.append(option_string)

        # infer destination, '--foo-bar' -> 'foo_bar' and '-x' -> 'x'
        dest = kwargs.pop('dest', None)
        if dest is None:
            if long_option_strings:
                dest_option_string = long_option_strings[0]
            else:
                dest_option_string = option_strings[0]
            dest = dest_option_string.lstrip(self.prefix_chars)
            if not dest:
                msg = f'dest= is required for options like {option_string!r}'
                raise TypeError(msg)
            dest = dest.replace('-', '_')

        # return the updated keyword arguments
        return dict(kwargs, dest=dest, option_strings=option_strings)

    def _pop_action_class(self, kwargs, default=None):
        action = kwargs.pop('action', default)
        return self._registry_get('action', action, action)

    def _get_handler(self):
        # determine function from conflict handler string
        handler_func_name = '_handle_conflict_%s' % self.conflict_handler
        try:
            return getattr(self, handler_func_name)
        except AttributeError:
            msg = f'invalid conflict_resolution value: {self.conflict_handler!r}'
            raise ValueError(msg)

    def _check_conflict(self, action):

        # find all options that conflict with this option
        confl_optionals = []
        for option_string in action.option_strings:
            if option_string in self._option_string_actions:
                confl_optional = self._option_string_actions[option_string]
                confl_optionals.append((option_string, confl_optional))

        # resolve any conflicts
        if confl_optionals:
            conflict_handler = self._get_handler()
            conflict_handler(action, confl_optionals)

    def _handle_conflict_error(self, action, conflicting_actions):
        message = ngettext('conflicting option string: %s',
                           'conflicting option strings: %s',
                           len(conflicting_actions))
        conflict_string = ', '.join([option_string
                                     for option_string, action
                                     in conflicting_actions])
        raise ArgumentError(action, message % conflict_string)

    def _handle_conflict_resolve(self, action, conflicting_actions):

        # remove all conflicting options
        for option_string, action in conflicting_actions:

            # remove the conflicting option
            action.option_strings.remove(option_string)
            self._option_string_actions.pop(option_string, None)

            # if the option now has no option string, remove it from the
            # container holding it
            if not action.option_strings:
                action.container._remove_action(action)

    def _check_help(self, action):
        if action.help and hasattr(self, "_get_validation_formatter"):
            formatter = self._get_validation_formatter()
            try:
                formatter._expand_help(action)
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError('badly formed help string') from exc


class _ArgumentGroup(_ActionsContainer):

    def __init__(self, container, title=None, description=None, **kwargs):
        if 'prefix_chars' in kwargs:
            import warnings
            depr_msg = (
                "The use of the undocumented 'prefix_chars' parameter in "
                "ArgumentParser.add_argument_group() is deprecated."
            )
            warnings.warn(depr_msg, DeprecationWarning, stacklevel=3)

        # add any missing keyword arguments by checking the container
        update = kwargs.setdefault
        update('conflict_handler', container.conflict_handler)
        update('prefix_chars', container.prefix_chars)
        update('argument_default', container.argument_default)
        super_init = super(_ArgumentGroup, self).__init__
        super_init(description=description, **kwargs)

        # group attributes
        self.title = title
        self._group_actions = []

        # share most attributes with the container
        self._registries = container._registries
        self._actions = container._actions
        self._option_string_actions = container._option_string_actions
        self._defaults = container._defaults
        self._has_negative_number_optionals = \
            container._has_negative_number_optionals
        self._mutually_exclusive_groups = container._mutually_exclusive_groups

    def _add_action(self, action):
        action = super(_ArgumentGroup, self)._add_action(action)
        self._group_actions.append(action)
        return action

    def _remove_action(self, action):
        super(_ArgumentGroup, self)._remove_action(action)
        self._group_actions.remove(action)

    def add_argument_group(self, *args, **kwargs):
        raise ValueError('argument groups cannot be nested')

class _MutuallyExclusiveGroup(_ArgumentGroup):

    def __init__(self, container, required=False):
        super(_MutuallyExclusiveGroup, self).__init__(container)
        self.required = required
        self._container = container

    def _add_action(self, action):
        if action.required:
            msg = 'mutually exclusive arguments must be optional'
            raise ValueError(msg)
        action = self._container._add_action(action)
        self._group_actions.append(action)
        return action

    def _remove_action(self, action):
        self._container._remove_action(action)
        self._group_actions.remove(action)

    def add_mutually_exclusive_group(self, **kwargs):
        raise ValueError('mutually exclusive groups cannot be nested')

def _prog_name(prog=None):
    if prog is not None:
        return prog
    arg0 = _sys.argv[0]
    try:
        modspec = _sys.modules['__main__'].__spec__
    except (KeyError, AttributeError):
        # possibly PYTHONSTARTUP or -X presite or other weird edge case
        # no good answer here, so fall back to the default
        modspec = None
    if modspec is None:
        # simple script
        return _os.path.basename(arg0)
    py = _os.path.basename(_sys.executable)
    if modspec.name != '__main__':
        # imported module or package
        modname = modspec.name.removesuffix('.__main__')
        return f'{py} -m {modname}'
    # directory or ZIP file
    return f'{py} {arg0}'


class ArgumentParser(_AttributeHolder, _ActionsContainer):
    """Object for parsing command line strings into Python objects.

    Keyword Arguments:
        - prog -- The name of the program (default:
            ``os.path.basename(sys.argv[0])``)
        - usage -- A usage message (default: auto-generated from arguments)
        - description -- A description of what the program does
        - epilog -- Text following the argument descriptions
        - parents -- Parsers whose arguments should be copied into this one
        - formatter_class -- HelpFormatter class for printing help messages
        - prefix_chars -- Characters that prefix optional arguments
        - fromfile_prefix_chars -- Characters that prefix files containing
            additional arguments
        - argument_default -- The default value for all arguments
        - conflict_handler -- String indicating how to handle conflicts
        - add_help -- Add a -h/-help option
        - allow_abbrev -- Allow long options to be abbreviated unambiguously
        - exit_on_error -- Determines whether or not ArgumentParser exits with
            error info when an error occurs
        - suggest_on_error - Enables suggestions for mistyped argument choices
            and subparser names (default: ``False``)
        - color - Allow color output in help messages (default: ``False``)
    """

    def __init__(self,
                 prog=None,
                 usage=None,
                 description=None,
                 epilog=None,
                 parents=[],
                 formatter_class=HelpFormatter,
                 prefix_chars='-',
                 fromfile_prefix_chars=None,
                 argument_default=None,
                 conflict_handler='error',
                 add_help=True,
                 allow_abbrev=True,
                 exit_on_error=True,
                 *,
                 suggest_on_error=False,
                 color=True,
                 ):
        superinit = super(ArgumentParser, self).__init__
        superinit(description=description,
                  prefix_chars=prefix_chars,
                  argument_default=argument_default,
                  conflict_handler=conflict_handler)

        self.prog = _prog_name(prog)
        self.usage = usage
        self.epilog = epilog
        self.formatter_class = formatter_class
        self.fromfile_prefix_chars = fromfile_prefix_chars
        self.add_help = add_help
        self.allow_abbrev = allow_abbrev
        self.exit_on_error = exit_on_error
        self.suggest_on_error = suggest_on_error
        self.color = color

        # Cached formatter for validation (avoids repeated _set_color calls)
        self._cached_formatter = None

        add_group = self.add_argument_group
        self._positionals = add_group(_('positional arguments'))
        self._optionals = add_group(_('options'))
        self._subparsers = None

        # register types
        self.register('type', None, _identity)

        # add help argument if necessary
        # (using explicit default to override global argument_default)
        default_prefix = '-' if '-' in prefix_chars else prefix_chars[0]
        if self.add_help:
            self.add_argument(
                default_prefix+'h', default_prefix*2+'help',
                action='help', default=SUPPRESS,
                help=_('show this help message and exit'))

        # add parent arguments and defaults
        for parent in parents:
            if not isinstance(parent, ArgumentParser):
                raise TypeError('parents must be a list of ArgumentParser')
            self._add_container_actions(parent)
            defaults = parent._defaults
            self._defaults.update(defaults)

    # =======================
    # Pretty __repr__ methods
    # =======================

    def _get_kwargs(self):
        names = [
            'prog',
            'usage',
            'description',
            'formatter_class',
            'conflict_handler',
            'add_help',
        ]
        return [(name, getattr(self, name)) for name in names]

    # ==================================
    # Optional/Positional adding methods
    # ==================================

    def add_subparsers(self, **kwargs):
        if self._subparsers is not None:
            raise ValueError('cannot have multiple subparser arguments')

        # add the parser class to the arguments if it's not present
        kwargs.setdefault('parser_class', type(self))

        if 'title' in kwargs or 'description' in kwargs:
            title = kwargs.pop('title', _('subcommands'))
            description = kwargs.pop('description', None)
            self._subparsers = self.add_argument_group(title, description)
        else:
            self._subparsers = self._positionals

        # prog defaults to the usage message of this parser, skipping
        # optional arguments and with no "usage:" prefix
        if kwargs.get('prog') is None:
            # Create formatter without color to avoid storing ANSI codes in prog
            formatter = self.formatter_class(prog=self.prog)
            formatter._set_color(False)
            positionals = self._get_positional_actions()
            groups = self._mutually_exclusive_groups
            formatter.add_usage(None, positionals, groups, '')
            kwargs['prog'] = formatter.format_help().strip()

        # create the parsers action and add it to the positionals list
        parsers_class = self._pop_action_class(kwargs, 'parsers')
        action = parsers_class(option_strings=[], **kwargs)
        action._color = self.color
        self._check_help(action)
        self._subparsers._add_action(action)

        # return the created parsers action
        return action

    def _add_action(self, action):
        if action.option_strings:
            self._optionals._add_action(action)
        else:
            self._positionals._add_action(action)
        return action

    def _get_optional_actions(self):
        return [action
                for action in self._actions
                if action.option_strings]

    def _get_positional_actions(self):
        return [action
                for action in self._actions
                if not action.option_strings]

    # =====================================
    # Command line argument parsing methods
    # =====================================

    def parse_args(self, args=None, namespace=None):
        args, argv = self.parse_known_args(args, namespace)
        if argv:
            msg = _('unrecognized arguments: %s') % ' '.join(argv)
            if self.exit_on_error:
                self.error(msg)
            else:
                raise ArgumentError(None, msg)
        return args

    def parse_known_args(self, args=None, namespace=None):
        return self._parse_known_args2(args, namespace, intermixed=False)

    def _parse_known_args2(self, args, namespace, intermixed):
        if args is None:
            # args default to the system args
            args = _sys.argv[1:]
        else:
            # make sure that args are mutable
            args = list(args)

        # default Namespace built from parser defaults
        if namespace is None:
            namespace = Namespace()

        # add any action defaults that aren't present
        for action in self._actions:
            if action.dest is not SUPPRESS:
                if not hasattr(namespace, action.dest):
                    if action.default is not SUPPRESS:
                        setattr(namespace, action.dest, action.default)

        # add any parser defaults that aren't present
        for dest in self._defaults:
            if not hasattr(namespace, dest):
                setattr(namespace, dest, self._defaults[dest])

        # parse the arguments and exit if there are any errors
        if self.exit_on_error:
            try:
                namespace, args = self._parse_known_args(args, namespace, intermixed)
            except ArgumentError as err:
                self.error(str(err))
        else:
            namespace, args = self._parse_known_args(args, namespace, intermixed)

        if hasattr(namespace, _UNRECOGNIZED_ARGS_ATTR):
            args.extend(getattr(namespace, _UNRECOGNIZED_ARGS_ATTR))
            delattr(namespace, _UNRECOGNIZED_ARGS_ATTR)
        return namespace, args

    def _parse_known_args(self, arg_strings, namespace, intermixed):
        # replace arg strings that are file references
        if self.fromfile_prefix_chars is not None:
            arg_strings = self._read_args_from_files(arg_strings)

        # map all mutually exclusive arguments to the other arguments
        # they can't occur with
        action_conflicts = {}
        for mutex_group in self._mutually_exclusive_groups:
            group_actions = mutex_group._group_actions
            for i, mutex_action in enumerate(mutex_group._group_actions):
                conflicts = action_conflicts.setdefault(mutex_action, [])
                conflicts.extend(group_actions[:i])
                conflicts.extend(group_actions[i + 1:])

        # find all option indices, and determine the arg_string_pattern
        # which has an 'O' if there is an option at an index,
        # an 'A' if there is an argument, or a '-' if there is a '--'
        option_string_indices = {}
        arg_string_pattern_parts = []
        arg_strings_iter = iter(arg_strings)
        for i, arg_string in enumerate(arg_strings_iter):

            # all args after -- are non-options
            if arg_string == '--':
                arg_string_pattern_parts.append('-')
                for arg_string in arg_strings_iter:
                    arg_string_pattern_parts.append('A')

            # otherwise, add the arg to the arg strings
            # and note the index if it was an option
            else:
                option_tuples = self._parse_optional(arg_string)
                if option_tuples is None:
                    pattern = 'A'
                else:
                    option_string_indices[i] = option_tuples
                    pattern = 'O'
                arg_string_pattern_parts.append(pattern)

        # join the pieces together to form the pattern
        arg_strings_pattern = ''.join(arg_string_pattern_parts)

        # converts arg strings to the appropriate and then takes the action
        seen_actions = set()
        seen_non_default_actions = set()
        warned = set()

        def take_action(action, argument_strings, option_string=None):
            seen_actions.add(action)
            argument_values = self._get_values(action, argument_strings)

            # error if this argument is not allowed with other previously
            # seen arguments
            if action.option_strings or argument_strings:
                seen_non_default_actions.add(action)
                for conflict_action in action_conflicts.get(action, []):
                    if conflict_action in seen_non_default_actions:
                        msg = _('not allowed with argument %s')
                        action_name = _get_action_name(conflict_action)
                        raise ArgumentError(action, msg % action_name)

            # take the action if we didn't receive a SUPPRESS value
            # (e.g. from a default)
            if argument_values is not SUPPRESS:
                action(self, namespace, argument_values, option_string)

        # function to convert arg_strings into an optional action
        def consume_optional(start_index):

            # get the optional identified at this index
            option_tuples = option_string_indices[start_index]
            # if multiple actions match, the option string was ambiguous
            if len(option_tuples) > 1:
                options = ', '.join([option_string
                    for action, option_string, sep, explicit_arg in option_tuples])
                args = {'option': arg_strings[start_index], 'matches': options}
                msg = _('ambiguous option: %(option)s could match %(matches)s')
                raise ArgumentError(None, msg % args)

            action, option_string, sep, explicit_arg = option_tuples[0]

            # identify additional optionals in the same arg string
            # (e.g. -xyz is the same as -x -y -z if no args are required)
            match_argument = self._match_argument
            action_tuples = []
            while True:

                # if we found no optional action, skip it
                if action is None:
                    extras.append(arg_strings[start_index])
                    extras_pattern.append('O')
                    return start_index + 1

                # if there is an explicit argument, try to match the
                # optional's string arguments to only this
                if explicit_arg is not None:
                    arg_count = match_argument(action, 'A')

                    # if the action is a single-dash option and takes no
                    # arguments, try to parse more single-dash options out
                    # of the tail of the option string
                    chars = self.prefix_chars
                    if (
                        arg_count == 0
                        and option_string[1] not in chars
                        and explicit_arg != ''
                    ):
                        if sep or explicit_arg[0] in chars:
                            msg = _('ignored explicit argument %r')
                            raise ArgumentError(action, msg % explicit_arg)
                        action_tuples.append((action, [], option_string))
                        char = option_string[0]
                        option_string = char + explicit_arg[0]
                        optionals_map = self._option_string_actions
                        if option_string in optionals_map:
                            action = optionals_map[option_string]
                            explicit_arg = explicit_arg[1:]
                            if not explicit_arg:
                                sep = explicit_arg = None
                            elif explicit_arg[0] == '=':
                                sep = '='
                                explicit_arg = explicit_arg[1:]
                            else:
                                sep = ''
                        else:
                            extras.append(char + explicit_arg)
                            extras_pattern.append('O')
                            stop = start_index + 1
                            break
                    # if the action expect exactly one argument, we've
                    # successfully matched the option; exit the loop
                    elif arg_count == 1:
                        stop = start_index + 1
                        args = [explicit_arg]
                        action_tuples.append((action, args, option_string))
                        break

                    # error if a double-dash option did not use the
                    # explicit argument
                    else:
                        msg = _('ignored explicit argument %r')
                        raise ArgumentError(action, msg % explicit_arg)

                # if there is no explicit argument, try to match the
                # optional's string arguments with the following strings
                # if successful, exit the loop
                else:
                    start = start_index + 1
                    selected_patterns = arg_strings_pattern[start:]
                    arg_count = match_argument(action, selected_patterns)
                    stop = start + arg_count
                    args = arg_strings[start:stop]
                    action_tuples.append((action, args, option_string))
                    break

            # add the Optional to the list and return the index at which
            # the Optional's string args stopped
            assert action_tuples
            for action, args, option_string in action_tuples:
                if action.deprecated and option_string not in warned:
                    self._warning(_("option '%(option)s' is deprecated") %
                                  {'option': option_string})
                    warned.add(option_string)
                take_action(action, args, option_string)
            return stop

        # the list of Positionals left to be parsed; this is modified
        # by consume_positionals()
        positionals = self._get_positional_actions()

        # function to convert arg_strings into positional actions
        def consume_positionals(start_index):
            # match as many Positionals as possible
            match_partial = self._match_arguments_partial
            selected_pattern = arg_strings_pattern[start_index:]
            arg_counts = match_partial(positionals, selected_pattern)

            # slice off the appropriate arg strings for each Positional
            # and add the Positional and its args to the list
            for action, arg_count in zip(positionals, arg_counts):
                args = arg_strings[start_index: start_index + arg_count]
                # Strip out the first '--' if it is not in REMAINDER arg.
                if action.nargs == PARSER:
                    if arg_strings_pattern[start_index] == '-':
                        assert args[0] == '--'
                        args.remove('--')
                elif action.nargs != REMAINDER:
                    if (arg_strings_pattern.find('-', start_index,
                                                 start_index + arg_count) >= 0):
                        args.remove('--')
                start_index += arg_count
                if args and action.deprecated and action.dest not in warned:
                    self._warning(_("argument '%(argument_name)s' is deprecated") %
                                  {'argument_name': action.dest})
                    warned.add(action.dest)
                take_action(action, args)

            # slice off the Positionals that we just parsed and return the
            # index at which the Positionals' string args stopped
            positionals[:] = positionals[len(arg_counts):]
            return start_index

        # consume Positionals and Optionals alternately, until we have
        # passed the last option string
        extras = []
        extras_pattern = []
        start_index = 0
        if option_string_indices:
            max_option_string_index = max(option_string_indices)
        else:
            max_option_string_index = -1
        while start_index <= max_option_string_index:

            # consume any Positionals preceding the next option
            next_option_string_index = start_index
            while next_option_string_index <= max_option_string_index:
                if next_option_string_index in option_string_indices:
                    break
                next_option_string_index += 1
            if not intermixed and start_index != next_option_string_index:
                positionals_end_index = consume_positionals(start_index)

                # only try to parse the next optional if we didn't consume
                # the option string during the positionals parsing
                if positionals_end_index > start_index:
                    start_index = positionals_end_index
                    continue
                else:
                    start_index = positionals_end_index

            # if we consumed all the positionals we could and we're not
            # at the index of an option string, there were extra arguments
            if start_index not in option_string_indices:
                strings = arg_strings[start_index:next_option_string_index]
                extras.extend(strings)
                extras_pattern.extend(arg_strings_pattern[start_index:next_option_string_index])
                start_index = next_option_string_index

            # consume the next optional and any arguments for it
            start_index = consume_optional(start_index)

        if not intermixed:
            # consume any positionals following the last Optional
            stop_index = consume_positionals(start_index)

            # if we didn't consume all the argument strings, there were extras
            extras.extend(arg_strings[stop_index:])
        else:
            extras.extend(arg_strings[start_index:])
            extras_pattern.extend(arg_strings_pattern[start_index:])
            extras_pattern = ''.join(extras_pattern)
            assert len(extras_pattern) == len(extras)
            # consume all positionals
            arg_strings = [s for s, c in zip(extras, extras_pattern) if c != 'O']
            arg_strings_pattern = extras_pattern.replace('O', '')
            stop_index = consume_positionals(0)
            # leave unknown optionals and non-consumed positionals in extras
            for i, c in enumerate(extras_pattern):
                if not stop_index:
                    break
                if c != 'O':
                    stop_index -= 1
                    extras[i] = None
            extras = [s for s in extras if s is not None]

        # make sure all required actions were present and also convert
        # action defaults which were not given as arguments
        required_actions = []
        for action in self._actions:
            if action not in seen_actions:
                if action.required:
                    required_actions.append(_get_action_name(action))
                else:
                    # Convert action default now instead of doing it before
                    # parsing arguments to avoid calling convert functions
                    # twice (which may fail) if the argument was given, but
                    # only if it was defined already in the namespace
                    if (action.default is not None and
                        isinstance(action.default, str) and
                        hasattr(namespace, action.dest) and
                        action.default is getattr(namespace, action.dest)):
                        setattr(namespace, action.dest,
                                self._get_value(action, action.default))

        if required_actions:
            raise ArgumentError(None, _('the following arguments are required: %s') %
                       ', '.join(required_actions))

        # make sure all required groups had one option present
        for group in self._mutually_exclusive_groups:
            if group.required:
                for action in group._group_actions:
                    if action in seen_non_default_actions:
                        break

                # if no actions were used, report the error
                else:
                    names = [_get_action_name(action)
                             for action in group._group_actions
                             if action.help is not SUPPRESS]
                    msg = _('one of the arguments %s is required')
                    raise ArgumentError(None, msg % ' '.join(names))

        # return the updated namespace and the extra arguments
        return namespace, extras

    def _read_args_from_files(self, arg_strings):
        # expand arguments referencing files
        new_arg_strings = []
        for arg_string in arg_strings:

            # for regular arguments, just add them back into the list
            if not arg_string or arg_string[0] not in self.fromfile_prefix_chars:
                new_arg_strings.append(arg_string)

            # replace arguments referencing files with the file content
            else:
                try:
                    with open(arg_string[1:],
                              encoding=_sys.getfilesystemencoding(),
                              errors=_sys.getfilesystemencodeerrors()) as args_file:
                        arg_strings = []
                        for arg_line in args_file.read().splitlines():
                            for arg in self.convert_arg_line_to_args(arg_line):
                                arg_strings.append(arg)
                        arg_strings = self._read_args_from_files(arg_strings)
                        new_arg_strings.extend(arg_strings)
                except OSError as err:
                    raise ArgumentError(None, str(err))

        # return the modified argument list
        return new_arg_strings

    def convert_arg_line_to_args(self, arg_line):
        return [arg_line]

    def _match_argument(self, action, arg_strings_pattern):
        # match the pattern for this action to the arg strings
        nargs_pattern = self._get_nargs_pattern(action)
        match = _re.match(nargs_pattern, arg_strings_pattern)

        # raise an exception if we weren't able to find a match
        if match is None:
            nargs_errors = {
                None: _('expected one argument'),
                OPTIONAL: _('expected at most one argument'),
                ONE_OR_MORE: _('expected at least one argument'),
            }
            msg = nargs_errors.get(action.nargs)
            if msg is None:
                msg = ngettext('expected %s argument',
                               'expected %s arguments',
                               action.nargs) % action.nargs
            raise ArgumentError(action, msg)

        # return the number of arguments matched
        return len(match.group(1))

    def _match_arguments_partial(self, actions, arg_strings_pattern):
        # progressively shorten the actions list by slicing off the
        # final actions until we find a match
        for i in range(len(actions), 0, -1):
            actions_slice = actions[:i]
            pattern = ''.join([self._get_nargs_pattern(action)
                               for action in actions_slice])
            match = _re.match(pattern, arg_strings_pattern)
            if match is not None:
                result = [len(string) for string in match.groups()]
                if (match.end() < len(arg_strings_pattern)
                    and arg_strings_pattern[match.end()] == 'O'):
                    while result and not result[-1]:
                        del result[-1]
                return result
        return []

    def _parse_optional(self, arg_string):
        # if it's an empty string, it was meant to be a positional
        if not arg_string:
            return None

        # if it doesn't start with a prefix, it was meant to be positional
        if not arg_string[0] in self.prefix_chars:
            return None

        # if the option string is present in the parser, return the action
        if arg_string in self._option_string_actions:
            action = self._option_string_actions[arg_string]
            return [(action, arg_string, None, None)]

        # if it's just a single character, it was meant to be positional
        if len(arg_string) == 1:
            return None

        # if the option string before the "=" is present, return the action
        option_string, sep, explicit_arg = arg_string.partition('=')
        if sep and option_string in self._option_string_actions:
            action = self._option_string_actions[option_string]
            return [(action, option_string, sep, explicit_arg)]

        # search through all possible prefixes of the option string
        # and all actions in the parser for possible interpretations
        option_tuples = self._get_option_tuples(arg_string)

        if option_tuples:
            return option_tuples

        # if it was not found as an option, but it looks like a negative
        # number, it was meant to be positional
        # unless there are negative-number-like options
        if self._negative_number_matcher.match(arg_string):
            if not self._has_negative_number_optionals:
                return None

        # if it contains a space, it was meant to be a positional
        if ' ' in arg_string:
            return None

        # it was meant to be an optional but there is no such option
        # in this parser (though it might be a valid option in a subparser)
        return [(None, arg_string, None, None)]

    def _get_option_tuples(self, option_string):
        result = []

        # option strings starting with two prefix characters are only
        # split at the '='
        chars = self.prefix_chars
        if option_string[0] in chars and option_string[1] in chars:
            if self.allow_abbrev:
                option_prefix, sep, explicit_arg = option_string.partition('=')
                if not sep:
                    sep = explicit_arg = None
                for option_string in self._option_string_actions:
                    if option_string.startswith(option_prefix):
                        action = self._option_string_actions[option_string]
                        tup = action, option_string, sep, explicit_arg
                        result.append(tup)

        # single character options can be concatenated with their arguments
        # but multiple character options always have to have their argument
        # separate
        elif option_string[0] in chars and option_string[1] not in chars:
            option_prefix, sep, explicit_arg = option_string.partition('=')
            if not sep:
                sep = explicit_arg = None
            short_option_prefix = option_string[:2]
            short_explicit_arg = option_string[2:]

            for option_string in self._option_string_actions:
                if option_string == short_option_prefix:
                    action = self._option_string_actions[option_string]
                    tup = action, option_string, '', short_explicit_arg
                    result.append(tup)
                elif self.allow_abbrev and option_string.startswith(option_prefix):
                    action = self._option_string_actions[option_string]
                    tup = action, option_string, sep, explicit_arg
                    result.append(tup)

        # shouldn't ever get here
        else:
            raise ArgumentError(None, _('unexpected option string: %s') % option_string)

        # return the collected option tuples
        return result

    def _get_nargs_pattern(self, action):
        # in all examples below, we have to allow for '--' args
        # which are represented as '-' in the pattern
        nargs = action.nargs
        # if this is an optional action, -- is not allowed
        option = action.option_strings

        # the default (None) is assumed to be a single argument
        if nargs is None:
            nargs_pattern = '([A])' if option else '(-*A-*)'

        # allow zero or one arguments
        elif nargs == OPTIONAL:
            nargs_pattern = '(A?)' if option else '(-*A?-*)'

        # allow zero or more arguments
        elif nargs == ZERO_OR_MORE:
            nargs_pattern = '(A*)' if option else '(-*[A-]*)'

        # allow one or more arguments
        elif nargs == ONE_OR_MORE:
            nargs_pattern = '(A+)' if option else '(-*A[A-]*)'

        # allow any number of options or arguments
        elif nargs == REMAINDER:
            nargs_pattern = '([AO]*)' if option else '(.*)'

        # allow one argument followed by any number of options or arguments
        elif nargs == PARSER:
            nargs_pattern = '(A[AO]*)' if option else '(-*A[-AO]*)'

        # suppress action, like nargs=0
        elif nargs == SUPPRESS:
            nargs_pattern = '()' if option else '(-*)'

        # all others should be integers
        else:
            nargs_pattern = '([AO]{%d})' % nargs if option else '((?:-*A){%d}-*)' % nargs

        # return the pattern
        return nargs_pattern

    # ========================
    # Alt command line argument parsing, allowing free intermix
    # ========================

    def parse_intermixed_args(self, args=None, namespace=None):
        args, argv = self.parse_known_intermixed_args(args, namespace)
        if argv:
            msg = _('unrecognized arguments: %s') % ' '.join(argv)
            if self.exit_on_error:
                self.error(msg)
            else:
                raise ArgumentError(None, msg)
        return args

    def parse_known_intermixed_args(self, args=None, namespace=None):
        # returns a namespace and list of extras
        #
        # positional can be freely intermixed with optionals.  optionals are
        # first parsed with all positional arguments deactivated.  The 'extras'
        # are then parsed.  If the parser definition is incompatible with the
        # intermixed assumptions (e.g. use of REMAINDER, subparsers) a
        # TypeError is raised.

        positionals = self._get_positional_actions()
        a = [action for action in positionals
             if action.nargs in [PARSER, REMAINDER]]
        if a:
            raise TypeError('parse_intermixed_args: positional arg'
                            ' with nargs=%s'%a[0].nargs)

        return self._parse_known_args2(args, namespace, intermixed=True)

    # ========================
    # Value conversion methods
    # ========================

    def _get_values(self, action, arg_strings):
        # optional argument produces a default when not present
        if not arg_strings and action.nargs == OPTIONAL:
            if action.option_strings:
                value = action.const
            else:
                value = action.default
            if isinstance(value, str) and value is not SUPPRESS:
                value = self._get_value(action, value)

        # when nargs='*' on a positional, if there were no command-line
        # args, use the default if it is anything other than None
        elif (not arg_strings and action.nargs == ZERO_OR_MORE and
              not action.option_strings):
            if action.default is not None:
                value = action.default
            else:
                value = []

        # single argument or optional argument produces a single value
        elif len(arg_strings) == 1 and action.nargs in [None, OPTIONAL]:
            arg_string, = arg_strings
            value = self._get_value(action, arg_string)
            self._check_value(action, value)

        # REMAINDER arguments convert all values, checking none
        elif action.nargs == REMAINDER:
            value = [self._get_value(action, v) for v in arg_strings]

        # PARSER arguments convert all values, but check only the first
        elif action.nargs == PARSER:
            value = [self._get_value(action, v) for v in arg_strings]
            self._check_value(action, value[0])

        # SUPPRESS argument does not put anything in the namespace
        elif action.nargs == SUPPRESS:
            value = SUPPRESS

        # all other types of nargs produce a list
        else:
            value = [self._get_value(action, v) for v in arg_strings]
            for v in value:
                self._check_value(action, v)

        # return the converted value
        return value

    def _get_value(self, action, arg_string):
        type_func = self._registry_get('type', action.type, action.type)
        if not callable(type_func):
            raise TypeError(f'{type_func!r} is not callable')

        # convert the value to the appropriate type
        try:
            result = type_func(arg_string)

        # ArgumentTypeErrors indicate errors
        except ArgumentTypeError as err:
            msg = str(err)
            raise ArgumentError(action, msg)

        # TypeErrors or ValueErrors also indicate errors
        except (TypeError, ValueError):
            name = getattr(action.type, '__name__', repr(action.type))
            args = {'type': name, 'value': arg_string}
            msg = _('invalid %(type)s value: %(value)r')
            raise ArgumentError(action, msg % args)

        # return the converted value
        return result

    def _check_value(self, action, value):
        # converted value must be one of the choices (if specified)
        choices = action.choices
        if choices is None:
            return

        if isinstance(choices, str):
            choices = iter(choices)

        if value not in choices:
            args = {'value': str(value),
                    'choices': ', '.join(repr(str(choice)) for choice in action.choices)}
            msg = _('invalid choice: %(value)r (choose from %(choices)s)')

            if self.suggest_on_error and isinstance(value, str):
                if all(isinstance(choice, str) for choice in action.choices):
                    import difflib
                    suggestions = difflib.get_close_matches(value, action.choices, 1)
                    if suggestions:
                        args['closest'] = suggestions[0]
                        msg = _('invalid choice: %(value)r, maybe you meant %(closest)r? '
                                '(choose from %(choices)s)')

            raise ArgumentError(action, msg % args)

    # =======================
    # Help-formatting methods
    # =======================

    def format_usage(self):
        formatter = self._get_formatter()
        formatter.add_usage(self.usage, self._actions,
                            self._mutually_exclusive_groups)
        return formatter.format_help()

    def format_help(self):
        formatter = self._get_formatter()

        # usage
        formatter.add_usage(self.usage, self._actions,
                            self._mutually_exclusive_groups)

        # description
        formatter.add_text(self.description)

        # positionals, optionals and user-defined groups
        for action_group in self._action_groups:
            formatter.start_section(action_group.title)
            formatter.add_text(action_group.description)
            formatter.add_arguments(action_group._group_actions)
            formatter.end_section()

        # epilog
        formatter.add_text(self.epilog)

        # determine help from format above
        return formatter.format_help()

    def _get_formatter(self):
        formatter = self.formatter_class(prog=self.prog)
        formatter._set_color(self.color)
        return formatter

    def _get_validation_formatter(self):
        # Return cached formatter for read-only validation operations
        # (_expand_help and _format_args). Avoids repeated slow _set_color calls.
        if self._cached_formatter is None:
            self._cached_formatter = self._get_formatter()
        return self._cached_formatter

    # =====================
    # Help-printing methods
    # =====================

    def print_usage(self, file=None):
        if file is None:
            file = _sys.stdout
        self._print_message(self.format_usage(), file)

    def print_help(self, file=None):
        if file is None:
            file = _sys.stdout
        self._print_message(self.format_help(), file)

    def _print_message(self, message, file=None):
        if message:
            file = file or _sys.stderr
            try:
                file.write(message)
            except (AttributeError, OSError):
                pass

    # ===============
    # Exiting methods
    # ===============

    def exit(self, status=0, message=None):
        if message:
            self._print_message(message, _sys.stderr)
        _sys.exit(status)

    def error(self, message):
        """error(message: string)

        Prints a usage message incorporating the message to stderr and
        exits.

        If you override this in a subclass, it should not return -- it
        should either exit or raise an exception.
        """
        self.print_usage(_sys.stderr)
        args = {'prog': self.prog, 'message': message}
        self.exit(2, _('%(prog)s: error: %(message)s\n') % args)

    def _warning(self, message):
        args = {'prog': self.prog, 'message': message}
        self._print_message(_('%(prog)s: warning: %(message)s\n') % args, _sys.stderr)
````

