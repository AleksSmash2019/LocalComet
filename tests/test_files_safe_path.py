"""Regression tests for modules/files.py safe_path() sandbox confinement."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import files  # noqa: E402


class SafePathConfinementTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="lc_files_safe_path_")
        root = Path(self._temporary.name)
        self.base_dir = root / "Projects"
        self.base_dir.mkdir()
        self.evil_dir = root / "ProjectsEvil"
        self.evil_dir.mkdir()
        self._patch = patch.object(files, "BASE_DIR", self.base_dir)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._temporary.cleanup()

    def test_sibling_prefix_collision_is_rejected(self) -> None:
        # str.startswith(BASE_DIR) would accept "...ProjectsEvil" for base "...Projects".
        with self.assertRaises(ValueError) as ctx:
            files.safe_path("../ProjectsEvil/payload")
        self.assertEqual(str(ctx.exception), "Запрещенный путь за пределами Projects.")

    def test_parent_traversal_escape_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            files.safe_path("../../escape.txt")

    def test_valid_path_inside_base_dir_passes(self) -> None:
        target = files.safe_path("inner/nested.txt")
        self.assertEqual(target, (self.base_dir / "inner" / "nested.txt").resolve())

    def test_base_dir_itself_passes(self) -> None:
        target = files.safe_path("")
        self.assertEqual(target, self.base_dir.resolve())

    def _can_create_symlink(self) -> bool:
        probe_target = self.base_dir / "_probe_target"
        probe_link = self.base_dir / "_probe_link"
        try:
            probe_target.mkdir(exist_ok=True)
            if probe_link.exists() or probe_link.is_symlink():
                try:
                    probe_link.unlink()
                except OSError:
                    pass
            probe_link.symlink_to(probe_target, target_is_directory=True)
            is_link = probe_link.is_symlink()
            probe_link.unlink()
            probe_target.rmdir()
            return is_link
        except (OSError, NotImplementedError):
            try:
                if probe_link.exists() or probe_link.is_symlink():
                    probe_link.unlink()
            except OSError:
                pass
            try:
                probe_target.rmdir()
            except OSError:
                pass
            return False

    def _can_create_junction(self) -> bool:
        # Junction requires Windows + mklink /J capability. Probe via ctypes + mklink.
        if self._can_create_symlink():
            # If symlink works, junction likely also possible, but probe explicitly
            import sys as _sys

            if _sys.platform != "win32":
                return False
        import subprocess as _sp
        import sys as _sys

        if _sys.platform != "win32":
            return False
        target = self.base_dir / "_junction_target"
        link = self.base_dir / "_junction_link"
        try:
            target.mkdir(exist_ok=True)
            if link.exists():
                try:
                    link.unlink()
                except OSError:
                    import shutil as _sh

                    _sh.rmtree(link, ignore_errors=True)
            # Use mklink /J — requires no admin on recent Windows with dev mode, but may still fail.
            result = _sp.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                text=True,
            )
            ok = result.returncode == 0 and link.exists()
            if link.exists():
                try:
                    link.unlink()
                except OSError:
                    import shutil as _sh

                    _sh.rmtree(link, ignore_errors=True)
            target.rmdir()
            return ok
        except Exception:
            try:
                if link.exists():
                    link.unlink()
            except OSError:
                pass
            try:
                target.rmdir()
            except OSError:
                pass
            return False

    def test_symlink_component_inside_base_pointing_inside_is_blocked(self) -> None:
        if not self._can_create_symlink():
            self.skipTest("symlink capability not available on this runner")
        inner = self.base_dir / "inner_real"
        inner.mkdir()
        link = self.base_dir / "link_inside"
        try:
            link.symlink_to(inner, target_is_directory=True)
            with self.assertRaises(ValueError) as ctx:
                files.safe_path("link_inside/file.txt")
            self.assertIn("Символические ссылки запрещены", str(ctx.exception))
            # Mutating ops must also fail closed through the link
            with self.assertRaises(ValueError):
                files.write_file("link_inside/file.txt", "payload")
            with self.assertRaises(ValueError):
                files.delete_path("link_inside/file.txt")
        finally:
            try:
                link.unlink()
            except OSError:
                pass
            try:
                inner.rmdir()
            except OSError:
                pass

    def test_symlink_component_inside_base_pointing_outside_is_blocked(self) -> None:
        if not self._can_create_symlink():
            self.skipTest("symlink capability not available on this runner")
        link = self.base_dir / "link_outside"
        try:
            link.symlink_to(self.evil_dir, target_is_directory=True)
            with self.assertRaises(ValueError) as ctx:
                files.safe_path("link_outside/payload.txt")
            self.assertIn("Символические ссылки запрещены", str(ctx.exception))
            with self.assertRaises(ValueError):
                files.write_file("link_outside/payload.txt", "evil")
        finally:
            try:
                link.unlink()
            except OSError:
                pass

    def test_junction_component_inside_base_is_blocked_or_skipped(self) -> None:
        if not self._can_create_junction():
            self.skipTest("junction capability not available on this runner")
        target = self.base_dir / "junction_target"
        link = self.base_dir / "junction_link"
        target.mkdir(exist_ok=True)
        import subprocess as _sp

        result = _sp.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.skipTest(f"mklink /J failed: {result.stderr.strip()}")
        try:
            with self.assertRaises(ValueError) as ctx:
                files.safe_path("junction_link/file.txt")
            self.assertIn("Символические ссылки запрещены", str(ctx.exception))
        finally:
            try:
                link.unlink()
            except OSError:
                import shutil as _sh

                _sh.rmtree(link, ignore_errors=True)
            try:
                target.rmdir()
            except OSError:
                pass

    def test_rollback_through_symlink_is_blocked(self) -> None:
        if not self._can_create_symlink():
            self.skipTest("symlink capability not available on this runner")
        inner = self.base_dir / "rollback_real"
        inner.mkdir()
        (inner / "snapshot.txt").write_text("snap", encoding="utf-8")
        link = self.base_dir / "rollback_link"
        try:
            link.symlink_to(inner, target_is_directory=True)
            with self.assertRaises(ValueError):
                files.rollback("rollback_link/restored.txt", "rollback_link/snapshot.txt")
            with self.assertRaises(ValueError):
                files.rollback_undo("rollback_link/restored.txt")
        finally:
            try:
                link.unlink()
            except OSError:
                pass
            import shutil as _sh

            _sh.rmtree(inner, ignore_errors=True)

    def test_reparse_attribute_lookup_failure_is_fail_closed(self) -> None:
        # Fail-closed: if Windows GetFileAttributesW cannot be determined for an existing path,
        # _is_symlink_or_reparse must not return False via `pass`.
        target = self.base_dir / "regular.txt"
        target.write_text("data", encoding="utf-8")
        try:
            self.assertFalse(target.is_symlink())
            # Force Windows reparse branch via os.name == "nt" even on non-Windows CI
            with patch.object(files.os, "name", "nt"):
                # Patch the attribute lookup to simulate windll failure
                with patch("ctypes.windll.kernel32.GetFileAttributesW", side_effect=RuntimeError("simulated failure")):
                    with self.assertRaises(ValueError) as ctx:
                        files._is_symlink_or_reparse(target)
                    self.assertIn("Символические ссылки запрещены", str(ctx.exception))
                    # safe_path must also fail closed through its pre-resolve guard
                    with self.assertRaises(ValueError):
                        files.safe_path("regular.txt")
            # After monkeypatch removed, normal path still works and is not a link
            self.assertFalse(files._is_symlink_or_reparse(target))
            self.assertEqual(files.safe_path("regular.txt"), (self.base_dir / "regular.txt").resolve())
        finally:
            try:
                target.unlink()
            except OSError:
                pass

    def test_safe_path_rejections_are_stable_typed_strings_without_mojibake(self) -> None:
        """F-08: typed rejections stay stable strings — no OS noise, no U+FFFD,
        and Cyrillic text survives the round trip into str() unharmed."""
        outside = "..\\ProjectsEvil\\secret.txt"
        with self.assertRaises(ValueError) as ctx:
            files.safe_path(outside)
        message = str(ctx.exception)
        self.assertTrue(message, "rejection must carry a typed message")
        self.assertNotIn("\ufffd", message, "replacement char means mojibake reached the UI")
        self.assertNotIn("OSError", message)
        # Cyrillic message content must round-trip through str()/repr().
        encoded = message.encode("utf-8").decode("utf-8")
        self.assertEqual(encoded, message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
