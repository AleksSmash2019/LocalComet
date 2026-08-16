from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class GateResult:
    gate_id: str
    command: list[str]
    cwd: str
    exit_code: int | None
    timed_out: bool
    duration_seconds: float
    log_path: str
    passed: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_gate(
    *,
    gate_id: str,
    command: list[str],
    cwd: Path,
    log_dir: Path,
    timeout_seconds: int,
    env: dict[str, str],
) -> GateResult:
    started = time.monotonic()
    exit_code: int | None = None
    timed_out = False
    log_path = log_dir / f"{gate_id}.log"
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        exit_code = completed.returncode
        output = completed.stdout
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        output = (exc.stdout or "") + "\n[TIMEOUT after %ss]\n" % timeout_seconds
    except OSError as exc:
        output = f"[PROCESS ERROR] {type(exc).__name__}: {exc}\n"
        exit_code = 127
    duration = time.monotonic() - started
    log_path.write_text(output, encoding="utf-8")
    return GateResult(
        gate_id=gate_id,
        command=command,
        cwd=str(cwd),
        exit_code=exit_code,
        timed_out=timed_out,
        duration_seconds=round(duration, 3),
        log_path=str(log_path),
        passed=(not timed_out and exit_code == 0),
    )


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    rust = root / "desktop" / "localcomet-desktop" / "src-tauri"
    frontend = root / "desktop" / "localcomet-desktop"
    audit_root = root / "AUDIT_ROOT" / "final_regression"
    log_dir = audit_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("CI", "1")
    env.setdefault("VITEST_POOL_SIZE", "1")
    python_executable = env.get(
        "LOCALCOMET_TEST_PYTHON",
        r"C:\Users\DNS\AppData\Local\Python\bin\python.exe",
    )

    gates: list[tuple[str, list[str], Path, int]] = [
        ("RUST_DEBUG_ALL_FEATURES", ["cargo", "test", "--all-features"], rust, 1800),
        ("RUST_RELEASE_ALL_FEATURES", ["cargo", "test", "--release", "--all-features"], rust, 2400),
        ("RUST_FMT_CHECK", ["cargo", "fmt", "--all", "--", "--check"], rust, 300),
        ("RUST_CLIPPY", ["cargo", "clippy", "--all-features", "--all-targets", "--", "-D", "warnings"], rust, 1800),
        ("FRONTEND_VITEST", ["npm.cmd", "test", "--", "--run"], frontend, 900),
        ("FRONTEND_SVELTE_CHECK", ["npm.cmd", "run", "check"], frontend, 900),
        ("PYTHON_COMPILE_CHANGED", [python_executable, "-m", "py_compile", "modules/workspace_memory_ru.py", "modules/screen_context_policy.py", "modules/browser_safety_policy.py", "modules/tool_execution_ru.py", "tools/test_workspace_memory_ru.py", "tools/test_phase_e_safety.py"], root, 300),
        ("PYTEST_FULL", [python_executable, "-m", "pytest", "-q"], root, 2400),
        ("GIT_DIFF_CHECK", ["git", "diff", "--check"], root, 300),
    ]

    results: list[GateResult] = []
    for gate_id, command, cwd, timeout_seconds in gates:
        result = run_gate(
            gate_id=gate_id,
            command=command,
            cwd=cwd,
            log_dir=log_dir,
            timeout_seconds=timeout_seconds,
            env=env,
        )
        results.append(result)
        print(json.dumps(asdict(result), ensure_ascii=False), flush=True)

    tracked_status = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    ).stdout
    status_path = audit_root / "git-status-final.txt"
    status_path.write_text(tracked_status, encoding="utf-8")

    payload = {
        "protocol": "prompt-v3-full-regression",
        "created_at_unix": int(time.time()),
        "root": str(root),
        "python": sys.executable,
        "results": [asdict(result) for result in results],
        "all_passed": all(result.passed for result in results),
        "git_status_path": str(status_path),
    }
    result_path = audit_root / "RESULTS.json"
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"results_path": str(result_path), "all_passed": payload["all_passed"]}, ensure_ascii=False), flush=True)
    return 0 if payload["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
