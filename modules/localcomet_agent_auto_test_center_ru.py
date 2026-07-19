from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple


AGENT_AUTO_TEST_VERSION = "v6.55b"
AGENT_AUTO_TEST_NAME = "Agent Automation Functional Test Center RU"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _root() -> Path:
    try:
        from modules.project_paths import get_project_root

        return get_project_root()
    except Exception:
        return Path(__file__).resolve().parents[1]


def _reports_dir() -> Path:
    try:
        from modules.project_paths import reports_dir

        return reports_dir(_root()) / "localcomet_agent_auto_tests"
    except Exception:
        return _root() / "Projects" / "Reports" / "localcomet_agent_auto_tests"


def _compact(value: Any, limit: int = 1800) -> Any:
    try:
        if isinstance(value, (dict, list, tuple, int, float, bool)) or value is None:
            text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        else:
            text = str(value)
    except Exception:
        text = str(value)
    if len(text) <= limit:
        return value
    return text[:limit] + "\n[trimmed]"


def _write_reports(payload: Dict[str, Any]) -> Dict[str, str]:
    report_dir = _reports_dir()
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    json_path = report_dir / f"agent_auto_test_{stamp}.json"
    md_path = report_dir / f"agent_auto_test_{stamp}.md"
    latest_json = report_dir / "latest_agent_auto_test.json"
    latest_md = report_dir / "latest_agent_auto_test.md"

    json_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json_path.write_text(json_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")

    summary = payload.get("summary", {})
    lines = [
        "# LocalComet Agent Automation Functional Test Center",
        "",
        f"- version: {payload.get('version')}",
        f"- ok: {payload.get('ok')}",
        f"- suite: {payload.get('suite')}",
        f"- started_at: {payload.get('started_at')}",
        f"- finished_at: {payload.get('finished_at')}",
        f"- passed: {summary.get('passed')}",
        f"- total: {summary.get('total')}",
        f"- failed: {summary.get('failed')}",
        "",
        "## Checks",
        "",
    ]
    for item in payload.get("checks", []):
        marker = "PASS" if item.get("ok") else "FAIL"
        lines.append(f"### {marker} {item.get('id')}")
        lines.append("")
        lines.append(f"- name: {item.get('name')}")
        lines.append(f"- category: {item.get('category')}")
        lines.append(f"- severity: {item.get('severity')}")
        if item.get("error"):
            lines.append(f"- error: `{item.get('error')}`")
        details = item.get("details")
        if details not in (None, "", {}, []):
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(details, ensure_ascii=False, indent=2, sort_keys=True)[:3500])
            lines.append("```")
        lines.append("")
    md_text = "\n".join(lines)
    md_path.write_text(md_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    return {
        "json": str(json_path),
        "md": str(md_path),
        "latest_json": str(latest_json),
        "latest_md": str(latest_md),
    }


def _item(test_id: str, name: str, category: str, severity: str, fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    started = datetime.now()
    payload: Dict[str, Any] = {
        "id": test_id,
        "name": name,
        "category": category,
        "severity": severity,
        "ok": False,
        "details": {},
        "error": "",
        "duration_ms": 0,
    }
    try:
        result = fn()
        payload["ok"] = bool(result.get("ok"))
        payload["details"] = _compact(result)
        if not payload["ok"] and result.get("error"):
            payload["error"] = str(result.get("error"))
    except Exception as exc:
        payload["ok"] = False
        payload["error"] = str(exc)
        payload["details"] = {"traceback": traceback.format_exc()}
    elapsed = datetime.now() - started
    payload["duration_ms"] = int(elapsed.total_seconds() * 1000)
    return payload


def _auto_action_click() -> Dict[str, Any]:
    from modules.computer_use_auto_action_ru import auto_policy_for_action, execute_gui_action

    action = {
        "kind": "click",
        "target": {"x": 12, "y": 12, "element_description": "synthetic button"},
        "grounded": True,
        "gui_only": True,
        "modifies_files": False,
        "ui_intent": "gui_navigation_or_button_click",
        "reason": "agent automation functional test synthetic click",
    }
    policy = auto_policy_for_action(action)
    result = execute_gui_action(action, simulate=True)
    return {
        "ok": bool(policy.get("ok")) and bool(policy.get("allowed_to_execute")) and bool(result.get("ok")) and bool(result.get("simulated")),
        "policy": {
            "allowed_to_execute": policy.get("allowed_to_execute"),
            "requires_confirmation": policy.get("requires_confirmation"),
            "blocked": policy.get("blocked"),
            "risk": policy.get("risk"),
        },
        "execution": {
            "ok": result.get("ok"),
            "simulated": result.get("simulated"),
            "primitive": result.get("primitive"),
            "mode": result.get("mode"),
        },
    }


def _auto_action_type() -> Dict[str, Any]:
    from modules.computer_use_auto_action_ru import auto_policy_for_action, execute_gui_action

    action = {
        "kind": "type",
        "text": "hello",
        "focused_target": True,
        "grounded": True,
        "gui_only": True,
        "modifies_files": False,
        "ui_intent": "verified_input_type",
        "reason": "agent automation functional test synthetic type",
    }
    policy = auto_policy_for_action(action)
    result = execute_gui_action(action, simulate=True)
    return {
        "ok": bool(policy.get("ok")) and bool(policy.get("allowed_to_execute")) and bool(result.get("ok")) and bool(result.get("simulated")),
        "policy": {
            "allowed_to_execute": policy.get("allowed_to_execute"),
            "requires_confirmation": policy.get("requires_confirmation"),
            "blocked": policy.get("blocked"),
            "risk": policy.get("risk"),
        },
        "execution": {
            "ok": result.get("ok"),
            "simulated": result.get("simulated"),
            "primitive": result.get("primitive"),
            "mode": result.get("mode"),
        },
    }


def _auto_action_hotkey() -> Dict[str, Any]:
    from modules.computer_use_auto_action_ru import auto_policy_for_action, execute_gui_action

    action = {
        "kind": "hotkey",
        "text": "ctrl+a",
        "grounded": True,
        "gui_only": True,
        "modifies_files": False,
        "reason": "agent automation functional test synthetic hotkey history repair regression",
    }
    policy = auto_policy_for_action(action)
    result = execute_gui_action(action, simulate=True)
    artifact = str(result.get("artifact") or "")
    return {
        "ok": bool(policy.get("ok")) and bool(policy.get("allowed_to_execute")) and bool(result.get("ok")) and bool(result.get("simulated")) and bool(artifact),
        "policy": {
            "allowed_to_execute": policy.get("allowed_to_execute"),
            "requires_confirmation": policy.get("requires_confirmation"),
            "blocked": policy.get("blocked"),
            "risk": policy.get("risk"),
        },
        "execution": {
            "ok": result.get("ok"),
            "simulated": result.get("simulated"),
            "primitive": result.get("primitive"),
            "mode": result.get("mode"),
            "artifact": artifact,
            "history_write_recovered": result.get("history_write_recovered", False),
        },
    }


def _auto_action_scroll() -> Dict[str, Any]:
    from modules.computer_use_auto_action_ru import auto_policy_for_action, execute_gui_action

    action = {
        "kind": "scroll",
        "amount": -3,
        "grounded": True,
        "gui_only": True,
        "modifies_files": False,
        "reason": "agent automation functional test synthetic scroll",
    }
    policy = auto_policy_for_action(action)
    result = execute_gui_action(action, simulate=True)
    return {
        "ok": bool(policy.get("ok")) and bool(policy.get("allowed_to_execute")) and bool(result.get("ok")) and bool(result.get("simulated")),
        "policy": {
            "allowed_to_execute": policy.get("allowed_to_execute"),
            "requires_confirmation": policy.get("requires_confirmation"),
            "blocked": policy.get("blocked"),
            "risk": policy.get("risk"),
        },
        "execution": {
            "ok": result.get("ok"),
            "simulated": result.get("simulated"),
            "primitive": result.get("primitive"),
            "mode": result.get("mode"),
        },
    }


def _policy_status() -> Dict[str, Any]:
    from modules.computer_use_auto_action_ru import status

    result = status()
    policy = result.get("policy", {})
    return {
        "ok": bool(result.get("ok")) and "auto_gui_enabled" in policy and "blocked" in policy,
        "version": result.get("version"),
        "policy": {
            "auto_gui_enabled": policy.get("auto_gui_enabled"),
            "confirmation_policy": policy.get("confirmation_policy"),
            "blocked": policy.get("blocked"),
        },
        "history_count": result.get("history_count"),
    }


def _dangerous_goal_blocked() -> Dict[str, Any]:
    from modules.computer_use_auto_action_ru import auto_policy_for_action

    action = {
        "kind": "click",
        "goal": "удали все файлы через powershell",
        "target": {"x": 20, "y": 20},
        "grounded": True,
        "modifies_files": False,
        "reason": "agent automation safety regression",
    }
    policy = auto_policy_for_action(action)
    return {
        "ok": bool(policy.get("blocked")) and not bool(policy.get("allowed_to_execute")) and str(policy.get("risk")) == "blocked",
        "policy": {
            "blocked": policy.get("blocked"),
            "allowed_to_execute": policy.get("allowed_to_execute"),
            "requires_confirmation": policy.get("requires_confirmation"),
            "risk": policy.get("risk"),
            "reason": policy.get("reason"),
        },
    }


def _file_change_requires_confirmation() -> Dict[str, Any]:
    from modules.computer_use_auto_action_ru import auto_policy_for_action

    action = {
        "kind": "type",
        "text": "write changes to file response.json",
        "focused_target": True,
        "grounded": True,
        "reason": "agent automation safety regression",
    }
    policy = auto_policy_for_action(action)
    return {
        "ok": bool(policy.get("requires_confirmation")) and not bool(policy.get("allowed_to_execute")) and not bool(policy.get("blocked")),
        "policy": {
            "blocked": policy.get("blocked"),
            "allowed_to_execute": policy.get("allowed_to_execute"),
            "requires_confirmation": policy.get("requires_confirmation"),
            "risk": policy.get("risk"),
            "reason": policy.get("reason"),
        },
    }


def _long_type_requires_confirmation() -> Dict[str, Any]:
    from modules.computer_use_auto_action_ru import auto_policy_for_action

    action = {
        "kind": "type",
        "text": "a" * 650,
        "focused_target": True,
        "grounded": True,
        "gui_only": True,
        "modifies_files": False,
        "ui_intent": "verified_input_type",
        "reason": "agent automation long typing safety regression",
    }
    policy = auto_policy_for_action(action)
    return {
        "ok": bool(policy.get("requires_confirmation")) and not bool(policy.get("allowed_to_execute")) and not bool(policy.get("blocked")),
        "policy": {
            "blocked": policy.get("blocked"),
            "allowed_to_execute": policy.get("allowed_to_execute"),
            "requires_confirmation": policy.get("requires_confirmation"),
            "risk": policy.get("risk"),
            "reason": policy.get("reason"),
        },
    }


def _unsupported_kind_blocked() -> Dict[str, Any]:
    from modules.computer_use_auto_action_ru import auto_policy_for_action

    action = {
        "kind": "drag",
        "target": {"x": 1, "y": 1},
        "grounded": True,
        "gui_only": True,
        "modifies_files": False,
        "reason": "agent automation unsupported primitive regression",
    }
    policy = auto_policy_for_action(action)
    return {
        "ok": bool(policy.get("blocked")) and not bool(policy.get("allowed_to_execute")),
        "policy": {
            "blocked": policy.get("blocked"),
            "allowed_to_execute": policy.get("allowed_to_execute"),
            "requires_confirmation": policy.get("requires_confirmation"),
            "risk": policy.get("risk"),
            "reason": policy.get("reason"),
        },
    }


def _observe_vision_self_check() -> Dict[str, Any]:
    from modules.computer_use_observe_vision_ru import run_self_check

    result = run_self_check(write_report=True)
    summary = result.get("summary", {})
    return {
        "ok": bool(result.get("ok")) and int(summary.get("failed", 1)) == 0,
        "summary": summary,
        "report": result.get("report"),
        "version": result.get("version"),
    }


def _real_actions_self_check() -> Dict[str, Any]:
    from modules.computer_use_real_actions_ru import run_self_check

    result = run_self_check(write_report=True)
    summary = result.get("summary", {})
    return {
        "ok": bool(result.get("ok")) and int(summary.get("failed", 1)) == 0,
        "summary": summary,
        "report": result.get("report"),
        "version": result.get("version"),
    }


def _full_control_simulate_route() -> Dict[str, Any]:
    from modules.computer_use_full_control_mission_ru import handle_dispatch_command

    result = handle_dispatch_command("pc computer full control simulate открой блокнот и напиши hello")
    return {
        "ok": bool(result.get("handled")) and result.get("outcome") == "done",
        "outcome": result.get("outcome"),
        "steps": len(result.get("steps", [])),
        "report": result.get("report"),
    }


def _core_dispatch_status_route() -> Dict[str, Any]:
    from modules.computer_use_core_ru import dispatch

    result = dispatch("pc computer agent auto test status")
    return {
        "ok": isinstance(result, dict) and bool(result.get("handled")) and bool(result.get("ok")) and result.get("version") == AGENT_AUTO_TEST_VERSION,
        "mode": result.get("mode") if isinstance(result, dict) else type(result).__name__,
        "version": result.get("version") if isinstance(result, dict) else "",
    }


def planned_checks(include_full: bool = True) -> List[Tuple[str, str, str, str, Callable[[], Dict[str, Any]]]]:
    checks: List[Tuple[str, str, str, str, Callable[[], Dict[str, Any]]]] = [
        ("auto.policy_status", "Auto action policy status is readable", "auto_action", "critical", _policy_status),
        ("auto.simulated_click", "Grounded GUI click is allowed and simulated", "auto_action", "critical", _auto_action_click),
        ("auto.simulated_type", "Grounded focused type is allowed and simulated", "auto_action", "critical", _auto_action_type),
        ("auto.simulated_hotkey", "Allowlisted hotkey is allowed and simulated", "auto_action", "critical", _auto_action_hotkey),
        ("auto.simulated_scroll", "Grounded scroll is allowed and simulated", "auto_action", "critical", _auto_action_scroll),
        ("safety.dangerous_goal_blocked", "Dangerous shell or delete goal is blocked", "safety", "critical", _dangerous_goal_blocked),
        ("safety.file_change_confirmation", "File-changing typed payload requires confirmation", "safety", "critical", _file_change_requires_confirmation),
        ("safety.long_type_confirmation", "Long typing payload requires confirmation", "safety", "critical", _long_type_requires_confirmation),
        ("safety.unsupported_kind_blocked", "Unsupported primitive is blocked", "safety", "critical", _unsupported_kind_blocked),
        ("core.dispatch_status", "Core dispatch exposes agent automation status route", "routing", "critical", _core_dispatch_status_route),
    ]
    if include_full:
        checks.extend([
            ("observe.self_check", "Observe and vision self-check passes", "observe_vision", "critical", _observe_vision_self_check),
            ("real_actions.self_check", "Real actions self-check passes in safe simulation", "real_actions", "critical", _real_actions_self_check),
            ("full_control.simulate", "Full-control simulate route completes", "full_control", "critical", _full_control_simulate_route),
            ("reports.write_latest", "Agent automation report artifacts can be written", "reports", "critical", _report_write_probe),
        ])
    return checks


def _report_write_probe() -> Dict[str, Any]:
    report_dir = _reports_dir()
    report_dir.mkdir(parents=True, exist_ok=True)
    probe = report_dir / f"write_probe_{_stamp()}.json"
    payload = {"ok": True, "version": AGENT_AUTO_TEST_VERSION, "created_at": _now()}
    probe.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    read_back = json.loads(probe.read_text(encoding="utf-8"))
    return {"ok": bool(read_back.get("ok")), "probe": str(probe)}


def run_suite(suite: str = "full", write_report: bool = True) -> Dict[str, Any]:
    normalized = str(suite or "full").strip().lower()
    include_full = normalized in {"full", "all", "complete", "полный"}
    started = _now()
    checks = [_item(test_id, name, category, severity, fn) for test_id, name, category, severity, fn in planned_checks(include_full=include_full)]
    failed = len([item for item in checks if not item.get("ok")])
    payload: Dict[str, Any] = {
        "ok": failed == 0,
        "handled": True,
        "mode": "localcomet_agent_auto_functional_test_center",
        "name": AGENT_AUTO_TEST_NAME,
        "version": AGENT_AUTO_TEST_VERSION,
        "suite": "full" if include_full else "smoke",
        "started_at": started,
        "finished_at": _now(),
        "summary": {
            "passed": len(checks) - failed,
            "total": len(checks),
            "failed": failed,
        },
        "checks": checks,
        "report": "",
        "json": "",
    }
    if write_report:
        paths = _write_reports(payload)
        payload["report"] = paths["md"]
        payload["json"] = paths["json"]
        payload["latest_report"] = paths["latest_md"]
        payload["latest_json"] = paths["latest_json"]
        payload["latest_artifacts_exist"] = Path(paths["latest_json"]).exists() and Path(paths["latest_md"]).exists()
    return payload


def run_smoke_suite(write_report: bool = True) -> Dict[str, Any]:
    return run_suite("smoke", write_report=write_report)


def run_full_suite(write_report: bool = True) -> Dict[str, Any]:
    return run_suite("full", write_report=write_report)


def run_contract_suite(write_report: bool = True) -> Dict[str, Any]:
    result = run_full_suite(write_report=write_report)
    return {
        "ok": bool(result.get("ok")),
        "mode": "localcomet_agent_auto_contracts",
        "version": AGENT_AUTO_TEST_VERSION,
        "summary": result.get("summary", {}),
        "checks": result.get("checks", []),
        "report": result.get("report"),
        "json": result.get("json"),
    }


def status() -> Dict[str, Any]:
    latest_json = _reports_dir() / "latest_agent_auto_test.json"
    return {
        "ok": True,
        "handled": True,
        "mode": "localcomet_agent_auto_test_status",
        "version": AGENT_AUTO_TEST_VERSION,
        "name": AGENT_AUTO_TEST_NAME,
        "latest_exists": latest_json.exists(),
        "reports_dir": str(_reports_dir()),
        "commands": [
            "pc computer agent auto test",
            "pc computer agent auto test full",
            "pc computer agent auto test status",
            "тест агента",
            "тест автоматических функций агента",
        ],
    }


def latest_report() -> Dict[str, Any]:
    latest_json = _reports_dir() / "latest_agent_auto_test.json"
    latest_md = _reports_dir() / "latest_agent_auto_test.md"
    if not latest_json.exists():
        return {
            "ok": True,
            "handled": True,
            "mode": "localcomet_agent_auto_test_latest",
            "version": AGENT_AUTO_TEST_VERSION,
            "exists": False,
            "report": str(latest_md),
            "json": str(latest_json),
        }
    payload = json.loads(latest_json.read_text(encoding="utf-8", errors="replace"))
    payload["handled"] = True
    payload["exists"] = True
    payload["report"] = str(latest_md)
    payload["json"] = str(latest_json)
    return payload


def is_agent_auto_test_command(command: str) -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {
        "pc computer agent auto test",
        "pc computer agent auto test full",
        "pc computer agent auto test smoke",
        "pc computer agent auto test status",
        "pc computer agent auto test latest",
        "pc computer agent automation test",
        "тест агента",
        "тест автоматических функций агента",
        "проверка автоматических функций агента",
    }:
        return True
    return lower.startswith("pc computer agent auto test ")


def handle_dispatch_command(command: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")
    if not is_agent_auto_test_command(text):
        return {"handled": False}
    if lower in {"pc computer agent auto test status"}:
        return status()
    if lower in {"pc computer agent auto test latest"}:
        return latest_report()
    if lower in {"pc computer agent auto test smoke"}:
        return run_smoke_suite(write_report=True)
    return run_full_suite(write_report=True)


if __name__ == "__main__":
    result = run_full_suite(write_report=True)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result.get("ok") else 1)
