from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_WEIGHT_AUDIT_VERSION = "v6.64a"
REPO_WEIGHT_AUDIT_NAME = "LocalComet Repository Weight Audit RU"

ROOT_PATH = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_PATH / ".localcomet" / "reports"
REPO_WEIGHT_JSON = OUTPUT_DIR / "repo_weight_report.json"
REPO_WEIGHT_MD = OUTPUT_DIR / "repo_weight_report.md"
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"

BACKUP_KEYWORDS = ["opencode_backup", ".opencode_backup", "backup_"]
CACHE_DIR_NAMES = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", "node_modules", "dist", "build", "logs",
}
GENERATED_ARTIFACT_PATH_PARTS = {".localcomet", "Projects/Reports", "Projects/ComputerUse/runs"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _detect_base_version() -> str:
    try:
        for line in CONTROL_PANEL_PATH.read_text(encoding="utf-8").split("\n"):
            if "LOCALCOMET_VERSION" in line and "=" in line:
                return line.split("=")[-1].strip().strip("\"'")
    except Exception:
        pass
    return "unknown"


def _classify_dir(rel_path: str) -> Tuple[bool, bool, bool]:
    is_backup = any(kw in rel_path for kw in BACKUP_KEYWORDS)
    is_cache = False
    is_generated = False
    parts_lower = rel_path.replace("\\", "/").lower()
    for cn in CACHE_DIR_NAMES:
        if f"/{cn}/" in parts_lower or parts_lower.endswith(f"/{cn}") or parts_lower.startswith(f"{cn}/") or parts_lower == cn:
            is_cache = True
            break
    for gp in GENERATED_ARTIFACT_PATH_PARTS:
        if gp.replace("/", "\\") in rel_path or gp.replace("/", "/") in parts_lower:
            is_generated = True
            break
    return is_backup, is_cache, is_generated


def scan() -> Dict[str, Any]:
    root = ROOT_PATH.resolve()
    root_str = str(root)
    total_size = 0
    file_count = 0
    folder_count = 0
    scan_errors: List[str] = []
    top_dirs: Dict[str, int] = {}
    top_files: List[Tuple[int, str]] = []
    backup_dirs: Dict[str, int] = {}
    cache_dirs: Dict[str, int] = {}
    generated_artifact_dirs: Dict[str, int] = {}
    min_top_dir_size = 0
    min_top_file_size = 0
    MAX_TOP_DIRS = 30
    MAX_TOP_FILES = 50
    MAX_BACKUP_DIRS = 50
    MAX_CACHE_DIRS = 50
    MAX_GENERATED_DIRS = 50
    stack = [(root, root_str)]
    visited = set()
    while stack:
        current, current_str = stack.pop()
        try:
            resolved = current.resolve()
            rs = str(resolved)
            if rs in visited:
                continue
            visited.add(rs)
        except Exception:
            scan_errors.append(f"Could not resolve {current}")
            continue
        dir_size = 0
        try:
            with os.scandir(str(current)) as it:
                entries = list(it)
        except PermissionError:
            scan_errors.append(f"Permission denied: {current}")
            continue
        except OSError as e:
            scan_errors.append(f"OS error reading {current}: {e}")
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    folder_count += 1
                    try:
                        child_path = entry.path
                        stack.append((Path(child_path), current_str))
                    except Exception:
                        scan_errors.append(f"Could not process dir: {entry.path}")
                        continue
                elif entry.is_file(follow_symlinks=False):
                    file_count += 1
                    try:
                        sz = entry.stat(follow_symlinks=False).st_size
                        total_size += sz
                        dir_size += sz
                        if sz > min_top_file_size:
                            top_files.append((sz, entry.path))
                            top_files.sort(reverse=True, key=lambda x: x[0])
                            if len(top_files) > MAX_TOP_FILES:
                                top_files = top_files[:MAX_TOP_FILES]
                            min_top_file_size = top_files[-1][0] if len(top_files) >= MAX_TOP_FILES else 0
                    except (OSError, PermissionError) as e:
                        scan_errors.append(f"Could not stat file: {entry.path}: {e}")
            except Exception:
                scan_errors.append(f"Unexpected error processing {entry.name}")
                continue
        rel = str(current.relative_to(root)) if current != root else "."
        is_backup, is_cache, is_generated = _classify_dir(rel)
        if is_backup:
            backup_dirs[rel] = dir_size
        if is_cache:
            cache_dirs[rel] = dir_size
        if is_generated:
            generated_artifact_dirs[rel] = dir_size
        if dir_size > min_top_dir_size:
            top_dirs[rel] = dir_size
            if len(top_dirs) > MAX_TOP_DIRS * 2:
                sorted_dirs = sorted(top_dirs.items(), key=lambda x: x[1], reverse=True)[:MAX_TOP_DIRS]
                top_dirs = dict(sorted_dirs)
                min_top_dir_size = sorted_dirs[-1][1] if len(sorted_dirs) >= MAX_TOP_DIRS else 0

    sorted_top_dirs = sorted(top_dirs.items(), key=lambda x: x[1], reverse=True)[:MAX_TOP_DIRS]
    sorted_top_files = [(p, s) for s, p in top_files]
    sorted_backup = sorted(backup_dirs.items(), key=lambda x: x[1], reverse=True)[:MAX_BACKUP_DIRS]
    sorted_cache = sorted(cache_dirs.items(), key=lambda x: x[1], reverse=True)[:MAX_CACHE_DIRS]
    sorted_generated = sorted(generated_artifact_dirs.items(), key=lambda x: x[1], reverse=True)[:MAX_GENERATED_DIRS]

    base_version = _detect_base_version()
    total_mb = round(total_size / (1024 * 1024), 2)
    total_gb = round(total_size / (1024 * 1024 * 1024), 2)

    return {
        "schema_version": "1.0",
        "project_name": "LocalComet / LocalAgent",
        "base_version": base_version,
        "generated_at": _now(),
        "root_path": root_str,
        "total_size_bytes": total_size,
        "total_size_mb": total_mb,
        "total_size_gb": total_gb,
        "file_count": file_count,
        "folder_count": folder_count,
        "top_directories": [{"path": p, "size_bytes": s, "size_mb": round(s / (1024 * 1024), 2)} for p, s in sorted_top_dirs],
        "top_files": [{"path": p, "size_bytes": s, "size_mb": round(s / (1024 * 1024), 2)} for p, s in sorted_top_files],
        "backup_directories": [{"path": p, "size_bytes": s, "size_mb": round(s / (1024 * 1024), 2)} for p, s in sorted_backup],
        "cache_directories": [{"path": p, "size_bytes": s, "size_mb": round(s / (1024 * 1024), 2)} for p, s in sorted_cache],
        "generated_artifact_directories": [{"path": p, "size_bytes": s, "size_mb": round(s / (1024 * 1024), 2)} for p, s in sorted_generated],
        "suspected_heavy_categories": {
            "opencode_backups_present": len(sorted_backup) > 0,
            "cache_present": len(sorted_cache) > 0,
            "generated_artifacts_present": len(sorted_generated) > 0,
        },
        "safe_cleanup_recommendations": [
            "Review opencode_backups directories; these contain pre-edit snapshots.",
            "Review __pycache__ directories; Python cache can be regenerated.",
            "Review .pytest_cache, .mypy_cache, .ruff_cache; test/lint caches.",
            "Review .venv / venv / node_modules; these can be reinstalled.",
            "Review dist / build; build artifacts can be regenerated.",
            "Review .localcomet generated reports; these are regenerated on demand.",
            "Review Projects/Reports; these are regenerated by tests and audits.",
            "Review Projects/ComputerUse/runs; these are runtime traces.",
            "Review backup .zip and manifest files in Projects/SelfEdit/opencode_backups.",
        ],
        "dangerous_cleanup_warning": "NO FILES WERE DELETED. This is an audit-only scan. Any cleanup requires explicit separate approval. The scanner only writes report files and never modifies repository data. Do not delete entire directories without verifying their contents.",
        "scan_errors": scan_errors if scan_errors else [],
        "source_references": {},
    }


def _write_report(payload: Dict[str, Any]) -> Dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPO_WEIGHT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# LocalComet Repository Weight Audit",
        "",
        f"- schema_version: {payload.get('schema_version')}",
        f"- project_name: {payload.get('project_name')}",
        f"- base_version: {payload.get('base_version')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- root_path: {payload.get('root_path')}",
        "",
        "## Overall Statistics",
        "",
        f"- total_size_bytes: {payload.get('total_size_bytes')}",
        f"- total_size_mb: {payload.get('total_size_mb')}",
        f"- total_size_gb: {payload.get('total_size_gb')}",
        f"- file_count: {payload.get('file_count')}",
        f"- folder_count: {payload.get('folder_count')}",
        "",
        "## Top Directories by Size",
        "",
    ]
    for i, d in enumerate(payload.get("top_directories", []), 1):
        lines.append(f"{i}. {d.get('path', '')} - {d.get('size_mb', 0)} MB ({d.get('size_bytes', 0)} bytes)")
    lines.append("")
    lines.extend(["## Top Files by Size", ""])
    for i, f in enumerate(payload.get("top_files", []), 1):
        lines.append(f"{i}. {f.get('path', '')} - {f.get('size_mb', 0)} MB ({f.get('size_bytes', 0)} bytes)")
    lines.append("")
    lines.extend(["## Backup Directories", ""])
    for bd in payload.get("backup_directories", []):
        lines.append(f"- {bd.get('path', '')} - {bd.get('size_mb', 0)} MB")
    if not payload.get("backup_directories"):
        lines.append("(none found)")
    lines.append("")
    lines.extend(["## Cache Directories", ""])
    for cd in payload.get("cache_directories", []):
        lines.append(f"- {cd.get('path', '')} - {cd.get('size_mb', 0)} MB")
    if not payload.get("cache_directories"):
        lines.append("(none found)")
    lines.append("")
    lines.extend(["## Generated Artifact Directories", ""])
    for ga in payload.get("generated_artifact_directories", []):
        lines.append(f"- {ga.get('path', '')} - {ga.get('size_mb', 0)} MB")
    if not payload.get("generated_artifact_directories"):
        lines.append("(none found)")
    lines.append("")
    lines.extend(["## Suspected Heavy Categories", ""])
    shc = payload.get("suspected_heavy_categories", {})
    for k, v in shc.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.extend(["## Safe Cleanup Recommendations", ""])
    for rec in payload.get("safe_cleanup_recommendations", []):
        lines.append(f"- {rec}")
    lines.append("")
    lines.extend(["## Dangerous Cleanup Warning", "", f"{payload.get('dangerous_cleanup_warning', '')}", ""])
    lines.extend(["## Scan Errors", ""])
    errs = payload.get("scan_errors", [])
    if errs:
        for e in errs:
            lines.append(f"- {e}")
    else:
        lines.append("(none)")
    lines.append("")
    REPO_WEIGHT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "json": str(REPO_WEIGHT_JSON.relative_to(ROOT_PATH)),
        "md": str(REPO_WEIGHT_MD.relative_to(ROOT_PATH)),
    }


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "repo_weight_audit_status",
        "version": REPO_WEIGHT_AUDIT_VERSION,
        "json_exists": REPO_WEIGHT_JSON.exists(),
        "md_exists": REPO_WEIGHT_MD.exists(),
    }


def report() -> Dict[str, Any]:
    payload = scan()
    paths = _write_report(payload)
    return {
        "ok": True,
        "mode": "repo_weight_audit_report",
        "version": REPO_WEIGHT_AUDIT_VERSION,
        "generated_at": _now(),
        "paths": paths,
    }


def is_repo_weight_audit_command(command: str) -> bool:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    return lowered in {
        "localcomet repo weight audit",
        "repo weight audit",
        "repo weight",
    } or lowered.startswith("localcomet repo weight audit ")


def dispatch(command: str) -> Dict[str, Any]:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    if lowered in {"localcomet repo weight audit", "repo weight audit", "repo weight"}:
        result = report()
        return {"ok": True, "handled": True, "mode": "repo_weight_audit_generated", "version": REPO_WEIGHT_AUDIT_VERSION, "paths": result.get("paths", {})}
    if lowered in {"localcomet repo weight audit status", "repo weight audit status", "repo weight status"}:
        return status()
    return {"ok": False, "mode": "repo_weight_audit_unknown", "version": REPO_WEIGHT_AUDIT_VERSION, "command": command, "hint": "Use: localcomet repo weight audit"}


if __name__ == "__main__":
    result = dispatch("localcomet repo weight audit")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
