"""Tests for modules.log_rotator (boundary, compression, idempotence, safety)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from modules.log_rotator import ROTATABLE_SUFFIXES, LogRotator


def _make_artifact(dir_path: Path, name: str, size: int) -> Path:
    path = dir_path / name
    path.write_bytes(b"x" * size)
    return path


def test_no_rotation_below_boundary(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path, boundary_bytes=5 * 1024 * 1024)
    rotator.active_dir.mkdir(parents=True)
    _make_artifact(rotator.active_dir, "a.jsonl", 1000)
    _make_artifact(rotator.active_dir, "b.json", 2000)

    plan = rotator.rotate()

    assert not plan.should_rotate
    assert (rotator.active_dir / "a.jsonl").exists()
    assert (rotator.active_dir / "b.json").exists()
    assert not rotator.archive_dir.exists()


def test_rotation_above_boundary_compresses_and_purges(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path, boundary_bytes=1000)
    rotator.active_dir.mkdir(parents=True)
    _make_artifact(rotator.active_dir, "a.jsonl", 600)
    _make_artifact(rotator.active_dir, "b.json", 600)

    plan = rotator.rotate()

    assert plan.should_rotate
    assert len(plan.files) == 2
    archive = rotator.archive_dir / plan.archive_name
    assert archive.exists()
    with zipfile.ZipFile(archive) as zipf:
        names = set(zipf.namelist())
    assert names == {"a.jsonl", "b.json"}
    # Originals purged after successful compression.
    assert not (rotator.active_dir / "a.jsonl").exists()
    assert not (rotator.active_dir / "b.json").exists()


def test_non_rotatable_extensions_preserved(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path, boundary_bytes=0)  # force rotate everything eligible
    rotator.active_dir.mkdir(parents=True)
    _make_artifact(rotator.active_dir, "keep.tmp", 100)
    _make_artifact(rotator.active_dir, "keep.unknown", 100)
    _make_artifact(rotator.active_dir, "rotate.jsonl", 100)

    plan = rotator.rotate()

    assert [p.name for p in plan.files] == ["rotate.jsonl"]
    assert (rotator.active_dir / "keep.tmp").exists()
    assert (rotator.active_dir / "keep.unknown").exists()


def test_force_rotates_even_below_boundary(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path, boundary_bytes=5 * 1024 * 1024)
    rotator.active_dir.mkdir(parents=True)
    _make_artifact(rotator.active_dir, "small.jsonl", 10)

    plan = rotator.rotate(force=True)

    assert plan.should_rotate
    assert len(plan.files) == 1


def test_plan_is_side_effect_free(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path, boundary_bytes=1000)
    rotator.active_dir.mkdir(parents=True)
    _make_artifact(rotator.active_dir, "a.jsonl", 600)
    _make_artifact(rotator.active_dir, "b.json", 600)

    plan = rotator.plan()

    assert plan.should_rotate
    assert not rotator.archive_dir.exists()
    assert (rotator.active_dir / "a.jsonl").exists()
    assert (rotator.active_dir / "b.json").exists()


def test_rotatable_suffixes_constant_is_expected() -> None:
    assert ROTATABLE_SUFFIXES == frozenset({".jsonl", ".json", ".md"})
