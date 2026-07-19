#!/usr/bin/env python
from __future__ import annotations

import ast
import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _paths_under(root: Path) -> dict[str, int]:
    if not root.exists():
        return {}
    result: dict[str, int] = {}
    for path in root.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            result[path.relative_to(root).as_posix()] = path.stat().st_size
    return result


def _reload_diagnostics(root: Path | None = None):
    if root is None:
        os.environ.pop("LOCALCOMET_ROOT", None)
        os.environ.pop("LOCALCOMET_ROOT_DIR", None)
    else:
        os.environ["LOCALCOMET_ROOT"] = str(root)
        os.environ.pop("LOCALCOMET_ROOT_DIR", None)
    sys.modules.pop("modules.maintenance_diagnostics_ru", None)
    return importlib.import_module("modules.maintenance_diagnostics_ru")


def test_import_creates_no_files() -> None:
    before = _paths_under(ROOT)
    _reload_diagnostics()
    after = _paths_under(ROOT)
    _assert(before == after, "Diagnostics import created or modified files.")


def test_command_matching() -> None:
    diag = _reload_diagnostics()
    for command in ("диагностика проекта", "project diagnostics", "maintenance status"):
        _assert(diag.is_diagnostics_command(command), f"Command did not match: {command}")
    for command in ("status", "reviewer bridge status", "проверь проект", ""):
        _assert(not diag.is_diagnostics_command(command), f"Unrelated command matched: {command!r}")


def test_panel_route_invokes_diagnostics_once() -> None:
    panel = importlib.import_module("LocalComet_Control_Panel")
    diag = _reload_diagnostics()
    calls: list[str] = []
    originals = {
        "diagnostics": diag.dispatch,
        "safety": panel._run_development_safety_command_ru_v676a,
        "reviewer": panel._run_reviewer_bridge_command_ru_v676a,
    }

    def fake_dispatch(command: str) -> dict[str, Any]:
        calls.append("diagnostics")
        return {
            "mode": "maintenance_diagnostics_status",
            "version": "v6.81",
            "ok": True,
            "command": command,
        }

    def fake_safety(command: str) -> dict[str, Any]:
        calls.append("safety")
        return {"ok": False}

    def fake_reviewer(command: str) -> dict[str, Any]:
        calls.append("reviewer")
        return {"ok": False}

    try:
        diag.dispatch = fake_dispatch
        panel._run_development_safety_command_ru_v676a = fake_safety
        panel._run_reviewer_bridge_command_ru_v676a = fake_reviewer
        result = panel.run_panel_chat_command("диагностика проекта")
        _assert(calls == ["diagnostics"], f"Unexpected route calls: {calls}")
        _assert(result.get("route") == "modules.maintenance_diagnostics_ru", "Wrong diagnostics route.")
    finally:
        diag.dispatch = originals["diagnostics"]
        panel._run_development_safety_command_ru_v676a = originals["safety"]
        panel._run_reviewer_bridge_command_ru_v676a = originals["reviewer"]


def test_panel_version_plain_string() -> None:
    panel = importlib.import_module("LocalComet_Control_Panel")
    source = (ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    _assert(type(panel.LOCALCOMET_VERSION) is str, "LOCALCOMET_VERSION must be built-in str.")
    _assert(panel.LOCALCOMET_VERSION.startswith("v6."), "LOCALCOMET_VERSION must be an active v6 release.")
    _assert(json.loads(json.dumps(panel.LOCALCOMET_VERSION)) == panel.LOCALCOMET_VERSION, "Version JSON serialization changed.")
    _assert('_LocalCometVersion' not in source, "Custom version class remains in panel source.")
    _assert(f'LOCALCOMET_VERSION = "{panel.LOCALCOMET_VERSION}"' in source, "Plain active version marker missing.")


def test_safety_called_once_and_lightweight() -> None:
    diag = _reload_diagnostics()
    safety = importlib.import_module("modules.development_safety_orchestrator_ru")
    original = safety.status
    calls: list[str] = []

    def fake_status() -> dict[str, Any]:
        calls.append("safety")
        return {
            "ok": True,
            "mode": "development_safety_orchestrator_status",
            "evaluation": {
                "lightweight": True,
                "overall_verdict": "GREEN_TO_CONTINUE",
                "gates": {
                    "strict": {"executed": False},
                    "contracts": {"executed": False},
                },
            },
        }

    try:
        safety.status = fake_status
        result = diag.diagnostics_status()
    finally:
        safety.status = original
    _assert(calls == ["safety"], f"Safety call count changed: {calls}")
    _assert(result["safety"]["lightweight"] is True, "Safety was not lightweight.")
    _assert(result["safety"]["strict_executed"] is False, "Strict gate executed.")
    _assert(result["safety"]["contracts_executed"] is False, "Contracts gate executed.")


def test_schema_privacy_and_runtime() -> None:
    diag = _reload_diagnostics()
    os.environ["LOCALCOMET_TEST_SECRET_VALUE"] = "secret-value-681"
    before = _paths_under(ROOT)
    start = time.perf_counter()
    result = diag.diagnostics_status()
    elapsed = time.perf_counter() - start
    after = _paths_under(ROOT)
    expected_keys = [
        "mode",
        "version",
        "ok",
        "project",
        "router",
        "git",
        "safety",
        "retention",
        "preflight",
        "audit_bundle",
        "tests",
        "warnings",
    ]
    _assert(list(result.keys()) == expected_keys, "Top-level schema keys changed.")
    _assert(elapsed < 0.5, f"Diagnostics took {elapsed:.3f}s.")
    _assert(before == after, "Diagnostics created or modified project files.")
    text = json.dumps(result, ensure_ascii=False, sort_keys=True)
    _assert("<PROJECT_ROOT>" in text, "Project root was not redacted.")
    _assert(str(Path.home()) not in text, "User profile path leaked.")
    _assert(str(ROOT) not in text and ROOT.as_posix() not in text, "Full project path leaked.")
    _assert("secret-value-681" not in text, "Environment secret value leaked.")
    for filename in ("LocalComet_Control_Panel.py", "modules/desktop_observer.py", ".gitignore"):
        _assert(filename not in text, f"Changed filename leaked: {filename}")
    _assert(result["tests"]["executed_now"] is False, "Diagnostics executed tests.")
    _assert(result["project"]["release"] == "v6.81", "Diagnostics project release changed.")


def test_missing_subsystems_warn_safely() -> None:
    with tempfile.TemporaryDirectory(prefix="localcomet_v681_missing_") as temp_text:
        temp_root = Path(temp_text)
        diag = _reload_diagnostics(temp_root)

        class FailedGit:
            returncode = 1
            stdout = ""
            stderr = "fatal"

        original_run = diag.subprocess.run
        try:
            diag.subprocess.run = lambda *args, **kwargs: FailedGit()
            result = diag.diagnostics_status()
        finally:
            diag.subprocess.run = original_run
        _assert(result["git"]["available"] is False, "Missing Git did not degrade safely.")
        _assert(result["preflight"]["manifest_present"] is False, "Missing manifest not reported.")
        _assert(result["audit_bundle"]["creator_present"] is False, "Missing creator not reported.")
        _assert(result["audit_bundle"]["verifier_present"] is False, "Missing verifier not reported.")
        _assert(result["warnings"], "Missing subsystems produced no warnings.")
        warning_text = json.dumps(result["warnings"], ensure_ascii=False)
        _assert(str(temp_root) not in warning_text, "Warning leaked temp root.")


def test_ast_single_dispatcher_and_route_present() -> None:
    source = (ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    count = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "run_panel_chat_command"
    )
    _assert(count == 1, f"Expected one run_panel_chat_command, found {count}.")
    _assert("maintenance_diagnostics_ru_v681" in source, "Diagnostics route missing.")


def test_previous_suites_and_staging() -> None:
    commands = [
        [sys.executable, "tools/test_v677_regression.py"],
        [sys.executable, "tools/test_v678_router_registry.py"],
        [sys.executable, "tools/test_v679_retention.py"],
        [sys.executable, "tools/test_v6801_audit_bundle.py"],
        [sys.executable, "tools/test_v6802_bundle_security.py"],
    ]
    optional = ROOT / "tools" / "test_v680_reproducibility.py"
    if optional.exists():
        commands.insert(3, [sys.executable, "tools/test_v680_reproducibility.py"])
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
            check=False,
        )
        _assert(completed.returncode == 0, f"Regression failed: {' '.join(command)}")
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _assert(staged.returncode == 0 and staged.stdout.strip() == "", "Staged files are present.")


def main() -> None:
    tests = [
        test_import_creates_no_files,
        test_command_matching,
        test_panel_route_invokes_diagnostics_once,
        test_panel_version_plain_string,
        test_safety_called_once_and_lightweight,
        test_schema_privacy_and_runtime,
        test_missing_subsystems_warn_safely,
        test_ast_single_dispatcher_and_route_present,
        test_previous_suites_and_staging,
    ]
    for test in tests:
        start = time.perf_counter()
        test()
        print(f"PASS {test.__name__} {time.perf_counter() - start:.3f}s")
    print("ALL v6.81 DIAGNOSTICS TESTS PASSED")


if __name__ == "__main__":
    main()
