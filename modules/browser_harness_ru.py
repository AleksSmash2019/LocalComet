from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
import json
import re
import urllib.parse
import uuid

from modules.project_paths import computer_use_dir, computer_use_latest_ui_map_path, reports_dir


BROWSER_HARNESS_VERSION = "v6.50c"
BROWSER_HARNESS_NAME = "LocalComet Browser Harness RU"

BROWSER_HARNESS_DIR = computer_use_dir() / "browser_harness"
BROWSER_HARNESS_REPORT_DIR = reports_dir() / "browser_harness"

BLOCKED_BROWSER_PATTERNS = [
    ("destructive_delete", r"удали|удалить|сотри|стереть|\b(delete|remove|wipe|format|erase|rm\s+-rf|rmdir|del\s+|shutil\.rmtree|os\.remove)\b"),
    ("shell_terminal_admin", r"терминал|командн|админ|\b(shell|cmd|cmd\.exe|powershell|terminal|bash|zsh|sudo|admin|administrator)\b"),
    ("secrets_browser_profile", r"парол|токен|секрет|куки|cookies|профил[ья] браузера|browser\s*profile|\b(password|passwd|token|api\s*key|api-key|secret|private\s*key|ssh\s*key|cookie)\b"),
    ("banking_payment_gambling", r"банк|плат[её]ж|карта|казино|ставк|\b(bank|payment|credit\s*card|paypal|wallet|gambling|casino|betting)\b"),
    ("deploy_backend_install", r"\b(deploy|backend|docker|kubectl|helm|npm|pip\s+install)\b|деплой|бекенд|бэкенд"),
]

FILE_CHANGE_PATTERNS = [
    ("download", r"скачай|загрузи\s+с\s+сайта|download\b|save\s+as|сохранить\s+как"),
    ("upload_attach", r"загрузи\s+файл|прикрепи\s+файл|upload\b|attach\b|drop\s+file"),
    ("export_print", r"экспорт|export\b|print\s+to\s+pdf|печать\s+в\s+pdf"),
    ("browser_file_edit", r"создай\s+файл|измени\s+файл|редактируй\s+файл|write\s+file|edit\s+file|modify\s+file"),
]

EXECUTABLE_DOWNLOAD_PATTERN = r"\.(exe|msi|bat|cmd|ps1|scr|vbs|jar)(\b|[?&#])|запусти\s+скачан|run\s+download|execute\s+download"

URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", flags=re.IGNORECASE)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs() -> None:
    BROWSER_HARNESS_DIR.mkdir(parents=True, exist_ok=True)
    BROWSER_HARNESS_REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower().replace("ё", "е"))


def _matches(patterns: List[tuple[str, str]], text: str) -> List[Dict[str, str]]:
    value = str(text or "")
    problems: List[Dict[str, str]] = []
    for problem_type, pattern in patterns:
        if re.search(pattern, value, flags=re.IGNORECASE):
            problems.append({"type": problem_type, "reason": f"blocked marker: {problem_type}"})
    return problems


def _file_change_reasons(text: str) -> List[Dict[str, str]]:
    value = str(text or "")
    reasons: List[Dict[str, str]] = []
    for reason_type, pattern in FILE_CHANGE_PATTERNS:
        if re.search(pattern, value, flags=re.IGNORECASE):
            reasons.append({"type": reason_type, "reason": f"confirmation marker: {reason_type}"})
    return reasons


def redact_browser_text(text: str) -> str:
    value = str(text or "")
    try:
        from modules.computer_use_safety_ru import redact_text as core_redact
        value = core_redact(value)
    except Exception:
        pass
    replacements = [
        (r"(?i)(api[_\-\s]*key\s*[:=]\s*)[^\s&]+", r"\1[REDACTED_SECRET]"),
        (r"(?i)(token\s*[:=]\s*)[^\s&]+", r"\1[REDACTED_SECRET]"),
        (r"(?i)(password\s*[:=]\s*)[^\s&]+", r"\1[REDACTED_SECRET]"),
        (r"(?i)(cookie\s*[:=]\s*)[^\s&]+", r"\1[REDACTED_SECRET]"),
    ]
    for pattern, repl in replacements:
        value = re.sub(pattern, repl, value)
    return value


def _extract_url(goal: str) -> str:
    match = URL_PATTERN.search(str(goal or ""))
    if not match:
        return ""
    url = match.group(0).rstrip(".,;)")
    return url


def validate_browser_url(url: str) -> Dict[str, Any]:
    raw = str(url or "").strip()
    if not raw:
        return {"ok": False, "reason": "URL is empty.", "blocked": False}
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"}:
        return {"ok": False, "reason": "Only http and https URLs are allowed.", "blocked": True}
    if not parsed.netloc:
        return {"ok": False, "reason": "URL has no host.", "blocked": True}
    if parsed.username or parsed.password:
        return {"ok": False, "reason": "URL userinfo is sensitive and blocked.", "blocked": True}
    if re.search(EXECUTABLE_DOWNLOAD_PATTERN, raw, flags=re.IGNORECASE):
        return {"ok": False, "reason": "Executable download or execution marker is blocked.", "blocked": True}
    return {
        "ok": True,
        "scheme": parsed.scheme.lower(),
        "host": parsed.netloc.lower(),
        "redacted_url": redact_browser_text(raw),
        "blocked": False,
    }


def safety_check_browser_goal(goal: str) -> Dict[str, Any]:
    raw = str(goal or "").strip()
    redacted = redact_browser_text(raw)
    if not raw:
        return {
            "ok": False,
            "blocked": False,
            "requires_confirmation": False,
            "allowed_to_execute": False,
            "risk": "invalid",
            "reason": "Browser goal is empty.",
            "problem_types": [],
            "file_change_reasons": [],
        }

    core_result: Dict[str, Any] = {"ok": True, "blocked": False, "problem_types": []}
    try:
        from modules.computer_use_safety_ru import safety_check_goal as core_safety_check
        core_result = core_safety_check(raw)
    except Exception as exc:
        core_result = {
            "ok": True,
            "blocked": False,
            "problem_types": [],
            "reason": f"core safety unavailable: {exc}",
        }

    blocked = _matches(BLOCKED_BROWSER_PATTERNS, raw)
    if not core_result.get("ok") or core_result.get("blocked"):
        for problem_type in core_result.get("problem_types", []):
            blocked.append({"type": str(problem_type), "reason": f"core safety marker: {problem_type}"})

    url = _extract_url(raw)
    url_check = validate_browser_url(url) if url else {"ok": True, "blocked": False}
    if url and not url_check.get("ok") and url_check.get("blocked"):
        blocked.append({"type": "unsafe_url", "reason": str(url_check.get("reason", "unsafe url"))})

    if re.search(EXECUTABLE_DOWNLOAD_PATTERN, raw, flags=re.IGNORECASE):
        blocked.append({"type": "executable_download", "reason": "Executable download or execution is blocked."})

    file_change_reasons = _file_change_reasons(raw)
    if blocked:
        return {
            "ok": False,
            "mode": "browser_harness_safety",
            "version": BROWSER_HARNESS_VERSION,
            "blocked": True,
            "requires_confirmation": True,
            "allowed_to_execute": False,
            "risk": "blocked",
            "reason": "; ".join(item["reason"] for item in blocked),
            "problem_types": [item["type"] for item in blocked],
            "file_change_reasons": file_change_reasons,
            "redacted_goal": redacted,
        }

    requires_confirmation = bool(file_change_reasons)
    return {
        "ok": True,
        "mode": "browser_harness_safety",
        "version": BROWSER_HARNESS_VERSION,
        "blocked": False,
        "requires_confirmation": requires_confirmation,
        "allowed_to_execute": not requires_confirmation,
        "risk": "medium" if requires_confirmation else "low",
        "reason": "Browser goal is safe for one-step GUI planning." if not requires_confirmation else "Browser goal may change files and requires explicit confirmation.",
        "problem_types": [],
        "file_change_reasons": file_change_reasons,
        "redacted_goal": redacted,
        "url_check": url_check,
    }


def classify_browser_goal(goal: str) -> Dict[str, Any]:
    raw = str(goal or "").strip()
    lowered = _normalize(raw)
    url = _extract_url(raw)
    if url:
        url_check = validate_browser_url(url)
        return {
            "ok": bool(url_check.get("ok")),
            "mode": "browser_harness_task",
            "version": BROWSER_HARNESS_VERSION,
            "task_type": "navigate_url",
            "payload": url_check.get("redacted_url", redact_browser_text(url)),
            "target_description": "Адресная строка",
            "reason": url_check.get("reason", "navigate to URL"),
            "url_check": url_check,
        }

    search_prefixes = [
        "найди ",
        "поиск ",
        "поищи ",
        "search ",
        "find ",
        "google ",
        "гугл ",
        "открой поиск ",
    ]
    for prefix in search_prefixes:
        if lowered.startswith(prefix.strip()):
            payload = raw[len(prefix):].strip()
            break
    else:
        payload = raw

    if lowered.startswith(("нажми ", "кликни ", "click ")):
        for prefix in ("нажми ", "кликни ", "click "):
            if lowered.startswith(prefix.strip()):
                description = raw[len(prefix):].strip()
                return {
                    "ok": True,
                    "mode": "browser_harness_task",
                    "version": BROWSER_HARNESS_VERSION,
                    "task_type": "click_text",
                    "payload": "",
                    "target_description": description or "browser element",
                    "reason": "click browser UI element by visible text",
                }

    return {
        "ok": True,
        "mode": "browser_harness_task",
        "version": BROWSER_HARNESS_VERSION,
        "task_type": "search_or_address_text",
        "payload": redact_browser_text(payload),
        "target_description": "Поиск",
        "reason": "type safe browser query into grounded search or address field",
    }


def read_browser_ui_map() -> Dict[str, Any]:
    path = computer_use_latest_ui_map_path()
    payload = _read_json(path, {})
    elements = payload.get("elements") if isinstance(payload, dict) else []
    if not isinstance(elements, list):
        elements = []
    return {
        "ok": True,
        "mode": "browser_harness_ui_map",
        "version": BROWSER_HARNESS_VERSION,
        "ui_map_path": str(path),
        "element_count": len(elements),
        "has_elements": bool(elements),
        "source": payload.get("source", "") if isinstance(payload, dict) else "",
        "fixture_label": payload.get("fixture_label", "") if isinstance(payload, dict) else "",
    }


def observe_browser_context() -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "ok": True,
        "mode": "browser_harness_observe",
        "version": BROWSER_HARNESS_VERSION,
        "observation": {},
        "ui_map": read_browser_ui_map(),
        "limitations": [],
    }
    try:
        from modules.computer_use_core_ru import observe_screen
        observation = observe_screen()
        result["observation"] = observation if isinstance(observation, dict) else {"ok": False, "reason": "observe_screen returned non-dict"}
    except Exception as exc:
        result["limitations"].append(f"observe_screen unavailable: {exc}")
    return result


def _ground_browser_target(descriptions: List[str], kind: str, text: str) -> Dict[str, Any]:
    from modules.computer_use_grounding_ru import build_grounded_action

    attempts: List[Dict[str, Any]] = []
    for description in descriptions:
        grounded = build_grounded_action(description, kind=kind, text=text, min_confidence=0.25)
        attempts.append({
            "description": description,
            "ok": bool(grounded.get("ok")),
            "reason": grounded.get("reason", ""),
            "confidence": grounded.get("action", {}).get("confidence"),
        })
        if grounded.get("ok"):
            return {
                "ok": True,
                "action": grounded["action"],
                "grounding": grounded.get("grounding", {}),
                "attempts": attempts,
            }
    return {
        "ok": False,
        "reason": "No grounded browser target found.",
        "attempts": attempts,
    }


def _target_candidates(task: Dict[str, Any]) -> List[str]:
    target = str(task.get("target_description") or "").strip()
    task_type = str(task.get("task_type") or "")
    if task_type == "navigate_url":
        return [target, "Address bar", "Адрес", "Поиск", "Search"]
    if task_type == "click_text":
        return [target]
    return [target, "Поиск", "Search", "Адресная строка", "Address bar"]


def _build_action(task: Dict[str, Any], safety: Dict[str, Any]) -> Dict[str, Any]:
    task_type = str(task.get("task_type") or "")
    payload = str(task.get("payload") or "")
    modifies_files = bool(safety.get("requires_confirmation"))

    if task_type == "click_text":
        grounding = _ground_browser_target(_target_candidates(task), kind="click", text="")
    else:
        grounding = _ground_browser_target(_target_candidates(task), kind="type", text=payload)

    if not grounding.get("ok"):
        return {
            "kind": "ask_user",
            "message": "Нужен видимый браузер и заземлённая адресная строка, поле поиска или целевой элемент.",
            "grounded": False,
            "gui_only": True,
            "modifies_files": modifies_files,
            "requires_confirmation": modifies_files,
            "allowed_to_execute": False,
            "reason": grounding.get("reason", "No grounded browser target found."),
            "grounding": grounding,
        }

    action = dict(grounding["action"])
    action.update({
        "goal": task.get("payload") or task.get("target_description") or "",
        "gui_only": True,
        "modifies_files": modifies_files,
        "file_change_policy": "requires_explicit_modifies_files_true",
        "ui_intent": "browser_harness_one_step_gui",
        "browser_harness_version": BROWSER_HARNESS_VERSION,
        "requires_confirmation": modifies_files,
        "reason": "Browser Harness proposes exactly one grounded GUI action.",
    })

    if task_type == "click_text":
        action["kind"] = "click"
        action["text"] = ""

    return action


def plan_one_browser_action(goal: str, simulate: bool = True, observe_first: bool = False) -> Dict[str, Any]:
    _ensure_dirs()
    safety = safety_check_browser_goal(goal)
    if safety.get("blocked"):
        result = {
            "ok": False,
            "handled": True,
            "mode": "browser_harness_plan",
            "version": BROWSER_HARNESS_VERSION,
            "blocked": True,
            "requires_confirmation": True,
            "allowed_to_execute": False,
            "one_action": True,
            "goal": redact_browser_text(goal),
            "safety": safety,
            "reason": safety.get("reason"),
        }
        result["artifact"] = _write_json(BROWSER_HARNESS_DIR / f"browser_harness_blocked_{_stamp()}_{uuid.uuid4().hex[:6]}.json", result)
        return result

    observation = observe_browser_context() if observe_first else {"ok": True, "mode": "browser_harness_observe_skipped"}
    task = classify_browser_goal(goal)
    if not task.get("ok"):
        result = {
            "ok": False,
            "handled": True,
            "mode": "browser_harness_plan",
            "version": BROWSER_HARNESS_VERSION,
            "blocked": bool(task.get("url_check", {}).get("blocked")),
            "requires_confirmation": True,
            "allowed_to_execute": False,
            "one_action": True,
            "goal": redact_browser_text(goal),
            "safety": safety,
            "task": task,
            "reason": task.get("reason", "task classification failed"),
        }
        result["artifact"] = _write_json(BROWSER_HARNESS_DIR / f"browser_harness_invalid_{_stamp()}_{uuid.uuid4().hex[:6]}.json", result)
        return result

    action = _build_action(task, safety)
    try:
        from modules.computer_use_auto_action_ru import auto_policy_for_action
        policy = auto_policy_for_action(action) if action.get("kind") != "ask_user" else {
            "ok": True,
            "blocked": False,
            "allowed_to_execute": False,
            "requires_confirmation": bool(action.get("requires_confirmation")),
            "risk": "medium" if action.get("requires_confirmation") else "low",
            "reason": "Ask-user action is not auto-executed.",
        }
    except Exception as exc:
        policy = {
            "ok": True,
            "blocked": False,
            "allowed_to_execute": False,
            "requires_confirmation": bool(action.get("requires_confirmation")),
            "risk": "medium",
            "reason": f"auto policy unavailable: {exc}",
        }

    requires_confirmation = bool(safety.get("requires_confirmation") or action.get("requires_confirmation") or policy.get("requires_confirmation"))
    allowed_to_execute = bool(policy.get("allowed_to_execute")) and not requires_confirmation and action.get("kind") != "ask_user"

    result = {
        "ok": bool(policy.get("ok", True)) and not bool(policy.get("blocked")),
        "handled": True,
        "mode": "browser_harness_plan",
        "version": BROWSER_HARNESS_VERSION,
        "goal": redact_browser_text(goal),
        "simulate": bool(simulate),
        "one_action": True,
        "action_count": 1,
        "task": task,
        "action": action,
        "policy": policy,
        "safety": safety,
        "observation": observation,
        "requires_confirmation": requires_confirmation,
        "allowed_to_execute": allowed_to_execute,
        "blocked": bool(policy.get("blocked")),
        "next_step": "observe_after_action" if allowed_to_execute else ("ask_user_confirmation" if requires_confirmation else "ask_user_to_open_browser_or_focus_target"),
    }
    result["artifact"] = _write_json(BROWSER_HARNESS_DIR / f"browser_harness_plan_{_stamp()}_{uuid.uuid4().hex[:6]}.json", result)
    return result


def simulate_browser_step(goal: str) -> Dict[str, Any]:
    result = plan_one_browser_action(goal, simulate=True, observe_first=False)
    result["mode"] = "browser_harness_simulate"
    result["executed"] = False
    result["execution_reason"] = "simulation only; no browser automation was executed"
    return result


def _browser_fixture_ui_map() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "browser_harness_contract_ui_map",
        "version": BROWSER_HARNESS_VERSION,
        "source": "browser_harness_contract",
        "elements": [
            {
                "element_id": "browser_address_bar",
                "role": "textbox",
                "text": "Адресная строка",
                "bounds": {"x": 80, "y": 42, "w": 760, "h": 32},
                "confidence": 0.96,
                "source": "browser_harness_contract",
            },
            {
                "element_id": "browser_search_field",
                "role": "textbox",
                "text": "Поиск",
                "bounds": {"x": 120, "y": 180, "w": 620, "h": 44},
                "confidence": 0.94,
                "source": "browser_harness_contract",
            },
            {
                "element_id": "browser_result_link",
                "role": "link",
                "text": "Python Documentation",
                "bounds": {"x": 130, "y": 260, "w": 260, "h": 24},
                "confidence": 0.90,
                "source": "browser_harness_contract",
            },
        ],
        "limitations": [],
    }


@contextmanager
def _temporary_browser_ui_map(label: str) -> Iterator[Dict[str, Any]]:
    from modules.computer_use_test_fixtures_ru import temporary_latest_ui_map

    with temporary_latest_ui_map(_browser_fixture_ui_map(), label=label) as info:
        yield info


def _contract(name: str, ok: bool, result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "finished_at": _now(),
        "result": result,
    }


def run_browser_harness_contracts(write_report: bool = True) -> Dict[str, Any]:
    contracts: List[Dict[str, Any]] = []

    status_result = status()
    contracts.append(_contract(
        "status_ok",
        bool(status_result.get("ok")) and status_result.get("version") == BROWSER_HARNESS_VERSION,
        status_result,
    ))

    with _temporary_browser_ui_map("browser_harness_safe_search") as fixture:
        plan = plan_one_browser_action("найди Python documentation", simulate=True)
        contracts.append(_contract(
            "safe_search_proposes_one_grounded_type",
            bool(plan.get("ok"))
            and plan.get("one_action") is True
            and plan.get("action", {}).get("kind") == "type"
            and plan.get("action", {}).get("grounded") is True
            and not bool(plan.get("requires_confirmation"))
            and bool(plan.get("allowed_to_execute")),
            {"plan": plan, "fixture": fixture},
        ))

    with _temporary_browser_ui_map("browser_harness_safe_click") as fixture:
        plan = plan_one_browser_action("кликни Python Documentation", simulate=True)
        contracts.append(_contract(
            "safe_click_proposes_one_grounded_click",
            bool(plan.get("ok"))
            and plan.get("one_action") is True
            and plan.get("action", {}).get("kind") == "click"
            and plan.get("action", {}).get("grounded") is True
            and not bool(plan.get("requires_confirmation")),
            {"plan": plan, "fixture": fixture},
        ))

    with _temporary_browser_ui_map("browser_harness_file_change") as fixture:
        plan = plan_one_browser_action("скачай файл report.pdf", simulate=True)
        contracts.append(_contract(
            "browser_file_change_requires_confirmation",
            bool(plan.get("ok"))
            and bool(plan.get("requires_confirmation"))
            and not bool(plan.get("allowed_to_execute")),
            {"plan": plan, "fixture": fixture},
        ))

    blocked_shell = safety_check_browser_goal("открой powershell через браузер")
    contracts.append(_contract(
        "dangerous_shell_goal_blocked",
        not bool(blocked_shell.get("ok")) and bool(blocked_shell.get("blocked")),
        blocked_shell,
    ))

    blocked_profile = safety_check_browser_goal("прочитай browser profile cookies")
    contracts.append(_contract(
        "browser_profile_and_cookies_blocked",
        not bool(blocked_profile.get("ok")) and bool(blocked_profile.get("blocked")),
        blocked_profile,
    ))

    summary = {
        "passed": sum(1 for item in contracts if item.get("ok")),
        "total": len(contracts),
        "failed": sum(1 for item in contracts if not item.get("ok")),
    }
    payload = {
        "ok": summary["failed"] == 0,
        "handled": True,
        "mode": "browser_harness_contract_tests",
        "version": BROWSER_HARNESS_VERSION,
        "summary": summary,
        "contracts": contracts,
        "created_at": _now(),
    }
    if write_report:
        payload["report"] = _write_json(BROWSER_HARNESS_REPORT_DIR / f"browser_harness_contracts_{_stamp()}.json", payload)
    return payload


def status() -> Dict[str, Any]:
    _ensure_dirs()
    ui_map = read_browser_ui_map()
    return {
        "ok": True,
        "mode": "browser_harness_status",
        "version": BROWSER_HARNESS_VERSION,
        "name": BROWSER_HARNESS_NAME,
        "browser_harness_dir": str(BROWSER_HARNESS_DIR),
        "report_dir": str(BROWSER_HARNESS_REPORT_DIR),
        "ui_map": ui_map,
        "capabilities": [
            "safe one-step browser GUI planning",
            "URL and query typing through grounded UI only",
            "click planning by visible browser text",
            "file-changing browser tasks require confirmation",
            "dangerous, sensitive, admin, terminal and browser-profile tasks are blocked",
        ],
    }


def report() -> Dict[str, Any]:
    _ensure_dirs()
    reports = sorted(BROWSER_HARNESS_REPORT_DIR.glob("browser_harness_*.json"), reverse=True)
    return {
        "ok": True,
        "mode": "browser_harness_report",
        "version": BROWSER_HARNESS_VERSION,
        "latest_reports": [str(path) for path in reports[:10]],
        "status": status(),
    }


def is_browser_harness_command(command: str) -> bool:
    value = _normalize(command)
    prefixes = [
        "pc browser harness",
        "browser harness",
        "pc computer browser",
        "pc computer browser harness",
        "браузер harness",
        "браузерный harness",
        "браузер план",
    ]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def _strip_command_goal(raw: str, prefixes: List[str]) -> str:
    lowered = _normalize(raw)
    for prefix in prefixes:
        normalized_prefix = _normalize(prefix)
        if lowered == normalized_prefix:
            return ""
        if lowered.startswith(normalized_prefix + " "):
            return raw[len(prefix):].strip(" :,-—")
    return raw.strip()


def handle_dispatch_command(command: str) -> Dict[str, Any]:
    raw = str(command or "").strip()
    value = _normalize(raw)

    status_aliases = {
        "pc browser harness status",
        "browser harness status",
        "pc computer browser status",
        "статус браузерного harness",
    }
    report_aliases = {
        "pc browser harness report",
        "browser harness report",
        "pc computer browser report",
        "отчет браузерного harness",
        "отчёт браузерного harness",
    }
    contract_aliases = {
        "pc browser harness contracts",
        "browser harness contracts",
        "pc computer browser contracts",
        "контракты браузерного harness",
    }

    if value in status_aliases:
        result = status()
        result["handled"] = True
        return result

    if value in report_aliases:
        result = report()
        result["handled"] = True
        return result

    if value in contract_aliases:
        result = run_browser_harness_contracts(write_report=True)
        result["handled"] = True
        return result

    plan_prefixes = [
        "pc browser harness plan",
        "browser harness plan",
        "pc computer browser plan",
        "браузер план",
    ]
    simulate_prefixes = [
        "pc browser harness simulate",
        "browser harness simulate",
        "pc computer browser simulate",
        "pc computer browser",
        "браузерный harness",
    ]

    for prefix in plan_prefixes:
        if value == _normalize(prefix) or value.startswith(_normalize(prefix) + " "):
            goal = _strip_command_goal(raw, [prefix])
            result = plan_one_browser_action(goal, simulate=True)
            result["handled"] = True
            return result

    for prefix in simulate_prefixes:
        if value == _normalize(prefix) or value.startswith(_normalize(prefix) + " "):
            goal = _strip_command_goal(raw, [prefix])
            result = simulate_browser_step(goal)
            result["handled"] = True
            return result

    return {
        "ok": False,
        "handled": False,
        "mode": "browser_harness_dispatch",
        "version": BROWSER_HARNESS_VERSION,
        "reason": "not a Browser Harness command",
    }


def dispatch(command: str) -> Dict[str, Any]:
    result = handle_dispatch_command(command)
    if result.get("handled"):
        return result
    return {
        "ok": False,
        "handled": False,
        "mode": "browser_harness_unknown_command",
        "version": BROWSER_HARNESS_VERSION,
        "command": command,
        "hint": "Используй: pc browser harness status, pc browser harness contracts, pc computer browser simulate <цель>",
    }
