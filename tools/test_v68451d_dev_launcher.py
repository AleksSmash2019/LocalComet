#!/usr/bin/env python
from __future__ import annotations

import importlib.util
import json
import os
import shutil
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


def make_resource_stage(root: Path, legacy_manifest: str = "{}\n") -> tuple[str, ...]:
    binaries = root / "desktop/localcomet-desktop/src-tauri/binaries"
    rows = [launcher.RUNTIME_IDENTITY_HEADER]
    relative_paths: list[str] = []
    for index in range(launcher.EXPECTED_TAURI_RESOURCE_IDENTITIES):
        relative = f"payload/resource-{index:02d}.bin"
        content = f"resource-{index:02d}\n".encode("ascii")
        target = binaries.joinpath(*Path(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        rows.append(
            f"{relative}\t{len(content)}\t{launcher.hashlib.sha256(content).hexdigest()}\n"
        )
        relative_paths.append(relative)
    identity_path = binaries / "runtime-manifest.tsv"
    identity_path.write_bytes("".join(rows).encode("utf-8"))
    legacy_path = root / launcher.LEGACY_RUNTIME_MANIFEST_RELATIVE
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_bytes(legacy_manifest.encode("utf-8"))
    return tuple(relative_paths)


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
    write(
        root / "desktop/localcomet-desktop/src-tauri/tauri.conf.json",
        json.dumps({"build": {"devUrl": "http://127.0.0.1:1420"}}) + "\n",
    )
    write(
        root / "desktop/localcomet-desktop/src-tauri/up00-runtime-manifest.json",
        json.dumps(
            {
                "schemaVersion": 1,
                "workPackage": "UP00-WP01",
                "targetTriple": "x86_64-pc-windows-msvc",
                "sidecarBaseName": "localcomet-core",
                "entrypoint": "tools/run_localcomet_desktop_sidecar.py",
                "python": {
                    "implementation": "CPython",
                    "major": 3,
                    "minor": 14,
                    "licenseFile": "LICENSE.txt",
                    "excludedTopLevel": [],
                },
                "sourceFiles": [
                    "modules/desktop_ipc_contract_ru.py",
                    "modules/desktop_sidecar_runtime_ru.py",
                    "tools/run_localcomet_desktop_sidecar.py",
                ],
            },
            indent=2,
        )
        + "\n",
    )
    write(root / "tools/build_up00_windows_installer.py", "STAGING = True\n")
    write(root / "third_party/llama.cpp/LICENSE-MIT.txt", "MIT\n")
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
        launcher.validate_source_layout(dirty_node)
        check(True, "source node_modules does not block clean-room launch")

        dirty_target = Path(text) / "dirty_target"
        make_source(dirty_target)
        (dirty_target / "desktop/localcomet-desktop/src-tauri/target").mkdir(parents=True)
        launcher.validate_source_layout(dirty_target)
        check(True, "source target does not block external Cargo launch")


def test_runtime_paths() -> None:
    with tempfile.TemporaryDirectory(prefix="lc_dev_runtime_") as text:
        base = Path(text)
        paths = runtime_paths(base)
        check(paths.root == (base / "LocalAppData/LocalCometDev").resolve(), "runtime root resolves under LOCALAPPDATA")
        check(paths.cargo_target == (paths.root / "cargo-target").resolve(), "Cargo target uses the required external path")
        check(paths.app_data == (paths.root / "app-data").resolve(), "development AppData is isolated")
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
            "binaries",
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
        check(Path(env["LOCALCOMET_APP_DATA_ROOT"]) == paths.app_data.resolve(), "child environment uses isolated development AppData")
        check("LOCALCOMET_KNOWLEDGE_VAULT" not in env, "child environment grants no Vault authority")
        check("LOCALCOMET_KNOWLEDGE_PROJECT_ROOT" not in env, "child environment grants no project knowledge authority")
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
            app_data=paths.app_data,
            resource_cache=paths.resource_cache,
            state=paths.state,
            logs=paths.logs,
        )
        expect_hold(
            lambda: launcher.build_launch_environment(source, escaped_paths),
            "sidecar project root cannot escape LocalCometDev",
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

        if os.name == "nt":
            graceful: dict[str, object] = {}

            class GracefulProcess:
                pid = 54321

                def poll(self):
                    return None

                def send_signal(self, value):
                    graceful["signal"] = value

                def wait(self, timeout=None):
                    graceful["timeout"] = timeout
                    return 0

            launcher.terminate_launcher_process_tree(GracefulProcess())
            check(
                graceful == {"signal": launcher.signal.CTRL_BREAK_EVENT, "timeout": 10},
                "Ctrl+C requests bounded graceful process-group shutdown first",
            )

    text = LAUNCHER_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("node.exe", "cargo.exe", "lm studio", "llama-server"):
        check(forbidden not in text, f"launcher does not target {forbidden}")
    check("taskkill" in text and "/pid" in text and "process.pid" in text, "Ctrl+C cleanup targets launcher-owned process tree only")
    check("ctrl_break_event" in text, "Ctrl+C first requests graceful process-group shutdown")
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


def test_tauri_resources_are_synchronized_from_external_stage() -> None:
    with tempfile.TemporaryDirectory(prefix="lc_dev_resource_sync_") as text:
        base = Path(text)
        source = base / "source"
        make_source(source)
        paths = runtime_paths(base)
        launcher.synchronize_runtime(source, paths, {})

        staged = paths.resource_cache / ("a" * 64)
        make_resource_stage(
            staged,
            (source / "localcomet_runtime_manifest.json").read_text(encoding="utf-8"),
        )
        identity = launcher.trusted_resource_stage_identity(staged)
        check(identity.runtime_resource_count == 52, "trusted stage has exactly 52 identities")
        binary_relative = "desktop/localcomet-desktop/src-tauri/binaries/runtime-manifest.tsv"
        summary, resources = launcher.synchronize_tauri_resources(staged, paths, {}, identity)
        check(summary.copied == 54, "all generated manifests and Tauri resources are copied")
        check(len(resources) == 54, "the exact trusted staged file set is synchronized")
        check(
            (paths.workspace / binary_relative).is_file(),
            "Tauri resource is present only in the external workspace",
        )
        launcher.validate_sidecar_layout(paths.workspace)
        check(True, "staged sidecar manifest contract validates")

        stale_relative = "desktop/localcomet-desktop/src-tauri/binaries/stale.dll"
        write(paths.workspace / stale_relative, "stale\n")
        state = {"runtime_resource_files": resources + [stale_relative]}
        summary, _ = launcher.synchronize_tauri_resources(staged, paths, state, identity)
        check(
            summary.removed_stale == 1 and not (paths.workspace / stale_relative).exists(),
            "only launcher-owned stale resources are removed",
        )


def test_tauri_resource_cache_identity_validation() -> None:
    with tempfile.TemporaryDirectory(prefix="lc_dev_resource_identity_") as text:
        base = Path(text)
        trusted_stage = base / "trusted"
        resource_paths = make_resource_stage(trusted_stage)
        trusted = launcher.trusted_resource_stage_identity(trusted_stage)
        check(trusted.runtime_resource_count == 52, "trusted identity pins all 52 resources")

        def cache_copy(name: str) -> Path:
            target = base / name
            shutil.copytree(trusted_stage, target)
            return target

        exact = cache_copy("exact")
        launcher.validate_cached_resource_stage(exact, trusted)
        check(True, "an exact cached resource stage is accepted")

        first_relative = resource_paths[0]
        first_path = Path("desktop/localcomet-desktop/src-tauri/binaries") / first_relative

        modified = cache_copy("modified")
        modified_target = modified / first_path
        modified_bytes = bytearray(modified_target.read_bytes())
        modified_bytes[0] ^= 1
        modified_target.write_bytes(modified_bytes)
        expect_hold(
            lambda: launcher.validate_cached_resource_stage(modified, trusted),
            "same-size modified cached contents are rejected by SHA-256",
        )

        wrong_size = cache_copy("wrong_size")
        with (wrong_size / first_path).open("ab") as handle:
            handle.write(b"x")
        expect_hold(
            lambda: launcher.validate_cached_resource_stage(wrong_size, trusted),
            "incorrect cached byte count is rejected",
        )

        missing = cache_copy("missing")
        (missing / first_path).unlink()
        expect_hold(
            lambda: launcher.validate_cached_resource_stage(missing, trusted),
            "missing cached resource is rejected",
        )

        extra = cache_copy("extra")
        write(extra / "desktop/localcomet-desktop/src-tauri/binaries/unexpected.bin")
        expect_hold(
            lambda: launcher.validate_cached_resource_stage(extra, trusted),
            "unexpected cached resource is rejected",
        )

        modified_manifest = cache_copy("modified_manifest")
        manifest_path = modified_manifest.joinpath(
            *launcher.PurePosixPath(launcher.RUNTIME_IDENTITY_RELATIVE).parts
        )
        manifest_bytes = bytearray(manifest_path.read_bytes())
        manifest_bytes[-2] = ord("0") if manifest_bytes[-2] != ord("0") else ord("1")
        manifest_path.write_bytes(manifest_bytes)
        expect_hold(
            lambda: launcher.validate_cached_resource_stage(modified_manifest, trusted),
            "modified cached identity manifest is rejected against fresh trust data",
        )

        non_regular = cache_copy("non_regular")
        (non_regular / first_path).unlink()
        (non_regular / first_path).mkdir()
        expect_hold(
            lambda: launcher.validate_cached_resource_stage(non_regular, trusted),
            "a directory cannot replace an expected regular cached file",
        )

        digest = "0" * 64
        unsafe_manifest = (
            launcher.RUNTIME_IDENTITY_HEADER + f"../escape\t1\t{digest}\n"
        ).encode("utf-8")
        expect_hold(
            lambda: launcher.parse_runtime_identity_manifest(unsafe_manifest),
            "unsafe identity-manifest relative path is rejected",
        )
        duplicate_manifest = (
            launcher.RUNTIME_IDENTITY_HEADER
            + f"payload/A.bin\t1\t{digest}\n"
            + f"payload/a.bin\t1\t{digest}\n"
        ).encode("utf-8")
        expect_hold(
            lambda: launcher.parse_runtime_identity_manifest(duplicate_manifest),
            "case-folded identity-manifest path alias is rejected",
        )

        try:
            launcher.validate_cached_resource_stage(extra, trusted)
        except launcher.LauncherHold as exc:
            message = str(exc)
            check(
                "LC_DEV_RESOURCE_CACHE_INVALID:unexpected_file" in message,
                "cache rejection has a stable actionable diagnostic code",
            )
            check(str(base) not in message, "cache rejection does not disclose raw paths")
        else:
            raise AssertionError("corrupt cache must fail closed")


def test_prepare_resources_uses_fresh_identity_source() -> None:
    with tempfile.TemporaryDirectory(prefix="lc_dev_resource_prepare_") as text:
        base = Path(text)
        source = base / "source"
        make_source(source)
        paths = runtime_paths(base)
        paths.workspace.mkdir(parents=True)
        staged_workspaces: list[Path] = []

        class FakePackagingHold(RuntimeError):
            pass

        class FakePackaging:
            PackagingHold = FakePackagingHold

            @staticmethod
            def stage_runtime(_source_root: Path, workspace: Path) -> None:
                staged_workspaces.append(workspace)
                make_resource_stage(
                    workspace,
                    (source / "localcomet_runtime_manifest.json").read_text(encoding="utf-8"),
                )

        fingerprint = "b" * 64
        original_fingerprint = launcher.runtime_resource_fingerprint
        launcher.runtime_resource_fingerprint = lambda _root: (fingerprint, FakePackaging, {})
        try:
            launcher.prepare_tauri_resources(source, paths, {})
            cache = paths.resource_cache / fingerprint
            check(cache.is_dir(), "first resource preparation creates the versioned cache")
            launcher.prepare_tauri_resources(source, paths, {})
            check(len(staged_workspaces) == 2, "cache reuse builds an independent fresh trust stage")
            check(staged_workspaces[1] != cache, "trusted identity is not read from the reused cache")

            cached_resource = cache / (
                Path("desktop/localcomet-desktop/src-tauri/binaries") / "payload/resource-00.bin"
            )
            corrupt_bytes = bytearray(cached_resource.read_bytes())
            corrupt_bytes[0] ^= 1
            cached_resource.write_bytes(corrupt_bytes)
            corrupt_identity = cached_resource.read_bytes()
            expect_hold(
                lambda: launcher.prepare_tauri_resources(source, paths, {}),
                "prepare fails closed when the existing cache is corrupted",
            )
            check(
                cached_resource.read_bytes() == corrupt_identity,
                "prepare does not repair or overwrite the corrupted cache",
            )
        finally:
            launcher.runtime_resource_fingerprint = original_fingerprint


def main() -> None:
    test_source_validation()
    test_runtime_paths()
    test_synchronization()
    test_dependency_state()
    test_vite_patch()
    test_launch_safety_static_and_env()
    test_sidecar_layout_validation()
    test_tauri_resources_are_synchronized_from_external_stage()
    test_tauri_resource_cache_identity_validation()
    test_prepare_resources_uses_fresh_identity_source()
    check(CHECKS >= 70, "at least seventy focused checks executed")
    print(f"ALL v6.84.5.1d2 DEV LAUNCHER TESTS PASSED ({CHECKS} checks)")


if __name__ == "__main__":
    main()
