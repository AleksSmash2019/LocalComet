import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
REGISTRY_DIR = ROOT_DIR / "Projects" / "PatchRegistry"
REGISTRY_FILE = REGISTRY_DIR / "patches.json"


def _ensure_registry():
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)

    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.write_text("[]", encoding="utf-8")


def _load_entries():
    _ensure_registry()

    if not REGISTRY_FILE.exists():
        return []

    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict) and isinstance(data.get("patches"), list):
        return data["patches"]

    return []


def _save_entries(entries):
    _ensure_registry()
    REGISTRY_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def extract_patch_version(*values):
    for value in values:
        text = str(value or "")

        for raw_token in text.replace(":", " ").replace(";", " ").replace(",", " ").split():
            token = raw_token.strip(" [](){}'\".")

            if len(token) >= 2 and token.lower().startswith("v") and any(ch.isdigit() for ch in token):
                return token

    return ""


def list_patches():
    return _load_entries()


def get_latest_patch():
    entries = _load_entries()

    if not entries:
        return {}

    return entries[-1]


def latest_patch():
    return get_latest_patch()


def _operation_paths(patch):
    paths = []

    for op in patch.get("operations", []) or []:
        if isinstance(op, dict) and op.get("path"):
            paths.append(str(op.get("path")))

    return paths


def _infer_source(patch, response_file, patch_file):
    explicit = str(patch.get("source", "") or "").strip()

    if explicit:
        return explicit

    text = f"{response_file} {patch_file}".lower()

    if "chatgpt_relay" in text or "chatgptrelay" in text or "response.json" in text:
        return "chatgpt_relay"

    if "codex" in text:
        return "codex"

    return "unknown"


def record_patch(
    patch=None,
    version="",
    summary="",
    applied_at="",
    response_file="",
    patch_file="",
    rollback_file="",
    changed_files=None,
    operation_count=None,
    tests=None,
    stability_score="",
    status="applied",
    source="",
):
    patch = patch or {}
    changed_files = changed_files if changed_files is not None else _operation_paths(patch)
    operation_count = operation_count if operation_count is not None else len(patch.get("operations", []) or [])
    summary = str(summary or patch.get("summary", "") or "").strip()
    version = extract_patch_version(
        version,
        patch.get("version", ""),
        patch.get("patch_version", ""),
        summary,
        patch_file,
    ) or "unknown"
    source = source or _infer_source(patch, response_file, patch_file)

    tests = tests if isinstance(tests, dict) else {"ok": bool(tests), "result": str(tests or "")}

    entry = {
        "version": version,
        "summary": summary or "нет summary",
        "applied_at": applied_at or datetime.now().isoformat(timespec="seconds"),
        "response_file": str(response_file or ""),
        "patch_file": str(patch_file or ""),
        "rollback_file": str(rollback_file or ""),
        "changed_files": list(changed_files or []),
        "operation_count": int(operation_count or 0),
        "tests": tests,
        "stability_score": str(stability_score or get_value("last_stability_score", "") or ""),
        "status": str(status or "unknown"),
        "source": source,
    }

    entries = _load_entries()
    entries.append(entry)
    _save_entries(entries)

    set_value("last_patch_registry_file", str(REGISTRY_FILE))
    set_value("last_patch_registry_count", len(entries))
    set_value("last_patch_version", version)
    set_value("last_patch_summary", entry["summary"])
    set_value("last_patch_status", entry["status"])
    set_value("last_patch_applied_at", entry["applied_at"])

    return entry


def register_applied_patch(
    patch,
    patch_file,
    rollback_file,
    tests_ok,
    tests_output,
    response_file="",
    changed_files=None,
    source="",
):
    return record_patch(
        patch=patch,
        response_file=response_file,
        patch_file=patch_file,
        rollback_file=rollback_file,
        changed_files=changed_files,
        tests={
            "ok": bool(tests_ok),
            "result": str(tests_output or ""),
        },
        status="applied" if tests_ok else "failed",
        source=source,
    )


def record_current_version(version="v5.52", summary="Manual current version snapshot"):
    return record_patch(
        version=version,
        summary=summary,
        changed_files=[
            "LocalComet_Control_Panel.py",
            "modules/patch_registry.py",
            "agents/system_agent.py",
            "modules/stability_test.py",
        ],
        operation_count=0,
        tests={
            "ok": True,
            "result": "manual registry snapshot",
        },
        status="applied",
        source="codex",
    )


def get_current_version():
    latest = get_latest_patch()
    return str(latest.get("version") or get_value("last_patch_version", "unknown") or "unknown")


def short_status():
    latest = get_latest_patch()

    if not latest:
        return f"Patch Registry: empty | file: {REGISTRY_FILE}"

    return (
        f"Patch Registry: {latest.get('version', 'unknown')} | "
        f"{latest.get('status', 'unknown')} | "
        f"{latest.get('summary', 'нет summary')} | "
        f"count: {len(list_patches())}"
    )


def registry_path():
    _ensure_registry()
    return REGISTRY_FILE
