#!/usr/bin/env python
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.test_fixtures.assertions import assert_condition
from tools.test_fixtures.path_inventory import paths_under_set


def _reload_module(name: str):
    sys.modules.pop(name, None)
    return importlib.import_module(name)


def test_panel_routes_single_dispatch() -> None:
    import LocalComet_Control_Panel as panel

    calls: list[str] = []

    originals = {
        "dev": panel._run_development_safety_command_ru_v676a,
        "reviewer": panel._run_reviewer_bridge_command_ru_v676a,
        "fallback": panel._run_panel_chat_command_before_v676a_minimal,
    }

    def run_dev(command):
        calls.append("dev")
        return {"route": "dev", "command": command}

    def run_reviewer(command):
        calls.append("reviewer")
        return {"route": "reviewer", "command": command}

    def run_fallback(command):
        calls.append("fallback")
        return {"route": "fallback", "command": command}

    try:
        panel._run_development_safety_command_ru_v676a = run_dev
        panel._run_reviewer_bridge_command_ru_v676a = run_reviewer
        panel._run_panel_chat_command_before_v676a_minimal = run_fallback

        calls.clear()
        result = panel.run_panel_chat_command("статус разработки")
        assert_condition(calls == ["dev"], "Safety route must dispatch exactly once.")
        assert_condition(result["route"] == "dev", "Safety command routed incorrectly.")

        calls.clear()
        result = panel.run_panel_chat_command("reviewer bridge status")
        assert_condition(calls == ["reviewer"], "Reviewer route must dispatch exactly once.")
        assert_condition(result["route"] == "reviewer", "Reviewer command routed incorrectly.")

        calls.clear()
        result = panel.run_panel_chat_command("definitely unknown v677 command")
        assert_condition(calls == ["fallback"], "Fallback must dispatch exactly once.")
        assert_condition(result["route"] == "fallback", "Unknown command skipped fallback.")
    finally:
        panel._run_development_safety_command_ru_v676a = originals["dev"]
        panel._run_reviewer_bridge_command_ru_v676a = originals["reviewer"]
        panel._run_panel_chat_command_before_v676a_minimal = originals["fallback"]


def test_safety_status_lightweight() -> None:
    os.environ["LOCALCOMET_ROOT"] = str(ROOT)
    os.environ.pop("LOCALCOMET_ROOT_DIR", None)
    safety = _reload_module("modules.development_safety_orchestrator_ru")

    def fail_gate_snapshot():
        raise AssertionError("Strict/contracts gates must not run for lightweight status.")

    safety._gate_snapshot = fail_gate_snapshot

    start = time.perf_counter()
    result = safety.status()
    elapsed = time.perf_counter() - start

    evaluation = result.get("evaluation", {})
    gates = evaluation.get("gates", {})
    assert_condition(elapsed < 0.5, f"Safety status took {elapsed:.3f}s; expected <0.5s.")
    assert_condition(gates.get("contracts", {}).get("executed") is False, "Contracts ran in status.")
    assert_condition(gates.get("strict", {}).get("executed") is False, "Strict checks ran in status.")
    assert_condition(
        evaluation.get("diff_risk", {}).get("untracked_ignored_for_risk") is True,
        "Untracked files must be ignored for risk.",
    )
    assert_condition(safety.ROOT_DIR == ROOT, "Safety ROOT_DIR must honor LOCALCOMET_ROOT.")


def test_reviewer_request_file_safety() -> None:
    with tempfile.TemporaryDirectory(prefix="localcomet_v677_reviewer_") as temp_text:
        temp_root = Path(temp_text)
        os.environ["LOCALCOMET_ROOT"] = str(temp_root)
        os.environ.pop("LOCALCOMET_ROOT_DIR", None)
        reviewer = _reload_module("modules.reviewer_bridge_ru")
        reviewer.collect_validation_snapshot = lambda: {
            "contracts": {"ok": True, "passed": 1, "total": 1},
            "strict": {"ok": True, "hard_failures": 0, "warnings": 0},
            "screenshot": {"enabled": False, "allow_write": False},
            "diff_risk": {"verdict": "GREEN_TO_CONTINUE", "source_changed": 0, "total_changed": 0},
        }

        first = reviewer.create_reviewer_request("same_task", "first")
        second = reviewer.create_reviewer_request("same_task", "second")
        traversal = reviewer.create_reviewer_request("../escape", "traversal probe")
        automatic = reviewer.create_reviewer_request("", "auto id probe")

        assert_condition(first["task_id"] == "same_task", "Reviewer task id was not preserved.")
        assert_condition(second["task_id"] == "same_task_2", "Duplicate reviewer id did not get suffix.")
        assert_condition(traversal["task_id"].startswith("review_"), "Traversal-like id was not replaced.")
        assert_condition(automatic["task_id"].startswith("review_"), "Blank id did not allocate auto id.")

        all_files = (
            first["files_created"]
            + second["files_created"]
            + traversal["files_created"]
            + automatic["files_created"]
        )
        assert_condition(len(first["files_created"]) == 3, "Reviewer must create exactly 3 files/request.")
        assert_condition(len(second["files_created"]) == 3, "Reviewer duplicate must create exactly 3 files.")
        for file_text in all_files:
            path = Path(file_text).resolve()
            path.relative_to(temp_root.resolve())
            assert_condition(path.exists(), f"Reviewer artifact missing: {path}")

        first_prompt = Path(first["files_created"][0]).read_text(encoding="utf-8")
        second_prompt = Path(second["files_created"][0]).read_text(encoding="utf-8")
        assert_condition("first" in first_prompt, "First reviewer prompt was overwritten.")
        assert_condition("second" in second_prompt, "Second reviewer prompt missing expected content.")
        assert_condition(reviewer.ROOT_DIR == temp_root.resolve(), "Reviewer ROOT_DIR must honor LOCALCOMET_ROOT.")


def test_nonexistent_root_overrides_are_read_only_on_import() -> None:
    modules = [
        "modules.reviewer_bridge_ru",
        "modules.development_safety_orchestrator_ru",
    ]
    for env_name in ("LOCALCOMET_ROOT", "LOCALCOMET_ROOT_DIR"):
        for module_name in modules:
            with tempfile.TemporaryDirectory(prefix="localcomet_v677_missing_root_") as temp_text:
                sandbox = Path(temp_text)
                configured_root = (sandbox / "missing-root").resolve()
                os.environ.pop("LOCALCOMET_ROOT", None)
                os.environ.pop("LOCALCOMET_ROOT_DIR", None)
                os.environ[env_name] = str(configured_root)

                before = paths_under_set(sandbox)
                module = _reload_module(module_name)
                after = paths_under_set(sandbox)

                assert_condition(module.ROOT_DIR == configured_root, f"{module_name} ignored {env_name}.")
                assert_condition(module.ROOT_DIR != ROOT, f"{module_name} fell back to the source repo.")
                assert_condition(before == after, f"{module_name} import created filesystem entries.")
                assert_condition(not configured_root.exists(), f"{module_name} import created the override root.")


def test_nonexistent_root_dispatches_do_not_escape_override() -> None:
    with tempfile.TemporaryDirectory(prefix="localcomet_v677_dispatch_root_") as temp_text:
        sandbox = Path(temp_text)
        configured_root = (sandbox / "missing-root").resolve()
        os.environ["LOCALCOMET_ROOT"] = str(configured_root)
        os.environ.pop("LOCALCOMET_ROOT_DIR", None)

        reviewer = _reload_module("modules.reviewer_bridge_ru")
        reviewer.collect_validation_snapshot = lambda: {
            "contracts": {"ok": True, "passed": 1, "total": 1},
            "strict": {"ok": True, "hard_failures": 0, "warnings": 0},
            "screenshot": {"enabled": False, "allow_write": False},
            "diff_risk": {"verdict": "GREEN_TO_CONTINUE", "source_changed": 0, "total_changed": 0},
        }

        result = reviewer.dispatch("reviewer bridge create missing_root_probe")
        assert_condition(result.get("ok") is True, "Reviewer dispatch failed for nonexistent override root.")
        for file_text in result.get("files_created", []):
            path = Path(file_text).resolve()
            path.relative_to(configured_root)
            path.relative_to(reviewer.INBOX_DIR.resolve())
            assert_condition(path.exists(), f"Reviewer dispatch did not create expected inbox file: {path}")
        observed = paths_under_set(sandbox)
        assert_condition(
            "missing-root/.localcomet/reviewer/archive" not in observed,
            "Reviewer dispatch created archive outside the inbox path.",
        )
        assert_condition(
            "missing-root/.localcomet/reviewer/outbox" not in observed,
            "Reviewer dispatch created outbox outside the inbox path.",
        )
        assert_condition(
            "missing-root/.localcomet/reviewer/templates" not in observed,
            "Reviewer dispatch created templates outside the inbox path.",
        )
        assert_condition(reviewer.ROOT_DIR == configured_root, "Reviewer dispatch selected the wrong root.")

    with tempfile.TemporaryDirectory(prefix="localcomet_v677_safety_root_") as temp_text:
        sandbox = Path(temp_text)
        configured_root = (sandbox / "missing-root").resolve()
        os.environ["LOCALCOMET_ROOT"] = str(configured_root)
        os.environ.pop("LOCALCOMET_ROOT_DIR", None)

        before = paths_under_set(sandbox)
        safety = _reload_module("modules.development_safety_orchestrator_ru")
        result = safety.status()
        after = paths_under_set(sandbox)

        assert_condition(result.get("ok") is True, "Safety status failed for nonexistent override root.")
        assert_condition(safety.ROOT_DIR == configured_root, "Safety status selected the wrong root.")
        assert_condition(before == after, "Safety status wrote under the configured missing root sandbox.")
        assert_condition(not configured_root.exists(), "Safety status created the configured missing root.")


def test_generate_capability_map_import_is_read_only() -> None:
    # NOTE: GenerateCapabilityMap.py is a minimal placeholder (see M-04 incident).
    # This test verifies only the import contract, not real map generation.
    with tempfile.TemporaryDirectory(prefix="localcomet_v677_report_") as temp_text:
        temp_root = Path(temp_text) / "root"
        report_dir = Path(temp_text) / "reports"
        temp_root.mkdir()
        os.environ["LOCALCOMET_ROOT"] = str(temp_root)
        os.environ["LOCALCOMET_REPORT_DIR"] = str(report_dir)

        module = _reload_module("GenerateCapabilityMap")
        assert_condition(module._project_root() == temp_root.resolve(), "Capability map root is not portable.")
        assert_condition(not report_dir.exists(), "GenerateCapabilityMap wrote reports during import.")


def main() -> None:
    tests = [
        test_panel_routes_single_dispatch,
        test_safety_status_lightweight,
        test_reviewer_request_file_safety,
        test_nonexistent_root_overrides_are_read_only_on_import,
        test_nonexistent_root_dispatches_do_not_escape_override,
        test_generate_capability_map_import_is_read_only,
    ]
    for test in tests:
        start = time.perf_counter()
        test()
        elapsed = time.perf_counter() - start
        print(f"PASS {test.__name__} {elapsed:.3f}s")
    print("ALL v6.77 REGRESSION TESTS PASSED")


if __name__ == "__main__":
    main()
