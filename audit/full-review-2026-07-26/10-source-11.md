# Полный исходный код (продолжение)

### ПУТЬ: modules/ai_project_map_ru.py (302 строк, 11933 байт)

````python
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
````

### ПУТЬ: modules/app_harness_registry_ru.py (244 строк, 11774 байт)

````python
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
````

### ПУТЬ: modules/auto_verification.py (315 строк, 8882 байт)

````python
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from time import perf_counter

from core.state import set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
AUTO_VERIFY_REPORTS_DIR = REPORTS_DIR / "auto_verification"

KEY_PY_FILES = [
    "LocalComet_Control_Panel.py",
    "next/app_v5.py",
    "core/router.py",
    "core/planner.py",
    "core/executor.py",
    "core/llm.py",
    "agents/system_agent.py",
    "agents/browser_agent.py",
    "agents/stability_agent.py",
    "agents/automation_agent.py",
    "modules/auto_verification.py",
    "modules/browser_super.py",
    "modules/browser_direct.py",
    "modules/natural_command_intents.py",
    "modules/project_health.py",
    "modules/regression_commands.py",
    "modules/stability_test.py",
    "modules/automation_center.py",
]


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value, limit=2200):
    text = str(value or "")

    if len(text) <= limit:
        return text

    return text[:limit] + "\n...[обрезано]"


def _run_step(name, runner, checker=None):
    started = perf_counter()

    try:
        output = str(runner())
        ok = bool(checker(output)) if checker else bool(output.strip())
        error = ""
    except Exception:
        output = ""
        ok = False
        error = traceback.format_exc()

    return {
        "name": name,
        "ok": ok,
        "duration_sec": round(perf_counter() - started, 3),
        "output": _short(output),
        "error": _short(error),
    }


def _git_changed_python_files():
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return []

    files = []

    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        path = line[3:].strip() if len(line) > 3 else line

        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()

        path = path.strip('"')

        if path.endswith(".py") and (ROOT_DIR / path).exists():
            files.append(path.replace("\\", "/"))

    return files


def _unique_existing(files):
    seen = set()
    result = []

    for path in files:
        normalized = str(path).replace("\\", "/")

        if normalized in seen:
            continue

        if (ROOT_DIR / normalized).exists():
            seen.add(normalized)
            result.append(normalized)

    return result


def get_auto_verification_files():
    return _unique_existing([*_git_changed_python_files(), *KEY_PY_FILES])


def _run_py_compile():
    files = get_auto_verification_files()

    if not files:
        return "Нет Python-файлов для py_compile."

    result = subprocess.run(
        ["python", "-m", "py_compile", *files],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )

    return (
        f"CODE: {result.returncode}\n"
        f"FILES: {len(files)}\n"
        + "\n".join(f"- {path}" for path in files)
        + f"\n\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def _run_lmstudio_diagnostics():
    from modules.diagnostics import check_lmstudio

    return check_lmstudio()


def _run_model_smoke():
    from core.llm import ask_llm

    answer = ask_llm(
        "Ты тестовый ассистент LocalComet.",
        "Ответь ровно одним словом: OK",
        max_tokens=50,
        timeout=90,
    )
    return repr(answer)


def _run_project_health():
    from modules.project_health import format_project_health_text

    return format_project_health_text()


def _run_regression_suite():
    from modules.regression_commands import format_regression_command_suite, run_regression_command_suite

    suite = run_regression_command_suite(write_report=False)
    return format_regression_command_suite(suite)


def _run_stability(mode):
    from modules.stability_test import run_auto_stability_test, run_fast_stability_test

    if mode == "full":
        return run_auto_stability_test()

    return run_fast_stability_test()


def run_auto_verification(mode="quick", write_report=True):
    mode = str(mode or "quick").strip().lower()

    if mode not in ["smoke", "quick", "full", "post_patch"]:
        mode = "quick"

    steps = [
        _run_step("py_compile", _run_py_compile, lambda r: "CODE: 0" in r),
    ]

    if mode != "smoke":
        steps.extend([
            _run_step("lmstudio diagnostics", _run_lmstudio_diagnostics, lambda r: "текущая модель" in r and "доступна" in r),
            _run_step("model smoke", _run_model_smoke, lambda r: "OK" in r),
            _run_step("project health", _run_project_health, lambda r: "Project Health Center:" in r),
            _run_step("regression suite", _run_regression_suite, lambda r: "status: ok" in r and "Problems:" in r),
        ])

    if mode in ["full", "post_patch"]:
        stability_mode = "full"
        steps.append(
            _run_step(
                f"{stability_mode} stability",
                lambda: _run_stability(stability_mode),
                lambda r: "Проблемы:\n- Не обнаружены." in r,
            )
        )

    passed = sum(1 for step in steps if step["ok"])
    total = len(steps)
    status = "ok" if passed == total else "failed"

    result = {
        "status": status,
        "mode": mode,
        "passed": passed,
        "total": total,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "steps": steps,
        "report": "",
    }

    if write_report:
        result["report"] = str(write_auto_verification_report(result))

    set_value("last_auto_verification_status", status)
    set_value("last_auto_verification_score", f"{passed}/{total}")
    set_value("last_auto_verification_mode", mode)
    set_value("last_auto_verification_generated_at", result["generated_at"])
    set_value("last_auto_verification_report", result.get("report", ""))

    return result


def format_auto_verification(result=None):
    result = result or run_auto_verification(write_report=False)

    lines = [
        "Auto Verification:",
        f"- status: {result.get('status')}",
        f"- mode: {result.get('mode')}",
        f"- score: {result.get('passed')}/{result.get('total')}",
        f"- generated_at: {result.get('generated_at')}",
    ]

    if result.get("report"):
        lines.append(f"- report: {result.get('report')}")

    lines.extend(["", "Checks:"])

    for step in result.get("steps", []):
        mark = "OK" if step.get("ok") else "FAIL"
        lines.append(f"- [{mark}] {step.get('name')} | {step.get('duration_sec')}s")

        if step.get("error"):
            lines.append(f"  error: {_short(step.get('error'), 300)}")

    problems = [step for step in result.get("steps", []) if not step.get("ok")]
    lines.extend(["", "Problems:"])

    if problems:
        for step in problems:
            lines.append(f"- {step.get('name')}")
    else:
        lines.append("- Не обнаружены.")

    return "\n".join(lines)


def write_auto_verification_report(result=None):
    result = result or run_auto_verification(write_report=False)
    AUTO_VERIFY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = AUTO_VERIFY_REPORTS_DIR / f"auto_verification_{_stamp()}.md"

    lines = ["# Auto Verification", "", format_auto_verification(result), ""]

    for step in result.get("steps", []):
        mark = "OK" if step.get("ok") else "FAIL"
        lines.extend([
            f"## [{mark}] {step.get('name')}",
            "",
            f"- duration_sec: {step.get('duration_sec')}",
            "",
            "```text",
            step.get("output", "") or step.get("error", ""),
            "```",
            "",
        ])

    path.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_auto_verification_report", str(path))
    return path


def latest_auto_verification_report():
    if not AUTO_VERIFY_REPORTS_DIR.exists():
        return None

    reports = [
        path
        for path in AUTO_VERIFY_REPORTS_DIR.glob("auto_verification_*.md")
        if path.is_file()
    ]

    if not reports:
        return None

    return max(reports, key=lambda path: path.stat().st_mtime)
````

### ПУТЬ: modules/automation_center.py (890 строк, 27268 байт)

````python
import re
import subprocess
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value, get_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
WINDOWS_DIR = PROJECTS_DIR / "Windows"


def _ensure_reports_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(text, limit: int = 2500):
    value = str(text or "")

    if len(value) <= limit:
        return value

    return value[:limit] + "\n\n...[обрезано]"


def _has_bad_result(text: str):
    value = str(text or "").lower()

    bad_markers = [
        "неизвестное действие",
        "не удалось",
        "error:",
        "error",
        "ошибка:",
        "ошибка",
        "traceback",
        "unknown",
    ]

    return any(marker in value for marker in bad_markers)


def _extract_limit(text: str, default: int = 3, maximum: int = 5):
    for token in str(text or "").replace(",", " ").split():
        digits = "".join(ch for ch in token if ch.isdigit())

        if digits:
            try:
                return max(1, min(int(digits), maximum))
            except Exception:
                pass

    return default


def _strip_prefix(text: str, prefixes):
    source = str(text or "").strip()
    lower = source.lower()

    for prefix in prefixes:
        if lower.startswith(prefix):
            source = source[len(prefix):].strip(" :,-—")
            break

    return source


def _clean_browser_goal(goal: str):
    text = str(goal or "").strip()

    text = _strip_prefix(
        text,
        [
            "multi task",
            "browser task",
            "browser batch",
            "browser compare",
            "browser report",
            "браузерная задача",
            "браузер задача",
            "комплексная задача",
            "мульти задача",
        ],
    )

    lower = text.lower()

    start_words = [
        "найди ",
        "найти ",
        "поищи ",
        "search ",
        "find ",
    ]

    for word in start_words:
        if lower.startswith(word):
            text = text[len(word):].strip()
            lower = text.lower()
            break

    instruction_markers = [
        ", прочитай",
        " и прочитай",
        ", прочти",
        " и прочти",
        ", открой",
        " и открой",
        ", открыть",
        " и открыть",
        ", сохрани",
        " и сохрани",
        ", сделай отчет",
        " и сделай отчет",
        ", сделай отчёт",
        " и сделай отчёт",
        ", открой папку",
        " и открой папку",
        " прочитай первые",
        " прочти первые",
        " первые 3 результата",
        " первые три результата",
    ]

    lower = text.lower()
    cut_indexes = []

    for marker in instruction_markers:
        index = lower.find(marker)

        if index != -1:
            cut_indexes.append(index)

    if cut_indexes:
        text = text[:min(cut_indexes)].strip(" :,-—")

    cleanup_phrases = [
        "и прочитай",
        "и прочти",
        "прочитай",
        "прочти",
        "сравни",
        "сделай отчет",
        "сделай отчёт",
        "сохрани отчет",
        "сохрани отчёт",
    ]

    for phrase in cleanup_phrases:
        if text.lower().endswith(phrase):
            text = text[: -len(phrase)].strip(" :,-—")

    return text.strip(" :,-—") or str(goal or "").strip()


def _resolve_read_first_query(goal: str):
    raw = str(goal or "").strip()
    lower = raw.lower()

    raw = _strip_prefix(
        raw,
        [
            "browser read first",
            "браузер прочитай первые",
            "прочитай первые результаты",
        ],
    ).strip(" :,-—")

    # Важный фикс v5.36:
    # browser read first 3 раньше превращался в поисковый запрос "3".
    # Если после команды осталась только цифра/лимит, берем last_browser_query.
    only_digits = "".join(ch for ch in raw if ch.isdigit()) == raw.replace(" ", "") and bool(raw.strip())

    if not raw or only_digits or lower in ["3", "first 3", "первые 3", "первые три"]:
        return str(get_value("last_browser_query", "") or "").strip()

    return _clean_browser_goal(raw)


def _split_goal_parts(goal: str):
    text = str(goal or "").strip()
    raw_parts = re.split(r"\s*,\s*|\s*;\s*|\s+\и\s+", text)

    return [part.strip(" :,-—") for part in raw_parts if part.strip(" :,-—")]


def _folder_steps_from_goal(goal: str):
    parts = _split_goal_parts(goal)
    steps = []
    folder_hits = []

    for part in parts:
        lower = part.lower()

        if "отчет" in lower or "отчёт" in lower or "reports" in lower:
            folder_hits.append(part)
            steps.append({
                "name": "open reports folder",
                "func": lambda: _open_folder(REPORTS_DIR),
            })
            continue

        if "проект" in lower or "projects" in lower:
            folder_hits.append(part)
            steps.append({
                "name": "open projects folder",
                "func": lambda: _open_folder(PROJECTS_DIR),
            })
            continue

        if "windows" in lower or "виндовс" in lower:
            folder_hits.append(part)
            steps.append({
                "name": "open windows folder",
                "func": lambda: _open_folder(WINDOWS_DIR),
            })
            continue

    return steps, folder_hits


def _strip_folder_commands(goal: str):
    parts = _split_goal_parts(goal)
    keep = []

    for part in parts:
        lower = part.lower()

        is_folder_part = (
            "папк" in lower
            and (
                "отчет" in lower
                or "отчёт" in lower
                or "reports" in lower
                or "проект" in lower
                or "projects" in lower
                or "windows" in lower
                or "виндовс" in lower
            )
        )

        if is_folder_part:
            continue

        keep.append(part)

    return ", ".join(keep).strip(" :,-—")


def _split_multi_goal(goal: str):
    text = str(goal or "").strip()
    browser_query = ""

    lower = text.lower()

    if any(word in lower for word in ["найди", "поиск", "browser", "браузер", "сайт", "страниц", "прочитай", "прочти"]):
        browser_query = _clean_browser_goal(text)

    pc_goal_parts = []
    folder_steps, folder_hits = _folder_steps_from_goal(text)

    if folder_hits:
        # Для PC-части берем только локальные инструкции, а не весь поисковый запрос.
        pc_goal_parts.extend(folder_hits)

    non_folder = _strip_folder_commands(text)

    # Если задача не является браузерной, можно отправить локальную часть целиком.
    if not browser_query and non_folder:
        pc_goal_parts.append(non_folder)

    # Если явно просили блокнот/написать — добавим эти части, но без browser-поиска.
    for part in _split_goal_parts(text):
        lower_part = part.lower()

        if any(word in lower_part for word in ["блокнот", "notepad", "напиши", "напечатай", "введи", "набери", "калькулятор", "calc"]):
            if part not in pc_goal_parts:
                pc_goal_parts.append(part)

    pc_goal = ", ".join(pc_goal_parts).strip(" :,-—")
    return browser_query, pc_goal


def _dev_task_files_hint(goal: str):
    lower = str(goal or "").lower()

    if any(word in lower for word in [
        "multi task",
        "browser batch",
        "pc batch",
        "task status",
        "task report",
        "automation",
        "автоматизац",
        "direct",
        "after patch",
        "dev task",
        "browser task",
        "pc task",
        "sequential",
        "runner",
        "parser",
        "парсер",
        "цепочк",
    ]):
        return [
            "modules/automation_center.py",
            "agents/automation_agent.py",
            "modules/browser.py",
            "agents/browser_agent.py",
            "agents/windows_agent.py",
            "agents/workspace_agent.py",
            "agents/file_agent.py",
            "core/router.py",
            "core/planner.py",
            "core/executor.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/stability_test.py",
        ]

    if any(word in lower for word in [
        "browser",
        "браузер",
        "вклад",
        "tab",
        "duckduckgo",
        "страниц",
        "читать сайт",
        "читать страницу",
    ]):
        return [
            "modules/browser.py",
            "agents/browser_agent.py",
            "modules/automation_center.py",
            "agents/automation_agent.py",
            "core/router.py",
            "core/planner.py",
            "core/executor.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/stability_test.py",
        ]

    if any(word in lower for word in [
        "relay",
        "релей",
        "chatgpt",
        "request",
        "response",
        "snapshot",
    ]):
        return [
            "modules/chatgpt_relay.py",
            "agents/chatgpt_relay_agent.py",
            "modules/self_edit.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/history_log.py",
        ]

    if any(word in lower for word in [
        "windows",
        "пк",
        "локальн",
        "блокнот",
        "notepad",
        "проводник",
        "файл",
        "папк",
    ]):
        return [
            "agents/windows_agent.py",
            "modules/windows.py",
            "agents/workspace_agent.py",
            "modules/workspace.py",
            "agents/file_agent.py",
            "modules/automation_center.py",
            "next/app_v5.py",
            "core/planner.py",
            "core/router.py",
        ]

    return []


def _save_automation_report(kind: str, title: str, body: str):
    _ensure_reports_dir()

    safe_kind = "".join(ch if ch.isalnum() or ch in ["_", "-"] else "_" for ch in str(kind or "automation"))
    path = REPORTS_DIR / f"{_stamp()}_{safe_kind}.md"

    text = "\n".join([
        f"# {title}",
        "",
        f"- Время: {datetime.now().isoformat(timespec='seconds')}",
        f"- Тип: {kind}",
        "",
        body,
    ])

    path.write_text(text, encoding="utf-8")

    set_value("last_automation_report", str(path))
    set_value("last_task_report", str(path))
    return path


def _save_result(task: str, result: str, kind: str = "automation"):
    set_value("last_automation_task", task)
    set_value("last_automation_result", _short(result))
    report = _save_automation_report(kind, f"Automation: {kind}", result)
    return report


def _run_steps(title: str, steps: list):
    rows = []
    ok_count = 0

    for index, step in enumerate(steps, start=1):
        name = step.get("name", f"step {index}")
        func = step.get("func")

        try:
            result = func()
            has_problem = _has_bad_result(result)
            step_ok = not has_problem

            if step_ok:
                ok_count += 1

            rows.append({
                "index": index,
                "name": name,
                "ok": step_ok,
                "result": _short(result, 3500),
                "error": "Результат содержит маркер проблемы." if has_problem else "",
            })
        except Exception as e:
            rows.append({
                "index": index,
                "name": name,
                "ok": False,
                "result": "",
                "error": _short(e, 2500),
            })

    lines = [
        title,
        f"Шагов успешно: {ok_count}/{len(steps)}",
        "",
        "Шаги:",
    ]

    for row in rows:
        mark = "✅" if row["ok"] else "❌"
        lines.extend([
            "",
            f"{row['index']}. {mark} {row['name']}",
        ])

        if row["result"]:
            lines.extend(["```text", row["result"], "```"])

        if row["error"]:
            lines.extend(["ERROR:", "```text", row["error"], "```"])

    return "\n".join(lines)


def _open_folder(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["explorer", str(path)])
    return f"Открыл папку: {path}"


def automation_status():
    return (
        "Automation Command Center status:\n"
        f"- last_automation_task: {get_value('last_automation_task', 'нет')}\n"
        f"- last_automation_result: {get_value('last_automation_result', 'нет')}\n"
        f"- last_automation_report: {get_value('last_automation_report', 'нет')}\n"
        f"- last_task_report: {get_value('last_task_report', 'нет')}\n"
        f"- last_multi_task: {get_value('last_multi_task', 'нет')}\n"
        f"- last_browser_batch: {get_value('last_browser_batch', 'нет')}\n"
        f"- last_pc_batch: {get_value('last_pc_batch', 'нет')}\n"
        f"- last_stability_score: {get_value('last_stability_score', 'нет')}\n"
        f"- last_stability_report: {get_value('last_stability_report', 'нет')}\n"
        f"- last_error: {get_value('last_error', 'нет')}\n\n"
        "Команды:\n"
        "- dev task <задача разработки>\n"
        "- browser task <что найти/прочитать>\n"
        "- browser batch <запрос>\n"
        "- browser read first 3\n"
        "- browser compare <запрос>\n"
        "- browser report <запрос или текущая страница>\n"
        "- pc task <локальная задача ПК>\n"
        "- pc batch <несколько локальных действий>\n"
        "- multi task <браузер + ПК + отчет>\n"
        "- task status\n"
        "- task report\n"
        "- after patch"
    )


def task_status():
    return automation_status()


def task_report():
    path = get_value("last_task_report", "") or get_value("last_automation_report", "")

    if not path:
        return "Последний task report не найден."

    report_path = Path(path)

    if not report_path.exists():
        return f"Task report не найден: {report_path}"

    text = report_path.read_text(encoding="utf-8", errors="replace")
    return f"Последний task report:\n{report_path}\n\n{_short(text, 5000)}"


def parser_diagnostics():
    old_query = get_value("last_browser_query", "")
    set_value("last_browser_query", "Godot official website")

    read_query = _resolve_read_first_query("3")
    browser_query, pc_goal = _split_multi_goal(
        "найди официальный сайт Python, прочитай первые 3 результата и открой папку отчетов"
    )
    pc_clean = _strip_folder_commands(
        "открой блокнот, напиши тест мультизадачи, открой папку отчетов"
    )
    folder_steps, folder_hits = _folder_steps_from_goal("открой папку отчетов")

    if old_query:
        set_value("last_browser_query", old_query)

    return (
        "Parser diagnostics:\n"
        f"- browser_read_first_query: {read_query}\n"
        f"- multi_browser_query: {browser_query}\n"
        f"- multi_pc_goal: {pc_goal}\n"
        f"- pc_batch_clean_goal: {pc_clean}\n"
        f"- pc_batch_folder_hits: {folder_hits}\n"
        f"- pc_batch_reports_only: {'ok' if folder_steps else 'fail'}"
    )


def dev_task(goal: str):
    goal = str(goal or "").strip()

    if not goal:
        return "Automation: не указана dev task."

    from modules.chatgpt_relay import create_snapshot, copy_request, open_chatgpt

    relay_goal = goal

    files_hint = _dev_task_files_hint(goal)

    if files_hint and "файлы:" not in relay_goal.lower() and "files:" not in relay_goal.lower():
        relay_goal = relay_goal.rstrip() + "\n\nфайлы: " + ", ".join(files_hint)

    if not relay_goal.lower().startswith("сделай "):
        relay_goal = "сделай " + relay_goal

    result_parts = [
        "Dev task запущена.",
        f"Цель разработки: {goal}",
        "",
        "--- SNAPSHOT ---",
        create_snapshot(relay_goal),
        "",
        "--- COPY ---",
        copy_request(),
        "",
        "--- OPEN CHATGPT ---",
        open_chatgpt(),
        "",
        "Следующий шаг:",
        "1. В ChatGPT отправь уже скопированный request.",
        "2. Скачай response.json в папку Relay.",
        "3. Выполни: relay проверь ответ",
        "4. Выполни: relay примени ответ",
        "5. Потом: after patch",
    ]

    result = "\n".join(str(part) for part in result_parts)
    report = _save_result(goal, result, kind="dev_task")

    return result + f"\n\nОтчет automation: {report}"


def _read_first_results(query: str, count: int = 3):
    from agents import browser_agent
    from modules.browser import get_search_result_links, open_url, read_page

    query = _clean_browser_goal(query)
    count = max(1, min(int(count or 3), 5))

    steps = []

    steps.append({
        "name": f"search: {query}",
        "func": lambda: browser_agent.handle("search", {"query": query}),
    })

    pages = []

    def collect_links():
        links = get_search_result_links(limit=count)
        pages.clear()
        pages.extend(links)
        return "\n".join(f"{i + 1}. {item['title']} — {item['url']}" for i, item in enumerate(links)) or "Ссылки не найдены."

    steps.append({"name": f"collect first {count} results", "func": collect_links})

    def make_read_step(position: int):
        def run():
            if position >= len(pages):
                return f"Результат #{position + 1} отсутствует."

            item = pages[position]
            open_result = open_url(item["url"])
            read_result = read_page(limit=2500)

            return (
                f"{open_result}\n\n"
                f"TITLE: {item['title']}\nURL: {item['url']}\n\n"
                f"{read_result}"
            )

        return run

    for i in range(count):
        steps.append({
            "name": f"read result #{i + 1}",
            "func": make_read_step(i),
        })

    output = _run_steps(f"Browser batch: {query}", steps)

    set_value("last_browser_batch", _short(output, 4000))
    set_value("last_multi_task", f"browser batch: {query}")

    report = _save_result(query, output, kind="browser_batch")
    return output + f"\n\nОтчет task: {report}"


def browser_task(goal: str):
    count = 3 if any(word in str(goal).lower() for word in ["3", "несколько", "сравни", "compare", "batch"]) else 1

    if count > 1:
        return _read_first_results(goal, count=count)

    goal = str(goal or "").strip()

    if not goal:
        return "Automation: не указана browser task."

    from agents import browser_agent

    browser_goal = _clean_browser_goal(goal)

    steps = [
        {
            "name": f"search: {browser_goal}",
            "func": lambda: browser_agent.handle("search", {"query": browser_goal}),
        },
        {
            "name": "open first result",
            "func": lambda: browser_agent.handle("open_first_result", {}),
        },
        {
            "name": "read page",
            "func": lambda: browser_agent.handle("read_page", {}),
        },
    ]

    result = _run_steps(f"Browser task: {goal}", steps)
    report = _save_result(goal, result, kind="browser_task")

    return result + f"\n\nОтчет automation: {report}"


def browser_batch(goal: str, count: int = 3):
    return _read_first_results(goal, count=count)


def browser_read_first(goal: str = "", count: int = 3):
    query = _resolve_read_first_query(goal)

    if not query:
        return "Нет last_browser_query. Сначала выполни browser batch <запрос> или найди <запрос>."

    return _read_first_results(query, count=count)


def browser_compare(goal: str):
    query = _clean_browser_goal(goal)
    result = _read_first_results(query, count=3)

    comparison = (
        "\n\n--- COMPARE SUMMARY ---\n"
        "Сравнение сохранено по первым 3 результатам. "
        "Смотри блоки read result #1/#2/#3: сравнивай title, URL и текст страницы. "
        "Для следующего уровня можно добавить LLM-сводку поверх этого отчета."
    )

    output = result + comparison
    set_value("last_browser_batch", _short(output, 4000))
    report = _save_result(query, output, kind="browser_compare")

    return output + f"\n\nОтчет compare: {report}"


def browser_report(goal: str = ""):
    from agents import browser_agent

    if goal:
        result = browser_task(goal)
    else:
        result = browser_agent.handle("read_page", {})

    report = _save_result(goal or "current browser page", result, kind="browser_report")
    return f"Browser report сохранен:\n{report}\n\n{_short(result, 3500)}"


def pc_task(goal: str):
    goal = str(goal or "").strip()

    if not goal:
        return "Automation: не указана pc task."

    from core.router import route
    from core.planner import plan
    from core.executor import execute

    route_name = route(goal)
    planned = plan(goal, route_name)
    result = execute(planned)

    output = (
        "PC task выполнена.\n"
        f"Цель: {goal}\n"
        f"ROUTE: {route_name}\n"
        f"PLAN: {planned}\n\n"
        f"RESULT:\n{result}"
    )

    report = _save_result(goal, output, kind="pc_task")
    set_value("last_pc_batch", _short(output, 4000))

    return output + f"\n\nОтчет automation: {report}"


def pc_batch(goal: str):
    goal = str(goal or "").strip()

    if not goal:
        return "Automation: не указана pc batch."

    steps = []

    clean_pc_goal = _strip_folder_commands(goal)

    if clean_pc_goal:
        steps.append({
            "name": "execute pc task",
            "func": lambda: pc_task(clean_pc_goal),
        })

    folder_steps, _ = _folder_steps_from_goal(goal)
    steps.extend(folder_steps)

    if not steps:
        return "PC batch: не нашел локальные действия."

    output = _run_steps(f"PC batch: {goal}", steps)
    set_value("last_pc_batch", _short(output, 4000))
    report = _save_result(goal, output, kind="pc_batch")

    return output + f"\n\nОтчет task: {report}"


def multi_task(goal: str):
    goal = str(goal or "").strip()

    if not goal:
        return "Automation: не указана multi task."

    browser_query, pc_goal = _split_multi_goal(goal)
    steps = []

    if browser_query:
        steps.append({
            "name": f"browser batch: {browser_query}",
            "func": lambda: browser_batch(browser_query, count=3),
        })

    if pc_goal:
        steps.append({
            "name": f"pc batch: {pc_goal}",
            "func": lambda: pc_batch(pc_goal),
        })

    if not steps:
        steps.append({
            "name": "browser task default",
            "func": lambda: browser_task(goal),
        })

    output = _run_steps(f"Multi task: {goal}", steps)
    set_value("last_multi_task", _short(output, 4000))
    report = _save_result(goal, output, kind="multi_task")

    return output + f"\n\nОтчет multi task: {report}"


def after_patch():
    from modules.auto_verification import format_auto_verification, run_auto_verification

    result = run_auto_verification(mode="post_patch", write_report=True)
    formatted = format_auto_verification(result)

    output = (
        "After Patch проверка выполнена.\n"
        "Запущен Auto Verification после применения патча.\n\n"
        f"{formatted}"
    )

    report = _save_result("after patch", output, kind="after_patch")

    return output + f"\n\nОтчет automation: {report}"


def handle_automation(action: str, data: dict):
    if action == "status":
        return automation_status()

    if action == "task_status":
        return task_status()

    if action == "task_report":
        return task_report()

    if action == "parser_diagnostics":
        return parser_diagnostics()

    if action == "dev_task":
        return dev_task(data.get("goal", ""))

    if action == "browser_task":
        return browser_task(data.get("goal", ""))

    if action == "browser_batch":
        return browser_batch(data.get("goal", ""), data.get("limit", 3))

    if action == "browser_read_first":
        return browser_read_first(data.get("goal", ""), data.get("limit", 3))

    if action == "browser_compare":
        return browser_compare(data.get("goal", ""))

    if action == "browser_report":
        return browser_report(data.get("goal", ""))

    if action == "pc_task":
        return pc_task(data.get("goal", ""))

    if action == "pc_batch":
        return pc_batch(data.get("goal", ""))

    if action == "multi_task":
        return multi_task(data.get("goal", ""))

    if action == "after_patch":
        return after_patch()

    return "Automation Command Center: неизвестное действие."
````

### ПУТЬ: modules/autonomous_action_executor_ru.py (968 строк, 50802 байт)

````python
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from modules.autonomy_policy_ru import (
    ActionProposal,
    AutonomyPolicy,
    BudgetUsage,
    KillSwitchStatus,
    PolicyDecisionType,
    evaluate_action_proposal,
    inspect_kill_switches,
    resolve_project_root,
    serialize_policy_decision,
    validate_target_path,
)

AUTONOMOUS_ACTION_EXECUTOR_VERSION = "v6.84"
APPROVAL_SCOPE_SINGLE_ACTION = "SINGLE_ACTION"
SUPPORTED_OPERATIONS = (
    "read_file",
    "list_directory",
    "search_text",
    "syntax_check",
    "run_allowlisted_test",
    "create_temp_file",
    "write_allowlisted_file",
    "apply_exact_patch",
)
UNSUPPORTED_OPERATIONS = {
    "arbitrary_command", "delete", "download", "install", "kill_switch_change",
    "move", "network", "policy_change", "powershell", "privilege_escalation",
    "registry", "rename", "scheduled_task", "service", "shell", "upload",
}
STATUS_VALUES = ("SUCCESS", "DENIED", "FAILED", "TIMEOUT", "ROLLED_BACK")
OPERATION_ACTIONS = {
    "read_file": {"inspect"},
    "list_directory": {"inspect"},
    "search_text": {"analyze"},
    "syntax_check": {"analyze", "verify"},
    "run_allowlisted_test": {"test"},
    "create_temp_file": {"create_temp"},
    "write_allowlisted_file": {"create_file", "edit_file"},
    "apply_exact_patch": {"apply_patch", "edit_file"},
}
_ZERO_SHA = "0" * 64
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_TOKEN_RE = re.compile(
    "|".join((
        r"sk" + r"-[A-Za-z0-9_\-]{8,}",
        r"ghp" + r"_[A-Za-z0-9_]{8,}",
        r"(?i:bearer\s+[A-Za-z0-9._\-]{8,})",
        r"(?i:(authorization\s*:\s*)[^\r\n]+)",
        r"(?i:((?:pass" + r"word|passwd)\s*[:=]\s*)[^\s'\";]{6,})",
        r"(?i:((?:api[_-]?key|token|sec" + r"ret)\s*[:=]\s*)[^\s'\";]{8,})",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    )),
    re.DOTALL,
)
_USER_PATH_RE = re.compile(
    r"(?i)([A-Z]:\\Us" + r"ers\\[^\\\s]+|/ho" + r"me/[^/\s]+|/Us" + r"ers/[^/\s]+|\\\\[^\\\s]+\\[^\\\s]+)"
)


class ExecutorValidationError(ValueError):
    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


@dataclass(frozen=True)
class ExecutorConfig:
    root: Path
    temporary_roots: tuple[Path, ...] = field(default_factory=tuple)
    write_allowlist: tuple[str, ...] = field(default_factory=tuple)
    test_allowlist: tuple[str, ...] = field(default_factory=tuple)
    max_read_bytes: int = 262_144
    max_write_bytes: int = 1_048_576
    max_directory_entries: int = 500
    max_search_files: int = 200
    max_search_bytes: int = 2_097_152
    max_search_matches: int = 200
    max_subprocess_output_bytes: int = 1_000_000
    default_timeout_seconds: float = 30.0
    max_timeout_seconds: float = 300.0
    allow_test_execution: bool = False
    allow_project_writes: bool = False
    allow_temp_writes: bool = False

    def __post_init__(self) -> None:
        root = Path(self.root).expanduser().resolve()
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "temporary_roots", tuple(sorted(Path(p).expanduser().resolve() for p in self.temporary_roots)))
        object.__setattr__(self, "write_allowlist", _normalize_allowlist(root, self.write_allowlist))
        object.__setattr__(self, "test_allowlist", _normalize_allowlist(root, self.test_allowlist))
        for name, maximum, allow_zero in (
            ("max_read_bytes", 10 * 1024 * 1024, False),
            ("max_write_bytes", 10 * 1024 * 1024, False),
            ("max_directory_entries", 10_000, False),
            ("max_search_files", 5_000, False),
            ("max_search_bytes", 100 * 1024 * 1024, False),
            ("max_search_matches", 10_000, False),
            ("max_subprocess_output_bytes", 10 * 1024 * 1024, False),
        ):
            object.__setattr__(self, name, _int_limit(getattr(self, name), maximum, allow_zero, name))
        object.__setattr__(self, "default_timeout_seconds", _float_limit(self.default_timeout_seconds, 900.0, False, "default_timeout_seconds"))
        object.__setattr__(self, "max_timeout_seconds", _float_limit(self.max_timeout_seconds, 900.0, False, "max_timeout_seconds"))
        if self.default_timeout_seconds > self.max_timeout_seconds:
            raise ValueError("default_timeout_seconds_out_of_bounds")
        for name in ("allow_test_execution", "allow_project_writes", "allow_temp_writes"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name}_not_bool")


@dataclass(frozen=True)
class ExecutableAction:
    proposal: ActionProposal
    operation: str
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalGrant:
    action_id: str
    action_fingerprint: str
    granted: bool
    scope: str = APPROVAL_SCOPE_SINGLE_ACTION


@dataclass(frozen=True)
class ActionResult:
    action_id: str
    action_type: str
    operation: str
    status: str
    ok: bool
    executed: bool
    target: str
    action_fingerprint: str
    approval: Mapping[str, bool]
    policy: Mapping[str, Any]
    timing: Mapping[str, Any]
    bytes_read: int = 0
    bytes_written: int = 0
    original_sha256: str | None = None
    result_sha256: str | None = None
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False
    rollback_performed: bool = False
    error_category: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


def default_executor_config(root: str | Path | None = None) -> ExecutorConfig:
    return ExecutorConfig(root=resolve_project_root(root))


def executor_config_from_dict(data: Mapping[str, Any]) -> ExecutorConfig:
    allowed = set(ExecutorConfig.__dataclass_fields__)
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError("unknown_configuration_key")
    return ExecutorConfig(**dict(data))


def validate_executor_config(config: ExecutorConfig) -> tuple[str, ...]:
    findings: list[str] = []
    if not config.root.exists() or not config.root.is_dir():
        findings.append("invalid_root")
    for rel in (*config.write_allowlist, *config.test_allowlist):
        data = validate_target_path(config.root, rel)
        if not data.get("ok"):
            findings.append("invalid_allowlist")
        if data.get("protected"):
            findings.append("protected_allowlist")
    if len(config.write_allowlist) != len(set(config.write_allowlist)):
        findings.append("duplicate_write_allowlist")
    if len(config.test_allowlist) != len(set(config.test_allowlist)):
        findings.append("duplicate_test_allowlist")
    for temp in config.temporary_roots:
        if not temp.exists() or not temp.is_dir():
            findings.append("invalid_temporary_root")
        if _has_symlink_component(temp, stop_before=temp.parent):
            findings.append("temporary_root_symlink")
    return tuple(sorted(set(findings)))


def serialize_executor_config(config: ExecutorConfig) -> dict[str, Any]:
    return {
        "mode": "autonomous_executor_config",
        "version": AUTONOMOUS_ACTION_EXECUTOR_VERSION,
        "root": "<PROJECT_ROOT>",
        "temporary_roots": [_display_temp_root(config, p) for p in config.temporary_roots],
        "write_allowlist": list(config.write_allowlist),
        "test_allowlist": list(config.test_allowlist),
        "limits": {
            "max_directory_entries": config.max_directory_entries,
            "max_read_bytes": config.max_read_bytes,
            "max_search_bytes": config.max_search_bytes,
            "max_search_files": config.max_search_files,
            "max_search_matches": config.max_search_matches,
            "max_subprocess_output_bytes": config.max_subprocess_output_bytes,
            "max_timeout_seconds": config.max_timeout_seconds,
            "max_write_bytes": config.max_write_bytes,
            "default_timeout_seconds": config.default_timeout_seconds,
        },
        "permissions": {
            "allow_project_writes": config.allow_project_writes,
            "allow_temp_writes": config.allow_temp_writes,
            "allow_test_execution": config.allow_test_execution,
        },
    }


def compute_action_fingerprint(action: ExecutableAction, config: ExecutorConfig) -> str:
    target = _target_info(config, action.proposal.target)
    canonical = {
        "version": AUTONOMOUS_ACTION_EXECUTOR_VERSION,
        "action_id": str(action.proposal.action_id),
        "action_type": str(action.proposal.action_type),
        "operation": str(action.operation),
        "target": target["display"],
        "expected_original_sha256": action.proposal.expected_original_sha256,
        "estimates": {
            "changed_files": action.proposal.estimated_changed_files,
            "changed_lines": action.proposal.estimated_changed_lines,
            "output_bytes": action.proposal.estimated_output_bytes,
            "subprocesses": action.proposal.estimated_subprocesses,
        },
        "parameters": _canonical_json(action.parameters),
    }
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_approval_grant(action: ExecutableAction, config: ExecutorConfig, approval: ApprovalGrant | None) -> dict[str, Any]:
    expected = compute_action_fingerprint(action, config)
    result = {"required": True, "provided": approval is not None, "valid": False, "reason": None}
    if approval is None:
        result["reason"] = "approval_required"
        return result
    if approval.granted is not True:
        result["reason"] = "approval_not_granted"
    elif approval.scope != APPROVAL_SCOPE_SINGLE_ACTION:
        result["reason"] = "approval_scope_mismatch"
    elif approval.action_id != action.proposal.action_id:
        result["reason"] = "approval_action_mismatch"
    elif not _SHA_RE.match(str(approval.action_fingerprint)):
        result["reason"] = "approval_fingerprint_invalid"
    elif approval.action_fingerprint != expected:
        result["reason"] = "approval_fingerprint_mismatch"
    else:
        result["valid"] = True
    return result


def execute_action(
    policy: AutonomyPolicy,
    action: ExecutableAction,
    *,
    config: ExecutorConfig | None = None,
    usage: BudgetUsage | None = None,
    kill_switch: KillSwitchStatus | None = None,
    approval: ApprovalGrant | None = None,
    now: Any = None,
    monotonic: Any = None,
) -> ActionResult:
    clock = _Clock(now, monotonic)
    started_at, start_mono = clock.start()
    cfg = config or default_executor_config(policy.allowed_roots[0] if getattr(policy, "allowed_roots", ()) else None)
    policy_payload: dict[str, Any] = {}
    fingerprint = ""
    display = "<PROJECT_ROOT>"
    approval_payload = {"required": False, "provided": approval is not None, "valid": False}
    try:
        config_findings = validate_executor_config(cfg)
        if config_findings:
            return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "invalid_configuration", warnings=config_findings)
        validation = _validate_action(action)
        if validation:
            return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, validation)
        target = _target_info(cfg, action.proposal.target)
        display = target["display"]
        fingerprint = compute_action_fingerprint(action, cfg)
        if not target["ok"]:
            category = "protected_path" if target["protected"] else "unsafe_path"
            return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category, warnings=target["reasons"])
        switch = kill_switch if kill_switch is not None else inspect_kill_switches(cfg.root)
        decision = evaluate_action_proposal(policy, action.proposal, usage=usage, kill_switch=switch)
        policy_payload = _sanitize_json(serialize_policy_decision(decision))
        if switch.active:
            return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "kill_switch_active")
        if decision.decision == PolicyDecisionType.BLOCK or not decision.budget.get("within_limits", True):
            category = "budget_exceeded" if not decision.budget.get("within_limits", True) else "policy_blocked"
            return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category)
        approval_required = decision.approval_required or action.operation in {"run_allowlisted_test", "create_temp_file", "write_allowlisted_file", "apply_exact_patch"}
        approval_payload = {"required": approval_required, "provided": approval is not None, "valid": not approval_required}
        if approval_required:
            grant = validate_approval_grant(action, cfg, approval)
            approval_payload = {"required": True, "provided": bool(grant["provided"]), "valid": bool(grant["valid"])}
            if not grant["valid"]:
                category = "approval_required" if not grant["provided"] else "approval_mismatch"
                return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category)
        target = _target_info(cfg, action.proposal.target)
        if not target["ok"]:
            category = "protected_path" if target["protected"] else "unsafe_path"
            return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category, warnings=target["reasons"])
        return _execute_operation(policy, action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    except ExecutorValidationError as exc:
        return _finish(action, "DENIED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, exc.category)
    except Exception:
        return _finish(action, "FAILED", False, False, display, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "internal_error")


def serialize_action_result(result: ActionResult) -> dict[str, Any]:
    return {
        "mode": "autonomous_action_result",
        "version": AUTONOMOUS_ACTION_EXECUTOR_VERSION,
        "action_id": result.action_id,
        "action_type": result.action_type,
        "operation": result.operation,
        "status": result.status,
        "ok": result.ok,
        "executed": result.executed,
        "target": result.target,
        "action_fingerprint": result.action_fingerprint,
        "approval": dict(result.approval),
        "policy": _sanitize_json(result.policy),
        "timing": dict(result.timing),
        "bytes_read": result.bytes_read,
        "bytes_written": result.bytes_written,
        "original_sha256": result.original_sha256,
        "result_sha256": result.result_sha256,
        "stdout": _redact(result.stdout),
        "stderr": _redact(result.stderr),
        "output_truncated": result.output_truncated,
        "rollback_performed": result.rollback_performed,
        "error_category": result.error_category,
        "details": _sanitize_json(result.details),
        "warnings": sorted(set(result.warnings)),
    }


def _execute_operation(policy: AutonomyPolicy, action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    op = action.operation
    if op == "read_file":
        return _read_file(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "list_directory":
        return _list_directory(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "search_text":
        return _search_text(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "syntax_check":
        return _syntax_check(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "run_allowlisted_test":
        return _run_allowlisted_test(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "create_temp_file":
        return _create_temp_file(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "write_allowlisted_file":
        return _write_allowlisted_file(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    if op == "apply_exact_patch":
        return _apply_exact_patch(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "unsupported_operation")


def _read_file(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    path = target["path"]
    if not path.exists():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_missing")
    if not path.is_file():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "binary_file" if path.is_dir() else "unsafe_path")
    size = path.stat().st_size
    if size > cfg.max_read_bytes:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "size_limit")
    data = path.read_bytes()
    if _looks_binary(data):
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "binary_file")
    text, encoding = _decode_text(data)
    details = {"content": _redact(text), "encoding": encoding}
    return _finish(action, "SUCCESS", True, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, None, bytes_read=len(data), original_sha256=_sha256_bytes(data), result_sha256=_sha256_bytes(data), details=details)


def _list_directory(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    path = target["path"]
    include_hidden = bool(action.parameters.get("include_hidden", True))
    if not path.exists():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_missing")
    if not path.is_dir():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "unsupported_parameters")
    entries = []
    for child in path.iterdir():
        if not include_hidden and child.name.startswith("."):
            continue
        if len(entries) >= cfg.max_directory_entries:
            return _finish(action, "DENIED", False, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "size_limit")
        rel = _rel(cfg.root, child)
        if rel and validate_target_path(cfg.root, rel).get("protected"):
            continue
        entries.append({"name": child.name, "path": _display(rel), "type": _entry_type(child), "symlink": child.is_symlink()})
    entries.sort(key=lambda item: item["name"].lower())
    return _finish(action, "SUCCESS", True, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, None, details={"entries": entries})


def _search_text(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    query = str(action.parameters.get("query", ""))
    if not query or len(query) > 256:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "unsupported_parameters")
    path = target["path"]
    if not path.exists():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_missing")
    case_sensitive = bool(action.parameters.get("case_sensitive", False))
    max_depth = int(action.parameters.get("max_depth", 8))
    needle = query if case_sensitive else query.casefold()
    matches: list[dict[str, Any]] = []
    scanned_files = 0
    scanned_bytes = 0
    roots = [path] if path.is_dir() else [path.parent]
    for base in roots:
        for current, dirs, files in os.walk(base):
            cur_path = Path(current)
            rel_current = _rel(cfg.root, cur_path)
            if rel_current and validate_target_path(cfg.root, rel_current).get("protected"):
                dirs[:] = []
                continue
            depth = len(Path(rel_current).parts) - len(Path(_rel(cfg.root, path)).parts) if rel_current else 0
            if depth >= max_depth:
                dirs[:] = []
            dirs[:] = sorted(d for d in dirs if not (cur_path / d).is_symlink())
            for name in sorted(files):
                file_path = cur_path / name
                if file_path.is_symlink():
                    continue
                rel = _rel(cfg.root, file_path)
                if not rel or validate_target_path(cfg.root, rel).get("protected"):
                    continue
                if not path.is_dir() and file_path != path:
                    continue
                scanned_files += 1
                if scanned_files > cfg.max_search_files:
                    return _finish(action, "DENIED", False, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "size_limit", details={"matches": matches})
                data = file_path.read_bytes()[: cfg.max_read_bytes + 1]
                scanned_bytes += len(data)
                if scanned_bytes > cfg.max_search_bytes:
                    return _finish(action, "DENIED", False, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "size_limit", details={"matches": matches})
                if _looks_binary(data):
                    continue
                text, _ = _decode_text(data[: cfg.max_read_bytes])
                for line_no, line in enumerate(text.splitlines(), 1):
                    hay = line if case_sensitive else line.casefold()
                    if needle in hay:
                        matches.append({"file": _display(rel), "line": line_no, "text": _redact(line)})
                        if len(matches) >= cfg.max_search_matches:
                            return _finish(action, "SUCCESS", True, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, None, output_truncated=True, details={"matches": matches, "scanned_files": scanned_files})
    return _finish(action, "SUCCESS", True, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, None, details={"matches": matches, "scanned_files": scanned_files})


def _syntax_check(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    path = target["path"]
    if path.suffix != ".py":
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "unsupported_parameters")
    if not path.exists():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_missing")
    data = path.read_bytes()
    if len(data) > cfg.max_read_bytes:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "size_limit")
    text, _ = _decode_text(data)
    details: dict[str, Any] = {"syntax_ok": True, "filename": target["display"]}
    category = None
    try:
        ast.parse(text, filename=target["display"])
    except SyntaxError as exc:
        details.update({"syntax_ok": False, "line": exc.lineno, "column": exc.offset, "message": "syntax_error"})
        category = "syntax_error"
    return _finish(action, "SUCCESS" if category is None else "FAILED", category is None, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category, bytes_read=len(data), details=details)


def _run_allowlisted_test(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    rel = target["relative"]
    path = target["path"]
    if not cfg.allow_test_execution:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "test_not_allowlisted")
    if rel not in cfg.test_allowlist:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "test_not_allowlisted")
    if not rel.startswith("tools/") or not Path(rel).name.startswith("test_") or path.suffix != ".py":
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "test_not_allowlisted")
    if path.is_symlink() or not path.is_file():
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "unsafe_path")
    if rel not in _manifest_tests(cfg.root):
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "test_not_allowlisted")
    timeout = _timeout(action.parameters.get("timeout_seconds", cfg.default_timeout_seconds), cfg)
    env = _subprocess_env()
    try:
        proc = subprocess.Popen([sys.executable, rel], cwd=str(cfg.root), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", shell=False, env=env)
        stdout, stderr, timed_out, output_limited = _communicate_bounded(proc, timeout, cfg.max_subprocess_output_bytes)
    except Exception:
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "subprocess_failed")
    if timed_out:
        return _finish(action, "TIMEOUT", False, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "timeout", stdout=stdout, stderr=stderr, output_truncated=True, details={"exit_code": None, "descendant_process_containment": "direct_child_only"})
    category = "output_limit" if output_limited else ("subprocess_failed" if proc.returncode else None)
    status = "FAILED" if category else "SUCCESS"
    return _finish(action, status, category is None, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category, stdout=stdout, stderr=stderr, output_truncated=output_limited, details={"exit_code": proc.returncode, "descendant_process_containment": "direct_child_only"})


def _create_temp_file(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    if not cfg.allow_temp_writes:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_not_allowlisted")
    if not any(_is_relative_to(target["path"], temp) for temp in cfg.temporary_roots):
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_not_allowlisted")
    return _write_new(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)


def _write_allowlisted_file(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    if not cfg.allow_project_writes or target["relative"] not in cfg.write_allowlist:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_not_allowlisted")
    if action.proposal.action_type == "create_file":
        return _write_new(action, cfg, target, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)
    return _replace_existing(action, cfg, target, str(action.parameters.get("content", "")), fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)


def _apply_exact_patch(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    if not cfg.allow_project_writes or target["relative"] not in cfg.write_allowlist:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_not_allowlisted")
    old = str(action.parameters.get("old_text", ""))
    new = str(action.parameters.get("new_text", ""))
    if not old or old == new:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "unsupported_parameters")
    path = target["path"]
    if not path.exists():
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "target_missing")
    data = path.read_bytes()
    text, _ = _decode_text(data)
    count = text.count(old)
    if count == 0:
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "patch_not_found")
    if count > 1:
        return _finish(action, "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "patch_not_unique")
    return _replace_existing(action, cfg, target, text.replace(old, new, 1), fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)


def _write_new(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    path = target["path"]
    content = str(action.parameters.get("content", ""))
    problem = _validate_write_target(path, target, cfg, content, must_exist=False)
    if problem:
        return _finish(action, "DENIED" if problem in {"size_limit", "secret_content", "target_exists"} else "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, problem)
    return _atomic_write(action, cfg, target, content.encode("utf-8"), None, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)


def _replace_existing(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], content: str, fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    path = target["path"]
    problem = _validate_write_target(path, target, cfg, content, must_exist=True)
    if problem:
        return _finish(action, "DENIED" if problem in {"size_limit", "secret_content", "target_changed"} else "FAILED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, problem)
    original = path.read_bytes()
    original_hash = _sha256_bytes(original)
    if action.proposal.expected_original_sha256 != original_hash:
        return _finish(action, "DENIED", False, False, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "hash_mismatch", original_sha256=original_hash)
    return _atomic_write(action, cfg, target, content.encode("utf-8"), original, fingerprint, approval_payload, policy_payload, clock, started_at, start_mono)


def _atomic_write(action: ExecutableAction, cfg: ExecutorConfig, target: Mapping[str, Any], data: bytes, original: bytes | None, fingerprint: str, approval_payload: Mapping[str, bool], policy_payload: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float) -> ActionResult:
    path = target["path"]
    tmp = path.with_name(f".{path.name}.localcomet-v684-{os.getpid()}.tmp")
    result_hash = _sha256_bytes(data)
    original_hash = _sha256_bytes(original) if original is not None else None
    original_mode = path.stat().st_mode if path.exists() else None
    try:
        with open(tmp, "xb") as handle:
            handle.write(data)
        os.replace(tmp, path)
        if original_mode is not None:
            try:
                os.chmod(path, original_mode)
            except OSError:
                pass
        if _sha256_file(path) != result_hash:
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
                if original_mode is not None:
                    try:
                        os.chmod(path, original_mode)
                    except OSError:
                        pass
            rolled_hash = None if original is None or not path.exists() else _sha256_file(path)
            category = "rollback_failed" if original is not None and rolled_hash != original_hash else "verification_failed"
            return _finish(action, "ROLLED_BACK", False, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, category, bytes_written=len(data), original_sha256=original_hash, result_sha256=result_hash, rollback_performed=True)
        return _finish(action, "SUCCESS", True, True, target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, None, bytes_written=len(data), original_sha256=original_hash, result_sha256=result_hash)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        return _finish(action, "FAILED", False, bool(tmp.exists()), target["display"], fingerprint, approval_payload, policy_payload, clock, started_at, start_mono, "write_failed", original_sha256=original_hash)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def _validate_write_target(path: Path, target: Mapping[str, Any], cfg: ExecutorConfig, content: str, *, must_exist: bool) -> str | None:
    if _has_symlink_component(path.parent, stop_before=cfg.root.parent) or path.is_symlink():
        return "unsafe_path"
    if not path.parent.exists():
        return "target_missing"
    if must_exist and not path.exists():
        return "target_missing"
    if not must_exist and path.exists():
        return "target_exists"
    data = content.encode("utf-8")
    if len(data) > cfg.max_write_bytes:
        return "size_limit"
    if _contains_secret(content):
        return "secret_content"
    return None


def _finish(action: ExecutableAction, status: str, ok: bool, executed: bool, target: str, fingerprint: str, approval: Mapping[str, bool], policy: Mapping[str, Any], clock: "_Clock", started_at: str, start_mono: float, error_category: str | None, *, bytes_read: int = 0, bytes_written: int = 0, original_sha256: str | None = None, result_sha256: str | None = None, stdout: str = "", stderr: str = "", output_truncated: bool = False, rollback_performed: bool = False, details: Mapping[str, Any] | None = None, warnings: tuple[str, ...] | list[str] = ()) -> ActionResult:
    finished_at, duration = clock.finish(start_mono)
    return ActionResult(
        action_id=str(action.proposal.action_id),
        action_type=str(action.proposal.action_type),
        operation=str(action.operation),
        status=status if status in STATUS_VALUES else "FAILED",
        ok=ok and status == "SUCCESS",
        executed=executed,
        target=_redact(target),
        action_fingerprint=fingerprint,
        approval=dict(approval),
        policy=policy,
        timing={"started_at": started_at, "finished_at": finished_at, "duration_seconds": duration},
        bytes_read=bytes_read,
        bytes_written=bytes_written,
        original_sha256=original_sha256,
        result_sha256=result_sha256,
        stdout=_redact(stdout),
        stderr=_redact(stderr),
        output_truncated=output_truncated,
        rollback_performed=rollback_performed,
        error_category=error_category,
        details=_sanitize_json(details or {}),
        warnings=tuple(sorted(set(str(w) for w in warnings))),
    )


def _validate_action(action: ExecutableAction) -> str | None:
    if action.operation not in SUPPORTED_OPERATIONS:
        return "unsupported_operation"
    if action.operation in UNSUPPORTED_OPERATIONS:
        return "unsupported_operation"
    if str(action.proposal.action_type) not in OPERATION_ACTIONS[action.operation]:
        return "invalid_action"
    if action.proposal.requires_network or action.proposal.requires_elevation:
        return "invalid_action"
    if not _parameters_safe(action.parameters):
        return "unsupported_parameters"
    allowed_keys = {
        "read_file": set(),
        "list_directory": {"include_hidden"},
        "search_text": {"query", "case_sensitive", "max_depth"},
        "syntax_check": set(),
        "run_allowlisted_test": {"timeout_seconds"},
        "create_temp_file": {"content"},
        "write_allowlisted_file": {"content"},
        "apply_exact_patch": {"old_text", "new_text"},
    }[action.operation]
    if set(action.parameters) - allowed_keys:
        return "unsupported_parameters"
    if "include_hidden" in action.parameters and not isinstance(action.parameters["include_hidden"], bool):
        return "unsupported_parameters"
    if "case_sensitive" in action.parameters and not isinstance(action.parameters["case_sensitive"], bool):
        return "unsupported_parameters"
    if "max_depth" in action.parameters and (isinstance(action.parameters["max_depth"], bool) or not isinstance(action.parameters["max_depth"], int) or action.parameters["max_depth"] < 0 or action.parameters["max_depth"] > 20):
        return "unsupported_parameters"
    if "timeout_seconds" in action.parameters and (isinstance(action.parameters["timeout_seconds"], bool) or not isinstance(action.parameters["timeout_seconds"], (int, float))):
        return "unsupported_parameters"
    for name in ("content", "old_text", "new_text", "query"):
        if name in action.parameters and not isinstance(action.parameters[name], str):
            return "unsupported_parameters"
    if action.operation in {"create_temp_file", "write_allowlisted_file"} and "content" not in action.parameters:
        return "unsupported_parameters"
    if action.operation == "apply_exact_patch" and not {"old_text", "new_text"} <= set(action.parameters):
        return "unsupported_parameters"
    return None


def _parameters_safe(value: Any, depth: int = 0) -> bool:
    if depth > 5:
        return False
    if value is None or isinstance(value, (str, int, bool)):
        return len(str(value)) <= 4096
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, (bytes, bytearray, Path)) or callable(value):
        return False
    if isinstance(value, (list, tuple)):
        return len(value) <= 50 and all(_parameters_safe(v, depth + 1) for v in value)
    if isinstance(value, Mapping):
        return len(value) <= 50 and all(isinstance(k, str) and len(k) <= 128 and _parameters_safe(v, depth + 1) for k, v in value.items())
    return False


def _target_info(config: ExecutorConfig, raw: str | Path) -> dict[str, Any]:
    data = validate_target_path(config.root, raw)
    rel = str(data.get("relative_path", ""))
    path = config.root.joinpath(*Path(rel).parts) if rel else config.root
    reasons = list(data.get("reasons", ()))
    if data.get("ok"):
        if _has_symlink_component(path if path.exists() else path.parent, stop_before=config.root.parent):
            reasons.append("symlink_escape")
        try:
            resolved = path.resolve(strict=False)
            if not _is_relative_to(resolved, config.root):
                reasons.append("target_escapes_root")
        except Exception:
            reasons.append("target_resolution_failed")
    ok = bool(data.get("ok")) and not reasons
    return {"ok": ok, "path": path, "relative": rel, "display": _display(rel), "protected": bool(data.get("protected")), "reasons": tuple(sorted(set(reasons)))}


def _normalize_allowlist(root: Path, values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        data = validate_target_path(root, value)
        if not data.get("ok") or data.get("protected"):
            raise ValueError("invalid_allowlist")
        normalized.append(str(data["relative_path"]))
    return tuple(sorted(set(normalized), key=str.lower))


def _int_limit(value: Any, maximum: int, allow_zero: bool, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name}_invalid")
    if value < 0 or (not allow_zero and value == 0) or value > maximum:
        raise ValueError(f"{name}_out_of_bounds")
    return value


def _float_limit(value: Any, maximum: float, allow_zero: bool, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name}_invalid")
    if value < 0 or (not allow_zero and value == 0) or value > maximum:
        raise ValueError(f"{name}_out_of_bounds")
    return float(value)


def _canonical_json(value: Any) -> Any:
    json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return value


def _decode_text(data: bytes) -> tuple[str, str]:
    try:
        if data.startswith(b"\xef\xbb\xbf"):
            return data.decode("utf-8-sig"), "utf-8-sig"
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError as exc:
        raise ExecutorValidationError("encoding_error") from exc


def _looks_binary(data: bytes) -> bool:
    return b"\x00" in data[:4096]


def _contains_secret(text: str) -> bool:
    return bool(_TOKEN_RE.search(text))


def _redact(text: Any) -> str:
    value = str(text)
    value = _TOKEN_RE.sub(lambda m: "<PRIVATE_KEY>" if "PRIVATE KEY" in m.group(0).upper() else "<REDACTED_SECRET>", value)
    return _USER_PATH_RE.sub("<USER_PATH>", value)


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, str):
        return _redact(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _sanitize_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_json(v) for v in value]
    return _redact(value)


def _sha256_bytes(data: bytes | None) -> str:
    return hashlib.sha256(data or b"").hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        if os.name == "nt":
            return str(child.resolve(strict=False)).lower().startswith(str(parent.resolve(strict=False)).lower().rstrip("\\/") + os.sep)
        return False


def _has_symlink_component(path: Path, *, stop_before: Path) -> bool:
    path = path.absolute()
    stop = stop_before.resolve(strict=False)
    current = path
    while True:
        try:
            if current.exists() and current.is_symlink():
                return True
        except OSError:
            return True
        if current == stop or current.parent == current:
            return False
        current = current.parent


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return ""


def _display(rel: str) -> str:
    return "<PROJECT_ROOT>" + (f"/{rel}" if rel else "")


def _display_temp_root(config: ExecutorConfig, path: Path) -> str:
    rel = _rel(config.root, path)
    return _display(rel) if rel else "<TEMP_ROOT>"


def _entry_type(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    return "other"


def _bounded(text: str, limit: int) -> str:
    data = text.encode("utf-8", "replace")
    if len(data) <= limit:
        return _redact(text)
    return _redact(data[:limit].decode("utf-8", "replace"))


def _communicate_bounded(proc: subprocess.Popen[str], timeout: float, output_limit: int) -> tuple[str, str, bool, bool]:
    lock = threading.Lock()
    chunks = {"stdout": [], "stderr": []}
    used = {"bytes": 0}
    flags = {"limited": False}

    def reader(name: str, stream: Any) -> None:
        try:
            while True:
                data = stream.read(4096)
                if not data:
                    break
                raw = data.encode("utf-8", "replace")
                with lock:
                    remaining = max(0, output_limit - used["bytes"])
                    if remaining:
                        chunks[name].append(raw[:remaining].decode("utf-8", "replace"))
                    used["bytes"] += len(raw)
                    if used["bytes"] > output_limit and not flags["limited"]:
                        flags["limited"] = True
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        break
        except Exception:
            with lock:
                flags["limited"] = True
                try:
                    proc.kill()
                except Exception:
                    pass

    threads = []
    for name, stream in (("stdout", proc.stdout), ("stderr", proc.stderr)):
        if stream is not None:
            thread = threading.Thread(target=reader, args=(name, stream), daemon=True)
            thread.start()
            threads.append(thread)
    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            proc.kill()
        except Exception:
            pass
        proc.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=5)
    return "".join(chunks["stdout"]), "".join(chunks["stderr"]), timed_out, flags["limited"]


def _timeout(value: Any, config: ExecutorConfig) -> float:
    timeout = _float_limit(value, config.max_timeout_seconds, False, "timeout_seconds")
    return min(timeout, config.max_timeout_seconds)


def _manifest_tests(root: Path) -> set[str]:
    try:
        data = json.loads((root / "localcomet_runtime_manifest.json").read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {str(item).replace("\\", "/") for item in data.get("tests", [])}


def _subprocess_env() -> dict[str, str]:
    env = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    for key in ("SystemRoot", "WINDIR", "TEMP", "TMP"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


class _Clock:
    def __init__(self, now: Any, monotonic: Any):
        self.now = now
        self.monotonic = monotonic

    def _now(self) -> str:
        value = self.now() if callable(self.now) else self.now
        if value is None:
            return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ExecutorValidationError("invalid_action")
            return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return str(value)

    def _mono(self) -> float:
        return float(self.monotonic() if callable(self.monotonic) else time.perf_counter())

    def start(self) -> tuple[str, float]:
        return self._now(), self._mono()

    def finish(self, start: float) -> tuple[str, float]:
        return self._now(), max(0.0, round(self._mono() - start, 6))
````

### ПУТЬ: modules/autonomous_run_state_ru.py (312 строк, 14485 байт)

````python
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from modules.autonomy_policy_ru import (
    ActionProposal,
    BudgetUsage,
    KillSwitchStatus,
    PolicyDecision,
    PolicyDecisionType,
    RiskLevel,
    evaluate_action_proposal,
)

AUTONOMOUS_RUN_STATE_VERSION = "v6.83"

class RunStateValidationError(ValueError):
    pass

class RunStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

TERMINAL_STATUSES = {RunStatus.FAILED, RunStatus.COMPLETED, RunStatus.CANCELLED}
ALLOWED_TRANSITIONS = {
    RunStatus.CREATED: (RunStatus.PLANNING, RunStatus.CANCELLED),
    RunStatus.PLANNING: (RunStatus.WAITING_APPROVAL, RunStatus.RUNNING, RunStatus.PAUSED, RunStatus.FAILED, RunStatus.CANCELLED),
    RunStatus.WAITING_APPROVAL: (RunStatus.RUNNING, RunStatus.PAUSED, RunStatus.FAILED, RunStatus.CANCELLED),
    RunStatus.RUNNING: (RunStatus.VERIFYING, RunStatus.WAITING_APPROVAL, RunStatus.PAUSED, RunStatus.FAILED, RunStatus.CANCELLED),
    RunStatus.VERIFYING: (RunStatus.RUNNING, RunStatus.WAITING_APPROVAL, RunStatus.PAUSED, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED),
    RunStatus.PAUSED: (RunStatus.PLANNING, RunStatus.WAITING_APPROVAL, RunStatus.RUNNING, RunStatus.FAILED, RunStatus.CANCELLED),
    RunStatus.FAILED: (),
    RunStatus.COMPLETED: (),
    RunStatus.CANCELLED: (),
}
_RUN_ID_RE = re.compile(r"^[0-9a-f]{24}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_STEP_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_SECRET_MARKERS = ("sk-", "ghp_", "password", "passwd", r"bearer\s+", "private key", "token=", "sec" + "ret=")
_SECRET_RE = re.compile("(?i)(" + "|".join(_SECRET_MARKERS) + ")")

@dataclass(frozen=True)
class AutonomousRunState:
    run_id: str
    status: RunStatus | str
    goal_hash: str
    current_step: str | None
    completed_steps: tuple[str, ...]
    failed_steps: tuple[str, ...]
    actions_used: int
    writes_used: int
    changed_files_used: int
    changed_lines_used: int
    subprocesses_used: int
    output_bytes_used: int
    replans_used: int
    started_at: str
    updated_at: str
    termination_reason: str | None = None
    pause_reason: str | None = None
    approval_required: bool = False
    last_action_id: str | None = None

def normalize_goal(goal: str) -> str:
    text = " ".join(str(goal or "").split())
    if not text:
        raise RunStateValidationError("empty_goal")
    if len(text) > 4000:
        raise RunStateValidationError("goal_too_long")
    return text

def compute_goal_hash(goal: str) -> str:
    return hashlib.sha256(normalize_goal(goal).encode("utf-8")).hexdigest()

def _normalize_nonce(session_nonce: str) -> str:
    text = " ".join(str(session_nonce or "").split())
    if not text:
        raise RunStateValidationError("empty_session_nonce")
    if len(text) > 256:
        raise RunStateValidationError("session_nonce_too_long")
    return text

def compute_run_id(goal: str, session_nonce: str) -> str:
    goal_hash = compute_goal_hash(goal)
    source = AUTONOMOUS_RUN_STATE_VERSION + "\n" + goal_hash + "\n" + _normalize_nonce(session_nonce)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:24]

def _format_dt(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RunStateValidationError("naive_datetime")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _parse_dt(text: str) -> datetime:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception as exc:
        raise RunStateValidationError("invalid_timestamp") from exc

def _coerce_now(now: datetime | str | None) -> str:
    if now is None:
        return _format_dt(datetime.now(timezone.utc))
    if isinstance(now, datetime):
        return _format_dt(now)
    text = str(now)
    parsed = _parse_dt(text)
    return _format_dt(parsed)

def _require_monotonic(previous: str, new: str) -> None:
    if _parse_dt(new) < _parse_dt(previous):
        raise RunStateValidationError("timestamp_not_monotonic")

def _sanitize_reason(reason: str | None, *, required: bool = False) -> str | None:
    if reason is None:
        if required:
            raise RunStateValidationError("reason_required")
        return None
    text = " ".join(str(reason).split())
    if not text and required:
        raise RunStateValidationError("reason_required")
    if len(text) > 160:
        raise RunStateValidationError("reason_too_long")
    if _SECRET_RE.search(text):
        raise RunStateValidationError("unsafe_reason")
    return text or None

def _safe_step(step_id: str) -> str:
    text = str(step_id or "")
    if not _STEP_RE.match(text):
        raise RunStateValidationError("unsafe_step_id")
    return text

def create_run_state(goal: str, session_nonce: str, now: datetime | str | None = None) -> AutonomousRunState:
    stamp = _coerce_now(now)
    return AutonomousRunState(
        run_id=compute_run_id(goal, session_nonce),
        status=RunStatus.CREATED,
        goal_hash=compute_goal_hash(goal),
        current_step=None,
        completed_steps=(),
        failed_steps=(),
        actions_used=0,
        writes_used=0,
        changed_files_used=0,
        changed_lines_used=0,
        subprocesses_used=0,
        output_bytes_used=0,
        replans_used=0,
        started_at=stamp,
        updated_at=stamp,
    )

def validate_run_state(state: AutonomousRunState) -> tuple[str, ...]:
    findings: list[str] = []
    status = state.status if isinstance(state.status, RunStatus) else RunStatus(state.status) if str(state.status) in RunStatus._value2member_map_ else None
    if not _RUN_ID_RE.match(str(state.run_id)):
        findings.append("invalid_run_id")
    if not _SHA_RE.match(str(state.goal_hash)):
        findings.append("invalid_goal_hash")
    if status is None:
        findings.append("invalid_status")
    for name in ("actions_used", "writes_used", "changed_files_used", "changed_lines_used", "subprocesses_used", "output_bytes_used", "replans_used"):
        value = getattr(state, name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            findings.append(f"{name}_invalid")
    completed = tuple(state.completed_steps)
    failed = tuple(state.failed_steps)
    if tuple(sorted(set(completed))) != completed:
        findings.append("completed_steps_not_sorted_unique")
    if tuple(sorted(set(failed))) != failed:
        findings.append("failed_steps_not_sorted_unique")
    if set(completed) & set(failed):
        findings.append("step_completed_and_failed")
    for step in (*completed, *failed, *((state.current_step,) if state.current_step else ())):
        if step and not _STEP_RE.match(step):
            findings.append("unsafe_step_id")
    if state.current_step and state.current_step in completed:
        findings.append("current_step_already_completed")
    if status in TERMINAL_STATUSES and state.current_step is not None:
        findings.append("terminal_has_current_step")
    if status not in TERMINAL_STATUSES and state.termination_reason is not None:
        findings.append("non_terminal_has_termination_reason")
    if status != RunStatus.PAUSED and state.pause_reason is not None:
        findings.append("non_paused_has_pause_reason")
    if (status == RunStatus.WAITING_APPROVAL) != bool(state.approval_required):
        findings.append("approval_required_inconsistent")
    try:
        _require_monotonic(state.started_at, state.updated_at)
    except RunStateValidationError:
        findings.append("timestamps_not_monotonic")
    for reason in (state.termination_reason, state.pause_reason):
        if reason and _SECRET_RE.search(reason):
            findings.append("unsafe_reason")
    return tuple(sorted(set(findings)))

def transition_run_state(state: AutonomousRunState, new_status: RunStatus | str, *, now: datetime | str | None = None, current_step: str | None = None, reason: str | None = None, approval_required: bool | None = None) -> AutonomousRunState:
    current = state.status if isinstance(state.status, RunStatus) else RunStatus(str(state.status))
    target = new_status if isinstance(new_status, RunStatus) else RunStatus(str(new_status))
    if target == current or target not in ALLOWED_TRANSITIONS[current]:
        raise RunStateValidationError("invalid_transition")
    stamp = _coerce_now(now)
    _require_monotonic(state.updated_at, stamp)
    pause_reason = _sanitize_reason(reason, required=(target == RunStatus.PAUSED)) if target == RunStatus.PAUSED else None
    termination = _sanitize_reason(reason, required=False) if target in TERMINAL_STATUSES else None
    step = None if target in TERMINAL_STATUSES else (_safe_step(current_step) if current_step else state.current_step)
    if target == RunStatus.WAITING_APPROVAL and approval_required is False:
        raise RunStateValidationError("approval_required_inconsistent")
    if target != RunStatus.WAITING_APPROVAL and approval_required is True:
        raise RunStateValidationError("approval_required_inconsistent")
    waiting = bool(approval_required) if approval_required is not None else target == RunStatus.WAITING_APPROVAL
    return replace(state, status=target, current_step=step, updated_at=stamp, termination_reason=termination, pause_reason=pause_reason, approval_required=waiting)

def record_completed_step(state: AutonomousRunState, step_id: str, *, now: datetime | str | None = None) -> AutonomousRunState:
    step = _safe_step(step_id)
    if step in state.completed_steps:
        raise RunStateValidationError("duplicate_completed_step")
    if step in state.failed_steps:
        raise RunStateValidationError("step_already_failed")
    stamp = _coerce_now(now)
    _require_monotonic(state.updated_at, stamp)
    completed = tuple(sorted((*state.completed_steps, step)))
    current = None if state.current_step == step else state.current_step
    return replace(state, completed_steps=completed, current_step=current, updated_at=stamp)

def record_failed_step(state: AutonomousRunState, step_id: str, sanitized_reason: str, *, now: datetime | str | None = None) -> AutonomousRunState:
    step = _safe_step(step_id)
    _sanitize_reason(sanitized_reason, required=True)
    if step in state.failed_steps:
        raise RunStateValidationError("duplicate_failed_step")
    if step in state.completed_steps:
        raise RunStateValidationError("step_already_completed")
    stamp = _coerce_now(now)
    _require_monotonic(state.updated_at, stamp)
    return replace(state, failed_steps=tuple(sorted((*state.failed_steps, step))), updated_at=stamp)

def _inc(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 1_000_000_000:
        raise RunStateValidationError("invalid_increment")
    return value

def consume_run_budget(state: AutonomousRunState, *, actions: int = 0, writes: int = 0, changed_files: int = 0, changed_lines: int = 0, subprocesses: int = 0, output_bytes: int = 0, replans: int = 0, now: datetime | str | None = None) -> AutonomousRunState:
    stamp = _coerce_now(now)
    _require_monotonic(state.updated_at, stamp)
    return replace(
        state,
        actions_used=state.actions_used + _inc(actions),
        writes_used=state.writes_used + _inc(writes),
        changed_files_used=state.changed_files_used + _inc(changed_files),
        changed_lines_used=state.changed_lines_used + _inc(changed_lines),
        subprocesses_used=state.subprocesses_used + _inc(subprocesses),
        output_bytes_used=state.output_bytes_used + _inc(output_bytes),
        replans_used=state.replans_used + _inc(replans),
        updated_at=stamp,
    )

def serialize_run_state(state: AutonomousRunState) -> dict[str, Any]:
    return {
        "mode": "autonomous_run_state",
        "version": AUTONOMOUS_RUN_STATE_VERSION,
        "run_id": state.run_id,
        "status": str(state.status.value if isinstance(state.status, RunStatus) else state.status),
        "goal_hash": state.goal_hash,
        "current_step": state.current_step,
        "completed_steps": list(state.completed_steps),
        "failed_steps": list(state.failed_steps),
        "actions_used": state.actions_used,
        "writes_used": state.writes_used,
        "changed_files_used": state.changed_files_used,
        "changed_lines_used": state.changed_lines_used,
        "subprocesses_used": state.subprocesses_used,
        "output_bytes_used": state.output_bytes_used,
        "replans_used": state.replans_used,
        "started_at": state.started_at,
        "updated_at": state.updated_at,
        "termination_reason": state.termination_reason,
        "pause_reason": state.pause_reason,
        "approval_required": state.approval_required,
        "last_action_id": state.last_action_id,
    }

def policy_decision_for_run(policy: Any, state: AutonomousRunState, proposal: ActionProposal, kill_switch: KillSwitchStatus | None = None) -> PolicyDecision:
    usage = BudgetUsage(
        actions_used=state.actions_used,
        changed_files_used=state.changed_files_used,
        changed_lines_used=state.changed_lines_used,
        subprocesses_used=state.subprocesses_used,
        output_bytes_used=state.output_bytes_used,
        replans_used=state.replans_used,
    )
    decision = evaluate_action_proposal(policy, proposal, usage=usage, kill_switch=kill_switch)
    status = state.status if isinstance(state.status, RunStatus) else RunStatus(str(state.status))
    reasons = set(decision.reasons)
    if status in TERMINAL_STATUSES:
        reasons.add("run_terminal")
    if status == RunStatus.PAUSED:
        reasons.add("run_paused")
    if status == RunStatus.WAITING_APPROVAL and decision.approval_required:
        reasons.add("run_waiting_approval")
    if reasons != set(decision.reasons):
        return replace(decision, decision=PolicyDecisionType.BLOCK, allowed=False, approval_required=True, risk=max(decision.risk, RiskLevel.HIGH, key=lambda r: ("LOW", "MEDIUM", "HIGH", "CRITICAL").index(r.value)), reasons=tuple(sorted(reasons)))
    return decision
````

### ПУТЬ: modules/autonomy_policy_ru.py (461 строк, 23087 байт)

````python
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

AUTONOMY_POLICY_VERSION = "v6.83"

class _StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value

class AutonomyLevel(_StrEnum):
    LEVEL_0_INSPECT_ONLY = "LEVEL_0_INSPECT_ONLY"
    LEVEL_1_PLAN_ONLY = "LEVEL_1_PLAN_ONLY"
    LEVEL_2_SAFE_AUTOMATION = "LEVEL_2_SAFE_AUTOMATION"
    LEVEL_3_CONTROLLED_EDIT = "LEVEL_3_CONTROLLED_EDIT"
    LEVEL_4_BOUNDED_FULL_AUTONOMY = "LEVEL_4_BOUNDED_FULL_AUTONOMY"

class ActionType(_StrEnum):
    inspect = "inspect"
    analyze = "analyze"
    plan = "plan"
    test = "test"
    verify = "verify"
    create_temp = "create_temp"
    create_file = "create_file"
    edit_file = "edit_file"
    apply_patch = "apply_patch"
    execute_allowlisted = "execute_allowlisted"
    delete = "delete"
    move = "move"
    install = "install"
    network = "network"
    credential_access = "credential_access"
    secret_extraction = "secret_extraction"
    privilege_escalation = "privilege_escalation"
    persistence = "persistence"
    security_bypass = "security_bypass"
    system_change = "system_change"
    policy_change = "policy_change"
    kill_switch_change = "kill_switch_change"
    unknown = "unknown"

class RiskLevel(_StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class PolicyDecisionType(_StrEnum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    BLOCK = "BLOCK"

class KillSwitchMode(_StrEnum):
    NONE = "NONE"
    PAUSE = "PAUSE"
    DISABLE = "DISABLE"
    STOP_FILE = "STOP_FILE"

_LOW = {ActionType.inspect, ActionType.analyze, ActionType.plan, ActionType.verify}
_MEDIUM = {ActionType.test, ActionType.create_temp, ActionType.create_file, ActionType.edit_file, ActionType.apply_patch}
_HIGH = {ActionType.execute_allowlisted, ActionType.move, ActionType.delete, ActionType.install, ActionType.network, ActionType.system_change, ActionType.policy_change, ActionType.kill_switch_change}
_CRITICAL = {ActionType.credential_access, ActionType.secret_extraction, ActionType.privilege_escalation, ActionType.persistence, ActionType.security_bypass}
_PERMANENT = _CRITICAL | {ActionType.kill_switch_change}
_DEFAULT_BLOCKED = tuple(sorted(a.value for a in (
    ActionType.credential_access, ActionType.delete, ActionType.install, ActionType.kill_switch_change,
    ActionType.network, ActionType.persistence, ActionType.policy_change, ActionType.privilege_escalation,
    ActionType.secret_extraction, ActionType.security_bypass, ActionType.system_change,
)))
_PROTECTED = (".git", ".incident_backup", ".localcomet/reviewer", ".localcomet/policies", ".tmp", "__pycache__", ".localcomet/autonomy/STOP")
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_STEP_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")

def _as_enum(enum: type[_StrEnum], value: Any) -> _StrEnum | None:
    try:
        return value if isinstance(value, enum) else enum(str(value))
    except Exception:
        return None

def _finite_number(value: Any, *, allow_zero: bool, maximum: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name}_invalid")
    if value < 0 or (not allow_zero and value == 0) or value > maximum:
        raise ValueError(f"{name}_out_of_bounds")
    return float(value)

def _int_limit(value: Any, *, allow_zero: bool, maximum: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name}_invalid")
    if value < 0 or (not allow_zero and value == 0) or value > maximum:
        raise ValueError(f"{name}_out_of_bounds")
    return value

@dataclass(frozen=True)
class AutonomyBudget:
    max_actions: int = 50
    max_runtime_seconds: float = 900.0
    max_changed_files: int = 5
    max_changed_lines: int = 500
    max_subprocesses: int = 20
    max_output_bytes: int = 1_000_000
    max_replans: int = 3

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_actions", _int_limit(self.max_actions, allow_zero=False, maximum=1000, name="max_actions"))
        object.__setattr__(self, "max_runtime_seconds", _finite_number(self.max_runtime_seconds, allow_zero=False, maximum=86400, name="max_runtime_seconds"))
        object.__setattr__(self, "max_changed_files", _int_limit(self.max_changed_files, allow_zero=True, maximum=100, name="max_changed_files"))
        object.__setattr__(self, "max_changed_lines", _int_limit(self.max_changed_lines, allow_zero=True, maximum=50000, name="max_changed_lines"))
        object.__setattr__(self, "max_subprocesses", _int_limit(self.max_subprocesses, allow_zero=True, maximum=500, name="max_subprocesses"))
        object.__setattr__(self, "max_output_bytes", _int_limit(self.max_output_bytes, allow_zero=True, maximum=100_000_000, name="max_output_bytes"))
        object.__setattr__(self, "max_replans", _int_limit(self.max_replans, allow_zero=True, maximum=20, name="max_replans"))

@dataclass(frozen=True)
class BudgetUsage:
    actions_used: int = 0
    runtime_seconds_used: float = 0.0
    changed_files_used: int = 0
    changed_lines_used: int = 0
    subprocesses_used: int = 0
    output_bytes_used: int = 0
    replans_used: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "actions_used", _int_limit(self.actions_used, allow_zero=True, maximum=1_000_000, name="actions_used"))
        object.__setattr__(self, "runtime_seconds_used", _finite_number(self.runtime_seconds_used, allow_zero=True, maximum=1_000_000, name="runtime_seconds_used"))
        for name in ("changed_files_used", "changed_lines_used", "subprocesses_used", "output_bytes_used", "replans_used"):
            object.__setattr__(self, name, _int_limit(getattr(self, name), allow_zero=True, maximum=1_000_000_000, name=name))

@dataclass(frozen=True)
class AutonomyPolicy:
    version: str = AUTONOMY_POLICY_VERSION
    level: AutonomyLevel | str = AutonomyLevel.LEVEL_1_PLAN_ONLY
    allowed_roots: tuple[Path, ...] = field(default_factory=tuple)
    temporary_roots: tuple[Path, ...] = field(default_factory=tuple)
    allowed_actions: tuple[str, ...] = ("analyze", "inspect", "plan", "verify")
    blocked_actions: tuple[str, ...] = _DEFAULT_BLOCKED
    budgets: AutonomyBudget = field(default_factory=AutonomyBudget)
    required_approval_for_writes: bool = True
    required_approval_for_execute: bool = True
    required_approval_for_network: bool = True
    required_approval_for_delete: bool = True
    protected_relative_paths: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_roots", tuple(Path(p) for p in self.allowed_roots))
        object.__setattr__(self, "temporary_roots", tuple(Path(p) for p in self.temporary_roots))
        object.__setattr__(self, "allowed_actions", tuple(sorted(str(a) for a in self.allowed_actions)))
        object.__setattr__(self, "blocked_actions", tuple(sorted(str(a) for a in self.blocked_actions)))
        object.__setattr__(self, "protected_relative_paths", tuple(sorted(str(p).replace("\\", "/").strip("/") for p in self.protected_relative_paths if str(p).strip())))

@dataclass(frozen=True)
class ActionProposal:
    action_id: str
    action_type: str
    target: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    read_only: bool = True
    reversible: bool = True
    expected_original_sha256: str | None = None
    estimated_changed_files: int = 0
    estimated_changed_lines: int = 0
    estimated_subprocesses: int = 0
    estimated_output_bytes: int = 0
    requires_network: bool = False
    requires_elevation: bool = False

@dataclass(frozen=True)
class KillSwitchStatus:
    active: bool = False
    mode: KillSwitchMode | str = KillSwitchMode.NONE
    reason: str | None = None

@dataclass(frozen=True)
class PolicyDecision:
    action_id: str
    decision: PolicyDecisionType
    allowed: bool
    approval_required: bool
    risk: RiskLevel
    normalized_target: str
    reasons: tuple[str, ...]
    budget: Mapping[str, Any]
    kill_switch: KillSwitchStatus

def default_autonomy_budget() -> AutonomyBudget:
    return AutonomyBudget()

def resolve_project_root(root: str | Path | None = None) -> Path:
    value = root if root is not None else os.environ.get("LOCALCOMET_ROOT") or os.environ.get("LOCALCOMET_ROOT_DIR")
    if value is None or str(value).strip() == "":
        value = Path(__file__).resolve().parents[1]
    return Path(value).expanduser().resolve()

def default_autonomy_policy(root: str | Path | None = None) -> AutonomyPolicy:
    return AutonomyPolicy(allowed_roots=(resolve_project_root(root),), budgets=default_autonomy_budget())

def _relative_display(root: Path, target: Path | None, rel: str = "") -> str:
    return "<PROJECT_ROOT>" + (f"/{rel}" if rel else "")

def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        if os.name == "nt":
            return str(child).lower().startswith(str(parent).lower().rstrip("\\/") + os.sep)
        return False

def validate_target_path(root: str | Path, target: str | Path) -> dict[str, Any]:
    text = str(target)
    reasons: list[str] = []
    if not text.strip():
        reasons.append("empty_target")
    if "\x00" in text:
        reasons.append("nul_target")
    if text.startswith(("\\\\", "//")):
        reasons.append("unc_target")
    if re.match(r"^[A-Za-z]:(?![\\/])", text) or re.match(r"^[A-Za-z]:[\\/]", text):
        reasons.append("windows_absolute_or_drive_target")
    if text.startswith(("/", "\\")):
        reasons.append("absolute_target")
    normalized = text.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        reasons.append("traversal_target")
    if any(p.split(".")[0].upper() in _RESERVED for p in parts):
        reasons.append("reserved_device_target")
    root_path = Path(root).expanduser().resolve()
    rel = "/".join(parts)
    candidate = root_path.joinpath(*parts) if parts else root_path
    try:
        resolved = candidate.resolve(strict=False)
        if not _is_relative_to(resolved, root_path):
            reasons.append("target_escapes_root")
    except Exception:
        reasons.append("target_resolution_failed")
    protected = is_protected_target(root_path, rel) if rel else False
    if protected:
        reasons.append("protected_target")
    return {
        "ok": not reasons,
        "normalized_target": _relative_display(root_path, candidate, rel if not reasons or protected else ""),
        "relative_path": rel,
        "protected": protected,
        "reasons": tuple(sorted(set(reasons))),
    }

def is_protected_target(root: str | Path, target: str | Path) -> bool:
    rel = str(target).replace("\\", "/").strip("/")
    protected = {p.lower() for p in (*_PROTECTED,)}
    rel_lower = rel.lower()
    return any(rel_lower == p or rel_lower.startswith(p + "/") for p in protected)

def _risk_for(action: ActionType | None) -> RiskLevel:
    if action in _CRITICAL:
        return RiskLevel.CRITICAL
    if action in _HIGH:
        return RiskLevel.HIGH
    if action in _MEDIUM:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW

def _json_safe(value: Any, depth: int = 0) -> bool:
    if depth > 5:
        return False
    if value is None or isinstance(value, (str, int, float, bool)):
        return not (isinstance(value, float) and not math.isfinite(value)) and len(str(value)) <= 2048
    if isinstance(value, (list, tuple)):
        return len(value) <= 50 and all(_json_safe(v, depth + 1) for v in value)
    if isinstance(value, dict):
        return len(value) <= 50 and all(isinstance(k, str) and len(k) <= 128 and _json_safe(v, depth + 1) for k, v in value.items())
    return False

def validate_autonomy_policy(policy: AutonomyPolicy) -> tuple[str, ...]:
    findings: list[str] = []
    if policy.version != AUTONOMY_POLICY_VERSION:
        findings.append("invalid_policy_version")
    if _as_enum(AutonomyLevel, policy.level) is None:
        findings.append("unknown_autonomy_level")
    for action in (*policy.allowed_actions, *policy.blocked_actions):
        if _as_enum(ActionType, action) is None:
            findings.append("unknown_action_type")
    if not policy.allowed_roots:
        findings.append("missing_allowed_root")
    for flag in ("required_approval_for_writes", "required_approval_for_execute", "required_approval_for_network", "required_approval_for_delete"):
        if not isinstance(getattr(policy, flag), bool):
            findings.append(f"{flag}_not_bool")
    return tuple(sorted(set(findings)))

def _proposal_findings(proposal: ActionProposal, level: AutonomyLevel) -> tuple[list[str], ActionType | None]:
    reasons: list[str] = []
    action = _as_enum(ActionType, proposal.action_type)
    if action is None or action == ActionType.unknown:
        reasons.append("unknown_action_type")
    if not _ID_RE.match(str(proposal.action_id)):
        reasons.append("malformed_action_id")
    if not _json_safe(dict(proposal.arguments)):
        reasons.append("malformed_arguments")
    for name in ("estimated_changed_files", "estimated_changed_lines", "estimated_subprocesses", "estimated_output_bytes"):
        try:
            _int_limit(getattr(proposal, name), allow_zero=True, maximum=1_000_000_000, name=name)
        except ValueError:
            reasons.append(f"{name}_invalid")
    if proposal.read_only and (proposal.estimated_changed_files or proposal.estimated_changed_lines):
        reasons.append("read_only_has_write_estimate")
    if proposal.requires_elevation:
        reasons.append("requires_elevation")
    if action in {ActionType.create_file, ActionType.edit_file, ActionType.apply_patch} and level in {AutonomyLevel.LEVEL_3_CONTROLLED_EDIT, AutonomyLevel.LEVEL_4_BOUNDED_FULL_AUTONOMY}:
        if not proposal.expected_original_sha256 or not _SHA_RE.match(proposal.expected_original_sha256):
            reasons.append("expected_original_sha256_required")
    if proposal.expected_original_sha256 is not None and not _SHA_RE.match(proposal.expected_original_sha256):
        reasons.append("invalid_expected_original_sha256")
    return reasons, action

def evaluate_budget(budget: AutonomyBudget, usage: BudgetUsage, proposal: ActionProposal | None = None) -> dict[str, Any]:
    add_actions = 1 if proposal else 0
    add_changed_files = int(getattr(proposal, "estimated_changed_files", 0) or 0)
    add_changed_lines = int(getattr(proposal, "estimated_changed_lines", 0) or 0)
    add_subprocesses = int(getattr(proposal, "estimated_subprocesses", 0) or 0)
    add_output = int(getattr(proposal, "estimated_output_bytes", 0) or 0)
    projected = {
        "actions": usage.actions_used + add_actions,
        "runtime_seconds": usage.runtime_seconds_used,
        "changed_files": usage.changed_files_used + add_changed_files,
        "changed_lines": usage.changed_lines_used + add_changed_lines,
        "subprocesses": usage.subprocesses_used + add_subprocesses,
        "output_bytes": usage.output_bytes_used + add_output,
        "replans": usage.replans_used,
    }
    limits = {
        "actions": budget.max_actions,
        "runtime_seconds": budget.max_runtime_seconds,
        "changed_files": budget.max_changed_files,
        "changed_lines": budget.max_changed_lines,
        "subprocesses": budget.max_subprocesses,
        "output_bytes": budget.max_output_bytes,
        "replans": budget.max_replans,
    }
    exceeded = sorted(k for k, v in projected.items() if v > limits[k])
    return {
        "within_limits": not exceeded,
        "exceeded": exceeded,
        "remaining_actions": max(0, budget.max_actions - projected["actions"]),
        "remaining_runtime_seconds": max(0.0, float(budget.max_runtime_seconds - projected["runtime_seconds"])),
        "remaining_changed_files": max(0, budget.max_changed_files - projected["changed_files"]),
        "remaining_changed_lines": max(0, budget.max_changed_lines - projected["changed_lines"]),
        "remaining_subprocesses": max(0, budget.max_subprocesses - projected["subprocesses"]),
        "remaining_output_bytes": max(0, budget.max_output_bytes - projected["output_bytes"]),
        "remaining_replans": max(0, budget.max_replans - projected["replans"]),
    }

def inspect_kill_switches(root: str | Path | None = None, environ: Mapping[str, str] | None = None) -> KillSwitchStatus:
    env = os.environ if environ is None else environ
    truthy = {"1", "true", "yes", "on"}
    if str(env.get("LOCALCOMET_AUTONOMY_DISABLED", "")).strip().lower() in truthy:
        return KillSwitchStatus(True, KillSwitchMode.DISABLE, "autonomy_disabled")
    root_path = resolve_project_root(root)
    stop_path = root_path / ".localcomet" / "autonomy" / "STOP"
    try:
        if stop_path.exists():
            reason = "stop_file_symlink" if stop_path.is_symlink() else "stop_file_present"
            return KillSwitchStatus(True, KillSwitchMode.STOP_FILE, reason)
    except Exception:
        return KillSwitchStatus(True, KillSwitchMode.STOP_FILE, "stop_file_check_failed")
    if str(env.get("LOCALCOMET_AUTONOMY_PAUSE", "")).strip().lower() in truthy:
        return KillSwitchStatus(True, KillSwitchMode.PAUSE, "autonomy_paused")
    return KillSwitchStatus(False, KillSwitchMode.NONE, None)

def evaluate_action_proposal(policy: AutonomyPolicy, proposal: ActionProposal, usage: BudgetUsage | None = None, kill_switch: KillSwitchStatus | None = None) -> PolicyDecision:
    usage = usage or BudgetUsage()
    kill_switch = kill_switch or KillSwitchStatus()
    level = _as_enum(AutonomyLevel, policy.level) or AutonomyLevel.LEVEL_1_PLAN_ONLY
    reasons = list(validate_autonomy_policy(policy))
    p_reasons, action = _proposal_findings(proposal, level)
    reasons.extend(p_reasons)
    target_info = validate_target_path(policy.allowed_roots[0], proposal.target) if policy.allowed_roots else {"ok": False, "normalized_target": "<PROJECT_ROOT>", "reasons": ("missing_allowed_root",)}
    reasons.extend(str(r) for r in target_info.get("reasons", ()))
    budget = evaluate_budget(policy.budgets, usage, proposal)
    if not budget["within_limits"]:
        reasons.extend(f"budget_{item}_exceeded" for item in budget["exceeded"])
    risk = _risk_for(action)
    if action in _PERMANENT or str(proposal.action_type) in policy.blocked_actions:
        reasons.append("permanent_block")
    if proposal.requires_network and (policy.required_approval_for_network or ActionType.network.value in policy.blocked_actions):
        reasons.append("network_unsupported")
    if kill_switch.active:
        reasons.append("kill_switch_active")
    if level == AutonomyLevel.LEVEL_0_INSPECT_ONLY and (action not in {ActionType.inspect, ActionType.analyze} or not proposal.read_only):
        reasons.append("level_0_inspect_only")
    if level == AutonomyLevel.LEVEL_1_PLAN_ONLY and action != ActionType.plan:
        reasons.append("level_plan_only_execution_disabled")
    if level == AutonomyLevel.LEVEL_2_SAFE_AUTOMATION and action in {ActionType.create_file, ActionType.edit_file, ActionType.apply_patch, ActionType.delete, ActionType.install, ActionType.network, ActionType.system_change}:
        reasons.append("level_2_action_not_executable")
    approval = False
    if action in {ActionType.test, ActionType.create_temp, ActionType.create_file, ActionType.edit_file, ActionType.apply_patch, ActionType.execute_allowlisted, ActionType.delete, ActionType.move, ActionType.network}:
        approval = True
    blocked = bool(reasons) and any(r not in {"approval_required"} for r in reasons)
    if risk == RiskLevel.CRITICAL or kill_switch.active or not budget["within_limits"]:
        blocked = True
    decision = PolicyDecisionType.BLOCK if blocked else (PolicyDecisionType.REQUIRE_APPROVAL if approval else PolicyDecisionType.ALLOW)
    return PolicyDecision(
        action_id=str(proposal.action_id),
        decision=decision,
        allowed=decision == PolicyDecisionType.ALLOW,
        approval_required=decision == PolicyDecisionType.REQUIRE_APPROVAL or approval,
        risk=risk,
        normalized_target=str(target_info.get("normalized_target", "<PROJECT_ROOT>")),
        reasons=tuple(sorted(set(reasons))),
        budget=budget,
        kill_switch=kill_switch,
    )

def serialize_policy(policy: AutonomyPolicy) -> dict[str, Any]:
    return {
        "mode": "autonomy_policy",
        "version": policy.version,
        "level": str(policy.level),
        "allowed_roots": ["<PROJECT_ROOT>" for _ in policy.allowed_roots],
        "temporary_roots": ["<TEMP_ROOT>" for _ in policy.temporary_roots],
        "allowed_actions": sorted(policy.allowed_actions),
        "blocked_actions": sorted(policy.blocked_actions),
        "budgets": {
            "max_actions": policy.budgets.max_actions,
            "max_changed_files": policy.budgets.max_changed_files,
            "max_changed_lines": policy.budgets.max_changed_lines,
            "max_output_bytes": policy.budgets.max_output_bytes,
            "max_replans": policy.budgets.max_replans,
            "max_runtime_seconds": policy.budgets.max_runtime_seconds,
            "max_subprocesses": policy.budgets.max_subprocesses,
        },
        "approval": {
            "required_for_delete": policy.required_approval_for_delete,
            "required_for_execute": policy.required_approval_for_execute,
            "required_for_network": policy.required_approval_for_network,
            "required_for_writes": policy.required_approval_for_writes,
        },
        "protected_relative_paths": sorted(policy.protected_relative_paths),
    }

def serialize_policy_decision(decision: PolicyDecision) -> dict[str, Any]:
    return {
        "mode": "autonomy_policy_decision",
        "version": AUTONOMY_POLICY_VERSION,
        "action_id": decision.action_id,
        "decision": decision.decision.value,
        "allowed": decision.allowed,
        "approval_required": decision.approval_required,
        "risk": decision.risk.value,
        "normalized_target": decision.normalized_target,
        "reasons": list(decision.reasons),
        "budget": {k: decision.budget[k] for k in ("within_limits", "remaining_actions", "remaining_runtime_seconds", "remaining_changed_files", "remaining_changed_lines", "remaining_subprocesses", "remaining_output_bytes", "remaining_replans")},
        "kill_switch": {"active": decision.kill_switch.active, "mode": str(decision.kill_switch.mode), "reason": decision.kill_switch.reason},
    }
````

### ПУТЬ: modules/browser.py (464 строк, 12638 байт)

````python
import threading
import urllib.parse
from pathlib import Path
from modules.project_paths import projects_dir

from playwright.sync_api import sync_playwright

from core.state import set_value, get_value


_playwright = None
_browser = None
_page = None
_owner_thread_id = None

PROJECTS_DIR = projects_dir()


def _remember_error(error):
    text = str(error or "")
    set_value("last_browser_error", text)
    return text


def _clear_error():
    set_value("last_browser_error", "")


def _is_closed_error(error):
    text = str(error or "").lower()

    markers = [
        "target page, context or browser has been closed",
        "browser has been closed",
        "context has been closed",
        "target closed",
        "page closed",
        "closed",
        "cannot switch to a different thread",
        "greenlet",
    ]

    return any(marker in text for marker in markers)


def _reset_browser(stop_playwright: bool = False, reason: str = ""):
    global _playwright, _browser, _page, _owner_thread_id

    errors = []

    try:
        if _page is not None:
            _page.close()
    except Exception as e:
        errors.append(f"page.close: {e}")

    try:
        if _browser is not None:
            _browser.close()
    except Exception as e:
        errors.append(f"browser.close: {e}")

    if stop_playwright:
        try:
            if _playwright is not None:
                _playwright.stop()
        except Exception as e:
            errors.append(f"playwright.stop: {e}")

        _playwright = None
        _owner_thread_id = None

    _page = None
    _browser = None

    set_value("last_browser_thread_reset_reason", str(reason or "reset_browser"))
    set_value("last_browser_thread_reset_errors", "\n".join(errors))
    set_value("last_browser_owner_thread_id", str(_owner_thread_id or ""))

    return errors


def _ensure_thread_owner():
    global _owner_thread_id

    current_thread_id = threading.get_ident()

    if _owner_thread_id is None:
        _owner_thread_id = current_thread_id
        set_value("last_browser_owner_thread_id", str(_owner_thread_id))
        return

    if _owner_thread_id != current_thread_id:
        old_thread_id = _owner_thread_id
        _reset_browser(
            stop_playwright=True,
            reason=f"thread_changed old={old_thread_id} new={current_thread_id}",
        )
        _owner_thread_id = current_thread_id
        set_value("last_browser_owner_thread_id", str(_owner_thread_id))


def close_browser_for_test():
    _reset_browser(stop_playwright=True, reason="close_browser_for_test")
    set_value("last_browser_error", "")
    return "Browser test: браузер программно закрыт полностью."


def _get_page(force_new: bool = False):
    global _playwright, _browser, _page, _owner_thread_id

    _ensure_thread_owner()

    if force_new:
        _reset_browser(stop_playwright=True, reason="force_new")
        _ensure_thread_owner()

    if _playwright is None:
        _playwright = sync_playwright().start()
        _owner_thread_id = threading.get_ident()
        set_value("last_browser_owner_thread_id", str(_owner_thread_id))

    try:
        if _browser is None or not _browser.is_connected():
            _browser = _playwright.chromium.launch(headless=False)
    except Exception:
        _reset_browser(stop_playwright=True, reason="browser_connection_failed")
        _ensure_thread_owner()
        _playwright = sync_playwright().start()
        _owner_thread_id = threading.get_ident()
        set_value("last_browser_owner_thread_id", str(_owner_thread_id))
        _browser = _playwright.chromium.launch(headless=False)

    try:
        if _page is None or _page.is_closed():
            _page = _browser.new_page()
    except Exception:
        _reset_browser(stop_playwright=True, reason="page_recreate_failed")
        _ensure_thread_owner()
        _playwright = sync_playwright().start()
        _owner_thread_id = threading.get_ident()
        set_value("last_browser_owner_thread_id", str(_owner_thread_id))
        _browser = _playwright.chromium.launch(headless=False)
        _page = _browser.new_page()

    return _page


def get_active_page_for_actions():
    return _get_page()


def get_browser_pages_for_actions():
    page = _get_page()
    return page.context.pages


def set_active_page_for_actions(index: int):
    global _page

    pages = get_browser_pages_for_actions()

    if index < 0 or index >= len(pages):
        raise IndexError(f"Нет вкладки с индексом {index}")

    _page = pages[index]
    _page.bring_to_front()
    set_value("current_url", _page.url)
    return _page


def _safe_page_call(func, recovery=None):
    try:
        _clear_error()
        return func(_get_page())
    except Exception as e:
        _remember_error(e)

        if not _is_closed_error(e):
            raise

        _reset_browser(stop_playwright=True, reason=f"recoverable_error: {e}")

        if recovery is not None:
            return recovery(_get_page())

        return func(_get_page())


def _duckduckgo_url(query):
    q = urllib.parse.quote_plus(str(query or ""))
    return f"https://duckduckgo.com/html/?q={q}"


def _search_url(query, engine="duckduckgo"):
    q = urllib.parse.quote_plus(str(query or ""))

    if engine == "bing":
        return f"https://www.bing.com/search?q={q}"

    return _duckduckgo_url(query)


def _goto_search_page(page, query, engine="duckduckgo"):
    url = _search_url(query, engine=engine)
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)

    set_value("last_browser_query", query)
    set_value("current_url", url)
    return url


def ensure_search_page(query=None):
    query = str(query or get_value("last_browser_query", "") or "").strip()

    if not query:
        return "Нет last_browser_query. Сначала выполни поиск."

    def run(page):
        url = _goto_search_page(page, query)
        return f"Открыл страницу поиска DuckDuckGo заново:\n{url}"

    return _safe_page_call(run)


def open_url(url):
    if not url:
        return "URL пустой."

    if not (
        url.startswith("http://")
        or url.startswith("https://")
        or url.startswith("file://")
    ):
        return open_local_site(url)

    def run(page):
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)
        set_value("current_url", url)
        return f"Открыл: {url}"

    return _safe_page_call(run)


def open_local_site(folder):
    file_path = PROJECTS_DIR / folder / "index.html"

    if not file_path.exists():
        return f"index.html не найден: {file_path}"

    url = file_path.resolve().as_uri()

    def run(page):
        page.goto(url, wait_until="domcontentloaded")
        set_value("current_url", url)
        return f"Открыл локальный сайт: {file_path}"

    return _safe_page_call(run)


def search(query, engine="duckduckgo"):
    query = str(query or "").strip()

    if not query:
        return "Поисковый запрос пустой."

    def run(page):
        _goto_search_page(page, query, engine=engine)
        return f"Ищу через {engine}: {query}"

    return _safe_page_call(run)


def read_page(limit=4000):
    def run(page):
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)

        title = page.title()
        current_url = page.url
        set_value("current_url", current_url)

        try:
            text = page.locator("body").inner_text(timeout=10000)
        except Exception as e:
            text = f"Не удалось прочитать страницу: {e}"
            _remember_error(e)

        return f"URL: {current_url}\nTITLE: {title}\n\n{text[:limit]}"

    def recovery(page):
        query = get_value("last_browser_query", "")

        if query:
            _goto_search_page(page, query)
            page.wait_for_timeout(1000)

        return run(page)

    return _safe_page_call(run, recovery=recovery)


def _normalize_result_url(href):
    if not href:
        return None

    if href.startswith("//"):
        href = "https:" + href

    parsed = urllib.parse.urlparse(href)
    query = urllib.parse.parse_qs(parsed.query)

    if "uddg" in query:
        href = urllib.parse.unquote(query["uddg"][0])

    bad_parts = [
        "duckduckgo.com/html",
        "duckduckgo.com/y.js",
        "google.com/search",
        "accounts.google",
        "bing.com/search",
        "youtube.com",
        "javascript:",
        "mailto:",
    ]

    if not href.startswith("http"):
        return None

    if any(bad in href for bad in bad_parts):
        return None

    return href


def get_search_result_links(limit=5):
    def run(page):
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)

        raw_links = page.locator("a").evaluate_all(
            """
            els => els.map(a => ({
                text: (a.innerText || '').trim(),
                href: a.href || ''
            }))
            """
        )

        clean = []
        seen = set()

        for item in raw_links:
            title = item.get("text", "").strip()
            href = item.get("href", "").strip()

            url = _normalize_result_url(href)

            if not url:
                continue

            if url in seen:
                continue

            if len(title) < 5:
                continue

            seen.add(url)

            clean.append({
                "title": title[:120],
                "url": url
            })

            if len(clean) >= limit:
                break

        return clean

    def recovery(page):
        query = get_value("last_browser_query", "")

        if query:
            _goto_search_page(page, query)

        return run(page)

    return _safe_page_call(run, recovery=recovery)


def click_text(text):
    def run(page):
        page.get_by_text(text, exact=False).first.click(timeout=7000)
        set_value("current_url", page.url)
        return f"Кликнул: {text}"

    return _safe_page_call(run)


def click_first_link():
    def run(page):
        links = get_search_result_links(limit=1)

        if not links:
            query = get_value("last_browser_query", "")

            if query:
                _goto_search_page(page, query)
                links = get_search_result_links(limit=1)

        if not links:
            raise Exception("Не нашел подходящую ссылку результата.")

        url = links[0]["url"]
        title = links[0]["title"]

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)

        set_value("current_url", url)

        return f"Открыл первый результат: {title}\n{url}"

    def recovery(page):
        query = get_value("last_browser_query", "")

        if query:
            _goto_search_page(page, query)

        return run(page)

    return _safe_page_call(run, recovery=recovery)


def browser_status():
    current_url = get_value("current_url", "нет")
    query = get_value("last_browser_query", "нет")
    error = get_value("last_browser_error", "нет")
    owner_thread = get_value("last_browser_owner_thread_id", "нет")
    reset_reason = get_value("last_browser_thread_reset_reason", "нет")

    page_state = "нет"

    try:
        page = _get_page()
        page_state = "открыта" if not page.is_closed() else "закрыта"
        if page.url:
            current_url = page.url
            set_value("current_url", current_url)
    except Exception as e:
        page_state = "ошибка"
        _remember_error(e)

    return (
        "Browser status:\n"
        f"- page: {page_state}\n"
        f"- current_url: {current_url}\n"
        f"- last_browser_query: {query}\n"
        f"- last_browser_error: {error or 'нет'}\n"
        f"- last_browser_owner_thread_id: {owner_thread}\n"
        f"- last_browser_thread_reset_reason: {reset_reason}"
    )
````

### ПУТЬ: modules/browser_actions.py (567 строк, 17858 байт)

````python
import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import get_value, set_value
from modules.browser import (
    click_first_link,
    ensure_search_page,
    get_active_page_for_actions,
    get_browser_pages_for_actions,
    open_url,
    set_active_page_for_actions,
)


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports"
ACTION_REPORTS_DIR = REPORTS_DIR / "browser_actions"
SCREENSHOTS_DIR = REPORTS_DIR / "browser_screenshots"
BLANK_PAGE_MESSAGE = (
    "Страница пустая. Сначала выполни: browser search <запрос>, потом browser open first."
)

DANGEROUS_MARKERS = [
    "оплатить",
    "купить",
    "заказать",
    "удалить",
    "подтвердить",
    "отправить заявку",
    "ставка",
    "поставить",
    "перевести деньги",
    "login submit",
    "password",
    "card",
    "cvv",
    "bank",
    "kaspi",
    "parimatch",
    "gambling",
    "betting",
]


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    ACTION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def _short(text, limit=1800):
    text = str(text or "")

    if len(text) <= limit:
        return text

    return text[:limit] + "\n...[обрезано]"


def _is_dangerous_browser_action(text):
    lower = str(text or "").lower()
    return any(marker in lower for marker in DANGEROUS_MARKERS)


def _stop_if_dangerous(text):
    if _is_dangerous_browser_action(text):
        return "STOP: действие требует ручного подтверждения пользователя."

    return ""


def _page_state(page):
    if page is None:
        return "нет"

    try:
        return "закрыта" if page.is_closed() else "открыта"
    except Exception:
        return "ошибка"


def _is_blank_url(value):
    return str(value or "").strip().lower() in ["", "about:blank", "нет", "none", "null"]


def _safe_page_url(page):
    try:
        return str(page.url or "").strip()
    except Exception:
        return ""


def _safe_page_title(page):
    try:
        return str(page.title() or "").strip()
    except Exception:
        return ""


def _safe_body_text(page):
    try:
        return str(page.locator("body").inner_text(timeout=2000) or "").strip()
    except Exception:
        return ""


def _is_blank_page(page):
    page_url = _safe_page_url(page)
    current_url = str(get_value("current_url", "") or "").strip()

    if _is_blank_url(page_url):
        return True

    if _is_blank_url(current_url) and not page_url:
        return True

    return not _safe_page_title(page) and not _safe_body_text(page)


def _ensure_action_page(page=None, recover=True):
    if page is None:
        page = get_active_page_for_actions()

    if not _is_blank_page(page):
        page_url = _safe_page_url(page)

        if page_url:
            set_value("current_url", page_url)

        return page

    if not recover:
        return BLANK_PAGE_MESSAGE

    query = str(get_value("last_browser_query", "") or "").strip()

    if not query:
        return BLANK_PAGE_MESSAGE

    try:
        ensure_search_page(query)
        click_first_link()
        recovered_page = get_active_page_for_actions()

        if not _is_blank_page(recovered_page):
            recovered_url = _safe_page_url(recovered_page)

            if recovered_url:
                set_value("current_url", recovered_url)

            set_value("last_browser_action_recovery", f"recovered_from_query: {query}")
            return recovered_page

        return (
            "Страница пустая. Попытка восстановления по last_browser_query не дала "
            f"содержимого: {query}. Повтори: browser search <запрос>, потом browser open first."
        )
    except Exception as e:
        set_value("last_browser_error", str(e))
        return (
            "Страница пустая. Не удалось восстановить страницу по last_browser_query: "
            f"{query}. Ошибка: {e}\n"
            "Сначала выполни: browser search <запрос>, потом browser open first."
        )


def _blank_action_message(action, reason=""):
    reason = str(reason or BLANK_PAGE_MESSAGE)
    messages = {
        "summarize": "Summary недоступен, потому что страница пустая.",
        "links": "Ссылки не найдены, потому что страница пустая.",
        "inputs": "Поля ввода не найдены, потому что страница пустая.",
        "find_text": "Текст не найден, потому что страница пустая.",
        "click_text": "Клик не выполнен, потому что страница пустая.",
        "screenshot": "Скриншот не сделан, потому что страница пустая.",
    }
    return f"{messages.get(action, 'Browser action остановлен, потому что страница пустая.')}\n{reason}"


def _action_page_or_stop(page, action):
    ready = _ensure_action_page(page)

    if isinstance(ready, str):
        return None, _blank_action_message(action, ready)

    return ready, ""


def _remember(action, result="", error="", screenshot_path=""):
    set_value("last_browser_action", action)
    set_value("last_browser_result", _short(result))
    set_value("last_browser_error", str(error or ""))

    if screenshot_path:
        set_value("last_browser_screenshot", str(screenshot_path))


def _save_action_report(action, url_before, url_after, result, screenshot_path="", error=""):
    _ensure_dirs()
    path = ACTION_REPORTS_DIR / f"browser_action_{_stamp()}.md"
    lines = [
        "# Browser Action Report",
        "",
        f"- started_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- action: {action}",
        f"- url_before: {url_before}",
        f"- url_after: {url_after}",
        f"- screenshot_path: {screenshot_path or 'нет'}",
        f"- errors: {error or 'нет'}",
        "",
        "## Result",
        "```text",
        str(result or ""),
        "```",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_browser_action_report", str(path))
    return path


def _run_action(action, func, safety_text=""):
    stop = _stop_if_dangerous(safety_text)

    if stop:
        _remember(action, stop, stop)
        return stop

    page = None
    url_before = get_value("current_url", "нет")

    try:
        page = get_active_page_for_actions()
        if page.url:
            url_before = page.url
        result, screenshot_path = func(page)
        url_after = page.url if page is not None else url_before
        set_value("current_url", url_after)
        _remember(action, result, "", screenshot_path)
        _save_action_report(action, url_before, url_after, result, screenshot_path)
        return result
    except Exception as e:
        url_after = ""
        try:
            url_after = page.url if page is not None else url_before
        except Exception:
            url_after = url_before

        error = str(e)
        _remember(action, "", error)
        _save_action_report(action, url_before, url_after, "", error=error)
        return f"Browser action failed: {action}\nОшибка: {error}"


def browser_action_status():
    def run(page):
        title = ""
        current_url = get_value("current_url", "нет")

        try:
            title = page.title()
            current_url = page.url or current_url
        except Exception:
            pass

        result = (
            "Browser Action status:\n"
            f"- page: {_page_state(page)}\n"
            f"- current_url: {current_url}\n"
            f"- title: {title or 'нет'}\n"
            f"- last_browser_query: {get_value('last_browser_query', 'нет')}\n"
            f"- last_browser_action: {get_value('last_browser_action', 'нет')}\n"
            f"- last_browser_error: {get_value('last_browser_error', 'нет') or 'нет'}"
        )
        return result, ""

    return _run_action("action_status", run)


def screenshot_page():
    def run(page):
        page, stop = _action_page_or_stop(page, "screenshot")

        if stop:
            return stop, ""

        _ensure_dirs()
        path = SCREENSHOTS_DIR / f"browser_{_stamp()}.png"
        page.screenshot(path=str(path), full_page=True)
        return f"Screenshot сохранен:\n{path}", str(path)

    return _run_action("screenshot", run)


def find_text_on_page(text):
    def run(page):
        page, stop = _action_page_or_stop(page, "find_text")

        if stop:
            return f"{stop}\nЗапрошенный текст: {text}", ""

        body = page.locator("body").inner_text(timeout=10000)
        lower = body.lower()
        needle = str(text or "").lower()
        index = lower.find(needle)

        if index < 0:
            return f"Текст не найден: {text}", ""

        start = max(0, index - 160)
        end = min(len(body), index + len(str(text)) + 160)
        return f"Текст найден: {text}\n\nКонтекст:\n{body[start:end]}", ""

    return _run_action("find_text", run, text)


def click_by_text(text):
    def run(page):
        page, stop = _action_page_or_stop(page, "click_text")

        if stop:
            return f"{stop}\nТекст для клика: {text}", ""

        page.get_by_text(str(text or ""), exact=False).first.click(timeout=7000)
        page.wait_for_timeout(500)
        return f"Клик по тексту выполнен: {text}", ""

    return _run_action("click_text", run, text)


def click_selector(selector):
    def run(page):
        page.locator(str(selector or "")).first.click(timeout=7000)
        page.wait_for_timeout(500)
        return f"Клик по selector выполнен: {selector}", ""

    return _run_action("click_selector", run, selector)


def fill_by_label(label, value):
    safety_text = f"{label} {value}"

    def run(page):
        target = str(label or "").strip()
        value_text = str(value or "")
        locators = [
            lambda: page.get_by_label(target, exact=False),
            lambda: page.get_by_placeholder(target, exact=False),
            lambda: page.locator(f'[aria-label*="{target}" i]'),
            lambda: page.locator(f'input[name*="{target}" i], textarea[name*="{target}" i]'),
            lambda: page.locator(f'input[id*="{target}" i], textarea[id*="{target}" i]'),
        ]

        last_error = ""

        for locator_factory in locators:
            try:
                locator = locator_factory().first
                locator.fill(value_text, timeout=5000)
                return f"Поле заполнено: {label}", ""
            except Exception as e:
                last_error = str(e)

        raise RuntimeError(f"Поле не найдено: {label}. Последняя ошибка: {last_error}")

    return _run_action("fill_label", run, safety_text)


def fill_selector(selector, value):
    safety_text = f"{selector} {value}"

    def run(page):
        page.locator(str(selector or "")).first.fill(str(value or ""), timeout=7000)
        return f"Поле selector заполнено: {selector}", ""

    return _run_action("fill_selector", run, safety_text)


def press_key(key):
    def run(page):
        key_text = str(key or "Enter").strip() or "Enter"
        page.keyboard.press(key_text)
        page.wait_for_timeout(300)
        return f"Клавиша нажата: {key_text}", ""

    return _run_action("press_key", run, key)


def wait_page(ms=1000):
    try:
        ms = int(ms)
    except Exception:
        ms = 1000

    ms = max(0, min(ms, 30000))

    def run(page):
        page.wait_for_timeout(ms)
        return f"Ожидание выполнено: {ms} ms", ""

    return _run_action("wait", run)


def extract_links(limit=20):
    limit = max(1, min(int(limit or 20), 100))

    def run(page):
        page, stop = _action_page_or_stop(page, "links")

        if stop:
            set_value("last_browser_links", [])
            return stop, ""

        links = page.locator("a").evaluate_all(
            """
            (els, limit) => els.slice(0, limit).map(a => ({
                text: (a.innerText || a.textContent || '').trim().slice(0, 160),
                href: a.href || ''
            }))
            """,
            limit,
        )
        set_value("last_browser_links", links)

        if not links:
            return f"Ссылки не найдены на текущей странице.\nURL: {_safe_page_url(page) or 'нет'}", ""

        return json.dumps(links, ensure_ascii=False, indent=2), ""

    return _run_action("extract_links", run)


def extract_inputs(limit=30):
    limit = max(1, min(int(limit or 30), 100))

    def run(page):
        page, stop = _action_page_or_stop(page, "inputs")

        if stop:
            set_value("last_browser_inputs", [])
            return stop, ""

        inputs = page.locator("input, textarea, select, button").evaluate_all(
            """
            (els, limit) => els.slice(0, limit).map(el => ({
                tag: el.tagName.toLowerCase(),
                type: el.getAttribute('type') || '',
                placeholder: el.getAttribute('placeholder') || '',
                aria_label: el.getAttribute('aria-label') || '',
                name: el.getAttribute('name') || '',
                id: el.getAttribute('id') || '',
                text: (el.innerText || el.value || '').trim().slice(0, 120)
            }))
            """,
            limit,
        )
        set_value("last_browser_inputs", inputs)

        if not inputs:
            return f"Поля ввода не найдены на текущей странице.\nURL: {_safe_page_url(page) or 'нет'}", ""

        return json.dumps(inputs, ensure_ascii=False, indent=2), ""

    return _run_action("extract_inputs", run)


def summarize_page(limit=4000):
    def run(page):
        page, stop = _action_page_or_stop(page, "summarize")

        if stop:
            return stop, ""

        title = page.title()
        url = page.url
        headings = page.locator("h1, h2").evaluate_all(
            "els => els.slice(0, 12).map(el => (el.innerText || '').trim()).filter(Boolean)"
        )
        links = page.locator("a").evaluate_all(
            "els => els.slice(0, 10).map(a => ({text:(a.innerText||'').trim().slice(0,120), href:a.href||''}))"
        )
        text = page.locator("body").inner_text(timeout=10000)

        if not title.strip() and not text.strip():
            return _blank_action_message("summarize"), ""

        result = (
            f"URL: {url}\n"
            f"TITLE: {title}\n\n"
            f"HEADINGS:\n" + "\n".join(f"- {item}" for item in headings) + "\n\n"
            f"LINKS:\n" + "\n".join(f"- {item.get('text')}: {item.get('href')}" for item in links) + "\n\n"
            f"TEXT:\n{text[:limit]}"
        )
        return result, ""

    return _run_action("summarize", run)


def open_new_tab(url):
    def run(page):
        if not str(url or "").startswith(("http://", "https://", "file://")):
            raise ValueError("Новая вкладка требует полный URL http/https/file.")

        new_page = page.context.new_page()
        new_page.goto(url, wait_until="domcontentloaded", timeout=30000)
        set_active_page_for_actions(len(page.context.pages) - 1)
        return f"Открыта новая вкладка:\n{url}", ""

    return _run_action("open_new_tab", run, url)


def list_tabs():
    try:
        pages = get_browser_pages_for_actions()
        tabs = []

        for index, page in enumerate(pages):
            try:
                tabs.append({
                    "index": index,
                    "title": page.title(),
                    "url": page.url,
                })
            except Exception:
                tabs.append({"index": index, "title": "ошибка", "url": ""})

        set_value("last_browser_tabs", tabs)
        return json.dumps(tabs, ensure_ascii=False, indent=2)
    except Exception as e:
        _remember("list_tabs", "", e)
        return f"Не удалось получить вкладки: {e}"


def switch_tab(index):
    try:
        index = int(index)
        page = set_active_page_for_actions(index)
        result = f"Переключено на вкладку {index}:\n{page.url}"
        _remember("switch_tab", result)
        return result
    except Exception as e:
        _remember("switch_tab", "", e)
        return f"Не удалось переключить вкладку: {e}"


def close_current_tab():
    try:
        pages = get_browser_pages_for_actions()

        if len(pages) <= 1:
            return "Закрытие отменено: открыта только одна вкладка."

        current = get_active_page_for_actions()
        index = pages.index(current) if current in pages else len(pages) - 1
        current.close()
        next_index = max(0, min(index - 1, len(pages) - 2))
        page = set_active_page_for_actions(next_index)
        result = f"Текущая вкладка закрыта. Активна вкладка {next_index}:\n{page.url}"
        _remember("close_tab", result)
        return result
    except Exception as e:
        _remember("close_tab", "", e)
        return f"Не удалось закрыть вкладку: {e}"
````

### ПУТЬ: modules/browser_autopilot.py (634 строк, 19138 байт)

````python
import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import get_value, set_value
from modules import browser_actions
from modules.browser import click_first_link, get_active_page_for_actions, search


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "browser_autopilot"

SAFETY_MARKERS = [
    "оплатить",
    "купить",
    "оформить заказ",
    "добавить в корзину",
    "корзину",
    "ставка",
    "поставить",
    "банк",
    "банков",
    "кредит",
    "пароль",
    "логин",
    "войти",
    "зарегистрироваться",
    "2fa",
    "sms",
    "удалить аккаунт",
    "отправь деньги",
    "checkout",
    "pay",
    "buy",
    "order",
    "cart",
    "bet",
    "casino",
    "bank",
    "password",
    "login",
    "sign in",
    "sign up",
    "delete account",
    "delete my account",
    "delete your account",
    "remove my account",
    "close my account",
    "deactivate account",
    "account deletion",
    "удалить мой аккаунт",
    "удалить учетную запись",
    "удалить учётную запись",
    "удалить профиль",
]


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_reports_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _report_path():
    _ensure_reports_dir()
    base = REPORTS_DIR / f"browser_autopilot_{_stamp()}.md"

    if not base.exists():
        return base

    for index in range(1, 100):
        candidate = REPORTS_DIR / f"browser_autopilot_{_stamp()}_{index:02d}.md"

        if not candidate.exists():
            return candidate

    return base


def _short(text, limit=3000):
    value = str(text or "")

    if len(value) <= limit:
        return value

    return value[:limit] + "\n...[обрезано]"


def _contains_any(text, markers):
    lower = str(text or "").lower()
    return any(marker in lower for marker in markers)


def is_browser_task_safe(task: str):
    lower = str(task or "").lower()

    for marker in SAFETY_MARKERS:
        if marker in lower:
            return False, f"Задача заблокирована safety guard: найден опасный маркер '{marker}'."

    return True, ""


def _clean_query(task: str):
    text = str(task or "").strip()
    lower = text.lower()

    prefixes = [
        "найди информацию про",
        "найди информацию о",
        "найди",
        "поиск",
        "исследуй",
        "изучи",
        "сравни",
        "на текущем сайте найди",
        "введи",
        "найди поле поиска и введи",
    ]

    for prefix in prefixes:
        if lower.startswith(prefix):
            text = text[len(prefix):].strip(" :,-")
            break

    remove_parts = [
        "и сделай отчет",
        "и сделай отчёт",
        "и собери ссылки",
        "и собери ссылку",
        "и сравни первые результаты",
        "сделай отчет",
        "сделай отчёт",
        "собери ссылки",
        "собери результаты",
    ]

    lower = text.lower()

    for part in remove_parts:
        index = lower.find(part)

        if index != -1:
            text = text[:index].strip(" :,-")
            lower = text.lower()

    return text.strip() or str(task or "").strip()


def _click_target(task: str):
    text = str(task or "").strip()
    lower = text.lower()

    markers = [
        "нажми ссылку",
        "кликни по",
        "кликни",
        "нажми",
        "открой",
    ]

    for marker in markers:
        if lower.startswith(marker):
            return text[len(marker):].strip(" :,-")

    return text


def _step(action, args=None):
    return {"action": action, "args": args or {}}


def _base_plan(task, mode, max_steps, steps, blocked_reason=""):
    return {
        "task": str(task or "").strip(),
        "mode": mode,
        "max_steps": int(max_steps),
        "steps": steps[: int(max_steps)],
        "blocked_reason": blocked_reason,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_browser_autopilot_plan(task: str, mode="dry_run", max_steps=8):
    task = str(task or "").strip()
    mode = "execute" if str(mode or "").lower() == "execute" else "dry_run"

    try:
        max_steps = max(1, min(int(max_steps or 8), 20))
    except Exception:
        max_steps = 8

    safe, reason = is_browser_task_safe(task)

    if not safe:
        return _base_plan(task, mode, max_steps, [], blocked_reason=reason)

    lower = task.lower()
    query = _clean_query(task)

    if "открой первый результат" in lower or "open first" in lower:
        steps = [
            _step("observe"),
            _step("open_first"),
            _step("summarize"),
            _step("screenshot"),
            _step("save_report"),
        ]
        return _base_plan(task, mode, max_steps, steps)

    if (
        "на текущем сайте" in lower
        or "поиск сайта" in lower
        or "поле поиска" in lower
        or lower.startswith("введи ")
    ):
        steps = [
            _step("observe"),
            _step("inputs"),
            _step("fill_search_field", {"query": query}),
            _step("press_enter"),
            _step("wait", {"ms": 1500}),
            _step("summarize"),
            _step("screenshot"),
            _step("save_report"),
        ]
        return _base_plan(task, mode, max_steps, steps)

    if _contains_any(lower, ["нажми", "кликни", "click "]):
        steps = [
            _step("observe"),
            _step("click_text", {"text": _click_target(task)}),
            _step("wait", {"ms": 1000}),
            _step("summarize"),
            _step("screenshot"),
            _step("save_report"),
        ]
        return _base_plan(task, mode, max_steps, steps)

    if _contains_any(lower, ["собери", "извлеки", "таблиц", "цены", "цену", "карточк", "заголовки"]):
        steps = [
            _step("observe"),
            _step("extract_links"),
            _step("extract_cards_or_text_blocks"),
            _step("screenshot"),
            _step("save_report"),
        ]
        return _base_plan(task, mode, max_steps, steps)

    if _contains_any(lower, ["текущ", "страниц"]) and "найди" not in lower:
        steps = [
            _step("observe"),
            _step("summarize"),
            _step("extract_links"),
            _step("extract_inputs"),
            _step("screenshot"),
            _step("save_report"),
        ]
        return _base_plan(task, mode, max_steps, steps)

    if _contains_any(lower, ["найди", "поиск", "изучи", "исследуй", "сравни"]):
        steps = [
            _step("search", {"query": query}),
            _step("open_first"),
            _step("summarize"),
            _step("extract_links"),
            _step("screenshot"),
            _step("save_report"),
        ]
        return _base_plan(task, mode, max_steps, steps)

    steps = [
        _step("observe"),
        _step("summarize"),
        _step("extract_links"),
        _step("extract_inputs"),
        _step("screenshot"),
        _step("save_report"),
    ]
    return _base_plan(task, mode, max_steps, steps)


def _safe_eval(page, script, default):
    try:
        return page.locator("body").evaluate(script)
    except Exception:
        return default


def observe_browser_page():
    try:
        page = get_active_page_for_actions()
        current_url = str(page.url or "")
        title = str(page.title() or "")

        headings = page.locator("h1, h2").evaluate_all(
            "els => els.slice(0, 10).map(el => (el.innerText || '').trim()).filter(Boolean)"
        )
        links = page.locator("a").evaluate_all(
            "els => els.slice(0, 10).map(a => ({text:(a.innerText||a.textContent||'').trim().slice(0,100), href:a.href||''}))"
        )
        inputs = page.locator("input, textarea, select, button").evaluate_all(
            "els => els.slice(0, 10).map(el => ({tag:el.tagName.toLowerCase(), type:el.getAttribute('type')||'', placeholder:el.getAttribute('placeholder')||'', name:el.getAttribute('name')||'', text:(el.innerText||el.value||'').trim().slice(0,80)}))"
        )
        body_text = _safe_eval(page, "body => (body.innerText || '').trim().slice(0, 1200)", "")

        observation = {
            "current_url": current_url,
            "title": title,
            "headings": headings,
            "visible_links": links,
            "inputs": inputs,
            "short_text": body_text,
        }

        return json.dumps(observation, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Browser observe failed: {e}"


def _extract_text_blocks():
    try:
        page = get_active_page_for_actions()
        blocks = page.locator("article, section, main, li, .card, [class*='card'], [class*='product']").evaluate_all(
            """
            els => els.slice(0, 20).map(el => (el.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 300)).filter(Boolean)
            """
        )

        if not blocks:
            text = page.locator("body").inner_text(timeout=5000)
            blocks = [line.strip() for line in text.splitlines() if len(line.strip()) > 20][:20]

        return json.dumps(blocks, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Не удалось извлечь текстовые блоки: {e}"


def _fill_search_field(query):
    query = str(query or "").strip()

    if not query:
        return "STOP: нечего вводить в поле поиска."

    attempts = []

    for label in ["Search", "Поиск", "search"]:
        result = browser_actions.fill_by_label(label, query)
        attempts.append(result)
        text = str(result)

        if "Поле заполнено" in text and "не найдено" not in text.lower():
            return text

    return attempts[-1] if attempts else "STOP: поле поиска не найдено."


def _step_failed(result):
    lower = str(result or "").lower()
    return any(marker in lower for marker in ["stop:", "failed", "ошибка", "не удалось", "не найдено"])


def _execute_step(step):
    action = str(step.get("action", "") or "").strip()
    args = step.get("args", {}) or {}

    if action == "observe":
        return observe_browser_page()

    if action == "search":
        return search(args.get("query", ""))

    if action == "open_first":
        return click_first_link()

    if action == "summarize":
        return browser_actions.summarize_page()

    if action in ["links", "extract_links"]:
        return browser_actions.extract_links()

    if action in ["inputs", "extract_inputs"]:
        return browser_actions.extract_inputs()

    if action == "click_text":
        return browser_actions.click_by_text(args.get("text", ""))

    if action == "fill_search_field":
        return _fill_search_field(args.get("query", ""))

    if action == "press_enter":
        return browser_actions.press_key("Enter")

    if action == "wait":
        return browser_actions.wait_page(args.get("ms", 1000))

    if action == "screenshot":
        return browser_actions.screenshot_page()

    if action == "extract_cards_or_text_blocks":
        return _extract_text_blocks()

    if action == "save_report":
        return "Report will be saved after autopilot completes."

    return f"Unknown browser autopilot step: {action}"


def _extract_screenshot_path(result):
    for line in str(result or "").splitlines():
        clean = line.strip()

        if clean.lower().endswith(".png") and ":" in clean:
            return clean

        if clean.lower().endswith(".png"):
            return clean

    return ""


def _save_report(plan, step_results, observations, screenshots, errors, final_result):
    path = _report_path()

    lines = [
        "# Browser Autopilot Report",
        "",
        "## Summary",
        "",
        f"- status: {final_result.get('status')}",
        f"- created_at: {plan.get('created_at')}",
        f"- steps_planned: {len(plan.get('steps', []))}",
        f"- steps_run: {len(step_results)}",
        "",
        "## Task",
        "",
        str(plan.get("task") or ""),
        "",
        "## Mode",
        "",
        str(plan.get("mode") or ""),
        "",
        "## Safety",
        "",
        f"- blocked_reason: {plan.get('blocked_reason') or 'нет'}",
        "",
        "## Plan",
        "",
        "```json",
        json.dumps(plan, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Step results",
        "",
    ]

    for item in step_results:
        lines.extend([
            f"### Step {item.get('index')}: {item.get('action')}",
            "",
            "```text",
            _short(item.get("result"), 4000),
            "```",
            "",
        ])

    lines.extend(["## Page observations", ""])

    for item in observations:
        lines.extend([
            f"### Observation after step {item.get('step')}",
            "",
            "```text",
            _short(item.get("observation"), 2500),
            "```",
            "",
        ])

    lines.extend(["## Screenshots", ""])

    if screenshots:
        lines.extend(f"- {path}" for path in screenshots)
    else:
        lines.append("- нет")

    lines.extend(["", "## Errors / recovery", ""])

    if errors:
        lines.extend(f"- {item}" for item in errors)
    else:
        lines.append("- нет")

    lines.extend([
        "",
        "## Final result",
        "",
        json.dumps(final_result, ensure_ascii=False, indent=2),
        "",
        "## Next suggested actions",
        "",
        "- Проверь report и screenshot.",
        "- Для опасных действий выполни ручное подтверждение вне Autopilot.",
        "- Если шаг не сработал, попробуй browser observe или уточни задачу.",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _remember_report(path, status, plan):
    set_value("last_browser_autopilot_report", str(path))
    set_value("last_browser_autopilot_status", status)
    set_value("last_browser_autopilot_task", plan.get("task", ""))
    set_value("last_browser_autopilot_mode", plan.get("mode", ""))


def run_browser_autopilot(task: str, mode="execute", max_steps=8):
    mode = "dry_run" if str(mode or "").lower() == "dry_run" else "execute"
    plan = build_browser_autopilot_plan(task, mode=mode, max_steps=max_steps)
    step_results = []
    observations = []
    screenshots = []
    errors = []

    if plan.get("blocked_reason"):
        final = {"status": "blocked", "reason": plan.get("blocked_reason")}
        report_path = _save_report(plan, step_results, observations, screenshots, errors, final)
        _remember_report(report_path, "blocked", plan)
        return f"STOP: Browser Autopilot blocked.\nПричина: {plan.get('blocked_reason')}\nReport: {report_path}"

    if mode == "dry_run":
        final = {"status": "dry_run", "message": "План построен, браузерные действия не выполнялись."}
        report_path = _save_report(plan, step_results, observations, screenshots, errors, final)
        _remember_report(report_path, "dry_run", plan)
        return (
            "Browser Autopilot dry-run завершен.\n"
            f"Steps: {len(plan.get('steps', []))}\n"
            f"Report: {report_path}"
        )

    for index, step in enumerate(plan.get("steps", [])[: int(plan.get("max_steps", 8))], start=1):
        action = step.get("action", "unknown")

        try:
            result = _execute_step(step)

            if _step_failed(result) and action not in ["save_report"]:
                errors.append(f"Step {index} failed, retry after wait: {action}")
                browser_actions.wait_page(1000)
                retry_result = _execute_step(step)
                result = str(result) + "\n\n--- RETRY ---\n" + str(retry_result)

                if _step_failed(retry_result):
                    fallback = browser_actions.screenshot_page()
                    errors.append(f"Step {index} still failed, screenshot fallback executed.")
                    result = str(result) + "\n\n--- FALLBACK SCREENSHOT ---\n" + str(fallback)

            screenshot_path = _extract_screenshot_path(result)

            if screenshot_path:
                screenshots.append(screenshot_path)

            step_results.append({
                "index": index,
                "action": action,
                "result": str(result),
            })

            if action not in ["observe", "save_report"]:
                observations.append({
                    "step": index,
                    "observation": observe_browser_page(),
                })

        except Exception as e:
            errors.append(f"Step {index} exception in {action}: {e}")
            step_results.append({
                "index": index,
                "action": action,
                "result": f"ERROR: {e}",
            })
            break

    status = "failed" if errors else "success"
    final = {"status": status, "errors": errors[-5:]}
    report_path = _save_report(plan, step_results, observations, screenshots, errors, final)
    _remember_report(report_path, status, plan)

    return (
        f"Browser Autopilot {status}.\n"
        f"Task: {plan.get('task')}\n"
        f"Steps run: {len(step_results)}/{len(plan.get('steps', []))}\n"
        f"Report: {report_path}"
    )


def format_browser_autopilot_plan(plan):
    lines = [
        "Browser Autopilot Plan:",
        f"- task: {plan.get('task')}",
        f"- mode: {plan.get('mode')}",
        f"- max_steps: {plan.get('max_steps')}",
        f"- blocked_reason: {plan.get('blocked_reason') or 'нет'}",
        "",
        "Steps:",
    ]

    for index, step in enumerate(plan.get("steps", []), start=1):
        lines.append(f"{index}. {step.get('action')} {step.get('args') or {}}")

    return "\n".join(lines)


def latest_browser_autopilot_report():
    path = str(get_value("last_browser_autopilot_report", "") or "").strip()

    if path:
        p = Path(path)

        if p.exists() and p.is_file():
            return p

    if not REPORTS_DIR.exists():
        return None

    reports = [p for p in REPORTS_DIR.glob("browser_autopilot_*.md") if p.is_file()]

    if not reports:
        return None

    return max(reports, key=lambda p: p.stat().st_mtime)
````

### ПУТЬ: modules/browser_direct.py (209 строк, 8810 байт)

````python
def _strip_browser_prefix(user):
    text = str(user or "").strip()
    lower = text.lower()

    for prefix in ["browser", "браузер"]:
        if lower.startswith(prefix):
            return text[len(prefix):].strip(" :,-")

    return text


def _extract_after(text, markers):
    lower = text.lower()

    for marker in markers:
        index = lower.find(marker)

        if index != -1:
            return text[index + len(marker):].strip(" :,-")

    return ""


def browser_action_direct_plan(user):
    source = str(user or "").strip()
    lower_source = source.lower()
    platform_site_request = (
        any(marker in lower_source for marker in ["используй платформу", "tilda", "тильда", "wix", "webflow", "framer", "carrd"])
        and any(marker in lower_source for marker in ["сайт", "site"])
    )

    if not lower_source.startswith(("browser", "браузер")) and not platform_site_request:
        return None

    text = _strip_browser_prefix(source) if lower_source.startswith(("browser", "браузер")) else source
    lower = text.lower()

    if lower in ["observe", "наблюдай", "осмотри страницу"]:
        return {"tool": "browser", "action": "observe"}

    if lower in ["autopilot last report", "autopilot report", "last autopilot report"]:
        return {"tool": "browser", "action": "autopilot_last_report"}

    if lower in ["super last report", "super report", "last super report"]:
        return {"tool": "browser", "action": "super_last_report"}

    if lower.startswith(("super plan ", "operator plan ")):
        marker = "super plan " if lower.startswith("super plan ") else "operator plan "
        task = text[len(marker):].strip()
        return {"tool": "browser", "action": "super_plan", "task": task, "max_results": 3}

    if lower.startswith(("super run ", "do ", "operator run ")):
        for marker in ["super run ", "operator run ", "do "]:
            if lower.startswith(marker):
                task = text[len(marker):].strip()
                return {"tool": "browser", "action": "super_run", "task": task, "max_results": 3}

    if lower.startswith(("research ", "deep research ", "исследуй ", "изучи ")):
        for marker in ["deep research ", "research ", "исследуй ", "изучи "]:
            if lower.startswith(marker):
                task = text[len(marker):].strip()
                return {"tool": "browser", "action": "research", "task": task, "max_results": 3}

    if lower.startswith(("compare ", "сравни ")):
        marker = "compare " if lower.startswith("compare ") else "сравни "
        task = text[len(marker):].strip()
        return {"tool": "browser", "action": "compare_research", "task": task, "max_results": 3}

    if lower in ["page audit", "audit page", "аудит страницы", "проверь текущую страницу"]:
        return {"tool": "browser", "action": "page_audit", "task": "current page"}

    if lower in ["form map", "forms map", "form audit", "карта форм", "поля формы"]:
        return {"tool": "browser", "action": "form_map", "task": "current page"}

    if lower.startswith(("build site ", "site workflow ", "напиши сайт ", "создай сайт ", "сделай сайт ")):
        for marker in ["site workflow ", "build site ", "напиши сайт ", "создай сайт ", "сделай сайт "]:
            if lower.startswith(marker):
                task = text[len(marker):].strip()
                return {"tool": "browser", "action": "platform_site_workflow", "task": task}

    if platform_site_request:
        return {"tool": "browser", "action": "platform_site_workflow", "task": text}

    if lower.startswith("autopilot dry "):
        task = text[len("autopilot dry "):].strip()
        return {"tool": "browser", "action": "autopilot_dry", "task": task, "max_steps": 8}

    if lower.startswith("autopilot run "):
        task = text[len("autopilot run "):].strip()
        return {"tool": "browser", "action": "autopilot_run", "task": task, "max_steps": 8}

    if lower.startswith("plan "):
        task = text[len("plan "):].strip()
        return {"tool": "browser", "action": "plan", "task": task, "max_steps": 8}

    if lower.startswith("task "):
        task = text[len("task "):].strip()
        return {"tool": "browser", "action": "browser_task", "task": task, "max_steps": 8}

    if lower == "workflow python search":
        return {
            "tool": "browser",
            "action": "browser_workflow",
            "steps": [
                {"action": "search", "args": {"query": "Python official website"}},
                {"action": "open_first"},
                {"action": "summarize"},
                {"action": "extract_links"},
                {"action": "extract_inputs"},
                {"action": "screenshot"}
            ],
            "title": "python search workflow"
        }

    if lower == "workflow current page":
        return {
            "tool": "browser",
            "action": "browser_workflow",
            "steps": [
                {"action": "summarize"},
                {"action": "extract_links"},
                {"action": "extract_inputs"},
                {"action": "screenshot"}
            ],
            "title": "current page workflow"
        }

    if lower in ["screenshot", "скрин", "скриншот"]:
        return {"tool": "browser", "action": "screenshot"}

    if lower in ["links", "ссылки"]:
        return {"tool": "browser", "action": "extract_links"}

    if lower in ["inputs", "поля", "формы"]:
        return {"tool": "browser", "action": "extract_inputs"}

    if lower in ["summarize", "summary", "резюме", "кратко", "summary page"]:
        return {"tool": "browser", "action": "summarize"}

    if lower in ["tabs", "вкладки"]:
        return {"tool": "browser", "action": "list_tabs"}

    if lower in ["close tab", "закрой вкладку", "close current tab"]:
        return {"tool": "browser", "action": "close_tab"}

    if lower in ["action status", "action статус", "actions status"]:
        return {"tool": "browser", "action": "action_status"}

    if lower.startswith(("find text", "найди текст")):
        value = _extract_after(text, ["find text", "найди текст"])
        return {"tool": "browser", "action": "find_text", "text": value}

    if lower.startswith(("click selector", "selector click")):
        value = _extract_after(text, ["click selector", "selector click"])
        return {"tool": "browser", "action": "click_selector", "selector": value}

    if lower.startswith(("click ", "клик ")):
        value = _extract_after(text, ["click", "клик"])
        return {"tool": "browser", "action": "click_text", "text": value}

    if lower.startswith(("fill selector", "selector fill")):
        value = _extract_after(text, ["fill selector", "selector fill"])

        if "=" in value:
            selector, fill_value = value.split("=", 1)
        else:
            selector, fill_value = value, ""

        return {
            "tool": "browser",
            "action": "fill_selector",
            "selector": selector.strip(),
            "value": fill_value.strip(),
        }

    if lower.startswith(("fill ", "введи ")):
        value = _extract_after(text, ["fill", "введи"])

        if "=" in value:
            label, fill_value = value.split("=", 1)
        else:
            label, fill_value = value, ""

        return {
            "tool": "browser",
            "action": "fill_label",
            "label": label.strip(),
            "value": fill_value.strip(),
        }

    if lower.startswith(("press ", "нажми ")):
        key = _extract_after(text, ["press", "нажми"]) or "Enter"
        return {"tool": "browser", "action": "press_key", "key": key.strip()}

    if lower.startswith(("wait ", "жди ", "подожди ")):
        raw = _extract_after(text, ["wait", "жди", "подожди"])
        digits = "".join(ch for ch in raw if ch.isdigit())
        return {"tool": "browser", "action": "wait", "ms": int(digits or "1000")}

    if lower.startswith(("new tab", "новая вкладка")):
        url = _extract_after(text, ["new tab", "новая вкладка"])
        return {"tool": "browser", "action": "open_new_tab", "url": url}

    if lower.startswith(("switch tab", "переключи вкладку")):
        raw = _extract_after(text, ["switch tab", "переключи вкладку"])
        digits = "".join(ch for ch in raw if ch.isdigit())
        return {"tool": "browser", "action": "switch_tab", "index": int(digits or "0")}

    return None
````

### ПУТЬ: modules/browser_harness_ru.py (756 строк, 29572 байт)

````python
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
import json
import re
import urllib.parse
import uuid

from modules.project_paths import computer_use_dir, computer_use_latest_ui_map_path, reports_dir


BROWSER_HARNESS_VERSION = "v6.50c"
BROWSER_HARNESS_NAME = "LocalComet Browser Harness RU"

BROWSER_HARNESS_DIR = computer_use_dir() / "browser_harness"
BROWSER_HARNESS_REPORT_DIR = reports_dir() / "browser_harness"

BLOCKED_BROWSER_PATTERNS = [
    ("destructive_delete", r"удали|удалить|сотри|стереть|\b(delete|remove|wipe|format|erase|rm\s+-rf|rmdir|del\s+|shutil\.rmtree|os\.remove)\b"),
    ("shell_terminal_admin", r"терминал|командн|админ|\b(shell|cmd|cmd\.exe|powershell|terminal|bash|zsh|sudo|admin|administrator)\b"),
    ("secrets_browser_profile", r"парол|токен|секрет|куки|cookies|профил[ья] браузера|browser\s*profile|\b(password|passwd|token|api\s*key|api-key|secret|private\s*key|ssh\s*key|cookie)\b"),
    ("banking_payment_gambling", r"банк|плат[её]ж|карта|казино|ставк|\b(bank|payment|credit\s*card|paypal|wallet|gambling|casino|betting)\b"),
    ("deploy_backend_install", r"\b(deploy|backend|docker|kubectl|helm|npm|pip\s+install)\b|деплой|бекенд|бэкенд"),
]

FILE_CHANGE_PATTERNS = [
    ("download", r"скачай|загрузи\s+с\s+сайта|download\b|save\s+as|сохранить\s+как"),
    ("upload_attach", r"загрузи\s+файл|прикрепи\s+файл|upload\b|attach\b|drop\s+file"),
    ("export_print", r"экспорт|export\b|print\s+to\s+pdf|печать\s+в\s+pdf"),
    ("browser_file_edit", r"создай\s+файл|измени\s+файл|редактируй\s+файл|write\s+file|edit\s+file|modify\s+file"),
]

EXECUTABLE_DOWNLOAD_PATTERN = r"\.(exe|msi|bat|cmd|ps1|scr|vbs|jar)(\b|[?&#])|запусти\s+скачан|run\s+download|execute\s+download"

URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", flags=re.IGNORECASE)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs() -> None:
    BROWSER_HARNESS_DIR.mkdir(parents=True, exist_ok=True)
    BROWSER_HARNESS_REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower().replace("ё", "е"))


def _matches(patterns: List[tuple[str, str]], text: str) -> List[Dict[str, str]]:
    value = str(text or "")
    problems: List[Dict[str, str]] = []
    for problem_type, pattern in patterns:
        if re.search(pattern, value, flags=re.IGNORECASE):
            problems.append({"type": problem_type, "reason": f"blocked marker: {problem_type}"})
    return problems


def _file_change_reasons(text: str) -> List[Dict[str, str]]:
    value = str(text or "")
    reasons: List[Dict[str, str]] = []
    for reason_type, pattern in FILE_CHANGE_PATTERNS:
        if re.search(pattern, value, flags=re.IGNORECASE):
            reasons.append({"type": reason_type, "reason": f"confirmation marker: {reason_type}"})
    return reasons


def redact_browser_text(text: str) -> str:
    value = str(text or "")
    try:
        from modules.computer_use_safety_ru import redact_text as core_redact
        value = core_redact(value)
    except Exception:
        pass
    replacements = [
        (r"(?i)(api[_\-\s]*key\s*[:=]\s*)[^\s&]+", r"\1[REDACTED_SECRET]"),
        (r"(?i)(token\s*[:=]\s*)[^\s&]+", r"\1[REDACTED_SECRET]"),
        (r"(?i)(password\s*[:=]\s*)[^\s&]+", r"\1[REDACTED_SECRET]"),
        (r"(?i)(cookie\s*[:=]\s*)[^\s&]+", r"\1[REDACTED_SECRET]"),
    ]
    for pattern, repl in replacements:
        value = re.sub(pattern, repl, value)
    return value


def _extract_url(goal: str) -> str:
    match = URL_PATTERN.search(str(goal or ""))
    if not match:
        return ""
    url = match.group(0).rstrip(".,;)")
    return url


def validate_browser_url(url: str) -> Dict[str, Any]:
    raw = str(url or "").strip()
    if not raw:
        return {"ok": False, "reason": "URL is empty.", "blocked": False}
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"}:
        return {"ok": False, "reason": "Only http and https URLs are allowed.", "blocked": True}
    if not parsed.netloc:
        return {"ok": False, "reason": "URL has no host.", "blocked": True}
    if parsed.username or parsed.password:
        return {"ok": False, "reason": "URL userinfo is sensitive and blocked.", "blocked": True}
    if re.search(EXECUTABLE_DOWNLOAD_PATTERN, raw, flags=re.IGNORECASE):
        return {"ok": False, "reason": "Executable download or execution marker is blocked.", "blocked": True}
    return {
        "ok": True,
        "scheme": parsed.scheme.lower(),
        "host": parsed.netloc.lower(),
        "redacted_url": redact_browser_text(raw),
        "blocked": False,
    }


def safety_check_browser_goal(goal: str) -> Dict[str, Any]:
    raw = str(goal or "").strip()
    redacted = redact_browser_text(raw)
    if not raw:
        return {
            "ok": False,
            "blocked": False,
            "requires_confirmation": False,
            "allowed_to_execute": False,
            "risk": "invalid",
            "reason": "Browser goal is empty.",
            "problem_types": [],
            "file_change_reasons": [],
        }

    core_result: Dict[str, Any] = {"ok": True, "blocked": False, "problem_types": []}
    try:
        from modules.computer_use_safety_ru import safety_check_goal as core_safety_check
        core_result = core_safety_check(raw)
    except Exception as exc:
        core_result = {
            "ok": True,
            "blocked": False,
            "problem_types": [],
            "reason": f"core safety unavailable: {exc}",
        }

    blocked = _matches(BLOCKED_BROWSER_PATTERNS, raw)
    if not core_result.get("ok") or core_result.get("blocked"):
        for problem_type in core_result.get("problem_types", []):
            blocked.append({"type": str(problem_type), "reason": f"core safety marker: {problem_type}"})

    url = _extract_url(raw)
    url_check = validate_browser_url(url) if url else {"ok": True, "blocked": False}
    if url and not url_check.get("ok") and url_check.get("blocked"):
        blocked.append({"type": "unsafe_url", "reason": str(url_check.get("reason", "unsafe url"))})

    if re.search(EXECUTABLE_DOWNLOAD_PATTERN, raw, flags=re.IGNORECASE):
        blocked.append({"type": "executable_download", "reason": "Executable download or execution is blocked."})

    file_change_reasons = _file_change_reasons(raw)
    if blocked:
        return {
            "ok": False,
            "mode": "browser_harness_safety",
            "version": BROWSER_HARNESS_VERSION,
            "blocked": True,
            "requires_confirmation": True,
            "allowed_to_execute": False,
            "risk": "blocked",
            "reason": "; ".join(item["reason"] for item in blocked),
            "problem_types": [item["type"] for item in blocked],
            "file_change_reasons": file_change_reasons,
            "redacted_goal": redacted,
        }

    requires_confirmation = bool(file_change_reasons)
    return {
        "ok": True,
        "mode": "browser_harness_safety",
        "version": BROWSER_HARNESS_VERSION,
        "blocked": False,
        "requires_confirmation": requires_confirmation,
        "allowed_to_execute": not requires_confirmation,
        "risk": "medium" if requires_confirmation else "low",
        "reason": "Browser goal is safe for one-step GUI planning." if not requires_confirmation else "Browser goal may change files and requires explicit confirmation.",
        "problem_types": [],
        "file_change_reasons": file_change_reasons,
        "redacted_goal": redacted,
        "url_check": url_check,
    }


def classify_browser_goal(goal: str) -> Dict[str, Any]:
    raw = str(goal or "").strip()
    lowered = _normalize(raw)
    url = _extract_url(raw)
    if url:
        url_check = validate_browser_url(url)
        return {
            "ok": bool(url_check.get("ok")),
            "mode": "browser_harness_task",
            "version": BROWSER_HARNESS_VERSION,
            "task_type": "navigate_url",
            "payload": url_check.get("redacted_url", redact_browser_text(url)),
            "target_description": "Адресная строка",
            "reason": url_check.get("reason", "navigate to URL"),
            "url_check": url_check,
        }

    search_prefixes = [
        "найди ",
        "поиск ",
        "поищи ",
        "search ",
        "find ",
        "google ",
        "гугл ",
        "открой поиск ",
    ]
    for prefix in search_prefixes:
        if lowered.startswith(prefix.strip()):
            payload = raw[len(prefix):].strip()
            break
    else:
        payload = raw

    if lowered.startswith(("нажми ", "кликни ", "click ")):
        for prefix in ("нажми ", "кликни ", "click "):
            if lowered.startswith(prefix.strip()):
                description = raw[len(prefix):].strip()
                return {
                    "ok": True,
                    "mode": "browser_harness_task",
                    "version": BROWSER_HARNESS_VERSION,
                    "task_type": "click_text",
                    "payload": "",
                    "target_description": description or "browser element",
                    "reason": "click browser UI element by visible text",
                }

    return {
        "ok": True,
        "mode": "browser_harness_task",
        "version": BROWSER_HARNESS_VERSION,
        "task_type": "search_or_address_text",
        "payload": redact_browser_text(payload),
        "target_description": "Поиск",
        "reason": "type safe browser query into grounded search or address field",
    }


def read_browser_ui_map() -> Dict[str, Any]:
    path = computer_use_latest_ui_map_path()
    payload = _read_json(path, {})
    elements = payload.get("elements") if isinstance(payload, dict) else []
    if not isinstance(elements, list):
        elements = []
    return {
        "ok": True,
        "mode": "browser_harness_ui_map",
        "version": BROWSER_HARNESS_VERSION,
        "ui_map_path": str(path),
        "element_count": len(elements),
        "has_elements": bool(elements),
        "source": payload.get("source", "") if isinstance(payload, dict) else "",
        "fixture_label": payload.get("fixture_label", "") if isinstance(payload, dict) else "",
    }


def observe_browser_context() -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "ok": True,
        "mode": "browser_harness_observe",
        "version": BROWSER_HARNESS_VERSION,
        "observation": {},
        "ui_map": read_browser_ui_map(),
        "limitations": [],
    }
    try:
        from modules.computer_use_core_ru import observe_screen
        observation = observe_screen()
        result["observation"] = observation if isinstance(observation, dict) else {"ok": False, "reason": "observe_screen returned non-dict"}
    except Exception as exc:
        result["limitations"].append(f"observe_screen unavailable: {exc}")
    return result


def _ground_browser_target(descriptions: List[str], kind: str, text: str) -> Dict[str, Any]:
    from modules.computer_use_grounding_ru import build_grounded_action

    attempts: List[Dict[str, Any]] = []
    for description in descriptions:
        grounded = build_grounded_action(description, kind=kind, text=text, min_confidence=0.25)
        attempts.append({
            "description": description,
            "ok": bool(grounded.get("ok")),
            "reason": grounded.get("reason", ""),
            "confidence": grounded.get("action", {}).get("confidence"),
        })
        if grounded.get("ok"):
            return {
                "ok": True,
                "action": grounded["action"],
                "grounding": grounded.get("grounding", {}),
                "attempts": attempts,
            }
    return {
        "ok": False,
        "reason": "No grounded browser target found.",
        "attempts": attempts,
    }


def _target_candidates(task: Dict[str, Any]) -> List[str]:
    target = str(task.get("target_description") or "").strip()
    task_type = str(task.get("task_type") or "")
    if task_type == "navigate_url":
        return [target, "Address bar", "Адрес", "Поиск", "Search"]
    if task_type == "click_text":
        return [target]
    return [target, "Поиск", "Search", "Адресная строка", "Address bar"]


def _build_action(task: Dict[str, Any], safety: Dict[str, Any]) -> Dict[str, Any]:
    task_type = str(task.get("task_type") or "")
    payload = str(task.get("payload") or "")
    modifies_files = bool(safety.get("requires_confirmation"))

    if task_type == "click_text":
        grounding = _ground_browser_target(_target_candidates(task), kind="click", text="")
    else:
        grounding = _ground_browser_target(_target_candidates(task), kind="type", text=payload)

    if not grounding.get("ok"):
        return {
            "kind": "ask_user",
            "message": "Нужен видимый браузер и заземлённая адресная строка, поле поиска или целевой элемент.",
            "grounded": False,
            "gui_only": True,
            "modifies_files": modifies_files,
            "requires_confirmation": modifies_files,
            "allowed_to_execute": False,
            "reason": grounding.get("reason", "No grounded browser target found."),
            "grounding": grounding,
        }

    action = dict(grounding["action"])
    action.update({
        "goal": task.get("payload") or task.get("target_description") or "",
        "gui_only": True,
        "modifies_files": modifies_files,
        "file_change_policy": "requires_explicit_modifies_files_true",
        "ui_intent": "browser_harness_one_step_gui",
        "browser_harness_version": BROWSER_HARNESS_VERSION,
        "requires_confirmation": modifies_files,
        "reason": "Browser Harness proposes exactly one grounded GUI action.",
    })

    if task_type == "click_text":
        action["kind"] = "click"
        action["text"] = ""

    return action


def plan_one_browser_action(goal: str, simulate: bool = True, observe_first: bool = False) -> Dict[str, Any]:
    _ensure_dirs()
    safety = safety_check_browser_goal(goal)
    if safety.get("blocked"):
        result = {
            "ok": False,
            "handled": True,
            "mode": "browser_harness_plan",
            "version": BROWSER_HARNESS_VERSION,
            "blocked": True,
            "requires_confirmation": True,
            "allowed_to_execute": False,
            "one_action": True,
            "goal": redact_browser_text(goal),
            "safety": safety,
            "reason": safety.get("reason"),
        }
        result["artifact"] = _write_json(BROWSER_HARNESS_DIR / f"browser_harness_blocked_{_stamp()}_{uuid.uuid4().hex[:6]}.json", result)
        return result

    observation = observe_browser_context() if observe_first else {"ok": True, "mode": "browser_harness_observe_skipped"}
    task = classify_browser_goal(goal)
    if not task.get("ok"):
        result = {
            "ok": False,
            "handled": True,
            "mode": "browser_harness_plan",
            "version": BROWSER_HARNESS_VERSION,
            "blocked": bool(task.get("url_check", {}).get("blocked")),
            "requires_confirmation": True,
            "allowed_to_execute": False,
            "one_action": True,
            "goal": redact_browser_text(goal),
            "safety": safety,
            "task": task,
            "reason": task.get("reason", "task classification failed"),
        }
        result["artifact"] = _write_json(BROWSER_HARNESS_DIR / f"browser_harness_invalid_{_stamp()}_{uuid.uuid4().hex[:6]}.json", result)
        return result

    action = _build_action(task, safety)
    try:
        from modules.computer_use_auto_action_ru import auto_policy_for_action
        policy = auto_policy_for_action(action) if action.get("kind") != "ask_user" else {
            "ok": True,
            "blocked": False,
            "allowed_to_execute": False,
            "requires_confirmation": bool(action.get("requires_confirmation")),
            "risk": "medium" if action.get("requires_confirmation") else "low",
            "reason": "Ask-user action is not auto-executed.",
        }
    except Exception as exc:
        policy = {
            "ok": True,
            "blocked": False,
            "allowed_to_execute": False,
            "requires_confirmation": bool(action.get("requires_confirmation")),
            "risk": "medium",
            "reason": f"auto policy unavailable: {exc}",
        }

    requires_confirmation = bool(safety.get("requires_confirmation") or action.get("requires_confirmation") or policy.get("requires_confirmation"))
    allowed_to_execute = bool(policy.get("allowed_to_execute")) and not requires_confirmation and action.get("kind") != "ask_user"

    result = {
        "ok": bool(policy.get("ok", True)) and not bool(policy.get("blocked")),
        "handled": True,
        "mode": "browser_harness_plan",
        "version": BROWSER_HARNESS_VERSION,
        "goal": redact_browser_text(goal),
        "simulate": bool(simulate),
        "one_action": True,
        "action_count": 1,
        "task": task,
        "action": action,
        "policy": policy,
        "safety": safety,
        "observation": observation,
        "requires_confirmation": requires_confirmation,
        "allowed_to_execute": allowed_to_execute,
        "blocked": bool(policy.get("blocked")),
        "next_step": "observe_after_action" if allowed_to_execute else ("ask_user_confirmation" if requires_confirmation else "ask_user_to_open_browser_or_focus_target"),
    }
    result["artifact"] = _write_json(BROWSER_HARNESS_DIR / f"browser_harness_plan_{_stamp()}_{uuid.uuid4().hex[:6]}.json", result)
    return result


def simulate_browser_step(goal: str) -> Dict[str, Any]:
    result = plan_one_browser_action(goal, simulate=True, observe_first=False)
    result["mode"] = "browser_harness_simulate"
    result["executed"] = False
    result["execution_reason"] = "simulation only; no browser automation was executed"
    return result


def _browser_fixture_ui_map() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "browser_harness_contract_ui_map",
        "version": BROWSER_HARNESS_VERSION,
        "source": "browser_harness_contract",
        "elements": [
            {
                "element_id": "browser_address_bar",
                "role": "textbox",
                "text": "Адресная строка",
                "bounds": {"x": 80, "y": 42, "w": 760, "h": 32},
                "confidence": 0.96,
                "source": "browser_harness_contract",
            },
            {
                "element_id": "browser_search_field",
                "role": "textbox",
                "text": "Поиск",
                "bounds": {"x": 120, "y": 180, "w": 620, "h": 44},
                "confidence": 0.94,
                "source": "browser_harness_contract",
            },
            {
                "element_id": "browser_result_link",
                "role": "link",
                "text": "Python Documentation",
                "bounds": {"x": 130, "y": 260, "w": 260, "h": 24},
                "confidence": 0.90,
                "source": "browser_harness_contract",
            },
        ],
        "limitations": [],
    }


@contextmanager
def _temporary_browser_ui_map(label: str) -> Iterator[Dict[str, Any]]:
    from modules.computer_use_test_fixtures_ru import temporary_latest_ui_map

    with temporary_latest_ui_map(_browser_fixture_ui_map(), label=label) as info:
        yield info


def _contract(name: str, ok: bool, result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "finished_at": _now(),
        "result": result,
    }


def run_browser_harness_contracts(write_report: bool = True) -> Dict[str, Any]:
    contracts: List[Dict[str, Any]] = []

    status_result = status()
    contracts.append(_contract(
        "status_ok",
        bool(status_result.get("ok")) and status_result.get("version") == BROWSER_HARNESS_VERSION,
        status_result,
    ))

    with _temporary_browser_ui_map("browser_harness_safe_search") as fixture:
        plan = plan_one_browser_action("найди Python documentation", simulate=True)
        contracts.append(_contract(
            "safe_search_proposes_one_grounded_type",
            bool(plan.get("ok"))
            and plan.get("one_action") is True
            and plan.get("action", {}).get("kind") == "type"
            and plan.get("action", {}).get("grounded") is True
            and not bool(plan.get("requires_confirmation"))
            and bool(plan.get("allowed_to_execute")),
            {"plan": plan, "fixture": fixture},
        ))

    with _temporary_browser_ui_map("browser_harness_safe_click") as fixture:
        plan = plan_one_browser_action("кликни Python Documentation", simulate=True)
        contracts.append(_contract(
            "safe_click_proposes_one_grounded_click",
            bool(plan.get("ok"))
            and plan.get("one_action") is True
            and plan.get("action", {}).get("kind") == "click"
            and plan.get("action", {}).get("grounded") is True
            and not bool(plan.get("requires_confirmation")),
            {"plan": plan, "fixture": fixture},
        ))

    with _temporary_browser_ui_map("browser_harness_file_change") as fixture:
        plan = plan_one_browser_action("скачай файл report.pdf", simulate=True)
        contracts.append(_contract(
            "browser_file_change_requires_confirmation",
            bool(plan.get("ok"))
            and bool(plan.get("requires_confirmation"))
            and not bool(plan.get("allowed_to_execute")),
            {"plan": plan, "fixture": fixture},
        ))

    blocked_shell = safety_check_browser_goal("открой powershell через браузер")
    contracts.append(_contract(
        "dangerous_shell_goal_blocked",
        not bool(blocked_shell.get("ok")) and bool(blocked_shell.get("blocked")),
        blocked_shell,
    ))

    blocked_profile = safety_check_browser_goal("прочитай browser profile cookies")
    contracts.append(_contract(
        "browser_profile_and_cookies_blocked",
        not bool(blocked_profile.get("ok")) and bool(blocked_profile.get("blocked")),
        blocked_profile,
    ))

    summary = {
        "passed": sum(1 for item in contracts if item.get("ok")),
        "total": len(contracts),
        "failed": sum(1 for item in contracts if not item.get("ok")),
    }
    payload = {
        "ok": summary["failed"] == 0,
        "handled": True,
        "mode": "browser_harness_contract_tests",
        "version": BROWSER_HARNESS_VERSION,
        "summary": summary,
        "contracts": contracts,
        "created_at": _now(),
    }
    if write_report:
        payload["report"] = _write_json(BROWSER_HARNESS_REPORT_DIR / f"browser_harness_contracts_{_stamp()}.json", payload)
    return payload


def status() -> Dict[str, Any]:
    _ensure_dirs()
    ui_map = read_browser_ui_map()
    return {
        "ok": True,
        "mode": "browser_harness_status",
        "version": BROWSER_HARNESS_VERSION,
        "name": BROWSER_HARNESS_NAME,
        "browser_harness_dir": str(BROWSER_HARNESS_DIR),
        "report_dir": str(BROWSER_HARNESS_REPORT_DIR),
        "ui_map": ui_map,
        "capabilities": [
            "safe one-step browser GUI planning",
            "URL and query typing through grounded UI only",
            "click planning by visible browser text",
            "file-changing browser tasks require confirmation",
            "dangerous, sensitive, admin, terminal and browser-profile tasks are blocked",
        ],
    }


def report() -> Dict[str, Any]:
    _ensure_dirs()
    reports = sorted(BROWSER_HARNESS_REPORT_DIR.glob("browser_harness_*.json"), reverse=True)
    return {
        "ok": True,
        "mode": "browser_harness_report",
        "version": BROWSER_HARNESS_VERSION,
        "latest_reports": [str(path) for path in reports[:10]],
        "status": status(),
    }


def is_browser_harness_command(command: str) -> bool:
    value = _normalize(command)
    prefixes = [
        "pc browser harness",
        "browser harness",
        "pc computer browser",
        "pc computer browser harness",
        "браузер harness",
        "браузерный harness",
        "браузер план",
    ]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def _strip_command_goal(raw: str, prefixes: List[str]) -> str:
    lowered = _normalize(raw)
    for prefix in prefixes:
        normalized_prefix = _normalize(prefix)
        if lowered == normalized_prefix:
            return ""
        if lowered.startswith(normalized_prefix + " "):
            return raw[len(prefix):].strip(" :,-—")
    return raw.strip()


def handle_dispatch_command(command: str) -> Dict[str, Any]:
    raw = str(command or "").strip()
    value = _normalize(raw)

    status_aliases = {
        "pc browser harness status",
        "browser harness status",
        "pc computer browser status",
        "статус браузерного harness",
    }
    report_aliases = {
        "pc browser harness report",
        "browser harness report",
        "pc computer browser report",
        "отчет браузерного harness",
        "отчёт браузерного harness",
    }
    contract_aliases = {
        "pc browser harness contracts",
        "browser harness contracts",
        "pc computer browser contracts",
        "контракты браузерного harness",
    }

    if value in status_aliases:
        result = status()
        result["handled"] = True
        return result

    if value in report_aliases:
        result = report()
        result["handled"] = True
        return result

    if value in contract_aliases:
        result = run_browser_harness_contracts(write_report=True)
        result["handled"] = True
        return result

    plan_prefixes = [
        "pc browser harness plan",
        "browser harness plan",
        "pc computer browser plan",
        "браузер план",
    ]
    simulate_prefixes = [
        "pc browser harness simulate",
        "browser harness simulate",
        "pc computer browser simulate",
        "pc computer browser",
        "браузерный harness",
    ]

    for prefix in plan_prefixes:
        if value == _normalize(prefix) or value.startswith(_normalize(prefix) + " "):
            goal = _strip_command_goal(raw, [prefix])
            result = plan_one_browser_action(goal, simulate=True)
            result["handled"] = True
            return result

    for prefix in simulate_prefixes:
        if value == _normalize(prefix) or value.startswith(_normalize(prefix) + " "):
            goal = _strip_command_goal(raw, [prefix])
            result = simulate_browser_step(goal)
            result["handled"] = True
            return result

    return {
        "ok": False,
        "handled": False,
        "mode": "browser_harness_dispatch",
        "version": BROWSER_HARNESS_VERSION,
        "reason": "not a Browser Harness command",
    }


def dispatch(command: str) -> Dict[str, Any]:
    result = handle_dispatch_command(command)
    if result.get("handled"):
        return result
    return {
        "ok": False,
        "handled": False,
        "mode": "browser_harness_unknown_command",
        "version": BROWSER_HARNESS_VERSION,
        "command": command,
        "hint": "Используй: pc browser harness status, pc browser harness contracts, pc computer browser simulate <цель>",
    }
````

### ПУТЬ: modules/browser_operator.py (656 строк, 20128 байт)

````python
import re
import json
from datetime import datetime
from json_repair import repair_json

from core.llm import ask_llm
from modules.browser import search, get_search_result_links, open_url, read_page
from modules.files import create_folder, write_file


USER_PC_PROFILE = """
Известный ПК пользователя:
- CPU: Intel Core i7-14700KF
- GPU: GeForce RTX 5070 12 GB
- RAM: 32 GB DDR5
- ОС: Windows
- Пользователь запускает локальные модели через LM Studio
"""


QUERY_SYSTEM = """
Ты Browser Operator Query Planner.

Твоя задача — превратить цель пользователя в 2-4 поисковых запроса.

Верни только JSON.

Формат:
{
  "queries": [
    "query 1",
    "query 2",
    "query 3"
  ]
}

Правила:
- Если пользователь просит найти варианты, сравнить и выбрать лучший — делай запросы под сравнение.
- Если пользователь спрашивает про локальные LLM для ПК — ищи именно модели, а не программы.
- Для локальных LLM добавляй: GGUF, LM Studio, 12GB VRAM, RTX, benchmarks.
- Если пользователь спрашивает про AI browser — добавляй Comet AI browser alternatives.
- Если пользователь спрашивает про Claude Code — добавляй Claude Code alternatives.
- Запросы должны быть короткие.
- Не используй markdown.
- Не объясняй.
"""


EXTRACT_SYSTEM = """
Ты Browser Operator Extractor.

Тебе дают текст одной страницы.
Нужно вытащить конкретные варианты, которые подходят под запрос пользователя.

Верни только JSON.

Формат:
{
  "items": [
    {
      "name": "Название",
      "category": "Категория",
      "pros": ["плюс 1", "плюс 2"],
      "cons": ["минус 1"],
      "best_for": "для кого подходит",
      "notes": "важная заметка"
    }
  ]
}

Строгие правила:
- Не выдумывай варианты, которых нет в тексте.
- Если пользователь ищет локальные LLM, извлекай только МОДЕЛИ.
- Если пользователь ищет локальные LLM, НЕ извлекай программы/платформы: LM Studio, Ollama, AnythingLLM, GPT4All, llama.cpp, Open WebUI, Jan.
- Если страница про инструменты запуска, бери только названия моделей, если они есть.
- Если страница мусорная или вариантов нет, верни {"items":[]}.
- Максимум 8 вариантов с одной страницы.
- Не используй markdown.
- Не объясняй.
"""


FINAL_SYSTEM = """
Ты Browser Operator.

Твоя задача — сравнить найденные варианты и выбрать лучший под задачу пользователя.

Верни обычный текст, не JSON.

Структура:

# Сравнение вариантов

## Задача
...

## Найденные варианты
...

## Таблица сравнения
...

## Лучший выбор
...

## Почему именно он
...

## Альтернативы
...

## Что сделать дальше
...

Правила:
- Пиши на русском.
- Будь практичным.
- Не выдумывай факты, которых нет в найденных данных.
- Если данных мало, честно напиши.
- Если задача связана с локальными LLM, учитывай железо пользователя.
- Если задача связана с локальными LLM, НЕ выбирай программу вместо модели.
- Если задача связана с локальными LLM, лучший выбор должен быть именно LLM-моделью.
- Для RTX 5070 12 GB нормально рассматривать 7B, 8B, 12B, 14B модели в GGUF Q4/Q5.
- Обязательно выбери лучший вариант, если данных достаточно.
- Обязательно закончи разделом "Что сделать дальше".
"""


BAD_LOCAL_LLM_TOOLS = [
    "lm studio",
    "ollama",
    "anythingllm",
    "gpt4all",
    "llama.cpp",
    "open webui",
    "jan",
    "koboldcpp",
    "text generation webui",
    "hugging face",
    "huggingface",
]


KNOWN_LOCAL_MODEL_PATTERNS = [
    "qwen",
    "qwen2.5",
    "qwen3",
    "qwen coder",
    "qwen2.5-coder",
    "gemma",
    "gemma 2",
    "gemma 3",
    "llama",
    "llama 3",
    "llama 3.1",
    "llama 3.2",
    "mistral",
    "mistral nemo",
    "mistral small",
    "deepseek",
    "deepseek coder",
    "deepseek r1",
    "phi",
    "phi-4",
    "mixtral",
    "starcoder",
    "starcoder2",
    "codellama",
    "nous hermes",
    "hermes",
    "zephyr",
    "openchat",
    "yi",
]


def _safe_filename(text: str):
    text = text.lower()
    text = re.sub(r"[^a-zа-я0-9]+", "_", text)
    text = text.strip("_")
    return text[:50] or "operator_report"


def _is_local_llm_goal(goal: str):
    text = goal.lower()

    return (
        "llm" in text
        or "локальн" in text and "модел" in text
        or "нейросет" in text and "пк" in text
        or "lm studio" in text
    )


def _target_count(goal: str):
    text = goal.lower()

    match = re.search(r"\b(\d{1,2})\b", text)

    if match:
        value = int(match.group(1))
        return max(1, min(value, 10))

    if "пять" in text:
        return 5

    if "три" in text:
        return 3

    if "топ" in text or "лучших" in text:
        return 5

    return 5


def _make_search_queries(goal: str):
    if _is_local_llm_goal(goal):
        return [
            "best local LLM models GGUF 12GB VRAM LM Studio",
            "best GGUF models RTX 12GB VRAM Qwen Gemma Llama Mistral",
            "best local coding LLM Qwen Coder DeepSeek Coder GGUF",
            "local LLM benchmark 7B 14B GGUF LM Studio",
        ]

    try:
        answer = ask_llm(QUERY_SYSTEM, goal, max_tokens=700)
        answer = answer.replace("```json", "").replace("```", "").strip()

        data = json.loads(repair_json(answer))
        queries = data.get("queries", [])

        if isinstance(queries, list) and queries:
            return queries[:4]

    except Exception:
        pass

    return [
        goal,
        f"{goal} comparison",
        f"{goal} best options",
    ]


def _collect_links(query: str, limit=4):
    search(query, engine="duckduckgo")
    links = get_search_result_links(limit=limit)

    if not links:
        search(query, engine="bing")
        links = get_search_result_links(limit=limit)

    return links


def _is_bad_local_llm_item(name: str):
    name = name.lower().strip()

    for bad in BAD_LOCAL_LLM_TOOLS:
        if bad in name:
            return True

    return False


def _normalize_item_name(name: str):
    name = name.strip()
    name = re.sub(r"\s+", " ", name)
    return name


def _extract_items(goal: str, source: dict):
    title = source.get("title", "")
    url = source.get("url", "")
    text = source.get("text", "")

    target_count = _target_count(goal)
    local_llm_goal = _is_local_llm_goal(goal)

    extra_rules = ""

    if local_llm_goal:
        extra_rules = """
Дополнительные правила для локальных LLM:
- Извлекай только названия моделей.
- Примеры моделей: Qwen, Qwen2.5-Coder, Qwen3, Gemma, Llama, Mistral, DeepSeek, Phi, Mixtral, StarCoder, Hermes, Zephyr.
- Не извлекай оболочки и программы: LM Studio, Ollama, AnythingLLM, GPT4All, llama.cpp, Open WebUI.
"""

    prompt = f"""
Цель пользователя:
{goal}

Нужно найти примерно {target_count} вариантов.

Источник:
{title}
{url}

Текст страницы:
{text[:6000]}

{extra_rules}

Вытащи конкретные варианты из источника.
"""

    try:
        answer = ask_llm(EXTRACT_SYSTEM, prompt, max_tokens=1800)
        answer = answer.replace("```json", "").replace("```", "").strip()

        data = json.loads(repair_json(answer))
        items = data.get("items", [])

        if not isinstance(items, list):
            return []

        cleaned = []

        for item in items:
            if not isinstance(item, dict):
                continue

            name = _normalize_item_name(item.get("name", ""))

            if not name:
                continue

            if local_llm_goal and _is_bad_local_llm_item(name):
                continue

            item["name"] = name
            item["source_title"] = title
            item["source_url"] = url
            cleaned.append(item)

        return cleaned

    except Exception:
        return []


def _keyword_candidates_from_sources(goal: str, sources: list):
    if not _is_local_llm_goal(goal):
        return []

    full_text = ""

    for source in sources:
        full_text += "\n" + source.get("title", "")
        full_text += "\n" + source.get("text", "")

    lower_text = full_text.lower()

    candidates = []

    model_map = [
        {
            "name": "Qwen2.5-Coder",
            "keywords": ["qwen2.5-coder", "qwen 2.5 coder", "qwen coder"],
            "best_for": "кодинг, локальный агент, работа с проектами",
        },
        {
            "name": "Qwen3",
            "keywords": ["qwen3", "qwen 3"],
            "best_for": "универсальные задачи, рассуждение, чат",
        },
        {
            "name": "Gemma 3",
            "keywords": ["gemma 3", "gemma3"],
            "best_for": "русский/английский чат, общее использование",
        },
        {
            "name": "Llama 3.1 / 3.2",
            "keywords": ["llama 3.1", "llama 3.2", "llama3.1", "llama3.2"],
            "best_for": "универсальное использование и совместимость",
        },
        {
            "name": "Mistral Nemo / Mistral Small",
            "keywords": ["mistral nemo", "mistral small"],
            "best_for": "быстрый локальный чат и баланс качества/скорости",
        },
        {
            "name": "DeepSeek Coder",
            "keywords": ["deepseek coder", "deepseek-coder"],
            "best_for": "программирование и работа с кодом",
        },
        {
            "name": "DeepSeek R1 Distill",
            "keywords": ["deepseek r1", "deepseek-r1", "r1 distill"],
            "best_for": "рассуждения и сложная логика",
        },
        {
            "name": "Phi-4",
            "keywords": ["phi-4", "phi 4"],
            "best_for": "лёгкая быстрая модель для повседневных задач",
        },
        {
            "name": "Hermes 2 Pro",
            "keywords": ["hermes 2 pro", "nous hermes", "hermes"],
            "best_for": "универсальный чат и инструкции",
        },
        {
            "name": "Zephyr 7B",
            "keywords": ["zephyr 7b", "zephyr"],
            "best_for": "лёгкий чат-помощник",
        },
    ]

    for model in model_map:
        found = False

        for keyword in model["keywords"]:
            if keyword.lower() in lower_text:
                found = True
                break

        if not found:
            continue

        candidates.append({
            "name": model["name"],
            "category": "Локальная LLM-модель",
            "pros": [
                "Найдена в источниках по локальным LLM",
                "Подходит для запуска через LM Studio/GGUF при наличии подходящей квантизации"
            ],
            "cons": [
                "Точные требования зависят от размера модели и квантизации"
            ],
            "best_for": model["best_for"],
            "notes": "Кандидат извлечен по упоминаниям в найденных источниках",
            "source_title": "Извлечено из найденных источников",
            "source_url": "multiple_sources"
        })

    return candidates


def _deduplicate_items(items: list, local_llm_goal: bool):
    result = []
    seen = set()

    for item in items:
        name = _normalize_item_name(item.get("name", ""))

        if not name:
            continue

        if local_llm_goal and _is_bad_local_llm_item(name):
            continue

        key = name.lower()

        if key in seen:
            continue

        seen.add(key)
        item["name"] = name
        result.append(item)

    return result


def _fallback_report(goal: str, search_queries: list, sources: list, items: list):
    lines = []

    lines.append("# Сравнение вариантов")
    lines.append("")
    lines.append("## Задача")
    lines.append(goal)
    lines.append("")
    lines.append("## Поисковые запросы")

    for q in search_queries:
        lines.append(f"- {q}")

    lines.append("")
    lines.append("## Источники")

    if not sources:
        lines.append("Источники не найдены.")
    else:
        for i, source in enumerate(sources, start=1):
            lines.append(f"{i}. {source.get('title', 'Без названия')}")
            lines.append(f"   {source.get('url', '')}")

    lines.append("")
    lines.append("## Найденные варианты")

    if not items:
        lines.append("Варианты не удалось надежно извлечь из источников.")
    else:
        for i, item in enumerate(items, start=1):
            lines.append(f"{i}. {item.get('name', 'Без названия')}")
            lines.append(f"   Для кого: {item.get('best_for', '')}")
            lines.append(f"   Источник: {item.get('source_url', '')}")

    lines.append("")
    lines.append("## Лучший выбор")
    lines.append("Автоматически выбрать лучший вариант не удалось — данных недостаточно.")
    lines.append("")
    lines.append("## Что сделать дальше")
    lines.append("- Повторить запрос более конкретно.")
    lines.append("- Проверить найденные источники вручную.")
    lines.append("- Использовать более сильную локальную модель для сравнения.")

    return "\n".join(lines)


def make_operator_report(goal: str):
    create_folder("Reports")

    target_count = _target_count(goal)
    local_llm_goal = _is_local_llm_goal(goal)

    search_queries = _make_search_queries(goal)

    all_links = []
    seen_urls = set()

    for query in search_queries:
        links = _collect_links(query, limit=5)

        for link in links:
            url = link.get("url")

            if not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)
            all_links.append(link)

            if len(all_links) >= 10:
                break

        if len(all_links) >= 10:
            break

    collected_sources = []

    for link in all_links[:7]:
        try:
            open_url(link["url"])
            text = read_page(limit=6500)

            collected_sources.append({
                "title": link.get("title", ""),
                "url": link.get("url", ""),
                "text": text
            })

        except Exception as e:
            collected_sources.append({
                "title": link.get("title", ""),
                "url": link.get("url", ""),
                "text": f"Не удалось открыть источник: {e}"
            })

    extracted_items = []

    for source in collected_sources:
        items = _extract_items(goal, source)
        extracted_items.extend(items)

    keyword_items = _keyword_candidates_from_sources(goal, collected_sources)
    extracted_items.extend(keyword_items)

    extracted_items = _deduplicate_items(extracted_items, local_llm_goal)

    hardware_context = ""

    if local_llm_goal:
        hardware_context = USER_PC_PROFILE

    items_text = json.dumps(extracted_items[:25], ensure_ascii=False, indent=2)

    sources_text = ""

    for i, source in enumerate(collected_sources, start=1):
        sources_text += f"""
SOURCE {i}
TITLE: {source.get("title", "")}
URL: {source.get("url", "")}

---
"""

    extra_final_rules = ""

    if local_llm_goal:
        extra_final_rules = f"""
Дополнительные правила:
- Пользователь просил примерно {target_count} локальных LLM.
- В итоговом списке должны быть именно модели, а не платформы.
- Не называй LM Studio, Ollama, AnythingLLM, GPT4All лучшей LLM — это инструменты/оболочки.
- Для RTX 5070 12 GB лучше рекомендовать модели 7B-14B в GGUF Q4/Q5.
- Если среди кандидатов есть Qwen2.5-Coder/Qwen Coder и задача связана с агентом/кодом, оцени его высоко.
"""

    prompt = f"""
Цель пользователя:
{goal}

Контекст пользователя:
{hardware_context}

Поисковые запросы:
{search_queries}

Источники:
{sources_text}

Извлеченные варианты:
{items_text}

{extra_final_rules}

Сравни варианты и выбери лучший.
"""

    try:
        report = ask_llm(FINAL_SYSTEM, prompt, max_tokens=4000)
    except Exception as e:
        report = f"Ошибка генерации сравнения: {e}"

    if not report or not report.strip():
        report = _fallback_report(goal, search_queries, collected_sources, extracted_items)

    if "## Что сделать дальше" not in report:
        report += """

## Что сделать дальше
- Проверить источники вручную.
- Повторить сравнение более точным запросом.
- Протестировать лучший вариант на практике.
"""

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = _safe_filename(goal)
    path = f"Reports/{stamp}_{name}_comparison.md"

    write_file(path, report)

    return {
        "path": path,
        "report": report,
        "sources": all_links,
        "search_queries": search_queries,
        "items": extracted_items,
        "collected_count": len(collected_sources),
        "target_count": target_count
    }
````

### ПУТЬ: modules/browser_profile_ignore.py (133 строк, 3384 байт)

````python
from pathlib import Path
from modules.project_paths import get_project_root
import importlib

from core.state import set_value


ROOT_DIR = get_project_root()
BROWSER_PROFILE_REL = Path("Projects") / "BrowserProfile"
BROWSER_PROFILE_DIR = ROOT_DIR / BROWSER_PROFILE_REL

RELAY_APPLY_ACTIONS = {
    "apply",
    "apply_response",
    "apply_answer",
    "apply_last_response",
    "relay_apply",
}


def _resolve(path):
    try:
        return Path(path).resolve()
    except Exception:
        return Path(str(path or ""))


def is_browser_profile_path(path, root_dir=ROOT_DIR):
    full = _resolve(path)
    profile = _resolve(Path(root_dir) / BROWSER_PROFILE_REL)

    return full == profile or profile in full.parents


def should_ignore_path(path):
    return is_browser_profile_path(path)


def filter_walk_dirs(current_root, dirs):
    safe_dirs = []

    for name in list(dirs):
        candidate = Path(current_root) / name

        if is_browser_profile_path(candidate):
            continue

        safe_dirs.append(name)

    dirs[:] = safe_dirs
    return dirs


def copytree_ignore(src, names):
    ignored = set()
    src_path = Path(src)

    for name in names:
        candidate = src_path / name

        if is_browser_profile_path(candidate):
            ignored.add(name)

    return ignored


def is_relay_apply_action(tool, action):
    return str(tool or "") == "chatgpt_relay" and str(action or "") in RELAY_APPLY_ACTIONS


def close_gpt_browser_context():
    """Close GPT Browser Bridge so Chromium releases BrowserProfile locks."""
    try:
        bridge = importlib.import_module("modules.gpt_browser_bridge")
    except Exception as e:
        result = f"GPT Browser Bridge close skipped: {e}"
        set_value("last_gpt_browser_action", "close")
        set_value("last_gpt_browser_close_result", result)
        return result

    close_bridge = getattr(bridge, "close_bridge", None)

    if callable(close_bridge):
        try:
            result = close_bridge()
            text = str(result or "GPT Browser Bridge close: close_bridge executed")
            set_value("last_gpt_browser_action", "close")
            set_value("last_gpt_browser_close_result", text)
            return text
        except Exception:
            pass

    closed = []

    for attr in ["_page", "_context", "_browser"]:
        obj = getattr(bridge, attr, None)

        if obj is None:
            continue

        try:
            obj.close()
            closed.append(attr)
        except Exception:
            pass

        try:
            setattr(bridge, attr, None)
        except Exception:
            pass

    playwright = getattr(bridge, "_playwright", None)

    if playwright is not None:
        try:
            playwright.stop()
            closed.append("_playwright")
        except Exception:
            pass

        try:
            setattr(bridge, "_playwright", None)
        except Exception:
            pass

    if closed:
        text = "GPT Browser Bridge close: closed " + ", ".join(closed)
    else:
        text = "GPT Browser Bridge close: no active Playwright objects found"

    set_value("last_gpt_browser_action", "close")
    set_value("last_gpt_browser_close_result", text)
    return text
````

### ПУТЬ: modules/browser_super.py (747 строк, 24356 байт)

````python
import json
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.llm import ask_llm
from core.state import get_value, set_value
from modules import browser_actions
from modules.browser import get_search_result_links, open_local_site, open_url, read_page, search
from modules.browser_autopilot import is_browser_task_safe, observe_browser_page
from modules.codegen import generate_site, improve_site


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "browser_super"

RESEARCH_SYSTEM = """
Ты Browser Research Agent уровня Perplexity/Comet.

Собери краткий, полезный ответ по источникам.
Пиши по-русски.
Не выдумывай факты.
Если данных мало, скажи это.
В конце добавь Sources с номерами и URL.
"""


PAGE_AUDIT_SYSTEM = """
Ты браузерный UX/research аналитик.

Проанализируй страницу по данным наблюдения.
Дай короткий список:
- что это за страница;
- ключевые элементы;
- полезные действия;
- риски/проблемы;
- следующий лучший шаг.
"""

PLATFORM_SITE_SYSTEM = """
Ты Browser Platform Site Operator.

Пользователь хочет сделать сайт на внешней платформе-конструкторе.
Подготовь практический build kit для работы в браузере:
- структура страниц;
- секции первого экрана и ниже;
- точные тексты для вставки;
- CTA;
- поля формы;
- SEO title/description;
- список изображений/ассетов;
- пошаговые действия на платформе.

Не проси пароли и оплату.
Не обещай публикацию без ручного подтверждения пользователя.
Пиши по-русски, кратко и прикладно.
"""

PLATFORM_URLS = {
    "tilda": "https://tilda.cc/",
    "тильда": "https://tilda.cc/",
    "тильде": "https://tilda.cc/",
    "тильду": "https://tilda.cc/",
    "tilde": "https://tilda.cc/",
    "wix": "https://www.wix.com/",
    "викс": "https://www.wix.com/",
    "webflow": "https://webflow.com/",
    "вебфлоу": "https://webflow.com/",
    "framer": "https://www.framer.com/",
    "фреймер": "https://www.framer.com/",
    "carrd": "https://carrd.co/",
    "readymag": "https://readymag.com/",
    "wordpress": "https://wordpress.com/",
    "wordpress.com": "https://wordpress.com/",
    "вордпресс": "https://wordpress.com/",
    "вордпресе": "https://wordpress.com/",
    "вордпрессе": "https://wordpress.com/",
    "notion": "https://www.notion.so/",
}


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_reports_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _short(value, limit=5000):
    text = str(value or "")

    if len(text) <= limit:
        return text

    return text[:limit] + "\n...[обрезано]"


def _clean_task(task):
    return str(task or "").strip(" \n\t:,-—")


def _strip_prefix(text, prefixes):
    source = _clean_task(text)
    lower = source.lower()

    for prefix in prefixes:
        if lower.startswith(prefix):
            return source[len(prefix):].strip(" :,-—")

    return source


def _extract_platform(task):
    text = _clean_task(task)
    lower = text.lower()

    for name in PLATFORM_URLS:
        if name in lower:
            return name

    markers = [
        "используй платформу",
        "на платформе",
        "через платформу",
        "use platform",
        "platform",
    ]

    for marker in markers:
        index = lower.find(marker)

        if index == -1:
            continue

        value = text[index + len(marker):].strip(" :,-—")
        value = re.split(r"[,.;\n]| и | with | для ", value, maxsplit=1)[0].strip()
        return value[:80] or "static html/css/js"

    if "react" in lower:
        return "React-style static prototype"

    if "tailwind" in lower:
        return "Tailwind-style static HTML/CSS"

    if "wordpress" in lower:
        return "WordPress-like landing prototype"

    return "static html/css/js"


def _platform_url(platform):
    key = str(platform or "").strip().lower()
    return PLATFORM_URLS.get(key, "")


def _is_external_platform(platform):
    return bool(_platform_url(platform))


def _research_query(task):
    return _strip_prefix(
        task,
        [
            "browser deep research",
            "browser research",
            "browser compare",
            "браузер исследуй",
            "браузер сравни",
            "исследуй",
            "изучи",
            "сравни",
            "найди",
        ],
    )


def _site_prompt(task):
    text = _strip_prefix(
        task,
        [
            "browser site workflow",
            "browser build site",
            "browser напиши сайт",
            "browser создай сайт",
            "напиши сайт",
            "создай сайт",
            "сделай сайт",
        ],
    )
    platform = _extract_platform(task)

    return (
        f"{text}\n\n"
        f"Platform / style target: {platform}\n"
        "Сделай локальный статический сайт с index.html, style.css и script.js. "
        "Дизайн должен быть готов к просмотру в браузере, с адаптивностью, формой/CTA если уместно."
    ).strip()


def classify_browser_super_task(task):
    lower = _clean_task(task).lower()
    site_request = any(marker in lower for marker in ["сайт", "лендинг", "site", "landing"])
    site_action = any(marker in lower for marker in ["сделай", "создай", "напиши", "собери", "построй", "разработай", "build", "create", "make"])
    platform = _extract_platform(task)

    if (
        any(marker in lower for marker in ["build site", "site workflow", "напиши сайт", "создай сайт", "сделай сайт", "используй платформу"])
        or (site_request and site_action and _is_external_platform(platform))
    ):
        return "site_workflow"

    if any(marker in lower for marker in ["page audit", "audit page", "аудит страницы", "проверь текущую страницу"]):
        return "page_audit"

    if any(marker in lower for marker in ["form map", "forms map", "карта форм", "поля формы", "form audit"]):
        return "form_map"

    if any(marker in lower for marker in ["compare", "сравни", "versus", " vs "]):
        return "compare_research"

    if any(marker in lower for marker in ["research", "deep research", "исследуй", "изучи", "перплексити", "perplexity"]):
        return "research"

    return "smart_browser"


def build_browser_super_plan(task, mode="dry_run", max_results=3):
    task = _clean_task(task)
    mode = "execute" if str(mode or "").lower() in ["execute", "run"] else "dry_run"
    kind = classify_browser_super_task(task)

    try:
        max_results = max(1, min(int(max_results or 3), 5))
    except Exception:
        max_results = 3

    safe, reason = is_browser_task_safe(task)

    if not safe:
        return {
            "task": task,
            "kind": kind,
            "mode": mode,
            "max_results": max_results,
            "blocked_reason": reason,
            "steps": [],
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    if kind == "site_workflow":
        platform = _extract_platform(task)

        if _is_external_platform(platform):
            steps = [
                {"action": "generate_platform_build_kit", "args": {"platform": platform}},
                {"action": "open_platform", "args": {"url": _platform_url(platform)}},
                {"action": "observe_platform_page"},
                {"action": "map_visible_forms"},
                {"action": "save_report"},
            ]
        else:
            steps = [
                {"action": "generate_local_site", "args": {"platform": platform}},
                {"action": "open_local_site"},
                {"action": "read_page"},
                {"action": "screenshot"},
                {"action": "save_report"},
            ]
    elif kind in ["research", "compare_research", "smart_browser"]:
        query = _research_query(task)
        steps = [
            {"action": "search", "args": {"query": query}},
            {"action": "collect_results", "args": {"limit": max_results}},
            {"action": "read_sources", "args": {"limit": max_results}},
            {"action": "synthesize_with_sources"},
            {"action": "save_report"},
        ]
    elif kind == "page_audit":
        steps = [
            {"action": "observe"},
            {"action": "summarize"},
            {"action": "extract_links"},
            {"action": "extract_inputs"},
            {"action": "screenshot"},
            {"action": "save_report"},
        ]
    elif kind == "form_map":
        steps = [
            {"action": "observe"},
            {"action": "extract_inputs"},
            {"action": "extract_buttons"},
            {"action": "save_report"},
        ]
    else:
        steps = [{"action": "observe"}, {"action": "save_report"}]

    return {
        "task": task,
        "kind": kind,
        "mode": mode,
        "max_results": max_results,
        "blocked_reason": "",
        "steps": steps,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def format_browser_super_plan(plan):
    lines = [
        "Browser Super Plan:",
        f"- task: {plan.get('task')}",
        f"- kind: {plan.get('kind')}",
        f"- mode: {plan.get('mode')}",
        f"- max_results: {plan.get('max_results')}",
        f"- blocked_reason: {plan.get('blocked_reason') or 'нет'}",
        "",
        "Steps:",
    ]

    for index, step in enumerate(plan.get("steps", []), start=1):
        lines.append(f"{index}. {step.get('action')} {step.get('args') or {}}")

    return "\n".join(lines)


def _report_path(kind):
    _ensure_reports_dir()
    safe_kind = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(kind or "browser_super")).strip("_")
    return REPORTS_DIR / f"{safe_kind}_{_stamp()}.md"


def _write_report(kind, title, task, sections, status="ok"):
    path = _report_path(kind)
    lines = [
        f"# {title}",
        "",
        f"- status: {status}",
        f"- task: {task}",
        f"- generated_at: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]

    for heading, body in sections:
        lines.extend([
            f"## {heading}",
            "",
            str(body or "нет"),
            "",
        ])

    path.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_browser_super_report", str(path))
    set_value("last_browser_super_status", status)
    set_value("last_browser_super_task", task)
    return path


def _synthesize_research(task, sources):
    source_text = []

    for index, item in enumerate(sources, start=1):
        source_text.append(
            f"[{index}] {item.get('title')}\nURL: {item.get('url')}\nTEXT:\n{_short(item.get('text'), 2200)}"
        )

    prompt = (
        f"Task:\n{task}\n\n"
        "Sources:\n"
        + "\n\n".join(source_text)
    )

    try:
        return ask_llm(RESEARCH_SYSTEM, prompt, max_tokens=2200, timeout=180, use_context=False)
    except Exception as exc:
        fallback = ["Не удалось синтезировать LLM-ответ, показываю собранные источники.", f"Ошибка: {exc}", ""]

        for index, item in enumerate(sources, start=1):
            fallback.append(f"[{index}] {item.get('title')} — {item.get('url')}")

        return "\n".join(fallback)


def _generate_platform_build_kit(task, platform):
    prompt = (
        f"Platform: {platform}\n"
        f"Task:\n{task}\n\n"
        "Сделай build kit так, чтобы пользователь мог быстро собрать сайт прямо в конструкторе."
    )

    try:
        return ask_llm(PLATFORM_SITE_SYSTEM, prompt, max_tokens=2400, timeout=180, use_context=False)
    except Exception as exc:
        return (
            f"LLM build kit failed: {exc}\n\n"
            "Fallback build kit:\n"
            "- Page: Главная\n"
            "- Sections: hero, преимущества, услуги/продукт, кейсы, форма заявки, контакты\n"
            "- CTA: Оставить заявку\n"
            "- Form fields: имя, телефон/email, комментарий\n"
            "- SEO: укажи название услуги, город/нишу и главный оффер."
        )


def run_platform_site_workflow(task):
    task = _clean_task(task)
    platform = _extract_platform(task)
    url = _platform_url(platform)

    if not url:
        return run_site_workflow(task, improve=False, force_local=True)

    safe, reason = is_browser_task_safe(task)

    if not safe:
        return f"STOP: Browser Platform Workflow blocked.\nПричина: {reason}"

    build_kit = _generate_platform_build_kit(task, platform)
    open_result = open_url(url)

    try:
        observation = observe_browser_page()
    except Exception as exc:
        observation = f"Observe failed: {exc}"

    try:
        inputs = browser_actions.extract_inputs(limit=30)
    except Exception as exc:
        inputs = f"Inputs extraction failed: {exc}"

    try:
        screenshot = browser_actions.screenshot_page()
    except Exception as exc:
        screenshot = f"Screenshot failed: {exc}"

    next_steps = (
        "Safe next steps:\n"
        "1. Если платформа просит логин/пароль — войди вручную.\n"
        "2. Потом выполни: browser form map\n"
        "3. Для вставки текстов используй build kit из отчёта.\n"
        "4. Публикацию, оплату, покупку домена и ввод персональных данных подтверждай вручную.\n"
        "5. Для продолжения на открытой странице: browser page audit или browser click <текст>."
    )

    report = _write_report(
        "browser_platform_site_workflow",
        "Browser Platform Site Workflow",
        task,
        [
            ("Platform", f"{platform}\n{url}"),
            ("Build Kit", build_kit),
            ("Open result", open_result),
            ("Observation", f"```json\n{observation}\n```"),
            ("Visible forms / controls", f"```text\n{inputs}\n```"),
            ("Screenshot", screenshot),
            ("Next safe actions", next_steps),
        ],
    )

    set_value("last_browser_platform", platform)
    set_value("last_browser_platform_url", url)
    set_value("last_browser_platform_site_workflow_report", str(report))

    return (
        "Browser Platform Site Workflow готов.\n"
        f"Platform: {platform}\n"
        f"URL: {url}\n"
        f"Report: {report}\n\n"
        f"{next_steps}"
    )


def run_youtube_search(query):
    query = _clean_task(query)

    if not query:
        open_result = open_url("https://www.youtube.com/")
        return f"YouTube открыт.\n{open_result}"

    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    open_result = open_url(url)

    try:
        observation = observe_browser_page()
    except Exception as exc:
        observation = f"Observe failed: {exc}"

    try:
        links = browser_actions.extract_links(limit=20)
    except Exception as exc:
        links = f"Links extraction failed: {exc}"

    try:
        screenshot = browser_actions.screenshot_page()
    except Exception as exc:
        screenshot = f"Screenshot failed: {exc}"

    report = _write_report(
        "browser_youtube_search",
        "Browser YouTube Search",
        query,
        [
            ("Open result", open_result),
            ("Observation", f"```json\n{observation}\n```"),
            ("Links", f"```text\n{links}\n```"),
            ("Screenshot", screenshot),
            ("Next actions", "Можно продолжить: browser click <название видео> или browser page audit."),
        ],
    )

    set_value("last_browser_youtube_query", query)
    set_value("last_browser_youtube_report", str(report))

    return (
        "YouTube search готов.\n"
        f"Query: {query}\n"
        f"URL: {url}\n"
        f"Report: {report}\n\n"
        "Дальше можно: browser click <название видео>"
    )


def run_browser_research(task, max_results=3):
    task = _clean_task(task)
    query = _research_query(task)

    if not query:
        return "Browser Research: пустой запрос."

    safe, reason = is_browser_task_safe(task)

    if not safe:
        return f"STOP: Browser Research blocked.\nПричина: {reason}"

    search_result = search(query)
    links = get_search_result_links(limit=max_results)
    sources = []

    for link in links[:max_results]:
        url = link.get("url", "")

        try:
            open_url(url)
            page_text = read_page(limit=4500)
        except Exception as exc:
            page_text = f"Не удалось прочитать источник: {exc}"

        sources.append({
            "title": link.get("title", ""),
            "url": url,
            "text": page_text,
        })

    answer = _synthesize_research(task, sources)
    report = _write_report(
        "browser_research",
        "Browser Research Report",
        task,
        [
            ("Search", search_result),
            ("Answer", answer),
            ("Sources", "\n".join(f"- [{i}] {item.get('title')} — {item.get('url')}" for i, item in enumerate(sources, start=1))),
        ],
        status="ok" if sources else "empty",
    )

    set_value("last_browser_research_report", str(report))
    set_value("last_browser_research_query", query)

    return (
        "Browser Research завершен.\n"
        f"Query: {query}\n"
        f"Sources: {len(sources)}\n"
        f"Report: {report}\n\n"
        f"{_short(answer, 2500)}"
    )


def run_page_audit(task="current page"):
    task = _clean_task(task) or "current page"
    observation = observe_browser_page()
    summary = browser_actions.summarize_page()
    links = browser_actions.extract_links(limit=15)
    inputs = browser_actions.extract_inputs(limit=20)
    screenshot = browser_actions.screenshot_page()

    prompt = (
        f"Task:\n{task}\n\n"
        f"Observation:\n{observation}\n\n"
        f"Summary:\n{summary}\n\n"
        f"Links:\n{links}\n\n"
        f"Inputs:\n{inputs}"
    )

    try:
        audit = ask_llm(PAGE_AUDIT_SYSTEM, prompt, max_tokens=1200, timeout=120, use_context=False)
    except Exception as exc:
        audit = f"LLM audit failed: {exc}\n\nSummary:\n{summary}"

    report = _write_report(
        "browser_page_audit",
        "Browser Page Audit",
        task,
        [
            ("Audit", audit),
            ("Observation", f"```json\n{observation}\n```"),
            ("Links", f"```text\n{links}\n```"),
            ("Inputs", f"```text\n{inputs}\n```"),
            ("Screenshot", screenshot),
        ],
    )

    set_value("last_browser_page_audit_report", str(report))
    return f"Browser Page Audit готов.\nReport: {report}\n\n{_short(audit, 2200)}"


def run_form_map(task="current page"):
    task = _clean_task(task) or "current page"
    observation = observe_browser_page()
    inputs = browser_actions.extract_inputs(limit=40)
    buttons = "Используй browser observe/page audit для кнопок, если нужно больше контекста."

    report = _write_report(
        "browser_form_map",
        "Browser Form Map",
        task,
        [
            ("Inputs", f"```text\n{inputs}\n```"),
            ("Observation", f"```json\n{observation}\n```"),
            ("Buttons / next actions", buttons),
        ],
    )

    set_value("last_browser_form_map_report", str(report))
    return f"Browser Form Map готов.\nReport: {report}\n\nInputs:\n{_short(inputs, 2200)}"


def run_site_workflow(task, improve=False, force_local=False):
    task = _clean_task(task)
    prompt = _site_prompt(task)
    platform = _extract_platform(task)

    if _is_external_platform(platform) and not force_local:
        return run_platform_site_workflow(task)

    safe, reason = is_browser_task_safe(task)

    if not safe:
        return f"STOP: Browser Site Workflow blocked.\nПричина: {reason}"

    site = generate_site(prompt)
    folder = site.get("folder", "")
    set_value("last_site", folder)

    open_result = open_local_site(folder)
    read_result = read_page(limit=2500)
    screenshot = browser_actions.screenshot_page()
    improve_result = "не запускалось"

    if improve:
        try:
            improved = improve_site(folder)
            improve_result = json.dumps(improved, ensure_ascii=False, indent=2)
            open_result = open_local_site(folder)
            read_result = read_page(limit=2500)
            screenshot = browser_actions.screenshot_page()
        except Exception as exc:
            improve_result = f"Improve failed: {exc}"

    report = _write_report(
        "browser_site_workflow",
        "Browser Site Workflow",
        task,
        [
            ("Platform", platform),
            ("Generated files", "\n".join(f"- {path}" for path in site.get("created", []))),
            ("Open result", open_result),
            ("Read result", f"```text\n{_short(read_result, 2500)}\n```"),
            ("Improve result", improve_result),
            ("Screenshot", screenshot),
        ],
    )

    set_value("last_browser_site_workflow_report", str(report))
    return (
        "Browser Site Workflow готов.\n"
        f"Platform: {platform}\n"
        f"Site folder: {folder}\n"
        f"Report: {report}\n\n"
        f"{open_result}"
    )


def run_browser_super(task, mode="execute", max_results=3):
    plan = build_browser_super_plan(task, mode=mode, max_results=max_results)

    if plan.get("blocked_reason"):
        return f"STOP: Browser Super blocked.\nПричина: {plan.get('blocked_reason')}"

    if plan.get("mode") == "dry_run":
        report = _write_report(
            "browser_super_plan",
            "Browser Super Plan",
            plan.get("task", ""),
            [("Plan", f"```json\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n```")],
            status="dry_run",
        )
        return f"{format_browser_super_plan(plan)}\n\nReport: {report}"

    kind = plan.get("kind")

    if kind in ["research", "compare_research", "smart_browser"]:
        return run_browser_research(plan.get("task", ""), max_results=plan.get("max_results", 3))

    if kind == "page_audit":
        return run_page_audit(plan.get("task", ""))

    if kind == "form_map":
        return run_form_map(plan.get("task", ""))

    if kind == "site_workflow":
        return run_site_workflow(plan.get("task", ""), improve="улучши" in plan.get("task", "").lower())

    return run_page_audit(plan.get("task", ""))


def latest_browser_super_report():
    path = str(get_value("last_browser_super_report", "") or "").strip()

    if path:
        candidate = Path(path)

        if candidate.exists() and candidate.is_file():
            return candidate

    if not REPORTS_DIR.exists():
        return None

    reports = [path for path in REPORTS_DIR.glob("*.md") if path.is_file()]

    if not reports:
        return None

    return max(reports, key=lambda path: path.stat().st_mtime)
````

### ПУТЬ: modules/browser_task_runner.py (177 строк, 5183 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from modules import browser_actions
from modules.browser import open_url, read_page, search
from core.state import set_value


ROOT_DIR = get_project_root()
TASK_REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "browser_tasks"
WORKFLOW_REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "browser_workflows"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dir():
    TASK_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    WORKFLOW_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _run_step(step):
    action = str(step.get("action", "") or "").strip()
    args = step.get("args", {}) or {}

    if action == "open_url":
        return open_url(args.get("url", ""))

    if action == "search":
        return search(args.get("query", ""))

    if action in ["read", "read_page"]:
        return read_page()

    if action == "summarize":
        return browser_actions.summarize_page()

    if action == "click_text":
        return browser_actions.click_by_text(args.get("text", ""))

    if action == "fill_label":
        return browser_actions.fill_by_label(args.get("label", ""), args.get("value", ""))

    if action == "press_key":
        return browser_actions.press_key(args.get("key", "Enter"))

    if action == "wait":
        return browser_actions.wait_page(args.get("ms", 1000))

    if action == "screenshot":
        return browser_actions.screenshot_page()

    if action in ["open_first", "open_first_result", "click_first_link"]:
        return browser_actions.click_first_link()

    if action in ["links", "extract_links"]:
        return browser_actions.extract_links()

    if action in ["inputs", "extract_inputs"]:
        return browser_actions.extract_inputs()

    if action == "find_text":
        return browser_actions.find_text_on_page(args.get("text", ""))

    return f"Unknown browser step action: {action}"


def run_browser_steps(steps: list):
    _ensure_dir()
    started_at = datetime.now().isoformat(timespec="seconds")
    report_path = TASK_REPORTS_DIR / f"browser_task_{_stamp()}.md"

    lines = [
        "# Browser Task Report",
        "",
        f"- started_at: {started_at}",
        f"- steps: {len(steps or [])}",
        "",
    ]

    ok = True

    for index, step in enumerate(steps or [], start=1):
        lines.extend([
            f"## Step {index}: {step.get('action', 'unknown')}",
            "",
            "```text",
        ])

        try:
            result = _run_step(step)
            lines.append(str(result))

            if "STOP:" in str(result) or "failed" in str(result).lower() or "ошибка" in str(result).lower():
                ok = False
                lines.append("STOP: step failed, sequence stopped.")
                lines.append("```")
                break

        except Exception as e:
            ok = False
            lines.append(f"ERROR: {e}")
            lines.append("```")
            break

        lines.append("```")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_browser_task_report", str(report_path))

    status = "ok" if ok else "failed"
    return f"Browser sequence {status}.\nReport: {report_path}"


def run_browser_workflow(steps: list, title: str = "browser workflow"):
    _ensure_dir()
    started_at = datetime.now().isoformat(timespec="seconds")
    report_path = WORKFLOW_REPORTS_DIR / f"browser_workflow_{_stamp()}.md"

    lines = [
        f"# Browser Workflow Report: {title}",
        "",
        f"- started_at: {started_at}",
        f"- steps_count: {len(steps or [])}",
        "",
    ]

    ok = True
    error_msg = ""
    last_index = 0

    for index, step in enumerate(steps or [], start=1):
        last_index = index
        action = step.get("action", "unknown")
        args = step.get("args", {})
        lines.extend([
            f"## Step {index}: {action}",
            f"- args: {args}",
            "",
            "```text",
        ])

        try:
            result = _run_step(step)
            lines.append(str(result))

            if "STOP:" in str(result) or "failed" in str(result).lower() or "ошибка" in str(result).lower():
                ok = False
                error_msg = str(result)
                lines.append("STOP: step failed, workflow stopped.")
                lines.append("```")
                break

        except Exception as e:
            ok = False
            error_msg = str(e)
            lines.append(f"ERROR: {e}")
            lines.append("```")
            break

        lines.append("```")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")

    status = "success" if ok else "failed"
    set_value("last_browser_workflow_report", str(report_path))
    set_value("last_browser_workflow_status", status)

    if ok:
        return f"Browser workflow '{title}' completed successfully. Report: {report_path}"
    else:
        return f"Browser workflow '{title}' failed at step {last_index}. Error: {error_msg}. Report: {report_path}"

````

### ПУТЬ: modules/chatgpt_desktop_bridge.py (1098 строк, 36771 байт)

````python
import ctypes
import ctypes.wintypes
import json
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value


ROOT_DIR = get_project_root()
BRIDGE_DIR = ROOT_DIR / "Projects" / "ChatGPTDesktopBridge"
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "chatgpt_desktop_bridge"
PROMPT_PATH = BRIDGE_DIR / "chatgpt_desktop_prompt.md"
RESPONSE_PATH = BRIDGE_DIR / "chatgpt_desktop_response.md"
LOOP_STATE_PATH = BRIDGE_DIR / "loop_state.json"
DEFAULT_LOOP_INTERVAL_SECONDS = 20


VK_CONTROL = 0x11
VK_V = 0x56
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _default_loop_state():
    return {
        "enabled": False,
        "started_at": "",
        "stopped_at": "",
        "goal": "",
        "mode": "grimoire",
        "send": True,
        "prompt_sent": False,
        "last_action": "",
        "last_message": "",
        "last_step_at": "",
        "interval_seconds": DEFAULT_LOOP_INTERVAL_SECONDS,
        "rate_limited": False,
        "rate_limited_at": "",
        "cooldown_until": "",
        "last_send_blocked_reason": "",
    }


def _load_loop_state():
    _ensure_dirs()
    state = _default_loop_state()

    if LOOP_STATE_PATH.exists():
        try:
            loaded = json.loads(LOOP_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except Exception:
            pass

    return state


def _save_loop_state(state):
    _ensure_dirs()
    LOOP_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def _now():
    return datetime.now()


def _now_iso():
    return _now().isoformat(timespec="seconds")


def _parse_iso_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _format_send_blocked_message(state):
    reason = str(state.get("last_send_blocked_reason") or "ChatGPT Desktop rate limit cooldown is active.").strip()
    cooldown_until = str(state.get("cooldown_until") or "").strip()

    if cooldown_until:
        return f"STOP: ChatGPT Desktop send blocked: {reason} Cooldown until: {cooldown_until}."

    return f"STOP: ChatGPT Desktop send blocked: {reason}"


def mark_chatgpt_desktop_rate_limited(reason="", cooldown_minutes=30):
    state = _load_loop_state()
    now = _now()

    try:
        minutes = int(cooldown_minutes)
    except Exception:
        minutes = 30

    if minutes < 1:
        minutes = 30

    reason = str(reason or "Manual ChatGPT Desktop rate-limit guard.").strip()
    cooldown_until = now + timedelta(minutes=minutes)
    state.update({
        "rate_limited": True,
        "rate_limited_at": now.isoformat(timespec="seconds"),
        "cooldown_until": cooldown_until.isoformat(timespec="seconds"),
        "last_send_blocked_reason": reason,
        "last_action": "rate_limit_marked",
        "last_message": f"GPT Desktop send paused for {minutes} minutes: {reason}",
        "last_step_at": now.isoformat(timespec="seconds"),
    })
    _save_loop_state(state)
    report = _write_report("rate_limit_mark", state)

    try:
        set_value("chatgpt_desktop_rate_limited", True)
        set_value("chatgpt_desktop_cooldown_until", state["cooldown_until"])
    except Exception:
        pass

    return {
        "ok": True,
        "message": state["last_message"],
        "cooldown_minutes": minutes,
        "report_path": report,
        **state,
    }


def clear_chatgpt_desktop_rate_limit():
    state = _load_loop_state()
    now = _now_iso()
    state.update({
        "rate_limited": False,
        "rate_limited_at": "",
        "cooldown_until": "",
        "last_send_blocked_reason": "",
        "last_action": "rate_limit_cleared",
        "last_message": "GPT Desktop rate-limit guard cleared.",
        "last_step_at": now,
    })
    _save_loop_state(state)
    report = _write_report("rate_limit_clear", state)

    try:
        set_value("chatgpt_desktop_rate_limited", False)
        set_value("chatgpt_desktop_cooldown_until", "")
    except Exception:
        pass

    return {"ok": True, "message": state["last_message"], "report_path": report, **state}


def is_chatgpt_desktop_send_allowed():
    state = _load_loop_state()

    if not state.get("rate_limited"):
        return {"ok": True, "allowed": True, "message": "ChatGPT Desktop send allowed.", **state}

    cooldown_until = _parse_iso_datetime(state.get("cooldown_until"))

    if cooldown_until and cooldown_until <= _now():
        state.update({
            "rate_limited": False,
            "rate_limited_at": "",
            "cooldown_until": "",
            "last_send_blocked_reason": "",
            "last_action": "rate_limit_auto_cleared",
            "last_message": "GPT Desktop rate-limit cooldown expired; send allowed.",
            "last_step_at": _now_iso(),
        })
        _save_loop_state(state)
        return {"ok": True, "allowed": True, "message": state["last_message"], **state}

    message = _format_send_blocked_message(state)
    state.update({
        "last_action": "send_blocked_rate_limit",
        "last_message": message,
        "last_step_at": _now_iso(),
    })
    _save_loop_state(state)

    return {"ok": False, "allowed": False, "message": message, **state}


def _window_text(hwnd):
    try:
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()
    except Exception:
        return ""


def _window_class(hwnd):
    try:
        buffer = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, buffer, 256)
        return buffer.value.strip()
    except Exception:
        return ""


def _window_rect(hwnd):
    try:
        rect = ctypes.wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return {}

        return {
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
            "width": int(rect.right - rect.left),
            "height": int(rect.bottom - rect.top),
        }
    except Exception:
        return {}


def _window_info(hwnd):
    return {
        "hwnd": int(hwnd or 0),
        "title": _window_text(hwnd),
        "class": _window_class(hwnd),
        "rect": _window_rect(hwnd),
    }


def _is_chatgpt_window_info(info):
    title_lower = str(info.get("title") or "").lower()
    return "chatgpt" in title_lower or title_lower.startswith("grimoire")


def _find_chatgpt_windows():
    user32 = ctypes.windll.user32
    matches = []

    def callback(hwnd, _):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True

            info = _window_info(hwnd)

            if _is_chatgpt_window_info(info):
                matches.append(info)
        except Exception:
            pass

        return True

    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(callback)
    user32.EnumWindows(enum_proc, 0)
    return matches


def _open_clipboard(user32):
    for _ in range(8):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.05)
    return False


def _clipboard_get_windows():
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [ctypes.wintypes.HWND]
    user32.OpenClipboard.restype = ctypes.wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.wintypes.BOOL
    user32.IsClipboardFormatAvailable.argtypes = [ctypes.wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = ctypes.wintypes.BOOL
    user32.GetClipboardData.argtypes = [ctypes.wintypes.UINT]
    user32.GetClipboardData.restype = ctypes.wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [ctypes.wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = ctypes.wintypes.BOOL

    if not _open_clipboard(user32):
        raise RuntimeError("OpenClipboard failed")

    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return ""

        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            raise RuntimeError("GetClipboardData failed")

        locked = kernel32.GlobalLock(handle)
        if not locked:
            raise RuntimeError("GlobalLock failed")

        try:
            return ctypes.wstring_at(locked)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _clipboard_set_windows(text):
    text = str(text or "")
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [ctypes.wintypes.HWND]
    user32.OpenClipboard.restype = ctypes.wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = ctypes.wintypes.BOOL
    user32.SetClipboardData.argtypes = [ctypes.wintypes.UINT, ctypes.wintypes.HANDLE]
    user32.SetClipboardData.restype = ctypes.wintypes.HANDLE
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [ctypes.wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [ctypes.wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = ctypes.wintypes.BOOL
    kernel32.GlobalFree.argtypes = [ctypes.wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = ctypes.wintypes.HGLOBAL

    data = ctypes.create_unicode_buffer(text)
    byte_count = ctypes.sizeof(data)
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, byte_count)

    if not handle:
        raise RuntimeError("GlobalAlloc failed")

    locked = kernel32.GlobalLock(handle)
    if not locked:
        kernel32.GlobalFree(handle)
        raise RuntimeError("GlobalLock failed")

    try:
        ctypes.memmove(locked, data, byte_count)
    finally:
        kernel32.GlobalUnlock(handle)

    if not _open_clipboard(user32):
        kernel32.GlobalFree(handle)
        raise RuntimeError("OpenClipboard failed")

    try:
        if not user32.EmptyClipboard():
            raise RuntimeError("EmptyClipboard failed")

        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            raise RuntimeError("SetClipboardData failed")

        handle = None
    finally:
        user32.CloseClipboard()
        if handle:
            kernel32.GlobalFree(handle)


def _clipboard_set_tkinter(text):
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.clipboard_clear()
    root.clipboard_append(str(text or ""))
    root.update()
    root.destroy()


def _clipboard_get_tkinter():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        return root.clipboard_get()
    finally:
        root.destroy()


def _clipboard_set_powershell(text):
    command = (
        "[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false); "
        "$text = [Console]::In.ReadToEnd(); "
        "Set-Clipboard -Value $text"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        input=str(text or ""),
        text=True,
        encoding="utf-8",
        check=True,
        capture_output=True,
        timeout=10,
    )


def get_clipboard_text():
    errors = []

    for method_name, getter in [
        ("windows_api", _clipboard_get_windows),
        ("tkinter", _clipboard_get_tkinter),
    ]:
        try:
            return getter()
        except Exception as exc:
            errors.append(f"{method_name}: {exc}")

    command = "Get-Clipboard -Raw"
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            text=True,
            encoding="utf-8",
            check=True,
            capture_output=True,
            timeout=10,
        )
        return completed.stdout
    except Exception as exc:
        errors.append(f"powershell: {exc}")
        raise RuntimeError("; ".join(errors))


def _clipboard_set(text):
    expected = str(text or "")
    attempts = []

    for method_name, setter in [
        ("windows_api", _clipboard_set_windows),
        ("tkinter", _clipboard_set_tkinter),
        ("powershell", _clipboard_set_powershell),
    ]:
        try:
            setter(expected)
            actual = get_clipboard_text()

            if actual == expected:
                return {
                    "ok": True,
                    "method": method_name,
                    "chars": len(expected),
                    "verified": True,
                }

            attempts.append({
                "method": method_name,
                "ok": False,
                "error": f"verification mismatch: expected {len(expected)} chars, got {len(actual or '')}",
            })
        except Exception as exc:
            attempts.append({"method": method_name, "ok": False, "error": str(exc)})

    return {
        "ok": False,
        "message": "Clipboard write verification failed.",
        "chars": len(expected),
        "attempts": attempts,
    }


def clipboard_self_test():
    _ensure_dirs()
    test_text = f"LocalComet clipboard self-test {_stamp()}"
    result = _clipboard_set(test_text)
    actual = ""

    try:
        actual = get_clipboard_text()
    except Exception as exc:
        result.setdefault("attempts", []).append({"method": "get_clipboard_text", "ok": False, "error": str(exc)})

    ok = bool(result.get("ok")) and actual == test_text
    payload = {
        "ok": ok,
        "message": "Clipboard self-test OK." if ok else "Clipboard self-test failed.",
        "test_text": test_text,
        "clipboard_chars": len(actual or ""),
        "method": result.get("method", ""),
        "verified": actual == test_text,
        "write_result": result,
    }
    payload["report_path"] = _write_report("clipboard_self_test", payload)
    return payload


def _key_down(vk):
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)


def _key_up(vk):
    ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _press_ctrl_v():
    _key_down(VK_CONTROL)
    time.sleep(0.05)
    _key_down(VK_V)
    time.sleep(0.05)
    _key_up(VK_V)
    time.sleep(0.05)
    _key_up(VK_CONTROL)


def _press_enter():
    _key_down(VK_RETURN)
    time.sleep(0.05)
    _key_up(VK_RETURN)


def _click_screen_point(x, y):
    user32 = ctypes.windll.user32
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _looks_sensitive(prompt):
    text = str(prompt or "")
    patterns = [
        r"sk-[A-Za-z0-9_-]{20,}",
        r"sk-proj-[A-Za-z0-9_-]{20,}",
        r"(?i)(api[_ -]?key|password|passwd|token|secret)\s*[:=]\s*\S+",
        r"(?i)(пароль|токен|секретный ключ)\s*[:=]\s*\S+",
    ]
    return [pattern for pattern in patterns if re.search(pattern, text)]


def _write_report(action, payload):
    _ensure_dirs()
    path = REPORTS_DIR / f"chatgpt_desktop_bridge_{_stamp()}.md"
    lines = [
        "# ChatGPT Desktop Bridge Report",
        "",
        f"- action: {action}",
        f"- created_at: {datetime.now().isoformat(timespec='seconds')}",
    ]

    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        lines.append(f"- {key}: {value}")

    path.write_text("\n".join(lines), encoding="utf-8")

    try:
        set_value("last_chatgpt_desktop_bridge_report", str(path))
    except Exception:
        pass

    return str(path)


def chatgpt_desktop_status():
    _ensure_dirs()
    windows = _find_chatgpt_windows()
    result = {
        "available": bool(windows),
        "window_count": len(windows),
        "windows": windows,
        "prompt_path": str(PROMPT_PATH),
        "response_path": str(RESPONSE_PATH),
    }
    report = _write_report("status", result)
    result["report_path"] = report

    try:
        set_value("chatgpt_desktop_bridge: да", "да")
        set_value("last_chatgpt_desktop_available", bool(windows))
        set_value("last_chatgpt_desktop_window", windows[0]["title"] if windows else "")
    except Exception:
        pass

    return result


def prepare_chatgpt_desktop_prompt(goal, mode="patch"):
    _ensure_dirs()
    goal = str(goal or "").strip()
    mode = str(mode or "patch").strip() or "patch"

    prompt = (
        "# LocalComet -> ChatGPT Desktop Request\n\n"
        "You are Grimoire helping improve the local LocalComet / LocalAgent project.\n"
        "Give a focused, safe answer. Prefer one small implementable step.\n\n"
        "## Mode\n"
        f"{mode}\n\n"
        "## User Goal\n"
        f"{goal or 'нет'}\n\n"
        "## Required Response Contract\n"
        "- Decision\n"
        "- Risk level\n"
        "- Files allowed to touch\n"
        "- Files forbidden\n"
        "- Exact operations\n"
        "- Tests/checks\n"
        "- Stop conditions\n\n"
        "Do not request changes to config/router/planner/executor/apply/validate/browser bridge unless explicitly required.\n"
    )

    PROMPT_PATH.write_text(prompt, encoding="utf-8")

    try:
        set_value("last_chatgpt_desktop_prompt", str(PROMPT_PATH))
        set_value("last_chatgpt_desktop_goal", goal)
    except Exception:
        pass

    return prompt


def copy_prompt_to_clipboard(prompt):
    prompt = str(prompt or "")
    sensitive = _looks_sensitive(prompt)

    if sensitive:
        return {
            "ok": False,
            "message": "STOP: prompt похож на содержащий секреты. Clipboard не изменен.",
            "sensitive_markers": sensitive,
        }

    clipboard_result = _clipboard_set(prompt)

    if not clipboard_result.get("ok"):
        report = _write_report("copy_prompt", {"prompt_chars": len(prompt), **clipboard_result})
        return {
            "ok": False,
            "message": "STOP: prompt не скопирован в clipboard: проверка записи не прошла.",
            "prompt_chars": len(prompt),
            "clipboard_result": clipboard_result,
            "report_path": report,
        }

    report = _write_report("copy_prompt", {"prompt_chars": len(prompt), **clipboard_result})
    return {
        "ok": True,
        "message": "Prompt скопирован в clipboard.",
        "prompt_chars": len(prompt),
        "clipboard_method": clipboard_result.get("method", ""),
        "verified": True,
        "report_path": report,
    }


def focus_chatgpt_desktop_window():
    windows = _find_chatgpt_windows()

    if not windows:
        report = _write_report("focus", {"ok": False, "message": "ChatGPT Desktop window not found"})
        return {"ok": False, "message": "Окно ChatGPT Desktop не найдено.", "windows": [], "report_path": report}

    window = windows[0]
    hwnd = int(window["hwnd"])
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 5)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.25)
    foreground = verify_chatgpt_desktop_foreground(write_report=False)
    payload = {
        "ok": bool(foreground.get("ok")),
        "window": window,
        "foreground": foreground,
    }

    if foreground.get("ok"):
        payload["message"] = "Окно ChatGPT Desktop сфокусировано."
    else:
        payload["message"] = "Окно ChatGPT Desktop найдено, но foreground-проверка не подтвердила фокус."

    report = _write_report("focus", payload)
    payload["report_path"] = report
    return payload


def get_foreground_window_info():
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return {"hwnd": 0, "title": "", "class": "", "rect": {}}
        return _window_info(hwnd)
    except Exception:
        return {"hwnd": 0, "title": "", "class": "", "rect": {}}


def verify_chatgpt_desktop_foreground(write_report=True):
    info = get_foreground_window_info()
    ok = _is_chatgpt_window_info(info)
    payload = {
        "ok": ok,
        "message": "ChatGPT Desktop is foreground." if ok else "Foreground window is not ChatGPT Desktop.",
        "foreground": info,
    }

    if write_report:
        payload["report_path"] = _write_report("verify_foreground", payload)

    return payload


def _safe_input_click_point(rect):
    width = int(rect.get("width") or 0)
    height = int(rect.get("height") or 0)
    left = int(rect.get("left") or 0)
    top = int(rect.get("top") or 0)
    right = int(rect.get("right") or 0)
    bottom = int(rect.get("bottom") or 0)

    if width <= 200 or height <= 200:
        return None

    x = left + int(width * 0.50)
    y = top + int(height * 0.89)
    x = min(max(x, left + 80), right - 80)
    y = min(max(y, top + 160), bottom - 45)
    return {"x": int(x), "y": int(y)}


def focus_chatgpt_desktop_input_box(dry_run=True):
    windows = _find_chatgpt_windows()

    if not windows:
        payload = {
            "ok": False,
            "dry_run": bool(dry_run),
            "message": "Окно ChatGPT Desktop не найдено.",
            "windows": [],
        }
        payload["report_path"] = _write_report("focus_input", payload)
        return payload

    window = windows[0]
    rect = window.get("rect") or {}
    point = _safe_input_click_point(rect)

    payload = {
        "dry_run": bool(dry_run),
        "window": window,
        "click_point": point,
    }

    if not point:
        payload["ok"] = False
        payload["message"] = "Не удалось рассчитать безопасную точку клика внутри окна ChatGPT Desktop."
        payload["report_path"] = _write_report("focus_input", payload)
        return payload

    focus_result = focus_chatgpt_desktop_window()
    payload["focus_result"] = focus_result

    if not focus_result.get("ok"):
        payload["ok"] = False
        payload["message"] = focus_result.get("message", "Окно ChatGPT Desktop не сфокусировано.")
        payload["report_path"] = _write_report("focus_input", payload)
        return payload

    if dry_run:
        payload["ok"] = True
        payload["message"] = "DRY RUN: input focus point calculated; click not performed."
        payload["report_path"] = _write_report("focus_input", payload)
        return payload

    _click_screen_point(point["x"], point["y"])
    time.sleep(0.25)
    foreground = verify_chatgpt_desktop_foreground(write_report=False)
    payload["foreground"] = foreground
    payload["ok"] = bool(foreground.get("ok"))
    payload["message"] = (
        "Поле ввода ChatGPT Desktop должно быть сфокусировано."
        if payload["ok"]
        else "Клик выполнен, но foreground-проверка не подтвердила ChatGPT Desktop."
    )
    payload["report_path"] = _write_report("focus_input", payload)
    return payload


def paste_prompt_after_input_focus(prompt=None, send=False, dry_run=True):
    _ensure_dirs()
    prompt = PROMPT_PATH.read_text(encoding="utf-8") if prompt is None and PROMPT_PATH.exists() else str(prompt or "")
    sensitive = _looks_sensitive(prompt)

    payload = {
        "dry_run": bool(dry_run),
        "send": bool(send),
        "focused_path": True,
        "prompt_chars": len(prompt),
        "sensitive_markers": sensitive,
    }

    if sensitive:
        payload["ok"] = False
        payload["message"] = "STOP: prompt похож на содержащий секреты."
        payload["report_path"] = _write_report("paste_prompt_focused", payload)
        return payload

    if send and not dry_run:
        send_allowed = is_chatgpt_desktop_send_allowed()
        payload["send_allowed"] = bool(send_allowed.get("allowed"))

        if not send_allowed.get("allowed"):
            payload["ok"] = False
            payload["message"] = send_allowed.get("message", "STOP: ChatGPT Desktop send blocked.")
            payload["rate_limited"] = bool(send_allowed.get("rate_limited"))
            payload["cooldown_until"] = send_allowed.get("cooldown_until", "")
            payload["last_send_blocked_reason"] = send_allowed.get("last_send_blocked_reason", "")
            payload["report_path"] = _write_report("paste_prompt_focused", payload)
            return payload

    status = chatgpt_desktop_status()
    payload["available"] = status.get("available")
    payload["window_count"] = status.get("window_count")

    if not status.get("available"):
        payload["ok"] = False
        payload["message"] = "Окно ChatGPT Desktop не найдено."
        payload["report_path"] = _write_report("paste_prompt_focused", payload)
        return payload

    focus_preview = focus_chatgpt_desktop_input_box(dry_run=True)
    payload["focus_preview"] = focus_preview

    if dry_run:
        payload["ok"] = bool(focus_preview.get("ok"))
        payload["message"] = (
            "DRY RUN: prompt готов, окно найдено, input-point рассчитан; paste/send не выполнялись."
            if payload["ok"]
            else focus_preview.get("message", "DRY RUN: input focus check failed.")
        )
        payload["report_path"] = _write_report("paste_prompt_focused", payload)
        return payload

    copy_result = copy_prompt_to_clipboard(prompt)
    payload["copy_result"] = copy_result

    if not copy_result.get("ok"):
        payload["ok"] = False
        payload["message"] = copy_result.get("message", "STOP: prompt не скопирован в clipboard.")
        payload["report_path"] = _write_report("paste_prompt_focused", payload)
        return payload

    focus_input_result = focus_chatgpt_desktop_input_box(dry_run=False)
    payload["focus_input_result"] = focus_input_result

    if not focus_input_result.get("ok"):
        payload["ok"] = False
        payload["message"] = focus_input_result.get("message", "STOP: поле ввода ChatGPT Desktop не сфокусировано.")
        payload["report_path"] = _write_report("paste_prompt_focused", payload)
        return payload

    _press_ctrl_v()
    time.sleep(0.35)

    if send:
        time.sleep(0.65)
        _press_enter()

    payload["ok"] = True
    payload["message"] = "Prompt вставлен в ChatGPT Desktop через focused path." + (" Enter отправлен." if send else " Enter не отправлялся.")
    payload["report_path"] = _write_report("paste_prompt_focused", payload)

    try:
        set_value("last_chatgpt_desktop_paste_result", payload["message"])
    except Exception:
        pass

    return payload


def paste_prompt_to_chatgpt_desktop(prompt=None, send=False, dry_run=True):
    return paste_prompt_after_input_focus(prompt=prompt, send=send, dry_run=dry_run)


def verify_chatgpt_desktop_send_state(before_clipboard="", after_clipboard="", send_result=None):
    send_result = send_result if isinstance(send_result, dict) else {}
    foreground = verify_chatgpt_desktop_foreground(write_report=False)
    send_requested = bool(send_result.get("send"))
    dry_run = bool(send_result.get("dry_run"))
    paste_ok = bool(send_result.get("ok"))
    rate_limited = bool(send_result.get("rate_limited"))
    send_allowed = send_result.get("send_allowed", True)
    clipboard_still_prompt = bool(before_clipboard) and str(after_clipboard or "") == str(before_clipboard or "")

    evidence = {
        "foreground_ok": bool(foreground.get("ok")),
        "paste_path_ok": paste_ok,
        "send_requested": send_requested,
        "dry_run": dry_run,
        "rate_limit_not_active": not rate_limited and send_allowed is not False,
        "clipboard_still_equals_prompt": clipboard_still_prompt,
        "message": send_result.get("message", ""),
    }

    likely_sent = (
        send_requested
        and not dry_run
        and paste_ok
        and evidence["foreground_ok"]
        and evidence["rate_limit_not_active"]
        and not clipboard_still_prompt
    )
    needs_manual_check = send_requested and not likely_sent

    if likely_sent:
        message = "ChatGPT Desktop send likely succeeded."
    elif not send_requested:
        message = "Send was not requested; prompt may only be prepared or pasted."
    elif clipboard_still_prompt:
        message = "Not enough evidence: clipboard still equals the prompt; manual check needed."
    else:
        message = "Not enough evidence that ChatGPT Desktop sent the prompt; manual check needed."

    return {
        "ok": bool(paste_ok) and (likely_sent or not send_requested),
        "likely_sent": likely_sent,
        "message": message,
        "evidence": evidence,
        "needs_manual_check": needs_manual_check,
    }


def save_clipboard_response_from_chatgpt_desktop():
    _ensure_dirs()
    text = get_clipboard_text()

    if not str(text or "").strip():
        report = _write_report("capture_response", {"ok": False, "message": "Clipboard пустой"})
        return {"ok": False, "message": "Clipboard пустой.", "report_path": report}

    RESPONSE_PATH.write_text(text, encoding="utf-8")
    report = _write_report("capture_response", {"ok": True, "response_chars": len(text), "response_path": str(RESPONSE_PATH)})

    try:
        set_value("last_chatgpt_desktop_response", str(RESPONSE_PATH))
    except Exception:
        pass

    return {"ok": True, "message": "Ответ из clipboard сохранен.", "response_path": str(RESPONSE_PATH), "response_chars": len(text), "report_path": report}


def chatgpt_desktop_loop_status():
    send_allowed = is_chatgpt_desktop_send_allowed()
    state = _load_loop_state()
    state["send_allowed"] = bool(send_allowed.get("allowed"))
    state["send_blocked_message"] = "" if send_allowed.get("allowed") else send_allowed.get("message", "")
    state["state_path"] = str(LOOP_STATE_PATH)
    state["prompt_path"] = str(PROMPT_PATH)
    state["response_path"] = str(RESPONSE_PATH)
    return state


def start_chatgpt_desktop_loop(goal="", mode="grimoire", send=True):
    state = _load_loop_state()
    now = datetime.now().isoformat(timespec="seconds")
    state.update({
        "enabled": True,
        "started_at": now,
        "stopped_at": "",
        "goal": str(goal or state.get("goal") or "Предложи следующий безопасный шаг для LocalComet.").strip(),
        "mode": str(mode or "grimoire").strip() or "grimoire",
        "send": bool(send),
        "prompt_sent": False,
        "last_action": "start",
        "last_message": "GPT Desktop loop включен.",
        "last_step_at": now,
        "interval_seconds": int(state.get("interval_seconds") or DEFAULT_LOOP_INTERVAL_SECONDS),
    })
    _save_loop_state(state)
    report = _write_report("loop_start", state)
    state["report_path"] = report

    try:
        set_value("chatgpt_desktop_loop_enabled", True)
        set_value("chatgpt_desktop_loop_goal", state["goal"])
    except Exception:
        pass

    return {"ok": True, "message": "GPT Desktop loop включен.", **state}


def stop_chatgpt_desktop_loop():
    state = _load_loop_state()
    now = datetime.now().isoformat(timespec="seconds")
    state.update({
        "enabled": False,
        "stopped_at": now,
        "last_action": "stop",
        "last_message": "GPT Desktop loop выключен.",
        "last_step_at": now,
    })
    _save_loop_state(state)
    report = _write_report("loop_stop", state)
    state["report_path"] = report

    try:
        set_value("chatgpt_desktop_loop_enabled", False)
    except Exception:
        pass

    return {"ok": True, "message": "GPT Desktop loop выключен.", **state}


def chatgpt_desktop_loop_step():
    state = _load_loop_state()
    now = datetime.now().isoformat(timespec="seconds")

    if not state.get("enabled"):
        return {"ok": False, "message": "GPT Desktop loop выключен.", **state}

    send_allowed = is_chatgpt_desktop_send_allowed()
    state = _load_loop_state()

    if not send_allowed.get("allowed"):
        message = send_allowed.get("message", "STOP: GPT Desktop loop ждет окончания rate-limit cooldown.")
        state.update({
            "last_action": "wait_rate_limit",
            "last_message": message,
            "last_step_at": now,
        })
        _save_loop_state(state)
        return {"ok": True, "message": message, "step": "wait_rate_limit", "send_allowed": False, **state}

    if not state.get("prompt_sent"):
        prompt = prepare_chatgpt_desktop_prompt(state.get("goal"), mode=state.get("mode") or "grimoire")
        result = paste_prompt_to_chatgpt_desktop(prompt, send=bool(state.get("send")), dry_run=False)
        state.update({
            "prompt_sent": bool(result.get("ok")),
            "last_action": "send_prompt",
            "last_message": result.get("message", ""),
            "last_step_at": now,
        })
        _save_loop_state(state)
        return {"ok": bool(result.get("ok")), "message": result.get("message", ""), "step": "send_prompt", "result": result, **state}

    clipboard_text = get_clipboard_text()
    prompt_text = PROMPT_PATH.read_text(encoding="utf-8") if PROMPT_PATH.exists() else ""

    if not str(clipboard_text or "").strip():
        message = "Ответ еще не найден: clipboard пустой."
        state.update({"last_action": "wait_response", "last_message": message, "last_step_at": now})
        _save_loop_state(state)
        return {"ok": True, "message": message, "step": "wait_response", **state}

    if clipboard_text == prompt_text or str(clipboard_text).lstrip().startswith("# LocalComet -> ChatGPT Desktop Request"):
        message = "Ответ еще не найден: в clipboard пока находится отправленный prompt."
        state.update({"last_action": "wait_response", "last_message": message, "last_step_at": now})
        _save_loop_state(state)
        return {"ok": True, "message": message, "step": "wait_response", **state}

    result = save_clipboard_response_from_chatgpt_desktop()
    state.update({
        "last_action": "capture_response",
        "last_message": result.get("message", ""),
        "last_step_at": now,
    })
    _save_loop_state(state)
    return {"ok": bool(result.get("ok")), "message": result.get("message", ""), "step": "capture_response", "result": result, **state}


def latest_chatgpt_desktop_bridge_report():
    if not REPORTS_DIR.exists():
        return ""

    reports = sorted(REPORTS_DIR.glob("chatgpt_desktop_bridge_*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(reports[0]) if reports else ""
````

