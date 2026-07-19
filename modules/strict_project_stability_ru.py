from __future__ import annotations

import ast
import hashlib
import json
import py_compile
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_PATH = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_PATH / "Projects" / "Reports" / "strict_project_stability"
BASELINE_PATH = REPORT_DIR / "strict_project_inventory_baseline.json"

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
}

CRITICAL_FILES = [
    "LocalComet_Control_Panel.py",
    "modules/premium_task_panel_ru.py",
    "modules/strict_project_stability_ru.py",
    "modules/project_one_command_check_ru.py",
]

PROJECT_COMMANDS = {
    "проверь проект",
    "проверить проект",
    "полная проверка проекта",
    "автопроверка проекта",
    "pc project check",
    "pc verify project",
    "pc verify all",
    "pc verify features",
}


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_PATH)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _is_skipped(path: Path) -> bool:
    return bool(set(path.parts).intersection(BLOCKED_DIRS))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
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


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _analyze_python_file(path: Path) -> dict[str, Any]:
    rel = _safe_relative(path)
    item: dict[str, Any] = {
        "path": rel,
        "sha256": "",
        "parse_ok": False,
        "parse_error": "",
        "functions": [],
        "classes": [],
        "imports": [],
        "has_dispatch": False,
        "has_status": False,
        "has_report": False,
        "commands": [],
    }

    try:
        text = _read_text(path)
        item["sha256"] = _sha256(path)
        tree = ast.parse(text, filename=rel)
    except Exception as exc:
        item["parse_error"] = str(exc)
        return item

    item["parse_ok"] = True

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

    item["functions"] = sorted(set(functions))
    item["classes"] = sorted(set(classes))
    item["imports"] = sorted(set(imports))
    item["has_dispatch"] = "dispatch" in item["functions"]
    item["has_status"] = "status" in item["functions"]
    item["has_report"] = "report" in item["functions"]

    lowered = text.lower().replace("ё", "е")
    for marker in [
        "проверь проект",
        "pc project check",
        "pc verify",
        "pc swiss",
        "pc core",
        "pc exec",
        "pc screen",
        "pc ui",
        "pc desktop",
        "pc agentos",
        "pc agents",
        "новый интерфейс",
    ]:
        if marker in lowered:
            item["commands"].append(marker)
    item["commands"] = sorted(set(item["commands"]))
    return item


def build_inventory() -> dict[str, Any]:
    files = [_analyze_python_file(path) for path in _iter_python_files()]
    return {
        "ok": True,
        "mode": "strict_project_inventory",
        "generated_at": _now(),
        "root": str(ROOT_PATH),
        "python_file_count": len(files),
        "function_count": sum(len(item.get("functions", [])) for item in files),
        "class_count": sum(len(item.get("classes", [])) for item in files),
        "parse_error_count": sum(1 for item in files if not item.get("parse_ok")),
        "command_module_count": sum(1 for item in files if item.get("has_dispatch") or item.get("commands")),
        "files": files,
    }


def _load_baseline() -> dict[str, Any]:
    if not BASELINE_PATH.exists():
        return {}
    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_baseline(inventory: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")


def _file_map(inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("path")): item
        for item in inventory.get("files", [])
        if item.get("path")
    }


def _diff_inventory(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    current_files = _file_map(current)
    old_files = _file_map(baseline)

    added_files: list[str] = []
    changed_files: list[str] = []
    removed_files: list[str] = []
    new_functions: list[str] = []
    changed_functions: list[str] = []

    for rel, item in current_files.items():
        old = old_files.get(rel)
        if old is None:
            added_files.append(rel)
            for function_name in item.get("functions", []):
                new_functions.append(f"{rel}:{function_name}")
            continue

        old_hash = old.get("sha256")
        new_hash = item.get("sha256")
        if old_hash != new_hash:
            changed_files.append(rel)

        old_functions = set(old.get("functions", []))
        new_function_set = set(item.get("functions", []))

        for function_name in sorted(new_function_set - old_functions):
            new_functions.append(f"{rel}:{function_name}")

        if old_hash != new_hash:
            for function_name in sorted(new_function_set.intersection(old_functions)):
                changed_functions.append(f"{rel}:{function_name}")

    for rel in old_files:
        if rel not in current_files:
            removed_files.append(rel)

    return {
        "added_files": sorted(added_files),
        "changed_files": sorted(changed_files),
        "removed_files": sorted(removed_files),
        "new_functions": sorted(new_functions),
        "changed_functions": sorted(changed_functions),
    }


def _compile_files(paths: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for rel in paths:
        path = ROOT_PATH / rel
        item: dict[str, Any] = {
            "path": rel,
            "ok": False,
            "error": "",
        }

        if not path.exists():
            item["error"] = "file not found"
            results.append(item)
            continue

        try:
            py_compile.compile(str(path), doraise=True)
            item["ok"] = True
        except Exception as exc:
            item["error"] = str(exc)

        results.append(item)

    return results


def _check_critical_files() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for rel in CRITICAL_FILES:
        path = ROOT_PATH / rel
        checks.append({
            "name": f"critical file: {rel}",
            "ok": path.exists(),
            "path": rel,
            "error": "" if path.exists() else "missing",
        })
    return checks


def _check_control_panel_route() -> list[dict[str, Any]]:
    path = ROOT_PATH / "LocalComet_Control_Panel.py"
    if not path.exists():
        return [{"name": "control panel route", "ok": False, "error": "LocalComet_Control_Panel.py missing"}]

    text = _read_text(path)
    checks = [
        {
            "name": "strict route helper",
            "ok": "def _is_strict_project_stability_ru_command(command):" in text,
            "error": "" if "def _is_strict_project_stability_ru_command(command):" in text else "helper missing",
        },
        {
            "name": "strict route dispatch",
            "ok": 'route_name = "strict_project_stability_ru"' in text,
            "error": "" if 'route_name = "strict_project_stability_ru"' in text else "route missing",
        },
        {
            "name": "single task panel auto-open",
            "ok": text.count("from modules.premium_task_panel_ru import auto_open_task_panel_if_enabled") == 1,
            "error": f"count={text.count('from modules.premium_task_panel_ru import auto_open_task_panel_if_enabled')}",
        },
        {
            "name": "version marker",
            "ok": "LOCALCOMET_VERSION =" in text and "LOCALCOMET_VERSION_LABEL =" in text and "LocalComet " in text,
            "error": "" if "LOCALCOMET_VERSION =" in text and "LOCALCOMET_VERSION_LABEL =" in text and "LocalComet " in text else "version marker missing",
        },
    ]
    return checks


def _check_task_panel_ui() -> list[dict[str, Any]]:
    path = ROOT_PATH / "modules" / "premium_task_panel_ru.py"
    if not path.exists():
        return [{"name": "task panel ui", "ok": False, "error": "premium_task_panel_ru.py missing"}]

    text = _read_text(path)
    checks = [
        {
            "name": "verification tab",
            "ok": '"Проверка", "verification"' in text or "Проверка" in text and "_render_verification_page" in text,
            "error": "verification tab missing",
        },
        {
            "name": "single check button",
            "ok": "Проверить проект" in text and "_run_project_check_from_tab" in text,
            "error": "single project check button missing",
        },
        {
            "name": "chat command mapping",
            "ok": "проверь проект" in text and "выполни: проверь проект" in text,
            "error": "Russian project check guidance missing",
        },
    ]
    return checks


def _check_command_contracts(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for item in inventory.get("files", []):
        rel = str(item.get("path", ""))
        if not rel.startswith("modules/"):
            continue
        if not item.get("has_dispatch") and not item.get("commands"):
            continue

        missing = []
        if not item.get("has_status"):
            missing.append("status")
        if not item.get("has_report"):
            missing.append("report")

        checks.append({
            "name": f"command contract: {rel}",
            "path": rel,
            "ok": not missing,
            "missing": missing,
            "warning": bool(missing),
            "error": "" if not missing else "missing " + ", ".join(missing),
        })
    return checks


def _safe_smoke_imports() -> list[dict[str, Any]]:
    imports = [
        "modules.strict_project_stability_ru",
        "modules.premium_task_panel_ru",
        "modules.project_one_command_check_ru",
    ]
    results: list[dict[str, Any]] = []
    for module_name in imports:
        item = {"name": f"safe import: {module_name}", "ok": False, "error": ""}
        try:
            __import__(module_name)
            item["ok"] = True
        except Exception as exc:
            item["error"] = str(exc)
        results.append(item)
    return results


def _check_safety_markers() -> list[dict[str, Any]]:
    files = [
        ROOT_PATH / "modules" / "pc_codex_core.py",
        ROOT_PATH / "modules" / "pc_codex_executor.py",
        ROOT_PATH / "modules" / "pc_desktop_primitives.py",
        ROOT_PATH / "modules" / "swiss_knife_skill_launcher.py",
    ]
    required_markers = ["password", "token", "delete", "rm", "powershell"]
    checks: list[dict[str, Any]] = []
    for path in files:
        if not path.exists():
            continue
        text = _read_text(path).lower()
        present = [marker for marker in required_markers if marker in text]
        checks.append({
            "name": f"safety markers: {_safe_relative(path)}",
            "ok": len(present) >= 2,
            "present": present,
            "error": "" if len(present) >= 2 else "safety marker coverage is weak",
        })
    return checks


def _write_reports(result: dict[str, Any]) -> dict[str, str]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"strict_project_stability_{stamp}.json"
    md_path = REPORT_DIR / f"strict_project_stability_{stamp}.md"

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Strict Project Stability RU",
        "",
        f"- generated_at: {result.get('generated_at')}",
        f"- ok: {result.get('ok')}",
        f"- score: {result.get('score')}",
        "",
        "## Summary",
        "",
    ]

    for key, value in result.get("summary", {}).items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Checks", ""])
    for group_name, group in result.get("check_groups", {}).items():
        lines.append(f"### {group_name}")
        for item in group:
            mark = "OK" if item.get("ok") else "FAIL"
            lines.append(f"- [{mark}] {item.get('name') or item.get('path')}")
            if item.get("error"):
                lines.append(f"  - error: {item.get('error')}")
        lines.append("")

    diff = result.get("diff", {})
    lines.extend(["", "## Diff", ""])
    for key in ("added_files", "changed_files", "removed_files", "new_functions", "changed_functions"):
        values = diff.get(key, [])
        lines.append(f"### {key}: {len(values)}")
        for value in values[:80]:
            lines.append(f"- {value}")
        if len(values) > 80:
            lines.append(f"- ... ещё {len(values) - 80}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"report": str(md_path), "json": str(json_path)}


def run_strict_project_check(update_baseline: bool = True) -> dict[str, Any]:
    inventory = build_inventory()
    baseline = _load_baseline()
    first_run = not bool(baseline)
    diff = _diff_inventory(inventory, baseline) if baseline else {
        "added_files": [],
        "changed_files": [],
        "removed_files": [],
        "new_functions": [],
        "changed_functions": [],
    }

    compile_targets = [item.get("path") for item in inventory.get("files", []) if item.get("path")]
    compile_checks = _compile_files(compile_targets)

    check_groups = {
        "critical_files": _check_critical_files(),
        "control_panel_route": _check_control_panel_route(),
        "task_panel_ui": _check_task_panel_ui(),
        "python_compile_all": compile_checks,
        "command_contracts": _check_command_contracts(inventory),
        "safe_smoke_imports": _safe_smoke_imports(),
        "safety_markers": _check_safety_markers(),
    }

    strict_groups = {
        "critical_files",
        "control_panel_route",
        "task_panel_ui",
        "safe_smoke_imports",
    }

    hard_failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    total_checks = 0
    passed_checks = 0

    for group_name, checks in check_groups.items():
        for item in checks:
            total_checks += 1
            if item.get("ok"):
                passed_checks += 1
                continue
            if group_name in strict_groups:
                hard_failures.append(item)
            else:
                warnings.append(item)

    parse_errors = [item for item in inventory.get("files", []) if not item.get("parse_ok")]
    for item in parse_errors:
        rel = str(item.get("path", ""))
        parse_issue = {
            "name": f"parse: {item.get('path')}",
            "path": rel,
            "ok": False,
            "error": item.get("parse_error"),
        }
        if rel == "LocalComet_Control_Panel.py" or rel.startswith("modules/") or rel.startswith("core/"):
            hard_failures.append(parse_issue)
        else:
            warnings.append(parse_issue)

    ok = not hard_failures
    result: dict[str, Any] = {
        "ok": ok,
        "mode": "strict_project_stability_check",
        "generated_at": _now(),
        "score": f"{passed_checks}/{total_checks}",
        "summary": {
            "python_files": inventory.get("python_file_count"),
            "functions": inventory.get("function_count"),
            "classes": inventory.get("class_count"),
            "command_modules": inventory.get("command_module_count"),
            "first_run": first_run,
            "parse_errors": len(parse_errors),
            "compile_failures": sum(1 for item in compile_checks if not item.get("ok")),
            "hard_failures": len(hard_failures),
            "warnings": len(warnings),
            "ok_criteria": "no hard failures; warnings are reported but do not block installation",
            "added_files": len(diff.get("added_files", [])),
            "changed_files": len(diff.get("changed_files", [])),
            "new_functions": len(diff.get("new_functions", [])),
            "changed_functions": len(diff.get("changed_functions", [])),
        },
        "diff": diff,
        "check_groups": check_groups,
        "hard_failures": hard_failures[:50],
        "warnings": warnings[:50],
    }

    paths = _write_reports(result)
    result.update(paths)

    if update_baseline and ok:
        _save_baseline(inventory)
        result["baseline_updated"] = True
    else:
        result["baseline_updated"] = False

    return result


def status() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "strict_project_stability_status",
        "generated_at": _now(),
        "main_command": "проверь проект",
        "button": "Проверка -> Проверить проект",
        "baseline_exists": BASELINE_PATH.exists(),
        "baseline_path": str(BASELINE_PATH),
        "checks": [
            "all Python AST parse",
            "all Python py_compile",
            "critical files",
            "control panel route",
            "verification tab UI",
            "safe smoke imports",
            "command contracts",
            "safety markers",
            "inventory diff",
            "report generation",
        ],
    }


def report() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "strict_project_stability_report",
        "generated_at": _now(),
        "latest_reports": [str(path) for path in sorted(REPORT_DIR.glob("strict_project_stability_*.md"), reverse=True)[:10]],
        "status": status(),
    }


def dispatch(command: str) -> dict[str, Any]:
    text = str(command or "").strip().lower().replace("ё", "е")
    if text in PROJECT_COMMANDS:
        return run_strict_project_check(update_baseline=True)
    if text in {"pc project status", "pc verify status", "статус проверки проекта"}:
        return status()
    if text in {"pc project report", "pc verify report", "отчет проверки проекта", "отчёт проверки проекта"}:
        return report()
    return {
        "ok": False,
        "mode": "strict_project_stability_unknown",
        "command": command,
        "hint": "Используй вкладку «Проверка» или команду: проверь проект",
    }


def is_strict_project_check_command(command: str) -> bool:
    text = str(command or "").strip().lower().replace("ё", "е")
    return text in PROJECT_COMMANDS or text in {
        "pc project status",
        "pc verify status",
        "статус проверки проекта",
        "pc project report",
        "pc verify report",
        "отчет проверки проекта",
        "отчёт проверки проекта",
    }

# Strict Project Stability dynamic version marker repair: v6.47f

# Strict Project Stability dynamic version marker repair: v6.47g

# Strict Project Stability dynamic version marker repair: v6.47h

# Strict Project Stability dynamic version marker repair: v6.47i
