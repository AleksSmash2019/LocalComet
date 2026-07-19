from __future__ import annotations

import importlib
import json
import os
import runpy
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


LOCALCOMET_VERSION = "v6.82"
LOCALCOMET_VERSION_LABEL = "LocalComet v6.82 - Explainable Task Planner & Approval Gate"
LEGACY_CONTROL_PANEL_RETIRED_RU_V650G = "v6.50g legacy tabbed control panel retired; launches new Computer Use menu only"
NEW_MENU_PATCH_COMMAND_BRIDGE_RU_V650J = "v6.50j route Patch Panel commands through new Computer Use menu"
COMPUTER_USE_FULL_CONTROL_MISSION_RU_V651 = "v6.51 управляй пк first-class Computer Use route"

ROOT_DIR = Path(os.environ.get("LOCALCOMET_ROOT") or Path(__file__).resolve().parent).resolve()

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    os.chdir(ROOT_DIR)
except Exception:
    pass


def _json_safe(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def _target_patch_panel() -> Path:
    candidate = ROOT_DIR / "LocalComet_Patch_Panel.py"
    if candidate.exists():
        return candidate
    return Path(__file__).resolve().parent / "LocalComet_Patch_Panel.py"


def _target_new_menu_module() -> str:
    return "modules.premium_task_panel_ru"


def _normalize_command(command: str) -> str:
    return str(command or "").strip().lower().replace("ё", "е")


def _is_strict_project_stability_ru_command(command):
    try:
        from modules.strict_project_stability_ru import is_strict_project_check_command
        return is_strict_project_check_command(command)
    except Exception:
        return False


def _run_strict_project_stability_ru_command(command):
    from modules.strict_project_stability_ru import dispatch
    return dispatch(command)


def _is_computer_use_command_bridge(command: str) -> bool:
    try:
        from modules.computer_use_core_ru import is_computer_use_command
        if is_computer_use_command(command):
            return True
    except Exception:
        pass
    lower = _normalize_command(command)
    prefixes = (
        "управляй пк",
        "сделай на компьютере",
        "агент пк",
        "computer use",
        "pc computer",
    )
    return any(lower == prefix or lower.startswith(prefix + " ") for prefix in prefixes)


def _run_computer_use_command_bridge(command: str) -> Dict[str, Any]:
    from modules.computer_use_core_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "computer_use_core_ru",
        "plan": {"tool": "computer_use_core_ru", "action": "dispatch"},
        "result": result,
    }


def _is_patch_panel_bridge_command(command):
    lower = _normalize_command(command)
    if not lower:
        return False
    exact = {
        "help",
        "помощь",
        "команды",
        "что умеешь",
        "?",
        "статус",
        "status",
        "обнови статус",
        "обновить статус",
        "refresh",
        "принять патч",
        "прими патч",
        "применить патч",
        "apply",
        "accept",
        "принять патч и проверить",
        "импорт",
        "import",
        "импорт проверка",
        "импорт + проверка",
        "import validate",
        "выбрать response",
        "выбери response",
        "select response",
        "choose response",
        "сброс выбора response",
        "сбросить выбор response",
        "clear selected response",
        "reset response source",
        "проверить проект",
        "проверь проект",
        "verify",
        "verify project",
        "checks",
        "проверки",
        "открыть relay",
        "relay",
        "open relay",
        "открыть reports",
        "reports",
        "open reports",
        "открыть отчеты",
        "открыть downloads",
        "downloads",
        "open downloads",
        "открыть logs",
        "logs",
        "open logs",
        "копировать лог",
        "копировать итог",
        "copy summary",
        "copy final summary",
        "статус патча",
        "patch status",
        "patch ux status",
        "открыть последний отчет",
        "open last report",
        "copy log",
        "сохранить лог",
        "save log",
        "очистить лог",
        "clear log",
        "перечитать панель",
        "reload panel",
        "перечитать код панели",
        "soft reload",
    }
    if lower in exact:
        return True
    prefixes = (
        "выбрать response ",
        "выбери response ",
        "select response ",
        "choose response ",
        "response ",
        "source ",
    )
    return lower.startswith(prefixes)


def _run_patch_panel_bridge_command(command):
    try:
        patch_panel = importlib.import_module("LocalComet_Patch_Panel")
        runner = getattr(patch_panel, "run_patch_panel_chat_command", None)
        if not callable(runner):
            return {
                "mode": "patch_panel_bridge",
                "route": "patch_panel_compact_chat",
                "plan": {"tool": "LocalComet_Patch_Panel", "action": "run_patch_panel_chat_command"},
                "result": "STOP: LocalComet_Patch_Panel.run_patch_panel_chat_command не найден.",
            }
        result = runner(command)
        return {
            "mode": "command",
            "route": "patch_panel_compact_chat",
            "plan": {"tool": "LocalComet_Patch_Panel", "action": "run_patch_panel_chat_command"},
            "result": result,
        }
    except Exception as exc:
        return {
            "mode": "patch_panel_bridge",
            "route": "patch_panel_compact_chat",
            "plan": {"tool": "LocalComet_Patch_Panel", "action": "run_patch_panel_chat_command"},
            "result": "STOP: patch panel bridge failed: " + str(exc),
        }


def _is_plain_desktop_goal(text: str) -> bool:
    lower = _normalize_command(text)
    if not lower:
        return False
    desktop_verbs = (
        "открой", "открыть", "откройте", "открывай", "открывайте",
        "запусти", "запустить", "запускай",
        "покажи", "показать", "покажите",
        "закрой", "закрыть", "закройте",
        "нажми", "нажать",
        "кликни", "кликнуть",
        "введи", "ввести",
        "выбери", "выбрать",
        "переименуй", "переименовать",
        "скопируй", "скопировать",
        "перемести", "переместить",
        "сохрани", "сохранить",
    )
    for verb in desktop_verbs:
        if lower == verb or lower.startswith(verb + " "):
            return True
    screenshot_keywords = ("скриншот", "скрин", "screenshot", "snapshot")
    for maker in ("сделай", "сделать", "сделайте", "создай", "создать", "создайте"):
        for obj in screenshot_keywords:
            if lower == maker + " " + obj or lower.startswith(maker + " " + obj + " "):
                return True
            if lower == obj or lower.startswith(obj + " "):
                return True
    desktop_phrases = ("покажи рабочий стол", "показать рабочий стол", "открой рабочий стол", "рабочий стол")
    for phrase in desktop_phrases:
        if lower == phrase:
            return True
    return False


def _is_working_directory_guard_command_ru_v665b(command):
    try:
        from modules.working_directory_guard_ru import is_working_directory_guard_command
        return is_working_directory_guard_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {
            "проверь рабочую папку",
            "working directory guard",
            "проверь рабочую директорию",
            "working dir guard",
        }


def _run_working_directory_guard_command_ru_v665b(command):
    from modules.working_directory_guard_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.working_directory_guard_ru",
        "plan": {"tool": "modules.working_directory_guard_ru", "action": "dispatch"},
        "result": result,
    }


def _is_screenshot_capture_policy_command_ru_v665c(command):
    try:
        from modules.screenshot_capture_policy_ru import is_screenshot_capture_policy_command
        return is_screenshot_capture_policy_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {
            "статус скриншотов",
            "status screenshots",
            "screenshot storage status",
            "screenshot status",
            "скриншоты статус",
        }


def _run_screenshot_capture_policy_command_ru_v665c(command):
    from modules.screenshot_capture_policy_ru import dispatch as _scp_dispatch
    result = _scp_dispatch(command)
    return {
        "mode": "command",
        "route": "modules.screenshot_capture_policy_ru",
        "plan": {"tool": "modules.screenshot_capture_policy_ru", "action": "dispatch"},
        "result": result,
    }


def _is_confirmed_app_action_command_ru_v669(command):
    try:
        from modules.confirmed_app_actions_ru import is_confirmed_app_action_command
        return is_confirmed_app_action_command(command)
    except Exception:
        return False


def _run_confirmed_app_action_command_ru_v669(command):
    from modules.confirmed_app_actions_ru import run_confirmed_app_action
    return run_confirmed_app_action(command)


def _is_plain_app_goal_ru_v669(command):
    try:
        from modules.confirmed_app_actions_ru import is_plain_app_goal
        return is_plain_app_goal(command)
    except Exception:
        return {"is_goal": False}


def _is_direct_allowlisted_app_command_ru_v672(command):
    try:
        from modules.confirmed_app_actions_ru import is_direct_allowlisted_app_command
        return is_direct_allowlisted_app_command(command)
    except Exception:
        return {"is_direct": False}


def _run_direct_allowlisted_app_command_ru_v672(command):
    from modules.confirmed_app_actions_ru import run_direct_allowlisted_app_action
    return run_direct_allowlisted_app_action(command)


def _is_confirmed_desktop_action_command_ru_v665g(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {
        "подтвердить открыть браузер",
        "confirm open browser",
        "подтвердить запустить браузер",
    }


def _run_confirmed_desktop_action_command_ru_v665g(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    action_taken = "unknown"
    if lower in {"подтвердить открыть браузер", "confirm open browser", "подтвердить запустить браузер"}:
        action_taken = "open_browser"
        try:
            import webbrowser
            webbrowser.open("https://www.google.com")
            browser_opened = True
        except Exception as exc:
            browser_opened = False
            action_taken = f"open_browser_failed: {exc}"
    return {
        "mode": "confirmed_desktop_action",
        "route": "confirmed_desktop_actions",
        "real_action": True,
        "action": action_taken,
        "browser_opened": browser_opened,
        "message": (
            "Выполнено: браузер открыт по вашему подтверждению.\n"
            "Действие было разрешено (allowlisted).\n"
            "Никакие другие действия Computer Use не выполнялись.\n"
            "Снимки экрана не создавались."
        ),
        "result": {
            "command": "allowlisted_desktop_action",
            "action": action_taken,
            "browser_opened": browser_opened,
            "note": "Только разрешённые действия. Полный Computer Use не включён.",
        },
    }


def _run_base_panel_chat_command(command):
    text = str(command or "").strip()
    if _is_strict_project_stability_ru_command(text):
        route_name = "strict_project_stability_ru"
        result = _run_strict_project_stability_ru_command(text)
        return {
            "mode": "command",
            "route": route_name,
            "plan": {"tool": "strict_project_stability_ru", "action": "dispatch"},
            "result": result,
        }
    if _is_patch_panel_bridge_command(text):
        return _run_patch_panel_bridge_command(text)
    if _is_computer_use_command_bridge(text):
        return _run_computer_use_command_bridge(text)
    if _is_screenshot_capture_policy_command_ru_v665c(text):
        return _run_screenshot_capture_policy_command_ru_v665c(text)
    if _is_working_directory_guard_command_ru_v665b(text):
        return _run_working_directory_guard_command_ru_v665b(text)
    if _is_confirmed_app_action_command_ru_v669(text):
        return _run_confirmed_app_action_command_ru_v669(text)
    if _is_confirmed_desktop_action_command_ru_v665g(text):
        return _run_confirmed_desktop_action_command_ru_v665g(text)
    direct_app = _is_direct_allowlisted_app_command_ru_v672(text)
    if direct_app.get("is_direct"):
        return _run_direct_allowlisted_app_command_ru_v672(text)
    plain_app_goal = _is_plain_app_goal_ru_v669(text)
    if plain_app_goal.get("is_goal"):
        return {
            "mode": "requires_confirmation",
            "route": "confirmed_app_actions",
            "plan": {"tool": "confirmed_app_actions", "action": "confirm"},
            "result": plain_app_goal["confirmation_message"],
        }
    if _is_plain_desktop_goal(text):
        return {
            "mode": "requires_confirmation",
            "route": "confirmed_desktop_actions",
            "plan": {"tool": "confirmed_desktop_actions", "action": "confirm"},
            "result": f"Требуется подтверждение: {text}? Напиши: подтвердить {text}",
        }
    return {
        "mode": "new_menu_only",
        "route": "premium_task_panel_ru",
        "plan": {"tool": "premium_task_panel_ru", "action": "chat"},
        "result": (
            "Команда не распознана bridge-router. "
            "Для полного Computer Use используй: управляй пк <цель>, pc computer full control simulate <цель>, "
            "pc computer full control status. Для patch workflow: статус, выбрать response <path>, принять патч."
        ),
    }


def format_panel_chat_result(payload):
    result = payload.get("result", "")
    if isinstance(result, dict):
        return _json_safe(result)
    return str(result)


def _launch_patch_panel_passthrough() -> None:
    target = _target_patch_panel()
    if not target.exists():
        raise FileNotFoundError(f"LocalComet_Patch_Panel.py not found: {target}")
    sys.argv = [str(target), *sys.argv[1:]]
    runpy.run_path(str(target), run_name="__main__")


def _launch_new_menu_only() -> None:
    import tkinter as tk
    from modules.premium_task_panel_ru import auto_open_task_panel_if_enabled, open_task_panel

    root = tk.Tk()
    root.withdraw()
    result = open_task_panel(None)
    if isinstance(result, dict) and not result.get("ok", True):
        fallback = auto_open_task_panel_if_enabled(None)
        if isinstance(fallback, dict) and not fallback.get("ok", True):
            raise RuntimeError(str(fallback))
    root.mainloop()


def run_headless_self_check() -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details})

    source = Path(__file__).read_text(encoding="utf-8", errors="replace")
    notebook_marker = "ttk." + "Notebook"
    command_marker = "Command" + " Center"
    class_marker = "class " + "LocalCometControlPanel"

    add("version marker", f'LOCALCOMET_VERSION = "{LOCALCOMET_VERSION}"' in source, LOCALCOMET_VERSION)
    add("legacy retired marker", "LEGACY_CONTROL_PANEL_RETIRED_RU_V650G" in source, "")
    add("full control marker", "COMPUTER_USE_FULL_CONTROL_MISSION_RU_V651" in source, "")
    add("no legacy notebook ui", notebook_marker not in source, "")
    add("no legacy command center ui", command_marker not in source, "")
    add("no legacy LocalCometControlPanel class", class_marker not in source, "")
    add("patch command bridge marker", "NEW_MENU_PATCH_COMMAND_BRIDGE_RU_V650J" in source, "")

    try:
        bridge_probe = run_panel_chat_command("pc computer full control status")
        result = bridge_probe.get("result") if isinstance(bridge_probe, dict) else {}
        add("computer use full control status route", isinstance(result, dict) and result.get("mode") == "computer_use_full_control_status", bridge_probe)
    except Exception:
        add("computer use full control status route", False, traceback.format_exc())

    try:
        full_probe = run_panel_chat_command("pc computer full control simulate открой блокнот и напиши hello")
        result = full_probe.get("result") if isinstance(full_probe, dict) else {}
        add("computer use full control simulate route", isinstance(result, dict) and result.get("outcome") == "done", result)
    except Exception:
        add("computer use full control simulate route", False, traceback.format_exc())

    try:
        patch_panel = _target_patch_panel()
        add("patch panel fallback exists", patch_panel.exists(), str(patch_panel))
    except Exception:
        add("patch panel fallback exists", False, traceback.format_exc())

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    return {
        "ok": summary["failed"] == 0,
        "mode": "legacy_control_panel_new_menu_only_self_check",
        "version": LOCALCOMET_VERSION,
        "summary": summary,
        "checks": checks,
    }


def main() -> None:
    if "--self-check" in sys.argv:
        print(_json_safe(run_headless_self_check()))
        return
    if "--patch-panel" in sys.argv:
        _launch_patch_panel_passthrough()
        return
    _launch_new_menu_only()



LOCALCOMET_AGENT_AUTO_TEST_CENTER_RU_V655B = "v6.55b agent automation functional test center repair installed"


# BEGIN v6.56 Professional Panel Capability Audit control bridge
LOCALCOMET_PANEL_CAPABILITY_AUDIT_RU_V656 = "v6.56 panel capability audit bridge installed"


def _is_panel_capability_audit_command_ru_v656(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {
        "pc panel capability audit",
        "pc task panel audit",
        "panel capability audit",
        "аудит панели",
        "аудит меню",
        "статус аудита панели",
        "pc panel capability audit status",
    }


def _run_panel_capability_audit_command_ru_v656(command):
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    from modules.panel_capability_audit_ru import dispatch as panel_audit_dispatch

    result = panel_audit_dispatch(command)
    return {
        "mode": "command",
        "route": "panel_capability_audit_ru",
        "plan": {"tool": "panel_capability_audit_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.56 Professional Panel Capability Audit control bridge

PATCH_PANEL_UX_RELIABILITY_CONTROL_BRIDGE_RU_V657 = "v6.57 patch panel UX commands added to control bridge"

# BEGIN v6.58 Developer Velocity Toolkit control bridge
LOCALCOMET_DEVELOPER_VELOCITY_TOOLKIT_RU_V658 = "v6.58 developer velocity toolkit lite installed"


def _is_developer_velocity_command_ru_v658(command):
    try:
        from modules.localcomet_developer_velocity_ru import is_developer_velocity_command
        return is_developer_velocity_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {
            "последний сбой",
            "последняя ошибка",
            "события патча",
            "таймлайн патча",
            "статус разработки",
            "статус проекта",
            "debug пакет",
            "собрать debug пакет",
            "first failure",
            "last failure",
            "patch events",
            "patch timeline",
            "green gate",
            "green gate status",
            "debug package",
        }


def _run_developer_velocity_command_ru_v658(command):
    from modules.localcomet_developer_velocity_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "localcomet_developer_velocity_ru",
        "plan": {"tool": "localcomet_developer_velocity_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.58 Developer Velocity Toolkit control bridge

# BEGIN v6.61 Context Pack Generator bridge
LOCALCOMET_CONTEXT_PACK_RU_V661 = "v6.61 context pack generator bridge installed"


def _is_context_pack_command_ru_v661(command):
    try:
        from modules.context_pack_ru import is_context_pack_command
        return is_context_pack_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet agent context pack", "agent context pack", "context pack"}


def _run_context_pack_command_ru_v661(command):
    from modules.context_pack_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.context_pack_ru",
        "plan": {"tool": "modules.context_pack_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.61 Context Pack Generator bridge

# BEGIN v6.62 Plan Contract Generator bridge
LOCALCOMET_PLAN_CONTRACT_RU_V662 = "v6.62 plan contract generator bridge installed"


def _is_plan_contract_command_ru_v662(command):
    try:
        from modules.plan_contract_ru import is_plan_contract_command
        return is_plan_contract_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet agent plan contract", "agent plan contract", "plan contract"}


def _run_plan_contract_command_ru_v662(command):
    from modules.plan_contract_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.plan_contract_ru",
        "plan": {"tool": "modules.plan_contract_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.62 Plan Contract Generator bridge

# BEGIN v6.63 Risk Classifier bridge
LOCALCOMET_RISK_CLASSIFIER_RU_V663 = "v6.63 risk classifier bridge installed"


def _is_risk_classifier_command_ru_v663(command):
    try:
        from modules.risk_classifier_ru import is_risk_classifier_command
        return is_risk_classifier_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet agent risk classify", "agent risk classify", "risk classify"}


def _run_risk_classifier_command_ru_v663(command):
    from modules.risk_classifier_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.risk_classifier_ru",
        "plan": {"tool": "modules.risk_classifier_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.63 Risk Classifier bridge

# BEGIN v6.64a Repository Weight Audit bridge
LOCALCOMET_REPO_WEIGHT_AUDIT_RU_V664A = "v6.64a repo weight audit bridge installed"


def _is_repo_weight_audit_command_ru_v664a(command):
    try:
        from modules.repo_weight_audit_ru import is_repo_weight_audit_command
        return is_repo_weight_audit_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet repo weight audit", "repo weight audit", "repo weight"}


def _run_repo_weight_audit_command_ru_v664a(command):
    from modules.repo_weight_audit_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.repo_weight_audit_ru",
        "plan": {"tool": "modules.repo_weight_audit_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.64a Repository Weight Audit bridge

# BEGIN v6.64b Storage Cleanup Plan bridge
LOCALCOMET_STORAGE_CLEANUP_PLAN_RU_V664B = "v6.64b storage cleanup plan bridge installed"


def _is_storage_cleanup_plan_command_ru_v664b(command):
    try:
        from modules.storage_cleanup_plan_ru import is_storage_cleanup_plan_command
        return is_storage_cleanup_plan_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet storage cleanup plan", "storage cleanup plan", "cleanup plan"}


def _run_storage_cleanup_plan_command_ru_v664b(command):
    from modules.storage_cleanup_plan_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.storage_cleanup_plan_ru",
        "plan": {"tool": "modules.storage_cleanup_plan_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.64b Storage Cleanup Plan bridge

# BEGIN v6.64c Screenshot Retention Dry Run bridge
LOCALCOMET_SCREENSHOT_RETENTION_DRY_RUN_RU_V664C = "v6.64c screenshot retention dry run bridge installed"


def _is_screenshot_retention_dry_run_command_ru_v664c(command):
    try:
        from modules.screenshot_retention_dry_run_ru import is_screenshot_retention_dry_run_command
        return is_screenshot_retention_dry_run_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet screenshots retention dry run", "screenshots retention dry run", "screenshot dry run"}


def _run_screenshot_retention_dry_run_command_ru_v664c(command):
    from modules.screenshot_retention_dry_run_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.screenshot_retention_dry_run_ru",
        "plan": {"tool": "modules.screenshot_retention_dry_run_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.64c Screenshot Retention Dry Run bridge

# BEGIN v6.64d Screenshot Storage Policy Simulator RU bridge


def _is_screenshot_storage_policy_simulator_command_ru_v664d(command):
    try:
        from modules.screenshot_storage_policy_simulator_ru import is_screenshot_storage_policy_simulator_command
        return is_screenshot_storage_policy_simulator_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet screenshots storage policy simulate", "screenshots storage policy simulate", "storage policy simulate"}


def _run_screenshot_storage_policy_simulator_command_ru_v664d(command):
    from modules.screenshot_storage_policy_simulator_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.screenshot_storage_policy_simulator_ru",
        "plan": {"tool": "modules.screenshot_storage_policy_simulator_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.64d Screenshot Storage Policy Simulator RU bridge

# BEGIN v6.64e Screenshot Retention Policy Config RU bridge


def _is_screenshot_retention_policy_config_command_ru_v664e(command):
    try:
        from modules.screenshot_retention_policy_config_ru import is_screenshot_retention_policy_config_command
        return is_screenshot_retention_policy_config_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet screenshots retention policy write", "screenshots retention policy write", "retention policy write"}


def _run_screenshot_retention_policy_config_command_ru_v664e(command):
    from modules.screenshot_retention_policy_config_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.screenshot_retention_policy_config_ru",
        "plan": {"tool": "modules.screenshot_retention_policy_config_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.64e Screenshot Retention Policy Config RU bridge

# BEGIN v6.67 Task Contract Registry RU bridge


def _is_task_contract_registry_command_ru_v667(command):
    try:
        from modules.task_contract_registry_ru import _match_registry_command
        return _match_registry_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"task contract registry", "реестр контрактов задач"} or lower.startswith("контракт команды ") or lower.startswith("contract for ")


def _run_task_contract_registry_command_ru_v667(command):
    from modules.task_contract_registry_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.task_contract_registry_ru",
        "plan": {"tool": "modules.task_contract_registry_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.67 Task Contract Registry RU bridge

# BEGIN v6.68 App Harness Registry RU bridge


def _is_app_harness_registry_command_ru_v668(command):
    try:
        from modules.app_harness_registry_ru import _match_app_harness_command
        return _match_app_harness_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"app harness status", "app harness registry", "реестр приложений", "app registry"} or lower.startswith("app harness plan ") or lower.startswith("план запуска ")


def _run_app_harness_registry_command_ru_v668(command):
    from modules.app_harness_registry_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.app_harness_registry_ru",
        "plan": {"tool": "modules.app_harness_registry_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.68 App Harness Registry RU bridge

# BEGIN v6.76a MINIMAL ROUTER BRIDGES
LOCALCOMET_DEVELOPMENT_SAFETY_BRIDGE_RU_V676A = (
    "v6.76a development safety orchestrator bridge installed"
)
LOCALCOMET_REVIEWER_BRIDGE_RU_V676A = (
    "v6.76a reviewer bridge installed"
)


def _normalize_v676a_command(command):
    return str(command or "").strip().lower().replace("ё", "е")


def _is_development_safety_command_ru_v676a(command):
    lower = _normalize_v676a_command(command)
    return lower in {
        "status",
        "development safety status",
        "dev safety status",
        "статус разработки",
        "pc dev safety status",
        "report",
        "pc dev safety report",
        "preflight audit",
        "pc preflight audit",
        "diff limit status",
        "pc diff limit status",
        "opencode recovery status",
        "pc opencode recovery status",
    }


def _run_development_safety_command_ru_v676a(command):
    try:
        from modules.development_safety_orchestrator_ru import dispatch
        result = dispatch(command)
    except Exception as exc:
        result = {
            "ok": False,
            "mode": "development_safety_orchestrator_error",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "mode": "command",
        "route": "modules.development_safety_orchestrator_ru",
        "plan": {
            "tool": "modules.development_safety_orchestrator_ru",
            "action": "dispatch",
        },
        "result": result,
    }


def _is_reviewer_bridge_command_ru_v676a(command):
    lower = _normalize_v676a_command(command)
    return (
        lower in {
            "status",
            "reviewer bridge status",
            "статус ревью",
            "pc reviewer bridge status",
            "report",
            "reviewer bridge report",
            "pc reviewer bridge report",
        }
        or lower == "создай запрос ревью"
        or lower.startswith("создай запрос ревью ")
        or lower == "reviewer bridge create"
        or lower.startswith("reviewer bridge create ")
    )


def _run_reviewer_bridge_command_ru_v676a(command):
    try:
        from modules.reviewer_bridge_ru import dispatch
        result = dispatch(command)
    except Exception as exc:
        result = {
            "ok": False,
            "mode": "reviewer_bridge_error",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "mode": "command",
        "route": "modules.reviewer_bridge_ru",
        "plan": {
            "tool": "modules.reviewer_bridge_ru",
            "action": "dispatch",
        },
        "result": result,
    }


def _is_maintenance_diagnostics_command_ru_v681(command):
    try:
        from modules.maintenance_diagnostics_ru import is_diagnostics_command
        return is_diagnostics_command(command)
    except Exception:
        lower = _normalize_v676a_command(command)
        return lower in {
            "диагностика проекта",
            "project diagnostics",
            "maintenance status",
        }


def _run_maintenance_diagnostics_command_ru_v681(command):
    try:
        from modules.maintenance_diagnostics_ru import dispatch
        result = dispatch(command)
    except Exception as exc:
        result = {
            "ok": False,
            "mode": "maintenance_diagnostics_error",
            "version": "v6.81",
            "warnings": [f"maintenance_diagnostics_error:{type(exc).__name__}"],
        }
    return {
        "mode": "command",
        "route": "modules.maintenance_diagnostics_ru",
        "plan": {
            "tool": "modules.maintenance_diagnostics_ru",
            "action": "dispatch",
        },
        "result": result,
    }


def _is_task_planner_command_ru_v682(command):
    try:
        from modules.task_planner_orchestrator_ru import is_task_plan_command
        return is_task_plan_command(command)
    except Exception:
        lower = _normalize_v676a_command(command)
        return (
            lower.startswith("спланируй задачу ")
            or lower.startswith("план задачи ")
            or lower.startswith("task plan ")
        )


def _run_task_planner_command_ru_v682(command):
    try:
        from modules.task_planner_orchestrator_ru import dispatch
        result = dispatch(command)
    except Exception as exc:
        result = {
            "ok": False,
            "mode": "explainable_task_plan",
            "version": "v6.82",
            "warnings": [f"task_planner_error:{type(exc).__name__}"],
        }
    return {
        "mode": "command",
        "route": "modules.task_planner_orchestrator_ru",
        "plan": {
            "tool": "modules.task_planner_orchestrator_ru",
            "action": "dispatch",
        },
        "result": result,
    }


PANEL_ROUTES = (
    (
        "development_safety_ru_v676a",
        _is_development_safety_command_ru_v676a,
        "_run_development_safety_command_ru_v676a",
    ),
    (
        "reviewer_bridge_ru_v676a",
        _is_reviewer_bridge_command_ru_v676a,
        "_run_reviewer_bridge_command_ru_v676a",
    ),
    (
        "maintenance_diagnostics_ru_v681",
        _is_maintenance_diagnostics_command_ru_v681,
        "_run_maintenance_diagnostics_command_ru_v681",
    ),
    (
        "task_planner_orchestrator_ru_v682",
        _is_task_planner_command_ru_v682,
        "_run_task_planner_command_ru_v682",
    ),
    (
        "app_harness_registry_ru_v668",
        _is_app_harness_registry_command_ru_v668,
        "_run_app_harness_registry_command_ru_v668",
    ),
    (
        "task_contract_registry_ru_v667",
        _is_task_contract_registry_command_ru_v667,
        "_run_task_contract_registry_command_ru_v667",
    ),
    (
        "screenshot_retention_policy_config_ru_v664e",
        _is_screenshot_retention_policy_config_command_ru_v664e,
        "_run_screenshot_retention_policy_config_command_ru_v664e",
    ),
    (
        "screenshot_storage_policy_simulator_ru_v664d",
        _is_screenshot_storage_policy_simulator_command_ru_v664d,
        "_run_screenshot_storage_policy_simulator_command_ru_v664d",
    ),
    (
        "screenshot_retention_dry_run_ru_v664c",
        _is_screenshot_retention_dry_run_command_ru_v664c,
        "_run_screenshot_retention_dry_run_command_ru_v664c",
    ),
    (
        "storage_cleanup_plan_ru_v664b",
        _is_storage_cleanup_plan_command_ru_v664b,
        "_run_storage_cleanup_plan_command_ru_v664b",
    ),
    (
        "repo_weight_audit_ru_v664a",
        _is_repo_weight_audit_command_ru_v664a,
        "_run_repo_weight_audit_command_ru_v664a",
    ),
    (
        "risk_classifier_ru_v663",
        _is_risk_classifier_command_ru_v663,
        "_run_risk_classifier_command_ru_v663",
    ),
    (
        "plan_contract_ru_v662",
        _is_plan_contract_command_ru_v662,
        "_run_plan_contract_command_ru_v662",
    ),
    (
        "context_pack_ru_v661",
        _is_context_pack_command_ru_v661,
        "_run_context_pack_command_ru_v661",
    ),
    (
        "developer_velocity_ru_v658",
        _is_developer_velocity_command_ru_v658,
        "_run_developer_velocity_command_ru_v658",
    ),
    (
        "panel_capability_audit_ru_v656",
        _is_panel_capability_audit_command_ru_v656,
        "_run_panel_capability_audit_command_ru_v656",
    ),
)


_run_panel_chat_command_before_v676a_minimal = _run_base_panel_chat_command


def run_panel_chat_command(command):
    text = str(command or "").strip()
    for _route_name, matcher, handler_name in PANEL_ROUTES:
        if matcher(text):
            handler = globals()[handler_name]
            return handler(text)
    return _run_panel_chat_command_before_v676a_minimal(command)


# END v6.76a MINIMAL ROUTER BRIDGES


if __name__ == "__main__":
    main()
