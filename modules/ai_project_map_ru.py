from __future__ import annotations

import ast
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_PATH = Path(__file__).resolve().parents[1]
MEMORY_DIR = ROOT_PATH / "Projects" / "AgentMemory"
PROJECT_MAP_PATH = MEMORY_DIR / "project_map.json"

BLOCKED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "BrowserProfile",
    "Backups",
    "LocalAgent_Backups",
}

COMMAND_HINT_RE = re.compile(
    r"(pc\s+[a-z0-9_\-]+\s+[a-z0-9_\-]+|pc\s+[a-z0-9_\-]+|агент\s+[а-яa-z0-9_\-]+|проверь\s+проект)",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_PATH)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _is_skipped(path: Path) -> bool:
    return bool(set(path.parts).intersection(BLOCKED_DIRS))


def _read_text(path: Path, limit: int = 30000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    if len(text) > limit:
        return text[:limit] + "\n\n[truncated]"
    return text


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        digest.update(path.read_bytes())
    except Exception:
        digest.update(str(path).encode("utf-8", errors="replace"))
    return digest.hexdigest()


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT_PATH.rglob("*.py"):
        if _is_skipped(path):
            continue
        if path.name.startswith("."):
            continue
        files.append(path)
    return sorted(files, key=lambda item: _safe_relative(item).lower())


def _extract_module_info(path: Path) -> dict[str, Any]:
    rel = _safe_relative(path)
    text = _read_text(path)
    lowered = text.lower().replace("ё", "е")

    info: dict[str, Any] = {
        "path": rel,
        "sha256": _sha256(path),
        "size": path.stat().st_size if path.exists() else 0,
        "parse_ok": False,
        "parse_error": "",
        "functions": [],
        "classes": [],
        "imports": [],
        "commands": sorted(set(COMMAND_HINT_RE.findall(text)))[:60],
        "has_dispatch": False,
        "has_status": False,
        "has_report": False,
        "is_command_module": False,
        "is_ui_module": False,
        "is_verification_module": False,
        "is_relay_module": False,
        "is_agent_module": False,
        "is_safety_module": False,
    }

    try:
        tree = ast.parse(text, filename=rel)
    except Exception as exc:
        info["parse_error"] = str(exc)
        return info

    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    info["parse_ok"] = True
    info["functions"] = sorted(set(functions))
    info["classes"] = sorted(set(classes))
    info["imports"] = sorted(set(imports))[:120]
    info["has_dispatch"] = "dispatch" in info["functions"]
    info["has_status"] = "status" in info["functions"]
    info["has_report"] = "report" in info["functions"]
    info["is_command_module"] = bool(info["has_dispatch"] or info["commands"])
    info["is_ui_module"] = any(marker in lowered for marker in ("tkinter", "ttk.", "tk.", "_render_", "window.title", "вкладка"))
    info["is_verification_module"] = any(marker in lowered for marker in ("verification", "stability", "провер", "hard_failures", "warnings"))
    info["is_relay_module"] = any(marker in lowered for marker in ("chatgptrelay", "response.json", "selfedit", "relay"))
    info["is_agent_module"] = any(marker in lowered for marker in ("ai_agent", "agent", "codex", "project_map", "draft_patch", "агент"))
    info["is_safety_module"] = any(marker in lowered for marker in ("danger", "blocked", "password", "token", "powershell", "delete"))
    return info


def _control_panel_info() -> dict[str, Any]:
    path = ROOT_PATH / "LocalComet_Control_Panel.py"
    text = _read_text(path, limit=70000)
    info: dict[str, Any] = {
        "path": _safe_relative(path),
        "exists": path.exists(),
        "version": "",
        "label": "",
        "routes": [],
        "auto_open_task_panel_count": text.count("auto_open_task_panel_if_enabled"),
    }

    version_match = re.search(r"LOCALCOMET_VERSION\s*=\s*['\"]([^'\"]+)['\"]", text)
    label_match = re.search(r"LOCALCOMET_VERSION_LABEL\s*=\s*['\"]([^'\"]+)['\"]", text)
    if version_match:
        info["version"] = version_match.group(1)
    if label_match:
        info["label"] = label_match.group(1)

    for match in re.finditer(r'route_name\s*=\s*["\']([^"\']+)["\']', text):
        info["routes"].append(match.group(1))
    info["routes"] = sorted(set(info["routes"]))
    return info


def build_project_map() -> dict[str, Any]:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    modules = [_extract_module_info(path) for path in _iter_python_files()]
    command_modules = [item for item in modules if item.get("is_command_module")]
    ui_modules = [item for item in modules if item.get("is_ui_module")]
    verification_modules = [item for item in modules if item.get("is_verification_module")]
    relay_modules = [item for item in modules if item.get("is_relay_module")]
    agent_modules = [item for item in modules if item.get("is_agent_module")]
    parse_errors = [item for item in modules if not item.get("parse_ok")]
    critical_parse_errors = [
        item for item in parse_errors
        if item.get("path") == "LocalComet_Control_Panel.py"
        or str(item.get("path", "")).startswith("modules/")
        or str(item.get("path", "")).startswith("core/")
    ]

    relation_map = {
        "command_modules": [item["path"] for item in command_modules],
        "ui_modules": [item["path"] for item in ui_modules],
        "verification_modules": [item["path"] for item in verification_modules],
        "relay_modules": [item["path"] for item in relay_modules],
        "agent_modules": [item["path"] for item in agent_modules],
        "safety_modules": [item["path"] for item in modules if item.get("is_safety_module")],
    }

    project_map = {
        "ok": True,
        "mode": "ai_project_map",
        "diagnostic_ok_policy": "project map is diagnostic; strict_project_stability_ru remains the runtime gate",
        "generated_at": _now(),
        "root": str(ROOT_PATH),
        "project_map_path": str(PROJECT_MAP_PATH),
        "control_panel": _control_panel_info(),
        "python_file_count": len(modules),
        "function_count": sum(len(item.get("functions", [])) for item in modules),
        "class_count": sum(len(item.get("classes", [])) for item in modules),
        "command_module_count": len(command_modules),
        "ui_module_count": len(ui_modules),
        "verification_module_count": len(verification_modules),
        "relay_module_count": len(relay_modules),
        "agent_module_count": len(agent_modules),
        "parse_error_count": len(parse_errors),
        "critical_parse_error_count": len(critical_parse_errors),
        "parse_warnings": parse_errors[:30],
        "critical_parse_errors": critical_parse_errors[:30],
        "runtime_gate": "Use strict_project_stability_ru / проверь проект for blocking decisions.",
        "modules": modules,
        "command_registry": command_modules,
        "ui_registry": ui_modules,
        "verification_registry": verification_modules,
        "relay_registry": relay_modules,
        "agent_registry": agent_modules,
        "relation_map": relation_map,
        "recommended_focus": [
            "ai_agent_core_ru",
            "ai_project_map_ru",
            "ai_patch_planner_ru",
            "ai_agent_memory_ru",
            "strict_project_stability_ru",
            "premium_task_panel_ru",
            "LocalComet_Control_Panel.py",
        ],
    }

    PROJECT_MAP_PATH.write_text(json.dumps(project_map, ensure_ascii=False, indent=2), encoding="utf-8")
    return project_map


def status() -> dict[str, Any]:
    project_map = build_project_map()
    return {
        "ok": bool(project_map.get("ok")),
        "mode": "ai_project_map_status",
        "generated_at": _now(),
        "project_map_path": str(PROJECT_MAP_PATH),
        "python_file_count": project_map.get("python_file_count"),
        "function_count": project_map.get("function_count"),
        "command_module_count": project_map.get("command_module_count"),
        "ui_module_count": project_map.get("ui_module_count"),
        "verification_module_count": project_map.get("verification_module_count"),
        "agent_module_count": project_map.get("agent_module_count"),
        "parse_error_count": project_map.get("parse_error_count"),
        "critical_parse_error_count": project_map.get("critical_parse_error_count"),
    }


def report() -> dict[str, Any]:
    project_map = build_project_map()
    return {
        "ok": bool(project_map.get("ok")),
        "mode": "ai_project_map_report",
        "generated_at": _now(),
        "project_map_path": str(PROJECT_MAP_PATH),
        "control_panel": project_map.get("control_panel"),
        "relation_map": project_map.get("relation_map"),
        "summary": {
            "python_file_count": project_map.get("python_file_count"),
            "function_count": project_map.get("function_count"),
            "command_module_count": project_map.get("command_module_count"),
            "ui_module_count": project_map.get("ui_module_count"),
            "verification_module_count": project_map.get("verification_module_count"),
            "agent_module_count": project_map.get("agent_module_count"),
            "parse_error_count": project_map.get("parse_error_count"),
            "critical_parse_error_count": project_map.get("critical_parse_error_count"),
        },
    }


def dispatch(command: str) -> dict[str, Any]:
    text = str(command or "").strip().lower().replace("ё", "е")
    if text in {"pc ai project map", "pc ai context", "агент контекст", "проанализируй проект"}:
        return build_project_map()
    if text in {"pc ai project map status", "карта проекта статус"}:
        return status()
    if text in {"pc ai project map report", "карта проекта отчет", "карта проекта отчёт"}:
        return report()
    return {
        "ok": False,
        "mode": "ai_project_map_unknown_command",
        "generated_at": _now(),
        "command": command,
        "hint": "Используй: pc ai context",
    }


def is_ai_project_map_command(command: str) -> bool:
    text = str(command or "").strip().lower().replace("ё", "е")
    return text in {"pc ai project map", "pc ai context", "агент контекст", "проанализируй проект", "pc ai project map status", "pc ai project map report"}
