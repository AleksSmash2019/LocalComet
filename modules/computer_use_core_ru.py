
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import json
import uuid

ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
TRACE_DIR = COMPUTER_USE_DIR / "traces"
REPORT_DIR = COMPUTER_USE_DIR / "reports"
STATE_PATH = COMPUTER_USE_DIR / "computer_use_state.json"
QUEUE_PATH = COMPUTER_USE_DIR / "action_queue.json"
UI_MAP_PATH = COMPUTER_USE_DIR / "latest_ui_map.json"

COMPUTER_USE_VERSION = "v6.58"
COMPUTER_USE_NAME = "LocalComet Computer Use Core RU Agent Automation Test Center"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    for path in [COMPUTER_USE_DIR, TRACE_DIR, REPORT_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _trace(event: Dict[str, Any]) -> str:
    _ensure_dirs()
    path = TRACE_DIR / f"computer_use_trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    _write_json(path, {"created_at": _now(), "version": COMPUTER_USE_VERSION, **event})
    return str(path)


def observe_screen() -> Dict[str, Any]:
    _ensure_dirs()
    result = {"ok": True, "mode": "computer_use_observe", "created_at": _now(), "active_window": "", "screen_size": {}, "screenshot_path": "", "screenshot_hash": "", "limitations": []}
    try:
        from modules.pc_desktop_primitives import dispatch as desktop_dispatch
        probe = desktop_dispatch("pc desktop screenshot")
        if isinstance(probe, dict):
            result["desktop_probe"] = probe
            result["screenshot_path"] = str(probe.get("path") or probe.get("screenshot") or probe.get("screenshot_path") or "")
            result["active_window"] = str(probe.get("active_window") or probe.get("window") or "")
            if isinstance(probe.get("screen_size"), dict):
                result["screen_size"] = probe["screen_size"]
    except Exception as exc:
        result["limitations"].append(f"desktop observer unavailable: {exc}")
    if not result["screenshot_path"]:
        result["limitations"].append("No screenshot path returned; fallback observation only.")
    result["trace_path"] = _trace({"event": "observe_screen", "result": result})
    state = _read_json(STATE_PATH, {})
    state.update({"latest_observation": result, "latest_trace_path": result["trace_path"], "updated_at": _now()})
    _write_json(STATE_PATH, state)
    return result


def build_ui_map() -> Dict[str, Any]:
    _ensure_dirs()
    elements: List[Dict[str, Any]] = []
    limitations: List[str] = []
    source = "fallback"
    try:
        from modules.pc_ui_parser_adapter import dispatch as ui_dispatch
        parsed = ui_dispatch("pc ui parse")
        if isinstance(parsed, dict):
            source = "pc_ui_parser_adapter"
            raw = parsed.get("elements") or parsed.get("ui_elements") or []
            if isinstance(raw, list):
                elements = [item for item in raw if isinstance(item, dict)]
    except Exception as exc:
        limitations.append(f"ui parser unavailable: {exc}")
    payload = {"ok": True, "mode": "computer_use_ui_map", "created_at": _now(), "source": source, "elements": elements[:200], "limitations": limitations}
    path = _write_json(UI_MAP_PATH, payload)
    payload["ui_map_path"] = path
    payload["trace_path"] = _trace({"event": "build_ui_map", "ui_map_path": path, "element_count": len(elements)})
    return payload


def safety_check_goal(goal: str) -> Dict[str, Any]:
    from modules.computer_use_safety_ru import safety_check_goal as check
    return check(goal)


def safety_check_action(action: Dict[str, Any]) -> Dict[str, Any]:
    from modules.computer_use_safety_ru import safety_check_action as check
    return check(action)


def plan_action(goal: str) -> Dict[str, Any]:
    safety = safety_check_goal(goal)
    if not safety["ok"]:
        return {"ok": False, "mode": "computer_use_plan", "blocked": True, "goal": goal, "risk": "blocked", "reason": safety["reason"], "problem_types": safety["problem_types"]}
    return {"ok": True, "mode": "computer_use_plan", "goal": goal, "risk": "low", "steps": ["observe", "build_ui_map", "propose_one_action", "safety_check", "confirmation", "limited_execute", "observe_result", "report"], "requires_confirmation": True, "allowed_to_execute": False}


def dry_run_action(goal: str) -> Dict[str, Any]:
    plan = plan_action(goal)
    if not plan["ok"]:
        plan["mode"] = "computer_use_dry_run"
        return plan
    observation = observe_screen()
    ui_map = build_ui_map()
    return {"ok": True, "mode": "computer_use_dry_run", "goal": goal, "risk": plan["risk"], "plan": plan, "observation": observation, "ui_map_path": ui_map.get("ui_map_path"), "requires_confirmation": True, "allowed_to_execute": False, "trace_path": _trace({"event": "dry_run_action", "goal": goal})}


def queue_action(goal: str) -> Dict[str, Any]:
    plan = plan_action(goal)
    if not plan["ok"]:
        return {"ok": False, "mode": "computer_use_queue", "blocked": True, "plan": plan}
    queue = _read_json(QUEUE_PATH, [])
    action_id = f"cu_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    item = {"action_id": action_id, "goal": goal, "plan": plan, "status": "queued", "confirmed": False, "executed": False, "created_at": _now()}
    queue.append(item)
    _write_json(QUEUE_PATH, queue)
    return {"ok": True, "mode": "computer_use_queue", "action_id": action_id, "queue_path": str(QUEUE_PATH), "trace_path": _trace({"event": "queue_action", "action_id": action_id})}


def confirm_action(action_id: str) -> Dict[str, Any]:
    queue = _read_json(QUEUE_PATH, [])
    for item in queue:
        if item.get("action_id") == action_id:
            item["confirmed"] = True
            item["confirmed_at"] = _now()
            _write_json(QUEUE_PATH, queue)
            return {"ok": True, "mode": "computer_use_confirm", "action_id": action_id, "confirmed": True, "trace_path": _trace({"event": "confirm_action", "action_id": action_id})}
    return {"ok": False, "mode": "computer_use_confirm", "error": "action not found", "action_id": action_id}


def execute_confirmed_action(action_id: str) -> Dict[str, Any]:
    queue = _read_json(QUEUE_PATH, [])
    for item in queue:
        if item.get("action_id") == action_id:
            if not item.get("confirmed"):
                return {"ok": False, "mode": "computer_use_run", "error": "action not confirmed", "action_id": action_id}
            item["executed"] = True
            item["executed_at"] = _now()
            item["execution_policy"] = "v6.47d auto GUI policy: click/type allowed when grounded and non-file"
            _write_json(QUEUE_PATH, queue)
            observation = observe_screen()
            ui_map = build_ui_map()
            return {"ok": True, "mode": "computer_use_run", "action_id": action_id, "executed": True, "policy": item["execution_policy"], "observation": observation, "ui_map_path": ui_map.get("ui_map_path"), "trace_path": _trace({"event": "execute_confirmed_action", "action_id": action_id})}
    return {"ok": False, "mode": "computer_use_run", "error": "action not found", "action_id": action_id}


def stop_action() -> Dict[str, Any]:
    state = _read_json(STATE_PATH, {})
    state.update({"stopped": True, "updated_at": _now()})
    _write_json(STATE_PATH, state)
    return {"ok": True, "mode": "computer_use_stop", "trace_path": _trace({"event": "stop_action"})}


def clear_queue() -> Dict[str, Any]:
    _write_json(QUEUE_PATH, [])
    return {"ok": True, "mode": "computer_use_clear", "queue_path": str(QUEUE_PATH), "trace_path": _trace({"event": "clear_queue"})}


def latest_trace() -> Dict[str, Any]:
    try:
        from modules.computer_use_trace_ru import latest_trace as latest_loop_trace
        loop_trace = latest_loop_trace()
        if loop_trace.get("ok"):
            return loop_trace
    except Exception:
        pass
    traces = sorted(TRACE_DIR.glob("computer_use_trace_*.json"))
    if not traces:
        return {"ok": False, "mode": "computer_use_latest_trace", "error": "no trace yet"}
    return {"ok": True, "mode": "computer_use_latest_trace", "trace_path": str(traces[-1]), "trace": _read_json(traces[-1], {})}


def write_trace(event: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "mode": "computer_use_write_trace", "trace_path": _trace(event)}


def write_report() -> Dict[str, Any]:
    _ensure_dirs()
    path = REPORT_DIR / f"computer_use_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    queue = _read_json(QUEUE_PATH, [])
    state = _read_json(STATE_PATH, {})
    lines = ["# Computer Use Core Report", "", f"- generated_at: {_now()}", f"- version: {COMPUTER_USE_VERSION}", f"- queue_count: {len(queue)}", f"- latest_trace_path: {state.get('latest_trace_path', '')}", "", "## Queue", ""]
    for item in queue[-20:]:
        lines.append(f"- {item.get('action_id')} confirmed={item.get('confirmed')} executed={item.get('executed')} goal={item.get('goal')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "mode": "computer_use_report", "report": str(path), "queue": queue, "state": state}


def status() -> Dict[str, Any]:
    _ensure_dirs()
    queue = _read_json(QUEUE_PATH, [])
    return {"ok": True, "mode": "computer_use_core_status", "version": COMPUTER_USE_VERSION, "name": COMPUTER_USE_NAME, "computer_use_dir": str(COMPUTER_USE_DIR), "queued_actions": len(queue)}


def report() -> Dict[str, Any]:
    try:
        from modules.computer_use_loop_ru import report as loop_report
        loop = loop_report()
        if loop.get("latest_run_id"):
            return loop
    except Exception:
        pass
    return write_report()


def is_computer_use_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = ["pc computer", "computer use", "pc computer contracts", "pc dev contracts", "контракты computer use", "pc computer auto", "pc computer simulate", "pc computer visual", "pc computer screen diff", "pc computer find", "pc computer ground", "pc computer focus", "pc computer guarded type", "pc computer click element", "pc computer type into", "кликни элемент", "введи в элемент", "безопасный ввод в", "авто клик", "авто ввод", "компьютер статус", "наблюдай экран", "карта экрана", "спланируй действие", "сухой запуск", "поставь действие в очередь", "подтверди действие", "выполни подтверждённое действие", "останови действие", "очисти очередь", "отчёт computer use", "цикл computer use", "шаг computer use", "одобри действие", "последний computer use"]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


# BEGIN LOCALCOMET V6.48I COMPUTER USE MULTISTEP CONTRACTS ROUTE DISPATCH WRAPPER

def _localcomet_contracts_core_dispatch_ru_v648i(command):
    _localcomet_command_text_ru_v648i = str(command or "").strip()
    _localcomet_command_lower_ru_v648i = _localcomet_command_text_ru_v648i.lower()
    _localcomet_contract_aliases_ru_v648i = {
        "pc computer contracts",
        "pc computer contract",
        "computer use contracts",
        "контракты computer use",
        "проверь computer use contracts",
    }
    if _localcomet_command_lower_ru_v648i in _localcomet_contract_aliases_ru_v648i:
        from modules.computer_use_contract_tests_ru import run_all_contracts as _localcomet_run_contracts_ru_v648i
        _localcomet_contracts_result_ru_v648i = _localcomet_run_contracts_ru_v648i(write_report=True)
        if not isinstance(_localcomet_contracts_result_ru_v648i, dict):
            _localcomet_contracts_result_ru_v648i = {
                "ok": False,
                "mode": "computer_use_contract_tests",
                "summary": {"passed": 0, "total": 1, "failed": 1},
                "reason": "contract runner returned non-dict result",
            }
        _localcomet_contracts_result_ru_v648i.setdefault("ok", False)
        _localcomet_contracts_result_ru_v648i.setdefault("mode", "computer_use_contract_tests")
        _localcomet_contracts_result_ru_v648i.setdefault("summary", {"passed": 0, "total": 0, "failed": 0})
        _localcomet_contracts_result_ru_v648i["handled"] = True
        _localcomet_contracts_result_ru_v648i["version"] = "v6.48i"
        return _localcomet_contracts_result_ru_v648i
    return None


def _localcomet_multistep_core_dispatch_ru_v648i(command):
    from modules.computer_use_multistep_loop_ru import handle_dispatch_command as _localcomet_multistep_dispatch_ru_v648i
    _localcomet_result_ru_v648i = _localcomet_multistep_dispatch_ru_v648i(command)
    if isinstance(_localcomet_result_ru_v648i, dict) and _localcomet_result_ru_v648i.get("handled"):
        return _localcomet_result_ru_v648i
    return None


_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648I = globals().get("dispatch")
if not callable(_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648I):
    for _localcomet_dispatch_name_ru_v648i in (
        "_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648E",
        "_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648D",
        "_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648C",
        "_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648B",
        "_dispatch_before_multistep_loop_ru_v648e",
        "_dispatch_before_multistep_loop_ru_v648d",
        "_dispatch_before_multistep_loop_ru_v648c",
        "_dispatch_before_multistep_loop_ru_v648b",
        "_dispatch_before_multistep_loop_ru_v648",
    ):
        _localcomet_candidate_ru_v648i = globals().get(_localcomet_dispatch_name_ru_v648i)
        if callable(_localcomet_candidate_ru_v648i):
            _LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648I = _localcomet_candidate_ru_v648i
            break


def dispatch(command):
    try:
        _localcomet_contracts_result_ru_v648i = _localcomet_contracts_core_dispatch_ru_v648i(command)
        if isinstance(_localcomet_contracts_result_ru_v648i, dict) and _localcomet_contracts_result_ru_v648i.get("handled"):
            return _localcomet_contracts_result_ru_v648i
    except Exception as _localcomet_contracts_exc_ru_v648i:
        return {
            "ok": False,
            "handled": True,
            "mode": "computer_use_contract_tests",
            "version": "v6.48i",
            "summary": {"passed": 0, "total": 1, "failed": 1},
            "reason": "contract route failed: " + str(_localcomet_contracts_exc_ru_v648i),
        }
    try:
        _localcomet_result_ru_v648i = _localcomet_multistep_core_dispatch_ru_v648i(command)
        if isinstance(_localcomet_result_ru_v648i, dict) and _localcomet_result_ru_v648i.get("handled"):
            return _localcomet_result_ru_v648i
    except Exception as _localcomet_exc_ru_v648i:
        _localcomet_multistep_error_ru_v648i = str(_localcomet_exc_ru_v648i)
    if callable(_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648I):
        return _LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648I(command)
    return {
        "ok": False,
        "handled": False,
        "mode": "computer_use_core_dispatch_contracts_route_repair",
        "version": "v6.48i",
        "reason": "original dispatch unavailable",
    }


COMPUTER_USE_MULTISTEP_LOOP_RU_V648I = "v6.48i multistep loop contracts route dispatch wrapper"

# END LOCALCOMET V6.48I COMPUTER USE MULTISTEP CONTRACTS ROUTE DISPATCH WRAPPER

# BEGIN LOCALCOMET V6.50B BROWSER HARNESS DISPATCH WRAPPER RU

def _localcomet_browser_harness_core_dispatch_ru_v650c(command):
    from modules.browser_harness_ru import handle_dispatch_command as _localcomet_browser_harness_dispatch_ru_v650c
    _localcomet_browser_result_ru_v650c = _localcomet_browser_harness_dispatch_ru_v650c(command)
    if isinstance(_localcomet_browser_result_ru_v650c, dict) and _localcomet_browser_result_ru_v650c.get("handled"):
        return _localcomet_browser_result_ru_v650c
    return None


_LOCALCOMET_CORE_DISPATCH_BEFORE_BROWSER_HARNESS_RU_V650C = dispatch


def dispatch(command):
    try:
        _localcomet_browser_result_ru_v650c = _localcomet_browser_harness_core_dispatch_ru_v650c(command)
        if isinstance(_localcomet_browser_result_ru_v650c, dict) and _localcomet_browser_result_ru_v650c.get("handled"):
            return _localcomet_browser_result_ru_v650c
    except Exception as _localcomet_browser_exc_ru_v650c:
        return {
            "ok": False,
            "handled": True,
            "mode": "browser_harness_core_dispatch",
            "version": "v6.50c",
            "reason": "Browser Harness route failed: " + str(_localcomet_browser_exc_ru_v650c),
        }
    return _LOCALCOMET_CORE_DISPATCH_BEFORE_BROWSER_HARNESS_RU_V650C(command)


COMPUTER_USE_BROWSER_HARNESS_RU_V650C = "v6.50c browser harness dispatch wrapper"

# END LOCALCOMET V6.50B BROWSER HARNESS DISPATCH WRAPPER RU

# BEGIN LOCALCOMET V6.50H COMPUTER USE AGENT MISSION DISPATCH WRAPPER RU

def _localcomet_agent_mission_core_dispatch_ru_v650h(command):
    from modules.computer_use_agent_mission_ru import handle_dispatch_command as _localcomet_agent_mission_dispatch_ru_v650h
    _localcomet_agent_result_ru_v650h = _localcomet_agent_mission_dispatch_ru_v650h(command)
    if isinstance(_localcomet_agent_result_ru_v650h, dict) and _localcomet_agent_result_ru_v650h.get("handled"):
        return _localcomet_agent_result_ru_v650h
    return None


_LOCALCOMET_CORE_DISPATCH_BEFORE_AGENT_MISSION_RU_V650H = globals().get("dispatch")
_LOCALCOMET_CORE_IS_BEFORE_AGENT_MISSION_RU_V650H = globals().get("is_computer_use_command")


def is_computer_use_command(command):
    try:
        from modules.computer_use_agent_mission_ru import is_agent_mission_command as _localcomet_is_agent_mission_command_ru_v650h
        if _localcomet_is_agent_mission_command_ru_v650h(command):
            return True
    except Exception:
        pass
    if callable(_LOCALCOMET_CORE_IS_BEFORE_AGENT_MISSION_RU_V650H):
        return bool(_LOCALCOMET_CORE_IS_BEFORE_AGENT_MISSION_RU_V650H(command))
    return False


def dispatch(command):
    try:
        _localcomet_agent_result_ru_v650h = _localcomet_agent_mission_core_dispatch_ru_v650h(command)
        if isinstance(_localcomet_agent_result_ru_v650h, dict) and _localcomet_agent_result_ru_v650h.get("handled"):
            return _localcomet_agent_result_ru_v650h
    except Exception as _localcomet_agent_exc_ru_v650h:
        return {
            "ok": False,
            "handled": True,
            "mode": "computer_use_agent_mission_core_dispatch",
            "version": "v6.50h",
            "reason": "Computer Use Agent Mission route failed: " + str(_localcomet_agent_exc_ru_v650h),
        }
    if callable(_LOCALCOMET_CORE_DISPATCH_BEFORE_AGENT_MISSION_RU_V650H):
        return _LOCALCOMET_CORE_DISPATCH_BEFORE_AGENT_MISSION_RU_V650H(command)
    return {
        "ok": False,
        "handled": False,
        "mode": "computer_use_agent_mission_core_dispatch",
        "version": "v6.50h",
        "reason": "previous computer use dispatch unavailable",
    }


COMPUTER_USE_AGENT_MISSION_RU_V650H = "v6.50h computer use agent mission dispatch wrapper"

# END LOCALCOMET V6.50H COMPUTER USE AGENT MISSION DISPATCH WRAPPER RU

# BEGIN LOCALCOMET V6.51 COMPUTER USE FULL CONTROL DISPATCH WRAPPER RU

def _localcomet_full_control_core_dispatch_ru_v651(command):
    from modules.computer_use_full_control_mission_ru import handle_dispatch_command as _localcomet_full_control_dispatch_ru_v651
    _localcomet_full_control_result_ru_v651 = _localcomet_full_control_dispatch_ru_v651(command)
    if isinstance(_localcomet_full_control_result_ru_v651, dict) and _localcomet_full_control_result_ru_v651.get("handled"):
        return _localcomet_full_control_result_ru_v651
    return None


_LOCALCOMET_CORE_DISPATCH_BEFORE_FULL_CONTROL_RU_V651 = globals().get("dispatch")
_LOCALCOMET_CORE_IS_BEFORE_FULL_CONTROL_RU_V651 = globals().get("is_computer_use_command")


def is_computer_use_command(command):
    try:
        from modules.computer_use_full_control_mission_ru import is_full_control_command as _localcomet_is_full_control_command_ru_v651
        if _localcomet_is_full_control_command_ru_v651(command):
            return True
    except Exception:
        pass
    if callable(_LOCALCOMET_CORE_IS_BEFORE_FULL_CONTROL_RU_V651):
        return bool(_LOCALCOMET_CORE_IS_BEFORE_FULL_CONTROL_RU_V651(command))
    return False


def dispatch(command):
    try:
        _localcomet_full_control_result_ru_v651 = _localcomet_full_control_core_dispatch_ru_v651(command)
        if isinstance(_localcomet_full_control_result_ru_v651, dict) and _localcomet_full_control_result_ru_v651.get("handled"):
            return _localcomet_full_control_result_ru_v651
    except Exception as _localcomet_full_control_exc_ru_v651:
        return {
            "ok": False,
            "handled": True,
            "mode": "computer_use_full_control_core_dispatch",
            "version": "v6.51",
            "reason": "Computer Use Full Control route failed: " + str(_localcomet_full_control_exc_ru_v651),
        }
    if callable(_LOCALCOMET_CORE_DISPATCH_BEFORE_FULL_CONTROL_RU_V651):
        return _LOCALCOMET_CORE_DISPATCH_BEFORE_FULL_CONTROL_RU_V651(command)
    return {
        "ok": False,
        "handled": False,
        "mode": "computer_use_core_dispatch_missing",
        "version": "v6.51",
        "reason": "previous computer_use_core_ru.dispatch was not callable",
    }


COMPUTER_USE_FULL_CONTROL_MISSION_RU_V651 = "v6.51 full control mission dispatch wrapper"

# END LOCALCOMET V6.51 COMPUTER USE FULL CONTROL DISPATCH WRAPPER RU

# BEGIN v6.54 Computer Use Observe/Vision core dispatch wrapper
try:
    _dispatch_before_observe_vision_ru_v654
except NameError:
    _dispatch_before_observe_vision_ru_v654 = dispatch

try:
    _is_computer_use_command_before_observe_vision_ru_v654
except NameError:
    _is_computer_use_command_before_observe_vision_ru_v654 = is_computer_use_command


def _is_observe_vision_command_ru_v654(command):
    lower = str(command or "").lower().replace("ё", "е").strip()
    if lower in {
        "pc computer vision",
        "pc computer vision status",
        "pc computer observe vision",
        "pc computer vision observe",
        "pc computer vision latest",
        "pc computer vision report",
        "статус зрения",
        "наблюдай экран",
        "осмотр экрана",
        "последний осмотр экрана",
        "отчет зрения",
        "возможности зрения",
    }:
        return True
    return lower.startswith((
        "pc computer vision observe ",
        "pc computer observe vision ",
        "наблюдай экран ",
        "осмотр экрана ",
    ))


def is_computer_use_command(command):
    try:
        if _is_observe_vision_command_ru_v654(command):
            return True
    except Exception:
        pass
    return _is_computer_use_command_before_observe_vision_ru_v654(command)


def dispatch(command, *args, **kwargs):
    try:
        from modules.computer_use_observe_vision_ru import handle_dispatch_command

        observed = handle_dispatch_command(command, *args, **kwargs)
        if isinstance(observed, dict) and observed.get("handled"):
            return observed
    except Exception as exc:
        if _is_observe_vision_command_ru_v654(command):
            return {
                "ok": False,
                "handled": True,
                "mode": "computer_use_observe_vision_error",
                "version": "v6.54",
                "error": str(exc),
            }
    return _dispatch_before_observe_vision_ru_v654(command, *args, **kwargs)
# END v6.54 Computer Use Observe/Vision core dispatch wrapper

# BEGIN v6.54b Computer Use Observe/Vision core dispatch wrapper
try:
    _dispatch_before_observe_vision_ru_v654b
except NameError:
    _dispatch_before_observe_vision_ru_v654b = dispatch

try:
    _is_computer_use_command_before_observe_vision_ru_v654b
except NameError:
    _is_computer_use_command_before_observe_vision_ru_v654b = is_computer_use_command


def _is_observe_vision_command_ru_v654b(command):
    lower = str(command or "").lower().replace("ё", "е").strip()
    if lower in {
        "pc computer vision",
        "pc computer vision status",
        "pc computer observe vision",
        "pc computer vision observe",
        "pc computer vision latest",
        "pc computer vision report",
        "статус зрения",
        "наблюдай экран",
        "осмотр экрана",
        "последний осмотр экрана",
        "отчет зрения",
        "возможности зрения",
    }:
        return True
    return lower.startswith((
        "pc computer vision observe ",
        "pc computer observe vision ",
        "наблюдай экран ",
        "осмотр экрана ",
    ))


def is_computer_use_command(command):
    try:
        if _is_observe_vision_command_ru_v654b(command):
            return True
    except Exception:
        pass
    return _is_computer_use_command_before_observe_vision_ru_v654b(command)


def dispatch(command, *args, **kwargs):
    try:
        from modules.computer_use_observe_vision_ru import handle_dispatch_command

        observed = handle_dispatch_command(command, *args, **kwargs)
        if isinstance(observed, dict) and observed.get("handled"):
            return observed
    except Exception as exc:
        if _is_observe_vision_command_ru_v654b(command):
            return {
                "ok": False,
                "handled": True,
                "mode": "computer_use_observe_vision_error",
                "version": "v6.54b",
                "error": str(exc),
            }
    return _dispatch_before_observe_vision_ru_v654b(command, *args, **kwargs)
# END v6.54b Computer Use Observe/Vision core dispatch wrapper


# BEGIN v6.55b Agent Automation Functional Test Center core dispatch wrapper
try:
    _dispatch_before_agent_auto_test_ru_v655b
except NameError:
    _dispatch_before_agent_auto_test_ru_v655b = dispatch

try:
    _is_computer_use_command_before_agent_auto_test_ru_v655b
except NameError:
    _is_computer_use_command_before_agent_auto_test_ru_v655b = is_computer_use_command


def _is_agent_auto_test_command_ru_v655b(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {
        "pc computer agent auto test",
        "pc computer agent auto test full",
        "pc computer agent auto test smoke",
        "pc computer agent auto test status",
        "pc computer agent auto test latest",
        "pc computer agent automation test",
        "тест агента",
        "тест автоматических функций агента",
        "проверка автоматических функций агента",
    }:
        return True
    return lower.startswith("pc computer agent auto test ")


def is_computer_use_command(command):
    try:
        if _is_agent_auto_test_command_ru_v655b(command):
            return True
    except Exception:
        pass
    return _is_computer_use_command_before_agent_auto_test_ru_v655b(command)


def dispatch(command, *args, **kwargs):
    try:
        from modules.localcomet_agent_auto_test_center_ru import handle_dispatch_command

        result = handle_dispatch_command(command, *args, **kwargs)
        if isinstance(result, dict) and result.get("handled"):
            return result
    except Exception as exc:
        if _is_agent_auto_test_command_ru_v655b(command):
            return {
                "ok": False,
                "handled": True,
                "mode": "localcomet_agent_auto_test_core_error",
                "version": "v6.55b",
                "error": str(exc),
            }
    return _dispatch_before_agent_auto_test_ru_v655b(command, *args, **kwargs)


COMPUTER_USE_AGENT_AUTO_TEST_CENTER_RU_V655B = "v6.55b agent automation functional test center route"
# END v6.55b Agent Automation Functional Test Center core dispatch wrapper

# BEGIN v6.58 Developer Velocity Toolkit computer use core bridge
COMPUTER_USE_DEVELOPER_VELOCITY_BRIDGE_RU_V658 = "v6.58 developer velocity toolkit commands routed through computer_use_core"


def _is_developer_velocity_command_ru_v658(command):
    try:
        from modules.localcomet_developer_velocity_ru import is_developer_velocity_command
        return is_developer_velocity_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"последний сбой", "события патча", "статус разработки", "debug пакет"}


try:
    _is_computer_use_command_before_developer_velocity_ru_v658
except NameError:
    _is_computer_use_command_before_developer_velocity_ru_v658 = is_computer_use_command


def is_computer_use_command(command: str) -> bool:
    return _is_developer_velocity_command_ru_v658(command) or _is_computer_use_command_before_developer_velocity_ru_v658(command)


try:
    _dispatch_before_developer_velocity_ru_v658
except NameError:
    _dispatch_before_developer_velocity_ru_v658 = dispatch


def dispatch(command):
    if _is_developer_velocity_command_ru_v658(command):
        from modules.localcomet_developer_velocity_ru import dispatch as _developer_velocity_dispatch
        result = _developer_velocity_dispatch(command)
        if isinstance(result, dict):
            result["handled"] = True
            result.setdefault("route", "localcomet_developer_velocity_ru")
            return result
        return {"ok": False, "handled": True, "mode": "developer_velocity_bridge", "reason": "non-dict result", "value": str(result)[:1000]}
    return _dispatch_before_developer_velocity_ru_v658(command)

# END v6.58 Developer Velocity Toolkit computer use core bridge

# BEGIN v6.59a Command Explorer RU bridge
COMPUTER_USE_COMMAND_EXPLORER_BRIDGE_RU_V659A = "v6.59a command explorer commands routed through computer_use_core"


def _is_command_explorer_command_ru_v659a(command):
    try:
        from modules.command_explorer_ru import is_command_explorer_command
        if is_command_explorer_command(command):
            return True
    except Exception:
        pass
    try:
        from modules.repo_analyzer_ru import is_repo_analyzer_command
        if is_repo_analyzer_command(command):
            return True
    except Exception:
        pass
    lowered = str(command or "").strip().lower().replace("ё", "е")
    return lowered in {"команды проекта", "список команд", "command explorer",
                       "анализ проекта", "repo analyzer", "карта проекта"}


def _route_v659a_bridge(command):
    if _is_command_explorer_command_ru_v659a(command):
        from modules.command_explorer_ru import dispatch as _ce_dispatch
        if command and str(command).strip().lower().replace("ё", "е") in {"анализ проекта", "repo analyzer", "карта проекта", "pc repo analyze", "pc repo analyzer"}:
            from modules.repo_analyzer_ru import dispatch as _ra_dispatch
            _ce_dispatch = _ra_dispatch
        result = _ce_dispatch(command)
        if isinstance(result, dict):
            result["handled"] = True
            result.setdefault("route", "modules.command_explorer_ru" if not result.get("mode", "").startswith("repo_analyzer") else "modules.repo_analyzer_ru")
            return result
        return {"ok": False, "handled": True, "mode": "command_explorer_bridge", "reason": "non-dict result", "value": str(result)[:1000]}
    return _dispatch_before_command_explorer_ru_v659a(command)


try:
    _is_computer_use_command_before_command_explorer_ru_v659a
except NameError:
    _is_computer_use_command_before_command_explorer_ru_v659a = is_computer_use_command


def is_computer_use_command(command: str) -> bool:
    return _is_command_explorer_command_ru_v659a(command) or _is_computer_use_command_before_command_explorer_ru_v659a(command)


try:
    _dispatch_before_command_explorer_ru_v659a
except NameError:
    _dispatch_before_command_explorer_ru_v659a = dispatch


def dispatch(command):
    return _route_v659a_bridge(command)

# END v6.59a Command Explorer RU bridge




