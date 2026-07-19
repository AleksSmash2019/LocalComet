from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import re
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
