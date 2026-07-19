
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator
import json
import uuid

from modules.project_paths import (
    PROJECT_PATHS_VERSION,
    computer_use_latest_ui_map_path,
    computer_use_test_fixtures_dir,
    ensure_dirs,
)


TEST_FIXTURES_VERSION = "v6.47i"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def canonical_ui_map() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "computer_use_contract_synthetic_ui_map",
        "version": TEST_FIXTURES_VERSION,
        "created_at": _now(),
        "source": "computer_use_test_fixtures_ru",
        "elements": [
            {
                "element_id": "btn_save",
                "role": "button",
                "text": "Сохранить",
                "bounds": {"x": 100, "y": 200, "w": 120, "h": 40},
                "confidence": 0.95,
                "source": "contract_fixture",
            },
            {
                "element_id": "field_search",
                "role": "textbox",
                "text": "Поиск",
                "bounds": {"x": 20, "y": 50, "w": 300, "h": 30},
                "confidence": 0.92,
                "source": "contract_fixture",
            },
            {
                "element_id": "field_chat",
                "role": "editor",
                "text": "Сообщение",
                "bounds": {"x": 40, "y": 310, "w": 520, "h": 90},
                "confidence": 0.88,
                "source": "contract_fixture",
            },
        ],
        "limitations": [],
    }


def write_fixture_file(name: str = "canonical_ui_map", payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    fixture_dir = computer_use_test_fixtures_dir()
    ensure_dirs([fixture_dir])
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name).strip("_") or "fixture"
    path = fixture_dir / f"{safe_name}.json"
    data = payload or canonical_ui_map()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "mode": "computer_use_write_fixture_file",
        "version": TEST_FIXTURES_VERSION,
        "path": str(path),
        "element_count": len(data.get("elements", [])),
    }


def _read_bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


@contextmanager
def temporary_latest_ui_map(payload: Dict[str, Any] | None = None, label: str = "contract") -> Iterator[Dict[str, Any]]:
    latest_path = computer_use_latest_ui_map_path()
    ensure_dirs([latest_path.parent, computer_use_test_fixtures_dir()])

    existed_before = latest_path.exists()
    original_bytes = _read_bytes(latest_path)
    data = payload or canonical_ui_map()
    data = dict(data)
    data["fixture_label"] = label
    data["fixture_started_at"] = _now()

    latest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    fixture_path = computer_use_test_fixtures_dir() / f"latest_ui_map_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    fixture_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    info = {
        "ok": True,
        "mode": "temporary_latest_ui_map",
        "version": TEST_FIXTURES_VERSION,
        "latest_path": str(latest_path),
        "fixture_path": str(fixture_path),
        "existed_before": existed_before,
        "element_count": len(data.get("elements", [])),
    }

    try:
        yield info
    finally:
        if existed_before and original_bytes is not None:
            latest_path.write_bytes(original_bytes)
        elif latest_path.exists():
            latest_path.unlink()


@contextmanager
def temporary_synthetic_ui_map(label: str = "contract") -> Iterator[Dict[str, Any]]:
    with temporary_latest_ui_map(canonical_ui_map(), label=label) as info:
        yield info


def verify_restore_behavior() -> Dict[str, Any]:
    latest_path = computer_use_latest_ui_map_path()
    existed_before = latest_path.exists()
    before_bytes = latest_path.read_bytes() if existed_before else None

    with temporary_synthetic_ui_map(label="restore_check") as info:
        during = json.loads(latest_path.read_text(encoding="utf-8"))
        if len(during.get("elements", [])) < 2:
            return {
                "ok": False,
                "mode": "computer_use_fixture_restore_check",
                "reason": "fixture was not written correctly",
                "info": info,
            }

    existed_after = latest_path.exists()
    after_bytes = latest_path.read_bytes() if existed_after else None

    restored = (existed_before == existed_after) and (before_bytes == after_bytes)
    return {
        "ok": restored,
        "mode": "computer_use_fixture_restore_check",
        "version": TEST_FIXTURES_VERSION,
        "existed_before": existed_before,
        "existed_after": existed_after,
        "restored": restored,
        "latest_path": str(latest_path),
    }


def status() -> Dict[str, Any]:
    fixture_dir = computer_use_test_fixtures_dir()
    latest_path = computer_use_latest_ui_map_path()
    return {
        "ok": True,
        "mode": "computer_use_test_fixtures_status",
        "version": TEST_FIXTURES_VERSION,
        "project_paths_version": PROJECT_PATHS_VERSION,
        "fixture_dir": str(fixture_dir),
        "latest_path": str(latest_path),
        "latest_exists": latest_path.exists(),
    }


def report() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "computer_use_test_fixtures_report",
        "status": status(),
        "restore_check": verify_restore_behavior(),
    }
