from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from modules.project_paths import build_retention_plan, get_project_root, localcomet_reports_dir, retention_runtime_roots

STORAGE_CLEANUP_PLAN_VERSION = "v6.79"
STORAGE_CLEANUP_PLAN_NAME = "LocalComet Storage Cleanup Plan Generator RU"

ROOT_PATH = get_project_root()
OUTPUT_DIR = localcomet_reports_dir(ROOT_PATH)
STORAGE_CLEANUP_JSON = OUTPUT_DIR / "storage_cleanup_plan.json"
STORAGE_CLEANUP_MD = OUTPUT_DIR / "storage_cleanup_plan.md"
REPO_WEIGHT_JSON = OUTPUT_DIR / "repo_weight_report.json"
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"

EXTERNAL_BACKUP_NOTE = (
    "An external backup folder at C:\\Users\\DNS\\Documents\\LocalAgent_Backups "
    "was noted (~32.9 GB). This path is outside the repository root "
    "and was not scanned by the internal audit. Manual review and cleanup required."
)

NO_DELETION_WARNING = (
    "NO FILES WERE DELETED. This is a plan-only report. "
    "Cleanup requires separate explicit approval."
)


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


def _load_source_report() -> Dict[str, Any]:
    result: Dict[str, Any] = {"found": False, "data": {}, "warning": ""}
    if not REPO_WEIGHT_JSON.exists():
        result["warning"] = "repo_weight_report.json not found. Run 'localcomet repo weight audit' first."
        return result
    try:
        data = json.loads(REPO_WEIGHT_JSON.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            result["warning"] = "repo_weight_report.json contains invalid data (not a dict)."
            return result
        result["found"] = True
        result["data"] = data
    except json.JSONDecodeError:
        result["warning"] = "repo_weight_report.json is invalid JSON. Run 'localcomet repo weight audit' to regenerate."
    except Exception as e:
        result["warning"] = f"Error reading repo_weight_report.json: {e}"
    return result


def _build_candidates(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    data = source.get("data", {})
    if not source.get("found"):
        return candidates

    dirs = data.get("top_directories", [])

    for d in dirs:
        dp = d.get("path", "")
        sz = d.get("size_bytes", 0)
        sm = d.get("size_mb", 0)
        if not dp:
            continue

        if "screenshots" in dp.lower():
            candidates.append({
                "path": dp,
                "size_bytes": sz,
                "size_mb": sm,
                "category": "screenshots",
                "action": "review",
                "priority": "high",
                "reason": f"Screenshot directory at {dp} consumes {sm} MB.",
            })

        if "opencode_backup" in dp.lower() or "backup" in dp.lower():
            candidates.append({
                "path": dp,
                "size_bytes": sz,
                "size_mb": sm,
                "category": "backup",
                "action": "review",
                "priority": "medium",
                "reason": f"Backup directory at {dp} consumes {sm} MB.",
            })

    for bd in data.get("backup_directories", []):
        bp = bd.get("path", "")
        bz = bd.get("size_bytes", 0)
        bm = bd.get("size_mb", 0)
        if bp and not any(c.get("path") == bp for c in candidates):
            candidates.append({
                "path": bp,
                "size_bytes": bz,
                "size_mb": bm,
                "category": "backup",
                "action": "review",
                "priority": "medium",
                "reason": f"Backup directory at {bp} consumes {bm} MB.",
            })

    for cd in data.get("cache_directories", []):
        cp = cd.get("path", "")
        cz = cd.get("size_bytes", 0)
        cm = cd.get("size_mb", 0)
        if cp and not any(c.get("path") == cp for c in candidates):
            candidates.append({
                "path": cp,
                "size_bytes": cz,
                "size_mb": cm,
                "category": "cache",
                "action": "clean",
                "priority": "low",
                "reason": f"Cache directory at {cp} consumes {cm} MB.",
            })

    for gd in data.get("generated_artifact_directories", []):
        gp = gd.get("path", "")
        gz = gd.get("size_bytes", 0)
        gm = gd.get("size_mb", 0)
        if gp and not any(c.get("path") == gp for c in candidates):
            candidates.append({
                "path": gp,
                "size_bytes": gz,
                "size_mb": gm,
                "category": "generated_artifact",
                "action": "regenerate",
                "priority": "low",
                "reason": f"Generated artifact directory at {gp} consumes {gm} MB.",
            })

    return candidates


def _estimate_reclaimable(candidates: List[Dict[str, Any]]) -> float:
    total = 0.0
    for c in candidates:
        if c.get("category") in ("cache", "backup", "generated_artifact"):
            total += c.get("size_mb", 0)
    return round(total, 2)


def generate() -> Dict[str, Any]:
    return build_retention_plan(ROOT_PATH, retention_runtime_roots(ROOT_PATH))


def _write_plan(payload: Dict[str, Any]) -> Dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_CLEANUP_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    lines = [
        "# LocalComet Runtime Retention Plan",
        "",
        f"- mode: {payload.get('mode')}",
        f"- version: {payload.get('version')}",
        f"- dry_run: {payload.get('dry_run')}",
        f"- candidate_count: {payload.get('totals', {}).get('candidate_count')}",
        f"- protected_count: {payload.get('totals', {}).get('protected_count')}",
        f"- rejected_count: {payload.get('totals', {}).get('rejected_count')}",
        "",
        "## Policy",
        "",
    ]
    for key, value in payload.get("policy", {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    lines.extend(["## Cleanup Candidates", ""])
    for c in payload.get("candidates", []):
        lines.append(f"- {c.get('path', '')} ({c.get('size_bytes', 0)} bytes)")
        lines.append(f"  - {c.get('reason', '')}")

    if not payload.get("candidates"):
        lines.append("(none found)")
    lines.append("")

    lines.extend(["## Dangerous Cleanup Warning", "", NO_DELETION_WARNING, ""])

    STORAGE_CLEANUP_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "json": str(STORAGE_CLEANUP_JSON.relative_to(ROOT_PATH)),
        "md": str(STORAGE_CLEANUP_MD.relative_to(ROOT_PATH)),
    }


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "storage_cleanup_plan_status",
        "version": STORAGE_CLEANUP_PLAN_VERSION,
        "json_exists": STORAGE_CLEANUP_JSON.exists(),
        "md_exists": STORAGE_CLEANUP_MD.exists(),
    }


def report() -> Dict[str, Any]:
    payload = generate()
    paths = _write_plan(payload)
    return {
        "ok": True,
        "mode": "storage_cleanup_plan_report",
        "version": STORAGE_CLEANUP_PLAN_VERSION,
        "paths": paths,
        "plan": payload,
    }


def is_storage_cleanup_plan_command(command: str) -> bool:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    return lowered in {
        "localcomet storage cleanup plan",
        "storage cleanup plan",
        "cleanup plan",
    } or lowered.startswith("localcomet storage cleanup plan ")


def dispatch(command: str) -> Dict[str, Any]:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    if lowered in {"localcomet storage cleanup plan", "storage cleanup plan", "cleanup plan"}:
        result = report()
        return {"ok": True, "handled": True, "mode": "storage_cleanup_plan_generated", "version": STORAGE_CLEANUP_PLAN_VERSION, "paths": result.get("paths", {})}
    if lowered in {"localcomet storage cleanup plan status", "storage cleanup plan status", "cleanup plan status"}:
        return status()
    return {"ok": False, "mode": "storage_cleanup_plan_unknown", "version": STORAGE_CLEANUP_PLAN_VERSION, "command": command, "hint": "Use: localcomet storage cleanup plan"}


if __name__ == "__main__":
    result = dispatch("localcomet storage cleanup plan")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
