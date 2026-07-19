#!/usr/bin/env python
from __future__ import annotations

import ast
import importlib
import json
import math
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _raises(fn, message: str) -> None:
    try:
        fn()
    except Exception:
        return
    raise AssertionError(message)


def _paths_under(root: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    if not root.exists():
        return result
    for path in root.rglob("*"):
        if "__pycache__" in path.parts or ".git" in path.parts:
            continue
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path.stat().st_size
    return result


def _import_executor():
    sys.modules.pop("modules.autonomous_action_executor_ru", None)
    return importlib.import_module("modules.autonomous_action_executor_ru")


def _policy(level: str = "LEVEL_2_SAFE_AUTOMATION", root: Path | None = None, actions: tuple[str, ...] = ("analyze", "inspect", "verify")):
    policy_mod = importlib.import_module("modules.autonomy_policy_ru")
    root = root or ROOT
    return replace(policy_mod.default_autonomy_policy(root), level=getattr(policy_mod.AutonomyLevel, level), allowed_actions=actions)


def _proposal(action_type: str, target: str, **updates: Any):
    policy_mod = importlib.import_module("modules.autonomy_policy_ru")
    data = {
        "action_id": "action_01",
        "action_type": action_type,
        "target": target,
        "arguments": {},
        "read_only": action_type in {"inspect", "analyze", "verify", "test"},
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
    return policy_mod.ActionProposal(**data)


def _action(action_type: str, operation: str, target: str, params: dict[str, Any] | None = None, **updates: Any):
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    return executor.ExecutableAction(_proposal(action_type, target, **updates), operation, params or {})


def _grant(action: Any, config: Any):
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    return executor.ApprovalGrant(action.proposal.action_id, executor.compute_action_fingerprint(action, config), True)


def _result(policy: Any, action: Any, config: Any, approval: Any | None = None, usage: Any | None = None, kill: Any | None = None):
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    res = executor.execute_action(policy, action, config=config, approval=approval, usage=usage, kill_switch=kill, now=lambda: "2026-07-13T12:00:00Z", monotonic=lambda: 10.0)
    return executor.serialize_action_result(res)


def _fixture_root() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="lc_v684_exec_")


def _write_manifest(root: Path, tests: list[str] | None = None) -> None:
    payload = {
        "release": "fixture",
        "project": "fixture",
        "entrypoints": [],
        "runtime": [],
        "lazy_runtime": [],
        "tests": sorted(tests or []),
        "tools": [],
    }
    (root / "localcomet_runtime_manifest.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_import_side_effects() -> None:
    before = _paths_under(ROOT)
    env_before = dict(os.environ)
    threads_before = {t.ident for t in threading.enumerate()}
    calls: list[str] = []
    originals = (subprocess.Popen, socket.socket, urllib.request.urlopen)

    def forbidden(name: str):
        def inner(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            raise AssertionError("external effect")

        return inner

    try:
        subprocess.Popen = forbidden("popen")
        socket.socket = forbidden("socket")
        urllib.request.urlopen = forbidden("urlopen")
        executor = _import_executor()
    finally:
        subprocess.Popen, socket.socket, urllib.request.urlopen = originals
    after = _paths_under(ROOT)
    _assert(executor.AUTONOMOUS_ACTION_EXECUTOR_VERSION == "v6.84", "Executor version changed.")
    _assert(before == after, "Executor import created or modified files.")
    _assert(calls == [], "Executor import used subprocess or network.")
    _assert(env_before == dict(os.environ), "Executor import mutated environment.")
    _assert({t.ident for t in threading.enumerate()} == threads_before, "Executor import started a thread.")


def test_configuration_and_validation() -> None:
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    with _fixture_root() as temp_text:
        root = Path(temp_text)
        (root / "tools").mkdir()
        cfg = executor.default_executor_config(root)
        payload = executor.serialize_executor_config(cfg)
        _assert(payload["root"] == "<PROJECT_ROOT>", "Root was not redacted.")
        _assert(str(root) not in json.dumps(payload), "Full root leaked.")
        _assert(cfg.allow_test_execution is False and cfg.allow_project_writes is False and cfg.allow_temp_writes is False, "Default config is not read-only.")
        cfg2 = executor.ExecutorConfig(root=root, write_allowlist=("b.py", "a.py", "a.py"), test_allowlist=("tools/test_b.py", "tools/test_a.py"))
        _assert(cfg2.write_allowlist == ("a.py", "b.py"), "Write allowlist not sorted unique.")
        _assert(cfg2.test_allowlist == ("tools/test_a.py", "tools/test_b.py"), "Test allowlist not sorted unique.")
        absolute_allowlist = "C:" + "\\x.py"
        _raises(lambda: executor.ExecutorConfig(root=root, write_allowlist=(absolute_allowlist,)), "Absolute allowlist accepted.")
        _raises(lambda: executor.ExecutorConfig(root=root, write_allowlist=("../x.py",)), "Traversal allowlist accepted.")
        _raises(lambda: executor.ExecutorConfig(root=root, write_allowlist=(".git/config",)), "Protected allowlist accepted.")
        _raises(lambda: executor.ExecutorConfig(root=root, max_read_bytes=True), "Boolean limit accepted.")
        _raises(lambda: executor.ExecutorConfig(root=root, max_write_bytes=-1), "Negative limit accepted.")
        _raises(lambda: executor.ExecutorConfig(root=root, max_timeout_seconds=math.inf), "Non-finite limit accepted.")
        _raises(lambda: executor.ExecutorConfig(root=root, max_write_bytes=11 * 1024 * 1024), "Hard limit not enforced.")
        _raises(lambda: executor.executor_config_from_dict({"root": root, "extra": 1}), "Unknown configuration key accepted.")


def test_action_mapping_fingerprint_and_approval() -> None:
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    with _fixture_root() as temp_text:
        root = Path(temp_text)
        (root / "a.txt").write_text("hello", encoding="utf-8")
        cfg = executor.default_executor_config(root)
        policy = _policy(root=root)
        supported = {
            "read_file": ("inspect", "a.txt", {}),
            "list_directory": ("inspect", ".", {"include_hidden": True}),
            "search_text": ("analyze", ".", {"query": "hello"}),
            "syntax_check": ("verify", "a.py", {}),
            "run_allowlisted_test": ("test", "tools/test_ok.py", {"timeout_seconds": 1}),
            "create_temp_file": ("create_temp", "tmp/new.txt", {"content": "x"}),
            "write_allowlisted_file": ("edit_file", "a.txt", {"content": "x"}),
            "apply_exact_patch": ("apply_patch", "a.txt", {"old_text": "hello", "new_text": "hi"}),
        }
        for op, (kind, target, params) in supported.items():
            action = _action(kind, op, target, params)
            if op == "syntax_check":
                (root / "a.py").write_text("x=1\n", encoding="utf-8")
            denied = _result(_policy("LEVEL_1_PLAN_ONLY", root=root), action, cfg)
            _assert(denied["status"] == "DENIED", "LEVEL_1 executed an operation.")
        unknown = _result(policy, _action("inspect", "shell", "a.txt"), cfg)
        _assert(unknown["error_category"] == "unsupported_operation" and unknown["executed"] is False, "Unknown operation was not denied.")
        mismatch = _result(policy, _action("inspect", "search_text", "a.txt", {"query": "hello"}), cfg)
        _assert(mismatch["error_category"] == "invalid_action", "Mapping mismatch was not denied.")
        for params in ({"extra": 1}, {"query": [[[[[[1]]]]]]}, {"query": "x" * 5000}, {"query": float("nan")}, {"query": Path("x")}, {"query": lambda: None}):
            data = _result(policy, _action("analyze", "search_text", ".", params), cfg)
            _assert(data["error_category"] == "unsupported_parameters", "Unsafe parameters were not denied.")
        net = _result(policy, _action("inspect", "read_file", "a.txt", requires_network=True), cfg)
        elev = _result(policy, _action("inspect", "read_file", "a.txt", requires_elevation=True), cfg)
        _assert(net["error_category"] == "invalid_action" and elev["error_category"] == "invalid_action", "Network/elevation proposal accepted.")
        a1 = _action("inspect", "read_file", "a.txt", {"z": 1, "a": 2})
        a2 = _action("inspect", "read_file", "a.txt", {"a": 2, "z": 1})
        fp = executor.compute_action_fingerprint(a1, cfg)
        _assert(fp == executor.compute_action_fingerprint(a2, cfg) and len(fp) == 64, "Fingerprint is not canonical.")
        _assert(fp != executor.compute_action_fingerprint(_action("inspect", "read_file", "b.txt"), cfg), "Target change did not affect fingerprint.")
        _assert(fp != executor.compute_action_fingerprint(_action("inspect", "list_directory", "."), cfg), "Operation change did not affect fingerprint.")
        changed_id = replace(a1, proposal=replace(a1.proposal, action_id="action_02"))
        _assert(fp != executor.compute_action_fingerprint(changed_id, cfg), "Action ID change did not affect fingerprint.")
        grant = _grant(a1, cfg)
        _assert(executor.validate_approval_grant(a1, cfg, grant)["valid"] is True, "Exact approval did not validate.")
        _assert(executor.validate_approval_grant(a1, cfg, None)["valid"] is False, "Missing approval validated.")
        _assert(executor.validate_approval_grant(a1, cfg, replace(grant, action_id="other"))["valid"] is False, "Wrong action approval validated.")
        _assert(executor.validate_approval_grant(a1, cfg, replace(grant, action_fingerprint="f" * 64))["valid"] is False, "Wrong fingerprint validated.")
        _assert(executor.validate_approval_grant(a1, cfg, replace(grant, granted=False))["valid"] is False, "Revoked approval validated.")
        _assert(executor.validate_approval_grant(a1, cfg, replace(grant, scope="GLOBAL"))["valid"] is False, "Invalid approval scope validated.")


def test_path_policy_and_kill_switches() -> None:
    policy_mod = importlib.import_module("modules.autonomy_policy_ru")
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    with _fixture_root() as temp_text, _fixture_root() as external_text:
        root = Path(temp_text)
        external = Path(external_text)
        (root / "safe.txt").write_text("ok", encoding="utf-8")
        cfg = executor.default_executor_config(root)
        policy = _policy(root=root)
        good = _result(policy, _action("inspect", "read_file", "safe.txt"), cfg)
        _assert(good["status"] == "SUCCESS" and good["target"] == "<PROJECT_ROOT>/safe.txt", "Safe read failed.")
        bads = ("../x", "..\\x", "C:" + "\\Windows\\x", "C:" + "Windows\\x", "\\\\server\\share", "/etc/passwd", "bad\x00path", "CON")
        for bad in bads:
            data = _result(policy, _action("inspect", "read_file", bad), cfg)
            _assert(data["status"] == "DENIED" and data["executed"] is False, "Unsafe path was not denied.")
        for protected in (".git/config", ".incident_backup/x", ".localcomet/reviewer/x", ".localcomet/policies/x", ".localcomet/autonomy/STOP"):
            data = _result(policy, _action("inspect", "read_file", protected), cfg)
            _assert(data["error_category"] in {"protected_path", "unsafe_path"}, "Protected path was not denied.")
        link = root / "link_out"
        try:
            link.symlink_to(external, target_is_directory=True)
            data = _result(policy, _action("inspect", "read_file", "link_out/file.txt"), cfg)
            _assert(data["status"] == "DENIED", "Symlink escape was not denied.")
            parent = root / "parent_link"
            parent.symlink_to(external, target_is_directory=True)
            _raises(lambda: executor.ExecutorConfig(root=root, write_allowlist=("parent_link/new.txt",), allow_project_writes=True), "Symlink parent allowlist accepted.")
        except OSError:
            print("SKIP symlink path tests: platform refused test symlink")
        kill = policy_mod.KillSwitchStatus(True, policy_mod.KillSwitchMode.DISABLE, "disabled")
        data = _result(policy, _action("inspect", "read_file", "safe.txt"), cfg, kill=kill)
        _assert(data["error_category"] == "kill_switch_active" and data["executed"] is False, "Kill switch did not deny read.")
        for mode in (policy_mod.KillSwitchMode.STOP_FILE, policy_mod.KillSwitchMode.PAUSE):
            data = _result(policy, _action("inspect", "read_file", "safe.txt"), cfg, kill=policy_mod.KillSwitchStatus(True, mode, "active"))
            _assert(data["error_category"] == "kill_switch_active", "Kill switch mode did not deny.")


def test_read_list_search_and_syntax() -> None:
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    with _fixture_root() as temp_text:
        root = Path(temp_text)
        (root / "dir").mkdir()
        secret = "sk" + "-" + "A" * 16
        (root / "dir" / "a.txt").write_text("Alpha\nneedle " + secret + "\n", encoding="utf-8")
        (root / "dir" / ".hidden").write_text("hide", encoding="utf-8")
        (root / "dir" / "b.bin").write_bytes(b"a\x00b")
        (root / "ok.py").write_text("x = 1\n", encoding="utf-8")
        (root / "bad.py").write_text("x =\n", encoding="utf-8")
        cfg = executor.ExecutorConfig(root=root, max_directory_entries=10, max_search_matches=10)
        policy = _policy(root=root)
        read = _result(policy, _action("inspect", "read_file", "dir/a.txt"), cfg)
        _assert(read["status"] == "SUCCESS" and read["original_sha256"], "Read did not succeed.")
        _assert(secret not in json.dumps(read) and "<REDACTED_SECRET>" in json.dumps(read), "Read secret was not redacted.")
        missing = _result(policy, _action("inspect", "read_file", "missing.txt"), cfg)
        oversized = _result(policy, _action("inspect", "read_file", "dir/a.txt"), executor.ExecutorConfig(root=root, max_read_bytes=2))
        binary = _result(policy, _action("inspect", "read_file", "dir/b.bin"), cfg)
        protected = _result(policy, _action("inspect", "read_file", ".git/config"), cfg)
        _assert(missing["error_category"] == "target_missing" and oversized["error_category"] == "size_limit" and binary["error_category"] == "binary_file" and protected["status"] == "DENIED", "Read failure categories changed.")
        listing = _result(policy, _action("inspect", "list_directory", "dir", {"include_hidden": False}), cfg)
        names = [entry["name"] for entry in listing["details"]["entries"]]
        _assert(names == sorted(names, key=str.lower) and ".hidden" not in names, "Directory listing not sorted or hidden filtering failed.")
        limit_listing = _result(policy, _action("inspect", "list_directory", "dir"), executor.ExecutorConfig(root=root, max_directory_entries=1))
        _assert(limit_listing["error_category"] == "size_limit", "Directory entry limit not enforced.")
        search = _result(policy, _action("analyze", "search_text", "dir", {"query": "NEEDLE", "case_sensitive": False}), cfg)
        _assert(search["details"]["matches"] and secret not in json.dumps(search), "Search did not redact match.")
        case = _result(policy, _action("analyze", "search_text", "dir", {"query": "NEEDLE", "case_sensitive": True}), cfg)
        literal = _result(policy, _action("analyze", "search_text", "dir", {"query": "needle.*"}), cfg)
        empty = _result(policy, _action("analyze", "search_text", "dir", {"query": ""}), cfg)
        _assert(case["details"]["matches"] == [] and literal["details"]["matches"] == [] and empty["status"] == "DENIED", "Search literal/case/empty behavior changed.")
        syntax_ok = _result(policy, _action("verify", "syntax_check", "ok.py"), cfg)
        syntax_bad = _result(policy, _action("verify", "syntax_check", "bad.py"), cfg)
        non_py = _result(policy, _action("verify", "syntax_check", "dir/a.txt"), cfg)
        _assert(syntax_ok["details"]["syntax_ok"] is True, "Valid syntax failed.")
        _assert(syntax_bad["details"]["syntax_ok"] is False and syntax_bad["details"]["filename"] == "<PROJECT_ROOT>/bad.py", "Invalid syntax details changed.")
        _assert(non_py["status"] == "DENIED" and not (root / "__pycache__").exists(), "Syntax check accepted non-Python or created pycache.")


def test_allowlisted_test_execution() -> None:
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    with _fixture_root() as temp_text:
        root = Path(temp_text)
        tools = root / "tools"
        tools.mkdir()
        (tools / "test_ok.py").write_text("print('ok')\n", encoding="utf-8")
        (tools / "test_fail.py").write_text("import sys\nprint('bad')\nsys.exit(3)\n", encoding="utf-8")
        (tools / "test_timeout.py").write_text("import time\ntime.sleep(2)\n", encoding="utf-8")
        (tools / "test_output.py").write_text("print('X' * 5000)\n", encoding="utf-8")
        secret = "ghp" + "_" + "B" * 16
        (tools / "test_secret.py").write_text("print('" + secret + "')\n", encoding="utf-8")
        _write_manifest(root, ["tools/test_ok.py", "tools/test_fail.py", "tools/test_timeout.py", "tools/test_output.py", "tools/test_secret.py"])
        policy = _policy("LEVEL_2_SAFE_AUTOMATION", root=root, actions=("analyze", "inspect", "test", "verify"))
        default = executor.default_executor_config(root)
        action = _action("test", "run_allowlisted_test", "tools/test_ok.py", {"timeout_seconds": 1}, estimated_subprocesses=1, estimated_output_bytes=20)
        _assert(_result(policy, action, default)["status"] == "DENIED", "Default config launched test.")
        cfg = executor.ExecutorConfig(root=root, test_allowlist=("tools/test_ok.py", "tools/test_fail.py", "tools/test_timeout.py", "tools/test_output.py", "tools/test_secret.py"), allow_test_execution=True, max_subprocess_output_bytes=1000)
        _assert(_result(policy, action, cfg, approval=_grant(action, cfg))["status"] == "SUCCESS", "Allowlisted test failed.")
        fail = _action("test", "run_allowlisted_test", "tools/test_fail.py", {"timeout_seconds": 1}, estimated_subprocesses=1, estimated_output_bytes=20)
        timeout = _action("test", "run_allowlisted_test", "tools/test_timeout.py", {"timeout_seconds": 0.1}, estimated_subprocesses=1, estimated_output_bytes=20)
        output = _action("test", "run_allowlisted_test", "tools/test_output.py", {"timeout_seconds": 1}, estimated_subprocesses=1, estimated_output_bytes=20)
        secret_action = _action("test", "run_allowlisted_test", "tools/test_secret.py", {"timeout_seconds": 1}, estimated_subprocesses=1, estimated_output_bytes=20)
        _assert(_result(policy, fail, cfg, approval=_grant(fail, cfg))["error_category"] == "subprocess_failed", "Failing test category changed.")
        _assert(_result(policy, timeout, cfg, approval=_grant(timeout, cfg))["status"] == "TIMEOUT", "Timeout did not terminate.")
        tiny = replace(cfg, max_subprocess_output_bytes=50)
        _assert(_result(policy, output, tiny, approval=_grant(output, tiny))["error_category"] == "output_limit", "Output limit not enforced.")
        redacted = _result(policy, secret_action, cfg, approval=_grant(secret_action, cfg))
        _assert(secret not in json.dumps(redacted), "Subprocess output leaked a secret fixture.")
        denied_action = _action("test", "run_allowlisted_test", "tools/not_manifest.py", {"timeout_seconds": 1}, estimated_subprocesses=1)
        denied = _result(policy, denied_action, cfg, approval=_grant(denied_action, cfg))
        _assert(denied["executed"] is False and denied["error_category"] == "test_not_allowlisted", "Non-manifest test was not denied.")


def test_writes_patches_hashes_and_rollback() -> None:
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    with _fixture_root() as temp_text:
        root = Path(temp_text)
        (root / "tmp").mkdir()
        (root / "src").mkdir()
        existing = root / "src" / "file.txt"
        existing.write_text("old text\n", encoding="utf-8")
        before_hash = executor._sha256_file(existing)
        cfg = executor.ExecutorConfig(root=root, temporary_roots=(root / "tmp",), write_allowlist=("src/file.txt", "src/new.txt"), allow_project_writes=True, allow_temp_writes=True)
        policy = _policy("LEVEL_3_CONTROLLED_EDIT", root=root, actions=("analyze", "apply_patch", "create_file", "create_temp", "edit_file", "inspect", "test", "verify"))
        temp_action = _action("create_temp", "create_temp_file", "tmp/t.txt", {"content": "temp"}, read_only=False, estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, temp_action, cfg, approval=_grant(temp_action, cfg))["status"] == "SUCCESS", "Temp creation failed.")
        blocked_secret = _action("create_temp", "create_temp_file", "tmp/s.txt", {"content": "token=" + "C" * 16}, read_only=False, estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, blocked_secret, cfg, approval=_grant(blocked_secret, cfg))["error_category"] == "secret_content", "Secret temp content was not blocked.")
        new_action = _action("create_file", "write_allowlisted_file", "src/new.txt", {"content": "new\n"}, read_only=False, expected_original_sha256="0" * 64, estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, new_action, cfg, approval=_grant(new_action, cfg))["status"] == "SUCCESS", "New allowlisted file failed.")
        wrong = _action("edit_file", "write_allowlisted_file", "src/file.txt", {"content": "bad\n"}, read_only=False, expected_original_sha256="b" * 64, estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, wrong, cfg, approval=_grant(wrong, cfg))["error_category"] == "hash_mismatch", "Wrong hash did not block.")
        _assert(existing.read_text(encoding="utf-8") == "old text\n", "Wrong-hash write changed bytes.")
        edit = _action("edit_file", "write_allowlisted_file", "src/file.txt", {"content": "new text\n"}, read_only=False, expected_original_sha256=before_hash, estimated_changed_files=1, estimated_changed_lines=1)
        edited = _result(policy, edit, cfg, approval=_grant(edit, cfg))
        _assert(edited["status"] == "SUCCESS" and edited["result_sha256"] == executor._sha256_file(existing), "Correct-hash edit failed.")
        _assert(not list((root / "src").glob("*.localcomet-v684-*.tmp")), "Staging artifact remained.")
        patch_hash = executor._sha256_file(existing)
        patch = _action("apply_patch", "apply_exact_patch", "src/file.txt", {"old_text": "new", "new_text": "patched"}, read_only=False, expected_original_sha256=patch_hash, estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, patch, cfg, approval=_grant(patch, cfg))["status"] == "SUCCESS", "Exact patch failed.")
        missing = _action("apply_patch", "apply_exact_patch", "src/file.txt", {"old_text": "absent", "new_text": "x"}, read_only=False, expected_original_sha256=executor._sha256_file(existing), estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, missing, cfg, approval=_grant(missing, cfg))["error_category"] == "patch_not_found", "Missing patch text category changed.")
        dup_file = root / "src" / "dup.txt"
        dup_file.write_text("x x", encoding="utf-8")
        dup_cfg = replace(cfg, write_allowlist=("src/dup.txt",))
        dup = _action("apply_patch", "apply_exact_patch", "src/dup.txt", {"old_text": "x", "new_text": "y"}, read_only=False, expected_original_sha256=executor._sha256_file(dup_file), estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, dup, dup_cfg, approval=_grant(dup, dup_cfg))["error_category"] == "patch_not_unique", "Duplicate patch text category changed.")
        original_sha_func = executor._sha256_file
        rollback_target = root / "src" / "file.txt"
        rollback_hash = original_sha_func(rollback_target)
        rollback_action = _action("edit_file", "write_allowlisted_file", "src/file.txt", {"content": "rollback probe\n"}, read_only=False, expected_original_sha256=rollback_hash, estimated_changed_files=1, estimated_changed_lines=1)
        try:
            def fake_sha(path: Path) -> str:
                return "f" * 64

            executor._sha256_file = fake_sha
            rolled = _result(policy, rollback_action, cfg, approval=_grant(rollback_action, cfg))
        finally:
            executor._sha256_file = original_sha_func
        _assert(rolled["status"] == "ROLLED_BACK" and rollback_target.read_text(encoding="utf-8") != "rollback probe\n", "Rollback did not restore pre-state.")
        kill = importlib.import_module("modules.autonomy_policy_ru").KillSwitchStatus(True, "DISABLE", "disabled")
        blocked = _action("edit_file", "write_allowlisted_file", "src/file.txt", {"content": "blocked\n"}, read_only=False, expected_original_sha256=original_sha_func(existing), estimated_changed_files=1, estimated_changed_lines=1)
        before = existing.read_bytes()
        _assert(_result(policy, blocked, cfg, approval=_grant(blocked, cfg), kill=kill)["executed"] is False and existing.read_bytes() == before, "Kill switch allowed a write.")


def test_result_budget_manifest_and_regression_invariants() -> None:
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    policy_mod = importlib.import_module("modules.autonomy_policy_ru")
    with _fixture_root() as temp_text:
        root = Path(temp_text)
        (root / "a.txt").write_text("x", encoding="utf-8")
        cfg = executor.default_executor_config(root)
        policy = _policy(root=root)
        action = _action("inspect", "read_file", "a.txt")
        data = _result(policy, action, cfg, usage=policy_mod.BudgetUsage(actions_used=policy.budgets.max_actions))
        _assert(data["status"] == "DENIED" and data["executed"] is False and data["error_category"] == "budget_exceeded", "Budget overflow did not deny before execution.")
        schema = list(_result(policy, action, cfg).keys())
        expected = ["mode", "version", "action_id", "action_type", "operation", "status", "ok", "executed", "target", "action_fingerprint", "approval", "policy", "timing", "bytes_read", "bytes_written", "original_sha256", "result_sha256", "stdout", "stderr", "output_truncated", "rollback_performed", "error_category", "details", "warnings"]
        _assert(schema == expected, "Action result schema changed.")
        _assert(_result(policy, action, cfg)["ok"] is True, "SUCCESS did not set ok=true.")
    manifest = json.loads((ROOT / "localcomet_runtime_manifest.json").read_text(encoding="utf-8"))
    if "modules/autonomous_action_executor_ru.py" in manifest.get("lazy_runtime", []) or "tools/test_v684_action_executor.py" in manifest.get("tests", []):
        _assert("modules/autonomous_action_executor_ru.py" in manifest.get("lazy_runtime", []), "Executor module missing from manifest.")
        _assert("tools/test_v684_action_executor.py" in manifest.get("tests", []), "v6.84 test missing from manifest.")
    seen: set[str] = set()
    for key in ("entrypoints", "runtime", "lazy_runtime", "tests", "tools"):
        values = manifest.get(key, [])
        _assert(values == sorted(values, key=str.lower), f"Manifest list not sorted: {key}")
        _assert(len(values) == len(set(values)), f"Manifest duplicates: {key}")
        _assert(not (seen & set(values)), f"Manifest cross-category duplicate: {key}")
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
        test_configuration_and_validation,
        test_action_mapping_fingerprint_and_approval,
        test_path_policy_and_kill_switches,
        test_read_list_search_and_syntax,
        test_allowlisted_test_execution,
        test_writes_patches_hashes_and_rollback,
        test_result_budget_manifest_and_regression_invariants,
    ]
    for test in tests:
        start = time.perf_counter()
        test()
        print(f"PASS {test.__name__} {time.perf_counter() - start:.3f}s")
    print("ALL v6.84 ACTION EXECUTOR TESTS PASSED")


if __name__ == "__main__":
    main()
