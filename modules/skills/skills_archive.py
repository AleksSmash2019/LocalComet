"""Safe skill-package archive extraction.

Guards: archive type allowlist, magic bytes, size caps, compression-bomb
ratio/count caps, absolute-path and `..` rejection, symlink rejection.
Extraction goes to a quarantine dir; nothing is executed here.
"""

from __future__ import annotations

import io
import json
import re
import tarfile
import zipfile
from pathlib import Path

from modules.skills.skills_contract import (
    ALLOWED_ARCHIVE_SUFFIXES,
    ARCHIVE_BOMB_RATIO,
    GZIP_MAGIC,
    MAX_ARCHIVE_BYTES,
    MAX_ARCHIVE_FILES,
    MAX_EXTRACTED_BYTES,
    MAX_MANIFEST_BYTES,
    WINDOWS_ABS_RE,
    ZIP_MAGIC,
    SkillError,
    SkillErrorCode,
)


def _safe_member_name(name: str) -> str:
    if not name or len(name) > 256:
        raise SkillError(SkillErrorCode.ARCHIVE_PATH_TRAVERSAL, "archive member name is empty or too long")
    if name.startswith(("/", "\\")) or WINDOWS_ABS_RE.match(name):
        raise SkillError(SkillErrorCode.ARCHIVE_PATH_TRAVERSAL, "absolute path in archive member")
    parts = re.split(r"[\\/]", name)
    if any(p in ("", ".", "..") for p in parts):
        raise SkillError(SkillErrorCode.ARCHIVE_PATH_TRAVERSAL, "path traversal in archive member")
    return "/".join(parts)


def detect_archive_kind(data: bytes, filename: str) -> str:
    lower = filename.lower()
    if data[:4] == ZIP_MAGIC and lower.endswith(".zip"):
        return "zip"
    if data[:2] == GZIP_MAGIC and lower.endswith(ALLOWED_ARCHIVE_SUFFIXES):
        return "tar.gz"
    raise SkillError(SkillErrorCode.ARCHIVE_TYPE_DENIED, "unsupported archive type or magic bytes")


def read_manifest_bytes_from_data(data: bytes, filename: str) -> bytes:
    """Return skill.json bytes from an in-memory archive buffer (no execution)."""
    if len(data) > MAX_ARCHIVE_BYTES:
        raise SkillError(SkillErrorCode.ARCHIVE_TOO_LARGE, "archive exceeds maximum size")
    kind = detect_archive_kind(data, filename)
    if kind == "zip":
        return _read_manifest_zip(data)
    return _read_manifest_targz(data)


def read_manifest_bytes(archive_path: Path) -> bytes:
    """Read and return skill.json bytes from a validated archive (no execution)."""
    return read_manifest_bytes_from_data(archive_path.read_bytes(), archive_path.name)


def _read_manifest_zip(data: bytes) -> bytes:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise SkillError(SkillErrorCode.ARCHIVE_CORRUPT, "corrupt zip archive") from exc
    with zf:
        names = zf.namelist()
        if len(names) > MAX_ARCHIVE_FILES:
            raise SkillError(SkillErrorCode.ARCHIVE_BOMB, "archive has too many files")
        total_uncompressed = 0
        manifest_info = None
        for info in zf.infolist():
            _safe_member_name(info.filename)
            # zip symlinks: unix mode high bits 0o120000
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise SkillError(SkillErrorCode.ARCHIVE_SYMLINK_DENIED, "symlink in archive is denied")
            total_uncompressed += info.file_size
            if total_uncompressed > MAX_EXTRACTED_BYTES:
                raise SkillError(SkillErrorCode.ARCHIVE_BOMB, "archive expands beyond limit")
            base = info.filename.rsplit("/", 1)[-1]
            if base == "skill.json":
                manifest_info = info
        _check_ratio(len(data), total_uncompressed)
        if manifest_info is None:
            raise SkillError(SkillErrorCode.MANIFEST_MISSING, "skill.json not found in archive")
        if manifest_info.file_size > MAX_MANIFEST_BYTES:
            raise SkillError(SkillErrorCode.MANIFEST_TOO_LARGE, "skill.json too large")
        return zf.read(manifest_info)


def _read_manifest_targz(data: bytes) -> bytes:
    try:
        tf = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    except tarfile.TarError as exc:
        raise SkillError(SkillErrorCode.ARCHIVE_CORRUPT, "corrupt tar.gz archive") from exc
    with tf:
        members = tf.getmembers()
        if len(members) > MAX_ARCHIVE_FILES:
            raise SkillError(SkillErrorCode.ARCHIVE_BOMB, "archive has too many files")
        total_uncompressed = 0
        manifest_member = None
        for m in members:
            _safe_member_name(m.name)
            if m.issym() or m.islnk():
                raise SkillError(SkillErrorCode.ARCHIVE_SYMLINK_DENIED, "link in archive is denied")
            if m.isdev():
                raise SkillError(SkillErrorCode.ARCHIVE_CORRUPT, "device entry in archive is denied")
            if m.isfile():
                total_uncompressed += m.size
                if total_uncompressed > MAX_EXTRACTED_BYTES:
                    raise SkillError(SkillErrorCode.ARCHIVE_BOMB, "archive expands beyond limit")
                if m.name.rsplit("/", 1)[-1] == "skill.json":
                    manifest_member = m
        _check_ratio(len(data), total_uncompressed)
        if manifest_member is None:
            raise SkillError(SkillErrorCode.MANIFEST_MISSING, "skill.json not found in archive")
        if manifest_member.size > MAX_MANIFEST_BYTES:
            raise SkillError(SkillErrorCode.MANIFEST_TOO_LARGE, "skill.json too large")
        f = tf.extractfile(manifest_member)
        if f is None:
            raise SkillError(SkillErrorCode.ARCHIVE_CORRUPT, "cannot read skill.json")
        return f.read()


def _check_ratio(compressed: int, uncompressed: int) -> None:
    if compressed > 0 and uncompressed // max(compressed, 1) > ARCHIVE_BOMB_RATIO:
        raise SkillError(SkillErrorCode.ARCHIVE_BOMB, "suspicious compression ratio")


def parse_manifest(manifest_bytes: bytes) -> dict:
    try:
        obj = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, "skill.json is not valid UTF-8 JSON") from exc
    if not isinstance(obj, dict):
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, "skill.json must be a JSON object")
    return obj


def extract_archive_from_data(data: bytes, filename: str, dest_dir: Path) -> list[str]:
    """Extract an in-memory archive buffer into dest_dir. Returns relative file paths."""
    if len(data) > MAX_ARCHIVE_BYTES:
        raise SkillError(SkillErrorCode.ARCHIVE_TOO_LARGE, "archive exceeds maximum size")
    kind = detect_archive_kind(data, filename)
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    if kind == "zip":
        _extract_zip(data, dest_dir, written)
    else:
        _extract_targz(data, dest_dir, written)
    return written


def extract_archive(archive_path: Path, dest_dir: Path) -> list[str]:
    """Extract a validated archive into dest_dir. Returns relative file paths."""
    return extract_archive_from_data(archive_path.read_bytes(), archive_path.name, dest_dir)


def _extract_zip(data: bytes, dest_dir: Path, written: list[str]) -> None:
    resolved_dest = dest_dir.resolve()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            rel = _safe_member_name(info.filename)
            if info.is_dir():
                continue
            target = (dest_dir / rel).resolve()
            if not target.is_relative_to(resolved_dest):
                raise SkillError(SkillErrorCode.ARCHIVE_PATH_TRAVERSAL, "extraction path escapes target directory")
            if target.is_symlink():
                raise SkillError(SkillErrorCode.ARCHIVE_SYMLINK_DENIED, "symlink destination in extraction is denied")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            written.append(rel)


def _extract_targz(data: bytes, dest_dir: Path, written: list[str]) -> None:
    resolved_dest = dest_dir.resolve()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf.getmembers():
            rel = _safe_member_name(m.name)
            if not m.isfile():
                continue
            target = (dest_dir / rel).resolve()
            if not target.is_relative_to(resolved_dest):
                raise SkillError(SkillErrorCode.ARCHIVE_PATH_TRAVERSAL, "extraction path escapes target directory")
            if target.is_symlink():
                raise SkillError(SkillErrorCode.ARCHIVE_SYMLINK_DENIED, "symlink destination in extraction is denied")
            target.parent.mkdir(parents=True, exist_ok=True)
            f = tf.extractfile(m)
            if f is None:
                continue
            with open(target, "wb") as dst:
                dst.write(f.read())
            written.append(rel)
