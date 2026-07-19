from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import get_value, set_value
from modules.git_status import short_status as git_short_status
from modules.llm_provider import short_status as provider_short_status
from modules.patch_registry import short_status as patch_registry_short_status


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
HEALTH_REPORTS_DIR = REPORTS_DIR / "project_health"
RELAY_DIR = PROJECTS_DIR / "ChatGPTRelay"
PATCH_REGISTRY_FILE = PROJECTS_DIR / "PatchRegistry" / "patches.json"
RESPONSE_FILE = RELAY_DIR / "response.json"
REQUEST_FILE = RELAY_DIR / "request.md"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value, limit=220):
    text = str(value or "нет")

    if len(text) <= limit:
        return text

    return text[:limit] + "... [обрезано]"


def _latest_report():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    reports = [path for path in REPORTS_DIR.glob("*.md") if path.is_file()]

    if not reports:
        return ""

    return str(max(reports, key=lambda path: path.stat().st_mtime))


def get_project_health():
    git_status = git_short_status()
    provider_status = provider_short_status()
    patch_status = patch_registry_short_status()
    last_error = get_value("last_error", "")
    last_stability_score = get_value("last_stability_score", "нет")
    last_auto_verification_status = get_value("last_auto_verification_status", "нет")

    checks = {
        "git_ready": "dirty" not in git_status.lower(),
        "request_exists": REQUEST_FILE.exists(),
        "response_exists": RESPONSE_FILE.exists(),
        "patch_registry_exists": PATCH_REGISTRY_FILE.exists(),
        "no_last_error": not bool(str(last_error or "").strip()),
        "stability_known": str(last_stability_score or "").strip() not in ["", "нет"],
        "auto_verification_known": str(last_auto_verification_status or "").strip() not in ["", "нет"],
    }

    problems = []

    if not checks["git_ready"]:
        problems.append("Git has uncommitted changes.")

    if not checks["patch_registry_exists"]:
        problems.append("PatchRegistry file is missing.")

    if not checks["no_last_error"]:
        problems.append(f"last_error is set: {_short(last_error, 160)}")

    if not checks["stability_known"]:
        problems.append("No stability score recorded yet.")

    if not checks["auto_verification_known"]:
        problems.append("No auto verification run recorded yet.")

    status = "ok" if not problems else "attention"

    health = {
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "git_status": git_status,
        "provider_status": provider_status,
        "patch_registry_status": patch_status,
        "latest_report": _latest_report() or "нет",
        "last_report": get_value("last_report", "нет"),
        "last_stability_score": last_stability_score,
        "last_stability_report": get_value("last_stability_report", "нет"),
        "last_auto_verification_status": last_auto_verification_status,
        "last_auto_verification_score": get_value("last_auto_verification_score", "нет"),
        "last_auto_verification_report": get_value("last_auto_verification_report", "нет"),
        "last_patch_version": get_value("last_patch_version", "нет"),
        "last_patch_status": get_value("last_patch_status", "нет"),
        "last_relay_status": get_value("last_relay_diagnostics_status", "нет"),
        "last_relay_report": get_value("last_relay_diagnostics_report", "нет"),
        "last_browser_action": get_value("last_browser_action", "нет"),
        "last_browser_report": (
            get_value("last_browser_autopilot_report", "")
            or get_value("last_browser_workflow_report", "")
            or get_value("last_browser_task_report", "")
            or "нет"
        ),
        "last_error": last_error or "нет",
        "checks": checks,
        "problems": problems,
        "recommended_checks": [
            "auto verify",
            "auto verify full",
            "status",
            "help",
        ],
    }

    set_value("last_project_health_status", status)
    set_value("last_project_health_generated_at", health["generated_at"])

    return health


def format_project_health_text(health=None):
    health = health or get_project_health()
    lines = [
        "Project Health Center:",
        f"- status: {health.get('status')}",
        f"- generated_at: {health.get('generated_at')}",
        f"- git: {health.get('git_status')}",
        f"- provider: {health.get('provider_status')}",
        f"- patch_registry: {health.get('patch_registry_status')}",
        f"- last_patch: {health.get('last_patch_version')} | {health.get('last_patch_status')}",
        f"- relay: {health.get('last_relay_status')}",
        f"- stability: {health.get('last_stability_score')} | {health.get('last_stability_report')}",
        f"- auto_verification: {health.get('last_auto_verification_status')} | {health.get('last_auto_verification_score')} | {health.get('last_auto_verification_report')}",
        f"- latest_report: {health.get('latest_report')}",
        f"- browser_report: {health.get('last_browser_report')}",
        f"- last_error: {_short(health.get('last_error'), 320)}",
        "",
        "Checks:",
    ]

    for key, value in health.get("checks", {}).items():
        lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("Problems:")

    problems = health.get("problems") or []

    if problems:
        for problem in problems:
            lines.append(f"- {problem}")
    else:
        lines.append("- Не обнаружены.")

    lines.append("")
    lines.append("Recommended before commit:")

    for command in health.get("recommended_checks", []):
        lines.append(f"- {command}")

    return "\n".join(lines)


def write_project_health_report(health=None):
    health = health or get_project_health()
    HEALTH_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = HEALTH_REPORTS_DIR / f"project_health_{_stamp()}.md"
    text = "# Project Health Center\n\n" + format_project_health_text(health)
    path.write_text(text, encoding="utf-8")
    set_value("last_project_health_report", str(path))
    set_value("last_project_health_status", health.get("status", "unknown"))
    return path


def latest_project_health_report():
    if not HEALTH_REPORTS_DIR.exists():
        return None

    reports = [path for path in HEALTH_REPORTS_DIR.glob("project_health_*.md") if path.is_file()]

    if not reports:
        return None

    return max(reports, key=lambda path: path.stat().st_mtime)
