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
