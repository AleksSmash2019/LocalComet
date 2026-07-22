#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import ctypes
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import io
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from typing import Any, Iterable
from urllib.parse import urlparse
import uuid


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import launch_localcomet_dev as legacy


RELEASE = "v6.84.5.1d4"
LOCK_NAME = "start.lock"
MAX_LOG_TAIL_BYTES = 64 * 1024
DEFAULT_LOG_TAIL_LINES = 80
MIN_FREE_BYTES = 512 * 1024 * 1024
WARN_FREE_BYTES = 2 * 1024 * 1024 * 1024
EXPECTED_LEGACY_RELEASE = "v6.84.5.1d2"
GENERATED_SOURCE_PATHS = (
    "desktop/localcomet-desktop/.svelte-kit",
    "desktop/localcomet-desktop/build",
    "desktop/localcomet-desktop/node_modules",
    "desktop/localcomet-desktop/src-tauri/binaries",
    "desktop/localcomet-desktop/src-tauri/target",
)
LOCALCOMET_PROCESS_NAMES = frozenset(("localcomet.exe", "localcomet-desktop.exe"))


class StartHold(RuntimeError):
    """A bounded launcher stop requiring operator correction."""


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str

    @property
    def ok(self) -> bool:
        return self.status in {"PASS", "WARN"}


@dataclass(frozen=True)
class DoctorReport:
    release: str
    legacy_release: str
    source_root: str
    runtime_root: str
    workspace: str
    cargo_target: str
    app_data: str
    dependency_action: str
    dev_url: str
    checks: tuple[Check, ...]

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.checks)

    @property
    def errors(self) -> int:
        return sum(item.status == "ERROR" for item in self.checks)

    @property
    def warnings(self) -> int:
        return sum(item.status == "WARN" for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "release": self.release,
            "legacy_release": self.legacy_release,
            "source_root": self.source_root,
            "runtime_root": self.runtime_root,
            "workspace": self.workspace,
            "cargo_target": self.cargo_target,
            "app_data": self.app_data,
            "dependency_action": self.dependency_action,
            "dev_url": self.dev_url,
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "checks": [asdict(item) for item in self.checks],
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _path_text(path: Path) -> str:
    return str(path.resolve(strict=False))


def _canonical_python() -> Path:
    executable = Path(sys.executable).resolve(strict=False)
    if not executable.is_file():
        raise StartHold(f"Python executable is not a regular file: {executable}")
    lowered = {part.casefold() for part in executable.parts}
    if "windowsapps" in lowered:
        raise StartHold(
            "WindowsApps Python shim is not permitted because it can corrupt framed sidecar stdout"
        )
    return executable


def _resolve_executable(candidates: Iterable[str]) -> str | None:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return str(Path(resolved).resolve(strict=False))
    return None


def _run_version(name: str, candidates: tuple[str, ...]) -> Check:
    executable = _resolve_executable(candidates)
    if executable is None:
        return Check(name, "ERROR", f"{name} was not found on PATH")
    try:
        result = subprocess.run(
            [executable, "--version"],
            shell=False,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Check(name, "ERROR", f"{name} version check failed: {type(exc).__name__}")
    output = (result.stdout or result.stderr).strip().splitlines()
    version = output[0].strip() if output else "no version output"
    if result.returncode != 0:
        return Check(name, "ERROR", f"{executable}: exit {result.returncode}; {version}")
    return Check(name, "PASS", f"{executable}: {version}")


def _running_localcomet_processes() -> tuple[tuple[int, str], ...]:
    if os.name != "nt":
        return ()
    tasklist = _resolve_executable(("tasklist.exe", "tasklist"))
    if tasklist is None:
        raise StartHold("tasklist is unavailable; existing LocalComet processes cannot be checked")
    try:
        result = subprocess.run(
            [tasklist, "/FO", "CSV", "/NH"],
            shell=False,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise StartHold("existing LocalComet process check failed") from exc
    if result.returncode != 0:
        raise StartHold("existing LocalComet process check returned a failure")

    found: list[tuple[int, str]] = []
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) < 2 or row[0].strip().casefold() not in LOCALCOMET_PROCESS_NAMES:
            continue
        try:
            pid = int(row[1].replace(",", "").strip())
        except ValueError:
            raise StartHold("existing LocalComet process check returned an invalid PID")
        found.append((pid, row[0].strip()))
    return tuple(sorted(found))


def _localcomet_process_check() -> Check:
    try:
        processes = _running_localcomet_processes()
    except StartHold as exc:
        return Check("existing_app", "ERROR", str(exc))
    if not processes:
        return Check("existing_app", "PASS", "no installed or development LocalComet process")
    detail = ", ".join(f"{name} (PID {pid})" for pid, name in processes)
    return Check("existing_app", "ERROR", f"close the existing LocalComet process first: {detail}")


def _generated_source_check(source_root: Path, relative: str) -> Check:
    candidate = source_root / relative
    name = f"source_generated:{relative}"
    if not candidate.exists():
        return Check(name, "PASS", "absent")
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", relative],
            cwd=source_root,
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Check(name, "ERROR", f"ignore verification failed: {type(exc).__name__}")
    if result.returncode == 0:
        return Check(name, "PASS", "present, ignored, and excluded from clean-room sync")
    return Check(name, "ERROR", "present but not covered by repository ignore policy")


def _load_dev_url(source_root: Path) -> str:
    config_path = (
        source_root
        / "desktop"
        / "localcomet-desktop"
        / "src-tauri"
        / "tauri.conf.json"
    )
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StartHold(
            f"Tauri configuration is unreadable or invalid: {config_path.name}"
        ) from exc
    if not isinstance(payload, dict):
        raise StartHold("Tauri configuration root must be an object")
    build = payload.get("build")
    if not isinstance(build, dict):
        raise StartHold("Tauri configuration has no build object")
    raw = build.get("devUrl")
    if not isinstance(raw, str) or not raw.strip():
        raise StartHold("Tauri build.devUrl is missing")
    parsed = urlparse(raw.strip())
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise StartHold("Tauri development URL must be loopback HTTP")
    try:
        port = parsed.port
    except ValueError as exc:
        raise StartHold("Tauri development URL contains an invalid port") from exc
    if port is None or not 1 <= port <= 65535:
        raise StartHold("Tauri development URL must contain a valid explicit port")
    return raw.strip()


def _port_available(dev_url: str) -> tuple[bool, str]:
    parsed = urlparse(dev_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    if port is None:
        return False, "development URL has no port"
    bind_host = "127.0.0.1" if host == "localhost" else host
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind((bind_host, port))
    except OSError as exc:
        return False, f"{bind_host}:{port} is unavailable ({exc.__class__.__name__})"
    finally:
        sock.close()
    return True, f"{bind_host}:{port} is available"


def _nearest_existing_parent(path: Path) -> Path:
    candidate = path.resolve(strict=False)
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate


def _disk_check(runtime_root: Path) -> Check:
    anchor = _nearest_existing_parent(runtime_root)
    try:
        free = shutil.disk_usage(anchor).free
    except OSError as exc:
        return Check("disk_space", "ERROR", f"disk usage failed: {type(exc).__name__}")
    gib = free / (1024**3)
    if free < MIN_FREE_BYTES:
        return Check("disk_space", "ERROR", f"{gib:.2f} GiB free at {anchor}")
    if free < WARN_FREE_BYTES:
        return Check("disk_space", "WARN", f"{gib:.2f} GiB free at {anchor}")
    return Check("disk_space", "PASS", f"{gib:.2f} GiB free at {anchor}")


def _is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information, False, pid
        )
        if not handle:
            return False
        exit_code = ctypes.c_ulong()
        try:
            if not ctypes.windll.kernel32.GetExitCodeProcess(
                handle,
                ctypes.byref(exit_code),
            ):
                return False
            return exit_code.value == 259
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _read_lock(lock_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not lock_path.exists():
        return None, None
    if lock_path.is_symlink() or not lock_path.is_file():
        return None, "lock path is not a regular file"
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "lock file is unreadable or invalid"
    if not isinstance(payload, dict):
        return None, "lock file root is not an object"
    pid = payload.get("pid")
    token = payload.get("token")
    if not isinstance(pid, int) or pid <= 0 or not isinstance(token, str) or not token:
        return None, "lock file has invalid fields"
    return payload, None


def _lock_check(runtime_root: Path) -> Check:
    lock_path = runtime_root / LOCK_NAME
    payload, error = _read_lock(lock_path)
    if error:
        return Check("single_instance", "ERROR", error)
    if payload is None:
        return Check("single_instance", "PASS", "no active wrapper lock")
    pid = int(payload["pid"])
    if _is_process_alive(pid):
        return Check("single_instance", "ERROR", f"launcher process {pid} is active")
    return Check("single_instance", "WARN", f"stale launcher lock for process {pid}")


class LauncherLock:
    def __init__(self, runtime_root: Path) -> None:
        self.runtime_root = runtime_root.resolve(strict=False)
        self.path = self.runtime_root / LOCK_NAME
        self.token = uuid.uuid4().hex
        self.acquired = False

    def _remove_stale(self) -> None:
        payload, error = _read_lock(self.path)
        if error:
            raise StartHold(f"Cannot safely recover launcher lock: {error}")
        if payload is None:
            return
        pid = int(payload["pid"])
        if _is_process_alive(pid):
            raise StartHold(f"LocalComet launcher is already running as process {pid}")
        try:
            self.path.unlink()
        except OSError as exc:
            raise StartHold("Stale launcher lock could not be removed") from exc

    def acquire(self) -> None:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self._remove_stale()
        record = {
            "release": RELEASE,
            "pid": os.getpid(),
            "token": self.token,
            "created_at_utc": _utc_now(),
        }
        encoded = (_json_dump(record) + "\n").encode("utf-8")
        try:
            descriptor = os.open(
                self.path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError as exc:
            raise StartHold("LocalComet launcher lock was acquired concurrently") from exc
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                self.path.unlink()
            except OSError:
                pass
            raise
        self.acquired = True

    def release(self) -> None:
        if not self.acquired:
            return
        payload, error = _read_lock(self.path)
        if error is None and payload is not None and payload.get("token") == self.token:
            try:
                self.path.unlink()
            except OSError:
                pass
        self.acquired = False

    def __enter__(self) -> "LauncherLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()


def _dependency_state(source_root: Path, paths: Any) -> tuple[str, bool]:
    state, malformed = legacy.read_state(paths.state)
    package_lock = (
        source_root / "desktop" / "localcomet-desktop" / "package-lock.json"
    )
    package_lock_hash = legacy.sha256_file(package_lock)
    node_modules = (
        paths.workspace / "desktop" / "localcomet-desktop" / "node_modules"
    )
    action = legacy.dependency_action(state, package_lock_hash, node_modules)
    return action, malformed


def collect_doctor_report(
    *,
    require_free_port: bool,
) -> DoctorReport:
    source_root = legacy.source_root_from_launcher()
    paths = legacy.resolve_runtime_paths()
    checks: list[Check] = []

    try:
        legacy.validate_source_layout(source_root)
    except Exception as exc:
        checks.append(Check("source_layout", "ERROR", str(exc)))
    else:
        checks.append(Check("source_layout", "PASS", "required source layout is valid"))

    legacy_release = str(getattr(legacy, "RELEASE", "UNKNOWN"))
    if legacy_release != EXPECTED_LEGACY_RELEASE:
        checks.append(
            Check(
                "legacy_release",
                "ERROR",
                f"expected {EXPECTED_LEGACY_RELEASE}, observed {legacy_release}",
            )
        )
    else:
        checks.append(Check("legacy_release", "PASS", legacy_release))

    try:
        python_path = _canonical_python()
    except StartHold as exc:
        checks.append(Check("python", "ERROR", str(exc)))
    else:
        checks.append(Check("python", "PASS", str(python_path)))

    checks.extend(
        (
            _run_version("node", ("node.exe", "node")),
            _run_version("npm", ("npm.cmd", "npm.exe", "npm")),
            _run_version("cargo", ("cargo.exe", "cargo")),
            _run_version("rustc", ("rustc.exe", "rustc")),
        )
    )

    try:
        dev_url = _load_dev_url(source_root)
    except StartHold as exc:
        dev_url = ""
        checks.append(Check("dev_url", "ERROR", str(exc)))
    else:
        checks.append(Check("dev_url", "PASS", dev_url))
        available, detail = _port_available(dev_url)
        if available:
            checks.append(Check("dev_port", "PASS", detail))
        elif require_free_port:
            checks.append(Check("dev_port", "ERROR", detail))
        else:
            checks.append(Check("dev_port", "WARN", detail))

    checks.append(_disk_check(paths.root))
    checks.append(_localcomet_process_check())
    lock_status = _lock_check(paths.root)
    if not require_free_port and lock_status.status == "ERROR":
        lock_status = Check(lock_status.name, "WARN", lock_status.detail)
    checks.append(lock_status)

    for relative in GENERATED_SOURCE_PATHS:
        checks.append(_generated_source_check(source_root, relative))

    try:
        dependency_action, malformed_state = _dependency_state(source_root, paths)
    except Exception as exc:
        dependency_action = "UNKNOWN"
        checks.append(
            Check(
                "dependency_state",
                "ERROR",
                f"dependency state failed: {type(exc).__name__}: {exc}",
            )
        )
    else:
        status = "WARN" if malformed_state else "PASS"
        detail = dependency_action
        if malformed_state:
            detail += "; malformed launcher state will be rebuilt"
        checks.append(Check("dependency_state", status, detail))

    return DoctorReport(
        release=RELEASE,
        legacy_release=legacy_release,
        source_root=_path_text(source_root),
        runtime_root=_path_text(paths.root),
        workspace=_path_text(paths.workspace),
        cargo_target=_path_text(paths.cargo_target),
        app_data=_path_text(paths.app_data),
        dependency_action=dependency_action,
        dev_url=dev_url,
        checks=tuple(checks),
    )


def _latest_log(log_dir: Path) -> Path | None:
    if not log_dir.is_dir():
        return None
    candidates = [
        path
        for path in log_dir.glob("launch_*.log")
        if path.is_file() and not path.is_symlink()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))


def _tail_text(path: Path, lines: int) -> str:
    if lines < 1 or lines > 500:
        raise StartHold("tail lines must be between 1 and 500")
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > MAX_LOG_TAIL_BYTES:
            handle.seek(size - MAX_LOG_TAIL_BYTES)
        data = handle.read(MAX_LOG_TAIL_BYTES)
    text = data.decode("utf-8", errors="replace")
    selected = text.splitlines()[-lines:]
    return "\n".join(selected)


def collect_status() -> dict[str, Any]:
    source_root = legacy.source_root_from_launcher()
    paths = legacy.resolve_runtime_paths()
    state, malformed = legacy.read_state(paths.state)
    latest = _latest_log(paths.logs)
    lock_payload, lock_error = _read_lock(paths.root / LOCK_NAME)
    lock_active = (
        lock_payload is not None
        and _is_process_alive(int(lock_payload.get("pid", 0)))
    )
    runtime_app = paths.workspace / "desktop" / "localcomet-desktop"
    try:
        running_processes = [
            {"pid": pid, "name": name}
            for pid, name in _running_localcomet_processes()
        ]
        process_check_error = None
    except StartHold as exc:
        running_processes = []
        process_check_error = str(exc)
    return {
        "release": RELEASE,
        "legacy_release": str(getattr(legacy, "RELEASE", "UNKNOWN")),
        "source_root": _path_text(source_root),
        "runtime_root": _path_text(paths.root),
        "workspace_exists": paths.workspace.is_dir(),
        "dependencies_ready": (runtime_app / "node_modules").is_dir(),
        "cargo_target_exists": paths.cargo_target.is_dir(),
        "app_data": _path_text(paths.app_data),
        "app_data_exists": paths.app_data.is_dir(),
        "state_exists": paths.state.is_file(),
        "state_malformed": malformed,
        "package_lock_sha256": state.get("package_lock_sha256"),
        "npm_ci_completed": state.get("npm_ci_completed") is True,
        "synced_file_count": len(
            [item for item in state.get("synced_files", []) if isinstance(item, str)]
        )
        if isinstance(state.get("synced_files"), list)
        else 0,
        "launcher_lock_active": lock_active,
        "launcher_lock_error": lock_error,
        "running_localcomet_processes": running_processes,
        "process_check_error": process_check_error,
        "latest_log": str(latest) if latest is not None else None,
        "source_generated_paths_ignored": all(
            _generated_source_check(source_root, relative).status == "PASS"
            for relative in GENERATED_SOURCE_PATHS
        ),
    }


def _print_report(report: DoctorReport) -> None:
    print(f"LocalComet launch doctor {report.release}")
    print(f"Legacy engine: {report.legacy_release}")
    print(f"Source: {report.source_root}")
    print(f"Runtime: {report.runtime_root}")
    print(f"Development AppData: {report.app_data}")
    print()
    for item in report.checks:
        print(f"[{item.status:5}] {item.name}: {item.detail}")
    print()
    print(
        f"Result: {'PASS' if report.ok else 'HOLD'} "
        f"(errors={report.errors}, warnings={report.warnings})"
    )


def _patched_environment() -> dict[str, str | None]:
    additions = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1",
    }
    previous: dict[str, str | None] = {}
    for key, value in additions.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    return previous


def _restore_environment(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def run_start(*, offline: bool) -> int:
    report = collect_doctor_report(require_free_port=True)
    _print_report(report)
    if not report.ok:
        print("HOLD: launch preflight failed", file=sys.stderr)
        return 2
    if offline and report.dependency_action != "REUSED":
        print(
            "HOLD: --offline requires an already reusable external node_modules",
            file=sys.stderr,
        )
        return 2

    paths = legacy.resolve_runtime_paths()
    previous_env = _patched_environment()
    try:
        with LauncherLock(paths.root):
            print()
            print("Starting the audited external LocalComet development runtime...")
            print("Close the LocalComet window or press Ctrl+C to stop.")
            try:
                result = legacy.main()
            except KeyboardInterrupt:
                return 130
            except SystemExit as exc:
                code = exc.code
                return int(code) if isinstance(code, int) else 1
            return int(result)
    except StartHold as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2
    finally:
        _restore_environment(previous_env)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Safe one-command LocalComet developer launch wrapper over the "
            "isolated external LocalCometDev engine."
        )
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("start", "doctor", "status", "logs"),
        default="start",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable output for doctor or status.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Refuse launch when external npm dependencies must be installed.",
    )
    parser.add_argument(
        "--tail-lines",
        type=int,
        default=DEFAULT_LOG_TAIL_LINES,
        help="Number of lines for the logs command (1-500).",
    )
    parser.add_argument("--version", action="version", version=RELEASE)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "start":
        if args.json:
            print("HOLD: --json is not supported for interactive start", file=sys.stderr)
            return 2
        return run_start(offline=bool(args.offline))

    if args.offline:
        print("HOLD: --offline is only valid with start", file=sys.stderr)
        return 2

    if args.command == "doctor":
        report = collect_doctor_report(require_free_port=False)
        if args.json:
            print(_json_dump(report.to_dict()))
        else:
            _print_report(report)
        return 0 if report.ok else 2

    if args.command == "status":
        status = collect_status()
        if args.json:
            print(_json_dump(status))
        else:
            print("LocalComet launcher status")
            for key, value in status.items():
                print(f"{key}: {value}")
        return 0

    if args.command == "logs":
        if args.json:
            print("HOLD: --json is not supported for logs", file=sys.stderr)
            return 2
        paths = legacy.resolve_runtime_paths()
        latest = _latest_log(paths.logs)
        if latest is None:
            print("No LocalComet launcher logs found.")
            return 0
        try:
            tail = _tail_text(latest, int(args.tail_lines))
        except (OSError, StartHold) as exc:
            print(f"HOLD: {exc}", file=sys.stderr)
            return 2
        print(f"Log: {latest}")
        if tail:
            print(tail)
        return 0

    print("HOLD: unsupported command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
