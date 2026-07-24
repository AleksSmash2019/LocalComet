from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from modules.project_paths import build_retention_plan, get_project_root, localcomet_reports_dir, retention_runtime_roots

ROOT_PATH = get_project_root()
REPORT_DIR = localcomet_reports_dir(ROOT_PATH)
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

SCREENSHOT_RETENTION_DRY_RUN_VERSION = "v6.79"
SCREENSHOT_RETENTION_DRY_RUN_NAME = "LocalComet Screenshot Retention Dry Run RU"
DRY_RUN_JSON = REPORT_DIR / "screenshot_retention_dry_run.json"
DRY_RUN_MD = REPORT_DIR / "screenshot_retention_dry_run.md"

def scan() -> Dict[str, Any]:
    return build_retention_plan(ROOT_PATH, retention_runtime_roots(ROOT_PATH))

def _write_md(payload: Dict[str, Any]) -> None:
    lines = [
        "# Runtime Retention Dry Run",
        f"- mode: {payload.get('mode')}",
        f"- version: {payload.get('version')}",
        f"- dry_run: {payload.get('dry_run')}",
        f"- candidate_count: {payload.get('totals', {}).get('candidate_count')}",
        f"- protected_count: {payload.get('totals', {}).get('protected_count')}",
        f"- rejected_count: {payload.get('totals', {}).get('rejected_count')}",
        "",
        "NO FILES WERE DELETED. This is a deterministic dry-run-only plan.",
    ]
    DRY_RUN_MD.parent.mkdir(parents=True, exist_ok=True)
    DRY_RUN_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

def report() -> Dict[str, Any]:
    payload = scan()
    _write_json(DRY_RUN_JSON, payload)
    _write_md(payload)
    return {"ok": True, "handled": True, "mode": "screenshot_retention_dry_run_generated", "version": SCREENSHOT_RETENTION_DRY_RUN_VERSION, "paths": {"json": _rel(DRY_RUN_JSON), "md": _rel(DRY_RUN_MD)}, "summary": payload.get("totals", {})}

def status() -> Dict[str, Any]:
    return {"ok": True, "mode": "screenshot_retention_dry_run_status", "version": SCREENSHOT_RETENTION_DRY_RUN_VERSION, "json": _rel(DRY_RUN_JSON), "md": _rel(DRY_RUN_MD)}

def is_screenshot_retention_dry_run_command(command: str) -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {"localcomet screenshots retention dry run", "screenshots retention dry run", "screenshot dry run", "localcomet screenshots retention dry-run"}

def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if "status" in lower:
        return status()
    if is_screenshot_retention_dry_run_command(command) or not lower:
        return report()
    return {"ok": False, "handled": False, "mode": "screenshot_retention_dry_run_unhandled", "version": SCREENSHOT_RETENTION_DRY_RUN_VERSION, "command": command}
