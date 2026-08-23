"""Synthetic-fixture tests for owner-scoped cleanup (unified prompt §4.7).

Every test runs against throwaway temp directories with fabricated manifests.
Nothing here points at the real %LOCALAPPDATA%, the repository target, or any
user data; nothing is deleted outside those fixtures.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import owned_run_cleanup as cleanup  # noqa: E402


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class Fixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.repo = self.base / "repo"
        self.isolated = self.base / "isolated-root"
        self.udf = self.isolated / "webview2-user-data"
        self.udf.mkdir(parents=True)
        (self.udf / "profile.bin").write_bytes(b"0")
        self.now = datetime.now(timezone.utc)
        self.manifest_path, _ = cleanup.write_manifest(
            run_root=self.isolated,
            audit_copy_dir=self.base / "evidence",
            owner="localcomet-hidden-harness",
            repo_root=self.repo,
            isolated_root=self.isolated,
            cargo_target_dir=self.base / "BuildCache" / "CargoTarget" / "isolated" / "x",
            vite_port=0,
            cdp_port=0,
            hidden_desktop="LocalCometHiddenCU_test",
            root_pid=0,
            owned_pids=[],
            owned_paths=[self.udf],
        )
        self.manifest = cleanup.load_manifest(self.manifest_path)

    def _age_manifest(self, delta: timedelta) -> None:
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        data["created_utc"] = _iso(self.now - delta)
        self.manifest_path.write_text(json.dumps(data), encoding="utf-8")
        self.manifest = cleanup.load_manifest(self.manifest_path)

    def _complete(self) -> None:
        cleanup.mark_completed(self.manifest_path)
        self.manifest = cleanup.load_manifest(self.manifest_path)

    def _plan(self, mode: str):
        return cleanup.plan_cleanup(
            dict(self.manifest), mode=mode, policy=cleanup.RetentionPolicy(), now=self.now
        )


class ManifestTests(Fixture):
    def test_manifest_carries_schema_and_marker(self) -> None:
        self.assertEqual(self.manifest["schema_version"], cleanup.MANIFEST_SCHEMA)
        marker = json.loads((self.isolated / cleanup.MARKER_NAME).read_text(encoding="utf-8"))
        self.assertEqual(marker["run_id"], self.manifest["run_id"])
        self.assertNotEqual(self.manifest["run_id"], "")
        self.assertTrue(str(self.manifest["cargo_target_dir"]).startswith(str(self.base)))

    def test_foreign_schema_is_unowned(self) -> None:
        foreign = self.base / "foreign.json"
        foreign.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
        with self.assertRaises(cleanup.CleanupHold):
            cleanup.load_manifest(foreign)


class SelectionTests(Fixture):
    def test_valid_completed_current_run_is_selected(self) -> None:
        self._complete()
        plan = self._plan(cleanup.MODE_OWNED_CURRENT_RUN)
        self.assertEqual(len(plan), 1)
        self.assertTrue(plan[0]["eligible"], plan[0])

    def test_run_not_marked_completed_blocks_current_mode(self) -> None:
        plan = self._plan(cleanup.MODE_OWNED_CURRENT_RUN)
        self.assertFalse(plan[0]["eligible"])
        self.assertIn("run_not_marked_completed", plan[0]["reasons"])

    def test_unowned_directory_is_never_selected(self) -> None:
        stranger = self.base / "stranger-dir"
        stranger.mkdir()
        self._complete()
        plan = self._plan(cleanup.MODE_OWNED_CURRENT_RUN)
        planned_paths = [entry["path"] for entry in plan]
        self.assertNotIn(str(stranger.resolve()).lower(), [p.lower() for p in planned_paths])
        # Selection is manifest-driven: an unowned directory cannot appear in
        # any plan because it is not referenced by any valid owned manifest.
        self.assertEqual(planned_paths, [str(Path(self.manifest["owned_paths"][0]).resolve())])

    def test_repo_source_path_never_selected_even_if_listed(self) -> None:
        source_file = self.repo / "src"
        source_file.mkdir(parents=True, exist_ok=True)
        manifest = dict(self.manifest)
        manifest["owned_paths"] = [str(source_file)]
        plan = cleanup.plan_cleanup(manifest, mode=cleanup.MODE_OWNED_STALE_RUNS,
                                    policy=cleanup.RetentionPolicy(), now=self.now)
        self.assertFalse(plan[0]["eligible"])
        self.assertIn("inside_repo_root_forbidden", plan[0]["reasons"])

    def test_reparse_point_rejected(self) -> None:
        import _winapi

        link = self.isolated / "junction-target"
        real = self.base / "real-udf"
        real.mkdir(exist_ok=True)
        _winapi.CreateJunction(str(real), str(link))
        manifest = dict(self.manifest)
        manifest["owned_paths"] = [str(link)]
        plan = cleanup.plan_cleanup(manifest, mode=cleanup.MODE_OWNED_STALE_RUNS,
                                    policy=cleanup.RetentionPolicy(), now=self.now)
        self.assertIn("reparse_or_symlink_ambiguous", plan[0]["reasons"])

    def test_active_pid_blocks_cleanup(self) -> None:
        self._complete()
        manifest = dict(self.manifest)
        manifest["root_pid"] = os.getpid()  # this very test process: provably alive
        plan = cleanup.plan_cleanup(manifest, mode=cleanup.MODE_OWNED_CURRENT_RUN,
                                    policy=cleanup.RetentionPolicy(), now=self.now)
        self.assertFalse(plan[0]["eligible"])
        self.assertIn("owner_process_still_alive", plan[0]["reasons"])
        self.assertTrue(self.udf.exists())  # inventoried, not touched

    def test_active_lock_blocks_cleanup(self) -> None:
        self._complete()
        (self.isolated / cleanup.LOCK_NAME).write_text("", encoding="utf-8")
        plan = self._plan(cleanup.MODE_OWNED_CURRENT_RUN)
        self.assertFalse(plan[0]["eligible"])
        self.assertIn("active_lock_present", plan[0]["reasons"])

    def test_wrong_run_id_cannot_claim_foreign_path(self) -> None:
        other_root = self.base / "other-run"
        other_udf = other_root / "udf"
        other_udf.mkdir(parents=True)
        other_path, _ = cleanup.write_manifest(
            run_root=other_root,
            audit_copy_dir=self.base / "evidence2",
            owner="localcomet-hidden-harness",
            repo_root=self.repo,
            isolated_root=other_root,
            cargo_target_dir=self.base / "bc",
            vite_port=0,
            cdp_port=0,
            hidden_desktop="LocalCometHiddenCU_other",
            root_pid=0,
            owned_pids=[],
            owned_paths=[other_udf],
        )
        other = cleanup.load_manifest(other_path)
        cleanup.mark_completed(other_path)
        verdict = cleanup.evaluate_candidate(
            str(other_udf), dict(self.manifest), mode=cleanup.MODE_OWNED_CURRENT_RUN,
            policy=cleanup.RetentionPolicy(), now=self.now,
        )
        self.assertFalse(verdict["eligible"])
        self.assertIn("not_listed_in_manifest_owned_paths", verdict["reasons"])
        self.assertNotEqual(other["run_id"], self.manifest["run_id"])

    def test_expired_marker_selectable_only_in_stale_mode(self) -> None:
        self._age_manifest(timedelta(days=30))
        stale = self._plan(cleanup.MODE_OWNED_STALE_RUNS)
        self.assertTrue(stale[0]["eligible"], stale[0])
        fresh_blocked = cleanup.plan_cleanup(
            dict(self.manifest), mode=cleanup.MODE_OWNED_STALE_RUNS,
            policy=cleanup.RetentionPolicy(), now=self.now - timedelta(days=29),
        )
        self.assertIn("ttl_not_expired", fresh_blocked[0]["reasons"])
        current = cleanup.plan_cleanup(
            dict(self.manifest), mode=cleanup.MODE_OWNED_CURRENT_RUN,
            policy=cleanup.RetentionPolicy(), now=self.now,
        )
        self.assertIn("run_not_marked_completed", current[0]["reasons"])

    def test_listening_port_blocks_cleanup(self) -> None:
        import socket

        self._complete()
        listener = socket.socket()
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        manifest = dict(self.manifest)
        manifest["cdp_port"] = port
        plan = cleanup.plan_cleanup(manifest, mode=cleanup.MODE_OWNED_CURRENT_RUN,
                                    policy=cleanup.RetentionPolicy(), now=self.now)
        self.assertIn("cdp_port_still_listening", plan[0]["reasons"])
        self.assertFalse(plan[0]["eligible"])


class ExecutionTests(Fixture):
    def test_dry_run_never_deletes_and_counts_nothing(self) -> None:
        self._complete()
        plan = self._plan(cleanup.MODE_DRY_RUN)
        result = cleanup.execute_plan(plan, mode=cleanup.MODE_DRY_RUN)
        self.assertEqual(result["deleted_count"], 0)
        self.assertEqual(result["results"][0]["action"], "dry_run_no_deletion")
        self.assertTrue(self.udf.exists())

    def test_owned_current_run_deletes_only_manifest_paths(self) -> None:
        self._complete()
        decoy = self.isolated / "decoy-not-in-manifest"
        decoy.mkdir()
        plan = self._plan(cleanup.MODE_OWNED_CURRENT_RUN)
        result = cleanup.execute_plan(plan, mode=cleanup.MODE_OWNED_CURRENT_RUN)
        self.assertEqual(result["deleted_count"], 1)
        self.assertEqual(result["results"][0]["action"], "deleted")
        self.assertFalse(self.udf.exists())
        self.assertTrue(decoy.exists(), "unlisted sibling must survive")

    def test_cleanup_is_idempotent(self) -> None:
        self._complete()
        first = cleanup.execute_plan(self._plan(cleanup.MODE_OWNED_CURRENT_RUN),
                                     mode=cleanup.MODE_OWNED_CURRENT_RUN)
        second = cleanup.execute_plan(self._plan(cleanup.MODE_OWNED_CURRENT_RUN),
                                      mode=cleanup.MODE_OWNED_CURRENT_RUN)
        self.assertEqual(first["deleted_count"], 1)
        self.assertEqual(second["deleted_count"], 0)
        self.assertEqual(second["results"][0]["action"], "already_absent")

    def test_vanished_between_plan_and_execute_fails_closed(self) -> None:
        self._complete()
        plan = self._plan(cleanup.MODE_OWNED_CURRENT_RUN)
        shutil.rmtree(self.udf)
        result = cleanup.execute_plan(plan, mode=cleanup.MODE_OWNED_CURRENT_RUN)
        self.assertEqual(result["deleted_count"], 0)
        self.assertEqual(result["results"][0]["action"], "already_absent")


if __name__ == "__main__":
    unittest.main()
