import subprocess
from pathlib import Path
from modules.project_paths import get_project_root


ROOT_DIR = get_project_root()


def _run_git(args):
    result = subprocess.run(
        ["git"] + list(args),
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=10,
    )

    return result.returncode, result.stdout.strip(), result.stderr.strip()


def git_status():
    code, stdout, stderr = _run_git(["rev-parse", "--is-inside-work-tree"])

    if code != 0 or stdout.lower() != "true":
        return {
            "state": "no repo",
            "branch": "",
            "last_commit": "",
            "dirty": False,
            "error": stderr or stdout or "not a git repository",
        }

    _, branch, _ = _run_git(["branch", "--show-current"])
    _, short_status, _ = _run_git(["status", "--short"])
    _, last_commit, _ = _run_git(["log", "-1", "--pretty=%h %s"])

    dirty = bool(short_status.strip())

    return {
        "state": "dirty" if dirty else "clean",
        "branch": branch or "unknown",
        "last_commit": last_commit or "unknown",
        "dirty": dirty,
        "error": "",
    }


def short_status():
    status = git_status()

    if status["state"] == "no repo":
        return "Git: no repo"

    return f"Git: {status['state']} | {status['branch']} | {status['last_commit']}"
