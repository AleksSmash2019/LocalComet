import importlib
import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
RELAY_DIR = PROJECTS_DIR / "ChatGPTRelay"
RELAY_DOWNLOADS_DIR = RELAY_DIR / "Downloads"
REPORTS_DIR = PROJECTS_DIR / "Reports"
LOGS_DIR = PROJECTS_DIR / "Logs"
PATCH_REGISTRY_FILE = PROJECTS_DIR / "PatchRegistry" / "patches.json"
DIAGNOSTICS_REPORTS_DIR = REPORTS_DIR / "relay_diagnostics"

REQUEST_FILE = RELAY_DIR / "request.md"
RESPONSE_FILE = RELAY_DIR / "response.json"
BAD_RESPONSE_FILE = RELAY_DIR / "bad_response.json"
RAW_RESPONSE_TXT_FILE = RELAY_DIR / "response_raw.txt"
RAW_RESPONSE_MD_FILE = RELAY_DIR / "response_raw.md"
LAST_ANSWER_FILE = RELAY_DIR / "gpt_browser_last_answer.txt"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _exists(path):
    return Path(path).exists()


def _module_imports(name):
    try:
        importlib.import_module(name)
        return True, ""
    except Exception as e:
        return False, str(e)


def _read_json(path):
    path = Path(path)

    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _latest_patch_summary():
    data = _read_json(PATCH_REGISTRY_FILE)

    if isinstance(data, dict):
        data = data.get("patches")

    if isinstance(data, list) and data:
        latest = data[-1]

        if isinstance(latest, dict):
            return {
                "version": latest.get("version", ""),
                "summary": latest.get("summary", ""),
                "applied_at": latest.get("applied_at", ""),
                "status": latest.get("status", ""),
            }

    return {
        "version": get_value("last_patch_version", ""),
        "summary": get_value("last_patch_summary", ""),
        "applied_at": get_value("last_patch_applied_at", ""),
        "status": get_value("last_patch_status", ""),
    }


def _source_contains(path, markers):
    path = Path(path)

    if not path.exists():
        return False

    try:
        text = path.read_text(encoding="utf-8", errors="replace").lower()
    except Exception:
        return False

    return all(marker.lower() in text for marker in markers)


def get_relay_diagnostics():
    imports = {}

    for module_name in [
        "modules.true_auto_relay",
        "modules.chatgpt_relay",
        "modules.self_edit",
    ]:
        ok, error = _module_imports(module_name)
        imports[module_name] = {"ok": ok, "error": error}

    diagnostics = {
        "project_root": str(ROOT_DIR),
        "paths": {
            "relay_dir": {"path": str(RELAY_DIR), "exists": _exists(RELAY_DIR)},
            "downloads_dir": {"path": str(RELAY_DOWNLOADS_DIR), "exists": _exists(RELAY_DOWNLOADS_DIR)},
            "reports_dir": {"path": str(REPORTS_DIR), "exists": _exists(REPORTS_DIR)},
            "logs_dir": {"path": str(LOGS_DIR), "exists": _exists(LOGS_DIR)},
        },
        "files": {
            "request_md": {"path": str(REQUEST_FILE), "exists": _exists(REQUEST_FILE)},
            "response_json": {"path": str(RESPONSE_FILE), "exists": _exists(RESPONSE_FILE)},
            "bad_response_json": {"path": str(BAD_RESPONSE_FILE), "exists": _exists(BAD_RESPONSE_FILE)},
            "last_raw_response_txt": {"path": str(RAW_RESPONSE_TXT_FILE), "exists": _exists(RAW_RESPONSE_TXT_FILE)},
            "last_raw_response_md": {"path": str(RAW_RESPONSE_MD_FILE), "exists": _exists(RAW_RESPONSE_MD_FILE)},
            "last_answer_txt": {"path": str(LAST_ANSWER_FILE), "exists": _exists(LAST_ANSWER_FILE)},
        },
        "state": {
            "current_cycle_id": get_value("last_true_auto_cycle_id", ""),
            "last_imported_cycle_id": get_value("last_true_auto_imported_cycle_id", ""),
            "last_relay_error": (
                get_value("last_relay_error", "")
                or get_value("last_gpt_browser_error", "")
                or get_value("last_true_auto_download_error", "")
                or get_value("last_error", "")
            ),
            "last_relay_request": get_value("last_relay_request", ""),
            "last_relay_response": get_value("last_relay_response", ""),
            "last_true_auto_relay_report": get_value("last_true_auto_relay_report", ""),
            "last_applied_patch": _latest_patch_summary(),
        },
        "guards": {
            "response_freshness_guard_present": _source_contains(
                ROOT_DIR / "modules" / "true_auto_relay.py",
                ["response freshness guard", "expected_cycle_id", "meta.cycle_id"],
            ),
            "patch_registry_present": _exists(PATCH_REGISTRY_FILE) and imports["modules.self_edit"]["ok"],
            "dry_run_safe": True,
        },
        "imports": imports,
    }

    return diagnostics


def _yes(value):
    return "да" if value else "нет"


def format_relay_diagnostics_text(diagnostics=None):
    diagnostics = diagnostics or get_relay_diagnostics()

    lines = [
        "Relay Diagnostics:",
        f"- project_root: {diagnostics.get('project_root')}",
        "",
        "Paths:",
    ]

    for name, item in diagnostics.get("paths", {}).items():
        lines.append(f"- {name}: {_yes(item.get('exists'))} | {item.get('path')}")

    lines.append("")
    lines.append("Existing files:")

    for name, item in diagnostics.get("files", {}).items():
        lines.append(f"- {name}: {_yes(item.get('exists'))} | {item.get('path')}")

    lines.append("")
    lines.append("Module imports:")

    for name, item in diagnostics.get("imports", {}).items():
        suffix = "" if item.get("ok") else f" | {item.get('error')}"
        lines.append(f"- {name}: {_yes(item.get('ok'))}{suffix}")

    state = diagnostics.get("state", {})
    guards = diagnostics.get("guards", {})

    lines.extend([
        "",
        "Relay safety:",
        f"- response_freshness_guard_present: {_yes(guards.get('response_freshness_guard_present'))}",
        f"- patch_registry_present: {_yes(guards.get('patch_registry_present'))}",
        f"- dry_run_safe: {_yes(guards.get('dry_run_safe'))}",
        "",
        "Last known state:",
        f"- current_cycle_id: {state.get('current_cycle_id') or 'нет'}",
        f"- last_imported_cycle_id: {state.get('last_imported_cycle_id') or 'нет'}",
        f"- last_relay_request: {state.get('last_relay_request') or 'нет'}",
        f"- last_relay_response: {state.get('last_relay_response') or 'нет'}",
        f"- last_true_auto_relay_report: {state.get('last_true_auto_relay_report') or 'нет'}",
        f"- last_relay_error: {state.get('last_relay_error') or 'нет'}",
    ])

    latest = state.get("last_applied_patch") or {}
    lines.extend([
        "- last_applied_patch: "
        + f"{latest.get('version') or 'нет'} | {latest.get('status') or 'нет'} | {latest.get('summary') or 'нет'}",
    ])

    return "\n".join(lines)


def _report_path():
    DIAGNOSTICS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return DIAGNOSTICS_REPORTS_DIR / f"relay_diagnostics_{_stamp()}.md"


def _section(lines, title, body):
    lines.append(f"## {title}")
    lines.append("")

    if isinstance(body, list):
        lines.extend(body)
    else:
        lines.append(str(body))

    lines.append("")


def run_relay_smoke_test(dry_run=True):
    diagnostics = get_relay_diagnostics()
    report_path = _report_path()

    paths_ok = all(item.get("exists") for item in diagnostics.get("paths", {}).values())
    imports_ok = all(item.get("ok") for item in diagnostics.get("imports", {}).values())
    guards = diagnostics.get("guards", {})
    safety_ok = bool(guards.get("response_freshness_guard_present") and guards.get("patch_registry_present"))
    passed = bool(paths_ok and imports_ok and safety_ok and dry_run)

    lines = [
        "# Relay Diagnostics Smoke Test",
        "",
        f"- started_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- dry_run: {_yes(dry_run)}",
        f"- result: {'PASS' if passed else 'CHECK'}",
        "",
    ]

    _section(lines, "Summary", [
        f"- paths_ok: {_yes(paths_ok)}",
        f"- imports_ok: {_yes(imports_ok)}",
        f"- safety_ok: {_yes(safety_ok)}",
        "- real_chatgpt_send: нет",
        "- real_patch_apply: нет",
    ])

    _section(lines, "Paths", [
        f"- {name}: {_yes(item.get('exists'))} | {item.get('path')}"
        for name, item in diagnostics.get("paths", {}).items()
    ])

    _section(lines, "Existing files", [
        f"- {name}: {_yes(item.get('exists'))} | {item.get('path')}"
        for name, item in diagnostics.get("files", {}).items()
    ])

    _section(lines, "Module imports", [
        f"- {name}: {_yes(item.get('ok'))}"
        + ("" if item.get("ok") else f" | {item.get('error')}")
        for name, item in diagnostics.get("imports", {}).items()
    ])

    _section(lines, "Relay safety", [
        f"- response_freshness_guard_present: {_yes(guards.get('response_freshness_guard_present'))}",
        f"- patch_registry_present: {_yes(guards.get('patch_registry_present'))}",
        f"- dry_run_safe: {_yes(guards.get('dry_run_safe'))}",
        "- response_json_created: нет",
        "- patch_applied: нет",
    ])

    state = diagnostics.get("state", {})
    latest = state.get("last_applied_patch") or {}

    _section(lines, "Last known state", [
        f"- current_cycle_id: {state.get('current_cycle_id') or 'нет'}",
        f"- last_imported_cycle_id: {state.get('last_imported_cycle_id') or 'нет'}",
        f"- last_relay_request: {state.get('last_relay_request') or 'нет'}",
        f"- last_relay_response: {state.get('last_relay_response') or 'нет'}",
        f"- last_true_auto_relay_report: {state.get('last_true_auto_relay_report') or 'нет'}",
        f"- last_relay_error: {state.get('last_relay_error') or 'нет'}",
        f"- last_applied_patch: {latest.get('version') or 'нет'} | {latest.get('status') or 'нет'} | {latest.get('summary') or 'нет'}",
    ])

    _section(lines, "Result", [
        f"- status: {'PASS' if passed else 'CHECK'}",
        f"- report: {report_path}",
    ])

    _section(lines, "Next manual steps", [
        "1. Открой панель LocalComet.",
        "2. Нажми Relay status.",
        "3. Нажми Relay smoke.",
        "4. Нажми Open last relay report.",
        "5. Только после ручной проверки запускай настоящий dev -> ChatGPT -> validate -> apply цикл.",
    ])

    report_path.write_text("\n".join(lines), encoding="utf-8")

    set_value("last_relay_diagnostics_report", str(report_path))
    set_value("last_relay_diagnostics_status", "PASS" if passed else "CHECK")
    set_value("last_relay_diagnostics_at", datetime.now().isoformat(timespec="seconds"))

    return (
        "Relay smoke test завершен.\n"
        f"Dry-run: {_yes(dry_run)}\n"
        f"Result: {'PASS' if passed else 'CHECK'}\n"
        f"Report: {report_path}\n\n"
        "Безопасность: ChatGPT не отправлялся, response.json не создавался, patch не применялся."
    )


def latest_relay_diagnostics_report():
    state_path = str(get_value("last_relay_diagnostics_report", "") or "").strip()

    if state_path:
        path = Path(state_path)

        if path.exists() and path.is_file():
            return path

    if not DIAGNOSTICS_REPORTS_DIR.exists():
        return None

    reports = [path for path in DIAGNOSTICS_REPORTS_DIR.glob("relay_diagnostics_*.md") if path.is_file()]

    if not reports:
        return None

    return max(reports, key=lambda path: path.stat().st_mtime)
