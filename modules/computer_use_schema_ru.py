
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json
import uuid

SCHEMA_VERSION = "v6.47d"
ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
RUNS_DIR = COMPUTER_USE_DIR / "runs"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_dirs() -> None:
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def make_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()


def safe_json_load(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def safe_json_dump(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def run_dir(run_id: str) -> Path:
    ensure_dirs()
    return RUNS_DIR / run_id


def steps_dir(run_id: str) -> Path:
    return run_dir(run_id) / "steps"


def screenshots_dir(run_id: str) -> Path:
    return run_dir(run_id) / "screenshots"


def reports_dir(run_id: str) -> Path:
    return run_dir(run_id) / "reports"


def events_path(run_id: str) -> Path:
    return run_dir(run_id) / "events.jsonl"


def run_state_path(run_id: str) -> Path:
    return run_dir(run_id) / "run.json"


def latest_run_id() -> str:
    ensure_dirs()
    runs = sorted(path.parent.name for path in RUNS_DIR.glob("run_*/run.json"))
    return runs[-1] if runs else ""


def load_run(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    return safe_json_load(run_state_path(rid), {}) if rid else {}


def save_run(state: Dict[str, Any]) -> str:
    state["updated_at"] = now_iso()
    return safe_json_dump(run_state_path(state["run_id"]), state)


def default_plan(goal: str) -> List[str]:
    return [
        f"Понять цель: {(goal or '').strip()}",
        "Наблюдать экран.",
        "Построить UI map.",
        "Предложить одно следующее действие.",
        "Проверить безопасность.",
        "Остановиться на подтверждении, если действие рискованное.",
        "После выполнения снова наблюдать экран.",
        "Записать replay/report.",
    ]


def make_action(run_id: str, step: int, kind: str, reason: str, risk: str = "low", allowed_to_execute: bool = False, requires_confirmation: bool = True, target: Dict[str, Any] | None = None, text: str = "") -> Dict[str, Any]:
    return {
        "action_id": f"act_{step:03d}_{uuid.uuid4().hex[:6]}",
        "run_id": run_id,
        "step": step,
        "kind": (kind or "").strip().lower().replace("-", "_"),
        "target": target or {"element_id": "", "element_description": "", "window_title": "", "x": None, "y": None, "x_norm": None, "y_norm": None},
        "text": text,
        "reason": reason,
        "risk": risk,
        "requires_confirmation": requires_confirmation,
        "allowed_to_execute": allowed_to_execute,
        "created_at": now_iso(),
        "safety_notes": [],
    }


def compact_state(state: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "run_id", "goal", "phase", "status", "step", "max_steps", "pending_action_id",
        "pending_confirmation", "latest_observation_path", "latest_ui_map_path",
        "latest_decision_path", "latest_result_path", "latest_report_path", "next_safe_action",
    ]
    return {key: state.get(key, "") for key in keys}


def new_run_state(goal: str, max_steps: int = 8) -> Dict[str, Any]:
    run_id = make_id("run")
    return {
        "run_id": run_id,
        "goal": goal,
        "phase": "created",
        "status": "running",
        "step": 0,
        "max_steps": max(1, int(max_steps or 8)),
        "consecutive_failures": 0,
        "paused": False,
        "stopped": False,
        "pending_action_id": "",
        "pending_confirmation": False,
        "latest_observation_path": "",
        "latest_ui_map_path": "",
        "latest_decision_path": "",
        "latest_result_path": "",
        "latest_report_path": "",
        "next_safe_action": "pc computer step",
        "plan": default_plan(goal),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def status() -> Dict[str, Any]:
    ensure_dirs()
    return {"ok": True, "mode": "computer_use_schema_status", "version": SCHEMA_VERSION, "runs_dir": str(RUNS_DIR)}


def report() -> Dict[str, Any]:
    return {"ok": True, "mode": "computer_use_schema_report", "latest_run_id": latest_run_id(), "latest_run": compact_state(load_run()) if latest_run_id() else {}}


def is_computer_use_schema_command(command: str) -> bool:
    return (command or "").strip().lower() in {"pc computer schema", "computer schema"}


def dispatch(command: str) -> Dict[str, Any]:
    return report() if is_computer_use_schema_command(command) else {"ok": False, "mode": "computer_use_schema_unknown_command", "command": command}
