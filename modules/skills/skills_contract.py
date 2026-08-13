"""Immutable contracts, permissions model and manifest validation for skills.

Strict, dependency-free. Manifest is UNTRUSTED input: every field is bounded,
paths are traversal-checked, permissions are validated against a closed set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Mapping

SKILL_CONTRACT_VERSION = "localcomet.skill/1.0"

# Bounded limits (defence in depth).
MAX_SKILL_ID_CHARS = 64
MAX_SKILL_NAME_CHARS = 128
MAX_SKILL_VERSION_CHARS = 32
MAX_SKILL_DESCRIPTION_CHARS = 2048
MAX_SKILL_AUTHOR_CHARS = 128
MAX_SKILL_ENTRYPOINT_CHARS = 256
MAX_SKILL_FIELD_CHARS = 512
MAX_PERMISSIONS = 32
MAX_CAPABILITIES = 32
MAX_DEPENDENCIES = 16
MAX_MANIFEST_BYTES = 65_536

# Archive / upload safety limits.
ALLOWED_ARCHIVE_SUFFIXES = (".zip", ".tar.gz", ".tgz")
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024          # 32 MiB compressed
MAX_EXTRACTED_BYTES = 64 * 1024 * 1024        # 64 MiB uncompressed (compression-bomb guard)
MAX_ARCHIVE_FILES = 512
MAX_ARCHIVE_MEMBER_CHARS = 256
ARCHIVE_BOMB_RATIO = 100                      # max uncompressed:compressed ratio
ZIP_MAGIC = b"PK\x03\x04"
GZIP_MAGIC = b"\x1f\x8b"

SKILL_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")


class SkillState(str, Enum):
    QUARANTINED = "QUARANTINED"
    INSTALLED = "INSTALLED"      # registered, DISABLED by default
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    FAILED = "FAILED"


class SkillPermission(str, Enum):
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    NETWORK = "network"
    MODEL_INVOKE = "model.invoke"
    CLIPBOARD = "clipboard"
    PROCESS_SPAWN = "process.spawn"
    SETTINGS_READ = "settings.read"
    SETTINGS_WRITE = "settings.write"
    UI_EXTENSION = "ui.extension"


# Never grantable, never accepted from a manifest.
FORBIDDEN_PERMISSIONS = frozenset({"secrets.access", "secrets.read", "secrets.write"})

ALLOWED_PERMISSIONS = frozenset(p.value for p in SkillPermission)


class SkillErrorCode(str, Enum):
    ARCHIVE_TOO_LARGE = "ARCHIVE_TOO_LARGE"
    ARCHIVE_BOMB = "ARCHIVE_BOMB"
    ARCHIVE_TYPE_DENIED = "ARCHIVE_TYPE_DENIED"
    ARCHIVE_PATH_TRAVERSAL = "ARCHIVE_PATH_TRAVERSAL"
    ARCHIVE_SYMLINK_DENIED = "ARCHIVE_SYMLINK_DENIED"
    ARCHIVE_CORRUPT = "ARCHIVE_CORRUPT"
    MANIFEST_MISSING = "MANIFEST_MISSING"
    MANIFEST_TOO_LARGE = "MANIFEST_TOO_LARGE"
    MANIFEST_INVALID = "MANIFEST_INVALID"
    MANIFEST_UNSUPPORTED_VERSION = "MANIFEST_UNSUPPORTED_VERSION"
    SKILL_ID_INVALID = "SKILL_ID_INVALID"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    PERMISSION_UNKNOWN = "PERMISSION_UNKNOWN"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    ENTRYPOINT_MISSING = "ENTRYPOINT_MISSING"
    SKILL_NOT_FOUND = "SKILL_NOT_FOUND"
    SKILL_STATE_CONFLICT = "SKILL_STATE_CONFLICT"
    INSTALL_FAILED = "INSTALL_FAILED"


class SkillError(Exception):
    """Safe, structured skill error. Never leaks absolute paths or stacks."""

    def __init__(self, code: SkillErrorCode, message: str, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details) if details else {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": self.message, "details": self.details}


def _is_safe_relative_path(value: str) -> bool:
    if not value or len(value) > MAX_ARCHIVE_MEMBER_CHARS:
        return False
    if value.startswith(("/", "\\")) or WINDOWS_ABS_RE.match(value):
        return False
    parts = re.split(r"[\\/]", value)
    if any(p in ("", ".", "..") for p in parts):
        return False
    return True


def _require_str(data: Mapping[str, Any], key: str, max_len: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest field '{key}' must be a non-empty string")
    value = value.strip()
    if len(value) > max_len:
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest field '{key}' exceeds {max_len} chars")
    return value


def _optional_str(data: Mapping[str, Any], key: str, max_len: int) -> str:
    value = data.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest field '{key}' must be a string")
    value = value.strip()
    if len(value) > max_len:
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest field '{key}' exceeds {max_len} chars")
    return value


def _validate_permissions(data: Mapping[str, Any]) -> tuple[str, ...]:
    raw = data.get("permissions", [])
    if not isinstance(raw, list):
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, "manifest 'permissions' must be a list")
    if len(raw) > MAX_PERMISSIONS:
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest 'permissions' exceeds {MAX_PERMISSIONS} entries")
    result: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise SkillError(SkillErrorCode.MANIFEST_INVALID, "permission entries must be strings")
        perm = item.strip()
        if perm in FORBIDDEN_PERMISSIONS:
            raise SkillError(SkillErrorCode.PERMISSION_DENIED, f"permission '{perm}' is never grantable")
        if perm not in ALLOWED_PERMISSIONS:
            raise SkillError(SkillErrorCode.PERMISSION_UNKNOWN, f"unknown permission '{perm}'")
        if perm not in result:
            result.append(perm)
    return tuple(result)


def _validate_str_list(data: Mapping[str, Any], key: str, max_items: int) -> tuple[str, ...]:
    raw = data.get(key, [])
    if raw is None:
        return ()
    if not isinstance(raw, list) or len(raw) > max_items:
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest '{key}' must be a list of at most {max_items}")
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str) or len(item) > MAX_SKILL_FIELD_CHARS:
            raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest '{key}' entries must be bounded strings")
        out.append(item.strip())
    return tuple(out)


@dataclass(frozen=True, slots=True)
class SkillManifest:
    skill_id: str
    name: str
    version: str
    entrypoint: str
    permissions: tuple[str, ...]
    description: str = ""
    author: str = ""
    compatible_app_version: str = ""
    capabilities: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.skill_id,
            "name": self.name,
            "version": self.version,
            "entrypoint": self.entrypoint,
            "permissions": list(self.permissions),
            "description": self.description,
            "author": self.author,
            "compatibleAppVersion": self.compatible_app_version,
            "capabilities": list(self.capabilities),
            "dependencies": list(self.dependencies),
            "checksum": self.checksum,
        }


def validate_manifest_dict(data: Mapping[str, Any]) -> SkillManifest:
    """Validate an untrusted manifest mapping into an immutable SkillManifest."""
    if not isinstance(data, Mapping):
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, "manifest must be an object")

    contract = _optional_str(data, "contract", MAX_SKILL_FIELD_CHARS)
    if contract and contract != SKILL_CONTRACT_VERSION:
        raise SkillError(
            SkillErrorCode.MANIFEST_UNSUPPORTED_VERSION,
            f"unsupported skill contract '{contract}'",
        )

    skill_id = _require_str(data, "id", MAX_SKILL_ID_CHARS)
    if not SKILL_ID_RE.fullmatch(skill_id):
        raise SkillError(SkillErrorCode.SKILL_ID_INVALID, f"invalid skill id '{skill_id}'")

    name = _require_str(data, "name", MAX_SKILL_NAME_CHARS)
    version = _require_str(data, "version", MAX_SKILL_VERSION_CHARS)
    if not SEMVER_RE.fullmatch(version):
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"invalid semver '{version}'")

    entrypoint = _require_str(data, "entrypoint", MAX_SKILL_ENTRYPOINT_CHARS)
    if not _is_safe_relative_path(entrypoint):
        raise SkillError(SkillErrorCode.ARCHIVE_PATH_TRAVERSAL, "entrypoint must be a safe relative path")
    if not entrypoint.endswith(".py"):
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, "entrypoint must be a .py file")

    permissions = _validate_permissions(data)
    capabilities = _validate_str_list(data, "capabilities", MAX_CAPABILITIES)
    dependencies = _validate_str_list(data, "dependencies", MAX_DEPENDENCIES)

    checksum = _optional_str(data, "checksum", MAX_SKILL_FIELD_CHARS)
    if checksum and not SHA256_RE.fullmatch(checksum):
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, "checksum must be lowercase sha256 hex")

    return SkillManifest(
        skill_id=skill_id,
        name=name,
        version=version,
        entrypoint=entrypoint,
        permissions=permissions,
        description=_optional_str(data, "description", MAX_SKILL_DESCRIPTION_CHARS),
        author=_optional_str(data, "author", MAX_SKILL_AUTHOR_CHARS),
        compatible_app_version=_optional_str(data, "compatibleAppVersion", MAX_SKILL_VERSION_CHARS),
        capabilities=capabilities,
        dependencies=dependencies,
        checksum=checksum,
    )
