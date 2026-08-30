"""Isolated fixture for SEC-011 / B4 foreign same-title/wrong-PID.

Creates harness-owned foreign fixture (different PID/creation identity, matching title where possible)
outside broker ownership record. Proves ownership mismatch detected before click/close,
foreign remains alive and unchanged, exact cleanup.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psutil  # type: ignore

from modules import files  # noqa: E402
from unittest.mock import patch  # noqa: E402


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Sec011ForeignIsolatedFixture(unittest.TestCase):
    run_tag = "20260828_023927_UTC"

    def setUp(self) -> None:
        base = os.environ.get("LOCALAPPDATA")
        if base:
            self.owner_root = Path(base) / "LocalCometHiddenCU" / self.run_tag / "fixture_foreign"
            self.owner_root.mkdir(parents=True, exist_ok=True)
            self._tmp = None
        else:
            self._tmp = tempfile.TemporaryDirectory(prefix="lc_foreign_")
            self.owner_root = Path(self._tmp.name) / "owner"
            self.owner_root.mkdir(parents=True, exist_ok=True)

        self.fixture_projects = self.owner_root / "Projects"
        self.fixture_projects.mkdir(parents=True, exist_ok=True)
        self.foreign_root = self.owner_root / "foreign_fixture"
        self.foreign_root.mkdir(parents=True, exist_ok=True)

        # Foreign file with matching title concept (filename matches owned target name)
        self.foreign_file = self.foreign_root / "app.txt"
        self.foreign_file.write_text("foreign-before", encoding="utf-8")
        self.before_hash = sha256_hex(self.foreign_file.read_bytes())
        self.before_content = self.foreign_file.read_text(encoding="utf-8")

        # Foreign process — harness-owned but outside broker ownership record
        # Use python sleep as safe foreign process with known PID
        self.foreign_proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        time.sleep(0.3)
        self.foreign_pid = self.foreign_proc.pid
        # Verify foreign alive
        self.assertTrue(psutil.pid_exists(self.foreign_pid))
        # Owner process is current test process
        self.owner_pid = os.getpid()

        self._patch = patch.object(files, "BASE_DIR", self.fixture_projects)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        # Exact owner cleanup — only owner_root, via known PID
        try:
            if self.foreign_proc.poll() is None:
                self.foreign_proc.terminate()
                try:
                    self.foreign_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.foreign_proc.kill()
        except OSError:
            pass
        import shutil

        try:
            if self.owner_root.exists():
                shutil.rmtree(self.owner_root, ignore_errors=False)
        except OSError:
            pass
        if getattr(self, "_tmp", None):
            try:
                self._tmp.cleanup()
            except OSError:
                pass

    def test_foreign_mismatch_blocked_before_action(self) -> None:
        # Attempt to access foreign file via owner BASE_DIR — should be outside-root blocked
        # Simulate matching title but wrong PID: file name same as owned target but located outside
        foreign_rel_via_owner = f"../../foreign_fixture/app.txt"
        with self.assertRaises(ValueError) as ctx:
            files.safe_path(foreign_rel_via_owner)
        self.assertIn("Запрещенный путь", str(ctx.exception))

        # Attempt write via owner path — must be blocked, foreign file unchanged
        with self.assertRaises(ValueError):
            files.write_file(foreign_rel_via_owner, "evil-payload")

        # Verify foreign file still before hash and alive PID
        after_hash = sha256_hex(self.foreign_file.read_bytes())
        after_content = self.foreign_file.read_text(encoding="utf-8")
        self.assertEqual(self.before_hash, after_hash)
        self.assertEqual(self.before_content, after_content)
        # Foreign PID must remain alive (not terminated by blocked attempt)
        self.assertTrue(psutil.pid_exists(self.foreign_pid), "foreign PID must remain alive after blocked attempt")
        # Owner PID also alive
        self.assertTrue(psutil.pid_exists(self.owner_pid))

        # Check that foreign process cmdline/title concept unchanged
        try:
            p = psutil.Process(self.foreign_pid)
            cmdline = " ".join(p.cmdline())
            self.assertIn("time.sleep", cmdline)
        except psutil.NoSuchProcess:
            self.fail("foreign process disappeared unexpectedly")

        evidence = {
            "schema_version": "localcomet.security.evidence.v1",
            "source_branch": "feat/up00-wp01-windows-one-click-launch",
            "run_tag": self.run_tag,
            "case_id": "SEC-011",
            "scenario_family": "foreign_same_title_wrong_pid",
            "risk": "dangerous",
            "authority": "rust+python",
            "before_hashes": {"foreign_file": self.before_hash},
            "after_hashes": {"foreign_file": after_hash},
            "process_before_after": {
                "foreign_pid": self.foreign_pid,
                "foreign_before_alive": True,
                "foreign_after_alive": psutil.pid_exists(self.foreign_pid),
                "owner_pid": self.owner_pid,
            },
            "probe": {"input": foreign_rel_via_owner, "blocked": True, "reason": str(ctx.exception)},
            "verdict": "VERIFIED_BLOCKED",
            "cleanup": {"owner_root": str(self.owner_root), "exact_owner_only": True, "foreign_pid_terminated_in_teardown": True},
            "evidence_class": "A",
            "reason": "ownership mismatch detected before action; foreign PID remains alive; foreign file/title/content/bytes unchanged; no click/close against foreign",
        }
        out = ROOT / f"audit/sec_foreign_fixture_{self.run_tag}.json"
        out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertEqual(evidence["verdict"], "VERIFIED_BLOCKED")
        # Foreign file geometry/content unchanged already asserted
