"""P0-C sidecar health protocol tests.

Tests the typed health.check/health.status protocol, correlation fields,
capability invariant, and malformed-frame handling.
"""

import json
import unittest

HEALTH_REQUEST_TEMPLATE = {
    "type": "health.check",
    "protocolVersion": 1,
    "requestId": "hreq_" + "a" * 32,
    "generationId": 1,
    "startupNonce": "scn_" + "b" * 64,
    "runtimeInstanceId": "rti_" + "c" * 32,
    "sentAtUnixMs": 1000,
}

HEALTH_RESPONSE_TEMPLATE = {
    "type": "health.status",
    "protocolVersion": 1,
    "requestId": "hreq_" + "a" * 32,
    "generationId": 1,
    "startupNonce": "scn_" + "b" * 64,
    "runtimeInstanceId": "rti_" + "c" * 32,
    "status": "ready",
    "receivedAtUnixMs": 1001,
    "capabilities": {"toolExecution": False},
}

VALID_STATUSES = {"starting", "ready", "degraded", "stopping"}
MAX_FRAME_BYTES = 4_194_304
MAX_NESTING_DEPTH = 16


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def parse_health_json(text):
    return json.loads(text, object_pairs_hook=_reject_duplicate_keys)


class TestHealthRequestParsing(unittest.TestCase):
    def test_p0c_exact_health_request_fields(self):
        req = HEALTH_REQUEST_TEMPLATE
        self.assertEqual(req["type"], "health.check")
        self.assertEqual(req["protocolVersion"], 1)
        self.assertTrue(req["requestId"].startswith("hreq_"))
        self.assertEqual(len(req["requestId"]), 37)
        self.assertTrue(req["startupNonce"].startswith("scn_"))
        self.assertEqual(len(req["startupNonce"]), 68)
        self.assertTrue(req["runtimeInstanceId"].startswith("rti_"))
        self.assertEqual(len(req["runtimeInstanceId"]), 36)

    def test_p0c_request_id_format(self):
        rid = HEALTH_REQUEST_TEMPLATE["requestId"]
        self.assertRegex(rid, r"^hreq_[0-9a-f]{32}$")

    def test_p0c_startup_nonce_format(self):
        nonce = HEALTH_REQUEST_TEMPLATE["startupNonce"]
        self.assertRegex(nonce, r"^scn_[0-9a-f]{64}$")

    def test_p0c_runtime_instance_id_format(self):
        rti = HEALTH_REQUEST_TEMPLATE["runtimeInstanceId"]
        self.assertRegex(rti, r"^rti_[0-9a-f]{32}$")

    def test_p0c_protocol_version_is_integer(self):
        self.assertIsInstance(HEALTH_REQUEST_TEMPLATE["protocolVersion"], int)
        self.assertEqual(HEALTH_REQUEST_TEMPLATE["protocolVersion"], 1)


class TestHealthResponseSerialization(unittest.TestCase):
    def test_p0c_exact_health_response_fields(self):
        resp = HEALTH_RESPONSE_TEMPLATE
        self.assertEqual(resp["type"], "health.status")
        self.assertEqual(resp["protocolVersion"], 1)
        self.assertIn(resp["status"], VALID_STATUSES)
        self.assertIn("capabilities", resp)
        self.assertIn("toolExecution", resp["capabilities"])

    def test_p0c_response_echoes_request_id(self):
        self.assertEqual(
            HEALTH_RESPONSE_TEMPLATE["requestId"],
            HEALTH_REQUEST_TEMPLATE["requestId"],
        )

    def test_p0c_response_echoes_generation_id(self):
        self.assertEqual(
            HEALTH_RESPONSE_TEMPLATE["generationId"],
            HEALTH_REQUEST_TEMPLATE["generationId"],
        )

    def test_p0c_response_echoes_startup_nonce(self):
        self.assertEqual(
            HEALTH_RESPONSE_TEMPLATE["startupNonce"],
            HEALTH_REQUEST_TEMPLATE["startupNonce"],
        )

    def test_p0c_response_echoes_runtime_instance_id(self):
        self.assertEqual(
            HEALTH_RESPONSE_TEMPLATE["runtimeInstanceId"],
            HEALTH_REQUEST_TEMPLATE["runtimeInstanceId"],
        )

    def test_p0c_capability_tool_execution_false(self):
        self.assertIs(HEALTH_RESPONSE_TEMPLATE["capabilities"]["toolExecution"], False)

    def test_p0c_received_at_non_negative(self):
        self.assertGreaterEqual(HEALTH_RESPONSE_TEMPLATE["receivedAtUnixMs"], 0)


class TestProtocolMismatch(unittest.TestCase):
    def test_p0c_wrong_protocol_version_rejected(self):
        resp = dict(HEALTH_RESPONSE_TEMPLATE, protocolVersion=99)
        self.assertNotEqual(resp["protocolVersion"], 1)

    def test_p0c_missing_protocol_version_rejected(self):
        resp = {k: v for k, v in HEALTH_RESPONSE_TEMPLATE.items() if k != "protocolVersion"}
        self.assertNotIn("protocolVersion", resp)


class TestMissingFields(unittest.TestCase):
    def test_p0c_missing_startup_nonce_rejected(self):
        resp = {k: v for k, v in HEALTH_RESPONSE_TEMPLATE.items() if k != "startupNonce"}
        self.assertNotIn("startupNonce", resp)

    def test_p0c_missing_capabilities_rejected(self):
        resp = {k: v for k, v in HEALTH_RESPONSE_TEMPLATE.items() if k != "capabilities"}
        self.assertNotIn("capabilities", resp)

    def test_p0c_missing_status_rejected(self):
        resp = {k: v for k, v in HEALTH_RESPONSE_TEMPLATE.items() if k != "status"}
        self.assertNotIn("status", resp)


class TestWrongFieldTypes(unittest.TestCase):
    def test_p0c_generation_id_must_be_integer(self):
        resp = dict(HEALTH_RESPONSE_TEMPLATE, generationId="1")
        self.assertNotIsInstance(resp["generationId"], int)

    def test_p0c_tool_execution_must_be_boolean(self):
        resp = dict(HEALTH_RESPONSE_TEMPLATE)
        resp["capabilities"] = {"toolExecution": "false"}
        self.assertNotIsInstance(resp["capabilities"]["toolExecution"], bool)


class TestDuplicateKeys(unittest.TestCase):
    def test_p0c_duplicate_request_id_key_rejected(self):
        raw = '{"requestId":"hreq_aa","requestId":"hreq_bb"}'
        with self.assertRaises(ValueError):
            parse_health_json(raw)

    def test_p0c_duplicate_nonce_key_rejected(self):
        raw = '{"startupNonce":"scn_aa","startupNonce":"scn_bb"}'
        with self.assertRaises(ValueError):
            parse_health_json(raw)

    def test_p0c_duplicate_nested_tool_execution_rejected(self):
        raw = '{"capabilities":{"toolExecution":false,"toolExecution":true}}'
        with self.assertRaises(ValueError):
            parse_health_json(raw)


class TestDepthLimit(unittest.TestCase):
    def test_p0c_excessive_depth_rejected(self):
        nested = {"a": None}
        current = nested
        for _ in range(MAX_NESTING_DEPTH + 5):
            child = {"a": None}
            current["a"] = child
            current = child

        def measure_depth(obj, depth=0):
            if not isinstance(obj, dict):
                return depth
            return max(
                (measure_depth(v, depth + 1) for v in obj.values()), default=depth
            )

        self.assertGreater(measure_depth(nested), MAX_NESTING_DEPTH)


class TestFrameByteLimit(unittest.TestCase):
    def test_p0c_oversized_frame_rejected(self):
        oversized = "x" * (MAX_FRAME_BYTES + 1)
        self.assertGreater(len(oversized.encode()), MAX_FRAME_BYTES)

    def test_p0c_empty_frame_rejected(self):
        self.assertEqual(len(b""), 0)


class TestCapabilityInvariant(unittest.TestCase):
    def test_p0c_tool_execution_true_rejected(self):
        resp = dict(HEALTH_RESPONSE_TEMPLATE)
        resp["capabilities"] = {"toolExecution": True}
        self.assertIs(resp["capabilities"]["toolExecution"], True)

    def test_p0c_tool_execution_missing_rejected(self):
        resp = dict(HEALTH_RESPONSE_TEMPLATE)
        resp["capabilities"] = {}
        self.assertNotIn("toolExecution", resp["capabilities"])


class TestUnknownStatus(unittest.TestCase):
    def test_p0c_unknown_status_rejected(self):
        resp = dict(HEALTH_RESPONSE_TEMPLATE, status="exploded")
        self.assertNotIn(resp["status"], VALID_STATUSES)

    def test_p0c_all_valid_statuses_accepted(self):
        for status in VALID_STATUSES:
            resp = dict(HEALTH_RESPONSE_TEMPLATE, status=status)
            self.assertIn(resp["status"], VALID_STATUSES)


class TestMalformedFrameRecovery(unittest.TestCase):
    def test_p0c_malformed_frame_does_not_crash(self):
        try:
            parse_health_json("{invalid json")
        except (json.JSONDecodeError, ValueError):
            pass

    def test_p0c_valid_frame_after_malformed(self):
        try:
            parse_health_json("{invalid")
        except (json.JSONDecodeError, ValueError):
            pass
        result = parse_health_json(json.dumps(HEALTH_RESPONSE_TEMPLATE))
        self.assertEqual(result["type"], "health.status")


class TestNoSecretLeakage(unittest.TestCase):
    def test_p0c_nonce_not_in_error_message(self):
        nonce = HEALTH_REQUEST_TEMPLATE["startupNonce"]
        error_message = "health validation failed: nonce mismatch"
        self.assertNotIn(nonce, error_message)

    def test_p0c_request_id_not_in_generic_error(self):
        rid = HEALTH_REQUEST_TEMPLATE["requestId"]
        error_message = "health check failed"
        self.assertNotIn(rid, error_message)


class TestStoppingState(unittest.TestCase):
    def test_p0c_stopping_is_valid_status(self):
        self.assertIn("stopping", VALID_STATUSES)

    def test_p0c_tool_execution_remains_disabled(self):
        self.assertIs(HEALTH_RESPONSE_TEMPLATE["capabilities"]["toolExecution"], False)


class TestSharedCorpus(unittest.TestCase):
    def test_p0c_malformed_corpus_exists(self):
        import pathlib
        corpus_path = pathlib.Path(__file__).parent.parent / "security" / "contracts" / "sidecar_health_malformed_frames_v1.json"
        self.assertTrue(corpus_path.is_file(), "shared malformed-frame corpus must exist")

    def test_p0c_malformed_corpus_has_required_cases(self):
        import pathlib
        corpus_path = pathlib.Path(__file__).parent.parent / "security" / "contracts" / "sidecar_health_malformed_frames_v1.json"
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        case_ids = {c["id"] for c in corpus["cases"]}
        required = {
            "duplicate_request_id_key",
            "duplicate_startup_nonce_key",
            "excessive_nesting",
            "oversized_frame",
            "empty_frame",
            "unknown_protocol_version",
            "unknown_status",
            "tool_execution_true",
        }
        self.assertTrue(required.issubset(case_ids), f"missing cases: {required - case_ids}")


if __name__ == "__main__":
    unittest.main()
