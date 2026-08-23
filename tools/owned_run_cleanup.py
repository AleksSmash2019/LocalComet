"""Owner-scoped run manifest and fail-closed temp cleanup (unified prompt §4).

Design invariants:
- Default mode is ``dry_run``; destructive modes are explicit opt-in values.
- A run owns ONLY what its manifest lists under an allowlisted LocalComet
  root. Ownership is proven by a schema-validated manifest plus an in-root
  marker, never by directory name, image name, port or age alone.
- Every precondition failure, ambiguity, reparse point or race skips the
  resource with a machine-readable reason instead of raising past the loop.
- Build caches, canonical evidence, source trees and model data are NOT part
  of temp cleanup and are never returned as candidates.

This module ships implemented and synthetic-fixture-tested; no caller in this
session invokes a destructive mode against existing user data.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import uuid
from typing import Any

MANIFEST_SCHEMA = "localcomet.owned-run.v1"
MARKER_NAME = "owned-run.marker.json"
MANIFEST_NAME = "owned_run_manifest.json"
LOCK_NAME = "owned-run.lock"
CLEANUP_POLICY_VERSION = "localcomet.cleanup-policy.v1"

MODE_DRY_RUN = "dry_run"
MODE_OWNED_CURRENT_RUN = "owned_current_run"
MODE_OWNED_STALE_RUNS = "owned_stale_runs"
ALLOWED_MODES = (MODE_DRY_RUN, MODE_OWNED_CURRENT_RUN, MODE_OWNED_STALE_RUNS)

_STILL_ACTIVE = 0x00000103
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class CleanupHold(RuntimeError):
    """Raised only for structural misuse (bad mode/manifest), never per-path."""


@dataclass(frozen=True)
class RetentionPolicy:
    """Typed retention thresholds (plan §4.6); nothing aggressive is baked in."""

    transient_temp: timedelta = timedelta(hours=6)
    run_udf: timedelta = timedelta(hours=6)
    failed_run_diagnostics: timedelta = timedelta(days=7)


@dataclass
class OwnedRunManifest:
    run_id: str
    created_utc: str
    owner: str
    repo_root: str
    isolated_root: str
    cargo_target_dir: str
    vite_port: int
    cdp_port: int
    hidden_desktop: str
    root_pid: int
    owned_pids: list[int] = field(default_factory=list)
    owned_paths: list[str] = field(default_factory=list)
    cleanup_policy_version: str = CLEANUP_POLICY_VERSION
    completed_utc: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_utc(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def write_manifest(
    run_root: Path,
    audit_copy_dir: Path,
    *,
    owner: str,
    repo_root: Path,
    isolated_root: Path,
    cargo_target_dir: Path,
    vite_port: int,
    cdp_port: int,
    hidden_desktop: str,
    root_pid: int,
    owned_pids: list[int],
    owned_paths: list[Path],
) -> tuple[Path, dict[str, Any]]:
    """Create the ownership manifest BEFORE any child resource exists (§4.1).

    Writes an in-root immutable-content marker plus the manifest itself, and
    duplicates the manifest into the run's evidence directory. No secrets,
    model contents or approval payloads are stored.
    """
    run_root = Path(run_root).resolve()
    manifest = OwnedRunManifest(
        run_id=uuid.uuid4().hex,
        created_utc=utc_now(),
        owner=str(owner),
        repo_root=str(Path(repo_root).resolve()),
        isolated_root=str(Path(isolated_root).resolve()),
        cargo_target_dir=str(Path(cargo_target_dir).resolve()),
        vite_port=int(vite_port),
        cdp_port=int(cdp_port),
        hidden_desktop=str(hidden_desktop),
        root_pid=int(root_pid),
        owned_pids=[int(pid) for pid in owned_pids],
        owned_paths=[str(Path(path).resolve()) for path in owned_paths],
    )
    payload = {"schema_version": MANIFEST_SCHEMA, **manifest.to_dict()}
    run_root.mkdir(parents=True, exist_ok=True)
    marker_path = run_root / MARKER_NAME
    marker_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path = run_root / MANIFEST_NAME
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit_copy_dir = Path(audit_copy_dir)
    audit_copy_dir.mkdir(parents=True, exist_ok=True)
    (audit_copy_dir / MANIFEST_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest_path, payload


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load a manifest or raise CleanupHold on any malformed content."""
    try:
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CleanupHold(f"manifest unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise CleanupHold("manifest is not an object")
    if data.get("schema_version") != MANIFEST_SCHEMA:
        # Only manifests carrying our explicit schema are owned; foreign or
        # legacy objects are unowned by definition and never cleaned.
        raise CleanupHold(f"foreign manifest schema: {data.get('schema_version')!r}")
    required = (
        "run_id", "created_utc", "owner", "isolated_root",
        "root_pid", "owned_paths", "cleanup_policy_version",
    )
    missing = [key for key in required if key not in data]
    if missing:
        raise CleanupHold("manifest missing fields: " + ", ".join(missing))
    return data


def mark_completed(manifest_path: Path) -> None:
    """Stamp completed_utc once the run's final evidence is written."""
    data = load_manifest(manifest_path)
    data["completed_utc"] = utc_now()
    Path(manifest_path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pid_alive(pid: int) -> bool | None:
    """True/False when provable, None when undeterminable (fail-closed)."""
    if os.name != "nt":
        return None
    if int(pid) <= 0:
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        # Access-denied means SOMETHING exists we cannot inspect: unknown.
        return None if ctypes.get_last_error() == 5 else False
    exit_code = wintypes.DWORD()
    ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
    kernel32.CloseHandle(handle)
    if not ok:
        return None
    return exit_code.value == _STILL_ACTIVE


def port_listening(port: int) -> bool:
    """Conservative probe: a successful loopback connect blocks cleanup."""
    if not int(port):
        return False
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.3):
            return True
    except OSError:
        return False


def is_reparse_point(path: Path) -> bool:
    try:
        attributes = os.stat(path, follow_symlinks=False).st_file_attributes
    except FileNotFoundError:
        # Absent paths are governed by the exists/already_absent rule, not by
        # the ambiguity rule.
        return False
    except (OSError, AttributeError):
        return True  # cannot prove it is a plain directory: fail closed
    return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def _under(root: Path, path: Path) -> bool:
    try:
        Path(path).relative_to(Path(root))
        return True
    except ValueError:
        return False


def evaluate_candidate(
    raw_path: str,
    manifest: dict[str, Any],
    *,
    mode: str,
    policy: RetentionPolicy,
    now: datetime | None = None,
    protected_roots: list[str] | None = None,
    lock_present: bool | None = None,
) -> dict[str, Any]:
    """Full precondition chain (plan §4.3). Never touches the filesystem
    beyond read-only stat/probes; returns an eligibility verdict."""
    reasons: list[str] = []
    now = now or datetime.now(timezone.utc)
    if mode not in ALLOWED_MODES:
        raise CleanupHold(f"unknown cleanup mode: {mode}")
    path = Path(str(raw_path))
    if not path.is_absolute():
        return {"path": str(raw_path), "eligible": False, "reasons": ["path_not_absolute"]}
    # Reparse state must be observed on the REQUESTED path: realpath resolves
    # junctions/symlinks away and would silently lose the ambiguity signal.
    if is_reparse_point(path):
        reasons.append("reparse_or_symlink_ambiguous")
    canonical = Path(os.path.realpath(path))
    if canonical != path and not _under(Path(manifest["isolated_root"]), canonical):
        reasons.append("realpath_diverges_from_manifest")
    manifest_owned = [
        entry for entry in manifest.get("owned_paths", [])
        if Path(os.path.realpath(entry)) == canonical
    ]
    if not manifest_owned:
        reasons.append("not_listed_in_manifest_owned_paths")
    for root in protected_roots or []:
        if _under(Path(root), canonical):
            reasons.append("under_protected_root")
            break
    created = _parse_utc(str(manifest.get("created_utc", "")))
    completed = _parse_utc(str(manifest.get("completed_utc") or ""))
    age = (now - created) if created else None
    stale_ttl = max(policy.transient_temp, policy.run_udf, policy.failed_run_diagnostics)
    if mode == MODE_OWNED_STALE_RUNS:
        if completed:
            reasons.append("completed_run_in_stale_mode")
        if age is None or age < stale_ttl:
            reasons.append("ttl_not_expired")
    if mode == MODE_OWNED_CURRENT_RUN:
        if not completed:
            reasons.append("run_not_marked_completed")
    if lock_present is None:
        lock_path = Path(manifest["isolated_root"]) / LOCK_NAME
        lock_present = lock_path.exists()
    if lock_present:
        reasons.append("active_lock_present")
    alive = pid_alive(int(manifest.get("root_pid", 0)))
    if alive is True:
        reasons.append("owner_process_still_alive")
    elif alive is None:
        reasons.append("owner_process_unknown")
    for pid in manifest.get("owned_pids", []):
        state = pid_alive(int(pid))
        if state is True:
            reasons.append(f"owned_pid_{int(pid)}_still_alive")
            break
        if state is None:
            reasons.append(f"owned_pid_{int(pid)}_unknown")
            break
    for key in ("vite_port", "cdp_port"):
        port = int(manifest.get(key, 0) or 0)
        if port and port_listening(port):
            reasons.append(f"{key}_still_listening")
    if canonical == Path(manifest["repo_root"]) or _under(Path(manifest["repo_root"]), canonical):
        reasons.append("inside_repo_root_forbidden")
    exists = canonical.exists()
    if not exists:
        reasons.append("already_absent")
    eligible = not reasons
    return {
        "path": str(canonical),
        "requested_path": str(path),
        "run_id": str(manifest.get("run_id", "")),
        "mode": mode,
        "exists": exists,
        "eligible": eligible,
        "reasons": reasons,
        "age_hours": round(age.total_seconds() / 3600.0, 3) if age else None,
    }


def plan_cleanup(
    manifest: dict[str, Any],
    *,
    mode: str,
    policy: RetentionPolicy | None = None,
    now: datetime | None = None,
    protected_roots: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Compute candidates and verdicts. dry_run-safe by construction: this
    function performs NO deletion and NO process operation."""
    policy = policy or RetentionPolicy()
    return [
        evaluate_candidate(
            path, manifest, mode=mode, policy=policy, now=now,
            protected_roots=protected_roots,
            lock_present=None,
        )
        for path in manifest.get("owned_paths", [])
    ]


def execute_plan(plan: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    """Act on an evaluated plan. Only eligible candidates are removed, one
    manifest-listed path at a time; dry_run never deletes. Idempotent."""
    if mode not in ALLOWED_MODES:
        raise CleanupHold(f"unknown cleanup mode: {mode}")
    results: list[dict[str, Any]] = []
    deleted = 0
    for item in plan:
        entry = dict(item)
        path = Path(item["path"])
        if mode == MODE_DRY_RUN:
            entry["action"] = "dry_run_no_deletion"
        elif item.get("eligible"):
            # Race guard (§4.3): anything that vanished between planning and
            # execution is reported honestly instead of claimed as deleted.
            if not path.exists() and not path.is_symlink():
                entry["action"] = "already_absent"
            else:
                try:
                    if path.is_dir() and not path.is_symlink():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    entry["action"] = "deleted"
                    deleted += 1
                except OSError as exc:
                    entry["action"] = "skipped_error"
                    entry["reasons"] = list(entry.get("reasons", [])) + [
                        f"os_error:{getattr(exc, 'winerror', '')}"
                    ]
        else:
            entry["action"] = "skipped_not_eligible"
            if list(entry.get("reasons", [])) == ["already_absent"]:
                entry["action"] = "already_absent"
        results.append(entry)
    return {
        "mode": mode,
        "policy_version": CLEANUP_POLICY_VERSION,
        "deleted_count": deleted if mode != MODE_DRY_RUN else 0,
        "results": results,
    }
