import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value
from modules import pc_control_core as pc_control


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
PC_AGENT_DIR = PROJECTS_DIR / "PCAgent"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "pc_agent"
STATE_PATH = PC_AGENT_DIR / "pc_agent_state.json"
GRIMOIRE_RESPONSE_PATH = PC_AGENT_DIR / "grimoire_response.md"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs():
    PC_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _default_state():
    return {
        "enabled": False,
        "goal": "",
        "current_step": "",
        "last_action": "",
        "last_status": "",
        "last_error": "",
        "last_report": "",
        "ask_grimoire": False,
        "confirmed": False,
        "dry_run": True,
        "stopped_at": "",
        "created_at": "",
    }


def _load_state():
    _ensure_dirs()
    state = _default_state()

    if STATE_PATH.exists():
        try:
            loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except Exception:
            pass

    return state


def _save_state(state):
    _ensure_dirs()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def _write_report(action, payload):
    _ensure_dirs()
    path = REPORTS_DIR / f"pc_agent_{action}_{_stamp()}.md"
    lines = [
        "# PC Agent Report",
        "",
        f"- action: {action}",
        f"- created_at: {_now()}",
        f"- status: {payload.get('status') or payload.get('last_status') or 'unknown'}",
        f"- goal: {payload.get('goal') or 'нет'}",
        "",
        "## Payload",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")

    try:
        set_value("last_pc_agent_report", str(path))
    except Exception:
        pass

    return str(path)


def latest_pc_agent_report():
    if not REPORTS_DIR.exists():
        return ""

    reports = sorted(REPORTS_DIR.glob("pc_agent_*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    return str(reports[0]) if reports else ""


def _update_state(**values):
    state = _load_state()
    state.update(values)
    _save_state(state)
    return state


def _blocked_goal_markers(goal):
    return pc_control.hard_block_reasons(goal)


def _command_for_goal(goal):
    lower = str(goal or "").lower()

    if "git status" in lower or "статус git" in lower:
        return "git status --short"
    if "git log" in lower or "последние коммит" in lower:
        return "git log -5 --oneline"
    if "diff stat" in lower or "diff --stat" in lower or "статистик" in lower:
        return "git diff --stat"
    if "compile pc agent" in lower or "py_compile pc_agent" in lower:
        return "python -m py_compile modules\\pc_agent_core.py"
    if "compile pc control" in lower or "py_compile pc_control" in lower:
        return "python -m py_compile modules\\pc_control_core.py"

    return ""


def _path_for_goal(goal):
    text = str(goal or "").strip()
    lower = text.lower()

    if "open pc agent reports" in lower or "открой pc agent reports" in lower:
        return str(REPORTS_DIR)
    if "open reports folder" in lower or "открой папку отчет" in lower or "открой отчеты" in lower:
        return str(PROJECTS_DIR / "Reports")
    if "open project folder" in lower or "открой папку проекта" in lower:
        return str(ROOT_DIR)

    prefixes = (
        "open safe project file ",
        "open project file ",
        "открой файл проекта ",
    )
    for prefix in prefixes:
        if lower.startswith(prefix):
            candidate = text[len(prefix):].strip(" :\"'")
            if not candidate:
                return ""
            candidate_path = Path(candidate)
            return str(candidate_path if candidate_path.is_absolute() else ROOT_DIR / candidate_path)

    return ""


def _next_action_for_plan(plan):
    if plan.get("status") == "blocked":
        return "Stop and ask the user for a safe non-destructive goal."

    action = plan.get("recommended_action") or {}
    if action.get("type") == "run_command":
        return f"Run allowlisted command: {action.get('command')}"
    if action.get("type") == "open_path":
        return f"Open safe LocalAgent path: {action.get('path')}"
    if action.get("type") == "ask_grimoire":
        return "Ask Grimoire through ChatGPT Desktop if send is explicitly enabled."

    return "Review the plan, then run a dry-run step or confirmed step."


def pc_agent_status():
    state = _load_state()
    payload = {
        "ok": True,
        "status": "ok",
        "state_path": str(STATE_PATH),
        "reports_dir": str(REPORTS_DIR),
        "latest_report": latest_pc_agent_report(),
        **state,
    }
    report = _write_report("status", payload)
    payload["report_path"] = report
    _update_state(last_action="status", last_status="ok", last_error="", last_report=report)
    return payload


def pc_agent_observe():
    result = pc_control.observe_pc()
    payload = {
        "ok": True,
        "status": "ok",
        "goal": "",
        "current_step": "observe",
        "observation": result,
    }
    report = _write_report("observe", payload)
    payload["report_path"] = report
    _update_state(current_step="observe", last_action="observe", last_status="ok", last_error="", last_report=report)
    return payload


def pc_agent_plan(goal, ask_grimoire=False):
    goal = str(goal or "").strip()
    blocked = _blocked_goal_markers(goal)
    command = _command_for_goal(goal)
    path = _path_for_goal(goal)
    path_check = {}
    path_block_reason = ""

    if path:
        path_ok, resolved_path, reason = pc_control.is_safe_project_path(path)
        path_check = {
            "ok": bool(path_ok),
            "resolved_path": str(resolved_path or ""),
            "reason": reason,
        }
        if not path_ok:
            path_block_reason = reason

    observation = pc_control.observe_pc()

    status = "blocked" if blocked or path_block_reason else "planned"
    recommended_action = {"type": "none"}

    if blocked or path_block_reason:
        steps = [
            "Stop: goal contains hard-blocked markers or an unsafe path.",
            "Do not run commands, click, type, send, submit, or open sensitive paths.",
            "Ask the user for a narrower safe task.",
        ]
        if path_block_reason:
            steps.insert(1, f"Unsafe path reason: {path_block_reason}")
    else:
        steps = [
            "Observe the current desktop/project state.",
            "Keep all actions inside the LocalAgent workspace and explicit allowlists.",
        ]

        if command:
            recommended_action = {"type": "run_command", "command": command}
            steps.append(f"Dry-run the allowlisted command: {command}")
            steps.append("If confirmed=True and dry_run=False, execute it from the LocalAgent root.")
        elif path:
            recommended_action = {"type": "open_path", "path": path}
            steps.append(f"Dry-run opening the safe LocalAgent path: {path}")
            steps.append("If confirmed=True and dry_run=False, open it through the OS shell.")
        elif ask_grimoire:
            recommended_action = {"type": "ask_grimoire"}
            steps.append("Prepare a concise Grimoire request through ChatGPT Desktop.")
        else:
            steps.append("No direct allowlisted action matched; produce a report and wait for a safer explicit step.")

    plan = {
        "ok": not blocked,
        "status": status,
        "goal": goal,
        "ask_grimoire": bool(ask_grimoire),
        "blocked_markers": blocked,
        "path_check": path_check,
        "recommended_action": recommended_action,
        "steps": steps,
        "observation": observation,
        "next_recommended_action": "",
    }
    plan["next_recommended_action"] = _next_action_for_plan(plan)
    report = _write_report("plan", plan)
    plan["report_path"] = report
    _update_state(
        goal=goal,
        current_step="plan",
        last_action="plan",
        last_status=status,
        last_error="" if status != "blocked" else path_block_reason or "blocked goal",
        last_report=report,
        ask_grimoire=bool(ask_grimoire),
    )
    return plan


def pc_agent_run_command(command, confirmed=False, dry_run=True):
    result = pc_control.run_allowed_command(command, confirmed=confirmed, dry_run=dry_run)
    payload = {
        "status": "ok" if result.get("ok") else "blocked_or_failed",
        "current_step": "act",
        "action": "run_command",
        "result": result,
    }
    report = _write_report("run_command", payload)
    payload["report_path"] = report
    _update_state(
        current_step="act",
        last_action="run_command",
        last_status=payload["status"],
        last_error="" if result.get("ok") else result.get("message", ""),
        last_report=report,
        confirmed=bool(confirmed),
        dry_run=bool(dry_run),
    )
    return payload


def pc_agent_open_path(path, confirmed=False, dry_run=True):
    result = pc_control.open_safe_path(path, confirmed=confirmed, dry_run=dry_run)
    payload = {
        "status": "ok" if result.get("ok") else "blocked_or_failed",
        "current_step": "act",
        "action": "open_path",
        "result": result,
    }
    report = _write_report("open_path", payload)
    payload["report_path"] = report
    _update_state(last_action="open_path", last_status=payload["status"], last_error="" if result.get("ok") else result.get("message", ""), last_report=report)
    return payload


def pc_agent_clipboard_set(text, confirmed=False, dry_run=True):
    result = pc_control.set_clipboard_text(text, confirmed=confirmed, dry_run=dry_run)
    payload = {
        "status": "ok" if result.get("ok") else "blocked_or_failed",
        "current_step": "act",
        "action": "clipboard_set",
        "result": result,
    }
    report = _write_report("clipboard_set", payload)
    payload["report_path"] = report
    _update_state(last_action="clipboard_set", last_status=payload["status"], last_error="" if result.get("ok") else result.get("message", ""), last_report=report)
    return payload


def _grimoire_prompt(goal):
    return (
        "# LocalComet PC Agent Request\n\n"
        "You are Grimoire, architect for LocalComet. Return one small safe patch plan or code instruction set.\n\n"
        "## Goal\n"
        f"{str(goal or '').strip() or 'нет'}\n\n"
        "## Local Contract\n"
        "- Codex is the local operator: it can inspect files, apply patches, run checks, and commit.\n"
        "- Prefer one focused change in allowed files only.\n"
        "- If code changes are needed, give exact file paths and exact edit instructions or a valid response.json patch.\n"
        "- If no code change is needed, give one safe verification or operating step.\n\n"
        "## Allowed Files\n"
        "- modules/pc_agent_core.py\n"
        "- modules/pc_control_core.py\n"
        "- modules/chatgpt_desktop_bridge.py\n"
        "- modules/desktop_action_planner.py\n"
        "- LocalComet_Control_Panel.py\n"
        "- Projects/PCAgent/* runtime state\n"
        "- Projects/Reports/pc_agent/* reports\n\n"
        "## Stop Conditions\n"
        "- Do not delete files.\n"
        "- Do not read secrets, tokens, private keys, browser profiles, or env files.\n"
        "- Do not submit forms, send messages to people, install software, or change system settings.\n"
        "- Do not ask for arbitrary shell execution.\n\n"
        "## Required\n"
        "- Decision\n"
        "- Risk level\n"
        "- Exact safe local actions for Codex\n"
        "- Files to edit\n"
        "- Tests to run\n"
        "- Stop conditions\n"
        "- Expected commit message\n"
    )


def pc_agent_ask_grimoire(goal, send=False, dry_run=True):
    from modules.chatgpt_desktop_bridge import is_chatgpt_desktop_send_allowed, paste_prompt_after_input_focus

    goal = str(goal or "").strip()
    blocked = _blocked_goal_markers(goal)

    payload = {
        "status": "blocked" if blocked else "planned",
        "goal": goal,
        "send": bool(send),
        "dry_run": bool(dry_run),
        "blocked_markers": blocked,
    }

    if blocked:
        payload["ok"] = False
        payload["message"] = "STOP: Grimoire request contains hard-blocked markers."
    else:
        allowed = is_chatgpt_desktop_send_allowed()
        payload["send_allowed"] = allowed

        if send and not allowed.get("allowed"):
            payload["ok"] = False
            payload["status"] = "blocked"
            payload["message"] = allowed.get("message", "STOP: ChatGPT Desktop send blocked.")
        else:
            prompt = _grimoire_prompt(goal)
            result = paste_prompt_after_input_focus(prompt, send=bool(send), dry_run=bool(dry_run))
            payload["ok"] = bool(result.get("ok"))
            payload["status"] = "ok" if result.get("ok") else "blocked_or_failed"
            payload["message"] = result.get("message", "")
            payload["bridge_result"] = result

    report = _write_report("ask_grimoire", payload)
    payload["report_path"] = report
    _update_state(goal=goal, current_step="ask_grimoire", last_action="ask_grimoire", last_status=payload["status"], last_error="" if payload.get("ok") else payload.get("message", ""), last_report=report, ask_grimoire=True, dry_run=bool(dry_run))
    return payload


def pc_agent_ask_grimoire_verified(goal, send=False, dry_run=True):
    from modules.chatgpt_desktop_bridge import get_clipboard_text, verify_chatgpt_desktop_send_state

    prompt = _grimoire_prompt(goal)
    result = pc_agent_ask_grimoire(goal, send=send, dry_run=dry_run)
    after_clipboard = get_clipboard_text()
    bridge_result = result.get("bridge_result") if isinstance(result.get("bridge_result"), dict) else result
    verification = verify_chatgpt_desktop_send_state(
        before_clipboard=prompt,
        after_clipboard=after_clipboard,
        send_result=bridge_result,
    )

    payload = {
        "ok": bool(result.get("ok")) and (not send or bool(verification.get("likely_sent"))),
        "status": "ok" if bool(result.get("ok")) and not verification.get("needs_manual_check") else "manual_check_needed",
        "goal": str(goal or "").strip(),
        "send": bool(send),
        "dry_run": bool(dry_run),
        "ask_result": result,
        "verification": verification,
        "message": verification.get("message", ""),
    }
    report = _write_report("ask_grimoire_verified", payload)
    payload["report_path"] = report
    _update_state(goal=goal, current_step="ask_grimoire_verified", last_action="ask_grimoire_verified", last_status=payload["status"], last_error="" if payload["ok"] else payload["message"], last_report=report, ask_grimoire=True, dry_run=bool(dry_run))
    return payload


def pc_agent_capture_grimoire_response():
    from modules.chatgpt_desktop_bridge import get_clipboard_text

    text = get_clipboard_text()
    text_stripped = str(text or "").strip()
    looks_like_own_request = (
        "# LocalComet PC Agent Request" in text_stripped
        and "## Local Contract" in text_stripped
    )
    payload = {
        "ok": bool(text_stripped) and not looks_like_own_request,
        "status": "ok" if text_stripped and not looks_like_own_request else "blocked_or_failed",
        "response_chars": len(text or ""),
        "response_path": str(GRIMOIRE_RESPONSE_PATH),
        "looks_like_own_request": looks_like_own_request,
    }

    if payload["ok"]:
        _ensure_dirs()
        GRIMOIRE_RESPONSE_PATH.write_text(text, encoding="utf-8")
        payload["message"] = "Grimoire response captured from clipboard."
    elif looks_like_own_request:
        payload["message"] = "STOP: clipboard still contains the PC Agent request, not a Grimoire response."
    else:
        payload["message"] = "STOP: clipboard is empty; no Grimoire response captured."

    report = _write_report("capture_grimoire", payload)
    payload["report_path"] = report
    _update_state(current_step="capture_grimoire", last_action="capture_grimoire", last_status=payload["status"], last_error="" if payload["ok"] else payload["message"], last_report=report)
    return payload


def pc_agent_step(goal, confirmed=False, dry_run=True, ask_grimoire=False):
    goal = str(goal or "").strip()
    result = {
        "ok": False,
        "status": "started",
        "goal": goal,
        "confirmed": bool(confirmed),
        "dry_run": bool(dry_run),
        "ask_grimoire": bool(ask_grimoire),
        "flow": ["observe", "decide", "act", "verify", "report", "next"],
    }

    observation = pc_agent_observe()
    result["observe"] = observation
    plan = pc_agent_plan(goal, ask_grimoire=ask_grimoire)
    result["plan"] = plan

    if plan.get("status") == "blocked":
        result["status"] = "blocked"
        result["message"] = "STOP: PC Agent plan blocked by hard safety guard."
    elif ask_grimoire:
        result["act"] = pc_agent_ask_grimoire(goal, send=False, dry_run=dry_run)
        result["status"] = "ok" if result["act"].get("ok") else "blocked_or_failed"
        result["message"] = "Grimoire request prepared." if result["act"].get("ok") else result["act"].get("message", "")
    else:
        action = plan.get("recommended_action") or {}
        if action.get("type") == "run_command":
            result["act"] = pc_agent_run_command(action.get("command"), confirmed=confirmed, dry_run=dry_run)
            result["status"] = "ok" if result["act"].get("result", {}).get("ok") else "blocked_or_failed"
            result["message"] = result["act"].get("result", {}).get("message", "")
        elif action.get("type") == "open_path":
            result["act"] = pc_agent_open_path(action.get("path"), confirmed=confirmed, dry_run=dry_run)
            result["status"] = "ok" if result["act"].get("result", {}).get("ok") else "blocked_or_failed"
            result["message"] = result["act"].get("result", {}).get("message", "")
        else:
            result["act"] = {"ok": True, "message": "No allowlisted action selected; report-only step."}
            result["status"] = "ok"
            result["message"] = "Report-only step completed."

    result["verify"] = {
        "ok": result["status"] == "ok",
        "checks": [
            "hard blocks checked",
            "command allowlist checked",
            "reports written",
        ],
    }
    result["next_recommended_action"] = _next_action_for_plan(plan)
    report = _write_report("step", result)
    result["report_path"] = report
    result["ok"] = result["status"] == "ok"
    _update_state(goal=goal, current_step="step", last_action="step", last_status=result["status"], last_error="" if result["ok"] else result.get("message", ""), last_report=report, confirmed=bool(confirmed), dry_run=bool(dry_run), ask_grimoire=bool(ask_grimoire))
    return result


def pc_agent_loop_step():
    state = _load_state()
    goal = str(state.get("goal") or "").strip()

    if not state.get("enabled"):
        payload = {"ok": False, "status": "blocked", "message": "STOP: PC Agent loop is not enabled.", "state": state}
    elif not goal:
        payload = {"ok": False, "status": "blocked", "message": "STOP: PC Agent loop has no goal.", "state": state}
    else:
        step = pc_agent_step(
            goal,
            confirmed=bool(state.get("confirmed")),
            dry_run=bool(state.get("dry_run", True)),
            ask_grimoire=bool(state.get("ask_grimoire")),
        )
        payload = {
            "ok": bool(step.get("ok")),
            "status": step.get("status", "unknown"),
            "message": "PC Agent loop step completed." if step.get("ok") else step.get("message", ""),
            "state": _load_state(),
            "step": step,
        }

    report = _write_report("loop_step", payload)
    payload["report_path"] = report
    _update_state(current_step="loop_step", last_action="loop_step", last_status=payload["status"], last_error="" if payload.get("ok") else payload.get("message", ""), last_report=report)
    return payload


def pc_agent_loop_start(goal, confirmed=False, ask_grimoire=False):
    state = _load_state()
    now = _now()
    state.update({
        "enabled": True,
        "goal": str(goal or "").strip(),
        "current_step": "loop_start",
        "last_action": "loop_start",
        "last_status": "ok",
        "last_error": "",
        "ask_grimoire": bool(ask_grimoire),
        "confirmed": bool(confirmed),
        "dry_run": not bool(confirmed),
        "stopped_at": "",
        "created_at": state.get("created_at") or now,
    })
    _save_state(state)
    first_step = pc_agent_loop_step()
    payload = {"ok": True, "message": "PC Agent loop enabled.", "state": _load_state(), "first_step": first_step}
    report = _write_report("loop_start", payload)
    payload["report_path"] = report
    _update_state(last_report=report)
    return payload


def pc_agent_loop_stop():
    state = _load_state()
    state.update({
        "enabled": False,
        "current_step": "loop_stop",
        "last_action": "loop_stop",
        "last_status": "ok",
        "last_error": "",
        "stopped_at": _now(),
    })
    _save_state(state)
    payload = {"ok": True, "message": "PC Agent loop stopped.", **state}
    report = _write_report("loop_stop", payload)
    payload["report_path"] = report
    _update_state(last_report=report)
    return payload


def pc_agent_loop_status():
    state = _load_state()
    payload = {
        "ok": True,
        "message": "PC Agent loop status.",
        "state_path": str(STATE_PATH),
        "latest_report": latest_pc_agent_report(),
        **state,
    }
    report = _write_report("loop_status", payload)
    payload["report_path"] = report
    _update_state(last_action="loop_status", last_status="ok", last_error="", last_report=report)
    return payload
