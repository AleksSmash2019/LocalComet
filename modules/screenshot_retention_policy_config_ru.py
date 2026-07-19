from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from modules.project_paths import get_project_root, localcomet_policies_dir, localcomet_reports_dir

ROOT_PATH = get_project_root()
REPORT_DIR = localcomet_reports_dir(ROOT_PATH)
POLICY_DIR = localcomet_policies_dir(ROOT_PATH)
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

SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION = "v6.64e"
SCREENSHOT_RETENTION_POLICY_CONFIG_NAME = "LocalComet Screenshot Retention Policy Config RU"
SIMULATION_JSON = REPORT_DIR / "screenshot_storage_policy_simulation.json"
POLICY_JSON = POLICY_DIR / "screenshot_retention_policy.json"
POLICY_MD = POLICY_DIR / "screenshot_retention_policy.md"

def _load_simulation() -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    if not SIMULATION_JSON.exists():
        warnings.append("simulation source not found")
        return {}, warnings
    try:
        return json.loads(SIMULATION_JSON.read_text(encoding="utf-8")), warnings
    except Exception as e:
        warnings.append(f"invalid simulation source: {e}")
        return {}, warnings

def generate() -> Dict[str, Any]:
    sim, warnings = _load_simulation()
    selected = "keep_newest_500_per_directory"
    expected = 0.0
    for item in sim.get("simulated_policies", []) if isinstance(sim, dict) else []:
        if item.get("policy_name") == selected:
            expected = item.get("estimated_reclaimable_gb", 0.0)
            break
    return {
        "schema_version": "1.0",
        "project_name": "LocalComet",
        "base_version": _base_version(),
        "generated_at": _now(),
        "cleanup_mode": "policy_config_only",
        "deletion_enabled": False,
        "manual_approval_required": True,
        "selected_policy": selected,
        "selected_policy_reason": "Conservative storage cap that preserves recent debugging screenshots while reducing growth.",
        "screenshot_directories": sim.get("screenshot_directories", []) if isinstance(sim, dict) else [],
        "policy_limits": {
            "keep_newest_per_directory": 500,
            "keep_younger_than_days": None,
            "max_total_gb": None,
            "max_gb_per_directory": None,
        },
        "expected_reclaimable_gb_from_latest_simulation": expected,
        "simulation_summary": {
            "total_screenshot_files": sim.get("total_screenshot_files", 0) if isinstance(sim, dict) else 0,
            "total_screenshot_size_gb": sim.get("total_screenshot_size_gb", 0.0) if isinstance(sim, dict) else 0.0,
            "recommended_policy": sim.get("recommended_policy", "") if isinstance(sim, dict) else "",
        },
        "enforcement_status": {
            "active": False,
            "reason": "Policy is recorded but not enforced. Cleanup requires a separate explicit manual cleanup command.",
        },
        "dangerous_cleanup_warning": "NO FILES WERE DELETED. This policy is recorded only. Cleanup requires separate explicit approval.",
        "next_safe_action": "Review policy, then implement a separate manual cleanup command only with explicit approval.",
        "source_references": [_rel(SIMULATION_JSON), "LocalComet_Control_Panel.py"],
        "warnings": warnings,
    }

def _write_md(payload: Dict[str, Any]) -> None:
    lines = [
        "# Screenshot Retention Policy",
        f"- base_version: {payload.get('base_version')}",
        f"- cleanup_mode: {payload.get('cleanup_mode')}",
        f"- deletion_enabled: {payload.get('deletion_enabled')}",
        f"- manual_approval_required: {payload.get('manual_approval_required')}",
        f"- selected_policy: {payload.get('selected_policy')}",
        f"- expected_reclaimable_gb_from_latest_simulation: {payload.get('expected_reclaimable_gb_from_latest_simulation')}",
        f"- enforcement_status.active: {payload.get('enforcement_status', {}).get('active')}",
        "",
        payload.get("dangerous_cleanup_warning", ""),
    ]
    POLICY_MD.parent.mkdir(parents=True, exist_ok=True)
    POLICY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

def write() -> Dict[str, Any]:
    payload = generate()
    _write_json(POLICY_JSON, payload)
    _write_md(payload)
    return {"ok": True, "handled": True, "mode": "screenshot_retention_policy_config_written", "version": SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION, "paths": {"json": _rel(POLICY_JSON), "md": _rel(POLICY_MD)}, "summary": {"selected_policy": payload["selected_policy"], "deletion_enabled": payload["deletion_enabled"]}}

def report() -> Dict[str, Any]:
    return write()

def status() -> Dict[str, Any]:
    return {"ok": True, "mode": "screenshot_retention_policy_config_status", "version": SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION, "json": _rel(POLICY_JSON), "md": _rel(POLICY_MD)}

def is_screenshot_retention_policy_config_command(command: str) -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {"localcomet screenshots retention policy write", "screenshots retention policy write", "retention policy write", "localcomet screenshots retention policy status"}

def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if "status" in lower:
        return status()
    if is_screenshot_retention_policy_config_command(command) or not lower:
        return write()
    return {"ok": False, "handled": False, "mode": "screenshot_retention_policy_config_unhandled", "version": SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION, "command": command}
