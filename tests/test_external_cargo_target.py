"""Offline contract tests for the unified external CARGO_TARGET_DIR (§3).

Pins the fail-closed resolver contract: one canonical base under
``%LOCALAPPDATA%\\LocalComet\\BuildCache\\CargoTarget``, isolated subkeys
confined to that base, and any path inside the repository rejected before a
build can start. All fixtures are synthetic temp directories.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.launch_localcomet_dev import (  # noqa: E402
    LauncherHold,
    RuntimePaths,
    build_launch_environment,
    cargo_target_evidence,
    canonical_cargo_target_base,
    resolve_canonical_cargo_target_dir,
)


def _fake_env(local_root: Path) -> dict[str, str]:
    return {"LOCALAPPDATA": str(local_root)}


class CanonicalBaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.local_root = Path(self._tmp.name)

    def test_default_base_is_external_buildcache_path(self) -> None:
        base = canonical_cargo_target_base(_fake_env(self.local_root))
        expected = self.local_root / "LocalComet" / "BuildCache" / "CargoTarget"
        self.assertEqual(base, expected.resolve())

    def test_missing_localappdata_fails_closed(self) -> None:
        with self.assertRaises(LauncherHold):
            canonical_cargo_target_base({})


class ResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.local_root = Path(self._tmp.name)
        self.repo = self.local_root / "repo"
        self.repo.mkdir(parents=True)
        self.env = _fake_env(self.local_root)

    def test_subkey_stays_inside_base_and_outside_repo(self) -> None:
        target = resolve_canonical_cargo_target_dir(
            self.repo, env=self.env, subkey="isolated/LocalCometHiddenCU_01"
        )
        base = canonical_cargo_target_base(self.env)
        self.assertTrue(target.is_relative_to(base))
        self.assertFalse(target.is_relative_to(self.repo.resolve()))

    def test_parent_escape_rejected(self) -> None:
        for bad in ("../escape", "isolated/../../outside"):
            with self.assertRaises(LauncherHold, msg=bad):
                resolve_canonical_cargo_target_dir(self.repo, env=self.env, subkey=bad)

    def test_absolute_subkey_rejected(self) -> None:
        with self.assertRaises(LauncherHold):
            resolve_canonical_cargo_target_dir(
                self.repo, env=self.env, subkey=str(self.local_root / "elsewhere")
            )

    def test_repo_inside_target_rejected(self) -> None:
        # A repo nested under the base would make the target a source parent.
        nested_repo = canonical_cargo_target_base(self.env) / "isolated" / "repo-inside"
        with self.assertRaises(LauncherHold):
            resolve_canonical_cargo_target_dir(nested_repo, env=self.env)


class LaunchEnvironmentPropagationTests(unittest.TestCase):
    """§3.2: whatever npm/tauri/cargo inherit must be the canonical target."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.local_root = Path(self._tmp.name)
        self.source = self.local_root / "src"
        self.root = self.local_root / "LocalCometDev"
        self.workspace = self.root / "workspace"
        self.app_data = self.root / "app-data"
        for path in (self.source, self.workspace, self.app_data):
            path.mkdir(parents=True)

    def _paths(self):
        return RuntimePaths(
            root=self.root,
            workspace=self.workspace,
            cargo_target=self.root / "cargo-target",
            app_data=self.app_data,
            resource_cache=self.root / "runtime-cache",
            state=self.root / "state.json",
            logs=self.root / "logs",
        )

    def test_env_points_to_canonical_external_dir(self) -> None:
        import os as _os

        original = _os.environ.get("LOCALAPPDATA")
        try:
            _os.environ["LOCALAPPDATA"] = str(self.local_root)
            env = build_launch_environment(self.source, self._paths())
        finally:
            if original is not None:
                _os.environ["LOCALAPPDATA"] = original
        resolved = Path(env["CARGO_TARGET_DIR"]).resolve()
        expected = (
            self.local_root / "LocalComet" / "BuildCache" / "CargoTarget"
        ).resolve()
        self.assertEqual(resolved, expected)
        # The legacy RuntimePaths field must NOT leak into child processes.
        self.assertNotEqual(resolved, (self.root / "cargo-target").resolve())


class EvidenceParityTests(unittest.TestCase):
    def test_evidence_carries_owner_mode_schema_without_secrets(self) -> None:
        payload = cargo_target_evidence(Path("C:/x/base/isolated/k"), "isolated", subkey="isolated/k")
        self.assertEqual(payload["owner"], "localcomet-buildcache")
        self.assertEqual(payload["mode"], "isolated")
        self.assertEqual(payload["schema_version"], "localcomet.cargo-target.v1")
        self.assertEqual(payload["subkey"], "isolated/k")


if __name__ == "__main__":
    unittest.main()
