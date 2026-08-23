"""Regression tests for P0-2A bundle-parity blind spot."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_bundle_parity", ROOT / "scripts" / "check_bundle_parity.py"
)
assert SPEC and SPEC.loader
check_bundle_parity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_bundle_parity)


class BundleParityGateTests(unittest.TestCase):
    def _write_modules(self, root: Path, names: set[str]) -> None:
        for name in names:
            (root / name).write_text(f"# {name}\n", encoding="utf-8")

    def test_missing_required_shipped_module_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo_modules = root / "repo"
            shipped_modules = root / "shipped"
            repo_modules.mkdir()
            shipped_modules.mkdir()
            required = {"alpha.py", "beta.py"}
            self._write_modules(repo_modules, required)
            self._write_modules(shipped_modules, {"alpha.py"})
            output = io.StringIO()
            with (
                patch.object(check_bundle_parity, "REPO_MODULES", repo_modules),
                patch.object(check_bundle_parity, "REQUIRED_SIDECAR_MODULES", frozenset(required)),
                contextlib.redirect_stdout(output),
            ):
                matched, stale, missing_in_repo, missing_in_shipped = check_bundle_parity.check_location(
                    "test", shipped_modules
                )
            self.assertEqual((matched, stale, missing_in_repo), (1, [], []))
            self.assertEqual(missing_in_shipped, ["beta.py"])
            self.assertIn("MISSING_IN_SHIPPED: beta.py", output.getvalue())

    def test_complete_identical_shipped_subset_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo_modules = root / "repo"
            shipped_modules = root / "shipped"
            repo_modules.mkdir()
            shipped_modules.mkdir()
            required = {"alpha.py", "beta.py"}
            self._write_modules(repo_modules, required)
            self._write_modules(shipped_modules, required)
            with (
                patch.object(check_bundle_parity, "REPO_MODULES", repo_modules),
                patch.object(check_bundle_parity, "REQUIRED_SIDECAR_MODULES", frozenset(required)),
            ):
                matched, stale, missing_in_repo, missing_in_shipped = check_bundle_parity.check_location(
                    "test", shipped_modules
                )
            self.assertEqual(matched, 2)
            self.assertEqual((stale, missing_in_repo, missing_in_shipped), ([], [], []))

    def test_default_deployed_root_is_the_supported_runtime(self) -> None:
        with patch.dict(check_bundle_parity.os.environ, {"LOCALAPPDATA": r"C:\\Users\\Test"}, clear=True):
            self.assertEqual(
                check_bundle_parity.deployed_modules(),
                Path(r"C:\\Users\\Test\\LocalCometDev\\workspace\\modules"),
            )

    def test_missing_localappdata_is_hard_failure(self) -> None:
        with patch.dict(check_bundle_parity.os.environ, {}, clear=True):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = check_bundle_parity.main()
            self.assertEqual(result, 2)
            self.assertIn("FAIL: LOCALAPPDATA is not set", output.getvalue())
            self.assertNotIn("SKIP:", output.getvalue())

    def test_missing_required_location_is_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo_modules = root / "repo"
            build_modules = root / "build"
            missing_deployed_modules = root / "missing-deployed"
            repo_modules.mkdir()
            build_modules.mkdir()
            required = {"alpha.py"}
            self._write_modules(repo_modules, required)
            self._write_modules(build_modules, required)
            output = io.StringIO()
            with (
                patch.object(check_bundle_parity, "REPO_MODULES", repo_modules),
                patch.object(check_bundle_parity, "BUILD_SOURCE_MODULES", build_modules),
                patch.object(check_bundle_parity, "REQUIRED_SIDECAR_MODULES", frozenset(required)),
                patch.object(check_bundle_parity, "REQUIRED_SKILL_FILES", frozenset()),
                patch.object(
                    check_bundle_parity,
                    "deployed_modules",
                    lambda: missing_deployed_modules,
                ),
                contextlib.redirect_stdout(output),
            ):
                result = check_bundle_parity.main()
            self.assertEqual(result, 2)
            self.assertIn("FAIL: [deployed] required shipped modules not found", output.getvalue())
            self.assertNotIn("SKIP:", output.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
