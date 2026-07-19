from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_PATH = Path(__file__).resolve().parents[1]
MEMORY_DIR = ROOT_PATH / "Projects" / "AgentMemory"
DRAFT_DIR = MEMORY_DIR / "drafts"
PLANS_DIR = MEMORY_DIR / "plans"

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
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    PLANS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_slug(text: str) -> str:
    lowered = str(text or "agent_task").strip().lower().replace("ё", "е")
    lowered = re.sub(r"[^a-zа-я0-9]+", "_", lowered, flags=re.IGNORECASE)
    lowered = lowered.strip("_")
    return lowered[:48] or "agent_task"


def _danger_reason(goal: str) -> str:
    lowered = str(goal or "").lower().replace("ё", "е")
    for marker in DANGEROUS_PATTERNS:
        if marker in lowered:
            return "цель содержит потенциально опасный маркер: " + marker
    return ""


def _load_context() -> dict[str, Any]:
    try:
        from modules.ai_project_map_ru import build_project_map

        return build_project_map()
    except Exception as exc:
        return {
            "ok": False,
            "mode": "ai_patch_planner_context_error",
            "error": str(exc),
        }


def build_patch_plan(goal: str) -> dict[str, Any]:
    _ensure_dirs()
    raw_goal = str(goal or "").strip() or "улучшить LocalComet как AI-агента"
    danger = _danger_reason(raw_goal)

    context = _load_context()
    stamp = _stamp()
    plan_path = PLANS_DIR / f"agent_plan_{stamp}_{_safe_slug(raw_goal)}.md"

    if danger:
        plan_text = (
            "# AI Agent Patch Plan\n\n"
            f"- generated_at: {_now()}\n"
            f"- goal: {raw_goal}\n"
            f"- blocked: true\n"
            f"- reason: {danger}\n"
        )
        plan_path.write_text(plan_text, encoding="utf-8")
        return {
            "ok": False,
            "mode": "ai_patch_plan_blocked",
            "generated_at": _now(),
            "goal": raw_goal,
            "reason": danger,
            "plan_path": str(plan_path),
        }

    summary = context.get("control_panel", {}) if isinstance(context, dict) else {}
    plan_text = (
        "# AI Agent Patch Plan\n\n"
        f"- generated_at: {_now()}\n"
        f"- goal: {raw_goal}\n"
        f"- current_version: {summary.get('version', '')}\n"
        f"- project_map: {context.get('project_map_path', '') if isinstance(context, dict) else ''}\n\n"
        "## Strategy\n\n"
        "1. Сузить цель до минимального безопасного изменения.\n"
        "2. Использовать карту проекта, а не угадывать файлы.\n"
        "3. Сформировать response.json draft с одним installer в tools/.\n"
        "4. Не применять patch автоматически.\n"
        "5. После применения запустить строгую проверку проекта.\n"
        "6. Если проверка падает — построить repair plan по отчёту.\n\n"
        "## Target areas\n\n"
        "- modules/ai_agent_core_ru.py\n"
        "- modules/ai_project_map_ru.py\n"
        "- modules/ai_patch_planner_ru.py\n"
        "- modules/ai_agent_memory_ru.py\n"
        "- modules/premium_task_panel_ru.py\n"
        "- LocalComet_Control_Panel.py\n"
    )
    plan_path.write_text(plan_text, encoding="utf-8")

    return {
        "ok": True,
        "mode": "ai_patch_plan",
        "generated_at": _now(),
        "goal": raw_goal,
        "plan_path": str(plan_path),
        "context_path": context.get("project_map_path", "") if isinstance(context, dict) else "",
        "target_files": [
            "modules/ai_agent_core_ru.py",
            "modules/ai_project_map_ru.py",
            "modules/ai_patch_planner_ru.py",
            "modules/ai_agent_memory_ru.py",
            "modules/premium_task_panel_ru.py",
            "LocalComet_Control_Panel.py",
        ],
        "next_step": "pc ai draft " + raw_goal,
    }


def _draft_installer_content(goal: str, stamp: str) -> str:
    safe_goal = repr(str(goal or "agent task"))
    return (
        "from pathlib import Path\n"
        "import json\n"
        "from datetime import datetime\n\n"
        "ROOT_PATH = Path(__file__).resolve().parents[1]\n"
        "REPORT_DIR = ROOT_PATH / 'Projects' / 'AgentMemory' / 'applied_drafts'\n"
        "REPORT_DIR.mkdir(parents=True, exist_ok=True)\n"
        f"MARKER = REPORT_DIR / 'agent_draft_marker_{stamp}.json'\n"
        "payload = {\n"
        "    'ok': True,\n"
        "    'mode': 'ai_agent_draft_marker',\n"
        "    'generated_at': datetime.now().replace(microsecond=0).isoformat(),\n"
        f"    'goal': {safe_goal},\n"
        "    'note': 'Safe marker generated by AI Agent Core. Replace this draft with concrete code changes after human review.',\n"
        "}\n"
        "MARKER.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')\n"
        "print('AI Agent draft marker written:', MARKER)\n"
    )


def draft_patch(goal: str) -> dict[str, Any]:
    _ensure_dirs()
    raw_goal = str(goal or "").strip() or "улучшить LocalComet как AI-агента"
    danger = _danger_reason(raw_goal)
    if danger:
        return {
            "ok": False,
            "mode": "ai_patch_draft_blocked",
            "generated_at": _now(),
            "goal": raw_goal,
            "reason": danger,
        }

    plan = build_patch_plan(raw_goal)
    stamp = _stamp()
    slug = _safe_slug(raw_goal)
    draft_path = DRAFT_DIR / f"response_agent_draft_{stamp}_{slug}.json"
    installer_path = f"tools/install_ai_agent_draft_marker_{stamp}.py"

    draft = {
        "summary": (
            "AI Agent Draft Patch: safe human-review draft generated by LocalComet AI Agent Core. "
            "This first-stage draft creates a marker report only, so the Relay pipeline can be verified before concrete code modifications. "
            "No browser, npm, shell, cmd, powershell, backend, delete, deploy, token, API-key, secret, or destructive actions are added."
        ),
        "operations": [
            {
                "type": "create",
                "path": installer_path,
                "content": _draft_installer_content(raw_goal, stamp),
            }
        ],
        "tests": [
            f"python {installer_path.replace('/', '\\\\')}",
            f"python -m py_compile {installer_path.replace('/', '\\\\')}",
            "python -c \"from pathlib import Path; files=list(Path('Projects/AgentMemory/applied_drafts').glob('agent_draft_marker_*.json')); assert files; print(files[-1])\"",
        ],
    }

    draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        from modules.ai_agent_memory_ru import remember_draft
        remember_draft(str(draft_path), raw_goal)
    except Exception:
        pass

    return {
        "ok": True,
        "mode": "ai_patch_draft",
        "generated_at": _now(),
        "goal": raw_goal,
        "draft_path": str(draft_path),
        "plan_path": plan.get("plan_path") if isinstance(plan, dict) else "",
        "summary": draft["summary"],
        "operations": len(draft["operations"]),
        "tests": len(draft["tests"]),
        "next_steps": [
            "Открыть draft_path.",
            "Проверить summary/operations/tests.",
            "Импортировать draft через Relay только после человеческого подтверждения.",
            "После применения нажать «Проверить проект».",
        ],
    }


def status() -> dict[str, Any]:
    _ensure_dirs()
    return {
        "ok": True,
        "mode": "ai_patch_planner_status",
        "generated_at": _now(),
        "draft_dir": str(DRAFT_DIR),
        "plans_dir": str(PLANS_DIR),
        "draft_count": len(list(DRAFT_DIR.glob("response_agent_draft_*.json"))),
        "plan_count": len(list(PLANS_DIR.glob("agent_plan_*.md"))),
    }


def report() -> dict[str, Any]:
    _ensure_dirs()
    return {
        "ok": True,
        "mode": "ai_patch_planner_report",
        "generated_at": _now(),
        "status": status(),
        "latest_drafts": [str(path) for path in sorted(DRAFT_DIR.glob("response_agent_draft_*.json"), reverse=True)[:10]],
        "latest_plans": [str(path) for path in sorted(PLANS_DIR.glob("agent_plan_*.md"), reverse=True)[:10]],
    }


def dispatch(command: str) -> dict[str, Any]:
    raw = str(command or "").strip()
    text = raw.lower().replace("ё", "е")
    if text in {"pc ai patch planner status", "планировщик патчей статус"}:
        return status()
    if text in {"pc ai patch planner report", "планировщик патчей отчет", "планировщик патчей отчёт"}:
        return report()
    if text.startswith("pc ai draft "):
        return draft_patch(raw[len("pc ai draft "):].strip())
    if text.startswith("сделай патч для "):
        return draft_patch(raw[len("сделай патч для "):].strip())
    return {
        "ok": False,
        "mode": "ai_patch_planner_unknown_command",
        "generated_at": _now(),
        "command": raw,
        "hint": "Используй: pc ai draft <цель>",
    }


def is_ai_patch_planner_command(command: str) -> bool:
    text = str(command or "").strip().lower().replace("ё", "е")
    return text.startswith("pc ai draft ") or text.startswith("сделай патч для ") or text.startswith("pc ai patch planner")
