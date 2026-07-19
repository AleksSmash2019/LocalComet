from __future__ import annotations

import hashlib
import re
from typing import Any


TASK_PLANNER_VERSION = "v6.82"

_MODE = "explainable_task_plan"
_PREFIXES = (
    "спланируй задачу",
    "план задачи",
    "task plan",
)
_INTENT_ORDER = (
    "inspect",
    "explain",
    "analyze",
    "test",
    "edit",
    "create",
    "execute",
    "install",
    "delete",
    "move",
    "network",
    "credential",
    "security_bypass",
    "system_change",
    "mixed",
    "unknown",
)
_READ_ONLY_ACTIONS = {"inspect", "explain", "analyze"}
_APPROVAL_ACTIONS = {
    "test",
    "edit",
    "create",
    "execute",
    "install",
    "delete",
    "move",
    "network",
    "credential",
    "security_bypass",
    "system_change",
}
_CRITICAL_ACTIONS = {"credential", "security_bypass", "system_change"}
_HIGH_ACTIONS = {"execute", "install", "delete", "move", "network"}
_MEDIUM_ACTIONS = {"test", "edit", "create"}
_SAFE_FILE_PREFIXES = ("agents/", "core/", "docs/", "modules/", "next/", "tools/")
_SAFE_FILE_RE = re.compile(
    r"(?<![A-Za-z0-9_./\\-])((?:agents|core|docs|modules|next|tools)[/\\][A-Za-z0-9_./\\-]+\.[A-Za-z0-9_]+)"
)
_DANGEROUS_PATH_PATTERNS = (
    re.compile(r"(?i)(?:^|\s)\.\.[/\\]"),
    re.compile(r"(?i)\b[A-Z]:[/\\]"),
    re.compile(r"(?i)(?:^|\s)//[^/\s]+/"),
    re.compile(r"(?i)(?:^|\s)\\\\[^\\\s]+\\"),
    re.compile(r"(?i)(?:^|\s)/(?:etc|bin|sbin|usr|var|root|home|Users)(?:/|\s|$)"),
    re.compile(r"(?i)(?:^|\s)~[/\\]"),
)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
    re.IGNORECASE | re.DOTALL,
)
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_PRIVATE_KEY_RE, "<PRIVATE_KEY>"),
    (re.compile(r"(?i)\bauthorization\s*:\s*[^\s]+(?:\s+[^\s]+)?"), "Authorization: <REDACTED_TOKEN>"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{6,}"), "Bearer <REDACTED_TOKEN>"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "<REDACTED_TOKEN>"),
    (re.compile(r"\bghp_[A-Za-z0-9_]{8,}\b"), "<REDACTED_TOKEN>"),
    (re.compile(r"(?i)\b[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY|ACCESS_KEY)\s*=\s*[^\s]+"), "<REDACTED_SECRET>"),
    (re.compile(r"(?i)\b(password|passwd|pwd|пароль)\s*[:=]\s*[^\s]+"), r"\1=<REDACTED_PASSWORD>"),
    (re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+(?:\\[^\s]*)?"), "<USER_PATH>"),
    (re.compile(r"(?i)\b[A-Z]:/Users/[^/\s]+(?:/[^\s]*)?"), "<USER_PATH>"),
    (re.compile(r"(?i)(?<!\S)/(?:home|Users)/[^/\s]+(?:/[^\s]*)?"), "<USER_PATH>"),
    (re.compile(r"(?i)(?<!\S)~[/\\][^\s]+"), "<USER_PATH>"),
    (re.compile(r"(?i)\\\\[^\\\s]+\\[^\\\s]+\\(?:Users\\)?[^\\\s]+(?:\\[^\s]*)?"), "<USER_PATH>"),
)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _normalize_key(value: Any) -> str:
    return _normalize_text(value).lower().replace("ё", "е")


def _redact(text: str) -> str:
    redacted = str(text or "")
    for pattern, replacement in _REDACTIONS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _preview(text: str) -> str:
    redacted = _redact(text)
    suffix = " <TRUNCATED>"
    if len(redacted) <= 300:
        return redacted
    return redacted[: 300 - len(suffix)].rstrip() + suffix


def _language(text: str) -> str:
    has_ru = any("а" <= char <= "я" or char == "ё" for char in text.lower())
    has_en = any("a" <= char <= "z" for char in text.lower())
    if has_ru and has_en:
        return "mixed"
    if has_ru:
        return "ru"
    if has_en:
        return "en"
    return "unknown"


def _base_schema(ok: bool) -> dict[str, Any]:
    return {
        "mode": _MODE,
        "version": TASK_PLANNER_VERSION,
        "ok": ok,
        "request": {
            "preview": "",
            "sha256": "",
            "language": "unknown",
            "normalized_length": 0,
        },
        "intent": {
            "category": "unknown",
            "read_only": True,
            "requested_actions": [],
        },
        "risk": {
            "level": "LOW",
            "reasons": [],
            "blocked": False,
        },
        "contract": {
            "goal": "",
            "inputs": [],
            "constraints": [],
            "success_criteria": [],
        },
        "context": {
            "required_files": [],
            "required_capabilities": [],
            "missing_information": [],
        },
        "steps": [],
        "approval": {
            "required": False,
            "reason": "",
            "execution_allowed": False,
        },
        "execution": {
            "performed": False,
            "writes": 0,
            "commands_run": 0,
            "network_requests": 0,
        },
        "warnings": [],
    }


def _match_prefix(command: str) -> tuple[bool, str, str]:
    normalized = _normalize_text(command)
    lowered = normalized.lower().replace("ё", "е")
    for prefix in _PREFIXES:
        normalized_prefix = prefix.replace("ё", "е")
        if lowered == normalized_prefix:
            return False, prefix, ""
        marker = normalized_prefix + " "
        if lowered.startswith(marker):
            return True, prefix, normalized[len(marker) :].strip()
    return False, "", ""


def is_task_plan_command(command: str = "") -> bool:
    matched, _prefix, request = _match_prefix(command)
    return matched and bool(request)


def parse_task_request(command: str) -> dict[str, Any]:
    matched, prefix, body = _match_prefix(command)
    if not matched or not body:
        return {
            "ok": False,
            "prefix": prefix,
            "normalized": "",
            "preview": "",
            "sha256": "",
            "language": "unknown",
            "normalized_length": 0,
            "warnings": ["empty_or_unrecognized_task_request"],
        }
    normalized = _normalize_text(body)
    return {
        "ok": True,
        "prefix": prefix,
        "normalized": normalized,
        "preview": _preview(normalized),
        "sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "language": _language(normalized),
        "normalized_length": len(normalized),
        "warnings": [],
    }


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _detect_actions(text: str) -> list[str]:
    lowered = text.lower().replace("ё", "е")
    actions: set[str] = set()
    if _contains_any(lowered, ("объяс", "explain", "describe", "поясн")):
        actions.add("explain")
    if _contains_any(lowered, ("анализ", "analyze", "analyse", "static analysis", "разбор")):
        actions.add("analyze")
    if _contains_any(lowered, ("провер", "inspect", "review", "read-only", "без изменений", "without changes")):
        actions.add("inspect")
    if _contains_any(lowered, ("тест", "test", "regression", "validation suite")):
        actions.add("test")
    if _contains_any(lowered, ("редакт", "исправ", "patch", "edit", "modify", "change source", "изменить")) and "без изменений" not in lowered:
        actions.add("edit")
    if _contains_any(lowered, ("создай", "создать", "create", "new file", "add file")):
        actions.add("create")
    if _contains_any(lowered, ("execute", "run command", "shell", "subprocess", "запусти команд", "выполни команд", "запустить скрипт")):
        actions.add("execute")
    if _contains_any(lowered, ("install", "pip install", "npm install", "установи", "установить пакет")):
        actions.add("install")
    if _contains_any(lowered, ("delete", "remove file", "удали", "удалить", "стереть", "destroy")):
        actions.add("delete")
    if _contains_any(lowered, ("move", "rename", "перемести", "перенеси", "переимен")):
        actions.add("move")
    if _contains_any(lowered, ("network", "download", "upload", "http://", "https://", "интернет", "скачай", "web request")):
        actions.add("network")
    if _contains_any(lowered, ("password", "credential", "secret", "token", "api key", "private key", "парол", "секрет", "ключ")):
        actions.add("credential")
    if _contains_any(lowered, ("disable safety", "отключить защит", "bypass approval", "обойти", "kill switch", "антивирус", "firewall")):
        actions.add("security_bypass")
    if _contains_any(lowered, ("admin", "administrator", "privilege", "elevat", "registry", "scheduled task", "startup", "service", "system32", "c:\\windows", "/etc/", "автозагруз", "служб")):
        actions.add("system_change")
    if not actions:
        actions.add("unknown")
    return sorted(actions)


def _has_dangerous_path(text: str) -> bool:
    return any(pattern.search(text) for pattern in _DANGEROUS_PATH_PATTERNS)


def _safe_required_files(text: str) -> list[str]:
    files: set[str] = set()
    for match in _SAFE_FILE_RE.finditer(text):
        candidate = match.group(1).replace("\\", "/").strip("./")
        if (
            candidate.startswith(_SAFE_FILE_PREFIXES)
            and ".." not in candidate.split("/")
            and ":" not in candidate
            and not candidate.startswith(("/", "~"))
        ):
            files.add(candidate)
    return sorted(files)[:20]


def classify_task_risk(request: dict) -> dict[str, Any]:
    normalized = str(request.get("normalized") or "")
    actions = [item for item in request.get("actions", []) if item in _INTENT_ORDER]
    if not actions:
        actions = _detect_actions(normalized)
    reasons: list[str] = []
    warnings: list[str] = []
    blocked = False
    level = "LOW"

    if any(action in _CRITICAL_ACTIONS for action in actions):
        level = "CRITICAL"
        blocked = True
        reasons.append("critical_safety_or_credential_request")
    elif any(action in _HIGH_ACTIONS for action in actions):
        level = "HIGH"
        reasons.append("high_risk_future_action")
    elif any(action in _MEDIUM_ACTIONS for action in actions):
        level = "MEDIUM"
        reasons.append("future_project_change_or_test")
    else:
        reasons.append("read_only_planning_or_analysis")

    if _has_dangerous_path(normalized):
        warnings.append("dangerous_path_text_redacted")
        reasons.append("dangerous_path_like_text")
        lower = normalized.lower().replace("ё", "е")
        if _contains_any(lower, ("system32", "c:\\windows", "/etc/", "~/.ssh", "id_rsa")):
            level = "CRITICAL"
            blocked = True

    if "unknown" in actions and len(actions) == 1:
        reasons.append("intent_requires_clarification")

    return {
        "level": level,
        "reasons": sorted(set(reasons)),
        "blocked": blocked,
        "warnings": sorted(set(warnings)),
    }


def _category(actions: list[str]) -> str:
    bounded = [action for action in actions if action in _INTENT_ORDER and action != "unknown"]
    if len(bounded) == 1:
        return bounded[0]
    if len(bounded) > 1:
        return "mixed"
    return "unknown"


def _capabilities(actions: list[str]) -> list[str]:
    caps: set[str] = set()
    if {"inspect", "explain", "analyze"} & set(actions):
        caps.update({"source_inspection", "static_analysis"})
    if "test" in actions:
        caps.add("test_execution")
    if "edit" in actions:
        caps.add("controlled_edit")
    if "create" in actions:
        caps.add("file_creation")
    if "network" in actions:
        caps.add("network_access")
    if "install" in actions:
        caps.add("package_management")
    if {"credential", "security_bypass", "system_change"} & set(actions):
        caps.add("security_review")
    if "explain" in actions:
        caps.add("documentation")
    if not caps:
        caps.add("unknown")
    return sorted(caps)


def _missing_information(actions: list[str], required_files: list[str]) -> list[str]:
    missing: list[str] = []
    if "unknown" in actions:
        missing.append("clarify requested outcome")
    if {"edit", "create", "test"} & set(actions) and not required_files:
        missing.append("explicit safe project target")
    return missing[:10]


def _step(step_id: int, title: str, description: str, action_type: str, read_only: bool, approval: bool, blocked: bool, depends_on: list[str], verification: str) -> dict[str, Any]:
    return {
        "id": f"step_{step_id:02d}",
        "title": title,
        "description": description,
        "action_type": action_type,
        "read_only": read_only,
        "requires_approval": approval,
        "blocked": blocked,
        "depends_on": depends_on,
        "verification": verification,
    }


def _steps(actions: list[str], risk: dict[str, Any]) -> list[dict[str, Any]]:
    result = [
        _step(1, "Inspect request", "Classify the task and identify safe context.", "inspect", True, False, False, [], "Intent and risk are documented."),
    ]
    if risk.get("blocked") is True:
        result.append(
            _step(2, "Stop blocked request", "Do not plan execution for blocked or unsafe content.", "stop", True, True, True, ["step_01"], "Blocked status is explicit.")
        )
        return result

    if any(action in actions for action in ("analyze", "inspect", "explain", "unknown")):
        result.append(
            _step(2, "Analyze safely", "Prepare a read-only explanation or inspection path.", "analyze", True, False, False, ["step_01"], "No write or execution step is included.")
        )
    next_id = len(result) + 1
    for action in ("test", "edit", "create", "execute"):
        if action in actions and len(result) < 11:
            result.append(
                _step(next_id, f"Plan {action}", f"Describe the future {action} action without performing it.", action, False, True, False, [result[-1]["id"]], "Approval is required before action.")
            )
            next_id += 1
    if len(result) < 12:
        result.append(
            _step(next_id, "Verify plan", "Confirm schema, approvals and safety constraints.", "verify", True, False, False, [result[-1]["id"]], "Plan remains deterministic and non-executing.")
        )
    return result[:12]


def build_task_plan(command: str) -> dict[str, Any]:
    parsed = parse_task_request(command)
    if not parsed.get("ok"):
        result = _base_schema(False)
        result["warnings"] = list(parsed.get("warnings", []))
        return result

    normalized = str(parsed["normalized"])
    actions = _detect_actions(normalized)
    parsed["actions"] = actions
    risk = classify_task_risk(parsed)
    required_files = _safe_required_files(normalized)
    approval_required = bool(set(actions) & _APPROVAL_ACTIONS or risk["level"] in {"HIGH", "CRITICAL"})
    preview = str(parsed["preview"])
    constraints = [
        "no execution in v6.82",
        "no filesystem writes",
        "approval required for future actions",
        "stay inside the project root",
        "respect Safety and protected paths",
    ]

    result = _base_schema(True)
    result["request"] = {
        "preview": preview,
        "sha256": str(parsed["sha256"]),
        "language": str(parsed["language"]),
        "normalized_length": int(parsed["normalized_length"]),
    }
    result["intent"] = {
        "category": _category(actions),
        "read_only": not bool(set(actions) & _APPROVAL_ACTIONS),
        "requested_actions": actions,
    }
    result["risk"] = {
        "level": str(risk["level"]),
        "reasons": list(risk["reasons"]),
        "blocked": bool(risk["blocked"]),
    }
    result["contract"] = {
        "goal": preview[:300],
        "inputs": ["task_request"],
        "constraints": constraints,
        "success_criteria": [
            "plan schema is complete",
            "risk and approval are explicit",
            "no execution is performed",
        ],
    }
    result["context"] = {
        "required_files": required_files,
        "required_capabilities": _capabilities(actions),
        "missing_information": _missing_information(actions, required_files),
    }
    result["steps"] = _steps(actions, risk)
    result["approval"] = {
        "required": approval_required,
        "reason": "future_action_requires_approval" if approval_required else "",
        "execution_allowed": False,
    }
    result["warnings"] = sorted(set(list(parsed.get("warnings", [])) + list(risk.get("warnings", []))))
    return result


def dispatch(command: str) -> dict[str, Any]:
    if not is_task_plan_command(command):
        result = _base_schema(False)
        result["warnings"] = ["unknown_task_plan_command"]
        return result
    return build_task_plan(command)
