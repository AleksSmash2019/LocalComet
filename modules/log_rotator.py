"""Log rotation and compression for AI sub-agent artifact traces.

Keeps the Obsidian-indexed ``.pi-subagents/artifacts`` tree light: active trace
events stay on a volatile ``.tmp`` path, and once a session ends or a size
boundary is crossed, they are compressed into a single ``.zip`` under an
archive directory and purged from the active path.

This is a pure-Python, dependency-free module (stdlib only). It never touches
unrelated files and is safe to run repeatedly (idempotent).

Design constraints (see SECURITY.md / workspace policy):
- Only ``*.jsonl``, ``*.json`` and ``*.md`` artifacts are rotated. Everything
  else (including ``.tmp`` markers and unknown extensions) is left in place.
- Files are only removed *after* they have been successfully written into the
  archive. A failed compression leaves the originals untouched.
- A dry-run mode reports what *would* happen without mutating the filesystem.
"""

from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# Default boundary: 5 MiB. Crossed when the sum of rotatable bytes >= boundary.
DEFAULT_ROTATE_BOUNDARY_BYTES = 5 * 1024 * 1024

# Extensions eligible for rotation. Everything else is preserved as-is.
ROTATABLE_SUFFIXES = frozenset({".jsonl", ".json", ".md"})


@dataclass(frozen=True)
class RotationPlan:
    """What a rotation would do, without side effects (dry-run friendly)."""

    active_dir: Path
    archive_dir: Path
    archive_name: str
    files: tuple[Path, ...]
    total_bytes: int

    @property
    def should_rotate(self) -> bool:
        return bool(self.files)


class LogRotator:
    """Rotates and compresses sub-agent artifact logs out of the live tree."""

    def __init__(self, vault_path: Path, boundary_bytes: int = DEFAULT_ROTATE_BOUNDARY_BYTES) -> None:
        self.vault_root = Path(vault_path)
        self.boundary_bytes = int(boundary_bytes)
        self.active_dir = self.vault_root / ".pi-subagents" / "artifacts"
        self.archive_dir = self.vault_root / ".pi-subagents" / "archive"

    # -- discovery ---------------------------------------------------------

    def _rotatable_files(self) -> list[Path]:
        """Rotatable artifact files, largest first (stable ordering)."""
        if not self.active_dir.is_dir():
            return []
        files: list[Path] = []
        for entry in self.active_dir.iterdir():
            if entry.is_file() and entry.suffix.lower() in ROTATABLE_SUFFIXES:
                files.append(entry)
        files.sort(key=lambda p: (-p.stat().st_size, p.name))
        return files

    def _build_plan(self, force: bool) -> RotationPlan:
        files = self._rotatable_files()
        if not files:
            return RotationPlan(
                active_dir=self.active_dir,
                archive_dir=self.archive_dir,
                archive_name="",
                files=(),
                total_bytes=0,
            )
        total = sum(f.stat().st_size for f in files)
        if not force and total < self.boundary_bytes:
            return RotationPlan(
                active_dir=self.active_dir,
                archive_dir=self.archive_dir,
                archive_name="",
                files=(),
                total_bytes=total,
            )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_name = f"session_logs_{stamp}.zip"
        return RotationPlan(
            active_dir=self.active_dir,
            archive_dir=self.archive_dir,
            archive_name=archive_name,
            files=tuple(files),
            total_bytes=total,
        )

    # -- API ---------------------------------------------------------------

    def plan(self, force: bool = False) -> RotationPlan:
        """Return what a rotation would do. No side effects."""
        return self._build_plan(force=force)

    def rotate(self, force: bool = False) -> RotationPlan:
        """Rotate now; returns the executed plan (empty plan if nothing moved)."""
        plan = self._build_plan(force=force)
        if not plan.should_rotate:
            return plan

        self.archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = self.archive_dir / plan.archive_name

        # Compress first; only then delete originals. On failure originals stay.
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file in plan.files:
                zipf.write(file, arcname=file.name)

        removed = 0
        for file in plan.files:
            try:
                file.unlink()
                removed += 1
            except OSError:
                # Best-effort cleanup; a locked file must not abort the whole
                # rotation or leave the archive in a half-written state.
                continue

        return plan

    def rotate_if_needed(self) -> RotationPlan:
        """Boundary-driven rotation: only acts when the size boundary is crossed."""
        return self.rotate(force=False)


def iter_rotatable_files(active_dir: str | Path) -> Iterable[Path]:
    """Convenience helper: yield rotatable files under *active_dir*."""
    directory = Path(active_dir)
    if not directory.is_dir():
        return
    for entry in directory.iterdir():
        if entry.is_file() and entry.suffix.lower() in ROTATABLE_SUFFIXES:
            yield entry
