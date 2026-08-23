"""Regression tests for out-of-band Computer Use turn correlation."""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules import local_model_gateway_ru as module


class ComputerUseCorrelationTests(unittest.TestCase):
    def test_correlation_does_not_mutate_model_arguments(self) -> None:
        request = types.SimpleNamespace(request_id="0123456789abcdef01234567")
        call = {
            "id": "call_0123456789abcdef0123456789ab",
            "name": "computer_use",
            "arguments": {"action": "open_app", "target": "notepad"},
        }

        correlated = module._correlate_tool_calls(request, [call])

        self.assertEqual(correlated, [call])
        self.assertNotIn("request_id", correlated[0]["arguments"])
        self.assertNotIn("action_id", correlated[0]["arguments"])

    def test_request_id_in_model_arguments_is_still_schema_invalid(self) -> None:
        with self.assertRaises(module.GatewayError):
            module.validate_tool_call(
                "computer_use",
                {
                    "action": "open_app",
                    "target": "notepad",
                    "request_id": "0123456789abcdef01234567",
                },
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
