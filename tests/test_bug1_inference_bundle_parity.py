"""Regression tests for the deployed Bug#1 bundle-parity guard."""
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
    "test_bug1_inference_bundle_parity_script",
    ROOT / "tools" / "test_bug1_inference_bundle_parity.py",
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class Bug1BundleParityTests(unittest.TestCase):
    def test_default_deployed_root_is_supported_localcometdev_runtime(self) -> None:
        with patch.dict(module.os.environ, {"LOCALAPPDATA": r"C:\Users\Test"}, clear=True):
            self.assertEqual(
                module.deployed_bundle_modules_dir(),
                Path(r"C:\Users\Test\LocalCometDev\workspace\modules"),
            )

    def test_missing_localappdata_is_an_error(self) -> None:
        with patch.dict(module.os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "LOCALAPPDATA is not set"):
                module.deployed_bundle_modules_dir()

    def test_missing_deployed_bundle_is_failure_not_skip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing-modules"
            output = io.StringIO()
            with (
                patch.object(module, "deployed_bundle_modules_dir", return_value=missing),
                contextlib.redirect_stdout(output),
            ):
                result = module.check_deployed_bundle([])
            self.assertFalse(result)
            self.assertIn("PART B FAIL", output.getvalue())
            self.assertNotIn("SKIP", output.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
