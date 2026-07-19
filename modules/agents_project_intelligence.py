from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import re
import hashlib


from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
AGENTS_DIR = PROJECTS_DIR / "PCAgent" / "AgentsMD"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "agents_project_intelligence"

STANDARD_AGENTS_DRAFT = AGENTS_DIR / "AGENTS_LocalComet_STANDARD.md"
PROJECT_PROFILE_FILE = AGENTS_DIR / "project_profile.json"
VALIDATION_FILE = AGENTS_DIR / "last_agents_validation.json"

AGENTS_FILENAMES = [
    "AGENTS.md",
    "agents.md",
    ".agents.md",
    "AGENT.md",
    "agent.md",
]

FORBIDDEN_TERMS = [
    "execute all commands",
    "run all commands",
    "auto approve all",
    "auto-approve all",
    "always yes",
    "always approve",
    "sudo",
    "run as administrator",
    "administrator",
    "powershell",
    "cmd.exe",
    "rm -rf",
    "rmdir",
    "del /f",
    "format",
    "wipe",
    "delete all",
    "delete files",
    "ssh key",
    "private key",
    "api key",
    "token",
    "password",
    "secret",
    "seed phrase",
    "send credentials",
    "deploy with ssh",
    "ignore safety",
    "ignore previous instructions",
    "bypass",
    "jailbreak",
]

RISKY_COMMAND_PATTERNS = [
    r"\bnpm\s+run\s+build\b",
    r"\bsudo\b",
    r"\bpowershell\b",
    r"\bcmd\s*/c\b",
    r"\brm\s+-rf\b",
    r"\brmdir\b",
    r"\bdel\s+/[fsq]\b",
    r"\bformat\b",
    r"\bssh\b",
    r"\bscp\b",
    r"\bchmod\s+777\b",
    r"\bpip\s+install\b",
    r"\bnpm\s+install\b",
    r"\bpnpm\s+install\b",
    r"\byarn\s+install\b",
]

SAFE_TEST_COMMAND_HINTS = [
    "python -m py_compile",
    "python -m pytest",
    "pytest",
    "npm run lint",
    "npm test",
    "pnpm lint",
    "pnpm test",
    "yarn lint",
    "yarn test",
]

PROJECT_MARKERS = {
    "python": ["pyproject.toml", "requirements.txt", "setup.py", "pytest.ini", "tox.ini"],
    "node": ["package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"],
    "nextjs": ["next.config.js", "next.config.mjs", "next.config.ts"],
    "vite": ["vite.config.js", "vite.config.ts", "vite.config.mjs"],
    "localcomet": ["LocalComet_Control_Panel.py", "Projects", "modules", "core"],
}


STANDARD_AGENTS_CONTENT = """# AGENTS.md — LocalComet Project Contract

This file is a predictable project contract for AI agents working inside this repository.

## Agent Identity

You are LocalComet, a local safety-first AI agent. You can help inspect, plan, draft, test, and patch the project, but you must never bypass safety gates.

## Core Workflow

```text
1. Read this AGENTS.md first.
2. Understand the user goal.
3. Run semantic firewall for risky tasks.
4. Inspect project context.
5. Build a plan.
6. Use dry-run before execution.
7. Require explicit confirmation for desktop or high-risk actions.
8. Modify project only through response.json patch workflow.
9. Run safe tests.
10. Save a report.
```

## Safe Project Editing

Allowed:

```text
- Read project files.
- Explain files and project structure.
- Generate request.md / response.json patches.
- Run py_compile for touched Python files.
- Run project-specific safe tests when listed below.
- Create reports in Projects/Reports/.
```

Denied:

```text
- Arbitrary shell/cmd/powershell.
- Delete/format/wipe/rm/rmdir.
- Direct editing of protected files without patch workflow.
- Secrets, passwords, tokens, SSH keys, API keys.
- Auto-approve all commands.
- Running installers or dependency changes without explicit plan.
```

## LocalComet Safe Commands

```text
python -m py_compile <file.py>
pc agentos firewall <intent>
pc agents validate
pc agents project-profile
pc screen plan <goal>
pc exec dry <goal>
pc exec run подтверждаю: <goal>
```

## Project Patch Rule

All code changes must go through:

```text
response.json -> validate -> apply -> tests -> after patch -> auto verification
```

## Forbidden Command Examples

```text
powershell
cmd /c
rm -rf
rmdir
del /f
format
ssh with secrets
npm install without review
pip install without review
auto yes to unknown commands
```

## Reports

Write reports under:

```text
Projects/Reports/
```

## Memory

Use:

```text
Projects/PCAgent/
Projects/Reports/
Patch Registry
SelfEdit rollback
```
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е")


def _ensure_dirs():
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _safe_read_text(path, max_chars=120000):
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            return text[:max_chars] + "\n\n[TRUNCATED]"
        return text
    except Exception as exc:
        return f"[READ_ERROR] {exc}"


def _hash_text(text):
    return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _is_within_root(path):
    try:
        Path(path).resolve().relative_to(ROOT_DIR.resolve())
        return True
    except Exception:
        return False


def find_agents_files():
    candidates = []

    for name in AGENTS_FILENAMES:
        path = ROOT_DIR / name
        if path.exists() and path.is_file():
            candidates.append(path)

    for base in [
        PROJECTS_DIR / "PCAgent" / "Onboarding",
        PROJECTS_DIR / "PCAgent" / "AgentOS",
        AGENTS_DIR,
    ]:
        if base.exists():
            for path in base.rglob("*.md"):
                if "agents" in path.name.lower() or path.name.lower() == "agents.md":
                    candidates.append(path)

    unique = []
    seen = set()
    for path in candidates:
        key = str(path.resolve()).lower()
        if key not in seen and _is_within_root(path):
            seen.add(key)
            unique.append(path)

    return unique


def project_markers():
    markers = {}
    for kind, names in PROJECT_MARKERS.items():
        found = []
        for name in names:
            path = ROOT_DIR / name
            if path.exists():
                found.append(str(path))
        markers[kind] = found
    return markers


def infer_project_type():
    markers = project_markers()
    detected = []

    if markers.get("localcomet") and len(markers.get("localcomet", [])) >= 2:
        detected.append("localcomet")
    if markers.get("python"):
        detected.append("python")
    if markers.get("nextjs"):
        detected.append("nextjs")
    if markers.get("vite"):
        detected.append("vite")
    if markers.get("node"):
        detected.append("node")

    if not detected:
        detected.append("unknown")

    return detected


def safe_command_profile(project_types=None):
    project_types = project_types or infer_project_type()
    safe = [
        "python -m py_compile <touched_file.py>",
        "pc agentos firewall <intent>",
        "pc agents validate",
        "pc agents project-profile",
    ]
    caution = [
        "python -m pytest",
        "pytest",
    ]
    forbidden = [
        "powershell",
        "cmd /c",
        "rm -rf",
        "rmdir",
        "del /f",
        "format",
        "ssh/scp with secrets",
        "npm install without explicit plan",
        "pip install without explicit plan",
        "auto-approve all commands",
    ]

    if "node" in project_types or "nextjs" in project_types or "vite" in project_types:
        safe.extend(["npm run lint", "npm test"])
        caution.extend(["npm run dev"])
        forbidden.append("npm run build inside interactive agent session unless explicitly requested")

    if "localcomet" in project_types:
        safe.extend([
            "python -m py_compile LocalComet_Control_Panel.py",
            "python -m py_compile modules/<changed_module>.py",
            "Auto Verification full",
            "Full Stability Test",
        ])

    return {
        "safe": sorted(set(safe)),
        "caution": sorted(set(caution)),
        "forbidden": sorted(set(forbidden)),
    }


def detect_project():
    _ensure_dirs()
    agents_files = find_agents_files()
    project_types = infer_project_type()
    profile = {
        "ok": True,
        "mode": "agents_project_detection",
        "generated_at": _now(),
        "root": str(ROOT_DIR),
        "project_types": project_types,
        "markers": project_markers(),
        "agents_files": [
            {
                "path": str(path),
                "name": path.name,
                "size": path.stat().st_size,
                "sha16": _hash_text(_safe_read_text(path, 200000)),
            }
            for path in agents_files
        ],
        "has_root_agents_md": any(path.name == "AGENTS.md" and path.parent == ROOT_DIR for path in agents_files),
        "safe_command_profile": safe_command_profile(project_types),
    }
    _write_json(PROJECT_PROFILE_FILE, profile)
    set_value("agents_project_profile", profile)
    return profile


def read_agents():
    agents_files = find_agents_files()
    payload = {
        "ok": True,
        "mode": "agents_md_read",
        "generated_at": _now(),
        "files": [],
    }

    for path in agents_files:
        text = _safe_read_text(path)
        payload["files"].append({
            "path": str(path),
            "name": path.name,
            "sha16": _hash_text(text),
            "chars": len(text),
            "content": text,
        })

    if not payload["files"]:
        payload["ok"] = False
        payload["message"] = "No AGENTS.md-like files found. Use: pc agents generate"

    set_value("agents_md_last_read", payload)
    return payload


def _validate_text(text, source="manual"):
    lower = _norm(text)
    forbidden_hits = sorted({term for term in FORBIDDEN_TERMS if term in lower})
    risky_commands = []

    for pattern in RISKY_COMMAND_PATTERNS:
        if re.search(pattern, lower):
            risky_commands.append(pattern)

    required_sections = {
        "workflow": any(word in lower for word in ["workflow", "pipeline", "core workflow", "рабочий процесс", "алгоритм"]),
        "testing": any(word in lower for word in ["test", "testing", "py_compile", "pytest", "lint", "провер"]),
        "forbidden": any(word in lower for word in ["forbidden", "denied", "нельзя", "запрещ"]),
        "safety": any(word in lower for word in ["safety", "security", "безопас"]),
    }

    score = 100
    score -= len(forbidden_hits) * 8
    score -= len(risky_commands) * 6
    score -= len([ok for ok in required_sections.values() if not ok]) * 10
    score = max(0, min(100, score))

    verdict = "good"
    if forbidden_hits or risky_commands:
        verdict = "needs_review"
    if any(hit in forbidden_hits for hit in ["execute all commands", "auto approve all", "always yes", "password", "token", "private key", "ssh key"]):
        verdict = "unsafe"

    return {
        "source": source,
        "sha16": _hash_text(text),
        "chars": len(text),
        "score": score,
        "verdict": verdict,
        "forbidden_hits": forbidden_hits,
        "risky_command_patterns": sorted(set(risky_commands)),
        "required_sections": required_sections,
        "recommendations": _recommendations(forbidden_hits, risky_commands, required_sections),
    }


def _recommendations(forbidden_hits, risky_commands, required_sections):
    recs = []

    if forbidden_hits:
        recs.append("Remove or rewrite dangerous auto-approval/secret/delete/admin instructions.")
    if risky_commands:
        recs.append("Move risky commands to explicit-review section or forbid them in agent sessions.")
    if not required_sections.get("workflow"):
        recs.append("Add a clear workflow: read -> plan -> dry-run -> confirm -> patch/test/report.")
    if not required_sections.get("testing"):
        recs.append("Add safe testing instructions.")
    if not required_sections.get("forbidden"):
        recs.append("Add forbidden commands and denied actions.")
    if not required_sections.get("safety"):
        recs.append("Add a safety section.")
    if not recs:
        recs.append("AGENTS.md looks usable. Keep it project-specific and safety-first.")
    return recs


def validate_agents():
    _ensure_dirs()
    files_payload = read_agents()
    validations = []

    for item in files_payload.get("files", []):
        validations.append(_validate_text(item.get("content", ""), item.get("path", "unknown")))

    if not validations:
        standard = STANDARD_AGENTS_CONTENT
        validations.append(_validate_text(standard, "generated_standard"))

    payload = {
        "ok": True,
        "mode": "agents_md_validation",
        "generated_at": _now(),
        "validations": validations,
        "overall_verdict": _overall_verdict(validations),
    }

    _write_json(VALIDATION_FILE, payload)
    set_value("agents_md_validation", payload)
    return payload


def _overall_verdict(validations):
    verdicts = [item.get("verdict") for item in validations]
    if "unsafe" in verdicts:
        return "unsafe"
    if "needs_review" in verdicts:
        return "needs_review"
    return "good"


def generate_agents():
    _ensure_dirs()
    STANDARD_AGENTS_DRAFT.write_text(STANDARD_AGENTS_CONTENT, encoding="utf-8")
    validation = _validate_text(STANDARD_AGENTS_CONTENT, str(STANDARD_AGENTS_DRAFT))
    payload = {
        "ok": True,
        "mode": "agents_md_generate",
        "generated_at": _now(),
        "path": str(STANDARD_AGENTS_DRAFT),
        "note": "Draft only. Review before copying to project root.",
        "validation": validation,
    }
    set_value("agents_md_generated", payload)
    return payload


def project_profile():
    detection = detect_project()
    validation = validate_agents()
    payload = {
        "ok": True,
        "mode": "agents_project_profile",
        "generated_at": _now(),
        "detection": detection,
        "agents_validation": validation,
        "recommended_policy": {
            "read_agents_md_first": True,
            "apply_to_pc_edit": True,
            "apply_to_patch_generation": True,
            "project_changes_via_response_json": True,
            "unsafe_agents_md_blocks_execution": True,
        },
    }
    set_value("agents_project_profile_full", payload)
    return payload


def rules():
    return {
        "ok": True,
        "mode": "agents_md_rules",
        "generated_at": _now(),
        "standard_sections": [
            "Agent Identity",
            "Core Workflow",
            "Safe Project Editing",
            "Allowed Actions",
            "Denied Actions",
            "Safe Commands",
            "Forbidden Commands",
            "Patch Rule",
            "Reports",
            "Memory",
        ],
        "safety_rules": [
            "AGENTS.md cannot override LocalComet safety.",
            "AGENTS.md can narrow permissions but cannot expand them.",
            "Dangerous instructions are marked unsafe.",
            "Project edits remain response.json patch workflow only.",
            "No secrets/tokens/passwords/SSH keys.",
        ],
        "safe_command_profile": safe_command_profile(),
    }


def status():
    detection = detect_project()
    payload = {
        "ok": True,
        "mode": "agents_project_intelligence",
        "generated_at": _now(),
        "root": str(ROOT_DIR),
        "project_types": detection.get("project_types", []),
        "agents_files_count": len(detection.get("agents_files", [])),
        "has_root_agents_md": detection.get("has_root_agents_md", False),
        "last_validation": get_value("agents_md_validation", ""),
        "commands": [
            "pc agents status",
            "pc agents detect",
            "pc agents read",
            "pc agents generate",
            "pc agents validate",
            "pc agents project-profile",
            "pc agents rules",
            "pc agents report",
        ],
    }
    set_value("agents_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    lines = [
        "AGENTS.md Project Intelligence:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- root: {payload.get('root')}",
        f"- project_types: {', '.join(payload.get('project_types', []))}",
        f"- agents_files_count: {payload.get('agents_files_count')}",
        f"- has_root_agents_md: {payload.get('has_root_agents_md')}",
        "",
        "Commands:",
    ]
    lines.extend("- " + command for command in payload.get("commands", []))
    return "\n".join(lines)


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "detection": detect_project(),
        "read": read_agents(),
        "validation": validate_agents(),
        "profile": project_profile(),
        "rules": rules(),
    }

    json_path = REPORTS_DIR / f"agents_project_intelligence_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"agents_project_intelligence_report_{_stamp()}.md"
    _write_json(json_path, payload)

    md = [
        "# AGENTS.md Project Intelligence Report",
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
        "## Project Types",
        "",
        "```json",
        json.dumps(payload["detection"].get("project_types", []), ensure_ascii=False, indent=2),
        "```",
        "",
        "## AGENTS.md Validation",
        "",
        "```json",
        json.dumps(payload["validation"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Safe Command Profile",
        "",
        "```json",
        json.dumps(payload["rules"]["safe_command_profile"], ensure_ascii=False, indent=2),
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
    lower = _norm(text).strip()

    if lower in {"pc agents", "pc agents status", "pc agents статус", "agents status"}:
        return format_status(status())

    if lower in {"pc agents detect", "pc agents найти", "pc agents поиск", "agents detect"}:
        return format_payload(detect_project())

    if lower in {"pc agents read", "pc agents читать", "agents read"}:
        return format_payload(read_agents())

    if lower in {"pc agents generate", "pc agents создать", "pc agents draft", "agents generate"}:
        return format_payload(generate_agents())

    if lower in {"pc agents validate", "pc agents проверка", "pc agents проверить", "agents validate"}:
        return format_payload(validate_agents())

    if lower in {"pc agents project-profile", "pc agents profile", "pc agents профиль", "agents profile"}:
        return format_payload(project_profile())

    if lower in {"pc agents rules", "pc agents правила", "agents rules"}:
        return format_payload(rules())

    if lower in {"pc agents report", "pc agents отчет", "pc agents отчёт", "agents report"}:
        return format_payload(report("manual report"))

    return format_payload({
        "ok": False,
        "error": "Unknown AGENTS.md Project Intelligence command.",
        "help": status().get("commands", []),
    })


def is_agents_command(command):
    lower = _norm(command).strip()
    exact = {
        "pc agents",
        "pc agents status",
        "pc agents статус",
        "agents status",
        "pc agents detect",
        "pc agents найти",
        "pc agents поиск",
        "agents detect",
        "pc agents read",
        "pc agents читать",
        "agents read",
        "pc agents generate",
        "pc agents создать",
        "pc agents draft",
        "agents generate",
        "pc agents validate",
        "pc agents проверка",
        "pc agents проверить",
        "agents validate",
        "pc agents project-profile",
        "pc agents profile",
        "pc agents профиль",
        "agents profile",
        "pc agents rules",
        "pc agents правила",
        "agents rules",
        "pc agents report",
        "pc agents отчет",
        "pc agents отчёт",
        "agents report",
    }
    return lower in exact
