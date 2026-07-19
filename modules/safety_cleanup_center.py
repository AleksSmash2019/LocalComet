from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import re
import shutil
import subprocess
import traceback


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
SAFETY_REPORTS_DIR = REPORTS_DIR / "safety_cleanup"
SELF_EDIT_DIR = PROJECTS_DIR / "SelfEdit"
CLEANUP_QUARANTINE_DIR = PROJECTS_DIR / "CleanupQuarantine"

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "BrowserProfile",
    "VoiceModels",
    "Reports",
    "Logs",
    "LocalAgent_Backups",
}

SENSITIVE_NAME_PATTERNS = [
    ".env",
    "secret",
    "token",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "private_key",
    ".pem",
    ".key",
]

DANGEROUS_PATTERNS = [
    ("shell_true", re.compile(r"shell\s*=\s*True")),
    ("rmtree", re.compile(r"\bshutil\.rmtree\s*\(")),
    ("unlink", re.compile(r"\.unlink\s*\(")),
    ("remove", re.compile(r"\bos\.remove\s*\(")),
    ("rmdir", re.compile(r"\bos\.rmdir\s*\(")),
    ("pyautogui", re.compile(r"\bpyautogui\.")),
    ("subprocess_popen", re.compile(r"\bsubprocess\.Popen\s*\(")),
    ("subprocess_run", re.compile(r"\bsubprocess\.run\s*\(")),
    ("keyboard_enter", re.compile(r"press\s*\(\s*['\"]enter['\"]\s*\)|hotkey\s*\([^)]*enter")),
    ("clipboard_paste", re.compile(r"pyperclip\.paste|clipboard")),
]


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value, limit=2200):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[обрезано]"


def _is_excluded(path: Path):
    parts = set(path.parts)
    return bool(parts.intersection(EXCLUDED_DIR_NAMES))


def _safe_relative(path: Path):
    try:
        return str(path.relative_to(ROOT_DIR))
    except Exception:
        return str(path)


def _iter_project_files():
    for path in ROOT_DIR.rglob("*"):
        if _is_excluded(path):
            continue
        if path.is_file():
            yield path


def _file_size_mb(path: Path):
    try:
        return round(path.stat().st_size / (1024 * 1024), 3)
    except Exception:
        return 0.0


def _git_status():
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=25,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except Exception:
        return {"ok": False, "error": traceback.format_exc()}


def find_cleanup_candidates():
    candidates = []

    if (ROOT_DIR / ".git").exists():
        candidates.append({
            "kind": "archive_exclude",
            "path": ".git",
            "action": "exclude_from_audit_zip",
            "reason": "Git history is large and should not be uploaded inside audit archives.",
        })

    for folder_name in ["Reports", "Logs"]:
        folder = PROJECTS_DIR / folder_name
        if folder.exists():
            candidates.append({
                "kind": "runtime_artifacts",
                "path": _safe_relative(folder),
                "action": "keep_latest_or_exclude_from_zip",
                "reason": "Runtime reports/logs grow quickly and are not required in code patches.",
            })

    if SELF_EDIT_DIR.exists():
        patch_files = sorted(
            [p for p in SELF_EDIT_DIR.glob("patch_*.json") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        rollback_files = sorted(
            [p for p in SELF_EDIT_DIR.glob("rollback_*.json") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for index, path in enumerate(patch_files):
            candidates.append({
                "kind": "selfedit_patch",
                "path": _safe_relative(path),
                "action": "keep" if index < 10 else "quarantine",
                "reason": "Keep the latest 10 patch files; quarantine older patch history.",
                "size_mb": _file_size_mb(path),
            })

        for index, path in enumerate(rollback_files):
            candidates.append({
                "kind": "selfedit_rollback",
                "path": _safe_relative(path),
                "action": "keep" if index < 10 else "quarantine",
                "reason": "Keep the latest 10 rollback files; quarantine older rollback history.",
                "size_mb": _file_size_mb(path),
            })

    for path in _iter_project_files():
        name = path.name.lower()
        if any(pattern in name for pattern in SENSITIVE_NAME_PATTERNS):
            candidates.append({
                "kind": "sensitive_name",
                "path": _safe_relative(path),
                "action": "review_do_not_upload",
                "reason": "Filename looks sensitive. Review manually before sharing.",
                "size_mb": _file_size_mb(path),
            })

    return candidates


def find_dangerous_places():
    findings = []

    for path in _iter_project_files():
        if path.suffix.lower() not in {".py", ".ps1", ".bat", ".cmd"}:
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            for name, pattern in DANGEROUS_PATTERNS:
                if pattern.search(line):
                    findings.append({
                        "kind": name,
                        "path": _safe_relative(path),
                        "line": line_no,
                        "code": stripped[:260],
                        "severity": _severity_for_finding(name, path),
                        "recommendation": _recommendation_for_finding(name),
                    })

    return findings


def _severity_for_finding(kind, path):
    critical = {"shell_true", "rmtree", "unlink", "remove", "rmdir", "keyboard_enter"}
    if path.name == "agent.py":
        return "high"
    if kind in critical:
        return "high"
    if kind in {"pyautogui", "subprocess_popen", "subprocess_run"}:
        return "medium"
    return "low"


def _recommendation_for_finding(kind):
    recommendations = {
        "shell_true": "Replace shell=True with an allowlisted subprocess call.",
        "rmtree": "Do not delete directly; move to CleanupQuarantine or require explicit confirmation.",
        "unlink": "Do not delete directly; move to CleanupQuarantine or require explicit confirmation.",
        "remove": "Do not delete directly; move to CleanupQuarantine or require explicit confirmation.",
        "rmdir": "Do not delete directly; move to CleanupQuarantine or require explicit confirmation.",
        "pyautogui": "Keep behind safety guards; block payment/login/destructive actions.",
        "subprocess_popen": "Use allowlists and avoid shell=True.",
        "subprocess_run": "Use allowlists and timeouts.",
        "keyboard_enter": "Never press Enter automatically unless the workflow is explicitly safe.",
        "clipboard_paste": "Do not paste private data; log intent only.",
    }
    return recommendations.get(kind, "Review manually.")


def audit_project():
    files = list(_iter_project_files())
    python_files = [p for p in files if p.suffix.lower() == ".py"]
    html_files = [p for p in files if p.suffix.lower() == ".html"]
    md_files = [p for p in files if p.suffix.lower() == ".md"]

    large_files = sorted(
        [
            {
                "path": _safe_relative(path),
                "size_mb": _file_size_mb(path),
            }
            for path in files
            if _file_size_mb(path) >= 1
        ],
        key=lambda item: item["size_mb"],
        reverse=True,
    )[:30]

    dangerous = find_dangerous_places()
    cleanup = find_cleanup_candidates()

    payload = {
        "status": "attention" if dangerous or any(item.get("action") == "quarantine" for item in cleanup) else "ok",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT_DIR),
        "counts": {
            "files": len(files),
            "python": len(python_files),
            "html": len(html_files),
            "markdown": len(md_files),
        },
        "large_files": large_files,
        "cleanup_candidates": cleanup,
        "dangerous_places": dangerous,
        "git": _git_status(),
        "recommendations": [
            "Keep LocalComet_Control_Panel.py stable; move new features into modules when possible.",
            "Prefer quarantine over deletion for cleanup.",
            "Keep Voice disabled unless explicitly needed.",
            "Avoid shell=True and direct delete operations.",
            "Keep latest 10 SelfEdit patch/rollback files; quarantine older ones.",
        ],
    }
    return payload


def format_project_audit(payload):
    counts = payload.get("counts", {})
    cleanup = payload.get("cleanup_candidates", [])
    dangerous = payload.get("dangerous_places", [])
    large = payload.get("large_files", [])

    lines = [
        "Safety Cleanup Audit:",
        f"- status: {payload.get('status')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- root: {payload.get('root')}",
        "",
        "Файлы:",
        f"- total: {counts.get('files')}",
        f"- python: {counts.get('python')}",
        f"- html: {counts.get('html')}",
        f"- markdown: {counts.get('markdown')}",
        "",
        "Что можно почистить:",
    ]

    if cleanup:
        for item in cleanup[:35]:
            lines.append(f"- [{item.get('action')}] {item.get('path')} — {item.get('reason')}")
        if len(cleanup) > 35:
            lines.append(f"- ...и еще {len(cleanup) - 35} пунктов")
    else:
        lines.append("- Явных кандидатов нет.")

    lines.append("")
    lines.append("Опасные места:")

    if dangerous:
        for item in dangerous[:45]:
            lines.append(
                f"- [{item.get('severity')}] {item.get('path')}:{item.get('line')} "
                f"{item.get('kind')} — {item.get('recommendation')}"
            )
            lines.append(f"  {item.get('code')}")
        if len(dangerous) > 45:
            lines.append(f"- ...и еще {len(dangerous) - 45} мест")
    else:
        lines.append("- Не обнаружены.")

    lines.append("")
    lines.append("Большие файлы:")
    if large:
        for item in large[:15]:
            lines.append(f"- {item.get('size_mb')} MB — {item.get('path')}")
    else:
        lines.append("- Нет файлов больше 1 MB.")

    lines.append("")
    lines.append("Рекомендации:")
    for item in payload.get("recommendations", []):
        lines.append("- " + item)

    return "\n".join(lines)


def cleanup_old_selfedit_files(keep_latest=10, dry_run=False):
    keep_latest = max(1, int(keep_latest or 10))
    CLEANUP_QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    target_dir = CLEANUP_QUARANTINE_DIR / f"selfedit_{_stamp()}"
    actions = []

    if not SELF_EDIT_DIR.exists():
        return {
            "ok": True,
            "dry_run": dry_run,
            "moved": 0,
            "actions": [],
            "message": "SelfEdit folder not found.",
        }

    files = []
    files.extend(sorted(SELF_EDIT_DIR.glob("patch_*.json"), key=lambda p: p.stat().st_mtime, reverse=True))
    files.extend(sorted(SELF_EDIT_DIR.glob("rollback_*.json"), key=lambda p: p.stat().st_mtime, reverse=True))

    groups = {}
    for path in files:
        prefix = "patch" if path.name.startswith("patch_") else "rollback"
        groups.setdefault(prefix, []).append(path)

    to_move = []
    for group_files in groups.values():
        to_move.extend(group_files[keep_latest:])

    if to_move and not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    for path in to_move:
        dest = target_dir / path.name
        action = {
            "source": _safe_relative(path),
            "destination": _safe_relative(dest),
            "dry_run": dry_run,
            "size_mb": _file_size_mb(path),
        }

        if not dry_run:
            shutil.move(str(path), str(dest))

        actions.append(action)

    return {
        "ok": True,
        "dry_run": dry_run,
        "keep_latest": keep_latest,
        "moved": 0 if dry_run else len(actions),
        "would_move": len(actions) if dry_run else 0,
        "quarantine_dir": _safe_relative(target_dir) if to_move else "",
        "actions": actions,
    }


def create_cleanup_report(apply_cleanup=False, dry_run=True):
    SAFETY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    audit = audit_project()
    cleanup_result = cleanup_old_selfedit_files(keep_latest=10, dry_run=(dry_run or not apply_cleanup))

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "apply_cleanup": bool(apply_cleanup),
        "dry_run": bool(dry_run or not apply_cleanup),
        "audit": audit,
        "cleanup_result": cleanup_result,
    }

    stamp = _stamp()
    json_path = SAFETY_REPORTS_DIR / f"safety_cleanup_{stamp}.json"
    md_path = SAFETY_REPORTS_DIR / f"safety_cleanup_{stamp}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# LocalComet Safety Cleanup Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- apply_cleanup: {payload['apply_cleanup']}",
        f"- dry_run: {payload['dry_run']}",
        "",
        "## Audit",
        "",
        "```text",
        format_project_audit(audit),
        "```",
        "",
        "## SelfEdit cleanup",
        "",
        "```json",
        json.dumps(cleanup_result, ensure_ascii=False, indent=2),
        "```",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return {
        "ok": True,
        "report": str(md_path),
        "json": str(json_path),
        "status": audit.get("status"),
        "cleanup": cleanup_result,
        "dangerous_count": len(audit.get("dangerous_places", [])),
        "cleanup_candidates": len(audit.get("cleanup_candidates", [])),
    }


def format_cleanup_report_result(payload):
    lines = [
        "Safety Cleanup Report:",
        f"- ok: {payload.get('ok')}",
        f"- status: {payload.get('status')}",
        f"- report: {payload.get('report')}",
        f"- json: {payload.get('json')}",
        f"- dangerous_count: {payload.get('dangerous_count')}",
        f"- cleanup_candidates: {payload.get('cleanup_candidates')}",
        "",
        "SelfEdit cleanup:",
    ]

    cleanup = payload.get("cleanup", {})
    lines.append(f"- dry_run: {cleanup.get('dry_run')}")
    lines.append(f"- moved: {cleanup.get('moved')}")
    lines.append(f"- would_move: {cleanup.get('would_move')}")
    lines.append(f"- quarantine_dir: {cleanup.get('quarantine_dir')}")

    return "\n".join(lines)
