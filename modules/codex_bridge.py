import os
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root


ROOT_DIR = get_project_root()
BRIDGE_DIR = ROOT_DIR / "Projects" / "CodexBridge"
PROMPTS_DIR = BRIDGE_DIR / "prompts"
REPORTS_DIR = BRIDGE_DIR / "reports"

IMPORTANT_FILES = [
    "LocalComet_Control_Panel.py",
    "next/app_v5.py",
    "core/router.py",
    "core/planner.py",
    "core/executor.py",
    "modules/self_edit.py",
    "modules/chatgpt_relay.py",
    "modules/gpt_browser_bridge.py",
    "modules/true_auto_relay.py",
    "modules/stability_test.py",
    "modules/patch_registry.py",
    "agents/system_agent.py",
]


def _ensure_dirs():
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _project_rules():
    path = ROOT_DIR / "AGENTS.md"

    if not path.exists():
        return "AGENTS.md not found."

    return path.read_text(encoding="utf-8", errors="replace")[:6000]


def create_codex_prompt(task: str):
    _ensure_dirs()

    task = str(task or "").strip() or "Продолжи безопасное улучшение LocalComet."
    prompt_path = PROMPTS_DIR / f"codex_task_{_stamp()}.md"

    lines = [
        "# Codex Task",
        "",
        "## Project",
        "LocalComet / LocalAgent",
        "",
        "## Run",
        "```powershell",
        "python -m next.app_v5",
        "```",
        "",
        "## Current Task",
        task,
        "",
        "## Important Files",
    ]

    for rel_path in IMPORTANT_FILES:
        lines.append(f"- {rel_path}")

    lines.extend([
        "",
        "## Required Tests",
        "```powershell",
        "python -m py_compile LocalComet_Control_Panel.py modules\\patch_registry.py modules\\llm_provider.py modules\\stability_test.py modules\\self_edit.py agents\\system_agent.py",
        "```",
        "",
        "## Project Rules",
        _project_rules(),
    ])

    prompt_path.write_text("\n".join(lines), encoding="utf-8")
    return f"Codex prompt создан:\n{prompt_path}"


def open_codex_bridge():
    _ensure_dirs()
    os.startfile(str(BRIDGE_DIR))
    return f"Открыта папка CodexBridge:\n{BRIDGE_DIR}"
