from __future__ import annotations

import argparse
import concurrent.futures
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop" / "localcomet-desktop"
RUST = DESKTOP / "src-tauri"
PYTHON = os.environ.get("LOCALCOMET_TEST_PYTHON") or sys.executable

MODEL_PY = [
    "tools/test_up05_wp01_model_chat_backend.py",
    "tools/test_v6845_model_gateway.py",
    "tools/test_v68451e4_knowledge_adapter.py",
    "tools/test_v68451e5_knowledge_control_plane.py",
    "tools/test_v68451e6_knowledge_injection.py",
    "tools/test_v68451e7_desktop_knowledge_preview.py",
    "tools/test_v68451e7b_sse_utf8_decoder.py",
]
MODEL_TS = [
    "tests/model-gateway.test.ts",
    "tests/chat-reliability.test.ts",
    "tests/p0c-sidecar-health.test.ts",
]
SECURITY_PY = [
    "tests/test_files_rollback.py",
    "tests/test_files_safe_path.py",
    "tests/test_skill_entrypoints_security.py",
    "tools/test_p0a_legacy_quarantine.py",
    "tools/test_up02_wp01_security_negative.py",
    "tools/test_t13_injection_and_approval.py",
    "tools/test_tool_risk_rust_parity.py",
    "tools/test_v6802_bundle_security.py",
]


def run(label: str, command: Sequence[str], cwd: Path) -> int:
    started = time.perf_counter()
    try:
        p = subprocess.run(list(command), cwd=str(cwd), text=True, capture_output=True,
                           encoding="utf-8", errors="replace")
        output = (p.stdout or "") + (p.stderr or "")
    except OSError as exc:
        print(f"[{label}] launch error: {exc}", flush=True)
        return 127
    print(f"\n=== {label} ({time.perf_counter() - started:.2f}s, exit={p.returncode}) ===", flush=True)
    if output.strip():
        print(output.rstrip(), flush=True)
    return p.returncode


def parallel(items: Sequence[tuple[str, Sequence[str], Path]]) -> list[int]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(items)) as pool:
        return [f.result() for f in [pool.submit(run, *item) for item in items]]


def py(script: str, *args: str) -> list[str]:
    return [PYTHON, str(ROOT / script), *args]


def npm(*args: str) -> list[str]:
    return ["npm.cmd" if os.name == "nt" else "npm", *args]


def cargo(*args: str) -> list[str]:
    return ["cargo", *args]


def frontend(targets: Sequence[str] | None = None, check: bool = False) -> list[int]:
    items: list[tuple[str, Sequence[str], Path]] = []
    if check:
        items.append(("frontend check", npm("run", "check"), DESKTOP))
    test = npm("test")
    if targets:
        test += ["--", *targets]
    items.append(("frontend Vitest", test, DESKTOP))
    return parallel(items)


def python_tests(files: Sequence[str]) -> list[int]:
    results: list[int] = []
    for name in files:
        path = ROOT / name
        if path.exists():
            results.append(run(name, py(name), ROOT))
        else:
            print(f"[skip] missing {name}", flush=True)
    return results


def fast() -> list[int]:
    return parallel([
        ("frontend Vitest", npm("test"), DESKTOP),
        ("Rust tests", cargo("test"), RUST),
    ])


def model() -> list[int]:
    return frontend(MODEL_TS) + python_tests(MODEL_PY)


def security() -> list[int]:
    return python_tests(SECURITY_PY)


def changed() -> list[int]:
    paths: set[str] = set()
    for cmd in (["git", "diff", "--name-only", "HEAD"], ["git", "ls-files", "--others", "--exclude-standard"]):
        p = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, encoding="utf-8", errors="replace")
        if p.returncode == 0:
            paths.update(x.strip().replace("/", "\\") for x in p.stdout.splitlines() if x.strip())
    paths = {x for x in paths if not x.lower().startswith("audit\\") or x.lower().endswith(".py")}
    if not paths: return []
    print("Affected paths:", *sorted(paths), sep="\n  ", flush=True)
    low = [x.lower() for x in paths]
    core = any(x in {"run-gates.ps1", "package-lock.json"} or x.endswith("\\cargo.toml")
               or x.endswith("\\cargo.lock") or x.endswith("\\package.json")
               or "security\\contracts\\" in x for x in low)
    if core:
        return full()
    results: list[int] = []
    if any(x.startswith("desktop\\localcomet-desktop\\src\\")
           or x.startswith("desktop\\localcomet-desktop\\tests\\")
           or x.endswith("\\vitest.config.ts") for x in low):
        results += frontend(check=True)
    if any(x.startswith("desktop\\localcomet-desktop\\src-tauri\\") for x in low):
        results += parallel([
            ("Rust format", cargo("fmt", "--check"), RUST),
            ("Rust tests", cargo("test"), RUST),
        ])
    pyfiles = [x for x in paths if x.lower().endswith(".py")]
    if pyfiles:
        results.append(run("Python syntax", [PYTHON, "-m", "py_compile", *[str(ROOT / x) for x in pyfiles]], ROOT))
        results += python_tests([x for x in pyfiles if Path(x).name.startswith("test_")])
        if any(any(k in x.lower() for k in ("local_model_gateway", "v6845", "sidecar")) for x in pyfiles):
            results += model()
    return results or fast()


def full() -> list[int]:
    powershell = os.environ.get("LOCALCOMET_POWERSHELL", "powershell.exe")
    return [run("full 69-gate audit", [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                                        "-File", str(ROOT / "Run-Gates.ps1")], ROOT)]


def main() -> int:
    parser = argparse.ArgumentParser(description="LocalComet layered development test runner")
    parser.add_argument("--profile", choices=("fast", "affected", "frontend", "model", "security", "full"), default="fast")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list:
        print("fast: frontend Vitest + cargo test in parallel")
        print("affected: changed-file routing; core/lock/contract changes escalate to full")
        print("frontend: npm check + Vitest in parallel")
        print("model: focused model UI tests + local-model/knowledge Python gates")
        print("security: focused filesystem, approval, injection, risk and bundle gates")
        print("full: unchanged Run-Gates.ps1 69-gate audit")
        return 0
    results = {"fast": fast, "affected": changed, "frontend": lambda: frontend(check=True),
               "model": model, "security": security, "full": full}[args.profile]()
    failed = sum(code != 0 for code in results)
    print(f"\nProfile {args.profile}: {len(results) - failed} passed, {failed} failed.", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())