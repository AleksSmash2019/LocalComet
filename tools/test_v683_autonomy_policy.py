#!/usr/bin/env python
from __future__ import annotations

import ast
import hashlib
import importlib
import json
import math
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import replace
from datetime import datetime, timezone
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
    result: dict[str, int] = {}
    for path in root.rglob("*"):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path.stat().st_size
    return result


def _import_modules():
    sys.modules.pop("modules.autonomy_policy_ru", None)
    sys.modules.pop("modules.autonomous_run_state_ru", None)
    policy = importlib.import_module("modules.autonomy_policy_ru")
    state = importlib.import_module("modules.autonomous_run_state_ru")
    return policy, state


def _proposal(action_type: str = "inspect", **updates: Any):
    policy = importlib.import_module("modules.autonomy_policy_ru")
    data = {
        "action_id": "action_01",
        "action_type": action_type,
        "target": "modules/task_planner_orchestrator_ru.py",
        "arguments": {},
        "read_only": True,
        "reversible": True,
        "expected_original_sha256": None,
        "estimated_changed_files": 0,
        "estimated_changed_lines": 0,
        "estimated_subprocesses": 0,
        "estimated_output_bytes": 0,
        "requires_network": False,
        "requires_elevation": False,
    }
    data.update(updates)
    return policy.ActionProposal(**data)


def _decision(policy_obj: Any, proposal: Any, usage: Any | None = None, kill: Any | None = None) -> dict[str, Any]:
    policy = importlib.import_module("modules.autonomy_policy_ru")
    return policy.serialize_policy_decision(policy.evaluate_action_proposal(policy_obj, proposal, usage=usage, kill_switch=kill))


def _raises(fn, message: str) -> None:
    try:
        fn()
    except Exception:
        return
    raise AssertionError(message)


def test_import_side_effects() -> None:
    before = _paths_under(ROOT)
    env_before = dict(os.environ)
    calls: list[str] = []
    original_run = subprocess.run
    original_popen = subprocess.Popen
    original_socket = socket.socket
    original_urlopen = urllib.request.urlopen

    def forbidden(name: str):
        def inner(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            raise AssertionError("external effect")

        return inner

    try:
        subprocess.run = forbidden("run")
        subprocess.Popen = forbidden("popen")
        socket.socket = forbidden("socket")
        urllib.request.urlopen = forbidden("urlopen")
        policy, state = _import_modules()
    finally:
        subprocess.run = original_run
        subprocess.Popen = original_popen
        socket.socket = original_socket
        urllib.request.urlopen = original_urlopen
    after = _paths_under(ROOT)
    _assert(policy.AUTONOMY_POLICY_VERSION == "v6.83", "Policy version changed.")
    _assert(state.AUTONOMOUS_RUN_STATE_VERSION == "v6.83", "State version changed.")
    _assert(before == after, "Imports created or modified files.")
    _assert(calls == [], "Imports used subprocess or network.")
    _assert(env_before == dict(os.environ), "Imports mutated environment.")


def test_policy_defaults_and_validation() -> None:
    policy = importlib.import_module("modules.autonomy_policy_ru")
    with tempfile.TemporaryDirectory(prefix="lc_v683_policy_") as temp_text:
        root = Path(temp_text)
        p = policy.default_autonomy_policy(root)
        payload = policy.serialize_policy(p)
        _assert(payload["level"] == "LEVEL_1_PLAN_ONLY", "Default level changed.")
        _assert(payload["allowed_roots"] == ["<PROJECT_ROOT>"], "Default root was not redacted.")
        _assert(str(root) not in json.dumps(payload), "Full root leaked.")
        _assert(payload["budgets"] == {
            "max_actions": 50,
            "max_changed_files": 5,
            "max_changed_lines": 500,
            "max_output_bytes": 1000000,
            "max_replans": 3,
            "max_runtime_seconds": 900.0,
            "max_subprocesses": 20,
        }, "Default budget changed.")
        _assert(payload == policy.serialize_policy(p), "Policy serialization is not deterministic.")
        _assert(policy.validate_autonomy_policy(p) == (), "Default policy should validate.")
        _assert("unknown_autonomy_level" in policy.validate_autonomy_policy(replace(p, level="TEXT_RAISED_LEVEL")), "Unknown level not rejected.")
        _assert("unknown_action_type" in policy.validate_autonomy_policy(replace(p, allowed_actions=("inspect", "custom"))), "Unknown action not rejected.")
    _raises(lambda: policy.AutonomyBudget(max_actions=True), "Boolean budget accepted.")
    _raises(lambda: policy.AutonomyBudget(max_runtime_seconds=math.inf), "Non-finite budget accepted.")
    _raises(lambda: policy.AutonomyBudget(max_changed_files=-1), "Negative budget accepted.")
    _raises(lambda: policy.AutonomyBudget(max_actions=1001), "Hard budget cap not enforced.")


def test_action_proposals_and_levels() -> None:
    policy = importlib.import_module("modules.autonomy_policy_ru")
    with tempfile.TemporaryDirectory(prefix="lc_v683_levels_") as temp_text:
        root = Path(temp_text)
        default = policy.default_autonomy_policy(root)
        inspect = _proposal()
        _assert(_decision(default, inspect)["decision"] == "BLOCK", "LEVEL_1 inspect should not be executable.")
        level0 = replace(default, level=policy.AutonomyLevel.LEVEL_0_INSPECT_ONLY)
        _assert(_decision(level0, inspect)["decision"] == "ALLOW", "LEVEL_0 inspect should be allowed.")
        _assert(_decision(level0, _proposal("test"))["decision"] == "BLOCK", "LEVEL_0 test should block.")
        level2 = replace(default, level=policy.AutonomyLevel.LEVEL_2_SAFE_AUTOMATION, allowed_actions=("analyze", "inspect", "plan", "test", "verify"))
        _assert(_decision(level2, _proposal("test"))["decision"] == "REQUIRE_APPROVAL", "LEVEL_2 test approval changed.")
        _assert(_decision(level2, _proposal("edit_file", read_only=False, estimated_changed_files=1, estimated_changed_lines=1))["decision"] == "BLOCK", "LEVEL_2 project write should block.")
        good_hash = "a" * 64
        level3 = replace(default, level=policy.AutonomyLevel.LEVEL_3_CONTROLLED_EDIT, allowed_actions=("edit_file", "inspect", "plan"))
        edit = _proposal("edit_file", read_only=False, expected_original_sha256=good_hash, estimated_changed_files=1, estimated_changed_lines=2)
        _assert(_decision(level3, edit)["decision"] == "REQUIRE_APPROVAL", "LEVEL_3 edit should require approval.")
        _assert(_decision(level3, replace(edit, expected_original_sha256=None))["decision"] == "BLOCK", "LEVEL_3 edit without hash should block.")
        level4 = replace(default, level=policy.AutonomyLevel.LEVEL_4_BOUNDED_FULL_AUTONOMY, allowed_actions=("inspect", "credential_access"))
        _assert(_decision(level4, _proposal("credential_access"))["risk"] == "CRITICAL", "Credential risk changed.")
        _assert(_decision(level4, _proposal("credential_access"))["decision"] == "BLOCK", "Credential action should block.")
        for action in ("secret_extraction", "privilege_escalation", "persistence", "security_bypass"):
            data = _decision(level4, _proposal(action))
            _assert(data["risk"] == "CRITICAL" and data["decision"] == "BLOCK", "Permanent-danger action not blocked.")
        for action in ("kill_switch_change", "policy_change"):
            data = _decision(default, _proposal(action))
            _assert(data["decision"] == "BLOCK", "Policy or kill-switch modification was not blocked.")
        _assert(_decision(default, _proposal("not_real"))["decision"] == "BLOCK", "Unknown action type not blocked.")
        _assert(_decision(default, _proposal(action_id="../bad"))["decision"] == "BLOCK", "Malformed action id not blocked.")
        _assert(_decision(default, _proposal(arguments={"a": [[[[[[1]]]]]]}))["decision"] == "BLOCK", "Oversized nesting not blocked.")
        _assert(_decision(default, _proposal(arguments={"nan": float("nan")}))["decision"] == "BLOCK", "NaN argument not blocked.")
        _assert(_decision(default, _proposal(read_only=True, estimated_changed_lines=1))["decision"] == "BLOCK", "Read-only write estimate not blocked.")
        _assert(_decision(default, _proposal(requires_elevation=True))["decision"] == "BLOCK", "Elevation not blocked.")


def test_path_safety_and_protection() -> None:
    policy = importlib.import_module("modules.autonomy_policy_ru")
    with tempfile.TemporaryDirectory(prefix="lc_v683_paths_") as temp_text, tempfile.TemporaryDirectory(prefix="lc_v683_external_") as ext_text:
        root = Path(temp_text)
        external = Path(ext_text)
        safe = policy.validate_target_path(root, "modules/example.py")
        _assert(safe["ok"] is True and safe["normalized_target"] == "<PROJECT_ROOT>/modules/example.py", "Safe target failed.")
        for bad in ("../outside.py", "..\\..\\Windows\\System32", "C:\\Windows\\System32", "C:Windows\\System32", "\\\\server\\share", "/etc/shadow", "bad\x00path"):
            _assert(policy.validate_target_path(root, bad)["ok"] is False, "Unsafe path accepted.")
        link = root / "link_out"
        try:
            link.symlink_to(external, target_is_directory=True)
            _assert(policy.validate_target_path(root, "link_out/file.txt")["ok"] is False, "Symlink escape accepted.")
        except OSError:
            print("SKIP symlink escape test: platform refused test symlink")
        for protected in (".git/config", ".incident_backup/x", ".localcomet/reviewer/x", ".localcomet/policies/x", ".tmp/x", "__pycache__/x", ".localcomet/autonomy/STOP"):
            data = policy.validate_target_path(root, protected)
            _assert(data["protected"] is True and data["ok"] is False, "Protected path not blocked.")
        for allowed in (".localcomet/autonomy/runs/item", ".localcomet/autonomy/checkpoints/item", ".localcomet/autonomy/memory/item"):
            _assert(policy.validate_target_path(root, allowed)["protected"] is False, "Future autonomy root was globally blocked.")
        text = json.dumps(policy.validate_target_path(root, "modules/example.py"))
        _assert(str(root) not in text and str(Path.home()) not in text, "Machine path leaked.")


def test_kill_switches_and_budget() -> None:
    policy = importlib.import_module("modules.autonomy_policy_ru")
    with tempfile.TemporaryDirectory(prefix="lc_v683_kill_") as temp_text:
        root = Path(temp_text)
        _assert(policy.inspect_kill_switches(root, {}) .mode == policy.KillSwitchMode.NONE, "NONE switch changed.")
        _assert(policy.inspect_kill_switches(root, {"LOCALCOMET_AUTONOMY_DISABLED": "1"}).mode == policy.KillSwitchMode.DISABLE, "DISABLE not detected.")
        _assert(policy.inspect_kill_switches(root, {"LOCALCOMET_AUTONOMY_PAUSE": "TrUe"}).mode == policy.KillSwitchMode.PAUSE, "PAUSE not detected.")
        stop = root / ".localcomet" / "autonomy" / "STOP"
        stop.parent.mkdir(parents=True)
        stop.write_text("not returned", encoding="utf-8")
        _assert(policy.inspect_kill_switches(root, {}).mode == policy.KillSwitchMode.STOP_FILE, "STOP file not detected.")
        _assert("not returned" not in str(policy.inspect_kill_switches(root, {})), "STOP contents leaked.")
        _assert(policy.inspect_kill_switches(root, {"LOCALCOMET_AUTONOMY_DISABLED": "yes", "LOCALCOMET_AUTONOMY_PAUSE": "yes"}).mode == policy.KillSwitchMode.DISABLE, "Switch precedence changed.")
        _assert(policy.inspect_kill_switches(root, {"LOCALCOMET_AUTONOMY_PAUSE": "maybe"}).mode == policy.KillSwitchMode.STOP_FILE, "Unknown env value activated incorrectly.")
        p = replace(policy.default_autonomy_policy(root), level=policy.AutonomyLevel.LEVEL_0_INSPECT_ONLY)
        blocked = _decision(p, _proposal(), kill=policy.KillSwitchStatus(True, policy.KillSwitchMode.PAUSE, "pause"))
        _assert(blocked["decision"] == "BLOCK", "Active kill switch did not block.")
        original_exists = policy.Path.exists
        try:
            def fake_exists(self: Path) -> bool:
                if str(self).endswith("STOP"):
                    raise OSError("blocked")
                return original_exists(self)
            policy.Path.exists = fake_exists
            _assert(policy.inspect_kill_switches(root, {}).active is True, "STOP check error did not block.")
        finally:
            policy.Path.exists = original_exists

    budget = policy.AutonomyBudget(max_actions=2, max_runtime_seconds=10, max_changed_files=1, max_changed_lines=3, max_subprocesses=1, max_output_bytes=10, max_replans=1)
    usage = policy.BudgetUsage(actions_used=1, runtime_seconds_used=10, changed_files_used=0, changed_lines_used=1, subprocesses_used=0, output_bytes_used=5, replans_used=1)
    exact = policy.evaluate_budget(budget, usage, _proposal("edit_file", read_only=False, estimated_changed_files=1, estimated_changed_lines=2, estimated_subprocesses=1, estimated_output_bytes=5))
    _assert(exact["within_limits"] is True and exact["remaining_actions"] == 0, "Exact budget boundary failed.")
    for name, (case_usage, proposal) in {
        "actions": (replace(usage, actions_used=2), _proposal("inspect")),
        "runtime_seconds": (replace(usage, runtime_seconds_used=11), _proposal("inspect")),
        "changed_files": (usage, _proposal("edit_file", read_only=False, estimated_changed_files=2)),
        "changed_lines": (usage, _proposal("edit_file", read_only=False, estimated_changed_lines=4)),
        "subprocesses": (usage, _proposal("test", estimated_subprocesses=2)),
        "output_bytes": (usage, _proposal("test", estimated_output_bytes=20)),
        "replans": (replace(usage, replans_used=2), _proposal("inspect")),
    }.items():
        data = policy.evaluate_budget(budget, case_usage, proposal)
        _assert(data["within_limits"] is False and name in data["exceeded"], "Budget overflow not reported.")
        _assert(all(v >= 0 for k, v in data.items() if k.startswith("remaining_")), "Remaining budget went negative.")


def test_run_id_state_transitions_and_privacy() -> None:
    state_mod = importlib.import_module("modules.autonomous_run_state_ru")
    secret_goal = "Проверить " + "sk" + "-" + "X" * 16
    normalized = state_mod.normalize_goal("  Проверить   проект  ")
    _assert(normalized == "Проверить проект", "Goal normalization changed.")
    _assert(state_mod.compute_goal_hash(normalized) == hashlib.sha256(normalized.encode("utf-8")).hexdigest(), "Goal hash changed.")
    run_a = state_mod.compute_run_id(normalized, "nonce-a")
    run_b = state_mod.compute_run_id("Проверить проект", "nonce-a")
    run_c = state_mod.compute_run_id("Проверить проект", "nonce-b")
    _assert(run_a == run_b and run_a != run_c and len(run_a) == 24, "Run ID determinism changed.")
    _raises(lambda: state_mod.compute_run_id("goal", ""), "Empty nonce accepted.")
    _raises(lambda: state_mod.compute_run_id("x" * 4001, "nonce"), "Oversized goal accepted.")
    _raises(lambda: state_mod.compute_run_id("goal", "n" * 257), "Oversized nonce accepted.")

    s = state_mod.create_run_state(secret_goal, "session-a", now="2026-07-13T12:00:00Z")
    text = json.dumps(state_mod.serialize_run_state(s), ensure_ascii=False)
    _assert(secret_goal not in text and "session-a" not in text, "Raw goal or nonce leaked.")
    _assert(s.status == state_mod.RunStatus.CREATED, "Initial status changed.")
    s2 = state_mod.transition_run_state(s, "PLANNING", now="2026-07-13T12:00:01Z", current_step="step_01")
    _assert(s2.status == state_mod.RunStatus.PLANNING, "Allowed transition failed.")
    _raises(lambda: state_mod.transition_run_state(s2, "PLANNING", now="2026-07-13T12:00:02Z"), "Self-transition accepted.")
    _raises(lambda: state_mod.transition_run_state(s2, "CREATED", now="2026-07-13T12:00:02Z"), "Disallowed transition accepted.")
    _raises(lambda: state_mod.transition_run_state(s2, "RUNNING", now="2026-07-13T12:00:00Z"), "Earlier timestamp accepted.")
    _raises(lambda: state_mod.create_run_state("goal", "nonce", now=datetime(2026, 7, 13, 12, 0, 0)), "Naive datetime accepted.")
    waiting = state_mod.transition_run_state(s2, "WAITING_APPROVAL", now="2026-07-13T12:00:02Z")
    _assert(waiting.approval_required is True, "WAITING_APPROVAL consistency changed.")
    _raises(lambda: state_mod.transition_run_state(s2, "WAITING_APPROVAL", now="2026-07-13T12:00:02Z", approval_required=False), "Inconsistent approval accepted.")
    paused = state_mod.transition_run_state(waiting, "PAUSED", now="2026-07-13T12:00:03Z", reason="manual_review")
    _assert(paused.pause_reason == "manual_review", "Pause reason changed.")
    _raises(lambda: state_mod.transition_run_state(waiting, "PAUSED", now="2026-07-13T12:00:03Z"), "Pause without reason accepted.")
    completed_step = state_mod.record_completed_step(s2, "step_01", now="2026-07-13T12:00:02Z")
    _assert(completed_step.current_step is None and completed_step.completed_steps == ("step_01",), "Completed step recording changed.")
    _raises(lambda: state_mod.record_completed_step(completed_step, "step_01", now="2026-07-13T12:00:03Z"), "Duplicate completed step accepted.")
    failed_step = state_mod.record_failed_step(s2, "step_02", "validation_failed", now="2026-07-13T12:00:02Z")
    _assert(failed_step.failed_steps == ("step_02",), "Failed step recording changed.")
    _raises(lambda: state_mod.record_failed_step(s2, "../bad", "validation_failed", now="2026-07-13T12:00:02Z"), "Unsafe step accepted.")
    _raises(lambda: state_mod.record_failed_step(s2, "step_03", "token=" + "x", now="2026-07-13T12:00:02Z"), "Unsafe reason accepted.")
    terminal = state_mod.transition_run_state(s2, "FAILED", now="2026-07-13T12:00:04Z", reason="validation_failed")
    _assert(terminal.current_step is None and terminal.termination_reason == "validation_failed", "Terminal transition changed.")
    _raises(lambda: state_mod.transition_run_state(terminal, "PLANNING", now="2026-07-13T12:00:05Z"), "Terminal transition accepted.")
    invalid = replace(s2, completed_steps=("step_01",), failed_steps=("step_01",))
    _assert("step_completed_and_failed" in state_mod.validate_run_state(invalid), "Invalid state finding missing.")


def test_run_budget_and_policy_interaction() -> None:
    policy = importlib.import_module("modules.autonomy_policy_ru")
    state_mod = importlib.import_module("modules.autonomous_run_state_ru")
    s = state_mod.create_run_state("Проверить проект", "nonce", now="2026-07-13T12:00:00Z")
    used = state_mod.consume_run_budget(s, actions=1, writes=1, changed_files=1, changed_lines=2, subprocesses=1, output_bytes=3, replans=1, now="2026-07-13T12:00:01Z")
    _assert(used.actions_used == 1 and s.actions_used == 0, "Budget increment mutated input.")
    _raises(lambda: state_mod.consume_run_budget(s, actions=-1), "Negative increment accepted.")
    _raises(lambda: state_mod.consume_run_budget(s, actions=True), "Boolean increment accepted.")
    _raises(lambda: state_mod.consume_run_budget(s, output_bytes=1_000_000_001), "Excessive increment accepted.")
    p = replace(policy.default_autonomy_policy(ROOT), level=policy.AutonomyLevel.LEVEL_4_BOUNDED_FULL_AUTONOMY, allowed_actions=("inspect", "plan"))
    decision = state_mod.policy_decision_for_run(p, used, _proposal("inspect"))
    _assert(decision.budget["remaining_actions"] == 48, "Run counters not used in policy decision.")
    terminal = state_mod.transition_run_state(state_mod.transition_run_state(s, "PLANNING", now="2026-07-13T12:00:01Z"), "FAILED", now="2026-07-13T12:00:02Z", reason="validation_failed")
    _assert(state_mod.policy_decision_for_run(p, terminal, _proposal("inspect")).decision == policy.PolicyDecisionType.BLOCK, "Terminal run did not block.")
    paused = state_mod.transition_run_state(state_mod.transition_run_state(s, "PLANNING", now="2026-07-13T12:00:01Z"), "PAUSED", now="2026-07-13T12:00:02Z", reason="manual_review")
    _assert(state_mod.policy_decision_for_run(p, paused, _proposal("inspect")).decision == policy.PolicyDecisionType.BLOCK, "Paused run did not block.")
    waiting = state_mod.transition_run_state(state_mod.transition_run_state(s, "PLANNING", now="2026-07-13T12:00:01Z"), "WAITING_APPROVAL", now="2026-07-13T12:00:02Z")
    _assert(state_mod.policy_decision_for_run(p, waiting, _proposal("test")).decision == policy.PolicyDecisionType.BLOCK, "Waiting approval bypassed approval.")


def test_manifest_and_regression_invariants() -> None:
    manifest = json.loads((ROOT / "localcomet_runtime_manifest.json").read_text(encoding="utf-8"))
    _assert("modules/autonomy_policy_ru.py" in manifest.get("lazy_runtime", []), "Policy module missing from manifest.")
    _assert("modules/autonomous_run_state_ru.py" in manifest.get("lazy_runtime", []), "Run-state module missing from manifest.")
    _assert("tools/test_v683_autonomy_policy.py" in manifest.get("tests", []), "v6.83 test missing from manifest.")
    seen: set[str] = set()
    for key in ("entrypoints", "runtime", "lazy_runtime", "tests", "tools"):
        values = manifest.get(key, [])
        _assert(values == sorted(values, key=str.lower), f"Manifest list not sorted: {key}")
        _assert(len(values) == len(set(values)), f"Manifest list has duplicates: {key}")
        overlap = seen & set(values)
        _assert(not overlap, f"Manifest cross-category duplicate: {key}")
        seen.update(values)
    panel = importlib.import_module("LocalComet_Control_Panel")
    source = (ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    _assert(type(panel.LOCALCOMET_VERSION) is str and panel.LOCALCOMET_VERSION == "v6.82", "Panel version changed.")
    _assert(sum(isinstance(n, ast.FunctionDef) and n.name == "run_panel_chat_command" for n in ast.walk(tree)) == 1, "Dispatcher count changed.")
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _assert(staged.returncode == 0 and staged.stdout.strip() == "", "Staged files present.")


def main() -> None:
    tests = [
        test_import_side_effects,
        test_policy_defaults_and_validation,
        test_action_proposals_and_levels,
        test_path_safety_and_protection,
        test_kill_switches_and_budget,
        test_run_id_state_transitions_and_privacy,
        test_run_budget_and_policy_interaction,
        test_manifest_and_regression_invariants,
    ]
    for test in tests:
        start = time.perf_counter()
        test()
        print(f"PASS {test.__name__} {time.perf_counter() - start:.3f}s")
    print("ALL v6.83 AUTONOMY POLICY TESTS PASSED")


if __name__ == "__main__":
    main()
