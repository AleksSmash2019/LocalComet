#!/usr/bin/env python
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = ROOT / "tools" / "launch_localcomet_dev.py"

spec = importlib.util.spec_from_file_location("launch_localcomet_dev", LAUNCHER_PATH)
launcher = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["launch_localcomet_dev"] = launcher
spec.loader.exec_module(launcher)


CHECKS = 0


def check(condition: bool, message: str) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(message)


def expect_hold(callback, message: str) -> None:
    try:
        callback()
    except launcher.LauncherHold:
        check(True, message)
        return
    raise AssertionError(message)


def write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_source(root: Path) -> None:
    write(root / "desktop/localcomet-desktop/package.json", "{}\n")
    write(root / "desktop/localcomet-desktop/package-lock.json", '{"lockfileVersion": 3}\n')
    write(
        root / "desktop/localcomet-desktop/vite.config.ts",
        "import { defineConfig } from 'vite';\n"
        "export default defineConfig({\n"
        "  server: {\n"
        "    host: '127.0.0.1',\n"
        "    strictPort: true\n"
        "  }\n"
        "});\n",
    )
    write(root / "desktop/localcomet-desktop/src-tauri/Cargo.toml", "[package]\nname = 'x'\n")
    write(root / "tools/run_localcomet_desktop_sidecar.py", "print('sidecar')\n")
    write(root / "tools/helper.py", "print('helper')\n")
    write(root / "modules/desktop_sidecar_runtime_ru.py", "RUNTIME = True\n")
    write(root / "modules/desktop_ipc_contract_ru.py", "IPC = True\n")
    manifest = {
        "entrypoints": [],
        "runtime": [],
        "lazy_runtime": [
            "modules/desktop_ipc_contract_ru.py",
            "modules/desktop_sidecar_runtime_ru.py",
        ],
        "tests": [],
        "tools": ["tools/run_localcomet_desktop_sidecar.py"],
    }
    write(root / "localcomet_runtime_manifest.json", json.dumps(manifest, indent=2) + "\n")


def runtime_paths(temp: Path) -> object:
    return launcher.resolve_runtime_paths({"LOCALAPPDATA": str(temp / "LocalAppData")})


def test_source_validation() -> None:
    with tempfile.TemporaryDirectory(prefix="lc_dev_source_") as text:
        source = Path(text) / "source"
        make_source(source)
        launcher.validate_source_layout(source)
        check(True, "valid source layout passes validation")

        missing = Path(text) / "missing"
        make_source(missing)
        (missing / "desktop/localcomet-desktop/package.json").unlink()
        expect_hold(lambda: launcher.validate_source_layout(missing), "missing required source file fails")

        dirty_node = Path(text) / "dirty_node"
        make_source(dirty_node)
        (dirty_node / "desktop/localcomet-desktop/node_modules").mkdir()
        expect_hold(lambda: launcher.validate_source_layout(dirty_node), "source node_modules causes hold")

        dirty_target = Path(text) / "dirty_target"
        make_source(dirty_target)
        (dirty_target / "desktop/localcomet-desktop/src-tauri/target").mkdir(parents=True)
        expect_hold(lambda: launcher.validate_source_layout(dirty_target), "source target causes hold")


def test_runtime_paths() -> None:
    with tempfile.TemporaryDirectory(prefix="lc_dev_runtime_") as text:
        base = Path(text)
        paths = runtime_paths(base)
        check(paths.root == (base / "LocalAppData/LocalComet/DevRuntime").resolve(), "runtime root resolves under LOCALAPPDATA")
        expect_hold(
            lambda: launcher.require_within(base / "outside", paths.root, "escape test"),
            "runtime path cannot escape launcher-owned root",
        )


def test_synchronization() -> None:
    with tempfile.TemporaryDirectory(prefix="lc_dev_sync_") as text:
        base = Path(text)
        source = base / "source"
        make_source(source)
        excluded = [
            "node_modules",
            "target",
            ".svelte-kit",
            "build",
            "dist",
            "__pycache__",
        ]
        for name in excluded:
            write(source / "desktop/localcomet-desktop" / name / "ignored.txt", "ignored\n")
        write(source / "desktop/visible.txt", "one\n")
        paths = runtime_paths(base)
        state: dict[str, object] = {}
        summary, synced = launcher.synchronize_runtime(source, paths, state)
        check("desktop/visible.txt" in synced and (paths.workspace / "desktop/visible.txt").is_file(), "new synchronized files are copied")
        for name in excluded:
            check(
                not (paths.workspace / "desktop/localcomet-desktop" / name / "ignored.txt").exists(),
                f"sync excludes {name}",
            )

        state["synced_files"] = synced
        summary, synced = launcher.synchronize_runtime(source, paths, state)
        check(summary.reused > 0, "unchanged synchronized files are reused")

        write(source / "desktop/visible.txt", "two\n")
        state["synced_files"] = synced
        summary, synced = launcher.synchronize_runtime(source, paths, state)
        check(summary.updated == 1, "changed synchronized files are updated")

        state["synced_files"] = synced + ["desktop/stale.txt"]
        write(paths.workspace / "desktop/stale.txt", "old\n")
        summary, synced = launcher.synchronize_runtime(source, paths, state)
        check(summary.removed_stale == 1 and not (paths.workspace / "desktop/stale.txt").exists(), "stale synchronized file is removed safely")

        write(paths.workspace / "desktop/localcomet-desktop/node_modules/keep.txt", "keep\n")
        state["synced_files"] = synced
        launcher.synchronize_runtime(source, paths, state)
        check((paths.workspace / "desktop/localcomet-desktop/node_modules/keep.txt").is_file(), "external runtime node_modules is preserved")

        state["synced_files"] = synced
        first_summary, first_synced = launcher.synchronize_runtime(source, paths, state)
        state["synced_files"] = first_synced
        second_summary, second_synced = launcher.synchronize_runtime(source, paths, state)
        check(first_synced == second_synced and second_summary.reused == len(second_synced), "repeated launch state remains deterministic")


def test_dependency_state() -> None:
    with tempfile.TemporaryDirectory(prefix="lc_dev_deps_") as text:
        base = Path(text)
        node_modules = base / "node_modules"
        node_modules.mkdir()
        state = {"package_lock_sha256": "abc", "npm_ci_completed": True}
        check(launcher.dependency_action(state, "abc", node_modules) == "REUSED", "package-lock hash unchanged reuses dependencies")
        check(launcher.dependency_action(state, "def", node_modules) == "INSTALLED", "changed package-lock requires npm ci")

        state_path = base / "state.json"
        state_path.write_text("{not json", encoding="utf-8")
        parsed, malformed = launcher.read_state(state_path)
        check(parsed == {} and malformed, "malformed state.json is reset safely")

        original_run = subprocess.run
        original_resolve = launcher.resolve_npm_executable

        class Failed:
            returncode = 7

        def fake_run(*args, **kwargs):
            return Failed()

        try:
            subprocess.run = fake_run
            launcher.resolve_npm_executable = lambda: "npm"
            failed_state = {"package_lock_sha256": "old", "npm_ci_completed": True, "synced_files": []}
            expect_hold(
                lambda: launcher.run_npm_ci(base, state_path, failed_state, "new"),
                "failed npm ci raises hold",
            )
            saved, _ = launcher.read_state(state_path)
            check(saved.get("package_lock_sha256") == "old" and saved.get("npm_ci_completed") is False, "failed npm ci does not save successful hash")
        finally:
            subprocess.run = original_run
            launcher.resolve_npm_executable = original_resolve


def test_vite_patch() -> None:
    source = (
        "import { defineConfig } from 'vite';\n"
        "export default defineConfig({\n"
        "  server: {\n"
        "    host: '127.0.0.1',\n"
        "    strictPort: true\n"
        "  }\n"
        "});\n"
    )
    patched = launcher.patch_vite_config_text(source)
    check("watch:" in patched and launcher.VITE_WATCH_IGNORE in patched, "Vite watcher patch is applied")
    second = launcher.patch_vite_config_text(patched)
    check(second == patched, "Vite watcher patch is idempotent")
    check(second.count(launcher.VITE_WATCH_IGNORE) == 1, "Vite watcher exclusion is not duplicated")


def test_launch_safety_static_and_env() -> None:
    with tempfile.TemporaryDirectory(prefix="lc_dev_env_") as text:
        base = Path(text)
        source = base / "source"
        make_source(source)
        paths = runtime_paths(base)
        sentinel_name = "LOCALCOMET_LAUNCHER_COPY_TEST"
        previous_sentinel = os.environ.get(sentinel_name)
        os.environ[sentinel_name] = "preserved"
        env = launcher.build_launch_environment(source, paths)
        check(not launcher.is_relative_to(Path(env["CARGO_TARGET_DIR"]).resolve(), source.resolve()), "CARGO_TARGET_DIR is outside source")
        check(Path(env["LOCALCOMET_TEST_PROJECT_ROOT"]) == paths.workspace.resolve(), "child environment uses exact external runtime project root")
        check(Path(env["LOCALCOMET_TEST_PYTHON"]) == Path(sys.executable).resolve(), "child environment uses canonical sys.executable")
        check(env[sentinel_name] == "preserved", "existing environment is copied into child environment")
        check("LOCALCOMET_TEST_PROJECT_ROOT" not in os.environ and "LOCALCOMET_TEST_PYTHON" not in os.environ, "sidecar environment does not mutate global environment")
        if previous_sentinel is None:
            os.environ.pop(sentinel_name, None)
        else:
            os.environ[sentinel_name] = previous_sentinel

        malformed_state = paths.state
        malformed_state.parent.mkdir(parents=True, exist_ok=True)
        malformed_state.write_text('{"LOCALCOMET_TEST_PROJECT_ROOT":', encoding="utf-8")
        parsed, malformed = launcher.read_state(malformed_state)
        state_independent_env = launcher.build_launch_environment(source, paths)
        check(parsed == {} and malformed, "malformed state is rejected before environment construction")
        check(Path(state_independent_env["LOCALCOMET_TEST_PROJECT_ROOT"]) == paths.workspace.resolve(), "malformed state cannot supply sidecar project root")
        check(Path(state_independent_env["LOCALCOMET_TEST_PYTHON"]) == Path(sys.executable).resolve(), "malformed state cannot supply sidecar Python")

        escaped_paths = launcher.RuntimePaths(
            root=paths.root,
            workspace=base / "outside",
            cargo_target=paths.cargo_target,
            state=paths.state,
            logs=paths.logs,
        )
        expect_hold(
            lambda: launcher.build_launch_environment(source, escaped_paths),
            "sidecar project root cannot escape DevRuntime",
        )

        captured: dict[str, object] = {}
        original_popen = subprocess.Popen
        original_resolve = launcher.resolve_npm_executable

        class FakeProcess:
            pid = 12345

            def wait(self):
                return 0

            def poll(self):
                return 0

        def fake_popen(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return FakeProcess()

        try:
            subprocess.Popen = fake_popen
            launcher.resolve_npm_executable = lambda: "npm"
            code = launcher.launch_localcomet(source / "desktop/localcomet-desktop", env)
            check(code == 0 and captured["kwargs"].get("shell") is False, "subprocess launch uses shell=False")
            check(captured["kwargs"].get("env") is env, "validated child environment is passed to Tauri")
        finally:
            subprocess.Popen = original_popen
            launcher.resolve_npm_executable = original_resolve

    text = LAUNCHER_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("node.exe", "cargo.exe", "python.exe", "lm studio", "llama-server"):
        check(forbidden not in text, f"launcher does not target {forbidden}")
    check("taskkill" in text and "/pid" in text and "process.pid" in text, "Ctrl+C cleanup targets launcher-owned process tree only")
    check("source_path.unlink" not in text and "source_root.unlink" not in text, "source repository paths are never deleted")

    supervisor = (ROOT / "desktop/localcomet-desktop/src-tauri/src/supervisor.rs").read_text(encoding="utf-8")
    check('#[cfg(not(debug_assertions))]' in supervisor and 'localcomet-core.exe' in supervisor, "release-sidecar Rust behavior remains present")


def test_sidecar_layout_validation() -> None:
    with tempfile.TemporaryDirectory(prefix="lc_dev_sidecar_layout_") as text:
        base = Path(text)
        source = base / "source"
        make_source(source)
        launcher.validate_sidecar_layout(source)
        check(True, "complete sidecar layout passes validation")

        required_cases = (
            "tools/run_localcomet_desktop_sidecar.py",
            "modules/desktop_sidecar_runtime_ru.py",
            "modules/desktop_ipc_contract_ru.py",
            "localcomet_runtime_manifest.json",
        )
        for relative in required_cases:
            case = base / ("missing_" + Path(relative).stem)
            make_source(case)
            (case / relative).unlink()
            expect_hold(
                lambda case=case: launcher.validate_sidecar_layout(case),
                f"missing {relative} fails before GUI launch",
            )

        manifest_missing = base / "missing_manifest_declared"
        make_source(manifest_missing)
        manifest = json.loads((manifest_missing / "localcomet_runtime_manifest.json").read_text(encoding="utf-8"))
        manifest["runtime"] = ["core/required.py"]
        write(manifest_missing / "localcomet_runtime_manifest.json", json.dumps(manifest) + "\n")
        expect_hold(
            lambda: launcher.validate_sidecar_layout(manifest_missing),
            "missing manifest-declared required runtime file fails before GUI launch",
        )


def test_manifest_declared_files_are_synchronized() -> None:
    with tempfile.TemporaryDirectory(prefix="lc_dev_manifest_sync_") as text:
        base = Path(text)
        source = base / "source"
        make_source(source)
        write(source / "core/required.py", "REQUIRED = True\n")
        manifest = json.loads((source / "localcomet_runtime_manifest.json").read_text(encoding="utf-8"))
        manifest["runtime"] = ["core/required.py"]
        write(source / "localcomet_runtime_manifest.json", json.dumps(manifest) + "\n")
        paths = runtime_paths(base)
        launcher.synchronize_runtime(source, paths, {})
        check((paths.workspace / "core/required.py").is_file(), "manifest-declared runtime file is synchronized")
        launcher.validate_sidecar_layout(paths.workspace)
        check(True, "synchronized manifest contract validates")


def main() -> None:
    test_source_validation()
    test_runtime_paths()
    test_synchronization()
    test_dependency_state()
    test_vite_patch()
    test_launch_safety_static_and_env()
    test_sidecar_layout_validation()
    test_manifest_declared_files_are_synchronized()
    check(CHECKS >= 50, "at least fifty focused checks executed")
    print(f"ALL v6.84.5.1d1 DEV LAUNCHER TESTS PASSED ({CHECKS} checks)")


if __name__ == "__main__":
    main()
