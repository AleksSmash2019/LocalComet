"""Regression tests for the real-sidecar CI honesty gate."""
from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import check_real_sidecar_tests  # noqa: E402


class RealSidecarGateTests(unittest.TestCase):
    def run_gate(self, result: subprocess.CompletedProcess[str]) -> tuple[int, list[str]]:
        with patch.dict("os.environ", {"LOCALCOMET_REQUIRE_REAL_SIDECAR": "1"}, clear=True), patch(
            "check_real_sidecar_tests.subprocess.run", return_value=result
        ) as run:
            status = check_real_sidecar_tests.main()
        return status, run.call_args.args[0]

    def test_later_ignored_cargo_summary_fails_require_mode(self) -> None:
        result = subprocess.CompletedProcess(
            ["cargo", "test"],
            0,
            stdout="running 1 test\ntest result: ok. 1 passed; 0 failed; 0 ignored\n"
            "running 2 tests\ntest result: ok. 0 passed; 0 failed; 2 ignored\n",
            stderr="",
        )
        status, _ = self.run_gate(result)
        self.assertEqual(status, 1)

    def test_command_exactly_filters_real_sidecar_supervisor_tests(self) -> None:
        result = subprocess.CompletedProcess(["cargo", "test"], 0, stdout="", stderr="")
        status, command = self.run_gate(result)
        self.assertEqual(status, 0)
        self.assertEqual(
            command,
            [
                "cargo",
                "test",
                "--manifest-path",
                str(check_real_sidecar_tests.CARGO_MANIFEST),
                "--lib",
                "supervisor::tests::real_sidecar_",
            ],
        )

    def test_correct_filtered_run_passes_require_mode(self) -> None:
        result = subprocess.CompletedProcess(
            ["cargo", "test"],
            0,
            stdout="test result: ok. 1 passed; 0 failed; 0 ignored\n"
            "test result: ok. 2 passed; 0 failed; 0 ignored\n",
            stderr="",
        )
        status, _ = self.run_gate(result)
        self.assertEqual(status, 0)

    def test_missing_environment_panic_still_fails_require_mode(self) -> None:
        result = subprocess.CompletedProcess(
            ["cargo", "test"],
            101,
            stdout="",
            stderr="LOCALCOMET_REQUIRE_REAL_SIDECAR is set but the real-sidecar environment",
        )
        status, _ = self.run_gate(result)
        self.assertEqual(status, 1)


if __name__ == "__main__":
    unittest.main()
