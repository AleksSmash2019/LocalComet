"""F-03 redaction gate: raw continuation tokens must never reach evidence.

The broker's raw `cgr_...` grant token is one-time capability material. The
hidden-desktop harness is the writer of every isolated-run evidence artifact,
so write_json() must scrub such tokens at the single persistence boundary.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_isolated_hidden_desktop_cu import redact_secret_refs, write_json  # noqa: E402


TOKEN = "cgr_f803c88af8d0b92c21b3b1893187159e"
MASK = "<redacted:cgr>"


class GrantRedactionTests(unittest.TestCase):
    def test_top_level_string_is_masked(self) -> None:
        self.assertEqual(redact_secret_refs(TOKEN), MASK)

    def test_nested_payload_is_masked(self) -> None:
        payload = {
            "result": {
                "execution": {
                    "continuation": {"grant_ref": TOKEN, "grant_state": "issued"},
                    "pid": 1234,
                },
                "log": f"issued grant {TOKEN} for step",
            },
            "tokens": [TOKEN, "plain"],
        }
        redacted = redact_secret_refs(payload)
        serialized = json.dumps(redacted)
        self.assertNotIn(TOKEN, serialized)
        self.assertIn(MASK, serialized)
        # Non-secret fields survive untouched.
        self.assertEqual(redacted["result"]["execution"]["continuation"]["grant_state"], "issued")
        self.assertEqual(redacted["result"]["execution"]["pid"], 1234)
        self.assertEqual(redacted["tokens"][1], "plain")

    def test_hash_like_hex_without_prefix_is_untouched(self) -> None:
        digest = "f803c88af8d0b92c21b3b1893187159e"
        self.assertEqual(redact_secret_refs(digest), digest)

    def test_short_cgr_lookalike_is_untouched(self) -> None:
        # Fewer than 8 hex chars: not a real token shape; leave as-is so the
        # mask never corrupts unrelated identifiers.
        self.assertEqual(redact_secret_refs("cgr_123"), "cgr_123")

    def test_write_json_scrubs_evidence_on_disk(self) -> None:
        payload = {
            "schema_version": "localcomet.intent-dispatch.v1",
            "payload": {
                "result": {
                    "execution": {
                        "continuation": {
                            "grant_ref": TOKEN,
                            "allowed_next_actions": ["observe"],
                        }
                    }
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "intent_dispatch.json"
            write_json(target, payload)
            text = target.read_text(encoding="utf-8")
            self.assertNotIn(TOKEN, text, "raw cgr_ token reached an evidence file")
            self.assertIn(MASK, text)
            parsed = json.loads(text)
            self.assertEqual(
                parsed["payload"]["result"]["execution"]["continuation"]["grant_ref"], MASK
            )


if __name__ == "__main__":
    unittest.main()
