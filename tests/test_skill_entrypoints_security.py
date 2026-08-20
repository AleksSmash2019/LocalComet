import ast
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "modules" / "skills"
INSTALLED_ROOT = SKILLS_ROOT / "installed"
ENTRYPOINTS = {
    "code-runner": INSTALLED_ROOT / "code-runner" / "entrypoint.py",
    "hf-model-ctl": INSTALLED_ROOT / "hf-model-ctl" / "entrypoint.py",
    "git-ops": INSTALLED_ROOT / "git-ops" / "entrypoint.py",
}
ALL_ENTRYPOINTS = tuple(sorted(SKILLS_ROOT.rglob("entrypoint.py")))
LEGACY_TEST_SKILLS = {"demo-echo", "verify-echo-174869", "verify-echo-655999"}


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


def uses_shell_true(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    return True
    return False


def test_all_skill_entrypoints_reject_shell_execution():
    assert ALL_ENTRYPOINTS
    for path in ALL_ENTRYPOINTS:
        source = path.read_text(encoding="utf-8")
        assert not uses_shell_true(path), path
        if "subprocess.run(" in source:
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


def test_test_only_skills_are_disabled_in_bundled_registry():
    registry = json.loads((SKILLS_ROOT / "registry.json").read_text(encoding="utf-8"))
    assert LEGACY_TEST_SKILLS.issubset(registry)
    assert {registry[skill]["state"] for skill in LEGACY_TEST_SKILLS} == {"DISABLED"}


def test_all_skill_entrypoints_compile():
    for path in ALL_ENTRYPOINTS:
        completed = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr

