from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from modules.project_paths import get_project_root
from urllib.parse import quote_plus, urlparse
import html
import json
import re
import traceback
import urllib.request

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
RELAY_DIR = PROJECTS_DIR / "ChatGPTRelay"
REPORTS_DIR = PROJECTS_DIR / "Reports"
KNOWLEDGE_REPORTS_DIR = REPORTS_DIR / "pc_agent_knowledge"
REQUEST_FILE = RELAY_DIR / "request.md"

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "BrowserProfile",
    "VoiceModels",
    "LocalAgent_Backups",
    "CleanupQuarantine",
}
EXCLUDED_PARTS = {
    "Projects/Reports",
    "Projects/Logs",
    "Projects/CleanupQuarantine",
}
IMPORTANT_FILES = [
    "LocalComet_Control_Panel.py",
    "agent.py",
    "config.py",
    "core/router.py",
    "core/planner.py",
    "core/executor.py",
    "core/llm.py",
    "modules/pc_agent_core.py",
    "modules/pc_codex_mode.py",
    "modules/pc_agent_actions.py",
    "modules/safety_cleanup_center.py",
    "modules/global_update_center.py",
    "modules/desktop_observer.py",
    "modules/desktop_action_planner.py",
    "modules/self_edit.py",
]

SENSITIVE_PATTERNS = [
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    ".env",
    ".pem",
    ".key",
]


class _DuckResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._in_a = False
        self._current_href = ""
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return

        attrs_dict = dict(attrs)
        href = attrs_dict.get("href", "")
        css = attrs_dict.get("class", "")

        if "result-link" in css or "/l/?" in href or href.startswith("http"):
            self._in_a = True
            self._current_href = href
            self._current_text = []

    def handle_data(self, data):
        if self._in_a:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or not self._in_a:
            return

        title = " ".join(" ".join(self._current_text).split())
        href = self._clean_href(self._current_href)

        if title and href and len(title) > 2:
            self.results.append({"title": html.unescape(title), "url": href, "snippet": ""})

        self._in_a = False
        self._current_href = ""
        self._current_text = []

    def _clean_href(self, href):
        if not href:
            return ""

        value = html.unescape(href)

        if value.startswith("//"):
            return "https:" + value

        if value.startswith("/l/?"):
            try:
                from urllib.parse import parse_qs, urlparse, unquote

                query = parse_qs(urlparse(value).query)
                uddg = query.get("uddg", [""])[0]
                return unquote(uddg)
            except Exception:
                return value

        if value.startswith("http://") or value.startswith("https://"):
            return value

        return ""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _is_sensitive_path(path: Path):
    lower = str(path).lower().replace("\\", "/")
    return any(pattern in lower for pattern in SENSITIVE_PATTERNS)


def _is_excluded(path: Path):
    parts = set(path.parts)
    if parts.intersection(EXCLUDED_DIRS):
        return True

    rel = ""
    try:
        rel = path.relative_to(ROOT_DIR).as_posix()
    except Exception:
        rel = path.as_posix()

    return any(rel.startswith(part) for part in EXCLUDED_PARTS)


def _safe_read_text(path: Path, limit=9000):
    if _is_sensitive_path(path):
        return "[SKIPPED: sensitive path]"

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"[READ ERROR: {exc}]"

    if len(text) > limit:
        return text[:limit] + "\n...[обрезано]"
    return text


def build_project_structure(max_files=260):
    files = []
    counts = {
        "total": 0,
        "python": 0,
        "markdown": 0,
        "json": 0,
        "html": 0,
    }

    if not ROOT_DIR.exists():
        return {
            "ok": False,
            "root": str(ROOT_DIR),
            "error": "ROOT_DIR does not exist.",
            "counts": counts,
            "files": [],
        }

    for path in ROOT_DIR.rglob("*"):
        if _is_excluded(path):
            continue
        if path.is_dir():
            continue
        if _is_sensitive_path(path):
            continue

        counts["total"] += 1
        suffix = path.suffix.lower()

        if suffix == ".py":
            counts["python"] += 1
        elif suffix in {".md", ".txt"}:
            counts["markdown"] += 1
        elif suffix == ".json":
            counts["json"] += 1
        elif suffix in {".html", ".htm"}:
            counts["html"] += 1

        if len(files) < max_files:
            try:
                rel = path.relative_to(ROOT_DIR).as_posix()
            except Exception:
                rel = str(path)
            files.append(rel)

    return {
        "ok": True,
        "root": str(ROOT_DIR),
        "generated_at": _now(),
        "counts": counts,
        "files": files,
        "truncated": counts["total"] > len(files),
    }


def build_project_context(include_contents=True):
    structure = build_project_structure()
    important = []

    for rel in IMPORTANT_FILES:
        path = ROOT_DIR / rel
        if not path.exists() or not path.is_file():
            important.append({"path": rel, "exists": False, "preview": ""})
            continue

        preview = _safe_read_text(path, limit=5000 if include_contents else 800)
        important.append({
            "path": rel,
            "exists": True,
            "preview": preview,
        })

    payload = {
        "ok": True,
        "generated_at": _now(),
        "project": "LocalComet / LocalAgent",
        "root": str(ROOT_DIR),
        "structure": structure,
        "important_files": important,
        "safety_rules": [
            "Do not edit private credentials, tokens, passwords, browser profiles, VoiceModels, .git, backups, Reports, or Logs.",
            "Use response.json patch workflow for changes.",
            "Prefer modules over expanding LocalComet_Control_Panel.py.",
            "Never use shell=True for unknown commands.",
            "Use quarantine instead of direct deletion.",
        ],
    }
    set_value("pc_agent_project_context", payload)
    return payload


def format_project_structure(payload=None):
    payload = payload or build_project_structure()
    lines = [
        "Project Structure:",
        f"- ok: {payload.get('ok')}",
        f"- root: {payload.get('root')}",
    ]

    counts = payload.get("counts", {})
    lines.extend([
        "",
        "Counts:",
        f"- total: {counts.get('total')}",
        f"- python: {counts.get('python')}",
        f"- markdown/txt: {counts.get('markdown')}",
        f"- json: {counts.get('json')}",
        f"- html: {counts.get('html')}",
        "",
        "Files:",
    ])

    for item in payload.get("files", [])[:180]:
        lines.append("- " + item)

    if payload.get("truncated"):
        lines.append("...[список обрезан]")

    return "\n".join(lines)


def format_project_context(payload=None):
    payload = payload or build_project_context(include_contents=False)
    lines = [
        "Project Context for Qwen / PC Agent:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- root: {payload.get('root')}",
        "",
        "Safety rules:",
    ]
    lines.extend("- " + item for item in payload.get("safety_rules", []))
    lines.append("")
    lines.append(format_project_structure(payload.get("structure", {})))
    lines.append("")
    lines.append("Important files:")
    for item in payload.get("important_files", []):
        lines.append(f"- {item.get('path')} exists={item.get('exists')}")
    return "\n".join(lines)


def search_web(query, max_results=6, timeout=12):
    query = str(query or "").strip()
    if not query:
        return {"ok": False, "query": query, "results": [], "error": "empty query"}

    url = "https://duckduckgo.com/html/?q=" + quote_plus(query)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 LocalComet/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            html_text = response.read(900000).decode("utf-8", errors="replace")
    except Exception as exc:
        fallback = "https://www.google.com/search?q=" + quote_plus(query)
        return {
            "ok": False,
            "query": query,
            "results": [],
            "error": str(exc),
            "fallback_url": fallback,
        }

    parser = _DuckResultParser()
    parser.feed(html_text)

    seen = set()
    results = []
    for item in parser.results:
        host = ""
        try:
            host = urlparse(item.get("url", "")).netloc
        except Exception:
            host = ""

        key = (item.get("title", ""), item.get("url", ""))
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "host": host,
            "snippet": item.get("snippet", ""),
        })

        if len(results) >= max_results:
            break

    return {
        "ok": True,
        "query": query,
        "generated_at": _now(),
        "results": results,
        "source": "duckduckgo_html",
    }


def format_search_recommendation(payload):
    query = payload.get("query", "")
    results = payload.get("results", [])

    lines = [
        "Internet Research:",
        f"- query: {query}",
        f"- ok: {payload.get('ok')}",
    ]

    if not payload.get("ok"):
        lines.append(f"- error: {payload.get('error')}")
        if payload.get("fallback_url"):
            lines.append(f"- fallback_url: {payload.get('fallback_url')}")
        lines.append("")
        lines.append("Рекомендация: интернет-поиск не сработал из Python. Открой fallback_url вручную или проверь доступ к сети.")
        return "\n".join(lines)

    if not results:
        lines.append("")
        lines.append("Результатов не найдено.")
        lines.append("Рекомендация: уточни запрос или попроси: pc web <более конкретный запрос>.")
        return "\n".join(lines)

    lines.append("")
    lines.append("Top results:")
    for index, item in enumerate(results, start=1):
        lines.append(f"{index}. {item.get('title')}")
        lines.append(f"   host: {item.get('host')}")
        lines.append(f"   url: {item.get('url')}")

    lines.append("")
    lines.append("Рекомендация:")
    lines.append("- Используй первые 2-3 результата как ориентир, но не выполняй опасные действия автоматически.")
    lines.append("- Если запрос про LocalComet, сначала сравни с Project Context.")
    lines.append("- Для изменения проекта используй: pc edit <что изменить>.")

    return "\n".join(lines)


def should_search_online(command):
    lower = _norm(command)
    triggers = [
        "найди",
        "поиск",
        "загугли",
        "интернет",
        "web",
        "google",
        "что такое",
        "как сделать",
        "почему",
        "ошибка",
        "документация",
        "latest",
        "новый",
        "актуальный",
        "не знаю",
    ]
    return any(trigger in lower for trigger in triggers)


def answer_unknown_command(command):
    command = str(command or "").strip()

    if not command:
        return "Пустая команда."

    project_context = build_project_context(include_contents=False)
    search_payload = search_web(command, max_results=5)

    report = {
        "ok": True,
        "mode": "unknown_command_research",
        "generated_at": _now(),
        "command": command,
        "project_context": {
            "root": project_context.get("root"),
            "counts": project_context.get("structure", {}).get("counts", {}),
            "important_files": [item.get("path") for item in project_context.get("important_files", []) if item.get("exists")],
        },
        "search": search_payload,
    }
    set_value("pc_agent_last_unknown_research", report)

    lines = [
        "Я не распознал это как готовую команду LocalComet, поэтому сделал research.",
        "",
        format_search_recommendation(search_payload),
        "",
        "Project awareness:",
        f"- root: {project_context.get('root')}",
        f"- python files: {project_context.get('structure', {}).get('counts', {}).get('python')}",
        f"- known modules: {', '.join(report['project_context']['important_files'][:12])}",
        "",
        "Что можно сделать дальше:",
        "- Если это вопрос: уточни, и я отвечу с учётом web results.",
        "- Если это изменение проекта: напиши `pc edit <что изменить>`.",
        "- Если это управление ПК: `pc codex план <цель>` → `pc codex dry <цель>` → `pc codex step подтверждаю: <цель>`.",
    ]
    return "\n".join(lines)


def create_project_edit_request(task):
    task = str(task or "").strip()
    if not task:
        return {"ok": False, "error": "empty task"}

    context = build_project_context(include_contents=True)

    RELAY_DIR.mkdir(parents=True, exist_ok=True)

    body = [
        "# LocalComet Project Edit Request",
        "",
        f"Generated: {_now()}",
        "",
        "## Task",
        "",
        task,
        "",
        "## Required output",
        "",
        "Return a response.json patch only.",
        "Use operations with type/create/replace.",
        "Do not use placeholders.",
        "Do not edit secrets, browser profile, .git, reports, logs, backups, VoiceModels, or private files.",
        "Prefer adding new modules over expanding LocalComet_Control_Panel.py.",
        "Use quarantine instead of direct deletion.",
        "",
        "## Project Context",
        "",
        "```json",
        json.dumps(context, ensure_ascii=False, indent=2),
        "```",
    ]

    REQUEST_FILE.write_text("\n".join(body), encoding="utf-8")
    payload = {
        "ok": True,
        "request": str(REQUEST_FILE),
        "task": task,
        "message": "request.md создан с контекстом проекта. Дальше можно отправлять его в ChatGPT/Codex workflow.",
    }
    set_value("pc_agent_last_edit_request", payload)
    return payload


def save_knowledge_report(note=""):
    KNOWLEDGE_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "project_context": build_project_context(include_contents=False),
        "last_unknown_research": get_value("pc_agent_last_unknown_research", ""),
        "last_edit_request": get_value("pc_agent_last_edit_request", ""),
    }

    json_path = KNOWLEDGE_REPORTS_DIR / f"knowledge_report_{_stamp()}.json"
    md_path = KNOWLEDGE_REPORTS_DIR / f"knowledge_report_{_stamp()}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# PC Agent Knowledge Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Project Context",
        "",
        "```text",
        format_project_context(payload["project_context"]),
        "```",
        "",
        "## Last Unknown Research",
        "",
        "```json",
        json.dumps(payload["last_unknown_research"], ensure_ascii=False, indent=2),
        "```",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def dispatch_knowledge_command(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"project context", "контекст проекта", "структура проекта", "project structure"}:
        return format_project_context(build_project_context(include_contents=False))

    if lower in {"knowledge report", "отчет знаний", "knowledge status"}:
        return json.dumps(save_knowledge_report("manual knowledge report"), ensure_ascii=False, indent=2)

    prefixes = [
        "pc web ",
        "web search ",
        "internet search ",
        "поиск в интернете ",
        "найди в интернете ",
        "загугли ",
    ]

    for prefix in prefixes:
        if lower.startswith(prefix):
            query = text[len(prefix):].strip(" :,-—")
            return format_search_recommendation(search_web(query, max_results=6))

    edit_prefixes = [
        "pc edit ",
        "project edit ",
        "измени проект ",
        "поменяй в проекте ",
        "доработай проект ",
    ]

    for prefix in edit_prefixes:
        if lower.startswith(prefix):
            task = text[len(prefix):].strip(" :,-—")
            return json.dumps(create_project_edit_request(task), ensure_ascii=False, indent=2)

    return answer_unknown_command(text)


def is_knowledge_command(command):
    lower = _norm(command)

    exact = {
        "project context",
        "контекст проекта",
        "структура проекта",
        "project structure",
        "knowledge report",
        "отчет знаний",
        "knowledge status",
    }
    if lower in exact:
        return True

    prefixes = (
        "pc web ",
        "web search ",
        "internet search ",
        "поиск в интернете ",
        "найди в интернете ",
        "загугли ",
        "pc edit ",
        "project edit ",
        "измени проект ",
        "поменяй в проекте ",
        "доработай проект ",
    )
    return lower.startswith(prefixes)
