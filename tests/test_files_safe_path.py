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


if __name__ == "__main__":
    unittest.main(verbosity=2)
