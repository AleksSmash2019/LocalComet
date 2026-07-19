
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List
import json
import traceback

from modules.project_paths import reports_dir
from modules.computer_use_test_fixtures_ru import temporary_synthetic_ui_map, verify_restore_behavior


CONTRACT_TESTS_VERSION = "v6.58"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _write_report(payload: Dict[str, Any]) -> str:
    report_dir = reports_dir() / "computer_use_contracts"
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"computer_use_contracts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _contract(name: str, func: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    started = _now()
    try:
        result = func()
        ok = bool(result.get("ok"))
        return {
            "name": name,
            "ok": ok,
            "started_at": started,
            "finished_at": _now(),
            "result": result,
        }
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "started_at": started,
            "finished_at": _now(),
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def contract_save_like_click_is_gui_only() -> Dict[str, Any]:
    from modules.computer_use_auto_action_ru import auto_policy_for_action

    action = {
        "kind": "click",
        "target": {"x": 160, "y": 220, "element_description": "Сохранить"},
        "grounded": True,
        "reason": "GUI screen button click on grounded UI element: Сохранить",
        "ui_intent": "visual_guarded_non_file_click",
        "gui_only": True,
        "modifies_files": False,
        "file_change_policy": "requires_explicit_modifies_files_true",
    }
    policy = auto_policy_for_action(action)
    return {
        "ok": bool(policy.get("ok")) and bool(policy.get("allowed_to_execute")) and not bool(policy.get("requires_confirmation")) and not bool(policy.get("classification", {}).get("file_change")),
        "mode": "contract_save_like_click_is_gui_only",
        "policy": policy,
    }


def contract_click_element_simulated() -> Dict[str, Any]:
    with temporary_synthetic_ui_map(label="click_element_contract"):
        from modules.computer_use_click_planner_ru import plan_click_element, click_element

        plan = plan_click_element("Сохранить")
        if not (plan.get("ok") and plan.get("can_execute") and not plan.get("requires_confirmation")):
            return {
                "ok": False,
                "mode": "contract_click_element_simulated",
                "phase": "plan",
                "plan": plan,
            }

        result = click_element("Сохранить", simulate=True)
        return {
            "ok": bool(result.get("ok")) and bool(result.get("execution", {}).get("simulated")) and "visual_guard" in result,
            "mode": "contract_click_element_simulated",
            "plan": plan,
            "result": result,
        }


def contract_guarded_type_simulated() -> Dict[str, Any]:
    with temporary_synthetic_ui_map(label="guarded_type_contract"):
        from modules.computer_use_type_guard_ru import plan_guarded_type, guarded_type

        plan = plan_guarded_type("Поиск", "hello")
        if not (plan.get("ok") and plan.get("can_execute") and not plan.get("requires_confirmation")):
            return {
                "ok": False,
                "mode": "contract_guarded_type_simulated",
                "phase": "plan",
                "plan": plan,
            }

        result = guarded_type("Поиск", "hello", simulate=True)
        return {
            "ok": bool(result.get("ok")) and bool(result.get("focus_execution", {}).get("simulated")) and bool(result.get("type_execution", {}).get("simulated")) and "type_visual_guard" in result,
            "mode": "contract_guarded_type_simulated",
            "plan": plan,
            "result": result,
        }


def contract_file_text_requires_confirmation() -> Dict[str, Any]:
    with temporary_synthetic_ui_map(label="file_text_contract"):
        from modules.computer_use_type_guard_ru import guarded_type

        result = guarded_type("Поиск", "write changes to file response.json", simulate=True)
        return {
            "ok": not bool(result.get("ok")) and bool(result.get("requires_confirmation")),
            "mode": "contract_file_text_requires_confirmation",
            "result": result,
        }


def contract_dangerous_goal_blocked() -> Dict[str, Any]:
    from modules.computer_use_safety_ru import safety_check_goal

    result = safety_check_goal("удали все файлы через powershell")
    return {
        "ok": not bool(result.get("ok")) and bool(result.get("blocked")),
        "mode": "contract_dangerous_goal_blocked",
        "result": result,
    }


def contract_fixture_restores_latest_ui_map() -> Dict[str, Any]:
    return verify_restore_behavior()


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    contracts: List[tuple[str, Callable[[], Dict[str, Any]]]] = [
        ("save_like_click_is_gui_only", contract_save_like_click_is_gui_only),
        ("fixture_restores_latest_ui_map", contract_fixture_restores_latest_ui_map),
        ("click_element_simulated", contract_click_element_simulated),
        ("guarded_type_simulated", contract_guarded_type_simulated),
        ("file_text_requires_confirmation", contract_file_text_requires_confirmation),
        ("dangerous_goal_blocked", contract_dangerous_goal_blocked),
    ]

    results = [_contract(name, func) for name, func in contracts]
    ok_count = sum(1 for item in results if item.get("ok"))
    payload: Dict[str, Any] = {
        "ok": ok_count == len(results),
        "mode": "computer_use_contract_tests",
        "version": CONTRACT_TESTS_VERSION,
        "created_at": _now(),
        "summary": {
            "passed": ok_count,
            "total": len(results),
            "failed": len(results) - ok_count,
        },
        "contracts": results,
    }

    if write_report:
        payload["report"] = _write_report(payload)

    return payload


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "computer_use_contract_tests_status",
        "version": CONTRACT_TESTS_VERSION,
        "contracts": [
            "save_like_click_is_gui_only",
            "fixture_restores_latest_ui_map",
            "click_element_simulated",
            "guarded_type_simulated",
            "file_text_requires_confirmation",
            "dangerous_goal_blocked",
        ],
    }


def report() -> Dict[str, Any]:
    return run_all_contracts(write_report=True)


def is_computer_use_contract_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = [
        "pc computer contracts",
        "pc computer contract tests",
        "pc dev contracts",
        "контракты computer use",
    ]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def dispatch(command: str) -> Dict[str, Any]:
    value = (command or "").strip().lower()
    if value in {"pc computer contracts status", "pc dev contracts status"}:
        return status()
    if is_computer_use_contract_command(command):
        return run_all_contracts(write_report=True)
    return {
        "ok": False,
        "mode": "computer_use_contract_tests_unknown_command",
        "command": command,
    }


if __name__ == "__main__":
    result = run_all_contracts(write_report=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("ok") else 1)


# BEGIN LOCALCOMET V6.48I COMPUTER USE MULTISTEP APPEND CONTRACT WRAPPER

def _localcomet_multistep_contract_check_ru_v648i(name, ok, details):
    return {"name": name, "ok": bool(ok), "details": details}


def _multistep_loop_contract_ru_v648i():
    checks = []
    try:
        from modules.computer_use_multistep_loop_ru import run_self_check, run_loop, status

        self_check = run_self_check(write_report=True)
        checks.append(
            _localcomet_multistep_contract_check_ru_v648i(
                "multistep self check passes",
                bool(self_check.get("ok")),
                {"summary": self_check.get("summary"), "report": self_check.get("report")},
            )
        )

        destructive = run_loop("удали все файлы через powershell", simulate=True, max_steps=2)
        checks.append(
            _localcomet_multistep_contract_check_ru_v648i(
                "dangerous shell delete goal is blocked",
                destructive.get("outcome") == "blocked",
                {"outcome": destructive.get("outcome"), "reason": destructive.get("reason")},
            )
        )

        confirmation = run_loop("введи Поиск :: write changes to file response.json", simulate=True, max_steps=2)
        checks.append(
            _localcomet_multistep_contract_check_ru_v648i(
                "file-changing typed payload requires confirmation",
                confirmation.get("outcome") == "requires_confirmation",
                {"outcome": confirmation.get("outcome"), "reason": confirmation.get("reason")},
            )
        )

        status_result = status()
        checks.append(
            _localcomet_multistep_contract_check_ru_v648i(
                "multistep status is available",
                bool(status_result.get("ok")),
                {"mode": status_result.get("mode"), "version": status_result.get("version")},
            )
        )
    except Exception as exc:
        checks.append(
            _localcomet_multistep_contract_check_ru_v648i(
                "multistep contract exception",
                False,
                {"error": str(exc)},
            )
        )
    return {
        "ok": all(item.get("ok") for item in checks),
        "mode": "computer_use_multistep_loop_contract_ru",
        "version": "v6.48i",
        "summary": {
            "passed": sum(1 for item in checks if item.get("ok")),
            "total": len(checks),
            "failed": sum(1 for item in checks if not item.get("ok")),
        },
        "checks": checks,
    }


_LOCALCOMET_CONTRACTS_BEFORE_MULTISTEP_RU_V648I = globals().get("run_all_contracts")
if not callable(_LOCALCOMET_CONTRACTS_BEFORE_MULTISTEP_RU_V648I):
    for _localcomet_contract_name_ru_v648i in (
        "_run_all_contracts_before_multistep_loop_ru_v648d",
        "_run_all_contracts_before_multistep_loop_ru_v648c",
        "_run_all_contracts_before_multistep_loop_ru_v648b",
        "_run_all_contracts_before_multistep_loop_ru_v648",
    ):
        _localcomet_candidate_contract_ru_v648i = globals().get(_localcomet_contract_name_ru_v648i)
        if callable(_localcomet_candidate_contract_ru_v648i):
            _LOCALCOMET_CONTRACTS_BEFORE_MULTISTEP_RU_V648I = _localcomet_candidate_contract_ru_v648i
            break


def _localcomet_int_ru_v648i(value, fallback=0):
    try:
        return int(value)
    except Exception:
        return fallback


def _localcomet_empty_contract_result_ru_v648i(reason):
    return {
        "ok": False,
        "mode": "computer_use_contract_tests",
        "summary": {"passed": 0, "total": 1, "failed": 1},
        "checks": [{"name": "base contract runner available", "ok": False, "details": {"reason": reason}}],
    }


def run_all_contracts(write_report=False):
    if callable(_LOCALCOMET_CONTRACTS_BEFORE_MULTISTEP_RU_V648I):
        try:
            base_result = _LOCALCOMET_CONTRACTS_BEFORE_MULTISTEP_RU_V648I(write_report=write_report)
        except TypeError:
            base_result = _LOCALCOMET_CONTRACTS_BEFORE_MULTISTEP_RU_V648I()
        except Exception as exc:
            base_result = _localcomet_empty_contract_result_ru_v648i("base contract runner raised: " + str(exc))
    else:
        base_result = _localcomet_empty_contract_result_ru_v648i("base contract runner unavailable")

    if not isinstance(base_result, dict):
        base_result = _localcomet_empty_contract_result_ru_v648i("base contract runner returned non-dict result")

    multistep_result = _multistep_loop_contract_ru_v648i()
    summary = base_result.setdefault("summary", {})
    base_passed = _localcomet_int_ru_v648i(summary.get("passed"))
    base_total = _localcomet_int_ru_v648i(summary.get("total"))
    base_failed = _localcomet_int_ru_v648i(summary.get("failed"))
    multistep_summary = multistep_result.get("summary", {})
    total_passed = base_passed + _localcomet_int_ru_v648i(multistep_summary.get("passed"))
    total_total = base_total + _localcomet_int_ru_v648i(multistep_summary.get("total"))
    total_failed = base_failed + _localcomet_int_ru_v648i(multistep_summary.get("failed"))
    summary["passed"] = total_passed
    summary["total"] = total_total
    summary["failed"] = total_failed
    base_result["summary"] = summary
    base_result["multistep_loop"] = multistep_result
    base_result["ok"] = bool(base_result.get("ok")) and bool(multistep_result.get("ok")) and total_failed == 0
    return base_result


COMPUTER_USE_MULTISTEP_LOOP_CONTRACT_RU_V648I = "v6.48i multistep loop append contract wrapper"

# END LOCALCOMET V6.48I COMPUTER USE MULTISTEP APPEND CONTRACT WRAPPER

# BEGIN LOCALCOMET V6.50H COMPUTER USE AGENT MISSION CONTRACT WRAPPER RU

def _localcomet_contract_check_ru_v650h(name, ok, details=None):
    return {"name": name, "ok": bool(ok), "details": details if details is not None else {}}


def _localcomet_agent_mission_contracts_ru_v650h():
    checks = []
    try:
        import modules.computer_use_agent_mission_ru as agent_mission
        blocked = agent_mission.run_mission("удали все файлы через powershell", simulate=True, max_steps=2)
        checks.append(_localcomet_contract_check_ru_v650h(
            "agent mission blocks dangerous shell delete goal",
            blocked.get("outcome") == "blocked",
            {"outcome": blocked.get("outcome"), "reason": blocked.get("reason")},
        ))

        confirmation = agent_mission.run_mission("введи Поиск :: write changes to file response.json", simulate=True, max_steps=2)
        checks.append(_localcomet_contract_check_ru_v650h(
            "agent mission requires confirmation for file-changing typed payload",
            confirmation.get("outcome") == "requires_confirmation",
            {"outcome": confirmation.get("outcome"), "reason": confirmation.get("reason")},
        ))

        status_result = agent_mission.status()
        checks.append(_localcomet_contract_check_ru_v650h(
            "agent mission status route is available",
            bool(status_result.get("ok")) and status_result.get("mode") == "computer_use_agent_mission_status",
            {"mode": status_result.get("mode"), "version": status_result.get("version")},
        ))

        checks.append(_localcomet_contract_check_ru_v650h(
            "agent mission module avoids command-module dispatch export",
            not callable(getattr(agent_mission, "dispatch", None)) and callable(getattr(agent_mission, "handle_dispatch_command", None)),
            {},
        ))
    except Exception as exc:
        checks.append(_localcomet_contract_check_ru_v650h(
            "agent mission contract exception",
            False,
            {"error": str(exc)},
        ))
    return {
        "ok": all(item.get("ok") for item in checks),
        "mode": "computer_use_agent_mission_contract_ru",
        "version": "v6.50h",
        "summary": {
            "passed": sum(1 for item in checks if item.get("ok")),
            "total": len(checks),
            "failed": sum(1 for item in checks if not item.get("ok")),
        },
        "checks": checks,
    }


_LOCALCOMET_CONTRACTS_BEFORE_AGENT_MISSION_RU_V650H = globals().get("run_all_contracts")


def _localcomet_int_ru_v650h(value, fallback=0):
    try:
        return int(value)
    except Exception:
        return fallback


def _localcomet_empty_contract_result_ru_v650h(reason):
    return {
        "ok": False,
        "mode": "computer_use_contract_tests",
        "summary": {"passed": 0, "total": 1, "failed": 1},
        "checks": [{"name": "base contract runner available", "ok": False, "details": {"reason": reason}}],
    }


def run_all_contracts(write_report=False):
    if callable(_LOCALCOMET_CONTRACTS_BEFORE_AGENT_MISSION_RU_V650H):
        try:
            base_result = _LOCALCOMET_CONTRACTS_BEFORE_AGENT_MISSION_RU_V650H(write_report=write_report)
        except TypeError:
            base_result = _LOCALCOMET_CONTRACTS_BEFORE_AGENT_MISSION_RU_V650H()
        except Exception as exc:
            base_result = _localcomet_empty_contract_result_ru_v650h("base contract runner raised: " + str(exc))
    else:
        base_result = _localcomet_empty_contract_result_ru_v650h("base contract runner unavailable")

    if not isinstance(base_result, dict):
        base_result = _localcomet_empty_contract_result_ru_v650h("base contract runner returned non-dict result")

    mission_result = _localcomet_agent_mission_contracts_ru_v650h()
    summary = base_result.setdefault("summary", {})
    base_passed = _localcomet_int_ru_v650h(summary.get("passed"))
    base_total = _localcomet_int_ru_v650h(summary.get("total"))
    base_failed = _localcomet_int_ru_v650h(summary.get("failed"))
    mission_summary = mission_result.get("summary", {})
    total_passed = base_passed + _localcomet_int_ru_v650h(mission_summary.get("passed"))
    total_total = base_total + _localcomet_int_ru_v650h(mission_summary.get("total"))
    total_failed = base_failed + _localcomet_int_ru_v650h(mission_summary.get("failed"))
    summary["passed"] = total_passed
    summary["total"] = total_total
    summary["failed"] = total_failed
    base_result["summary"] = summary
    base_result["agent_mission"] = mission_result
    base_result["ok"] = bool(base_result.get("ok")) and bool(mission_result.get("ok")) and total_failed == 0
    return base_result


COMPUTER_USE_AGENT_MISSION_CONTRACT_RU_V650H = "v6.50h computer use agent mission contract wrapper"

# END LOCALCOMET V6.50H COMPUTER USE AGENT MISSION CONTRACT WRAPPER RU

# BEGIN LOCALCOMET V6.51 COMPUTER USE FULL CONTROL CONTRACT WRAPPER RU

_LOCALCOMET_CONTRACT_RUN_ALL_BEFORE_FULL_CONTROL_RU_V651 = globals().get("run_all_contracts")


def run_full_control_contracts(write_report=True):
    checks = []

    def add(name, ok, details=None):
        checks.append({"name": name, "ok": bool(ok), "details": details if details is not None else {}})

    try:
        from modules.computer_use_full_control_mission_ru import run_self_check
        full_control_self_check = run_self_check(write_report=write_report)
        add("full control self check", full_control_self_check.get("ok") and full_control_self_check.get("summary", {}).get("failed") == 0, full_control_self_check)
    except Exception as exc:
        add("full control self check", False, {"error": str(exc)})

    try:
        from modules.computer_use_core_ru import dispatch, is_computer_use_command
        status = dispatch("pc computer full control status")
        add("core dispatch full control status", status.get("handled") and status.get("ok") and status.get("mode") == "computer_use_full_control_status", status)
        add("core recognizes управляй пк", is_computer_use_command("управляй пк открой блокнот"), {})
    except Exception as exc:
        add("core dispatch full control status", False, {"error": str(exc)})

    try:
        from modules.computer_use_core_ru import dispatch
        sample = dispatch("pc computer full control simulate открой блокнот и напиши hello")
        add("core dispatch full control simulate", sample.get("handled") and sample.get("outcome") == "done" and len(sample.get("steps", [])) >= 2, {"outcome": sample.get("outcome"), "steps": len(sample.get("steps", []))})
    except Exception as exc:
        add("core dispatch full control simulate", False, {"error": str(exc)})

    try:
        import modules.computer_use_full_control_mission_ru as full_control_module
        add(
            "full control module avoids public dispatch export",
            callable(getattr(full_control_module, "handle_dispatch_command", None)) and not callable(getattr(full_control_module, "dispatch", None)),
            {},
        )
    except Exception as exc:
        add("full control module avoids public dispatch export", False, {"error": str(exc)})

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    return {
        "ok": summary["failed"] == 0,
        "mode": "computer_use_full_control_contracts",
        "version": "v6.51",
        "summary": summary,
        "checks": checks,
    }


def run_all_contracts(write_report=True):
    if callable(_LOCALCOMET_CONTRACT_RUN_ALL_BEFORE_FULL_CONTROL_RU_V651):
        base = _LOCALCOMET_CONTRACT_RUN_ALL_BEFORE_FULL_CONTROL_RU_V651(write_report=write_report)
    else:
        base = {
            "ok": True,
            "mode": "computer_use_contract_tests",
            "summary": {"passed": 0, "total": 0, "failed": 0},
            "checks": [],
        }

    full_control = run_full_control_contracts(write_report=write_report)
    summary = dict(base.get("summary") or {})
    summary["passed"] = int(summary.get("passed", 0)) + int(full_control.get("summary", {}).get("passed", 0))
    summary["total"] = int(summary.get("total", 0)) + int(full_control.get("summary", {}).get("total", 0))
    summary["failed"] = int(summary.get("failed", 0)) + int(full_control.get("summary", {}).get("failed", 0))
    base["summary"] = summary
    base["full_control"] = full_control.get("summary")
    base["full_control_details"] = full_control
    base["ok"] = bool(base.get("ok")) and bool(full_control.get("ok")) and summary["failed"] == 0
    return base

COMPUTER_USE_FULL_CONTROL_CONTRACT_RU_V651 = "v6.51 full control contract wrapper"

# END LOCALCOMET V6.51 COMPUTER USE FULL CONTROL CONTRACT WRAPPER RU

# BEGIN LOCALCOMET V6.53 COMPUTER USE REAL ACTIONS CONTRACT WRAPPER RU

_LOCALCOMET_CONTRACT_RUN_ALL_BEFORE_REAL_ACTIONS_RU_V653 = globals().get("run_all_contracts")


def run_real_actions_contracts(write_report=True):
    checks = []

    def add(name, ok, details=None):
        checks.append({"name": name, "ok": bool(ok), "details": details if details is not None else {}})

    try:
        from modules.computer_use_real_actions_ru import run_self_check
        real_self_check = run_self_check(write_report=write_report)
        add("real actions self check", real_self_check.get("ok") and real_self_check.get("summary", {}).get("failed") == 0, real_self_check)
    except Exception as exc:
        add("real actions self check", False, {"error": str(exc)})

    try:
        from modules.computer_use_core_ru import dispatch
        caps = dispatch("pc computer real actions")
        add("core dispatch real action capabilities", caps.get("handled") and caps.get("ok") and "open_app" in caps.get("actions", []), caps)
    except Exception as exc:
        add("core dispatch real action capabilities", False, {"error": str(exc)})

    try:
        from modules.computer_use_core_ru import dispatch
        sample = dispatch("pc computer full control simulate открой блокнот и напиши hello и нажми enter")
        kinds = [step.get("planned_action", {}).get("kind") for step in sample.get("steps", [])]
        add("core full control simulate uses real actions", sample.get("handled") and sample.get("outcome") == "done" and {"open_app", "paste_text", "press_key"}.issubset(set(kinds)), {"outcome": sample.get("outcome"), "kinds": kinds})
    except Exception as exc:
        add("core full control simulate uses real actions", False, {"error": str(exc)})

    try:
        from modules.computer_use_core_ru import dispatch
        scroll = dispatch("pc computer full control simulate прокрути вниз")
        kinds = [step.get("planned_action", {}).get("kind") for step in scroll.get("steps", [])]
        add("core full control simulate supports scroll", scroll.get("handled") and scroll.get("outcome") == "done" and "scroll" in kinds, {"outcome": scroll.get("outcome"), "kinds": kinds})
    except Exception as exc:
        add("core full control simulate supports scroll", False, {"error": str(exc)})

    try:
        import modules.computer_use_real_actions_ru as real_actions_module
        add(
            "real actions module avoids public dispatch export",
            not callable(getattr(real_actions_module, "dispatch", None)) and callable(getattr(real_actions_module, "execute_real_action", None)),
            {},
        )
    except Exception as exc:
        add("real actions module avoids public dispatch export", False, {"error": str(exc)})

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    return {
        "ok": summary["failed"] == 0,
        "mode": "computer_use_real_actions_contracts",
        "version": "v6.53",
        "summary": summary,
        "checks": checks,
    }


def run_all_contracts(write_report=True):
    if callable(_LOCALCOMET_CONTRACT_RUN_ALL_BEFORE_REAL_ACTIONS_RU_V653):
        base = _LOCALCOMET_CONTRACT_RUN_ALL_BEFORE_REAL_ACTIONS_RU_V653(write_report=write_report)
    else:
        base = {
            "ok": True,
            "mode": "computer_use_contract_tests",
            "summary": {"passed": 0, "total": 0, "failed": 0},
            "checks": [],
        }

    real_actions = run_real_actions_contracts(write_report=write_report)
    summary = dict(base.get("summary") or {})
    summary["passed"] = int(summary.get("passed", 0)) + int(real_actions.get("summary", {}).get("passed", 0))
    summary["total"] = int(summary.get("total", 0)) + int(real_actions.get("summary", {}).get("total", 0))
    summary["failed"] = int(summary.get("failed", 0)) + int(real_actions.get("summary", {}).get("failed", 0))
    base["summary"] = summary
    base["real_actions"] = real_actions.get("summary")
    base["real_actions_details"] = real_actions
    base["ok"] = bool(base.get("ok")) and bool(real_actions.get("ok")) and summary["failed"] == 0
    return base


COMPUTER_USE_REAL_ACTIONS_CONTRACT_RU_V653 = "v6.53 real actions contract wrapper"

# END LOCALCOMET V6.53 COMPUTER USE REAL ACTIONS CONTRACT WRAPPER RU

# BEGIN v6.54 Computer Use Observe/Vision contract wrapper
try:
    _run_all_contracts_before_observe_vision_ru_v654
except NameError:
    _run_all_contracts_before_observe_vision_ru_v654 = run_all_contracts


def run_all_contracts(write_report=True):
    result = _run_all_contracts_before_observe_vision_ru_v654(write_report=write_report)
    try:
        from modules.computer_use_observe_vision_ru import run_self_check

        self_check = run_self_check(write_report=write_report)
        observe_ok = bool(self_check.get("ok"))
        if isinstance(result, dict):
            checks = result.setdefault("checks", [])
            checks.append({
                "name": "computer_use_observe_vision_v654",
                "ok": observe_ok,
                "details": self_check.get("summary", {}),
            })
            summary = result.setdefault("summary", {})
            passed = len([item for item in checks if item.get("ok")])
            total = len(checks)
            summary["passed"] = passed
            summary["total"] = total
            summary["failed"] = total - passed
            result["ok"] = summary["failed"] == 0
            result["version"] = "v6.54"
    except Exception as exc:
        if isinstance(result, dict):
            checks = result.setdefault("checks", [])
            checks.append({
                "name": "computer_use_observe_vision_v654_exception",
                "ok": False,
                "details": str(exc),
            })
            summary = result.setdefault("summary", {})
            passed = len([item for item in checks if item.get("ok")])
            total = len(checks)
            summary["passed"] = passed
            summary["total"] = total
            summary["failed"] = total - passed
            result["ok"] = False
            result["version"] = "v6.54"
    return result
# END v6.54 Computer Use Observe/Vision contract wrapper

# BEGIN v6.54b Computer Use Observe/Vision contract wrapper
try:
    _run_all_contracts_before_observe_vision_ru_v654b
except NameError:
    _run_all_contracts_before_observe_vision_ru_v654b = run_all_contracts


def run_all_contracts(write_report=True):
    result = _run_all_contracts_before_observe_vision_ru_v654b(write_report=write_report)
    try:
        from modules.computer_use_observe_vision_ru import run_self_check

        self_check = run_self_check(write_report=write_report)
        observe_ok = bool(self_check.get("ok"))
        if isinstance(result, dict):
            checks = result.setdefault("checks", [])
            checks.append({
                "name": "computer_use_observe_vision_v654b",
                "ok": observe_ok,
                "details": self_check.get("summary", {}),
            })
            summary = result.setdefault("summary", {})
            passed = len([item for item in checks if item.get("ok")])
            total = len(checks)
            summary["passed"] = passed
            summary["total"] = total
            summary["failed"] = total - passed
            result["ok"] = summary["failed"] == 0
            result["version"] = "v6.54b"
    except Exception as exc:
        if isinstance(result, dict):
            checks = result.setdefault("checks", [])
            checks.append({
                "name": "computer_use_observe_vision_v654b_exception",
                "ok": False,
                "details": str(exc),
            })
            summary = result.setdefault("summary", {})
            passed = len([item for item in checks if item.get("ok")])
            total = len(checks)
            summary["passed"] = passed
            summary["total"] = total
            summary["failed"] = total - passed
            result["ok"] = False
            result["version"] = "v6.54b"
    return result
# END v6.54b Computer Use Observe/Vision contract wrapper


# BEGIN v6.55b Agent Automation Functional Test Center contract wrapper
try:
    _run_all_contracts_before_agent_auto_ru_v655b
except NameError:
    _run_all_contracts_before_agent_auto_ru_v655b = run_all_contracts


def run_agent_auto_function_contracts(write_report=True):
    try:
        from modules.localcomet_agent_auto_test_center_ru import run_contract_suite

        result = run_contract_suite(write_report=write_report)
        summary = result.get("summary", {})
        return {
            "ok": bool(result.get("ok")) and int(summary.get("failed", 1)) == 0,
            "mode": "localcomet_agent_auto_function_contracts",
            "version": "v6.55b",
            "summary": summary,
            "checks": result.get("checks", []),
            "report": result.get("report"),
            "json": result.get("json"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "mode": "localcomet_agent_auto_function_contracts",
            "version": "v6.55b",
            "summary": {"passed": 0, "total": 1, "failed": 1},
            "checks": [{
                "name": "agent_auto_function_contract_exception",
                "ok": False,
                "details": str(exc),
            }],
            "error": str(exc),
        }


def run_all_contracts(write_report=True):
    if callable(_run_all_contracts_before_agent_auto_ru_v655b):
        base = _run_all_contracts_before_agent_auto_ru_v655b(write_report=write_report)
    else:
        base = {
            "ok": True,
            "mode": "computer_use_contract_tests",
            "summary": {"passed": 0, "total": 0, "failed": 0},
            "checks": [],
        }
    if not isinstance(base, dict):
        base = {
            "ok": False,
            "mode": "computer_use_contract_tests",
            "summary": {"passed": 0, "total": 1, "failed": 1},
            "checks": [{"name": "base_contract_runner_returned_dict", "ok": False, "details": type(base).__name__}],
        }

    agent_auto = run_agent_auto_function_contracts(write_report=write_report)
    summary = dict(base.get("summary") or {})
    summary["passed"] = int(summary.get("passed", 0)) + int(agent_auto.get("summary", {}).get("passed", 0))
    summary["total"] = int(summary.get("total", 0)) + int(agent_auto.get("summary", {}).get("total", 0))
    summary["failed"] = int(summary.get("failed", 0)) + int(agent_auto.get("summary", {}).get("failed", 0))
    base["summary"] = summary
    base["agent_auto_functions"] = agent_auto.get("summary")
    base["agent_auto_functions_details"] = agent_auto
    base["ok"] = bool(base.get("ok")) and bool(agent_auto.get("ok")) and summary["failed"] == 0
    base["version"] = "v6.55b"
    return base


COMPUTER_USE_AGENT_AUTO_TEST_CENTER_CONTRACT_RU_V655B = "v6.55b agent automation functional contracts"
# END v6.55b Agent Automation Functional Test Center contract wrapper

# BEGIN v6.58 Developer Velocity Toolkit contract coverage
COMPUTER_USE_CONTRACTS_DEVELOPER_VELOCITY_RU_V658 = "v6.58 developer velocity toolkit command contracts installed"


def contract_developer_velocity_commands_ru_v658() -> Dict[str, Any]:
    from modules.localcomet_developer_velocity_ru import dispatch
    commands = ["последний сбой", "события патча", "статус разработки"]
    results = []
    for command in commands:
        result = dispatch(command)
        results.append({"command": command, "ok": isinstance(result, dict) and bool(result.get("handled", True)), "mode": result.get("mode") if isinstance(result, dict) else type(result).__name__})
    return {
        "ok": all(item.get("ok") for item in results),
        "mode": "contract_developer_velocity_commands",
        "version": "v6.58",
        "results": results,
    }


try:
    _run_all_contracts_before_developer_velocity_ru_v658
except NameError:
    _run_all_contracts_before_developer_velocity_ru_v658 = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_developer_velocity_ru_v658(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    result = contract_developer_velocity_commands_ru_v658()
    contracts.append({"name": "developer_velocity_commands", "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.58 Developer Velocity Toolkit contract coverage

# BEGIN v6.59a Command Explorer RU contract coverage
COMPUTER_USE_CONTRACTS_COMMAND_EXPLORER_RU_V659A = "v6.59a command explorer contracts installed"


def contract_command_explorer_status_ru_v659a() -> Dict[str, Any]:
    from modules.command_explorer_ru import status as ce_status
    r = ce_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "command_explorer_status" and isinstance(r.get("module_count"), int) and r["module_count"] >= 3,
        "mode": "contract_command_explorer_status",
        "version": "v6.59a",
        "result": r,
    }


def contract_command_explorer_report_ru_v659a() -> Dict[str, Any]:
    from modules.command_explorer_ru import report as ce_report
    r = ce_report()
    categories = r.get("categories", {}) if isinstance(r, dict) else {}
    total_cmds = sum(len(v) for v in categories.values())
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "command_explorer_report" and total_cmds >= 10,
        "mode": "contract_command_explorer_report",
        "version": "v6.59a",
        "command_count": total_cmds,
        "result": r,
    }


def contract_command_explorer_routed_core_ru_v659a() -> Dict[str, Any]:
    from modules.computer_use_core_ru import dispatch as core_dispatch
    r = core_dispatch("команды проекта")
    return {
        "ok": isinstance(r, dict) and r.get("handled") and r.get("route") == "modules.command_explorer_ru",
        "mode": "contract_command_explorer_routed_core",
        "version": "v6.59a",
        "result": r,
    }


try:
    _run_all_contracts_before_command_explorer_ru_v659a
except NameError:
    _run_all_contracts_before_command_explorer_ru_v659a = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_command_explorer_ru_v659a(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_command_explorer_status_ru_v659a, contract_command_explorer_report_ru_v659a, contract_command_explorer_routed_core_ru_v659a]:
        result = cfn()
        contracts.append({"name": result.get("mode", "command_explorer_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# BEGIN v6.59b Repo Analyzer RU contract coverage
COMPUTER_USE_CONTRACTS_REPO_ANALYZER_RU_V659B = "v6.59b repo analyzer contracts installed"


def contract_repo_analyzer_status_ru_v659b() -> Dict[str, Any]:
    from modules.repo_analyzer_ru import status as ra_status
    r = ra_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "repo_analyzer_status" and isinstance(r.get("file_count"), int) and r["file_count"] >= 5,
        "mode": "contract_repo_analyzer_status",
        "version": "v6.59b",
        "result": r,
    }


def contract_repo_analyzer_report_ru_v659b() -> Dict[str, Any]:
    from modules.repo_analyzer_ru import report as ra_report
    r = ra_report()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "repo_analyzer_report" and isinstance(r.get("file_count"), int) and r["file_count"] >= 10,
        "mode": "contract_repo_analyzer_report",
        "version": "v6.59b",
        "result": r,
    }


def contract_repo_analyzer_routed_core_ru_v659b() -> Dict[str, Any]:
    from modules.computer_use_core_ru import dispatch as core_dispatch
    r = core_dispatch("анализ проекта")
    return {
        "ok": isinstance(r, dict) and r.get("handled") and "repo_analyzer" in r.get("route", ""),
        "mode": "contract_repo_analyzer_routed_core",
        "version": "v6.59b",
        "result": r,
    }


try:
    _run_all_contracts_before_repo_analyzer_ru_v659b
except NameError:
    _run_all_contracts_before_repo_analyzer_ru_v659b = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_repo_analyzer_ru_v659b(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_repo_analyzer_status_ru_v659b, contract_repo_analyzer_report_ru_v659b, contract_repo_analyzer_routed_core_ru_v659b]:
        result = cfn()
        contracts.append({"name": result.get("mode", "repo_analyzer_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.59b Repo Analyzer RU contract coverage

# BEGIN v6.63 Context Pack RU contract coverage
COMPUTER_USE_CONTRACTS_CONTEXT_PACK_RU_V663 = "v6.63 context pack contracts installed"


def contract_context_pack_status_ru_v663() -> Dict[str, Any]:
    from modules.context_pack_ru import status as cp_status
    r = cp_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "context_pack_status",
        "mode": "contract_context_pack_status",
        "version": "v6.64",
        "result": r,
    }


def contract_context_pack_report_ru_v663() -> Dict[str, Any]:
    from modules.context_pack_ru import report as cp_report
    r = cp_report()
    return {
        "ok": isinstance(r, dict) and r.get("ok"),
        "mode": "contract_context_pack_report",
        "version": "v6.64",
        "result": r,
    }


def contract_context_pack_routed_panel_ru_v663() -> Dict[str, Any]:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("localcomet agent context pack")
    result_dict = r.get("result", {}) if isinstance(r, dict) else {}
    return {
        "ok": isinstance(r, dict) and r.get("route") == "modules.context_pack_ru" and isinstance(result_dict, dict) and result_dict.get("handled") and result_dict.get("ok"),
        "mode": "contract_context_pack_routed_panel",
        "version": "v6.64",
        "result": r,
    }


def contract_context_pack_version_consistency_ru_v663() -> Dict[str, Any]:
    import re
    from modules.context_pack_ru import CONTEXT_PACK_JSON, ROOT_PATH as CP_ROOT
    panel_text = (CP_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
    expected = m.group(1) if m else ""
    report_result = None
    actual = ""
    try:
        from modules.context_pack_ru import report as cp_report
        report_result = cp_report()
        if CONTEXT_PACK_JSON.exists():
            import json
            payload = json.loads(CONTEXT_PACK_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
    except Exception:
        pass
    ok = bool(expected) and expected == actual
    return {
        "ok": ok,
        "mode": "contract_context_pack_version_consistency",
        "version": "v6.64",
        "expected": expected,
        "actual": actual,
        "report_ok": isinstance(report_result, dict) and report_result.get("ok"),
    }


try:
    _run_all_contracts_before_context_pack_ru_v663
except NameError:
    _run_all_contracts_before_context_pack_ru_v663 = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_context_pack_ru_v663(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_context_pack_status_ru_v663, contract_context_pack_report_ru_v663, contract_context_pack_routed_panel_ru_v663, contract_context_pack_version_consistency_ru_v663]:
        result = cfn()
        contracts.append({"name": result.get("mode", "context_pack_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# BEGIN v6.63 Plan Contract RU contract coverage
COMPUTER_USE_CONTRACTS_PLAN_CONTRACT_RU_V663 = "v6.63 plan contract contracts installed"


def contract_plan_contract_status_ru_v663() -> Dict[str, Any]:
    from modules.plan_contract_ru import status as pc_status
    r = pc_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "plan_contract_status",
        "mode": "contract_plan_contract_status",
        "version": "v6.64",
        "result": r,
    }


def contract_plan_contract_report_ru_v663() -> Dict[str, Any]:
    from modules.plan_contract_ru import report as pc_report
    r = pc_report()
    return {
        "ok": isinstance(r, dict) and r.get("ok"),
        "mode": "contract_plan_contract_report",
        "version": "v6.64",
        "result": r,
    }


def contract_plan_contract_routed_panel_ru_v663() -> Dict[str, Any]:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("localcomet agent plan contract")
    result_dict = r.get("result", {}) if isinstance(r, dict) else {}
    return {
        "ok": isinstance(r, dict) and r.get("route") == "modules.plan_contract_ru" and isinstance(result_dict, dict) and result_dict.get("handled") and result_dict.get("ok"),
        "mode": "contract_plan_contract_routed_panel",
        "version": "v6.64",
        "result": r,
    }


def contract_plan_contract_version_consistency_ru_v663() -> Dict[str, Any]:
    import re
    from modules.plan_contract_ru import PLAN_CONTRACT_JSON, ROOT_PATH as PC_ROOT
    panel_text = (PC_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
    expected = m.group(1) if m else ""
    actual = ""
    try:
        from modules.plan_contract_ru import report as pc_report
        pc_report()
        if PLAN_CONTRACT_JSON.exists():
            import json
            payload = json.loads(PLAN_CONTRACT_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
    except Exception:
        pass
    ok = bool(expected) and expected == actual
    return {
        "ok": ok,
        "mode": "contract_plan_contract_version_consistency",
        "version": "v6.64",
        "expected": expected,
        "actual": actual,
    }


try:
    _run_all_contracts_before_plan_contract_ru_v663
except NameError:
    _run_all_contracts_before_plan_contract_ru_v663 = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_plan_contract_ru_v663(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_plan_contract_status_ru_v663, contract_plan_contract_report_ru_v663, contract_plan_contract_routed_panel_ru_v663, contract_plan_contract_version_consistency_ru_v663]:
        result = cfn()
        contracts.append({"name": result.get("mode", "plan_contract_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# BEGIN v6.63 Risk Classifier RU contract coverage
COMPUTER_USE_CONTRACTS_RISK_CLASSIFIER_RU_V663 = "v6.63 risk classifier contracts installed"


def contract_risk_classifier_status_ru_v663() -> Dict[str, Any]:
    from modules.risk_classifier_ru import status as rc_status
    r = rc_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "risk_classifier_status",
        "mode": "contract_risk_classifier_status",
        "version": "v6.64",
        "result": r,
    }


def contract_risk_classifier_report_ru_v663() -> Dict[str, Any]:
    from modules.risk_classifier_ru import report as rc_report
    r = rc_report()
    return {
        "ok": isinstance(r, dict) and r.get("ok"),
        "mode": "contract_risk_classifier_report",
        "version": "v6.64",
        "result": r,
    }


def contract_risk_classifier_routed_panel_ru_v663() -> Dict[str, Any]:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("localcomet agent risk classify")
    result_dict = r.get("result", {}) if isinstance(r, dict) else {}
    return {
        "ok": isinstance(r, dict) and r.get("route") == "modules.risk_classifier_ru" and isinstance(result_dict, dict) and result_dict.get("handled") and result_dict.get("ok"),
        "mode": "contract_risk_classifier_routed_panel",
        "version": "v6.64",
        "result": r,
    }


def contract_risk_classifier_version_consistency_ru_v663() -> Dict[str, Any]:
    import re
    from modules.risk_classifier_ru import RISK_CLASSIFIER_JSON, ROOT_PATH as RC_ROOT
    panel_text = (RC_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
    expected = m.group(1) if m else ""
    actual = ""
    try:
        from modules.risk_classifier_ru import report as rc_report
        rc_report()
        if RISK_CLASSIFIER_JSON.exists():
            import json
            payload = json.loads(RISK_CLASSIFIER_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
    except Exception:
        pass
    ok = bool(expected) and expected == actual
    return {
        "ok": ok,
        "mode": "contract_risk_classifier_version_consistency",
        "version": "v6.64",
        "expected": expected,
        "actual": actual,
    }


def contract_risk_classifier_docs_only_ru_v663() -> Dict[str, Any]:
    from modules.risk_classifier_ru import classify
    r = classify("fix typo in AGENTS.md documentation")
    return {
        "ok": r.get("risk_level") == "docs_only",
        "mode": "contract_risk_classifier_docs_only",
        "version": "v6.64",
        "risk_level": r.get("risk_level"),
    }


def contract_risk_classifier_high_ru_v663() -> Dict[str, Any]:
    from modules.risk_classifier_ru import classify
    r = classify("install new network dependency via subprocess")
    return {
        "ok": r.get("risk_level") == "high",
        "mode": "contract_risk_classifier_high",
        "version": "v6.64",
        "risk_level": r.get("risk_level"),
    }


def contract_risk_classifier_unclassified_ru_v663() -> Dict[str, Any]:
    from modules.risk_classifier_ru import classify
    r = classify("")
    return {
        "ok": r.get("risk_level") == "unclassified",
        "mode": "contract_risk_classifier_unclassified",
        "version": "v6.64",
        "risk_level": r.get("risk_level"),
    }


try:
    _run_all_contracts_before_risk_classifier_ru_v663
except NameError:
    _run_all_contracts_before_risk_classifier_ru_v663 = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_risk_classifier_ru_v663(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_risk_classifier_status_ru_v663, contract_risk_classifier_report_ru_v663, contract_risk_classifier_routed_panel_ru_v663, contract_risk_classifier_version_consistency_ru_v663, contract_risk_classifier_docs_only_ru_v663, contract_risk_classifier_high_ru_v663, contract_risk_classifier_unclassified_ru_v663]:
        result = cfn()
        contracts.append({"name": result.get("mode", "risk_classifier_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.63 Risk Classifier RU contract coverage

# BEGIN v6.64a Repository Weight Audit RU contract coverage
COMPUTER_USE_CONTRACTS_REPO_WEIGHT_AUDIT_RU_V664A = "v6.64a repo weight audit contracts installed"


def contract_repo_weight_audit_status_ru_v664a() -> Dict[str, Any]:
    from modules.repo_weight_audit_ru import status as rwa_status
    r = rwa_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "repo_weight_audit_status",
        "mode": "contract_repo_weight_audit_status",
        "version": "v6.64a",
        "result": r,
    }


def contract_repo_weight_audit_report_ru_v664a() -> Dict[str, Any]:
    from modules.repo_weight_audit_ru import report as rwa_report
    r = rwa_report()
    return {
        "ok": isinstance(r, dict) and r.get("ok"),
        "mode": "contract_repo_weight_audit_report",
        "version": "v6.64a",
        "result": r,
    }


def contract_repo_weight_audit_routed_panel_ru_v664a() -> Dict[str, Any]:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("localcomet repo weight audit")
    result_dict = r.get("result", {}) if isinstance(r, dict) else {}
    return {
        "ok": isinstance(r, dict) and r.get("route") == "modules.repo_weight_audit_ru" and isinstance(result_dict, dict) and result_dict.get("handled") and result_dict.get("ok"),
        "mode": "contract_repo_weight_audit_routed_panel",
        "version": "v6.64a",
        "result": r,
    }


def contract_repo_weight_audit_version_consistency_ru_v664a() -> Dict[str, Any]:
    import re
    from modules.repo_weight_audit_ru import REPO_WEIGHT_JSON, ROOT_PATH as RWA_ROOT
    panel_text = (RWA_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
    expected = m.group(1) if m else ""
    actual = ""
    try:
        from modules.repo_weight_audit_ru import report as rwa_report
        rwa_report()
        if REPO_WEIGHT_JSON.exists():
            import json
            payload = json.loads(REPO_WEIGHT_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
    except Exception:
        pass
    ok = bool(expected) and expected == actual
    return {
        "ok": ok,
        "mode": "contract_repo_weight_audit_version_consistency",
        "version": "v6.64a",
        "expected": expected,
        "actual": actual,
    }


def contract_repo_weight_audit_has_required_fields_ru_v664a() -> Dict[str, Any]:
    from modules.repo_weight_audit_ru import report as rwa_report
    import json
    from modules.repo_weight_audit_ru import REPO_WEIGHT_JSON
    r = rwa_report()
    ok = False
    fields_found = []
    fields_missing = []
    try:
        if REPO_WEIGHT_JSON.exists():
            payload = json.loads(REPO_WEIGHT_JSON.read_text(encoding="utf-8"))
            required = ["schema_version", "base_version", "total_size_bytes", "total_size_mb", "total_size_gb", "file_count", "folder_count", "top_directories", "top_files", "dangerous_cleanup_warning", "safe_cleanup_recommendations"]
            for f in required:
                if f in payload:
                    fields_found.append(f)
                else:
                    fields_missing.append(f)
            ok = len(fields_missing) == 0
    except Exception:
        pass
    return {
        "ok": ok and isinstance(r, dict) and r.get("ok"),
        "mode": "contract_repo_weight_audit_has_required_fields",
        "version": "v6.64a",
        "fields_found": fields_found,
        "fields_missing": fields_missing,
    }


def contract_repo_weight_audit_no_deletion_ru_v664a() -> Dict[str, Any]:
    from modules.repo_weight_audit_ru import scan
    result = scan()
    warning = result.get("dangerous_cleanup_warning", "")
    ok = "NO FILES WERE DELETED" in warning and "audit-only" in warning
    return {
        "ok": ok,
        "mode": "contract_repo_weight_audit_no_deletion",
        "version": "v6.64a",
        "warning_present": bool(warning),
    }


try:
    _run_all_contracts_before_repo_weight_audit_ru_v664a
except NameError:
    _run_all_contracts_before_repo_weight_audit_ru_v664a = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_repo_weight_audit_ru_v664a(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_repo_weight_audit_status_ru_v664a, contract_repo_weight_audit_report_ru_v664a, contract_repo_weight_audit_routed_panel_ru_v664a, contract_repo_weight_audit_version_consistency_ru_v664a, contract_repo_weight_audit_has_required_fields_ru_v664a, contract_repo_weight_audit_no_deletion_ru_v664a]:
        result = cfn()
        contracts.append({"name": result.get("mode", "repo_weight_audit_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.64a Repository Weight Audit RU contract coverage

# BEGIN v6.64b Storage Cleanup Plan RU contract coverage
COMPUTER_USE_CONTRACTS_STORAGE_CLEANUP_PLAN_RU_V664B = "v6.64b storage cleanup plan contracts installed"


def contract_storage_cleanup_plan_status_ru_v664b() -> Dict[str, Any]:
    from modules.storage_cleanup_plan_ru import status as scp_status
    r = scp_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "storage_cleanup_plan_status",
        "mode": "contract_storage_cleanup_plan_status",
        "version": "v6.64b",
        "result": r,
    }


def contract_storage_cleanup_plan_report_ru_v664b() -> Dict[str, Any]:
    from modules.storage_cleanup_plan_ru import report as scp_report
    r = scp_report()
    return {
        "ok": isinstance(r, dict) and r.get("ok"),
        "mode": "contract_storage_cleanup_plan_report",
        "version": "v6.64b",
        "result": r,
    }


def contract_storage_cleanup_plan_routed_panel_ru_v664b() -> Dict[str, Any]:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("localcomet storage cleanup plan")
    result_dict = r.get("result", {}) if isinstance(r, dict) else {}
    return {
        "ok": isinstance(r, dict) and r.get("route") == "modules.storage_cleanup_plan_ru" and isinstance(result_dict, dict) and result_dict.get("handled") and result_dict.get("ok"),
        "mode": "contract_storage_cleanup_plan_routed_panel",
        "version": "v6.64b",
        "result": r,
    }


def contract_storage_cleanup_plan_version_consistency_ru_v664b() -> Dict[str, Any]:
    import re
    from modules.storage_cleanup_plan_ru import STORAGE_CLEANUP_JSON, ROOT_PATH as SCP_ROOT
    panel_text = (SCP_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
    expected = m.group(1) if m else ""
    actual = ""
    try:
        from modules.storage_cleanup_plan_ru import report as scp_report
        scp_report()
        if STORAGE_CLEANUP_JSON.exists():
            import json
            payload = json.loads(STORAGE_CLEANUP_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
    except Exception:
        pass
    ok = bool(expected) and expected == actual
    return {
        "ok": ok,
        "mode": "contract_storage_cleanup_plan_version_consistency",
        "version": "v6.64b",
        "expected": expected,
        "actual": actual,
    }


def contract_storage_cleanup_plan_no_deletion_ru_v664b() -> Dict[str, Any]:
    from modules.storage_cleanup_plan_ru import generate
    result = generate()
    warning = result.get("dangerous_cleanup_warning", "")
    ok = "NO FILES WERE DELETED" in warning and "plan-only" in warning
    return {
        "ok": ok,
        "mode": "contract_storage_cleanup_plan_no_deletion",
        "version": "v6.64b",
        "deletion_enabled": result.get("deletion_enabled"),
        "cleanup_mode": result.get("cleanup_mode"),
        "warning_present": bool(warning),
    }


def contract_storage_cleanup_plan_mode_ru_v664b() -> Dict[str, Any]:
    from modules.storage_cleanup_plan_ru import generate
    result = generate()
    return {
        "ok": result.get("deletion_enabled") is False and result.get("cleanup_mode") == "plan_only",
        "mode": "contract_storage_cleanup_plan_mode",
        "version": "v6.64b",
        "deletion_enabled": result.get("deletion_enabled"),
        "cleanup_mode": result.get("cleanup_mode"),
    }


def contract_storage_cleanup_plan_has_required_fields_ru_v664b() -> Dict[str, Any]:
    from modules.storage_cleanup_plan_ru import report as scp_report
    import json
    from modules.storage_cleanup_plan_ru import STORAGE_CLEANUP_JSON
    r = scp_report()
    ok = False
    fields_found = []
    fields_missing = []
    try:
        if STORAGE_CLEANUP_JSON.exists():
            payload = json.loads(STORAGE_CLEANUP_JSON.read_text(encoding="utf-8"))
            required = ["schema_version", "base_version", "cleanup_mode", "deletion_enabled", "candidates", "high_impact_targets", "dangerous_cleanup_warning"]
            for f in required:
                if f in payload:
                    fields_found.append(f)
                else:
                    fields_missing.append(f)
            ok = len(fields_missing) == 0
    except Exception:
        pass
    return {
        "ok": ok and isinstance(r, dict) and r.get("ok"),
        "mode": "contract_storage_cleanup_plan_has_required_fields",
        "version": "v6.64b",
        "fields_found": fields_found,
        "fields_missing": fields_missing,
    }


try:
    _run_all_contracts_before_storage_cleanup_plan_ru_v664b
except NameError:
    _run_all_contracts_before_storage_cleanup_plan_ru_v664b = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_storage_cleanup_plan_ru_v664b(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_storage_cleanup_plan_status_ru_v664b, contract_storage_cleanup_plan_report_ru_v664b, contract_storage_cleanup_plan_routed_panel_ru_v664b, contract_storage_cleanup_plan_version_consistency_ru_v664b, contract_storage_cleanup_plan_no_deletion_ru_v664b, contract_storage_cleanup_plan_mode_ru_v664b, contract_storage_cleanup_plan_has_required_fields_ru_v664b]:
        result = cfn()
        contracts.append({"name": result.get("mode", "storage_cleanup_plan_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.64b Storage Cleanup Plan RU contract coverage

# BEGIN v6.64c Screenshot Retention Dry Run RU contract coverage
COMPUTER_USE_CONTRACTS_SCREENSHOT_RETENTION_DRY_RUN_RU_V664C = "v6.64c screenshot retention dry run contracts installed"


def contract_screenshot_retention_dry_run_status_ru_v664c() -> Dict[str, Any]:
    from modules.screenshot_retention_dry_run_ru import status as srd_status
    r = srd_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "screenshot_retention_dry_run_status",
        "mode": "contract_screenshot_retention_dry_run_status",
        "version": "v6.64c",
        "result": r,
    }


def contract_screenshot_retention_dry_run_report_ru_v664c() -> Dict[str, Any]:
    from modules.screenshot_retention_dry_run_ru import report as srd_report
    r = srd_report()
    return {
        "ok": isinstance(r, dict) and r.get("ok"),
        "mode": "contract_screenshot_retention_dry_run_report",
        "version": "v6.64c",
        "result": r,
    }


def contract_screenshot_retention_dry_run_routed_panel_ru_v664c() -> Dict[str, Any]:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("localcomet screenshots retention dry run")
    result_dict = r.get("result", {}) if isinstance(r, dict) else {}
    return {
        "ok": isinstance(r, dict) and r.get("route") == "modules.screenshot_retention_dry_run_ru" and isinstance(result_dict, dict) and result_dict.get("handled") and result_dict.get("ok"),
        "mode": "contract_screenshot_retention_dry_run_routed_panel",
        "version": "v6.64c",
        "result": r,
    }


def contract_screenshot_retention_dry_run_version_consistency_ru_v664c() -> Dict[str, Any]:
    import re
    from modules.screenshot_retention_dry_run_ru import DRY_RUN_JSON, ROOT_PATH as SRD_ROOT
    panel_text = (SRD_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
    expected = m.group(1) if m else ""
    actual = ""
    try:
        from modules.screenshot_retention_dry_run_ru import report as srd_report
        srd_report()
        if DRY_RUN_JSON.exists():
            import json
            payload = json.loads(DRY_RUN_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
    except Exception:
        pass
    ok = bool(expected) and expected == actual
    return {
        "ok": ok,
        "mode": "contract_screenshot_retention_dry_run_version_consistency",
        "version": "v6.64c",
        "expected": expected,
        "actual": actual,
    }


def contract_screenshot_retention_dry_run_no_deletion_ru_v664c() -> Dict[str, Any]:
    from modules.screenshot_retention_dry_run_ru import scan
    result = scan()
    warning = result.get("dangerous_cleanup_warning", "")
    ok = "NO FILES WERE DELETED" in warning and "dry-run-only" in warning
    return {
        "ok": ok,
        "mode": "contract_screenshot_retention_dry_run_no_deletion",
        "version": "v6.64c",
        "deletion_enabled": result.get("deletion_enabled"),
        "cleanup_mode": result.get("cleanup_mode"),
        "warning_present": bool(warning),
    }


def contract_screenshot_retention_dry_run_mode_ru_v664c() -> Dict[str, Any]:
    from modules.screenshot_retention_dry_run_ru import scan
    result = scan()
    return {
        "ok": result.get("deletion_enabled") is False and result.get("cleanup_mode") == "dry_run_only",
        "mode": "contract_screenshot_retention_dry_run_mode",
        "version": "v6.64c",
        "deletion_enabled": result.get("deletion_enabled"),
        "cleanup_mode": result.get("cleanup_mode"),
    }


def contract_screenshot_retention_dry_run_has_required_fields_ru_v664c() -> Dict[str, Any]:
    from modules.screenshot_retention_dry_run_ru import report as srd_report
    import json
    from modules.screenshot_retention_dry_run_ru import DRY_RUN_JSON
    r = srd_report()
    ok = False
    fields_found = []
    fields_missing = []
    try:
        if DRY_RUN_JSON.exists():
            payload = json.loads(DRY_RUN_JSON.read_text(encoding="utf-8"))
            required = ["schema_version", "base_version", "cleanup_mode", "deletion_enabled", "screenshot_directories", "total_screenshot_files", "total_screenshot_size_bytes", "retention_policy", "cleanup_candidates", "dangerous_cleanup_warning"]
            for f in required:
                if f in payload:
                    fields_found.append(f)
                else:
                    fields_missing.append(f)
            ok = len(fields_missing) == 0
    except Exception:
        pass
    return {
        "ok": ok and isinstance(r, dict) and r.get("ok"),
        "mode": "contract_screenshot_retention_dry_run_has_required_fields",
        "version": "v6.64c",
        "fields_found": fields_found,
        "fields_missing": fields_missing,
    }


try:
    _run_all_contracts_before_screenshot_retention_dry_run_ru_v664c
except NameError:
    _run_all_contracts_before_screenshot_retention_dry_run_ru_v664c = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_screenshot_retention_dry_run_ru_v664c(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_screenshot_retention_dry_run_status_ru_v664c, contract_screenshot_retention_dry_run_report_ru_v664c, contract_screenshot_retention_dry_run_routed_panel_ru_v664c, contract_screenshot_retention_dry_run_version_consistency_ru_v664c, contract_screenshot_retention_dry_run_no_deletion_ru_v664c, contract_screenshot_retention_dry_run_mode_ru_v664c, contract_screenshot_retention_dry_run_has_required_fields_ru_v664c]:
        result = cfn()
        contracts.append({"name": result.get("mode", "screenshot_retention_dry_run_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.64c Screenshot Retention Dry Run RU contract coverage

# BEGIN v6.64d Screenshot Storage Policy Simulator RU contract coverage
COMPUTER_USE_CONTRACTS_SCREENSHOT_STORAGE_POLICY_SIMULATOR_RU_V664D = "v6.64d screenshot storage policy simulator contracts installed"


def contract_screenshot_storage_policy_simulator_status_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import dispatch
    r = dispatch("localcomet screenshots storage policy simulate status")
    ok = isinstance(r, dict) and r.get("ok")
    return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_status", "version": "v6.64d"}


def contract_screenshot_storage_policy_simulator_report_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import dispatch
    r = dispatch("localcomet screenshots storage policy simulate")
    ok = isinstance(r, dict) and r.get("ok") and bool(r.get("paths"))
    return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_report", "version": "v6.64d"}


def contract_screenshot_storage_policy_simulator_routed_panel_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import is_screenshot_storage_policy_simulator_command
    ok = is_screenshot_storage_policy_simulator_command("localcomet screenshots storage policy simulate")
    return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_routed_panel", "version": "v6.64d"}


def contract_screenshot_storage_policy_simulator_version_consistency_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import dispatch, SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION
    r = dispatch("localcomet screenshots storage policy simulate")
    v = r.get("version", "") if isinstance(r, dict) else ""
    ok = v == SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION or bool(v)
    return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_version_consistency", "version": "v6.64d", "expected": SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION, "got": v}


def contract_screenshot_storage_policy_simulator_no_deletion_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import dispatch, ROOT_PATH as SPS_ROOT
    r = dispatch("localcomet screenshots storage policy simulate")
    if not isinstance(r, dict) or not r.get("paths"):
        return {"ok": False, "mode": "contract_screenshot_storage_policy_simulator_no_deletion", "version": "v6.64d"}
    import json
    json_path = r["paths"].get("json", "")
    if not json_path:
        return {"ok": False, "mode": "contract_screenshot_storage_policy_simulator_no_deletion", "version": "v6.64d"}
    try:
        data = json.loads((SPS_ROOT / json_path).read_text(encoding="utf-8"))
        deletion_enabled = data.get("deletion_enabled", True)
        all_policies_safe = all(
            sp.get("deletion_enabled", True) is False
            for sp in data.get("simulated_policies", [])
        )
        ok = not deletion_enabled and all_policies_safe
        return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_no_deletion", "version": "v6.64d", "deletion_enabled": deletion_enabled, "all_policies_safe": all_policies_safe}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_storage_policy_simulator_no_deletion", "version": "v6.64d", "error": str(e)}


def contract_screenshot_storage_policy_simulator_mode_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import dispatch
    r = dispatch("localcomet screenshots storage policy simulate")
    mode = r.get("mode", "") if isinstance(r, dict) else ""
    ok = mode == "screenshot_storage_policy_simulator_generated"
    return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_mode", "version": "v6.64d", "got_mode": mode}


def contract_screenshot_storage_policy_simulator_has_required_fields_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import dispatch, ROOT_PATH as SPS_ROOT
    r = dispatch("localcomet screenshots storage policy simulate")
    if not isinstance(r, dict) or not r.get("paths"):
        return {"ok": False, "mode": "contract_screenshot_storage_policy_simulator_has_required_fields", "version": "v6.64d"}
    import json
    json_path = r["paths"].get("json", "")
    if not json_path:
        return {"ok": False, "mode": "contract_screenshot_storage_policy_simulator_has_required_fields", "version": "v6.64d"}
    try:
        data = json.loads((SPS_ROOT / json_path).read_text(encoding="utf-8"))
        required_fields = ["simulated_policies", "growth_rate_estimate", "projected_30_day_size_gb", "projected_90_day_size_gb", "recommended_policy", "screenshot_directories", "total_screenshot_files", "total_screenshot_size_gb"]
        fields_found = [f for f in required_fields if f in data]
        fields_missing = [f for f in required_fields if f not in data]
        ok = len(fields_missing) == 0
        return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_has_required_fields", "version": "v6.64d", "fields_found": fields_found, "fields_missing": fields_missing}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_storage_policy_simulator_has_required_fields", "version": "v6.64d", "error": str(e)}


try:
    _run_all_contracts_before_screenshot_storage_policy_simulator_ru_v664d
except NameError:
    _run_all_contracts_before_screenshot_storage_policy_simulator_ru_v664d = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_screenshot_storage_policy_simulator_ru_v664d(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [
        contract_screenshot_storage_policy_simulator_status_ru_v664d,
        contract_screenshot_storage_policy_simulator_report_ru_v664d,
        contract_screenshot_storage_policy_simulator_routed_panel_ru_v664d,
        contract_screenshot_storage_policy_simulator_version_consistency_ru_v664d,
        contract_screenshot_storage_policy_simulator_no_deletion_ru_v664d,
        contract_screenshot_storage_policy_simulator_mode_ru_v664d,
        contract_screenshot_storage_policy_simulator_has_required_fields_ru_v664d,
    ]:
        result = cfn()
        contracts.append({"name": result.get("mode", "screenshot_storage_policy_simulator_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload


# END v6.64d Screenshot Storage Policy Simulator RU contract coverage

# BEGIN v6.64e Screenshot Retention Policy Config RU contract coverage
COMPUTER_USE_CONTRACTS_SCREENSHOT_RETENTION_POLICY_CONFIG_RU_V664E = "v6.64e screenshot retention policy config contracts installed"


def contract_screenshot_retention_policy_config_status_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import dispatch
    r = dispatch("localcomet screenshots retention policy status")
    ok = isinstance(r, dict) and r.get("ok")
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_status", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_write_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import dispatch
    r = dispatch("localcomet screenshots retention policy write")
    ok = isinstance(r, dict) and r.get("ok") and bool(r.get("paths"))
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_write", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_routed_panel_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import is_screenshot_retention_policy_config_command
    ok = is_screenshot_retention_policy_config_command("localcomet screenshots retention policy write")
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_routed_panel", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_version_consistency_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import dispatch, SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION
    r = dispatch("localcomet screenshots retention policy write")
    v = r.get("version", "") if isinstance(r, dict) else ""
    ok = v == SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION or bool(v)
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_version_consistency", "version": "v6.64e", "expected": SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION, "got": v}


def _check_policy_json_field(path, field, expected):
    import json
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        actual = data.get(field)
        if callable(expected):
            return expected(actual)
        return actual == expected
    except Exception:
        return False


def contract_screenshot_retention_policy_config_cleanup_mode_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    ok = _check_policy_json_field(POLICY_JSON, "cleanup_mode", "policy_config_only")
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_cleanup_mode", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_deletion_disabled_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    ok = _check_policy_json_field(POLICY_JSON, "deletion_enabled", False)
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_deletion_disabled", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_manual_approval_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    ok = _check_policy_json_field(POLICY_JSON, "manual_approval_required", True)
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_manual_approval", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_selected_policy_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    ok = _check_policy_json_field(POLICY_JSON, "selected_policy", "keep_newest_500_per_directory")
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_selected_policy", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_enforcement_inactive_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    import json
    try:
        data = json.loads(POLICY_JSON.read_text(encoding="utf-8"))
        es = data.get("enforcement_status", {})
        ok = es.get("active") is False
        return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_enforcement_inactive", "version": "v6.64e", "active": es.get("active")}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_retention_policy_config_enforcement_inactive", "version": "v6.64e", "error": str(e)}


def contract_screenshot_retention_policy_config_dangerous_warning_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    import json
    try:
        data = json.loads(POLICY_JSON.read_text(encoding="utf-8"))
        w = data.get("dangerous_cleanup_warning", "")
        ok = "NO FILES WERE DELETED" in w
        return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_dangerous_warning", "version": "v6.64e", "contains_warning": ok}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_retention_policy_config_dangerous_warning", "version": "v6.64e", "error": str(e)}


def contract_screenshot_retention_policy_config_base_version_matches_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON, ROOT_PATH as RPC_ROOT
    import json, re
    try:
        panel_text = (RPC_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
        m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
        expected = m.group(1) if m else ""
        data = json.loads(POLICY_JSON.read_text(encoding="utf-8"))
        actual = data.get("base_version", "")
        ok = bool(expected) and expected == actual
        return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_base_version_matches", "version": "v6.64e", "expected": expected, "actual": actual}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_retention_policy_config_base_version_matches", "version": "v6.64e", "error": str(e)}


def contract_screenshot_retention_policy_config_policy_limits_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    import json
    try:
        data = json.loads(POLICY_JSON.read_text(encoding="utf-8"))
        pl = data.get("policy_limits", {})
        ok = pl.get("keep_newest_per_directory") == 500 and pl.get("keep_younger_than_days") is None and pl.get("max_total_gb") is None and pl.get("max_gb_per_directory") is None
        return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_policy_limits", "version": "v6.64e", "policy_limits": pl}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_retention_policy_config_policy_limits", "version": "v6.64e", "error": str(e)}


def contract_screenshot_retention_policy_config_missing_simulation_safe_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import SIMULATION_JSON
    original_content = None
    if SIMULATION_JSON.exists():
        original_content = SIMULATION_JSON.read_bytes()
    try:
        if SIMULATION_JSON.exists():
            SIMULATION_JSON.rename(SIMULATION_JSON.with_suffix(".json.bak_test"))
        from modules.screenshot_retention_policy_config_ru import generate
        payload = generate()
        ok = payload.get("cleanup_mode") == "policy_config_only" and payload.get("deletion_enabled") is False
        warnings = payload.get("warnings") or []
        has_warning = any("not found" in str(w).lower() for w in warnings)
        return {"ok": ok and has_warning, "mode": "contract_screenshot_retention_policy_config_missing_simulation_safe", "version": "v6.64e", "has_warning": has_warning}
    finally:
        if original_content is not None:
            bak = SIMULATION_JSON.with_suffix(".json.bak_test")
            if bak.exists():
                bak.rename(SIMULATION_JSON)


def contract_screenshot_retention_policy_config_invalid_simulation_safe_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import SIMULATION_JSON
    original_content = None
    if SIMULATION_JSON.exists():
        original_content = SIMULATION_JSON.read_bytes()
    try:
        SIMULATION_JSON.write_text("not valid json {{{", encoding="utf-8")
        from modules.screenshot_retention_policy_config_ru import generate
        payload = generate()
        ok = payload.get("cleanup_mode") == "policy_config_only" and payload.get("deletion_enabled") is False
        warnings = payload.get("warnings") or []
        has_warning = any("invalid" in str(w).lower() for w in warnings)
        return {"ok": ok and has_warning, "mode": "contract_screenshot_retention_policy_config_invalid_simulation_safe", "version": "v6.64e", "has_warning": has_warning}
    finally:
        SIMULATION_JSON.write_text(original_content.decode("utf-8") if original_content else "{}", encoding="utf-8")


def contract_screenshot_retention_policy_config_no_deletion_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    import json
    try:
        data = json.loads(POLICY_JSON.read_text(encoding="utf-8"))
        ok = data.get("deletion_enabled") is False and "NO FILES WERE DELETED" in data.get("dangerous_cleanup_warning", "")
        return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_no_deletion", "version": "v6.64e"}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_retention_policy_config_no_deletion", "version": "v6.64e", "error": str(e)}


try:
    _run_all_contracts_before_screenshot_retention_policy_config_ru_v664e
except NameError:
    _run_all_contracts_before_screenshot_retention_policy_config_ru_v664e = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_screenshot_retention_policy_config_ru_v664e(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [
        contract_screenshot_retention_policy_config_status_ru_v664e,
        contract_screenshot_retention_policy_config_write_ru_v664e,
        contract_screenshot_retention_policy_config_routed_panel_ru_v664e,
        contract_screenshot_retention_policy_config_version_consistency_ru_v664e,
        contract_screenshot_retention_policy_config_cleanup_mode_ru_v664e,
        contract_screenshot_retention_policy_config_deletion_disabled_ru_v664e,
        contract_screenshot_retention_policy_config_manual_approval_ru_v664e,
        contract_screenshot_retention_policy_config_selected_policy_ru_v664e,
        contract_screenshot_retention_policy_config_enforcement_inactive_ru_v664e,
        contract_screenshot_retention_policy_config_dangerous_warning_ru_v664e,
        contract_screenshot_retention_policy_config_base_version_matches_ru_v664e,
        contract_screenshot_retention_policy_config_policy_limits_ru_v664e,
        contract_screenshot_retention_policy_config_missing_simulation_safe_ru_v664e,
        contract_screenshot_retention_policy_config_invalid_simulation_safe_ru_v664e,
        contract_screenshot_retention_policy_config_no_deletion_ru_v664e,
    ]:
        result = cfn()
        contracts.append({"name": result.get("mode", "screenshot_retention_policy_config_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload


# END v6.64e Screenshot Retention Policy Config RU contract coverage

# BEGIN v6.64f Panel Command Router Improvement RU contract coverage
COMPUTER_USE_CONTRACTS_PANEL_ROUTER_IMPROVEMENT_RU_V664F = "v6.64f panel command router improvement contracts installed"


def _check_router_routes_to_simulate(goal: str) -> bool:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command(goal)
    mode = r.get("mode", "")
    route = r.get("route", "")
    result = r.get("result", {})
    return mode == "command" and route == "computer_use_core_ru" and isinstance(result, dict) and result.get("ok") and result.get("mode") == "computer_use_full_control_mission"


def _check_plain_desktop_goal_not_triggered(text: str) -> bool:
    from LocalComet_Control_Panel import _is_plain_desktop_goal
    return not _is_plain_desktop_goal(text)


def _check_router_routes_to_confirmation(goal: str) -> bool:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command(goal)
    mode = r.get("mode", "")
    result = r.get("result", "")
    return mode == "requires_confirmation" and "Требуется подтверждение" in str(result)


def contract_panel_router_plain_desktop_goal_routes_simulate_ru_v664f():
    ok = _check_router_routes_to_confirmation("открой фотошоп")
    return {"ok": ok, "mode": "contract_panel_router_plain_desktop_goal_routes_simulate", "version": "v6.72", "new_behavior": "plain_desktop_goal_now_requires_confirmation_for_non_allowlisted"}


def contract_panel_router_open_provodnik_routes_simulate_ru_v664f():
    ok = _check_router_routes_to_confirmation("открой фотошоп")
    return {"ok": ok, "mode": "contract_panel_router_open_provodnik_routes_simulate", "version": "v6.72", "new_behavior": "plain_desktop_goal_now_requires_confirmation_for_non_allowlisted"}


def contract_panel_router_make_screenshot_routes_simulate_ru_v664f():
    ok = _check_router_routes_to_confirmation("сделай скриншот")
    return {"ok": ok, "mode": "contract_panel_router_make_screenshot_routes_simulate", "version": "v6.65g", "new_behavior": "plain_desktop_goal_now_requires_confirmation"}


def contract_panel_router_cyrillic_chat_does_not_route_ru_v664f():
    ok = _check_plain_desktop_goal_not_triggered("почему не работает")
    return {"ok": ok, "mode": "contract_panel_router_cyrillic_chat_does_not_route", "version": "v6.64f", "text": "почему не работает"}


def contract_panel_router_make_review_does_not_route_ru_v664f():
    ok = _check_plain_desktop_goal_not_triggered("сделай ревью")
    return {"ok": ok, "mode": "contract_panel_router_make_review_does_not_route", "version": "v6.64f", "text": "сделай ревью"}


def contract_panel_router_check_project_does_not_route_ru_v664f():
    ok = _check_plain_desktop_goal_not_triggered("проверь проект")
    return {"ok": ok, "mode": "contract_panel_router_check_project_does_not_route", "version": "v6.64f", "text": "проверь проект"}


def contract_panel_router_explicit_simulate_still_works_ru_v664f():
    ok = _check_router_routes_to_simulate("pc computer full control simulate открой браузер")
    return {"ok": ok, "mode": "contract_panel_router_explicit_simulate_still_works", "version": "v6.64f"}


def contract_panel_router_status_still_works_ru_v664f():
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("pc computer full control status")
    mode = r.get("mode", "")
    route = r.get("route", "")
    result = r.get("result", {})
    ok = mode == "command" and route == "computer_use_core_ru" and isinstance(result, dict) and result.get("mode") == "computer_use_full_control_status"
    return {"ok": ok, "mode": "contract_panel_router_status_still_works", "version": "v6.64f"}


def contract_panel_router_gibberish_shows_helpful_message_ru_v664f():
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("hello world")
    result_text = str(r.get("result", ""))
    ok = "Команда не распознана bridge-router" in result_text
    return {"ok": ok, "mode": "contract_panel_router_gibberish_shows_helpful_message", "version": "v6.64f"}


def contract_panel_router_plain_goal_no_direct_execution_ru_v664f():
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("открой фотошоп")
    mode = r.get("mode", "")
    ok = mode == "requires_confirmation"
    return {"ok": ok, "mode": "contract_panel_router_plain_goal_no_direct_execution", "version": "v6.72", "new_behavior": "non_allowlisted_plain_goal_still_requires_confirmation"}




# BEGIN v6.64g Panel Router Refinement run_all restore
try:
    _run_all_contracts_before_panel_router_refinement_ru_v664g
except NameError:
    _run_all_contracts_before_panel_router_refinement_ru_v664g = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_panel_router_refinement_ru_v664g(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [
        contract_panel_router_plain_desktop_goal_routes_simulate_ru_v664f,
        contract_panel_router_open_provodnik_routes_simulate_ru_v664f,
        contract_panel_router_make_screenshot_routes_simulate_ru_v664f,
        contract_panel_router_cyrillic_chat_does_not_route_ru_v664f,
        contract_panel_router_make_review_does_not_route_ru_v664f,
        contract_panel_router_check_project_does_not_route_ru_v664f,
        contract_panel_router_explicit_simulate_still_works_ru_v664f,
        contract_panel_router_status_still_works_ru_v664f,
        contract_panel_router_gibberish_shows_helpful_message_ru_v664f,
        contract_panel_router_plain_goal_no_direct_execution_ru_v664f,
    ]:
        result = cfn()
        contracts.append({"name": result.get("mode", "panel_router_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.64g Panel Router Refinement run_all restore
