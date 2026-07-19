from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_PATH = Path(__file__).resolve().parents[1]
MEMORY_DIR = ROOT_PATH / "Projects" / "AgentMemory"
STATE_PATH = MEMORY_DIR / "agent_state.json"
PROJECT_CONTEXT_PATH = MEMORY_DIR / "project_context.json"
TASK_HISTORY_PATH = MEMORY_DIR / "task_history.json"
BACKLOG_PATH = MEMORY_DIR / "agent_backlog.json"


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_memory_dir() -> Path:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return MEMORY_DIR


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _write_json(path: Path, data: Any) -> Path:
    ensure_memory_dir()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def default_state() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "ai_agent_state",
        "created_at": _now(),
        "updated_at": _now(),
        "agent_version": "v6.41d",
        "phase": "idle",
        "active_goal": "",
        "latest_project_map": "",
        "latest_context": str(PROJECT_CONTEXT_PATH),
        "latest_draft": "",
        "latest_verification_report": "",
        "latest_repair_plan": "",
        "stable_version": "",
        "notes": [
            "LocalComet AI Agent Core is safe-by-default.",
            "Patches are drafted for Relay and are not applied automatically.",
            "Project verification is the gate after every applied patch.",
        ],
    }


def load_state() -> dict[str, Any]:
    ensure_memory_dir()
    state = _read_json(STATE_PATH, default_state())
    if not isinstance(state, dict):
        state = default_state()
    state.setdefault("ok", True)
    state.setdefault("mode", "ai_agent_state")
    state.setdefault("phase", "idle")
    state.setdefault("active_goal", "")
    state.setdefault("agent_version", "v6.41d")
    state["updated_at"] = _now()
    return state


def save_state(state: dict[str, Any]) -> dict[str, Any]:
    payload = dict(state)
    payload["updated_at"] = _now()
    _write_json(STATE_PATH, payload)
    return payload


def set_phase(phase: str, goal: str | None = None, **extra: Any) -> dict[str, Any]:
    state = load_state()
    state["phase"] = str(phase or "idle")
    if goal is not None:
        state["active_goal"] = str(goal)
    for key, value in extra.items():
        state[key] = value
    return save_state(state)


def append_history(event: dict[str, Any]) -> list[dict[str, Any]]:
    ensure_memory_dir()
    history = _read_json(TASK_HISTORY_PATH, [])
    if not isinstance(history, list):
        history = []
    item = dict(event)
    item.setdefault("generated_at", _now())
    history.append(item)
    history = history[-300:]
    _write_json(TASK_HISTORY_PATH, history)
    return history


def save_project_context(context: dict[str, Any]) -> dict[str, Any]:
    _write_json(PROJECT_CONTEXT_PATH, context)
    state = load_state()
    state["latest_context"] = str(PROJECT_CONTEXT_PATH)
    if context.get("project_map_path"):
        state["latest_project_map"] = str(context.get("project_map_path"))
    save_state(state)
    append_history({
        "type": "project_context",
        "ok": bool(context.get("ok", True)),
        "path": str(PROJECT_CONTEXT_PATH),
        "summary": {
            "python_files": context.get("python_file_count"),
            "functions": context.get("function_count"),
            "command_modules": context.get("command_module_count"),
        },
    })
    return context


def save_backlog(items: list[dict[str, Any]]) -> Path:
    return _write_json(BACKLOG_PATH, items)


def load_backlog() -> list[dict[str, Any]]:
    data = _read_json(BACKLOG_PATH, [])
    return data if isinstance(data, list) else []


def seed_default_backlog(force: bool = False) -> list[dict[str, Any]]:
    existing = load_backlog()
    if existing and not force:
        return existing

    items = [
        {
            "id": "AI-0001",
            "priority": "P0",
            "status": "ready",
            "title": "Project Map",
            "why": "Агенту нужна карта проекта перед любым планом.",
            "command": "pc ai context",
        },
        {
            "id": "AI-0002",
            "priority": "P0",
            "status": "ready",
            "title": "Patch Draft Planner",
            "why": "Агент должен готовить безопасный response.json draft, а не просто советовать.",
            "command": "pc ai draft <цель>",
        },
        {
            "id": "AI-0003",
            "priority": "P1",
            "status": "planned",
            "title": "Verification Critic",
            "why": "После проверки агент должен читать отчёт и предлагать repair.",
            "command": "pc ai repair",
        },
        {
            "id": "AI-0004",
            "priority": "P1",
            "status": "planned",
            "title": "Plan/Act UX",
            "why": "Нужно разделить планирование и действие как у сильных coding agents.",
            "command": "pc ai plan <цель>",
        },
        {
            "id": "AI-0005",
            "priority": "P2",
            "status": "planned",
            "title": "Agent Workspace Shell",
            "why": "Красивый shell имеет смысл после рабочего агентского ядра.",
            "command": "pc ai cycle <цель>",
        },
    ]
    save_backlog(items)
    return items


def find_latest_verification_report() -> str:
    reports_root = ROOT_PATH / "Projects" / "Reports"
    if not reports_root.exists():
        return ""

    candidates: list[Path] = []
    for folder_name in ("strict_project_stability", "auto_verification"):
        folder = reports_root / folder_name
        if folder.exists():
            candidates.extend(folder.glob("*.json"))
            candidates.extend(folder.glob("*.md"))

    candidates.extend(reports_root.glob("*auto_stability_test*.md"))
    candidates = [path for path in candidates if path.exists()]
    if not candidates:
        return ""

    latest = max(candidates, key=lambda item: item.stat().st_mtime)
    return str(latest)


def remember_draft(path: str, goal: str) -> dict[str, Any]:
    state = set_phase("wait_for_user_apply", goal, latest_draft=path)
    append_history({
        "type": "draft_patch",
        "goal": goal,
        "draft_path": path,
        "phase": "wait_for_user_apply",
    })
    return state


def remember_verification(path: str, ok: bool | None = None) -> dict[str, Any]:
    state = load_state()
    state["latest_verification_report"] = str(path or "")
    state["phase"] = "done" if ok else "critique"
    save_state(state)
    append_history({
        "type": "verification_report",
        "ok": ok,
        "path": path,
        "phase": state["phase"],
    })
    return state


def status() -> dict[str, Any]:
    state = load_state()
    backlog = seed_default_backlog(force=False)
    latest_report = find_latest_verification_report()
    if latest_report and state.get("latest_verification_report") != latest_report:
        state["latest_verification_report"] = latest_report
        save_state(state)

    return {
        "ok": True,
        "mode": "ai_agent_memory_status",
        "generated_at": _now(),
        "memory_dir": str(MEMORY_DIR),
        "state_path": str(STATE_PATH),
        "project_context_path": str(PROJECT_CONTEXT_PATH),
        "task_history_path": str(TASK_HISTORY_PATH),
        "backlog_path": str(BACKLOG_PATH),
        "phase": state.get("phase"),
        "active_goal": state.get("active_goal"),
        "latest_draft": state.get("latest_draft"),
        "latest_verification_report": state.get("latest_verification_report") or latest_report,
        "backlog_items": len(backlog),
    }


def report() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "ai_agent_memory_report",
        "generated_at": _now(),
        "status": status(),
        "state": load_state(),
        "backlog": seed_default_backlog(force=False),
        "history": _read_json(TASK_HISTORY_PATH, [])[-20:],
    }


def dispatch(command: str) -> dict[str, Any]:
    text = str(command or "").strip().lower().replace("ё", "е")
    if text in {"pc ai memory", "pc ai memory status", "агент память", "память агента"}:
        return status()
    if text in {"pc ai memory report", "агент память отчет", "агент память отчёт"}:
        return report()
    if text in {"pc ai backlog", "агент backlog", "агент задачи"}:
        return {
            "ok": True,
            "mode": "ai_agent_memory_backlog",
            "generated_at": _now(),
            "backlog_path": str(BACKLOG_PATH),
            "items": seed_default_backlog(force=False),
        }
    return {
        "ok": False,
        "mode": "ai_agent_memory_unknown_command",
        "generated_at": _now(),
        "command": command,
        "hint": "Используй: pc ai memory, pc ai backlog",
    }


def is_ai_agent_memory_command(command: str) -> bool:
    text = str(command or "").strip().lower().replace("ё", "е")
    return text.startswith("pc ai memory") or text in {"агент память", "память агента", "агент backlog", "агент задачи"}
