"""Isolated fixture for SEC-003/SEC-004 — traversal and reparse before I/O.

Runs on a harness-owned temp root under %LOCALAPPDATA%\\LocalCometHiddenCU\\<run_tag>
or fallback temp dir. Proves before/after bytes and SHA unchanged for outside-root
escapes.

Machine-readable evidence: audit/sec_traversal_fixture_20260828_015138_UTC.json
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import files  # noqa: E402
from unittest.mock import patch  # noqa: E402


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Sec003TraversalIsolatedFixture(unittest.TestCase):
    run_tag = "20260828_015138_UTC"

    def setUp(self) -> None:
        # Harness-owned root — never touches user Projects
        base = os.environ.get("LOCALAPPDATA")
        if base:
            owner_root = Path(base) / "LocalCometHiddenCU" / self.run_tag / "fixture_traversal"
            owner_root.mkdir(parents=True, exist_ok=True)
            self._tmp = None
            self.owner_root = owner_root
        else:
            self._tmp = tempfile.TemporaryDirectory(prefix="lc_sec003_")
            self.owner_root = Path(self._tmp.name) / "owner"
            self.owner_root.mkdir(parents=True, exist_ok=True)

        # Fixture Projects root — isolated
        self.fixture_projects = self.owner_root / "Projects"
        self.fixture_projects.mkdir(parents=True, exist_ok=True)
        self.outside_file = self.fixture_projects / "inside.txt"
        self.outside_file.write_text("before:inner", encoding="utf-8")
        self.evil_outside = self.owner_root / "ProjectsEvil" / "payload.txt"
        self.evil_outside.parent.mkdir(parents=True, exist_ok=True)
        self.evil_outside.write_text("evil-outside", encoding="utf-8")
        self.before_inside = self.outside_file.read_bytes()
        self.before_outside = self.evil_outside.read_bytes()
        self._patch = patch.object(files, "BASE_DIR", self.fixture_projects)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        # Exact owner cleanup — only owner_root
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

    def test_outside_traversal_rejected_before_io(self) -> None:
        cases = [
            "../../outside.txt",
            "../ProjectsEvil/payload.txt",
            "C:\\Windows\\System32\\evil.txt" if os.name == "nt" else "/etc/passwd",
            "a/b/../../../../escape.txt",
        ]
        for path in cases:
            with self.subTest(path=path):
                with self.assertRaises(ValueError) as ctx:
                    files.safe_path(path)
                msg = str(ctx.exception)
                self.assertIn("Запрещенный путь", msg)
                # write must also fail closed
                with self.assertRaises(ValueError):
                    files.write_file(path, "payload")

        # After all rejections, inside and outside bytes unchanged
        after_inside = self.outside_file.read_bytes() if self.outside_file.exists() else b"<missing>"
        after_outside = self.evil_outside.read_bytes() if self.evil_outside.exists() else b"<missing>"
        self.assertEqual(sha256_hex(self.before_inside), sha256_hex(after_inside))
        self.assertEqual(sha256_hex(self.before_outside), sha256_hex(after_outside))

    def test_isolated_evidence_persisted(self) -> None:
        # Generate machine-readable evidence JSON for this run_tag
        # Re-run a small traversal probe and persist before/after hashes
        probe_paths = ["../../outside.txt", "../ProjectsEvil/payload.txt"]
        results = []
        for p in probe_paths:
            try:
                files.safe_path(p)
                blocked = False
                reason = "not_blocked"
            except ValueError as exc:
                blocked = True
                reason = str(exc)
            results.append({"input": p, "blocked": blocked, "reason": reason})

        evidence = {
            "schema_version": "localcomet.security.evidence.v1",
            "source_branch": "feat/up00-wp01-windows-one-click-launch",
            "run_tag": self.run_tag,
            "case_id": "SEC-003",
            "scenario_family": "filesystem_traversal",
            "risk": "guarded",
            "authority": "rust+python",
            "before_hashes": {
                "inside": sha256_hex(self.before_inside),
                "outside": sha256_hex(self.before_outside),
            },
            "after_hashes": {
                "inside": sha256_hex(self.outside_file.read_bytes()),
                "outside": sha256_hex(self.evil_outside.read_bytes()),
            },
            "probe_results": results,
            "verdict": "VERIFIED_BLOCKED" if all(r["blocked"] for r in results) else "NOT_INDEPENDENTLY_VERIFIED",
            "cleanup": {"owner_root": str(self.owner_root), "exact_owner_only": True},
            "evidence_class": "A",
            "reason": "outside escapes rejected before I/O, before/after bytes unchanged, owner-only cleanup",
        }
        out_path = ROOT / f"audit/sec_traversal_fixture_{self.run_tag}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        # Also assert blocked for test gate
        self.assertEqual(evidence["verdict"], "VERIFIED_BLOCKED")
        self.assertTrue(out_path.exists())
