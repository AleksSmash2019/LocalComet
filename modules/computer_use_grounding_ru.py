
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
import json
import math
import re
import uuid

GROUNDING_VERSION = "v6.47d"
ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
GROUNDING_DIR = COMPUTER_USE_DIR / "grounding"
LATEST_UI_MAP_PATH = COMPUTER_USE_DIR / "latest_ui_map.json"


ROLE_SYNONYMS = {
    "button": {"button", "btn", "кнопка", "нажми", "click", "клик"},
    "textbox": {"textbox", "input", "edit", "field", "поле", "ввод", "поиск", "search", "editor"},
    "tab": {"tab", "вкладка"},
    "menu": {"menu", "меню"},
    "checkbox": {"checkbox", "check", "чекбокс", "галочка"},
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)
    GROUNDING_DIR.mkdir(parents=True, exist_ok=True)


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
    value = str(text or "").lower().replace("_", " ").replace("-", " ")
    return re.findall(r"[a-zа-яё0-9]+", value, flags=re.IGNORECASE)


def _norm(text: str) -> str:
    return " ".join(_tokens(text))


def _element_text(element: Dict[str, Any]) -> str:
    fields = [
        "text", "label", "name", "title", "value", "placeholder", "automation_id",
        "id", "element_id", "role", "type", "class_name", "description",
    ]
    values = []
    for field in fields:
        value = element.get(field)
        if value is not None:
            values.append(str(value))
    return " ".join(values)


def _extract_bounds(element: Dict[str, Any]) -> Dict[str, int]:
    raw = element.get("bounds") or element.get("rect") or element.get("box") or {}
    if isinstance(raw, list) and len(raw) >= 4:
        x, y, w, h = raw[:4]
        return {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
    if not isinstance(raw, dict):
        raw = {}

    def first(*names: str, default: int = 0) -> int:
        for name in names:
            if name in raw and raw[name] is not None:
                try:
                    return int(float(raw[name]))
                except Exception:
                    pass
            if name in element and element[name] is not None:
                try:
                    return int(float(element[name]))
                except Exception:
                    pass
        return default

    left = first("x", "left")
    top = first("y", "top")
    width = first("w", "width")
    height = first("h", "height")
    right = first("right", default=left + width)
    bottom = first("bottom", default=top + height)

    if width <= 0 and right > left:
        width = right - left
    if height <= 0 and bottom > top:
        height = bottom - top

    return {"x": left, "y": top, "w": max(0, width), "h": max(0, height)}


def _center(bounds: Dict[str, int]) -> Dict[str, int]:
    return {
        "x": int(bounds.get("x", 0) + bounds.get("w", 0) / 2),
        "y": int(bounds.get("y", 0) + bounds.get("h", 0) / 2),
    }


def _extract_elements(payload: Any) -> List[Dict[str, Any]]:
    elements: List[Dict[str, Any]] = []
    if isinstance(payload, dict):
        for key in ("elements", "ui_elements", "items", "nodes"):
            value = payload.get(key)
            if isinstance(value, list):
                elements.extend(item for item in value if isinstance(item, dict))
        backend = payload.get("backend")
        if isinstance(backend, dict):
            elements.extend(_extract_elements(backend))
        ui_map = payload.get("ui_map")
        if isinstance(ui_map, dict):
            elements.extend(_extract_elements(ui_map))
    elif isinstance(payload, list):
        elements.extend(item for item in payload if isinstance(item, dict))

    deduped = []
    seen = set()
    for item in elements:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def _candidate_paths() -> List[Path]:
    paths: List[Path] = []
    if LATEST_UI_MAP_PATH.exists():
        paths.append(LATEST_UI_MAP_PATH)

    runs_dir = COMPUTER_USE_DIR / "runs"
    if runs_dir.exists():
        paths.extend(sorted(runs_dir.glob("run_*/steps/step_*_ui_map.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20])

    return paths


def load_latest_ui_map() -> Dict[str, Any]:
    _ensure_dirs()
    for path in _candidate_paths():
        payload = _read_json(path, {})
        elements = _extract_elements(payload)
        if elements or path == LATEST_UI_MAP_PATH:
            return {
                "ok": True,
                "mode": "computer_use_grounding_load_ui_map",
                "ui_map_path": str(path),
                "payload": payload,
                "elements": elements,
                "element_count": len(elements),
            }

    return {
        "ok": False,
        "mode": "computer_use_grounding_load_ui_map",
        "ui_map_path": "",
        "payload": {},
        "elements": [],
        "element_count": 0,
        "error": "No UI map found. Run pc computer map or pc computer loop first.",
    }


def score_element(description: str, element: Dict[str, Any]) -> Dict[str, Any]:
    query_tokens = set(_tokens(description))
    text_value = _element_text(element)
    element_tokens = set(_tokens(text_value))
    role = str(element.get("role") or element.get("type") or "").lower()

    if not query_tokens:
        overlap_score = 0.0
    else:
        overlap = query_tokens & element_tokens
        overlap_score = len(overlap) / max(1, len(query_tokens))

    substring_score = 0.0
    normalized_description = _norm(description)
    normalized_element = _norm(text_value)
    if normalized_description and normalized_description in normalized_element:
        substring_score = 0.35
    elif normalized_element and normalized_element in normalized_description:
        substring_score = 0.2

    role_score = 0.0
    for canonical_role, words in ROLE_SYNONYMS.items():
        if canonical_role in role or any(word in query_tokens for word in words):
            if canonical_role in role:
                role_score = max(role_score, 0.18)

    bounds = _extract_bounds(element)
    bounds_score = 0.08 if bounds.get("w", 0) > 0 and bounds.get("h", 0) > 0 else 0.0

    try:
        source_conf = float(element.get("confidence", element.get("score", 0.5)))
    except Exception:
        source_conf = 0.5
    source_score = max(0.0, min(1.0, source_conf)) * 0.12

    exact_id_score = 0.0
    element_id = str(element.get("element_id") or element.get("id") or element.get("automation_id") or "").lower()
    if element_id and any(token in element_id for token in query_tokens):
        exact_id_score = 0.18

    total = min(1.0, overlap_score * 0.55 + substring_score + role_score + bounds_score + source_score + exact_id_score)

    return {
        "score": round(total, 4),
        "overlap_score": round(overlap_score, 4),
        "substring_score": round(substring_score, 4),
        "role_score": round(role_score, 4),
        "bounds_score": round(bounds_score, 4),
        "source_score": round(source_score, 4),
        "exact_id_score": round(exact_id_score, 4),
        "bounds": bounds,
        "center": _center(bounds),
        "element_text": text_value,
    }


def find_candidates(description: str, limit: int = 8) -> Dict[str, Any]:
    loaded = load_latest_ui_map()
    elements = loaded.get("elements", [])
    candidates = []
    for index, element in enumerate(elements):
        scored = score_element(description, element)
        candidate = {
            "rank": 0,
            "index": index,
            "score": scored["score"],
            "element_id": element.get("element_id") or element.get("id") or element.get("automation_id") or f"el_{index:03d}",
            "role": element.get("role") or element.get("type") or "",
            "text": element.get("text") or element.get("label") or element.get("name") or element.get("title") or "",
            "bounds": scored["bounds"],
            "center": scored["center"],
            "source": element.get("source", ""),
            "raw": element,
            "score_details": scored,
        }
        candidates.append(candidate)

    candidates.sort(key=lambda item: item["score"], reverse=True)
    for rank, candidate in enumerate(candidates, start=1):
        candidate["rank"] = rank

    path = GROUNDING_DIR / f"find_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    payload = {
        "ok": True,
        "mode": "computer_use_find_candidates",
        "version": GROUNDING_VERSION,
        "description": description,
        "ui_map_path": loaded.get("ui_map_path", ""),
        "element_count": len(elements),
        "candidates": candidates[:limit],
        "created_at": _now(),
    }
    artifact = _write_json(path, payload)
    payload["artifact"] = artifact
    return payload


def ground_element(description: str, min_confidence: float = 0.35) -> Dict[str, Any]:
    found = find_candidates(description, limit=8)
    candidates = found.get("candidates", [])
    best = candidates[0] if candidates else None

    if not best:
        result = {
            "ok": False,
            "mode": "computer_use_ground_element",
            "description": description,
            "reason": "No UI candidates found.",
            "candidates": [],
            "min_confidence": min_confidence,
        }
    elif float(best.get("score", 0.0)) < float(min_confidence):
        result = {
            "ok": False,
            "mode": "computer_use_ground_element",
            "description": description,
            "reason": "Best candidate is below confidence threshold.",
            "best": best,
            "candidates": candidates,
            "min_confidence": min_confidence,
        }
    else:
        bounds = best.get("bounds") or {}
        center = best.get("center") or {}
        result = {
            "ok": True,
            "mode": "computer_use_ground_element",
            "version": GROUNDING_VERSION,
            "description": description,
            "confidence": best["score"],
            "element_id": best["element_id"],
            "role": best.get("role", ""),
            "text": best.get("text", ""),
            "bounds": bounds,
            "center": center,
            "target": {
                "element_id": best["element_id"],
                "element_description": description,
                "window_title": "",
                "x": center.get("x"),
                "y": center.get("y"),
                "x_norm": None,
                "y_norm": None,
                "bounds": bounds,
            },
            "candidate": best,
            "candidates": candidates,
        }

    path = GROUNDING_DIR / f"ground_element_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    result["artifact"] = _write_json(path, result)
    return result


def build_grounded_action(description: str, kind: str = "click", text: str = "", min_confidence: float = 0.35) -> Dict[str, Any]:
    grounded = ground_element(description, min_confidence=min_confidence)
    if not grounded.get("ok"):
        return {
            "ok": False,
            "mode": "computer_use_grounded_action",
            "description": description,
            "kind": kind,
            "reason": grounded.get("reason"),
            "grounding": grounded,
        }

    action = {
        "kind": kind,
        "target": grounded["target"],
        "text": text,
        "grounded": True,
        "confidence": grounded["confidence"],
        "element_id": grounded["element_id"],
        "reason": f"Grounded {kind} action for element: {description}",
    }

    if kind == "type":
        action["focused_target"] = True

    return {
        "ok": True,
        "mode": "computer_use_grounded_action",
        "description": description,
        "kind": kind,
        "action": action,
        "grounding": grounded,
    }


def status() -> Dict[str, Any]:
    loaded = load_latest_ui_map()
    return {
        "ok": True,
        "mode": "computer_use_grounding_status",
        "version": GROUNDING_VERSION,
        "ui_map_path": loaded.get("ui_map_path", ""),
        "element_count": loaded.get("element_count", 0),
        "grounding_dir": str(GROUNDING_DIR),
    }


def report() -> Dict[str, Any]:
    return status()


def is_computer_use_grounding_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = [
        "pc computer find",
        "pc computer ground",
        "computer find",
        "computer ground",
        "найди элемент",
        "заземли элемент",
    ]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def dispatch(command: str) -> Dict[str, Any]:
    raw = (command or "").strip()
    value = raw.lower()

    if value in {"pc computer grounding status", "computer grounding status"}:
        return status()

    if value.startswith("pc computer find "):
        return find_candidates(raw[len("pc computer find "):].strip())

    if value.startswith("computer find "):
        return find_candidates(raw[len("computer find "):].strip())

    if value.startswith("найди элемент "):
        return find_candidates(raw[len("найди элемент "):].strip())

    if value.startswith("pc computer ground "):
        return ground_element(raw[len("pc computer ground "):].strip())

    if value.startswith("computer ground "):
        return ground_element(raw[len("computer ground "):].strip())

    if value.startswith("заземли элемент "):
        return ground_element(raw[len("заземли элемент "):].strip())

    return {
        "ok": False,
        "mode": "computer_use_grounding_unknown_command",
        "command": command,
    }
