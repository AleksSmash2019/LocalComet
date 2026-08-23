import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for path in (ROOT, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_isolated_hidden_desktop_cu import (  # noqa: E402
    classify_case,
    validate_correlation,
    validate_screenshot_evidence,
    _uia_control_text,
)


REQUEST_ID = "0123456789abcdef01234567"
MODEL_ACTION_ID = "call_0123456789abcdef0123456789ab"
APPROVAL_PROMPT_ID = "appr_0123456789abcdef0123456789abcdef"
APPROVAL_ID = "appr_abcdef0123456789abcdef0123456789"
APPROVAL_CALL_ID = "call_abcdef0123456789abcdef0123456789"
INPUT_DIGEST = "a" * 64
SCREENSHOT_SHA = "b" * 64


class _ReaderRange:
    def GetText(self, _length):
        return "LocalComet isolated smoke test."


class _ReaderTextPattern:
    DocumentRange = _ReaderRange()


class _ReaderValuePattern:
    Value = "LocalComet isolated smoke test."


class _DirectReaderControl:
    Name = ""

    def GetTextPattern(self):
        return _ReaderTextPattern()

    def GetValuePattern(self):
        return _ReaderValuePattern()

    def GetPattern(self, _pattern_id):
        raise AssertionError("generic PatternId path should not be needed")


class _PatternIds:
    TextPattern = 10014
    ValuePattern = 10002


class HiddenEvidenceContractTests(unittest.TestCase):
    def test_read_only_text_reader_accepts_direct_uia_patterns(self):
        values = _uia_control_text(_DirectReaderControl(), _PatternIds())
        self.assertIn(("uia_text_pattern", "LocalComet isolated smoke test."), values)
        self.assertIn(("uia_value_pattern", "LocalComet isolated smoke test."), values)

    def test_correlation_requires_real_ids_and_prompt_matches_model_event(self):
        observation = {
            "approval_prompt": {
                "approval_request_id": APPROVAL_PROMPT_ID,
                "model_request_id": REQUEST_ID,
                "model_action_id": MODEL_ACTION_ID,
            }
        }
        evidence = {
            "request_id": REQUEST_ID,
            "action_id": MODEL_ACTION_ID,
            "approval_id": APPROVAL_ID,
            "approval_call_id": APPROVAL_CALL_ID,
            "input_digest": INPUT_DIGEST,
        }
        result = validate_correlation(observation, evidence, approvals=1)
        failed_checks = [key for key, value in result["checks"].items() if not value]
        self.assertEqual(failed_checks, [], result["checks"])
        self.assertEqual(result["status"], "validated", result)

    def test_correlation_missing_ids_is_incomplete_not_green(self):
        result = validate_correlation(
            {"approval_prompt": {"approval_request_id": APPROVAL_PROMPT_ID}},
            {"request_id": "not-exposed", "action_id": "", "approval_id": "", "approval_call_id": "", "input_digest": ""},
            approvals=1,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "incomplete")

    def test_screenshot_requires_present_png_evidence_metadata(self):
        valid = validate_screenshot_evidence({
            "screenshot_present": True,
            "screenshot_sha256": SCREENSHOT_SHA,
            "screenshot_backend": "printwindow",
            "screenshot_scope": "window",
            "screenshot_bytes": "1234",
        })
        self.assertTrue(valid["ok"])
        invalid = validate_screenshot_evidence({
            "screenshot_present": True,
            "screenshot_sha256": "",
            "screenshot_backend": "",
            "screenshot_scope": "",
            "screenshot_bytes": "0",
        })
        self.assertFalse(invalid["ok"])

    def test_pass_requires_text_and_screenshot_proof_when_requested(self):
        self.assertEqual(
            classify_case("PASS", 1, True, correlation_ok=True, text_ok=False),
            "NOT_INDEPENDENTLY_VERIFIED",
        )
        self.assertEqual(
            classify_case("PASS", 0, True, correlation_ok=True, screenshot_ok=False),
            "NOT_INDEPENDENTLY_VERIFIED",
        )
        self.assertEqual(
            classify_case("PASS", 1, True, correlation_ok=True, text_ok=True, screenshot_ok=True),
            "VERIFIED_SUCCESS",
        )


if __name__ == "__main__":
    unittest.main()
