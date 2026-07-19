
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import time

from modules.computer_use_schema_ru import compact_state, latest_run_id, load_run, make_action, new_run_state, now_iso, safe_json_load, save_run
from modules.computer_use_safety_ru import redact_text, safety_check_action, safety_check_goal
from modules.computer_use_trace_ru import build_replay_summary, save_step_artifact, write_event, write_run_report

LOOP_VERSION = "v6.47d"


def start_run(goal: str, max_steps: int = 8) -> Dict[str, Any]:
    clean_goal = redact_text((goal or "").strip())
    safety = safety_check_goal(clean_goal)
    if not safety["ok"]:
        return {"ok": False, "mode": "computer_use_run_blocked", "blocked": True, "goal": clean_goal, "reason": safety["reason"], "problem_types": safety["problem_types"]}
    state = new_run_state(clean_goal, max_steps)
    save_run(state)
    write_event(state["run_id"], "computer_run_started", {"goal": clean_goal, "max_steps": max_steps})
    return {"ok": True, "mode": "computer_use_run_started", "run_id": state["run_id"], "state": state}


def _core_observe() -> Dict[str, Any]:
    try:
        from modules.computer_use_core_ru import observe_screen
        result = observe_screen()
        return result if isinstance(result, dict) else {"ok": False, "error": "observe returned non-dict"}
    except Exception as exc:
        return {"ok": False, "mode": "computer_use_observe_fallback", "error": str(exc), "limitations": [str(exc)]}


def _core_map() -> Dict[str, Any]:
    try:
        from modules.computer_use_core_ru import build_ui_map
        result = build_ui_map()
        return result if isinstance(result, dict) else {"ok": False, "error": "map returned non-dict"}
    except Exception as exc:
        return {"ok": False, "mode": "computer_use_map_fallback", "error": str(exc), "elements": [], "limitations": [str(exc)]}


def observe_for_run(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_observation", "error": "no run"}
    state = load_run(rid)
    step = int(state.get("step") or 0) + 1
    state["step"] = step
    state["phase"] = "observing"
    save_run(state)
    observed = _core_observe()
    observation = {"ok": True, "mode": "computer_use_observation", "run_id": rid, "step": step, "created_at": now_iso(), "backend": observed}
    path = save_step_artifact(rid, step, "observation", observation)
    state["latest_observation_path"] = path
    state["phase"] = "mapping_ui"
    save_run(state)
    write_event(rid, "screen_observed", {"step": step, "observation_path": path, "backend_ok": observed.get("ok")})
    return observation | {"observation_path": path}


def build_ui_map_for_run(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_ui_map", "error": "no run"}
    state = load_run(rid)
    step = int(state.get("step") or 1)
    mapped = _core_map()
    ui_map = {"ok": True, "mode": "computer_use_ui_map", "run_id": rid, "step": step, "created_at": now_iso(), "backend": mapped, "elements": mapped.get("elements", []) if isinstance(mapped.get("elements", []), list) else []}
    path = save_step_artifact(rid, step, "ui_map", ui_map)
    state["latest_ui_map_path"] = path
    state["phase"] = "thinking"
    save_run(state)
    write_event(rid, "ui_map_built", {"step": step, "ui_map_path": path, "element_count": len(ui_map["elements"])})
    return ui_map | {"ui_map_path": path, "element_count": len(ui_map["elements"])}


def propose_next_action(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_decision", "error": "no run"}
    state = load_run(rid)
    step = int(state.get("step") or 1)
    goal = (state.get("goal") or "").lower()

    if step >= int(state.get("max_steps") or 8):
        action = make_action(rid, step, "ask_user", "Достигнут лимит шагов. Нужна новая инструкция.", "medium", False, True)
    elif any(word in goal for word in ["готово", "done", "finish", "заверши"]):
        action = make_action(rid, step, "done", "Цель похожа на завершение.", "low", True, False)
    elif any(word in goal for word in ["клик", "click", "нажми", "введи", "type", "hotkey", "scroll", "прокрути"]):
        action = make_action(rid, step, "ask_user", "Запрошено интерактивное действие. v6.47d может выполнить grounded non-file click/type автоматически.", "medium", False, True, {"element_description": "уточнить элемент"})
    else:
        action = make_action(rid, step, "ask_user", "Экран и UI map собраны. Нужен выбор конкретного следующего безопасного действия.", "medium", False, True)

    safety = safety_check_action(action)
    action["risk"] = safety.get("risk", action["risk"])
    action["requires_confirmation"] = safety.get("requires_confirmation", True)
    action["allowed_to_execute"] = bool(safety.get("allowed_to_execute")) and not action["requires_confirmation"]
    action["safety_notes"] = safety.get("notes", []) + [safety.get("reason", "")]
    decision = {"ok": not safety.get("blocked", False), "mode": "computer_use_decision", "run_id": rid, "step": step, "action": action, "safety": safety, "requires_confirmation": action["requires_confirmation"], "allowed_to_execute": action["allowed_to_execute"]}
    path = save_step_artifact(rid, step, "decision", decision)
    state["latest_decision_path"] = path
    state["pending_action_id"] = action["action_id"]
    state["pending_confirmation"] = action["requires_confirmation"]
    state["phase"] = "waiting_confirmation" if action["requires_confirmation"] else "ready_to_execute"
    state["next_safe_action"] = f"pc computer approve {action['action_id']}" if action["requires_confirmation"] else "pc computer step"
    save_run(state)
    write_event(rid, "decision_proposed", {"step": step, "decision_path": path, "action": action, "safety": safety})
    return decision | {"decision_path": path}


def run_goal_loop(goal: str, max_steps: int = 8, require_confirmation: bool = True) -> Dict[str, Any]:
    started = start_run(goal, max_steps)
    if not started.get("ok"):
        return started
    rid = started["run_id"]
    observation = observe_for_run(rid)
    ui_map = build_ui_map_for_run(rid)
    decision = propose_next_action(rid)
    report_result = write_run_report(rid)
    state = load_run(rid)
    return {"ok": True, "mode": "computer_use_loop_started", "run_id": rid, "state": compact_state(state), "observation": observation, "ui_map": ui_map, "decision": decision, "report": report_result.get("report"), "next_safe_action": state.get("next_safe_action")}


def approve_action(action_id: str, run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_approve", "error": "no run"}
    state = load_run(rid)
    decision = safe_json_load(Path(state.get("latest_decision_path", "")), {})
    action = decision.get("action") or {}
    if action.get("action_id") != action_id:
        return {"ok": False, "mode": "computer_use_approve", "error": "action id mismatch", "expected": action.get("action_id"), "received": action_id}
    safety = safety_check_action(action)
    if safety.get("blocked"):
        state["phase"] = "blocked"
        state["status"] = "blocked"
        save_run(state)
        return {"ok": False, "mode": "computer_use_approve", "blocked": True, "safety": safety}
    action["confirmed"] = True
    action["confirmed_at"] = now_iso()
    decision["action"] = action
    decision["confirmed"] = True
    Path(state["latest_decision_path"]).write_text(__import__("json").dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    state["pending_confirmation"] = False
    state["phase"] = "approved"
    state["next_safe_action"] = "pc computer step"
    save_run(state)
    write_event(rid, "action_confirmed", {"action_id": action_id})
    return {"ok": True, "mode": "computer_use_approve", "run_id": rid, "action_id": action_id, "confirmed": True}


def execute_one_step(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_step", "error": "no run"}
    state = load_run(rid)
    decision = safe_json_load(Path(state.get("latest_decision_path", "")), {})
    action = decision.get("action") or {}
    if not action:
        observe_for_run(rid)
        build_ui_map_for_run(rid)
        return propose_next_action(rid)
    if action.get("requires_confirmation") and not action.get("confirmed"):
        state["phase"] = "waiting_confirmation"
        state["pending_confirmation"] = True
        save_run(state)
        return {"ok": False, "mode": "computer_use_step_waiting_confirmation", "pending_action_id": action.get("action_id"), "next_safe_action": f"pc computer approve {action.get('action_id')}"}

    kind = action.get("kind")
    if kind in {"click", "double_click", "type", "hotkey", "scroll", "move"}:
        from modules.computer_use_auto_action_ru import execute_gui_action
        auto_result = execute_gui_action(action, simulate=bool(action.get("simulate")))
        ok = bool(auto_result.get("ok"))
        result = {"ok": ok, "mode": "computer_use_action_result", "run_id": rid, "step": state.get("step"), "action_id": action.get("action_id"), "action_kind": kind, "executed": bool(auto_result.get("executed")), "message": auto_result.get("message") or auto_result.get("reason") or "auto GUI action processed", "auto_result": auto_result, "created_at": now_iso()}
    else:
        ok = kind in {"observe", "screenshot", "wait", "done"}
        if kind == "wait":
            time.sleep(0.2)
        if kind == "done":
            state["phase"] = "done"
            state["status"] = "done"
        result = {"ok": ok, "mode": "computer_use_action_result", "run_id": rid, "step": state.get("step"), "action_id": action.get("action_id"), "action_kind": kind, "executed": ok, "message": "v6.47d limited non-GUI primitive execution", "created_at": now_iso()}
    result_path = save_step_artifact(rid, int(state.get("step") or 1), "result", result)
    state["latest_result_path"] = result_path
    state["pending_action_id"] = ""
    state["pending_confirmation"] = False
    if state.get("status") != "done":
        observe_for_run(rid)
        build_ui_map_for_run(rid)
        propose_next_action(rid)
    save_run(load_run(rid) | {"latest_result_path": result_path})
    write_event(rid, "action_executed", result)
    write_run_report(rid)
    return result | {"result_path": result_path, "state": compact_state(load_run(rid))}


def stop_run(run_id: str = "") -> Dict[str, Any]:
    rid = run_id or latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_stop", "error": "no run"}
    state = load_run(rid)
    state["phase"] = "stopped"
    state["status"] = "stopped"
    state["stopped"] = True
    state["next_safe_action"] = "pc computer report"
    save_run(state)
    write_event(rid, "run_stopped", {})
    write_run_report(rid)
    return {"ok": True, "mode": "computer_use_stop", "run_id": rid, "state": compact_state(state)}


def latest_run() -> Dict[str, Any]:
    rid = latest_run_id()
    if not rid:
        return {"ok": False, "mode": "computer_use_latest", "error": "no runs"}
    return {"ok": True, "mode": "computer_use_latest", "state": compact_state(load_run(rid)), "replay": build_replay_summary(rid)}


def list_runs() -> Dict[str, Any]:
    from modules.computer_use_schema_ru import RUNS_DIR
    rows = [compact_state(load_run(path.parent.name)) for path in sorted(RUNS_DIR.glob("run_*/run.json"))[-20:]]
    return {"ok": True, "mode": "computer_use_runs", "runs": rows, "latest_run_id": latest_run_id()}


def status() -> Dict[str, Any]:
    return {"ok": True, "mode": "computer_use_loop_status", "version": LOOP_VERSION, "latest_run_id": latest_run_id(), "state": compact_state(load_run()) if latest_run_id() else {}}


def report() -> Dict[str, Any]:
    rid = latest_run_id()
    if not rid:
        return {"ok": True, "mode": "computer_use_loop_report", "version": LOOP_VERSION, "latest_run_id": ""}
    rep = write_run_report(rid)
    return {"ok": True, "mode": "computer_use_loop_report", "version": LOOP_VERSION, "latest_run_id": rid, "report": rep.get("report"), "state": compact_state(load_run(rid))}


def is_computer_use_loop_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = ["pc computer loop", "pc computer step", "pc computer approve", "pc computer resume", "pc computer runs", "pc computer latest", "pc computer replay", "цикл computer use", "шаг computer use", "одобри действие", "последний computer use"]
    return any(value == p or value.startswith(p + " ") for p in prefixes)


def dispatch(command: str) -> Dict[str, Any]:
    raw = (command or "").strip()
    value = raw.lower()
    if value.startswith("pc computer loop "):
        return run_goal_loop(raw[len("pc computer loop "):].strip())
    if value.startswith("цикл computer use "):
        return run_goal_loop(raw[len("цикл computer use "):].strip())
    if value in {"pc computer step", "шаг computer use"}:
        return execute_one_step()
    if value.startswith("pc computer approve "):
        return approve_action(raw[len("pc computer approve "):].strip())
    if value.startswith("одобри действие "):
        return approve_action(raw[len("одобри действие "):].strip())
    if value in {"pc computer resume"}:
        return execute_one_step()
    if value in {"pc computer runs"}:
        return list_runs()
    if value in {"pc computer latest", "последний computer use"}:
        return latest_run()
    if value.startswith("pc computer replay"):
        parts = raw.split()
        return build_replay_summary(parts[-1] if len(parts) >= 4 else "")
    if value in {"pc computer report", "отчёт computer use"}:
        return report()
    return {"ok": False, "mode": "computer_use_loop_unknown_command", "command": command}
