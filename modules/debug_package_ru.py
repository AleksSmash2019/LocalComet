from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List


DEBUG_PACKAGE_VERSION = "v6.58"
DEBUG_PACKAGE_NAME = "LocalComet Debug Package Collector RU"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / "AGENTS.md").exists() or (candidate / "LocalComet_Control_Panel.py").exists():
            return candidate
    return get_project_root()


def _packages_dir() -> Path:
    path = _root() / "Projects" / "Reports" / "debug_packages"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_rel(path: Path) -> str:
    try:
        return str(path.relative_to(_root())).replace("\\", "/")
    except Exception:
        return path.name


def _add_if_exists(zipf: zipfile.ZipFile, path: Path, added: List[str]) -> None:
    try:
        if path.exists() and path.is_file():
            arcname = _safe_rel(path)
            zipf.write(path, arcname)
            added.append(arcname)
    except Exception:
        pass


def _latest_in(folder: Path, pattern: str) -> Path | None:
    if not folder.exists():
        return None
    items = [p for p in folder.glob(pattern) if p.is_file()]
    if not items:
        return None
    try:
        return max(items, key=lambda p: p.stat().st_mtime)
    except Exception:
        return items[-1]


def _collect_candidates() -> List[Path]:
    root = _root()
    candidates: List[Path] = [
        root / "Projects" / "ChatGPTRelay" / "response.json",
        root / "Projects" / "ChatGPTRelay" / "selected_response_source.txt",
        root / "Projects" / "Reports" / "patch_panel_ux" / "latest_patch_panel_ux_report.md",
        root / "Projects" / "Reports" / "patch_panel_ux" / "latest_patch_panel_ux_report.json",
        root / "Projects" / "Reports" / "developer_velocity" / "latest_first_failure.md",
        root / "Projects" / "Reports" / "developer_velocity" / "latest_first_failure.json",
        root / "Projects" / "Reports" / "patch_event_timeline" / "latest_patch_event_timeline.md",
        root / "Projects" / "Reports" / "patch_event_timeline" / "latest_patch_event_timeline.json",
        root / "Projects" / "Reports" / "green_gate_status" / "latest_green_gate_status.md",
        root / "Projects" / "Reports" / "green_gate_status" / "latest_green_gate_status.json",
    ]
    latest_folders = [
        (root / "Projects" / "Reports" / "strict_project_stability", "*.md"),
        (root / "Projects" / "Reports" / "localcomet_functional_tests", "*.md"),
        (root / "Projects" / "Reports" / "computer_use_contracts", "*.json"),
        (root / "Projects" / "Reports" / "auto_verification", "*.md"),
    ]
    for folder, pattern in latest_folders:
        latest = _latest_in(folder, pattern)
        if latest:
            candidates.append(latest)
    return candidates


def create_debug_package(write_report: bool = True) -> Dict[str, Any]:
    from modules.first_failure_extractor_ru import find_latest_failure
    from modules.patch_event_timeline_ru import build_latest_timeline
    from modules.green_gate_status_ru import get_green_gate_status

    failure = find_latest_failure(write_report=True)
    timeline = build_latest_timeline(write_report=True)
    green = get_green_gate_status(write_report=True)

    package_path = _packages_dir() / f"localcomet_debug_package_{_stamp()}.zip"
    latest_package = _packages_dir() / "latest_localcomet_debug_package.zip"
    added: List[str] = []
    manifest: Dict[str, Any] = {
        "ok": True,
        "mode": "debug_package",
        "version": DEBUG_PACKAGE_VERSION,
        "created_at": _now(),
        "package": str(package_path),
        "first_failure": failure.get("failure", {}),
        "timeline_summary": timeline.get("summary", {}),
        "green_gate": {
            "clean_green": green.get("clean_green"),
            "recommendation": green.get("recommendation"),
            "strict_summary": green.get("strict", {}).get("summary", {}),
        },
        "files": [],
    }

    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for path in _collect_candidates():
            _add_if_exists(zipf, path, added)
        manifest["files"] = added
        zipf.writestr("debug_package_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))

    try:
        latest_package.write_bytes(package_path.read_bytes())
    except Exception:
        pass

    manifest["files"] = added
    manifest["package"] = str(package_path)
    manifest["latest_package"] = str(latest_package)
    if write_report:
        paths = _write_reports(manifest)
        manifest["report"] = str(paths["md"])
        manifest["json"] = str(paths["json"])
    return manifest


def _write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    out = _packages_dir()
    json_path = out / f"debug_package_{_stamp()}.json"
    md_path = out / f"debug_package_{_stamp()}.md"
    latest_json = out / "latest_debug_package.json"
    latest_md = out / "latest_debug_package.md"
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json_path.write_text(text, encoding="utf-8")
    latest_json.write_text(text, encoding="utf-8")
    lines = [
        "# LocalComet Debug Package",
        "",
        f"- version: {payload.get('version')}",
        f"- package: {payload.get('package')}",
        f"- latest_package: {payload.get('latest_package')}",
        f"- files: {len(payload.get('files', []))}",
        "",
        "## First failure",
        "",
        "```json",
        json.dumps(payload.get("first_failure", {}), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Green gate",
        "",
        "```json",
        json.dumps(payload.get("green_gate", {}), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
    ]
    md = "\n".join(lines)
    md_path.write_text(md, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")
    return {"json": json_path, "md": md_path}


def status(command: str = "status") -> Dict[str, Any]:
    latest = _packages_dir() / "latest_localcomet_debug_package.zip"
    return {
        "ok": True,
        "mode": "debug_package_status",
        "version": DEBUG_PACKAGE_VERSION,
        "latest_package": str(latest),
        "latest_exists": latest.exists(),
        "commands": ["debug пакет", "debug package", "собрать debug пакет"],
    }


def report(command: str = "report") -> Dict[str, Any]:
    return create_debug_package(write_report=True)


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"debug пакет", "собрать debug пакет", "debug package", "debug pack", "пакет отладки"}:
        payload = create_debug_package(write_report=True)
        payload["handled"] = True
        return payload
    if lower in {"status", "статус", "debug package status"}:
        payload = status(command)
        payload["handled"] = True
        return payload
    if lower in {"report", "отчет", "debug package report"}:
        payload = report(command)
        payload["handled"] = True
        return payload
    return {"ok": False, "handled": False, "mode": "debug_package", "reason": "unknown command"}
