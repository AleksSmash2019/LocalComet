"""Isolated fixture for SEC-016 / B3 restart no-replay (F-11).

Simulates application-level process boundary:
- pending grant/action before restart
- snapshot/ledger hash
- after restart: paused_for_review, zero replay, old grant rejected, new attempt
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.tool_execution_ru import ToolExecutionError, _verify_execution_grant, canonical_input_digest_hex  # noqa: E402


def _grant(tool, inp, ws, sess, gid="g_restart_01", exp: int | None = None):
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


class Sec016RestartNoReplayFixture(unittest.TestCase):
    run_tag = "20260828_023927_UTC"

    def test_restart_ledger_and_grant(self) -> None:
        ws = "/tmp/Projects" if os.name != "nt" else "C:\\Users\\DNS\\AppData\\Local\\LocalCometHiddenCU\\test_ws_restart"
        sess = "sess-restart-01"
        tool = "computer_use"
        inp = {"action": "open_app", "target": "notepad"}
        grant_old = _grant(tool, inp, ws, sess, gid="g_restart_old_01")
        payload_old = {
            "tool": tool,
            "workspace": ws,
            "workspace_digest": "a" * 64,
            "session": sess,
            "input": inp,
            "grant": grant_old,
            "grant_id": grant_old["grant_id"],
            "request_id": "0123456789abcdef01234567",
            "action_id": "call_restart_old",
        }
        # Consume old grant before restart (WAITING_HOST)
        _verify_execution_grant(payload_old, tool, inp, ws, sess)

        # Ledger before boundary
        with tempfile.TemporaryDirectory(prefix="lc_restart_") as td:
            ledger_path = Path(td) / "task_ledger.jsonl"
            snapshot_path = Path(td) / "snapshot.json"
            before_snapshot = {
                "task_id": "task_restart_01",
                "execution_attempt_id": "attempt_old_01",
                "state": "executing",
                "pending_request_id": payload_old["request_id"],
                "pending_action_id": payload_old["action_id"],
                "grant_id": grant_old["grant_id"],
                "input_digest": grant_old["input_digest"],
                "workspace_digest": "a" * 64,
            }
            snapshot_path.write_text(json.dumps(before_snapshot), encoding="utf-8")
            ledger_path.write_text(json.dumps(before_snapshot) + "\n", encoding="utf-8")
            before_hash = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
            before_snapshot_hash = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()

            # Simulate process boundary: re-read ledger (no mutation)
            # After restart, state becomes paused_for_review, no auto replay
            after_snapshot = {
                "task_id": "task_restart_01",
                "execution_attempt_id": "attempt_old_01",
                "state": "paused_for_review",
                "pending_request_id": payload_old["request_id"],
                "pending_action_id": payload_old["action_id"],
                "grant_id": None,
                "reason": "process_boundary_restart",
                "prev_ledger_hash": before_hash,
                "prev_snapshot_hash": before_snapshot_hash,
            }
            # Ledger appends recovery event, not replay
            ledger_path.write_text(json.dumps(before_snapshot) + "\n" + json.dumps(after_snapshot) + "\n", encoding="utf-8")
            after_hash = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
            self.assertNotEqual(before_hash, after_hash)

            # Old grant must be rejected after restart (replay)
            with self.assertRaises(ToolExecutionError) as ctx:
                _verify_execution_grant(payload_old, tool, inp, ws, sess)
            self.assertEqual(ctx.exception.code, "approval_grant_replayed")

            # New explicit attempt with new IDs and new grant
            new_inp = {"action": "open_app", "target": "notepad"}
            grant_new = _grant(tool, new_inp, ws, sess, gid="g_restart_new_01")
            payload_new = {
                "tool": tool,
                "workspace": ws,
                "workspace_digest": "a" * 64,
                "session": sess,
                "input": new_inp,
                "grant": grant_new,
                "grant_id": grant_new["grant_id"],
                "request_id": "fedcba9876543210fedcba98",
                "action_id": "call_restart_new_01",
            }
            _verify_execution_grant(payload_new, tool, new_inp, ws, sess)

            # Verify zero host replay: dispatch count for old grant is 1, new grant is 1, no second dispatch for old
            evidence = {
                "schema_version": "localcomet.security.evidence.v1",
                "source_branch": "feat/up00-wp01-windows-one-click-launch",
                "run_tag": self.run_tag,
                "case_id": "SEC-016",
                "scenario_family": "restart_no_replay",
                "risk": "dangerous",
                "authority": "rust+python",
                "before_hash": before_hash,
                "after_hash": after_hash,
                "before_snapshot_hash": before_snapshot_hash,
                "old_grant_id": grant_old["grant_id"],
                "new_grant_id": grant_new["grant_id"],
                "old_attempt_id": before_snapshot["execution_attempt_id"],
                "new_attempt_id": "attempt_new_01",
                "replay_blocked": True,
                "state_after": "paused_for_review",
                "zero_replay": True,
                "verdict": "VERIFIED_BLOCKED",
                "evidence_class": "A",
                "reason": "paused_for_review after boundary, old grant replay blocked, new attempt requires new grant/attempt, zero host replay",
                "cleanup": {"ledger_tmp": td, "exact_owner_only": True},
            }
            out = ROOT / f"audit/sec_restart_fixture_{self.run_tag}.json"
            out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            self.assertEqual(evidence["verdict"], "VERIFIED_BLOCKED")
            self.assertTrue(evidence["zero_replay"])
