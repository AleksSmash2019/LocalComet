"""Run LocalComet's deterministic hidden quality tiers without desktop interaction.

Default: Computer Use contracts and the Svelte user-journey contract.
Optional ``--runtime-smoke``: the pre-existing isolated Qwen3-1.7B llama.cpp
smoke (it starts and stops only a loopback test server on port 18081).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "desktop" / "localcomet-desktop"


def run(label: str, command: list[str], *, cwd: Path) -> None:
    print(f"[quality] {label}", flush=True)
    completed = subprocess.run(command, cwd=str(cwd), check=False)
    if completed.returncode != 0:
        raise SystemExit(f"[quality] FAILED {label}: exit={completed.returncode}")
    print(f"[quality] PASS {label}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run hidden LocalComet quality tiers")
    parser.add_argument(
        "--runtime-smoke",
        action="store_true",
        help="also run the isolated Qwen3-1.7B llama.cpp smoke on port 18081",
    )
    args = parser.parse_args()

    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("[quality] npm is required for the Svelte user-journey test")

    run(
        "computer-use reliability",
        [sys.executable, "tests/test_computer_use_reliability.py"],
        cwd=ROOT,
    )
    run(
        "computer-use quality contracts",
        [sys.executable, "tests/test_computer_use_quality_contracts.py"],
        cwd=ROOT,
    )
    run(
        "UI user-journey contracts",
        [npm, "test", "--", "--run", "tests/user-journey-quality.test.ts"],
        cwd=FRONTEND,
    )
    if args.runtime_smoke:
        run(
            "isolated Qwen3-1.7B runtime smoke",
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tests/hidden_llama_runtime_smoke.ps1"],
            cwd=ROOT,
        )
    print("[quality] all requested hidden tiers passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
