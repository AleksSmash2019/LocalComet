from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import textwrap

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
ONBOARDING_DIR = PROJECTS_DIR / "PCAgent" / "Onboarding"
DEMO_DIR = PROJECTS_DIR / "PCAgent" / "DemoWorkspace"
DEMO_SITE_DIR = DEMO_DIR / "demo-site"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "agent_onboarding_demo"

QUICKSTART_AGENTS_FILE = ONBOARDING_DIR / "AGENTS_LocalComet_QUICKSTART.md"
ONBOARDING_CHECKLIST_FILE = ONBOARDING_DIR / "onboarding_checklist.json"
DEMO_REQUEST_FILE = DEMO_DIR / "demo_site_request.md"

AGENT_FORMULA = {
    "LLM": {
        "plain": "Мозг агента.",
        "localcomet": "LM Studio / Qwen / ChatGPT relay / local model smoke checks.",
    },
    "Tools": {
        "plain": "Руки агента.",
        "localcomet": "pc desktop, pc screen, pc exec, pc boost, pc agentos, project patch workflow.",
    },
    "Loop": {
        "plain": "Цикл достижения цели.",
        "localcomet": "observe -> plan -> dry-run -> confirm -> execute -> report.",
    },
    "Memory": {
        "plain": "Память и рабочее пространство.",
        "localcomet": "core.state, Projects/PCAgent, Projects/Reports, patch registry, future knowledge graph.",
    },
}

SAFETY_PROFILE = {
    "admin_terminal": "denied",
    "arbitrary_shell": "denied",
    "execute_all_commands": "denied",
    "auto_yes_all": "denied",
    "secrets_passwords_tokens_ssh": "denied",
    "delete_files": "denied",
    "quarantine_files": "allowed_after_confirmation",
    "read_project_files": "allowed",
    "project_changes": "response_json_patch_only",
    "desktop_actions": "dry_run_then_explicit_confirmation",
    "reports": "required_for_workflows",
}

ONBOARDING_STEPS = [
    {
        "id": "understand_agent",
        "title": "Понять, что агент это LLM + Tools + Loop + Memory.",
        "command": "pc onboard explain",
        "status": "ready",
    },
    {
        "id": "check_localcomet_stack",
        "title": "Проверить LocalComet stack и safety-профиль.",
        "command": "pc onboard localcomet",
        "status": "ready",
    },
    {
        "id": "check_lmstudio",
        "title": "Проверить локальную модель / LM Studio.",
        "command": "pc onboard lmstudio",
        "status": "manual_check",
    },
    {
        "id": "optional_qwen_cli",
        "title": "Qwen CLI как внешний reference agent, не как доверенный executor.",
        "command": "pc onboard qwen",
        "status": "optional",
    },
    {
        "id": "generate_agents_md",
        "title": "Создать безопасный AGENTS.md quickstart draft.",
        "command": "pc onboard agents.md",
        "status": "ready",
    },
    {
        "id": "demo_site",
        "title": "Сделать безопасный demo-site workflow через request/draft files.",
        "command": "pc demo site plan",
        "status": "ready",
    },
]

LOCALCOMET_QUICKSTART_AGENTS_MD = """# AGENTS.md — LocalComet Quickstart

## What is this agent?

LocalComet is a local safety-first AI agent. It is not just a chatbot. It is a system made of four parts:

```text
LLM    -> reasoning brain
Tools  -> safe hands
Loop   -> plan/dry-run/confirm/execute/report
Memory -> project context, reports, state, skill registry
```

## Golden Workflow

```text
1. Understand the user's goal.
2. Check safety with semantic firewall.
3. Observe project/screen context.
4. Pick a safe skill.
5. Create a plan.
6. Run dry-run.
7. Ask for explicit confirmation when needed.
8. Execute one bounded safe step.
9. Save report.
10. Suggest the next step.
```

## LocalComet Safety Rules

```yaml
admin_terminal: denied
arbitrary_shell: denied
execute_all_commands: denied
auto_yes_all: denied
secrets_passwords_tokens_ssh: denied
delete_files: denied
quarantine_files: allowed_after_confirmation
read_project_files: allowed
project_changes: response_json_patch_only
desktop_actions: dry_run_then_explicit_confirmation
reports: required_for_workflows
```

## Useful Commands

```text
pc onboard status
pc onboard explain
pc onboard safety
pc agentos firewall <intent>
pc screen plan <goal>
pc desktop windows
pc exec dry <goal>
pc exec run подтверждаю: <goal>
pc demo site plan
pc demo site request
```

## Demo Task

Use the safe demo workflow:

```text
pc demo site plan
pc demo site dry
pc demo site request
```

The agent must not run a web server or shell command automatically. It creates draft files and a patch/request plan first.
"""


DEMO_INDEX_HTML = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LocalComet Demo Site</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="page">
    <section class="hero" aria-labelledby="hero-title">
      <p class="eyebrow">LocalComet Demo Workspace</p>
      <h1 id="hero-title">Добро пожаловать!</h1>
      <p class="lead">
        Это безопасный draft-сайт, созданный через LocalComet onboarding workflow.
        Никакие shell-команды не выполнялись автоматически.
      </p>
      <a class="button" href="#details">Посмотреть детали</a>
    </section>
    <section id="details" class="card">
      <h2>Как работает агент</h2>
      <p>LLM думает, tools действуют, loop ведёт задачу до результата, memory сохраняет контекст.</p>
    </section>
  </main>
</body>
</html>
"""

DEMO_STYLES_CSS = """* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  font-family: Arial, sans-serif;
  background: linear-gradient(135deg, #4f46e5, #7c3aed, #0f172a);
  color: #ffffff;
}

.page {
  width: min(960px, calc(100% - 32px));
  margin: 0 auto;
  padding: 72px 0;
}

.hero {
  min-height: 70vh;
  display: grid;
  align-content: center;
  text-align: center;
}

.eyebrow {
  margin: 0 0 16px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.76);
}

h1 {
  margin: 0;
  font-size: clamp(44px, 9vw, 92px);
  line-height: 0.95;
}

.lead {
  max-width: 720px;
  margin: 24px auto;
  font-size: clamp(18px, 2.5vw, 24px);
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.88);
}

.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 48px;
  padding: 0 22px;
  border-radius: 999px;
  background: #ffffff;
  color: #4f46e5;
  text-decoration: none;
  font-weight: 700;
}

.card {
  margin-top: 40px;
  padding: 28px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 24px;
  background: rgba(15, 23, 42, 0.46);
  backdrop-filter: blur(14px);
}
"""

DEMO_README = """# Demo Site Draft

This folder was generated by LocalComet Agent Onboarding + Demo Workspace.

## Safety

No shell command was executed.
No local server was started automatically.
No admin terminal was used.
No secrets were requested.

## Files

- `index.html`
- `styles.css`

Open `index.html` manually in a browser or create a LocalComet patch/deploy workflow later.
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    ONBOARDING_DIR.mkdir(parents=True, exist_ok=True)
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _localcomet_stack():
    stack = [
        "PC Codex Core",
        "PC Codex Executor",
        "Screen-Aware Planner",
        "Open-Source GUI Boost Base",
        "Desktop Interaction Primitives",
        "AgentOS Kernel + Skills Blueprint",
    ]
    return {
        "ok": True,
        "items": stack,
        "pipeline": "observe -> plan -> dry-run -> confirm -> execute -> report",
        "safe_execution": "confirmed action only",
    }


def status():
    payload = {
        "ok": True,
        "mode": "agent_onboarding_demo",
        "generated_at": _now(),
        "formula": AGENT_FORMULA,
        "steps_count": len(ONBOARDING_STEPS),
        "safety_profile": SAFETY_PROFILE,
        "last_checklist": get_value("agent_onboarding_last_checklist", ""),
        "last_demo": get_value("agent_onboarding_last_demo", ""),
        "commands": [
            "pc onboard status",
            "pc onboard explain",
            "pc onboard checklist",
            "pc onboard localcomet",
            "pc onboard qwen",
            "pc onboard lmstudio",
            "pc onboard safety",
            "pc onboard agents.md",
            "pc onboard report",
            "pc demo site plan",
            "pc demo site dry",
            "pc demo site request",
            "pc demo site files",
            "pc demo site report",
        ],
    }
    set_value("agent_onboarding_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    lines = [
        "Agent Onboarding + Demo Workspace:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- steps_count: {payload.get('steps_count')}",
        "",
        "Agent formula:",
    ]
    for key, item in payload.get("formula", {}).items():
        lines.append(f"- {key}: {item.get('plain')} | LocalComet: {item.get('localcomet')}")
    lines.append("")
    lines.append("Commands:")
    lines.extend("- " + command for command in payload.get("commands", []))
    return "\n".join(lines)


def explain():
    payload = {
        "ok": True,
        "mode": "agent_explanation",
        "generated_at": _now(),
        "short": "ИИ-агент = LLM + Tools + Loop + Memory.",
        "formula": AGENT_FORMULA,
        "localcomet_translation": [
            "LLM: мозг для рассуждения.",
            "Tools: безопасные модули desktop/screen/exec/project/browser.",
            "Loop: план -> dry-run -> подтверждение -> действие -> отчёт.",
            "Memory: state, reports, project context, skills registry.",
        ],
        "why_localcomet_is_safer": [
            "No admin terminal by default.",
            "No arbitrary shell.",
            "No auto-yes for unknown commands.",
            "No secrets/tokens/passwords.",
            "Project edits through response.json patch workflow.",
        ],
    }
    set_value("agent_onboarding_explain", payload)
    return payload


def checklist():
    _ensure_dirs()
    items = []
    for step in ONBOARDING_STEPS:
        items.append({
            "id": step["id"],
            "title": step["title"],
            "command": step["command"],
            "status": step["status"],
            "done": step["status"] in {"ready", "optional"},
        })

    payload = {
        "ok": True,
        "mode": "agent_onboarding_checklist",
        "generated_at": _now(),
        "items": items,
        "safety_profile": SAFETY_PROFILE,
        "path": str(ONBOARDING_CHECKLIST_FILE),
    }
    _write_json(ONBOARDING_CHECKLIST_FILE, payload)
    set_value("agent_onboarding_last_checklist", payload)
    return payload


def localcomet():
    payload = {
        "ok": True,
        "mode": "localcomet_stack_check",
        "generated_at": _now(),
        "stack": _localcomet_stack(),
        "recommended_first_commands": [
            "pc agentos status",
            "pc onboard explain",
            "pc screen status",
            "pc desktop status",
            "pc exec status",
        ],
    }
    set_value("agent_onboarding_localcomet", payload)
    return payload


def qwen_reference():
    payload = {
        "ok": True,
        "mode": "qwen_cli_reference",
        "generated_at": _now(),
        "positioning": "Qwen CLI can be treated as an external reference/coding agent, not a trusted executor inside LocalComet.",
        "safe_use": [
            "Use it for comparison or manual coding workflows.",
            "Do not paste secrets into external agents.",
            "Do not run unknown install commands through LocalComet.",
            "Do not grant auto-approve all commands.",
            "LocalComet remains the orchestrator for project safety.",
        ],
        "localcomet_alternative": [
            "pc edit <goal>",
            "pc agentos firewall <intent>",
            "response.json patch workflow",
            "Auto Verification + Full Stability",
        ],
    }
    set_value("agent_onboarding_qwen_reference", payload)
    return payload


def lmstudio_reference():
    payload = {
        "ok": True,
        "mode": "lmstudio_reference",
        "generated_at": _now(),
        "purpose": "Local LLM backend for private/offline reasoning.",
        "checklist": [
            "Model loads successfully.",
            "Local server is running.",
            "Tool-use capable model preferred.",
            "Large context configured when hardware allows.",
            "Compact prompt enabled when context pressure appears.",
            "Model smoke test passes in LocalComet.",
        ],
        "localcomet_commands": [
            "lmstudio diagnostics",
            "model smoke",
            "auto verification full",
        ],
    }
    set_value("agent_onboarding_lmstudio_reference", payload)
    return payload


def safety():
    payload = {
        "ok": True,
        "mode": "onboarding_safety_profile",
        "generated_at": _now(),
        "profile": SAFETY_PROFILE,
        "plain_rules": [
            "Не запускаем cmd/powershell/shell из чата.",
            "Не используем режим администратора для агента.",
            "Не подтверждаем все команды подряд.",
            "Не даём агенту пароли, токены, SSH-ключи.",
            "Не удаляем файлы; при необходимости только quarantine.",
            "Любые изменения проекта идут через patch + tests + rollback.",
        ],
    }
    set_value("agent_onboarding_safety", payload)
    return payload


def generate_agents_md():
    _ensure_dirs()
    _write_text(QUICKSTART_AGENTS_FILE, LOCALCOMET_QUICKSTART_AGENTS_MD)
    payload = {
        "ok": True,
        "mode": "quickstart_agents_md",
        "generated_at": _now(),
        "path": str(QUICKSTART_AGENTS_FILE),
        "note": "Draft only. Review before copying anywhere else.",
        "safe": True,
    }
    set_value("agent_onboarding_agents_md", payload)
    return payload


def demo_site_plan():
    payload = {
        "ok": True,
        "mode": "demo_site_plan",
        "generated_at": _now(),
        "goal": "Create a simple one-page demo site in a safe workspace.",
        "steps": [
            {
                "type": "safety",
                "title": "No shell, no admin terminal, no auto-server.",
                "status": "required",
            },
            {
                "type": "workspace",
                "title": "Use Projects/PCAgent/DemoWorkspace/demo-site.",
                "status": "ready",
            },
            {
                "type": "files",
                "title": "Draft index.html, styles.css, README.md.",
                "status": "dry-run available",
            },
            {
                "type": "review",
                "title": "User reviews files manually or requests response.json patch.",
                "status": "required",
            },
            {
                "type": "serve",
                "title": "Local server is not started automatically.",
                "status": "manual only",
            },
        ],
        "next": "pc demo site dry",
    }
    set_value("agent_demo_site_plan", payload)
    return payload


def demo_site_dry():
    payload = {
        "ok": True,
        "mode": "demo_site_dry_run",
        "generated_at": _now(),
        "would_create": [
            str(DEMO_SITE_DIR / "index.html"),
            str(DEMO_SITE_DIR / "styles.css"),
            str(DEMO_SITE_DIR / "README.md"),
        ],
        "would_not_execute": [
            "npm",
            "python -m http.server",
            "cmd",
            "powershell",
            "browser auto-open",
            "admin terminal",
        ],
        "next": "pc demo site request",
    }
    set_value("agent_demo_site_dry", payload)
    return payload


def demo_site_request():
    _ensure_dirs()
    content = f"""# Demo Site Request

Generated: {_now()}

## Goal

Create a simple one-page website in a safe LocalComet demo workspace.

## Safety

- No shell commands.
- No admin terminal.
- No automatic server start.
- No browser auto-open.
- No secrets.
- Files are created only inside:

```text
{DEMO_SITE_DIR}
```

## Planned files

```text
index.html
styles.css
README.md
```

## Next safe command

```text
pc demo site files
```

This creates draft files only. It does not execute a server.
"""
    _write_text(DEMO_REQUEST_FILE, content)
    payload = {
        "ok": True,
        "mode": "demo_site_request",
        "generated_at": _now(),
        "path": str(DEMO_REQUEST_FILE),
        "next": "pc demo site files",
    }
    set_value("agent_demo_site_request", payload)
    return payload


def demo_site_files():
    _ensure_dirs()
    _write_text(DEMO_SITE_DIR / "index.html", DEMO_INDEX_HTML)
    _write_text(DEMO_SITE_DIR / "styles.css", DEMO_STYLES_CSS)
    _write_text(DEMO_SITE_DIR / "README.md", DEMO_README)

    payload = {
        "ok": True,
        "mode": "demo_site_files_created",
        "generated_at": _now(),
        "folder": str(DEMO_SITE_DIR),
        "files": [
            str(DEMO_SITE_DIR / "index.html"),
            str(DEMO_SITE_DIR / "styles.css"),
            str(DEMO_SITE_DIR / "README.md"),
        ],
        "executed_shell": False,
        "server_started": False,
        "browser_opened": False,
        "note": "Open index.html manually or request a deployment/patch workflow.",
    }
    set_value("agent_onboarding_last_demo", payload)
    return payload


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "explain": explain(),
        "checklist": checklist(),
        "localcomet": localcomet(),
        "safety": safety(),
        "qwen_reference": qwen_reference(),
        "lmstudio_reference": lmstudio_reference(),
        "demo_plan": demo_site_plan(),
        "last_demo": get_value("agent_onboarding_last_demo", ""),
    }

    json_path = REPORTS_DIR / f"agent_onboarding_demo_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"agent_onboarding_demo_report_{_stamp()}.md"
    _write_json(json_path, payload)

    md = [
        "# Agent Onboarding + Demo Workspace Report",
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
        "## Agent Formula",
        "",
    ]

    for key, item in AGENT_FORMULA.items():
        md.extend([
            f"### {key}",
            "",
            f"- Plain: {item['plain']}",
            f"- LocalComet: {item['localcomet']}",
            "",
        ])

    md.extend([
        "## Safety Profile",
        "",
        "```json",
        json.dumps(SAFETY_PROFILE, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Demo Site Plan",
        "",
        "```json",
        json.dumps(payload["demo_plan"], ensure_ascii=False, indent=2),
        "```",
    ])

    _write_text(md_path, "\n".join(md))
    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc onboard", "pc onboard status", "pc onboard статус", "onboard status"}:
        return format_status(status())

    if lower in {"pc onboard explain", "pc onboard объясни", "pc onboard что такое агент", "onboard explain"}:
        return format_payload(explain())

    if lower in {"pc onboard checklist", "pc onboard чеклист", "onboard checklist"}:
        return format_payload(checklist())

    if lower in {"pc onboard localcomet", "pc onboard local", "onboard localcomet"}:
        return format_payload(localcomet())

    if lower in {"pc onboard qwen", "pc onboard qwen cli", "onboard qwen"}:
        return format_payload(qwen_reference())

    if lower in {"pc onboard lmstudio", "pc onboard lm studio", "onboard lmstudio"}:
        return format_payload(lmstudio_reference())

    if lower in {"pc onboard safety", "pc onboard безопасность", "onboard safety"}:
        return format_payload(safety())

    if lower in {"pc onboard agents.md", "pc onboard agents", "onboard agents.md"}:
        return format_payload(generate_agents_md())

    if lower in {"pc onboard report", "pc onboard отчет", "pc onboard отчёт", "onboard report"}:
        return format_payload(report("manual report"))

    if lower in {"pc demo site plan", "pc demo план сайта", "demo site plan"}:
        return format_payload(demo_site_plan())

    if lower in {"pc demo site dry", "pc demo сайт dry", "demo site dry"}:
        return format_payload(demo_site_dry())

    if lower in {"pc demo site request", "pc demo request", "pc demo сайт request", "demo site request"}:
        return format_payload(demo_site_request())

    if lower in {"pc demo site files", "pc demo site create", "pc demo сайт файлы", "demo site files"}:
        return format_payload(demo_site_files())

    if lower in {"pc demo site report", "pc demo сайт отчет", "pc demo сайт отчёт", "demo site report"}:
        return format_payload(report("demo site report"))

    return format_payload({
        "ok": False,
        "error": "Unknown onboarding/demo command.",
        "help": status().get("commands", []),
    })


def is_onboarding_command(command):
    lower = _norm(command)
    exact = {
        "pc onboard",
        "pc onboard status",
        "pc onboard статус",
        "onboard status",
        "pc onboard explain",
        "pc onboard объясни",
        "pc onboard что такое агент",
        "onboard explain",
        "pc onboard checklist",
        "pc onboard чеклист",
        "onboard checklist",
        "pc onboard localcomet",
        "pc onboard local",
        "onboard localcomet",
        "pc onboard qwen",
        "pc onboard qwen cli",
        "onboard qwen",
        "pc onboard lmstudio",
        "pc onboard lm studio",
        "onboard lmstudio",
        "pc onboard safety",
        "pc onboard безопасность",
        "onboard safety",
        "pc onboard agents.md",
        "pc onboard agents",
        "onboard agents.md",
        "pc onboard report",
        "pc onboard отчет",
        "pc onboard отчёт",
        "onboard report",
        "pc demo site plan",
        "pc demo план сайта",
        "demo site plan",
        "pc demo site dry",
        "pc demo сайт dry",
        "demo site dry",
        "pc demo site request",
        "pc demo request",
        "pc demo сайт request",
        "demo site request",
        "pc demo site files",
        "pc demo site create",
        "pc demo сайт файлы",
        "demo site files",
        "pc demo site report",
        "pc demo сайт отчет",
        "pc demo сайт отчёт",
        "demo site report",
    }
    return lower in exact
