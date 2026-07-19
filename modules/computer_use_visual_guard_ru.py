
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import json
import re
import uuid

VISUAL_GUARD_VERSION = "v6.47d"
ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
VISUAL_GUARD_DIR = COMPUTER_USE_DIR / "visual_guard"
LATEST_UI_MAP_PATH = COMPUTER_USE_DIR / "latest_ui_map.json"

DIALOG_MARKERS = {
    "ok", "cancel", "yes", "no", "apply", "close", "retry", "abort", "ignore",
    "ок", "отмена", "да", "нет", "применить", "закрыть", "повторить", "ошибка",
    "error", "warning", "confirm", "confirmation", "dialog", "modal",
}

ERROR_MARKERS = {
    "error", "failed", "exception", "traceback", "warning", "denied", "blocked",
    "ошибка", "сбой", "не удалось", "исключение", "предупреждение", "запрещено", "заблокировано",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_GUARD_DIR.mkdir(parents=True, exist_ok=True)


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


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-zа-яё0-9]+", str(text or "").lower(), flags=re.IGNORECASE)


def _extract_observation_summary(observation: Dict[str, Any]) -> Dict[str, Any]:
    data = observation or {}
    backend = data.get("backend") if isinstance(data.get("backend"), dict) else {}
    desktop_probe = backend.get("desktop_probe") if isinstance(backend.get("desktop_probe"), dict) else {}

    active_window = (
        data.get("active_window")
        or backend.get("active_window")
        or backend.get("window")
        or desktop_probe.get("active_window")
        or desktop_probe.get("window")
        or ""
    )
    screenshot_path = (
        data.get("screenshot_path")
        or backend.get("screenshot_path")
        or backend.get("path")
        or desktop_probe.get("screenshot_path")
        or desktop_probe.get("path")
        or ""
    )
    screenshot_hash = (
        data.get("screenshot_hash")
        or data.get("hash")
        or backend.get("screenshot_hash")
        or backend.get("hash")
        or desktop_probe.get("screenshot_hash")
        or desktop_probe.get("hash")
        or ""
    )
    screen_size = data.get("screen_size") or backend.get("screen_size") or desktop_probe.get("screen_size") or {}
    limitations = []
    for source in (data, backend, desktop_probe):
        value = source.get("limitations") if isinstance(source, dict) else None
        if isinstance(value, list):
            limitations.extend(str(item) for item in value)

    return {
        "active_window": str(active_window or ""),
        "screenshot_path": str(screenshot_path or ""),
        "screenshot_hash": str(screenshot_hash or ""),
        "screen_size": screen_size if isinstance(screen_size, dict) else {},
        "limitations": limitations,
    }


def _load_current_ui_map() -> Dict[str, Any]:
    if LATEST_UI_MAP_PATH.exists():
        payload = _read_json(LATEST_UI_MAP_PATH, {})
        elements = []
        if isinstance(payload, dict):
            raw = payload.get("elements") or payload.get("ui_elements") or []
            if isinstance(raw, list):
                elements = [item for item in raw if isinstance(item, dict)]
        return {
            "ok": True,
            "ui_map_path": str(LATEST_UI_MAP_PATH),
            "element_count": len(elements),
            "elements": elements,
            "payload": payload,
        }
    return {
        "ok": False,
        "ui_map_path": "",
        "element_count": 0,
        "elements": [],
        "payload": {},
    }


def _ui_map_element_count(ui_map: Dict[str, Any]) -> int:
    if not isinstance(ui_map, dict):
        return 0
    if isinstance(ui_map.get("elements"), list):
        return len([item for item in ui_map.get("elements", []) if isinstance(item, dict)])
    if isinstance(ui_map.get("ui_elements"), list):
        return len([item for item in ui_map.get("ui_elements", []) if isinstance(item, dict)])
    try:
        return int(ui_map.get("element_count") or 0)
    except Exception:
        return 0


def _preserve_previous_useful_ui_map(previous_ui_map: Dict[str, Any], new_ui_map: Dict[str, Any]) -> Dict[str, Any]:
    previous_count = _ui_map_element_count(previous_ui_map)
    new_count = _ui_map_element_count(new_ui_map)

    if previous_count > 0 and new_count == 0:
        preserved = dict(previous_ui_map)
        preserved["preserved_by_visual_guard"] = True
        preserved["preservation_reason"] = "build_ui_map returned zero elements; kept previous non-empty UI map for grounding stability"
        preserved["previous_element_count"] = previous_count
        preserved["discarded_empty_ui_map"] = new_ui_map
        try:
            LATEST_UI_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = preserved.get("payload") if isinstance(preserved.get("payload"), dict) else preserved
            if isinstance(payload, dict) and "elements" not in payload and isinstance(preserved.get("elements"), list):
                payload = dict(payload)
                payload["elements"] = preserved.get("elements", [])
            LATEST_UI_MAP_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return preserved

    return new_ui_map


def _element_text_blob(elements: List[Dict[str, Any]]) -> str:
    fields = ["text", "label", "name", "title", "role", "type", "value", "placeholder", "description"]
    parts: List[str] = []
    for element in elements[:250]:
        for field in fields:
            value = element.get(field)
            if value is not None:
                parts.append(str(value))
    return " ".join(parts).lower()


def classify_ui_markers(ui_map: Dict[str, Any]) -> Dict[str, Any]:
    elements = ui_map.get("elements") if isinstance(ui_map.get("elements"), list) else []
    blob = _element_text_blob(elements)
    tokens = set(_tokens(blob))
    dialog_hits = sorted((tokens & DIALOG_MARKERS) | {marker for marker in DIALOG_MARKERS if marker in blob})
    error_hits = sorted((tokens & ERROR_MARKERS) | {marker for marker in ERROR_MARKERS if marker in blob})
    return {
        "dialog_like": bool(dialog_hits),
        "error_like": bool(error_hits),
        "dialog_hits": dialog_hits[:20],
        "error_hits": error_hits[:20],
        "element_count": len(elements),
    }


def compare_observations(before: Dict[str, Any], after: Dict[str, Any], before_ui_map: Dict[str, Any] | None = None, after_ui_map: Dict[str, Any] | None = None) -> Dict[str, Any]:
    before_summary = _extract_observation_summary(before)
    after_summary = _extract_observation_summary(after)
    before_map = before_ui_map or {}
    after_map = after_ui_map or {}
    before_markers = classify_ui_markers(before_map)
    after_markers = classify_ui_markers(after_map)

    same_window = bool(before_summary["active_window"] and before_summary["active_window"] == after_summary["active_window"])
    window_changed = bool(before_summary["active_window"] and after_summary["active_window"] and before_summary["active_window"] != after_summary["active_window"])

    before_hash = before_summary.get("screenshot_hash", "")
    after_hash = after_summary.get("screenshot_hash", "")
    hash_changed = bool(before_hash and after_hash and before_hash != after_hash)
    hash_same = bool(before_hash and after_hash and before_hash == after_hash)

    before_count = int(before_map.get("element_count") or len(before_map.get("elements") or []) or 0)
    after_count = int(after_map.get("element_count") or len(after_map.get("elements") or []) or 0)
    element_delta = after_count - before_count
    element_delta_abs = abs(element_delta)

    changed_signals = 0
    if window_changed:
        changed_signals += 2
    if hash_changed:
        changed_signals += 2
    if element_delta_abs >= 3:
        changed_signals += 1
    if after_markers["dialog_like"] and not before_markers["dialog_like"]:
        changed_signals += 2
    if after_markers["error_like"] and not before_markers["error_like"]:
        changed_signals += 3

    stable_signals = 0
    if same_window:
        stable_signals += 1
    if hash_same:
        stable_signals += 1
    if element_delta_abs <= 2:
        stable_signals += 1

    if after_markers["error_like"]:
        decision = "stop"
        reason = "Error-like markers appeared after action."
    elif after_markers["dialog_like"] and not before_markers["dialog_like"]:
        decision = "ask_user"
        reason = "Dialog-like UI appeared after action."
    elif window_changed:
        decision = "replan"
        reason = "Active window changed after action."
    elif changed_signals >= 2:
        decision = "replan"
        reason = "Screen/UI changed enough to require replanning."
    elif stable_signals >= 2:
        decision = "continue"
        reason = "Screen appears stable after action."
    else:
        decision = "observe_again"
        reason = "Not enough evidence; observe once more."

    return {
        "ok": True,
        "mode": "computer_use_visual_compare",
        "version": VISUAL_GUARD_VERSION,
        "before": before_summary,
        "after": after_summary,
        "same_window": same_window,
        "window_changed": window_changed,
        "hash_changed": hash_changed,
        "hash_same": hash_same,
        "before_element_count": before_count,
        "after_element_count": after_count,
        "element_delta": element_delta,
        "changed_signals": changed_signals,
        "stable_signals": stable_signals,
        "before_markers": before_markers,
        "after_markers": after_markers,
        "decision": decision,
        "reason": reason,
    }


def observe_with_ui_map(label: str = "") -> Dict[str, Any]:
    observation = {}
    previous_ui_map = _load_current_ui_map()
    try:
        from modules.computer_use_core_ru import observe_screen, build_ui_map
        observation = observe_screen()
        fresh_ui_map = build_ui_map()
        ui_map = _preserve_previous_useful_ui_map(previous_ui_map, fresh_ui_map)
    except Exception as exc:
        observation = {
            "ok": False,
            "mode": "computer_use_visual_observe_error",
            "error": str(exc),
            "limitations": [str(exc)],
        }
        ui_map = previous_ui_map if _ui_map_element_count(previous_ui_map) > 0 else _load_current_ui_map()

    result = {
        "ok": True,
        "mode": "computer_use_visual_observe",
        "version": VISUAL_GUARD_VERSION,
        "label": label,
        "created_at": _now(),
        "observation": observation,
        "observation_summary": _extract_observation_summary(observation),
        "ui_map": ui_map,
        "ui_map_preserved": bool(isinstance(ui_map, dict) and ui_map.get("preserved_by_visual_guard")),
        "ui_markers": classify_ui_markers(ui_map),
    }
    _ensure_dirs()
    path = VISUAL_GUARD_DIR / f"visual_observe_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    result["artifact"] = _write_json(path, result)
    return result


def guarded_execute(action: Dict[str, Any], simulate: bool = False, before: Dict[str, Any] | None = None) -> Dict[str, Any]:
    before_snapshot = before or observe_with_ui_map("before_action")

    from modules.computer_use_auto_action_ru import execute_gui_action
    execution = execute_gui_action(action, simulate=simulate)

    after_snapshot = observe_with_ui_map("after_action")
    comparison = compare_observations(
        before_snapshot.get("observation", before_snapshot),
        after_snapshot.get("observation", after_snapshot),
        before_snapshot.get("ui_map", {}),
        after_snapshot.get("ui_map", {}),
    )

    result = {
        "ok": bool(execution.get("ok")),
        "mode": "computer_use_visual_guarded_execute",
        "version": VISUAL_GUARD_VERSION,
        "simulated": simulate,
        "action": action,
        "before": before_snapshot,
        "execution": execution,
        "after": after_snapshot,
        "comparison": comparison,
        "next_decision": comparison.get("decision"),
        "reason": comparison.get("reason"),
        "created_at": _now(),
    }
    _ensure_dirs()
    path = VISUAL_GUARD_DIR / f"visual_guarded_execute_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    result["artifact"] = _write_json(path, result)
    return result


def visual_guard_latest() -> Dict[str, Any]:
    _ensure_dirs()
    artifacts = sorted(VISUAL_GUARD_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not artifacts:
        return {
            "ok": False,
            "mode": "computer_use_visual_guard_latest",
            "error": "No visual guard artifacts yet.",
            "visual_guard_dir": str(VISUAL_GUARD_DIR),
        }
    payload = _read_json(artifacts[0], {})
    return {
        "ok": True,
        "mode": "computer_use_visual_guard_latest",
        "artifact": str(artifacts[0]),
        "payload": payload,
    }


def status() -> Dict[str, Any]:
    _ensure_dirs()
    return {
        "ok": True,
        "mode": "computer_use_visual_guard_status",
        "version": VISUAL_GUARD_VERSION,
        "visual_guard_dir": str(VISUAL_GUARD_DIR),
    }


def report() -> Dict[str, Any]:
    latest = visual_guard_latest()
    return {
        "ok": True,
        "mode": "computer_use_visual_guard_report",
        "version": VISUAL_GUARD_VERSION,
        "status": status(),
        "latest": latest,
    }


def is_computer_use_visual_guard_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = [
        "pc computer visual status",
        "pc computer visual observe",
        "pc computer visual latest",
        "pc computer visual compare",
        "pc computer visual guard",
        "визуальная проверка",
    ]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def dispatch(command: str) -> Dict[str, Any]:
    raw = (command or "").strip()
    value = raw.lower()

    if value == "pc computer visual status":
        return status()

    if value.startswith("pc computer visual observe"):
        label = raw[len("pc computer visual observe"):].strip() or "manual"
        return observe_with_ui_map(label)

    if value == "pc computer visual latest":
        return visual_guard_latest()

    if value == "pc computer visual compare":
        latest = visual_guard_latest()
        return latest

    if value.startswith("визуальная проверка"):
        return observe_with_ui_map("manual_ru")

    return {
        "ok": False,
        "mode": "computer_use_visual_guard_unknown_command",
        "command": command,
    }
