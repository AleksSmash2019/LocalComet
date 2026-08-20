"""Tests for the skills subsystem: manifest validation, archive safety, lifecycle."""
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.skills import SkillsManager, SkillError, SkillErrorCode, validate_manifest_dict
from modules.skills.skills_archive import read_manifest_bytes


def _manifest(**over):
    base = {"id": "demo.skill", "name": "Demo", "version": "1.0.0",
            "entrypoint": "main.py", "permissions": ["filesystem.read"]}
    base.update(over)
    return base


def _make_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)


def _make_pkg(path: Path, manifest: dict, entry: bytes = b"print('ok')") -> None:
    files = {"skill.json": json.dumps(manifest).encode(), manifest["entrypoint"]: entry}
    _make_zip(path, files)


class ManifestTests(unittest.TestCase):
    def test_valid(self):
        m = validate_manifest_dict(_manifest())
        self.assertEqual(m.skill_id, "demo.skill")

    def test_bad_id(self):
        with self.assertRaises(SkillError):
            validate_manifest_dict(_manifest(id="Bad ID!"))

    def test_forbidden_permission(self):
        with self.assertRaises(SkillError) as cm:
            validate_manifest_dict(_manifest(permissions=["secrets.access"]))
        self.assertEqual(cm.exception.code, SkillErrorCode.PERMISSION_DENIED)

    def test_unknown_permission(self):
        with self.assertRaises(SkillError) as cm:
            validate_manifest_dict(_manifest(permissions=["root.access"]))
        self.assertEqual(cm.exception.code, SkillErrorCode.PERMISSION_UNKNOWN)

    def test_entrypoint_traversal(self):
        with self.assertRaises(SkillError):
            validate_manifest_dict(_manifest(entrypoint="../evil.py"))

    def test_entrypoint_abs(self):
        with self.assertRaises(SkillError):
            validate_manifest_dict(_manifest(entrypoint="C:/evil.py"))

    def test_bad_semver(self):
        with self.assertRaises(SkillError):
            validate_manifest_dict(_manifest(version="1.0"))

    def test_bad_checksum(self):
        with self.assertRaises(SkillError):
            validate_manifest_dict(_manifest(checksum="zz"))


class ArchiveTests(unittest.TestCase):
    def test_zip_slip_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "evil.zip"
            _make_zip(p, {"../escape.py": b"x", "skill.json": json.dumps(_manifest()).encode()})
            with self.assertRaises(SkillError) as cm:
                read_manifest_bytes(p)
            self.assertEqual(cm.exception.code, SkillErrorCode.ARCHIVE_PATH_TRAVERSAL)

    def test_missing_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nomanifest.zip"
            _make_zip(p, {"main.py": b"x"})
            with self.assertRaises(SkillError) as cm:
                read_manifest_bytes(p)
            self.assertEqual(cm.exception.code, SkillErrorCode.MANIFEST_MISSING)

    def test_corrupt(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.zip"
            p.write_bytes(b"PK\x03\x04garbage")
            with self.assertRaises(SkillError):
                read_manifest_bytes(p)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name) / "skills"
        self.mgr = SkillsManager(self.root)
        self.pkg = Path(self.td.name) / "demo.zip"
        _make_pkg(self.pkg, _manifest())

    def tearDown(self):
        self.td.cleanup()

    def test_install_disabled_by_default(self):
        res = self.mgr.install(self.pkg)
        self.assertEqual(res["state"], "DISABLED")
        self.assertEqual(self.mgr.list_skills()[0]["id"], "demo.skill")

    def test_duplicate_install_rejected(self):
        self.mgr.install(self.pkg)
        with self.assertRaises(SkillError) as cm:
            self.mgr.install(self.pkg)
        self.assertEqual(cm.exception.code, SkillErrorCode.SKILL_STATE_CONFLICT)

    def test_enable_execute_gate(self):
        self.mgr.install(self.pkg)
        # not enabled -> entrypoint blocked
        with self.assertRaises(SkillError):
            self.mgr.entrypoint_path("demo.skill")
        self.mgr.enable("demo.skill")
        ep = self.mgr.entrypoint_path("demo.skill")
        self.assertTrue(ep.name == "main.py")
        self.mgr.disable("demo.skill")
        with self.assertRaises(SkillError):
            self.mgr.entrypoint_path("demo.skill")

    def test_mutated_enabled_package_is_rejected_before_entrypoint_resolution(self):
        self.mgr.install(self.pkg)
        self.mgr.enable("demo.skill")
        entrypoint = self.root / "installed" / "demo.skill" / "main.py"
        entrypoint.write_text("print('tampered')", encoding="utf-8")
        with self.assertRaises(SkillError) as cm:
            self.mgr.entrypoint_path("demo.skill")
        self.assertEqual(cm.exception.code, SkillErrorCode.CHECKSUM_MISMATCH)

    def test_bundled_baseline_is_seeded_once(self):
        seeded = self.mgr.ensure_builtins()
        self.assertEqual(
            seeded,
            ["diagnostics-reader", "project-inspector", "runtime-doctor", "workspace-inspector"],
        )
        listed = self.mgr.list_skills()
        self.assertEqual(
            [skill["id"] for skill in listed],
            ["diagnostics-reader", "project-inspector", "runtime-doctor", "workspace-inspector"],
        )
        self.assertTrue(all(skill["state"] == "ENABLED" for skill in listed))
        self.assertTrue(all(skill["builtin"] for skill in listed))
        self.assertEqual(self.mgr.ensure_builtins(), [])

    def test_legacy_test_skills_are_hidden_and_disabled(self):
        legacy = {"demo-echo", "verify-echo-174869", "verify-echo-655999"}
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "registry.json").write_text(
            json.dumps({skill_id: {"state": "ENABLED", "hidden": False} for skill_id in legacy}),
            encoding="utf-8",
        )
        self.mgr = SkillsManager(self.root)

        self.mgr.ensure_builtins()

        for skill_id in legacy:
            self.assertEqual(self.mgr._registry[skill_id]["state"], "DISABLED")
            self.assertTrue(self.mgr._registry[skill_id]["hidden"])

    def test_builtin_invocation_is_bounded_json(self):
        from modules.skills.skills_invoker import invoke_skill

        with tempfile.TemporaryDirectory() as skills_root:
            previous = os.environ.get("LOCALCOMET_SKILLS_ROOT")
            os.environ["LOCALCOMET_SKILLS_ROOT"] = skills_root
            try:
                result = invoke_skill(
                    "runtime-doctor",
                    {"checks": ["python"]},
                    ["settings.read", "process.spawn"],
                )
            finally:
                if previous is None:
                    os.environ.pop("LOCALCOMET_SKILLS_ROOT", None)
                else:
                    os.environ["LOCALCOMET_SKILLS_ROOT"] = previous
        self.assertEqual(result["skill"], "runtime-doctor")
        self.assertEqual(result["returncode"], 0, result)
        self.assertIn('"checks"', result["stdout"])

    def test_uninstall_cleanup(self):
        self.mgr.install(self.pkg)
        res = self.mgr.uninstall("demo.skill")
        self.assertTrue(res["removed"])
        self.assertEqual(self.mgr.list_skills(), [])

    def test_not_found(self):
        with self.assertRaises(SkillError) as cm:
            self.mgr.enable("nope")
        self.assertEqual(cm.exception.code, SkillErrorCode.SKILL_NOT_FOUND)

    def test_checksum_mismatch(self):
        bad = Path(self.td.name) / "bad.zip"
        _make_pkg(bad, _manifest(checksum="0" * 64))
        with self.assertRaises(SkillError) as cm:
            self.mgr.install(bad)
        self.assertEqual(cm.exception.code, SkillErrorCode.CHECKSUM_MISMATCH)


if __name__ == "__main__":
    unittest.main()
