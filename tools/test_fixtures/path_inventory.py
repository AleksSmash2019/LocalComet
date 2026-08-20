from __future__ import annotations

from os import walk
from pathlib import Path

SKIP_DIRS = {".git", "__pycache__", "artifacts", "target", "node_modules", ".svelte-kit"}


def paths_under(root: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for dirpath, dirnames, filenames in walk(root):
        dirnames[:] = [
            d for d in dirnames
            if not (Path(dirpath) / d).is_symlink() and d not in SKIP_DIRS
        ]
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_file():
                result[path.relative_to(root).as_posix()] = path.stat().st_size
    return result

def paths_under_set(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {path.relative_to(root).as_posix() for path in root.rglob('*')}
