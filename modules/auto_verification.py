import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from time import perf_counter

from core.state import set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
AUTO_VERIFY_REPORTS_DIR = REPORTS_DIR / "auto_verification"

KEY_PY_FILES = [
    "LocalComet_Control_Panel.py",
    "next/app_v5.py",
    "core/router.py",
    "core/planner.py",
    "core/executor.py",
    "core/llm.py",
    "agents/system_agent.py",
    "agents/browser_agent.py",
    "agents/stability_agent.py",
    "agents/automation_agent.py",
    "modules/auto_verification.py",
    "modules/browser_super.py",
    "modules/browser_direct.py",
    "modules/natural_command_intents.py",
    "modules/project_health.py",
    "modules/regression_commands.py",
    "modules/stability_test.py",
    "modules/automation_center.py",
]


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value, limit=2200):
    text = str(value or "")

    if len(text) <= limit:
        return text

    return text[:limit] + "\n...[обрезано]"


def _run_step(name, runner, checker=None):
    started = perf_counter()

    try:
        output = str(runner())
        ok = bool(checker(output)) if checker else bool(output.strip())
        error = ""
    except Exception:
        output = ""
        ok = False
        error = traceback.format_exc()

    return {
        "name": name,
        "ok": ok,
        "duration_sec": round(perf_counter() - started, 3),
        "output": _short(output),
        "error": _short(error),
    }


def _git_changed_python_files():
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return []

    files = []

    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        path = line[3:].strip() if len(line) > 3 else line

        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()

        path = path.strip('"')

        if path.endswith(".py") and (ROOT_DIR / path).exists():
            files.append(path.replace("\\", "/"))

    return files


def _unique_existing(files):
    seen = set()
    result = []

    for path in files:
        normalized = str(path).replace("\\", "/")

        if normalized in seen:
            continue

        if (ROOT_DIR / normalized).exists():
            seen.add(normalized)
            result.append(normalized)

    return result


def get_auto_verification_files():
    return _unique_existing([*_git_changed_python_files(), *KEY_PY_FILES])


def _run_py_compile():
    files = get_auto_verification_files()

    if not files:
        return "Нет Python-файлов для py_compile."

    result = subprocess.run(
        ["python", "-m", "py_compile", *files],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )

    return (
        f"CODE: {result.returncode}\n"
        f"FILES: {len(files)}\n"
        + "\n".join(f"- {path}" for path in files)
        + f"\n\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def _run_lmstudio_diagnostics():
    from modules.diagnostics import check_lmstudio

    return check_lmstudio()


def _run_model_smoke():
    from core.llm import ask_llm

    answer = ask_llm(
        "Ты тестовый ассистент LocalComet.",
        "Ответь ровно одним словом: OK",
        max_tokens=50,
        timeout=90,
    )
    return repr(answer)


def _run_project_health():
    from modules.project_health import format_project_health_text

    return format_project_health_text()


def _run_regression_suite():
    from modules.regression_commands import format_regression_command_suite, run_regression_command_suite

    suite = run_regression_command_suite(write_report=False)
    return format_regression_command_suite(suite)


def _run_stability(mode):
    from modules.stability_test import run_auto_stability_test, run_fast_stability_test

    if mode == "full":
        return run_auto_stability_test()

    return run_fast_stability_test()


def run_auto_verification(mode="quick", write_report=True):
    mode = str(mode or "quick").strip().lower()

    if mode not in ["smoke", "quick", "full", "post_patch"]:
        mode = "quick"

    steps = [
        _run_step("py_compile", _run_py_compile, lambda r: "CODE: 0" in r),
    ]

    if mode != "smoke":
        steps.extend([
            _run_step("lmstudio diagnostics", _run_lmstudio_diagnostics, lambda r: "текущая модель" in r and "доступна" in r),
            _run_step("model smoke", _run_model_smoke, lambda r: "OK" in r),
            _run_step("project health", _run_project_health, lambda r: "Project Health Center:" in r),
            _run_step("regression suite", _run_regression_suite, lambda r: "status: ok" in r and "Problems:" in r),
        ])

    if mode in ["full", "post_patch"]:
        stability_mode = "full"
        steps.append(
            _run_step(
                f"{stability_mode} stability",
                lambda: _run_stability(stability_mode),
                lambda r: "Проблемы:\n- Не обнаружены." in r,
            )
        )

    passed = sum(1 for step in steps if step["ok"])
    total = len(steps)
    status = "ok" if passed == total else "failed"

    result = {
        "status": status,
        "mode": mode,
        "passed": passed,
        "total": total,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "steps": steps,
        "report": "",
    }

    if write_report:
        result["report"] = str(write_auto_verification_report(result))

    set_value("last_auto_verification_status", status)
    set_value("last_auto_verification_score", f"{passed}/{total}")
    set_value("last_auto_verification_mode", mode)
    set_value("last_auto_verification_generated_at", result["generated_at"])
    set_value("last_auto_verification_report", result.get("report", ""))

    return result


def format_auto_verification(result=None):
    result = result or run_auto_verification(write_report=False)

    lines = [
        "Auto Verification:",
        f"- status: {result.get('status')}",
        f"- mode: {result.get('mode')}",
        f"- score: {result.get('passed')}/{result.get('total')}",
        f"- generated_at: {result.get('generated_at')}",
    ]

    if result.get("report"):
        lines.append(f"- report: {result.get('report')}")

    lines.extend(["", "Checks:"])

    for step in result.get("steps", []):
        mark = "OK" if step.get("ok") else "FAIL"
        lines.append(f"- [{mark}] {step.get('name')} | {step.get('duration_sec')}s")

        if step.get("error"):
            lines.append(f"  error: {_short(step.get('error'), 300)}")

    problems = [step for step in result.get("steps", []) if not step.get("ok")]
    lines.extend(["", "Problems:"])

    if problems:
        for step in problems:
            lines.append(f"- {step.get('name')}")
    else:
        lines.append("- Не обнаружены.")

    return "\n".join(lines)


def write_auto_verification_report(result=None):
    result = result or run_auto_verification(write_report=False)
    AUTO_VERIFY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = AUTO_VERIFY_REPORTS_DIR / f"auto_verification_{_stamp()}.md"

    lines = ["# Auto Verification", "", format_auto_verification(result), ""]

    for step in result.get("steps", []):
        mark = "OK" if step.get("ok") else "FAIL"
        lines.extend([
            f"## [{mark}] {step.get('name')}",
            "",
            f"- duration_sec: {step.get('duration_sec')}",
            "",
            "```text",
            step.get("output", "") or step.get("error", ""),
            "```",
            "",
        ])

    path.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_auto_verification_report", str(path))
    return path


def latest_auto_verification_report():
    if not AUTO_VERIFY_REPORTS_DIR.exists():
        return None

    reports = [
        path
        for path in AUTO_VERIFY_REPORTS_DIR.glob("auto_verification_*.md")
        if path.is_file()
    ]

    if not reports:
        return None

    return max(reports, key=lambda path: path.stat().st_mtime)
