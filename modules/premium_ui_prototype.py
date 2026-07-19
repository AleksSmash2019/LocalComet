from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json


ROOT_DIR = get_project_root()
UI_ROOT = ROOT_DIR / "Projects" / "UI" / "localcomet-premium-dashboard"
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "premium_ui_prototype"
REQUESTS_DIR = ROOT_DIR / "Projects" / "UI" / "localcomet-premium-dashboard_requests"

PREMIUM_UI_VERSION = "v6.29b"
PREMIUM_UI_NAME = "LocalComet Premium Dashboard Prototype + Launcher Ready"


EXPECTED_FILES = [
    "package.json",
    "vite.config.ts",
    "tailwind.config.ts",
    "index.html",
    "src/App.tsx",
    "src/main.tsx",
    "src/index.css",
    "src/layout/Sidebar.tsx",
    "src/layout/TopBar.tsx",
    "src/layout/CommandPalette.tsx",
    "src/layout/EmergencyStopModal.tsx",
    "src/pages/CommandCenterPage.tsx",
    "src/pages/AgentOSPage.tsx",
    "src/pages/SwissKnifePage.tsx",
    "src/pages/DesktopPage.tsx",
    "src/pages/UIParserPage.tsx",
    "src/pages/ProjectsPage.tsx",
    "src/pages/PatchesPage.tsx",
    "src/pages/ReportsPage.tsx",
    "src/pages/SafetyPage.tsx",
    "src/pages/SettingsPage.tsx",
    "src/data/mock.ts",
    "src/data/skills.ts",
    "src/lib/store.tsx",
    "src/types/index.ts",
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def _file_info(rel_path):
    path = UI_ROOT / rel_path
    if not path.exists():
        return {"path": rel_path, "exists": False}
    return {
        "path": rel_path,
        "exists": True,
        "size": path.stat().st_size,
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
    }


def _list_project_files():
    if not UI_ROOT.exists():
        return []
    files = []
    for path in sorted(UI_ROOT.rglob("*")):
        if path.is_file():
            rel = path.relative_to(UI_ROOT).as_posix()
            if "/node_modules/" in rel or rel.startswith("node_modules/"):
                continue
            files.append({
                "path": rel,
                "size": path.stat().st_size,
            })
    return files


def audit():
    package_path = UI_ROOT / "package.json"
    package = _read_json(package_path) if package_path.exists() else {}

    files = [_file_info(item) for item in EXPECTED_FILES]
    missing = [item["path"] for item in files if not item["exists"]]

    package_text = package_path.read_text(encoding="utf-8") if package_path.exists() else ""
    supabase_present = "supabase" in package_text.lower()

    checks = [
        {"name": "ui_root_exists", "ok": UI_ROOT.exists(), "detail": str(UI_ROOT)},
        {"name": "expected_files_present", "ok": not missing, "detail": missing},
        {"name": "frontend_only_no_supabase_dependency", "ok": not supabase_present, "detail": "supabase not found in package.json"},
        {"name": "vite_react_present", "ok": (UI_ROOT / "vite.config.ts").exists(), "detail": "vite.config.ts"},
        {"name": "tailwind_present", "ok": (UI_ROOT / "tailwind.config.ts").exists(), "detail": "tailwind.config.ts"},
        {"name": "safe_emergency_modal_present", "ok": (UI_ROOT / "src" / "layout" / "EmergencyStopModal.tsx").exists(), "detail": "mock modal only"},
        {"name": "command_palette_present", "ok": (UI_ROOT / "src" / "layout" / "CommandPalette.tsx").exists(), "detail": "mock searchable commands"},
    ]

    return {
        "ok": all(item["ok"] for item in checks),
        "mode": "premium_ui_audit",
        "generated_at": _now(),
        "version": PREMIUM_UI_VERSION,
        "ui_root": str(UI_ROOT),
        "package": {
            "name": package.get("name"),
            "version": package.get("version"),
            "scripts": package.get("scripts", {}),
            "dependencies": package.get("dependencies", {}),
            "devDependencies": package.get("devDependencies", {}),
        },
        "checks": checks,
        "missing": missing,
    }


def status():
    result = audit()
    project_files = _list_project_files()
    return {
        "ok": result["ok"],
        "mode": "premium_ui_status",
        "generated_at": _now(),
        "name": PREMIUM_UI_NAME,
        "version": PREMIUM_UI_VERSION,
        "ui_root": str(UI_ROOT),
        "files_count": len(project_files),
        "audit": result,
        "commands": [
            "pc premium ui status",
            "pc premium ui files",
            "pc premium ui audit",
            "pc premium ui open request",
            "pc premium ui report",
        ],
        "safety": [
            "Frontend-only prototype.",
            "No shell/cmd/powershell execution.",
            "No delete/format actions.",
            "No secrets/tokens/SSH.",
            "No backend bridge yet.",
            "Emergency Stop is mock UI state only.",
        ],
    }


def files():
    return {
        "ok": UI_ROOT.exists(),
        "mode": "premium_ui_files",
        "generated_at": _now(),
        "ui_root": str(UI_ROOT),
        "files": _list_project_files(),
    }


def open_request():
    _ensure_dirs()
    request_path = REQUESTS_DIR / f"premium_ui_manual_preview_request_{_stamp()}.md"
    content = f"""# LocalComet Premium Dashboard Manual Preview Request

Generated: {_now()}

Prototype path:

```text
{UI_ROOT}
```

This command intentionally does not launch a browser, terminal, npm, shell, cmd, PowerShell, install, deploy, or backend action.

Manual preview options:

```text
cd C:\\Users\\DNS\\Documents\\LocalAgent\\Projects\\UI\\localcomet-premium-dashboard
npm install
npm run dev
```

Safety:

- frontend-only;
- no real backend;
- no real command execution;
- no secrets;
- no delete actions;
- no deploy actions.
"""
    request_path.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "mode": "premium_ui_open_request",
        "generated_at": _now(),
        "request": str(request_path),
        "message": "Manual preview request created. No browser or shell was launched.",
    }


def report():
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "status": status(),
        "files": files(),
    }

    json_path = REPORTS_DIR / f"premium_ui_prototype_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"premium_ui_prototype_report_{_stamp()}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# LocalComet Premium Dashboard Prototype Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- ui_root: {UI_ROOT}",
        f"- ok: {payload['status']['ok']}",
        f"- files_count: {payload['status']['files_count']}",
        "",
        "## Commands",
        "",
    ]
    md.extend(f"- `{command}`" for command in payload["status"]["commands"])
    md.extend([
        "",
        "## Safety",
        "",
    ])
    md.extend(f"- {item}" for item in payload["status"]["safety"])
    md_path.write_text("\n".join(md), encoding="utf-8")

    return {
        "ok": True,
        "mode": "premium_ui_report",
        "generated_at": _now(),
        "report": str(md_path),
        "json": str(json_path),
    }


def format_text(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")

    if lower in {"pc premium ui", "pc premium ui status", "premium ui status"}:
        return format_text(status())
    if lower in {"pc premium ui files", "premium ui files"}:
        return format_text(files())
    if lower in {"pc premium ui audit", "premium ui audit"}:
        return format_text(audit())
    if lower in {"pc premium ui open request", "pc premium ui preview request", "premium ui open request"}:
        return format_text(open_request())
    if lower in {"pc premium ui report", "premium ui report"}:
        return format_text(report())

    return format_text({
        "ok": False,
        "mode": "premium_ui_unknown_command",
        "generated_at": _now(),
        "error": "Unknown premium UI command.",
        "commands": status().get("commands", []),
    })


def is_premium_ui_command(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    exact = {
        "pc premium ui",
        "pc premium ui status",
        "premium ui status",
        "pc premium ui files",
        "premium ui files",
        "pc premium ui audit",
        "premium ui audit",
        "pc premium ui open request",
        "pc premium ui preview request",
        "premium ui open request",
        "pc premium ui report",
        "premium ui report",
    }
    return lower in exact
