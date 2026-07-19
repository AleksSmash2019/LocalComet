from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List


PATCH_EVENT_TIMELINE_VERSION = "v6.58"
PATCH_EVENT_TIMELINE_NAME = "LocalComet Patch Event Timeline RU"


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
    path = _root() / "Projects" / "Reports" / "patch_event_timeline"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _latest_patch_ux_report() -> Path:
    return _root() / "Projects" / "Reports" / "patch_panel_ux" / "latest_patch_panel_ux_report.md"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _event_status(line: str) -> str:
    lower = line.lower().replace("ё", "е")
    if any(token in lower for token in ["✅", "ok:", "успеш", "пройдена", "code: 0", "applied_ok"]):
        return "ok"
    if any(token in lower for token in ["❌", "stop:", "ошибка", "failed", "rollback", "откачен", "code: 1", "code: 2"]):
        return "error"
    if any(token in lower for token in ["warning", "предупреж"]):
        return "warning"
    return "info"


def build_timeline_from_text(text: str, source: str = "") -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    current_stage = "unknown"
    section_pattern = re.compile(r"^\s*-{2,}\s*([A-ZА-ЯЁ0-9 _-]+)\s*-{2,}\s*$")
    for number, raw in enumerate(str(text or "").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        section = section_pattern.match(line)
        if section:
            current_stage = section.group(1).strip().lower().replace(" ", "_")
            events.append({
                "event_id": f"evt_{len(events)+1:04d}",
                "line": number,
                "stage": current_stage,
                "kind": "stage",
                "status": "info",
                "message": line,
            })
            continue
        lower = line.lower().replace("ё", "е")
        interesting = (
            lower.startswith("$ ")
            or "code:" in lower
            or "rollback" in lower
            or "откач" in lower
            or "ошибка" in lower
            or "stop:" in lower
            or "patch успешно" in lower
            or "patch registry" in lower
            or "validation" in lower
            or "проверка" in lower
        )
        if interesting:
            events.append({
                "event_id": f"evt_{len(events)+1:04d}",
                "line": number,
                "stage": current_stage,
                "kind": "observation" if not lower.startswith("$ ") else "action",
                "status": _event_status(line),
                "message": line[:1200],
            })
    summary = {
        "total": len(events),
        "errors": sum(1 for item in events if item.get("status") == "error"),
        "warnings": sum(1 for item in events if item.get("status") == "warning"),
        "ok": sum(1 for item in events if item.get("status") == "ok"),
    }
    return {
        "ok": True,
        "mode": "patch_event_timeline",
        "version": PATCH_EVENT_TIMELINE_VERSION,
        "generated_at": _now(),
        "source": source,
        "summary": summary,
        "events": events[-200:],
    }


def build_latest_timeline(write_report: bool = True) -> Dict[str, Any]:
    source = _latest_patch_ux_report()
    text = _read(source)
    if not text:
        source = _root() / "Projects" / "ChatGPTRelay" / "response.json"
        text = _read(source)
    payload = build_timeline_from_text(text, source=str(source))
    if write_report:
        paths = _write_reports(payload)
        payload["report"] = str(paths["md"])
        payload["json"] = str(paths["json"])
    return payload


def _write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    out = _reports_dir()
    json_path = out / f"patch_event_timeline_{_stamp()}.json"
    md_path = out / f"patch_event_timeline_{_stamp()}.md"
    latest_json = out / "latest_patch_event_timeline.json"
    latest_md = out / "latest_patch_event_timeline.md"
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json_path.write_text(text, encoding="utf-8")
    latest_json.write_text(text, encoding="utf-8")
    lines = [
        "# LocalComet Patch Event Timeline",
        "",
        f"- version: {payload.get('version')}",
        f"- source: {payload.get('source')}",
        f"- summary: {payload.get('summary')}",
        "",
        "| id | stage | kind | status | message |",
        "|---|---|---|---|---|",
    ]
    for event in payload.get("events", [])[-80:]:
        message = str(event.get("message", "")).replace("|", "\\|")
        lines.append(f"| {event.get('event_id')} | {event.get('stage')} | {event.get('kind')} | {event.get('status')} | {message[:300]} |")
    md = "\n".join(lines)
    md_path.write_text(md, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")
    return {"json": json_path, "md": md_path}


def status(command: str = "status") -> Dict[str, Any]:
    latest = _reports_dir() / "latest_patch_event_timeline.json"
    return {
        "ok": True,
        "mode": "patch_event_timeline_status",
        "version": PATCH_EVENT_TIMELINE_VERSION,
        "latest_json": str(latest),
        "latest_exists": latest.exists(),
        "commands": ["события патча", "patch events", "patch timeline"],
    }


def report(command: str = "report") -> Dict[str, Any]:
    return build_latest_timeline(write_report=True)


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"события патча", "patch events", "patch timeline", "таймлайн патча"}:
        payload = build_latest_timeline(write_report=True)
        payload["handled"] = True
        return payload
    if lower in {"status", "статус", "patch events status"}:
        payload = status(command)
        payload["handled"] = True
        return payload
    if lower in {"report", "отчет", "patch events report"}:
        payload = report(command)
        payload["handled"] = True
        return payload
    return {"ok": False, "handled": False, "mode": "patch_event_timeline", "reason": "unknown command"}
