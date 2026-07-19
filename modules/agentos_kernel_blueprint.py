from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import re
import uuid

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
AGENTOS_DIR = PROJECTS_DIR / "PCAgent" / "AgentOS"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "agentos_kernel_blueprint"
SKILLS_FILE = AGENTOS_DIR / "skills_registry.json"
FIREWALL_LOG = AGENTOS_DIR / "semantic_firewall_log.jsonl"
AGENTS_DRAFT_FILE = AGENTOS_DIR / "AGENTS_LocalComet_DRAFT.md"

LOCALCOMET_AGENTOS_VERSION = "agentos_blueprint_v1"

BLOCKED_INTENT_TERMS = [
    "delete",
    "remove",
    "rm ",
    "rmdir",
    "del ",
    "format",
    "wipe",
    "erase",
    "удали",
    "стереть",
    "формат",
    "снеси",
    "shell",
    "cmd",
    "powershell",
    "terminal",
    "registry",
    "regedit",
    "password",
    "пароль",
    "token",
    "secret",
    "private key",
    "api key",
    "ssh",
    "login",
    "логин",
    "bank",
    "банк",
    "payment",
    "casino",
    "ставк",
    "crypto wallet",
    "seed phrase",
]

PROMPT_INJECTION_TERMS = [
    "ignore previous instructions",
    "ignore all previous",
    "system prompt",
    "developer message",
    "reveal instructions",
    "bypass",
    "jailbreak",
    "disregard safety",
    "do not tell the user",
    "exfiltrate",
    "утеки данных",
    "обойди правила",
    "игнорируй инструкции",
    "скрой от пользователя",
    "выведи системный промпт",
]

OUTBOUND_DLP_PATTERNS = [
    r"sk-[A-Za-z0-9_\-]{12,}",
    r"ghp_[A-Za-z0-9_]{20,}",
    r"AIza[0-9A-Za-z\-_]{20,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
]

DEFAULT_SKILLS = [
    {
        "id": "single_port_chat",
        "name": "Single Port Chat",
        "category": "interface",
        "description": "Unified natural language command portal for LocalComet.",
        "commands": ["pc agentos status", "pc core status", "pc screen status"],
        "risk": "low",
        "dry_run_required": False,
        "confirmation_required": False,
        "enabled": True,
    },
    {
        "id": "semantic_firewall",
        "name": "Semantic Firewall",
        "category": "safety",
        "description": "Intent vetting, prompt-injection detection, and DLP-style output checks.",
        "commands": ["pc agentos firewall <intent>"],
        "risk": "critical_guard",
        "dry_run_required": False,
        "confirmation_required": False,
        "enabled": True,
    },
    {
        "id": "screen_aware_planner",
        "name": "Screen-Aware Planner",
        "category": "planner",
        "description": "Observes active window/screen metadata and creates safe screen-aware plans.",
        "commands": ["pc screen observe", "pc screen plan <goal>", "pc screen dry <goal>"],
        "risk": "medium",
        "dry_run_required": True,
        "confirmation_required": True,
        "enabled": True,
    },
    {
        "id": "desktop_primitives",
        "name": "Desktop Interaction Primitives",
        "category": "desktop",
        "description": "Windows list, mouse position, screenshot metadata, dry-click, dry-hotkey, confirmed focus.",
        "commands": ["pc desktop windows", "pc desktop dry click <x> <y>", "pc desktop focus подтверждаю: <title>"],
        "risk": "medium",
        "dry_run_required": True,
        "confirmation_required": True,
        "enabled": True,
    },
    {
        "id": "pc_codex_executor",
        "name": "PC Codex Executor",
        "category": "executor",
        "description": "Safe queue, dry-run, confirmed run, stop flag, and reports.",
        "commands": ["pc exec queue <goal>", "pc exec dry <goal>", "pc exec run подтверждаю: <goal>"],
        "risk": "high",
        "dry_run_required": True,
        "confirmation_required": True,
        "enabled": True,
    },
    {
        "id": "project_patch_workflow",
        "name": "Project Patch Workflow",
        "category": "coding",
        "description": "Project changes through request/response.json, validation, patch registry, rollback backup.",
        "commands": ["pc edit <goal>", "project context", "структура проекта"],
        "risk": "high",
        "dry_run_required": True,
        "confirmation_required": True,
        "enabled": True,
    },
    {
        "id": "open_source_gui_boost",
        "name": "Open-Source GUI Boost",
        "category": "adapter",
        "description": "OmniParser/ShowUI/UI-TARS/OpenCUA-inspired schemas and adapters.",
        "commands": ["pc boost status", "pc boost elements", "pc boost suggest <goal>"],
        "risk": "low",
        "dry_run_required": False,
        "confirmation_required": False,
        "enabled": True,
    },
    {
        "id": "web_research",
        "name": "Web Research",
        "category": "research",
        "description": "Research fallback and source-backed recommendations.",
        "commands": ["pc web <query>", "поиск в интернете <query>"],
        "risk": "medium",
        "dry_run_required": False,
        "confirmation_required": False,
        "enabled": True,
    },
]


AGENTOS_BLUEPRINT = {
    "version": LOCALCOMET_AGENTOS_VERSION,
    "name": "LocalComet AgentOS Kernel Blueprint",
    "principle": "LocalComet remains the safety-first orchestrator. External models and GUI tools are adapters, not trusted executors.",
    "layers": [
        {
            "name": "Single Port",
            "localcomet_component": "Panel Chat / PC Codex Chat",
            "purpose": "One natural-language control surface for text, voice, project, desktop, browser, and patch tasks.",
            "current_status": "active",
        },
        {
            "name": "Northbound Intent Interface",
            "localcomet_component": "run_panel_chat_command + command routers",
            "purpose": "Parse user intent into structured routes, plans, and safe tool calls.",
            "current_status": "active",
        },
        {
            "name": "Agent Kernel",
            "localcomet_component": "pc_codex_core + pc_codex_executor + screen_aware_planner",
            "purpose": "Goal memory, planning, dry-run, confirmed action, stop, report.",
            "current_status": "active",
        },
        {
            "name": "Semantic Firewall",
            "localcomet_component": "agentos semantic firewall + existing safety blocks",
            "purpose": "Detect unsafe intents, prompt injections, secret exfiltration, and high-risk actions.",
            "current_status": "v6.23 base",
        },
        {
            "name": "Skills-as-Modules",
            "localcomet_component": "modules/*.py + skills_registry.json",
            "purpose": "Reusable safe tools with metadata, risk level, commands, and confirmation rules.",
            "current_status": "v6.23 base",
        },
        {
            "name": "Southbound Tool Interface",
            "localcomet_component": "desktop primitives, browser tools, project workflow, reports",
            "purpose": "Execute only through allowlisted modules, never arbitrary shell.",
            "current_status": "active",
        },
        {
            "name": "Personal Context / Knowledge Graph",
            "localcomet_component": "project context, memory, reports, future PKG",
            "purpose": "Remember goals, workflows, preferences, project structure, and validated skills.",
            "current_status": "planned",
        },
        {
            "name": "Rollback / Checkpoints",
            "localcomet_component": "SelfEdit rollback + backups + future task checkpoints",
            "purpose": "Every risky change should have audit trail and recovery path.",
            "current_status": "partial",
        },
    ],
}


ROADMAP = [
    {
        "version": "v6.23",
        "name": "AgentOS Kernel + Skills Blueprint",
        "adds": [
            "AgentOS blueprint",
            "skills registry",
            "semantic firewall base",
            "AGENTS.md draft generator",
            "memory/checkpoint roadmap",
            "reports",
        ],
    },
    {
        "version": "v6.24",
        "name": "UI Parser Adapter",
        "adds": [
            "pc ui parse",
            "pc ui elements",
            "pc ui find <text>",
            "OmniParser-compatible output schema",
            "screen element confidence scoring",
        ],
    },
    {
        "version": "v6.25",
        "name": "Visual Action Suggestion",
        "adds": [
            "ShowUI/UI-TARS-style action parser",
            "goal + UI elements -> action suggestion",
            "action confidence",
            "semantic firewall before executor",
        ],
    },
    {
        "version": "v6.26",
        "name": "Safe Text Operator",
        "adds": [
            "confirmed text input",
            "active-window checks",
            "no secrets/tokens/passwords",
            "no auto-enter submission",
        ],
    },
    {
        "version": "v6.27",
        "name": "Task Memory + Checkpoints",
        "adds": [
            "task sessions",
            "checkpoint graph",
            "execution trace",
            "resume/continue",
            "rollback hints",
        ],
    },
    {
        "version": "v6.28",
        "name": "Full Agent Mode",
        "adds": [
            "pc agent <goal>",
            "observe -> intent -> firewall -> skills -> plan -> dry-run -> confirm -> execute -> report",
            "bounded multi-step loop",
        ],
    },
]


AGENTS_MD_TEMPLATE = """# AGENTS.md — LocalComet Safe Agent Workspace

## Mission

You are LocalComet, a local safety-first PC agent. Your job is to help the user operate the project and desktop through a controlled workflow.

## Prime Rules

1. Never execute arbitrary shell, cmd, powershell, terminal, registry, format, delete, wipe, or credential actions.
2. Never request, expose, store, paste, or transmit passwords, tokens, API keys, SSH keys, seed phrases, banking data, or payment data.
3. For project changes, use request/response patch workflow. Do not directly rewrite important files without a patch and tests.
4. For desktop actions, use observe, plan, dry-run, and explicit confirmation before execution.
5. For uncertain tasks, ask a clarifying question or create a safe plan.
6. Prefer quarantine over deletion.
7. Always create reports for executed workflows.

## Standard Pipeline

```text
1. Understand user goal.
2. Run semantic firewall check.
3. Collect project/screen context.
4. Select a safe skill.
5. Build a plan.
6. Run dry-run.
7. Ask for explicit confirmation when needed.
8. Execute one bounded step.
9. Save report.
10. Suggest next step.
```

## LocalComet Command Families

```text
pc agentos status
pc agentos blueprint
pc agentos skills
pc agentos firewall <intent>
pc screen plan <goal>
pc desktop dry click <x> <y>
pc exec dry <goal>
pc exec run подтверждаю: <goal>
pc boost suggest <goal>
pc edit <project change>
```

## Safety Permission Profile

```yaml
read_project_files: allowed
write_project_files_directly: denied
write_project_files_via_patch: allowed
execute_arbitrary_shell: denied
execute_safe_allowlisted_tools: allowed
desktop_observe: allowed
desktop_click_without_dry_run: denied
desktop_type_without_confirmation: denied
delete_files: denied
quarantine_files: allowed_after_confirmation
handle_secrets: denied
```

## Working Memory

Keep task notes in `Projects/PCAgent/`.
Keep reports in `Projects/Reports/`.
Keep generated patch requests in the relay/self-edit workflow.
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    AGENTOS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _append_jsonl(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def ensure_skill_registry():
    _ensure_dirs()
    payload = _read_json(SKILLS_FILE, None)
    if not isinstance(payload, dict) or "skills" not in payload:
        payload = {
            "ok": True,
            "version": "localcomet_skill_registry_v1",
            "created_at": _now(),
            "updated_at": _now(),
            "skills": DEFAULT_SKILLS,
        }
        _write_json(SKILLS_FILE, payload)
    return payload


def save_skill_registry(registry):
    registry["updated_at"] = _now()
    _write_json(SKILLS_FILE, registry)
    set_value("agentos_skills_registry", registry)
    return registry


def status():
    registry = ensure_skill_registry()
    payload = {
        "ok": True,
        "mode": "agentos_kernel_blueprint",
        "generated_at": _now(),
        "version": LOCALCOMET_AGENTOS_VERSION,
        "skills_count": len(registry.get("skills", [])),
        "enabled_skills": len([item for item in registry.get("skills", []) if item.get("enabled")]),
        "blueprint_layers": len(AGENTOS_BLUEPRINT.get("layers", [])),
        "last_firewall": get_value("agentos_last_firewall", ""),
        "commands": [
            "pc agentos status",
            "pc agentos blueprint",
            "pc agentos skills",
            "pc agentos firewall <intent>",
            "pc agentos memory",
            "pc agentos roadmap",
            "pc agentos agents.md",
            "pc agentos report",
        ],
        "safety": [
            "Semantic Firewall checks intent before high-risk actions.",
            "Skills are metadata + safe command routes, not arbitrary plugins.",
            "No shell/cmd/powershell/delete/secrets.",
            "Project modifications stay inside request/response patch workflow.",
            "Desktop actions keep dry-run and confirmation gates.",
        ],
    }
    set_value("agentos_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    lines = [
        "LocalComet AgentOS Kernel Blueprint:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- version: {payload.get('version')}",
        f"- skills_count: {payload.get('skills_count')}",
        f"- enabled_skills: {payload.get('enabled_skills')}",
        f"- blueprint_layers: {payload.get('blueprint_layers')}",
        "",
        "Commands:",
    ]
    lines.extend("- " + item for item in payload.get("commands", []))
    lines.append("")
    lines.append("Safety:")
    lines.extend("- " + item for item in payload.get("safety", []))
    return "\n".join(lines)


def blueprint():
    payload = {
        "ok": True,
        "generated_at": _now(),
        "blueprint": AGENTOS_BLUEPRINT,
        "localcomet_mapping": {
            "single_port": "Panel Chat / PC Codex Chat",
            "intent_parser": "run_panel_chat_command routers",
            "agent_kernel": ["pc_codex_core", "pc_codex_executor", "pc_screen_planner"],
            "semantic_firewall": "pc agentos firewall",
            "skills": "skills_registry.json",
            "rollback": ["SelfEdit rollback", "LocalAgent_Backups", "future checkpoints"],
        },
    }
    set_value("agentos_blueprint", payload)
    return payload


def skills():
    registry = ensure_skill_registry()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "registry_path": str(SKILLS_FILE),
        "skills": registry.get("skills", []),
        "counts": {
            "total": len(registry.get("skills", [])),
            "enabled": len([item for item in registry.get("skills", []) if item.get("enabled")]),
            "high_risk": len([item for item in registry.get("skills", []) if item.get("risk") == "high"]),
        },
    }
    set_value("agentos_skills", payload)
    return payload


def _detect_dlp(text):
    findings = []
    for pattern in OUTBOUND_DLP_PATTERNS:
        if re.search(pattern, str(text or "")):
            findings.append(pattern)
    return findings


def semantic_firewall(intent):
    raw = str(intent or "").strip()
    lower = _norm(raw)
    blocked_hits = [term for term in BLOCKED_INTENT_TERMS if term in lower]
    injection_hits = [term for term in PROMPT_INJECTION_TERMS if term in lower]
    dlp_hits = _detect_dlp(raw)

    risk_score = 0
    risk_score += len(blocked_hits) * 5
    risk_score += len(injection_hits) * 4
    risk_score += len(dlp_hits) * 6

    if not raw:
        verdict = "blocked"
        reason = "empty intent"
    elif dlp_hits:
        verdict = "blocked"
        reason = "possible secret/payment/key pattern detected"
    elif blocked_hits:
        verdict = "blocked"
        reason = "blocked intent terms detected"
    elif injection_hits:
        verdict = "review"
        reason = "possible prompt-injection terms detected"
    else:
        verdict = "allowed_for_planning"
        reason = "no immediate semantic firewall hit"

    recommended_route = "pc screen plan <goal>"
    if verdict == "blocked":
        recommended_route = "refuse_or_create_safe_alternative"
    elif any(word in lower for word in ["проект", "код", "модуль", "patch", "response.json", "исправь"]):
        recommended_route = "pc edit <goal>"
    elif any(word in lower for word in ["клик", "click", "hotkey", "мыш", "окно", "focus"]):
        recommended_route = "pc desktop dry <action>"
    elif any(word in lower for word in ["открыть", "запусти", "open", "launch"]):
        recommended_route = "pc exec dry <goal>"
    elif any(word in lower for word in ["найди", "поиск", "web", "интернет", "что такое", "как сделать"]):
        recommended_route = "pc web <query>"

    payload = {
        "ok": verdict != "blocked",
        "mode": "semantic_firewall",
        "generated_at": _now(),
        "intent": raw,
        "verdict": verdict,
        "reason": reason,
        "risk_score": risk_score,
        "blocked_terms": sorted(set(blocked_hits)),
        "prompt_injection_terms": sorted(set(injection_hits)),
        "dlp_patterns": dlp_hits,
        "recommended_route": recommended_route,
        "rules": {
            "no_shell": True,
            "no_delete": True,
            "no_secrets": True,
            "dry_run_first": True,
            "confirmation_for_execution": True,
            "project_changes_via_patch": True,
        },
    }

    set_value("agentos_last_firewall", payload)
    _append_jsonl(FIREWALL_LOG, payload)
    return payload


def memory_blueprint():
    payload = {
        "ok": True,
        "generated_at": _now(),
        "mode": "agentos_memory_blueprint",
        "current_memory_sources": [
            "core.state key-value state",
            "Projects/PCAgent session JSON files",
            "Projects/Reports generated reports",
            "Patch Registry",
            "SelfEdit rollback files",
            "project context scanner",
        ],
        "future_personal_knowledge_graph": {
            "nodes": [
                "Task",
                "Skill",
                "File",
                "Window",
                "Report",
                "Patch",
                "UserPreference",
                "WorkflowPattern",
            ],
            "edges": [
                "Task uses Skill",
                "Skill creates Report",
                "Patch changes File",
                "Window observed during Task",
                "WorkflowPattern repeats Task",
            ],
            "storage_plan": "Projects/PCAgent/AgentOS/personal_knowledge_graph.json",
            "privacy": "local only; no secrets; tainted external content cannot trigger high-privilege actions",
        },
        "checkpoint_plan": [
            "Before risky project patch: backup and rollback file.",
            "Before desktop action: dry-run artifact.",
            "During multi-step task: action trace with timestamp.",
            "After completion: report with next-step suggestions.",
        ],
    }
    set_value("agentos_memory_blueprint", payload)
    return payload


def roadmap():
    payload = {
        "ok": True,
        "generated_at": _now(),
        "roadmap": ROADMAP,
    }
    set_value("agentos_roadmap", payload)
    return payload


def generate_agents_md():
    _ensure_dirs()
    AGENTS_DRAFT_FILE.write_text(AGENTS_MD_TEMPLATE, encoding="utf-8")
    payload = {
        "ok": True,
        "generated_at": _now(),
        "path": str(AGENTS_DRAFT_FILE),
        "note": "Draft only. Review before copying into project root.",
        "safety_profile": {
            "direct_write_to_root": False,
            "contains_secrets": False,
            "shell_commands": False,
        },
    }
    set_value("agentos_agents_md_draft", payload)
    return payload


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "blueprint": blueprint(),
        "skills": skills(),
        "memory": memory_blueprint(),
        "roadmap": roadmap(),
        "last_firewall": get_value("agentos_last_firewall", ""),
    }

    json_path = REPORTS_DIR / f"agentos_kernel_blueprint_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"agentos_kernel_blueprint_report_{_stamp()}.md"
    _write_json(json_path, payload)

    md = [
        "# LocalComet AgentOS Kernel Blueprint Report",
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
        "## Blueprint Layers",
        "",
    ]

    for layer in AGENTOS_BLUEPRINT["layers"]:
        md.extend([
            f"### {layer['name']}",
            "",
            f"- LocalComet component: {layer['localcomet_component']}",
            f"- Purpose: {layer['purpose']}",
            f"- Status: {layer['current_status']}",
            "",
        ])

    md.extend([
        "## Skills",
        "",
        "```json",
        json.dumps(payload["skills"]["skills"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Roadmap",
        "",
        "```json",
        json.dumps(ROADMAP, ensure_ascii=False, indent=2),
        "```",
    ])

    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc agentos", "pc agentos status", "pc agentos статус", "agentos status"}:
        return format_status(status())

    if lower in {"pc agentos blueprint", "pc agentos архитектура", "agentos blueprint"}:
        return format_payload(blueprint())

    if lower in {"pc agentos skills", "pc agentos скиллы", "pc agentos skills list", "agentos skills"}:
        return format_payload(skills())

    if lower in {"pc agentos memory", "pc agentos память", "agentos memory"}:
        return format_payload(memory_blueprint())

    if lower in {"pc agentos roadmap", "pc agentos план", "agentos roadmap"}:
        return format_payload(roadmap())

    if lower in {"pc agentos agents.md", "pc agentos agents", "pc agentos ag", "agentos agents.md"}:
        return format_payload(generate_agents_md())

    if lower in {"pc agentos report", "pc agentos отчет", "pc agentos отчёт", "agentos report"}:
        return format_payload(report("manual report"))

    prefixes = [
        "pc agentos firewall ",
        "pc agentos файрвол ",
        "pc agentos проверка ",
        "agentos firewall ",
    ]

    for prefix in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            return format_payload(semantic_firewall(value))

    return format_payload({
        "ok": False,
        "error": "Unknown AgentOS command.",
        "help": status().get("commands", []),
    })


def is_agentos_command(command):
    lower = _norm(command)
    exact = {
        "pc agentos",
        "pc agentos status",
        "pc agentos статус",
        "agentos status",
        "pc agentos blueprint",
        "pc agentos архитектура",
        "agentos blueprint",
        "pc agentos skills",
        "pc agentos скиллы",
        "pc agentos skills list",
        "agentos skills",
        "pc agentos memory",
        "pc agentos память",
        "agentos memory",
        "pc agentos roadmap",
        "pc agentos план",
        "agentos roadmap",
        "pc agentos agents.md",
        "pc agentos agents",
        "pc agentos ag",
        "agentos agents.md",
        "pc agentos report",
        "pc agentos отчет",
        "pc agentos отчёт",
        "agentos report",
    }
    if lower in exact:
        return True
    prefixes = (
        "pc agentos firewall ",
        "pc agentos файрвол ",
        "pc agentos проверка ",
        "agentos firewall ",
    )
    return lower.startswith(prefixes)
