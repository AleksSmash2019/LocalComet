"""Deterministic 1000-case Computer Use P0 campaign.

The campaign uses real validators/planners/normalizers and simulation-only action
execution. It never launches an application, sends input, or kills processes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import pc_agent_actions
from modules import tool_execution_ru as tool_execution
from modules.computer_use_real_actions_ru import build_real_action_plan, execute_real_action
from modules.tool_execution_ru import ToolExecutionError


MATRIX = [
    ("schema_normalization", 100),
    ("allowlist_safety", 150),
    ("approval_contract", 100),
    ("real_action_planner", 150),
    ("sidecar_dispatcher", 100),
    ("windows_launcher", 100),
    ("input_grounding", 100),
    ("observation_screenshots", 75),
    ("ui_result_mapping", 75),
    ("recovery_idempotency", 50),
    ("adversarial", 100),
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def normalized(raw: dict, action: str = "open_app", index: int = 0) -> dict:
    return tool_execution._normalize_computer_use_result(
        raw,
        action=action,
        request_id=f"campaign-request-{index:04d}",
        action_id=f"campaign-action-{index:04d}",
    )


def run_schema_case(index: int) -> dict:
    variants = [
        {"ok": True, "status": "executed", "verification": "pending"},
        {"ok": True, "status": "executed", "verification": "verified"},
        {"ok": False, "status": "blocked", "blocked": True},
        {"ok": False, "status": "failed", "reason": "backend"},
        {"ok": True, "status": "launch_pending", "verification": "pending"},
        {"ok": True, "status": "completed", "verification": "verified"},
        {"ok": False, "status": "cancelled"},
        {"ok": True},
        {"status": "unsupported"},
        {"ok": False, "status": "requires_confirmation"},
    ]
    result = normalized(variants[index % len(variants)], index=index)
    require(result["schema_version"] == "computer_use.result.v1", "schema version missing")
    require(isinstance(result["terminal"], bool) and isinstance(result["succeeded"], bool), "terminal flags not boolean")
    if result["status"] == "launch_pending":
        require(not result["terminal"] and not result["succeeded"], "pending result became terminal")
    if result["succeeded"]:
        require(result["terminal"] and result["status"] == "completed" and result["verification"] == "verified", "success contract incomplete")
    return {"status": result["status"], "terminal": result["terminal"], "succeeded": result["succeeded"]}


def run_allowlist_case(index: int) -> dict:
    actions = [
        {"kind": "open_app", "target": "notepad"},
        {"kind": "open_app", "target": "калькулятор"},
        {"kind": "open_folder", "target": "projects"},
        {"kind": "click_element", "target": "button"},
        {"kind": "double_click_element", "target": "button"},
        {"kind": "paste_text", "text": "Привет, LocalComet"},
        {"kind": "press_key", "key": "enter"},
        {"kind": "hotkey", "keys": ["ctrl", "a"]},
        {"kind": "scroll", "direction": "down", "clicks": 2},
        {"kind": "open_app", "target": "powershell"},
    ]
    action = actions[index % len(actions)]
    result = execute_real_action(action, simulate=True)
    require(isinstance(result, dict) and "ok" in result, "allowlist result shape missing")
    if action.get("target") == "powershell":
        require(result["ok"] is False, "blocked launcher was accepted")
    else:
        # A safe action may still fail closed when there is no grounded UI
        # candidate; allowlist safety is separate from grounding success.
        require(result["ok"] is True or result.get("reason") == "No UI candidates found.", f"safe simulated action violated contract: {result}")
    return {"ok": result["ok"], "status": result.get("status")}


def run_approval_case(index: int) -> dict:
    variants = [
        ({"ok": True, "status": "executed", "verification": "pending"}, False, False),
        ({"ok": True, "status": "executed", "verification": "verified"}, True, True),
        ({"ok": False, "status": "blocked", "blocked": True}, True, False),
        ({"ok": False, "status": "requires_confirmation"}, True, False),
    ]
    raw, terminal, success = variants[index % len(variants)]
    result = normalized(raw, action="click", index=index)
    require(result["terminal"] is terminal, f"approval terminal mismatch: {result}")
    require(result["succeeded"] is success, f"approval success mismatch: {result}")
    require(result["request_id"].startswith("campaign-request-"), "request correlation missing")
    return {"status": result["status"], "terminal": result["terminal"], "succeeded": result["succeeded"]}


def run_planner_case(index: int) -> dict:
    goals = [
        "открой блокнот и напиши Привет",
        "найди погоду в екатеринбурге",
        "найди в интернете новости спорта",
        "найди мой пароль",
        "открой powershell",
    ]
    goal = goals[index % len(goals)]
    plan = build_real_action_plan(goal, max_steps=8)
    if "пароль" in goal or "powershell" in goal:
        require(plan.get("blocked") is True and plan.get("actions") == [], f"adversarial planner goal was not blocked: {plan}")
    else:
        require(plan.get("ok") is True and plan.get("blocked") is not True and plan.get("actions"), f"safe planner goal has no executable actions: {plan}")
    return {"blocked": plan.get("blocked"), "actions": [item.get("kind") for item in plan.get("actions", [])]}


def run_dispatcher_case(index: int) -> dict:
    # These cases deliberately fail before OS execution, exercising the sidecar
    # dispatcher type/allowlist boundary with no real action.
    variants = [
        {"action": ""},
        {"action": "unsupported"},
        {"action": "click", "target": 1},
        {"action": "type", "text": 1},
        {"action": "drag", "coordinate": "bad"},
        {"action": "type", "text": "a\x00b"},
        {"action": "open_app", "target": 42},
        {"action": "screenshot", "target": 1},
        {"action": "hotkey", "text": []},
        {"action": "wait", "text": 1},
    ]
    payload = {
        "tool": "computer_use",
        "workspace": str(ROOT),
        "workspace_digest": "a" * 64,
        "session": "campaign-session",
        "input": variants[index % len(variants)],
    }
    try:
        tool_execution.execute_tool_call(payload)
    except ToolExecutionError as exc:
        require(exc.code in {"invalid_payload", "unsupported_method", "policy_blocked"}, f"unexpected dispatcher code: {exc.code}")
        return {"error_code": exc.code}
    raise AssertionError("malformed dispatcher input reached action execution")


def run_launcher_case(index: int) -> dict:
    ready = index % 2 == 1
    with patch.object(pc_agent_actions.os, "name", "nt"), \
         patch.object(pc_agent_actions, "_shell_execute_open_bounded", return_value=True), \
         patch.object(pc_agent_actions, "_wait_for_app_readiness", return_value=ready):
        result = pc_agent_actions.open_app("notepad", dry_run=False)
    require(result["ok"] is ready, f"launcher ok mismatch: {result}")
    require(result["status"] == ("completed" if ready else "launch_pending"), f"launcher status mismatch: {result}")
    require(result["verification"] == ("verified" if ready else "pending"), f"launcher verification mismatch: {result}")
    return {"ok": result["ok"], "status": result["status"], "verification": result["verification"]}


def run_input_case(index: int) -> dict:
    cases = [
        ({"kind": "click_element", "target": "button"}, False),
        ({"kind": "click_element", "target": ""}, False),
        ({"kind": "paste_text", "text": "Русский текст"}, True),
        ({"kind": "paste_text", "text": "a\x00b"}, True),
        ({"kind": "drag", "coordinate": [100, 100, 800, 800]}, True),
        ({"kind": "drag", "coordinate": [100, 100]}, False),
        ({"kind": "scroll", "direction": "up", "clicks": 2}, True),
        ({"kind": "press_key", "key": "unsupported"}, True),
        ({"kind": "hotkey", "keys": ["ctrl", "a"]}, True),
        ({"kind": "paste_text", "text": "x" * 20_000}, True),
    ]
    action, expected_ok = cases[index % len(cases)]
    result = execute_real_action(action, simulate=True)
    require(result.get("ok") is expected_ok, f"input grounding mismatch: {result}")
    return {"ok": result.get("ok"), "status": result.get("status")}


def run_observation_case(index: int) -> dict:
    result = execute_real_action({"kind": "screenshot"}, simulate=True)
    require(result.get("ok") is True, f"simulated observation failed: {result}")
    require(result.get("status") == "simulated", f"unexpected observation status: {result}")
    return {"ok": result["ok"], "status": result["status"]}


def run_ui_mapping_case(index: int) -> dict:
    variants = [
        {"ok": True, "status": "executed", "verification": "pending"},
        {"ok": True, "status": "executed", "verification": "verified"},
        {"ok": False, "status": "blocked", "blocked": True},
        {"ok": False, "status": "failed"},
        {"ok": True, "status": "awaiting_observation", "verification": "pending"},
    ]
    result = normalized(variants[index % len(variants)], action="screenshot", index=index)
    expected_ui = "WAITING" if not result["terminal"] else "PASS" if result["succeeded"] else "FAIL"
    require(expected_ui != "PASS" or (result["status"] == "completed" and result["verification"] == "verified"), "UI mapping permits false PASS")
    return {"ui_state": expected_ui, "backend_status": result["status"]}


def run_recovery_case(index: int) -> dict:
    raw = {"ok": True, "status": "executed", "verification": "verified", "attempt": index % 3}
    first = normalized(raw, action="wait", index=index)
    second = normalized(raw, action="wait", index=index)
    require(first == second, "normalization is not deterministic/idempotent")
    require(first["terminal"] and first["succeeded"], "verified recovery result is not terminal success")
    return {"status": first["status"], "idempotent": True}


def run_adversarial_case(index: int) -> dict:
    cases = [
        {"kind": "open_app", "target": "cmd"},
        {"kind": "open_app", "target": "powershell"},
        {"kind": "open_app", "target": "regedit"},
        {"kind": "open_folder", "target": "../escape"},
        {"kind": "open_folder", "target": "C:/outside"},
        {"kind": "paste_text", "text": "password token secret"},
        {"kind": "paste_text", "text": "\ud800"},
        {"kind": "drag", "coordinate": [1, 2]},
        {"kind": "click_element", "target": 42},
        {"kind": "unknown", "target": "x"},
    ]
    result = execute_real_action(cases[index % len(cases)], simulate=True)
    require(
        isinstance(result, dict) and (result.get("ok") is False or result.get("status") == "simulated"),
        f"adversarial input violated fail-closed/simulation contract: {result}",
    )
    return {"ok": result.get("ok"), "status": result.get("status"), "reason": result.get("reason")}


RUNNERS = {
    "schema_normalization": run_schema_case,
    "allowlist_safety": run_allowlist_case,
    "approval_contract": run_approval_case,
    "real_action_planner": run_planner_case,
    "sidecar_dispatcher": run_dispatcher_case,
    "windows_launcher": run_launcher_case,
    "input_grounding": run_input_case,
    "observation_screenshots": run_observation_case,
    "ui_result_mapping": run_ui_mapping_case,
    "recovery_idempotency": run_recovery_case,
    "adversarial": run_adversarial_case,
}


def main() -> int:
    results: list[dict] = []
    case_number = 1
    for family, count in MATRIX:
        runner = RUNNERS[family]
        for index in range(count):
            row = {"id": f"CU{case_number:04d}", "family": family, "index": index}
            try:
                row.update({"status": "PASS", "details": runner(index)})
            except Exception as exc:
                row.update({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
            results.append(row)
            case_number += 1
    output = {
        "campaign": "computer_use_p0_1000",
        "matrix": [{"family": family, "count": count} for family, count in MATRIX],
        "scenario_count": len(results),
        "passed": sum(row["status"] == "PASS" for row in results),
        "failed": sum(row["status"] == "FAIL" for row in results),
        "results": results,
    }
    report = ROOT / "Projects" / "Reports" / "computer_use_real_actions" / "campaign_1000_p0.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: output[key] for key in ("campaign", "scenario_count", "passed", "failed")}, ensure_ascii=False))
    for row in results:
        if row["status"] == "FAIL":
            print(json.dumps(row, ensure_ascii=False))
    return 0 if output["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

