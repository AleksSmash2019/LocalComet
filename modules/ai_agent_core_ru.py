from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_PATH = Path(__file__).resolve().parents[1]
MEMORY_DIR = ROOT_PATH / "Projects" / "AgentMemory"
REPORT_DIR = MEMORY_DIR / "reports"

AI_AGENT_VERSION = "v6.41d"
AI_AGENT_NAME = "LocalComet AI Agent Core Superboost Stable RU"

STATE_MACHINE = [
    "intake",
    "context_scan",
    "plan",
    "draft_patch",
    "wait_for_user_apply",
    "verify",
    "critique",
    "repair_plan",
    "done",
]

DANGEROUS_PATTERNS = [
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
    "browser profile",
    "браузерный профиль",
]


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _danger_reason(goal: str) -> str:
    lowered = str(goal or "").lower().replace("ё", "е")
    for marker in DANGEROUS_PATTERNS:
        if marker in lowered:
            return "запрос содержит потенциально опасный маркер: " + marker
    return ""


def _summarize_context(context: dict[str, Any]) -> str:
    control = context.get("control_panel", {}) if isinstance(context, dict) else {}
    lines = [
        f"Версия проекта: {control.get('version', '')} — {control.get('label', '')}",
        f"Python files: {context.get('python_file_count', '')}",
        f"Functions: {context.get('function_count', '')}",
        f"Classes: {context.get('class_count', '')}",
        f"Command modules: {context.get('command_module_count', '')}",
        f"UI modules: {context.get('ui_module_count', '')}",
        f"Verification modules: {context.get('verification_module_count', '')}",
        f"Agent modules: {context.get('agent_module_count', '')}",
        f"Parse warnings: {context.get('parse_error_count', '')}",
        f"Critical parse errors: {context.get('critical_parse_error_count', '')}",
        f"Project map: {context.get('project_map_path', '')}",
    ]
    return "\n".join(lines)


def _write_report(name: str, content: str) -> str:
    _ensure_dirs()
    path = REPORT_DIR / f"{name}_{_stamp()}.md"
    path.write_text(content, encoding="utf-8")
    return str(path)


def _latest_file(patterns: list[str]) -> Path | None:
    candidates: list[Path] = []
    reports = ROOT_PATH / "Projects" / "Reports"
    for pattern in patterns:
        candidates.extend(reports.rglob(pattern) if reports.exists() else [])
    candidates = [path for path in candidates if path.exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def build_project_context() -> dict[str, Any]:
    from modules.ai_agent_memory_ru import save_project_context, set_phase
    from modules.ai_project_map_ru import build_project_map

    set_phase("context_scan")
    context = build_project_map()
    save_project_context(context)
    set_phase("plan")
    return {
        "ok": bool(context.get("ok", True)),
        "mode": "ai_agent_project_context",
        "generated_at": _now(),
        "agent_version": AI_AGENT_VERSION,
        "project_map_path": context.get("project_map_path"),
        "summary": {
            "python_file_count": context.get("python_file_count"),
            "function_count": context.get("function_count"),
            "class_count": context.get("class_count"),
            "command_module_count": context.get("command_module_count"),
            "ui_module_count": context.get("ui_module_count"),
            "verification_module_count": context.get("verification_module_count"),
            "agent_module_count": context.get("agent_module_count"),
            "parse_error_count": context.get("parse_error_count"),
            "critical_parse_error_count": context.get("critical_parse_error_count"),
            "map_policy": context.get("diagnostic_ok_policy", "diagnostic project map"),
        },
        "context": context,
    }


def build_task_plan(goal: str) -> dict[str, Any]:
    from modules.ai_agent_memory_ru import append_history, set_phase

    raw_goal = str(goal or "").strip() or "развивать LocalComet как локального AI-агента"
    set_phase("intake", raw_goal)
    danger = _danger_reason(raw_goal)
    context_result = build_project_context()
    context = context_result.get("context", {})

    if danger:
        set_phase("done", raw_goal)
        return {
            "ok": False,
            "mode": "ai_agent_plan_blocked",
            "generated_at": _now(),
            "goal": raw_goal,
            "reason": danger,
            "answer": "План заблокирован: " + danger,
        }

    set_phase("plan", raw_goal)
    plan_text = (
        "AI Agent Core Plan\n\n"
        f"Цель: {raw_goal}\n\n"
        "Контекст проекта:\n"
        f"{_summarize_context(context)}\n\n"
        "Архитектурный план:\n"
        "1. Не начинать с UI. Сначала собрать карту проекта и понять затрагиваемые модули.\n"
        "2. Сформировать минимальный self-edit draft response.json через planner.\n"
        "3. Показать draft пользователю для импорта через Relay.\n"
        "4. После применения запустить вкладку «Проверка» / команду «проверь проект».\n"
        "5. Если hard_failures или warnings не ноль — построить repair plan по последнему отчёту.\n"
        "6. Только после зелёной проверки двигаться к следующему пункту backlog.\n\n"
        "Режимы агента:\n"
        "- Plan: построить план без изменения файлов.\n"
        "- Draft: создать response.json draft без применения.\n"
        "- Verify: прочитать/запустить безопасную проверку.\n"
        "- Critique: объяснить проблемы отчёта.\n"
        "- Repair: подготовить следующий repair draft.\n\n"
        "Следующая безопасная команда:\n"
        f"pc ai draft {raw_goal}\n"
    )

    report_path = _write_report("ai_agent_plan", "# AI Agent Plan\n\n" + plan_text)
    append_history({
        "type": "agent_plan",
        "goal": raw_goal,
        "report": report_path,
        "phase": "plan",
    })

    return {
        "ok": True,
        "mode": "ai_agent_plan",
        "generated_at": _now(),
        "goal": raw_goal,
        "answer": plan_text,
        "report": report_path,
        "project_map_path": context.get("project_map_path"),
        "next_safe_command": "pc ai draft " + raw_goal,
        "state_machine": STATE_MACHINE,
    }


def draft_patch(goal: str) -> dict[str, Any]:
    from modules.ai_agent_memory_ru import set_phase
    from modules.ai_patch_planner_ru import draft_patch as planner_draft

    raw_goal = str(goal or "").strip() or "развивать LocalComet как локального AI-агента"
    set_phase("draft_patch", raw_goal)
    result = planner_draft(raw_goal)
    if result.get("ok"):
        set_phase("wait_for_user_apply", raw_goal, latest_draft=result.get("draft_path", ""))
    return result


def analyze_verification_report(path: str | None = None) -> dict[str, Any]:
    from modules.ai_agent_memory_ru import find_latest_verification_report, remember_verification, set_phase

    set_phase("critique")
    target = str(path or "").strip()
    if not target:
        target = find_latest_verification_report()

    if not target:
        return {
            "ok": False,
            "mode": "ai_agent_verification_analysis",
            "generated_at": _now(),
            "error": "verification report not found",
        }

    report_path = Path(target)
    if not report_path.exists():
        return {
            "ok": False,
            "mode": "ai_agent_verification_analysis",
            "generated_at": _now(),
            "error": "report path does not exist",
            "path": target,
        }

    text = report_path.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    hard_failures = _extract_int(text, "hard_failures")
    warnings = _extract_int(text, "warnings")
    ok = ("ok: true" in lowered or '"ok": true' in lowered or "[ok]" in lowered) and not ("[fail]" in lowered)

    if hard_failures is not None:
        ok = ok and hard_failures == 0
    if warnings is not None:
        ok = ok and warnings == 0

    remember_verification(str(report_path), ok=ok)
    set_phase("done" if ok else "repair_plan")

    report = {
        "ok": ok,
        "mode": "ai_agent_verification_analysis",
        "generated_at": _now(),
        "path": str(report_path),
        "hard_failures": hard_failures,
        "warnings": warnings,
        "has_fail": "[FAIL]" in text or '"ok": false' in lowered or "ok: false" in lowered,
        "summary": _shorten_report(text),
    }
    return report


def _extract_int(text: str, key: str) -> int | None:
    patterns = [
        rf'"{re.escape(key)}"\s*:\s*(\d+)',
        rf"{re.escape(key)}\s*:\s*(\d+)",
        rf"-\s*{re.escape(key)}\s*:\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _shorten_report(text: str, limit: int = 2500) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(marker in stripped.lower() for marker in ("hard_failures", "warnings", "[fail]", "error", "итог", "проблем", "score", "ok:")):
            lines.append(stripped)
    summary = "\n".join(lines[:80])
    if not summary:
        summary = text[:limit]
    return summary[:limit]


def propose_repair(goal_or_report: str = "") -> dict[str, Any]:
    from modules.ai_agent_memory_ru import set_phase

    set_phase("repair_plan")
    analysis = analyze_verification_report(goal_or_report if goal_or_report and Path(str(goal_or_report)).exists() else None)

    if analysis.get("ok"):
        return {
            "ok": True,
            "mode": "ai_agent_repair_not_needed",
            "generated_at": _now(),
            "analysis": analysis,
            "answer": "Последняя проверка зелёная. Repair не нужен.",
        }

    repair_goal = (
        "починить проект по последнему verification report: "
        + str(analysis.get("path") or goal_or_report or "unknown report")
    )
    plan = build_task_plan(repair_goal)
    set_phase("repair_plan", repair_goal)

    return {
        "ok": True,
        "mode": "ai_agent_repair_plan",
        "generated_at": _now(),
        "goal": repair_goal,
        "analysis": analysis,
        "plan": plan,
        "next_safe_command": "pc ai draft " + repair_goal,
    }


def run_agent_cycle(goal: str, dry_run: bool = True) -> dict[str, Any]:
    from modules.ai_agent_memory_ru import set_phase

    raw_goal = str(goal or "").strip() or "развивать LocalComet как локального AI-агента"
    set_phase("intake", raw_goal)
    context = build_project_context()
    plan = build_task_plan(raw_goal)
    draft = draft_patch(raw_goal)
    verification = analyze_verification_report()

    result = {
        "ok": bool(context.get("ok")) and bool(plan.get("ok")) and bool(draft.get("ok")),
        "mode": "ai_agent_cycle",
        "generated_at": _now(),
        "goal": raw_goal,
        "dry_run": dry_run,
        "phase": "wait_for_user_apply",
        "context": {
            "project_map_path": context.get("project_map_path"),
            "summary": context.get("summary"),
        },
        "plan": {
            "ok": plan.get("ok"),
            "report": plan.get("report"),
            "next_safe_command": plan.get("next_safe_command"),
        },
        "draft": {
            "ok": draft.get("ok"),
            "draft_path": draft.get("draft_path"),
            "summary": draft.get("summary"),
        },
        "verification_analysis": verification,
        "next_steps": [
            "Открой draft_path.",
            "Импортируй draft через Relay только если он соответствует цели.",
            "После применения нажми «Проверить проект».",
            "Если проверка падает — команда pc ai repair.",
        ],
    }
    set_phase("wait_for_user_apply", raw_goal, latest_draft=draft.get("draft_path", ""))
    report_path = _write_report("ai_agent_cycle", "# AI Agent Cycle\n\n" + json.dumps(result, ensure_ascii=False, indent=2))
    result["report"] = report_path
    return result


def run_verification() -> dict[str, Any]:
    from modules.ai_agent_memory_ru import remember_verification, set_phase

    set_phase("verify")
    try:
        from modules.strict_project_stability_ru import dispatch as strict_dispatch

        result = strict_dispatch("проверь проект")
        if isinstance(result, dict):
            remember_verification(str(result.get("report", "")), ok=bool(result.get("ok")))
            result["called_by"] = "ai_agent_core_ru"
            return result
    except Exception as exc:
        return {
            "ok": False,
            "mode": "ai_agent_verify_error",
            "generated_at": _now(),
            "error": str(exc),
        }

    return {
        "ok": False,
        "mode": "ai_agent_verify_error",
        "generated_at": _now(),
        "error": "strict verification returned non-dict result",
    }


def _format_status_summary() -> dict[str, Any]:
    from modules.ai_agent_memory_ru import status as memory_status

    memory = memory_status()
    return {
        "phase": memory.get("phase"),
        "active_goal": memory.get("active_goal"),
        "latest_draft": memory.get("latest_draft"),
        "latest_verification_report": memory.get("latest_verification_report"),
        "memory_dir": memory.get("memory_dir"),
    }


def status() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "ai_agent_core_status",
        "generated_at": _now(),
        "agent_version": AI_AGENT_VERSION,
        "agent_name": AI_AGENT_NAME,
        "state_machine": STATE_MACHINE,
        "summary": _format_status_summary(),
        "commands": [
            "pc ai status",
            "pc ai context",
            "pc ai plan <цель>",
            "pc ai draft <цель>",
            "pc ai cycle <цель>",
            "pc ai verify",
            "pc ai repair",
            "агент статус",
            "агент контекст",
            "агент план <цель>",
            "агент черновик <цель>",
        ],
    }


def report() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "ai_agent_core_report",
        "generated_at": _now(),
        "status": status(),
        "memory": _format_status_summary(),
    }


def dispatch(command: str) -> dict[str, Any]:
    raw = str(command or "").strip()
    text = raw.lower().replace("ё", "е")

    if text in {"pc ai status", "ai agent status", "агент статус", "статус агента"}:
        return status()

    if text in {"pc ai context", "ai agent context", "агент контекст", "проанализируй проект", "контекст проекта"}:
        return build_project_context()

    if text in {"pc ai report", "агент отчет", "агент отчёт"}:
        return report()

    if text in {"pc ai verify", "агент проверка"}:
        return run_verification()

    if text in {"pc ai repair", "агент repair", "почини по последнему отчету", "почини по последнему отчёту"}:
        return propose_repair()

    for prefix in ("pc ai plan ", "агент план ", "спланируй "):
        if text.startswith(prefix):
            return build_task_plan(raw[len(prefix):].strip())

    for prefix in ("pc ai draft ", "агент черновик ", "сделай патч для "):
        if text.startswith(prefix):
            return draft_patch(raw[len(prefix):].strip())

    for prefix in ("pc ai cycle ", "агент цикл "):
        if text.startswith(prefix):
            return run_agent_cycle(raw[len(prefix):].strip(), dry_run=True)

    if text in {"pc ai plan", "агент план"}:
        return build_task_plan("развивать LocalComet как локального AI-агента")

    if text in {"pc ai draft", "агент черновик"}:
        return draft_patch("развивать LocalComet как локального AI-агента")

    if text in {"pc ai cycle", "агент цикл"}:
        return run_agent_cycle("развивать LocalComet как локального AI-агента", dry_run=True)

    return {
        "ok": False,
        "mode": "ai_agent_unknown_command",
        "generated_at": _now(),
        "command": raw,
        "hint": "Используй: pc ai status, pc ai context, pc ai plan <цель>, pc ai draft <цель>, pc ai repair",
    }


def is_ai_agent_command(command: str) -> bool:
    text = str(command or "").strip().lower().replace("ё", "е")
    return (
        text.startswith("pc ai ")
        or text.startswith("агент план ")
        or text.startswith("агент черновик ")
        or text.startswith("агент цикл ")
        or text.startswith("сделай патч для ")
        or text.startswith("спланируй ")
        or text in {
            "агент статус",
            "статус агента",
            "агент контекст",
            "проанализируй проект",
            "контекст проекта",
            "агент проверка",
            "агент repair",
            "почини по последнему отчету",
            "почини по последнему отчёту",
        }
    )
