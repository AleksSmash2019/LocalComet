from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict


GREEN_GATE_STATUS_VERSION = "v6.58"
GREEN_GATE_STATUS_NAME = "LocalComet Green Gate Status RU"


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


def _reports_dir() -> Path:
    path = _root() / "Projects" / "Reports" / "green_gate_status"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_payload(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"ok": False, "mode": "unexpected_result", "value": str(value)[:2000]}


def _run_strict() -> Dict[str, Any]:
    try:
        from modules.strict_project_stability_ru import dispatch
        return _safe_payload(dispatch("проверь проект"))
    except Exception as exc:
        return {"ok": False, "mode": "strict_project_stability_error", "error": str(exc)}


def _latest_report(folder: str, pattern: str = "*.json") -> str:
    base = _root() / "Projects" / "Reports" / folder
    if not base.exists():
        return ""
    items = [p for p in base.glob(pattern) if p.is_file()]
    if not items:
        return ""
    try:
        return str(max(items, key=lambda p: p.stat().st_mtime))
    except Exception:
        return str(items[-1])


def get_green_gate_status(write_report: bool = True) -> Dict[str, Any]:
    strict = _run_strict()
    summary = strict.get("summary", {}) if isinstance(strict, dict) else {}
    hard_failures = int(summary.get("hard_failures", 999) or 0)
    warnings = int(summary.get("warnings", 999) or 0)
    clean_green = bool(strict.get("ok")) and hard_failures == 0 and warnings == 0
    payload: Dict[str, Any] = {
        "ok": clean_green,
        "mode": "green_gate_status",
        "version": GREEN_GATE_STATUS_VERSION,
        "generated_at": _now(),
        "clean_green": clean_green,
        "strict": {
            "ok": bool(strict.get("ok")),
            "score": strict.get("score", ""),
            "summary": summary,
            "report": strict.get("report", ""),
        },
        "latest_reports": {
            "functional": _latest_report("localcomet_functional_tests"),
            "contracts": _latest_report("computer_use_contracts"),
            "patch_ux": str(_root() / "Projects" / "Reports" / "patch_panel_ux" / "latest_patch_panel_ux_report.md"),
            "first_failure": str(_root() / "Projects" / "Reports" / "developer_velocity" / "latest_first_failure.md"),
        },
        "recommendation": "READY_FOR_NEXT_PATCH" if clean_green else "REPAIR_BEFORE_NEXT_PATCH",
        "report": "",
        "json": "",
    }
    if write_report:
        paths = _write_reports(payload)
        payload["report"] = str(paths["md"])
        payload["json"] = str(paths["json"])
    return payload


def _write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    out = _reports_dir()
    json_path = out / f"green_gate_status_{_stamp()}.json"
    md_path = out / f"green_gate_status_{_stamp()}.md"
    latest_json = out / "latest_green_gate_status.json"
    latest_md = out / "latest_green_gate_status.md"
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json_path.write_text(text, encoding="utf-8")
    latest_json.write_text(text, encoding="utf-8")
    strict_summary = payload.get("strict", {}).get("summary", {})
    lines = [
        "# LocalComet Green Gate Status",
        "",
        f"- version: {payload.get('version')}",
        f"- clean_green: {payload.get('clean_green')}",
        f"- recommendation: {payload.get('recommendation')}",
        f"- hard_failures: {strict_summary.get('hard_failures')}",
        f"- warnings: {strict_summary.get('warnings')}",
        f"- score: {payload.get('strict', {}).get('score')}",
        "",
        "## Latest reports",
        "",
    ]
    for key, value in payload.get("latest_reports", {}).items():
        lines.append(f"- {key}: {value}")
    md = "\n".join(lines)
    md_path.write_text(md, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")
    return {"json": json_path, "md": md_path}


def status(command: str = "status") -> Dict[str, Any]:
    return get_green_gate_status(write_report=True)


def report(command: str = "report") -> Dict[str, Any]:
    return get_green_gate_status(write_report=True)


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"статус разработки", "green gate", "green gate status", "dev status", "статус проекта"}:
        payload = get_green_gate_status(write_report=True)
        payload["handled"] = True
        return payload
    if lower in {"status", "статус"}:
        payload = status(command)
        payload["handled"] = True
        return payload
    if lower in {"report", "отчет"}:
        payload = report(command)
        payload["handled"] = True
        return payload
    return {"ok": False, "handled": False, "mode": "green_gate_status", "reason": "unknown command"}
