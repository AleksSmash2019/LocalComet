import json
import os
import subprocess
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from modules.project_paths import get_project_root


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
CODEX_BRIDGE_DIR = PROJECTS_DIR / "CodexBridge"
REPORTS_DIR = PROJECTS_DIR / "Reports"
RELAY_DIR = PROJECTS_DIR / "ChatGPTRelay"
RESPONSE_TARGET_PATH = RELAY_DIR / "response.json"
PROMPT_PATH = CODEX_BRIDGE_DIR / "codex_task_prompt.md"
CONTEXT_PATH = CODEX_BRIDGE_DIR / "codex_task_context.json"
REVIEW_PATH = CODEX_BRIDGE_DIR / "codex_response_review.md"
LEDGER_PATH = CODEX_BRIDGE_DIR / "codex_run_state.json"
HISTORY_DIR = CODEX_BRIDGE_DIR / "history"


IGNORED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "venv",
    ".venv",
    "BrowserProfile",
}

PROTECTED_RESPONSE_PATHS = {
    "config.py",
    "core/router.py",
    "core/planner.py",
    "core/executor.py",
    "modules/self_edit.py",
}

RISKY_RESPONSE_PATH_MARKERS = (
    "apply",
    "validate",
    "validator",
    "browser_bridge",
    "gpt_browser_bridge",
    "Projects/BrowserProfile",
)

IMPORTANT_ALWAYS = [
    "LocalComet_Control_Panel.py",
    "modules/codex_bridge.py",
    "modules/stability_test.py",
    "modules/auto_verification.py",
    "modules/self_edit.py",
]

GOAL_FILE_HINTS = [
    (("command center", "command_center", "команд", "панел", "ui", "интерфейс"), [
        "modules/command_center_ui.py",
        "LocalComet_Control_Panel.py",
    ]),
    (("relay", "response", "chatgpt", "чатгпт", "browser bridge", "gpt browser"), [
        "modules/gpt_browser_bridge.py",
        "modules/chatgpt_relay.py",
        "agents/chatgpt_relay_agent.py",
        "agents/gpt_browser_agent.py",
    ]),
    (("codex", "кодекс"), [
        "modules/codex_bridge.py",
        "modules/codex_connector.py",
    ]),
    (("stability", "стабил", "full test", "полный тест"), [
        "modules/stability_test.py",
        "modules/auto_verification.py",
        "agents/system_agent.py",
    ]),
    (("router", "route", "planner", "маршрут", "план"), [
        "core/router.py",
        "core/planner.py",
        "core/executor.py",
    ]),
    (("browser", "браузер", "autopilot", "автопилот"), [
        "modules/browser_actions.py",
        "modules/browser_task_runner.py",
        "modules/browser_autopilot.py",
        "modules/browser_super.py",
        "agents/browser_agent.py",
    ]),
]


def _ensure_dir():
    CODEX_BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    RELAY_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _short_text(value, limit=12000):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated for Codex prompt]"


def _looks_corrupted_text(text):
    sample = str(text or "")[:1600]

    if not sample:
        return False

    replacement_count = sample.count("\ufffd")
    nul_count = sample.count("\x00")
    control_count = sum(
        1
        for char in sample
        if ord(char) < 32 and char not in "\r\n\t"
    )
    mojibake_markers = ["╤", "Є", "є", "√", "Ё", "ё", "ъЄ", "хЁ", "щэ", "яряю"]
    mojibake_count = sum(sample.count(marker) for marker in mojibake_markers)

    return (
        replacement_count > 4
        or nul_count > 4
        or control_count > max(10, len(sample) // 18)
        or mojibake_count > 12
    )


def _decode_bytes_safely(raw):
    candidates = []

    for encoding in ("utf-8-sig", "utf-16", "cp866", "cp1251", "utf-16-le", "utf-16-be", "utf-8"):
        try:
            text = raw.decode(encoding).replace("\x00", "")
            score = 0

            if _looks_corrupted_text(text):
                score -= 100

            if "Структура папок" in text or "Серийный номер тома" in text:
                score += 50

            if "LocalComet_Control_Panel.py" in text:
                score += 20

            if "modules" in text and "agents" in text and "core" in text:
                score += 15

            if "╤" in text or "Є" in text or "√" in text:
                score -= 30

            candidates.append((score, encoding, text))
        except Exception:
            pass

    if not candidates:
        return ""

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][2]


def _read_file(path, limit=12000):
    path = Path(path)

    if not path.exists() or not path.is_file():
        return ""

    try:
        raw = path.read_bytes()
    except Exception as exc:
        return f"[READ ERROR] {path}: {exc}"

    if not raw:
        return ""

    text = _decode_bytes_safely(raw)

    if not text:
        return f"[READ ERROR] {path}: cannot decode file safely"

    return _short_text(text, limit)


def _detect_response_json():
    if not RESPONSE_TARGET_PATH.exists():
        return {
            "status": "missing",
            "ready": False,
            "message": "response.json пока нет.",
            "summary": "",
            "operation_count": 0,
            "operation_types": [],
            "paths": [],
            "tests": [],
        }

    try:
        raw = RESPONSE_TARGET_PATH.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as exc:
        return {
            "status": "read_error",
            "ready": False,
            "message": f"response.json не удалось прочитать: {exc}",
            "summary": "",
            "operation_count": 0,
            "operation_types": [],
            "paths": [],
            "tests": [],
        }

    try:
        data = json.loads(raw)
    except Exception as exc:
        return {
            "status": "invalid_json",
            "ready": False,
            "message": f"response.json есть, но JSON невалидный: {exc}",
            "summary": "",
            "operation_count": 0,
            "operation_types": [],
            "paths": [],
            "tests": [],
        }

    if not isinstance(data, dict):
        return {
            "status": "invalid_shape",
            "ready": False,
            "message": "response.json должен быть JSON object.",
            "summary": "",
            "operation_count": 0,
            "operation_types": [],
            "paths": [],
            "tests": [],
        }

    summary = str(data.get("summary", "") or "").strip()
    operations = data.get("operations", [])
    tests = data.get("tests", [])
    problems = []

    if not summary:
        problems.append("нет summary")

    if not isinstance(operations, list) or not operations:
        problems.append("operations должен быть непустым list")

    if not isinstance(tests, list) or not tests:
        problems.append("tests должен быть непустым list")

    paths = []
    operation_types = []

    if isinstance(operations, list):
        for index, operation in enumerate(operations, start=1):
            if not isinstance(operation, dict):
                problems.append(f"operation #{index} не object")
                continue

            operation_type = operation.get("type")
            operation_path = str(operation.get("path", "") or "").strip()
            operation_types.append(str(operation_type or ""))

            if operation_type not in ["replace", "create"]:
                problems.append(f"operation #{index}: запрещенный type={operation_type!r}")

            if not operation_path:
                problems.append(f"operation #{index}: нет path")
            elif Path(operation_path).is_absolute() or ".." in Path(operation_path).parts:
                problems.append(f"operation #{index}: небезопасный path={operation_path!r}")
            else:
                paths.append(operation_path)

    ready = not problems

    return {
        "status": "ready" if ready else "needs_fix",
        "ready": ready,
        "message": "response.json готов к Импорт + проверка." if ready else "; ".join(problems),
        "summary": summary,
        "operation_count": len(operations) if isinstance(operations, list) else 0,
        "operation_types": operation_types,
        "paths": paths,
        "tests": [str(item) for item in tests] if isinstance(tests, list) else [],
    }


def detect_response_json():
    return _detect_response_json()


def _response_review_risk(detector):
    warnings = []

    for path in detector.get("paths") or []:
        normalized = str(path or "").replace("\\", "/").strip()
        lowered = normalized.lower()

        if normalized in PROTECTED_RESPONSE_PATHS:
            warnings.append(f"protected path: `{normalized}`")
            continue

        if lowered.startswith("projects/browserprofile/"):
            warnings.append(f"BrowserProfile path: `{normalized}`")
            continue

        for marker in RISKY_RESPONSE_PATH_MARKERS:
            if marker.lower() in lowered:
                warnings.append(f"risky path marker `{marker}` in `{normalized}`")
                break

    if warnings:
        return "high", warnings

    if detector.get("ready"):
        return "low", []

    return "medium", ["response.json is not ready"]


def _response_review_next_action(detector, risk_level):
    if not detector.get("ready"):
        return "Fix response.json before Import + проверка."

    if risk_level == "high":
        return "Stop. Ask user/Grimoire before importing this response.json."

    return "Run Command Center -> Импорт + проверка. If validation passes, run Применить + after."


def _read_json_file(path):
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        pass

    return {}


def _response_review_fingerprint(detector, risk_level, warnings):
    payload = {
        "status": detector.get("status"),
        "ready": detector.get("ready"),
        "summary": detector.get("summary"),
        "operation_count": detector.get("operation_count"),
        "operation_types": detector.get("operation_types") or [],
        "paths": detector.get("paths") or [],
        "tests": detector.get("tests") or [],
        "risk_level": risk_level,
        "warnings": warnings or [],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return sha256(raw.encode("utf-8")).hexdigest()


def _write_codex_run_ledger(detector, review, review_text):
    previous = _read_json_file(LEDGER_PATH)
    fingerprint = _response_review_fingerprint(
        detector,
        review.get("risk_level"),
        review.get("warnings") or [],
    )
    latest_history = str(previous.get("latest_history_review") or "")

    if previous.get("last_review_fingerprint") != fingerprint:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        history_path = HISTORY_DIR / f"codex_response_review_{stamp}.md"
        history_path.write_text(review_text, encoding="utf-8")
        latest_history = str(history_path)

    state = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "response_file": str(RESPONSE_TARGET_PATH),
        "review_file": str(REVIEW_PATH),
        "latest_history_review": latest_history,
        "last_review_fingerprint": fingerprint,
        "status": detector.get("status"),
        "ready": bool(detector.get("ready")),
        "summary": detector.get("summary") or "",
        "operation_count": detector.get("operation_count"),
        "operation_types": detector.get("operation_types") or [],
        "paths": detector.get("paths") or [],
        "tests": detector.get("tests") or [],
        "risk_level": review.get("risk_level"),
        "warnings": review.get("warnings") or [],
        "next_action": review.get("next_action"),
    }

    LEDGER_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def _write_response_review(detector):
    risk_level, warnings = _response_review_risk(detector)
    created_at = datetime.now().isoformat(timespec="seconds")
    paths = detector.get("paths") or []
    tests = detector.get("tests") or []

    lines = [
        "# Codex Response Review",
        "",
        f"- created_at: {created_at}",
        f"- response_file: `{RESPONSE_TARGET_PATH}`",
        f"- status: `{detector.get('status')}`",
        f"- ready: `{detector.get('ready')}`",
        f"- risk_level: `{risk_level}`",
        f"- message: {detector.get('message')}",
        "",
        "## Summary",
        "",
        detector.get("summary") or "нет",
        "",
        "## Files Touched",
        "",
    ]

    lines.extend([f"- `{path}`" for path in paths] or ["- нет"])

    lines.extend([
        "",
        "## Tests",
        "",
    ])

    lines.extend([f"- `{test}`" for test in tests] or ["- нет"])

    lines.extend([
        "",
        "## Warnings",
        "",
    ])

    lines.extend([f"- {warning}" for warning in warnings] or ["- нет"])

    lines.extend([
        "",
        "## Next Action",
        "",
        _response_review_next_action(detector, risk_level),
        "",
    ])

    review_text = "\n".join(lines)
    REVIEW_PATH.write_text(review_text, encoding="utf-8")
    review = {
        "path": str(REVIEW_PATH),
        "risk_level": risk_level,
        "warnings": warnings,
        "next_action": _response_review_next_action(detector, risk_level),
    }
    ledger = _write_codex_run_ledger(detector, review, review_text)
    review["ledger_path"] = str(LEDGER_PATH)
    review["latest_history_review"] = ledger.get("latest_history_review")

    return review


def write_codex_response_review():
    _ensure_dir()
    return _write_response_review(_detect_response_json())


def _project_relative(path):
    path = Path(path)
    try:
        return str(path.relative_to(ROOT_DIR)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _collect_project_tree(limit=9000):
    lines = []
    allowed_suffixes = {".py", ".md", ".json", ".txt", ".toml", ".yaml", ".yml"}

    for path in sorted(ROOT_DIR.rglob("*")):
        if any(part in IGNORED_DIR_NAMES for part in path.parts):
            continue

        rel = _project_relative(path)
        rel_lower = rel.lower()

        if path.is_dir():
            continue

        if rel_lower.startswith(".git/"):
            continue

        if "/__pycache__/" in rel_lower or rel_lower.endswith(".pyc"):
            continue

        if rel_lower.startswith("projects/browserprofile/"):
            continue

        if path.suffix.lower() not in allowed_suffixes and path.name not in {".gitignore"}:
            continue

        if len(lines) >= 260:
            lines.append("...[clean tree truncated]")
            break

        lines.append(rel)

    if not lines:
        return "No project files found for clean tree excerpt."

    return _short_text("\n".join(lines), limit)


def _latest_report_excerpt(limit=7000):
    if not REPORTS_DIR.exists():
        return "No reports directory yet."

    candidates = []
    for pattern in ("*stability*.md", "*auto_verification*.md", "*regression*.md", "*health*.md"):
        candidates.extend(REPORTS_DIR.rglob(pattern))

    candidates = [path for path in candidates if path.is_file()]

    if not candidates:
        return "No recent LocalComet reports found."

    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    return f"Latest report: {_project_relative(latest)}\n\n{_read_file(latest, limit=limit)}"


def _goal_files(goal):
    lowered = str(goal or "").lower()
    chosen = []

    for rel in IMPORTANT_ALWAYS:
        chosen.append(rel)

    for markers, files in GOAL_FILE_HINTS:
        if any(marker in lowered for marker in markers):
            chosen.extend(files)

    unique = []
    seen = set()

    for rel in chosen:
        if rel in seen:
            continue
        seen.add(rel)
        path = ROOT_DIR / rel
        if path.exists() and path.is_file():
            unique.append(rel)

    return unique


def _file_context(goal, per_file_limit=9000, total_limit=42000):
    chunks = []
    included = []
    total = 0

    for rel in _goal_files(goal):
        path = ROOT_DIR / rel
        text = _read_file(path, limit=per_file_limit)

        if not text:
            continue

        chunk = f"## FILE: {rel}\n```text\n{text}\n```"

        if total + len(chunk) > total_limit:
            chunks.append("## FILE CONTEXT TRUNCATED\nFurther files omitted to keep Codex prompt compact.")
            break

        chunks.append(chunk)
        included.append({"path": rel, "chars": len(text)})
        total += len(chunk)

    return "\n\n".join(chunks), included


def _copy_to_clipboard(text):
    copied = False
    error = ""

    try:
        import pyperclip

        pyperclip.copy(text)
        copied = True
    except Exception as exc:
        error = str(exc)

    if not copied and os.name == "nt":
        try:
            subprocess.run(
                "clip",
                input=text,
                text=True,
                shell=True,
                check=True,
                timeout=10,
            )
            copied = True
            error = ""
        except Exception as exc:
            error = str(exc)

    return copied, error


def build_codex_prompt(goal):
    goal = str(goal or "").strip()

    if not goal:
        goal = (
            "Проанализируй LocalComet и предложи маленькое безопасное улучшение "
            "для стабильности agent workflow."
        )

    project_tree = _collect_project_tree()
    latest_report = _latest_report_excerpt()
    file_context, included_files = _file_context(goal)

    prompt = f"""# LocalComet → Codex Task Pack

You are Codex, a coding agent working on this local Windows project.

## User goal

{goal}

## Repository

- Root: `{ROOT_DIR}`
- Relay patch target: `{RELAY_DIR / "response.json"}`
- CodexBridge folder: `{CODEX_BRIDGE_DIR}`

## Codex agent operating mode

Act like a careful autonomous coding agent, not like a chat bot.

Before editing anything, reason internally through this workflow:

1. Understand the user goal.
2. Identify the smallest safe change.
3. Pick only the files needed for that change.
4. Check whether the task is ambiguous or risky.
5. If it is ambiguous, do not guess.
6. If it is safe and clear, create `response.json`.

If the task is ambiguous, create this file instead of `response.json`:

`{CODEX_BRIDGE_DIR / "codex_questions.md"}`

The questions file must contain:
- 1 short summary of what is unclear;
- up to 3 precise questions;
- the exact files Codex needs next;
- the recommended next user answer.

If the task is clear, create this plan file before writing the patch:

`{CODEX_BRIDGE_DIR / "codex_plan.md"}`

The plan file must be compact and contain:
- goal;
- selected files;
- risk level: low / medium / high;
- planned operation count;
- tests to run;
- rollback note.

## Required output contract

Create a patch file at:

`{RELAY_DIR / "response.json"}`

The file must be valid JSON with this exact shape:

```json
{{
  "summary": "short Russian summary",
  "operations": [
    {{
      "type": "replace",
      "path": "relative/path.py",
      "old": "exact old text",
      "new": "exact new text"
    }}
  ],
  "tests": [
    "python -m py_compile relative\\\\path.py"
  ]
}}
```

Allowed operation types: `replace`, `create`.

Do not use JSON Patch `op`.
Do not return placeholders.
Do not create `.exe`, `.bat`, `.cmd`, `.ps1`.
Prefer one small safe change.
Avoid risky central changes in `core/router.py`, `config.py`, apply/validate logic, and browser bridge unless the task explicitly requires it.
If changing UI, keep backend untouched.
If changing tests, explain why the old test was stale or too strict in `summary`.

## Token saving rules

Use only the context below unless you truly need more.
Do not read the whole repository first.
Patch exact snippets only.
Keep the final response compact.
Write `response.json`; do not paste a huge explanation.

## Project tree excerpt

```text
{project_tree}
```

## Recent report excerpt

```text
{latest_report}
```

## Selected file context

{file_context}

## Final reminder

When done, the user will import `{RELAY_DIR / "response.json"}` in LocalComet and run validate/apply/after-checks.
"""
    return prompt, {
        "goal": goal,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT_DIR),
        "prompt_path": str(PROMPT_PATH),
        "response_target": str(RELAY_DIR / "response.json"),
        "included_files": included_files,
    }


def create_codex_task_pack(goal, copy_prompt=True):
    _ensure_dir()
    prompt, context = build_codex_prompt(goal)

    PROMPT_PATH.write_text(prompt, encoding="utf-8")
    CONTEXT_PATH.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")

    copied, copy_error = _copy_to_clipboard(prompt) if copy_prompt else (False, "")

    try:
        from core.state import set_value

        set_value("last_codex_task_prompt", str(PROMPT_PATH))
        set_value("last_codex_task_context", str(CONTEXT_PATH))
        set_value("last_codex_response_target", str(RELAY_DIR / "response.json"))
    except Exception:
        pass

    lines = [
        "OK: Codex Task Pack создан.",
        f"Prompt: {PROMPT_PATH}",
        f"Context: {CONTEXT_PATH}",
        f"Response target: {RELAY_DIR / 'response.json'}",
        f"Prompt chars: {len(prompt)}",
        f"Included files: {len(context.get('included_files', []))}",
    ]

    if copied:
        lines.append("Clipboard: prompt скопирован. Можно вставить его в Codex.")
    elif copy_error:
        lines.append(f"Clipboard: не удалось скопировать автоматически: {copy_error}")

    lines.extend([
        "",
        "Дальше:",
        "1. Открой Codex.",
        "2. Вставь prompt из буфера или из codex_task_prompt.md.",
        "3. Попроси Codex создать Projects/ChatGPTRelay/response.json.",
        "4. Вернись в LocalComet: Импорт + проверка -> Применить + after.",
    ])

    return "\n".join(lines)


def codex_status():
    _ensure_dir()

    try:
        result = subprocess.run(
            ["codex", "--version"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=20,
        )
        installed = result.returncode == 0
        output = (result.stdout or result.stderr or "").strip()
    except FileNotFoundError:
        installed = False
        output = "codex command not found"
    except Exception as exc:
        installed = False
        output = str(exc)

    detector = _detect_response_json()
    review = _write_response_review(detector)

    lines = [
        "Codex Connector status:",
        f"- folder: {CODEX_BRIDGE_DIR}",
        f"- prompt: {PROMPT_PATH}",
        f"- context: {CONTEXT_PATH}",
        f"- response target: {RESPONSE_TARGET_PATH}",
        f"- response review: {REVIEW_PATH}",
        f"- run ledger: {LEDGER_PATH}",
        f"- codex CLI installed: {installed}",
        f"- codex CLI output: {output or 'нет'}",
        "",
        "Response detector:",
        f"- status: {detector.get('status')}",
        f"- ready: {detector.get('ready')}",
        f"- message: {detector.get('message')}",
        f"- summary: {detector.get('summary') or 'нет'}",
        f"- operations: {detector.get('operation_count')}",
        "- paths: " + (", ".join(detector.get("paths") or []) or "нет"),
        "- tests: " + (", ".join(detector.get("tests") or []) or "нет"),
        "",
        "Response review:",
        f"- risk: {review.get('risk_level')}",
        f"- warnings: {', '.join(review.get('warnings') or []) or 'нет'}",
        f"- next action: {review.get('next_action')}",
        f"- history: {review.get('latest_history_review') or 'нет'}",
    ]

    try:
        from core.state import set_value

        set_value("last_codex_response_ready", bool(detector.get("ready")))
        set_value("last_codex_response_status", str(detector.get("status")))
        set_value("last_codex_response_summary", str(detector.get("summary") or ""))
        set_value("last_codex_response_review", str(REVIEW_PATH))
        set_value("last_codex_response_risk", str(review.get("risk_level")))
        set_value("last_codex_run_ledger", str(LEDGER_PATH))
        set_value("last_codex_response_history", str(review.get("latest_history_review") or ""))
        set_value("last_codex_connector_status", "\n".join(lines)[:5000])
    except Exception:
        pass

    return "\n".join(lines)


def open_codex_connector_folder():
    _ensure_dir()
    os.startfile(str(CODEX_BRIDGE_DIR))
    return f"Открыта папка CodexBridge:\n{CODEX_BRIDGE_DIR}"
