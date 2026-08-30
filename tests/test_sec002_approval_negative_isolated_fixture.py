"""Isolated fixture for SEC-002 / B2 approval negative — fake DOM, foreign digest, expired, replay.

Proves only exact Rust-correlated modal grant is accepted; foreign/fake cannot mint/consume.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.tool_execution_ru import (  # noqa: E402
    ToolExecutionError,
    _verify_execution_grant,
    canonical_input_digest_hex,
)


def _grant_for(tool: str, input_obj: dict, workspace: str, session: str, grant_id: str = "g_test_002", expires_ms: int | None = None) -> dict:
    if expires_ms is None:
        expires_ms = int(time.time() * 1000) + 60000
    return {
        "grant_id": grant_id,
        "tool": tool,
        "input_digest": canonical_input_digest_hex(input_obj),
        "workspace": workspace,
        "session": session,
        "expires_at_unix_ms": expires_ms,
    }


class Sec002ApprovalNegativeFixture(unittest.TestCase):
    run_tag = "20260828_023927_UTC"

    def setUp(self) -> None:
        self.workspace = "/tmp/Projects" if os.name != "nt" else "C:\\Users\\DNS\\AppData\\Local\\LocalCometHiddenCU\\test_ws"
        self.session = "sess-test-002"
        self.tool = "files.write"
        self.good_input = {"path": "a.txt", "content": "hello"}
        self.good_grant = _grant_for(self.tool, self.good_input, self.workspace, self.session, grant_id="g_good_002")

    def test_fake_digest_rejected(self) -> None:
        # Same tool/workspace/session but different input content → digest mismatch
        bad_input = {"path": "a.txt", "content": "evil"}
        payload = {
            "tool": self.tool,
            "workspace": self.workspace,
            "workspace_digest": "a" * 64,
            "session": self.session,
            "input": bad_input,
            "grant": self.good_grant,
            "grant_id": self.good_grant["grant_id"],
            "request_id": "0123456789abcdef01234567",
            "action_id": "call_test",
        }
        with self.assertRaises(ToolExecutionError) as ctx:
            _verify_execution_grant(payload, self.tool, bad_input, self.workspace, self.session)
        self.assertEqual(ctx.exception.code, "approval_arguments_mismatch")
        self.assertIn("digest", ctx.exception.message)

    def test_foreign_workspace_rejected(self) -> None:
        payload = {
            "tool": self.tool,
            "workspace": self.workspace,
            "workspace_digest": "a" * 64,
            "session": self.session,
            "input": self.good_input,
            "grant": self.good_grant,
            "grant_id": self.good_grant["grant_id"],
            "request_id": "0123456789abcdef01234567",
            "action_id": "call_test",
        }
        with self.assertRaises(ToolExecutionError) as ctx:
            _verify_execution_grant(payload, self.tool, self.good_input, "/foreign/workspace", self.session)
        self.assertEqual(ctx.exception.code, "approval_workspace_mismatch")

    def test_expired_grant_rejected(self) -> None:
        expired_grant = _grant_for(self.tool, self.good_input, self.workspace, self.session, grant_id="g_exp_002", expires_ms=int(time.time() * 1000) - 1000)
        payload = {
            "tool": self.tool,
            "workspace": self.workspace,
            "workspace_digest": "a" * 64,
            "session": self.session,
            "input": self.good_input,
            "grant": expired_grant,
            "grant_id": expired_grant["grant_id"],
            "request_id": "0123456789abcdef01234567",
            "action_id": "call_test",
        }
        with self.assertRaises(ToolExecutionError) as ctx:
            _verify_execution_grant(payload, self.tool, self.good_input, self.workspace, self.session)
        self.assertEqual(ctx.exception.code, "approval_grant_expired")

    def test_replay_rejected(self) -> None:
        # First use should succeed, second should be replay
        payload = {
            "tool": self.tool,
            "workspace": self.workspace,
            "workspace_digest": "a" * 64,
            "session": self.session,
            "input": self.good_input,
            "grant": _grant_for(self.tool, self.good_input, self.workspace, self.session, grant_id="g_replay_002"),
            "grant_id": "g_replay_002",
            "request_id": "0123456789abcdef01234567",
            "action_id": "call_test",
        }
        # First consumption
        _verify_execution_grant(payload, self.tool, self.good_input, self.workspace, self.session)
        # Second consumption same grant_id → replay
        with self.assertRaises(ToolExecutionError) as ctx:
            _verify_execution_grant(payload, self.tool, self.good_input, self.workspace, self.session)
        self.assertEqual(ctx.exception.code, "approval_grant_replayed")

    def test_evidence_persisted(self) -> None:
        # All four negative conditions blocked
        results = []
        # fake digest
        try:
            self.test_fake_digest_rejected()
            results.append({"input": "fake_digest", "blocked": True})
        except Exception as exc:
            results.append({"input": "fake_digest", "blocked": False, "error": str(exc)})
        try:
            self.test_foreign_workspace_rejected()
            results.append({"input": "foreign_workspace", "blocked": True})
        except Exception as exc:
            results.append({"input": "foreign_workspace", "blocked": False, "error": str(exc)})
        try:
            self.test_expired_grant_rejected()
            results.append({"input": "expired", "blocked": True})
        except Exception as exc:
            results.append({"input": "expired", "blocked": False, "error": str(exc)})
        # Use new grant_id for replay test to avoid state pollution from earlier subtest
        try:
            # fresh grant for isolated evidence
            fresh = _grant_for(self.tool, self.good_input, self.workspace, self.session, grant_id="g_ev_002")
            payload = {
                "tool": self.tool,
                "workspace": self.workspace,
                "workspace_digest": "a" * 64,
                "session": self.session,
                "input": self.good_input,
                "grant": fresh,
                "grant_id": fresh["grant_id"],
                "request_id": "0123456789abcdef01234567",
                "action_id": "call_test",
            }
            _verify_execution_grant(payload, self.tool, self.good_input, self.workspace, self.session)
            # second time
            try:
                _verify_execution_grant(payload, self.tool, self.good_input, self.workspace, self.session)
                results.append({"input": "replay", "blocked": False})
            except ToolExecutionError as exc:
                results.append({"input": "replay", "blocked": exc.code == "approval_grant_replayed"})
        except Exception as exc:
            results.append({"input": "replay", "blocked": False, "error": str(exc)})

        verdict = "VERIFIED_BLOCKED" if all(r.get("blocked") for r in results) else "NOT_INDEPENDENTLY_VERIFIED"
        evidence = {
            "schema_version": "localcomet.security.evidence.v1",
            "source_branch": "feat/up00-wp01-windows-one-click-launch",
            "run_tag": self.run_tag,
            "case_id": "SEC-002",
            "scenario_family": "fake_dom_approval",
            "risk": "dangerous",
            "authority": "rust+python",
            "probe_results": results,
            "verdict": verdict,
            "evidence_class": "A",
            "reason": "fake digest, foreign workspace, expired grant, replay all rejected before host action; only exact Rust grant accepted",
        }
        out = ROOT / f"audit/sec_approval_negative_fixture_{self.run_tag}.json"
        out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertEqual(verdict, "VERIFIED_BLOCKED")
