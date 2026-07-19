#!/usr/bin/env python
from __future__ import annotations

import ast
import importlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _paths_under(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {path.relative_to(root).as_posix() for path in root.rglob("*")}


def _load_panel(temp_root: Path):
    os.environ["LOCALCOMET_ROOT"] = str(temp_root)
    os.environ.pop("LOCALCOMET_ROOT_DIR", None)
    sys.modules.pop("LocalComet_Control_Panel", None)
    panel = importlib.import_module("LocalComet_Control_Panel")
    os.chdir(ROOT)
    return panel


def _patch_attr(module: Any, name: str, value: Any, restore: list[tuple[Any, str, Any]]) -> None:
    restore.append((module, name, getattr(module, name)))
    setattr(module, name, value)


def _sentinel_handler(route_name: str, calls: list[str]) -> Callable[[str], dict[str, Any]]:
    def handler(command: str) -> dict[str, Any]:
        calls.append(route_name)
        return {
            "mode": "command",
            "route": route_name,
            "plan": {"tool": route_name, "action": "dispatch"},
            "result": {"ok": True, "route_name": route_name, "command": command},
        }

    return handler


ROUTE_CASES = (
    ("app_harness_registry_ru_v668", "app harness status", "_run_app_harness_registry_command_ru_v668"),
    ("task_contract_registry_ru_v667", "task contract registry", "_run_task_contract_registry_command_ru_v667"),
    ("screenshot_retention_policy_config_ru_v664e", "retention policy write", "_run_screenshot_retention_policy_config_command_ru_v664e"),
    ("screenshot_storage_policy_simulator_ru_v664d", "storage policy simulate", "_run_screenshot_storage_policy_simulator_command_ru_v664d"),
    ("screenshot_retention_dry_run_ru_v664c", "screenshot dry run", "_run_screenshot_retention_dry_run_command_ru_v664c"),
    ("storage_cleanup_plan_ru_v664b", "cleanup plan", "_run_storage_cleanup_plan_command_ru_v664b"),
    ("repo_weight_audit_ru_v664a", "repo weight", "_run_repo_weight_audit_command_ru_v664a"),
    ("risk_classifier_ru_v663", "risk classify", "_run_risk_classifier_command_ru_v663"),
    ("plan_contract_ru_v662", "plan contract", "_run_plan_contract_command_ru_v662"),
    ("context_pack_ru_v661", "context pack", "_run_context_pack_command_ru_v661"),
    ("developer_velocity_ru_v658", "last failure", "_run_developer_velocity_command_ru_v658"),
    ("panel_capability_audit_ru_v656", "panel capability audit", "_run_panel_capability_audit_command_ru_v656"),
    ("strict_project_stability_ru", "проверь проект", "_run_strict_project_stability_ru_command"),
    ("patch_panel_compact_chat", "apply", "_run_patch_panel_bridge_command"),
    ("computer_use_core_ru", "pc computer full control status", "_run_computer_use_command_bridge"),
    ("screenshot_capture_policy_ru_v665c", "screenshot status", "_run_screenshot_capture_policy_command_ru_v665c"),
    ("working_directory_guard_ru_v665b", "working directory guard", "_run_working_directory_guard_command_ru_v665b"),
    ("confirmed_app_action_ru_v669", "confirm open calculator", "_run_confirmed_app_action_command_ru_v669"),
    ("direct_allowlisted_app_ru_v672", "open calculator", "_run_direct_allowlisted_app_command_ru_v672"),
)


PREDICATE_COMMANDS = (
    ("_is_development_safety_command_ru_v676a", "статус разработки"),
    ("_is_reviewer_bridge_command_ru_v676a", "создай запрос ревью v678_predicate_probe"),
    ("_is_app_harness_registry_command_ru_v668", "app harness status"),
    ("_is_task_contract_registry_command_ru_v667", "task contract registry"),
    ("_is_screenshot_retention_policy_config_command_ru_v664e", "retention policy write"),
    ("_is_screenshot_storage_policy_simulator_command_ru_v664d", "storage policy simulate"),
    ("_is_screenshot_retention_dry_run_command_ru_v664c", "screenshot dry run"),
    ("_is_storage_cleanup_plan_command_ru_v664b", "cleanup plan"),
    ("_is_repo_weight_audit_command_ru_v664a", "repo weight"),
    ("_is_risk_classifier_command_ru_v663", "risk classify"),
    ("_is_plan_contract_command_ru_v662", "plan contract"),
    ("_is_context_pack_command_ru_v661", "context pack"),
    ("_is_developer_velocity_command_ru_v658", "last failure"),
    ("_is_panel_capability_audit_command_ru_v656", "panel capability audit"),
    ("_is_strict_project_stability_ru_command", "проверь проект"),
    ("_is_patch_panel_bridge_command", "apply"),
    ("_is_computer_use_command_bridge", "pc computer full control status"),
    ("_is_screenshot_capture_policy_command_ru_v665c", "screenshot status"),
    ("_is_working_directory_guard_command_ru_v665b", "working directory guard"),
    ("_is_confirmed_app_action_command_ru_v669", "confirm open calculator"),
    ("_is_confirmed_desktop_action_command_ru_v665g", "confirm open browser"),
    ("_is_direct_allowlisted_app_command_ru_v672", "open calculator"),
    ("_is_plain_desktop_goal", "открой параметры системы"),
)


def test_safety_and_reviewer_routes() -> None:
    with tempfile.TemporaryDirectory(prefix="localcomet_v678_routes_") as temp_text:
        temp_root = Path(temp_text)
        panel = _load_panel(temp_root)
        safety_module = importlib.import_module("modules.development_safety_orchestrator_ru")
        reviewer_module = importlib.import_module("modules.reviewer_bridge_ru")
        real_safety_dispatch = safety_module.dispatch
        real_reviewer_dispatch = reviewer_module.dispatch
        calls: list[str] = []

        def safety_dispatch(command: str):
            calls.append("safety")
            return real_safety_dispatch(command)

        def reviewer_dispatch(command: str):
            calls.append("reviewer")
            return real_reviewer_dispatch(command)

        restore = []
        try:
            _patch_attr(safety_module, "dispatch", safety_dispatch, restore)
            _patch_attr(reviewer_module, "dispatch", reviewer_dispatch, restore)
            _patch_attr(
                reviewer_module,
                "collect_validation_snapshot",
                lambda: {
                    "contracts": {"ok": True, "passed": 1, "total": 1},
                    "strict": {"ok": True, "hard_failures": 0, "warnings": 0},
                    "screenshot": {"enabled": False, "allow_write": False},
                    "diff_risk": {"verdict": "GREEN_TO_CONTINUE", "source_changed": 0, "total_changed": 0},
                },
                restore,
            )

            start = time.perf_counter()
            safety_result = panel.run_panel_chat_command("статус разработки")
            elapsed = time.perf_counter() - start
            _assert(calls == ["safety"], "Safety command must dispatch exactly once.")
            _assert(elapsed < 0.5, f"Safety status took {elapsed:.3f}s.")
            safety_payload = safety_result.get("result", {})
            evaluation = safety_payload.get("evaluation", {})
            gates = evaluation.get("gates", {})
            _assert(safety_payload.get("mode") == "development_safety_orchestrator_status", "Safety result mode changed.")
            _assert(evaluation.get("lightweight") is True, "Safety status must stay lightweight.")
            _assert(gates.get("contracts", {}).get("executed") is False, "Contracts ran during safety status.")
            _assert(gates.get("strict", {}).get("executed") is False, "Strict ran during safety status.")
            _assert(
                evaluation.get("diff_risk", {}).get("untracked_ignored_for_risk") is True,
                "Untracked risk flag changed.",
            )

            calls.clear()
            reviewer_result = panel.run_panel_chat_command("создай запрос ревью v678_router_smoke")
            _assert(calls == ["reviewer"], "Reviewer command must dispatch exactly once.")
            _assert(reviewer_result.get("route") == "modules.reviewer_bridge_ru", "Reviewer route changed.")
            _assert(reviewer_result.get("result", {}).get("mode") == "reviewer_request_created", "Reviewer schema changed.")
        finally:
            for module, name, original in reversed(restore):
                setattr(module, name, original)


def test_all_reachable_legacy_routes_dispatch_once() -> None:
    with tempfile.TemporaryDirectory(prefix="localcomet_v678_legacy_") as temp_text:
        temp_root = Path(temp_text)
        panel = _load_panel(temp_root)
        calls: list[str] = []
        restore: list[tuple[Any, str, Any]] = []
        try:
            replacement_handlers = {}
            for route_name, _command, handler_name in ROUTE_CASES:
                handler = _sentinel_handler(route_name, calls)
                replacement_handlers[route_name] = handler
                _patch_attr(panel, handler_name, handler, restore)

            if hasattr(panel, "PANEL_ROUTES"):
                patched_routes = []
                for route_name, matcher, handler in panel.PANEL_ROUTES:
                    if isinstance(handler, str):
                        patched_routes.append((route_name, matcher, handler))
                        continue
                    patched_routes.append(
                        (route_name, matcher, replacement_handlers.get(route_name, handler))
                    )
                _patch_attr(panel, "PANEL_ROUTES", tuple(patched_routes), restore)

            for route_name, command, _handler_name in ROUTE_CASES:
                calls.clear()
                result = panel.run_panel_chat_command(command)
                _assert(calls == [route_name], f"{route_name} dispatched {calls}, expected one call.")
                _assert(result.get("mode") == "command", f"{route_name} top-level mode changed.")
                _assert(result.get("route") == route_name, f"{route_name} route changed.")
        finally:
            for module, name, original in reversed(restore):
                setattr(module, name, original)


def test_fallback_and_empty_input_schema() -> None:
    with tempfile.TemporaryDirectory(prefix="localcomet_v678_fallback_") as temp_text:
        panel = _load_panel(Path(temp_text))
        for command in ("definitely unknown v678 command", "   ", ""):
            result = panel.run_panel_chat_command(command)
            _assert(result.get("mode") == "new_menu_only", f"Fallback mode changed for {command!r}.")
            _assert(result.get("route") == "premium_task_panel_ru", f"Fallback route changed for {command!r}.")
            _assert(result.get("plan") == {"tool": "premium_task_panel_ru", "action": "chat"}, "Fallback plan changed.")


def test_predicates_are_read_only() -> None:
    with tempfile.TemporaryDirectory(prefix="localcomet_v678_predicates_") as temp_text:
        temp_root = Path(temp_text)
        panel = _load_panel(temp_root)
        before = _paths_under(temp_root)
        for predicate_name, command in PREDICATE_COMMANDS:
            predicate = getattr(panel, predicate_name)
            result = predicate(command)
            if isinstance(result, dict):
                _assert(any(result.values()), f"{predicate_name} did not recognize {command!r}.")
            else:
                _assert(bool(result), f"{predicate_name} did not recognize {command!r}.")
        after = _paths_under(temp_root)
        _assert(before == after, f"Predicates wrote to temp root: {sorted(after - before)}")


def test_router_ast_shape_when_consolidated() -> None:
    source = ROOT / "LocalComet_Control_Panel.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    count = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "run_panel_chat_command"
    )
    if hasattr(importlib.import_module("LocalComet_Control_Panel"), "PANEL_ROUTES"):
        _assert(count == 1, f"Consolidated router must have one run_panel_chat_command, found {count}.")


def test_headless_self_check_version_marker() -> None:
    with tempfile.TemporaryDirectory(prefix="localcomet_v678_self_check_") as temp_text:
        panel = _load_panel(Path(temp_text))
        source = (ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
        _assert(type(panel.LOCALCOMET_VERSION) is str, "Panel version must be a built-in str.")
        _assert(panel.LOCALCOMET_VERSION.startswith("v6."), "Panel version marker must be an active release.")
        _assert(json.loads(json.dumps(panel.LOCALCOMET_VERSION)) == panel.LOCALCOMET_VERSION, "Panel version JSON changed.")
        _assert(f'LOCALCOMET_VERSION = "{panel.LOCALCOMET_VERSION}"' in source, "Active version marker missing.")
        _assert("_LocalCometVersion" not in source, "Custom version class remains.")
        _assert('LOCALCOMET_VERSION == "v6.64"' not in source, "Self-check still expects v6.64.")

        result = panel.run_headless_self_check()
        _assert(result.get("version") == panel.LOCALCOMET_VERSION, "Self-check version does not match LOCALCOMET_VERSION.")
        version_check = next(
            item for item in result.get("checks", [])
            if item.get("name") == "version marker"
        )
        _assert(version_check.get("ok") is True, "Self-check version marker failed.")
        _assert(version_check.get("details") == panel.LOCALCOMET_VERSION, "Self-check version details changed.")

        tree = ast.parse(source)
        count = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "run_panel_chat_command"
        )
        _assert(count == 1, f"Consolidated router must have one run_panel_chat_command, found {count}.")


def main() -> None:
    tests = [
        test_safety_and_reviewer_routes,
        test_all_reachable_legacy_routes_dispatch_once,
        test_fallback_and_empty_input_schema,
        test_predicates_are_read_only,
        test_router_ast_shape_when_consolidated,
        test_headless_self_check_version_marker,
    ]
    for test in tests:
        start = time.perf_counter()
        test()
        elapsed = time.perf_counter() - start
        print(f"PASS {test.__name__} {elapsed:.3f}s")
    print("ALL v6.78 ROUTER REGISTRY TESTS PASSED")


if __name__ == "__main__":
    main()
