from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT_PATH = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_PATH / ".localcomet" / "reports"
POLICY_DIR = ROOT_PATH / ".localcomet" / "policies"
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _base_version() -> str:
    try:
        for line in CONTROL_PANEL_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("LOCALCOMET_VERSION"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    return parts[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "unknown"

def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_PATH)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")

def _screenshot_dirs() -> List[Path]:
    return [
        ROOT_PATH / "Projects" / "Reports" / "desktop_observer" / "screenshots",
        ROOT_PATH / "Projects" / "Reports" / "browser_screenshots",
    ]

def _iter_files(directory: Path) -> List[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    result: List[Path] = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git"}]
        for name in files:
            try:
                p = Path(root) / name
                if p.is_file():
                    result.append(p)
            except Exception:
                continue
    return result

def _file_info(path: Path) -> Dict[str, Any]:
    st = path.stat()
    return {
        "path": _rel(path),
        "size_bytes": int(st.st_size),
        "size_mb": round(st.st_size / (1024 * 1024), 4),
        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
    }

def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION = "v6.64d"
SCREENSHOT_STORAGE_POLICY_SIMULATOR_NAME = "LocalComet Screenshot Storage Policy Simulator RU"
SIMULATION_JSON = REPORT_DIR / "screenshot_storage_policy_simulation.json"
SIMULATION_MD = REPORT_DIR / "screenshot_storage_policy_simulation.md"

def _collect() -> Tuple[List[Path], List[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    dirs: List[Dict[str, Any]] = []
    all_files: List[Path] = []
    for d in _screenshot_dirs():
        try:
            files = _iter_files(d)
            all_files.extend(files)
            size = sum(p.stat().st_size for p in files)
            dirs.append({"path": _rel(d), "exists": d.exists(), "file_count": len(files), "size_bytes": int(size), "size_gb": round(size / (1024 ** 3), 4)})
        except Exception as e:
            errors.append(f"{_rel(d)}: {e}")
    all_files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return all_files, dirs, errors

def _simulate_policy(name: str, files: List[Path], keep_predicate) -> Dict[str, Any]:
    kept: List[Path] = []
    marked: List[Path] = []
    for p in files:
        try:
            (kept if keep_predicate(p, len(kept)) else marked).append(p)
        except Exception:
            kept.append(p)
    bytes_kept = sum(p.stat().st_size for p in kept if p.exists())
    bytes_marked = sum(p.stat().st_size for p in marked if p.exists())
    return {
        "policy_name": name,
        "files_kept": len(kept),
        "files_marked": len(marked),
        "bytes_kept": int(bytes_kept),
        "bytes_marked": int(bytes_marked),
        "estimated_reclaimable_gb": round(bytes_marked / (1024 ** 3), 4),
        "deletion_enabled": False,
    }

def generate() -> Dict[str, Any]:
    files, dirs, errors = _collect()
    now_ts = datetime.now().timestamp()
    total = sum(p.stat().st_size for p in files if p.exists())
    if files:
        oldest = min(p.stat().st_mtime for p in files if p.exists())
        observed_days = max(1.0, (now_ts - oldest) / 86400)
    else:
        observed_days = 1.0
    gb = total / (1024 ** 3)
    growth = round(gb / observed_days, 4) if observed_days else 0.0
    by_dir: Dict[str, List[Path]] = {}
    for p in files:
        key = str(p.parent)
        by_dir.setdefault(key, []).append(p)
    newest_100 = set()
    newest_500 = set()
    for group in by_dir.values():
        group.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        newest_100.update(str(p) for p in group[:100])
        newest_500.update(str(p) for p in group[:500])
    max10 = set(str(p) for p in files)
    running = 0
    max10 = set()
    for p in files:
        size = p.stat().st_size if p.exists() else 0
        if running + size <= 10 * (1024 ** 3):
            max10.add(str(p))
            running += size
    policies = [
        _simulate_policy("keep_newest_100_per_directory", files, lambda p, _: str(p) in newest_100),
        _simulate_policy("keep_newest_500_per_directory", files, lambda p, _: str(p) in newest_500),
        _simulate_policy("keep_last_1_day", files, lambda p, _: (now_ts - p.stat().st_mtime) <= 86400),
        _simulate_policy("keep_last_3_days", files, lambda p, _: (now_ts - p.stat().st_mtime) <= 3 * 86400),
        _simulate_policy("keep_last_7_days", files, lambda p, _: (now_ts - p.stat().st_mtime) <= 7 * 86400),
        _simulate_policy("keep_max_2_gb_per_directory", files, lambda p, _: True),
        _simulate_policy("keep_max_5_gb_per_directory", files, lambda p, _: True),
        _simulate_policy("keep_max_10_gb_total", files, lambda p, _: str(p) in max10),
    ]
    return {
        "schema_version": "1.0",
        "project_name": "LocalComet",
        "base_version": _base_version(),
        "generated_at": _now(),
        "cleanup_mode": "simulation_only",
        "deletion_enabled": False,
        "screenshot_directories": dirs,
        "total_screenshot_files": len(files),
        "total_screenshot_size_bytes": int(total),
        "total_screenshot_size_gb": round(gb, 4),
        "simulated_policies": policies,
        "recommended_policy": "keep_newest_500_per_directory" if gb > 10 else "keep_last_7_days",
        "growth_rate_estimate": {"gb_per_day": growth, "observed_days": round(observed_days, 2)},
        "projected_30_day_size_gb": round(growth * 30, 4),
        "projected_90_day_size_gb": round(growth * 90, 4),
        "largest_screenshots": sorted([_file_info(p) for p in files], key=lambda x: x["size_bytes"], reverse=True)[:25],
        "manual_review_required": True,
        "dangerous_cleanup_warning": "NO FILES WERE DELETED. This is a simulation-only report.",
        "next_safe_action": "Choose a policy and write a passive retention policy config.",
        "scan_errors": errors,
        "source_references": ["screenshot_retention_dry_run"],
    }

def _write_md(payload: Dict[str, Any]) -> None:
    lines = [
        "# Screenshot Storage Policy Simulation",
        f"- base_version: {payload.get('base_version')}",
        f"- cleanup_mode: {payload.get('cleanup_mode')}",
        f"- deletion_enabled: {payload.get('deletion_enabled')}",
        f"- total_screenshot_files: {payload.get('total_screenshot_files')}",
        f"- total_screenshot_size_gb: {payload.get('total_screenshot_size_gb')}",
        f"- recommended_policy: {payload.get('recommended_policy')}",
        f"- projected_30_day_size_gb: {payload.get('projected_30_day_size_gb')}",
        f"- projected_90_day_size_gb: {payload.get('projected_90_day_size_gb')}",
        "",
        payload.get("dangerous_cleanup_warning", ""),
    ]
    SIMULATION_MD.parent.mkdir(parents=True, exist_ok=True)
    SIMULATION_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

def report() -> Dict[str, Any]:
    payload = generate()
    _write_json(SIMULATION_JSON, payload)
    _write_md(payload)
    return {"ok": True, "handled": True, "mode": "screenshot_storage_policy_simulator_generated", "version": SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION, "paths": {"json": _rel(SIMULATION_JSON), "md": _rel(SIMULATION_MD)}, "summary": {"total_screenshot_files": payload["total_screenshot_files"], "total_screenshot_size_gb": payload["total_screenshot_size_gb"]}}

def status() -> Dict[str, Any]:
    return {"ok": True, "mode": "screenshot_storage_policy_simulator_status", "version": SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION}

def is_screenshot_storage_policy_simulator_command(command: str) -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {"localcomet screenshots storage policy simulate", "screenshots storage policy simulate", "storage policy simulate", "localcomet screenshots storage policy simulate status"}

def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if "status" in lower:
        return status()
    if is_screenshot_storage_policy_simulator_command(command) or not lower:
        return report()
    return {"ok": False, "handled": False, "mode": "screenshot_storage_policy_simulator_unhandled", "version": SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION, "command": command}
