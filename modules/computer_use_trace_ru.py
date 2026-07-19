
from __future__ import annotations

from typing import Any, Dict, List
import json

from modules.computer_use_schema_ru import events_path, latest_run_id, load_run, now_iso, reports_dir, run_dir, safe_json_dump, save_run, steps_dir

TRACE_VERSION = "v6.43"


def write_event(run_id: str, event_type: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_event_write", "error": "no run"}
    path = events_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"created_at": now_iso(), "run_id": rid, "event_type": event_type, "payload": payload or {}}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    state = load_run(rid)
    if state:
        state["events_count"] = int(state.get("events_count") or 0) + 1
        save_run(state)
    return {"ok": True, "mode": "computer_use_event_write", "event": event, "path": str(path)}


def save_step_artifact(run_id: str, step: int, artifact_type: str, payload: Dict[str, Any]) -> str:
    return safe_json_dump(steps_dir(run_id) / f"step_{step:03d}_{artifact_type}.json", payload)


def read_events(run_id: str = "", limit: int = 200) -> List[Dict[str, Any]]:
    rid = run_id or latest_run_id()
    if not rid:
        return []
    path = events_path(rid)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"event_type": "broken_event", "raw": line})
    return rows[-limit:]


def build_replay_summary(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_replay_summary", "error": "no runs"}
    return {"ok": True, "mode": "computer_use_replay_summary", "run_id": rid, "run_dir": str(run_dir(rid)), "events_path": str(events_path(rid)), "state": load_run(rid), "events": read_events(rid, 50)}


def write_run_report(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_report", "error": "no runs"}
    state = load_run(rid)
    path = reports_dir(rid) / "report.md"
    events = read_events(rid, 500)
    lines = [
        "# Computer Use Run Report",
        "",
        f"- generated_at: {now_iso()}",
        f"- run_id: {rid}",
        f"- goal: {state.get('goal', '')}",
        f"- phase: {state.get('phase', '')}",
        f"- status: {state.get('status', '')}",
        f"- step: {state.get('step', '')}",
        f"- pending_action_id: {state.get('pending_action_id', '')}",
        f"- pending_confirmation: {state.get('pending_confirmation', '')}",
        f"- latest_observation_path: {state.get('latest_observation_path', '')}",
        f"- latest_ui_map_path: {state.get('latest_ui_map_path', '')}",
        f"- latest_decision_path: {state.get('latest_decision_path', '')}",
        f"- latest_result_path: {state.get('latest_result_path', '')}",
        "",
        "## Events",
        "",
    ]
    for event in events:
        compact = json.dumps(event.get("payload") or {}, ensure_ascii=False)
        if len(compact) > 600:
            compact = compact[:600] + "..."
        lines.append(f"- {event.get('created_at', '')} `{event.get('event_type', '')}`")
        lines.append(f"  - payload: {compact}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    state["latest_report_path"] = str(path)
    save_run(state)
    return {"ok": True, "mode": "computer_use_report", "run_id": rid, "report": str(path), "state": state}


def latest_trace() -> Dict[str, Any]:
    rid = latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_latest_trace", "error": "no runs"}
    return {"ok": True, "mode": "computer_use_latest_trace", "run_id": rid, "state": load_run(rid), "events": read_events(rid, 30), "events_path": str(events_path(rid))}


def status() -> Dict[str, Any]:
    return {"ok": True, "mode": "computer_use_trace_status", "version": TRACE_VERSION, "latest_run_id": latest_run_id()}


def report() -> Dict[str, Any]:
    return latest_trace()


def is_computer_use_trace_command(command: str) -> bool:
    value = (command or "").strip().lower()
    return value in {"pc computer trace", "pc computer latest", "pc computer replay", "computer trace", "computer latest"}


def dispatch(command: str) -> Dict[str, Any]:
    value = (command or "").strip().lower()
    if value in {"pc computer trace", "computer trace", "pc computer latest", "computer latest"}:
        return latest_trace()
    if value.startswith("pc computer replay"):
        return build_replay_summary((command or "").strip().split()[-1] if len((command or "").strip().split()) >= 4 else "")
    if value in {"pc computer report", "отчёт computer use"}:
        return write_run_report()
    return {"ok": False, "mode": "computer_use_trace_unknown_command", "command": command}
