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
