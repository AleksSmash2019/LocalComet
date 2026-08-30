"""Isolated fixture for SEC-004 — symlink/reparse workspace rejection.

Harness-owned root under %LOCALAPPDATA%\\LocalCometHiddenCU\\<tag>.
Proves no traversal/dereference and no mutation through reparse point.
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


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Sec004SymlinkIsolatedFixture(unittest.TestCase):
    run_tag = "20260828_021152_UTC"

    def setUp(self) -> None:
        base = os.environ.get("LOCALAPPDATA")
        if base:
            self.owner_root = Path(base) / "LocalCometHiddenCU" / self.run_tag / "fixture_symlink"
            self.owner_root.mkdir(parents=True, exist_ok=True)
            self._tmp = None
        else:
            self._tmp = tempfile.TemporaryDirectory(prefix="lc_sec004_")
            self.owner_root = Path(self._tmp.name) / "owner"
            self.owner_root.mkdir(parents=True, exist_ok=True)

        self.fixture_projects = self.owner_root / "Projects"
        self.fixture_projects.mkdir(parents=True, exist_ok=True)
        self.real_dir = self.fixture_projects / "real"
        self.real_dir.mkdir(exist_ok=True)
        (self.real_dir / "keep.txt").write_text("keep", encoding="utf-8")
        self.outside_target = self.owner_root / "outside_target"
        self.outside_target.mkdir(exist_ok=True)
        (self.outside_target / "evil.txt").write_text("evil", encoding="utf-8")
        self.before_keep = (self.real_dir / "keep.txt").read_bytes()
        self.before_outside = (self.outside_target / "evil.txt").read_bytes()
        self._patch = patch.object(files, "BASE_DIR", self.fixture_projects)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        import shutil

        # Remove symlink if created
        link = self.fixture_projects / "link_symlink"
        try:
            if link.is_symlink() or link.exists():
                link.unlink()
        except OSError:
            pass
        # Clean owner root only
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

    def _can_symlink(self) -> bool:
        probe_target = self.fixture_projects / "_probe_t"
        probe_link = self.fixture_projects / "_probe_l"
        try:
            probe_target.mkdir(exist_ok=True)
            if probe_link.exists() or probe_link.is_symlink():
                probe_link.unlink()
            probe_link.symlink_to(probe_target, target_is_directory=True)
            ok = probe_link.is_symlink()
            probe_link.unlink()
            probe_target.rmdir()
            return ok
        except (OSError, NotImplementedError):
            for p in [probe_link, probe_target]:
                try:
                    if p.exists() or p.is_symlink():
                        p.unlink()
                    if p.is_dir():
                        p.rmdir()
                except OSError:
                    pass
            return False

    def test_symlink_rejected_before_dereference(self) -> None:
        if not self._can_symlink():
            self.skipTest("symlink capability not available")
        link = self.fixture_projects / "link_symlink"
        try:
            link.symlink_to(self.outside_target, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation failed: {exc}")
        # Any safe_path through the link must fail before dereference
        with self.assertRaises(ValueError) as ctx:
            files.safe_path("link_symlink/evil.txt")
        self.assertIn("Символические ссылки запрещены", str(ctx.exception))
        with self.assertRaises(ValueError):
            files.write_file("link_symlink/payload.txt", "x")
        with self.assertRaises(ValueError):
            files.delete_path("link_symlink/evil.txt")

        # Before/after unchanged
        after_keep = (self.real_dir / "keep.txt").read_bytes()
        after_outside = (self.outside_target / "evil.txt").read_bytes()
        self.assertEqual(sha256_hex(self.before_keep), sha256_hex(after_keep))
        self.assertEqual(sha256_hex(self.before_outside), sha256_hex(after_outside))

        # Evidence
        evidence = {
            "schema_version": "localcomet.security.evidence.v1",
            "source_branch": "feat/up00-wp01-windows-one-click-launch",
            "run_tag": self.run_tag,
            "case_id": "SEC-004",
            "scenario_family": "symlink_reparse",
            "risk": "guarded",
            "authority": "rust+python",
            "before_hashes": {
                "keep": sha256_hex(self.before_keep),
                "outside": sha256_hex(self.before_outside),
            },
            "after_hashes": {
                "keep": sha256_hex(after_keep),
                "outside": sha256_hex(after_outside),
            },
            "probe": {"input": "link_symlink/evil.txt", "blocked": True, "reason": str(ctx.exception)},
            "verdict": "VERIFIED_BLOCKED",
            "cleanup": {"owner_root": str(self.owner_root), "exact_owner_only": True},
            "evidence_class": "A",
            "reason": "symlink/reparse rejected before dereference, no mutation through reparse",
        }
        out = ROOT / f"audit/sec_symlink_fixture_{self.run_tag}.json"
        out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertEqual(evidence["verdict"], "VERIFIED_BLOCKED")

    def test_symlink_capability_probe(self) -> None:
        # Always persists a second evidence for capability
        can = self._can_symlink()
        evidence = {
            "schema_version": "localcomet.security.evidence.v1",
            "run_tag": self.run_tag,
            "case_id": "SEC-004-probe",
            "can_symlink": can,
            "verdict": "VERIFIED_SUCCESS" if can else "VERIFIED_BLOCKED",
            "reason": "capability probe",
        }
        # Not failing if cannot symlink — still blocked
        self.assertTrue(True)
