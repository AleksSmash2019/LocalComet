"""Regression tests for P0-2D sidecar execution-risk coverage."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tool_risk_registry", ROOT / "scripts" / "check_tool_risk_registry.py"
)
assert SPEC and SPEC.loader
risk_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(risk_gate)


class ToolRiskRegistryGateTests(unittest.TestCase):
    def test_static_sidecar_dispatch_vocabulary_is_extracted(self) -> None:
        source = 'SUPPORTED_TOOLS = frozenset(("files.read", "files.write"))\n'
        self.assertEqual(risk_gate.parse_supported_tools(source), {"files.read", "files.write"})

    def test_dynamic_sidecar_dispatch_vocabulary_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            risk_gate.parse_supported_tools("SUPPORTED_TOOLS = load_tools()\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
