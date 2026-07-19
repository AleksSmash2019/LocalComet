from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import subprocess
import traceback

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
GLOBAL_UPDATE_REPORTS_DIR = REPORTS_DIR / "global_update_center"
PATCH_REGISTRY_FILE = PROJECTS_DIR / "PatchRegistry" / "patches.json"
RELAY_RESPONSE_FILE = PROJECTS_DIR / "ChatGPTRelay" / "response.json"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value, limit=2200):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[обрезано]"


def _safe_call(label, func):
    try:
        return {"ok": True, "label": label, "value": func(), "error": ""}
    except Exception:
        return {"ok": False, "label": label, "value": None, "error": traceback.format_exc()}


def _git_status_short():
    result = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=25,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _latest_file(folder: Path, patterns):
    if not folder.exists():
        return ""
    files = []
    for pattern in patterns:
        files.extend(folder.glob(pattern))
    files = [path for path in files if path.is_file()]
    if not files:
        return ""
    return str(max(files, key=lambda path: path.stat().st_mtime))


def _patch_registry_status():
    if not PATCH_REGISTRY_FILE.exists():
        return {"exists": False, "count": 0, "latest": None}

    try:
        data = json.loads(PATCH_REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"exists": True, "count": 0, "latest": None, "error": str(exc)}

    patches = data if isinstance(data, list) else data.get("patches", []) if isinstance(data, dict) else []
    return {
        "exists": True,
        "count": len(patches),
        "latest": patches[-1] if patches else None,
    }


def _voice_status():
    try:
        from modules.voice_control import get_voice_status
        return get_voice_status()
    except Exception:
        return {"error": traceback.format_exc()}


def _pc_agent_health():
    try:
        from modules.pc_agent_core import pc_agent_health_snapshot
        return pc_agent_health_snapshot()
    except Exception:
        return {"error": traceback.format_exc()}


def _chatgpt_desktop_status():
    try:
        from modules.chatgpt_desktop_bridge import chatgpt_desktop_status, chatgpt_desktop_loop_status
        return {
            "status": chatgpt_desktop_status(),
            "loop": chatgpt_desktop_loop_status(),
        }
    except Exception:
        return {"error": traceback.format_exc()}


def build_global_update_plan():
    return {
        "title": "LocalComet Global Update Plan",
        "steps": [
            {
                "id": 1,
                "title": "Холодный безопасный режим",
                "command": "safe mode",
                "reason": "Выключить голос и известные циклы перед работой.",
            },
            {
                "id": 2,
                "title": "Проверка проекта",
                "command": "полная проверка",
                "reason": "Понять, что сломано до следующего patch.",
            },
            {
                "id": 3,
                "title": "Снимок релиза",
                "command": "снимок релиза",
                "reason": "Зафиксировать состояние перед крупными изменениями.",
            },
            {
                "id": 4,
                "title": "PC Agent next",
                "command": "что дальше",
                "reason": "Получить безопасные следующие шаги.",
            },
            {
                "id": 5,
                "title": "Коммит",
                "command": "статус git",
                "reason": "Коммитить только после зелёных проверок.",
            },
        ],
    }


def format_global_update_plan(plan=None):
    plan = plan or build_global_update_plan()
    lines = [plan.get("title", "Global Update Plan") + ":"]
    for step in plan.get("steps", []):
        lines.append("")
        lines.append(f"{step.get('id')}. {step.get('title')}")
        lines.append(f"   Команда: {step.get('command')}")
        lines.append(f"   Зачем: {step.get('reason')}")
    return "\n".join(lines)


def get_global_update_status():
    checks = {
        "git": _safe_call("git", _git_status_short),
        "patch_registry": _safe_call("patch_registry", _patch_registry_status),
        "voice": _safe_call("voice", _voice_status),
        "pc_agent": _safe_call("pc_agent", _pc_agent_health),
        "chatgpt_desktop": _safe_call("chatgpt_desktop", _chatgpt_desktop_status),
        "relay_response": {
            "ok": RELAY_RESPONSE_FILE.exists(),
            "path": str(RELAY_RESPONSE_FILE),
            "size": RELAY_RESPONSE_FILE.stat().st_size if RELAY_RESPONSE_FILE.exists() else 0,
        },
        "latest_reports": {
            "auto_verification": _latest_file(REPORTS_DIR / "auto_verification", ["*.md"]),
            "pc_agent": _latest_file(REPORTS_DIR / "pc_agent", ["*.md", "*.json"]),
            "voice": _latest_file(REPORTS_DIR / "voice_sessions", ["*.md", "*.json"]),
            "global_update_center": _latest_file(GLOBAL_UPDATE_REPORTS_DIR, ["*.md", "*.json"]),
        },
    }

    problems = []
    git_value = checks["git"].get("value") if checks["git"].get("ok") else {}
    git_text = ((git_value or {}).get("stdout") or "") + "\n" + ((git_value or {}).get("stderr") or "")
    if "??" in git_text or "\n M " in git_text or "\nM " in git_text or "\n D " in git_text:
        problems.append("Git содержит незакоммиченные изменения.")

    voice_value = checks["voice"].get("value") if checks["voice"].get("ok") else {}
    if isinstance(voice_value, dict) and voice_value.get("listening"):
        problems.append("Voice сейчас слушает микрофон.")
    if isinstance(voice_value, dict) and not voice_value.get("disabled", False):
        problems.append("Voice не заблокирован. Для холодного режима лучше держать Voice Kill включенным.")

    for name in ["pc_agent", "chatgpt_desktop"]:
        if not checks[name].get("ok"):
            problems.append(f"{name} не прочитан.")

    status = "attention" if problems else "ok"
    payload = {
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT_DIR),
        "checks": checks,
        "problems": problems,
        "recommended_next_steps": build_global_update_plan()["steps"],
    }
    set_value("last_global_update_status", payload)
    return payload


def format_global_update_status(payload):
    checks = payload.get("checks", {})
    problems = payload.get("problems", [])

    lines = [
        "Global Update Center:",
        f"- status: {payload.get('status')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- root: {payload.get('root')}",
        "",
        "Ключевые статусы:",
    ]

    git = checks.get("git", {})
    git_value = git.get("value") if isinstance(git, dict) else {}
    lines.append("- git: " + ("ok" if git.get("ok") else "fail"))
    if isinstance(git_value, dict) and git_value.get("stdout"):
        lines.append(_short(git_value.get("stdout"), 500))

    registry = checks.get("patch_registry", {})
    registry_value = registry.get("value") if isinstance(registry, dict) else {}
    if isinstance(registry_value, dict):
        lines.append(f"- patch_registry: {registry_value.get('count')} patches")

    voice = checks.get("voice", {})
    voice_value = voice.get("value") if isinstance(voice, dict) else {}
    if isinstance(voice_value, dict):
        lines.append(
            "- voice: "
            f"enabled={voice_value.get('enabled')} "
            f"disabled={voice_value.get('disabled')} "
            f"listening={voice_value.get('listening')} "
            f"muted={voice_value.get('muted')}"
        )

    relay = checks.get("relay_response", {})
    if isinstance(relay, dict):
        lines.append(f"- response.json: exists={relay.get('ok')} size={relay.get('size')}")

    lines.append("")
    lines.append("Проблемы:")
    if problems:
        lines.extend("- " + problem for problem in problems)
    else:
        lines.append("- Не обнаружены.")

    lines.append("")
    lines.append("Рекомендуемые следующие шаги:")
    for step in payload.get("recommended_next_steps", []):
        lines.append(f"{step.get('id')}. {step.get('title')} — {step.get('command')}")

    return "\n".join(lines)


def activate_safe_mode():
    actions = []

    try:
        from modules.voice_control import voice_kill_switch
        actions.append({"voice_kill_switch": voice_kill_switch(disable_voice=True)})
    except Exception:
        actions.append({"voice_kill_switch_error": traceback.format_exc()})

    try:
        from modules.pc_agent_core import pc_agent_loop_stop
        actions.append({"pc_agent_loop_stop": pc_agent_loop_stop()})
    except Exception:
        actions.append({"pc_agent_loop_stop_error": traceback.format_exc()})

    try:
        from modules.chatgpt_desktop_bridge import chatgpt_desktop_loop_stop
        actions.append({"chatgpt_desktop_loop_stop": chatgpt_desktop_loop_stop()})
    except Exception:
        actions.append({"chatgpt_desktop_loop_stop_error": "not available"})

    set_value("global_safe_mode", True)
    payload = {
        "ok": True,
        "safe_mode": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "actions": actions,
        "message": "Safe Mode enabled. Voice and known loops were asked to stop.",
    }
    set_value("last_global_safe_mode", payload)
    return payload


def create_release_snapshot(note=""):
    GLOBAL_UPDATE_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    status = get_global_update_status()
    plan = build_global_update_plan()
    snapshot = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "note": str(note or "").strip(),
        "status": status,
        "plan": plan,
    }

    stamp = _stamp()
    json_path = GLOBAL_UPDATE_REPORTS_DIR / f"release_snapshot_{stamp}.json"
    md_path = GLOBAL_UPDATE_REPORTS_DIR / f"release_snapshot_{stamp}.md"

    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# LocalComet Release Snapshot",
        "",
        f"- generated_at: {snapshot['generated_at']}",
        f"- note: {snapshot['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_global_update_status(status),
        "```",
        "",
        "## Plan",
        "",
        "```text",
        format_global_update_plan(plan),
        "```",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    set_value("last_global_update_report", str(md_path))
    return {
        "ok": True,
        "json": str(json_path),
        "report": str(md_path),
        "status": status.get("status"),
        "problems": status.get("problems", []),
    }


def format_release_snapshot(payload):
    lines = [
        "Release Snapshot:",
        f"- ok: {payload.get('ok')}",
        f"- status: {payload.get('status')}",
        f"- report: {payload.get('report')}",
        f"- json: {payload.get('json')}",
        "",
        "Problems:",
    ]
    problems = payload.get("problems", [])
    if problems:
        lines.extend("- " + problem for problem in problems)
    else:
        lines.append("- Не обнаружены.")
    return "\n".join(lines)
