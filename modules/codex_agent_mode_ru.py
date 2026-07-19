from __future__ import annotations

import ast
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_PATH = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_PATH / "Projects" / "Reports" / "codex_agent_workspace"
CONTEXT_PATH = REPORT_DIR / "latest_codex_agent_context.json"

AGENT_VERSION = "v6.41"
AGENT_NAME = "LocalComet Codex Agent Workspace RU"

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

DANGEROUS_TERMS = {
    "пароль",
    "password",
    "token",
    "api key",
    "api-key",
    "secret",
    "private key",
    "ssh key",
    "cookie",
    "cookies",
    "удали",
    "удалить",
    "стереть",
    "сотри",
    "format",
    "wipe",
    "rm ",
    "rmdir",
    "del ",
    "powershell",
    "cmd.exe",
    "bash",
    "shell",
    "terminal",
    "админ",
    "administrator",
    "sudo",
    "банк",
    "bank",
    "карта",
    "payment",
    "casino",
    "gambling",
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


def _read_text(path: Path, limit: int = 12000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    if len(text) > limit:
        return text[:limit] + "\n\n[truncated]"
    return text


def _extract_python_symbols(path: Path) -> dict[str, Any]:
    rel = _safe_relative(path)
    text = _read_text(path, 16000)
    item = {
        "path": rel,
        "functions": [],
        "classes": [],
        "has_dispatch": False,
        "has_status": False,
        "has_report": False,
        "parse_ok": False,
        "parse_error": "",
    }

    try:
        tree = ast.parse(text, filename=rel)
    except Exception as exc:
        item["parse_error"] = str(exc)
        return item

    item["parse_ok"] = True
    functions = []
    classes = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)

    item["functions"] = sorted(set(functions))
    item["classes"] = sorted(set(classes))
    item["has_dispatch"] = "dispatch" in item["functions"]
    item["has_status"] = "status" in item["functions"]
    item["has_report"] = "report" in item["functions"]
    return item


def _iter_python_files() -> list[Path]:
    files = []
    for path in ROOT_PATH.rglob("*.py"):
        if _is_skipped(path):
            continue
        if path.name.startswith("."):
            continue
        files.append(path)
    return sorted(files, key=lambda p: _safe_relative(p).lower())


def _control_panel_version() -> dict[str, str]:
    panel = ROOT_PATH / "LocalComet_Control_Panel.py"
    text = _read_text(panel, 20000)
    version = ""
    label = ""

    version_match = re.search(r"LOCALCOMET_VERSION\s*=\s*['\"]([^'\"]+)['\"]", text)
    label_match = re.search(r"LOCALCOMET_VERSION_LABEL\s*=\s*['\"]([^'\"]+)['\"]", text)

    if version_match:
        version = version_match.group(1)
    if label_match:
        label = label_match.group(1)

    return {
        "version": version,
        "label": label,
    }


def _recent_reports() -> list[str]:
    reports_root = ROOT_PATH / "Projects" / "Reports"
    if not reports_root.exists():
        return []

    reports = []
    for pattern in ("*.md", "*.json"):
        for path in reports_root.rglob(pattern):
            if _is_skipped(path):
                continue
            reports.append(path)

    reports = sorted(reports, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return [_safe_relative(path) for path in reports[:12]]


def _important_files() -> list[str]:
    candidates = [
        "LocalComet_Control_Panel.py",
        "modules/premium_task_panel_ru.py",
        "modules/strict_project_stability_ru.py",
        "modules/codex_agent_mode_ru.py",
        "modules/pc_codex_core.py",
        "modules/pc_codex_executor.py",
        "modules/swiss_knife_skill_launcher.py",
        "modules/project_one_command_check_ru.py",
    ]
    return [item for item in candidates if (ROOT_PATH / item).exists()]


def build_context_capsule() -> dict[str, Any]:
    python_files = _iter_python_files()
    symbols = [_extract_python_symbols(path) for path in python_files]
    command_modules = [item for item in symbols if item.get("has_dispatch")]

    context = {
        "ok": True,
        "mode": "codex_agent_context_capsule",
        "generated_at": _now(),
        "agent_version": AGENT_VERSION,
        "agent_name": AGENT_NAME,
        "root": str(ROOT_PATH),
        "control_panel": _control_panel_version(),
        "python_file_count": len(python_files),
        "function_count": sum(len(item.get("functions", [])) for item in symbols),
        "class_count": sum(len(item.get("classes", [])) for item in symbols),
        "command_module_count": len(command_modules),
        "important_files": _important_files(),
        "command_modules": command_modules[:40],
        "recent_reports": _recent_reports(),
        "available_safe_commands": [
            "проверь проект",
            "pc agent status",
            "pc agent context",
            "pc agent plan <цель>",
            "pc agent brief <цель>",
            "pc agent verify",
            "pc swiss plan <цель>",
            "pc core status",
            "pc exec status",
            "pc ui status",
            "pc screen observe",
        ],
        "agent_rules_ru": [
            "Работай как Codex-подобный локальный агент поверх проекта LocalComet.",
            "Сначала понимай цель и контекст проекта, затем предлагай план.",
            "Не выполняй разрушительные действия.",
            "Не читай и не выводи пароли, токены, ключи, cookies, банковские данные.",
            "Для изменений кода предлагай self-edit patch через безопасный pipeline.",
            "После изменения всегда запускай проверку проекта.",
            "Обычный чат не должен запускать router/research без явного намерения.",
        ],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_PATH.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
    return context


def _dangerous_goal_reason(goal: str) -> str:
    lowered = str(goal or "").lower().replace("ё", "е")
    for term in sorted(DANGEROUS_TERMS):
        if term in lowered:
            return f"Запрос содержит потенциально опасный маркер: {term}"
    return ""


def _context_as_text(context: dict[str, Any]) -> str:
    panel = context.get("control_panel", {})
    command_modules = context.get("command_modules", [])
    lines = [
        f"Проект: {context.get('root')}",
        f"Версия панели: {panel.get('version')} — {panel.get('label')}",
        f"Python files: {context.get('python_file_count')}",
        f"Functions: {context.get('function_count')}",
        f"Classes: {context.get('class_count')}",
        f"Command modules: {context.get('command_module_count')}",
        "",
        "Ключевые файлы:",
    ]
    for item in context.get("important_files", []):
        lines.append(f"- {item}")

    lines.append("")
    lines.append("Командные модули:")
    for item in command_modules[:20]:
        lines.append(
            f"- {item.get('path')} dispatch={item.get('has_dispatch')} "
            f"status={item.get('has_status')} report={item.get('has_report')}"
        )

    lines.append("")
    lines.append("Последние отчёты:")
    for item in context.get("recent_reports", [])[:8]:
        lines.append(f"- {item}")

    return "\n".join(lines)


def _ask_local_llm(system: str, user: str) -> str:
    try:
        from core.llm import ask_llm, is_llm_offline_error
    except Exception:
        return ""

    try:
        answer = ask_llm(
            system=system,
            user=user,
            max_tokens=900,
            use_context=True,
            no_think=True,
            temperature=0.25,
            timeout=90,
        )
    except Exception:
        return ""

    if not answer:
        return ""

    try:
        if is_llm_offline_error(answer):
            return ""
    except Exception:
        pass

    return str(answer).strip()


def _fallback_agent_plan(goal: str, context: dict[str, Any]) -> str:
    return (
        "Codex Agent Plan:\n\n"
        f"Цель: {goal}\n\n"
        "Понимание:\n"
        "- Работаем внутри LocalComet как локальный агент разработки.\n"
        "- Сначала используем контекст проекта, затем предлагаем безопасный план.\n"
        "- Изменения должны идти через self-edit patch и проверяться кнопкой «Проверить проект».\n\n"
        "План:\n"
        "1. Уточнить, какой модуль/экран/команда относится к задаче.\n"
        "2. Найти релевантные файлы через context capsule.\n"
        "3. Составить минимальный patch без разрушительных действий.\n"
        "4. Применить через Relay только после проверки response.json.\n"
        "5. Запустить «Проверить проект» и добиться hard_failures=0, warnings=0.\n\n"
        "Безопасная следующая команда:\n"
        f"pc swiss plan {goal}\n\n"
        "Контекст:\n"
        f"{_context_as_text(context)}"
    )


def build_agent_plan(goal: str, mode: str = "plan") -> dict[str, Any]:
    raw_goal = str(goal or "").strip()
    if not raw_goal:
        raw_goal = "развивать LocalComet в сторону Codex-подобного AI-агента"

    danger = _dangerous_goal_reason(raw_goal)
    context = build_context_capsule()

    if danger:
        return {
            "ok": False,
            "mode": "codex_agent_plan_blocked",
            "generated_at": _now(),
            "goal": raw_goal,
            "blocked": True,
            "reason": danger,
            "answer": (
                "Я не буду планировать или выполнять потенциально опасную задачу.\n"
                f"Причина: {danger}\n\n"
                "Можно переформулировать цель как безопасный проектный план без доступа к секретам, shell, удалению или админ-действиям."
            ),
            "context_path": str(CONTEXT_PATH),
        }

    system = (
        "Ты LocalComet Codex Agent Workspace RU. "
        "Ты локальный AI-агент разработки, похожий по идее на coding agent: понимаешь проект, "
        "строишь план, предлагаешь безопасные команды и всегда требуешь проверку проекта после изменений. "
        "Отвечай по-русски. Не заявляй, что уже изменил файлы. Не запускай shell/browser/research. "
        "Не проси и не выводи токены, пароли, ключи, cookies, банковские данные. "
        "Если нужны изменения кода, формулируй их как self-edit patch через безопасный Relay pipeline. "
        "Формат ответа: Понимание, План, Риски, Следующая безопасная команда."
    )
    user = (
        "Контекст проекта:\n"
        f"{_context_as_text(context)}\n\n"
        "Цель пользователя:\n"
        f"{raw_goal}\n\n"
        "Составь Codex-like агентский план."
    )

    answer = _ask_local_llm(system, user)
    if not answer:
        answer = _fallback_agent_plan(raw_goal, context)

    result = {
        "ok": True,
        "mode": f"codex_agent_{mode}",
        "generated_at": _now(),
        "goal": raw_goal,
        "agent_version": AGENT_VERSION,
        "answer": answer,
        "context_path": str(CONTEXT_PATH),
        "next_safe_commands": [
            f"pc agent plan {raw_goal}",
            f"pc swiss plan {raw_goal}",
            "проверь проект",
        ],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"codex_agent_{mode}_{stamp}.md"
    report_path.write_text(
        "# LocalComet Codex Agent Workspace\n\n"
        f"- generated_at: {result['generated_at']}\n"
        f"- goal: {raw_goal}\n"
        f"- context: {CONTEXT_PATH}\n\n"
        "## Answer\n\n"
        f"{answer}\n",
        encoding="utf-8",
    )
    result["report"] = str(report_path)
    return result


def run_project_verify() -> dict[str, Any]:
    try:
        from modules.strict_project_stability_ru import dispatch as strict_dispatch

        result = strict_dispatch("проверь проект")
        if isinstance(result, dict):
            result["called_by"] = "codex_agent_mode_ru"
            return result
    except Exception as exc:
        return {
            "ok": False,
            "mode": "codex_agent_verify_error",
            "generated_at": _now(),
            "error": str(exc),
        }

    return {
        "ok": False,
        "mode": "codex_agent_verify_error",
        "generated_at": _now(),
        "error": "strict verification returned non-dict result",
    }


def status() -> dict[str, Any]:
    context = build_context_capsule()
    return {
        "ok": True,
        "mode": "codex_agent_status",
        "generated_at": _now(),
        "agent_version": AGENT_VERSION,
        "agent_name": AGENT_NAME,
        "context_path": str(CONTEXT_PATH),
        "project_version": context.get("control_panel", {}).get("version"),
        "python_files": context.get("python_file_count"),
        "functions": context.get("function_count"),
        "command_modules": context.get("command_module_count"),
        "commands": [
            "pc agent status",
            "pc agent context",
            "pc agent plan <цель>",
            "pc agent brief <цель>",
            "pc agent verify",
            "агент статус",
            "контекст проекта",
        ],
    }


def report() -> dict[str, Any]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "ok": True,
        "mode": "codex_agent_report",
        "generated_at": _now(),
        "latest_reports": [
            str(path)
            for path in sorted(REPORT_DIR.glob("codex_agent_*.md"), reverse=True)[:10]
        ],
        "context_path": str(CONTEXT_PATH),
        "status": status(),
    }


def dispatch(command: str) -> dict[str, Any]:
    raw = str(command or "").strip()
    text = raw.lower().replace("ё", "е")

    if text in {"pc agent status", "агент статус", "статус агента"}:
        return status()

    if text in {"pc agent context", "контекст проекта", "агент контекст"}:
        return build_context_capsule()

    if text in {"pc agent report", "агент отчет", "агент отчёт"}:
        return report()

    if text in {"pc agent verify", "агент проверка", "проверь проект агентом"}:
        return run_project_verify()

    for prefix in ("pc agent plan ", "pc agent brief ", "агент план ", "агент задача "):
        if text.startswith(prefix):
            goal = raw[len(prefix):].strip()
            mode = "brief" if "brief" in prefix else "plan"
            return build_agent_plan(goal, mode=mode)

    if text in {"pc agent plan", "pc agent brief", "агент план"}:
        return build_agent_plan("развивать LocalComet в сторону Codex-подобного AI-агента", mode="plan")

    return {
        "ok": False,
        "mode": "codex_agent_unknown_command",
        "generated_at": _now(),
        "command": raw,
        "hint": "Используй: pc agent plan <цель>, pc agent context, pc agent verify",
    }


def is_codex_agent_command(command: str) -> bool:
    text = str(command or "").strip().lower().replace("ё", "е")
    return (
        text.startswith("pc agent ")
        or text.startswith("агент план ")
        or text.startswith("агент задача ")
        or text in {
            "агент статус",
            "статус агента",
            "контекст проекта",
            "агент контекст",
            "агент проверка",
            "проверь проект агентом",
        }
    )
