from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import html
import json
import webbrowser


ROOT_DIR = get_project_root()
UI_ROOT = ROOT_DIR / "Projects" / "UI" / "localcomet-premium-dashboard"
LAUNCHER_DIR = ROOT_DIR / "Projects" / "UI" / "Launchers"
REQUESTS_DIR = ROOT_DIR / "Projects" / "UI" / "localcomet-premium-dashboard_requests"
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "premium_ui_launcher"

LAUNCHER_VERSION = "v6.29b"
LAUNCHER_NAME = "LocalComet Premium UI Launcher"

EXPECTED_UI_FILES = [
    "index.html",
    "package.json",
    "README.md",
    "vite.config.ts",
    "tailwind.config.ts",
    "src/App.tsx",
    "src/main.tsx",
    "src/index.css",
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
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def audit_ui():
    package_path = UI_ROOT / "package.json"
    package = _read_json(package_path) if package_path.exists() else {}
    package_text = package_path.read_text(encoding="utf-8") if package_path.exists() else ""

    missing = [item for item in EXPECTED_UI_FILES if not (UI_ROOT / item).exists()]
    forbidden_config_js = [str(path.relative_to(UI_ROOT)) for path in UI_ROOT.rglob("*.config.js")] if UI_ROOT.exists() else []

    checks = [
        {"name": "ui_root_exists", "ok": UI_ROOT.exists(), "detail": str(UI_ROOT)},
        {"name": "expected_files_present", "ok": not missing, "detail": missing},
        {"name": "no_supabase_dependency", "ok": "supabase" not in package_text.lower(), "detail": "package.json"},
        {"name": "no_forbidden_config_js", "ok": not forbidden_config_js, "detail": forbidden_config_js},
        {"name": "emergency_stop_modal", "ok": (UI_ROOT / "src" / "layout" / "EmergencyStopModal.tsx").exists(), "detail": "mock confirmation modal"},
        {"name": "command_palette", "ok": (UI_ROOT / "src" / "layout" / "CommandPalette.tsx").exists(), "detail": "mock searchable commands"},
    ]

    return {
        "ok": all(item["ok"] for item in checks),
        "mode": "premium_ui_launcher_audit",
        "generated_at": _now(),
        "version": LAUNCHER_VERSION,
        "ui_root": str(UI_ROOT),
        "package": {
            "name": package.get("name"),
            "version": package.get("version"),
            "scripts": package.get("scripts", {}),
        },
        "checks": checks,
        "missing": missing,
        "forbidden_config_js": forbidden_config_js,
    }


def status():
    audit = audit_ui()
    return {
        "ok": audit["ok"],
        "mode": "premium_ui_launcher_status",
        "generated_at": _now(),
        "name": LAUNCHER_NAME,
        "version": LAUNCHER_VERSION,
        "ui_root": str(UI_ROOT),
        "launcher_dir": str(LAUNCHER_DIR),
        "audit": audit,
        "commands": [
            "pc premium launcher status",
            "pc premium launcher guide",
            "pc premium launcher page",
            "pc premium launcher open request",
            "pc premium launcher open подтверждаю",
            "pc premium launcher report",
            "pc premium ui launcher status",
            "pc premium ui launcher page",
            "pc premium ui launcher report",
        ],
        "safety": [
            "Default commands never launch npm or a browser.",
            "Open command requires explicit confirmation.",
            "Confirmed open only opens a static local HTML launcher page.",
            "No shell/cmd/powershell.",
            "No delete/format.",
            "No backend bridge.",
            "No deploy.",
            "No secrets/tokens/API keys.",
        ],
    }


def guide():
    return {
        "ok": True,
        "mode": "premium_ui_launcher_guide",
        "generated_at": _now(),
        "summary": "LocalComet Premium UI is installed as a frontend-only React/Vite/Tailwind prototype.",
        "manual_preview": [
            "Open a terminal manually only if you intentionally want to preview the React app.",
            "cd C:\\Users\\DNS\\Documents\\LocalAgent\\Projects\\UI\\localcomet-premium-dashboard",
            "npm install",
            "npm run dev",
        ],
        "localcomet_safe_commands": [
            "pc premium ui status",
            "pc premium ui audit",
            "pc premium launcher page",
            "pc premium launcher report",
        ],
        "do_not_do_automatically": [
            "Do not auto-run npm.",
            "Do not auto-open shell/cmd/powershell.",
            "Do not connect backend yet.",
            "Do not deploy.",
            "Do not add tokens/API keys.",
        ],
    }


def create_launcher_page():
    _ensure_dirs()
    audit = audit_ui()
    page_path = LAUNCHER_DIR / "localcomet_premium_dashboard_launcher.html"
    audit_json = html.escape(json.dumps(audit, ensure_ascii=False, indent=2))

    checks_markup = []
    for check in audit.get("checks", []):
        badge = "OK" if check.get("ok") else "WARN"
        cls = "ok" if check.get("ok") else "warn"
        checks_markup.append(
            f"<div class='check {cls}'><span>{html.escape(badge)}</span><strong>{html.escape(check.get('name', ''))}</strong><small>{html.escape(str(check.get('detail', '')))}</small></div>"
        )

    content = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>LocalComet Premium Dashboard Launcher</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #050711;
      --panel: rgba(255,255,255,.065);
      --panel2: rgba(255,255,255,.035);
      --border: rgba(255,255,255,.12);
      --text: #f8fafc;
      --muted: #94a3b8;
      --blue: #60a5fa;
      --violet: #a78bfa;
      --green: #34d399;
      --red: #fb7185;
      --amber: #fbbf24;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(96,165,250,.22), transparent 32rem),
        radial-gradient(circle at top right, rgba(167,139,250,.20), transparent 30rem),
        var(--bg);
      color: var(--text);
      padding: 42px;
    }}
    .shell {{ max-width: 1120px; margin: 0 auto; }}
    .hero {{
      border: 1px solid var(--border);
      background: linear-gradient(135deg, rgba(255,255,255,.09), rgba(255,255,255,.035));
      border-radius: 28px;
      padding: 34px;
      box-shadow: 0 24px 90px rgba(0,0,0,.35);
    }}
    h1 {{ margin: 0; font-size: 42px; letter-spacing: -.04em; }}
    p {{ color: var(--muted); line-height: 1.65; }}
    .badge-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 22px 0; }}
    .badge {{
      border: 1px solid var(--border);
      background: var(--panel2);
      color: var(--text);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 13px;
    }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 22px; }}
    .card {{
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 20px;
      padding: 20px;
    }}
    .card h2 {{ margin: 0 0 12px; font-size: 17px; }}
    code, pre {{
      font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      color: #dbeafe;
    }}
    pre {{
      overflow: auto;
      background: rgba(0,0,0,.28);
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 16px;
      padding: 16px;
      font-size: 12px;
      line-height: 1.55;
    }}
    .checks {{ display: grid; gap: 10px; }}
    .check {{
      display: grid;
      grid-template-columns: 54px 1fr;
      gap: 8px 12px;
      align-items: center;
      padding: 11px 12px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: rgba(255,255,255,.03);
    }}
    .check span {{
      grid-row: span 2;
      width: 44px;
      text-align: center;
      padding: 5px 0;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
    }}
    .check.ok span {{ background: rgba(52,211,153,.14); color: var(--green); }}
    .check.warn span {{ background: rgba(251,191,36,.14); color: var(--amber); }}
    .check strong {{ font-size: 13px; }}
    .check small {{ color: var(--muted); overflow-wrap: anywhere; }}
    .danger {{ color: var(--red); }}
    @media (max-width: 820px) {{
      body {{ padding: 18px; }}
      h1 {{ font-size: 30px; }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <h1>LocalComet Premium Dashboard Launcher</h1>
      <p>Static safe launcher page for the frontend-only AgentOS dashboard prototype. This page does not execute npm, shell, backend, deploy, delete, or browser automation. It only documents the installed UI and manual preview path.</p>
      <div class="badge-row">
        <div class="badge">LocalComet {html.escape(LAUNCHER_VERSION)}</div>
        <div class="badge">Frontend-only</div>
        <div class="badge">Safe Mode</div>
        <div class="badge">No backend bridge</div>
        <div class="badge">No shell execution</div>
      </div>
      <div class="grid">
        <article class="card">
          <h2>Installed UI path</h2>
          <pre>{html.escape(str(UI_ROOT))}</pre>
        </article>
        <article class="card">
          <h2>Manual preview commands</h2>
          <p>Run manually only when you intentionally want to preview the React app.</p>
          <pre>cd C:\\Users\\DNS\\Documents\\LocalAgent\\Projects\\UI\\localcomet-premium-dashboard
npm install
npm run dev</pre>
        </article>
        <article class="card">
          <h2>Safety rules</h2>
          <p class="danger">This launcher does not perform real system actions.</p>
          <ul>
            <li>No shell/cmd/powershell execution</li>
            <li>No delete/format actions</li>
            <li>No deploy</li>
            <li>No backend bridge</li>
            <li>No secrets/tokens/API keys</li>
          </ul>
        </article>
        <article class="card">
          <h2>Audit checks</h2>
          <div class="checks">
            {''.join(checks_markup)}
          </div>
        </article>
      </div>
      <article class="card" style="margin-top:18px">
        <h2>Audit JSON</h2>
        <pre>{audit_json}</pre>
      </article>
    </section>
  </main>
</body>
</html>
"""
    page_path.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "mode": "premium_ui_launcher_page",
        "generated_at": _now(),
        "page": str(page_path),
        "audit_ok": audit.get("ok"),
        "message": "Static launcher page created. No browser was opened.",
    }


def open_request():
    _ensure_dirs()
    page = create_launcher_page()
    request_path = REQUESTS_DIR / f"premium_ui_launcher_open_request_{_stamp()}.md"
    content = f"""# Premium UI Launcher Open Request

Generated: {_now()}

Launcher page:

```text
{page.get('page')}
```

Safe confirmed command:

```text
pc premium launcher open подтверждаю
```

This command opens only the static local launcher HTML page in the default browser.

It does not run:

- npm
- shell/cmd/powershell
- backend
- deploy
- delete
- install
- browser automation

Manual React preview, if needed:

```text
cd C:\\Users\\DNS\\Documents\\LocalAgent\\Projects\\UI\\localcomet-premium-dashboard
npm install
npm run dev
```
"""
    request_path.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "mode": "premium_ui_launcher_open_request",
        "generated_at": _now(),
        "request": str(request_path),
        "launcher_page": page.get("page"),
        "message": "Open request created. No browser was opened.",
    }


def open_confirmed(command):
    text = str(command or "").lower().replace("ё", "е")
    confirmed = "подтверждаю" in text or "confirm" in text
    if not confirmed:
        return {
            "ok": False,
            "mode": "premium_ui_launcher_open",
            "generated_at": _now(),
            "error": "Opening requires explicit confirmation.",
            "required": "pc premium launcher open подтверждаю",
        }

    page = create_launcher_page()
    uri = Path(page["page"]).resolve().as_uri()
    webbrowser.open(uri)
    return {
        "ok": True,
        "mode": "premium_ui_launcher_open",
        "generated_at": _now(),
        "opened": uri,
        "message": "Opened static launcher HTML page only. No shell/npm/backend/deploy was executed.",
    }


def report():
    _ensure_dirs()
    page = create_launcher_page()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "status": status(),
        "guide": guide(),
        "launcher_page": page,
    }

    json_path = REPORTS_DIR / f"premium_ui_launcher_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"premium_ui_launcher_report_{_stamp()}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# Premium UI Launcher Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- launcher_page: {page.get('page')}",
        f"- ui_root: {UI_ROOT}",
        f"- ok: {payload['status']['ok']}",
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
        "mode": "premium_ui_launcher_report",
        "generated_at": _now(),
        "report": str(md_path),
        "json": str(json_path),
        "launcher_page": page.get("page"),
    }


def format_payload(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")

    if lower in {"pc premium launcher", "pc premium launcher status", "pc premium ui launcher status", "premium launcher status"}:
        return format_payload(status())

    if lower in {"pc premium launcher guide", "pc premium ui launcher guide", "premium launcher guide"}:
        return format_payload(guide())

    if lower in {"pc premium launcher page", "pc premium ui launcher page", "premium launcher page"}:
        return format_payload(create_launcher_page())

    if lower in {"pc premium launcher open request", "pc premium ui launcher open request", "premium launcher open request"}:
        return format_payload(open_request())

    if lower.startswith("pc premium launcher open") or lower.startswith("pc premium ui launcher open"):
        return format_payload(open_confirmed(text))

    if lower in {"pc premium launcher report", "pc premium ui launcher report", "premium launcher report"}:
        return format_payload(report())

    return format_payload({
        "ok": False,
        "mode": "premium_ui_launcher_unknown_command",
        "generated_at": _now(),
        "error": "Unknown Premium UI Launcher command.",
        "commands": status().get("commands", []),
    })


def is_premium_ui_launcher_command(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    exact = {
        "pc premium launcher",
        "pc premium launcher status",
        "pc premium ui launcher status",
        "premium launcher status",
        "pc premium launcher guide",
        "pc premium ui launcher guide",
        "premium launcher guide",
        "pc premium launcher page",
        "pc premium ui launcher page",
        "premium launcher page",
        "pc premium launcher open request",
        "pc premium ui launcher open request",
        "premium launcher open request",
        "pc premium launcher report",
        "pc premium ui launcher report",
        "premium launcher report",
    }
    if lower in exact:
        return True
    return lower.startswith("pc premium launcher open") or lower.startswith("pc premium ui launcher open")
