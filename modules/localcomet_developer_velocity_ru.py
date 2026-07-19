from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


DEVELOPER_VELOCITY_VERSION = "v6.58"
DEVELOPER_VELOCITY_NAME = "LocalComet Developer Velocity Toolkit Lite RU"


COMMAND_ALIASES = {
    "последний сбой": "first_failure",
    "последняя ошибка": "first_failure",
    "first failure": "first_failure",
    "last failure": "first_failure",
    "события патча": "patch_events",
    "таймлайн патча": "patch_events",
    "patch events": "patch_events",
    "patch timeline": "patch_events",
    "статус разработки": "green_gate",
    "статус проекта": "green_gate",
    "green gate": "green_gate",
    "green gate status": "green_gate",
    "dev status": "green_gate",
    "debug пакет": "debug_package",
    "собрать debug пакет": "debug_package",
    "debug package": "debug_package",
    "пакет отладки": "debug_package",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def is_developer_velocity_command(command: str) -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in COMMAND_ALIASES or lower in {"developer velocity", "velocity status", "velocity report", "help velocity"}


def status(command: str = "status") -> Dict[str, Any]:
    return {
        "ok": True,
        "handled": True,
        "mode": "developer_velocity_status",
        "version": DEVELOPER_VELOCITY_VERSION,
        "commands": sorted(COMMAND_ALIASES.keys()),
        "modules": [
            "modules.first_failure_extractor_ru",
            "modules.patch_event_timeline_ru",
            "modules.green_gate_status_ru",
            "modules.debug_package_ru",
        ],
    }


def report(command: str = "report") -> Dict[str, Any]:
    from modules.green_gate_status_ru import get_green_gate_status
    from modules.first_failure_extractor_ru import find_latest_failure
    return {
        "ok": True,
        "handled": True,
        "mode": "developer_velocity_report",
        "version": DEVELOPER_VELOCITY_VERSION,
        "generated_at": _now(),
        "green_gate": get_green_gate_status(write_report=True),
        "first_failure": find_latest_failure(write_report=True),
    }


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    target = COMMAND_ALIASES.get(lower, "")
    if lower in {"developer velocity", "velocity status", "help velocity"}:
        return status(command)
    if lower in {"velocity report", "developer velocity report"}:
        return report(command)

    if target == "first_failure":
        from modules.first_failure_extractor_ru import dispatch as _dispatch
        result = _dispatch(command)
    elif target == "patch_events":
        from modules.patch_event_timeline_ru import dispatch as _dispatch
        result = _dispatch(command)
    elif target == "green_gate":
        from modules.green_gate_status_ru import dispatch as _dispatch
        result = _dispatch(command)
    elif target == "debug_package":
        from modules.debug_package_ru import dispatch as _dispatch
        result = _dispatch(command)
    else:
        return {"ok": False, "handled": False, "mode": "developer_velocity", "version": DEVELOPER_VELOCITY_VERSION, "reason": "unknown command"}

    if isinstance(result, dict):
        result["handled"] = True
        result.setdefault("developer_velocity_version", DEVELOPER_VELOCITY_VERSION)
        return result
    return {"ok": False, "handled": True, "mode": "developer_velocity", "version": DEVELOPER_VELOCITY_VERSION, "reason": "target returned non-dict", "value": str(result)[:1000]}
