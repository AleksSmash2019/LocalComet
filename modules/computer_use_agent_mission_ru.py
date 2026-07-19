from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List, Optional, Tuple


AGENT_MISSION_VERSION = "v6.50h"
AGENT_MISSION_NAME = "Computer Use Agent Mission RU"

ROOT_DIR = get_project_root()
if not ROOT_DIR.exists():
    ROOT_DIR = Path(__file__).resolve().parents[1]

PROJECTS_DIR = ROOT_DIR / "Projects"
COMPUTER_USE_DIR = PROJECTS_DIR / "ComputerUse"
MISSION_DIR = COMPUTER_USE_DIR / "agent_missions"
LATEST_POINTER_FILE = MISSION_DIR / "latest_agent_mission.json"
STOP_REQUEST_FILE = MISSION_DIR / "agent_mission_stop_requested.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _safe_text(value: Any, limit: int = 6000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[truncated]"


def _ensure_dirs() -> None:
    MISSION_DIR.mkdir(parents=True, exist_ok=True)


def _safe_json_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _safe_json_read(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(value, dict):
                return value
    except Exception:
        return {}
    return {}


def _write_event(run_dir: Path, event: Dict[str, Any]) -> None:
    event_payload = dict(event)
    event_payload.setdefault("timestamp", _now())
    events_path = run_dir / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event_payload, ensure_ascii=False, sort_keys=True) + "\n")


def _make_mission(goal: str, simulate: bool, max_steps: int) -> Tuple[str, Path, Dict[str, Any]]:
    _ensure_dirs()
    mission_id = "mission_" + _stamp()
    run_dir = MISSION_DIR / mission_id
    run_dir.mkdir(parents=True, exist_ok=True)
    mission = {
        "ok": True,
        "mode": "computer_use_agent_mission",
        "version": AGENT_MISSION_VERSION,
        "mission_id": mission_id,
        "goal": str(goal or "").strip(),
        "simulate": bool(simulate),
        "max_steps": int(max_steps),
        "status": "running",
        "outcome": "running",
        "created_at": _now(),
        "updated_at": _now(),
        "run_dir": str(run_dir),
        "phases": [],
        "loop_result": None,
    }
    _safe_json_write(run_dir / "mission.json", mission)
    _safe_json_write(LATEST_POINTER_FILE, {"mission_id": mission_id, "run_dir": str(run_dir), "updated_at": _now()})
    _write_event(run_dir, {"event": "mission_created", "goal": goal, "simulate": bool(simulate), "max_steps": int(max_steps)})
    return mission_id, run_dir, mission


def _finish_mission(run_dir: Path, mission: Dict[str, Any], status: str, outcome: str, reason: str = "") -> Dict[str, Any]:
    mission["status"] = status
    mission["outcome"] = outcome
    mission["reason"] = reason
    mission["updated_at"] = _now()
    mission["ok"] = outcome not in {"blocked", "error"} if outcome != "requires_confirmation" else True
    _safe_json_write(run_dir / "mission.json", mission)
    _write_event(run_dir, {"event": "mission_finished", "status": status, "outcome": outcome, "reason": reason})
    _write_report(run_dir, mission)
    _safe_json_write(LATEST_POINTER_FILE, {"mission_id": mission.get("mission_id"), "run_dir": str(run_dir), "updated_at": _now()})
    return dict(mission)


def _write_report(run_dir: Path, mission: Dict[str, Any]) -> str:
    loop_result = mission.get("loop_result")
    loop_mode = loop_result.get("mode") if isinstance(loop_result, dict) else "none"
    loop_outcome = loop_result.get("outcome") if isinstance(loop_result, dict) else "none"
    lines = [
        "# Computer Use Agent Mission",
        "",
        f"- version: {AGENT_MISSION_VERSION}",
        f"- mission_id: {mission.get('mission_id')}",
        f"- status: {mission.get('status')}",
        f"- outcome: {mission.get('outcome')}",
        f"- simulate: {mission.get('simulate')}",
        f"- goal: {mission.get('goal')}",
        f"- reason: {mission.get('reason', '')}",
        f"- loop_mode: {loop_mode}",
        f"- loop_outcome: {loop_outcome}",
        "",
        "## Phases",
    ]
    for phase in mission.get("phases", []):
        lines.append(f"- {phase.get('name')}: {phase.get('status')} - {phase.get('detail', '')}")
    path = run_dir / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _phase(mission: Dict[str, Any], name: str, status: str, detail: str = "", data: Optional[Dict[str, Any]] = None) -> None:
    item = {"name": name, "status": status, "detail": str(detail or ""), "timestamp": _now()}
    if data is not None:
        item["data"] = data
    mission.setdefault("phases", []).append(item)


def _normalize(command: str) -> str:
    return " ".join(str(command or "").lower().replace("ё", "е").strip().split())


def _goal_after_prefix(raw: str, prefixes: List[str]) -> str:
    normalized_raw = _normalize(raw)
    raw_text = str(raw or "").strip()
    for prefix in prefixes:
        normalized_prefix = _normalize(prefix)
        if normalized_raw.startswith(normalized_prefix):
            return raw_text[len(prefix):].strip(" :,-—")
    return ""


def _typed_payload(goal: str) -> str:
    text = str(goal or "")
    if "::" in text:
        return text.split("::", 1)[1].strip()
    markers = ["введи ", "напечатай ", "type "]
    lowered = text.lower()
    for marker in markers:
        if marker in lowered:
            index = lowered.find(marker)
            return text[index + len(marker):].strip()
    return ""


def _payload_requires_confirmation(goal: str) -> Tuple[bool, str]:
    payload = _typed_payload(goal)
    if not payload:
        return False, ""
    lowered = payload.lower().replace("ё", "е")
    risky_markers = [
        "write ",
        "save ",
        "commit",
        "response.json",
        "request.md",
        "patch",
        "file",
        "файл",
        "запиши",
        "сохрани",
        "создай",
        "измени",
        "удали",
    ]
    for marker in risky_markers:
        if marker in lowered:
            return True, "typed payload appears to change files and needs explicit confirmation"
    return False, ""


def stop_requested() -> bool:
    return STOP_REQUEST_FILE.exists()


def request_stop(reason: str = "user requested stop") -> Dict[str, Any]:
    payload = {
        "ok": True,
        "mode": "computer_use_agent_mission_stop",
        "version": AGENT_MISSION_VERSION,
        "reason": str(reason or "user requested stop"),
        "timestamp": _now(),
    }
    _safe_json_write(STOP_REQUEST_FILE, payload)
    return payload


def clear_stop_request() -> Dict[str, Any]:
    existed = STOP_REQUEST_FILE.exists()
    if existed:
        cleared = STOP_REQUEST_FILE.with_name(STOP_REQUEST_FILE.name + ".cleared_" + _stamp())
        STOP_REQUEST_FILE.rename(cleared)
    return {
        "ok": True,
        "mode": "computer_use_agent_mission_clear_stop",
        "version": AGENT_MISSION_VERSION,
        "existed": existed,
    }


def status() -> Dict[str, Any]:
    _ensure_dirs()
    pointer = _safe_json_read(LATEST_POINTER_FILE)
    latest_data: Dict[str, Any] = {}
    run_dir_text = pointer.get("run_dir")
    if run_dir_text:
        latest_data = _safe_json_read(Path(str(run_dir_text)) / "mission.json")
    return {
        "ok": True,
        "handled": True,
        "mode": "computer_use_agent_mission_status",
        "version": AGENT_MISSION_VERSION,
        "missions_dir": str(MISSION_DIR),
        "latest_pointer": pointer,
        "latest_mission_id": latest_data.get("mission_id") or pointer.get("mission_id"),
        "latest_status": latest_data.get("status"),
        "latest_outcome": latest_data.get("outcome"),
        "stop_requested": stop_requested(),
    }


def latest_mission() -> Dict[str, Any]:
    pointer = _safe_json_read(LATEST_POINTER_FILE)
    run_dir_text = pointer.get("run_dir")
    if not run_dir_text:
        return {
            "ok": False,
            "handled": True,
            "mode": "computer_use_agent_mission_latest",
            "version": AGENT_MISSION_VERSION,
            "reason": "no mission has been recorded yet",
        }
    mission = _safe_json_read(Path(str(run_dir_text)) / "mission.json")
    if not mission:
        return {
            "ok": False,
            "handled": True,
            "mode": "computer_use_agent_mission_latest",
            "version": AGENT_MISSION_VERSION,
            "reason": "latest mission pointer exists but mission.json is missing",
            "latest_pointer": pointer,
        }
    mission["handled"] = True
    return mission


def latest_report() -> Dict[str, Any]:
    latest = latest_mission()
    if not latest.get("ok"):
        return latest
    report_path = Path(str(latest.get("run_dir"))) / "report.md"
    if not report_path.exists():
        _write_report(report_path.parent, latest)
    return {
        "ok": True,
        "handled": True,
        "mode": "computer_use_agent_mission_report",
        "version": AGENT_MISSION_VERSION,
        "mission_id": latest.get("mission_id"),
        "report": str(report_path),
        "content": _safe_text(report_path.read_text(encoding="utf-8", errors="replace"), 4000),
    }


def _safety_check(goal: str) -> Dict[str, Any]:
    try:
        from modules.computer_use_safety_ru import safety_check_goal
        result = safety_check_goal(goal)
        if isinstance(result, dict):
            return result
    except Exception as exc:
        return {"ok": False, "blocked": True, "risk": "blocked", "reason": "safety check failed: " + str(exc), "problem_types": ["safety_exception"]}
    return {"ok": False, "blocked": True, "risk": "blocked", "reason": "safety check returned invalid result", "problem_types": ["safety_invalid"]}


def _run_multistep(goal: str, simulate: bool, max_steps: int) -> Dict[str, Any]:
    from modules.computer_use_multistep_loop_ru import run_loop
    result = run_loop(goal, simulate=simulate, max_steps=max_steps, max_failures=1)
    if isinstance(result, dict):
        return result
    return {
        "ok": False,
        "mode": "computer_use_multistep_loop",
        "version": AGENT_MISSION_VERSION,
        "status": "error",
        "outcome": "error",
        "reason": "multistep loop returned non-dict result",
    }


def run_mission(goal: str, simulate: bool = True, max_steps: int = 4) -> Dict[str, Any]:
    goal = str(goal or "").strip()
    if not goal:
        return {
            "ok": False,
            "handled": True,
            "mode": "computer_use_agent_mission",
            "version": AGENT_MISSION_VERSION,
            "status": "rejected",
            "outcome": "ask_user",
            "reason": "empty goal",
        }

    max_steps = max(1, min(int(max_steps), 8))
    mission_id, run_dir, mission = _make_mission(goal, simulate, max_steps)

    try:
        _phase(mission, "goal_intake", "ok", "goal accepted", {"goal": goal, "simulate": bool(simulate)})
        if stop_requested():
            _phase(mission, "stop_gate", "stopped", "stop request is active")
            return _finish_mission(run_dir, mission, "stopped", "stopped", "stop request is active")

        safety = _safety_check(goal)
        mission["safety"] = safety
        if safety.get("blocked") or (safety.get("ok") is False and safety.get("risk") == "blocked"):
            _phase(mission, "safety_check", "blocked", str(safety.get("reason", "")), safety)
            return _finish_mission(run_dir, mission, "blocked", "blocked", str(safety.get("reason", "blocked by safety policy")))

        _phase(mission, "safety_check", "ok", str(safety.get("reason", "allowed")), safety)

        needs_confirmation, confirmation_reason = _payload_requires_confirmation(goal)
        if needs_confirmation:
            _phase(mission, "confirmation_gate", "requires_confirmation", confirmation_reason)
            return _finish_mission(run_dir, mission, "needs_user", "requires_confirmation", confirmation_reason)

        _phase(mission, "delegate_multistep_loop", "running", "delegating one-action-per-observation work to multistep loop")
        loop_result = _run_multistep(goal, simulate=simulate, max_steps=max_steps)
        mission["loop_result"] = loop_result
        loop_outcome = str(loop_result.get("outcome") or "ask_user")
        loop_status = str(loop_result.get("status") or ("done" if loop_result.get("ok") else "needs_user"))
        _phase(
            mission,
            "loop_result",
            "ok" if loop_result.get("ok") else "needs_user",
            "multistep loop returned " + loop_outcome,
            {
                "mode": loop_result.get("mode"),
                "status": loop_status,
                "outcome": loop_outcome,
                "reason": loop_result.get("reason", ""),
            },
        )
        if loop_outcome == "blocked":
            return _finish_mission(run_dir, mission, "blocked", "blocked", str(loop_result.get("reason", "")))
        if loop_outcome == "requires_confirmation":
            return _finish_mission(run_dir, mission, "needs_user", "requires_confirmation", str(loop_result.get("reason", "")))
        if loop_outcome == "done":
            return _finish_mission(run_dir, mission, "done", "done", str(loop_result.get("reason", "")))
        return _finish_mission(run_dir, mission, loop_status if loop_status else "needs_user", loop_outcome, str(loop_result.get("reason", "")))
    except Exception as exc:
        mission["error"] = str(exc)
        _phase(mission, "exception", "error", str(exc))
        return _finish_mission(run_dir, mission, "error", "error", str(exc))


def is_agent_mission_command(command: str) -> bool:
    lowered = _normalize(command)
    exact = {
        "pc computer agent status",
        "pc computer mission status",
        "pc computer agent latest",
        "pc computer mission latest",
        "pc computer agent report",
        "pc computer mission report",
        "pc computer agent stop",
        "pc computer mission stop",
        "pc computer agent clear stop",
        "статус агент computer use",
        "статус миссии computer use",
        "последняя миссия computer use",
        "отчет миссии computer use",
        "отчёт миссии computer use",
        "останови агент computer use",
    }
    if lowered in exact:
        return True
    prefixes = [
        "pc computer agent mission",
        "pc computer mission",
        "pc computer agent simulate",
        "pc computer simulate mission",
        "агент computer use",
        "миссия computer use",
        "симуляция агент computer use",
        "симуляция миссии computer use",
    ]
    return any(lowered.startswith(_normalize(prefix)) for prefix in prefixes)


def handle_dispatch_command(command: str) -> Dict[str, Any]:
    raw = str(command or "").strip()
    lowered = _normalize(raw)

    if lowered in {"pc computer agent status", "pc computer mission status", "статус агент computer use", "статус миссии computer use"}:
        return status()

    if lowered in {"pc computer agent latest", "pc computer mission latest", "последняя миссия computer use"}:
        result = latest_mission()
        result["handled"] = True
        return result

    if lowered in {"pc computer agent report", "pc computer mission report", "отчет миссии computer use", "отчёт миссии computer use"}:
        return latest_report()

    if lowered in {"pc computer agent stop", "pc computer mission stop", "останови агент computer use"}:
        result = request_stop("dispatch command: " + raw)
        result["handled"] = True
        return result

    if lowered == "pc computer agent clear stop":
        result = clear_stop_request()
        result["handled"] = True
        return result

    simulate_prefixes = [
        "pc computer agent simulate",
        "pc computer simulate mission",
        "симуляция агент computer use",
        "симуляция миссии computer use",
    ]
    for prefix in simulate_prefixes:
        goal = _goal_after_prefix(raw, [prefix])
        if goal:
            result = run_mission(goal, simulate=True, max_steps=4)
            result["handled"] = True
            return result

    run_prefixes = [
        "pc computer agent mission",
        "pc computer mission",
        "агент computer use",
        "миссия computer use",
    ]
    for prefix in run_prefixes:
        goal = _goal_after_prefix(raw, [prefix])
        if goal:
            result = run_mission(goal, simulate=False, max_steps=4)
            result["handled"] = True
            return result

    return {
        "ok": False,
        "handled": False,
        "mode": "computer_use_agent_mission",
        "version": AGENT_MISSION_VERSION,
        "reason": "not an agent mission command",
    }


def run_self_check(write_report: bool = True) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details if details is not None else {}})

    blocked = run_mission("удали все файлы через powershell", simulate=True, max_steps=2)
    add("dangerous shell delete mission is blocked", blocked.get("outcome") == "blocked", {"outcome": blocked.get("outcome"), "reason": blocked.get("reason")})

    confirmation = run_mission("введи Поиск :: write changes to file response.json", simulate=True, max_steps=2)
    add("file-changing typed mission requires confirmation", confirmation.get("outcome") == "requires_confirmation", {"outcome": confirmation.get("outcome"), "reason": confirmation.get("reason")})

    status_result = status()
    add("status route works", bool(status_result.get("ok")) and status_result.get("mode") == "computer_use_agent_mission_status", status_result)

    dispatch_status = handle_dispatch_command("pc computer agent status")
    add("dispatch status handled", bool(dispatch_status.get("handled")) and bool(dispatch_status.get("ok")), dispatch_status)

    dispatch_sim = handle_dispatch_command("pc computer agent simulate нажми Сохранить")
    add("dispatch simulated mission returns safe outcome", dispatch_sim.get("outcome") in {"done", "ask_user", "requires_confirmation", "blocked"}, {"outcome": dispatch_sim.get("outcome"), "status": dispatch_sim.get("status")})

    add("module has no public dispatch export", "dispatch" not in globals(), {})

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    payload = {
        "ok": summary["failed"] == 0,
        "mode": "computer_use_agent_mission_self_check",
        "version": AGENT_MISSION_VERSION,
        "summary": summary,
        "checks": checks,
    }

    if write_report:
        report_dir = MISSION_DIR / "self_checks"
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / ("self_check_" + _stamp() + ".json")
        _safe_json_write(path, payload)
        payload["report"] = str(path)

    return payload
