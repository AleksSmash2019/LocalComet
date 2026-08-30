"""Focused tests for the deterministic worker --use-intent dispatch seam.

Offline contract only: these verify the pure helpers (expression builder,
verdict classifier). The live hidden dispatch itself is a separate bounded
harness run and is never claimed by these tests.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_isolated_hidden_desktop_cu import (  # noqa: E402
    INTENT_DISPATCH_PROMPT,
    build_intent_dispatch_expression,
    classify_intent_dispatch_result,
)

import unittest  # noqa: E402


class TestExpressionBuilder(unittest.TestCase):
    def test_contains_real_command_chain(self):
        expr = build_intent_dispatch_expression(INTENT_DISPATCH_PROMPT)
        for command in (
            "intent_compile",
            "request_approval",
            "resolve_tool_approval",
            "run_tool_call",
        ):
            assert command in expr, f"missing real command {command}"

    def test_prompt_embedded_as_json_not_interpolated(self):
        evil = 'РћС‚РєСЂРѕР№ https://a"; process.exit();//'
        expr = build_intent_dispatch_expression(evil)
        assert json.dumps(evil, ensure_ascii=False) in expr
        assert evil + '"' not in expr  # never raw interpolation

    def test_deterministic_shape(self):
        a = build_intent_dispatch_expression("x")
        b = build_intent_dispatch_expression("x")
        assert a == b

    def test_no_calculator_anywhere(self):
        expr = build_intent_dispatch_expression(INTENT_DISPATCH_PROMPT)
        assert "calc" not in expr.lower()

    def test_uses_internals_bridge_not_model(self):
        expr = build_intent_dispatch_expression(INTENT_DISPATCH_PROMPT)
        assert "__TAURI_INTERNALS__" in expr


class TestClassifier(unittest.TestCase):
    def test_completed_verified_success(self):
        payload = {
            "result": {
                "status": "completed",
                "verification": "verified",
                "execution": {"continuation": {"grant_ref": "cgr_ab"}},
            }
        }
        outcome, classification = classify_intent_dispatch_result(payload)
        assert outcome == "COMPLETED_VERIFIED"
        assert classification == "VERIFIED_SUCCESS"

    def test_launch_pending_is_pending_terminal_never_success(self):
        payload = {"result": {"status": "launch_pending", "verification": "pending", "execution": {}}}
        outcome, classification = classify_intent_dispatch_result(payload)
        assert outcome == "LAUNCH_PENDING_OBSERVED"
        assert classification == "PENDING_TERMINAL"

    def test_broker_blocked_is_blocked(self):
        payload = {"result": {"status": "blocked", "execution": {}}}
        _, classification = classify_intent_dispatch_result(payload)
        assert classification == "VERIFIED_BLOCKED"

    def test_broker_failed_is_failed(self):
        payload = {"result": {"status": "failed", "execution": {}}}
        _, classification = classify_intent_dispatch_result(payload)
        assert classification == "VERIFIED_FAILED"

    def test_error_payload_is_blocked(self):
        _, classification = classify_intent_dispatch_result({"error": "approval_denied"})
        assert classification == "VERIFIED_BLOCKED"

    def test_no_evidence_is_not_independently_verified(self):
        _, classification = classify_intent_dispatch_result({})
        assert classification == "NOT_INDEPENDENTLY_VERIFIED"

    def test_non_dict_is_malformed(self):
        _, classification = classify_intent_dispatch_result(None)
        assert classification == "MALFORMED_RESULT"


if __name__ == "__main__":
    import unittest

    suite = unittest.TestLoader().loadTestsFromTestCase(TestExpressionBuilder)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestClassifier))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
