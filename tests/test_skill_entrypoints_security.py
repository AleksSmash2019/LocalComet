import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = {
    "code-runner": ROOT / "modules/skills/installed/code-runner/entrypoint.py",
    "hf-model-ctl": ROOT / "modules/skills/installed/hf-model-ctl/entrypoint.py",
    "git-ops": ROOT / "modules/skills/installed/git-ops/entrypoint.py",
}


def run_entrypoint(name: str, *args: str) -> dict:
    completed = subprocess.run(
        [sys.executable, str(ENTRYPOINTS[name]), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return json.loads(completed.stdout)


def test_active_skill_entrypoints_do_not_use_shell_true():
    for path in ENTRYPOINTS.values():
        source = path.read_text(encoding="utf-8")
        assert "shell=True" not in source, path
        assert "shell=False" in source, path


def test_code_runner_rejects_arbitrary_shell_commands():
    result = run_entrypoint("code-runner", "shell", "echo", "blocked")
    assert "arbitrary shell commands are disabled" in result["error"]
    assert "echo" not in result["allowed_commands"]


def test_git_ops_rejects_unknown_modes():
    result = run_entrypoint("git-ops", "shell")
    assert result["error"].startswith("unknown mode:")
    assert result["allowed_modes"] == ["branch", "diff", "log", "status"]


def test_hf_model_control_handles_local_cache_without_shell():
    result = run_entrypoint("hf-model-ctl", "local_cache")
    assert "cache" in result
    assert isinstance(result["items"], list)


def test_active_skill_entrypoints_compile():
    for path in ENTRYPOINTS.values():
        completed = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr
