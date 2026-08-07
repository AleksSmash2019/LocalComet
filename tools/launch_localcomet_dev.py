#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
import os
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable


RELEASE = "v6.84.5.1d2"
RUNTIME_RELATIVE = Path("LocalCometDev")
WORKSPACE_NAME = "workspace"
CARGO_TARGET_NAME = "cargo-target"
APP_DATA_NAME = "app-data"
RESOURCE_CACHE_NAME = "runtime-cache"
STATE_NAME = "state.json"
LOGS_NAME = "logs"

SYNC_ROOTS = ("desktop", "modules", "tools")
SYNC_FILES = ("third_party/llama.cpp/LICENSE-MIT.txt",)
MANIFEST_PATH_CATEGORIES = ("entrypoints", "runtime", "lazy_runtime", "tests", "tools")
EXCLUDED_NAMES = {
    ".coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svelte-kit",
    "__pycache__",
    "build",
    "binaries",
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
    "desktop/localcomet-desktop/src-tauri/tauri.conf.json",
    "desktop/localcomet-desktop/src-tauri/up00-runtime-manifest.json",
    "tools/build_up00_windows_installer.py",
    "tools/run_localcomet_desktop_sidecar.py",
    "third_party/llama.cpp/LICENSE-MIT.txt",
    "modules/desktop_sidecar_runtime_ru.py",
    "modules/desktop_ipc_contract_ru.py",
)
REQUIRED_SIDECAR_FILES = (
    "tools/run_localcomet_desktop_sidecar.py",
    "modules/desktop_sidecar_runtime_ru.py",
    "modules/desktop_ipc_contract_ru.py",
    "localcomet_runtime_manifest.json",
)
VITE_WATCH_IGNORE = "**/src-tauri/target/**"
RUNTIME_IDENTITY_RELATIVE = (
    "desktop/localcomet-desktop/src-tauri/binaries/runtime-manifest.tsv"
)
RUNTIME_BINARIES_PREFIX = "desktop/localcomet-desktop/src-tauri/binaries/"
LEGACY_RUNTIME_MANIFEST_RELATIVE = "localcomet_runtime_manifest.json"
EXPECTED_TAURI_RESOURCE_IDENTITIES = 54
RUNTIME_IDENTITY_HEADER = "path\tbytes\tsha256\n"


class LauncherHold(RuntimeError):
    """A hard safety stop that the user must resolve manually."""


class VitePropertyNotFound(LauncherHold):
    """Raised when an optional Vite property is absent."""


@dataclass(frozen=True)
class RuntimePaths:
    root: Path
    workspace: Path
    cargo_target: Path
    app_data: Path
    resource_cache: Path
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


@dataclass(frozen=True)
class ResourceFileIdentity:
    relative_path: str
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class ResourceStageIdentity:
    files: tuple[ResourceFileIdentity, ...]
    runtime_resource_count: int


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


def _resource_identity_error(code: str, *, cached: bool) -> LauncherHold:
    if cached:
        return LauncherHold(
            "Cached Tauri runtime resources failed identity validation "
            f"(LC_DEV_RESOURCE_CACHE_INVALID:{code}); remove only the versioned "
            "LocalCometDev runtime-cache entry and retry"
        )
    return LauncherHold(
        "Fresh Tauri runtime identity generation failed "
        f"(LC_DEV_RESOURCE_IDENTITY_INVALID:{code})"
    )


def _resource_path_alias(relative: str) -> str:
    return unicodedata.normalize("NFC", relative).casefold()


def canonical_resource_relative(value: str, *, cached: bool = False) -> str:
    pure = PurePosixPath(value)
    invalid_windows_character = any(character in '<>:"|?*' for character in value)
    if (
        not value
        or value != value.strip()
        or value != unicodedata.normalize("NFC", value)
        or "\\" in value
        or value.startswith(("/", "\\"))
        or PureWindowsPath(value).drive
        or any(ord(character) < 32 for character in value)
        or invalid_windows_character
        or any(part in {"", ".", ".."} for part in pure.parts)
        or pure.as_posix() != value
    ):
        raise _resource_identity_error("unsafe_path", cached=cached)
    return value


def _is_reparse_metadata(metadata: os.stat_result) -> bool:
    return bool(getattr(metadata, "st_file_attributes", 0) & 0x400)


def _sha256_regular_file(path: Path, expected: os.stat_result, *, cached: bool) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        observed = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise _resource_identity_error("unreadable_file", cached=cached) from exc
    if (
        expected.st_size != observed.st_size
        or not stat.S_ISREG(observed.st_mode)
        or _is_reparse_metadata(observed)
    ):
        raise _resource_identity_error("unstable_file", cached=cached)
    return digest.hexdigest()


def scan_resource_stage(
    staged_workspace: Path,
    *,
    cached: bool,
) -> tuple[ResourceFileIdentity, ...]:
    try:
        root_metadata = staged_workspace.stat(follow_symlinks=False)
    except OSError as exc:
        raise _resource_identity_error("missing_stage", cached=cached) from exc
    if (
        not stat.S_ISDIR(root_metadata.st_mode)
        or staged_workspace.is_symlink()
        or _is_reparse_metadata(root_metadata)
    ):
        raise _resource_identity_error("non_regular_stage", cached=cached)

    resolved_root = canonical(staged_workspace)
    pending: list[tuple[Path, str]] = [(staged_workspace, "")]
    identities: list[ResourceFileIdentity] = []
    seen_aliases: set[str] = set()
    while pending:
        directory, relative_directory = pending.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda item: item.name.casefold())
        except OSError as exc:
            raise _resource_identity_error("unreadable_directory", cached=cached) from exc
        for entry in entries:
            relative = (
                f"{relative_directory}/{entry.name}" if relative_directory else entry.name
            )
            relative = canonical_resource_relative(relative, cached=cached)
            alias = _resource_path_alias(relative)
            if alias in seen_aliases:
                raise _resource_identity_error("path_alias", cached=cached)
            seen_aliases.add(alias)
            path = Path(entry.path)
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise _resource_identity_error("unreadable_entry", cached=cached) from exc
            if entry.is_symlink() or _is_reparse_metadata(metadata):
                raise _resource_identity_error("linked_entry", cached=cached)
            resolved = canonical(path)
            if not is_relative_to(resolved, resolved_root):
                raise _resource_identity_error("path_escape", cached=cached)
            if stat.S_ISDIR(metadata.st_mode):
                pending.append((path, relative))
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise _resource_identity_error("non_regular_entry", cached=cached)
            identities.append(
                ResourceFileIdentity(
                    relative_path=relative,
                    byte_count=metadata.st_size,
                    sha256=_sha256_regular_file(path, metadata, cached=cached),
                )
            )
    return tuple(sorted(identities, key=lambda item: _resource_path_alias(item.relative_path)))


def parse_runtime_identity_manifest(raw: bytes) -> tuple[ResourceFileIdentity, ...]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _resource_identity_error("manifest_encoding", cached=False) from exc
    if "\r" in text or not text.endswith("\n") or not text.startswith(RUNTIME_IDENTITY_HEADER):
        raise _resource_identity_error("manifest_format", cached=False)

    rows = text.splitlines()[1:]
    identities: list[ResourceFileIdentity] = []
    seen_aliases: set[str] = set()
    for row in rows:
        columns = row.split("\t")
        if len(columns) != 3:
            raise _resource_identity_error("manifest_row", cached=False)
        relative, byte_text, sha256 = columns
        relative = canonical_resource_relative(relative)
        alias = _resource_path_alias(relative)
        if alias in seen_aliases:
            raise _resource_identity_error("manifest_path_alias", cached=False)
        seen_aliases.add(alias)
        if (
            not byte_text
            or not byte_text.isascii()
            or not byte_text.isdecimal()
            or (byte_text.startswith("0") and byte_text != "0")
        ):
            raise _resource_identity_error("manifest_byte_count", cached=False)
        if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
            raise _resource_identity_error("manifest_sha256", cached=False)
        identities.append(
            ResourceFileIdentity(
                relative_path=relative,
                byte_count=int(byte_text),
                sha256=sha256,
            )
        )
    if [item.relative_path for item in identities] != sorted(
        (item.relative_path for item in identities),
        key=_resource_path_alias,
    ):
        raise _resource_identity_error("manifest_order", cached=False)
    if len(identities) != EXPECTED_TAURI_RESOURCE_IDENTITIES:
        raise _resource_identity_error("manifest_resource_count", cached=False)
    return tuple(identities)


def trusted_resource_stage_identity(staged_workspace: Path) -> ResourceStageIdentity:
    files = scan_resource_stage(staged_workspace, cached=False)
    by_path = {item.relative_path: item for item in files}
    identity_file = by_path.get(RUNTIME_IDENTITY_RELATIVE)
    if identity_file is None or LEGACY_RUNTIME_MANIFEST_RELATIVE not in by_path:
        raise _resource_identity_error("required_manifest_missing", cached=False)
    identity_path = staged_workspace.joinpath(*PurePosixPath(RUNTIME_IDENTITY_RELATIVE).parts)
    try:
        raw_manifest = identity_path.read_bytes()
    except OSError as exc:
        raise _resource_identity_error("manifest_unreadable", cached=False) from exc
    if (
        len(raw_manifest) != identity_file.byte_count
        or hashlib.sha256(raw_manifest).hexdigest() != identity_file.sha256
    ):
        raise _resource_identity_error("manifest_unstable", cached=False)
    runtime_identities = parse_runtime_identity_manifest(raw_manifest)

    actual_runtime = {
        item.relative_path.removeprefix(RUNTIME_BINARIES_PREFIX): item
        for item in files
        if item.relative_path.startswith(RUNTIME_BINARIES_PREFIX)
        and item.relative_path != RUNTIME_IDENTITY_RELATIVE
    }
    declared_runtime = {item.relative_path: item for item in runtime_identities}
    if actual_runtime.keys() != declared_runtime.keys():
        raise _resource_identity_error("manifest_file_set", cached=False)
    for relative, declared in declared_runtime.items():
        actual = actual_runtime[relative]
        if actual.byte_count != declared.byte_count:
            raise _resource_identity_error("manifest_size", cached=False)
        if actual.sha256 != declared.sha256:
            raise _resource_identity_error("manifest_hash", cached=False)

    expected_stage_paths = {
        LEGACY_RUNTIME_MANIFEST_RELATIVE,
        RUNTIME_IDENTITY_RELATIVE,
        *(f"{RUNTIME_BINARIES_PREFIX}{item.relative_path}" for item in runtime_identities),
    }
    if by_path.keys() != expected_stage_paths:
        raise _resource_identity_error("unexpected_generated_file", cached=False)
    return ResourceStageIdentity(
        files=files,
        runtime_resource_count=len(runtime_identities),
    )


def validate_cached_resource_stage(
    staged_workspace: Path,
    trusted_identity: ResourceStageIdentity,
) -> None:
    cached_files = scan_resource_stage(staged_workspace, cached=True)
    expected = {item.relative_path: item for item in trusted_identity.files}
    observed = {item.relative_path: item for item in cached_files}
    if expected.keys() - observed.keys():
        raise _resource_identity_error("missing_file", cached=True)
    if observed.keys() - expected.keys():
        raise _resource_identity_error("unexpected_file", cached=True)
    for relative, expected_file in expected.items():
        observed_file = observed[relative]
        if observed_file.byte_count != expected_file.byte_count:
            raise _resource_identity_error("byte_count", cached=True)
        if observed_file.sha256 != expected_file.sha256:
            raise _resource_identity_error("sha256", cached=True)


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
        raise LauncherHold("LOCALAPPDATA is not set; cannot resolve stable LocalCometDev path")
    local_root = canonical(Path(local_app_data))
    runtime_root = require_within(local_root / RUNTIME_RELATIVE, local_root, "Runtime root")
    paths = RuntimePaths(
        root=runtime_root,
        workspace=require_within(runtime_root / WORKSPACE_NAME, runtime_root, "Runtime workspace"),
        cargo_target=require_within(runtime_root / CARGO_TARGET_NAME, runtime_root, "Cargo cache"),
        app_data=require_within(runtime_root / APP_DATA_NAME, runtime_root, "Development AppData"),
        resource_cache=require_within(
            runtime_root / RESOURCE_CACHE_NAME,
            runtime_root,
            "Runtime resource cache",
        ),
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
        "runtime_resource_fingerprint": state.get("runtime_resource_fingerprint"),
        "runtime_resource_files": sorted(
            str(item)
            for item in state.get("runtime_resource_files", [])
            if isinstance(item, str)
        ),
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


def _packaging_helpers():
    try:
        from tools import build_up00_windows_installer as packaging
    except ModuleNotFoundError as exc:
        if exc.name != "tools":
            raise
        import build_up00_windows_installer as packaging
    return packaging


def runtime_resource_fingerprint(source_root: Path) -> tuple[str, object, dict[str, object]]:
    packaging = _packaging_helpers()
    try:
        manifest = packaging.load_runtime_manifest(source_root)
        python_base = packaging.validate_python_runtime(manifest)
    except packaging.PackagingHold as exc:
        raise LauncherHold(f"Tauri runtime resource validation failed: {exc}") from exc

    inputs: list[tuple[str, Path]] = [
        (
            packaging.RUNTIME_MANIFEST.as_posix(),
            canonical(source_root / packaging.RUNTIME_MANIFEST),
        ),
        (
            "tools/build_up00_windows_installer.py",
            canonical(source_root / "tools/build_up00_windows_installer.py"),
        ),
    ]
    for value in manifest["sourceFiles"]:
        relative = packaging.safe_relative(str(value), "runtime source path")
        inputs.append((f"source/{relative.as_posix()}", canonical(source_root / relative)))

    python = manifest["python"]
    if not isinstance(python, dict):
        raise LauncherHold("Tauri runtime Python manifest is invalid")
    major = int(python["major"])
    minor = int(python["minor"])
    fixed_runtime_names = (
        "python.exe",
        f"python{major}{minor}.dll",
        "python3.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        str(python["licenseFile"]),
    )
    for name in fixed_runtime_names:
        path = canonical(python_base / name)
        if path.is_file() and not path.is_symlink():
            inputs.append((f"python/{name}", path))

    dll_root = canonical(python_base / "DLLs")
    for path in sorted(dll_root.iterdir(), key=lambda item: item.name.casefold()):
        if path.is_file() and not path.is_symlink():
            inputs.append((f"python/DLLs/{path.name}", path))

    excluded_values = python.get("excludedTopLevel")
    if not isinstance(excluded_values, list) or not all(
        isinstance(value, str) for value in excluded_values
    ):
        raise LauncherHold("Tauri runtime excludedTopLevel manifest is invalid")
    excluded = frozenset(excluded_values)
    lib_root = canonical(python_base / "Lib")
    for path in sorted(
        lib_root.rglob("*"),
        key=lambda item: item.relative_to(lib_root).as_posix().casefold(),
    ):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(lib_root)
        if packaging.excluded_stdlib_path(relative, excluded):
            continue
        inputs.append((f"python/Lib/{relative.as_posix()}", path))

    digest = hashlib.sha256()
    for label, path in sorted(inputs, key=lambda item: item[0].casefold()):
        if not path.is_file() or path.is_symlink():
            raise LauncherHold(f"Tauri runtime input is missing or linked: {label}")
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(path.stat().st_size).encode("ascii"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest(), packaging, manifest


def synchronize_tauri_resources(
    staged_workspace: Path,
    paths: RuntimePaths,
    state: dict[str, object],
    trusted_identity: ResourceStageIdentity,
) -> tuple[SyncSummary, list[str]]:
    workspace = require_within(paths.workspace, paths.root, "Runtime workspace")
    staged_workspace = require_within(
        staged_workspace,
        paths.resource_cache,
        "Staged runtime resources",
    )
    validate_cached_resource_stage(staged_workspace, trusted_identity)
    sources = [
        (
            staged_workspace.joinpath(*PurePosixPath(identity.relative_path).parts),
            identity.relative_path,
        )
        for identity in trusted_identity.files
    ]

    summary = SyncSummary()
    current_files: list[str] = []
    for source, relative in sources:
        target = require_within(workspace / Path(relative), workspace, "Runtime resource target")
        target.parent.mkdir(parents=True, exist_ok=True)
        current_files.append(relative)
        if not target.exists():
            shutil.copy2(source, target)
            summary.copied += 1
        elif files_match(source, target):
            summary.reused += 1
        else:
            shutil.copy2(source, target)
            summary.updated += 1

    previous_files = state.get("runtime_resource_files", [])
    previous_set = {item for item in previous_files if isinstance(item, str)}
    current_set = set(current_files)
    for relative in sorted(previous_set - current_set):
        target = require_within(workspace / Path(relative), workspace, "Stale runtime resource")
        if target.is_file() or target.is_symlink():
            target.unlink()
            summary.removed_stale += 1
    return summary, sorted(current_files)


def prepare_tauri_resources(
    source_root: Path,
    paths: RuntimePaths,
    state: dict[str, object],
) -> tuple[SyncSummary, str, list[str]]:
    fingerprint, packaging, _manifest = runtime_resource_fingerprint(source_root)
    resource_cache = require_within(paths.resource_cache, paths.root, "Runtime resource cache")
    resource_cache.mkdir(parents=True, exist_ok=True)
    staged_workspace = require_within(
        resource_cache / fingerprint,
        resource_cache,
        "Versioned runtime resource cache",
    )
    if os.path.lexists(staged_workspace):
        try:
            with tempfile.TemporaryDirectory(
                prefix=f".identity-{fingerprint[:12]}-",
                dir=resource_cache,
            ) as temporary:
                trusted_workspace = Path(temporary)
                packaging.stage_runtime(source_root, trusted_workspace)
                trusted_identity = trusted_resource_stage_identity(trusted_workspace)
                validate_cached_resource_stage(staged_workspace, trusted_identity)
        except packaging.PackagingHold as exc:
            raise LauncherHold(f"Tauri runtime resource staging failed: {exc}") from exc
    else:
        try:
            packaging.stage_runtime(source_root, staged_workspace)
        except packaging.PackagingHold as exc:
            raise LauncherHold(f"Tauri runtime resource staging failed: {exc}") from exc
        trusted_identity = trusted_resource_stage_identity(staged_workspace)

    summary, resource_files = synchronize_tauri_resources(
        staged_workspace,
        paths,
        state,
        trusted_identity,
    )
    return summary, fingerprint, resource_files


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
        raise LauncherHold(f"Sidecar project root must be the LocalCometDev workspace: {project_root}")
    python_executable = canonical(Path(sys.executable))
    if not python_executable.is_file():
        raise LauncherHold(f"Sidecar Python executable is not a regular file: {python_executable}")
    if "windowsapps" in {part.casefold() for part in python_executable.parts}:
        raise LauncherHold("WindowsApps Python shims are not valid sidecar executables")
    app_data = require_within(paths.app_data, paths.root, "Development AppData")
    expected_app_data = canonical(paths.root / APP_DATA_NAME)
    if app_data != expected_app_data:
        raise LauncherHold(f"Development AppData must use the isolated launcher path: {app_data}")
    app_data.mkdir(parents=True, exist_ok=True)
    env["LOCALCOMET_TEST_PROJECT_ROOT"] = str(project_root)
    env["LOCALCOMET_TEST_PYTHON"] = str(python_executable)
    env["LOCALCOMET_APP_DATA_ROOT"] = str(app_data)
    env.pop("LOCALCOMET_KNOWLEDGE_VAULT", None)
    env.pop("LOCALCOMET_KNOWLEDGE_PROJECT_ROOT", None)
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
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT)
            process.wait(timeout=10)
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
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
    print(f"Development AppData: {paths.app_data}")
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
        write_log(log_path, f"development_app_data={paths.app_data}")
        write_log(log_path, f"package_lock_sha256={package_lock_hash}")
        if malformed_state:
            write_log(log_path, "state=malformed_reset")

        summary, synced_files = synchronize_runtime(source_root, paths, state)
        state["synced_files"] = synced_files
        save_state(paths.state, state)
        write_log(log_path, "sync_summary=" + json.dumps(summary.as_dict(), sort_keys=True))

        resource_summary, resource_fingerprint, resource_files = prepare_tauri_resources(
            source_root,
            paths,
            state,
        )
        state["runtime_resource_fingerprint"] = resource_fingerprint
        state["runtime_resource_files"] = resource_files
        save_state(paths.state, state)
        write_log(log_path, f"runtime_resource_fingerprint={resource_fingerprint}")
        write_log(
            log_path,
            f"runtime_resource_identities={EXPECTED_TAURI_RESOURCE_IDENTITIES}",
        )
        write_log(
            log_path,
            "runtime_resource_summary="
            + json.dumps(resource_summary.as_dict(), sort_keys=True),
        )
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
        write_log(log_path, f"application_data_root={env['LOCALCOMET_APP_DATA_ROOT']}")
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
