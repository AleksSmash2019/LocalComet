from __future__ import annotations

import json
import re
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

MULTISTEP_LOOP_VERSION = "v6.48i"
MODULE_NAME = "computer_use_multistep_loop_ru"


@dataclass
class UiCandidate:
    text: str
    role: str
    source_path: str
    bounds: dict[str, Any]
    raw: dict[str, Any]
    confidence: float = 0.0


@dataclass
class PlannedAction:
    kind: str
    target: str
    text: str
    confidence: float
    reason: str
    candidate: dict[str, Any] | None


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _json_default(value: Any) -> str:
    return str(value)


def _safe_json_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default),
        encoding="utf-8",
    )


def _safe_json_read(path: Path, fallback: Any) -> Any:
    try:
        if not path.exists():
            return fallback
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return fallback
        return json.loads(text)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": str(path)}


def _append_event(run_dir: Path, event: dict[str, Any]) -> None:
    event = dict(event)
    event.setdefault("timestamp", datetime.now().isoformat(timespec="seconds"))
    path = run_dir / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True, default=_json_default))
        handle.write("\n")


def _project_status() -> dict[str, Any]:
    try:
        from modules.project_paths import status

        result = status()
        if isinstance(result, dict):
            return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": False, "error": "project_paths.status unavailable"}


def _root() -> Path:
    status = _project_status()
    root_value = status.get("root")
    if root_value:
        return Path(root_value)
    return Path.cwd()


def _computer_use_dir() -> Path:
    status = _project_status()
    value = status.get("computer_use_dir")
    if value:
        return Path(value)
    return _root() / "Projects" / "ComputerUse"


def _latest_ui_map_path() -> Path:
    status = _project_status()
    value = status.get("computer_use_latest_ui_map_path")
    if value:
        return Path(value)
    return _computer_use_dir() / "latest_ui_map.json"


def _runs_dir() -> Path:
    return _computer_use_dir() / "multistep_runs"


def _latest_run_pointer() -> Path:
    return _runs_dir() / "latest_run.json"


def _stop_file() -> Path:
    return _runs_dir() / "stop_requested.json"


def _normalize(text: Any) -> str:
    value = str(text or "").casefold()
    value = value.replace("ё", "е")
    value = re.sub(r"[^0-9a-zа-я_:\-\s]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _looks_destructive_or_sensitive(text: str) -> bool:
    lowered = _normalize(text)
    markers = [
        "powershell",
        "cmd",
        "terminal",
        "shell",
        "sudo",
        "admin",
        "удали",
        "удалить",
        "delete",
        "wipe",
        "format",
        "rm ",
        "rmdir",
        "del ",
        "token",
        "api key",
        "apikey",
        "private key",
        "ssh",
        "cookie",
        "cookies",
        "browser profile",
        "password",
        "пароль",
        "секрет",
        "ключ",
        "банк",
        "bank",
        "payment",
        "casino",
        "gambling",
    ]
    return any(marker in lowered for marker in markers)


def _looks_file_changing(text: str) -> bool:
    lowered = _normalize(text)
    markers = [
        "write changes",
        "save file",
        "response json",
        "response.json",
        "запиши файл",
        "сохрани файл",
        "измени файл",
        "перезапиши",
        "создай файл",
        "create file",
        "modify file",
        "delete file",
        "удали файл",
        "patch",
        "installer",
    ]
    return any(marker in lowered for marker in markers)


def _safety_check_goal(goal: str) -> dict[str, Any]:
    try:
        from modules.computer_use_safety_ru import safety_check_goal

        result = safety_check_goal(goal)
        if isinstance(result, dict):
            return result
    except Exception as exc:
        if _looks_destructive_or_sensitive(goal):
            return {
                "ok": False,
                "blocked": True,
                "risk": "blocked",
                "reason": "fallback blocked dangerous or sensitive marker after safety module error: " + str(exc),
                "problem_types": ["fallback_block"],
            }
        return {"ok": True, "blocked": False, "risk": "unknown", "warning": str(exc)}
    if _looks_destructive_or_sensitive(goal):
        return {
            "ok": False,
            "blocked": True,
            "risk": "blocked",
            "reason": "fallback blocked dangerous or sensitive marker",
            "problem_types": ["fallback_block"],
        }
    return {"ok": True, "blocked": False, "risk": "unknown"}


def _iter_dict_nodes(value: Any, path: str = "$") -> list[tuple[str, dict[str, Any]]]:
    nodes: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, dict):
        nodes.append((path, value))
        for key, child in value.items():
            nodes.extend(_iter_dict_nodes(child, path + "." + str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            nodes.extend(_iter_dict_nodes(child, path + "[" + str(index) + "]"))
    return nodes


def _first_text(data: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)) and str(value).strip():
            return str(value).strip()
    return ""


def _extract_bounds(data: dict[str, Any]) -> dict[str, Any]:
    direct: dict[str, Any] = {}
    for key in ("x", "y", "width", "height", "left", "top", "right", "bottom"):
        if key in data and isinstance(data.get(key), (int, float, str)):
            direct[key] = data.get(key)
    for key in ("bounds", "bbox", "rect", "rectangle"):
        value = data.get(key)
        if isinstance(value, dict):
            for bkey in ("x", "y", "width", "height", "left", "top", "right", "bottom"):
                if bkey in value:
                    direct[bkey] = value.get(bkey)
        elif isinstance(value, list) and len(value) >= 4:
            direct["x"] = value[0]
            direct["y"] = value[1]
            direct["width"] = value[2]
            direct["height"] = value[3]
    return direct


def extract_candidates(ui_map: Any) -> list[dict[str, Any]]:
    candidates: list[UiCandidate] = []
    text_keys = [
        "text",
        "title",
        "name",
        "label",
        "caption",
        "value",
        "automation_id",
        "automationId",
        "id",
        "control",
        "control_text",
    ]
    role_keys = ["role", "type", "control_type", "controlType", "class_name", "className", "kind"]
    for path, node in _iter_dict_nodes(ui_map):
        text = _first_text(node, text_keys)
        role = _first_text(node, role_keys)
        bounds = _extract_bounds(node)
        if not text and not role:
            continue
        if not text and role:
            continue
        if len(text) > 180:
            continue
        candidates.append(
            UiCandidate(
                text=text,
                role=role,
                source_path=path,
                bounds=bounds,
                raw={key: node.get(key) for key in set(text_keys + role_keys) if key in node},
            )
        )
    unique: dict[tuple[str, str, str], UiCandidate] = {}
    for item in candidates:
        key = (_normalize(item.text), _normalize(item.role), item.source_path)
        unique[key] = item
    return [asdict(item) for item in unique.values()]


def _read_ui_map() -> dict[str, Any]:
    path = _latest_ui_map_path()
    data = _safe_json_read(path, {})
    candidates = extract_candidates(data)
    return {
        "ok": bool(candidates) or isinstance(data, dict),
        "path": str(path),
        "raw": data,
        "candidates": candidates,
        "candidate_count": len(candidates),
    }


def _strip_command_prefix(goal: str) -> str:
    value = _normalize(goal)
    prefixes = [
        "pc computer run loop",
        "pc computer simulate loop",
        "цикл computer use",
        "симуляция цикла computer use",
        "computer use",
        "pc computer",
    ]
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix) :].strip()
    return value


def _action_kind(goal: str) -> str:
    value = _normalize(goal)
    type_markers = ["type", "search", "введи", "напечатай", "поиск", "найди"]
    click_markers = ["click", "open", "press", "нажми", "клик", "кликни", "открой", "выбери"]
    if "::" in goal and any(marker in value for marker in type_markers):
        return "type"
    if any(marker in value for marker in click_markers):
        return "click"
    return "unknown"


def _target_words(goal: str) -> str:
    value = _strip_command_prefix(goal)
    remove_words = [
        "click",
        "open",
        "press",
        "button",
        "element",
        "нажми",
        "клик",
        "кликни",
        "открой",
        "выбери",
        "кнопку",
        "кнопка",
        "элемент",
        "меню",
        "по",
        "на",
    ]
    words = [word for word in value.split() if word not in remove_words]
    return " ".join(words).strip()


def _score_candidate_for_goal(candidate: dict[str, Any], goal: str, target: str) -> float:
    text = _normalize(candidate.get("text"))
    role = _normalize(candidate.get("role"))
    full = (text + " " + role).strip()
    normalized_goal = _normalize(goal)
    normalized_target = _normalize(target)
    if not text:
        return 0.0
    if text in normalized_goal:
        return 0.97
    if normalized_target and normalized_target in full:
        return 0.94
    if normalized_target and full in normalized_target and len(full) >= 3:
        return 0.91
    target_words = [word for word in normalized_target.split() if len(word) >= 3]
    if target_words:
        matched = sum(1 for word in target_words if word in full)
        ratio = matched / max(1, len(target_words))
        if ratio >= 0.67:
            return 0.66 + min(0.22, ratio * 0.22)
    if "button" in role or "кноп" in role:
        goal_words = [word for word in normalized_goal.split() if len(word) >= 4]
        if goal_words and any(word in text for word in goal_words):
            return 0.68
    return 0.0


def _best_candidate(candidates: list[dict[str, Any]], goal: str, target: str) -> tuple[dict[str, Any] | None, float]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for candidate in candidates:
        score = _score_candidate_for_goal(candidate, goal, target)
        updated = dict(candidate)
        updated["confidence"] = round(score, 4)
        scored.append((score, updated))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if not scored:
        return None, 0.0
    return scored[0][1], scored[0][0]


def _parse_type_goal(goal: str) -> tuple[str, str]:
    left, right = goal.split("::", 1)
    target = _target_words(left)
    normalized = _normalize(target)
    if "поиск" in normalized or "search" in normalized:
        target = "Поиск"
    target = target.strip() or "Поиск"
    text = right.strip()
    return target, text


def _candidate_summaries(candidates: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for candidate in candidates[:limit]:
        result.append(
            {
                "text": candidate.get("text", ""),
                "role": candidate.get("role", ""),
                "confidence": candidate.get("confidence", 0.0),
                "source_path": candidate.get("source_path", ""),
                "bounds": candidate.get("bounds", {}),
            }
        )
    return result


def decide_next_action(goal: str, ui_observation: dict[str, Any]) -> dict[str, Any]:
    candidates = ui_observation.get("candidates", [])
    kind = _action_kind(goal)
    if kind == "type":
        if "::" not in goal:
            return {
                "ok": False,
                "decision": "ask_user",
                "reason": "Для ввода нужен формат: цель :: текст",
                "candidates": _candidate_summaries(candidates),
            }
        target, text = _parse_type_goal(goal)
        candidate, confidence = _best_candidate(candidates, goal, target)
        if candidate is None or confidence < 0.62:
            return {
                "ok": False,
                "decision": "ask_user",
                "reason": "Низкая уверенность grounding для поля ввода",
                "target": target,
                "candidates": _candidate_summaries(candidates),
            }
        return {
            "ok": True,
            "decision": "action",
            "action": asdict(
                PlannedAction(
                    kind="type",
                    target=target,
                    text=text,
                    confidence=round(confidence, 4),
                    reason="deterministic type rule with explicit :: payload",
                    candidate=candidate,
                )
            ),
        }
    if kind == "click":
        target = _target_words(goal)
        candidate, confidence = _best_candidate(candidates, goal, target)
        if candidate is None or confidence < 0.62:
            return {
                "ok": False,
                "decision": "ask_user",
                "reason": "Низкая уверенность grounding для клика",
                "target": target,
                "candidates": _candidate_summaries(candidates),
            }
        return {
            "ok": True,
            "decision": "action",
            "action": asdict(
                PlannedAction(
                    kind="click",
                    target=str(candidate.get("text") or target),
                    text="",
                    confidence=round(confidence, 4),
                    reason="deterministic click/open rule matched candidate text",
                    candidate=candidate,
                )
            ),
        }
    return {
        "ok": False,
        "decision": "ask_user",
        "reason": "Не найдено безопасное детерминированное действие",
        "candidates": _candidate_summaries(candidates),
    }


def _call_click_element(target: str, simulate: bool) -> dict[str, Any]:
    module_names = [
        "modules.computer_use_auto_action_ru",
        "modules.computer_use_click_planner_ru",
        "modules.computer_use_core_ru",
    ]
    last_error = ""
    for module_name in module_names:
        try:
            module = import_module(module_name)
            func = getattr(module, "click_element", None)
            if callable(func):
                result = func(target, simulate=simulate)
                if isinstance(result, dict):
                    return result
                return {"ok": bool(result), "result": result}
        except Exception as exc:
            last_error = module_name + ": " + str(exc)
    if simulate:
        return {
            "ok": True,
            "mode": "click_element_simulated_by_multistep_loop",
            "target": target,
            "simulate": True,
            "warning": last_error,
        }
    return {
        "ok": False,
        "mode": "click_element_unavailable",
        "target": target,
        "simulate": False,
        "error": last_error or "click_element function not found",
    }


def _call_guarded_type(target: str, text: str, simulate: bool) -> dict[str, Any]:
    module_names = [
        "modules.computer_use_type_guard_ru",
        "modules.computer_use_auto_action_ru",
        "modules.computer_use_core_ru",
    ]
    last_error = ""
    for module_name in module_names:
        try:
            module = import_module(module_name)
            func = getattr(module, "guarded_type", None)
            if callable(func):
                result = func(target, text, simulate=simulate)
                if isinstance(result, dict):
                    return result
                return {"ok": bool(result), "result": result}
        except Exception as exc:
            last_error = module_name + ": " + str(exc)
    if simulate:
        return {
            "ok": True,
            "mode": "guarded_type_simulated_by_multistep_loop",
            "target": target,
            "text": text,
            "simulate": True,
            "warning": last_error,
        }
    return {
        "ok": False,
        "mode": "guarded_type_unavailable",
        "target": target,
        "text": text,
        "simulate": False,
        "error": last_error or "guarded_type function not found",
    }


def import_module(name: str) -> Any:
    import importlib

    return importlib.import_module(name)


def execute_planned_action(action: dict[str, Any], simulate: bool) -> dict[str, Any]:
    kind = action.get("kind")
    target = str(action.get("target") or "").strip()
    text = str(action.get("text") or "")
    if not target:
        return {"ok": False, "status": "error", "reason": "empty target"}
    if kind == "type":
        if _looks_file_changing(text):
            return {
                "ok": False,
                "status": "requires_confirmation",
                "requires_confirmation": True,
                "reason": "typed payload appears to change files and needs explicit confirmation",
                "target": target,
            }
        return _call_guarded_type(target, text, simulate=simulate)
    if kind == "click":
        return _call_click_element(target, simulate=simulate)
    return {"ok": False, "status": "error", "reason": "unsupported action kind: " + str(kind)}


def visual_guard_compare(before_observation: dict[str, Any], after_observation: dict[str, Any], action_result: dict[str, Any]) -> dict[str, Any]:
    before_count = int(before_observation.get("candidate_count") or 0)
    after_count = int(after_observation.get("candidate_count") or 0)
    if action_result.get("requires_confirmation") or action_result.get("status") == "requires_confirmation":
        decision = "ask_user"
        reason = "action requires explicit confirmation"
    elif not action_result.get("ok"):
        decision = "stop"
        reason = "action failed"
    elif before_count == 0 and after_count == 0:
        decision = "ask_user"
        reason = "no UI candidates before or after action"
    else:
        decision = "done"
        reason = "deterministic one-action loop completed"
    return {
        "ok": decision in {"done", "replan", "ask_user"},
        "mode": "computer_use_visual_guard_record",
        "version": MULTISTEP_LOOP_VERSION,
        "decision": decision,
        "reason": reason,
        "before_candidate_count": before_count,
        "after_candidate_count": after_count,
    }


def _make_run(goal: str, simulate: bool, max_steps: int) -> tuple[str, Path, dict[str, Any]]:
    run_id = "run_" + _now_stamp()
    run_dir = _runs_dir() / run_id
    (run_dir / "steps").mkdir(parents=True, exist_ok=True)
    data = {
        "ok": True,
        "mode": "computer_use_multistep_loop",
        "version": MULTISTEP_LOOP_VERSION,
        "run_id": run_id,
        "goal": goal,
        "simulate": bool(simulate),
        "max_steps": max_steps,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "created",
        "outcome": "running",
        "steps": [],
        "run_dir": str(run_dir),
    }
    _safe_json_write(run_dir / "run.json", data)
    _safe_json_write(_latest_run_pointer(), {"run_id": run_id, "run_dir": str(run_dir), "updated_at": data["updated_at"]})
    return run_id, run_dir, data


def _write_report(run_dir: Path, run_data: dict[str, Any]) -> str:
    lines = [
        "# Computer Use Multi-Step Loop Report",
        "",
        "- Version: " + str(run_data.get("version")),
        "- Run ID: " + str(run_data.get("run_id")),
        "- Status: " + str(run_data.get("status")),
        "- Outcome: " + str(run_data.get("outcome")),
        "- Simulate: " + str(run_data.get("simulate")),
        "- Goal: " + str(run_data.get("goal")),
        "- Steps: " + str(len(run_data.get("steps", []))),
        "",
        "## Steps",
    ]
    for step in run_data.get("steps", []):
        lines.append("")
        lines.append("### Step " + str(step.get("step_index")))
        lines.append("- Decision: " + str(step.get("decision", {}).get("decision")))
        action = step.get("action")
        if isinstance(action, dict):
            lines.append("- Action: " + str(action.get("kind")) + " -> " + str(action.get("target")))
        result = step.get("action_result")
        if isinstance(result, dict):
            lines.append("- Result ok: " + str(result.get("ok")))
            lines.append("- Result status: " + str(result.get("status", result.get("mode", ""))))
        visual = step.get("visual_guard")
        if isinstance(visual, dict):
            lines.append("- Visual guard: " + str(visual.get("decision")) + " / " + str(visual.get("reason")))
    report_path = run_dir / "report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(report_path)


def _finish_run(run_dir: Path, run_data: dict[str, Any], status: str, outcome: str, reason: str) -> dict[str, Any]:
    run_data["status"] = status
    run_data["outcome"] = outcome
    run_data["reason"] = reason
    run_data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    report = _write_report(run_dir, run_data)
    run_data["report"] = report
    _safe_json_write(run_dir / "run.json", run_data)
    _safe_json_write(_latest_run_pointer(), {"run_id": run_data.get("run_id"), "run_dir": str(run_dir), "updated_at": run_data["updated_at"]})
    _append_event(run_dir, {"event": "finish", "status": status, "outcome": outcome, "reason": reason})
    result = dict(run_data)
    result["ok"] = outcome in {"done", "requires_confirmation", "ask_user", "blocked", "stopped"}
    return result


def run_loop(goal: str, simulate: bool = False, max_steps: int = 3, max_failures: int = 1) -> dict[str, Any]:
    goal = str(goal or "").strip()
    if not goal:
        return {
            "ok": False,
            "mode": "computer_use_multistep_loop",
            "version": MULTISTEP_LOOP_VERSION,
            "status": "rejected",
            "outcome": "ask_user",
            "reason": "empty goal",
        }
    max_steps = max(1, min(int(max_steps), 8))
    max_failures = max(1, min(int(max_failures), 5))
    safety = _safety_check_goal(goal)
    if safety.get("blocked") or safety.get("ok") is False and safety.get("risk") == "blocked":
        run_id, run_dir, run_data = _make_run(goal, simulate, max_steps)
        run_data["safety"] = safety
        return _finish_run(run_dir, run_data, "blocked", "blocked", str(safety.get("reason", "blocked by safety policy")))
    if _action_kind(goal) == "type":
        parsed_target, parsed_text = _parse_type_goal(goal) if "::" in goal else ("", "")
        if _looks_file_changing(parsed_text):
            run_id, run_dir, run_data = _make_run(goal, simulate, max_steps)
            run_data["safety"] = safety
            run_data["steps"].append(
                {
                    "step_index": 0,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "observation": {"ok": None, "candidate_count": None, "candidates": []},
                    "decision": {
                        "ok": False,
                        "decision": "requires_confirmation",
                        "reason": "typed payload appears to change files and needs explicit confirmation before grounding",
                        "target": parsed_target,
                    },
                    "action": {
                        "kind": "type",
                        "target": parsed_target,
                        "text": parsed_text,
                        "confidence": 0.0,
                        "reason": "confirmation gate before UI grounding",
                        "candidate": None,
                    },
                    "action_result": {
                        "ok": False,
                        "status": "requires_confirmation",
                        "requires_confirmation": True,
                        "reason": "typed payload appears to change files and needs explicit confirmation",
                        "target": parsed_target,
                    },
                    "visual_guard": {
                        "ok": True,
                        "mode": "computer_use_visual_guard_record",
                        "version": MULTISTEP_LOOP_VERSION,
                        "decision": "ask_user",
                        "reason": "action requires explicit confirmation",
                    },
                }
            )
            return _finish_run(run_dir, run_data, "needs_confirmation", "requires_confirmation", "typed payload appears to change files and needs explicit confirmation")
    run_id, run_dir, run_data = _make_run(goal, simulate, max_steps)
    run_data["safety"] = safety
    _append_event(run_dir, {"event": "start", "run_id": run_id, "simulate": simulate, "goal": goal})
    failures = 0
    for step_index in range(1, max_steps + 1):
        if _stop_file().exists():
            stop_data = _safe_json_read(_stop_file(), {})
            return _finish_run(run_dir, run_data, "stopped", "stopped", "stop requested: " + str(stop_data.get("reason", "")))
        before = _read_ui_map()
        decision = decide_next_action(goal, before)
        step: dict[str, Any] = {
            "step_index": step_index,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "observation": {
                "ok": before.get("ok"),
                "path": before.get("path"),
                "candidate_count": before.get("candidate_count"),
                "candidates": _candidate_summaries(before.get("candidates", []), limit=8),
            },
            "decision": decision,
            "action": None,
            "action_result": None,
            "visual_guard": None,
        }
        if decision.get("decision") == "ask_user":
            step["visual_guard"] = {
                "ok": True,
                "mode": "computer_use_visual_guard_record",
                "version": MULTISTEP_LOOP_VERSION,
                "decision": "ask_user",
                "reason": decision.get("reason", "low confidence"),
            }
            run_data["steps"].append(step)
            _safe_json_write(run_dir / "steps" / ("step_" + str(step_index).zfill(3) + ".json"), step)
            _append_event(run_dir, {"event": "step", "step": step_index, "decision": "ask_user", "reason": decision.get("reason")})
            return _finish_run(run_dir, run_data, "needs_user", "ask_user", str(decision.get("reason", "low confidence")))
        if not decision.get("ok"):
            failures += 1
            step["action_result"] = {"ok": False, "status": "decision_failed", "reason": decision.get("reason", "decision failed")}
            run_data["steps"].append(step)
            _safe_json_write(run_dir / "steps" / ("step_" + str(step_index).zfill(3) + ".json"), step)
            _append_event(run_dir, {"event": "step", "step": step_index, "decision": "failed", "failures": failures})
            if failures >= max_failures:
                return _finish_run(run_dir, run_data, "failed", "error", "max failures reached")
            continue
        action = decision.get("action")
        if not isinstance(action, dict):
            failures += 1
            step["action_result"] = {"ok": False, "status": "missing_action"}
            run_data["steps"].append(step)
            _safe_json_write(run_dir / "steps" / ("step_" + str(step_index).zfill(3) + ".json"), step)
            if failures >= max_failures:
                return _finish_run(run_dir, run_data, "failed", "error", "missing action")
            continue
        step["action"] = action
        action_result = execute_planned_action(action, simulate=simulate)
        step["action_result"] = action_result
        after = _read_ui_map()
        visual = visual_guard_compare(before, after, action_result)
        step["visual_guard"] = visual
        run_data["steps"].append(step)
        _safe_json_write(run_dir / "steps" / ("step_" + str(step_index).zfill(3) + ".json"), step)
        _append_event(
            run_dir,
            {
                "event": "step",
                "step": step_index,
                "decision": decision.get("decision"),
                "action_kind": action.get("kind"),
                "action_target": action.get("target"),
                "action_ok": action_result.get("ok"),
                "visual_guard_decision": visual.get("decision"),
            },
        )
        if action_result.get("requires_confirmation") or action_result.get("status") == "requires_confirmation":
            return _finish_run(run_dir, run_data, "needs_confirmation", "requires_confirmation", str(action_result.get("reason", "confirmation required")))
        if visual.get("decision") == "ask_user":
            return _finish_run(run_dir, run_data, "needs_user", "ask_user", str(visual.get("reason", "visual guard asks user")))
        if visual.get("decision") == "stop":
            return _finish_run(run_dir, run_data, "stopped", "stopped", str(visual.get("reason", "visual guard stop")))
        if visual.get("decision") == "replan":
            continue
        return _finish_run(run_dir, run_data, "done", "done", "one deterministic action completed")
    return _finish_run(run_dir, run_data, "stopped", "stopped", "max_steps reached")


def status() -> dict[str, Any]:
    runs = _runs_dir()
    pointer = _safe_json_read(_latest_run_pointer(), {})
    stop_requested = _stop_file().exists()
    latest = latest_run()
    return {
        "ok": True,
        "mode": "computer_use_multistep_loop_status",
        "version": MULTISTEP_LOOP_VERSION,
        "runs_dir": str(runs),
        "latest_pointer": pointer,
        "latest_run_id": latest.get("run_id") if isinstance(latest, dict) else "",
        "latest_status": latest.get("status") if isinstance(latest, dict) else "",
        "latest_outcome": latest.get("outcome") if isinstance(latest, dict) else "",
        "stop_requested": stop_requested,
    }


def latest_run() -> dict[str, Any]:
    pointer = _safe_json_read(_latest_run_pointer(), {})
    run_dir = pointer.get("run_dir") if isinstance(pointer, dict) else ""
    if run_dir:
        data = _safe_json_read(Path(run_dir) / "run.json", {})
        if isinstance(data, dict) and data:
            data.setdefault("ok", True)
            data.setdefault("mode", "computer_use_multistep_loop_latest")
            return data
    return {
        "ok": False,
        "mode": "computer_use_multistep_loop_latest",
        "version": MULTISTEP_LOOP_VERSION,
        "reason": "no latest run",
    }


def latest_report() -> dict[str, Any]:
    data = latest_run()
    report_path = data.get("report") if isinstance(data, dict) else ""
    if report_path and Path(report_path).exists():
        return {
            "ok": True,
            "mode": "computer_use_multistep_loop_report",
            "version": MULTISTEP_LOOP_VERSION,
            "report": report_path,
            "content": Path(report_path).read_text(encoding="utf-8"),
        }
    return {
        "ok": False,
        "mode": "computer_use_multistep_loop_report",
        "version": MULTISTEP_LOOP_VERSION,
        "reason": "no report available",
        "latest": data,
    }


def request_stop(reason: str = "user requested stop") -> dict[str, Any]:
    data = {
        "ok": True,
        "mode": "computer_use_multistep_loop_stop",
        "version": MULTISTEP_LOOP_VERSION,
        "reason": str(reason or "user requested stop"),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    _safe_json_write(_stop_file(), data)
    return data


def clear_stop_request() -> dict[str, Any]:
    path = _stop_file()
    existed = path.exists()
    if existed:
        cleared_path = path.with_name(path.name + ".cleared_" + _now_stamp())
        path.rename(cleared_path)
    return {
        "ok": True,
        "mode": "computer_use_multistep_loop_clear_stop",
        "version": MULTISTEP_LOOP_VERSION,
        "existed": existed,
    }


def handle_dispatch_command(command: str) -> dict[str, Any]:
    raw = str(command or "").strip()
    lowered = _normalize(raw)
    prefixes_run = ["pc computer run loop", "цикл computer use"]
    prefixes_sim = ["pc computer simulate loop", "симуляция цикла computer use"]
    if lowered in {"pc computer loop status", "статус цикла computer use"}:
        result = status()
        result["handled"] = True
        return result
    if lowered in {"pc computer loop latest", "последний цикл computer use"}:
        result = latest_run()
        result["handled"] = True
        return result
    if lowered in {"pc computer loop report", "отчет цикла computer use", "отчёт цикла computer use"}:
        result = latest_report()
        result["handled"] = True
        return result
    if lowered in {"pc computer loop stop", "останови цикл computer use"}:
        result = request_stop("dispatch command: " + raw)
        result["handled"] = True
        return result
    for prefix in prefixes_sim:
        if lowered.startswith(prefix):
            goal = raw[len(prefix) :].strip()
            result = run_loop(goal, simulate=True)
            result["handled"] = True
            return result
    for prefix in prefixes_run:
        if lowered.startswith(prefix):
            goal = raw[len(prefix) :].strip()
            result = run_loop(goal, simulate=False)
            result["handled"] = True
            return result
    return {"handled": False, "ok": False, "mode": "computer_use_multistep_loop_dispatch", "reason": "not a multistep loop command"}


def _synthetic_ui_map() -> dict[str, Any]:
    return {
        "ok": True,
        "source": "computer_use_multistep_loop_ru self check",
        "elements": [
            {
                "text": "Сохранить",
                "role": "button",
                "x": 20,
                "y": 20,
                "width": 140,
                "height": 36,
                "automation_id": "btn_save",
            },
            {
                "text": "Поиск",
                "role": "edit",
                "x": 20,
                "y": 80,
                "width": 260,
                "height": 32,
                "automation_id": "input_search",
            },
            {
                "text": "Отмена",
                "role": "button",
                "x": 180,
                "y": 20,
                "width": 120,
                "height": 36,
                "automation_id": "btn_cancel",
            },
        ],
    }


def _backup_latest_ui_map() -> tuple[Path, Path | None, bool]:
    latest = _latest_ui_map_path()
    existed = latest.exists()
    backup = None
    if existed:
        backup = latest.with_name(latest.name + ".v648i_multistep_backup")
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(latest.read_bytes())
    return latest, backup, existed


def _restore_latest_ui_map(latest: Path, backup: Path | None, existed: bool) -> None:
    if existed and backup is not None and backup.exists():
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest.write_bytes(backup.read_bytes())
    elif not existed and latest.exists():
        quarantine = latest.with_name(latest.name + ".v648i_quarantine_" + _now_stamp())
        latest.rename(quarantine)


def _check(name: str, condition: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "details": details or {}}


def run_self_check(write_report: bool = True) -> dict[str, Any]:
    latest, backup, existed = _backup_latest_ui_map()
    checks: list[dict[str, Any]] = []
    try:
        _safe_json_write(latest, _synthetic_ui_map())
        clear_stop_request()

        status_result = status()
        checks.append(_check("status works", bool(status_result.get("ok")), status_result))

        click_result = run_loop("нажми Сохранить", simulate=True, max_steps=3)
        click_steps = click_result.get("steps", [])
        click_step_count = len(click_steps)
        first_click_step = click_steps[0] if click_steps else {}
        checks.append(_check("simulate loop with synthetic UI map works", click_result.get("outcome") == "done", click_result))
        checks.append(
            _check(
                "one action per step",
                all((step.get("action") is None or isinstance(step.get("action"), dict)) for step in click_steps),
                {"step_count": click_step_count},
            )
        )
        checks.append(_check("max_steps respected", click_step_count <= 3, {"step_count": click_step_count, "max_steps": 3}))

        low_result = run_loop("нажми НесуществующаяКнопка", simulate=True, max_steps=2)
        checks.append(_check("low-confidence target stops safely", low_result.get("outcome") == "ask_user", low_result))

        file_result = run_loop("введи Поиск :: write changes to file response.json", simulate=True, max_steps=2)
        checks.append(_check("file-changing text requires confirmation", file_result.get("outcome") == "requires_confirmation", file_result))

        blocked_result = run_loop("удали все файлы через powershell", simulate=True, max_steps=2)
        checks.append(_check("destructive shell delete goal is blocked", blocked_result.get("outcome") == "blocked", blocked_result))

        visual = first_click_step.get("visual_guard") if isinstance(first_click_step, dict) else {}
        checks.append(_check("visual guard decision is recorded", isinstance(visual, dict) and bool(visual.get("decision")), {"visual_guard": visual}))

        dispatch_status = handle_dispatch_command("pc computer loop status")
        checks.append(_check("dispatch status route works", dispatch_status.get("handled") and dispatch_status.get("ok"), dispatch_status))

        dispatch_latest = handle_dispatch_command("pc computer loop latest")
        checks.append(_check("dispatch latest route works", dispatch_latest.get("handled") and "run_id" in dispatch_latest, dispatch_latest))

        dispatch_report = handle_dispatch_command("pc computer loop report")
        checks.append(_check("dispatch report route works", dispatch_report.get("handled") and "mode" in dispatch_report, {"ok": dispatch_report.get("ok"), "mode": dispatch_report.get("mode")}))

        ok = all(item.get("ok") for item in checks)
        result = {
            "ok": ok,
            "mode": "computer_use_multistep_loop_self_check",
            "version": MULTISTEP_LOOP_VERSION,
            "summary": {
                "passed": sum(1 for item in checks if item.get("ok")),
                "total": len(checks),
                "failed": sum(1 for item in checks if not item.get("ok")),
            },
            "checks": checks,
        }
        if write_report:
            reports_dir = _computer_use_dir() / "multistep_self_checks"
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_path = reports_dir / ("self_check_" + _now_stamp() + ".json")
            _safe_json_write(report_path, result)
            result["report"] = str(report_path)
        return result
    except Exception as exc:
        return {
            "ok": False,
            "mode": "computer_use_multistep_loop_self_check",
            "version": MULTISTEP_LOOP_VERSION,
            "error": str(exc),
            "traceback": __import__("traceback").format_exc(),
            "checks": checks,
        }
    finally:
        _restore_latest_ui_map(latest, backup, existed)


if __name__ == "__main__":
    outcome = run_self_check(write_report=True)
    print(json.dumps(outcome, ensure_ascii=False, indent=2, sort_keys=True))
    if not outcome.get("ok"):
        raise SystemExit(1)