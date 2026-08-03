import json
import re
import shlex
import subprocess
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

import requests

from config import LMSTUDIO_API, MODEL
from core.state import set_value, get_value
from modules.maintenance import backup_project as _maintenance_backup_project
from modules.browser_profile_ignore import close_gpt_browser_context, is_browser_profile_path
from modules.patch_registry import record_patch, register_applied_patch


def backup_project():
    close_gpt_browser_context()
    return _maintenance_backup_project()


ROOT_DIR = get_project_root()
SELF_DIR = ROOT_DIR / "Projects" / "SelfEdit"
RAW_DIR = SELF_DIR / "RawResponses"
RELAY_RESPONSE_FILE = ROOT_DIR / "Projects" / "ChatGPTRelay" / "response.json"

SKIP_PARTS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "Projects",
}


def _ensure_dir():
    SELF_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def _now_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_path(rel_path: str):
    rel_path = str(rel_path or "").strip().replace("\\", "/")

    if not rel_path:
        return None

    p = Path(rel_path)

    if p.is_absolute():
        return None

    if ".." in p.parts:
        return None

    full = (ROOT_DIR / p).resolve()

    try:
        full.relative_to(ROOT_DIR.resolve())
    except Exception:
        return None

    if is_browser_profile_path(full):
        return None

    return full


def _project_tree():
    allowed_roots = {"agents", "modules", "core", "next", "tools"}

    files = []

    for path in ROOT_DIR.rglob("*"):
        if not path.is_file():
            continue

        if any(part in SKIP_PARTS for part in path.parts):
            continue

        rel = path.relative_to(ROOT_DIR)
        parts = rel.parts

        if len(parts) == 1:
            if path.suffix in [".py", ".json"]:
                files.append(str(rel).replace("\\", "/"))
            continue

        if parts[0] in allowed_roots and path.suffix == ".py":
            files.append(str(rel).replace("\\", "/"))

    files = sorted(files)
    return "\n".join(files)


def _read_file(rel_path: str, limit: int = 12000):
    full = _safe_path(rel_path)

    if not full or not full.exists() or not full.is_file():
        return None

    if is_browser_profile_path(full):
        return None

    text = full.read_text(encoding="utf-8", errors="replace")

    if len(text) > limit:
        return text[:limit] + "\n\n# ... FILE TRUNCATED FOR SELF_EDIT ..."

    return text


def _call_llm(system: str, user: str, max_tokens: int = 3000):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system.strip()},
            {"role": "user", "content": user.strip() + "\n\n/no_think"},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }

    response = None

    try:
        response = requests.post(
            LMSTUDIO_API,
            json=payload,
            timeout=300,
        )

        if response.status_code == 400:
            short_user = user[:12000]

            payload["messages"][1]["content"] = short_user + "\n\n/no_think"
            payload["max_tokens"] = min(max_tokens, 2000)

            response = requests.post(
                LMSTUDIO_API,
                json=payload,
                timeout=300,
            )

        response.raise_for_status()

    except requests.exceptions.HTTPError as e:
        body = ""

        if response is not None:
            try:
                body = response.text
            except Exception:
                body = ""

        raise RuntimeError(
            "LM Studio вернул ошибку.\n"
            f"HTTP: {e}\n"
            f"Ответ LM Studio: {body[:1000]}"
        )

    except Exception as e:
        raise RuntimeError(f"Ошибка запроса к LM Studio: {e}")

    data = response.json()
    return data["choices"][0]["message"]["content"]


def _save_raw_response(text: str, prefix: str = "raw_llm_response"):
    _ensure_dir()

    path = RAW_DIR / f"{prefix}_{_now_stamp()}.txt"
    path.write_text(str(text or ""), encoding="utf-8")

    set_value("last_self_raw_response", str(path))

    return path


def _extract_json(text: str):
    raw = str(text or "").strip()

    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()

    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raw_path = _save_raw_response(raw, "bad_json_no_object")
        raise ValueError(f"LLM не вернула JSON. Сырой ответ сохранен: {raw_path}")

    json_text = raw[start:end + 1]

    try:
        return json.loads(json_text)
    except Exception as e:
        raw_path = _save_raw_response(raw, "bad_json_parse")
        raise ValueError(
            f"LLM вернула битый JSON: {e}\n"
            f"Сырой ответ сохранен: {raw_path}"
        )


def _choose_files(goal: str):
    goal_lower = str(goal or "").lower()

    stability_keywords = [
        "auto stability",
        "auto stability test",
        "stability test",
        "model test",
        "тест стабильности",
        "проверка стабильности",
        "автотест",
        "10 баллов",
        "10 баллов без ручной проверки",
    ]

    if any(keyword in goal_lower for keyword in stability_keywords):
        return [
            "modules/stability_test.py",
            "agents/stability_agent.py",
            "modules/browser.py",
            "agents/browser_agent.py",
            "core/executor.py",
            "core/router.py",
            "core/planner.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/self_edit.py",
            "modules/history_log.py",
        ]

    gpt_browser_keywords = [
        "gpt browser bridge",
        "gpt browser",
        "chatgpt browser",
        "browser bridge",
        "persistent browser profile",
        "gpt browser open",
        "gpt browser paste request",
        "gpt browser full cycle",
        "gpt browser full apply",
        "gpt browser close",
        "browserprofile",
        "browser profile",
        "permission denied",
        "lockfile",
        "modules/gpt_browser_bridge.py",
        "agents/gpt_browser_agent.py",
    ]

    if any(keyword in goal_lower for keyword in gpt_browser_keywords):
        return [
            "modules/gpt_browser_bridge.py",
            "agents/gpt_browser_agent.py",
            "modules/browser.py",
            "modules/chatgpt_relay.py",
            "agents/chatgpt_relay_agent.py",
            "modules/automation_center.py",
            "agents/automation_agent.py",
            "core/router.py",
            "core/planner.py",
            "core/executor.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/stability_test.py",
        ]

    automation_multi_keywords = [
        "browser + pc multi task",
        "multi task",
        "browser batch",
        "browser read first",
        "browser compare",
        "browser report",
        "pc batch",
        "task status",
        "task report",
        "sequential task runner",
        "sequential runner",
        "last_multi_task",
        "last_task_report",
        "last_browser_batch",
        "last_pc_batch",
        "цепочка задач",
        "несколько шагов",
    ]

    if any(keyword in goal_lower for keyword in automation_multi_keywords):
        return [
            "modules/automation_center.py",
            "agents/automation_agent.py",
            "modules/browser.py",
            "agents/browser_agent.py",
            "core/router.py",
            "core/planner.py",
            "core/executor.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/stability_test.py",
            "modules/history_log.py",
        ]

    browser_keywords = [
        "browser follow",
        "browser agent",
        "браузерный агент",
        "browser last",
        "browser open first",
        "browser read",
        "последний поиск",
        "открой первый результат",
        "читать страницу",
        "read_page",
        "click_first_link",
        "duckduckgo",
        "browser recovery",
        "browser status",
        "current_url",
        "last_browser_query",
        "last_browser_error",
        "страница, контекст или браузер закрыт",
        "переоткрывай браузер",
        "modules/browser.py",
    ]

    if any(keyword in goal_lower for keyword in browser_keywords):
        return [
            "modules/browser.py",
            "agents/browser_agent.py",
            "core/planner.py",
            "core/router.py",
            "core/executor.py",
            "next/app_v5.py",
            "agents/system_agent.py",
            "modules/self_edit.py",
        ]

    relay_keywords = [
        "relay",
        "релей",
        "chatgpt relay",
        "чатгпт relay",
        "chatgpt_relay",
        "response",
        "clipboard",
        "wrong clipboard",
        "utf-8-sig",
        "relative/path.py",
        "проверка response",
        "проверь ответ",
        "очистка response",
        "очисти ответ",
        "папку relay",
        "открой папку",
        "snapshot",
        "снапшот",
        "project snapshot",
        "ручной список файлов",
        "последний request",
        "последний запрос",
        "dated request",
        "датированный запрос",
        "error doctor",
        "doctor",
        "доктор",
        "ошибка",
        "ошибку",
        "баг",
        "bug",
        "traceback",
        "exception",
        "last_error",
        "last_result",
        "логи",
        "doctor path fix",
        "path fix",
        "кривой список файлов",
        "пути от кавычек",
        "кавычек и скобок",
    ]

    if any(keyword in goal_lower for keyword in relay_keywords):
        return [
            "modules/self_edit.py",
            "modules/chatgpt_relay.py",
            "agents/chatgpt_relay_agent.py",
            "next/app_v5.py",
            "agents/system_agent.py",
        ]

    if (
        "шапк" in goal_lower
        or "верси" in goal_lower
        or "v5." in goal_lower
        or "v5" in goal_lower
        or "header" in goal_lower
        or "title" in goal_lower
        or "maintenance pack" in goal_lower
        or "self-edit safe mode" in goal_lower
        or "app_v5" in goal_lower
        or "next/app_v5.py" in goal_lower
    ):
        return ["next/app_v5.py"]

    if (
        "help" in goal_lower
        or "что ты умеешь" in goal_lower
        or "раздел self-edit" in goal_lower
        or "раздел self edit" in goal_lower
    ):
        return ["agents/system_agent.py"]

    if (
        "shortcut" in goal_lower
        or "алиас" in goal_lower
        or "команд" in goal_lower
    ):
        return ["next/app_v5.py", "agents/system_agent.py"]

    if (
        "executor" in goal_lower
        or "инструмент" in goal_lower
        or "tool" in goal_lower
    ):
        return ["core/executor.py", "next/app_v5.py"]

    tree = _project_tree()

    system = """
Ты инженер проекта LocalComet.
Твоя задача — выбрать файлы, которые нужно прочитать для изменения проекта.
Верни только JSON без markdown.

Формат:
{
  "files": ["relative/path.py"],
  "reason": "кратко почему"
}

Правила:
- максимум 3 файла
- выбирай только существующие файлы из дерева
- если меняется help, выбирай agents/system_agent.py
- если меняется шапка/версия/v5, выбирай next/app_v5.py
"""

    user = f"""
Цель пользователя:
{goal}

Дерево файлов проекта:
{tree}
"""

    answer = _call_llm(system, user, max_tokens=800)
    data = _extract_json(answer)

    selected = data.get("files", [])

    safe = []

    for rel in selected:
        full = _safe_path(rel)

        if full and full.exists() and full.is_file():
            safe.append(str(Path(rel).as_posix()))

    safe = safe[:3]

    if not safe:
        safe = ["agents/system_agent.py"]

    return safe


def create_patch(goal: str):
    _ensure_dir()

    goal = str(goal or "").strip()

    if not goal:
        return "Нет цели для self-edit."

    selected_files = _choose_files(goal)

    file_blocks = []

    for rel in selected_files:
        content = _read_file(rel)

        if content is None:
            continue

        file_blocks.append(
            f"\n--- FILE: {rel} ---\n{content}\n--- END FILE: {rel} ---\n"
        )

    system = """
Ты инженер Python-проекта LocalComet.
Нужно создать безопасный patch для изменения проекта.

Верни только JSON без markdown.

Формат:
{
  "summary": "что изменится",
  "operations": [
    {
      "type": "replace",
      "path": "relative/path.py",
      "old": "точный существующий фрагмент",
      "new": "новый фрагмент"
    },
    {
      "type": "create",
      "path": "relative/path.py",
      "content": "полное содержимое нового файла"
    }
  ],
  "tests": [
    "python -m py_compile relative/path.py"
  ]
}

Правила безопасности:
- НЕ возвращай объяснения вне JSON.
- Для существующих файлов используй type=replace с точным old-фрагментом.
- old должен быть коротким, но уникальным.
- Не меняй файлы за пределами LocalAgent.
- Не удаляй файлы.
- Не используй абсолютные пути.
- Не создавай .exe/.bat/.ps1.
- Для Python-файлов добавь py_compile тесты.
- Если задача слишком большая, сделай минимальный первый шаг.
"""

    user = f"""
Цель пользователя:
{goal}

Прочитанные файлы:
{''.join(file_blocks)}
"""

    answer = _call_llm(system, user, max_tokens=3000)
    patch = _extract_json(answer)

    patch["goal"] = goal
    patch["selected_files"] = selected_files
    patch["created_at"] = datetime.now().isoformat(timespec="seconds")
    patch["model"] = MODEL

    patch_path = SELF_DIR / f"patch_{_now_stamp()}.json"
    patch_path.write_text(
        json.dumps(patch, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_value("last_self_patch", str(patch_path))

    ops = patch.get("operations", [])

    return (
        "Self-edit patch создан.\n"
        f"Файл: {patch_path}\n"
        f"Операций: {len(ops)}\n"
        f"Описание: {patch.get('summary', 'нет')}\n\n"
        "Дальше команда: примени последний патч"
    )


def show_last_patch():
    path = get_value("last_self_patch")

    if not path:
        return "Последний self-edit patch не найден."

    patch_path = Path(path)

    if not patch_path.exists():
        return f"Patch не найден: {patch_path}"

    patch = json.loads(patch_path.read_text(encoding="utf-8"))

    lines = [
        "Последний self-edit patch:",
        f"Файл: {patch_path}",
        f"Цель: {patch.get('goal', 'нет')}",
        f"Модель: {patch.get('model', 'нет')}",
        f"Описание: {patch.get('summary', 'нет')}",
        "",
        "Операции:",
    ]

    for i, op in enumerate(patch.get("operations", []), start=1):
        suffix = ""

        if op.get("already_applied"):
            suffix = " [уже применено]"

        lines.append(f"{i}. {op.get('type')} -> {op.get('path')}{suffix}")

    lines.append("")
    lines.append("Тесты:")

    for test in patch.get("tests", []):
        lines.append(f"- {test}")

    return "\n".join(lines)


def _validate_operations(operations):
    if not isinstance(operations, list) or not operations:
        return False, "В patch нет operations."

    for op in operations:
        op_type = op.get("type")
        rel_path = op.get("path")
        full = _safe_path(rel_path)

        if op_type not in ["replace", "create", "write"]:
            return False, f"Запрещенный тип операции: {op_type}"

        if not full:
            return False, f"Небезопасный путь: {rel_path}"

        if full.suffix not in [".py", ".json", ".md", ".txt"]:
            return False, f"Запрещенное расширение файла: {rel_path}"

        if op_type == "replace":
            if not full.exists():
                return False, f"Файл для replace не найден: {rel_path}"

            old = op.get("old", "")
            new = op.get("new", "")

            if not old:
                return False, f"Пустой old-фрагмент для: {rel_path}"

            current = full.read_text(encoding="utf-8", errors="replace")

            if old not in current:
                if new and new in current:
                    op["already_applied"] = True
                    continue

                return False, f"old-фрагмент не найден в файле: {rel_path}"

    return True, "OK"


def _affected_files(operations):
    result = []

    for op in operations:
        rel_path = op.get("path")
        full = _safe_path(rel_path)

        if full and full not in result:
            result.append(full)

    return result


def _save_rollback(files):
    _ensure_dir()

    rollback = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "files": [],
    }

    for full in files:
        rel = str(full.relative_to(ROOT_DIR)).replace("\\", "/")

        if full.exists():
            content = full.read_text(encoding="utf-8", errors="replace")
            existed = True
        else:
            content = ""
            existed = False

        rollback["files"].append(
            {
                "path": rel,
                "existed": existed,
                "content": content,
            }
        )

    rollback_path = SELF_DIR / f"rollback_{_now_stamp()}.json"
    rollback_path.write_text(
        json.dumps(rollback, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_value("last_self_rollback", str(rollback_path))
    return rollback_path


def _restore_rollback(rollback_path: Path):
    rollback = json.loads(rollback_path.read_text(encoding="utf-8"))

    restored = []

    for item in rollback.get("files", []):
        full = _safe_path(item.get("path"))

        if not full:
            continue

        if item.get("existed"):
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(item.get("content", ""), encoding="utf-8")
            restored.append(str(full.relative_to(ROOT_DIR)).replace("\\", "/"))
        else:
            if full.exists():
                full.unlink()
                restored.append(str(full.relative_to(ROOT_DIR)).replace("\\", "/"))

    return restored


_SAFE_TEST_COMMAND_RE = re.compile(
    r"^python -m py_compile [a-zA-Z0-9_/.\\-]+\.py$"
)


def _run_tests(tests, changed_files):
    commands = []

    for test in tests or []:
        if isinstance(test, str) and test.strip():
            cmd = test.strip()
            if not _SAFE_TEST_COMMAND_RE.match(cmd):
                return False, f"Command rejected (not an allowed py_compile invocation): {cmd}"
            commands.append(cmd)

    for full in changed_files:
        if full.suffix == ".py":
            rel = str(full.relative_to(ROOT_DIR)).replace("\\", "/")
            cmd = f"python -m py_compile {rel}"

            if cmd not in commands:
                commands.append(cmd)

    if not commands:
        return True, "Тестов нет."

    outputs = []

    for cmd in commands:
        result = subprocess.run(
            shlex.split(cmd),
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )

        outputs.append(
            f"$ {cmd}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\nCODE: {result.returncode}"
        )

        if result.returncode != 0:
            return False, "\n\n".join(outputs)

    return True, "\n\n".join(outputs)


def _same_path(left, right):
    try:
        return Path(left).resolve() == Path(right).resolve()
    except Exception:
        return False


def _current_response_file(patch_path):
    relay_patch = str(get_value("last_relay_imported_patch", "") or "").strip()

    if not relay_patch or not _same_path(relay_patch, patch_path):
        return ""

    response_file = str(get_value("last_relay_response", "") or "").strip()

    if response_file:
        return response_file

    if RELAY_RESPONSE_FILE.exists():
        return str(RELAY_RESPONSE_FILE)

    return ""


def _registry_changed_files(changed_files):
    result = []

    for full in changed_files:
        try:
            result.append(str(full.relative_to(ROOT_DIR)).replace("\\", "/"))
        except Exception:
            result.append(str(full))

    return result


def _patch_source(patch_path, response_file=""):
    text = f"{patch_path} {response_file}".lower()

    if "chatgpt_relay" in text or "response.json" in text:
        return "chatgpt_relay"

    return "unknown"


def _record_failed_patch(patch, patch_path, rollback_path, changed_files, tests_output, error):
    try:
        response_file = _current_response_file(patch_path)
        return record_patch(
            patch=patch,
            response_file=response_file,
            patch_file=patch_path,
            rollback_file=rollback_path,
            changed_files=_registry_changed_files(changed_files),
            tests={
                "ok": False,
                "result": str(tests_output or error or ""),
            },
            status="failed",
            source=_patch_source(patch_path, response_file),
        )
    except Exception:
        return None


def apply_last_patch():
    path = get_value("last_self_patch")

    if not path:
        return "Последний self-edit patch не найден."

    patch_path = Path(path)

    if not patch_path.exists():
        return f"Patch не найден: {patch_path}"

    patch = json.loads(patch_path.read_text(encoding="utf-8"))
    operations = patch.get("operations", [])

    ok, message = _validate_operations(operations)

    if not ok:
        return "Patch НЕ применен.\nПричина: " + message

    already_count = len([op for op in operations if op.get("already_applied")])

    if already_count == len(operations):
        set_value("last_self_applied_patch", str(patch_path))

        patch["already_applied_at"] = datetime.now().isoformat(timespec="seconds")
        patch_path.write_text(
            json.dumps(patch, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return (
            "Patch уже был применен ранее.\n"
            f"Patch: {patch_path}\n"
            "Изменения не требуются."
        )

    changed_files = _affected_files(operations)
    rollback_path = _save_rollback(changed_files)

    backup_result = backup_project()

    try:
        for op in operations:
            op_type = op.get("type")
            full = _safe_path(op.get("path"))

            if op_type == "replace":
                if op.get("already_applied"):
                    continue

                current = full.read_text(encoding="utf-8", errors="replace")
                current = current.replace(op.get("old", ""), op.get("new", ""), 1)
                full.write_text(current, encoding="utf-8")

            elif op_type == "create":
                if full.exists():
                    raise RuntimeError(f"Файл уже существует, create отменен: {op.get('path')}")

                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text(op.get("content", ""), encoding="utf-8")

            elif op_type == "write":
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text(op.get("content", ""), encoding="utf-8")

        tests_ok, tests_output = _run_tests(patch.get("tests", []), changed_files)

        if not tests_ok:
            restored = _restore_rollback(rollback_path)
            _record_failed_patch(
                patch,
                patch_path,
                rollback_path,
                changed_files,
                tests_output,
                "tests failed",
            )

            return (
                "Patch применен, но тесты упали. Изменения ОТКАЧЕНЫ.\n\n"
                f"Rollback: {rollback_path}\n"
                f"Восстановлено: {restored}\n\n"
                f"Тесты:\n{tests_output}"
            )

        set_value("last_self_applied_patch", str(patch_path))
        response_file = _current_response_file(patch_path)
        registry_entry = register_applied_patch(
            patch=patch,
            patch_file=patch_path,
            rollback_file=rollback_path,
            tests_ok=tests_ok,
            tests_output=tests_output,
            response_file=response_file,
            changed_files=_registry_changed_files(changed_files),
            source=_patch_source(patch_path, response_file),
        )

        return (
            "Patch успешно применен.\n"
            f"Patch: {patch_path}\n"
            f"Rollback: {rollback_path}\n"
            f"Patch Registry: {registry_entry.get('version')} записан\n"
            f"{backup_result}\n\n"
            f"Тесты:\n{tests_output}"
        )

    except Exception as e:
        restored = _restore_rollback(rollback_path)
        _record_failed_patch(
            patch,
            patch_path,
            rollback_path,
            changed_files,
            "",
            e,
        )

        return (
            "Ошибка применения patch. Изменения ОТКАЧЕНЫ.\n"
            f"Ошибка: {e}\n"
            f"Rollback: {rollback_path}\n"
            f"Восстановлено: {restored}"
        )


def rollback_last_patch():
    path = get_value("last_self_rollback")

    if not path:
        return "Rollback не найден."

    rollback_path = Path(path)

    if not rollback_path.exists():
        return f"Rollback-файл не найден: {rollback_path}"

    restored = _restore_rollback(rollback_path)

    return (
        "Rollback выполнен.\n"
        f"Файл: {rollback_path}\n"
        f"Восстановлено: {restored}"
    )


def repair_last_patch():
    path = get_value("last_self_patch")

    if not path:
        return "Последний self-edit patch не найден."

    patch_path = Path(path)

    if not patch_path.exists():
        return f"Patch не найден: {patch_path}"

    try:
        patch = json.loads(patch_path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Не удалось прочитать patch JSON: {e}"

    operations = patch.get("operations", [])

    if not operations:
        return "В patch нет operations, ремонт невозможен."

    repaired = []
    failed = []

    for op in operations:
        op_type = op.get("type")
        rel_path = op.get("path")
        old = op.get("old", "")
        new = op.get("new", "")

        if op_type != "replace":
            repaired.append(op)
            continue

        full = _safe_path(rel_path)

        if not full or not full.exists():
            failed.append(f"{rel_path}: файл не найден")
            repaired.append(op)
            continue

        current = full.read_text(encoding="utf-8", errors="replace")

        if old and old in current:
            repaired.append(op)
            continue

        if new and new in current:
            op["already_applied"] = True
            repaired.append(op)
            continue

        system = """
Ты ремонтируешь JSON patch для Python-проекта.
Нужно найти точный old-фрагмент в текущем файле, который надо заменить на new.

Верни только JSON без markdown:
{
  "old": "точный фрагмент из файла",
  "new": "новый фрагмент"
}

Правила:
- old обязан быть точной подстрокой текущего файла
- old должен быть минимальным, но уникальным
- new сохрани по смыслу из исходного patch
- не добавляй объяснения
"""

        user = f"""
Patch summary:
{patch.get("summary", "")}

Файл:
{rel_path}

Текущий неверный old:
{old}

Желаемый new:
{new}

Текущее содержимое файла:
{current[:16000]}
"""

        try:
            answer = _call_llm(system, user, max_tokens=2000)
            data = _extract_json(answer)

            fixed_old = data.get("old", "")
            fixed_new = data.get("new", new)

            if not fixed_old or fixed_old not in current:
                failed.append(f"{rel_path}: LLM не дала точный old")
                repaired.append(op)
                continue

            repaired.append(
                {
                    "type": "replace",
                    "path": rel_path,
                    "old": fixed_old,
                    "new": fixed_new,
                }
            )

        except Exception as e:
            failed.append(f"{rel_path}: {e}")
            repaired.append(op)

    patch["operations"] = repaired
    patch["summary"] = str(patch.get("summary", "")) + " [repaired]"
    patch["repaired_at"] = datetime.now().isoformat(timespec="seconds")

    patch_path.write_text(
        json.dumps(patch, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if failed:
        return (
            "Patch частично отремонтирован, но есть проблемы:\n"
            + "\n".join(failed)
            + f"\n\nФайл patch: {patch_path}"
        )

    return f"Patch отремонтирован успешно:\n{patch_path}"


def project_health():
    py_files = []

    for path in ROOT_DIR.rglob("*.py"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue

        py_files.append(path)

    if not py_files:
        return "Python-файлы не найдены."

    errors = []
    ok_count = 0

    for path in py_files:
        rel = str(path.relative_to(ROOT_DIR)).replace("\\", "/")

        result = subprocess.run(
            ["python", "-m", "py_compile", rel],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            ok_count += 1
        else:
            errors.append(
                f"{rel}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

    if errors:
        return (
            "Self-check проекта: ❌ есть ошибки.\n"
            f"OK: {ok_count}\n"
            f"Ошибок: {len(errors)}\n\n"
            + "\n\n".join(errors[:10])
        )

    return f"Self-check проекта: ✅ все Python-файлы компилируются. Проверено: {ok_count}"


def auto_edit(goal: str):
    created = create_patch(goal)
    applied = apply_last_patch()

    return created + "\n\n--- APPLY RESULT ---\n\n" + applied
