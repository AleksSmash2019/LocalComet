"""Regression test for P0-2F: inert mockData allowlist entries must fail."""
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
    "mockdata_imports", ROOT / "scripts" / "check_mockdata_imports.py"
)
assert SPEC and SPEC.loader
mockdata_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mockdata_gate)


class MockdataImportGateTests(unittest.TestCase):
    def test_inert_allowlist_entry_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "desktop" / "localcomet-desktop" / "src"
            source.mkdir(parents=True)
            (source / "live.ts").write_text("export const value = 1;\n", encoding="utf-8")
            output = io.StringIO()
            with (
                patch.object(mockdata_gate, "ROOT", root),
                patch.object(mockdata_gate, "SRC", source),
                patch.object(mockdata_gate, "ALLOWLIST", {"src/unused.ts": "obsolete"}),
                contextlib.redirect_stdout(output),
            ):
                result = mockdata_gate.main()
        self.assertEqual(result, 1)
        self.assertIn("INERT_ALLOWLIST: src/unused.ts", output.getvalue())

    def test_multiline_relative_import_is_a_violation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "desktop" / "localcomet-desktop" / "src"
            mock_data = source / "lib" / "data" / "mockData.ts"
            rogue = source / "lib" / "components" / "rogue.ts"
            mock_data.parent.mkdir(parents=True)
            rogue.parent.mkdir(parents=True)
            mock_data.write_text("export const example = 1;\n", encoding="utf-8")
            rogue.write_text(
                "import {\n  example\n} from '../data/mockData';\nexport { example };\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with (
                patch.object(mockdata_gate, "ROOT", root),
                patch.object(mockdata_gate, "SRC", source),
                patch.object(mockdata_gate, "MOCK_DATA_SOURCE", mock_data),
                patch.object(mockdata_gate, "ALLOWLIST", {}),
                contextlib.redirect_stdout(output),
            ):
                result = mockdata_gate.main()
        self.assertEqual(result, 1)
        self.assertIn("VIOLATION: src/lib/components/rogue.ts", output.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
