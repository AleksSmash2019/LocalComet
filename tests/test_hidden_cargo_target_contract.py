"""Contract tests for hidden-run Cargo target routing."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_isolated_hidden_desktop_cu as harness  # noqa: E402
from tools.launch_localcomet_dev import canonical_cargo_target_base  # noqa: E402


class HiddenCargoTargetContractTests(unittest.TestCase):
    def test_hidden_target_is_stable_and_external_to_each_isolated_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            parent_appdata = tmp_root / "AppData" / "Local"
            root_a = parent_appdata / "LC_hidden_a"
            root_b = parent_appdata / "LC_hidden_b"
            target_a = harness.resolve_hidden_cargo_target(ROOT, str(parent_appdata))
            target_b = harness.resolve_hidden_cargo_target(ROOT, str(parent_appdata))
            expected_base = canonical_cargo_target_base({"LOCALAPPDATA": str(parent_appdata)})
        self.assertEqual(target_a, target_b)
        self.assertEqual(target_a, expected_base / harness.HIDDEN_CARGO_TARGET_SUBKEY)
        self.assertNotIn(str(root_a).lower(), str(target_a).lower())
        self.assertNotIn(str(root_b).lower(), str(target_a).lower())
        self.assertFalse(target_a.is_relative_to(ROOT.resolve()))

    def test_missing_parent_appdata_fails_closed(self):
        with self.assertRaises(RuntimeError):
            harness.resolve_hidden_cargo_target(ROOT, "")

    def test_harness_has_no_root_specific_target_expression(self):
        source = (ROOT / "tools" / "run_isolated_hidden_desktop_cu.py").read_text(encoding="utf-8")
        self.assertNotIn('f"isolated/{isolated_root.name', source)
        self.assertIn('HIDDEN_CARGO_TARGET_SUBKEY = "hidden-isolated"', source)


if __name__ == "__main__":
    unittest.main()
