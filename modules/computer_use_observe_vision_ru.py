
from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


VERSION = "v6.54b"
FEATURE_NAME = "Computer Use Observe/Vision Upgrade RU"

ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = ROOT / "Projects"
COMPUTER_USE_DIR = PROJECTS_DIR / "ComputerUse"
VISION_REPORTS_DIR = COMPUTER_USE_DIR / "observe_vision_reports"
LATEST_OBSERVATION_FILE = VISION_REPORTS_DIR / "latest_observation.json"
LATEST_REPORT_FILE = VISION_REPORTS_DIR / "latest_observation.md"


def _now() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    VISION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (VISION_REPORTS_DIR / "snapshots").mkdir(parents=True, exist_ok=True)


def _safe_json_read(path: Path) -> Tuple[bool, Any, str]:
    try:
        if not path.exists():
            return False, None, "missing"
        return True, json.loads(path.read_text(encoding="utf-8")), "ok"
    except Exception as exc:
        return False, None, str(exc)


def _safe_json_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _candidate_ui_map_paths() -> List[Path]:
    return [
        COMPUTER_USE_DIR / "latest_ui_map.json",
        COMPUTER_USE_DIR / "ui_maps" / "latest_ui_map.json",
        COMPUTER_USE_DIR / "runtime" / "latest_ui_map.json",
        PROJECTS_DIR / "Reports" / "computer_use" / "latest_ui_map.json",
    ]


def _load_latest_ui_map() -> Dict[str, Any]:
    for path in _candidate_ui_map_paths():
        ok, data, message = _safe_json_read(path)
        if ok and isinstance(data, dict):
            data.setdefault("_source", str(path))
            return data
    return {
        "_source": "none",
        "ok": False,
        "elements": [],
        "windows": [],
        "message": "latest UI map was not found; observe/vision will use desktop observer if available and synthetic-safe fallback otherwise",
    }


def _flatten_elements(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        result: List[Dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, list):
                result.extend(_flatten_elements(item))
        return result
    if isinstance(value, dict):
        for key in ("elements", "items", "nodes", "controls", "children"):
            if key in value:
                return _flatten_elements(value.get(key))
    return []


def _normalize_text(value: Any) -> str:
    return str(value or "").replace("\n", " ").replace("\r", " ").strip()


def _element_label(element: Dict[str, Any]) -> str:
    for key in ("label", "text", "name", "title", "automation_id", "id", "value", "placeholder"):
        text = _normalize_text(element.get(key))
        if text:
            return text
    return ""


def _element_role(element: Dict[str, Any]) -> str:
    for key in ("role", "type", "control_type", "class_name", "kind"):
        text = _normalize_text(element.get(key))
        if text:
            return text.lower()
    return ""


def _rect_value(element: Dict[str, Any]) -> Dict[str, Any]:
    rect = element.get("rect") or element.get("bbox") or element.get("bounds") or element.get("box") or {}
    if isinstance(rect, dict):
        return dict(rect)
    if isinstance(rect, (list, tuple)) and len(rect) >= 4:
        return {"x": rect[0], "y": rect[1], "width": rect[2], "height": rect[3]}
    return {}


def _ui_map_quality(ui_map: Dict[str, Any]) -> Dict[str, Any]:
    elements = _flatten_elements(ui_map)
    labels = [_element_label(item) for item in elements]
    roles = [_element_role(item) for item in elements]
    clickable = 0
    inputs = 0
    visible = 0
    for item, role in zip(elements, roles):
        label = _element_label(item).lower()
        if item.get("visible", True) is not False:
            visible += 1
        if any(word in role for word in ("button", "menu", "link", "tab", "item")) or bool(item.get("clickable")):
            clickable += 1
        if any(word in role for word in ("edit", "input", "text", "search", "combobox")) or "поиск" in label or "search" in label:
            inputs += 1
    return {
        "source": ui_map.get("_source", "unknown"),
        "element_count": len(elements),
        "visible_count": visible,
        "label_count": len([label for label in labels if label]),
        "clickable_count": clickable,
        "input_count": inputs,
        "has_elements": bool(elements),
    }


def _desktop_observe_snapshot() -> Dict[str, Any]:
    try:
        from modules.desktop_observer import observe_desktop

        observed = observe_desktop(write_report=True)
        if isinstance(observed, dict):
            return {
                "ok": bool(observed.get("ok", True)),
                "source": "desktop_observer",
                "payload": observed,
            }
        return {
            "ok": True,
            "source": "desktop_observer",
            "payload": {"text": str(observed)},
        }
    except Exception as exc:
        return {
            "ok": False,
            "source": "desktop_observer_unavailable",
            "error": str(exc),
        }


def _active_window_from_snapshot(snapshot: Dict[str, Any], ui_map: Dict[str, Any]) -> Dict[str, Any]:
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
    for key in ("active_window", "window", "foreground_window", "focused_window"):
        value = payload.get(key)
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str) and value.strip():
            return {"title": value.strip()}
    windows = ui_map.get("windows")
    if isinstance(windows, list) and windows:
        first = windows[0]
        if isinstance(first, dict):
            return dict(first)
        return {"title": str(first)}
    return {"title": "unknown", "app": "unknown"}


def _fingerprint_observation(ui_quality: Dict[str, Any], active_window: Dict[str, Any]) -> str:
    payload = {
        "active_window": active_window,
        "quality": {
            "element_count": ui_quality.get("element_count"),
            "label_count": ui_quality.get("label_count"),
            "clickable_count": ui_quality.get("clickable_count"),
            "input_count": ui_quality.get("input_count"),
            "source": ui_quality.get("source"),
        },
    }
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    import hashlib

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _load_previous_observation() -> Dict[str, Any]:
    ok, data, message = _safe_json_read(LATEST_OBSERVATION_FILE)
    if ok and isinstance(data, dict):
        return data
    return {}


def _stuck_status(current_fingerprint: str, previous: Dict[str, Any]) -> Dict[str, Any]:
    previous_fingerprint = str(previous.get("fingerprint") or "")
    repeat_count = 0
    if previous_fingerprint and previous_fingerprint == current_fingerprint:
        repeat_count = int(previous.get("repeat_count", 0) or 0) + 1
    return {
        "fingerprint": current_fingerprint,
        "previous_fingerprint": previous_fingerprint,
        "repeat_count": repeat_count,
        "possibly_stuck": repeat_count >= 2,
    }


def _score_candidate(goal: str, element: Dict[str, Any]) -> Dict[str, Any]:
    label = _element_label(element)
    role = _element_role(element)
    text = f"{label} {role}".lower()
    goal_lower = goal.lower()
    tokens = [token for token in re_split_words(goal_lower) if len(token) >= 3]
    matches = [token for token in tokens if token in text]
    exact = bool(label and label.lower() in goal_lower)
    role_bonus = 0.0
    if any(word in goal_lower for word in ("нажми", "click", "клик", "открой")) and any(word in role for word in ("button", "link", "menu", "tab")):
        role_bonus += 0.18
    if any(word in goal_lower for word in ("введи", "напиши", "type", "search", "поиск")) and any(word in role for word in ("edit", "input", "text", "search")):
        role_bonus += 0.18
    score = min(0.99, (0.18 * len(matches)) + (0.28 if exact else 0.0) + role_bonus)
    return {
        "label": label,
        "role": role,
        "rect": _rect_value(element),
        "score": round(score, 3),
        "matched_tokens": matches,
        "exact_label_in_goal": exact,
    }


def re_split_words(text: str) -> List[str]:
    result: List[str] = []
    current: List[str] = []
    for char in text:
        if char.isalnum() or char in "_-":
            current.append(char)
        elif current:
            result.append("".join(current))
            current = []
    if current:
        result.append("".join(current))
    return result


def find_target_candidates(goal: str, ui_map: Optional[Dict[str, Any]] = None, limit: int = 8) -> List[Dict[str, Any]]:
    ui_map = ui_map if isinstance(ui_map, dict) else _load_latest_ui_map()
    scored: List[Dict[str, Any]] = []
    for element in _flatten_elements(ui_map):
        candidate = _score_candidate(str(goal or ""), element)
        if candidate["score"] > 0 or candidate["label"]:
            scored.append(candidate)
    scored.sort(key=lambda item: (item.get("score", 0), bool(item.get("rect"))), reverse=True)
    return scored[:limit]


def _write_markdown_report(payload: Dict[str, Any], path: Path) -> None:
    lines = [
        f"# {FEATURE_NAME}",
        "",
        f"- version: {VERSION}",
        f"- timestamp: {payload.get('timestamp')}",
        f"- ok: {payload.get('ok')}",
        f"- mode: {payload.get('mode')}",
        "",
        "## Active Window",
        "```json",
        json.dumps(payload.get("active_window", {}), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## UI Map Quality",
        "```json",
        json.dumps(payload.get("ui_map_quality", {}), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Stuck Detection",
        "```json",
        json.dumps(payload.get("stuck", {}), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
    ]
    if payload.get("goal"):
        lines.extend([
            "## Goal Candidates",
            "```json",
            json.dumps(payload.get("target_candidates", []), ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
        ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def observe_screen_vision(goal: str = "", write_report: bool = True, simulate: bool = False) -> Dict[str, Any]:
    _ensure_dirs()
    if simulate:
        ui_map = {
            "_source": "synthetic_self_check",
            "elements": [
                {"label": "Сохранить", "role": "button", "rect": {"x": 100, "y": 80, "width": 90, "height": 24}},
                {"label": "Поиск", "role": "edit", "rect": {"x": 200, "y": 80, "width": 180, "height": 24}},
                {"label": "Отмена", "role": "button", "rect": {"x": 390, "y": 80, "width": 80, "height": 24}},
            ],
            "windows": [{"title": "Synthetic LocalComet", "app": "LocalComet"}],
        }
        desktop_snapshot = {"ok": True, "source": "synthetic", "payload": {"active_window": {"title": "Synthetic LocalComet", "app": "LocalComet"}}}
    else:
        ui_map = _load_latest_ui_map()
        desktop_snapshot = _desktop_observe_snapshot()
    ui_quality = _ui_map_quality(ui_map)
    active_window = _active_window_from_snapshot(desktop_snapshot, ui_map)
    fingerprint = _fingerprint_observation(ui_quality, active_window)
    previous = _load_previous_observation()
    stuck = _stuck_status(fingerprint, previous)
    candidates = find_target_candidates(goal, ui_map) if goal else []
    payload: Dict[str, Any] = {
        "ok": True,
        "handled": True,
        "mode": "computer_use_observe_vision",
        "version": VERSION,
        "feature": FEATURE_NAME,
        "timestamp": _iso_now(),
        "goal": goal,
        "desktop_snapshot": desktop_snapshot,
        "active_window": active_window,
        "ui_map_quality": ui_quality,
        "target_candidates": candidates,
        "fingerprint": fingerprint,
        "repeat_count": stuck.get("repeat_count", 0),
        "stuck": stuck,
        "next_decision": "continue" if not stuck.get("possibly_stuck") else "replan_or_ask_user",
        "report": "",
    }
    if write_report:
        stamp = _now()
        json_report = VISION_REPORTS_DIR / f"observe_vision_{stamp}.json"
        md_report = VISION_REPORTS_DIR / f"observe_vision_{stamp}.md"
        payload["report"] = str(md_report)
        _safe_json_write(json_report, payload)
        _safe_json_write(LATEST_OBSERVATION_FILE, payload)
        _write_markdown_report(payload, md_report)
        LATEST_REPORT_FILE.write_text(md_report.read_text(encoding="utf-8"), encoding="utf-8")
    return payload


def get_latest_observation() -> Dict[str, Any]:
    _ensure_dirs()
    ok, data, message = _safe_json_read(LATEST_OBSERVATION_FILE)
    if ok and isinstance(data, dict):
        data["handled"] = True
        return data
    return {
        "ok": False,
        "handled": True,
        "mode": "computer_use_observe_vision_latest",
        "version": VERSION,
        "error": message,
        "report": str(LATEST_REPORT_FILE),
    }


def get_status() -> Dict[str, Any]:
    latest = get_latest_observation()
    return {
        "ok": True,
        "handled": True,
        "mode": "computer_use_observe_vision_status",
        "version": VERSION,
        "feature": FEATURE_NAME,
        "reports_dir": str(VISION_REPORTS_DIR),
        "latest_exists": bool(LATEST_OBSERVATION_FILE.exists()),
        "latest_ok": bool(latest.get("ok")),
        "latest_timestamp": latest.get("timestamp"),
        "latest_stuck": latest.get("stuck", {}),
    }


def get_capabilities() -> Dict[str, Any]:
    return {
        "ok": True,
        "handled": True,
        "mode": "computer_use_observe_vision_capabilities",
        "version": VERSION,
        "commands": [
            "pc computer vision status",
            "pc computer vision observe",
            "pc computer vision observe <goal>",
            "pc computer vision latest",
            "pc computer vision report",
            "наблюдай экран",
            "осмотр экрана",
            "статус зрения",
        ],
        "outputs": [
            "active_window",
            "ui_map_quality",
            "target_candidates",
            "fingerprint",
            "stuck detection",
            "markdown/json reports",
        ],
    }


def _is_command(command: str) -> bool:
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
    prefixes = (
        "pc computer vision observe ",
        "pc computer observe vision ",
        "наблюдай экран ",
        "осмотр экрана ",
    )
    return lower.startswith(prefixes)


def handle_dispatch_command(command: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е").strip()
    if not _is_command(text):
        return {"handled": False}
    if lower in {"pc computer vision", "возможности зрения"}:
        return get_capabilities()
    if lower in {"pc computer vision status", "статус зрения"}:
        return get_status()
    if lower in {"pc computer vision latest", "последний осмотр экрана"}:
        return get_latest_observation()
    if lower in {"pc computer vision report", "отчет зрения"}:
        latest = get_latest_observation()
        return {
            "ok": bool(latest.get("ok")),
            "handled": True,
            "mode": "computer_use_observe_vision_report",
            "version": VERSION,
            "report": latest.get("report") or str(LATEST_REPORT_FILE),
            "latest": latest,
        }
    goal = ""
    for prefix in ("pc computer vision observe", "pc computer observe vision", "наблюдай экран", "осмотр экрана"):
        prefix_norm = prefix.lower().replace("ё", "е")
        if lower.startswith(prefix_norm):
            goal = text[len(prefix):].strip(" :,-—")
            break
    return observe_screen_vision(goal=goal, write_report=True, simulate=False)


def run_self_check(write_report: bool = True) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details})

    try:
        observed = observe_screen_vision(goal="нажми Сохранить", write_report=write_report, simulate=True)
        add("synthetic observe ok", bool(observed.get("ok")), observed.get("mode"))
        quality = observed.get("ui_map_quality", {})
        add("synthetic ui map has elements", int(quality.get("element_count", 0) or 0) >= 3, quality)
        candidates = observed.get("target_candidates", [])
        add("target candidates produced", bool(candidates), candidates[:2])
        add("best candidate references save", bool(candidates and "сохран" in str(candidates[0].get("label", "")).lower()), candidates[:2])
        latest = get_latest_observation()
        add("latest observation readable", bool(latest.get("ok")), latest.get("mode"))
        status = get_status()
        add("status ok", bool(status.get("ok")), status)
        capabilities = get_capabilities()
        add("capabilities ok", bool(capabilities.get("ok") and capabilities.get("commands")), capabilities.get("commands"))
        no_public_dispatch = "dispatch" not in globals()
        add("no public dispatch export", no_public_dispatch, sorted([key for key in globals() if key == "dispatch"]))
    except Exception as exc:
        add("self check exception", False, traceback.format_exc())

    failed = len([item for item in checks if not item.get("ok")])
    result = {
        "ok": failed == 0,
        "handled": True,
        "mode": "computer_use_observe_vision_self_check",
        "version": VERSION,
        "summary": {"passed": len(checks) - failed, "total": len(checks), "failed": failed},
        "checks": checks,
        "report": "",
    }
    if write_report:
        _ensure_dirs()
        report = VISION_REPORTS_DIR / f"observe_vision_self_check_{_now()}.json"
        _safe_json_write(report, result)
        result["report"] = str(report)
    return result
