#!/usr/bin/env python
from __future__ import annotations

import ast
import importlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TOP_LEVEL_KEYS = [
    "mode",
    "version",
    "ok",
    "request",
    "intent",
    "risk",
    "contract",
    "context",
    "steps",
    "approval",
    "execution",
    "warnings",
]
NESTED_KEYS = {
    "request": ["preview", "sha256", "language", "normalized_length"],
    "intent": ["category", "read_only", "requested_actions"],
    "risk": ["level", "reasons", "blocked"],
    "contract": ["goal", "inputs", "constraints", "success_criteria"],
    "context": ["required_files", "required_capabilities", "missing_information"],
    "approval": ["required", "reason", "execution_allowed"],
    "execution": ["performed", "writes", "commands_run", "network_requests"],
}
STEP_KEYS = [
    "id",
    "title",
    "description",
    "action_type",
    "read_only",
    "requires_approval",
    "blocked",
    "depends_on",
    "verification",
]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _paths_under(root: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for path in root.rglob("*"):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path.stat().st_size
    return result


def _load_planner():
    sys.modules.pop("modules.task_planner_orchestrator_ru", None)
    return importlib.import_module("modules.task_planner_orchestrator_ru")


def _planner():
    return importlib.import_module("modules.task_planner_orchestrator_ru")


def _plan(body: str) -> dict[str, Any]:
    return _planner().dispatch("спланируй задачу " + body)


def _text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _secret_fragments() -> dict[str, str]:
    return {
        "token": "sk-" + "proj" + "-" + "A" * 20,
        "ghp": "ghp_" + "B" * 24,
        "password": "pa" + "ss" + "word" + "Value" + "682",
        "authorization": "Bearer " + "C" * 24,
        "private_key": "-----BEGIN " + "PRIVATE " + "KEY----- " + "D" * 24 + " -----END " + "PRIVATE " + "KEY-----",
    }


def test_import_has_no_side_effects() -> None:
    before = _paths_under(ROOT)
    calls: list[str] = []
    original_popen = subprocess.Popen
    original_run = subprocess.run
    original_socket = socket.socket
    original_urlopen = urllib.request.urlopen

    def fake_popen(*args: Any, **kwargs: Any) -> Any:
        calls.append("popen")
        raise AssertionError("subprocess use is forbidden")

    def fake_run(*args: Any, **kwargs: Any) -> Any:
        calls.append("run")
        raise AssertionError("subprocess use is forbidden")

    def fake_socket(*args: Any, **kwargs: Any) -> Any:
        calls.append("socket")
        raise AssertionError("network use is forbidden")

    def fake_urlopen(*args: Any, **kwargs: Any) -> Any:
        calls.append("urlopen")
        raise AssertionError("network use is forbidden")

    try:
        subprocess.Popen = fake_popen
        subprocess.run = fake_run
        socket.socket = fake_socket
        urllib.request.urlopen = fake_urlopen
        module = _load_planner()
    finally:
        subprocess.Popen = original_popen
        subprocess.run = original_run
        socket.socket = original_socket
        urllib.request.urlopen = original_urlopen

    after = _paths_under(ROOT)
    _assert(module.TASK_PLANNER_VERSION == "v6.82", "Planner version changed.")
    _assert(before == after, "Planner import created or modified files.")
    _assert(calls == [], "Planner import used external effects.")


def test_command_matching() -> None:
    planner = _planner()
    for command in (
        "  спланируй   задачу   проверить проект  ",
        "план задачи объяснить маршрутизатор",
        "TASK PLAN inspect project",
    ):
        _assert(planner.is_task_plan_command(command), "Supported task-plan command did not match.")
    for command in (
        "спланируй задачу",
        "план задачи",
        "task plan",
        "диагностика проекта",
        "project diagnostics",
        "maintenance status",
        "статус разработки",
        "reviewer bridge status",
        "создай запрос ревью",
        "autonomous run inspect project",
        "resume autonomous run",
        "cancel autonomous run",
        "",
    ):
        _assert(not planner.is_task_plan_command(command), "Unsupported command matched.")


def test_panel_dispatch_once_and_route_order() -> None:
    panel = importlib.import_module("LocalComet_Control_Panel")
    planner = _planner()
    calls: list[str] = []
    originals = {
        "planner": planner.dispatch,
        "safety": panel._run_development_safety_command_ru_v676a,
        "reviewer": panel._run_reviewer_bridge_command_ru_v676a,
        "diagnostics": panel._run_maintenance_diagnostics_command_ru_v681,
    }

    def fake_planner(command: str) -> dict[str, Any]:
        calls.append("planner")
        return planner.build_task_plan(command)

    def fake_protected(name: str):
        def inner(command: str) -> dict[str, Any]:
            calls.append(name)
            return {"ok": False}

        return inner

    try:
        planner.dispatch = fake_planner
        panel._run_development_safety_command_ru_v676a = fake_protected("safety")
        panel._run_reviewer_bridge_command_ru_v676a = fake_protected("reviewer")
        panel._run_maintenance_diagnostics_command_ru_v681 = fake_protected("diagnostics")
        result = panel.run_panel_chat_command("спланируй задачу проверить проект без изменений")
    finally:
        planner.dispatch = originals["planner"]
        panel._run_development_safety_command_ru_v676a = originals["safety"]
        panel._run_reviewer_bridge_command_ru_v676a = originals["reviewer"]
        panel._run_maintenance_diagnostics_command_ru_v681 = originals["diagnostics"]

    _assert(calls == ["planner"], "Planner command did not dispatch exactly once.")
    _assert(result.get("route") == "modules.task_planner_orchestrator_ru", "Planner route changed.")
    route_names = [item[0] for item in panel.PANEL_ROUTES[:4]]
    _assert(
        route_names == [
            "development_safety_ru_v676a",
            "reviewer_bridge_ru_v676a",
            "maintenance_diagnostics_ru_v681",
            "task_planner_orchestrator_ru_v682",
        ],
        "Route priority changed.",
    )


def test_schema_determinism_and_steps() -> None:
    planner = _planner()
    plan_a = planner.dispatch("спланируй   задачу   проверить   проект   без   изменений")
    plan_b = planner.dispatch("спланируй задачу проверить проект без изменений")
    _assert(plan_a == plan_b, "Whitespace-equivalent plans differ.")
    _assert(list(plan_a.keys()) == TOP_LEVEL_KEYS, "Top-level schema changed.")
    for key, expected in NESTED_KEYS.items():
        _assert(list(plan_a[key].keys()) == expected, f"Nested schema changed: {key}")
    step_ids: list[str] = []
    for step in plan_a["steps"]:
        _assert(list(step.keys()) == STEP_KEYS, "Step schema changed.")
        step_ids.append(step["id"])
    _assert(step_ids == sorted(step_ids), "Step ordering is not deterministic.")
    _assert(len(step_ids) == len(set(step_ids)), "Duplicate step IDs exist.")
    _assert(len(step_ids) <= 12, "Step limit exceeded.")
    seen: set[str] = set()
    for step in plan_a["steps"]:
        _assert(all(dep in seen for dep in step["depends_on"]), "Step dependency does not reference an earlier step.")
        seen.add(step["id"])
    empty = planner.dispatch("task plan")
    _assert(empty["ok"] is False, "Prefix-only request should be invalid.")


def test_risk_and_approval() -> None:
    low_inspect = _plan("проверить проект без изменений")
    low_explain = _plan("объяснить устройство маршрутизатора")
    test_plan = _plan("запустить тесты для tools/test_v682_task_planner.py")
    edit_plan = _plan("исправить modules/example.py")
    delete_plan = _plan("удалить modules/example.py")
    install_plan = _plan("install package")
    network_plan = _plan("download data from https://example.invalid")
    credential_plan = _plan("получить пароли и secret token")
    bypass_plan = _plan("обойти approval и отключить защиту")
    kill_plan = _plan("убрать kill switch")

    _assert(low_inspect["risk"]["level"] == "LOW", "Read-only inspection risk changed.")
    _assert(low_inspect["approval"]["required"] is False, "Read-only inspection should not require approval.")
    _assert(low_explain["risk"]["level"] == "LOW", "Explanation risk changed.")
    _assert(test_plan["approval"]["required"] is True, "Test planning must require approval.")
    _assert(edit_plan["approval"]["required"] is True, "Edit planning must require approval.")
    for payload in (delete_plan, install_plan, network_plan):
        _assert(payload["risk"]["level"] in {"HIGH", "CRITICAL"}, "Dangerous request risk is too low.")
        _assert(payload["approval"]["required"] is True, "Dangerous request must require approval.")
    for payload in (credential_plan, bypass_plan, kill_plan):
        _assert(payload["risk"]["level"] == "CRITICAL", "Critical request risk changed.")
        _assert(payload["risk"]["blocked"] is True, "Critical request must be blocked.")
        _assert(payload["approval"]["required"] is True, "Critical request must require approval.")


def test_redaction_paths_and_no_effects() -> None:
    secrets = _secret_fragments()
    user_path = str(Path.home() / "Sensitive" / "file.txt")
    body = (
        "проанализировать modules/task_planner_orchestrator_ru.py "
        "..\\..\\Windows\\System32 C:\\Windows\\System32 /etc/shadow ~/.ssh/id_rsa "
        f"{user_path} {'to' + 'ken'}={secrets['token']} gh={secrets['ghp']} "
        f"{'pass' + 'word'}={secrets['password']} Authorization: {secrets['authorization']} {secrets['private_key']}"
    )

    before = _paths_under(ROOT)
    start = time.perf_counter()
    result = _plan(body)
    elapsed = time.perf_counter() - start
    after = _paths_under(ROOT)
    text = _text(result)

    _assert(elapsed < 0.5, "Planner runtime exceeded limit.")
    _assert(before == after, "Planning created or modified files.")
    for value in secrets.values():
        _assert(value not in text, "Secret fixture value leaked.")
    _assert(str(Path.home()) not in text, "User profile path leaked.")
    _assert("Windows/System32" not in json.dumps(result["context"]["required_files"]), "Unsafe path entered required files.")
    _assert("/etc/shadow" not in json.dumps(result["context"]["required_files"]), "Sensitive path entered required files.")
    _assert("modules/task_planner_orchestrator_ru.py" in result["context"]["required_files"], "Safe relative file not detected.")
    _assert(len(result["request"]["preview"]) <= 300, "Preview length exceeded.")
    _assert(result["request"]["sha256"] == _plan(body)["request"]["sha256"], "SHA-256 is not deterministic.")
    _assert(result["request"]["normalized_length"] == len(" ".join(body.split())), "Normalized length changed.")


def test_execution_counters_and_external_calls() -> None:
    calls: list[str] = []
    original_run = subprocess.run
    original_socket = socket.socket
    original_urlopen = urllib.request.urlopen

    def fake_run(*args: Any, **kwargs: Any) -> Any:
        calls.append("run")
        raise AssertionError("subprocess use is forbidden")

    def fake_socket(*args: Any, **kwargs: Any) -> Any:
        calls.append("socket")
        raise AssertionError("network use is forbidden")

    def fake_urlopen(*args: Any, **kwargs: Any) -> Any:
        calls.append("urlopen")
        raise AssertionError("network use is forbidden")

    try:
        subprocess.run = fake_run
        socket.socket = fake_socket
        urllib.request.urlopen = fake_urlopen
        result = _plan("проверить проект без изменений")
    finally:
        subprocess.run = original_run
        socket.socket = original_socket
        urllib.request.urlopen = original_urlopen

    _assert(calls == [], "Planner used subprocess or network.")
    _assert(result["execution"] == {"performed": False, "writes": 0, "commands_run": 0, "network_requests": 0}, "Execution counters changed.")
    _assert(result["approval"]["execution_allowed"] is False, "Execution must not be allowed in v6.82.")


def test_panel_version_manifest_and_dispatcher() -> None:
    panel = importlib.import_module("LocalComet_Control_Panel")
    source = (ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    count = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "run_panel_chat_command"
    )
    _assert(count == 1, "Expected exactly one run_panel_chat_command definition.")
    _assert(type(panel.LOCALCOMET_VERSION) is str, "Panel version must be built-in str.")
    _assert(panel.LOCALCOMET_VERSION == "v6.82", "Panel version must be v6.82.")
    _assert(json.loads(json.dumps(panel.LOCALCOMET_VERSION)) == "v6.82", "Panel version JSON changed.")

    manifest = json.loads((ROOT / "localcomet_runtime_manifest.json").read_text(encoding="utf-8"))
    _assert("modules/task_planner_orchestrator_ru.py" in manifest.get("lazy_runtime", []), "Planner module missing from manifest.")
    _assert("tools/test_v682_task_planner.py" in manifest.get("tests", []), "Planner test missing from manifest.")
    for key in ("lazy_runtime", "tests"):
        values = manifest.get(key, [])
        _assert(values == sorted(values), f"Manifest list is not sorted: {key}")
        _assert(len(values) == len(set(values)), f"Manifest list has duplicates: {key}")

    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _assert(staged.returncode == 0 and staged.stdout.strip() == "", "Staged files are present.")


def main() -> None:
    tests = [
        test_import_has_no_side_effects,
        test_command_matching,
        test_panel_dispatch_once_and_route_order,
        test_schema_determinism_and_steps,
        test_risk_and_approval,
        test_redaction_paths_and_no_effects,
        test_execution_counters_and_external_calls,
        test_panel_version_manifest_and_dispatcher,
    ]
    for test in tests:
        start = time.perf_counter()
        test()
        elapsed = time.perf_counter() - start
        print(f"PASS {test.__name__} {elapsed:.3f}s")
    print("ALL v6.82 TASK PLANNER TESTS PASSED")


if __name__ == "__main__":
    main()
