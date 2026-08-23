from __future__ import annotations

import os
from pathlib import Path
from typing import List

def iter_files(directory: Path) -> List[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    result: List[Path] = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git"}]
        for name in files:
            try:
                p = Path(root) / name
                if p.is_file():
                    result.append(p)
            except Exception:
                continue
    return result

