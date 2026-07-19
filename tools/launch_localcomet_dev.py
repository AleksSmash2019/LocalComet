#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable


RELEASE = "v6.84.5.1d1"
RUNTIME_RELATIVE = Path("LocalComet") / "DevRuntime"
WORKSPACE_NAME = "workspace"
CARGO_TARGET_NAME = "cargo-target"
STATE_NAME = "state.json"
LOGS_NAME = "logs"

SYNC_ROOTS = ("desktop", "modules", "tools")
SYNC_FILES = ("localcomet_runtime_manifest.json",)
MANIFEST_PATH_CATEGORIES = ("entrypoints", "runtime", "lazy_runtime", "tests", "tools")
EXCLUDED_NAMES = {
    ".coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svelte-kit",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
}
REQUIRED_SOURCE_FILES = (
    "desktop/localcomet-desktop/package.json",
    "desktop/localcomet-desktop/package-lock.json",
    "desktop/localcomet-desktop/vite.config.ts",
    "desktop/localcomet-desktop/src-tauri/Cargo.toml",
    "tools/run_localcomet_desktop_sidecar.py",
    "modules/desktop_sidecar_runtime_ru.py",
    "modules/desktop_ipc_contract_ru.py",
    "localcomet_runtime_manifest.json",
)
REQUIRED_SIDECAR_FILES = (
    "tools/run_localcomet_desktop_sidecar.py",
    "modules/desktop_sidecar_runtime_ru.py",
    "modules/desktop_ipc_contract_ru.py",
    "localcomet_runtime_manifest.json",
)
PROHIBITED_SOURCE_PATHS = (
    "desktop/localcomet-desktop/node_modules",
    "desktop/localcomet-desktop/src-tauri/target",
)
VITE_WATCH_IGNORE = "**/src-tauri/target/**"


class LauncherHold(RuntimeError):
    """A hard safety stop that the user must resolve manually."""


class VitePropertyNotFound(LauncherHold):
    """Raised when an optional Vite property is absent."""


@dataclass(frozen=True)
class RuntimePaths:
    root: Path
    workspace: Path
    cargo_target: Path
    state: Path
    logs: Path


@dataclass
class SyncSummary:
    copied: int = 0
    updated: int = 0
    reused: int = 0
    removed_stale: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "copied": self.copied,
            "updated": self.updated,
            "reused": self.reused,
            "removed_stale": self.removed_stale,
        }


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def canonical(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def require_within(path: Path, root: Path, label: str) -> Path:
    resolved_path = canonical(path)
    resolved_root = canonical(root)
    if resolved_path != resolved_root and not is_relative_to(resolved_path, resolved_root):
        raise LauncherHold(f"{label} escapes launcher-owned root: {resolved_path}")
    return resolved_path


def source_root_from_launcher() -> Path:
    return canonical(Path(__file__).resolve().parents[1])


def validate_source_layout(source_root: Path) -> None:
    source_root = canonical(source_root)
    missing = []
    for relative in REQUIRED_SOURCE_FILES:
        path = canonical(source_root / relative)
        if not is_relative_to(path, source_root):
            raise LauncherHold(f"Required source path escapes repository: {relative}")
        if not path.is_file():
            missing.append(relative)
    if missing:
        raise LauncherHold("Missing required source file(s): " + ", ".join(missing))

    present = []
    for relative in PROHIBITED_SOURCE_PATHS:
        path = canonical(source_root / relative)
        if not is_relative_to(path, source_root):
            raise LauncherHold(f"Generated source path escapes repository: {relative}")
        if path.exists():
            present.append(relative)
    if present:
        raise LauncherHold(
            "Generated source path(s) are present; remove manually before launching: "
            + ", ".join(present)
        )


def load_manifest_paths(manifest_path: Path) -> tuple[str, ...]:
    if not manifest_path.is_file():
        raise LauncherHold("Missing runtime manifest: localcomet_runtime_manifest.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise LauncherHold("Runtime manifest is unreadable or invalid JSON") from exc
    if not isinstance(manifest, dict):
        raise LauncherHold("Runtime manifest root must be an object")

    declared: list[str] = []
    seen: set[str] = set()
    for category in MANIFEST_PATH_CATEGORIES:
        values = manifest.get(category)
        if not isinstance(values, list):
            raise LauncherHold(f"Runtime manifest category must be a list: {category}")
        for value in values:
            if not isinstance(value, str):
                raise LauncherHold(f"Runtime manifest path must be a string: {category}")
            normalized = value.replace("\\", "/").strip()
            pure = PurePosixPath(normalized)
            if (
                not normalized
                or PureWindowsPath(normalized).drive
                or normalized.startswith(("/", "\\"))
                or any(part in {"", ".", ".."} for part in pure.parts)
            ):
                raise LauncherHold(f"Unsafe runtime manifest path: {value}")
            relative = pure.as_posix()
            if relative not in seen:
                seen.add(relative)
                declared.append(relative)
    return tuple(declared)


def validate_sidecar_layout(workspace: Path) -> None:
    workspace = canonical(workspace)
    missing_sidecar = [
        relative for relative in REQUIRED_SIDECAR_FILES if not (workspace / relative).is_file()
    ]
    if missing_sidecar:
        raise LauncherHold("Missing required sidecar file(s): " + ", ".join(missing_sidecar))

    manifest_path = workspace / "localcomet_runtime_manifest.json"
    missing_manifest_files = []
    for relative in load_manifest_paths(manifest_path):
        target = canonical(workspace / Path(relative))
        if not is_relative_to(target, workspace):
            raise LauncherHold(f"Runtime manifest path escapes workspace: {relative}")
        if not target.is_file():
            missing_manifest_files.append(relative)
    if missing_manifest_files:
        raise LauncherHold(
            "Missing manifest-declared runtime file(s): " + ", ".join(missing_manifest_files)
        )


def resolve_runtime_paths(env: dict[str, str] | None = None) -> RuntimePaths:
    data = os.environ if env is None else env
    local_app_data = data.get("LOCALAPPDATA")
    if not local_app_data:
        raise LauncherHold("LOCALAPPDATA is not set; cannot resolve stable DevRuntime path")
    local_root = canonical(Path(local_app_data))
    runtime_root = require_within(local_root / RUNTIME_RELATIVE, local_root, "Runtime root")
    paths = RuntimePaths(
        root=runtime_root,
        workspace=require_within(runtime_root / WORKSPACE_NAME, runtime_root, "Runtime workspace"),
        cargo_target=require_within(runtime_root / CARGO_TARGET_NAME, runtime_root, "Cargo cache"),
        state=require_within(runtime_root / STATE_NAME, runtime_root, "Launcher state"),
        logs=require_within(runtime_root / LOGS_NAME, runtime_root, "Launcher logs"),
    )
    return paths


def read_state(state_path: Path) -> tuple[dict[str, object], bool]:
    if not state_path.exists():
        return {}, False
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}, True
    if not isinstance(data, dict):
        return {}, True
    return data, False


def save_state(state_path: Path, state: dict[str, object]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    safe_state = {
        "package_lock_sha256": state.get("package_lock_sha256"),
        "npm_ci_completed": bool(state.get("npm_ci_completed", False)),
        "synced_files": sorted(str(item) for item in state.get("synced_files", []) if isinstance(item, str)),
    }
    temporary = state_path.with_name(f"{state_path.name}.tmp")
    temporary.write_text(json.dumps(safe_state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(state_path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_match(source: Path, target: Path) -> bool:
    if not target.is_file():
        return False
    source_stat = source.stat()
    target_stat = target.stat()
    if source_stat.st_size != target_stat.st_size:
        return False
    return sha256_file(source) == sha256_file(target)


def target_matches_bytes(target: Path, expected: bytes) -> bool:
    if not target.is_file():
        return False
    if target.stat().st_size != len(expected):
        return False
    return target.read_bytes() == expected


def runtime_content_for(source_path: Path, relative: str) -> bytes | None:
    if relative == "desktop/localcomet-desktop/vite.config.ts":
        source_text = source_path.read_text(encoding="utf-8")
        return patch_vite_config_text(source_text).encode("utf-8")
    return None


def iter_source_files(source_root: Path) -> Iterable[tuple[Path, str]]:
    yielded: set[str] = set()
    for root_name in SYNC_ROOTS:
        root = canonical(source_root / root_name)
        if not root.is_dir():
            raise LauncherHold(f"Missing synchronized source directory: {root_name}")
        for current, dir_names, file_names in os.walk(root):
            current_path = Path(current)
            dir_names[:] = sorted(name for name in dir_names if name not in EXCLUDED_NAMES)
            for file_name in sorted(file_names):
                if file_name in EXCLUDED_NAMES:
                    continue
                source_path = canonical(current_path / file_name)
                if not is_relative_to(source_path, source_root):
                    raise LauncherHold(f"Source file escapes repository: {source_path}")
                relative = source_path.relative_to(source_root).as_posix()
                if relative not in yielded:
                    yielded.add(relative)
                    yield source_path, relative

    for file_name in SYNC_FILES:
        source_path = canonical(source_root / file_name)
        if not source_path.is_file():
            raise LauncherHold(f"Missing synchronized source file: {file_name}")
        relative = source_path.relative_to(source_root).as_posix()
        if relative not in yielded:
            yielded.add(relative)
            yield source_path, relative

    manifest_path = canonical(source_root / "localcomet_runtime_manifest.json")
    for relative in load_manifest_paths(manifest_path):
        source_path = canonical(source_root / Path(relative))
        if not is_relative_to(source_path, source_root):
            raise LauncherHold(f"Manifest source path escapes repository: {relative}")
        if not source_path.is_file():
            raise LauncherHold(f"Missing manifest-declared source file: {relative}")
        if relative not in yielded:
            yielded.add(relative)
            yield source_path, relative


def synchronize_runtime(source_root: Path, paths: RuntimePaths, state: dict[str, object]) -> tuple[SyncSummary, list[str]]:
    source_root = canonical(source_root)
    workspace = require_within(paths.workspace, paths.root, "Runtime workspace")
    workspace.mkdir(parents=True, exist_ok=True)
    summary = SyncSummary()
    current_files: list[str] = []

    for source_path, relative in iter_source_files(source_root):
        target_path = require_within(workspace / Path(relative), workspace, "Synchronized target")
        current_files.append(relative)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_content = runtime_content_for(source_path, relative)
        if runtime_content is not None:
            if not target_path.exists():
                target_path.write_bytes(runtime_content)
                summary.copied += 1
            elif target_matches_bytes(target_path, runtime_content):
                summary.reused += 1
            else:
                target_path.write_bytes(runtime_content)
                summary.updated += 1
        elif not target_path.exists():
            shutil.copy2(source_path, target_path)
            summary.copied += 1
        elif files_match(source_path, target_path):
            summary.reused += 1
        else:
            shutil.copy2(source_path, target_path)
            summary.updated += 1

    previous_files = state.get("synced_files", [])
    previous_set = {item for item in previous_files if isinstance(item, str)}
    current_set = set(current_files)
    for relative in sorted(previous_set - current_set):
        target_path = require_within(workspace / Path(relative), workspace, "Stale synchronized target")
        if target_path.is_file() or target_path.is_symlink():
            target_path.unlink()
            summary.removed_stale += 1

    return summary, sorted(current_files)


def find_property_object(text: str, property_name: str, start: int = 0, end: int | None = None) -> tuple[int, int, int]:
    search_end = len(text) if end is None else end
    index = start
    in_string: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    while index < search_end:
        char = text[index]
        next_char = text[index + 1] if index + 1 < search_end else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            index += 1
            continue
        if char in {"'", '"', "`"}:
            in_string = char
            index += 1
            continue
        if char == "/" and next_char == "/":
            line_comment = True
            index += 2
            continue
        if char == "/" and next_char == "*":
            block_comment = True
            index += 2
            continue
        if text.startswith(property_name, index):
            before = text[index - 1] if index > 0 else " "
            after_index = index + len(property_name)
            after = text[after_index] if after_index < search_end else " "
            if (before.isalnum() or before in {"_", "$"}) or (after.isalnum() or after in {"_", "$"}):
                index += 1
                continue
            colon = after_index
            while colon < search_end and text[colon].isspace():
                colon += 1
            if colon >= search_end or text[colon] != ":":
                index += 1
                continue
            brace = colon + 1
            while brace < search_end and text[brace].isspace():
                brace += 1
            if brace >= search_end or text[brace] != "{":
                raise LauncherHold(f"Vite property {property_name!r} is not an object")
            close = find_matching(text, brace, "{", "}")
            return index, brace, close
        index += 1
    raise VitePropertyNotFound(f"Vite property {property_name!r} was not found")


def find_matching(text: str, open_index: int, open_char: str, close_char: str) -> int:
    depth = 0
    index = open_index
    in_string: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            index += 1
            continue
        if char in {"'", '"', "`"}:
            in_string = char
            index += 1
            continue
        if char == "/" and next_char == "/":
            line_comment = True
            index += 2
            continue
        if char == "/" and next_char == "*":
            block_comment = True
            index += 2
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise LauncherHold("Could not find matching Vite config delimiter")


def line_indent_before(text: str, index: int) -> str:
    line_start = text.rfind("\n", 0, index) + 1
    segment = text[line_start:index]
    return segment[: len(segment) - len(segment.lstrip(" \t"))]


def previous_significant(text: str, index: int) -> str:
    cursor = index - 1
    while cursor >= 0 and text[cursor].isspace():
        cursor -= 1
    return text[cursor] if cursor >= 0 else ""


def insert_object_property(text: str, object_open: int, object_close: int, property_text: str) -> str:
    close_indent = line_indent_before(text, object_close)
    property_indent = close_indent + "  "
    previous = previous_significant(text, object_close)
    comma = "" if previous in {"{", ","} else ","
    insertion = "\n".join(property_indent + line if line else "" for line in property_text.splitlines())
    return text[:object_close] + comma + "\n" + insertion + text[object_close:]


def patch_vite_config_text(text: str) -> str:
    _, server_open, server_close = find_property_object(text, "server")
    server_body = text[server_open + 1 : server_close]
    if VITE_WATCH_IGNORE in server_body:
        return text

    try:
        _, watch_open, watch_close = find_property_object(text, "watch", server_open + 1, server_close)
    except VitePropertyNotFound:
        watch_block = "watch: {\n  ignored: ['**/src-tauri/target/**']\n}"
        return insert_object_property(text, server_open, server_close, watch_block)

    watch_body = text[watch_open + 1 : watch_close]
    if "ignored" in watch_body:
        ignored_index = text.find("ignored", watch_open + 1, watch_close)
        bracket_open = text.find("[", ignored_index, watch_close)
        if bracket_open == -1:
            raise LauncherHold("Vite watch.ignored is not an array")
        bracket_close = find_matching(text, bracket_open, "[", "]")
        previous = previous_significant(text, bracket_close)
        comma = "" if previous in {"[", ","} else ","
        return text[:bracket_close] + f"{comma} '{VITE_WATCH_IGNORE}'" + text[bracket_close:]

    ignored_property = "ignored: ['**/src-tauri/target/**']"
    return insert_object_property(text, watch_open, watch_close, ignored_property)


def patch_runtime_vite_config(vite_config: Path) -> bool:
    original = vite_config.read_text(encoding="utf-8")
    patched = patch_vite_config_text(original)
    if patched == original:
        return False
    vite_config.write_text(patched, encoding="utf-8")
    return True


def dependency_action(state: dict[str, object], package_lock_hash: str, node_modules: Path) -> str:
    if not node_modules.is_dir():
        return "INSTALLED"
    if state.get("package_lock_sha256") != package_lock_hash:
        return "INSTALLED"
    if state.get("npm_ci_completed") is not True:
        return "INSTALLED"
    return "REUSED"


def resolve_npm_executable() -> str:
    candidates = ("npm.cmd", "npm.exe", "npm") if os.name == "nt" else ("npm",)
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise LauncherHold("npm was not found on PATH")


def run_npm_ci(app_dir: Path, state_path: Path, state: dict[str, object], package_lock_hash: str) -> None:
    npm = resolve_npm_executable()
    result = subprocess.run([npm, "ci"], cwd=app_dir, shell=False)
    if result.returncode != 0:
        state["npm_ci_completed"] = False
        save_state(state_path, state)
        raise LauncherHold(f"npm ci failed with exit code {result.returncode}")
    state["package_lock_sha256"] = package_lock_hash
    state["npm_ci_completed"] = True
    save_state(state_path, state)


def build_launch_environment(source_root: Path, paths: RuntimePaths) -> dict[str, str]:
    env = os.environ.copy()
    cargo_target = require_within(paths.cargo_target, paths.root, "Cargo cache")
    if is_relative_to(cargo_target, canonical(source_root)):
        raise LauncherHold(f"CARGO_TARGET_DIR must be outside source repository: {cargo_target}")
    cargo_target.mkdir(parents=True, exist_ok=True)
    env["CARGO_TARGET_DIR"] = str(cargo_target)
    project_root = require_within(paths.workspace, paths.root, "Sidecar project root")
    expected_workspace = canonical(paths.root / WORKSPACE_NAME)
    if project_root != expected_workspace:
        raise LauncherHold(f"Sidecar project root must be the DevRuntime workspace: {project_root}")
    python_executable = canonical(Path(sys.executable))
    if not python_executable.is_file():
        raise LauncherHold(f"Sidecar Python executable is not a regular file: {python_executable}")
    env["LOCALCOMET_TEST_PROJECT_ROOT"] = str(project_root)
    env["LOCALCOMET_TEST_PYTHON"] = str(python_executable)
    knowledge_vault = canonical(source_root.parent / "LocalCometVault")
    if knowledge_vault.is_dir():
        env["LOCALCOMET_KNOWLEDGE_VAULT"] = str(knowledge_vault)
        env["LOCALCOMET_KNOWLEDGE_PROJECT_ROOT"] = str(canonical(source_root))
    return env


def launch_localcomet(app_dir: Path, env: dict[str, str]) -> int:
    npm = resolve_npm_executable()
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(
        [npm, "run", "tauri", "dev"],
        cwd=app_dir,
        env=env,
        shell=False,
        creationflags=creationflags,
    )
    try:
        return int(process.wait())
    except KeyboardInterrupt:
        terminate_launcher_process_tree(process)
        return 130


def terminate_launcher_process_tree(process: subprocess.Popen[object]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def write_log(log_path: Path, message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def print_startup_summary(
    source_root: Path,
    paths: RuntimePaths,
    dependency: str,
    env: dict[str, str],
) -> None:
    print("LocalComet Developer Launcher")
    print()
    print(f"Source: {source_root}")
    print(f"Runtime: {paths.workspace}")
    print(f"Dependencies: {dependency}")
    print(f"Cargo cache: {paths.cargo_target}")
    print(f"Sidecar project root: {env['LOCALCOMET_TEST_PROJECT_ROOT']}")
    print(f"Sidecar Python: {env['LOCALCOMET_TEST_PYTHON']}")
    print("Sidecar layout: VALID")
    print()
    print("Starting LocalComet...")


def main() -> int:
    source_root = source_root_from_launcher()
    log_path: Path | None = None
    try:
        validate_source_layout(source_root)
        paths = resolve_runtime_paths()
        paths.root.mkdir(parents=True, exist_ok=True)
        paths.logs.mkdir(parents=True, exist_ok=True)
        log_path = paths.logs / f"launch_{utc_stamp()}_{os.getpid()}.log"
        state, malformed_state = read_state(paths.state)
        package_lock_hash = sha256_file(source_root / "desktop/localcomet-desktop/package-lock.json")
        write_log(log_path, f"release={RELEASE}")
        write_log(log_path, f"source={source_root}")
        write_log(log_path, f"runtime_workspace={paths.workspace}")
        write_log(log_path, f"cargo_target={paths.cargo_target}")
        write_log(log_path, f"package_lock_sha256={package_lock_hash}")
        if malformed_state:
            write_log(log_path, "state=malformed_reset")

        summary, synced_files = synchronize_runtime(source_root, paths, state)
        state["synced_files"] = synced_files
        save_state(paths.state, state)
        write_log(log_path, "sync_summary=" + json.dumps(summary.as_dict(), sort_keys=True))
        validate_sidecar_layout(paths.workspace)
        write_log(log_path, "sidecar_layout=VALID")

        runtime_app_dir = paths.workspace / "desktop" / "localcomet-desktop"
        patched = patch_runtime_vite_config(runtime_app_dir / "vite.config.ts")
        write_log(log_path, f"vite_watcher_patch={'applied' if patched else 'already_present'}")

        node_modules = runtime_app_dir / "node_modules"
        dependency = dependency_action(state, package_lock_hash, node_modules)
        if dependency == "INSTALLED":
            run_npm_ci(runtime_app_dir, paths.state, state, package_lock_hash)
        write_log(log_path, f"dependency_action={dependency}")

        env = build_launch_environment(source_root, paths)
        write_log(log_path, f"sidecar_project_root={env['LOCALCOMET_TEST_PROJECT_ROOT']}")
        write_log(log_path, f"sidecar_python={env['LOCALCOMET_TEST_PYTHON']}")
        print_startup_summary(source_root, paths, dependency, env)
        write_log(log_path, "launch_start=npm run tauri dev")
        exit_code = launch_localcomet(runtime_app_dir, env)
        write_log(log_path, f"launch_exit_code={exit_code}")
        return exit_code
    except LauncherHold as exc:
        if log_path is not None:
            write_log(log_path, f"error={exc}")
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        if log_path is not None:
            write_log(log_path, f"error={type(exc).__name__}: {exc}")
        print(f"HOLD: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
