from __future__ import annotations

import ast
import hashlib
import importlib
import json
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from time import perf_counter


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
FEATURE_ROOT = PROJECTS_DIR / "FeatureVerification"
REPORTS_FEATURE_DIR = REPORTS_DIR / "feature_verification"
INVENTORY_PATH = FEATURE_ROOT / "feature_inventory.json"
LAST_OK_INVENTORY_PATH = FEATURE_ROOT / "feature_inventory_last_ok.json"

SCAN_ROOTS = [
    "agents",
    "core",
    "modules",
    "next",
]

ALWAYS_INCLUDE = [
    "LocalComet_Control_Panel.py",
]

SKIP_DIR_PARTS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

SAFE_SMOKE_MODULES = [
    "modules.feature_verification",
    "modules.russian_command_context",
    "modules.premium_task_panel_ru",
    "modules.auto_verification",
    "modules.project_health",
    "modules.regression_commands",
    "modules.patch_registry",
    "core.project_context",
]

COMMAND_KEYWORDS = (
    "dispatch",
    "status",
    "report",
    "command",
    "commands",
    "is_",
    "pc ",
)


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    FEATURE_ROOT.mkdir(parents=True, exist_ok=True)
    REPORTS_FEATURE_DIR.mkdir(parents=True, exist_ok=True)


def _short(value, limit=2600):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[обрезано]"


def _rel(path):
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT_DIR.resolve()).as_posix()
    except Exception:
        return path.as_posix().replace("\\", "/")


def _is_skipped(path):
    parts = {part for part in Path(path).parts}
    return bool(parts & SKIP_DIR_PARTS)


def _python_files():
    files = []

    for relative in ALWAYS_INCLUDE:
        path = ROOT_DIR / relative
        if path.exists() and path.is_file():
            files.append(path)

    for root_name in SCAN_ROOTS:
        root = ROOT_DIR / root_name
        if not root.exists() or not root.is_dir():
            continue

        for path in root.rglob("*.py"):
            if path.is_file() and not _is_skipped(path):
                files.append(path)

    seen = set()
    result = []
    for path in files:
        normalized = _rel(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(path)

    return result


def _read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _file_hash(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _node_name(node):
    return getattr(node, "name", "")


def _literal_string(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _extract_string_literals(tree, limit=120):
    values = []
    for node in ast.walk(tree):
        value = _literal_string(node)
        if value:
            stripped = value.strip()
            if stripped and len(stripped) <= 160:
                values.append(stripped)
        if len(values) >= limit:
            break
    return values


def _extract_symbols(path):
    text = _read_text(path)
    rel = _rel(path)
    payload = {
        "path": rel,
        "hash": _file_hash(text),
        "line_count": len(text.splitlines()),
        "functions": [],
        "async_functions": [],
        "classes": [],
        "command_functions": [],
        "dispatch_functions": [],
        "status_functions": [],
        "report_functions": [],
        "command_literals": [],
        "parse_ok": True,
        "parse_error": "",
    }

    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        payload["parse_ok"] = False
        payload["parse_error"] = str(exc)
        return payload

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            payload["functions"].append(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            payload["async_functions"].append(node.name)
        elif isinstance(node, ast.ClassDef):
            payload["classes"].append(node.name)

    all_functions = set(payload["functions"]) | set(payload["async_functions"])

    for name in sorted(all_functions):
        lower = name.lower()
        if lower == "dispatch":
            payload["dispatch_functions"].append(name)
        if lower == "status" or lower.endswith("_status"):
            payload["status_functions"].append(name)
        if lower == "report" or lower.endswith("_report"):
            payload["report_functions"].append(name)
        if lower.startswith("is_") and lower.endswith("_command"):
            payload["command_functions"].append(name)

    literals = _extract_string_literals(tree)
    payload["command_literals"] = [
        item
        for item in literals
        if any(keyword in item.lower().replace("ё", "е") for keyword in COMMAND_KEYWORDS)
    ][:80]

    return payload


def scan_feature_inventory():
    files = [_extract_symbols(path) for path in _python_files()]
    files.sort(key=lambda item: item["path"])

    totals = {
        "files": len(files),
        "functions": sum(len(item.get("functions", [])) for item in files),
        "async_functions": sum(len(item.get("async_functions", [])) for item in files),
        "classes": sum(len(item.get("classes", [])) for item in files),
        "command_modules": sum(1 for item in files if item.get("command_functions") or item.get("dispatch_functions")),
        "parse_errors": sum(1 for item in files if not item.get("parse_ok")),
    }

    return {
        "ok": totals["parse_errors"] == 0,
        "mode": "feature_inventory",
        "generated_at": _now(),
        "root": str(ROOT_DIR),
        "totals": totals,
        "files": files,
    }


def _load_inventory(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _save_inventory(data, path):
    _ensure_dirs()
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _symbols_for(item):
    return {
        "functions": set(item.get("functions", [])),
        "async_functions": set(item.get("async_functions", [])),
        "classes": set(item.get("classes", [])),
        "command_functions": set(item.get("command_functions", [])),
        "dispatch_functions": set(item.get("dispatch_functions", [])),
        "status_functions": set(item.get("status_functions", [])),
        "report_functions": set(item.get("report_functions", [])),
    }


def diff_inventory(current, previous=None):
    previous = previous or {}
    previous_files = {item.get("path"): item for item in previous.get("files", []) if item.get("path")}
    current_files = {item.get("path"): item for item in current.get("files", []) if item.get("path")}

    new_files = []
    changed_files = []
    removed_files = []
    new_symbols = []

    for path, item in current_files.items():
        before = previous_files.get(path)
        if before is None:
            new_files.append(path)
            symbols = _symbols_for(item)
            for group, names in symbols.items():
                for name in sorted(names):
                    new_symbols.append({"path": path, "kind": group, "name": name})
            continue

        if before.get("hash") != item.get("hash"):
            changed_files.append(path)
            before_symbols = _symbols_for(before)
            after_symbols = _symbols_for(item)
            for group, after_names in after_symbols.items():
                before_names = before_symbols.get(group, set())
                for name in sorted(after_names - before_names):
                    new_symbols.append({"path": path, "kind": group, "name": name})

    for path in previous_files:
        if path not in current_files:
            removed_files.append(path)

    return {
        "new_files": sorted(new_files),
        "changed_files": sorted(changed_files),
        "removed_files": sorted(removed_files),
        "new_symbols": new_symbols,
        "changed_or_new_files": sorted(set(new_files + changed_files)),
    }


def _compile_targets(diff, current):
    candidates = diff.get("changed_or_new_files", [])
    safe_bootstrap_files = [
        "modules/feature_verification.py",
        "modules/russian_command_context.py",
        "modules/premium_task_panel_ru.py",
        "modules/auto_verification.py",
        "LocalComet_Control_Panel.py",
    ]

    if not candidates:
        candidates = list(safe_bootstrap_files)

    if len(candidates) > 40:
        candidates = [
            path
            for path in candidates
            if path in set(safe_bootstrap_files)
            or path.startswith("modules/feature_")
            or path.startswith("modules/russian_")
        ]

    existing = []
    for path in candidates:
        full = ROOT_DIR / path
        if full.exists() and full.suffix == ".py":
            existing.append(path)

    if not existing:
        existing = [
            item["path"]
            for item in current.get("files", [])
            if item.get("path") in {
                "modules/feature_verification.py",
                "modules/russian_command_context.py",
                "modules/premium_task_panel_ru.py",
                "modules/auto_verification.py",
                "LocalComet_Control_Panel.py",
            }
        ]

    return sorted(set(existing))


def _run_py_compile(files):
    if not files:
        return {
            "ok": True,
            "name": "py_compile changed/new feature files",
            "output": "Нет новых или изменённых Python-файлов для py_compile.",
            "files": [],
        }

    result = subprocess.run(
        ["python", "-m", "py_compile", *files],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )

    return {
        "ok": result.returncode == 0,
        "name": "py_compile changed/new feature files",
        "files": files,
        "output": (
            f"CODE: {result.returncode}\n"
            f"FILES: {len(files)}\n"
            + "\n".join(f"- {path}" for path in files)
            + f"\n\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        ),
    }


def _safe_import(module_name):
    started = perf_counter()
    try:
        module = importlib.import_module(module_name)
        return {
            "module": module_name,
            "ok": True,
            "duration_sec": round(perf_counter() - started, 3),
            "error": "",
            "has_status": callable(getattr(module, "status", None)),
            "has_report": callable(getattr(module, "report", None)),
            "has_dispatch": callable(getattr(module, "dispatch", None)),
        }
    except Exception:
        return {
            "module": module_name,
            "ok": False,
            "duration_sec": round(perf_counter() - started, 3),
            "error": _short(traceback.format_exc(), 900),
            "has_status": False,
            "has_report": False,
            "has_dispatch": False,
        }


def _run_smoke_imports():
    results = [_safe_import(module_name) for module_name in SAFE_SMOKE_MODULES]
    return {
        "ok": all(item["ok"] for item in results),
        "name": "safe smoke imports",
        "results": results,
    }


def _run_command_contract_checks(current):
    problems = []
    checked = 0

    for item in current.get("files", []):
        path = item.get("path", "")
        if not path.startswith("modules/"):
            continue

        has_command_surface = bool(
            item.get("command_functions")
            or item.get("dispatch_functions")
            or item.get("command_literals")
        )
        if not has_command_surface:
            continue

        checked += 1

        if item.get("dispatch_functions") and not item.get("status_functions"):
            problems.append(f"{path}: dispatch есть, но status/status_* не найден.")

        if item.get("dispatch_functions") and not item.get("report_functions"):
            problems.append(f"{path}: dispatch есть, но report/report_* не найден.")

    return {
        "ok": not problems,
        "name": "command module contracts",
        "checked": checked,
        "problems": problems,
    }


def _run_russian_context_contract():
    try:
        from modules.russian_command_context import (
            build_russian_agent_context,
            explain_russian_intent,
            normalize_russian_agent_command,
            status as context_status,
        )

        normalized = normalize_russian_agent_command("проверь новые функции")
        context = build_russian_agent_context("проверь новые функции")
        explained = explain_russian_intent("проверь новые функции")
        payload = context_status()

        ok = (
            normalized == "pc verify features"
            and "Русский контекст" in context
            and explained.get("suggested_command") == "pc verify features"
            and payload.get("ok") is True
        )

        return {
            "ok": ok,
            "name": "russian command context contract",
            "normalized": normalized,
            "intent": explained,
            "status": payload,
            "context_preview": _short(context, 700),
        }
    except Exception:
        return {
            "ok": False,
            "name": "russian command context contract",
            "error": _short(traceback.format_exc(), 1200),
        }


def _run_feature_module_contract():
    try:
        own_status = status()
        ok = (
            own_status.get("ok") is True
            and "pc verify features" in own_status.get("commands", [])
            and own_status.get("browser_used") is False
        )
        return {
            "ok": ok,
            "name": "feature verification contract",
            "status": own_status,
        }
    except Exception:
        return {
            "ok": False,
            "name": "feature verification contract",
            "error": _short(traceback.format_exc(), 1200),
        }


def run_feature_verification(write_report=True, allow_browser=False):
    _ensure_dirs()
    previous = _load_inventory(LAST_OK_INVENTORY_PATH)
    current = scan_feature_inventory()
    diff = diff_inventory(current, previous)
    compile_files = _compile_targets(diff, current)

    steps = [
        {
            "ok": current.get("ok") is True,
            "name": "static feature inventory",
            "totals": current.get("totals", {}),
            "parse_errors": [
                {"path": item.get("path"), "error": item.get("parse_error")}
                for item in current.get("files", [])
                if not item.get("parse_ok")
            ],
        },
        _run_py_compile(compile_files),
        _run_smoke_imports(),
        _run_command_contract_checks(current),
        _run_russian_context_contract(),
        _run_feature_module_contract(),
    ]

    passed = sum(1 for step in steps if step.get("ok"))
    total = len(steps)
    result = {
        "ok": passed == total,
        "status": "ok" if passed == total else "failed",
        "mode": "feature_verification",
        "generated_at": _now(),
        "allow_browser": bool(allow_browser),
        "browser_used": False,
        "passed": passed,
        "total": total,
        "diff": diff,
        "compile_files": compile_files,
        "inventory_totals": current.get("totals", {}),
        "steps": steps,
        "report": "",
        "inventory": str(INVENTORY_PATH),
        "last_ok_inventory": str(LAST_OK_INVENTORY_PATH),
    }

    _save_inventory(current, INVENTORY_PATH)

    if result["ok"]:
        _save_inventory(current, LAST_OK_INVENTORY_PATH)

    if write_report:
        result["report"] = str(write_feature_verification_report(result, current))

    return result


def format_feature_verification(result=None):
    result = result or run_feature_verification(write_report=False)
    diff = result.get("diff", {})
    lines = [
        "Feature Verification:",
        f"- status: {result.get('status')}",
        f"- mode: {result.get('mode')}",
        f"- score: {result.get('passed')}/{result.get('total')}",
        f"- generated_at: {result.get('generated_at')}",
        f"- browser_used: {str(result.get('browser_used')).lower()}",
        f"- report: {result.get('report') or 'не записан'}",
        "",
        "Detected changes:",
        f"- new_files: {len(diff.get('new_files', []))}",
        f"- changed_files: {len(diff.get('changed_files', []))}",
        f"- removed_files: {len(diff.get('removed_files', []))}",
        f"- new_symbols: {len(diff.get('new_symbols', []))}",
        "",
        "Checks:",
    ]

    for step in result.get("steps", []):
        mark = "OK" if step.get("ok") else "FAIL"
        lines.append(f"- [{mark}] {step.get('name')}")

    problems = [step for step in result.get("steps", []) if not step.get("ok")]
    lines.extend(["", "Problems:"])

    if problems:
        for step in problems:
            lines.append(f"- {step.get('name')}: {_short(step.get('error') or step.get('problems') or step.get('output'), 400)}")
    else:
        lines.append("- Не обнаружены.")

    return "\n".join(lines)


def write_feature_verification_report(result=None, inventory=None):
    _ensure_dirs()
    result = result or run_feature_verification(write_report=False)
    inventory = inventory or scan_feature_inventory()
    path = REPORTS_FEATURE_DIR / f"feature_verification_{_stamp()}.md"
    diff = result.get("diff", {})

    lines = [
        "# Feature Verification",
        "",
        format_feature_verification({**result, "report": str(path)}),
        "",
        "## Inventory totals",
        "",
    ]

    for key, value in result.get("inventory_totals", {}).items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Changed or new files", ""])

    changed_or_new = diff.get("changed_or_new_files", [])
    if changed_or_new:
        for item in changed_or_new[:120]:
            lines.append(f"- `{item}`")
    else:
        lines.append("- Нет новых или изменённых файлов относительно последнего успешного inventory.")

    lines.extend(["", "## New symbols", ""])

    new_symbols = diff.get("new_symbols", [])
    if new_symbols:
        for item in new_symbols[:160]:
            lines.append(f"- `{item.get('path')}` · {item.get('kind')} · `{item.get('name')}`")
    else:
        lines.append("- Новые функции/классы не обнаружены.")

    lines.extend(["", "## Step details", ""])

    for step in result.get("steps", []):
        mark = "OK" if step.get("ok") else "FAIL"
        lines.extend([
            f"### [{mark}] {step.get('name')}",
            "",
            "```json",
            json.dumps(step, ensure_ascii=False, indent=2),
            "```",
            "",
        ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def latest_feature_verification_report():
    if not REPORTS_FEATURE_DIR.exists():
        return None
    reports = [
        path
        for path in REPORTS_FEATURE_DIR.glob("feature_verification_*.md")
        if path.is_file()
    ]
    if not reports:
        return None
    return max(reports, key=lambda path: path.stat().st_mtime)


def status():
    latest = latest_feature_verification_report()
    previous = _load_inventory(LAST_OK_INVENTORY_PATH)
    current = scan_feature_inventory()
    return {
        "ok": True,
        "mode": "feature_verification_status",
        "generated_at": _now(),
        "browser_used": False,
        "checks_new_functions": True,
        "detects_new_functions": True,
        "auto_verification_integration": True,
        "inventory": str(INVENTORY_PATH),
        "last_ok_inventory": str(LAST_OK_INVENTORY_PATH),
        "latest_report": str(latest) if latest else "",
        "has_baseline": bool(previous),
        "totals": current.get("totals", {}),
        "commands": [
            "pc verify features",
            "pc verify status",
            "pc verify report",
            "проверь новые функции",
            "автопроверка функций",
        ],
    }


def report():
    result = run_feature_verification(write_report=True, allow_browser=False)
    return {
        "ok": result.get("ok"),
        "mode": "feature_verification_report",
        "generated_at": _now(),
        "status": result.get("status"),
        "report": result.get("report"),
        "score": f"{result.get('passed')}/{result.get('total')}",
    }


def dispatch(command):
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")

    if lower in {"pc verify", "pc verify status", "pc feature status", "pc features status", "статус проверки функций"}:
        return json.dumps(status(), ensure_ascii=False, indent=2)

    if lower in {
        "pc verify features",
        "pc feature verify",
        "pc features verify",
        "pc auto verify features",
        "проверь новые функции",
        "проверить новые функции",
        "автопроверка функций",
        "проверка функций",
    }:
        return json.dumps(run_feature_verification(write_report=True, allow_browser=False), ensure_ascii=False, indent=2)

    if lower in {"pc verify report", "pc feature report", "pc features report", "отчет проверки функций", "отчёт проверки функций"}:
        return json.dumps(report(), ensure_ascii=False, indent=2)

    return json.dumps(
        {
            "ok": False,
            "mode": "feature_verification_unknown_command",
            "generated_at": _now(),
            "error": "Неизвестная команда проверки функций.",
            "commands": status().get("commands", []),
        },
        ensure_ascii=False,
        indent=2,
    )


def is_feature_verification_command(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower.startswith(("pc verify", "pc feature", "pc features", "pc auto verify")):
        return True
    return lower in {
        "проверь новые функции",
        "проверить новые функции",
        "автопроверка функций",
        "проверка функций",
        "статус проверки функций",
        "отчет проверки функций",
        "отчёт проверки функций",
    }
