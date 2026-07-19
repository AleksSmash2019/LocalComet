
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


PROJECT_PATHS_VERSION = "v6.79"
RETENTION_PLAN_VERSION = "v6.79"
DEFAULT_RETENTION_MAX_AGE_DAYS = 7
DEFAULT_RETENTION_MAX_ITEMS_PER_GROUP = 200


def _module_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_project_root() -> Path:
    """Return the active LocalComet root.

    LOCALCOMET_ROOT is the only runtime override. If it is set, return it even
    when it does not exist so dry-run tools cannot silently fall back to the
    source checkout.
    """
    explicit_root = os.environ.get("LOCALCOMET_ROOT", "").strip()
    if explicit_root:
        return Path(explicit_root).expanduser().resolve()

    return _module_root()


def projects_dir(root: Path | None = None) -> Path:
    return (root or get_project_root()) / "Projects"


def reports_dir(root: Path | None = None) -> Path:
    return projects_dir(root) / "Reports"


def localcomet_dir(root: Path | None = None) -> Path:
    return (root or get_project_root()) / ".localcomet"


def localcomet_reports_dir(root: Path | None = None) -> Path:
    return localcomet_dir(root) / "reports"


def localcomet_policies_dir(root: Path | None = None) -> Path:
    return localcomet_dir(root) / "policies"


def computer_use_dir(root: Path | None = None) -> Path:
    return projects_dir(root) / "ComputerUse"


def computer_use_runs_dir(root: Path | None = None) -> Path:
    return computer_use_dir(root) / "runs"


def computer_use_latest_ui_map_path(root: Path | None = None) -> Path:
    return computer_use_dir(root) / "latest_ui_map.json"


def test_fixtures_dir(root: Path | None = None) -> Path:
    return projects_dir(root) / "TestFixtures"


def computer_use_test_fixtures_dir(root: Path | None = None) -> Path:
    return test_fixtures_dir(root) / "ComputerUse"


def ensure_dirs(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def retention_runtime_roots(root: Path | None = None) -> tuple[Path, ...]:
    active_root = root or get_project_root()
    return (
        localcomet_reports_dir(active_root),
        reports_dir(active_root),
        computer_use_runs_dir(active_root),
    )


def _norm(path: Path) -> str:
    return path.resolve().as_posix().lower()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.resolve().as_posix()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _age_days(path: Path, now_ts: float) -> float:
    return max(0.0, (now_ts - path.stat().st_mtime) / 86400)


def _protected_reason(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    rel = _rel(resolved, project_root)
    parts = {part.lower() for part in resolved.parts}
    name = resolved.name.lower()
    stem = resolved.stem.lower()

    if ".git" in parts:
        return "git metadata is protected"
    if ".incident_backup" in parts:
        return "incident backups are protected"
    if ".tmp" in parts:
        return ".tmp is not configured for v6.79 retention"
    if "localagent_archive" in _norm(resolved):
        return "external LocalAgent_Archive paths are protected"
    if "testfixtures" in parts or ("projects" in parts and "testfixtures" in parts):
        return "test fixtures are protected"
    if ".localcomet" in parts and "reviewer" in parts:
        return "reviewer inbox/outbox/archive data is protected"
    if ".localcomet" in parts and "policies" in parts:
        return "policies are protected"
    if name.endswith(".py"):
        return "source Python files are protected"
    if any(marker in stem for marker in ("latest", "current", "manifest")):
        return "latest/current/manifest files are protected"
    if rel.replace("\\", "/").startswith("Projects/TestFixtures/"):
        return "test fixtures are protected"
    return ""


def _file_item(path: Path, project_root: Path, now_ts: float, reason: str = "") -> dict:
    stat = path.stat()
    item = {
        "path": _rel(path, project_root),
        "size_bytes": int(stat.st_size),
        "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        "age_days": round(_age_days(path, now_ts), 3),
    }
    if reason:
        item["reason"] = reason
    return item


def build_retention_plan(
    root: Path | None = None,
    scan_roots: Iterable[Path] | None = None,
    max_age_days: int = DEFAULT_RETENTION_MAX_AGE_DAYS,
    max_items_per_group: int = DEFAULT_RETENTION_MAX_ITEMS_PER_GROUP,
    now_ts: float | None = None,
) -> dict:
    project_root = (root or get_project_root()).resolve()
    configured_roots = tuple(Path(path).expanduser().resolve() for path in (scan_roots or retention_runtime_roots(project_root)))
    now_value = float(now_ts if now_ts is not None else datetime.now(tz=timezone.utc).timestamp())
    allowed_roots = tuple(path for path in configured_roots if _is_relative_to(path, project_root))
    roots: list[dict] = []
    candidates: list[dict] = []
    protected: list[dict] = []
    rejected: list[dict] = []
    warnings: list[str] = []

    for scan_root in sorted(configured_roots, key=lambda item: item.as_posix().lower()):
        root_info = {
            "path": _rel(scan_root, project_root),
            "exists": scan_root.exists(),
            "allowed": _is_relative_to(scan_root, project_root),
        }
        roots.append(root_info)
        if not root_info["allowed"]:
            rejected.append({"path": scan_root.as_posix(), "reason": "scan root is outside project root"})
            continue
        if not scan_root.exists():
            continue
        if not scan_root.is_dir():
            rejected.append({"path": _rel(scan_root, project_root), "reason": "scan root is not a directory"})
            continue
        if scan_root.is_symlink():
            rejected.append({"path": _rel(scan_root, project_root), "reason": "scan root is a symlink"})
            continue

        group_files: list[Path] = []
        for current_root, dir_names, file_names in os.walk(scan_root, topdown=True, followlinks=False):
            current_path = Path(current_root)
            kept_dirs: list[str] = []
            for dir_name in sorted(dir_names):
                dir_path = current_path / dir_name
                reason = _protected_reason(dir_path, project_root)
                if dir_path.is_symlink():
                    rejected.append({"path": _rel(dir_path, project_root), "reason": "directory symlink is not followed"})
                    continue
                if reason:
                    protected.append({"path": _rel(dir_path, project_root), "reason": reason})
                    continue
                kept_dirs.append(dir_name)
            dir_names[:] = kept_dirs

            for file_name in sorted(file_names):
                file_path = current_path / file_name
                if not _is_relative_to(file_path, project_root):
                    rejected.append({"path": file_path.as_posix(), "reason": "file escaped project root"})
                    continue
                if not any(_is_relative_to(file_path, allowed_root) for allowed_root in allowed_roots):
                    rejected.append({"path": _rel(file_path, project_root), "reason": "file is outside allowed runtime roots"})
                    continue
                if file_path.is_symlink():
                    rejected.append({"path": _rel(file_path, project_root), "reason": "file symlink is not followed"})
                    continue
                if not file_path.is_file():
                    continue
                reason = _protected_reason(file_path, project_root)
                if reason:
                    protected.append(_file_item(file_path, project_root, now_value, reason))
                    continue
                group_files.append(file_path)

        newest_first = sorted(group_files, key=lambda item: (-item.stat().st_mtime, _rel(item, project_root)))
        keep_set = {path.resolve() for path in newest_first[:max_items_per_group]}
        for path in newest_first:
            age = _age_days(path, now_value)
            is_over_count = path.resolve() not in keep_set
            is_over_age = age > max_age_days
            if is_over_age or is_over_count:
                reasons = []
                if is_over_age:
                    reasons.append(f"age>{max_age_days}d")
                if is_over_count:
                    reasons.append(f"rank>{max_items_per_group}")
                item = _file_item(path, project_root, now_value, ", ".join(reasons))
                item["dry_run_action"] = "would_delete"
                candidates.append(item)

    candidates.sort(key=lambda item: item["path"].lower())
    protected.sort(key=lambda item: item["path"].lower())
    rejected.sort(key=lambda item: item["path"].lower())
    roots.sort(key=lambda item: item["path"].lower())
    total_candidate_bytes = sum(item.get("size_bytes", 0) for item in candidates)

    return {
        "mode": "runtime_retention_plan",
        "version": RETENTION_PLAN_VERSION,
        "dry_run": True,
        "roots": roots,
        "policy": {
            "max_age_days": int(max_age_days),
            "max_items_per_group": int(max_items_per_group),
            "delete_enabled": False,
        },
        "candidates": candidates,
        "protected": protected,
        "rejected": rejected,
        "totals": {
            "candidate_count": len(candidates),
            "candidate_bytes": int(total_candidate_bytes),
            "protected_count": len(protected),
            "rejected_count": len(rejected),
            "roots_count": len(roots),
        },
        "warnings": warnings,
    }


def status() -> dict:
    root = get_project_root()
    return {
        "ok": True,
        "mode": "project_paths_status",
        "version": PROJECT_PATHS_VERSION,
        "root": str(root),
        "projects_dir": str(projects_dir(root)),
        "reports_dir": str(reports_dir(root)),
        "localcomet_reports_dir": str(localcomet_reports_dir(root)),
        "localcomet_policies_dir": str(localcomet_policies_dir(root)),
        "computer_use_dir": str(computer_use_dir(root)),
        "computer_use_runs_dir": str(computer_use_runs_dir(root)),
        "computer_use_latest_ui_map_path": str(computer_use_latest_ui_map_path(root)),
        "test_fixtures_dir": str(test_fixtures_dir(root)),
        "retention_runtime_roots": [str(path) for path in retention_runtime_roots(root)],
    }


def report() -> dict:
    return status()

# v6.54 Computer Use Observe/Vision Upgrade RU: enabled.
