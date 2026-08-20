"""Local-folder-only Markdown adapter for the LocalComet Vault boundary.

This module deliberately does not know about Obsidian APIs or MCP. It operates
on a caller-supplied canonical root and exposes read/preview/apply operations
with optimistic concurrency. The default workflow is read-only until a
proposal is explicitly applied by the caller.
"""
from __future__ import annotations

import difflib
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

MAX_MARKDOWN_BYTES = 4 * 1024 * 1024
_OBSIDIAN_DIR = ".obsidian"


class LocalVaultError(ValueError):
    """Base error for fail-closed local Vault operations."""


class VaultConflictError(LocalVaultError):
    """Raised when optimistic-concurrency state no longer matches."""


@dataclass(frozen=True, slots=True)
class VaultIdentity:
    canonical_root: str
    root_digest: str


@dataclass(frozen=True, slots=True)
class VaultNote:
    relative_path: str
    sha256: str
    content: str
    byte_length: int


@dataclass(frozen=True, slots=True)
class VaultProposal:
    operation: str
    relative_path: str
    expected_sha256: str
    new_sha256: str
    content: str
    diff: str


class LocalVault:
    """Constrained Markdown operations below one canonical local directory."""

    def __init__(self, root: str | os.PathLike[str], *, max_bytes: int = MAX_MARKDOWN_BYTES) -> None:
        if not isinstance(root, (str, os.PathLike)) or not str(root).strip():
            raise LocalVaultError("Vault root is required")
        if max_bytes <= 0:
            raise LocalVaultError("Vault byte limit must be positive")
        raw_root = Path(root).expanduser()
        if not raw_root.is_absolute():
            raise LocalVaultError("Vault root must be absolute")
        try:
            canonical_root = raw_root.resolve(strict=True)
        except OSError as exc:
            raise LocalVaultError("Vault root cannot be resolved") from exc
        if not canonical_root.is_dir():
            raise LocalVaultError("Vault root must be a directory")
        self._root = canonical_root
        self._max_bytes = max_bytes
        self.identity = VaultIdentity(
            canonical_root=_portable(canonical_root),
            root_digest=hashlib.sha256(_portable(canonical_root).encode("utf-8")).hexdigest(),
        )

    @property
    def root(self) -> Path:
        return self._root

    def list_markdown(self, directory: str = "") -> tuple[str, ...]:
        base = self._resolve_relative(directory, allow_empty=True)
        if not base.is_dir():
            raise LocalVaultError("Vault directory does not exist")
        results: list[str] = []
        for candidate in base.rglob("*.md"):
            relative = candidate.relative_to(self._root)
            if _is_forbidden_relative(relative):
                continue
            self._validate_existing_path(relative)
            if candidate.is_file() and not candidate.is_symlink():
                results.append(relative.as_posix())
        return tuple(sorted(results, key=str.casefold))

    def read_markdown(self, relative_path: str) -> VaultNote:
        target = self._resolve_markdown(relative_path)
        self._validate_existing_path(Path(relative_path))
        try:
            data = target.read_bytes()
        except OSError as exc:
            raise LocalVaultError("Markdown note cannot be read") from exc
        self._check_size(data)
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LocalVaultError("Markdown note must be UTF-8") from exc
        return VaultNote(
            relative_path=Path(relative_path).as_posix(),
            sha256=_sha256(data),
            content=content,
            byte_length=len(data),
        )

    def propose_create(self, relative_path: str, content: str) -> VaultProposal:
        target = self._resolve_markdown(relative_path)
        if target.exists() or target.is_symlink():
            raise VaultConflictError("Markdown note already exists")
        encoded = _encode_content(content)
        self._check_size(encoded)
        relative = Path(relative_path).as_posix()
        return VaultProposal(
            operation="create",
            relative_path=relative,
            expected_sha256="",
            new_sha256=_sha256(encoded),
            content=content,
            diff=_unified_diff(relative, "", content),
        )

    def propose_update(self, relative_path: str, expected_sha256: str, content: str) -> VaultProposal:
        current = self.read_markdown(relative_path)
        if current.sha256 != expected_sha256:
            raise VaultConflictError("Markdown note changed since it was read")
        encoded = _encode_content(content)
        self._check_size(encoded)
        relative = Path(relative_path).as_posix()
        return VaultProposal(
            operation="update",
            relative_path=relative,
            expected_sha256=expected_sha256,
            new_sha256=_sha256(encoded),
            content=content,
            diff=_unified_diff(relative, current.content, content),
        )

    def apply_proposal(self, proposal: VaultProposal) -> VaultNote:
        if not isinstance(proposal, VaultProposal):
            raise LocalVaultError("Invalid Vault proposal")
        target = self._resolve_markdown(proposal.relative_path)
        self._validate_existing_path(Path(proposal.relative_path), allow_missing_leaf=True)
        encoded = _encode_content(proposal.content)
        self._check_size(encoded)
        if proposal.operation == "create":
            if target.exists() or target.is_symlink():
                raise VaultConflictError("Markdown note already exists")
        elif proposal.operation == "update":
            current = self.read_markdown(proposal.relative_path)
            if current.sha256 != proposal.expected_sha256:
                raise VaultConflictError("Markdown note changed before apply")
        else:
            raise LocalVaultError("Unsupported Vault operation")
        if _sha256(encoded) != proposal.new_sha256:
            raise VaultConflictError("Proposal content digest does not match")
        target.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(target, encoded)
        return self.read_markdown(proposal.relative_path)

    def _resolve_markdown(self, relative_path: str) -> Path:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise LocalVaultError("Markdown relative path is required")
        if "\x00" in relative_path or "\r" in relative_path or "\n" in relative_path:
            raise LocalVaultError("Markdown path contains control characters")
        relative = Path(relative_path.replace("\\", "/"))
        if relative.is_absolute() or relative.drive:
            raise LocalVaultError("Absolute Markdown paths are not allowed")
        if _is_forbidden_relative(relative):
            raise LocalVaultError(".obsidian is outside the Vault content boundary")
        if relative.suffix.casefold() != ".md":
            raise LocalVaultError("Only Markdown notes are supported")
        target = self._resolve_relative(relative_path)
        return target

    def _resolve_relative(self, relative_path: str, *, allow_empty: bool = False) -> Path:
        if not isinstance(relative_path, str):
            raise LocalVaultError("Relative path must be text")
        if not relative_path and allow_empty:
            return self._root
        relative = Path(relative_path.replace("\\", "/"))
        if relative.is_absolute() or relative.drive or any(part == ".." for part in relative.parts):
            raise LocalVaultError("Path escapes the Vault root")
        if _is_forbidden_relative(relative):
            raise LocalVaultError(".obsidian is outside the Vault content boundary")
        target = self._root.joinpath(*relative.parts)
        try:
            resolved = target.resolve(strict=False)
            resolved.relative_to(self._root)
        except (OSError, ValueError) as exc:
            raise LocalVaultError("Path escapes the Vault root") from exc
        return target

    def _validate_existing_path(self, relative: Path, *, allow_missing_leaf: bool = False) -> None:
        current = self._root
        parts = tuple(relative.parts)
        for index, part in enumerate(parts):
            current = current / part
            if not current.exists() and not current.is_symlink():
                if allow_missing_leaf and index == len(parts) - 1:
                    return
                continue
            if current.is_symlink():
                raise LocalVaultError("Symlinked Vault paths are not allowed")
            try:
                current.resolve(strict=True).relative_to(self._root)
            except (OSError, ValueError) as exc:
                raise LocalVaultError("Vault path escapes the configured root") from exc

    def _check_size(self, data: bytes) -> None:
        if len(data) > self._max_bytes:
            raise LocalVaultError("Markdown note exceeds the configured byte limit")

    @staticmethod
    def _atomic_write(target: Path, data: bytes) -> None:
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False) as handle:
                temporary = handle.name
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            temporary = None
        except OSError as exc:
            raise LocalVaultError("Atomic Markdown write failed") from exc
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass


def _portable(path: Path) -> str:
    return str(path).replace("\\", "/")


def _is_forbidden_relative(relative: Path) -> bool:
    return any(part.casefold() == _OBSIDIAN_DIR for part in relative.parts)


def _encode_content(content: str) -> bytes:
    if not isinstance(content, str):
        raise LocalVaultError("Markdown content must be text")
    try:
        return content.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise LocalVaultError("Markdown content must be valid UTF-8") from exc


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unified_diff(relative_path: str, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
        )
    )


__all__ = [
    "LocalVault",
    "LocalVaultError",
    "MAX_MARKDOWN_BYTES",
    "VaultConflictError",
    "VaultIdentity",
    "VaultNote",
    "VaultProposal",
]
