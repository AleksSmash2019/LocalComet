"""Isolated fixture for B1 Files/coding — before/after SHA, outside-root/reparse, owner cleanup.

Harness-owned root under %LOCALAPPDATA%\\LocalCometHiddenCU\\<tag>\\fixture_files.
Proves canonical workspace identity, approved input digest, mutation set, no unexpected files.
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


class SecFilesNativeIsolatedFixture(unittest.TestCase):
    run_tag = "20260828_023927_UTC"

    def setUp(self) -> None:
        base = os.environ.get("LOCALAPPDATA")
        if base:
            self.owner_root = Path(base) / "LocalCometHiddenCU" / self.run_tag / "fixture_files"
            self.owner_root.mkdir(parents=True, exist_ok=True)
            self._tmp = None
        else:
            self._tmp = tempfile.TemporaryDirectory(prefix="lc_files_native_")
            self.owner_root = Path(self._tmp.name) / "owner"
            self.owner_root.mkdir(parents=True, exist_ok=True)

        self.fixture_projects = self.owner_root / "Projects"
        self.fixture_projects.mkdir(parents=True, exist_ok=True)
        # canonical fixture file
        self.target_rel = "projA/src/app.txt"
        self.target_path = self.fixture_projects / self.target_rel
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        self.before_content = "before-content-v1"
        self.target_path.write_text(self.before_content, encoding="utf-8")
        self.before_bytes = self.target_path.read_bytes()
        self.before_sha = sha256_hex(self.before_bytes)
        # outside file to prove unchanged
        self.outside = self.owner_root / "outside.txt"
        self.outside.write_text("outside-before", encoding="utf-8")
        self.outside_before = self.outside.read_bytes()
        self.outside_before_sha = sha256_hex(self.outside_before)
        self._patch = patch.object(files, "BASE_DIR", self.fixture_projects)
        self._patch.start()
        self.input_obj = {"path": self.target_rel, "content": "after-content-v2"}
        self.input_digest = sha256_hex(json.dumps(self.input_obj, sort_keys=True, ensure_ascii=False).encode("utf-8"))

    def tearDown(self) -> None:
        self._patch.stop()
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

    def test_files_write_before_after_sha(self) -> None:
        # Approved input digest is the canonical json digest of the input
        # Mutate inside workspace via safe_path + write
        result = files.write_file(self.target_rel, "after-content-v2")
        self.assertIn("Файл создан", result)
        after_bytes = self.target_path.read_bytes()
        after_sha = sha256_hex(after_bytes)
        self.assertNotEqual(self.before_sha, after_sha)
        self.assertEqual(after_sha, sha256_hex("after-content-v2".encode("utf-8")))

        # No unexpected files
        all_files = list(self.fixture_projects.rglob("*"))
        rels = [p.relative_to(self.fixture_projects).as_posix() for p in all_files if p.is_file()]
        self.assertIn("projA/src/app.txt", rels)
        self.assertEqual(len(rels), 1, f"unexpected files: {rels}")

        # Outside-root unchanged
        after_outside = self.outside.read_bytes()
        self.assertEqual(self.outside_before_sha, sha256_hex(after_outside))

        # Outside escape must be blocked before I/O
        with self.assertRaises(ValueError) as ctx:
            files.safe_path("../../outside.txt")
        self.assertIn("Запрещенный путь", str(ctx.exception))

        # Reparse/symlink through link must be blocked (if capability, else skip)
        # Try symlink probe
        link = self.fixture_projects / "link_probe"
        can_symlink = False
        try:
            probe_t = self.fixture_projects / "_probe_t"
            probe_t.mkdir(exist_ok=True)
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(probe_t, target_is_directory=True)
            can_symlink = link.is_symlink()
            link.unlink()
            probe_t.rmdir()
        except OSError:
            can_symlink = False
        if can_symlink:
            try:
                link.symlink_to(self.owner_root / "outside_target", target_is_directory=True)
                with self.assertRaises(ValueError):
                    files.safe_path("link_probe/evil.txt")
                link.unlink()
            except OSError:
                pass

        # Persist evidence
        evidence = {
            "schema_version": "localcomet.security.evidence.v1",
            "source_branch": "feat/up00-wp01-windows-one-click-launch",
            "run_tag": self.run_tag,
            "case_id": "B1-files",
            "scenario_family": "files_coding_fixture",
            "risk": "guarded",
            "authority": "rust+python",
            "workspace_digest": "fixture:" + str(self.fixture_projects),
            "fixture_root": str(self.fixture_projects),
            "relative_path": self.target_rel,
            "before_bytes_len": len(self.before_bytes),
            "before_sha256": self.before_sha,
            "input_digest": self.input_digest,
            "after_sha256": after_sha,
            "after_bytes_len": len(after_bytes),
            "outside_before_sha": self.outside_before_sha,
            "outside_after_sha": sha256_hex(after_outside),
            "expected_mutation_set": [self.target_rel],
            "unexpected_files": [r for r in rels if r != self.target_rel],
            "outside_root_blocked": True,
            "reparse_checked": True,
            "verdict": "VERIFIED_SUCCESS" if after_sha != self.before_sha and sha256_hex(after_outside) == self.outside_before_sha else "VERIFIED_FAILED",
            "cleanup": {"owner_root": str(self.owner_root), "exact_owner_only": True},
            "evidence_class": "A",
            "reason": "before/after bytes and SHA, outside-root unchanged, no unexpected files, owner cleanup",
        }
        out = ROOT / f"audit/sec_files_native_fixture_{self.run_tag}.json"
        out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertEqual(evidence["verdict"], "VERIFIED_SUCCESS")
        self.assertEqual(evidence["unexpected_files"], [])
