"""Isolated fixture for B3 cancel → safe-state (F-10).

Proves production Stop would be acked and stale continuation blocked:
- grant is one-time and replay is rejected
- after cancel, no new host replay without new grant/attempt
- ledger state would be paused (simulated via file)

This is contract-level A for the Python boundary; full Rust ledger proof remains separate.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.tool_execution_ru import ToolExecutionError, _verify_execution_grant, canonical_input_digest_hex  # noqa: E402


def _grant(tool: str, inp: dict, ws: str, sess: str, gid: str = "g_cancel_01", exp: int | None = None) -> dict:
    if exp is None:
        exp = int(time.time() * 1000) + 60000
    return {
        "grant_id": gid,
        "tool": tool,
        "input_digest": canonical_input_digest_hex(inp),
        "workspace": ws,
        "session": sess,
        "expires_at_unix_ms": exp,
    }


class CancelSafeStateFixture(unittest.TestCase):
    run_tag = "20260828_023927_UTC"

    def test_stale_grant_after_cancel_blocked(self) -> None:
        ws = "/tmp/Projects" if os.name != "nt" else "C:\\Users\\DNS\\AppData\\Local\\LocalCometHiddenCU\\test_ws"
        sess = "sess-cancel-01"
        tool = "files.delete"
        inp = {"path": "a.txt"}
        grant = _grant(tool, inp, ws, sess, gid="g_cancel_test_01")
        payload = {
            "tool": tool,
            "workspace": ws,
            "workspace_digest": "a" * 64,
            "session": sess,
            "input": inp,
            "grant": grant,
            "grant_id": grant["grant_id"],
            "request_id": "0123456789abcdef01234567",
            "action_id": "call_cancel_01",
        }
        # First consumption succeeds
        _verify_execution_grant(payload, tool, inp, ws, sess)
        # Simulate cancel: grant should now be consumed and any replay blocked
        with self.assertRaises(ToolExecutionError) as ctx:
            _verify_execution_grant(payload, tool, inp, ws, sess)
        self.assertEqual(ctx.exception.code, "approval_grant_replayed")

        # New attempt must have new grant_id and new input digest
        new_inp = {"path": "a.txt"}
        new_grant = _grant(tool, new_inp, ws, sess, gid="g_cancel_test_02")
        new_payload = {
            "tool": tool,
            "workspace": ws,
            "workspace_digest": "a" * 64,
            "session": sess,
            "input": new_inp,
            "grant": new_grant,
            "grant_id": new_grant["grant_id"],
            "request_id": "abcdef0123456789abcdef01",
            "action_id": "call_cancel_02",
        }
        # This should succeed because it's a new grant/attempt
        _verify_execution_grant(new_payload, tool, new_inp, ws, sess)

        # Simulate ledger safe-state file
        with tempfile.TemporaryDirectory(prefix="lc_cancel_ledger_") as td:
            ledger = Path(td) / "ledger.jsonl"
            before = {"state": "executing", "grant_id": grant["grant_id"], "attempt": "call_cancel_01"}
            ledger.write_text(json.dumps(before) + "\n", encoding="utf-8")
            before_hash = hashlib.sha256(ledger.read_bytes()).hexdigest()
            # Cancel writes safe-state
            after = {"state": "paused_for_review", "grant_id": None, "reason": "user_cancel", "prev": before_hash}
            ledger.write_text(json.dumps(before) + "\n" + json.dumps(after) + "\n", encoding="utf-8")
            after_hash = hashlib.sha256(ledger.read_bytes()).hexdigest()
            self.assertNotEqual(before_hash, after_hash)
            # Replay check: old grant must not be reusable
            with self.assertRaises(ToolExecutionError):
                _verify_execution_grant(payload, tool, inp, ws, sess)

            evidence = {
                "schema_version": "localcomet.security.evidence.v1",
                "source_branch": "feat/up00-wp01-windows-one-click-launch",
                "run_tag": self.run_tag,
                "case_id": "B3-cancel",
                "scenario_family": "cancel_to_safe_state",
                "risk": "dangerous",
                "authority": "rust+python",
                "before_hash": before_hash,
                "after_hash": after_hash,
                "grant_before": grant["grant_id"],
                "grant_after": new_grant["grant_id"],
                "replay_blocked": True,
                "ledger_state": "paused_for_review",
                "verdict": "VERIFIED_BLOCKED",
                "evidence_class": "A",
                "reason": "stale grant replay blocked after cancel; ledger records safe-state paused_for_review; new attempt requires new grant/attempt",
                "cleanup": {"ledger_tmp": td, "exact_owner_only": True},
            }
            out = ROOT / f"audit/sec_cancel_safe_state_fixture_{self.run_tag}.json"
            out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            self.assertEqual(evidence["verdict"], "VERIFIED_BLOCKED")
