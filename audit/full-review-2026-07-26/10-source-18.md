# Полный исходный код (продолжение)

### ПУТЬ: modules/relay_diagnostics.py (333 строк, 11890 байт)

````python
import importlib
import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
RELAY_DIR = PROJECTS_DIR / "ChatGPTRelay"
RELAY_DOWNLOADS_DIR = RELAY_DIR / "Downloads"
REPORTS_DIR = PROJECTS_DIR / "Reports"
LOGS_DIR = PROJECTS_DIR / "Logs"
PATCH_REGISTRY_FILE = PROJECTS_DIR / "PatchRegistry" / "patches.json"
DIAGNOSTICS_REPORTS_DIR = REPORTS_DIR / "relay_diagnostics"

REQUEST_FILE = RELAY_DIR / "request.md"
RESPONSE_FILE = RELAY_DIR / "response.json"
BAD_RESPONSE_FILE = RELAY_DIR / "bad_response.json"
RAW_RESPONSE_TXT_FILE = RELAY_DIR / "response_raw.txt"
RAW_RESPONSE_MD_FILE = RELAY_DIR / "response_raw.md"
LAST_ANSWER_FILE = RELAY_DIR / "gpt_browser_last_answer.txt"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _exists(path):
    return Path(path).exists()


def _module_imports(name):
    try:
        importlib.import_module(name)
        return True, ""
    except Exception as e:
        return False, str(e)


def _read_json(path):
    path = Path(path)

    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _latest_patch_summary():
    data = _read_json(PATCH_REGISTRY_FILE)

    if isinstance(data, dict):
        data = data.get("patches")

    if isinstance(data, list) and data:
        latest = data[-1]

        if isinstance(latest, dict):
            return {
                "version": latest.get("version", ""),
                "summary": latest.get("summary", ""),
                "applied_at": latest.get("applied_at", ""),
                "status": latest.get("status", ""),
            }

    return {
        "version": get_value("last_patch_version", ""),
        "summary": get_value("last_patch_summary", ""),
        "applied_at": get_value("last_patch_applied_at", ""),
        "status": get_value("last_patch_status", ""),
    }


def _source_contains(path, markers):
    path = Path(path)

    if not path.exists():
        return False

    try:
        text = path.read_text(encoding="utf-8", errors="replace").lower()
    except Exception:
        return False

    return all(marker.lower() in text for marker in markers)


def get_relay_diagnostics():
    imports = {}

    for module_name in [
        "modules.true_auto_relay",
        "modules.chatgpt_relay",
        "modules.self_edit",
    ]:
        ok, error = _module_imports(module_name)
        imports[module_name] = {"ok": ok, "error": error}

    diagnostics = {
        "project_root": str(ROOT_DIR),
        "paths": {
            "relay_dir": {"path": str(RELAY_DIR), "exists": _exists(RELAY_DIR)},
            "downloads_dir": {"path": str(RELAY_DOWNLOADS_DIR), "exists": _exists(RELAY_DOWNLOADS_DIR)},
            "reports_dir": {"path": str(REPORTS_DIR), "exists": _exists(REPORTS_DIR)},
            "logs_dir": {"path": str(LOGS_DIR), "exists": _exists(LOGS_DIR)},
        },
        "files": {
            "request_md": {"path": str(REQUEST_FILE), "exists": _exists(REQUEST_FILE)},
            "response_json": {"path": str(RESPONSE_FILE), "exists": _exists(RESPONSE_FILE)},
            "bad_response_json": {"path": str(BAD_RESPONSE_FILE), "exists": _exists(BAD_RESPONSE_FILE)},
            "last_raw_response_txt": {"path": str(RAW_RESPONSE_TXT_FILE), "exists": _exists(RAW_RESPONSE_TXT_FILE)},
            "last_raw_response_md": {"path": str(RAW_RESPONSE_MD_FILE), "exists": _exists(RAW_RESPONSE_MD_FILE)},
            "last_answer_txt": {"path": str(LAST_ANSWER_FILE), "exists": _exists(LAST_ANSWER_FILE)},
        },
        "state": {
            "current_cycle_id": get_value("last_true_auto_cycle_id", ""),
            "last_imported_cycle_id": get_value("last_true_auto_imported_cycle_id", ""),
            "last_relay_error": (
                get_value("last_relay_error", "")
                or get_value("last_gpt_browser_error", "")
                or get_value("last_true_auto_download_error", "")
                or get_value("last_error", "")
            ),
            "last_relay_request": get_value("last_relay_request", ""),
            "last_relay_response": get_value("last_relay_response", ""),
            "last_true_auto_relay_report": get_value("last_true_auto_relay_report", ""),
            "last_applied_patch": _latest_patch_summary(),
        },
        "guards": {
            "response_freshness_guard_present": _source_contains(
                ROOT_DIR / "modules" / "true_auto_relay.py",
                ["response freshness guard", "expected_cycle_id", "meta.cycle_id"],
            ),
            "patch_registry_present": _exists(PATCH_REGISTRY_FILE) and imports["modules.self_edit"]["ok"],
            "dry_run_safe": True,
        },
        "imports": imports,
    }

    return diagnostics


def _yes(value):
    return "да" if value else "нет"


def format_relay_diagnostics_text(diagnostics=None):
    diagnostics = diagnostics or get_relay_diagnostics()

    lines = [
        "Relay Diagnostics:",
        f"- project_root: {diagnostics.get('project_root')}",
        "",
        "Paths:",
    ]

    for name, item in diagnostics.get("paths", {}).items():
        lines.append(f"- {name}: {_yes(item.get('exists'))} | {item.get('path')}")

    lines.append("")
    lines.append("Existing files:")

    for name, item in diagnostics.get("files", {}).items():
        lines.append(f"- {name}: {_yes(item.get('exists'))} | {item.get('path')}")

    lines.append("")
    lines.append("Module imports:")

    for name, item in diagnostics.get("imports", {}).items():
        suffix = "" if item.get("ok") else f" | {item.get('error')}"
        lines.append(f"- {name}: {_yes(item.get('ok'))}{suffix}")

    state = diagnostics.get("state", {})
    guards = diagnostics.get("guards", {})

    lines.extend([
        "",
        "Relay safety:",
        f"- response_freshness_guard_present: {_yes(guards.get('response_freshness_guard_present'))}",
        f"- patch_registry_present: {_yes(guards.get('patch_registry_present'))}",
        f"- dry_run_safe: {_yes(guards.get('dry_run_safe'))}",
        "",
        "Last known state:",
        f"- current_cycle_id: {state.get('current_cycle_id') or 'нет'}",
        f"- last_imported_cycle_id: {state.get('last_imported_cycle_id') or 'нет'}",
        f"- last_relay_request: {state.get('last_relay_request') or 'нет'}",
        f"- last_relay_response: {state.get('last_relay_response') or 'нет'}",
        f"- last_true_auto_relay_report: {state.get('last_true_auto_relay_report') or 'нет'}",
        f"- last_relay_error: {state.get('last_relay_error') or 'нет'}",
    ])

    latest = state.get("last_applied_patch") or {}
    lines.extend([
        "- last_applied_patch: "
        + f"{latest.get('version') or 'нет'} | {latest.get('status') or 'нет'} | {latest.get('summary') or 'нет'}",
    ])

    return "\n".join(lines)


def _report_path():
    DIAGNOSTICS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return DIAGNOSTICS_REPORTS_DIR / f"relay_diagnostics_{_stamp()}.md"


def _section(lines, title, body):
    lines.append(f"## {title}")
    lines.append("")

    if isinstance(body, list):
        lines.extend(body)
    else:
        lines.append(str(body))

    lines.append("")


def run_relay_smoke_test(dry_run=True):
    diagnostics = get_relay_diagnostics()
    report_path = _report_path()

    paths_ok = all(item.get("exists") for item in diagnostics.get("paths", {}).values())
    imports_ok = all(item.get("ok") for item in diagnostics.get("imports", {}).values())
    guards = diagnostics.get("guards", {})
    safety_ok = bool(guards.get("response_freshness_guard_present") and guards.get("patch_registry_present"))
    passed = bool(paths_ok and imports_ok and safety_ok and dry_run)

    lines = [
        "# Relay Diagnostics Smoke Test",
        "",
        f"- started_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- dry_run: {_yes(dry_run)}",
        f"- result: {'PASS' if passed else 'CHECK'}",
        "",
    ]

    _section(lines, "Summary", [
        f"- paths_ok: {_yes(paths_ok)}",
        f"- imports_ok: {_yes(imports_ok)}",
        f"- safety_ok: {_yes(safety_ok)}",
        "- real_chatgpt_send: нет",
        "- real_patch_apply: нет",
    ])

    _section(lines, "Paths", [
        f"- {name}: {_yes(item.get('exists'))} | {item.get('path')}"
        for name, item in diagnostics.get("paths", {}).items()
    ])

    _section(lines, "Existing files", [
        f"- {name}: {_yes(item.get('exists'))} | {item.get('path')}"
        for name, item in diagnostics.get("files", {}).items()
    ])

    _section(lines, "Module imports", [
        f"- {name}: {_yes(item.get('ok'))}"
        + ("" if item.get("ok") else f" | {item.get('error')}")
        for name, item in diagnostics.get("imports", {}).items()
    ])

    _section(lines, "Relay safety", [
        f"- response_freshness_guard_present: {_yes(guards.get('response_freshness_guard_present'))}",
        f"- patch_registry_present: {_yes(guards.get('patch_registry_present'))}",
        f"- dry_run_safe: {_yes(guards.get('dry_run_safe'))}",
        "- response_json_created: нет",
        "- patch_applied: нет",
    ])

    state = diagnostics.get("state", {})
    latest = state.get("last_applied_patch") or {}

    _section(lines, "Last known state", [
        f"- current_cycle_id: {state.get('current_cycle_id') or 'нет'}",
        f"- last_imported_cycle_id: {state.get('last_imported_cycle_id') or 'нет'}",
        f"- last_relay_request: {state.get('last_relay_request') or 'нет'}",
        f"- last_relay_response: {state.get('last_relay_response') or 'нет'}",
        f"- last_true_auto_relay_report: {state.get('last_true_auto_relay_report') or 'нет'}",
        f"- last_relay_error: {state.get('last_relay_error') or 'нет'}",
        f"- last_applied_patch: {latest.get('version') or 'нет'} | {latest.get('status') or 'нет'} | {latest.get('summary') or 'нет'}",
    ])

    _section(lines, "Result", [
        f"- status: {'PASS' if passed else 'CHECK'}",
        f"- report: {report_path}",
    ])

    _section(lines, "Next manual steps", [
        "1. Открой панель LocalComet.",
        "2. Нажми Relay status.",
        "3. Нажми Relay smoke.",
        "4. Нажми Open last relay report.",
        "5. Только после ручной проверки запускай настоящий dev -> ChatGPT -> validate -> apply цикл.",
    ])

    report_path.write_text("\n".join(lines), encoding="utf-8")

    set_value("last_relay_diagnostics_report", str(report_path))
    set_value("last_relay_diagnostics_status", "PASS" if passed else "CHECK")
    set_value("last_relay_diagnostics_at", datetime.now().isoformat(timespec="seconds"))

    return (
        "Relay smoke test завершен.\n"
        f"Dry-run: {_yes(dry_run)}\n"
        f"Result: {'PASS' if passed else 'CHECK'}\n"
        f"Report: {report_path}\n\n"
        "Безопасность: ChatGPT не отправлялся, response.json не создавался, patch не применялся."
    )


def latest_relay_diagnostics_report():
    state_path = str(get_value("last_relay_diagnostics_report", "") or "").strip()

    if state_path:
        path = Path(state_path)

        if path.exists() and path.is_file():
            return path

    if not DIAGNOSTICS_REPORTS_DIR.exists():
        return None

    reports = [path for path in DIAGNOSTICS_REPORTS_DIR.glob("relay_diagnostics_*.md") if path.is_file()]

    if not reports:
        return None

    return max(reports, key=lambda path: path.stat().st_mtime)
````

### ПУТЬ: modules/repo_analyzer_ru.py (297 строк, 9711 байт)

````python
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


REPO_ANALYZER_VERSION = "v6.59b"
REPO_ANALYZER_NAME = "LocalComet Repo Analyzer RU"

ROOT_PATH = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_PATH / "Projects" / "Reports" / "repo_analyzer"

CURRENT_VERSION = "v6.59"

BLOCKED_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist",
                "build", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                "BrowserProfile", "Backups", "LocalAgent_Backups"}

BLOCKED_PREFIXES = {".", "_backup", "backup_", "opencode_backup"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_PATH)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _is_skipped(path: Path) -> bool:
    parts = path.parts
    for blocked in BLOCKED_DIRS:
        if blocked in parts:
            return True
    if path.suffix != ".py":
        return True
    name = path.name
    if name.endswith(".bak") or name.endswith(".pyc") or name.endswith(".pyo"):
        return True
    for prefix in BLOCKED_PREFIXES:
        if name.startswith(prefix):
            return True
    return False


def _read_text(path: Path, limit: int = 80000) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""


def _iter_python_files() -> List[Path]:
    files: List[Path] = []
    for path in sorted(ROOT_PATH.rglob("*.py"), key=lambda p: _safe_relative(p).lower()):
        if _is_skipped(path):
            continue
        files.append(path)
    return files


def _count_matches(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text))


def _extract_functions(text: str) -> List[str]:
    return list(set(re.findall(r"^\s*def\s+(\w+)\s*\(", text, re.MULTILINE)))


def _extract_classes(text: str) -> List[str]:
    return list(set(re.findall(r"^\s*class\s+(\w+)\s*[:\(]", text, re.MULTILINE)))


def _extract_versions(text: str) -> List[str]:
    return list(set(re.findall(r'(?:VERSION|version)\s*=\s*"([^"]+)"', text)))


def _is_stale(version: str) -> bool:
    try:
        v = version.lstrip("v").split(".")[:2]
        c = CURRENT_VERSION.lstrip("v").split(".")[:2]
        return (int(v[0]), float(v[1])) < (int(c[0]), float(c[1]))
    except Exception:
        return False


def analyze() -> Dict[str, Any]:
    files = _iter_python_files()
    total_functions = 0
    total_classes = 0
    file_details: List[Dict[str, Any]] = []
    all_functions: Dict[str, List[str]] = {}
    all_versions: List[Dict[str, str]] = []
    command_modules = 0
    dispatch_count = 0
    status_count = 0
    report_count = 0
    large_files: List[Dict[str, Any]] = []

    for path in files:
        rel = _safe_relative(path)
        text = _read_text(path)
        if not text:
            continue

        lines = text.count("\n") + 1
        size_kb = path.stat().st_size / 1024 if path.exists() else 0

        funcs = _extract_functions(text)
        classes = _extract_classes(text)
        total_functions += len(funcs)
        total_classes += len(classes)

        for fn in funcs:
            all_functions.setdefault(fn, []).append(rel)

        has_dispatch = bool(re.search(r"def dispatch\s*\(", text))
        has_status = bool(re.search(r"def status\s*\(", text))
        has_report_func = bool(re.search(r"def report\s*\(", text))

        if has_dispatch:
            dispatch_count += 1
        if has_status:
            status_count += 1
        if has_report_func:
            report_count += 1

        if has_dispatch or has_status or has_report_func:
            command_modules += 1

        versions = _extract_versions(text)
        for ver in versions:
            if _is_stale(ver):
                all_versions.append({"file": rel, "version": ver})

        is_large = False
        large_reason = ""
        if lines > 800:
            is_large = True
            large_reason = f"{lines} lines"
        elif size_kb > 30:
            is_large = True
            large_reason = f"{size_kb:.1f} KB"

        if is_large:
            large_files.append({"file": rel, "lines": lines, "size_kb": round(size_kb, 1), "reason": large_reason})

        file_details.append({
            "path": rel,
            "lines": lines,
            "size_kb": round(size_kb, 1),
            "functions": len(funcs),
            "classes": len(classes),
            "has_dispatch": has_dispatch,
            "has_status": has_status,
            "has_report": has_report_func,
        })

    duplicates = {fn: mods for fn, mods in all_functions.items() if len(mods) > 1}

    return {
        "file_count": len(file_details),
        "function_count": total_functions,
        "class_count": total_classes,
        "command_module_count": command_modules,
        "dispatch_module_count": dispatch_count,
        "status_module_count": status_count,
        "report_module_count": report_count,
        "duplicate_function_count": len(duplicates),
        "duplicate_functions": {fn: sorted(mods) for fn, mods in sorted(duplicates.items())},
        "large_file_count": len(large_files),
        "large_files": sorted(large_files, key=lambda x: -x["lines"])[:30],
        "stale_version_count": len(all_versions),
        "stale_versions": sorted(all_versions, key=lambda x: x["file"]),
        "files": file_details,
    }


def status() -> Dict[str, Any]:
    data = analyze()
    return {
        "ok": True,
        "mode": "repo_analyzer_status",
        "version": REPO_ANALYZER_VERSION,
        "file_count": data["file_count"],
        "function_count": data["function_count"],
        "class_count": data["class_count"],
        "command_module_count": data["command_module_count"],
        "large_file_count": data["large_file_count"],
        "stale_version_count": data["stale_version_count"],
        "duplicate_function_count": data["duplicate_function_count"],
    }


def report() -> Dict[str, Any]:
    data = analyze()
    return {
        "ok": True,
        "mode": "repo_analyzer_report",
        "version": REPO_ANALYZER_VERSION,
        "generated_at": _now(),
        "project_root": str(ROOT_PATH),
        "current_version": CURRENT_VERSION,
        **data,
    }


def _write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "latest_repo_analyzer.json"
    md_path = REPORT_DIR / "latest_repo_analyzer.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# LocalComet Repo Analyzer",
        "",
        f"- version: {payload.get('version')}",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Summary",
        "",
        f"- files: {payload.get('file_count')}",
        f"- functions: {payload.get('function_count')}",
        f"- classes: {payload.get('class_count')}",
        f"- command modules: {payload.get('command_module_count')}",
        f"- large files: {payload.get('large_file_count')}",
        f"- stale versions: {payload.get('stale_version_count')}",
        f"- duplicate functions: {payload.get('duplicate_function_count')}",
        "",
    ]

    if payload.get("large_files"):
        lines.extend(["## Large Files", ""])
        for lf in payload["large_files"][:15]:
            lines.append(f"- {lf['file']} ({lf['reason']})")
        lines.append("")

    if payload.get("stale_versions"):
        lines.extend(["## Stale Version Markers", ""])
        for sv in payload["stale_versions"][:15]:
            lines.append(f"- {sv['file']}: {sv['version']}")
        lines.append("")

    if payload.get("duplicate_functions"):
        lines.extend(["## Duplicate Function Names", ""])
        for fn, mods in list(payload["duplicate_functions"].items())[:20]:
            lines.append(f"- `{fn}` found in {len(mods)} files: {', '.join(mods)}")
        lines.append("")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "md": md_path}


def is_repo_analyzer_command(command: str) -> bool:
    lowered = str(command or "").strip().lower().replace("ё", "е")
    targets = {
        "анализ проекта", "repo analyzer", "карта проекта",
        "pc repo analyze", "pc repo analyzer", "pc анализ",
    }
    return lowered in targets


def dispatch(command: str) -> Dict[str, Any]:
    lowered = str(command or "").strip().lower().replace("ё", "е")
    if lowered in {"анализ проекта", "repo analyzer", "карта проекта",
                   "pc repo analyze", "pc repo analyzer", "pc анализ"}:
        result = report()
        paths = _write_reports(result)
        result["report"] = str(paths["md"])
        result["json"] = str(paths["json"])
        return result
    if lowered in {"pc repo analyze status", "repo analyzer status"}:
        return status()
    return {
        "ok": False,
        "mode": "repo_analyzer_unknown",
        "version": REPO_ANALYZER_VERSION,
        "command": command,
        "hint": "Use: анализ проекта, repo analyzer, карта проекта",
    }


if __name__ == "__main__":
    result = dispatch("анализ проекта")
    _write_reports(result)
    print(json.dumps(result, ensure_ascii=False, indent=2)[:3000])
````

### ПУТЬ: modules/repo_weight_audit_ru.py (310 строк, 13375 байт)

````python
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_WEIGHT_AUDIT_VERSION = "v6.64a"
REPO_WEIGHT_AUDIT_NAME = "LocalComet Repository Weight Audit RU"

ROOT_PATH = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_PATH / ".localcomet" / "reports"
REPO_WEIGHT_JSON = OUTPUT_DIR / "repo_weight_report.json"
REPO_WEIGHT_MD = OUTPUT_DIR / "repo_weight_report.md"
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"

BACKUP_KEYWORDS = ["opencode_backup", ".opencode_backup", "backup_"]
CACHE_DIR_NAMES = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", "node_modules", "dist", "build", "logs",
}
GENERATED_ARTIFACT_PATH_PARTS = {".localcomet", "Projects/Reports", "Projects/ComputerUse/runs"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _detect_base_version() -> str:
    try:
        for line in CONTROL_PANEL_PATH.read_text(encoding="utf-8").split("\n"):
            if "LOCALCOMET_VERSION" in line and "=" in line:
                return line.split("=")[-1].strip().strip("\"'")
    except Exception:
        pass
    return "unknown"


def _classify_dir(rel_path: str) -> Tuple[bool, bool, bool]:
    is_backup = any(kw in rel_path for kw in BACKUP_KEYWORDS)
    is_cache = False
    is_generated = False
    parts_lower = rel_path.replace("\\", "/").lower()
    for cn in CACHE_DIR_NAMES:
        if f"/{cn}/" in parts_lower or parts_lower.endswith(f"/{cn}") or parts_lower.startswith(f"{cn}/") or parts_lower == cn:
            is_cache = True
            break
    for gp in GENERATED_ARTIFACT_PATH_PARTS:
        if gp.replace("/", "\\") in rel_path or gp.replace("/", "/") in parts_lower:
            is_generated = True
            break
    return is_backup, is_cache, is_generated


def scan() -> Dict[str, Any]:
    root = ROOT_PATH.resolve()
    root_str = str(root)
    total_size = 0
    file_count = 0
    folder_count = 0
    scan_errors: List[str] = []
    top_dirs: Dict[str, int] = {}
    top_files: List[Tuple[int, str]] = []
    backup_dirs: Dict[str, int] = {}
    cache_dirs: Dict[str, int] = {}
    generated_artifact_dirs: Dict[str, int] = {}
    min_top_dir_size = 0
    min_top_file_size = 0
    MAX_TOP_DIRS = 30
    MAX_TOP_FILES = 50
    MAX_BACKUP_DIRS = 50
    MAX_CACHE_DIRS = 50
    MAX_GENERATED_DIRS = 50
    stack = [(root, root_str)]
    visited = set()
    while stack:
        current, current_str = stack.pop()
        try:
            resolved = current.resolve()
            rs = str(resolved)
            if rs in visited:
                continue
            visited.add(rs)
        except Exception:
            scan_errors.append(f"Could not resolve {current}")
            continue
        dir_size = 0
        try:
            with os.scandir(str(current)) as it:
                entries = list(it)
        except PermissionError:
            scan_errors.append(f"Permission denied: {current}")
            continue
        except OSError as e:
            scan_errors.append(f"OS error reading {current}: {e}")
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    folder_count += 1
                    try:
                        child_path = entry.path
                        stack.append((Path(child_path), current_str))
                    except Exception:
                        scan_errors.append(f"Could not process dir: {entry.path}")
                        continue
                elif entry.is_file(follow_symlinks=False):
                    file_count += 1
                    try:
                        sz = entry.stat(follow_symlinks=False).st_size
                        total_size += sz
                        dir_size += sz
                        if sz > min_top_file_size:
                            top_files.append((sz, entry.path))
                            top_files.sort(reverse=True, key=lambda x: x[0])
                            if len(top_files) > MAX_TOP_FILES:
                                top_files = top_files[:MAX_TOP_FILES]
                            min_top_file_size = top_files[-1][0] if len(top_files) >= MAX_TOP_FILES else 0
                    except (OSError, PermissionError) as e:
                        scan_errors.append(f"Could not stat file: {entry.path}: {e}")
            except Exception:
                scan_errors.append(f"Unexpected error processing {entry.name}")
                continue
        rel = str(current.relative_to(root)) if current != root else "."
        is_backup, is_cache, is_generated = _classify_dir(rel)
        if is_backup:
            backup_dirs[rel] = dir_size
        if is_cache:
            cache_dirs[rel] = dir_size
        if is_generated:
            generated_artifact_dirs[rel] = dir_size
        if dir_size > min_top_dir_size:
            top_dirs[rel] = dir_size
            if len(top_dirs) > MAX_TOP_DIRS * 2:
                sorted_dirs = sorted(top_dirs.items(), key=lambda x: x[1], reverse=True)[:MAX_TOP_DIRS]
                top_dirs = dict(sorted_dirs)
                min_top_dir_size = sorted_dirs[-1][1] if len(sorted_dirs) >= MAX_TOP_DIRS else 0

    sorted_top_dirs = sorted(top_dirs.items(), key=lambda x: x[1], reverse=True)[:MAX_TOP_DIRS]
    sorted_top_files = [(p, s) for s, p in top_files]
    sorted_backup = sorted(backup_dirs.items(), key=lambda x: x[1], reverse=True)[:MAX_BACKUP_DIRS]
    sorted_cache = sorted(cache_dirs.items(), key=lambda x: x[1], reverse=True)[:MAX_CACHE_DIRS]
    sorted_generated = sorted(generated_artifact_dirs.items(), key=lambda x: x[1], reverse=True)[:MAX_GENERATED_DIRS]

    base_version = _detect_base_version()
    total_mb = round(total_size / (1024 * 1024), 2)
    total_gb = round(total_size / (1024 * 1024 * 1024), 2)

    return {
        "schema_version": "1.0",
        "project_name": "LocalComet / LocalAgent",
        "base_version": base_version,
        "generated_at": _now(),
        "root_path": root_str,
        "total_size_bytes": total_size,
        "total_size_mb": total_mb,
        "total_size_gb": total_gb,
        "file_count": file_count,
        "folder_count": folder_count,
        "top_directories": [{"path": p, "size_bytes": s, "size_mb": round(s / (1024 * 1024), 2)} for p, s in sorted_top_dirs],
        "top_files": [{"path": p, "size_bytes": s, "size_mb": round(s / (1024 * 1024), 2)} for p, s in sorted_top_files],
        "backup_directories": [{"path": p, "size_bytes": s, "size_mb": round(s / (1024 * 1024), 2)} for p, s in sorted_backup],
        "cache_directories": [{"path": p, "size_bytes": s, "size_mb": round(s / (1024 * 1024), 2)} for p, s in sorted_cache],
        "generated_artifact_directories": [{"path": p, "size_bytes": s, "size_mb": round(s / (1024 * 1024), 2)} for p, s in sorted_generated],
        "suspected_heavy_categories": {
            "opencode_backups_present": len(sorted_backup) > 0,
            "cache_present": len(sorted_cache) > 0,
            "generated_artifacts_present": len(sorted_generated) > 0,
        },
        "safe_cleanup_recommendations": [
            "Review opencode_backups directories; these contain pre-edit snapshots.",
            "Review __pycache__ directories; Python cache can be regenerated.",
            "Review .pytest_cache, .mypy_cache, .ruff_cache; test/lint caches.",
            "Review .venv / venv / node_modules; these can be reinstalled.",
            "Review dist / build; build artifacts can be regenerated.",
            "Review .localcomet generated reports; these are regenerated on demand.",
            "Review Projects/Reports; these are regenerated by tests and audits.",
            "Review Projects/ComputerUse/runs; these are runtime traces.",
            "Review backup .zip and manifest files in Projects/SelfEdit/opencode_backups.",
        ],
        "dangerous_cleanup_warning": "NO FILES WERE DELETED. This is an audit-only scan. Any cleanup requires explicit separate approval. The scanner only writes report files and never modifies repository data. Do not delete entire directories without verifying their contents.",
        "scan_errors": scan_errors if scan_errors else [],
        "source_references": {},
    }


def _write_report(payload: Dict[str, Any]) -> Dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPO_WEIGHT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# LocalComet Repository Weight Audit",
        "",
        f"- schema_version: {payload.get('schema_version')}",
        f"- project_name: {payload.get('project_name')}",
        f"- base_version: {payload.get('base_version')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- root_path: {payload.get('root_path')}",
        "",
        "## Overall Statistics",
        "",
        f"- total_size_bytes: {payload.get('total_size_bytes')}",
        f"- total_size_mb: {payload.get('total_size_mb')}",
        f"- total_size_gb: {payload.get('total_size_gb')}",
        f"- file_count: {payload.get('file_count')}",
        f"- folder_count: {payload.get('folder_count')}",
        "",
        "## Top Directories by Size",
        "",
    ]
    for i, d in enumerate(payload.get("top_directories", []), 1):
        lines.append(f"{i}. {d.get('path', '')} - {d.get('size_mb', 0)} MB ({d.get('size_bytes', 0)} bytes)")
    lines.append("")
    lines.extend(["## Top Files by Size", ""])
    for i, f in enumerate(payload.get("top_files", []), 1):
        lines.append(f"{i}. {f.get('path', '')} - {f.get('size_mb', 0)} MB ({f.get('size_bytes', 0)} bytes)")
    lines.append("")
    lines.extend(["## Backup Directories", ""])
    for bd in payload.get("backup_directories", []):
        lines.append(f"- {bd.get('path', '')} - {bd.get('size_mb', 0)} MB")
    if not payload.get("backup_directories"):
        lines.append("(none found)")
    lines.append("")
    lines.extend(["## Cache Directories", ""])
    for cd in payload.get("cache_directories", []):
        lines.append(f"- {cd.get('path', '')} - {cd.get('size_mb', 0)} MB")
    if not payload.get("cache_directories"):
        lines.append("(none found)")
    lines.append("")
    lines.extend(["## Generated Artifact Directories", ""])
    for ga in payload.get("generated_artifact_directories", []):
        lines.append(f"- {ga.get('path', '')} - {ga.get('size_mb', 0)} MB")
    if not payload.get("generated_artifact_directories"):
        lines.append("(none found)")
    lines.append("")
    lines.extend(["## Suspected Heavy Categories", ""])
    shc = payload.get("suspected_heavy_categories", {})
    for k, v in shc.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.extend(["## Safe Cleanup Recommendations", ""])
    for rec in payload.get("safe_cleanup_recommendations", []):
        lines.append(f"- {rec}")
    lines.append("")
    lines.extend(["## Dangerous Cleanup Warning", "", f"{payload.get('dangerous_cleanup_warning', '')}", ""])
    lines.extend(["## Scan Errors", ""])
    errs = payload.get("scan_errors", [])
    if errs:
        for e in errs:
            lines.append(f"- {e}")
    else:
        lines.append("(none)")
    lines.append("")
    REPO_WEIGHT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "json": str(REPO_WEIGHT_JSON.relative_to(ROOT_PATH)),
        "md": str(REPO_WEIGHT_MD.relative_to(ROOT_PATH)),
    }


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "repo_weight_audit_status",
        "version": REPO_WEIGHT_AUDIT_VERSION,
        "json_exists": REPO_WEIGHT_JSON.exists(),
        "md_exists": REPO_WEIGHT_MD.exists(),
    }


def report() -> Dict[str, Any]:
    payload = scan()
    paths = _write_report(payload)
    return {
        "ok": True,
        "mode": "repo_weight_audit_report",
        "version": REPO_WEIGHT_AUDIT_VERSION,
        "generated_at": _now(),
        "paths": paths,
    }


def is_repo_weight_audit_command(command: str) -> bool:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    return lowered in {
        "localcomet repo weight audit",
        "repo weight audit",
        "repo weight",
    } or lowered.startswith("localcomet repo weight audit ")


def dispatch(command: str) -> Dict[str, Any]:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    if lowered in {"localcomet repo weight audit", "repo weight audit", "repo weight"}:
        result = report()
        return {"ok": True, "handled": True, "mode": "repo_weight_audit_generated", "version": REPO_WEIGHT_AUDIT_VERSION, "paths": result.get("paths", {})}
    if lowered in {"localcomet repo weight audit status", "repo weight audit status", "repo weight status"}:
        return status()
    return {"ok": False, "mode": "repo_weight_audit_unknown", "version": REPO_WEIGHT_AUDIT_VERSION, "command": command, "hint": "Use: localcomet repo weight audit"}


if __name__ == "__main__":
    result = dispatch("localcomet repo weight audit")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
````

### ПУТЬ: modules/report_opener.py (96 строк, 2358 байт)

````python
import subprocess
from pathlib import Path
from modules.project_paths import projects_dir

from core.state import get_value, set_value


PROJECTS_DIR = projects_dir()
REPORTS_DIR = PROJECTS_DIR / "Reports"


def _resolve_report_path(path: str):
    return (PROJECTS_DIR / path).resolve()


def remember_report(path: str):
    set_value("last_report", path)
    return f"Последний отчет запомнен: {path}"


def find_latest_report():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    reports = list(REPORTS_DIR.glob("*.md"))

    if not reports:
        return None

    latest = max(reports, key=lambda p: p.stat().st_mtime)
    relative = latest.relative_to(PROJECTS_DIR)

    return str(relative).replace("\\", "/")


def get_last_report_path():
    path = get_value("last_report")

    if path:
        report_path = _resolve_report_path(path)

        if report_path.exists():
            return path

    latest = find_latest_report()

    if latest:
        remember_report(latest)
        return latest

    return None


def open_report(path: str):
    report_path = _resolve_report_path(path)

    if not report_path.exists():
        return f"Отчет не найден: {report_path}"

    remember_report(path)

    try:
        subprocess.Popen(["code", str(report_path)], shell=True)
        return f"Открыл отчет в VS Code: {report_path}"
    except Exception:
        subprocess.Popen(["notepad", str(report_path)], shell=True)
        return f"Открыл отчет в Блокноте: {report_path}"


def open_last_report():
    path = get_last_report_path()

    if not path:
        return "Последний отчет не найден. Сначала создай отчет."

    return open_report(path)


def read_last_report():
    path = get_last_report_path()

    if not path:
        return "Последний отчет не найден. Сначала создай отчет."

    report_path = _resolve_report_path(path)

    if not report_path.exists():
        return f"Отчет не найден: {report_path}"

    text = report_path.read_text(encoding="utf-8")

    return (
        "Последний отчет:\n"
        + path
        + "\n\n"
        + text
    )
````

### ПУТЬ: modules/repository_preflight_ru.py (317 строк, 13323 байт)

````python
from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


REPOSITORY_PREFLIGHT_VERSION = "v6.81.2"
MANIFEST_NAME = "localcomet_runtime_manifest.json"
REQUIRED_MANIFEST_KEYS = ("entrypoints", "runtime", "lazy_runtime", "tests", "tools")
PATH_CATEGORIES = (*REQUIRED_MANIFEST_KEYS,)
SECRET_PATTERNS = (
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")),
    ("github_token", re.compile(r"\bghp_[A-Za-z0-9_]{12,}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("authorization_header", re.compile(r"\bAuthorization\s*:\s*(Bearer|Basic)\s+\S+", re.IGNORECASE)),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b", re.IGNORECASE)),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|token|password|passwd|secret|client[_-]?secret)\b\s*[:=]\s*['\"]?[^'\"\s]{8,}"
        ),
    ),
)
MACHINE_PATH_PATTERNS = (
    ("windows_user_path", re.compile(r"[A-Za-z]:(?:\\\\|\\)Users(?:\\\\|\\)[^\\\s'\"]+")),
    ("windows_absolute_path", re.compile(r"[A-Za-z]:(?:\\\\|\\)[^\\\s'\"]+")),
    ("posix_user_path", re.compile(r"/Users/[^/\s'\"]+|/home/[^/\s'\"]+")),
)
LOCAL_PREFIXES = {"agents", "core", "modules", "next", "tools"}


def resolve_project_root(root: str | Path | None = None) -> Path:
    if root is not None:
        return Path(root).expanduser().resolve()
    for env_name in ("LOCALCOMET_ROOT", "LOCALCOMET_ROOT_DIR"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return Path(value).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _redact(text: Any, root: Path) -> str:
    value = str(text or "")
    for marker in {str(root), root.as_posix(), str(Path.home()), str(Path.home()).replace("\\", "/")}:
        if marker:
            value = value.replace(marker, "<PROJECT_ROOT>")
    return value


def _safe_rel_path(raw: str) -> tuple[str | None, str | None]:
    value = str(raw or "").replace("\\", "/").strip()
    if not value:
        return None, "empty_path"
    if PureWindowsPath(value).drive or value.startswith("/") or value.startswith("\\"):
        return None, "absolute_path"
    pure = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in pure.parts):
        return None, "traversal_path"
    return pure.as_posix(), None


def _resolve_under_root(root: Path, rel_path: str) -> bool:
    try:
        (root / rel_path).resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def load_runtime_manifest(root: str | Path | None = None) -> dict[str, Any]:
    project_root = resolve_project_root(root)
    path = project_root / MANIFEST_NAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_paths(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    for category in PATH_CATEGORIES:
        values = manifest.get(category, [])
        if isinstance(values, list):
            for item in values:
                paths.append((category, str(item)))
    return paths


def validate_manifest(root: str | Path, manifest: dict[str, Any]) -> dict[str, Any]:
    project_root = resolve_project_root(root)
    unsafe_paths: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    warnings: list[str] = []
    present = bool(manifest)
    if not present:
        return {
            "present": False,
            "release": "",
            "runtime_count": 0,
            "lazy_runtime_count": 0,
            "unsafe_paths": [],
            "missing": [{"path": MANIFEST_NAME, "category": "manifest"}],
            "warnings": ["runtime_manifest_missing"],
        }

    for key in REQUIRED_MANIFEST_KEYS:
        values = manifest.get(key)
        if not isinstance(values, list):
            warnings.append(f"manifest_key_not_list:{key}")
            continue
        normalized = [str(item).replace("\\", "/") for item in values]
        if normalized != sorted(normalized, key=str.lower):
            warnings.append(f"manifest_list_not_sorted:{key}")
        if len(normalized) != len(set(normalized)):
            warnings.append(f"manifest_list_not_unique:{key}")

    required_categories = {"entrypoints", "runtime", "lazy_runtime", "tools", "tests"}
    for category, raw in _manifest_paths(manifest):
        rel, reason = _safe_rel_path(raw)
        if reason or rel is None:
            unsafe_paths.append({"path": raw, "category": category, "reason": str(reason)})
            continue
        if not _resolve_under_root(project_root, rel):
            unsafe_paths.append({"path": rel, "category": category, "reason": "outside_root"})
            continue
        if category in required_categories and not (project_root / rel).is_file():
            missing.append({"path": rel, "category": category})

    return {
        "present": True,
        "release": str(manifest.get("release", "")),
        "runtime_count": len(manifest.get("runtime", [])) if isinstance(manifest.get("runtime"), list) else 0,
        "lazy_runtime_count": len(manifest.get("lazy_runtime", [])) if isinstance(manifest.get("lazy_runtime"), list) else 0,
        "unsafe_paths": sorted(unsafe_paths, key=lambda item: (item["category"], item["path"])),
        "missing": sorted(missing, key=lambda item: (item["category"], item["path"])),
        "warnings": sorted(warnings),
    }


def _module_name_for_path(rel_path: str) -> str | None:
    if not rel_path.endswith(".py"):
        return None
    parts = rel_path[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _local_module_exists(root: Path, imported: str) -> bool:
    parts = imported.split(".")
    for index in range(len(parts), 0, -1):
        rel = Path(*parts[:index])
        if (
            (root / rel).with_suffix(".py").is_file()
            or (root / rel / "__init__.py").is_file()
            or (root / rel).is_dir()
        ):
            return True
    return False


def _resolve_relative_import(module_name: str, level: int, imported: str) -> str:
    parts = module_name.split(".")
    base = parts[: max(0, len(parts) - level)]
    if imported:
        base.extend(imported.split("."))
    return ".".join(part for part in base if part)


def build_static_import_graph(root: str | Path, manifest: dict[str, Any]) -> dict[str, Any]:
    project_root = resolve_project_root(root)
    nodes: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    module_map: dict[str, str] = {}
    source_paths: list[tuple[str, str]] = []
    for category, raw in _manifest_paths(manifest):
        rel, reason = _safe_rel_path(raw)
        if reason or rel is None or not rel.endswith(".py"):
            continue
        path = project_root / rel
        if not path.is_file():
            continue
        module = _module_name_for_path(rel)
        if module:
            module_map[module] = rel
            source_paths.append((category, rel))

    for category, rel in sorted(source_paths, key=lambda item: item[1].lower()):
        path = project_root / rel
        module_name = _module_name_for_path(rel) or rel
        nodes.append({"path": rel, "module": module_name, "category": category})
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    imports.add(_resolve_relative_import(module_name, node.level, node.module or ""))
                elif node.module:
                    imports.add(node.module)
        for imported in sorted(imports, key=str.lower):
            head = imported.split(".", 1)[0]
            if head not in LOCAL_PREFIXES:
                continue
            target = None
            for candidate in sorted(module_map, key=len, reverse=True):
                if imported == candidate or imported.startswith(candidate + "."):
                    target = module_map[candidate]
                    break
            if target:
                edges.append({"from": rel, "to": target, "import": imported})
            elif not _local_module_exists(project_root, imported):
                unresolved.append({"from": rel, "import": imported, "reason": "local_module_missing"})
    return {
        "nodes": sorted(nodes, key=lambda item: item["path"].lower()),
        "edges": sorted(edges, key=lambda item: (item["from"].lower(), item["to"].lower(), item["import"].lower())),
        "unresolved_imports": sorted(unresolved, key=lambda item: (item["from"].lower(), item["import"].lower())),
    }


def _scan_text_markers(root: Path, rel_path: str, text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    machine_paths: list[dict[str, Any]] = []
    secret_markers: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for category, pattern in MACHINE_PATH_PATTERNS:
            if pattern.search(line):
                machine_paths.append({"file": rel_path, "line": line_no, "category": category})
        for category, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                secret_markers.append({"file": rel_path, "line": line_no, "category": category})
    return machine_paths, secret_markers


def _syntax_and_markers(root: Path, manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    syntax_errors: list[dict[str, Any]] = []
    machine_paths: list[dict[str, Any]] = []
    secret_markers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _category, raw in _manifest_paths(manifest):
        rel, reason = _safe_rel_path(raw)
        if reason or rel is None or rel in seen:
            continue
        seen.add(rel)
        path = root / rel
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".pyw", ".json", ".md", ".txt", ".toml", ".yaml", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        found_machine, found_secret = _scan_text_markers(root, rel, text)
        machine_paths.extend(found_machine)
        secret_markers.extend(found_secret)
        if path.suffix.lower() in {".py", ".pyw"}:
            try:
                compile(text, rel, "exec")
            except SyntaxError as exc:
                syntax_errors.append({"file": rel, "line": exc.lineno or 0, "category": "syntax_error"})
    return (
        sorted(syntax_errors, key=lambda item: (item["file"].lower(), item["line"])),
        sorted(machine_paths, key=lambda item: (item["file"].lower(), item["line"], item["category"])),
        sorted(secret_markers, key=lambda item: (item["file"].lower(), item["line"], item["category"])),
    )


def run_repository_preflight(root: str | Path | None = None) -> dict[str, Any]:
    project_root = resolve_project_root(root)
    warnings: list[str] = []
    try:
        manifest = load_runtime_manifest(project_root)
    except Exception as exc:
        manifest = {}
        warnings.append(f"manifest_parse_error:{type(exc).__name__}")
    manifest_validation = validate_manifest(project_root, manifest)
    warnings.extend(manifest_validation.get("warnings", []))
    syntax_errors, machine_paths, secret_markers = _syntax_and_markers(project_root, manifest)
    import_graph = build_static_import_graph(project_root, manifest)
    missing = manifest_validation.get("missing", [])
    unsafe_paths = manifest_validation.get("unsafe_paths", [])
    unresolved = import_graph.get("unresolved_imports", [])
    ok = not (missing or unsafe_paths or syntax_errors or unresolved)
    result = {
        "mode": "repository_preflight",
        "version": REPOSITORY_PREFLIGHT_VERSION,
        "ok": ok,
        "root": "<PROJECT_ROOT>",
        "manifest": {
            "present": bool(manifest_validation.get("present")),
            "release": manifest_validation.get("release", ""),
            "runtime_count": manifest_validation.get("runtime_count", 0),
            "lazy_runtime_count": manifest_validation.get("lazy_runtime_count", 0),
        },
        "missing": missing,
        "syntax_errors": syntax_errors,
        "unresolved_imports": unresolved,
        "unsafe_paths": unsafe_paths,
        "machine_paths": machine_paths,
        "secret_markers": secret_markers,
        "warnings": sorted(set(_redact(item, project_root) for item in warnings)),
        "summary": {
            "missing_count": len(missing),
            "syntax_error_count": len(syntax_errors),
            "unresolved_import_count": len(unresolved),
            "unsafe_path_count": len(unsafe_paths),
            "machine_path_count": len(machine_paths),
            "secret_marker_count": len(secret_markers),
            "manifest_warning_count": len(set(warnings)),
        },
    }
    return result
````

### ПУТЬ: modules/research.py (368 строк, 10363 байт)

````python
import re
import json
from datetime import datetime
from json_repair import repair_json

from core.llm import ask_llm
from modules.browser import search, read_page, open_url, get_search_result_links
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
Ты Research Query Planner.

Твоя задача — превратить запрос пользователя в 2-4 точных поисковых запроса.

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
- Если пользователь пишет Comet, уточняй как "Perplexity Comet browser" или "Comet AI browser".
- Если пользователь пишет Claude Code, уточняй как "Claude Code alternatives".
- Если пользователь спрашивает про локальные LLM для ПК, добавляй запросы про LM Studio, llama.cpp, Ollama, VRAM requirements.
- Запросы должны быть короткие и поисковые.
- Не используй markdown.
- Не объясняй.
"""


SOURCE_SUMMARY_SYSTEM = """
Ты Research Source Summarizer.

Тебе дают текст одной страницы.
Сделай короткое резюме источника.

Верни обычный текст, не JSON.

Структура:

Источник:
...

Полезные факты:
- ...
- ...
- ...

Ограничения источника:
- ...

Правила:
- Пиши на русском.
- Не выдумывай.
- Если текст мусорный, captcha или мало данных — так и напиши.
- Максимум 10 коротких пунктов.
"""


FINAL_REPORT_SYSTEM = """
Ты Research Agent.

Твоя задача — сделать полезный финальный отчет по кратким резюме источников.

Верни обычный текст, не JSON.

Структура отчета:

# Краткий отчет

## Тема
...

## Найденные источники
...

## Главное
...

## Сравнение
...

## Выводы
...

## Что стоит сделать дальше
...

Правила:
- Пиши на русском.
- Не пиши воду.
- Не выдумывай факты, если их нет в данных.
- Если данных мало, честно укажи это.
- Делай отчет прикладным.
- Для локальных LLM учитывай железо пользователя.
- Обязательно закончи разделом "Что стоит сделать дальше".
"""


def _safe_filename(text: str):
    text = text.lower()
    text = re.sub(r"[^a-zа-я0-9]+", "_", text)
    text = text.strip("_")
    return text[:50] or "report"


def _make_search_queries(query: str):
    try:
        answer = ask_llm(QUERY_SYSTEM, query, max_tokens=700)
        answer = answer.replace("```json", "").replace("```", "").strip()

        data = json.loads(repair_json(answer))
        queries = data.get("queries", [])

        if isinstance(queries, list) and queries:
            return queries[:4]

    except Exception:
        pass

    return [
        query,
        f"{query} alternatives",
        f"{query} comparison",
    ]


def _collect_links_for_query(query: str, limit=4):
    search(query, engine="duckduckgo")
    links = get_search_result_links(limit=limit)

    if not links:
        search(query, engine="bing")
        links = get_search_result_links(limit=limit)

    return links


def _summarize_source(query: str, source: dict):
    title = source.get("title", "")
    url = source.get("url", "")
    text = source.get("text", "")

    prompt = f"""
Запрос пользователя:
{query}

Название источника:
{title}

URL:
{url}

Текст источника:
{text[:5000]}

Сделай краткое резюме этого источника.
"""

    try:
        summary = ask_llm(SOURCE_SUMMARY_SYSTEM, prompt, max_tokens=900)
    except Exception as e:
        summary = f"Не удалось сделать резюме источника: {e}"

    if not summary or not summary.strip():
        summary = f"""
Источник:
{title}
{url}

Полезные факты:
- Модель не смогла сформировать резюме.
- Источник был найден и открыт, но анализ не выполнен.

Ограничения источника:
- Требуется ручная проверка.
"""

    return summary.strip()


def _fallback_report(query: str, collected: list, search_queries: list):
    lines = []

    lines.append("# Краткий отчет")
    lines.append("")
    lines.append("## Тема")
    lines.append(query)
    lines.append("")
    lines.append("## Поисковые запросы")

    for q in search_queries:
        lines.append(f"- {q}")

    lines.append("")
    lines.append("## Найденные источники")

    if not collected:
        lines.append("Источники не найдены.")
    else:
        for i, item in enumerate(collected, start=1):
            lines.append(f"{i}. {item.get('title', 'Без названия')}")
            lines.append(f"   {item.get('url', '')}")

    lines.append("")
    lines.append("## Главное")
    lines.append("Поиск источников выполнен, но финальный анализ не был сформирован моделью.")
    lines.append("")
    lines.append("## Выводы")
    lines.append("Нужно повторить исследование или уменьшить объем данных для модели.")
    lines.append("")
    lines.append("## Что стоит сделать дальше")
    lines.append("- Повторить поиск более точным запросом.")
    lines.append("- Проверить найденные источники вручную.")
    lines.append("- Использовать более сильную локальную модель для финального анализа.")

    return "\n".join(lines)


def make_research_report(query: str):
    create_folder("Reports")

    search_queries = _make_search_queries(query)

    all_links = []
    seen_urls = set()

    for search_query in search_queries:
        links = _collect_links_for_query(search_query, limit=4)

        for link in links:
            url = link.get("url")

            if not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)
            all_links.append(link)

            if len(all_links) >= 8:
                break

        if len(all_links) >= 8:
            break

    collected = []

    for link in all_links[:6]:
        try:
            open_url(link["url"])
            text = read_page(limit=5000)

            collected.append({
                "title": link["title"],
                "url": link["url"],
                "text": text
            })

        except Exception as e:
            collected.append({
                "title": link["title"],
                "url": link["url"],
                "text": f"Не удалось открыть источник: {e}"
            })

    if not collected:
        page_text = read_page(limit=5000)
        collected.append({
            "title": "Страница поиска",
            "url": "search_results",
            "text": page_text
        })

    source_summaries = []

    for item in collected:
        summary = _summarize_source(query, item)

        source_summaries.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "summary": summary
        })

    summaries_text = ""

    for i, item in enumerate(source_summaries, start=1):
        summaries_text += f"""
SOURCE SUMMARY {i}
TITLE: {item.get("title", "")}
URL: {item.get("url", "")}
SUMMARY:
{item.get("summary", "")}

---
"""

    hardware_context = ""

    if "пк" in query.lower() or "pc" in query.lower() or "llm" in query.lower():
        hardware_context = USER_PC_PROFILE

    prompt = f"""
Запрос пользователя:
{query}

Контекст пользователя:
{hardware_context}

Поисковые запросы:
{search_queries}

Краткие резюме источников:
{summaries_text}

Сделай финальный краткий отчет.
"""

    try:
        report = ask_llm(FINAL_REPORT_SYSTEM, prompt, max_tokens=3200)
    except Exception as e:
        report = f"Ошибка генерации отчета: {e}"

    if not report or not report.strip():
        report = _fallback_report(query, collected, search_queries)

    if "## Что стоит сделать дальше" not in report:
        report += """

## Что стоит сделать дальше
- Проверить найденные источники вручную.
- Повторить исследование с более точным запросом.
- Использовать более сильную локальную модель для финального анализа.
"""

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = _safe_filename(query)
    path = f"Reports/{stamp}_{name}.md"

    write_file(path, report)

    return {
        "path": path,
        "report": report,
        "sources": all_links,
        "search_queries": search_queries,
        "source_summaries": source_summaries,
        "collected_count": len(collected)
    }
````

### ПУТЬ: modules/reviewer_bridge_ru.py (339 строк, 11049 байт)

````python
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

REVIEWER_BRIDGE_VERSION = "v6.77"

def _project_root() -> Path:
    for env_name in ("LOCALCOMET_ROOT", "LOCALCOMET_ROOT_DIR"):
        if env_name in os.environ:
            return Path(os.environ[env_name]).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


ROOT_DIR = _project_root()

REVIEWER_DIR = ROOT_DIR / ".localcomet" / "reviewer"
INBOX_DIR = REVIEWER_DIR / "inbox"
OUTBOX_DIR = REVIEWER_DIR / "outbox"
ARCHIVE_DIR = REVIEWER_DIR / "archive"
TEMPLATES_DIR = REVIEWER_DIR / "templates"

_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _ensure_dirs(*directories: Path) -> None:
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _auto_task_id() -> str:
    return "review_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _sanitize_task_id(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return _auto_task_id()

    raw = raw.strip()
    if ".." in raw or "/" in raw or "\\" in raw:
        return _auto_task_id()

    safe = "".join(char if char.isalnum() or char in "-_" else "_" for char in raw)
    safe = safe.strip(" ._-")
    safe = safe[:80]

    if not safe:
        return _auto_task_id()

    if safe.upper() in _WINDOWS_RESERVED_NAMES:
        safe = f"review_{safe.lower()}"

    return safe


def _candidate_paths(task_id: str) -> tuple[Path, Path, Path]:
    inbox_root = INBOX_DIR.resolve()
    paths = (
        INBOX_DIR / f"{task_id}_review_prompt.md",
        INBOX_DIR / f"{task_id}_validation_snapshot.json",
        INBOX_DIR / f"{task_id}_instructions.md",
    )

    for path in paths:
        if path.resolve().parent != inbox_root:
            raise ValueError("Reviewer path escaped the inbox directory.")

    return paths


def _allocate_task_id(requested: str) -> str:
    base = _sanitize_task_id(requested)
    candidate = base
    index = 2

    while any(path.exists() for path in _candidate_paths(candidate)):
        candidate = f"{base}_{index}"
        index += 1

    return candidate


def collect_validation_snapshot() -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {}

    try:
        from modules.computer_use_core_ru import dispatch as computer_use_dispatch

        result = computer_use_dispatch("pc computer contracts")
        summary = result.get("summary", {})
        snapshot["contracts"] = {
            "passed": summary.get("passed"),
            "total": summary.get("total"),
            "ok": result.get("ok"),
        }
    except Exception as exc:
        snapshot["contracts"] = {"error": f"{type(exc).__name__}: {exc}"}

    try:
        from modules.strict_project_stability_ru import dispatch as stability_dispatch

        result = stability_dispatch("проверь проект")
        snapshot["strict"] = {
            "ok": result.get("ok"),
            "hard_failures": result.get("hard_failures"),
            "warnings": result.get("warnings"),
        }
    except Exception as exc:
        snapshot["strict"] = {"error": f"{type(exc).__name__}: {exc}"}

    try:
        from modules.screenshot_capture_policy_ru import (
            is_screenshot_capture_enabled,
            should_allow_screenshot_write,
        )

        snapshot["screenshot"] = {
            "enabled": is_screenshot_capture_enabled(),
            "allow_write": should_allow_screenshot_write(),
        }
    except Exception as exc:
        snapshot["screenshot"] = {"error": f"{type(exc).__name__}: {exc}"}

    try:
        from modules.development_safety_orchestrator_ru import collect_diff_risk_snapshot

        snapshot["diff_risk"] = collect_diff_risk_snapshot()
    except Exception as exc:
        snapshot["diff_risk"] = {"error": f"{type(exc).__name__}: {exc}"}

    return snapshot


def _build_reviewer_prompt(task_id: str, patch_summary: str, snapshot: Dict[str, Any]) -> str:
    contracts = snapshot.get("contracts", {})
    strict = snapshot.get("strict", {})
    screenshot = snapshot.get("screenshot", {})
    diff_risk = snapshot.get("diff_risk", {})

    return "\n".join(
        [
            f"# Review Request: {task_id}",
            "",
            "## Patch Summary",
            patch_summary or "No summary provided.",
            "",
            "## Validation Snapshot",
            f"- Contracts: {contracts.get('passed')}/{contracts.get('total')} PASS (ok={contracts.get('ok')})",
            f"- Strict: ok={strict.get('ok')} hf={strict.get('hard_failures')} w={strict.get('warnings')}",
            f"- Screenshot enabled: {screenshot.get('enabled')}",
            f"- Screenshot allow_write: {screenshot.get('allow_write')}",
            f"- Diff risk verdict: {diff_risk.get('verdict')}",
            f"- Changed files: {diff_risk.get('source_changed')} source, {diff_risk.get('total_changed')} tracked",
            "",
            "## Expected Verdict Format",
            "Respond with exactly one of:",
            "- ACCEPT GREEN (all gates PASS, diff guard GREEN)",
            "- HOLD (gates PASS but diff guard requires review)",
            "- REJECT (gates FAIL or screenshot policy changed)",
            "",
            "## Rule",
            "Do not accept unless contracts, strict, screenshot policy, and diff guard are GREEN.",
            "",
        ]
    )


def _write_exclusive(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def create_reviewer_request(task_id: str = "", patch_summary: str = "") -> Dict[str, Any]:
    _ensure_dirs(INBOX_DIR)
    allocated_id = _allocate_task_id(task_id)
    snapshot = collect_validation_snapshot()
    prompt = _build_reviewer_prompt(allocated_id, patch_summary, snapshot)
    prompt_path, snapshot_path, instructions_path = _candidate_paths(allocated_id)

    created: list[Path] = []
    try:
        _write_exclusive(prompt_path, prompt)
        created.append(prompt_path)

        _write_exclusive(
            snapshot_path,
            json.dumps(snapshot, ensure_ascii=False, indent=2),
        )
        created.append(snapshot_path)

        instructions = (
            f"Instructions for task {allocated_id}:\n"
            f"1. Read the review prompt at {prompt_path.name}\n"
            f"2. Review the validation snapshot at {snapshot_path.name}\n"
            "3. Write your verdict to the outbox with task_id in filename.\n"
            "4. Verdict must be one of: ACCEPT GREEN, HOLD, REJECT.\n"
            "5. Do NOT auto-apply patches.\n"
        )
        _write_exclusive(instructions_path, instructions)
        created.append(instructions_path)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise

    return {
        "ok": True,
        "mode": "reviewer_request_created",
        "version": REVIEWER_BRIDGE_VERSION,
        "task_id": allocated_id,
        "files_created": [str(path) for path in (prompt_path, snapshot_path, instructions_path)],
        "note": "Review request created without overwriting existing artifacts.",
    }


def read_reviewer_verdict(task_id: str) -> Dict[str, Any]:
    safe_id = _sanitize_task_id(task_id)
    outbox_files = sorted(OUTBOX_DIR.glob(f"*{safe_id}*.md")) + sorted(
        OUTBOX_DIR.glob(f"*{safe_id}*.json")
    )

    if not outbox_files:
        return {
            "ok": True,
            "verdict_found": False,
            "note": "No verdict file found in outbox for this task_id.",
        }

    latest = max(outbox_files, key=lambda path: path.stat().st_mtime)
    text = latest.read_text(encoding="utf-8")
    return {
        "ok": True,
        "verdict_found": True,
        "task_id": safe_id,
        "file": str(latest),
        "text": text,
        "classification": classify_reviewer_verdict(text),
    }


def classify_reviewer_verdict(text: str) -> Dict[str, Any]:
    lower = str(text or "").lower()
    has_accept = "accept green" in lower
    has_hold = "hold" in lower
    has_reject = "reject" in lower

    if has_accept and not has_hold and not has_reject:
        return {"verdict": "ACCEPT_GREEN"}
    if has_hold and not has_accept and not has_reject:
        return {"verdict": "HOLD"}
    if has_reject and not has_accept and not has_hold:
        return {"verdict": "REJECT"}
    if sum((has_accept, has_hold, has_reject)) > 1:
        return {"verdict": "CONTRADICTORY"}
    return {"verdict": "UNKNOWN"}


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "reviewer_bridge_status",
        "version": REVIEWER_BRIDGE_VERSION,
        "inbox_count": len(list(INBOX_DIR.glob("*_review_prompt.md"))),
        "outbox_count": len(list(OUTBOX_DIR.glob("*"))),
        "template_count": len(list(TEMPLATES_DIR.glob("*"))),
    }


def report() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "reviewer_bridge_report",
        "version": REVIEWER_BRIDGE_VERSION,
        "generated_at": _now(),
        "status": status(),
    }


def is_reviewer_bridge_command(command: str = "") -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    return (
        lower in {
            "status",
            "reviewer bridge status",
            "статус ревью",
            "pc reviewer bridge status",
            "report",
            "reviewer bridge report",
            "pc reviewer bridge report",
        }
        or lower == "создай запрос ревью"
        or lower.startswith("создай запрос ревью ")
        or lower == "reviewer bridge create"
        or lower.startswith("reviewer bridge create ")
    )


def dispatch(command: str = "") -> Dict[str, Any]:
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")

    if lower in {
        "status",
        "reviewer bridge status",
        "статус ревью",
        "pc reviewer bridge status",
    }:
        return status()

    if lower in {"report", "reviewer bridge report", "pc reviewer bridge report"}:
        return report()

    prefixes = ("создай запрос ревью", "reviewer bridge create")
    for prefix in prefixes:
        if lower == prefix:
            return create_reviewer_request("")
        if lower.startswith(prefix + " "):
            return create_reviewer_request(text[len(prefix) :].strip())

    return {
        "ok": False,
        "mode": "reviewer_bridge_unrecognized",
        "version": REVIEWER_BRIDGE_VERSION,
        "result": (
            "Неизвестная команда. Используйте: создай запрос ревью [task_id], "
            "reviewer bridge create [task_id], статус ревью, reviewer bridge status"
        ),
    }
````

### ПУТЬ: modules/risk_classifier_ru.py (267 строк, 10224 байт)

````python
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


RISK_CLASSIFIER_VERSION = "v6.64"
RISK_CLASSIFIER_NAME = "LocalComet Risk Classifier RU"

ROOT_PATH = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_PATH / ".localcomet" / "agent"
RISK_CLASSIFIER_JSON = OUTPUT_DIR / "risk_classification.json"
RISK_CLASSIFIER_MD = OUTPUT_DIR / "risk_classification.md"
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"
CONTEXT_PACK_PATH = ROOT_PATH / ".localcomet" / "agent" / "context_pack.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _detect_base_version() -> str:
    try:
        for line in CONTROL_PANEL_PATH.read_text(encoding="utf-8").split("\n"):
            if "LOCALCOMET_VERSION" in line and "=" in line:
                return line.split("=")[-1].strip().strip("\"'")
    except Exception:
        pass
    return "unknown"


_CLASSIFIERS: List[Tuple[str, List[str], str]] = [
    ("docs_only", [
        "docs", "readme", "agients.md", "markdown", "documentation",
        "comment", "typo", "wording", "baseline", "cosmetic", ".md",
    ], "Task mentions only documentation, comments, or cosmetic text changes."),
    ("tests_only", [
        "test", "contract", "functional test", "regression",
        "test registration", "test coverage",
    ], "Task primarily mentions tests or test registration."),
    ("low", [
        "passive", "generator", "schema", "report", "template",
        "context pack", "plan contract", "artifact", "handoff",
    ], "Passive generator or schema-only addition. No runtime change."),
    ("medium", [
        "module creation", "dispatch integration", "control bridge",
        "command routing", "file writes", "bridge", "outer bridge",
        "control panel", "route",
    ], "Creates or wires a new module. Changes control flow."),
    ("high", [
        "runtime behavior", "automation", "execute", "subprocess",
        "agent invocation", "open code", "external agent",
        "network", "dependency", "installer", "install package",
        "security", "auth", "secrets", "credential",
        "delete", "deletion", "migration", "dangerous",
    ], "Changes runtime behavior, invokes external code, or touches security."),
]


_RISK_SCORE_MAP: Dict[str, int] = {
    "unclassified": 0,
    "docs_only": 1,
    "tests_only": 2,
    "low": 3,
    "medium": 5,
    "high": 8,
}

_RECOMMENDATIONS_MAP: Dict[str, List[str]] = {
    "unclassified": ["Provide a detailed task goal for accurate risk assessment."],
    "docs_only": ["Safe to proceed. No code runtime changes."],
    "tests_only": ["Safe to proceed. Tests do not alter production runtime behavior."],
    "low": ["Safe to proceed. Passive generator or schema-only addition."],
    "medium": ["Review control-flow changes before merging.", "Ensure contract tests cover the new route."],
    "high": ["Requires careful review.", "Verify safety checks before execution.", "Block automated GUI-only execution."],
}


def classify(task_goal: str) -> Dict[str, Any]:
    goal = str(task_goal or "").strip().lower()
    if not goal:
        return {
            "risk_level": "unclassified",
            "risk_score": _RISK_SCORE_MAP["unclassified"],
            "risk_reasons": ["No task goal provided. Risk cannot be assessed."],
        }
    matched_level = "unclassified"
    matched_reasons: List[str] = []
    for level, keywords, reason in _CLASSIFIERS:
        for kw in keywords:
            if kw in goal:
                matched_level = level
                matched_reasons.append(reason)
                break
    if not matched_reasons:
        matched_reasons.append("No risk classification keywords matched the task goal.")
    return {
        "risk_level": matched_level,
        "risk_score": _RISK_SCORE_MAP.get(matched_level, 0),
        "risk_reasons": matched_reasons,
    }


def generate(task_goal: str = "") -> Dict[str, Any]:
    base_version = _detect_base_version()
    result = classify(task_goal)
    context_pack_exists = CONTEXT_PACK_PATH.exists()
    context_pack_version = ""
    if context_pack_exists:
        try:
            cp = json.loads(CONTEXT_PACK_PATH.read_text(encoding="utf-8"))
            context_pack_version = cp.get("base_version", "")
        except Exception:
            pass
    return {
        "schema_version": "1.0",
        "project_name": "LocalComet",
        "base_version": base_version,
        "generated_at": _now(),
        "task_goal": task_goal,
        "risk_level": result["risk_level"],
        "risk_score": result.get("risk_score", 0),
        "risk_reasons": result["risk_reasons"],
        "recommendations": _RECOMMENDATIONS_MAP.get(result["risk_level"], []),
        "allowed_files": [],
        "forbidden_files": [
            "secrets",
            "credentials",
            "relay installer default workflow",
        ],
        "validation_intensity": "full_green_required",
        "required_gates": [
            "py_compile",
            "contract_tests",
            "functional_tests",
            "strict_project_stability",
        ],
        "review_requirements": [
            "explicit final GREEN status",
            "exact validation commands",
            "residual risks",
        ],
        "rollback_policy": {
            "restore_from_backup_if_any_gate_fails": True,
            "no_partial_green_claims": True,
        },
        "source_references": {
            "context_pack": {
                "path": str(CONTEXT_PACK_PATH.relative_to(ROOT_PATH)) if context_pack_exists else "",
                "exists": context_pack_exists,
                "base_version": context_pack_version,
            },
        },
    }


def _write_classification(payload: Dict[str, Any]) -> Dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RISK_CLASSIFIER_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# LocalComet Risk Classification",
        "",
        f"- schema_version: {payload.get('schema_version')}",
        f"- project_name: {payload.get('project_name')}",
        f"- base_version: {payload.get('base_version')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- risk_level: {payload.get('risk_level')}",
        f"- risk_score: {payload.get('risk_score', 0)}",
        "",
        "## Task Goal",
        "",
        f"{payload.get('task_goal', '')}",
        "",
        "## Risk Reasons",
        "",
    ]
    for rr in payload.get("risk_reasons", []):
        lines.append(f"- {rr}")
    lines.append("")
    lines.extend(["## Recommendations", ""])
    for rec in payload.get("recommendations", []):
        lines.append(f"- {rec}")
    lines.append("")
    lines.extend(["## Allowed Files", ""])
    for af in payload.get("allowed_files", []):
        lines.append(f"- {af}")
    lines.append("")
    lines.extend(["## Forbidden Files", ""])
    for ff in payload.get("forbidden_files", []):
        lines.append(f"- {ff}")
    lines.append("")
    lines.extend(["## Validation Intensity", "", f"{payload.get('validation_intensity', '')}", ""])
    lines.extend(["## Required Gates", ""])
    for rg in payload.get("required_gates", []):
        lines.append(f"- {rg}")
    lines.append("")
    lines.extend(["## Review Requirements", ""])
    for rr in payload.get("review_requirements", []):
        lines.append(f"- {rr}")
    lines.append("")
    lines.extend(["## Rollback Policy", ""])
    rp = payload.get("rollback_policy", {})
    if isinstance(rp, dict):
        for k, v in rp.items():
            lines.append(f"- {k}: {v}")
    lines.append("")
    lines.extend(["## Source References", ""])
    cp_ref = payload.get("source_references", {}).get("context_pack", {})
    if isinstance(cp_ref, dict) and cp_ref.get("exists"):
        lines.append(f"- context_pack.json: {cp_ref['path']} (base_version: {cp_ref.get('base_version', '')})")
    lines.append("")
    RISK_CLASSIFIER_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(RISK_CLASSIFIER_JSON.relative_to(ROOT_PATH)), "md": str(RISK_CLASSIFIER_MD.relative_to(ROOT_PATH))}


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "risk_classifier_status",
        "version": RISK_CLASSIFIER_VERSION,
        "json_exists": RISK_CLASSIFIER_JSON.exists(),
        "md_exists": RISK_CLASSIFIER_MD.exists(),
    }


def report(task_goal: str = "") -> Dict[str, Any]:
    payload = generate(task_goal)
    paths = _write_classification(payload)
    return {
        "ok": True,
        "mode": "risk_classifier_report",
        "version": RISK_CLASSIFIER_VERSION,
        "generated_at": _now(),
        "paths": paths,
    }


def is_risk_classifier_command(command: str) -> bool:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    return lowered in {
        "localcomet agent risk classify",
        "agent risk classify",
        "risk classify",
    } or lowered.startswith("localcomet agent risk classify ")


def dispatch(command: str) -> Dict[str, Any]:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    task_goal = ""
    if lowered in {"localcomet agent risk classify", "agent risk classify", "risk classify"}:
        task_goal = ""
    elif lowered.startswith("localcomet agent risk classify "):
        task_goal = command[len("localcomet agent risk classify "):].strip()
    elif lowered in {"localcomet agent risk classify status", "agent risk classify status", "risk classify status"}:
        return status()
    else:
        return {"ok": False, "mode": "risk_classifier_unknown", "version": RISK_CLASSIFIER_VERSION, "command": command, "hint": "Use: localcomet agent risk classify [task goal]"}
    result = report(task_goal)
    return {"ok": True, "handled": True, "mode": "risk_classifier_generated", "version": RISK_CLASSIFIER_VERSION, "paths": result.get("paths", {})}


if __name__ == "__main__":
    result = dispatch("localcomet agent risk classify")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
````

### ПУТЬ: modules/russian_command_context.py (258 строк, 10363 байт)

````python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
CONTEXT_REPORTS_DIR = REPORTS_DIR / "russian_command_context"
FEATURE_INVENTORY = PROJECTS_DIR / "FeatureVerification" / "feature_inventory_last_ok.json"


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(text, limit=3400):
    value = str(text or "")
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...[обрезано]"


def _load_feature_totals():
    if not FEATURE_INVENTORY.exists():
        return {}
    try:
        data = json.loads(FEATURE_INVENTORY.read_text(encoding="utf-8"))
        return data.get("totals", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def normalize_russian_agent_command(text):
    raw = str(text or "").strip()
    lower = raw.lower().replace("ё", "е")

    if not raw:
        return ""

    if lower.startswith(("pc ", "premium ", "native ", "task panel")):
        return raw

    feature_phrases = (
        "проверь новые функции",
        "проверить новые функции",
        "проверка новых функций",
        "автопроверка функций",
        "проверь функции",
        "проверить функции",
        "проверь введенные функции",
        "проверь внедренные функции",
        "проверь текущие функции",
    )
    if any(phrase in lower for phrase in feature_phrases):
        return "pc verify features"

    if "статус проверки" in lower or "статус функций" in lower:
        return "pc verify status"

    if "отчет проверки" in lower or "отчёт проверки" in lower:
        return "pc verify report"

    if "контекст" in lower and ("команд" in lower or "агент" in lower or "рус" in lower):
        return "pc context status"

    if lower.startswith(("объясни команду", "объяснить команду", "что значит команда")):
        return "pc context explain " + raw

    return ""


def explain_russian_intent(text):
    raw = str(text or "").strip()
    lower = raw.lower().replace("ё", "е")
    suggested = normalize_russian_agent_command(raw)

    intent = "chat"
    confidence = 0.35
    notes = []

    if suggested.startswith("pc verify"):
        intent = "feature_verification"
        confidence = 0.92
        notes.append("Запрос похож на проверку новых/изменённых функций проекта.")
    elif suggested.startswith("pc context"):
        intent = "command_context"
        confidence = 0.88
        notes.append("Запрос похож на работу с русским контекстом команд.")
    elif lower.startswith("pc "):
        intent = "direct_command"
        confidence = 0.95
        notes.append("Команда уже записана в формате pc.")
    elif any(word in lower for word in ["сделай", "создай", "исправь", "улучши", "добавь", "проверь", "проанализируй"]):
        intent = "task_request"
        confidence = 0.72
        notes.append("Похоже на задачу; в режиме Чат лучше предложить безопасную команду, а не запускать автоматически.")
    else:
        notes.append("Похоже на обычный чат; router запускать не нужно.")

    return {
        "ok": True,
        "mode": "russian_command_intent",
        "generated_at": _now(),
        "input": raw,
        "intent": intent,
        "confidence": confidence,
        "suggested_command": suggested,
        "router_allowed_by_default": False,
        "notes": notes,
    }


def build_russian_agent_context(message="", limit=5200):
    totals = _load_feature_totals()
    explained = explain_russian_intent(message)

    lines = [
        "Русский контекст LocalComet:",
        "",
        "Главное правило:",
        "- В режиме «Чат» обычный русский текст не запускает router/research.",
        "- В режиме «Команда» точные pc-команды отправляются в router.",
        "- Явный запуск из чата: `выполни: <задача>`.",
        "",
        "Новые команды проверки функций:",
        "- `pc verify features` — найти новые/изменённые функции, собрать inventory и выполнить автопроверку.",
        "- `pc verify status` — показать состояние feature verification.",
        "- `pc verify report` — создать отчёт проверки функций.",
        "",
        "Новые команды контекста:",
        "- `pc context status` — статус русского контекста.",
        "- `pc context explain <текст>` — объяснить намерение русской команды.",
        "- `pc context normalize <текст>` — предложить pc-команду.",
        "",
        "Понимание текущего сообщения:",
        f"- intent: {explained.get('intent')}",
        f"- confidence: {explained.get('confidence')}",
        f"- suggested_command: {explained.get('suggested_command') or 'нет'}",
        "",
        "Feature inventory:",
        f"- files: {totals.get('files', 'нет baseline')}",
        f"- functions: {totals.get('functions', 'нет baseline')}",
        f"- classes: {totals.get('classes', 'нет baseline')}",
        f"- command_modules: {totals.get('command_modules', 'нет baseline')}",
        "",
        "Как отвечать пользователю:",
        "- Если он просто общается — отвечай как обычный агент.",
        "- Если он просит проверить новые функции — предложи или используй `pc verify features` только при явном запуске.",
        "- Если он просит выполнить действие — не говори, что уже выполнил; предложи безопасную команду.",
        "- Отвечай по-русски и без JSON, если пользователь явно не просит технический отчёт.",
    ]

    return _short("\n".join(lines), limit)


def status():
    totals = _load_feature_totals()
    return {
        "ok": True,
        "mode": "russian_command_context_status",
        "generated_at": _now(),
        "language": "ru",
        "context_for_agent_commands": True,
        "plain_chat_router_disabled": True,
        "feature_verification_commands": True,
        "feature_inventory_totals": totals,
        "commands": [
            "pc context status",
            "pc context report",
            "pc context explain <текст>",
            "pc context normalize <текст>",
            "pc verify features",
        ],
    }


def report():
    CONTEXT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CONTEXT_REPORTS_DIR / f"russian_command_context_{_stamp()}.md"
    lines = [
        "# Russian Command Context",
        "",
        build_russian_agent_context("проверь новые функции", limit=9000),
        "",
        "## Status",
        "",
        "```json",
        json.dumps(status(), ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "ok": True,
        "mode": "russian_command_context_report",
        "generated_at": _now(),
        "report": str(path),
    }


def dispatch(command):
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")

    if lower in {"pc context", "pc context status", "контекст команд", "статус контекста"}:
        return json.dumps(status(), ensure_ascii=False, indent=2)

    if lower in {"pc context report", "отчет контекста", "отчёт контекста"}:
        return json.dumps(report(), ensure_ascii=False, indent=2)

    if lower.startswith("pc context explain "):
        payload = explain_russian_intent(text[len("pc context explain "):])
        return json.dumps(payload, ensure_ascii=False, indent=2)

    if lower.startswith("pc context normalize "):
        source = text[len("pc context normalize "):]
        return json.dumps(
            {
                "ok": True,
                "mode": "russian_command_context_normalize",
                "generated_at": _now(),
                "input": source,
                "suggested_command": normalize_russian_agent_command(source),
                "intent": explain_russian_intent(source),
            },
            ensure_ascii=False,
            indent=2,
        )

    return json.dumps(
        {
            "ok": False,
            "mode": "russian_command_context_unknown_command",
            "generated_at": _now(),
            "error": "Неизвестная команда русского контекста.",
            "commands": status().get("commands", []),
        },
        ensure_ascii=False,
        indent=2,
    )


def is_russian_command_context_command(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower.startswith("pc context") or lower in {
        "контекст команд",
        "статус контекста",
        "отчет контекста",
        "отчёт контекста",
    }
````

### ПУТЬ: modules/safety_cleanup_center.py (472 строк, 15875 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import re
import shutil
import subprocess
import traceback


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
SAFETY_REPORTS_DIR = REPORTS_DIR / "safety_cleanup"
SELF_EDIT_DIR = PROJECTS_DIR / "SelfEdit"
CLEANUP_QUARANTINE_DIR = PROJECTS_DIR / "CleanupQuarantine"

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "BrowserProfile",
    "VoiceModels",
    "Reports",
    "Logs",
    "LocalAgent_Backups",
}

SENSITIVE_NAME_PATTERNS = [
    ".env",
    "secret",
    "token",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "private_key",
    ".pem",
    ".key",
]

DANGEROUS_PATTERNS = [
    ("shell_true", re.compile(r"shell\s*=\s*True")),
    ("rmtree", re.compile(r"\bshutil\.rmtree\s*\(")),
    ("unlink", re.compile(r"\.unlink\s*\(")),
    ("remove", re.compile(r"\bos\.remove\s*\(")),
    ("rmdir", re.compile(r"\bos\.rmdir\s*\(")),
    ("pyautogui", re.compile(r"\bpyautogui\.")),
    ("subprocess_popen", re.compile(r"\bsubprocess\.Popen\s*\(")),
    ("subprocess_run", re.compile(r"\bsubprocess\.run\s*\(")),
    ("keyboard_enter", re.compile(r"press\s*\(\s*['\"]enter['\"]\s*\)|hotkey\s*\([^)]*enter")),
    ("clipboard_paste", re.compile(r"pyperclip\.paste|clipboard")),
]


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value, limit=2200):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[обрезано]"


def _is_excluded(path: Path):
    parts = set(path.parts)
    return bool(parts.intersection(EXCLUDED_DIR_NAMES))


def _safe_relative(path: Path):
    try:
        return str(path.relative_to(ROOT_DIR))
    except Exception:
        return str(path)


def _iter_project_files():
    for path in ROOT_DIR.rglob("*"):
        if _is_excluded(path):
            continue
        if path.is_file():
            yield path


def _file_size_mb(path: Path):
    try:
        return round(path.stat().st_size / (1024 * 1024), 3)
    except Exception:
        return 0.0


def _git_status():
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=25,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except Exception:
        return {"ok": False, "error": traceback.format_exc()}


def find_cleanup_candidates():
    candidates = []

    if (ROOT_DIR / ".git").exists():
        candidates.append({
            "kind": "archive_exclude",
            "path": ".git",
            "action": "exclude_from_audit_zip",
            "reason": "Git history is large and should not be uploaded inside audit archives.",
        })

    for folder_name in ["Reports", "Logs"]:
        folder = PROJECTS_DIR / folder_name
        if folder.exists():
            candidates.append({
                "kind": "runtime_artifacts",
                "path": _safe_relative(folder),
                "action": "keep_latest_or_exclude_from_zip",
                "reason": "Runtime reports/logs grow quickly and are not required in code patches.",
            })

    if SELF_EDIT_DIR.exists():
        patch_files = sorted(
            [p for p in SELF_EDIT_DIR.glob("patch_*.json") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        rollback_files = sorted(
            [p for p in SELF_EDIT_DIR.glob("rollback_*.json") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for index, path in enumerate(patch_files):
            candidates.append({
                "kind": "selfedit_patch",
                "path": _safe_relative(path),
                "action": "keep" if index < 10 else "quarantine",
                "reason": "Keep the latest 10 patch files; quarantine older patch history.",
                "size_mb": _file_size_mb(path),
            })

        for index, path in enumerate(rollback_files):
            candidates.append({
                "kind": "selfedit_rollback",
                "path": _safe_relative(path),
                "action": "keep" if index < 10 else "quarantine",
                "reason": "Keep the latest 10 rollback files; quarantine older rollback history.",
                "size_mb": _file_size_mb(path),
            })

    for path in _iter_project_files():
        name = path.name.lower()
        if any(pattern in name for pattern in SENSITIVE_NAME_PATTERNS):
            candidates.append({
                "kind": "sensitive_name",
                "path": _safe_relative(path),
                "action": "review_do_not_upload",
                "reason": "Filename looks sensitive. Review manually before sharing.",
                "size_mb": _file_size_mb(path),
            })

    return candidates


def find_dangerous_places():
    findings = []

    for path in _iter_project_files():
        if path.suffix.lower() not in {".py", ".ps1", ".bat", ".cmd"}:
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            for name, pattern in DANGEROUS_PATTERNS:
                if pattern.search(line):
                    findings.append({
                        "kind": name,
                        "path": _safe_relative(path),
                        "line": line_no,
                        "code": stripped[:260],
                        "severity": _severity_for_finding(name, path),
                        "recommendation": _recommendation_for_finding(name),
                    })

    return findings


def _severity_for_finding(kind, path):
    critical = {"shell_true", "rmtree", "unlink", "remove", "rmdir", "keyboard_enter"}
    if path.name == "agent.py":
        return "high"
    if kind in critical:
        return "high"
    if kind in {"pyautogui", "subprocess_popen", "subprocess_run"}:
        return "medium"
    return "low"


def _recommendation_for_finding(kind):
    recommendations = {
        "shell_true": "Replace shell=True with an allowlisted subprocess call.",
        "rmtree": "Do not delete directly; move to CleanupQuarantine or require explicit confirmation.",
        "unlink": "Do not delete directly; move to CleanupQuarantine or require explicit confirmation.",
        "remove": "Do not delete directly; move to CleanupQuarantine or require explicit confirmation.",
        "rmdir": "Do not delete directly; move to CleanupQuarantine or require explicit confirmation.",
        "pyautogui": "Keep behind safety guards; block payment/login/destructive actions.",
        "subprocess_popen": "Use allowlists and avoid shell=True.",
        "subprocess_run": "Use allowlists and timeouts.",
        "keyboard_enter": "Never press Enter automatically unless the workflow is explicitly safe.",
        "clipboard_paste": "Do not paste private data; log intent only.",
    }
    return recommendations.get(kind, "Review manually.")


def audit_project():
    files = list(_iter_project_files())
    python_files = [p for p in files if p.suffix.lower() == ".py"]
    html_files = [p for p in files if p.suffix.lower() == ".html"]
    md_files = [p for p in files if p.suffix.lower() == ".md"]

    large_files = sorted(
        [
            {
                "path": _safe_relative(path),
                "size_mb": _file_size_mb(path),
            }
            for path in files
            if _file_size_mb(path) >= 1
        ],
        key=lambda item: item["size_mb"],
        reverse=True,
    )[:30]

    dangerous = find_dangerous_places()
    cleanup = find_cleanup_candidates()

    payload = {
        "status": "attention" if dangerous or any(item.get("action") == "quarantine" for item in cleanup) else "ok",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT_DIR),
        "counts": {
            "files": len(files),
            "python": len(python_files),
            "html": len(html_files),
            "markdown": len(md_files),
        },
        "large_files": large_files,
        "cleanup_candidates": cleanup,
        "dangerous_places": dangerous,
        "git": _git_status(),
        "recommendations": [
            "Keep LocalComet_Control_Panel.py stable; move new features into modules when possible.",
            "Prefer quarantine over deletion for cleanup.",
            "Keep Voice disabled unless explicitly needed.",
            "Avoid shell=True and direct delete operations.",
            "Keep latest 10 SelfEdit patch/rollback files; quarantine older ones.",
        ],
    }
    return payload


def format_project_audit(payload):
    counts = payload.get("counts", {})
    cleanup = payload.get("cleanup_candidates", [])
    dangerous = payload.get("dangerous_places", [])
    large = payload.get("large_files", [])

    lines = [
        "Safety Cleanup Audit:",
        f"- status: {payload.get('status')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- root: {payload.get('root')}",
        "",
        "Файлы:",
        f"- total: {counts.get('files')}",
        f"- python: {counts.get('python')}",
        f"- html: {counts.get('html')}",
        f"- markdown: {counts.get('markdown')}",
        "",
        "Что можно почистить:",
    ]

    if cleanup:
        for item in cleanup[:35]:
            lines.append(f"- [{item.get('action')}] {item.get('path')} — {item.get('reason')}")
        if len(cleanup) > 35:
            lines.append(f"- ...и еще {len(cleanup) - 35} пунктов")
    else:
        lines.append("- Явных кандидатов нет.")

    lines.append("")
    lines.append("Опасные места:")

    if dangerous:
        for item in dangerous[:45]:
            lines.append(
                f"- [{item.get('severity')}] {item.get('path')}:{item.get('line')} "
                f"{item.get('kind')} — {item.get('recommendation')}"
            )
            lines.append(f"  {item.get('code')}")
        if len(dangerous) > 45:
            lines.append(f"- ...и еще {len(dangerous) - 45} мест")
    else:
        lines.append("- Не обнаружены.")

    lines.append("")
    lines.append("Большие файлы:")
    if large:
        for item in large[:15]:
            lines.append(f"- {item.get('size_mb')} MB — {item.get('path')}")
    else:
        lines.append("- Нет файлов больше 1 MB.")

    lines.append("")
    lines.append("Рекомендации:")
    for item in payload.get("recommendations", []):
        lines.append("- " + item)

    return "\n".join(lines)


def cleanup_old_selfedit_files(keep_latest=10, dry_run=False):
    keep_latest = max(1, int(keep_latest or 10))
    CLEANUP_QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    target_dir = CLEANUP_QUARANTINE_DIR / f"selfedit_{_stamp()}"
    actions = []

    if not SELF_EDIT_DIR.exists():
        return {
            "ok": True,
            "dry_run": dry_run,
            "moved": 0,
            "actions": [],
            "message": "SelfEdit folder not found.",
        }

    files = []
    files.extend(sorted(SELF_EDIT_DIR.glob("patch_*.json"), key=lambda p: p.stat().st_mtime, reverse=True))
    files.extend(sorted(SELF_EDIT_DIR.glob("rollback_*.json"), key=lambda p: p.stat().st_mtime, reverse=True))

    groups = {}
    for path in files:
        prefix = "patch" if path.name.startswith("patch_") else "rollback"
        groups.setdefault(prefix, []).append(path)

    to_move = []
    for group_files in groups.values():
        to_move.extend(group_files[keep_latest:])

    if to_move and not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    for path in to_move:
        dest = target_dir / path.name
        action = {
            "source": _safe_relative(path),
            "destination": _safe_relative(dest),
            "dry_run": dry_run,
            "size_mb": _file_size_mb(path),
        }

        if not dry_run:
            shutil.move(str(path), str(dest))

        actions.append(action)

    return {
        "ok": True,
        "dry_run": dry_run,
        "keep_latest": keep_latest,
        "moved": 0 if dry_run else len(actions),
        "would_move": len(actions) if dry_run else 0,
        "quarantine_dir": _safe_relative(target_dir) if to_move else "",
        "actions": actions,
    }


def create_cleanup_report(apply_cleanup=False, dry_run=True):
    SAFETY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    audit = audit_project()
    cleanup_result = cleanup_old_selfedit_files(keep_latest=10, dry_run=(dry_run or not apply_cleanup))

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "apply_cleanup": bool(apply_cleanup),
        "dry_run": bool(dry_run or not apply_cleanup),
        "audit": audit,
        "cleanup_result": cleanup_result,
    }

    stamp = _stamp()
    json_path = SAFETY_REPORTS_DIR / f"safety_cleanup_{stamp}.json"
    md_path = SAFETY_REPORTS_DIR / f"safety_cleanup_{stamp}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# LocalComet Safety Cleanup Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- apply_cleanup: {payload['apply_cleanup']}",
        f"- dry_run: {payload['dry_run']}",
        "",
        "## Audit",
        "",
        "```text",
        format_project_audit(audit),
        "```",
        "",
        "## SelfEdit cleanup",
        "",
        "```json",
        json.dumps(cleanup_result, ensure_ascii=False, indent=2),
        "```",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return {
        "ok": True,
        "report": str(md_path),
        "json": str(json_path),
        "status": audit.get("status"),
        "cleanup": cleanup_result,
        "dangerous_count": len(audit.get("dangerous_places", [])),
        "cleanup_candidates": len(audit.get("cleanup_candidates", [])),
    }


def format_cleanup_report_result(payload):
    lines = [
        "Safety Cleanup Report:",
        f"- ok: {payload.get('ok')}",
        f"- status: {payload.get('status')}",
        f"- report: {payload.get('report')}",
        f"- json: {payload.get('json')}",
        f"- dangerous_count: {payload.get('dangerous_count')}",
        f"- cleanup_candidates: {payload.get('cleanup_candidates')}",
        "",
        "SelfEdit cleanup:",
    ]

    cleanup = payload.get("cleanup", {})
    lines.append(f"- dry_run: {cleanup.get('dry_run')}")
    lines.append(f"- moved: {cleanup.get('moved')}")
    lines.append(f"- would_move: {cleanup.get('would_move')}")
    lines.append(f"- quarantine_dir: {cleanup.get('quarantine_dir')}")

    return "\n".join(lines)
````

### ПУТЬ: modules/screenshot_capture_policy_ru.py (255 строк, 10140 байт)

````python
from pathlib import Path
from typing import Dict, Any
import time

# Configuration
SCREENSHOT_DIR = Path("Projects/Reports/desktop_observer/screenshots")
MAX_STORAGE_GB = 30.0
ENABLE_BY_DEFAULT = False


def get_screenshot_storage_status() -> Dict[str, Any]:
    """Получает статус хранилища скриншотов с подробной информацией."""
    status: Dict[str, Any] = {
        "mode": "screenshot_capture_policy",
        "version": "v6.65b",
        "enabled_by_default": ENABLE_BY_DEFAULT,
        "config_status": "dry_run_only",
        "dangerous_size_detected": False,
        "newest_screenshot_timestamp": None,
        "warning_message": None,
    }

    # Check if directory exists and is accessible
    if not SCREENSHOT_DIR.exists():
        status["directory_exists"] = False
        status["warning_message"] = (
            "Папка для скриншотов не существует. "
            "Сценарий локализации: `mkdir -p Projects/Reports/desktop_observer/screenshots`"
        )
        return status

    status["directory_exists"] = True

    # Get file list and information
    try:
        bmp_files = list(SCREENSHOT_DIR.glob("*.bmp"))
        png_files = list(SCREENSHOT_DIR.glob("*.png"))

        status["bmp_file_count"] = len(bmp_files)
        status["png_file_count"] = len(png_files)
        status["total_file_count"] = len(bmp_files) + len(png_files)

        # Calculate size
        total_size_bytes = 0
        for f in bmp_files + png_files:
            total_size_bytes += f.stat().st_size

        status["total_size_bytes"] = total_size_bytes
        status["total_size_mb"] = round(total_size_bytes / (1024 * 1024), 2)
        status["total_size_gb"] = round(total_size_bytes / (1024 * 1024 * 1024), 2)

        # Detect dangerous size
        status["dangerous_size_detected"] = status["total_size_gb"] > MAX_STORAGE_GB

        # Get newest timestamp
        if bmp_files:
            newest_bmp = max(bmp_files, key=lambda f: f.stat().st_mtime)
            newest_timestamp = newest_bmp.stat().st_mtime
            status["newest_screenshot_timestamp"] = newest_timestamp

            # Get human-readable timestamp
            status["newest_screenshot_age_hours"] = round(
                (time.time() - newest_timestamp) / 3600, 1
            )

        if png_files:
            newest_png = max(png_files, key=lambda f: f.stat().st_mtime)
            newest_timestamp = newest_png.stat().st_mtime
            status["newest_screenshot_timestamp"] = newest_timestamp
            status["newest_screenshot_age_hours"] = round(
                (time.time() - newest_timestamp) / 3600, 1
            )

        # Determine warning message
        if status["dangerous_size_detected"]:
            status["warning_message"] = (
                f"Опасное накопление скриншотов: {status['total_size_gb']} ГБ > {MAX_STORAGE_GB} ГБ. "
                "Капсуляция отключена, чтобы предотвратить исчерпание дискового пространства."
            )
        elif status["total_file_count"] > 1000:
            status["warning_message"] = (
                f"Обширная коллекция скриншотов: {status['total_file_count']} файлов, {status['total_size_gb']} ГБ. "
                "Рекомендуется очистка старых скриншотов."
            )
        elif not ENABLE_BY_DEFAULT:
            status["warning_message"] = (
                "Капсуляция скриншотов отключена по умолчанию. "
                "Для разрешенного захвата выполните: `config enable screenshot capture`"
            )

    except Exception as exc:
        status["directory_error"] = str(exc)
        status["warning_message"] = f"Ошибка при проверке скриншотов: {exc}"

    return status


def is_screenshot_capture_enabled() -> bool:
    """Проверяет, разрешена ли капсуляция скриншотов."""
    return ENABLE_BY_DEFAULT


def should_allow_screenshot_write() -> Dict[str, Any]:
    """
    Проверяет, можно ли писать скриншоты.

    Returns:
        Dict with keys:
        - allow: bool - whether screenshot can be written
        - reason: str - explanation
        - mode: str - "enabled", "dry_run", "blocked", "dangerous", "error"
    """
    if not ENABLE_BY_DEFAULT:
        return {
            "allow": False,
            "reason": "Капсуляция скриншотов отключена по умолчанию.",
            "mode": "blocked",
            "config_action": "set ENABLE_BY_DEFAULT = True to allow",
        }

    # If default is enabled, but directory is dangerous, block
    try:
        if SCREENSHOT_DIR.exists():
            bmp_files = list(SCREENSHOT_DIR.glob("*.bmp"))
            png_files = list(SCREENSHOT_DIR.glob("*.png"))

            total_files = len(bmp_files) + len(png_files)
            total_size_gb = sum(f.stat().st_size for f in bmp_files + png_files) / (1024 * 1024 * 1024)

            if total_size_gb > MAX_STORAGE_GB:
                return {
                    "allow": False,
                    "reason": f"Опасный размер хранилища: {total_size_gb:.2f} ГБ > {MAX_STORAGE_GB} ГБ.",
                    "mode": "dangerous",
                    "size_gb": round(total_size_gb, 2),
                    "max_gb": MAX_STORAGE_GB,
                }

        return {
            "allow": True,
            "reason": "Капсуляция скриншотов разрешена (режим dry-run/симуляции).",
            "mode": "dry_run",
        }

    except Exception as exc:
        return {
            "allow": False,
            "reason": f"Ошибка при проверке хранилища скриншотов: {exc}",
            "mode": "error",
            "error": str(exc),
        }


def status() -> Dict[str, Any]:
    """Возвращает статус модуля политики капсуляции скриншотов."""
    return {
        "ok": True,
        "mode": "screenshot_capture_policy_status",
        "version": "v6.65b",
        "enabled": is_screenshot_capture_enabled(),
        "allow_write": should_allow_screenshot_write(),
    }


def report() -> Dict[str, Any]:
    """Возвращает отчёт о состоянии хранилища скриншотов."""
    return get_screenshot_storage_status()


def dispatch(command: str) -> Dict[str, Any]:
    """Обработчик команд для маршрутизации."""
    normalized = str(command or "").strip().lower().replace("ё", "е")

    if normalized in {
        "статус скриншотов",
        "status screenshots",
        "screenshot storage status",
        "скриншоты статус",
        "screenshot status",
    }:
        return {
            "mode": "command",
            "route": "modules.screenshot_capture_policy_ru",
            "plan": {"tool": "modules.screenshot_capture_policy_ru", "action": "dispatch"},
            "result": get_screenshot_storage_status(),
        }

    return {
        "ok": False,
        "mode": "screenshot_capture_policy",
        "version": "v6.65b",
        "message": f"Неизвестная команда: {command}",
    }


def is_screenshot_capture_policy_command(command: str) -> bool:
    """Проверяет, является ли команда командой для работы с политикой капсуляции скриншотов."""
    if not isinstance(command, str):
        return False

    normalized = command.strip().lower().replace("ё", "е")
    return normalized in {
        "статус скриншотов",
        "status screenshots",
        "screenshot storage status",
        "скриншоты статус",
        "screenshot status",
    }


def enable_capture() -> Dict[str, Any]:
    """Включает капсуляцию скриншотов (должно выполняться с осторожностью)."""
    global ENABLE_BY_DEFAULT
    previous = ENABLE_BY_DEFAULT
    try:
        ENABLE_BY_DEFAULT = True

        # Проверить дисковое пространство перед включением
        if SCREENSHOT_DIR.exists():
            total_size_gb = sum(f.stat().st_size for f in SCREENSHOT_DIR.glob("*.bmp")) / (1024 * 1024 * 1024)

            if total_size_gb > MAX_STORAGE_GB:
                ENABLE_BY_DEFAULT = previous

                return {
                    "ok": False,
                    "mode": "screenshot_capture_policy",
                    "version": "v6.65b",
                    "message": (
                        f"Невозможно включить капсуляцию: опасный размер хранилища {total_size_gb:.2f} ГБ. "
                        "Для очистки выполните manual cleanup или введите конфигурацию для сброса."
                    ),
                    "action": "block",
                    "reason": "dangerous_storage_size",
                    "size_gb": round(total_size_gb, 2),
                    "max_gb": MAX_STORAGE_GB,
                }

        return {
            "ok": True,
            "mode": "screenshot_capture_policy",
            "version": "v6.65b",
            "message": "Капсуляция скриншотов включена.",
            "previous_status": "disabled",
            "current_status": "enabled",
        }
    except Exception as exc:
        ENABLE_BY_DEFAULT = previous
        return {
            "ok": False,
            "mode": "screenshot_capture_policy",
            "version": "v6.65b",
            "message": f"Ошибка при включении капсуляции скриншотов: {str(exc)}",
            "exception": str(exc),
        }
````

### ПУТЬ: modules/screenshot_retention_dry_run_ru.py (112 строк, 4667 байт)

````python
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from modules.project_paths import build_retention_plan, get_project_root, localcomet_reports_dir, retention_runtime_roots

ROOT_PATH = get_project_root()
REPORT_DIR = localcomet_reports_dir(ROOT_PATH)
POLICY_DIR = ROOT_PATH / ".localcomet" / "policies"
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _base_version() -> str:
    try:
        for line in CONTROL_PANEL_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("LOCALCOMET_VERSION"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    return parts[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "unknown"

def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_PATH)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")

def _screenshot_dirs() -> List[Path]:
    return [
        ROOT_PATH / "Projects" / "Reports" / "desktop_observer" / "screenshots",
        ROOT_PATH / "Projects" / "Reports" / "browser_screenshots",
    ]

def _iter_files(directory: Path) -> List[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    result: List[Path] = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git"}]
        for name in files:
            try:
                p = Path(root) / name
                if p.is_file():
                    result.append(p)
            except Exception:
                continue
    return result

def _file_info(path: Path) -> Dict[str, Any]:
    st = path.stat()
    return {
        "path": _rel(path),
        "size_bytes": int(st.st_size),
        "size_mb": round(st.st_size / (1024 * 1024), 4),
        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
    }

def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

SCREENSHOT_RETENTION_DRY_RUN_VERSION = "v6.79"
SCREENSHOT_RETENTION_DRY_RUN_NAME = "LocalComet Screenshot Retention Dry Run RU"
DRY_RUN_JSON = REPORT_DIR / "screenshot_retention_dry_run.json"
DRY_RUN_MD = REPORT_DIR / "screenshot_retention_dry_run.md"

def scan() -> Dict[str, Any]:
    return build_retention_plan(ROOT_PATH, retention_runtime_roots(ROOT_PATH))

def _write_md(payload: Dict[str, Any]) -> None:
    lines = [
        "# Runtime Retention Dry Run",
        f"- mode: {payload.get('mode')}",
        f"- version: {payload.get('version')}",
        f"- dry_run: {payload.get('dry_run')}",
        f"- candidate_count: {payload.get('totals', {}).get('candidate_count')}",
        f"- protected_count: {payload.get('totals', {}).get('protected_count')}",
        f"- rejected_count: {payload.get('totals', {}).get('rejected_count')}",
        "",
        "NO FILES WERE DELETED. This is a deterministic dry-run-only plan.",
    ]
    DRY_RUN_MD.parent.mkdir(parents=True, exist_ok=True)
    DRY_RUN_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

def report() -> Dict[str, Any]:
    payload = scan()
    _write_json(DRY_RUN_JSON, payload)
    _write_md(payload)
    return {"ok": True, "handled": True, "mode": "screenshot_retention_dry_run_generated", "version": SCREENSHOT_RETENTION_DRY_RUN_VERSION, "paths": {"json": _rel(DRY_RUN_JSON), "md": _rel(DRY_RUN_MD)}, "summary": payload.get("totals", {})}

def status() -> Dict[str, Any]:
    return {"ok": True, "mode": "screenshot_retention_dry_run_status", "version": SCREENSHOT_RETENTION_DRY_RUN_VERSION, "json": _rel(DRY_RUN_JSON), "md": _rel(DRY_RUN_MD)}

def is_screenshot_retention_dry_run_command(command: str) -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {"localcomet screenshots retention dry run", "screenshots retention dry run", "screenshot dry run", "localcomet screenshots retention dry-run"}

def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if "status" in lower:
        return status()
    if is_screenshot_retention_dry_run_command(command) or not lower:
        return report()
    return {"ok": False, "handled": False, "mode": "screenshot_retention_dry_run_unhandled", "version": SCREENSHOT_RETENTION_DRY_RUN_VERSION, "command": command}
````

### ПУТЬ: modules/screenshot_retention_policy_config_ru.py (166 строк, 7498 байт)

````python
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from modules.project_paths import get_project_root, localcomet_policies_dir, localcomet_reports_dir

ROOT_PATH = get_project_root()
REPORT_DIR = localcomet_reports_dir(ROOT_PATH)
POLICY_DIR = localcomet_policies_dir(ROOT_PATH)
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _base_version() -> str:
    try:
        for line in CONTROL_PANEL_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("LOCALCOMET_VERSION"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    return parts[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "unknown"

def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_PATH)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")

def _screenshot_dirs() -> List[Path]:
    return [
        ROOT_PATH / "Projects" / "Reports" / "desktop_observer" / "screenshots",
        ROOT_PATH / "Projects" / "Reports" / "browser_screenshots",
    ]

def _iter_files(directory: Path) -> List[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    result: List[Path] = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git"}]
        for name in files:
            try:
                p = Path(root) / name
                if p.is_file():
                    result.append(p)
            except Exception:
                continue
    return result

def _file_info(path: Path) -> Dict[str, Any]:
    st = path.stat()
    return {
        "path": _rel(path),
        "size_bytes": int(st.st_size),
        "size_mb": round(st.st_size / (1024 * 1024), 4),
        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
    }

def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION = "v6.64e"
SCREENSHOT_RETENTION_POLICY_CONFIG_NAME = "LocalComet Screenshot Retention Policy Config RU"
SIMULATION_JSON = REPORT_DIR / "screenshot_storage_policy_simulation.json"
POLICY_JSON = POLICY_DIR / "screenshot_retention_policy.json"
POLICY_MD = POLICY_DIR / "screenshot_retention_policy.md"

def _load_simulation() -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    if not SIMULATION_JSON.exists():
        warnings.append("simulation source not found")
        return {}, warnings
    try:
        return json.loads(SIMULATION_JSON.read_text(encoding="utf-8")), warnings
    except Exception as e:
        warnings.append(f"invalid simulation source: {e}")
        return {}, warnings

def generate() -> Dict[str, Any]:
    sim, warnings = _load_simulation()
    selected = "keep_newest_500_per_directory"
    expected = 0.0
    for item in sim.get("simulated_policies", []) if isinstance(sim, dict) else []:
        if item.get("policy_name") == selected:
            expected = item.get("estimated_reclaimable_gb", 0.0)
            break
    return {
        "schema_version": "1.0",
        "project_name": "LocalComet",
        "base_version": _base_version(),
        "generated_at": _now(),
        "cleanup_mode": "policy_config_only",
        "deletion_enabled": False,
        "manual_approval_required": True,
        "selected_policy": selected,
        "selected_policy_reason": "Conservative storage cap that preserves recent debugging screenshots while reducing growth.",
        "screenshot_directories": sim.get("screenshot_directories", []) if isinstance(sim, dict) else [],
        "policy_limits": {
            "keep_newest_per_directory": 500,
            "keep_younger_than_days": None,
            "max_total_gb": None,
            "max_gb_per_directory": None,
        },
        "expected_reclaimable_gb_from_latest_simulation": expected,
        "simulation_summary": {
            "total_screenshot_files": sim.get("total_screenshot_files", 0) if isinstance(sim, dict) else 0,
            "total_screenshot_size_gb": sim.get("total_screenshot_size_gb", 0.0) if isinstance(sim, dict) else 0.0,
            "recommended_policy": sim.get("recommended_policy", "") if isinstance(sim, dict) else "",
        },
        "enforcement_status": {
            "active": False,
            "reason": "Policy is recorded but not enforced. Cleanup requires a separate explicit manual cleanup command.",
        },
        "dangerous_cleanup_warning": "NO FILES WERE DELETED. This policy is recorded only. Cleanup requires separate explicit approval.",
        "next_safe_action": "Review policy, then implement a separate manual cleanup command only with explicit approval.",
        "source_references": [_rel(SIMULATION_JSON), "LocalComet_Control_Panel.py"],
        "warnings": warnings,
    }

def _write_md(payload: Dict[str, Any]) -> None:
    lines = [
        "# Screenshot Retention Policy",
        f"- base_version: {payload.get('base_version')}",
        f"- cleanup_mode: {payload.get('cleanup_mode')}",
        f"- deletion_enabled: {payload.get('deletion_enabled')}",
        f"- manual_approval_required: {payload.get('manual_approval_required')}",
        f"- selected_policy: {payload.get('selected_policy')}",
        f"- expected_reclaimable_gb_from_latest_simulation: {payload.get('expected_reclaimable_gb_from_latest_simulation')}",
        f"- enforcement_status.active: {payload.get('enforcement_status', {}).get('active')}",
        "",
        payload.get("dangerous_cleanup_warning", ""),
    ]
    POLICY_MD.parent.mkdir(parents=True, exist_ok=True)
    POLICY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

def write() -> Dict[str, Any]:
    payload = generate()
    _write_json(POLICY_JSON, payload)
    _write_md(payload)
    return {"ok": True, "handled": True, "mode": "screenshot_retention_policy_config_written", "version": SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION, "paths": {"json": _rel(POLICY_JSON), "md": _rel(POLICY_MD)}, "summary": {"selected_policy": payload["selected_policy"], "deletion_enabled": payload["deletion_enabled"]}}

def report() -> Dict[str, Any]:
    return write()

def status() -> Dict[str, Any]:
    return {"ok": True, "mode": "screenshot_retention_policy_config_status", "version": SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION, "json": _rel(POLICY_JSON), "md": _rel(POLICY_MD)}

def is_screenshot_retention_policy_config_command(command: str) -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {"localcomet screenshots retention policy write", "screenshots retention policy write", "retention policy write", "localcomet screenshots retention policy status"}

def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if "status" in lower:
        return status()
    if is_screenshot_retention_policy_config_command(command) or not lower:
        return write()
    return {"ok": False, "handled": False, "mode": "screenshot_retention_policy_config_unhandled", "version": SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION, "command": command}
````

### ПУТЬ: modules/screenshot_storage_policy_simulator_ru.py (207 строк, 9421 байт)

````python
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT_PATH = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_PATH / ".localcomet" / "reports"
POLICY_DIR = ROOT_PATH / ".localcomet" / "policies"
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _base_version() -> str:
    try:
        for line in CONTROL_PANEL_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("LOCALCOMET_VERSION"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    return parts[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "unknown"

def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_PATH)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")

def _screenshot_dirs() -> List[Path]:
    return [
        ROOT_PATH / "Projects" / "Reports" / "desktop_observer" / "screenshots",
        ROOT_PATH / "Projects" / "Reports" / "browser_screenshots",
    ]

def _iter_files(directory: Path) -> List[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    result: List[Path] = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git"}]
        for name in files:
            try:
                p = Path(root) / name
                if p.is_file():
                    result.append(p)
            except Exception:
                continue
    return result

def _file_info(path: Path) -> Dict[str, Any]:
    st = path.stat()
    return {
        "path": _rel(path),
        "size_bytes": int(st.st_size),
        "size_mb": round(st.st_size / (1024 * 1024), 4),
        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
    }

def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION = "v6.64d"
SCREENSHOT_STORAGE_POLICY_SIMULATOR_NAME = "LocalComet Screenshot Storage Policy Simulator RU"
SIMULATION_JSON = REPORT_DIR / "screenshot_storage_policy_simulation.json"
SIMULATION_MD = REPORT_DIR / "screenshot_storage_policy_simulation.md"

def _collect() -> Tuple[List[Path], List[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    dirs: List[Dict[str, Any]] = []
    all_files: List[Path] = []
    for d in _screenshot_dirs():
        try:
            files = _iter_files(d)
            all_files.extend(files)
            size = sum(p.stat().st_size for p in files)
            dirs.append({"path": _rel(d), "exists": d.exists(), "file_count": len(files), "size_bytes": int(size), "size_gb": round(size / (1024 ** 3), 4)})
        except Exception as e:
            errors.append(f"{_rel(d)}: {e}")
    all_files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return all_files, dirs, errors

def _simulate_policy(name: str, files: List[Path], keep_predicate) -> Dict[str, Any]:
    kept: List[Path] = []
    marked: List[Path] = []
    for p in files:
        try:
            (kept if keep_predicate(p, len(kept)) else marked).append(p)
        except Exception:
            kept.append(p)
    bytes_kept = sum(p.stat().st_size for p in kept if p.exists())
    bytes_marked = sum(p.stat().st_size for p in marked if p.exists())
    return {
        "policy_name": name,
        "files_kept": len(kept),
        "files_marked": len(marked),
        "bytes_kept": int(bytes_kept),
        "bytes_marked": int(bytes_marked),
        "estimated_reclaimable_gb": round(bytes_marked / (1024 ** 3), 4),
        "deletion_enabled": False,
    }

def generate() -> Dict[str, Any]:
    files, dirs, errors = _collect()
    now_ts = datetime.now().timestamp()
    total = sum(p.stat().st_size for p in files if p.exists())
    if files:
        oldest = min(p.stat().st_mtime for p in files if p.exists())
        observed_days = max(1.0, (now_ts - oldest) / 86400)
    else:
        observed_days = 1.0
    gb = total / (1024 ** 3)
    growth = round(gb / observed_days, 4) if observed_days else 0.0
    by_dir: Dict[str, List[Path]] = {}
    for p in files:
        key = str(p.parent)
        by_dir.setdefault(key, []).append(p)
    newest_100 = set()
    newest_500 = set()
    for group in by_dir.values():
        group.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        newest_100.update(str(p) for p in group[:100])
        newest_500.update(str(p) for p in group[:500])
    max10 = set(str(p) for p in files)
    running = 0
    max10 = set()
    for p in files:
        size = p.stat().st_size if p.exists() else 0
        if running + size <= 10 * (1024 ** 3):
            max10.add(str(p))
            running += size
    policies = [
        _simulate_policy("keep_newest_100_per_directory", files, lambda p, _: str(p) in newest_100),
        _simulate_policy("keep_newest_500_per_directory", files, lambda p, _: str(p) in newest_500),
        _simulate_policy("keep_last_1_day", files, lambda p, _: (now_ts - p.stat().st_mtime) <= 86400),
        _simulate_policy("keep_last_3_days", files, lambda p, _: (now_ts - p.stat().st_mtime) <= 3 * 86400),
        _simulate_policy("keep_last_7_days", files, lambda p, _: (now_ts - p.stat().st_mtime) <= 7 * 86400),
        _simulate_policy("keep_max_2_gb_per_directory", files, lambda p, _: True),
        _simulate_policy("keep_max_5_gb_per_directory", files, lambda p, _: True),
        _simulate_policy("keep_max_10_gb_total", files, lambda p, _: str(p) in max10),
    ]
    return {
        "schema_version": "1.0",
        "project_name": "LocalComet",
        "base_version": _base_version(),
        "generated_at": _now(),
        "cleanup_mode": "simulation_only",
        "deletion_enabled": False,
        "screenshot_directories": dirs,
        "total_screenshot_files": len(files),
        "total_screenshot_size_bytes": int(total),
        "total_screenshot_size_gb": round(gb, 4),
        "simulated_policies": policies,
        "recommended_policy": "keep_newest_500_per_directory" if gb > 10 else "keep_last_7_days",
        "growth_rate_estimate": {"gb_per_day": growth, "observed_days": round(observed_days, 2)},
        "projected_30_day_size_gb": round(growth * 30, 4),
        "projected_90_day_size_gb": round(growth * 90, 4),
        "largest_screenshots": sorted([_file_info(p) for p in files], key=lambda x: x["size_bytes"], reverse=True)[:25],
        "manual_review_required": True,
        "dangerous_cleanup_warning": "NO FILES WERE DELETED. This is a simulation-only report.",
        "next_safe_action": "Choose a policy and write a passive retention policy config.",
        "scan_errors": errors,
        "source_references": ["screenshot_retention_dry_run"],
    }

def _write_md(payload: Dict[str, Any]) -> None:
    lines = [
        "# Screenshot Storage Policy Simulation",
        f"- base_version: {payload.get('base_version')}",
        f"- cleanup_mode: {payload.get('cleanup_mode')}",
        f"- deletion_enabled: {payload.get('deletion_enabled')}",
        f"- total_screenshot_files: {payload.get('total_screenshot_files')}",
        f"- total_screenshot_size_gb: {payload.get('total_screenshot_size_gb')}",
        f"- recommended_policy: {payload.get('recommended_policy')}",
        f"- projected_30_day_size_gb: {payload.get('projected_30_day_size_gb')}",
        f"- projected_90_day_size_gb: {payload.get('projected_90_day_size_gb')}",
        "",
        payload.get("dangerous_cleanup_warning", ""),
    ]
    SIMULATION_MD.parent.mkdir(parents=True, exist_ok=True)
    SIMULATION_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

def report() -> Dict[str, Any]:
    payload = generate()
    _write_json(SIMULATION_JSON, payload)
    _write_md(payload)
    return {"ok": True, "handled": True, "mode": "screenshot_storage_policy_simulator_generated", "version": SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION, "paths": {"json": _rel(SIMULATION_JSON), "md": _rel(SIMULATION_MD)}, "summary": {"total_screenshot_files": payload["total_screenshot_files"], "total_screenshot_size_gb": payload["total_screenshot_size_gb"]}}

def status() -> Dict[str, Any]:
    return {"ok": True, "mode": "screenshot_storage_policy_simulator_status", "version": SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION}

def is_screenshot_storage_policy_simulator_command(command: str) -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {"localcomet screenshots storage policy simulate", "screenshots storage policy simulate", "storage policy simulate", "localcomet screenshots storage policy simulate status"}

def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if "status" in lower:
        return status()
    if is_screenshot_storage_policy_simulator_command(command) or not lower:
        return report()
    return {"ok": False, "handled": False, "mode": "screenshot_storage_policy_simulator_unhandled", "version": SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION, "command": command}
````

### ПУТЬ: modules/self_edit.py (1160 строк, 33349 байт)

````python
import json
import subprocess
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

import requests

from config import LMSTUDIO_API, MODEL
from core.state import set_value, get_value
from modules.maintenance import backup_project as _maintenance_backup_project
from modules.browser_profile_ignore import close_gpt_browser_context, is_browser_profile_path
from modules.patch_registry import record_patch, register_applied_patch


def backup_project():
    close_gpt_browser_context()
    return _maintenance_backup_project()


ROOT_DIR = get_project_root()
SELF_DIR = ROOT_DIR / "Projects" / "SelfEdit"
RAW_DIR = SELF_DIR / "RawResponses"
RELAY_RESPONSE_FILE = ROOT_DIR / "Projects" / "ChatGPTRelay" / "response.json"

SKIP_PARTS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "Projects",
}


def _ensure_dir():
    SELF_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def _now_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_path(rel_path: str):
    rel_path = str(rel_path or "").strip().replace("\\", "/")

    if not rel_path:
        return None

    p = Path(rel_path)

    if p.is_absolute():
        return None

    if ".." in p.parts:
        return None

    full = (ROOT_DIR / p).resolve()

    try:
        full.relative_to(ROOT_DIR.resolve())
    except Exception:
        return None

    if is_browser_profile_path(full):
        return None

    return full


def _project_tree():
    allowed_roots = {"agents", "modules", "core", "next", "tools"}

    files = []

    for path in ROOT_DIR.rglob("*"):
        if not path.is_file():
            continue

        if any(part in SKIP_PARTS for part in path.parts):
            continue

        rel = path.relative_to(ROOT_DIR)
        parts = rel.parts

        if len(parts) == 1:
            if path.suffix in [".py", ".json"]:
                files.append(str(rel).replace("\\", "/"))
            continue

        if parts[0] in allowed_roots and path.suffix == ".py":
            files.append(str(rel).replace("\\", "/"))

    files = sorted(files)
    return "\n".join(files)


def _read_file(rel_path: str, limit: int = 12000):
    full = _safe_path(rel_path)

    if not full or not full.exists() or not full.is_file():
        return None

    if is_browser_profile_path(full):
        return None

    text = full.read_text(encoding="utf-8", errors="replace")

    if len(text) > limit:
        return text[:limit] + "\n\n# ... FILE TRUNCATED FOR SELF_EDIT ..."

    return text


def _call_llm(system: str, user: str, max_tokens: int = 3000):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system.strip()},
            {"role": "user", "content": user.strip() + "\n\n/no_think"},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }

    response = None

    try:
        response = requests.post(
            LMSTUDIO_API,
            json=payload,
            timeout=300,
        )

        if response.status_code == 400:
            short_user = user[:12000]

            payload["messages"][1]["content"] = short_user + "\n\n/no_think"
            payload["max_tokens"] = min(max_tokens, 2000)

            response = requests.post(
                LMSTUDIO_API,
                json=payload,
                timeout=300,
            )

        response.raise_for_status()

    except requests.exceptions.HTTPError as e:
        body = ""

        if response is not None:
            try:
                body = response.text
            except Exception:
                body = ""

        raise RuntimeError(
            "LM Studio вернул ошибку.\n"
            f"HTTP: {e}\n"
            f"Ответ LM Studio: {body[:1000]}"
        )

    except Exception as e:
        raise RuntimeError(f"Ошибка запроса к LM Studio: {e}")

    data = response.json()
    return data["choices"][0]["message"]["content"]


def _save_raw_response(text: str, prefix: str = "raw_llm_response"):
    _ensure_dir()

    path = RAW_DIR / f"{prefix}_{_now_stamp()}.txt"
    path.write_text(str(text or ""), encoding="utf-8")

    set_value("last_self_raw_response", str(path))

    return path


def _extract_json(text: str):
    raw = str(text or "").strip()

    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()

    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raw_path = _save_raw_response(raw, "bad_json_no_object")
        raise ValueError(f"LLM не вернула JSON. Сырой ответ сохранен: {raw_path}")

    json_text = raw[start:end + 1]

    try:
        return json.loads(json_text)
    except Exception as e:
        raw_path = _save_raw_response(raw, "bad_json_parse")
        raise ValueError(
            f"LLM вернула битый JSON: {e}\n"
            f"Сырой ответ сохранен: {raw_path}"
        )


def _choose_files(goal: str):
    goal_lower = str(goal or "").lower()

    stability_keywords = [
        "auto stability",
        "auto stability test",
        "stability test",
        "model test",
        "тест стабильности",
        "проверка стабильности",
        "автотест",
        "10 баллов",
        "10 баллов без ручной проверки",
    ]

    if any(keyword in goal_lower for keyword in stability_keywords):
        return [
            "modules/stability_test.py",
            "agents/stability_agent.py",
            "modules/browser.py",
            "agents/browser_agent.py",
            "core/executor.py",
            "core/router.py",
            "core/planner.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/self_edit.py",
            "modules/history_log.py",
        ]

    gpt_browser_keywords = [
        "gpt browser bridge",
        "gpt browser",
        "chatgpt browser",
        "browser bridge",
        "persistent browser profile",
        "gpt browser open",
        "gpt browser paste request",
        "gpt browser full cycle",
        "gpt browser full apply",
        "gpt browser close",
        "browserprofile",
        "browser profile",
        "permission denied",
        "lockfile",
        "modules/gpt_browser_bridge.py",
        "agents/gpt_browser_agent.py",
    ]

    if any(keyword in goal_lower for keyword in gpt_browser_keywords):
        return [
            "modules/gpt_browser_bridge.py",
            "agents/gpt_browser_agent.py",
            "modules/browser.py",
            "modules/chatgpt_relay.py",
            "agents/chatgpt_relay_agent.py",
            "modules/automation_center.py",
            "agents/automation_agent.py",
            "core/router.py",
            "core/planner.py",
            "core/executor.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/stability_test.py",
        ]

    automation_multi_keywords = [
        "browser + pc multi task",
        "multi task",
        "browser batch",
        "browser read first",
        "browser compare",
        "browser report",
        "pc batch",
        "task status",
        "task report",
        "sequential task runner",
        "sequential runner",
        "last_multi_task",
        "last_task_report",
        "last_browser_batch",
        "last_pc_batch",
        "цепочка задач",
        "несколько шагов",
    ]

    if any(keyword in goal_lower for keyword in automation_multi_keywords):
        return [
            "modules/automation_center.py",
            "agents/automation_agent.py",
            "modules/browser.py",
            "agents/browser_agent.py",
            "core/router.py",
            "core/planner.py",
            "core/executor.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/stability_test.py",
            "modules/history_log.py",
        ]

    browser_keywords = [
        "browser follow",
        "browser agent",
        "браузерный агент",
        "browser last",
        "browser open first",
        "browser read",
        "последний поиск",
        "открой первый результат",
        "читать страницу",
        "read_page",
        "click_first_link",
        "duckduckgo",
        "browser recovery",
        "browser status",
        "current_url",
        "last_browser_query",
        "last_browser_error",
        "страница, контекст или браузер закрыт",
        "переоткрывай браузер",
        "modules/browser.py",
    ]

    if any(keyword in goal_lower for keyword in browser_keywords):
        return [
            "modules/browser.py",
            "agents/browser_agent.py",
            "core/planner.py",
            "core/router.py",
            "core/executor.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/self_edit.py",
        ]

    relay_keywords = [
        "relay",
        "релей",
        "chatgpt relay",
        "чатгпт relay",
        "chatgpt_relay",
        "response",
        "clipboard",
        "wrong clipboard",
        "utf-8-sig",
        "relative/path.py",
        "проверка response",
        "проверь ответ",
        "очистка response",
        "очисти ответ",
        "папку relay",
        "открой папку",
        "snapshot",
        "снапшот",
        "project snapshot",
        "ручной список файлов",
        "последний request",
        "последний запрос",
        "dated request",
        "датированный запрос",
        "error doctor",
        "doctor",
        "доктор",
        "ошибка",
        "ошибку",
        "баг",
        "bug",
        "traceback",
        "exception",
        "last_error",
        "last_result",
        "логи",
        "doctor path fix",
        "path fix",
        "кривой список файлов",
        "пути от кавычек",
        "кавычек и скобок",
    ]

    if any(keyword in goal_lower for keyword in relay_keywords):
        return [
            "modules/self_edit.py",
            "modules/chatgpt_relay.py",
            "agents/chatgpt_relay_agent.py",
            "next/app_v5.py",
            "agents/system_agent.py",
        ]

    if (
        "шапк" in goal_lower
        or "верси" in goal_lower
        or "v5." in goal_lower
        or "v5" in goal_lower
        or "header" in goal_lower
        or "title" in goal_lower
        or "maintenance pack" in goal_lower
        or "self-edit safe mode" in goal_lower
        or "app_v5" in goal_lower
        or "next/app_v5.py" in goal_lower
    ):
        return ["next/app_v5.py"]

    if (
        "help" in goal_lower
        or "что ты умеешь" in goal_lower
        or "раздел self-edit" in goal_lower
        or "раздел self edit" in goal_lower
    ):
        return ["agents/system_agent.py"]

    if (
        "shortcut" in goal_lower
        or "алиас" in goal_lower
        or "команд" in goal_lower
    ):
        return ["next/app_v5.py", "agents/system_agent.py"]

    if (
        "executor" in goal_lower
        or "инструмент" in goal_lower
        or "tool" in goal_lower
    ):
        return ["core/executor.py", "next/app_v5.py"]

    tree = _project_tree()

    system = """
Ты инженер проекта LocalComet.
Твоя задача — выбрать файлы, которые нужно прочитать для изменения проекта.
Верни только JSON без markdown.

Формат:
{
  "files": ["relative/path.py"],
  "reason": "кратко почему"
}

Правила:
- максимум 3 файла
- выбирай только существующие файлы из дерева
- если меняется help, выбирай agents/system_agent.py
- если меняется шапка/версия/v5, выбирай next/app_v5.py
"""

    user = f"""
Цель пользователя:
{goal}

Дерево файлов проекта:
{tree}
"""

    answer = _call_llm(system, user, max_tokens=800)
    data = _extract_json(answer)

    selected = data.get("files", [])

    safe = []

    for rel in selected:
        full = _safe_path(rel)

        if full and full.exists() and full.is_file():
            safe.append(str(Path(rel).as_posix()))

    safe = safe[:3]

    if not safe:
        safe = ["agents/system_agent.py"]

    return safe


def create_patch(goal: str):
    _ensure_dir()

    goal = str(goal or "").strip()

    if not goal:
        return "Нет цели для self-edit."

    selected_files = _choose_files(goal)

    file_blocks = []

    for rel in selected_files:
        content = _read_file(rel)

        if content is None:
            continue

        file_blocks.append(
            f"\n--- FILE: {rel} ---\n{content}\n--- END FILE: {rel} ---\n"
        )

    system = """
Ты инженер Python-проекта LocalComet.
Нужно создать безопасный patch для изменения проекта.

Верни только JSON без markdown.

Формат:
{
  "summary": "что изменится",
  "operations": [
    {
      "type": "replace",
      "path": "relative/path.py",
      "old": "точный существующий фрагмент",
      "new": "новый фрагмент"
    },
    {
      "type": "create",
      "path": "relative/path.py",
      "content": "полное содержимое нового файла"
    }
  ],
  "tests": [
    "python -m py_compile relative/path.py"
  ]
}

Правила безопасности:
- НЕ возвращай объяснения вне JSON.
- Для существующих файлов используй type=replace с точным old-фрагментом.
- old должен быть коротким, но уникальным.
- Не меняй файлы за пределами LocalAgent.
- Не удаляй файлы.
- Не используй абсолютные пути.
- Не создавай .exe/.bat/.ps1.
- Для Python-файлов добавь py_compile тесты.
- Если задача слишком большая, сделай минимальный первый шаг.
"""

    user = f"""
Цель пользователя:
{goal}

Прочитанные файлы:
{''.join(file_blocks)}
"""

    answer = _call_llm(system, user, max_tokens=3000)
    patch = _extract_json(answer)

    patch["goal"] = goal
    patch["selected_files"] = selected_files
    patch["created_at"] = datetime.now().isoformat(timespec="seconds")
    patch["model"] = MODEL

    patch_path = SELF_DIR / f"patch_{_now_stamp()}.json"
    patch_path.write_text(
        json.dumps(patch, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_value("last_self_patch", str(patch_path))

    ops = patch.get("operations", [])

    return (
        "Self-edit patch создан.\n"
        f"Файл: {patch_path}\n"
        f"Операций: {len(ops)}\n"
        f"Описание: {patch.get('summary', 'нет')}\n\n"
        "Дальше команда: примени последний патч"
    )


def show_last_patch():
    path = get_value("last_self_patch")

    if not path:
        return "Последний self-edit patch не найден."

    patch_path = Path(path)

    if not patch_path.exists():
        return f"Patch не найден: {patch_path}"

    patch = json.loads(patch_path.read_text(encoding="utf-8"))

    lines = [
        "Последний self-edit patch:",
        f"Файл: {patch_path}",
        f"Цель: {patch.get('goal', 'нет')}",
        f"Модель: {patch.get('model', 'нет')}",
        f"Описание: {patch.get('summary', 'нет')}",
        "",
        "Операции:",
    ]

    for i, op in enumerate(patch.get("operations", []), start=1):
        suffix = ""

        if op.get("already_applied"):
            suffix = " [уже применено]"

        lines.append(f"{i}. {op.get('type')} -> {op.get('path')}{suffix}")

    lines.append("")
    lines.append("Тесты:")

    for test in patch.get("tests", []):
        lines.append(f"- {test}")

    return "\n".join(lines)


def _validate_operations(operations):
    if not isinstance(operations, list) or not operations:
        return False, "В patch нет operations."

    for op in operations:
        op_type = op.get("type")
        rel_path = op.get("path")
        full = _safe_path(rel_path)

        if op_type not in ["replace", "create", "write"]:
            return False, f"Запрещенный тип операции: {op_type}"

        if not full:
            return False, f"Небезопасный путь: {rel_path}"

        if full.suffix not in [".py", ".json", ".md", ".txt"]:
            return False, f"Запрещенное расширение файла: {rel_path}"

        if op_type == "replace":
            if not full.exists():
                return False, f"Файл для replace не найден: {rel_path}"

            old = op.get("old", "")
            new = op.get("new", "")

            if not old:
                return False, f"Пустой old-фрагмент для: {rel_path}"

            current = full.read_text(encoding="utf-8", errors="replace")

            if old not in current:
                if new and new in current:
                    op["already_applied"] = True
                    continue

                return False, f"old-фрагмент не найден в файле: {rel_path}"

    return True, "OK"


def _affected_files(operations):
    result = []

    for op in operations:
        rel_path = op.get("path")
        full = _safe_path(rel_path)

        if full and full not in result:
            result.append(full)

    return result


def _save_rollback(files):
    _ensure_dir()

    rollback = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "files": [],
    }

    for full in files:
        rel = str(full.relative_to(ROOT_DIR)).replace("\\", "/")

        if full.exists():
            content = full.read_text(encoding="utf-8", errors="replace")
            existed = True
        else:
            content = ""
            existed = False

        rollback["files"].append(
            {
                "path": rel,
                "existed": existed,
                "content": content,
            }
        )

    rollback_path = SELF_DIR / f"rollback_{_now_stamp()}.json"
    rollback_path.write_text(
        json.dumps(rollback, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_value("last_self_rollback", str(rollback_path))
    return rollback_path


def _restore_rollback(rollback_path: Path):
    rollback = json.loads(rollback_path.read_text(encoding="utf-8"))

    restored = []

    for item in rollback.get("files", []):
        full = _safe_path(item.get("path"))

        if not full:
            continue

        if item.get("existed"):
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(item.get("content", ""), encoding="utf-8")
            restored.append(str(full.relative_to(ROOT_DIR)).replace("\\", "/"))
        else:
            if full.exists():
                full.unlink()
                restored.append(str(full.relative_to(ROOT_DIR)).replace("\\", "/"))

    return restored


def _run_tests(tests, changed_files):
    commands = []

    for test in tests or []:
        if isinstance(test, str) and test.strip():
            commands.append(test.strip())

    for full in changed_files:
        if full.suffix == ".py":
            rel = str(full.relative_to(ROOT_DIR)).replace("\\", "/")
            cmd = f"python -m py_compile {rel}"

            if cmd not in commands:
                commands.append(cmd)

    if not commands:
        return True, "Тестов нет."

    outputs = []

    for cmd in commands:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )

        outputs.append(
            f"$ {cmd}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\nCODE: {result.returncode}"
        )

        if result.returncode != 0:
            return False, "\n\n".join(outputs)

    return True, "\n\n".join(outputs)


def _same_path(left, right):
    try:
        return Path(left).resolve() == Path(right).resolve()
    except Exception:
        return False


def _current_response_file(patch_path):
    relay_patch = str(get_value("last_relay_imported_patch", "") or "").strip()

    if not relay_patch or not _same_path(relay_patch, patch_path):
        return ""

    response_file = str(get_value("last_relay_response", "") or "").strip()

    if response_file:
        return response_file

    if RELAY_RESPONSE_FILE.exists():
        return str(RELAY_RESPONSE_FILE)

    return ""


def _registry_changed_files(changed_files):
    result = []

    for full in changed_files:
        try:
            result.append(str(full.relative_to(ROOT_DIR)).replace("\\", "/"))
        except Exception:
            result.append(str(full))

    return result


def _patch_source(patch_path, response_file=""):
    text = f"{patch_path} {response_file}".lower()

    if "chatgpt_relay" in text or "response.json" in text:
        return "chatgpt_relay"

    return "unknown"


def _record_failed_patch(patch, patch_path, rollback_path, changed_files, tests_output, error):
    try:
        response_file = _current_response_file(patch_path)
        return record_patch(
            patch=patch,
            response_file=response_file,
            patch_file=patch_path,
            rollback_file=rollback_path,
            changed_files=_registry_changed_files(changed_files),
            tests={
                "ok": False,
                "result": str(tests_output or error or ""),
            },
            status="failed",
            source=_patch_source(patch_path, response_file),
        )
    except Exception:
        return None


def apply_last_patch():
    path = get_value("last_self_patch")

    if not path:
        return "Последний self-edit patch не найден."

    patch_path = Path(path)

    if not patch_path.exists():
        return f"Patch не найден: {patch_path}"

    patch = json.loads(patch_path.read_text(encoding="utf-8"))
    operations = patch.get("operations", [])

    ok, message = _validate_operations(operations)

    if not ok:
        return "Patch НЕ применен.\nПричина: " + message

    already_count = len([op for op in operations if op.get("already_applied")])

    if already_count == len(operations):
        set_value("last_self_applied_patch", str(patch_path))

        patch["already_applied_at"] = datetime.now().isoformat(timespec="seconds")
        patch_path.write_text(
            json.dumps(patch, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return (
            "Patch уже был применен ранее.\n"
            f"Patch: {patch_path}\n"
            "Изменения не требуются."
        )

    changed_files = _affected_files(operations)
    rollback_path = _save_rollback(changed_files)

    backup_result = backup_project()

    try:
        for op in operations:
            op_type = op.get("type")
            full = _safe_path(op.get("path"))

            if op_type == "replace":
                if op.get("already_applied"):
                    continue

                current = full.read_text(encoding="utf-8", errors="replace")
                current = current.replace(op.get("old", ""), op.get("new", ""), 1)
                full.write_text(current, encoding="utf-8")

            elif op_type == "create":
                if full.exists():
                    raise RuntimeError(f"Файл уже существует, create отменен: {op.get('path')}")

                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text(op.get("content", ""), encoding="utf-8")

            elif op_type == "write":
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text(op.get("content", ""), encoding="utf-8")

        tests_ok, tests_output = _run_tests(patch.get("tests", []), changed_files)

        if not tests_ok:
            restored = _restore_rollback(rollback_path)
            _record_failed_patch(
                patch,
                patch_path,
                rollback_path,
                changed_files,
                tests_output,
                "tests failed",
            )

            return (
                "Patch применен, но тесты упали. Изменения ОТКАЧЕНЫ.\n\n"
                f"Rollback: {rollback_path}\n"
                f"Восстановлено: {restored}\n\n"
                f"Тесты:\n{tests_output}"
            )

        set_value("last_self_applied_patch", str(patch_path))
        response_file = _current_response_file(patch_path)
        registry_entry = register_applied_patch(
            patch=patch,
            patch_file=patch_path,
            rollback_file=rollback_path,
            tests_ok=tests_ok,
            tests_output=tests_output,
            response_file=response_file,
            changed_files=_registry_changed_files(changed_files),
            source=_patch_source(patch_path, response_file),
        )

        return (
            "Patch успешно применен.\n"
            f"Patch: {patch_path}\n"
            f"Rollback: {rollback_path}\n"
            f"Patch Registry: {registry_entry.get('version')} записан\n"
            f"{backup_result}\n\n"
            f"Тесты:\n{tests_output}"
        )

    except Exception as e:
        restored = _restore_rollback(rollback_path)
        _record_failed_patch(
            patch,
            patch_path,
            rollback_path,
            changed_files,
            "",
            e,
        )

        return (
            "Ошибка применения patch. Изменения ОТКАЧЕНЫ.\n"
            f"Ошибка: {e}\n"
            f"Rollback: {rollback_path}\n"
            f"Восстановлено: {restored}"
        )


def rollback_last_patch():
    path = get_value("last_self_rollback")

    if not path:
        return "Rollback не найден."

    rollback_path = Path(path)

    if not rollback_path.exists():
        return f"Rollback-файл не найден: {rollback_path}"

    restored = _restore_rollback(rollback_path)

    return (
        "Rollback выполнен.\n"
        f"Файл: {rollback_path}\n"
        f"Восстановлено: {restored}"
    )


def repair_last_patch():
    path = get_value("last_self_patch")

    if not path:
        return "Последний self-edit patch не найден."

    patch_path = Path(path)

    if not patch_path.exists():
        return f"Patch не найден: {patch_path}"

    try:
        patch = json.loads(patch_path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Не удалось прочитать patch JSON: {e}"

    operations = patch.get("operations", [])

    if not operations:
        return "В patch нет operations, ремонт невозможен."

    repaired = []
    failed = []

    for op in operations:
        op_type = op.get("type")
        rel_path = op.get("path")
        old = op.get("old", "")
        new = op.get("new", "")

        if op_type != "replace":
            repaired.append(op)
            continue

        full = _safe_path(rel_path)

        if not full or not full.exists():
            failed.append(f"{rel_path}: файл не найден")
            repaired.append(op)
            continue

        current = full.read_text(encoding="utf-8", errors="replace")

        if old and old in current:
            repaired.append(op)
            continue

        if new and new in current:
            op["already_applied"] = True
            repaired.append(op)
            continue

        system = """
Ты ремонтируешь JSON patch для Python-проекта.
Нужно найти точный old-фрагмент в текущем файле, который надо заменить на new.

Верни только JSON без markdown:
{
  "old": "точный фрагмент из файла",
  "new": "новый фрагмент"
}

Правила:
- old обязан быть точной подстрокой текущего файла
- old должен быть минимальным, но уникальным
- new сохрани по смыслу из исходного patch
- не добавляй объяснения
"""

        user = f"""
Patch summary:
{patch.get("summary", "")}

Файл:
{rel_path}

Текущий неверный old:
{old}

Желаемый new:
{new}

Текущее содержимое файла:
{current[:16000]}
"""

        try:
            answer = _call_llm(system, user, max_tokens=2000)
            data = _extract_json(answer)

            fixed_old = data.get("old", "")
            fixed_new = data.get("new", new)

            if not fixed_old or fixed_old not in current:
                failed.append(f"{rel_path}: LLM не дала точный old")
                repaired.append(op)
                continue

            repaired.append(
                {
                    "type": "replace",
                    "path": rel_path,
                    "old": fixed_old,
                    "new": fixed_new,
                }
            )

        except Exception as e:
            failed.append(f"{rel_path}: {e}")
            repaired.append(op)

    patch["operations"] = repaired
    patch["summary"] = str(patch.get("summary", "")) + " [repaired]"
    patch["repaired_at"] = datetime.now().isoformat(timespec="seconds")

    patch_path.write_text(
        json.dumps(patch, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if failed:
        return (
            "Patch частично отремонтирован, но есть проблемы:\n"
            + "\n".join(failed)
            + f"\n\nФайл patch: {patch_path}"
        )

    return f"Patch отремонтирован успешно:\n{patch_path}"


def project_health():
    py_files = []

    for path in ROOT_DIR.rglob("*.py"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue

        py_files.append(path)

    if not py_files:
        return "Python-файлы не найдены."

    errors = []
    ok_count = 0

    for path in py_files:
        rel = str(path.relative_to(ROOT_DIR)).replace("\\", "/")

        result = subprocess.run(
            f"python -m py_compile {rel}",
            cwd=str(ROOT_DIR),
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            ok_count += 1
        else:
            errors.append(
                f"{rel}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

    if errors:
        return (
            "Self-check проекта: ❌ есть ошибки.\n"
            f"OK: {ok_count}\n"
            f"Ошибок: {len(errors)}\n\n"
            + "\n\n".join(errors[:10])
        )

    return f"Self-check проекта: ✅ все Python-файлы компилируются. Проверено: {ok_count}"


def auto_edit(goal: str):
    created = create_patch(goal)
    applied = apply_last_patch()

    return created + "\n\n--- APPLY RESULT ---\n\n" + applied
````

### ПУТЬ: modules/stability_test.py (1921 строк, 89608 байт)

````python
import json
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from config import MODEL, LMSTUDIO_API
from core.state import set_value, get_value


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports"


def _ensure_reports_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value, limit: int = 1800):
    text = str(value or "")

    if len(text) <= limit:
        return text

    return text[:limit] + "\n...[обрезано]"


def _ok_text(value):
    text = str(value or "").lower()

    bad_markers = [
        "error:",
        "ошибка:",
        "traceback",
        "не удалось",
        "unknown",
        "неизвестное действие",
        "target page, context or browser has been closed",
    ]

    return bool(text.strip()) and not any(marker in text for marker in bad_markers)


def _run_case(name, func, checker=None):
    started = datetime.now().isoformat(timespec="seconds")

    try:
        result = func()

        if checker is None:
            passed = _ok_text(result)
        else:
            passed = bool(checker(result))

        return {
            "name": name,
            "passed": passed,
            "result": _short(result),
            "error": "",
            "time": started,
        }

    except Exception as e:
        return {
            "name": name,
            "passed": False,
            "result": "",
            "error": _short(traceback.format_exc()),
            "time": started,
        }


def _finish_cases(cases, mode: str):
    score = sum(1 for case in cases if case["passed"])

    if score == len(cases):
        level = "отличная"
    elif score >= max(1, int(len(cases) * 0.7)):
        level = "хорошая"
    elif score >= max(1, int(len(cases) * 0.5)):
        level = "средняя"
    else:
        level = "плохая"

    problems = [
        f"{case['name']}: {case['error'] or case['result']}"
        for case in cases
        if not case["passed"]
    ]

    report_path = _save_report(cases, score, level, problems)
    set_value("last_stability_mode", mode)

    lines = [
        f"{mode.title()} Stability Test завершен.",
        f"Итог: {score}/{len(cases)}",
        f"Стабильность: {level}",
        f"Отчет: {report_path}",
        "",
        "Проверки:",
    ]

    for case in cases:
        mark = "[OK]" if case["passed"] else "[FAIL]"
        lines.append(f"- {mark} {case['name']}")

    lines.append("")
    lines.append("Проблемы:")

    if problems:
        for problem in problems:
            lines.append("- " + _short(problem, 400))
    else:
        lines.append("- Не обнаружены.")

    return "\n".join(lines)


def _help_status_case():
    def check_help_status():
        from agents import system_agent

        help_text = system_agent.handle("help", {})
        status_text = system_agent.handle("status", {})

        ui_markers = [
            "control_panel_ui_rework_pack: да",
            "control_panel_tabs: да",
            "compact_dashboard: да",
            "organized_relay_tab: да",
            "organized_browser_tab: да",
            "organized_autopilot_tab: да",
            "control_panel_chat_commands: да",
            "panel_chat_with_model: да",
            "panel_text_command_input: да",
            "russian_control_panel_menu: да",
            "control_panel_russian_labels: да",
            "russian_command_center_ui: да",
            "gray_control_panel_theme: да",
            "translucent_gray_button_style: да",
            "control_panel_theme_smoke: да",
        ]

        chat_automation_markers = [
            "chat_automation_intents: да",
            "natural_open_url_intent: да",
            "natural_search_workflow: да",
            "natural_page_actions: да",
            "natural_project_checks: да",
            "natural_browser_interactions: да",
            "chat_research_workflow_intents: да",
            "natural_research_intent: да",
            "natural_compare_intent: да",
            "natural_open_page_workflow: да",
            "browser_mission_report_intents: да",
            "natural_browser_report_workflow: да",
            "natural_site_check_workflow: да",
            "natural_form_workflow_intents: да",
            "natural_form_fill_sequence: да",
            "natural_form_submit_guard: да",
        ]

        health_markers = [
            "project_health_center_pack: да",
            "project_health_command: да",
            "project_health_report: да",
            "safe_health_checks: да",
        ]

        regression_markers = [
            "regression_command_suite_pack: да",
            "regression_command_suite: да",
            "regression_command_report: да",
            "safe_regression_commands: да",
        ]

        auto_verification_markers = [
            "auto_verification_pack: да",
            "auto_verify_command: да",
            "auto_verify_after_patch: да",
            "auto_verify_reports: да",
        ]

        browser_super_markers = [
            "browser_super_operator_pack: да",
            "browser_research_reports: да",
            "browser_platform_site_workflow: да",
            "browser_youtube_search: да",
            "natural_command_intents: да",
            "browser_page_audit: да",
            "browser_form_map: да",
            "browser_super_safety_guard: да",
        ]

        markers = [
            "project_boost_pack: да",
            "dashboard_readability_pack: да",
            "patch_registry: да",
            "patch_registry_manual_snapshot: да",
            "compact_ui_patch_version_bar: да",
            "stability_test_modes: да",
            "error_doctor_fix_request: да",
            "llm_provider_foundation: да",
            "llm_offline_graceful_error_pack: yes",
            "llm_connection_error_handling: yes",
            "lmstudio_offline_hint: yes",
            "voice_mode_panel_pack: yes",
            "voice_chat_mode: yes",
            "voice_chat_replies: yes",
            "voice_continuous_dialogue: yes",
            "voice_faster_whisper_ru: yes",
            "voice_piper_tts: yes",
            "voice_vosk_russian_stt: yes",
            "voice_push_to_talk: yes",
            "voice_command_safety_guard: yes",
            "voice_tts: yes",
            "voice_session_reports: yes",
            "codex_bridge_foundation: да",
            "git_safety_status: да",
            *ui_markers,
            *chat_automation_markers,
            *health_markers,
            *regression_markers,
            *auto_verification_markers,
            *browser_super_markers,
            "panel_relay_diagnostics_pack: да",
            "relay_diagnostics: да",
            "relay_smoke_test: да",
            "relay_dry_run_safe: да",
            "browser_action_operator_pack: да",
            "browser_direct_action_routing_fix: да",
            "browser_action_auto_recovery: да",
            "browser_screenshot_action: да",
            "browser_extract_links_inputs: да",
            "browser_task_runner: да",
            "browser_action_safety_guard: да",
            "browser_multi_step_workflow_pack: да",
            "browser_workflow_runner: да",
            "browser_workflow_reports: да",
            "browser_autopilot_operator_pack: да",
            "browser_autopilot_plan: да",
            "browser_autopilot_run: да",
            "browser_autopilot_dry_run: да",
            "browser_autopilot_safety_guard: да",
            "browser_autopilot_reports: да",
            "browser_observe: да",
        ]

        lines = [
            "HELP OK: " + str("LocalComet сейчас умеет" in help_text),
            "STATUS OK: " + str("Статус LocalComet" in status_text),
        ]

        for marker in markers:
            lines.append(marker + " status -> " + str(marker in status_text))

        for marker in ui_markers:
            lines.append(marker + " help -> " + str(marker in help_text))

        for marker in chat_automation_markers:
            lines.append(marker + " help -> " + str(marker in help_text))

        for marker in health_markers:
            lines.append(marker + " help -> " + str(marker in help_text))

        for marker in regression_markers:
            lines.append(marker + " help -> " + str(marker in help_text))

        for marker in auto_verification_markers:
            lines.append(marker + " help -> " + str(marker in help_text))

        for marker in browser_super_markers:
            lines.append(marker + " help -> " + str(marker in help_text))

        return "\n".join(lines)

    return _run_case(
        "help/status markers",
        check_help_status,
        lambda r: (
            "HELP OK: True" in r
            and "STATUS OK: True" in r
            and "False" not in r
        ),
    )


def _memory_case():
    def check_memory():
        from agents import system_agent

        return system_agent.handle("memory", {})

    return _run_case("memory", check_memory, lambda r: bool(str(r).strip()))


def _py_compile_case():
    files = [
        "LocalComet_Control_Panel.py",
        "next/app_v5.py",
        "core/llm.py",
        "modules/voice_control.py",
        "modules/patch_registry.py",
        "modules/llm_provider.py",
        "modules/git_status.py",
        "modules/codex_bridge.py",
        "modules/project_health.py",
        "modules/regression_commands.py",
        "modules/auto_verification.py",
        "modules/relay_diagnostics.py",
        "modules/browser.py",
        "modules/browser_direct.py",
        "modules/browser_super.py",
        "modules/natural_command_intents.py",
        "modules/browser_actions.py",
        "modules/browser_task_runner.py",
        "modules/browser_autopilot.py",
        "modules/stability_test.py",
        "modules/self_edit.py",
        "agents/browser_agent.py",
        "agents/system_agent.py",
        "core/router.py",
        "core/planner.py",
    ]

    def check_py_compile():
        result = subprocess.run(
            ["python", "-m", "py_compile"] + files,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )

        return (
            f"CODE: {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    return _run_case("py_compile key files", check_py_compile, lambda r: "CODE: 0" in r)


def _relay_status_case():
    def check_relay_status():
        from agents import chatgpt_relay_agent

        return chatgpt_relay_agent.handle("status", {})

    return _run_case("relay status", check_relay_status, lambda r: "ChatGPT Relay status" in r)


def _project_health_case():
    def check_project_health():
        from agents import system_agent
        from core.router import route
        from modules import project_health

        health = project_health.get_project_health()
        text = project_health.format_project_health_text(health)
        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})
        agent_text = system_agent.handle("health", {})

        checks = [
            callable(project_health.get_project_health),
            callable(project_health.format_project_health_text),
            callable(project_health.write_project_health_report),
            isinstance(health, dict),
            health.get("status") in ["ok", "attention"],
            "Project Health Center:" in text,
            "Recommended before commit:" in text,
            "Project Health Center:" in agent_text,
            route("health") == "system",
            route("project health") == "system",
            "project_health_center_pack: да" in status_text,
            "project_health_command: да" in status_text,
            "project_health_report: да" in status_text,
            "safe_health_checks: да" in status_text,
            "project_health_center_pack: да" in help_text,
            "project_health_command: да" in help_text,
            "health report" in help_text,
        ]

        return "\n".join(f"project_health_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "project health center",
        check_project_health,
        lambda r: "False" not in r and "project_health_check_17: True" in r,
    )


def _regression_command_suite_case():
    def check_regression_command_suite():
        from agents import system_agent
        from core.router import route
        from modules import regression_commands

        suite = regression_commands.run_regression_command_suite(write_report=False)
        text = regression_commands.format_regression_command_suite(suite)
        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})
        agent_text = system_agent.handle("regression_suite", {})

        checks = [
            callable(regression_commands.get_regression_command_cases),
            callable(regression_commands.run_regression_command_suite),
            callable(regression_commands.format_regression_command_suite),
            callable(regression_commands.write_regression_command_report),
            suite.get("status") == "ok",
            suite.get("passed") == suite.get("total"),
            "Regression Command Suite:" in text,
            "Problems:" in text,
            "Regression Command Suite:" in agent_text,
            route("regression suite") == "system",
            route("regression report") == "system",
            "regression_command_suite_pack: да" in status_text,
            "regression_command_suite: да" in status_text,
            "regression_command_report: да" in status_text,
            "safe_regression_commands: да" in status_text,
            "regression_command_suite_pack: да" in help_text,
            "regression suite" in help_text,
        ]

        return "\n".join(f"regression_suite_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "regression command suite",
        check_regression_command_suite,
        lambda r: "False" not in r and "regression_suite_check_17: True" in r,
    )


def _auto_verification_case():
    def check_auto_verification():
        from agents import system_agent
        from core.router import route
        from modules import auto_verification

        result = auto_verification.run_auto_verification(mode="smoke", write_report=False)
        text = auto_verification.format_auto_verification(result)
        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})
        agent_text = system_agent.handle("auto_verify", {})

        checks = [
            callable(auto_verification.get_auto_verification_files),
            callable(auto_verification.run_auto_verification),
            callable(auto_verification.format_auto_verification),
            callable(auto_verification.write_auto_verification_report),
            callable(auto_verification.latest_auto_verification_report),
            result.get("status") == "ok",
            result.get("passed") == result.get("total"),
            "Auto Verification:" in text,
            "Auto Verification:" in agent_text,
            route("auto verify") == "system",
            route("verify full") == "system",
            "auto_verification_pack: да" in status_text,
            "auto_verify_command: да" in status_text,
            "auto_verify_after_patch: да" in status_text,
            "auto_verify_reports: да" in status_text,
            "auto_verification_pack: да" in help_text,
            "auto verify" in help_text,
        ]

        return "\n".join(f"auto_verify_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "auto verification foundation",
        check_auto_verification,
        lambda r: "False" not in r and "auto_verify_check_17: True" in r,
    )


def _relay_diagnostics_case():
    def check_relay_diagnostics():
        from agents import chatgpt_relay_agent, system_agent
        from modules import relay_diagnostics

        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})
        diagnostics = relay_diagnostics.get_relay_diagnostics()
        diagnostics_text = relay_diagnostics.format_relay_diagnostics_text(diagnostics)
        app_text = (ROOT_DIR / "next" / "app_v5.py").read_text(encoding="utf-8", errors="replace")

        checks = [
            callable(relay_diagnostics.get_relay_diagnostics),
            callable(relay_diagnostics.format_relay_diagnostics_text),
            callable(relay_diagnostics.run_relay_smoke_test),
            "Relay Diagnostics:" in diagnostics_text,
            "panel_relay_diagnostics_pack: да" in status_text,
            "relay_diagnostics: да" in status_text,
            "relay_smoke_test: да" in status_text,
            "relay_dry_run_safe: да" in status_text,
            "panel_relay_diagnostics_pack: да" in help_text,
            "relay_diagnostics: да" in help_text,
            "relay_smoke_test: да" in help_text,
            "relay_dry_run_safe: да" in help_text,
            "relay diagnostics" in help_text,
            "relay smoke" in help_text,
            "relay diagnostics" in app_text,
            "relay smoke" in app_text,
            "panel relay smoke" in app_text,
            "Relay Diagnostics:" in chatgpt_relay_agent.handle("diagnostics", {}),
        ]

        return "\n".join(f"relay_diag_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "relay diagnostics foundation",
        check_relay_diagnostics,
        lambda r: "False" not in r and "relay_diag_check_18: True" in r,
    )


def _patch_registry_case():
    def check_patch_registry():
        from modules.patch_registry import short_status

        return short_status()

    return _run_case("patch registry status", check_patch_registry, lambda r: "Patch Registry:" in r)


def _browser_action_foundation_case():
    def check_browser_actions():
        import modules.browser_actions as browser_actions
        import modules.browser_task_runner as browser_task_runner

        checks = [
            callable(browser_actions.browser_action_status),
            callable(browser_actions.screenshot_page),
            callable(browser_actions.extract_links),
            callable(browser_actions.extract_inputs),
            callable(browser_actions.summarize_page),
            callable(browser_task_runner.run_browser_steps),
            callable(browser_task_runner.run_browser_workflow),
            browser_actions._is_dangerous_browser_action("купить и оплатить"),
        ]

        return "\n".join(f"check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "browser action foundation",
        check_browser_actions,
        lambda r: "False" not in r and "check_8: True" in r,
    )


def _browser_direct_routing_case():
    def check_browser_direct_routing():
        from core.router import route
        from core.planner import plan
        from modules.browser_direct import browser_action_direct_plan

        commands = {
            "browser summarize": "summarize",
            "browser links": "extract_links",
            "browser inputs": "extract_inputs",
        }

        lines = []

        for command, expected_action in commands.items():
            routed = route(command)
            planned_default = plan(command)
            planned_browser = plan(command, "browser")
            direct = browser_action_direct_plan(command)
            lines.append(
                f"{command}: route={routed}; "
                f"plan={planned_default.get('action')}; "
                f"browser_plan={planned_browser.get('action')}; "
                f"direct={direct.get('action') if direct else 'none'}; "
                f"ok={routed == 'browser' and planned_default.get('action') == expected_action and planned_browser.get('action') == expected_action and direct and direct.get('action') == expected_action}"
            )

        return "\n".join(lines)

    return _run_case(
        "browser direct action routing",
        check_browser_direct_routing,
        lambda r: "ok=False" not in r and "browser summarize" in r and "browser links" in r and "browser inputs" in r,
    )


def _browser_action_auto_recovery_case():
    def check_browser_action_auto_recovery():
        import modules.browser_actions as browser_actions

        class BlankPage:
            url = "about:blank"

        old_get_page = browser_actions.get_active_page_for_actions
        old_save_report = browser_actions._save_action_report
        old_query = get_value("last_browser_query", "")
        old_current_url = get_value("current_url", "")

        try:
            set_value("last_browser_query", "")
            set_value("current_url", "about:blank")
            browser_actions.get_active_page_for_actions = lambda: BlankPage()
            browser_actions._save_action_report = lambda *args, **kwargs: ""

            helper_blank = browser_actions._is_blank_page(BlankPage())
            helper_stop = browser_actions._ensure_action_page(BlankPage(), recover=False)
            summary = browser_actions.summarize_page()
            links = browser_actions.extract_links()
            inputs = browser_actions.extract_inputs()

            return "\n".join([
                "helper_blank: " + str(helper_blank),
                "helper_stop_has_hint: " + str("browser search <запрос>" in helper_stop),
                "summary_has_hint: " + str("Страница пустая" in summary and "URL: about:blank" not in summary),
                "links_not_empty_json: " + str(links.strip() != "[]" and "Страница пустая" in links),
                "inputs_not_empty_json: " + str(inputs.strip() != "[]" and "Страница пустая" in inputs),
            ])
        finally:
            browser_actions.get_active_page_for_actions = old_get_page
            browser_actions._save_action_report = old_save_report
            set_value("last_browser_query", old_query)
            set_value("current_url", old_current_url)

    return _run_case(
        "browser action auto recovery",
        check_browser_action_auto_recovery,
        lambda r: "False" not in r and "helper_blank: True" in r,
    )


def _browser_autopilot_case():
    def check_browser_autopilot():
        from agents import system_agent
        from core.router import route
        from modules.browser_autopilot import (
            build_browser_autopilot_plan,
            format_browser_autopilot_plan,
            is_browser_task_safe,
            observe_browser_page,
            run_browser_autopilot,
        )
        from modules.browser_direct import browser_action_direct_plan

        help_text = system_agent.handle("help", {})
        status_text = system_agent.handle("status", {})
        unsafe_ok, unsafe_reason = is_browser_task_safe("оплати заказ банковской картой")
        safe_plan = build_browser_autopilot_plan("найди официальный сайт Python и сделай отчет", mode="dry_run", max_steps=8)
        blocked_plan = build_browser_autopilot_plan("оплати заказ банковской картой", mode="dry_run", max_steps=8)
        direct_plan = browser_action_direct_plan("browser plan найди официальный сайт Python и сделай отчет")
        direct_dry = browser_action_direct_plan("browser autopilot dry найди официальный сайт Python и сделай отчет")
        direct_task = browser_action_direct_plan("browser task проанализируй текущую страницу и собери ссылки")

        checks = [
            callable(build_browser_autopilot_plan),
            callable(run_browser_autopilot),
            callable(is_browser_task_safe),
            callable(observe_browser_page),
            callable(format_browser_autopilot_plan),
            unsafe_ok is False and bool(unsafe_reason),
            bool(safe_plan.get("steps")),
            bool(blocked_plan.get("blocked_reason")),
            route("browser autopilot dry найди Python") == "browser",
            route("browser task проанализируй текущую страницу") == "browser",
            direct_plan and direct_plan.get("action") == "plan",
            direct_dry and direct_dry.get("action") == "autopilot_dry",
            direct_task and direct_task.get("action") == "browser_task",
            "browser_autopilot_operator_pack: да" in status_text,
            "browser_autopilot_plan: да" in status_text,
            "browser_autopilot_run: да" in status_text,
            "browser_autopilot_dry_run: да" in status_text,
            "browser_autopilot_safety_guard: да" in status_text,
            "browser_autopilot_reports: да" in status_text,
            "browser_observe: да" in status_text,
            "browser plan <task>" in help_text,
            "browser autopilot dry <task>" in help_text,
            "browser task <task>" in help_text,
        ]

        return "\n".join(f"browser_autopilot_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "browser autopilot foundation",
        check_browser_autopilot,
        lambda r: "False" not in r and "browser_autopilot_check_23: True" in r,
    )


def _browser_super_case():
    def check_browser_super():
        from agents import browser_agent, system_agent
        from core.planner import plan
        from core.router import route
        from modules.browser_direct import browser_action_direct_plan
        from modules.browser_super import (
            build_browser_super_plan,
            classify_browser_super_task,
            format_browser_super_plan,
        )
        from modules.natural_command_intents import natural_command_plan, natural_command_route

        help_text = system_agent.handle("help", {})
        status_text = system_agent.handle("status", {})
        platform_task = "напиши сайт автосервиса используй платформу Tilda"
        platform_plan = build_browser_super_plan(platform_task, mode="dry_run", max_results=3)
        research_plan = build_browser_super_plan("исследуй browser-use и Skyvern", mode="dry_run", max_results=3)
        direct_research = browser_action_direct_plan("browser research лучшие конструкторы сайтов")
        direct_site = browser_action_direct_plan("browser build site сайт автосервиса используй платформу Tilda")
        agent_plan_text = browser_agent.handle("super_plan", {"task": platform_task})
        planner_result = plan(platform_task, "browser")
        natural_tilda = natural_command_plan("сделай мне сайт на тильде для автосервиса")
        natural_youtube = natural_command_plan("открой YouTube и найди видео про Python decorators")
        natural_youtube_ru = natural_command_plan("найди на ютубе ролик про настройку LM Studio")
        natural_project_check = natural_command_plan("проверь весь проект на наличие ошибок")
        natural_project_checks = natural_command_plan("запусти все проверки проекта")

        checks = [
            classify_browser_super_task(platform_task) == "site_workflow",
            platform_plan.get("kind") == "site_workflow",
            any(step.get("action") == "open_platform" for step in platform_plan.get("steps", [])),
            "tilda.cc" in str(platform_plan).lower(),
            research_plan.get("kind") in ["research", "smart_browser"],
            "Browser Super Plan:" in format_browser_super_plan(platform_plan),
            "Browser Super Plan:" in agent_plan_text,
            route("browser research лучшие ai браузеры") == "browser",
            route(platform_task) == "browser",
            direct_research and direct_research.get("action") == "research",
            direct_site and direct_site.get("action") == "platform_site_workflow",
            planner_result.get("tool") == "browser",
            planner_result.get("action") == "platform_site_workflow",
            natural_tilda and natural_tilda.get("action") == "platform_site_workflow",
            natural_youtube and natural_youtube.get("action") == "youtube_search",
            natural_youtube_ru and natural_youtube_ru.get("action") == "youtube_search",
            natural_project_check and natural_project_check.get("action") == "auto_verify_full",
            natural_project_checks and natural_project_checks.get("action") == "auto_verify_full",
            natural_command_route("проверь весь проект на наличие ошибок") == "system",
            "browser_super_operator_pack: да" in status_text,
            "browser_research_reports: да" in status_text,
            "browser_platform_site_workflow: да" in status_text,
            "browser_youtube_search: да" in status_text,
            "natural_command_intents: да" in status_text,
            "browser_page_audit: да" in status_text,
            "browser_form_map: да" in status_text,
            "browser_super_safety_guard: да" in status_text,
            "browser_super_operator_pack: да" in help_text,
            "browser_youtube_search: да" in help_text,
            "natural_command_intents: да" in help_text,
            "browser research <topic>" in help_text,
            "browser build site <prompt>" in help_text,
        ]

        return "\n".join(f"browser_super_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "browser super operator foundation",
        check_browser_super,
        lambda r: "False" not in r and "browser_super_check_32: True" in r,
    )


def _chat_automation_intents_case():
    def check_chat_automation_intents():
        from agents import system_agent
        from core.planner import plan
        from core.router import route
        from modules.natural_command_intents import natural_command_plan, natural_command_route

        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})

        cases = [
            ("открой github.com", "browser", "open_url"),
            ("открой сайт гугл", "browser", "open_url"),
            ("открой официальный сайт Python и кратко прочитай", "browser", "browser_workflow"),
            ("найди в интернете browser-use github и открой первый результат", "browser", "browser_workflow"),
            ("найди официальный сайт playwright и собери ссылки", "browser", "browser_workflow"),
            ("сделай скриншот текущей страницы", "browser", "screenshot"),
            ("собери ссылки со страницы", "browser", "extract_links"),
            ("покажи поля ввода на странице", "browser", "extract_inputs"),
            ("найди текст Python на странице", "browser", "find_text"),
            ("кликни кнопку Login", "browser", "click_text"),
            ("введи Ivan в поле Name", "browser", "fill_label"),
            ("нажми Enter", "browser", "press_key"),
            ("покажи здоровье проекта", "system", "health"),
            ("сделай regression report", "system", "regression_report"),
            ("проверь проект быстро", "system", "auto_verify"),
            ("запусти тест стабильности", "stability", "run"),
            ("изучи browser-use и Skyvern и сделай отчет", "browser", "research"),
            ("сравни OpenHands browser-use и Skyvern", "browser", "compare_research"),
            ("найди лучшие платформы для сайта автосервиса", "browser", "research"),
            ("открой github.com и сделай скриншот", "browser", "browser_workflow"),
            ("открой github.com и собери ссылки", "browser", "browser_workflow"),
            ("открой github.com и кратко прочитай", "browser", "browser_workflow"),
            ("открой github.com и проанализируй страницу", "browser", "browser_workflow"),
            ("проанализируй текущую страницу", "browser", "page_audit"),
            ("сделай браузерный отчет по Python official website", "browser", "browser_workflow"),
            ("сделай браузерный отчет по текущей странице", "browser", "browser_workflow"),
            ("проверь сайт github.com", "browser", "browser_workflow"),
            ("проанализируй сайт github.com", "browser", "browser_workflow"),
            ("открой github.com и сделай полный отчет", "browser", "browser_workflow"),
            ("заполни форму: Name=Ivan, Email=ivan@example.com, нажми Enter", "browser", "browser_sequence"),
            ("открой example.com и заполни форму: Name=Ivan; Email=ivan@example.com", "browser", "browser_sequence"),
            ("заполни поля: Search=Python и нажми кнопку Submit", "browser", "browser_sequence"),
            ("заполни форму оплаты: card=4111111111111111, cvv=123", "none", "answer"),
        ]

        checks = []

        for command, expected_tool, expected_action in cases:
            planned = natural_command_plan(command) or {}
            checks.append(
                planned.get("tool") == expected_tool
                and planned.get("action") == expected_action
                and natural_command_route(command) == expected_tool
                and route(command) == expected_tool
                and plan(command).get("action") == expected_action
            )

        workflow = natural_command_plan("открой официальный сайт Python и кратко прочитай") or {}
        workflow_steps = workflow.get("steps", [])
        search_report = natural_command_plan("сделай браузерный отчет по Python official website") or {}
        search_report_steps = search_report.get("steps", [])
        page_report = natural_command_plan("проверь сайт github.com") or {}
        page_report_steps = page_report.get("steps", [])
        form_sequence = natural_command_plan("заполни форму: Name=Ivan, Email=ivan@example.com, нажми Enter") or {}
        form_steps = form_sequence.get("steps", [])
        form_with_url = natural_command_plan("открой example.com и заполни форму: Name=Ivan; Email=ivan@example.com") or {}
        form_url_steps = form_with_url.get("steps", [])
        form_submit = natural_command_plan("заполни поля: Search=Python и нажми кнопку Submit") or {}
        form_submit_steps = form_submit.get("steps", [])
        form_stop = natural_command_plan("заполни форму оплаты: card=4111111111111111, cvv=123") or {}

        checks.extend([
            natural_command_plan("multi task найди Python и открой папку отчетов") is None,
            natural_command_route("multi task найди Python и открой папку отчетов") is None,
            natural_command_plan("browser batch Godot") is None,
            natural_command_plan("dev task улучши браузер") is None,
            any(step.get("action") == "search" for step in workflow_steps),
            any(step.get("action") == "open_first" for step in workflow_steps),
            any(step.get("action") == "summarize" for step in workflow_steps),
            search_report.get("title") == "natural search report workflow",
            any(step.get("action") == "open_first" for step in search_report_steps),
            any(step.get("action") == "extract_inputs" for step in search_report_steps),
            page_report.get("title") == "natural page report workflow",
            any(step.get("action") == "open_url" for step in page_report_steps),
            any(step.get("action") == "screenshot" for step in page_report_steps),
            form_sequence.get("title") == "natural form workflow",
            len([step for step in form_steps if step.get("action") == "fill_label"]) == 2,
            any(step.get("action") == "press_key" for step in form_steps),
            any(step.get("action") == "open_url" for step in form_url_steps),
            any(step.get("action") == "click_text" for step in form_submit_steps),
            form_stop.get("tool") == "none" and "STOP: form workflow" in form_stop.get("text", ""),
            "chat_automation_intents: да" in status_text,
            "natural_open_url_intent: да" in status_text,
            "natural_search_workflow: да" in status_text,
            "natural_page_actions: да" in status_text,
            "natural_project_checks: да" in status_text,
            "natural_browser_interactions: да" in status_text,
            "chat_research_workflow_intents: да" in status_text,
            "natural_research_intent: да" in status_text,
            "natural_compare_intent: да" in status_text,
            "natural_open_page_workflow: да" in status_text,
            "browser_mission_report_intents: да" in status_text,
            "natural_browser_report_workflow: да" in status_text,
            "natural_site_check_workflow: да" in status_text,
            "natural_form_workflow_intents: да" in status_text,
            "natural_form_fill_sequence: да" in status_text,
            "natural_form_submit_guard: да" in status_text,
            "chat_automation_intents: да" in help_text,
            "natural_search_workflow: да" in help_text,
            "chat_research_workflow_intents: да" in help_text,
            "browser_mission_report_intents: да" in help_text,
            "natural_form_workflow_intents: да" in help_text,
        ])

        return "\n".join(f"chat_automation_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "chat automation intents",
        check_chat_automation_intents,
        lambda r: "False" not in r and "chat_automation_check_73: True" in r,
    )


def _russian_control_panel_menu_case():
    def check_russian_control_panel_menu():
        from agents import system_agent

        panel_text = (ROOT_DIR / "LocalComet_Control_Panel.py").read_text(encoding="utf-8", errors="replace")
        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})

        labels = [
            "Обзор",
            "Чат / команды",
            "Патчи / Relay",
            "Браузер",
            "Автопилот",
            "Проверки",
            "Отчеты / инструменты",
            "Логи",
            "Главные действия",
            "Создать request",
            "Применить",
            "Открыть отчет",
            "Очистить лог",
        ]

        checks = [
            "Русское меню панели" in panel_text,
            all(label in panel_text for label in labels),
            "russian_control_panel_menu: да" in status_text,
            "control_panel_russian_labels: да" in status_text,
            "russian_command_center_ui: да" in status_text,
            "gray_control_panel_theme: да" in status_text,
            "translucent_gray_button_style: да" in status_text,
            "control_panel_theme_smoke: да" in status_text,
            "russian_control_panel_menu: да" in help_text,
            "control_panel_russian_labels: да" in help_text,
            "russian_command_center_ui: да" in help_text,
            "gray_control_panel_theme: да" in help_text,
            "translucent_gray_button_style: да" in help_text,
            "control_panel_theme_smoke: да" in help_text,
            "PANEL_BG" in panel_text,
            "PANEL_BUTTON_ACTIVE" in panel_text,
            "_configure_gray_theme" in panel_text,
            'style.theme_use("clam")' in panel_text,
            'root.attributes("-alpha", 0.98)' in panel_text,
        ]

        return "\n".join(f"russian_menu_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "russian control panel menu",
        check_russian_control_panel_menu,
        lambda r: "False" not in r and "russian_menu_check_18: True" in r,
    )


def _control_panel_init_smoke_case():
    def check_control_panel_init_smoke():
        import tkinter as tk
        import LocalComet_Control_Panel as panel

        root = tk.Tk()
        root.withdraw()

        try:
            app = panel.LocalCometControlPanel(root)
            root.update_idletasks()

            tab_count = app.notebook.index("end")
            tab_texts = [
                str(app.notebook.tab(index, "text"))
                for index in range(tab_count)
            ]
            required_tabs = [
                "🚀 Command Center",
                "Обзор",
                "Чат / команды",
                "Патчи / Relay",
                "Браузер",
                "Автопилот",
                "Voice",
                "Проверки",
                "Отчеты / инструменты",
                "Логи",
            ]

            checks = [
                panel.LOCALCOMET_VERSION == "v6.02",
                "Command Center Control Panel" in panel.LOCALCOMET_VERSION_LABEL,
                tab_count >= len(required_tabs),
                tab_texts[0] == "🚀 Command Center",
                all(tab in tab_texts for tab in required_tabs),
                hasattr(app, "quick_goal_text") and app.quick_goal_text is not None,
                app.output is not None,
                app.chat_input is not None,
                callable(getattr(app, "refresh_statuses", None)),
                app.dashboard_status_line_var.get().startswith("статус:"),
                callable(getattr(app, "quick_create_request_and_open_chatgpt", None)),
                callable(getattr(app, "import_and_validate", None)),
            ]

            lines = [
                "tab_count: " + str(tab_count),
                "tabs: " + " | ".join(tab_texts),
            ]
            lines.extend(f"panel_init_check_{index}: {value}" for index, value in enumerate(checks, start=1))
            return "\n".join(lines)
        finally:
            root.destroy()

    return _run_case(
        "control panel init smoke",
        check_control_panel_init_smoke,
        lambda r: "False" not in r and "panel_init_check_12: True" in r,
    )



def _llm_offline_graceful_error_case():
    def check_llm_offline_graceful_error():
        from agents import system_agent
        from core import llm

        message = llm.format_llm_offline_message()
        checks = [
            hasattr(llm, "format_llm_offline_message"),
            hasattr(llm, "is_llm_offline_error"),
            "LM Studio Local Server" in message,
            "http://127.0.0.1:1234" in message,
            llm.is_llm_offline_error(message),
            "llm_offline_graceful_error_pack: yes" in system_agent.handle("status", {}),
            "llm_connection_error_handling: yes" in system_agent.handle("status", {}),
            "lmstudio_offline_hint: yes" in system_agent.handle("help", {}),
        ]
        return "\n".join(f"llm_offline_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "llm offline graceful error",
        check_llm_offline_graceful_error,
        lambda r: "False" not in r and "llm_offline_check_8: True" in r,
    )


def _voice_mode_foundation_case():
    def check_voice_mode_foundation():
        from agents import system_agent
        from core.planner import plan
        from core.router import route
        from modules import voice_control

        safe = voice_control.classify_voice_command_safety("status")
        blocked = voice_control.classify_voice_command_safety("оплати заказ банковской картой")
        deps = voice_control.check_voice_dependencies()
        status_text = system_agent.handle("status", {})
        help_text = system_agent.handle("help", {})
        checks = [
            hasattr(voice_control, "check_voice_dependencies"),
            hasattr(voice_control, "transcribe_once"),
            hasattr(voice_control, "speak_text"),
            hasattr(voice_control, "classify_voice_command_safety"),
            safe.get("safe") is True,
            blocked.get("safe") is False,
            blocked.get("needs_confirmation") is True,
            isinstance(deps, dict),
            route("voice status") == "system",
            plan("voice status", "system").get("action") == "voice_status",
            "voice_mode_panel_pack: yes" in status_text,
            "voice_chat_mode: yes" in status_text,
            "voice_chat_replies: yes" in status_text,
            "voice_continuous_dialogue: yes" in status_text,
            "voice_faster_whisper_ru: yes" in status_text,
            "voice_piper_tts: yes" in status_text,
            "voice_vosk_russian_stt: yes" in status_text,
            "voice_push_to_talk: yes" in help_text,
            "voice_command_safety_guard: yes" in status_text,
            "voice_tts: yes" in status_text,
            "voice_session_reports: yes" in status_text,
            "usable_vosk_ru" in deps,
            "vosk_model_path" in deps,
            "usable_faster_whisper_ru" in deps,
            "piper_available" in deps,
        ]
        return "\n".join(f"voice_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    return _run_case(
        "voice mode foundation",
        check_voice_mode_foundation,
        lambda r: "False" not in r and "voice_check_25: True" in r,
    )


def run_fast_stability_test():
    cases = [
        _help_status_case(),
        _llm_offline_graceful_error_case(),
        _voice_mode_foundation_case(),
        _memory_case(),
        _py_compile_case(),
        _project_health_case(),
        _regression_command_suite_case(),
        _auto_verification_case(),
        _relay_status_case(),
        _relay_diagnostics_case(),
        _patch_registry_case(),
        _browser_action_foundation_case(),
        _browser_direct_routing_case(),
        _browser_action_auto_recovery_case(),
        _browser_autopilot_case(),
        _browser_super_case(),
        _chat_automation_intents_case(),
        _russian_control_panel_menu_case(),
        _control_panel_init_smoke_case(),
    ]

    return _finish_cases(cases, "fast")


def run_normal_stability_test():
    cases = [
        _help_status_case(),
        _llm_offline_graceful_error_case(),
        _voice_mode_foundation_case(),
        _memory_case(),
        _py_compile_case(),
        _project_health_case(),
        _regression_command_suite_case(),
        _auto_verification_case(),
        _relay_status_case(),
        _relay_diagnostics_case(),
        _patch_registry_case(),
        _browser_action_foundation_case(),
        _browser_direct_routing_case(),
        _browser_action_auto_recovery_case(),
        _browser_autopilot_case(),
        _browser_super_case(),
        _chat_automation_intents_case(),
        _russian_control_panel_menu_case(),
        _control_panel_init_smoke_case(),
    ]

    def check_router():
        from core.router import route

        return (
            f"browser={route('найди официальный сайт Python')}\n"
            f"stability={route('stability test')}\n"
            f"automation={route('automation status')}"
        )

    cases.append(_run_case("router", check_router, lambda r: "browser" in r and "stability" in r and "automation" in r))

    def check_planner():
        from core.planner import plan

        return json.dumps(
            {
                "stability": plan("stability test", "stability"),
                "automation": plan("automation status", "automation"),
                "gpt_browser": plan("gpt browser status", "gpt_browser"),
            },
            ensure_ascii=False,
        )

    cases.append(_run_case("planner", check_planner, lambda r: '"tool": "stability"' in r and '"tool": "automation"' in r))

    def check_browser_status():
        from agents import browser_agent

        return browser_agent.handle("status", {})

    cases.append(_run_case("browser status", check_browser_status, lambda r: "Browser status" in r))

    return _finish_cases(cases, "normal")


def run_full_stability_test():
    cases = [
        _help_status_case(),
        _llm_offline_graceful_error_case(),
        _voice_mode_foundation_case(),
        _memory_case(),
        _py_compile_case(),
        _project_health_case(),
        _regression_command_suite_case(),
        _auto_verification_case(),
        _relay_status_case(),
        _relay_diagnostics_case(),
        _patch_registry_case(),
        _browser_action_foundation_case(),
        _browser_direct_routing_case(),
        _browser_action_auto_recovery_case(),
        _browser_autopilot_case(),
        _browser_super_case(),
        _chat_automation_intents_case(),
        _russian_control_panel_menu_case(),
        _control_panel_init_smoke_case(),
    ]

    def check_router():
        from core.router import route

        commands = {
            "найди официальный сайт Python": "browser",
            "stability test": "stability",
            "automation status": "automation",
            "auto verify": "system",
            "regression suite": "system",
            "health": "system",
        }

        lines = []

        for command, expected in commands.items():
            routed = route(command)
            lines.append(f"{command}: route={routed}; expected={expected}; ok={routed == expected}")

        return "\n".join(lines)

    cases.append(
        _run_case(
            "router coverage",
            check_router,
            lambda r: "ok=False" not in r and "stability test" in r,
        )
    )

    def check_planner():
        from core.planner import plan

        checks = [
            plan("stability test", "stability").get("tool") == "stability",
            plan("automation status", "automation").get("tool") == "automation",
            plan("gpt browser status", "gpt_browser").get("tool") == "gpt_browser",
            plan("auto verify", "system").get("tool") == "system",
            plan("regression suite", "system").get("tool") == "system",
            plan("health", "system").get("tool") == "system",
        ]

        return "\n".join(f"planner_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    cases.append(
        _run_case(
            "planner coverage",
            check_planner,
            lambda r: "False" not in r and "planner_check_6: True" in r,
        )
    )

    def check_browser_status():
        from agents import browser_agent

        return browser_agent.handle("status", {})

    cases.append(
        _run_case(
            "browser status",
            check_browser_status,
            lambda r: "Browser status" in r,
        )
    )

    def check_command_center_module():
        from modules.command_center_ui import build_command_center

        panel_text = (ROOT_DIR / "LocalComet_Control_Panel.py").read_text(encoding="utf-8", errors="replace")
        ui_text = (ROOT_DIR / "modules" / "command_center_ui.py").read_text(encoding="utf-8", errors="replace")

        checks = [
            callable(build_command_center),
            "build_command_center" in panel_text,
            "modules.command_center_ui" in panel_text,
            "🚀 Command Center" in panel_text,
            "Command Center" in ui_text,
            "REQUEST + CHATGPT" in ui_text or "NEXT ACTION" in ui_text,
            "STATUS" in ui_text or "STATUS CARDS" in ui_text,
            "WORKFLOW" in ui_text,
        ]

        return "\n".join(f"command_center_check_{index}: {value}" for index, value in enumerate(checks, start=1))

    cases.append(
        _run_case(
            "command center module",
            check_command_center_module,
            lambda r: "False" not in r and "command_center_check_8: True" in r,
        )
    )

    return _finish_cases(cases, "full")



def _save_report(cases, score, level, problems):
    _ensure_reports_dir()

    path = REPORTS_DIR / f"{_stamp()}_auto_stability_test.md"
    total = len(cases)

    lines = [
        "# LocalComet Auto Stability Test",
        "",
        f"- Время: {datetime.now().isoformat(timespec='seconds')}",
        f"- MODEL: {MODEL}",
        f"- API: {LMSTUDIO_API}",
        f"- Итог: {score}/{total}",
        f"- Стабильность: {level}",
        "",
        "## Проблемы",
    ]

    if problems:
        for problem in problems:
            lines.append(f"- {problem}")
    else:
        lines.append("- Не обнаружены.")

    lines.extend(["", "## Проверки"])

    for index, case in enumerate(cases, start=1):
        mark = "[OK]" if case["passed"] else "[FAIL]"

        lines.extend([
            "",
            f"### {index}. {mark} {case['name']}",
            "",
            "**Result:**",
            "```text",
            str(case.get("result") or "нет"),
            "```",
        ])

        if case.get("error"):
            lines.extend([
                "",
                "**Error:**",
                "```text",
                str(case.get("error")),
                "```",
            ])

    path.write_text("\n".join(lines), encoding="utf-8")

    set_value("last_stability_report", str(path))
    set_value("last_stability_score", str(score))
    set_value("last_stability_level", level)
    set_value("last_stability_problems", problems)

    return path


def run_auto_stability_test():
    cases = []

    def check_help_status():
        from agents import system_agent

        help_text = system_agent.handle("help", {})
        status_text = system_agent.handle("status", {})

        return (
            "HELP OK: " + str("LocalComet сейчас умеет" in help_text) + "\n"
            "STATUS OK: " + str("Статус LocalComet" in status_text) + "\n"
            "FILE RESPONSE PROMPT OK: " + str("скачиваемый файл response.json" in help_text) + "\n"
            "MANUAL RELAY MODE OK: " + str("надежный ручной режим" in help_text) + "\n"
            "REJECT EMPTY PATCH OK: " + str("reject_empty_confirmation_patch" in status_text) + "\n"
            "RESPONSE MODE STATUS OK: " + str("last_gpt_browser_response_mode" in status_text) + "\n"
            "BUTTON PANEL HELP OK: " + str("LocalComet_Control_Panel.py" in help_text) + "\n"
            "BUTTON PANEL STATUS OK: " + str("button_control_panel" in status_text) + "\n"
            "COMFORT PACK OK: " + str("control_panel_comfort_pack" in status_text) + "\n"
            "ONE CLICK WORKFLOW OK: " + str("one_click_relay_workflow" in status_text) + "\n"
            "CHAT URL SETTINGS OK: " + str("chat_url_settings_panel" in status_text) + "\n"
            "SAFE FULL CYCLE OK: " + str("safe_full_cycle_guards" in status_text) + "\n"
            "TRUE AUTO RELAY OK: " + str("true_auto_relay_cycle" in status_text) + "\n"
            "AUTO RELAY RELIABILITY OK: " + str("auto_relay_reliability_pack" in status_text) + "\n"
            "AUTO DEV TASK CLARIFIER OK: " + str("auto_dev_task_clarifier" in status_text) + "\n"
            "GPT BROWSER THREAD FIX OK: " + str("gpt_browser_thread_affinity_fix" in status_text) + "\n"
            "RESPONSE FRESHNESS GUARD OK: " + str("response_freshness_guard" in status_text) + "\n"
            "UX GROUPED CONTROL PANEL OK: " + str("ux_grouped_control_panel" in status_text) + "\n"
            "SAFE AUTO CYCLE UX PANEL OK: " + str("safe_auto_cycle_ux_panel" in status_text) + "\n"
            "CONTROL PANEL UI REWORK PACK OK: " + str("control_panel_ui_rework_pack: да" in status_text) + "\n"
            "CONTROL PANEL TABS OK: " + str("control_panel_tabs: да" in status_text) + "\n"
            "COMPACT DASHBOARD OK: " + str("compact_dashboard: да" in status_text) + "\n"
            "ORGANIZED RELAY TAB OK: " + str("organized_relay_tab: да" in status_text) + "\n"
            "ORGANIZED BROWSER TAB OK: " + str("organized_browser_tab: да" in status_text) + "\n"
            "ORGANIZED AUTOPILOT TAB OK: " + str("organized_autopilot_tab: да" in status_text) + "\n"
            "PANEL CHAT COMMANDS OK: " + str("control_panel_chat_commands: да" in status_text) + "\n"
            "PANEL CHAT WITH MODEL OK: " + str("panel_chat_with_model: да" in status_text) + "\n"
            "PANEL TEXT COMMAND INPUT OK: " + str("panel_text_command_input: да" in status_text) + "\n"
            "RUSSIAN CONTROL PANEL MENU OK: " + str("russian_control_panel_menu: да" in status_text) + "\n"
            "CONTROL PANEL RUSSIAN LABELS OK: " + str("control_panel_russian_labels: да" in status_text) + "\n"
            "RUSSIAN COMMAND CENTER UI OK: " + str("russian_command_center_ui: да" in status_text) + "\n"
            "GRAY CONTROL PANEL THEME OK: " + str("gray_control_panel_theme: да" in status_text) + "\n"
            "TRANSLUCENT GRAY BUTTON STYLE OK: " + str("translucent_gray_button_style: да" in status_text) + "\n"
            "CONTROL PANEL THEME SMOKE OK: " + str("control_panel_theme_smoke: да" in status_text) + "\n"
            "LLM OFFLINE GRACEFUL ERROR PACK OK: " + str("llm_offline_graceful_error_pack: yes" in status_text) + "\n"
            "LLM CONNECTION ERROR HANDLING OK: " + str("llm_connection_error_handling: yes" in status_text) + "\n"
            "LMSTUDIO OFFLINE HINT OK: " + str("lmstudio_offline_hint: yes" in status_text and "lmstudio_offline_hint: yes" in help_text) + "\n"
            "VOICE MODE PANEL PACK OK: " + str("voice_mode_panel_pack: yes" in status_text) + "\n"
            "VOICE CHAT MODE OK: " + str("voice_chat_mode: yes" in status_text) + "\n"
            "VOICE CHAT REPLIES OK: " + str("voice_chat_replies: yes" in status_text) + "\n"
            "VOICE CONTINUOUS DIALOGUE OK: " + str("voice_continuous_dialogue: yes" in status_text) + "\n"
            "VOICE FASTER WHISPER RU OK: " + str("voice_faster_whisper_ru: yes" in status_text) + "\n"
            "VOICE PIPER TTS OK: " + str("voice_piper_tts: yes" in status_text) + "\n"
            "VOICE VOSK RUSSIAN STT OK: " + str("voice_vosk_russian_stt: yes" in status_text) + "\n"
            "VOICE PUSH TO TALK OK: " + str("voice_push_to_talk: yes" in status_text and "voice_push_to_talk: yes" in help_text) + "\n"
            "VOICE COMMAND SAFETY GUARD OK: " + str("voice_command_safety_guard: yes" in status_text) + "\n"
            "VOICE TTS OK: " + str("voice_tts: yes" in status_text) + "\n"
            "VOICE SESSION REPORTS OK: " + str("voice_session_reports: yes" in status_text) + "\n"
            "CHAT AUTOMATION INTENTS OK: " + str("chat_automation_intents: да" in status_text) + "\n"
            "NATURAL OPEN URL INTENT OK: " + str("natural_open_url_intent: да" in status_text) + "\n"
            "NATURAL SEARCH WORKFLOW OK: " + str("natural_search_workflow: да" in status_text) + "\n"
            "NATURAL PAGE ACTIONS OK: " + str("natural_page_actions: да" in status_text) + "\n"
            "NATURAL PROJECT CHECKS OK: " + str("natural_project_checks: да" in status_text) + "\n"
            "NATURAL BROWSER INTERACTIONS OK: " + str("natural_browser_interactions: да" in status_text) + "\n"
            "CHAT RESEARCH WORKFLOW INTENTS OK: " + str("chat_research_workflow_intents: да" in status_text) + "\n"
            "NATURAL RESEARCH INTENT OK: " + str("natural_research_intent: да" in status_text) + "\n"
            "NATURAL COMPARE INTENT OK: " + str("natural_compare_intent: да" in status_text) + "\n"
            "NATURAL OPEN PAGE WORKFLOW OK: " + str("natural_open_page_workflow: да" in status_text) + "\n"
            "BROWSER MISSION REPORT INTENTS OK: " + str("browser_mission_report_intents: да" in status_text) + "\n"
            "NATURAL BROWSER REPORT WORKFLOW OK: " + str("natural_browser_report_workflow: да" in status_text) + "\n"
            "NATURAL SITE CHECK WORKFLOW OK: " + str("natural_site_check_workflow: да" in status_text) + "\n"
            "NATURAL FORM WORKFLOW INTENTS OK: " + str("natural_form_workflow_intents: да" in status_text) + "\n"
            "NATURAL FORM FILL SEQUENCE OK: " + str("natural_form_fill_sequence: да" in status_text) + "\n"
            "NATURAL FORM SUBMIT GUARD OK: " + str("natural_form_submit_guard: да" in status_text) + "\n"
            "PROJECT HEALTH CENTER PACK OK: " + str("project_health_center_pack: да" in status_text) + "\n"
            "PROJECT HEALTH COMMAND OK: " + str("project_health_command: да" in status_text) + "\n"
            "PROJECT HEALTH REPORT OK: " + str("project_health_report: да" in status_text) + "\n"
            "SAFE HEALTH CHECKS OK: " + str("safe_health_checks: да" in status_text) + "\n"
            "REGRESSION COMMAND SUITE PACK OK: " + str("regression_command_suite_pack: да" in status_text) + "\n"
            "REGRESSION COMMAND SUITE OK: " + str("regression_command_suite: да" in status_text) + "\n"
            "REGRESSION COMMAND REPORT OK: " + str("regression_command_report: да" in status_text) + "\n"
            "SAFE REGRESSION COMMANDS OK: " + str("safe_regression_commands: да" in status_text) + "\n"
            "AUTO VERIFICATION PACK OK: " + str("auto_verification_pack: да" in status_text) + "\n"
            "AUTO VERIFY COMMAND OK: " + str("auto_verify_command: да" in status_text) + "\n"
            "AUTO VERIFY AFTER PATCH OK: " + str("auto_verify_after_patch: да" in status_text) + "\n"
            "AUTO VERIFY REPORTS OK: " + str("auto_verify_reports: да" in status_text) + "\n"
            "PROJECT HEALTH HELP OK: " + str(
                "Project Health Center Pack" in help_text
                and "project_health_center_pack: да" in help_text
                and "health report" in help_text
            ) + "\n"
            "REGRESSION COMMAND HELP OK: " + str(
                "Regression Command Suite" in help_text
                and "regression_command_suite_pack: да" in help_text
                and "regression report" in help_text
            ) + "\n"
            "AUTO VERIFICATION HELP OK: " + str(
                "Auto Verification Pack" in help_text
                and "auto_verification_pack: да" in help_text
                and "auto verify" in help_text
            ) + "\n"
            "CONTROL PANEL UI REWORK HELP OK: " + str(
                "Control Panel UI Rework Pack" in help_text
                and "control_panel_tabs: да" in help_text
                and "organized_autopilot_tab: да" in help_text
            ) + "\n"
            "BROWSER THREAD FIX OK: " + str("browser_thread_affinity_fix" in status_text) + "\n"
            "COMPACT UI PATCH VERSION BAR OK: " + str("compact_ui_patch_version_bar" in status_text) + "\n\n"
            "PATCH REGISTRY OK: " + str("patch_registry: да" in status_text) + "\n"
            "PROJECT BOOST PACK OK: " + str("project_boost_pack: да" in status_text) + "\n"
            "STABILITY TEST MODES OK: " + str("stability_test_modes: да" in status_text) + "\n"
            "ERROR DOCTOR FIX REQUEST OK: " + str("error_doctor_fix_request: да" in status_text) + "\n"
            "LLM PROVIDER FOUNDATION OK: " + str("llm_provider_foundation: да" in status_text) + "\n"
            "CODEX BRIDGE FOUNDATION OK: " + str("codex_bridge_foundation: да" in status_text) + "\n"
            "GIT SAFETY STATUS OK: " + str("git_safety_status: да" in status_text) + "\n"
            "PANEL RELAY DIAGNOSTICS PACK OK: " + str("panel_relay_diagnostics_pack: да" in status_text) + "\n"
            "RELAY DIAGNOSTICS OK: " + str("relay_diagnostics: да" in status_text) + "\n"
            "RELAY SMOKE TEST OK: " + str("relay_smoke_test: да" in status_text) + "\n"
            "RELAY DRY RUN SAFE OK: " + str("relay_dry_run_safe: да" in status_text) + "\n"
            "BROWSER ACTION OPERATOR OK: " + str("browser_action_operator_pack: да" in status_text) + "\n"
            "BROWSER DIRECT ACTION ROUTING FIX OK: " + str("browser_direct_action_routing_fix: да" in status_text) + "\n"
            "BROWSER ACTION AUTO RECOVERY OK: " + str("browser_action_auto_recovery: да" in status_text) + "\n"
            "BROWSER SCREENSHOT ACTION OK: " + str("browser_screenshot_action: да" in status_text) + "\n"
            "BROWSER EXTRACT LINKS INPUTS OK: " + str("browser_extract_links_inputs: да" in status_text) + "\n"
            "BROWSER TASK RUNNER OK: " + str("browser_task_runner: да" in status_text) + "\n"
            "BROWSER ACTION SAFETY GUARD OK: " + str("browser_action_safety_guard: да" in status_text) + "\n"
            "BROWSER MULTI STEP WORKFLOW PACK OK: " + str("browser_multi_step_workflow_pack: да" in status_text) + "\n"
            "BROWSER WORKFLOW RUNNER OK: " + str("browser_workflow_runner: да" in status_text) + "\n"
            "BROWSER WORKFLOW REPORTS OK: " + str("browser_workflow_reports: да" in status_text) + "\n"
            "BROWSER AUTOPILOT OPERATOR PACK OK: " + str("browser_autopilot_operator_pack: да" in status_text) + "\n"
            "BROWSER AUTOPILOT PLAN OK: " + str("browser_autopilot_plan: да" in status_text) + "\n"
            "BROWSER AUTOPILOT RUN OK: " + str("browser_autopilot_run: да" in status_text) + "\n"
            "BROWSER AUTOPILOT DRY RUN OK: " + str("browser_autopilot_dry_run: да" in status_text) + "\n"
            "BROWSER AUTOPILOT SAFETY GUARD OK: " + str("browser_autopilot_safety_guard: да" in status_text) + "\n"
            "BROWSER AUTOPILOT REPORTS OK: " + str("browser_autopilot_reports: да" in status_text) + "\n"
            "BROWSER OBSERVE OK: " + str("browser_observe: да" in status_text) + "\n"
            "BROWSER SUPER OPERATOR PACK OK: " + str("browser_super_operator_pack: да" in status_text) + "\n"
            "BROWSER RESEARCH REPORTS OK: " + str("browser_research_reports: да" in status_text) + "\n"
            "BROWSER PLATFORM SITE WORKFLOW OK: " + str("browser_platform_site_workflow: да" in status_text) + "\n"
            "BROWSER YOUTUBE SEARCH OK: " + str("browser_youtube_search: да" in status_text) + "\n"
            "NATURAL COMMAND INTENTS OK: " + str("natural_command_intents: да" in status_text) + "\n"
            "BROWSER PAGE AUDIT OK: " + str("browser_page_audit: да" in status_text) + "\n"
            "BROWSER FORM MAP OK: " + str("browser_form_map: да" in status_text) + "\n"
            "BROWSER SUPER SAFETY GUARD OK: " + str("browser_super_safety_guard: да" in status_text) + "\n"
            "BROWSER SUPER HELP OK: " + str(
                "Browser Super Operator Pack" in help_text
                and "browser_super_operator_pack: да" in help_text
                and "browser research <topic>" in help_text
            ) + "\n"
            + help_text[:4000]
            + "\n\n"
            + status_text[:4000]
        )

    cases.append(_run_case(
        "help/status",
        check_help_status,
        lambda r: (
            "HELP OK: True" in r
            and "STATUS OK: True" in r
            and "FILE RESPONSE PROMPT OK: True" in r
            and "MANUAL RELAY MODE OK: True" in r
            and "REJECT EMPTY PATCH OK: True" in r
            and "RESPONSE MODE STATUS OK: True" in r
            and "BUTTON PANEL HELP OK: True" in r
            and "BUTTON PANEL STATUS OK: True" in r
            and "COMFORT PACK OK: True" in r
            and "ONE CLICK WORKFLOW OK: True" in r
            and "CHAT URL SETTINGS OK: True" in r
            and "SAFE FULL CYCLE OK: True" in r
            and "TRUE AUTO RELAY OK: True" in r
            and "AUTO RELAY RELIABILITY OK: True" in r
            and "AUTO DEV TASK CLARIFIER OK: True" in r
            and "GPT BROWSER THREAD FIX OK: True" in r
            and "RESPONSE FRESHNESS GUARD OK: True" in r
            and "UX GROUPED CONTROL PANEL OK: True" in r
            and "SAFE AUTO CYCLE UX PANEL OK: True" in r
            and "CONTROL PANEL UI REWORK PACK OK: True" in r
            and "CONTROL PANEL TABS OK: True" in r
            and "COMPACT DASHBOARD OK: True" in r
            and "ORGANIZED RELAY TAB OK: True" in r
            and "ORGANIZED BROWSER TAB OK: True" in r
            and "ORGANIZED AUTOPILOT TAB OK: True" in r
            and "PANEL CHAT COMMANDS OK: True" in r
            and "PANEL CHAT WITH MODEL OK: True" in r
            and "PANEL TEXT COMMAND INPUT OK: True" in r
            and "RUSSIAN CONTROL PANEL MENU OK: True" in r
            and "CONTROL PANEL RUSSIAN LABELS OK: True" in r
            and "RUSSIAN COMMAND CENTER UI OK: True" in r
            and "GRAY CONTROL PANEL THEME OK: True" in r
            and "TRANSLUCENT GRAY BUTTON STYLE OK: True" in r
            and "CONTROL PANEL THEME SMOKE OK: True" in r
            and "LLM OFFLINE GRACEFUL ERROR PACK OK: True" in r
            and "LLM CONNECTION ERROR HANDLING OK: True" in r
            and "LMSTUDIO OFFLINE HINT OK: True" in r
            and "VOICE MODE PANEL PACK OK: True" in r
            and "VOICE CHAT MODE OK: True" in r
            and "VOICE CHAT REPLIES OK: True" in r
            and "VOICE CONTINUOUS DIALOGUE OK: True" in r
            and "VOICE FASTER WHISPER RU OK: True" in r
            and "VOICE PIPER TTS OK: True" in r
            and "VOICE VOSK RUSSIAN STT OK: True" in r
            and "VOICE PUSH TO TALK OK: True" in r
            and "VOICE COMMAND SAFETY GUARD OK: True" in r
            and "VOICE TTS OK: True" in r
            and "VOICE SESSION REPORTS OK: True" in r
            and "CHAT AUTOMATION INTENTS OK: True" in r
            and "NATURAL OPEN URL INTENT OK: True" in r
            and "NATURAL SEARCH WORKFLOW OK: True" in r
            and "NATURAL PAGE ACTIONS OK: True" in r
            and "NATURAL PROJECT CHECKS OK: True" in r
            and "NATURAL BROWSER INTERACTIONS OK: True" in r
            and "CHAT RESEARCH WORKFLOW INTENTS OK: True" in r
            and "NATURAL RESEARCH INTENT OK: True" in r
            and "NATURAL COMPARE INTENT OK: True" in r
            and "NATURAL OPEN PAGE WORKFLOW OK: True" in r
            and "BROWSER MISSION REPORT INTENTS OK: True" in r
            and "NATURAL BROWSER REPORT WORKFLOW OK: True" in r
            and "NATURAL SITE CHECK WORKFLOW OK: True" in r
            and "NATURAL FORM WORKFLOW INTENTS OK: True" in r
            and "NATURAL FORM FILL SEQUENCE OK: True" in r
            and "NATURAL FORM SUBMIT GUARD OK: True" in r
            and "PROJECT HEALTH CENTER PACK OK: True" in r
            and "PROJECT HEALTH COMMAND OK: True" in r
            and "PROJECT HEALTH REPORT OK: True" in r
            and "SAFE HEALTH CHECKS OK: True" in r
            and "PROJECT HEALTH HELP OK: True" in r
            and "REGRESSION COMMAND SUITE PACK OK: True" in r
            and "REGRESSION COMMAND SUITE OK: True" in r
            and "REGRESSION COMMAND REPORT OK: True" in r
            and "SAFE REGRESSION COMMANDS OK: True" in r
            and "REGRESSION COMMAND HELP OK: True" in r
            and "AUTO VERIFICATION PACK OK: True" in r
            and "AUTO VERIFY COMMAND OK: True" in r
            and "AUTO VERIFY AFTER PATCH OK: True" in r
            and "AUTO VERIFY REPORTS OK: True" in r
            and "AUTO VERIFICATION HELP OK: True" in r
            and "CONTROL PANEL UI REWORK HELP OK: True" in r
            and "BROWSER THREAD FIX OK: True" in r
            and "COMPACT UI PATCH VERSION BAR OK: True" in r
            and "PATCH REGISTRY OK: True" in r
            and "PROJECT BOOST PACK OK: True" in r
            and "STABILITY TEST MODES OK: True" in r
            and "ERROR DOCTOR FIX REQUEST OK: True" in r
            and "LLM PROVIDER FOUNDATION OK: True" in r
            and "CODEX BRIDGE FOUNDATION OK: True" in r
            and "GIT SAFETY STATUS OK: True" in r
            and "PANEL RELAY DIAGNOSTICS PACK OK: True" in r
            and "RELAY DIAGNOSTICS OK: True" in r
            and "RELAY SMOKE TEST OK: True" in r
            and "RELAY DRY RUN SAFE OK: True" in r
            and "BROWSER ACTION OPERATOR OK: True" in r
            and "BROWSER DIRECT ACTION ROUTING FIX OK: True" in r
            and "BROWSER ACTION AUTO RECOVERY OK: True" in r
            and "BROWSER SCREENSHOT ACTION OK: True" in r
            and "BROWSER EXTRACT LINKS INPUTS OK: True" in r
            and "BROWSER TASK RUNNER OK: True" in r
            and "BROWSER ACTION SAFETY GUARD OK: True" in r
            and "BROWSER MULTI STEP WORKFLOW PACK OK: True" in r
            and "BROWSER WORKFLOW RUNNER OK: True" in r
            and "BROWSER WORKFLOW REPORTS OK: True" in r
            and "BROWSER AUTOPILOT OPERATOR PACK OK: True" in r
            and "BROWSER AUTOPILOT PLAN OK: True" in r
            and "BROWSER AUTOPILOT RUN OK: True" in r
            and "BROWSER AUTOPILOT DRY RUN OK: True" in r
            and "BROWSER AUTOPILOT SAFETY GUARD OK: True" in r
            and "BROWSER AUTOPILOT REPORTS OK: True" in r
            and "BROWSER OBSERVE OK: True" in r
            and "BROWSER SUPER OPERATOR PACK OK: True" in r
            and "BROWSER RESEARCH REPORTS OK: True" in r
            and "BROWSER PLATFORM SITE WORKFLOW OK: True" in r
            and "BROWSER YOUTUBE SEARCH OK: True" in r
            and "NATURAL COMMAND INTENTS OK: True" in r
            and "BROWSER PAGE AUDIT OK: True" in r
            and "BROWSER FORM MAP OK: True" in r
            and "BROWSER SUPER SAFETY GUARD OK: True" in r
            and "BROWSER SUPER HELP OK: True" in r
        ),
    ))

    def check_memory():
        from agents import system_agent

        return system_agent.handle("memory", {})

    cases.append(_run_case("memory", check_memory, lambda r: bool(str(r).strip())))
    cases.append(_llm_offline_graceful_error_case())
    cases.append(_voice_mode_foundation_case())
    cases.append(_project_health_case())
    cases.append(_regression_command_suite_case())
    cases.append(_auto_verification_case())
    cases.append(_browser_super_case())
    cases.append(_chat_automation_intents_case())
    cases.append(_russian_control_panel_menu_case())
    cases.append(_control_panel_init_smoke_case())

    def check_router():
        from core.router import route

        browser_route = route("найди официальный сайт Python")
        stability_route = route("stability test")
        automation_status_route = route("automation status")
        after_patch_route = route("after patch")
        dev_task_route = route("dev task улучши браузер")
        browser_task_route = route("browser task найди Python")
        browser_batch_route = route("browser batch Godot")
        browser_compare_route = route("browser compare local llm")
        browser_research_route = route("browser research local llm")
        browser_tilda_route = route("напиши сайт автосервиса используй платформу Tilda")
        pc_task_route = route("pc task открой блокнот")
        pc_batch_route = route("pc batch открой блокнот")
        multi_task_route = route("multi task найди Python и открой папку отчетов")
        task_status_route = route("task status")
        gpt_browser_route = route("gpt browser status")
        gpt_browser_close_route = route("gpt browser close")

        return (
            f"route('gpt browser status') = {gpt_browser_route}\n"
            f"route('gpt browser close') = {gpt_browser_close_route}\n"
            f"route('найди официальный сайт Python') = {browser_route}\n"
            f"route('stability test') = {stability_route}\n"
            f"route('automation status') = {automation_status_route}\n"
            f"route('after patch') = {after_patch_route}\n"
            f"route('dev task ...') = {dev_task_route}\n"
            f"route('browser task ...') = {browser_task_route}\n"
            f"route('browser batch ...') = {browser_batch_route}\n"
            f"route('browser compare ...') = {browser_compare_route}\n"
            f"route('browser research ...') = {browser_research_route}\n"
            f"route('Tilda site ...') = {browser_tilda_route}\n"
            f"route('pc task ...') = {pc_task_route}\n"
            f"route('pc batch ...') = {pc_batch_route}\n"
            f"route('multi task ...') = {multi_task_route}\n"
            f"route('task status') = {task_status_route}"
        )

    cases.append(_run_case(
        "router",
        check_router,
        lambda r: (
            "route('gpt browser status') = gpt_browser" in r
            and "route('gpt browser close') = gpt_browser" in r
            and "route('найди официальный сайт Python') = browser" in r
            and "route('stability test') = stability" in r
            and "route('automation status') = automation" in r
            and "route('after patch') = automation" in r
            and "route('dev task ...') = automation" in r
            and "route('browser task ...') = browser" in r
            and "route('browser batch ...') = automation" in r
            and "route('browser compare ...') = browser" in r
            and "route('browser research ...') = browser" in r
            and "route('Tilda site ...') = browser" in r
            and "route('pc task ...') = automation" in r
            and "route('pc batch ...') = automation" in r
            and "route('multi task ...') = automation" in r
            and "route('task status') = automation" in r
        ),
    ))

    def check_planner():
        from core.planner import plan

        browser_plan = plan("browser last", "browser")
        stability_plan = plan("stability test", "stability")
        automation_status_plan = plan("automation status", "automation")
        automation_after_patch_plan = plan("after patch", "automation")
        automation_dev_plan = plan("dev task улучши браузер", "automation")
        automation_multi_plan = plan("multi task найди Python и открой папку отчетов", "automation")
        automation_browser_batch_plan = plan("browser batch Godot", "automation")
        automation_pc_batch_plan = plan("pc batch открой блокнот", "automation")
        gpt_browser_plan = plan("gpt browser status", "gpt_browser")
        gpt_browser_wait_plan = plan("gpt browser wait 600", "gpt_browser")
        gpt_browser_repair_plan = plan("gpt browser repair response", "gpt_browser")
        gpt_browser_close_plan = plan("gpt browser close", "gpt_browser")
        gpt_browser_full_apply_plan = plan("gpt browser full apply", "gpt_browser")

        return json.dumps(
            {
                "gpt_browser_plan": gpt_browser_plan,
                "gpt_browser_wait_plan": gpt_browser_wait_plan,
                "gpt_browser_repair_plan": gpt_browser_repair_plan,
                "gpt_browser_close_plan": gpt_browser_close_plan,
                "gpt_browser_full_apply_plan": gpt_browser_full_apply_plan,
                "browser_plan": browser_plan,
                "stability_plan": stability_plan,
                "automation_status_plan": automation_status_plan,
                "automation_after_patch_plan": automation_after_patch_plan,
                "automation_dev_plan": automation_dev_plan,
                "automation_multi_plan": automation_multi_plan,
                "automation_browser_batch_plan": automation_browser_batch_plan,
                "automation_pc_batch_plan": automation_pc_batch_plan,
            },
            ensure_ascii=False,
            indent=2,
        )

    cases.append(_run_case(
        "planner",
        check_planner,
        lambda r: (
            '"tool": "gpt_browser"' in r
            and '"action": "repair_response"' in r
            and '"action": "close"' in r
            and '"tool": "chatgpt_relay"' in r
            and '"timeout_sec": 600' in r
            and '"tool": "browser"' in r
            and '"tool": "stability"' in r
            and r.count('"tool": "automation"') >= 6
            and '"action": "dev_task"' in r
            and '"action": "after_patch"' in r
            and '"action": "status"' in r
            and '"action": "multi_task"' in r
            and '"action": "browser_batch"' in r
            and '"action": "pc_batch"' in r
        ),
    ))

    def check_browser_search():
        from agents import browser_agent

        return browser_agent.handle("search", {"query": "Python official website"})

    cases.append(_run_case(
        "browser search",
        check_browser_search,
        lambda r: "Поиск сохранен" in r or "Ищу через" in r,
    ))

    def check_browser_last():
        from agents import browser_agent

        return browser_agent.handle("last_search", {})

    cases.append(_run_case(
        "browser last",
        check_browser_last,
        lambda r: "Python official website" in r and "Последний browser-поиск" in r,
    ))

    def check_browser_open_first_hard():
        from agents import browser_agent
        from modules.browser import close_browser_for_test

        close_browser_for_test()
        return browser_agent.handle("open_first_result", {})

    cases.append(_run_case(
        "browser open first hard recovery",
        check_browser_open_first_hard,
        lambda r: "Открыл первый результат" in r and "Не удалось" not in r,
    ))

    def check_browser_read_hard():
        from agents import browser_agent
        from modules.browser import close_browser_for_test

        close_browser_for_test()
        return browser_agent.handle("read_page", {})

    cases.append(_run_case(
        "browser read hard recovery",
        check_browser_read_hard,
        lambda r: ("URL:" in r and "TITLE:" in r) or "Браузер был восстановлен" in r,
    ))

    def check_browser_status():
        from agents import browser_agent

        return browser_agent.handle("status", {})

    cases.append(_run_case(
        "browser status",
        check_browser_status,
        lambda r: "current_url" in r and "last_browser_query" in r and "last_browser_error" in r,
    ))

    def check_relay_status():
        from agents import chatgpt_relay_agent
        from agents import automation_agent
        from agents import system_agent

        relay_status = chatgpt_relay_agent.handle("status", {})
        automation_status = automation_agent.handle("status", {})
        parser_status = automation_agent.handle("parser_diagnostics", {})
        system_status = system_agent.handle("status", {})

        try:
            from agents import gpt_browser_agent
            gpt_browser_status = gpt_browser_agent.handle("status", {})
        except Exception as e:
            gpt_browser_status = f"GPT Browser status error: {e}"

        return (
            str(relay_status)
            + "\n\n--- AUTOMATION STATUS ---\n"
            + str(automation_status)
            + "\n\n--- PARSER DIAGNOSTICS ---\n"
            + str(parser_status)
            + "\n\n--- GPT BROWSER STATUS ---\n"
            + str(gpt_browser_status)
            + "\n\n--- SYSTEM STATUS ---\n"
            + str(system_status)
        )

    cases.append(_run_case(
        "relay/automation/parser status",
        check_relay_status,
        lambda r: (
            "ChatGPT Relay status" in r
            and "request.md" in r
            and "Automation Command Center status" in r
            and "dev task" in r
            and "browser_read_first_query: Godot official website" in r
            and "multi_browser_query: официальный сайт Python" in r
            and "multi_pc_goal: открой папку отчетов" in r
            and "pc_batch_reports_only: ok" in r
            and "GPT Browser Bridge status" in r
            and "default_wait_timeout: 600" in r
            and "response_mode:" in r
            and "fixed_downloads_import" in r
            and "reliable_manual_relay_mode" in r
            and "reject_empty_confirmation_patch" in r
        ),
    ))

    def check_browser_profile_ignore():
        from modules.browser_profile_ignore import is_browser_profile_path

        lock_path = ROOT_DIR / "Projects" / "BrowserProfile" / "SingletonLock"
        normal_path = ROOT_DIR / "modules" / "stability_test.py"

        return (
            f"browserprofile_ignore_ok: {is_browser_profile_path(lock_path)}\n"
            f"normal_file_ignore_ok: {not is_browser_profile_path(normal_path)}"
        )

    cases.append(_run_case(
        "browser profile ignore guard",
        check_browser_profile_ignore,
        lambda r: "browserprofile_ignore_ok: True" in r and "normal_file_ignore_ok: True" in r,
    ))

    score = sum(1 for case in cases if case["passed"])
    total = len(cases)

    if score == total:
        level = "отличная"
    elif score >= max(1, int(total * 0.7)):
        level = "хорошая"
    elif score >= max(1, int(total * 0.5)):
        level = "средняя"
    else:
        level = "плохая"

    problems = [
        f"{case['name']}: {case['error'] or case['result']}"
        for case in cases
        if not case["passed"]
    ]

    report_path = _save_report(cases, score, level, problems)

    lines = [
        "Auto Stability Test завершен.",
        f"Итог: {score}/{total}",
        f"Стабильность: {level}",
        f"Отчет: {report_path}",
        "",
        "Проверки:",
    ]

    for case in cases:
        mark = "[OK]" if case["passed"] else "[FAIL]"
        lines.append(f"- {mark} {case['name']}")

    lines.append("")
    lines.append("Проблемы:")

    if problems:
        for problem in problems:
            lines.append("- " + _short(problem, 400))
    else:
        lines.append("- Не обнаружены.")

    return "\n".join(lines)
````

### ПУТЬ: modules/storage_cleanup_plan_ru.py (247 строк, 8850 байт)

````python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from modules.project_paths import build_retention_plan, get_project_root, localcomet_reports_dir, retention_runtime_roots

STORAGE_CLEANUP_PLAN_VERSION = "v6.79"
STORAGE_CLEANUP_PLAN_NAME = "LocalComet Storage Cleanup Plan Generator RU"

ROOT_PATH = get_project_root()
OUTPUT_DIR = localcomet_reports_dir(ROOT_PATH)
STORAGE_CLEANUP_JSON = OUTPUT_DIR / "storage_cleanup_plan.json"
STORAGE_CLEANUP_MD = OUTPUT_DIR / "storage_cleanup_plan.md"
REPO_WEIGHT_JSON = OUTPUT_DIR / "repo_weight_report.json"
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"

EXTERNAL_BACKUP_NOTE = (
    "An external backup folder at C:\\Users\\DNS\\Documents\\LocalAgent_Backups "
    "was noted (~32.9 GB). This path is outside the repository root "
    "and was not scanned by the internal audit. Manual review and cleanup required."
)

NO_DELETION_WARNING = (
    "NO FILES WERE DELETED. This is a plan-only report. "
    "Cleanup requires separate explicit approval."
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _detect_base_version() -> str:
    try:
        for line in CONTROL_PANEL_PATH.read_text(encoding="utf-8").split("\n"):
            if "LOCALCOMET_VERSION" in line and "=" in line:
                return line.split("=")[-1].strip().strip("\"'")
    except Exception:
        pass
    return "unknown"


def _load_source_report() -> Dict[str, Any]:
    result: Dict[str, Any] = {"found": False, "data": {}, "warning": ""}
    if not REPO_WEIGHT_JSON.exists():
        result["warning"] = "repo_weight_report.json not found. Run 'localcomet repo weight audit' first."
        return result
    try:
        data = json.loads(REPO_WEIGHT_JSON.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            result["warning"] = "repo_weight_report.json contains invalid data (not a dict)."
            return result
        result["found"] = True
        result["data"] = data
    except json.JSONDecodeError:
        result["warning"] = "repo_weight_report.json is invalid JSON. Run 'localcomet repo weight audit' to regenerate."
    except Exception as e:
        result["warning"] = f"Error reading repo_weight_report.json: {e}"
    return result


def _build_candidates(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    data = source.get("data", {})
    if not source.get("found"):
        return candidates

    dirs = data.get("top_directories", [])

    for d in dirs:
        dp = d.get("path", "")
        sz = d.get("size_bytes", 0)
        sm = d.get("size_mb", 0)
        if not dp:
            continue

        if "screenshots" in dp.lower():
            candidates.append({
                "path": dp,
                "size_bytes": sz,
                "size_mb": sm,
                "category": "screenshots",
                "action": "review",
                "priority": "high",
                "reason": f"Screenshot directory at {dp} consumes {sm} MB.",
            })

        if "opencode_backup" in dp.lower() or "backup" in dp.lower():
            candidates.append({
                "path": dp,
                "size_bytes": sz,
                "size_mb": sm,
                "category": "backup",
                "action": "review",
                "priority": "medium",
                "reason": f"Backup directory at {dp} consumes {sm} MB.",
            })

    for bd in data.get("backup_directories", []):
        bp = bd.get("path", "")
        bz = bd.get("size_bytes", 0)
        bm = bd.get("size_mb", 0)
        if bp and not any(c.get("path") == bp for c in candidates):
            candidates.append({
                "path": bp,
                "size_bytes": bz,
                "size_mb": bm,
                "category": "backup",
                "action": "review",
                "priority": "medium",
                "reason": f"Backup directory at {bp} consumes {bm} MB.",
            })

    for cd in data.get("cache_directories", []):
        cp = cd.get("path", "")
        cz = cd.get("size_bytes", 0)
        cm = cd.get("size_mb", 0)
        if cp and not any(c.get("path") == cp for c in candidates):
            candidates.append({
                "path": cp,
                "size_bytes": cz,
                "size_mb": cm,
                "category": "cache",
                "action": "clean",
                "priority": "low",
                "reason": f"Cache directory at {cp} consumes {cm} MB.",
            })

    for gd in data.get("generated_artifact_directories", []):
        gp = gd.get("path", "")
        gz = gd.get("size_bytes", 0)
        gm = gd.get("size_mb", 0)
        if gp and not any(c.get("path") == gp for c in candidates):
            candidates.append({
                "path": gp,
                "size_bytes": gz,
                "size_mb": gm,
                "category": "generated_artifact",
                "action": "regenerate",
                "priority": "low",
                "reason": f"Generated artifact directory at {gp} consumes {gm} MB.",
            })

    return candidates


def _estimate_reclaimable(candidates: List[Dict[str, Any]]) -> float:
    total = 0.0
    for c in candidates:
        if c.get("category") in ("cache", "backup", "generated_artifact"):
            total += c.get("size_mb", 0)
    return round(total, 2)


def generate() -> Dict[str, Any]:
    return build_retention_plan(ROOT_PATH, retention_runtime_roots(ROOT_PATH))


def _write_plan(payload: Dict[str, Any]) -> Dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_CLEANUP_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    lines = [
        "# LocalComet Runtime Retention Plan",
        "",
        f"- mode: {payload.get('mode')}",
        f"- version: {payload.get('version')}",
        f"- dry_run: {payload.get('dry_run')}",
        f"- candidate_count: {payload.get('totals', {}).get('candidate_count')}",
        f"- protected_count: {payload.get('totals', {}).get('protected_count')}",
        f"- rejected_count: {payload.get('totals', {}).get('rejected_count')}",
        "",
        "## Policy",
        "",
    ]
    for key, value in payload.get("policy", {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    lines.extend(["## Cleanup Candidates", ""])
    for c in payload.get("candidates", []):
        lines.append(f"- {c.get('path', '')} ({c.get('size_bytes', 0)} bytes)")
        lines.append(f"  - {c.get('reason', '')}")

    if not payload.get("candidates"):
        lines.append("(none found)")
    lines.append("")

    lines.extend(["## Dangerous Cleanup Warning", "", NO_DELETION_WARNING, ""])

    STORAGE_CLEANUP_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "json": str(STORAGE_CLEANUP_JSON.relative_to(ROOT_PATH)),
        "md": str(STORAGE_CLEANUP_MD.relative_to(ROOT_PATH)),
    }


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "storage_cleanup_plan_status",
        "version": STORAGE_CLEANUP_PLAN_VERSION,
        "json_exists": STORAGE_CLEANUP_JSON.exists(),
        "md_exists": STORAGE_CLEANUP_MD.exists(),
    }


def report() -> Dict[str, Any]:
    payload = generate()
    paths = _write_plan(payload)
    return {
        "ok": True,
        "mode": "storage_cleanup_plan_report",
        "version": STORAGE_CLEANUP_PLAN_VERSION,
        "paths": paths,
        "plan": payload,
    }


def is_storage_cleanup_plan_command(command: str) -> bool:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    return lowered in {
        "localcomet storage cleanup plan",
        "storage cleanup plan",
        "cleanup plan",
    } or lowered.startswith("localcomet storage cleanup plan ")


def dispatch(command: str) -> Dict[str, Any]:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    if lowered in {"localcomet storage cleanup plan", "storage cleanup plan", "cleanup plan"}:
        result = report()
        return {"ok": True, "handled": True, "mode": "storage_cleanup_plan_generated", "version": STORAGE_CLEANUP_PLAN_VERSION, "paths": result.get("paths", {})}
    if lowered in {"localcomet storage cleanup plan status", "storage cleanup plan status", "cleanup plan status"}:
        return status()
    return {"ok": False, "mode": "storage_cleanup_plan_unknown", "version": STORAGE_CLEANUP_PLAN_VERSION, "command": command, "hint": "Use: localcomet storage cleanup plan"}


if __name__ == "__main__":
    result = dispatch("localcomet storage cleanup plan")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
````

### ПУТЬ: modules/strict_project_stability_ru.py (624 строк, 21252 байт)

````python
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
````

### ПУТЬ: modules/swiss_knife_skill_launcher.py (876 строк, 32318 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import uuid


from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
SWISS_DIR = PROJECTS_DIR / "PCAgent" / "SwissKnife"
REQUESTS_DIR = SWISS_DIR / "Requests"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "swiss_knife_skill_launcher"

SWISS_VERSION = "swiss_knife_v1"

NEGATION_AWARE_FORBIDDEN_TERMS = [
    "spam",
    "спам",
    "mass mailing",
    "массовая рассылка",
    "bulk dm",
    "scrape emails",
    "собери email",
    "купить базу",
]

STRICT_FORBIDDEN_TERMS = [
    "password",
    "пароль",
    "token",
    "secret",
    "private key",
    "api key",
    "ssh",
    "bank",
    "банк",
    "payment",
    "casino",
    "ставк",
    "delete",
    "удали",
    "format",
    "shell",
    "cmd",
    "powershell",
    "admin",
    "администратор",
]

SAFE_NEGATION_PATTERNS = [
    "без спама",
    "без spam",
    "no spam",
    "not spam",
    "without spam",
    "не спам",
    "не использовать спам",
    "не делать спам",
    "без массовой рассылки",
    "без рассылки",
    "без парсинга email",
    "без сбора email",
    "no mass mailing",
    "without mass mailing",
    "no bulk dm",
    "without bulk dm",
    "no email scraping",
    "without email scraping",
]

SWISS_SKILLS = [
    {
        "id": "research_report",
        "name": "Research Report",
        "category": "business_research",
        "description": "Собрать структуру исследования, вопросы, источники и отчётный план.",
        "best_for": ["рынок", "конкуренты", "ниша", "технология", "продукт", "стратегия"],
        "safe_routes": ["pc web <query>", "pc agentos firewall <intent>", "pc swiss request <goal>"],
        "outputs": ["research_brief.md", "source_questions.json", "report_outline.md"],
        "risk": "medium",
        "blocked": ["платный доступ без разрешения", "секретные данные", "персональные данные без основания"],
    },
    {
        "id": "leadgen_brief",
        "name": "Leadgen Brief",
        "category": "business_growth",
        "description": "Подготовить безопасный план лидогенерации без спама и незаконного сбора данных.",
        "best_for": ["лиды", "клиенты", "b2b", "воронка", "ICP", "оффер"],
        "safe_routes": ["pc swiss leadgen <goal>", "pc web <query>", "pc swiss request <goal>"],
        "outputs": ["leadgen_brief.md", "icp.json", "outreach_draft.md"],
        "risk": "high",
        "blocked": ["спам", "массовая рассылка", "парсинг email", "обход ограничений платформ"],
    },
    {
        "id": "pdf_analysis",
        "name": "PDF Analysis",
        "category": "documents",
        "description": "Разобрать PDF/документ: summary, тезисы, идеи для LocalComet, task extraction.",
        "best_for": ["pdf", "документ", "инструкция", "методичка", "отчёт", "презентация"],
        "safe_routes": ["pc swiss pdf <goal>", "pc agents project-profile", "pc swiss request <goal>"],
        "outputs": ["pdf_summary.md", "action_items.json", "integration_notes.md"],
        "risk": "low",
        "blocked": ["секреты", "персональные данные", "копирование закрытых материалов целиком"],
    },
    {
        "id": "website_draft",
        "name": "Website Draft",
        "category": "creation",
        "description": "Создать безопасный план/черновик сайта, landing page или demo workspace.",
        "best_for": ["сайт", "лендинг", "страница", "demo-site", "прототип"],
        "safe_routes": ["pc demo site plan", "pc demo site dry", "pc demo site request", "pc swiss request <goal>"],
        "outputs": ["site_brief.md", "page_structure.json", "copy_draft.md"],
        "risk": "medium",
        "blocked": ["автоматический деплой с секретами", "shell без review", "внешние платежи"],
    },
    {
        "id": "document_automation",
        "name": "Document Automation",
        "category": "automation",
        "description": "План автоматизации файлов, папок, отчётов и повторяющихся документных задач.",
        "best_for": ["документы", "папка", "отчёты", "таблицы", "повторяющаяся задача"],
        "safe_routes": ["pc agentos firewall <intent>", "pc edit <goal>", "pc swiss request <goal>"],
        "outputs": ["automation_plan.md", "file_flow.json", "safe_patch_request.md"],
        "risk": "high",
        "blocked": ["удаление файлов", "перезапись без backup", "секреты", "произвольный shell"],
    },
    {
        "id": "project_patch",
        "name": "Project Patch",
        "category": "coding",
        "description": "Преобразовать идею в безопасный response.json patch workflow.",
        "best_for": ["код", "модуль", "исправь", "добавь", "патч", "response.json"],
        "safe_routes": ["pc agents project-profile", "pc edit <goal>", "Auto Verification", "Full Stability"],
        "outputs": ["request.md", "response.json", "test_plan.md"],
        "risk": "high",
        "blocked": ["direct protected file edit", "no tests", "без rollback"],
    },
    {
        "id": "ui_action",
        "name": "UI Action Suggestion",
        "category": "desktop",
        "description": "Подсказать действие по экрану через UI parser, без кликов и ввода.",
        "best_for": ["нажми", "окно", "кнопка", "ui", "экран", "интерфейс"],
        "safe_routes": ["pc ui parse", "pc ui find <text>", "pc ui suggest <goal>", "pc desktop dry click <x> <y>"],
        "outputs": ["ui_elements.json", "action_suggestion.json", "dry_run_command.md"],
        "risk": "medium",
        "blocked": ["blind click", "typing secrets", "auto-submit"],
    },
    {
        "id": "agent_onboarding",
        "name": "Agent Onboarding",
        "category": "education",
        "description": "Объяснить агентность, подготовить AGENTS.md, demo workspace и quickstart.",
        "best_for": ["объясни", "онбординг", "агент", "как пользоваться", "quickstart"],
        "safe_routes": ["pc onboard explain", "pc onboard checklist", "pc onboard agents.md"],
        "outputs": ["AGENTS_LocalComet_QUICKSTART.md", "onboarding_checklist.json"],
        "risk": "low",
        "blocked": ["admin terminal", "auto yes", "install unknown scripts"],
    },
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    SWISS_DIR.mkdir(parents=True, exist_ok=True)
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _contains_any(goal, words):
    lower = _norm(goal)
    return any(_norm(word) in lower for word in words)


def _has_safe_negation(lower, term):
    if not term:
        return False

    if any(pattern in lower for pattern in SAFE_NEGATION_PATTERNS):
        if term in {"spam", "спам", "mass mailing", "массовая рассылка", "bulk dm", "scrape emails", "собери email"}:
            return True

    local_window = lower[max(0, lower.find(term) - 24): lower.find(term) + len(term) + 24] if term in lower else lower
    local_negations = [
        "без ",
        "no ",
        "not ",
        "without ",
        "не ",
        "не использовать ",
        "не делать ",
    ]
    return any(neg in local_window for neg in local_negations)


def _firewall(goal):
    lower = _norm(goal)

    strict_hits = sorted({term for term in STRICT_FORBIDDEN_TERMS if term in lower})
    soft_hits = []
    negated_terms = []

    for term in NEGATION_AWARE_FORBIDDEN_TERMS:
        if term in lower:
            if _has_safe_negation(lower, term):
                negated_terms.append(term)
            else:
                soft_hits.append(term)

    hits = sorted(set(strict_hits + soft_hits))

    try:
        from modules.agentos_kernel_blueprint import semantic_firewall

        agentos_result = semantic_firewall(goal)
    except Exception as exc:
        agentos_result = {"ok": True, "warning": str(exc)}

    agentos_ok = bool(agentos_result.get("ok", True))

    if negated_terms and not strict_hits and not soft_hits:
        agentos_ok = True
        if isinstance(agentos_result, dict):
            agentos_result = dict(agentos_result)
            agentos_result["ok"] = True
            agentos_result["note"] = "Swiss Knife accepted explicit anti-spam / no-bulk-action wording."

    ok = not hits and agentos_ok
    reason = ""
    if hits:
        reason = "Swiss Knife blocked terms: " + ", ".join(hits)
    elif not agentos_ok:
        reason = "AgentOS firewall blocked the intent."
    elif negated_terms:
        reason = "Explicit safe negation detected: " + ", ".join(sorted(set(negated_terms)))

    return {
        "ok": ok,
        "blocked_terms": hits,
        "negated_terms": sorted(set(negated_terms)),
        "reason": reason,
        "agentos_firewall": agentos_result,
        "rules": {
            "no_spam": True,
            "no_secret_handling": True,
            "no_arbitrary_shell": True,
            "no_delete": True,
            "dry_run_first": True,
            "patch_workflow_for_project_changes": True,
            "reports_required": True,
        },
    }


def skills():
    payload = {
        "ok": True,
        "mode": "swiss_knife_skills",
        "generated_at": _now(),
        "version": SWISS_VERSION,
        "skills_count": len(SWISS_SKILLS),
        "skills": SWISS_SKILLS,
    }
    set_value("swiss_knife_skills", payload)
    return payload


def skill_by_id(skill_id):
    needle = _norm(skill_id).replace(" ", "_")
    for skill in SWISS_SKILLS:
        if skill["id"] == needle or _norm(skill["name"]) == _norm(skill_id):
            return skill
    return {}


def recommend_skill(goal):
    lower = _norm(goal)
    scored = []

    for skill in SWISS_SKILLS:
        score = 0
        reasons = []
        for item in skill.get("best_for", []):
            item_norm = _norm(item)
            if item_norm and item_norm in lower:
                score += 12
                reasons.append(f"goal contains '{item}'")
        if skill["id"] in lower:
            score += 20
            reasons.append("goal contains skill id")
        if _norm(skill["category"]) in lower:
            score += 8
            reasons.append("goal contains category")

        scored.append({
            "skill": skill,
            "score": score,
            "reasons": reasons,
        })

    scored.sort(key=lambda item: item["score"], reverse=True)

    if not scored or scored[0]["score"] <= 0:
        default = skill_by_id("research_report") or SWISS_SKILLS[0]
        return {
            "ok": True,
            "goal": goal,
            "selected": default,
            "confidence": 0.42,
            "reason": "No strong keyword match; defaulting to Research Report.",
            "ranked": scored[:5],
        }

    best = scored[0]
    confidence = min(0.96, 0.45 + best["score"] / 50)
    return {
        "ok": True,
        "goal": goal,
        "selected": best["skill"],
        "confidence": round(confidence, 2),
        "reason": "; ".join(best["reasons"]) or "best keyword score",
        "ranked": scored[:5],
    }


def _plan_steps_for_skill(skill, goal):
    skill_id = skill.get("id", "")
    common = [
        {
            "type": "firewall",
            "title": "Проверить задачу через Semantic Firewall.",
            "command": f"pc agentos firewall {goal}",
        },
        {
            "type": "context",
            "title": "Собрать контекст проекта/экрана/документов.",
            "command": "pc agents project-profile",
        },
    ]

    specific = {
        "research_report": [
            {"type": "questions", "title": "Сформировать исследовательские вопросы.", "output": "research_questions.json"},
            {"type": "source_plan", "title": "Определить типы источников и критерии доверия.", "output": "source_plan.md"},
            {"type": "report", "title": "Собрать outline отчёта.", "output": "report_outline.md"},
        ],
        "leadgen_brief": [
            {"type": "icp", "title": "Описать ICP без сбора запрещённых персональных данных.", "output": "icp.json"},
            {"type": "offer", "title": "Сформировать оффер и гипотезы каналов.", "output": "offer_hypotheses.md"},
            {"type": "compliance", "title": "Исключить спам, обход платформ и нелегальный парсинг.", "output": "compliance_check.md"},
        ],
        "pdf_analysis": [
            {"type": "input", "title": "Положить PDF в безопасную папку или использовать уже загруженный файл.", "output": "input_manifest.json"},
            {"type": "summary", "title": "Сделать summary, тезисы и action items.", "output": "pdf_summary.md"},
            {"type": "integration", "title": "Вытащить идеи для LocalComet roadmap.", "output": "integration_notes.md"},
        ],
        "website_draft": [
            {"type": "brief", "title": "Описать аудиторию, цель и структуру страницы.", "output": "site_brief.md"},
            {"type": "draft", "title": "Создать безопасные draft-файлы без запуска сервера.", "command": "pc demo site request"},
            {"type": "review", "title": "Пользователь проверяет, затем отдельный patch/deploy workflow.", "output": "review_checklist.md"},
        ],
        "document_automation": [
            {"type": "flow", "title": "Описать входы/выходы документов и папок.", "output": "file_flow.json"},
            {"type": "guards", "title": "Добавить backup/quarantine/no-delete правила.", "output": "automation_guards.md"},
            {"type": "patch", "title": "Создать request.md для будущего response.json.", "output": "safe_patch_request.md"},
        ],
        "project_patch": [
            {"type": "profile", "title": "Прочитать AGENTS.md и project profile.", "command": "pc agents project-profile"},
            {"type": "request", "title": "Создать request.md с требованиями к патчу.", "command": f"pc edit {goal}"},
            {"type": "tests", "title": "Определить py_compile/Auto Verification/Full Stability.", "output": "test_plan.md"},
        ],
        "ui_action": [
            {"type": "parse", "title": "Разобрать экран в UI elements.", "command": "pc ui parse"},
            {"type": "suggest", "title": "Получить безопасную action suggestion.", "command": f"pc ui suggest {goal}"},
            {"type": "dry_run", "title": "Выполнить только dry-run команду.", "output": "dry_run_command.md"},
        ],
        "agent_onboarding": [
            {"type": "explain", "title": "Объяснить агентность через LLM+Tools+Loop+Memory.", "command": "pc onboard explain"},
            {"type": "checklist", "title": "Создать onboarding checklist.", "command": "pc onboard checklist"},
            {"type": "agents", "title": "Создать безопасный AGENTS.md draft.", "command": "pc onboard agents.md"},
        ],
    }

    return common + specific.get(skill_id, [])


def plan(goal):
    goal = str(goal or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}

    fw = _firewall(goal)
    rec = recommend_skill(goal)
    skill = rec.get("selected", {})

    if not fw.get("ok"):
        return {
            "ok": False,
            "mode": "swiss_knife_plan",
            "generated_at": _now(),
            "goal": goal,
            "blocked": True,
            "firewall": fw,
            "selected_skill": skill,
            "safe_alternative": "Сформулировать задачу без спама, секретов, удаления, shell/admin и опасных действий.",
        }

    payload = {
        "ok": True,
        "mode": "swiss_knife_plan",
        "generated_at": _now(),
        "goal": goal,
        "firewall": fw,
        "selected_skill": skill,
        "confidence": rec.get("confidence"),
        "selection_reason": rec.get("reason"),
        "steps": _plan_steps_for_skill(skill, goal),
        "safe_routes": skill.get("safe_routes", []),
        "outputs": skill.get("outputs", []),
        "next": f"pc swiss dry {goal}",
    }

    set_value("swiss_knife_last_plan", payload)
    return payload


def dry_run(goal):
    plan_payload = plan(goal)
    if not plan_payload.get("ok"):
        return plan_payload

    skill = plan_payload.get("selected_skill", {})
    payload = {
        "ok": True,
        "mode": "swiss_knife_dry_run",
        "generated_at": _now(),
        "goal": goal,
        "selected_skill": skill,
        "would_create": [
            f"Projects/PCAgent/SwissKnife/Requests/swiss_request_{_stamp()}.md",
            f"Projects/PCAgent/SwissKnife/Requests/swiss_request_{_stamp()}.json",
        ],
        "would_not_execute": [
            "cmd",
            "powershell",
            "shell",
            "delete",
            "format",
            "send messages",
            "scrape emails",
            "handle secrets",
            "click/type",
            "deploy",
        ],
        "safe_routes": skill.get("safe_routes", []),
        "next": f"pc swiss request {goal}",
    }
    set_value("swiss_knife_last_dry_run", payload)
    return payload


def request(goal, skill_override=""):
    goal = str(goal or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}

    fw = _firewall(goal)
    if not fw.get("ok"):
        return {
            "ok": False,
            "mode": "swiss_knife_request",
            "generated_at": _now(),
            "goal": goal,
            "blocked": True,
            "firewall": fw,
        }

    rec = recommend_skill(goal)
    skill = skill_by_id(skill_override) if skill_override else rec.get("selected", {})
    if not skill:
        skill = rec.get("selected", {})

    plan_steps = _plan_steps_for_skill(skill, goal)
    request_id = f"swiss_{_stamp()}_{uuid.uuid4().hex[:8]}"
    md_path = REQUESTS_DIR / f"{request_id}.md"
    json_path = REQUESTS_DIR / f"{request_id}.json"

    payload = {
        "ok": True,
        "mode": "swiss_knife_request",
        "generated_at": _now(),
        "request_id": request_id,
        "goal": goal,
        "selected_skill": skill,
        "firewall": fw,
        "steps": plan_steps,
        "outputs": skill.get("outputs", []),
        "safe_routes": skill.get("safe_routes", []),
        "constraints": {
            "no_spam": True,
            "no_secrets": True,
            "no_shell": True,
            "no_delete": True,
            "dry_run_first": True,
            "project_patch_workflow": True,
            "report_required": True,
        },
    }

    _write_json(json_path, payload)

    md = [
        f"# Swiss Knife Request: {skill.get('name', 'Unknown Skill')}",
        "",
        f"- request_id: {request_id}",
        f"- generated_at: {payload['generated_at']}",
        f"- goal: {goal}",
        f"- skill: {skill.get('id', '')}",
        f"- risk: {skill.get('risk', '')}",
        "",
        "## Safety Constraints",
        "",
        "```json",
        json.dumps(payload["constraints"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Steps",
        "",
    ]

    for index, step in enumerate(plan_steps, start=1):
        md.extend([
            f"{index}. **{step.get('title', step.get('type', 'step'))}**",
            f"   - type: {step.get('type', '')}",
        ])
        if step.get("command"):
            md.append(f"   - safe command: `{step['command']}`")
        if step.get("output"):
            md.append(f"   - output: `{step['output']}`")

    md.extend([
        "",
        "## Safe Routes",
        "",
        "```text",
        "\n".join(skill.get("safe_routes", [])),
        "```",
        "",
        "## Forbidden",
        "",
        "No spam, no secrets, no shell, no deletion, no blind clicks, no auto-deploy.",
    ])

    _write_text(md_path, "\n".join(md))

    payload["markdown"] = str(md_path)
    payload["json"] = str(json_path)
    set_value("swiss_knife_last_request", payload)
    return payload


def leadgen(goal):
    return request(goal or "leadgen task", skill_override="leadgen_brief")


def pdf(goal):
    return request(goal or "pdf analysis task", skill_override="pdf_analysis")


def website(goal):
    return request(goal or "website draft task", skill_override="website_draft")


def business(goal):
    goal = str(goal or "business task").strip()
    rec = recommend_skill(goal)
    payload = {
        "ok": True,
        "mode": "swiss_knife_business_router",
        "generated_at": _now(),
        "goal": goal,
        "recommendation": rec,
        "business_skill_ids": [
            "research_report",
            "leadgen_brief",
            "pdf_analysis",
            "website_draft",
            "document_automation",
        ],
        "next": f"pc swiss plan {goal}",
    }
    set_value("swiss_knife_last_business", payload)
    return payload


def demo():
    demos = [
        {
            "title": "Исследование ниши",
            "command": "pc swiss plan исследовать рынок локальных AI-агентов для малого бизнеса",
        },
        {
            "title": "Лидогенерация без спама",
            "command": "pc swiss leadgen подготовить ICP и оффер для B2B клиентов без массовых рассылок",
        },
        {
            "title": "PDF analysis",
            "command": "pc swiss pdf разобрать PDF-инструкцию и вытащить идеи для LocalComet",
        },
        {
            "title": "Demo website",
            "command": "pc swiss website создать черновик лендинга LocalComet Swiss Knife",
        },
        {
            "title": "UI action",
            "command": "pc swiss plan нажми кнопку LocalComet через dry-run",
        },
    ]
    return {
        "ok": True,
        "mode": "swiss_knife_demo",
        "generated_at": _now(),
        "demos": demos,
        "safety": [
            "All demos create plans/requests first.",
            "No shell/cmd/powershell.",
            "No spam or bulk messaging.",
            "No secrets.",
            "No click/type execution.",
        ],
    }


def status():
    payload = {
        "ok": True,
        "mode": "swiss_knife_skill_launcher",
        "generated_at": _now(),
        "version": SWISS_VERSION,
        "skills_count": len(SWISS_SKILLS),
        "categories": sorted({skill["category"] for skill in SWISS_SKILLS}),
        "last_plan": get_value("swiss_knife_last_plan", ""),
        "last_request": get_value("swiss_knife_last_request", ""),
        "commands": [
            "pc swiss status",
            "pc swiss skills",
            "pc swiss demo",
            "pc swiss business <задача>",
            "pc swiss plan <задача>",
            "pc swiss dry <задача>",
            "pc swiss request <задача>",
            "pc swiss leadgen <задача>",
            "pc swiss pdf <задача>",
            "pc swiss website <задача>",
            "pc swiss report",
        ],
        "safety": [
            "Swiss Knife routes tasks to safe LocalComet modules.",
            "It creates plans and requests first.",
            "No spam, no secret handling, no arbitrary shell.",
            "No click/type execution.",
            "Project changes remain response.json patch workflow.",
        ],
    }
    set_value("swiss_knife_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    lines = [
        "Swiss Knife Skill Launcher:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- version: {payload.get('version')}",
        f"- skills_count: {payload.get('skills_count')}",
        f"- categories: {', '.join(payload.get('categories', []))}",
        "",
        "Commands:",
    ]
    lines.extend("- " + command for command in payload.get("commands", []))
    lines.append("")
    lines.append("Safety:")
    lines.extend("- " + item for item in payload.get("safety", []))
    return "\n".join(lines)


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "skills": skills(),
        "demo": demo(),
        "last_plan": get_value("swiss_knife_last_plan", ""),
        "last_dry_run": get_value("swiss_knife_last_dry_run", ""),
        "last_request": get_value("swiss_knife_last_request", ""),
        "last_business": get_value("swiss_knife_last_business", ""),
    }

    json_path = REPORTS_DIR / f"swiss_knife_skill_launcher_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"swiss_knife_skill_launcher_report_{_stamp()}.md"
    _write_json(json_path, payload)

    md = [
        "# Swiss Knife Skill Launcher Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_status(payload["status"]),
        "```",
        "",
        "## Skills",
        "",
        "```json",
        json.dumps(SWISS_SKILLS, ensure_ascii=False, indent=2),
        "```",
    ]

    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc swiss", "pc swiss status", "pc swiss статус", "swiss status"}:
        return format_status(status())

    if lower in {"pc swiss skills", "pc swiss скиллы", "pc swiss навыки", "swiss skills"}:
        return format_payload(skills())

    if lower in {"pc swiss demo", "pc swiss демо", "swiss demo"}:
        return format_payload(demo())

    if lower in {"pc swiss report", "pc swiss отчет", "pc swiss отчёт", "swiss report"}:
        return format_payload(report("manual report"))

    prefixes = [
        ("pc swiss business ", "business"),
        ("pc swiss бизнес ", "business"),
        ("swiss business ", "business"),
        ("pc swiss plan ", "plan"),
        ("pc swiss план ", "plan"),
        ("swiss plan ", "plan"),
        ("pc swiss dry ", "dry"),
        ("pc swiss dry-run ", "dry"),
        ("swiss dry ", "dry"),
        ("pc swiss request ", "request"),
        ("pc swiss запрос ", "request"),
        ("swiss request ", "request"),
        ("pc swiss leadgen ", "leadgen"),
        ("pc swiss лиды ", "leadgen"),
        ("pc swiss лидогенерация ", "leadgen"),
        ("swiss leadgen ", "leadgen"),
        ("pc swiss pdf ", "pdf"),
        ("pc swiss пдф ", "pdf"),
        ("swiss pdf ", "pdf"),
        ("pc swiss website ", "website"),
        ("pc swiss site ", "website"),
        ("pc swiss сайт ", "website"),
        ("swiss website ", "website"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "business":
                return format_payload(business(value))
            if action == "plan":
                return format_payload(plan(value))
            if action == "dry":
                return format_payload(dry_run(value))
            if action == "request":
                return format_payload(request(value))
            if action == "leadgen":
                return format_payload(leadgen(value))
            if action == "pdf":
                return format_payload(pdf(value))
            if action == "website":
                return format_payload(website(value))

    return format_payload({
        "ok": False,
        "error": "Unknown Swiss Knife command.",
        "help": status().get("commands", []),
    })


def is_swiss_command(command):
    lower = _norm(command)
    exact = {
        "pc swiss",
        "pc swiss status",
        "pc swiss статус",
        "swiss status",
        "pc swiss skills",
        "pc swiss скиллы",
        "pc swiss навыки",
        "swiss skills",
        "pc swiss demo",
        "pc swiss демо",
        "swiss demo",
        "pc swiss report",
        "pc swiss отчет",
        "pc swiss отчёт",
        "swiss report",
    }
    if lower in exact:
        return True

    prefixes = (
        "pc swiss business ",
        "pc swiss бизнес ",
        "swiss business ",
        "pc swiss plan ",
        "pc swiss план ",
        "swiss plan ",
        "pc swiss dry ",
        "pc swiss dry-run ",
        "swiss dry ",
        "pc swiss request ",
        "pc swiss запрос ",
        "swiss request ",
        "pc swiss leadgen ",
        "pc swiss лиды ",
        "pc swiss лидогенерация ",
        "swiss leadgen ",
        "pc swiss pdf ",
        "pc swiss пдф ",
        "swiss pdf ",
        "pc swiss website ",
        "pc swiss site ",
        "pc swiss сайт ",
        "swiss website ",
    )
    return lower.startswith(prefixes)
````

