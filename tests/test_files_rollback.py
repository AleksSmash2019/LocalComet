"""Tests for files.rollback (T9 — path A).

Acceptance criteria:
1. rollback without approval token does not change file on disk
   (NOTE: approval enforcement is in Rust; these tests verify the Python
   function's own path-A contract, not the Rust approval boundary).
2. After rollback, rollback_undo restores the original content.
3. rollback of a non-existent snapshot returns an error string, not an exception.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


# ---------------------------------------------------------------------------
# Minimal stub for modules.project_paths so tests can import modules.files
# without the full LocalComet runtime installed.
# ---------------------------------------------------------------------------

def _install_stubs(tmp_path: Path) -> None:
    stub = types.ModuleType("modules")
    stub.project_paths = types.ModuleType("modules.project_paths")
    stub.project_paths.projects_dir = lambda: tmp_path / "Projects"  # type: ignore[assignment]
    sys.modules.setdefault("modules", stub)
    sys.modules["modules.project_paths"] = stub.project_paths


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_files_module(tmp_path: Path):
    """Load modules/files.py with a mocked projects_dir pointing at tmp_path."""
    _install_stubs(tmp_path)
    # Force fresh import so BASE_DIR is recomputed against tmp_path.
    spec = importlib.util.spec_from_file_location(
        "modules.files_test_fresh",
        Path(__file__).parent.parent / "modules" / "files.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

import importlib.util
import pytest


@pytest.fixture()
def files_mod(tmp_path: Path):
    return _load_files_module(tmp_path)


def test_rollback_restores_content(files_mod, tmp_path: Path) -> None:
    """After rollback(), target contains the snapshot content."""
    projects = tmp_path / "Projects"
    projects.mkdir(parents=True, exist_ok=True)

    target = projects / "target.txt"
    snapshot = projects / "snapshot.txt"

    target.write_text("original content", encoding="utf-8")
    snapshot.write_text("snapshot content", encoding="utf-8")

    result = files_mod.rollback("target.txt", "snapshot.txt")

    assert target.read_text(encoding="utf-8") == "snapshot content"
    assert "Восстановлено" in result


def test_rollback_undo_restores_original(files_mod, tmp_path: Path) -> None:
    """rollback_undo() restores the content displaced by rollback()."""
    projects = tmp_path / "Projects"
    projects.mkdir(parents=True, exist_ok=True)

    target = projects / "target.txt"
    snapshot = projects / "snapshot.txt"

    target.write_text("original content", encoding="utf-8")
    snapshot.write_text("snapshot content", encoding="utf-8")

    files_mod.rollback("target.txt", "snapshot.txt")
    assert target.read_text(encoding="utf-8") == "snapshot content"

    undo_result = files_mod.rollback_undo("target.txt")
    assert target.read_text(encoding="utf-8") == "original content"
    assert "Откат отменён" in undo_result


def test_rollback_missing_snapshot_returns_error(files_mod, tmp_path: Path) -> None:
    """rollback() with non-existent snapshot returns error string, not exception."""
    projects = tmp_path / "Projects"
    projects.mkdir(parents=True, exist_ok=True)

    result = files_mod.rollback("target.txt", "nonexistent_snapshot.txt")

    assert isinstance(result, str)
    assert "Snapshot не найден" in result
    # Target must not have been created.
    assert not (projects / "target.txt").exists()


def test_rollback_snapshot_not_deleted(files_mod, tmp_path: Path) -> None:
    """rollback() does not delete the snapshot file (path A contract)."""
    projects = tmp_path / "Projects"
    projects.mkdir(parents=True, exist_ok=True)

    target = projects / "target.txt"
    snapshot = projects / "snapshot.txt"

    target.write_text("v1", encoding="utf-8")
    snapshot.write_text("v2", encoding="utf-8")

    files_mod.rollback("target.txt", "snapshot.txt")

    assert snapshot.exists(), "snapshot must be preserved after rollback"


def test_rollback_undo_no_prior_snapshot(files_mod, tmp_path: Path) -> None:
    """rollback_undo() without a prior rollback returns error, not exception."""
    projects = tmp_path / "Projects"
    projects.mkdir(parents=True, exist_ok=True)

    result = files_mod.rollback_undo("no_prior.txt")

    assert isinstance(result, str)
    assert "снимка" in result or "Нет" in result
