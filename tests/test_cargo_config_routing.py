"""Repo-level Cargo routing tests (Part A §8) + verdict selection (§17).

Offline assertions parse the real repository ``.cargo/config.toml`` and the
resolver contract; the live direct-invocation proof is opt-in via
``LOCALCOMET_CARGO_ROUTING_LIVE=1`` so the normal suite stays hermetic.
Destructive scenarios use synthetic fixtures only; no cargo clean, no
deletion of any existing target.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.launch_localcomet_dev import LauncherHold  # noqa: E402
from tools.launch_localcomet_dev import (  # noqa: E402
    build_launch_environment,
    canonical_cargo_target_base,
)
from tools.storage_verdict import (  # noqa: E402
    VERDICT_FULL,
    VERDICT_NOT_ACCEPTED,
    VERDICT_PARTIAL,
    select_storage_verdict,
)


def _config() -> dict:
    return tomllib.loads((ROOT / ".cargo" / "config.toml").read_text(encoding="utf-8"))


class RepoConfigTests(unittest.TestCase):
    def test_config_exists_and_parses(self) -> None:
        data = _config()
        self.assertIn("build", data)

    def test_target_dir_is_not_source_local(self) -> None:
        build = _config()["build"]
        raw = str(build["target-dir"])
        self.assertNotEqual(raw.strip(), "target")
        self.assertFalse(Path(raw).is_absolute())

    def test_relative_paths_resolve_outside_repo(self) -> None:
        build = _config()["build"]
        repo = ROOT.resolve()
        for key in ("target-dir", "build-dir"):
            if key not in build:
                continue
            resolved = (repo / str(build[key])).resolve()
            self.assertFalse(
                resolved == repo or resolved.is_relative_to(repo),
                f"{key} resolves inside the repository: {resolved}",
            )
            self.assertTrue(resolved.is_dir() or key == "build-dir",
                            f"{key} location missing after live verification: {resolved}")

    def test_build_dir_when_declared_is_external(self) -> None:
        build = _config()["build"]
        if "build-dir" not in build:
            self.skipTest("build.build-dir not declared")
        resolved = (ROOT / str(build["build-dir"])).resolve()
        self.assertFalse(resolved.is_relative_to(ROOT.resolve()))


class ResolverOverrideRejectionTests(unittest.TestCase):
    """LocalComet-owned entry points must ignore/defeat poisoned ambient env."""

    def test_launcher_env_beats_source_local_ambient_override(self) -> None:
        import shutil as _shutil
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        local_root = Path(tmp.name)
        # Source tree must NOT contain the canonical base: keep the fake repo
        # under work/, the fake LOCALAPPDATA under AppData/.
        fake_repo = local_root / "work" / "repos" / "somerepo"
        fake_repo.joinpath("src-tauri").mkdir(parents=True)
        poisoned = str(fake_repo / "src-tauri" / "target")
        original = os.environ.get("LOCALAPPDATA")
        original_ctd = os.environ.get("CARGO_TARGET_DIR")
        try:
            os.environ["LOCALAPPDATA"] = str(local_root / "AppData" / "Local")
            os.environ["CARGO_TARGET_DIR"] = poisoned
            env = build_launch_environment(fake_repo.parent, _fake_paths(local_root / "work" / "repos"))
        finally:
            if original is not None:
                os.environ["LOCALAPPDATA"] = original
            else:
                os.environ.pop("LOCALAPPDATA", None)
            if original_ctd is not None:
                os.environ["CARGO_TARGET_DIR"] = original_ctd
            else:
                os.environ.pop("CARGO_TARGET_DIR", None)
        self.assertNotEqual(Path(env["CARGO_TARGET_DIR"]), Path(poisoned))
        # The resolved dir is always the canonical BuildCache base.
        self.assertEqual(Path(env["CARGO_TARGET_DIR"]).name, "CargoTarget")

    def test_resolver_rejects_repo_inside_subkey(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_root = Path(tmp)
            repo = local_root / "repo"
            (repo / "src").mkdir(parents=True)
            env = {"LOCALAPPDATA": str(local_root / "AppData" / "Local")}
            with self.assertRaises(LauncherHold):
                from tools.launch_localcomet_dev import resolve_canonical_cargo_target_dir

                resolve_canonical_cargo_target_dir(repo, env=env, subkey="../..")


class LiveRoutingTests(unittest.TestCase):
    """Opt-in proof: direct cargo from the project directory, no env override."""

    def test_direct_invocation_resolves_external_without_env(self) -> None:
        if os.environ.get("LOCALCOMET_CARGO_ROUTING_LIVE") != "1":
            self.skipTest("set LOCALCOMET_CARGO_ROUTING_LIVE=1 for the live proof")
        project = ROOT / "desktop" / "localcomet-desktop" / "src-tauri"
        env = {k: v for k, v in os.environ.items() if k != "CARGO_TARGET_DIR"}
        completed = subprocess.run(
            ["cargo", "metadata", "--no-deps", "--format-version", "1"],
            cwd=str(project), env=env, capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr[-400:])
        payload = __import__("json").loads(completed.stdout)
        resolved = Path(payload["target_directory"]).resolve()
        self.assertFalse(resolved.is_relative_to(ROOT.resolve()))
        self.assertNotEqual(resolved, project / "target")


class VerdictSelectionTests(unittest.TestCase):
    BASE_OK = {
        "repo_config_valid": True,
        "default_resolves_external": True,
        "source_local_recreated_after_fix": False,
        "direct_invocation_uses_external": True,
        "supported_entry_points_enforced": True,
        "legacy_inventory_read_only_complete": True,
        "automated_cleanup_deletions": 0,
        "automated_cleanup_process_stops": 0,
    }

    def test_full_requires_no_possible_overrides(self) -> None:
        state = dict(self.BASE_OK, explicit_overrides_remain_possible=False)
        self.assertEqual(select_storage_verdict(state), VERDICT_FULL)

    def test_partial_when_overrides_remain(self) -> None:
        state = dict(self.BASE_OK, explicit_overrides_remain_possible=True)
        self.assertEqual(select_storage_verdict(state), VERDICT_PARTIAL)

    def test_not_accepted_on_any_hard_failure(self) -> None:
        cases = [
            dict(self.BASE_OK, repo_config_valid=False),
            dict(self.BASE_OK, default_resolves_external=False),
            dict(self.BASE_OK, source_local_recreated_after_fix=True),
            dict(self.BASE_OK, direct_invocation_uses_external=False),
            dict(self.BASE_OK, automated_cleanup_deletions=3),
            dict(self.BASE_OK, automated_cleanup_process_stops=1),
        ]
        for state in cases:
            self.assertEqual(select_storage_verdict(state), VERDICT_NOT_ACCEPTED, state)

    def test_partial_when_entry_points_or_inventory_incomplete(self) -> None:
        self.assertEqual(
            select_storage_verdict(dict(self.BASE_OK, supported_entry_points_enforced=False)),
            VERDICT_PARTIAL,
        )
        self.assertEqual(
            select_storage_verdict(dict(self.BASE_OK, legacy_inventory_read_only_complete=False)),
            VERDICT_PARTIAL,
        )


def _fake_paths(local_root: Path):
    from tools.launch_localcomet_dev import RuntimePaths

    root = local_root / "LocalCometDev"
    return RuntimePaths(
        root=root,
        workspace=root / "workspace",
        cargo_target=root / "cargo-target",
        app_data=root / "app-data",
        resource_cache=root / "runtime-cache",
        state=root / "state.json",
        logs=root / "logs",
    )


if __name__ == "__main__":
    unittest.main()
