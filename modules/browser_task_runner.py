from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from modules import browser_actions
from modules.browser import open_url, read_page, search
from core.state import set_value


ROOT_DIR = get_project_root()
TASK_REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "browser_tasks"
WORKFLOW_REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "browser_workflows"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dir():
    TASK_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    WORKFLOW_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _run_step(step):
    action = str(step.get("action", "") or "").strip()
    args = step.get("args", {}) or {}

    if action == "open_url":
        return open_url(args.get("url", ""))

    if action == "search":
        return search(args.get("query", ""))

    if action in ["read", "read_page"]:
        return read_page()

    if action == "summarize":
        return browser_actions.summarize_page()

    if action == "click_text":
        return browser_actions.click_by_text(args.get("text", ""))

    if action == "fill_label":
        return browser_actions.fill_by_label(args.get("label", ""), args.get("value", ""))

    if action == "press_key":
        return browser_actions.press_key(args.get("key", "Enter"))

    if action == "wait":
        return browser_actions.wait_page(args.get("ms", 1000))

    if action == "screenshot":
        return browser_actions.screenshot_page()

    if action in ["open_first", "open_first_result", "click_first_link"]:
        return browser_actions.click_first_link()

    if action in ["links", "extract_links"]:
        return browser_actions.extract_links()

    if action in ["inputs", "extract_inputs"]:
        return browser_actions.extract_inputs()

    if action == "find_text":
        return browser_actions.find_text_on_page(args.get("text", ""))

    return f"Unknown browser step action: {action}"


def run_browser_steps(steps: list):
    _ensure_dir()
    started_at = datetime.now().isoformat(timespec="seconds")
    report_path = TASK_REPORTS_DIR / f"browser_task_{_stamp()}.md"

    lines = [
        "# Browser Task Report",
        "",
        f"- started_at: {started_at}",
        f"- steps: {len(steps or [])}",
        "",
    ]

    ok = True

    for index, step in enumerate(steps or [], start=1):
        lines.extend([
            f"## Step {index}: {step.get('action', 'unknown')}",
            "",
            "```text",
        ])

        try:
            result = _run_step(step)
            lines.append(str(result))

            if "STOP:" in str(result) or "failed" in str(result).lower() or "ошибка" in str(result).lower():
                ok = False
                lines.append("STOP: step failed, sequence stopped.")
                lines.append("```")
                break

        except Exception as e:
            ok = False
            lines.append(f"ERROR: {e}")
            lines.append("```")
            break

        lines.append("```")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_browser_task_report", str(report_path))

    status = "ok" if ok else "failed"
    return f"Browser sequence {status}.\nReport: {report_path}"


def run_browser_workflow(steps: list, title: str = "browser workflow"):
    _ensure_dir()
    started_at = datetime.now().isoformat(timespec="seconds")
    report_path = WORKFLOW_REPORTS_DIR / f"browser_workflow_{_stamp()}.md"

    lines = [
        f"# Browser Workflow Report: {title}",
        "",
        f"- started_at: {started_at}",
        f"- steps_count: {len(steps or [])}",
        "",
    ]

    ok = True
    error_msg = ""
    last_index = 0

    for index, step in enumerate(steps or [], start=1):
        last_index = index
        action = step.get("action", "unknown")
        args = step.get("args", {})
        lines.extend([
            f"## Step {index}: {action}",
            f"- args: {args}",
            "",
            "```text",
        ])

        try:
            result = _run_step(step)
            lines.append(str(result))

            if "STOP:" in str(result) or "failed" in str(result).lower() or "ошибка" in str(result).lower():
                ok = False
                error_msg = str(result)
                lines.append("STOP: step failed, workflow stopped.")
                lines.append("```")
                break

        except Exception as e:
            ok = False
            error_msg = str(e)
            lines.append(f"ERROR: {e}")
            lines.append("```")
            break

        lines.append("```")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")

    status = "success" if ok else "failed"
    set_value("last_browser_workflow_report", str(report_path))
    set_value("last_browser_workflow_status", status)

    if ok:
        return f"Browser workflow '{title}' completed successfully. Report: {report_path}"
    else:
        return f"Browser workflow '{title}' failed at step {last_index}. Error: {error_msg}. Report: {report_path}"

