"""Skills lifecycle manager.

States: QUARANTINED -> INSTALLED (disabled by default) -> ENABLED <-> DISABLED.
Install is atomic (temp dir + rename). No code execution during install.
Registry persisted as JSON under <skills_root>/registry.json.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from modules.skills.skills_archive import extract_archive, parse_manifest, read_manifest_bytes
from modules.skills.skills_contract import (
    MAX_ARCHIVE_BYTES,
    SkillError,
    SkillErrorCode,
    SkillManifest,
    SkillState,
    validate_manifest_dict,
)

_REGISTRY_NAME = "registry.json"


class SkillsManager:
    """Manages skill packages under a confined skills root."""

    def __init__(self, skills_root: Path | str) -> None:
        self._root = Path(skills_root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / "quarantine").mkdir(exist_ok=True)
        (self._root / "installed").mkdir(exist_ok=True)
        self._registry_path = self._root / _REGISTRY_NAME
        self._registry: dict[str, dict[str, Any]] = self._load_registry()

    def _load_registry(self) -> dict[str, dict[str, Any]]:
        if not self._registry_path.exists():
            return {}
        try:
            data = json.loads(self._registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_registry(self) -> None:
        tmp = self._registry_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._registry, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._registry_path)

    def _entry(self, skill_id: str) -> dict[str, Any]:
        entry = self._registry.get(skill_id)
        if entry is None:
            raise SkillError(SkillErrorCode.SKILL_NOT_FOUND, f"skill '{skill_id}' is not installed")
        return entry

    # --- API ---

    def list_skills(self) -> list[dict[str, Any]]:
        return [
            {
                "id": sid,
                "name": e.get("name", ""),
                "version": e.get("version", ""),
                "state": e.get("state", SkillState.INSTALLED.value),
                "permissions": e.get("permissions", []),
            }
            for sid, e in sorted(self._registry.items())
        ]

    def validate_package(self, archive_path: Path | str) -> SkillManifest:
        """Validate archive + manifest without installing. Returns manifest."""
        path = Path(archive_path)
        manifest_bytes = read_manifest_bytes(path)
        return validate_manifest_dict(parse_manifest(manifest_bytes))

    def install(self, archive_path: Path | str) -> dict[str, Any]:
        """Quarantine -> validate -> checksum -> atomic install -> register DISABLED."""
        path = Path(archive_path)
        if not path.exists():
            raise SkillError(SkillErrorCode.INSTALL_FAILED, "package not found")
        if path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise SkillError(SkillErrorCode.ARCHIVE_TOO_LARGE, "archive exceeds maximum size")

        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest = self.validate_package(path)
        if manifest.checksum and manifest.checksum != sha:
            raise SkillError(SkillErrorCode.CHECKSUM_MISMATCH, "package checksum mismatch")

        if manifest.skill_id in self._registry:
            raise SkillError(SkillErrorCode.SKILL_STATE_CONFLICT, f"skill '{manifest.skill_id}' already installed")

        install_dir = self._root / "installed" / manifest.skill_id
        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=self._root / "installed"))
        try:
            written = extract_archive(path, staging)
            if manifest.entrypoint not in written:
                raise SkillError(SkillErrorCode.ENTRYPOINT_MISSING, f"entrypoint '{manifest.entrypoint}' not in package")
            if install_dir.exists():
                shutil.rmtree(install_dir)
            os.replace(staging, install_dir)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

        self._registry[manifest.skill_id] = {
            "name": manifest.name,
            "version": manifest.version,
            "state": SkillState.DISABLED.value,  # disabled by default
            "permissions": list(manifest.permissions),
            "entrypoint": manifest.entrypoint,
            "sha256": sha,
            "path": str(install_dir.relative_to(self._root)),
        }
        self._save_registry()
        return {"id": manifest.skill_id, "state": SkillState.DISABLED.value, "permissions": list(manifest.permissions)}

    def enable(self, skill_id: str) -> dict[str, Any]:
        entry = self._entry(skill_id)
        entry["state"] = SkillState.ENABLED.value
        self._save_registry()
        return {"id": skill_id, "state": entry["state"]}

    def disable(self, skill_id: str) -> dict[str, Any]:
        entry = self._entry(skill_id)
        entry["state"] = SkillState.DISABLED.value
        self._save_registry()
        return {"id": skill_id, "state": entry["state"]}

    def uninstall(self, skill_id: str) -> dict[str, Any]:
        entry = self._entry(skill_id)
        target = self._root / entry.get("path", "")
        if target.exists() and target.is_dir() and target.resolve().is_relative_to(self._root):
            shutil.rmtree(target, ignore_errors=True)
        del self._registry[skill_id]
        self._save_registry()
        return {"id": skill_id, "removed": True}

    def inspect_permissions(self, skill_id: str) -> list[str]:
        return list(self._entry(skill_id).get("permissions", []))

    def get_version(self, skill_id: str) -> str:
        return str(self._entry(skill_id).get("version", ""))

    def entrypoint_path(self, skill_id: str) -> Path:
        """Resolve the entrypoint only for ENABLED skills (execution gate)."""
        entry = self._entry(skill_id)
        if entry.get("state") != SkillState.ENABLED.value:
            raise SkillError(SkillErrorCode.SKILL_STATE_CONFLICT, f"skill '{skill_id}' is not enabled")
        path = (self._root / entry["path"] / entry["entrypoint"]).resolve()
        if not path.is_relative_to(self._root):
            raise SkillError(SkillErrorCode.ARCHIVE_PATH_TRAVERSAL, "entrypoint escapes skills root")
        return path
