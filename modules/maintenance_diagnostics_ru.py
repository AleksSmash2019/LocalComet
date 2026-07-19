from __future__ import annotations

import ast
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


MAINTENANCE_DIAGNOSTICS_VERSION = "v6.81"


def _project_root() -> Path:
    for env_name in ("LOCALCOMET_ROOT", "LOCALCOMET_ROOT_DIR"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return Path(value).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


ROOT_DIR = _project_root()


def _redact(value: Any) -> str:
    text = str(value or "")
    home = str(Path.home())
    home_posix = home.replace("\\", "/")
    for marker in (home, home_posix, str(ROOT_DIR), ROOT_DIR.as_posix()):
        if marker:
            text = text.replace(marker, "<PROJECT_ROOT>")
    return text


def _warning(category: str, exc: Exception | None = None) -> str:
    if exc is None:
        return category
    return f"{category}:{type(exc).__name__}"


def is_diagnostics_command(command: str = "") -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {
        "диагностика проекта",
        "project diagnostics",
        "maintenance status",
    }


def _run_git_count(args: list[str]) -> tuple[bool, int, str | None]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
            check=False,
        )
    except Exception as exc:
        return False, 0, _warning("git_unavailable", exc)
    if result.returncode != 0:
        return False, 0, "git_command_failed"
    return True, len([line for line in result.stdout.splitlines() if line.strip()]), None


def _git_section(warnings: list[str]) -> dict[str, Any]:
    status_ok, tracked_changed, status_warning = _run_git_count(["status", "--short", "--untracked-files=no"])
    staged_ok, staged_count, staged_warning = _run_git_count(["diff", "--cached", "--name-only"])
    untracked_ok, untracked_count, untracked_warning = _run_git_count(["ls-files", "--others", "--exclude-standard"])
    for item in (status_warning, staged_warning, untracked_warning):
        if item:
            warnings.append(item)
    available = status_ok and staged_ok and untracked_ok
    return {
        "available": available,
        "tracked_changed_count": tracked_changed,
        "staged_count": staged_count,
        "untracked_count": untracked_count,
        "untracked_ignored_for_risk": True,
        "hold_expected": bool(tracked_changed or staged_count),
    }


def _safety_section(warnings: list[str]) -> dict[str, Any]:
    try:
        from modules.development_safety_orchestrator_ru import status

        payload = status()
        evaluation = payload.get("evaluation", {})
        gates = evaluation.get("gates", {})
        strict = gates.get("strict", {})
        contracts = gates.get("contracts", {})
        return {
            "available": True,
            "lightweight": evaluation.get("lightweight") is True,
            "verdict": str(evaluation.get("overall_verdict") or ""),
            "strict_executed": bool(strict.get("executed", False)),
            "contracts_executed": bool(contracts.get("executed", False)),
        }
    except Exception as exc:
        warnings.append(_warning("safety_status_unavailable", exc))
        return {
            "available": False,
            "lightweight": False,
            "verdict": "UNKNOWN",
            "strict_executed": False,
            "contracts_executed": False,
        }


def _router_section(warnings: list[str]) -> dict[str, Any]:
    panel_path = ROOT_DIR / "LocalComet_Control_Panel.py"
    result = {
        "registry_present": False,
        "dispatcher_definition_count": 0,
        "route_count": 0,
        "diagnostics_route_present": False,
    }
    try:
        text = panel_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
        result["dispatcher_definition_count"] = sum(
            1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "run_panel_chat_command"
        )
        result["registry_present"] = "PANEL_ROUTES" in text
        result["diagnostics_route_present"] = "maintenance_diagnostics_ru_v681" in text
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if any(isinstance(target, ast.Name) and target.id == "PANEL_ROUTES" for target in node.targets):
                    if isinstance(node.value, (ast.Tuple, ast.List)):
                        result["route_count"] = len(node.value.elts)
                    break
    except Exception as exc:
        warnings.append(_warning("router_static_read_failed", exc))
    return result


def _retention_section(warnings: list[str]) -> dict[str, Any]:
    try:
        from modules import project_paths

        return {
            "available": True,
            "dry_run": True,
            "max_age_days": int(project_paths.DEFAULT_RETENTION_MAX_AGE_DAYS),
            "max_items_per_group": int(project_paths.DEFAULT_RETENTION_MAX_ITEMS_PER_GROUP),
        }
    except Exception as exc:
        warnings.append(_warning("retention_defaults_unavailable", exc))
        return {
            "available": False,
            "dry_run": True,
            "max_age_days": 7,
            "max_items_per_group": 200,
        }


def _manifest_section(warnings: list[str]) -> dict[str, Any]:
    path = ROOT_DIR / "localcomet_runtime_manifest.json"
    if not path.exists():
        warnings.append("runtime_manifest_missing")
        return {
            "manifest_present": False,
            "manifest_release": "",
            "runtime_count": 0,
            "lazy_runtime_count": 0,
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "manifest_present": True,
            "manifest_release": str(data.get("release", "")),
            "runtime_count": len(data.get("runtime", [])) if isinstance(data.get("runtime", []), list) else 0,
            "lazy_runtime_count": len(data.get("lazy_runtime", [])) if isinstance(data.get("lazy_runtime", []), list) else 0,
        }
    except Exception as exc:
        warnings.append(_warning("runtime_manifest_parse_failed", exc))
        return {
            "manifest_present": False,
            "manifest_release": "",
            "runtime_count": 0,
            "lazy_runtime_count": 0,
        }


def _audit_bundle_section(warnings: list[str]) -> dict[str, Any]:
    creator = ROOT_DIR / "tools" / "create_project_audit_bundle.py"
    verifier = ROOT_DIR / "tools" / "verify_project_audit_bundle.py"
    creator_present = creator.exists()
    verifier_present = verifier.exists()
    if not creator_present:
        warnings.append("audit_bundle_creator_missing")
    if not verifier_present:
        warnings.append("audit_bundle_verifier_missing")
    return {
        "creator_present": creator_present,
        "verifier_present": verifier_present,
        "latest_bundle_known": False,
        "latest_bundle_id": None,
    }


def _tests_section() -> dict[str, Any]:
    tools = ROOT_DIR / "tools"
    return {
        "v677_present": (tools / "test_v677_regression.py").exists(),
        "v678_present": (tools / "test_v678_router_registry.py").exists(),
        "v679_present": (tools / "test_v679_retention.py").exists(),
        "v680_present": (ROOT_DIR / "localcomet_runtime_manifest.json").exists(),
        "v6801_present": (tools / "test_v6801_audit_bundle.py").exists(),
        "v6802_present": (tools / "test_v6802_bundle_security.py").exists(),
        "executed_now": False,
    }


def diagnostics_status() -> dict[str, Any]:
    started = time.perf_counter()
    warnings: list[str] = []
    manifest = _manifest_section(warnings)
    result = {
        "mode": "maintenance_diagnostics_status",
        "version": MAINTENANCE_DIAGNOSTICS_VERSION,
        "ok": True,
        "project": {
            "release": MAINTENANCE_DIAGNOSTICS_VERSION,
            "root": "<PROJECT_ROOT>",
            "portable_root": True,
        },
        "router": _router_section(warnings),
        "git": _git_section(warnings),
        "safety": _safety_section(warnings),
        "retention": _retention_section(warnings),
        "preflight": manifest,
        "audit_bundle": _audit_bundle_section(warnings),
        "tests": _tests_section(),
        "warnings": sorted(set(_redact(item) for item in warnings)),
    }
    elapsed = time.perf_counter() - started
    if elapsed > 0.5:
        result["warnings"] = sorted(set([*result["warnings"], "diagnostics_runtime_over_0_5s"]))
    return result


def dispatch(command: str = "") -> dict[str, Any]:
    if not is_diagnostics_command(command):
        return {
            "mode": "maintenance_diagnostics_unrecognized",
            "version": MAINTENANCE_DIAGNOSTICS_VERSION,
            "ok": False,
            "warnings": ["unknown_diagnostics_command"],
        }
    return diagnostics_status()
