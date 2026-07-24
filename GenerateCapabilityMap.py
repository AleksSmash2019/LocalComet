"""Minimal placeholder, created 2026-07-25.

The original capability map generation module NEVER existed in this
repository (legacy of fictitious reporting, incident M-04).  Test v677
verifies only the contract: import without side-effects plus
LOCALCOMET_ROOT portability.  Real capability map generation is a
deliberate backlog task: implement or remove together with the test.
"""
from __future__ import annotations

import os
from pathlib import Path


def _project_root() -> Path:
    value = os.environ.get("LOCALCOMET_ROOT", "").strip()
    if value:
        return Path(value).expanduser().resolve()
    return Path(__file__).resolve().parent
