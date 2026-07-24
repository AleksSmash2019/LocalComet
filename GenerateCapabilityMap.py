from __future__ import annotations

import os
from pathlib import Path


def _project_root() -> Path:
    value = os.environ.get("LOCALCOMET_ROOT", "").strip()
    if value:
        return Path(value).expanduser().resolve()
    return Path(__file__).resolve().parent
