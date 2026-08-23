from __future__ import annotations

from pathlib import Path
from typing import Callable

def make_relative_path(root: Path) -> Callable[[Path], str]:
    def relative(path: Path) -> str:
        try:
            return str(path.relative_to(root)).replace("\\", "/")
        except Exception:
            return str(path).replace("\\", "/")

    return relative

