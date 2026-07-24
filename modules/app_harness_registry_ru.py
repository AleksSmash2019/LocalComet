from __future__ import annotations

from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List, Optional

APP_HARNESS_REGISTRY_VERSION = "v6.71"

ROOT_DIR = get_project_root()
if not ROOT_DIR.exists():
    ROOT_DIR = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _registry() -> List[Dict[str, Any]]:
    return [
        {
            "id": "browser",
            "title": "Default web browser",
            "aliases": ["browser", "браузер", "default browser"],
            "risk_class": "MEDIUM",
            "launch_allowed_now": False,
            "confirmation_required": True,
            "real_action_supported_now": False,
            "dry_run_supported": True,
            "allowed_methods": ["Python webbrowser.open (v6.65g allowlist only)"],
            "forbidden_methods": ["shell", "subprocess", "os.system", "Popen"],
            "expected_behavior": "dry-run plan only in v6.68. Real launch requires allowlisted confirmed command.",
            "evidence_files": ["modules/app_harness_registry_ru.py", "LocalComet_Control_Panel.py"],
            "notes": "Real browser opening is already handled by v6.65g confirmed action. App harness is dry-run only.",
        },
        {
            "id": "calculator",
            "title": "Windows Calculator",
            "aliases": ["calculator", "calc", "калькулятор"],
            "risk_class": "MEDIUM",
            "launch_allowed_now": False,
            "confirmation_required": True,
            "real_action_supported_now": True,
            "dry_run_supported": True,
            "allowed_methods": ["subprocess.Popen(['calc.exe'], shell=False)"],
            "forbidden_methods": ["shell", "os.system", "shell=True with Popen"],
            "expected_behavior": "dry-run plan only via app harness. Real launch only via confirmed allowlist command: подтвердить открыть калькулятор",
            "evidence_files": ["modules/app_harness_registry_ru.py", "modules/confirmed_app_actions_ru.py"],
            "notes": "v6.69: Real launch available through confirmed allowlist command only. Plan remains dry-run.",
        },
        {
            "id": "explorer",
            "title": "Windows File Explorer",
            "aliases": ["explorer", "file explorer", "проводник"],
            "risk_class": "MEDIUM",
            "launch_allowed_now": False,
            "confirmation_required": True,
            "real_action_supported_now": True,
            "dry_run_supported": True,
            "allowed_methods": ["subprocess.Popen(['explorer.exe'], shell=False)"],
            "forbidden_methods": ["shell", "os.system", "shell=True with Popen"],
            "expected_behavior": "dry-run plan only via app harness. Real launch only via confirmed allowlist command: подтвердить открыть проводник",
            "evidence_files": ["modules/app_harness_registry_ru.py", "modules/confirmed_app_actions_ru.py"],
            "notes": "v6.71: Real launch available through confirmed allowlist command only. Plan remains dry-run.",
        },
        {
            "id": "notepad",
            "title": "Windows Notepad",
            "aliases": ["notepad", "блокнот"],
            "risk_class": "MEDIUM",
            "launch_allowed_now": False,
            "confirmation_required": True,
            "real_action_supported_now": True,
            "dry_run_supported": True,
            "allowed_methods": ["subprocess.Popen(['notepad.exe'], shell=False)"],
            "forbidden_methods": ["shell", "os.system", "shell=True with Popen"],
            "expected_behavior": "dry-run plan only via app harness. Real launch only via confirmed allowlist command: подтвердить открыть блокнот",
            "evidence_files": ["modules/app_harness_registry_ru.py", "modules/confirmed_app_actions_ru.py"],
            "notes": "v6.70: Real launch available through confirmed allowlist command only. Plan remains dry-run.",
        },
    ]


def get_app_harness_registry() -> List[Dict[str, Any]]:
    return _registry()


def get_app_entry(app_name: str) -> Optional[Dict[str, Any]]:
    lower = str(app_name or "").strip().lower().replace("ё", "е")
    for entry in _registry():
        for alias in entry.get("aliases", []):
            if lower == alias.strip().lower().replace("ё", "е"):
                return entry
    return None


def classify_app_request(command: str) -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    registry_prefixes = ("app harness", "реестр приложений", "app registry")
    if any(lower.startswith(p) for p in registry_prefixes) or lower in {"app harness status"}:
        return {"ok": True, "type": "registry_query", "real_action": False}
    plan_prefixes = ("app harness plan ", "план запуска ")
    for prefix in plan_prefixes:
        if lower.startswith(prefix):
            target = lower[len(prefix):].strip()
            entry = get_app_entry(target)
            if entry:
                return {
                    "ok": True,
                    "type": "dry_run_plan",
                    "app_id": entry["id"],
                    "title": entry["title"],
                    "real_action": False,
                    "launch_allowed_now": entry["launch_allowed_now"],
                }
            return {"ok": False, "type": "unknown_app", "real_action": False}
    return {"ok": False, "type": "unknown", "real_action": False}


def plan_app_action(command: str) -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    plan_prefixes = ("app harness plan ", "план запуска ")
    target = None
    for prefix in plan_prefixes:
        if lower.startswith(prefix):
            target = lower[len(prefix):].strip()
            break
    if not target:
        return {
            "ok": False,
            "mode": "app_harness_plan_error",
            "version": APP_HARNESS_REGISTRY_VERSION,
            "real_action": False,
            "result": "Команда не содержит название приложения. Используйте: app harness plan <app>, план запуска <app>",
        }
    entry = get_app_entry(target)
    if not entry:
        return {
            "ok": False,
            "mode": "app_harness_plan_unknown",
            "version": APP_HARNESS_REGISTRY_VERSION,
            "real_action": False,
            "query": target,
            "result": f"Приложение '{target}' не найдено в реестре. Доступные: {', '.join(e['id'] for e in _registry())}",
        }
    return {
        "ok": True,
        "mode": "app_harness_dry_run_plan",
        "version": APP_HARNESS_REGISTRY_VERSION,
        "real_action": False,
        "app_id": entry["id"],
        "title": entry["title"],
        "launch_allowed_now": entry["launch_allowed_now"],
        "confirmation_required": entry["confirmation_required"],
        "dry_run_supported": entry["dry_run_supported"],
        "plan_summary": f"План (сухой запуск): {entry['title']} — только симуляция. Реальный запуск доступен только через подтверждённую команду (подтвердить открыть {entry['aliases'][0]}).",
        "allowed_methods": entry["allowed_methods"],
        "forbidden_methods": entry["forbidden_methods"],
        "notes": "Этот план не выполняет никаких реальных действий. Реальный запуск доступен через подтверждённую команду (подтвердить открыть).",
    }


def _match_app_harness_command(command: str) -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"app harness status", "app harness registry", "реестр приложений", "app registry"}:
        return True
    if lower.startswith("app harness plan ") or lower.startswith("план запуска "):
        return True
    return False


def _run_app_harness_command(command: str) -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"app harness status", "app harness registry", "реестр приложений", "app registry"}:
        registry = _registry()
        summary = {
            "total_apps": len(registry),
            "launch_allowed_now": sum(1 for e in registry if e["launch_allowed_now"]),
            "dry_run_only": sum(1 for e in registry if not e["launch_allowed_now"]),
            "apps": [
                {
                    "id": e["id"],
                    "title": e["title"],
                    "launch_allowed_now": e["launch_allowed_now"],
                    "confirmation_required": e["confirmation_required"],
                    "real_action_supported_now": e["real_action_supported_now"],
                }
                for e in registry
            ],
        }
        return {
            "mode": "app_harness_registry_summary",
            "version": APP_HARNESS_REGISTRY_VERSION,
            "summary": summary,
            "result": f"Реестр приложений: {summary['total_apps']} приложений, реальный запуск: {summary['launch_allowed_now']}, симуляция: {summary['dry_run_only']}. Реальные запуски только через подтверждённую команду (v6.69).",
        }
    if lower.startswith("app harness plan ") or lower.startswith("план запуска "):
        return plan_app_action(command)
    return {
        "mode": "app_harness_registry_error",
        "version": APP_HARNESS_REGISTRY_VERSION,
        "result": "Неизвестная команда реестра приложений. Используйте: app harness status, реестр приложений, app harness plan <app>, план запуска <app>",
    }


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"status", "app harness status", "pc app harness status"}:
        return status()
    if lower in {"report", "app harness report", "pc app harness report"}:
        return report()
    if _match_app_harness_command(lower):
        return _run_app_harness_command(lower)
    return {
        "mode": "app_harness_unrecognized",
        "version": APP_HARNESS_REGISTRY_VERSION,
        "result": "Команда не распознана. Используйте: app harness status, реестр приложений, app harness plan <app>, план запуска <app>",
    }


def status() -> Dict[str, Any]:
    registry = _registry()
    return {
        "ok": True,
        "mode": "app_harness_registry_status",
        "version": APP_HARNESS_REGISTRY_VERSION,
        "total_apps": len(registry),
        "launch_allowed_now": sum(1 for e in registry if e["launch_allowed_now"]),
        "dry_run_only": sum(1 for e in registry if not e["launch_allowed_now"]),
        "apps": [e["id"] for e in registry],
    }


def report() -> Dict[str, Any]:
    registry = _registry()
    return {
        "ok": True,
        "mode": "app_harness_registry_report",
        "version": APP_HARNESS_REGISTRY_VERSION,
        "generated_at": _now(),
        "entries": registry,
        "status": status(),
        "note": "v6.71 — dry-run plan only. Real launches via confirmed allowlist commands only (calculator v6.69, notepad v6.70, explorer v6.71).",
    }
