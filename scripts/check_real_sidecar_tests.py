"""Real-sidecar test honesty gate (Task D).

The real-sidecar integration tests in supervisor.rs skip via early return when
LOCALCOMET_TEST_PROJECT_ROOT / LOCALCOMET_TEST_PYTHON are absent. With
LOCALCOMET_REQUIRE_REAL_SIDECAR set (CI, after installing the sidecar) that
skip becomes a panic, so the suite count can no longer silently include
not-actually-run tests.

This gate enforces the CI contract:
  - Only meaningful when LOCALCOMET_REQUIRE_REAL_SIDECAR is set.
  - Runs only the explicitly named real-sidecar supervisor tests and fails if
    any filtered test is reported "ignored" or if the require-environment panic
    fired (meaning the sidecar was not installed before cargo test).

Exit 0 = contract holds, 1 = violation, 2 = could not run.

CI usage:
  set LOCALCOMET_REQUIRE_REAL_SIDECAR=1
  python scripts/check_real_sidecar_tests.py
"""

import os
import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CARGO_MANIFEST = REPO_ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "Cargo.toml"
REAL_SIDECAR_TEST_FILTER = "supervisor::tests::real_sidecar_"


def main() -> int:
    if os.environ.get("LOCALCOMET_REQUIRE_REAL_SIDECAR") is None:
        print(
            "SKIP: LOCALCOMET_REQUIRE_REAL_SIDECAR not set; gate only enforces in "
            "require mode (CI). Real-sidecar tests skip honestly with a notice."
        )
        return 0

    result = subprocess.run(
        [
            "cargo",
            "test",
            "--manifest-path",
            str(CARGO_MANIFEST),
            "--lib",
            REAL_SIDECAR_TEST_FILTER,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "") + (result.stderr or "")

    problems = []

    ignored_counts = [int(value) for value in re.findall(r"(\d+) ignored", output)]
    ignored_total = sum(ignored_counts)
    if ignored_total > 0:
        problems.append(f"{ignored_total} test(s) reported ignored under require mode")

    if "LOCALCOMET_REQUIRE_REAL_SIDECAR is set but the real-sidecar environment" in output:
        problems.append(
            "real-sidecar tests panicked: sidecar environment missing "
            "(install the sidecar and set LOCALCOMET_TEST_PROJECT_ROOT / "
            "LOCALCOMET_TEST_PYTHON before cargo test)"
        )

    if result.returncode != 0 and not problems:
        problems.append(f"cargo test exited {result.returncode}")

    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1

    print("OK: real-sidecar tests ran under require mode with no silent skips")
    return 0


if __name__ == "__main__":
    sys.exit(main())
