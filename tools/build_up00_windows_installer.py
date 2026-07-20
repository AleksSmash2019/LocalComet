from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import subprocess
import sys
from datetime import datetime, timezone
import zipfile


WORK_PACKAGE = "UP00-WP01"
TARGET_TRIPLE = "x86_64-pc-windows-msvc"
GENERATED_ROOT = Path("target") / "up00-wp01"
RUNTIME_MANIFEST = Path("desktop/localcomet-desktop/src-tauri/up00-runtime-manifest.json")
TAURI_DIR = Path("desktop/localcomet-desktop/src-tauri")
APP_DIR = Path("desktop/localcomet-desktop")
SIDECAR_READY_TEST = Path("tools/test_v6843_sidecar_supervisor.py")
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


class PackagingHold(RuntimeError):
    """A bounded packaging precondition was not met."""


def repository_root() -> Path:
    return Path(__file__).resolve(strict=True).parents[1]


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def require_within(path: Path, root: Path, label: str) -> Path:
    resolved_root = root.resolve(strict=False)
    resolved = path.resolve(strict=False)
    if resolved == resolved_root or is_relative_to(resolved, resolved_root):
        return resolved
    raise PackagingHold(f"{label} escapes its bounded root")


def safe_relative(value: str, label: str) -> Path:
    normalized = value.replace("\\", "/").strip()
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(normalized)
    if (
        not normalized
        or normalized.startswith(("/", "\\"))
        or windows.drive
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise PackagingHold(f"unsafe {label}")
    return Path(*posix.parts)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_runtime_manifest(root: Path) -> dict[str, object]:
    path = require_within(root / RUNTIME_MANIFEST, root, "runtime manifest")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackagingHold("runtime manifest is unreadable or invalid") from exc
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise PackagingHold("unsupported runtime manifest schema")
    if data.get("workPackage") != WORK_PACKAGE:
        raise PackagingHold("runtime manifest work package mismatch")
    if data.get("targetTriple") != TARGET_TRIPLE:
        raise PackagingHold("runtime manifest target mismatch")
    if data.get("sidecarBaseName") != "localcomet-core":
        raise PackagingHold("runtime manifest sidecar name mismatch")
    source_files = data.get("sourceFiles")
    if not isinstance(source_files, list) or not source_files:
        raise PackagingHold("runtime manifest sourceFiles must be a non-empty list")
    if source_files != sorted(source_files, key=str.casefold) or len(source_files) != len(set(source_files)):
        raise PackagingHold("runtime sourceFiles must be unique and casefold-sorted")
    normalized = [safe_relative(value, "runtime source path") for value in source_files if isinstance(value, str)]
    if len(normalized) != len(source_files):
        raise PackagingHold("runtime source path must be a string")
    entrypoint = data.get("entrypoint")
    if not isinstance(entrypoint, str) or safe_relative(entrypoint, "runtime entrypoint") not in normalized:
        raise PackagingHold("runtime entrypoint is not in sourceFiles")
    return data


def validate_python_runtime(manifest: dict[str, object]) -> Path:
    if os.name != "nt" or sys.implementation.name != "cpython":
        raise PackagingHold("UP00-WP01 packaging requires CPython on Windows")
    python = manifest.get("python")
    if not isinstance(python, dict):
        raise PackagingHold("runtime manifest python section is invalid")
    required = (python.get("major"), python.get("minor"))
    actual = (sys.version_info.major, sys.version_info.minor)
    if required != actual:
        raise PackagingHold(f"CPython ABI mismatch: required {required[0]}.{required[1]}")
    base = Path(sys.base_prefix).resolve(strict=True)
    expected = [
        base / "python.exe",
        base / f"python{actual[0]}{actual[1]}.dll",
        base / "python3.dll",
        base / "Lib",
        base / "DLLs",
        base / str(python.get("licenseFile", "")),
    ]
    if any(not path.exists() for path in expected):
        raise PackagingHold("local CPython runtime is incomplete")
    return base


def git_output(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise PackagingHold("Git could not materialize the bounded build workspace")
    return completed.stdout


def require_clean_feature_branch(root: Path) -> str:
    branch = git_output(root, "branch", "--show-current").decode("utf-8").strip()
    if branch != "feat/up00-wp01-windows-one-click-launch":
        raise PackagingHold("packaging must run from the authorized feature branch")
    status = git_output(root, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise PackagingHold("packaging requires a clean feature worktree")
    return git_output(root, "rev-parse", "HEAD").decode("ascii").strip()


def tracked_paths(root: Path) -> tuple[Path, ...]:
    raw = git_output(root, "ls-files", "-z")
    values = raw.decode("utf-8").split("\0")
    paths = tuple(safe_relative(value, "tracked path") for value in values if value)
    if not paths:
        raise PackagingHold("tracked source set is empty")
    return paths


def materialize_workspace(root: Path, workspace: Path) -> None:
    workspace = require_within(workspace, root / GENERATED_ROOT, "generated workspace")
    if workspace.exists():
        raise PackagingHold("generated workspace already exists")
    workspace.mkdir(parents=True)
    for relative in tracked_paths(root):
        source = require_within(root / relative, root, "tracked source")
        destination = require_within(workspace / relative, workspace, "workspace target")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def copy_runtime_sources(
    source_root: Path,
    binaries: Path,
    manifest: dict[str, object],
) -> None:
    app_root = binaries / "app"
    for value in manifest["sourceFiles"]:
        relative = safe_relative(str(value), "runtime source path")
        source = require_within(source_root / relative, source_root, "runtime source")
        if not source.is_file() or source.is_symlink():
            raise PackagingHold("runtime source file is missing or linked")
        target = require_within(app_root / relative, app_root, "runtime target")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def excluded_stdlib_path(relative: Path, excluded_top_level: frozenset[str]) -> bool:
    if not relative.parts:
        return True
    if relative.parts[0] in excluded_top_level:
        return True
    if "__pycache__" in relative.parts:
        return True
    return relative.suffix.lower() in {".pyc", ".pyo"}


def write_stdlib_zip(base: Path, target: Path, manifest: dict[str, object]) -> None:
    python = manifest["python"]
    if not isinstance(python, dict):
        raise PackagingHold("runtime manifest python section is invalid")
    excluded_values = python.get("excludedTopLevel")
    if not isinstance(excluded_values, list) or not all(isinstance(value, str) for value in excluded_values):
        raise PackagingHold("excludedTopLevel must be a string list")
    excluded = frozenset(excluded_values)
    lib_root = (base / "Lib").resolve(strict=True)
    files = [
        path
        for path in lib_root.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and not excluded_stdlib_path(path.relative_to(lib_root), excluded)
    ]
    if not any(path.relative_to(lib_root).as_posix() == "encodings/__init__.py" for path in files):
        raise PackagingHold("stdlib closure is missing encodings")
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(files, key=lambda path: path.relative_to(lib_root).as_posix().casefold()):
            relative = source.relative_to(lib_root).as_posix()
            info = zipfile.ZipInfo(relative, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def copy_python_runtime(base: Path, binaries: Path, manifest: dict[str, object]) -> None:
    python = manifest["python"]
    if not isinstance(python, dict):
        raise PackagingHold("runtime manifest python section is invalid")
    major = int(python["major"])
    minor = int(python["minor"])
    shutil.copy2(base / "python.exe", binaries / f"localcomet-core-{TARGET_TRIPLE}.exe")
    for name in [f"python{major}{minor}.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll"]:
        source = base / name
        if source.is_file():
            shutil.copy2(source, binaries / name)
    dll_target = binaries / "DLLs"
    dll_target.mkdir()
    for source in sorted((base / "DLLs").iterdir(), key=lambda path: path.name.casefold()):
        if source.is_file() and not source.is_symlink():
            shutil.copy2(source, dll_target / source.name)
    write_stdlib_zip(base, binaries / f"python{major}{minor}.zip", manifest)
    license_name = str(python["licenseFile"])
    shutil.copy2(base / license_name, binaries / "LICENSE.python.txt")


def write_identity_manifest(binaries: Path) -> None:
    rows = ["path\tbytes\tsha256\n"]
    for path in sorted(binaries.rglob("*"), key=lambda item: item.relative_to(binaries).as_posix().casefold()):
        if not path.is_file() or path.name == "runtime-manifest.tsv":
            continue
        relative = path.relative_to(binaries).as_posix()
        rows.append(f"{relative}\t{path.stat().st_size}\t{sha256_file(path)}\n")
    (binaries / "runtime-manifest.tsv").write_text("".join(rows), encoding="utf-8", newline="\n")


def write_generated_legacy_manifest(workspace: Path, manifest: dict[str, object]) -> None:
    source_files = [str(value) for value in manifest["sourceFiles"]]
    runner = str(manifest["entrypoint"])
    validator = "tools/validate_localcomet_vault.py"
    lazy_runtime = sorted(
        [value for value in source_files if value.startswith("modules/")],
        key=str.casefold,
    )
    tools = sorted([value for value in source_files if value in {runner, validator}], key=str.casefold)
    generated = {
        "entrypoints": [],
        "runtime": [],
        "lazy_runtime": lazy_runtime,
        "tests": [SIDECAR_READY_TEST.as_posix()],
        "tools": tools,
    }
    target = require_within(workspace / "localcomet_runtime_manifest.json", workspace, "legacy manifest")
    target.write_text(json.dumps(generated, indent=2, sort_keys=False) + "\n", encoding="utf-8", newline="\n")


def stage_runtime(source_root: Path, workspace: Path) -> Path:
    manifest = load_runtime_manifest(source_root)
    base = validate_python_runtime(manifest)
    binaries = require_within(workspace / TAURI_DIR / "binaries", workspace, "runtime staging")
    if binaries.exists():
        raise PackagingHold("runtime staging directory already exists")
    binaries.mkdir(parents=True)
    copy_runtime_sources(source_root, binaries, manifest)
    copy_python_runtime(base, binaries, manifest)
    shutil.copy2(source_root / RUNTIME_MANIFEST, binaries / "up00-runtime-manifest.json")
    write_identity_manifest(binaries)
    write_generated_legacy_manifest(workspace, manifest)
    return binaries


def resolve_npm() -> str:
    for name in ("npm.cmd", "npm.exe", "npm"):
        value = shutil.which(name)
        if value:
            return value
    raise PackagingHold("npm was not found")


def run_checked(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    print(f"RUN {cwd}: {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=cwd, env=env, shell=False, check=False)
    if completed.returncode != 0:
        raise PackagingHold(f"command failed with exit code {completed.returncode}: {command[0]}")


def build_installer(root: Path, workspace: Path) -> tuple[Path, ...]:
    npm = resolve_npm()
    app_dir = workspace / APP_DIR
    tauri_dir = workspace / TAURI_DIR
    env = os.environ.copy()
    cargo_target = require_within(root / GENERATED_ROOT / "cargo-target", root / GENERATED_ROOT, "Cargo target")
    cargo_target.mkdir(parents=True, exist_ok=True)
    env["CARGO_TARGET_DIR"] = str(cargo_target)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["LOCALCOMET_TEST_PROJECT_ROOT"] = str(workspace)
    env["LOCALCOMET_TEST_PYTHON"] = sys.executable
    env.pop("LOCALCOMET_KNOWLEDGE_VAULT", None)
    env.pop("LOCALCOMET_KNOWLEDGE_PROJECT_ROOT", None)

    run_checked([sys.executable, str(SIDECAR_READY_TEST)], workspace, env)
    run_checked([npm, "ci", "--offline"], app_dir, env)
    run_checked([npm, "test"], app_dir, env)
    run_checked([npm, "run", "check"], app_dir, env)
    run_checked([npm, "run", "build"], app_dir, env)
    run_checked(["cargo", "fmt", "--all", "--", "--check"], tauri_dir, env)
    run_checked(["cargo", "check", "--offline"], tauri_dir, env)
    run_checked(["cargo", "clippy", "--offline", "--all-targets", "--", "-D", "warnings"], tauri_dir, env)
    run_checked(["cargo", "test", "--offline"], tauri_dir, env)
    run_checked(
        [npm, "run", "tauri", "--", "build", "--bundles", "nsis", "--no-sign", "--ci", "--", "--offline"],
        app_dir,
        env,
    )
    bundle_root = cargo_target / "release" / "bundle" / "nsis"
    installers = tuple(sorted(bundle_root.glob("*.exe"), key=lambda path: path.name.casefold()))
    if len(installers) != 1:
        raise PackagingHold("Tauri did not produce exactly one NSIS installer")
    return installers


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the bounded UP00-WP01 Windows installer.")
    parser.add_argument("--build", action="store_true", help="Run offline tests and the Tauri NSIS build after staging.")
    parser.add_argument("--workspace", default=None, help="New generated workspace below target/up00-wp01.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = repository_root()
    try:
        commit = require_clean_feature_branch(root)
        generated_root = require_within(root / GENERATED_ROOT, root, "generated root")
        generated_root.mkdir(parents=True, exist_ok=True)
        if args.workspace:
            workspace = require_within(Path(args.workspace), generated_root, "requested workspace")
        else:
            workspace = generated_root / f"build-{utc_stamp()}-{os.getpid()}"
        materialize_workspace(root, workspace)
        binaries = stage_runtime(root, workspace)
        installers = build_installer(root, workspace) if args.build else ()
        result = {
            "work_package": WORK_PACKAGE,
            "source_commit": commit,
            "workspace": str(workspace),
            "runtime_manifest": str(binaries / "runtime-manifest.tsv"),
            "installers": [
                {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
                for path in installers
            ],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except PackagingHold as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
