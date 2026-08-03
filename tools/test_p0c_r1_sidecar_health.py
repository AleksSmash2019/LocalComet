"""Executable MVP-P0-C-R1 production-seam tests.

These tests exercise the real Python IPC decoder/runtime and a live sidecar
process. They intentionally do not duplicate production validation logic.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.desktop_ipc_contract_ru import (
    ENVELOPE_KEYS,
    FrameDecoder,
    IPCProtocolError,
    decode_frame,
    encode_frame,
    make_hello,
    make_request,
)
from modules.desktop_sidecar_runtime_ru import (
    DesktopSidecarRuntime,
    validate_health_check_payload,
)
from scripts import refresh_evidence

CORPUS_PATH = ROOT / "security" / "contracts" / "sidecar_health_malformed_frames_v1.json"
REQUEST_ID = "hreq_" + "a" * 32
NONCE = "scn_" + "b" * 64
RUNTIME_ID = "rti_" + "c" * 32


def health_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "health.check",
        "protocolVersion": 1,
        "requestId": REQUEST_ID,
        "generationId": 1,
        "startupNonce": NONCE,
        "runtimeInstanceId": RUNTIME_ID,
        "sentAtUnixMs": 1,
    }
    payload.update(updates)
    return payload


def hello(runtime: DesktopSidecarRuntime) -> None:
    runtime.handle_message(make_hello("desktop-hello", session_nonce="session"))


def production_parse(body: bytes) -> dict[str, object]:
    return decode_frame(struct.pack(">I", len(body)) + body)


def response_for(payload: dict[str, object] | None = None, outer_id: str = REQUEST_ID):
    runtime = DesktopSidecarRuntime(session_nonce="test")
    hello(runtime)
    request = make_request(outer_id, "app.health", payload or health_payload())
    return runtime.handle_message(request)[0]


def read_one(stream) -> tuple[dict[str, object], bytes]:
    prefix = stream.read(4)
    if len(prefix) != 4:
        raise AssertionError(f"missing frame prefix: {prefix!r}")
    size = struct.unpack(">I", prefix)[0]
    body = stream.read(size)
    if len(body) != size:
        raise AssertionError("truncated live sidecar frame")
    return decode_frame(prefix + body), prefix + body


class VariantAProductionTests(unittest.TestCase):
    def test_p0c_r1_valid_payload(self):
        self.assertEqual(validate_health_check_payload(health_payload(), REQUEST_ID), ())

    def test_p0c_r1_outer_inner_request_binding(self):
        self.assertIn("health_request_id_mismatch", validate_health_check_payload(health_payload(), "hreq_" + "d" * 32))

    def test_p0c_r1_response_outer_id_binding(self):
        response = response_for()
        self.assertEqual(response["id"], REQUEST_ID)

    def test_p0c_r1_response_reply_to_binding(self):
        response = response_for()
        self.assertEqual(response["reply_to"], REQUEST_ID)

    def test_p0c_r1_response_inner_id_binding(self):
        response = response_for()
        self.assertEqual(response["payload"]["requestId"], REQUEST_ID)

    def test_p0c_r1_response_exact_outer_keys(self):
        self.assertEqual(tuple(response_for().keys()), ENVELOPE_KEYS)

    def test_p0c_r1_response_type(self):
        self.assertEqual(response_for()["payload"]["type"], "health.status")

    def test_p0c_r1_response_protocol(self):
        self.assertEqual(response_for()["payload"]["protocolVersion"], 1)

    def test_p0c_r1_response_echoes_generation(self):
        self.assertEqual(response_for(health_payload(generationId=42))["payload"]["generationId"], 42)

    def test_p0c_r1_response_echoes_nonce(self):
        self.assertEqual(response_for()["payload"]["startupNonce"], NONCE)

    def test_p0c_r1_response_echoes_runtime(self):
        self.assertEqual(response_for()["payload"]["runtimeInstanceId"], RUNTIME_ID)

    def test_p0c_r1_health_capability_exactly_disabled(self):
        self.assertEqual(response_for()["payload"]["capabilities"], {"toolExecution": False})

    def test_p0c_r1_ready_status(self):
        self.assertEqual(response_for()["payload"]["status"], "ready")

    def test_p0c_r1_received_timestamp_non_negative(self):
        self.assertGreaterEqual(response_for()["payload"]["receivedAtUnixMs"], 0)


class InvalidRequestTests(unittest.TestCase):
    def assert_invalid(self, **updates: object) -> None:
        response = response_for(health_payload(**updates))
        self.assertEqual(response["type"], "error")
        self.assertEqual(response["payload"]["code"], "invalid_payload")

    def test_p0c_r1_bad_type(self): self.assert_invalid(type="health.status")
    def test_p0c_r1_bad_protocol(self): self.assert_invalid(protocolVersion=2)
    def test_p0c_r1_bad_request_id(self): self.assert_invalid(requestId="bad")
    def test_p0c_r1_boolean_generation(self): self.assert_invalid(generationId=True)
    def test_p0c_r1_zero_generation(self): self.assert_invalid(generationId=0)
    def test_p0c_r1_bad_nonce(self): self.assert_invalid(startupNonce="bad")
    def test_p0c_r1_bad_runtime_id(self): self.assert_invalid(runtimeInstanceId="bad")
    def test_p0c_r1_negative_sent_at(self): self.assert_invalid(sentAtUnixMs=-1)


class ProductionParserCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["cases"]

    def body_for(self, case: dict[str, object]) -> bytes:
        if case.get("invalid_utf8"):
            return b'{"bad":"\xff\xfe"}'
        if case.get("size_bytes") == 0:
            return b""
        if case.get("size_bytes"):
            return b"x" * int(case["size_bytes"])
        if case.get("depth"):
            depth = int(case["depth"])
            return ("[" * depth + "0" + "]" * depth).encode()
        return str(case["json"]).encode()

    def test_p0c_r1_corpus_has_cross_language_minimum(self):
        self.assertGreaterEqual(len(self.corpus), 15)

    def test_p0c_r1_every_parser_case_uses_production_decoder(self):
        parser_cases = [case for case in self.corpus if case.get("parser_reject")]
        self.assertGreaterEqual(len(parser_cases), 12)
        for case in parser_cases:
            with self.subTest(case=case["id"]):
                body = self.body_for(case)
                if len(body) > 4_194_304:
                    frame = struct.pack(">I", len(body))
                else:
                    frame = struct.pack(">I", len(body)) + body
                with self.assertRaises(IPCProtocolError):
                    decode_frame(frame)

    def test_p0c_r1_unicode_decoded_duplicate_rejected(self):
        with self.assertRaises(IPCProtocolError):
            production_parse(b'{"status":1,"st\\u0061tus":2}')

    def test_p0c_r1_repeated_array_values_accepted(self):
        message = make_request("array-values", "app.health", {"tags": ["x", "x"]})
        body = json.dumps(message, separators=(",", ":")).encode()
        self.assertEqual(production_parse(body)["payload"]["tags"], ["x", "x"])

    def test_p0c_r1_frame_decoder_recovers_after_reset(self):
        decoder = FrameDecoder()
        with self.assertRaises(IPCProtocolError):
            decoder.feed(struct.pack(">I", 0))
        valid = encode_frame(make_hello("hello-after-error", session_nonce="session"))
        self.assertEqual(len(decoder.feed(valid)), 1)


class LiveSidecarTests(unittest.TestCase):
    def test_p0c_r1_live_sidecar_reaches_ready_without_stdout_contamination(self):
        env = {key: value for key, value in os.environ.items() if key in {"SystemRoot", "WINDIR", "TEMP", "TMP"}}
        env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"})
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", str(ROOT / "tools" / "run_localcomet_desktop_sidecar.py")],
            cwd=ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stdin and process.stdout and process.stderr
        try:
            startup, raw_startup = read_one(process.stdout)
            self.assertEqual(startup["type"], "hello")
            process.stdin.write(encode_frame(make_hello("desktop-live", session_nonce="session")))
            process.stdin.flush()
            echoed_hello, raw_hello = read_one(process.stdout)
            self.assertEqual(echoed_hello["type"], "hello")
            process.stdin.write(encode_frame(make_request(REQUEST_ID, "app.health", health_payload())))
            process.stdin.flush()
            health, raw_health = read_one(process.stdout)
            self.assertEqual(health["payload"]["status"], "ready")
            self.assertEqual(health["id"], health["reply_to"])
            self.assertEqual(health["id"], health["payload"]["requestId"])
            for raw in (raw_startup, raw_hello, raw_health):
                self.assertEqual(len(raw), 4 + struct.unpack(">I", raw[:4])[0])
        finally:
            process.stdin.close()
            process.wait(timeout=10)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(process.stderr.read(), b"")
        process.stdout.close()
        process.stderr.close()


class DigestAuthorityTests(unittest.TestCase):
    def test_p0c_r1_contract_glob_is_authoritative(self):
        self.assertIn("security/contracts/**/*.json", refresh_evidence.SOURCE_GLOBS)

    def test_p0c_r1_contract_selected_by_source_files(self):
        selected = {path.relative_to(ROOT).as_posix() for path in refresh_evidence.source_files()}
        self.assertIn("security/contracts/sidecar_health_malformed_frames_v1.json", selected)

    def test_p0c_r1_digest_authority_document_selected(self):
        selected = {path.relative_to(ROOT).as_posix() for path in refresh_evidence.source_files()}
        self.assertIn("security/contracts/source_digest_authority_v1.json", selected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
