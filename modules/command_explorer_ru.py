from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


COMMAND_EXPLORER_VERSION = "v6.59a"
COMMAND_EXPLORER_NAME = "LocalComet Command Explorer RU"

ROOT_PATH = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_PATH / "Projects" / "Reports" / "command_explorer"

BLOCKED_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist",
                "build", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                "BrowserProfile", "Backups"}


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
    if path.name.endswith(".bak"):
        return True
    return False


def _read_text(path: Path, limit: int = 50000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
    if len(text) > limit:
        return text[:limit] + "\n[truncated]"
    return text


def _iter_python_files() -> List[Path]:
    files: List[Path] = []
    for path in sorted(ROOT_PATH.rglob("*.py"), key=lambda p: _safe_relative(p).lower()):
        if _is_skipped(path):
            continue
        files.append(path)
    return files


def _guess_category(path: str) -> str:
    name = Path(path).stem.lower()
    if name.startswith("computer_use_") or name == "computer_use_core_ru":
        return "computer_use"
    if name.startswith("premium_"):
        return "premium"
    if name.startswith("localcomet_"):
        return "developer"
    if name.startswith("ai_") or "agent" in name:
        return "ai_agent"
    if name.startswith("browser_"):
        return "browser"
    if name.startswith("pc_"):
        return "pc_codex"
    if name in {"app", "config", "agent"} or name.startswith("core/"):
        return "system"
    if name.startswith("install_") or name.startswith("localcomet_preflight"):
        return "tool"
    if "verification" in name or "stability" in name or "check" in name:
        return "verification"
    if "relay" in name or "chatgpt" in name:
        return "relay"
    if "safety" in name or "danger" in name:
        return "safety"
    return "other"


def _extract_aliases(text: str) -> List[str]:
    found: List[str] = []
    m = re.search(r"COMMAND_ALIASES\s*=\s*\{", text)
    if m:
        chunk = text[m.end():m.end() + 3000]
        for alias in re.findall(r"\"([^\"]+)\"\s*:", chunk):
            if len(alias) < 100:
                found.append(alias)
    return found


def _extract_command_functions(text: str) -> List[str]:
    found: List[str] = []
    for m in re.finditer(r"def\s+(is_\w+_command)\s*\(", text):
        if m:
            found.append(m.group(1))
    return found


def _extract_command_literals(text: str) -> List[str]:
    found: set = set()
    for m in re.finditer(r"\"(pc\s[a-zа-я0-9_\-]+)", text.lower()):
        found.add(m.group(1))
    for m in re.finditer(r"'pc\s([a-zа-я0-9_\-]+)", text.lower()):
        found.add("pc " + m.group(1))
    return sorted(found)


def _extract_route_names(text: str) -> List[str]:
    found: List[str] = []
    for m in re.finditer(r"route_name\s*=\s*[\"']([^\"']+)[\"']", text):
        found.append(m.group(1))
    return found


def _get_dispatch_docstring(text: str) -> str:
    m = re.search(r"def dispatch\s*\([^)]*\).*?\"\"\"(.*?)\"\"\"", text, re.DOTALL)
    if m:
        return m.group(1).strip().split("\n")[0][:200]
    return ""


def discover_commands() -> Dict[str, Any]:
    files = _iter_python_files()
    modules: List[Dict[str, Any]] = []
    categories: Dict[str, List[str]] = {}

    for path in files:
        rel = _safe_relative(path)
        text = _read_text(path)
        if not text:
            continue

        aliases = _extract_aliases(text)
        cmd_fns = _extract_command_functions(text)
        literals = _extract_command_literals(text)
        routes = _extract_route_names(text)
        doc = _get_dispatch_docstring(text)
        category = _guess_category(rel)

        commands: Dict[str, Any] = {}
        if aliases:
            commands["aliases"] = aliases[:30]
        if cmd_fns:
            commands["functions"] = cmd_fns
        if routes:
            commands["routes"] = routes
        if literals:
            commands["literals"] = literals[:30]
        if doc:
            commands["help"] = doc

        if any([aliases, cmd_fns, routes, literals]):
            cat_commands = []
            for alias in aliases[:10]:
                cat_commands.append(alias)
                categories.setdefault(category, []).append(alias)
            for literal in literals[:10]:
                cat_commands.append(literal)
                categories.setdefault(category, []).append(literal)
            for route in routes[:5]:
                categories.setdefault(category, []).append(route)

        modules.append({
            "path": rel,
            "category": category,
            "has_dispatch": "def dispatch" in text,
            "has_status": "def status" in text,
            "has_report": "def report" in text,
            "commands": commands,
        })

    return {
        "modules": modules,
        "categories": {k: sorted(set(v))[:60] for k, v in categories.items()},
    }


def status() -> Dict[str, Any]:
    data = discover_commands()
    total_cmds = sum(len(v) for v in data.get("categories", {}).values())
    return {
        "ok": True,
        "mode": "command_explorer_status",
        "version": COMMAND_EXPLORER_VERSION,
        "module_count": len(data.get("modules", [])),
        "command_count": total_cmds,
        "category_count": len(data.get("categories", {})),
    }


def report() -> Dict[str, Any]:
    data = discover_commands()
    total_cmds = sum(len(v) for v in data.get("categories", {}).values())
    return {
        "ok": True,
        "mode": "command_explorer_report",
        "version": COMMAND_EXPLORER_VERSION,
        "generated_at": _now(),
        "module_count": len(data.get("modules", [])),
        "command_count": total_cmds,
        "category_count": len(data.get("categories", {})),
        "modules": data.get("modules", []),
        "categories": data.get("categories", {}),
    }


def _write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "latest_command_explorer.json"
    md_path = REPORT_DIR / "latest_command_explorer.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# LocalComet Command Explorer",
        "",
        f"- version: {payload.get('version')}",
        f"- ok: {payload.get('ok')}",
        f"- module_count: {payload.get('module_count')}",
        f"- command_count: {payload.get('command_count')}",
        f"- category_count: {payload.get('category_count')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Categories",
        "",
    ]
    categories = payload.get("categories", {})
    for cat, cmds in sorted(categories.items()):
        lines.append(f"### {cat} ({len(cmds)})")
        lines.append("")
        for cmd in cmds:
            lines.append(f"- `{cmd}`")
        lines.append("")

    lines.append("## Modules")
    lines.append("")
    for mod in payload.get("modules", []):
        status_chars = ""
        if mod.get("has_dispatch"):
            status_chars += "D"
        if mod.get("has_status"):
            status_chars += "S"
        if mod.get("has_report"):
            status_chars += "R"
        tags = f"[{status_chars}]" if status_chars else ""
        lines.append(f"- {tags} {mod['path']}")
        cmds = mod.get("commands", {})
        if cmds.get("functions"):
            lines.append(f"  - functions: {', '.join(cmds['functions'][:5])}")
        if cmds.get("aliases"):
            lines.append(f"  - aliases: {', '.join(cmds['aliases'][:5])}")
        if cmds.get("routes"):
            lines.append(f"  - routes: {', '.join(cmds['routes'][:5])}")
        if cmds.get("literals"):
            lines.append(f"  - literals: {', '.join(cmds['literals'][:5])}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "md": md_path}


def is_command_explorer_command(command: str) -> bool:
    lowered = str(command or "").strip().lower().replace("ё", "е")
    targets = {
        "команды проекта", "список команд", "command explorer",
        "pc commands", "pc команды", "pc список", "pc command explorer",
    }
    return lowered in targets


def dispatch(command: str) -> Dict[str, Any]:
    lowered = str(command or "").strip().lower().replace("ё", "е")
    if lowered in {"команды проекта", "список команд", "command explorer",
                   "pc command explorer", "pc commands status"}:
        result = report()
        paths = _write_reports(result)
        result["report"] = str(paths["md"])
        result["json"] = str(paths["json"])
        return result
    if lowered in {"pc commands status", "command explorer status", "статус команд"}:
        return status()
    return {
        "ok": False,
        "mode": "command_explorer_unknown",
        "version": COMMAND_EXPLORER_VERSION,
        "command": command,
        "hint": "Use: команды проекта, список команд, command explorer",
    }


if __name__ == "__main__":
    result = dispatch("команды проекта")
    _write_reports(result)
    print(json.dumps(result, ensure_ascii=False, indent=2)[:3000])
