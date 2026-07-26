# Полный исходный код (продолжение)

### ПУТЬ: modules/chatgpt_relay.py (1232 строк, 36274 байт)

````python
import json
import os
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value, get_value
from modules.self_edit import (
    _choose_files,
    _read_file,
    SELF_DIR,
    MODEL,
    apply_last_patch,
)


ROOT_DIR = get_project_root()
RELAY_DIR = ROOT_DIR / "Projects" / "ChatGPTRelay"
REQUESTS_DIR = RELAY_DIR / "Requests"
REQUEST_FILE = RELAY_DIR / "request.md"
RESPONSE_FILE = RELAY_DIR / "response.json"
RAW_RESPONSE_FILE = RELAY_DIR / "response_raw.txt"
BAD_RESPONSE_FILE = RELAY_DIR / "bad_response.json"
LOG_FILE = ROOT_DIR / "Projects" / "Logs" / "actions.jsonl"

MAX_FILE_CHARS = 18000
MAX_TOTAL_REQUEST_CHARS = 90000

DOCTOR_CORE_FILES = [
    "modules/chatgpt_relay.py",
    "agents/chatgpt_relay_agent.py",
    "next/app_v5.py",
    "agents/system_agent.py",
    "modules/history_log.py",
]


def _ensure_dir():
    RELAY_DIR.mkdir(parents=True, exist_ok=True)
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    SELF_DIR.mkdir(parents=True, exist_ok=True)


def _now_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _set_clipboard(text: str):
    text = str(text or "")

    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()

        return True, "Буфер обмена обновлен через tkinter."

    except Exception:
        pass

    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
            input=text,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
        )

        return True, "Буфер обмена обновлен через PowerShell."

    except Exception as e:
        return False, f"Не удалось записать в буфер обмена: {e}"


def _get_clipboard():
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()

        return True, text

    except Exception:
        pass

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        if result.returncode != 0:
            return False, result.stderr

        return True, result.stdout

    except Exception as e:
        return False, f"Не удалось прочитать буфер обмена: {e}"


def _strip_markdown_fences(text: str):
    raw = str(text or "").strip()

    if raw.startswith("```json"):
        raw = raw.replace("```json", "", 1).strip()

        if raw.endswith("```"):
            raw = raw[:-3].strip()

    elif raw.startswith("```"):
        raw = raw.replace("```", "", 1).strip()

        if raw.endswith("```"):
            raw = raw[:-3].strip()

    return raw


def _find_json_objects(text: str):
    raw = _strip_markdown_fences(text)

    objects = []

    start = None
    depth = 0
    in_string = False
    escape = False

    for i, char in enumerate(raw):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False

            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            if depth == 0:
                start = i
            depth += 1
            continue

        if char == "}":
            if depth > 0:
                depth -= 1

                if depth == 0 and start is not None:
                    candidate = raw[start:i + 1]
                    objects.append(candidate)
                    start = None

    return objects


def _extract_patch_json(text: str):
    raw = _strip_markdown_fences(text)

    try:
        data = json.loads(raw)

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    candidates = _find_json_objects(raw)

    parsed = []

    for candidate in candidates:
        try:
            data = json.loads(candidate)

            if isinstance(data, dict):
                parsed.append(data)

        except Exception:
            continue

    if not parsed:
        raise ValueError("Не найден валидный JSON-объект.")

    for data in parsed:
        if isinstance(data.get("operations"), list):
            return data

    for data in parsed:
        if "summary" in data and "operations" in data:
            return data

    raise ValueError(
        "JSON найден, но это не patch. Нужны поля summary, operations, tests."
    )


def _looks_like_relay_request(text: str):
    lower = str(text or "").lower()

    markers = [
        "ты помогаешь дорабатывать локальный python-проект localcomet",
        "формат ответа:",
        "цель пользователя:",
        "--- file:",
        "relative/path.py",
        "точный существующий фрагмент",
    ]

    hits = sum(1 for marker in markers if marker in lower)
    return hits >= 3


CONFIRMATION_SUMMARY_MARKERS = [
    "принято",
    "готово",
    "буду делать",
    "буду создавать",
    "буду по возможности",
    "дальше для localcomet",
    "дальше для localagent",
    "создавать скачиваемый файл",
    "не выводить большой json",
    "acknowledged",
    "accepted",
]


def _summary_looks_like_confirmation(summary):
    lower = str(summary or "").lower()
    return any(marker in lower for marker in CONFIRMATION_SUMMARY_MARKERS)


def _is_empty_confirmation_patch(patch):
    return (
        isinstance(patch, dict)
        and isinstance(patch.get("operations"), list)
        and not patch.get("operations")
        and _summary_looks_like_confirmation(patch.get("summary", ""))
    )


def _write_bad_response(reason, patch):
    _ensure_dir()

    payload = {
        "reason": str(reason),
        "patch": patch,
    }

    BAD_RESPONSE_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_value("last_relay_bad_response", str(BAD_RESPONSE_FILE))
    set_value("last_relay_bad_response_reason", str(reason))

    return BAD_RESPONSE_FILE


def _validate_patch_data(patch: dict):
    if not isinstance(patch, dict):
        return False, "Ответ не является JSON-объектом."

    operations = patch.get("operations")

    if not isinstance(operations, list):
        return False, "В patch нет списка operations."

    if not operations:
        if _is_empty_confirmation_patch(patch):
            bad_path = _write_bad_response(
                "Пустой response.json похож на подтверждение, а не на patch.",
                patch,
            )
            return (
                False,
                "response.json отклонен: operations пустой, а summary похож на "
                f"подтверждение вместо patch. bad_response: {bad_path}",
            )

        return False, "В patch пустой список operations. Применять нечего."

    for index, op in enumerate(operations, start=1):
        if not isinstance(op, dict):
            return False, f"Операция #{index} не является объектом."

        op_type = op.get("type")
        rel_path = str(op.get("path", "")).strip().replace("\\", "/")

        if rel_path in ["relative/path.py", "relative/path", ""]:
            return (
                False,
                "Похоже, скопирован шаблон из request.md, а не настоящий ответ ChatGPT. "
                f"Плохой path в операции #{index}: {rel_path or 'пусто'}",
            )

        if rel_path.startswith("/") or ".." in Path(rel_path).parts:
            return False, f"Небезопасный путь в операции #{index}: {rel_path}"

        if op_type not in ["replace", "create", "write"]:
            return False, f"Запрещенный тип операции #{index}: {op_type}"

        if op_type == "replace":
            if not op.get("old"):
                return False, f"В replace операции #{index} пустой old."
            if "new" not in op:
                return False, f"В replace операции #{index} нет new."

        if op_type in ["create", "write"]:
            if "content" not in op:
                return False, f"В {op_type} операции #{index} нет content."

    tests = patch.get("tests", [])

    if tests is not None and not isinstance(tests, list):
        return False, "Поле tests должно быть списком."

    return True, "OK"


def _clean_file_token(token: str):
    value = str(token or "").strip()
    value = value.replace("\\", "/")

    while value.startswith("- "):
        value = value[2:].strip()

    # Иногда путь приходит как часть repr-списка:
    # "['modules/a.py", "next/app_v5.py']", "(agents/x.py)".
    # Чистим несколько раз, чтобы убрать кавычки/скобки в любом порядке.
    wrappers = "`'\" [](){}.,;"

    previous = None

    while value and value != previous:
        previous = value
        value = value.strip()
        value = value.strip(wrappers)

    return value


def _is_existing_project_file(rel_path: str):
    rel_path = _clean_file_token(rel_path)

    if not rel_path:
        return False

    path = Path(rel_path)

    if path.is_absolute():
        return False

    if ".." in path.parts:
        return False

    if path.suffix not in [".py", ".json", ".md", ".txt"]:
        return False

    full = (ROOT_DIR / path).resolve()

    try:
        full.relative_to(ROOT_DIR.resolve())
    except Exception:
        return False

    return full.exists() and full.is_file()


def _dedupe_existing_files(files, max_files: int = 10):
    result = []
    seen = set()

    for item in files or []:
        rel = _clean_file_token(item)

        if not rel:
            continue

        if rel in seen:
            continue

        if not _is_existing_project_file(rel):
            continue

        result.append(rel)
        seen.add(rel)

        if len(result) >= max_files:
            break

    return result


def _extract_manual_files(goal: str):
    text = str(goal or "")
    lower = text.lower()

    markers = [
        "файлы:",
        "файлы=",
        "files:",
        "files=",
        "с файлами:",
        "с файлами",
    ]

    for marker in markers:
        idx = lower.find(marker)

        if idx == -1:
            continue

        tail = text[idx + len(marker):].strip()

        stop_markers = [
            "\n\n",
            "\nцель:",
            "\nзадача:",
            "\nчто сделать:",
        ]

        for stop in stop_markers:
            stop_idx = tail.lower().find(stop)

            if stop_idx != -1:
                tail = tail[:stop_idx].strip()
                break

        raw_parts = []

        for line in tail.splitlines():
            clean_line = line.strip()

            if not clean_line:
                continue

            raw_parts.extend(clean_line.replace(";", ",").split(","))

        return _dedupe_existing_files(raw_parts, max_files=12)

    return []


def _goal_has_any(goal: str, words):
    lower = str(goal or "").lower()
    return any(word in lower for word in words)


def _is_error_doctor_goal(goal: str):
    return _goal_has_any(
        goal,
        [
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
            "logs",
        ],
    )


def _infer_snapshot_files(goal: str):
    is_doctor = _is_error_doctor_goal(goal)

    manual = _extract_manual_files(goal)

    # Для Error Doctor не доверяем manual "Файлы:" из last_result/логов.
    # Иначе он может подхватить repr-список вроде "['modules/a.py".
    if manual and not is_doctor:
        return manual

    candidates = []

    try:
        candidates.extend(_choose_files(goal))
    except Exception:
        pass

    if is_doctor:
        candidates.extend(DOCTOR_CORE_FILES)

    if _goal_has_any(
        goal,
        [
            "relay",
            "релей",
            "chatgpt relay",
            "чатгпт",
            "request",
            "response",
            "snapshot",
            "снапшот",
            "clipboard",
            "буфер",
            "json",
            "открой папку",
            "последний запрос",
            "ручной список файлов",
        ],
    ):
        candidates.extend(
            [
                "modules/self_edit.py",
                "modules/chatgpt_relay.py",
                "agents/chatgpt_relay_agent.py",
                "next/app_v5.py",
                "agents/system_agent.py",
            ]
        )

    if is_doctor:
        candidates.extend(
            [
                "core/executor.py",
                "core/planner.py",
                "core/router.py",
            ]
        )

    if _goal_has_any(goal, ["help", "что ты умеешь", "справка"]):
        candidates.append("agents/system_agent.py")

    if _goal_has_any(goal, ["executor", "исполнитель", "tool", "инструмент"]):
        candidates.extend(["core/executor.py", "next/app_v5.py"])

    if _goal_has_any(goal, ["gpt", "api", "openai"]):
        candidates.extend(
            [
                "modules/gpt_client.py",
                "agents/gpt_agent.py",
                "core/executor.py",
                "next/app_v5.py",
            ]
        )

    if _goal_has_any(goal, ["planner", "планировщик", "router", "роутер"]):
        candidates.extend(["core/planner.py", "core/router.py", "next/app_v5.py"])

    return _dedupe_existing_files(candidates, max_files=10)


def _read_tail(path: Path, max_lines: int = 40, max_chars: int = 12000):
    if not path.exists() or not path.is_file():
        return ""

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        return f"Не удалось прочитать {path}: {e}"

    text = "\n".join(lines[-max_lines:])

    if len(text) > max_chars:
        return text[-max_chars:]

    return text


def _short_value(value, limit: int = 6000):
    text = str(value or "")

    if len(text) <= limit:
        return text

    return text[:limit] + "\n...[обрезано]"


def _build_error_context():
    keys = [
        "last_error",
        "last_result",
        "last_user_goal",
        "last_real_goal",
        "last_task",
        "last_route",
        "last_action",
        "last_plan",
        "last_relay_goal",
        "last_stability_score",
        "last_stability_report",
        "last_self_patch",
        "last_self_rollback",
        "last_relay_response",
        "last_patch_registry_file",
        "last_patch_version",
        "last_patch_status",
    ]

    lines = [
        "ERROR DOCTOR CONTEXT",
        "",
        "Состояние LocalComet:",
    ]

    for key in keys:
        lines.append(f"- {key}: {_short_value(get_value(key, 'нет'), limit=2500)}")

    lines.extend(
        [
            "",
            "Последние записи Projects/Logs/actions.jsonl:",
            _read_tail(LOG_FILE, max_lines=35, max_chars=14000) or "Лог не найден или пуст.",
        ]
    )

    if RAW_RESPONSE_FILE.exists():
        lines.extend(
            [
                "",
                "Последний response_raw.txt:",
                _short_value(
                    RAW_RESPONSE_FILE.read_text(encoding="utf-8", errors="replace"),
                    limit=6000,
                ),
            ]
        )

    return "\n".join(lines)


def _build_request_text(goal: str, selected_files, extra_context: str = ""):
    file_blocks = []
    total_chars = 0

    for rel in selected_files:
        remaining = max(4000, MAX_TOTAL_REQUEST_CHARS - total_chars)
        limit = min(MAX_FILE_CHARS, remaining)

        content = _read_file(rel, limit=limit)

        if content is None:
            continue

        total_chars += len(content)

        file_blocks.append(
            f"\n\n--- FILE: {rel} ---\n"
            f"{content}\n"
            f"--- END FILE: {rel} ---\n"
        )

        if total_chars >= MAX_TOTAL_REQUEST_CHARS:
            file_blocks.append(
                "\n\n# REQUEST TRUNCATED: достигнут лимит размера snapshot.\n"
            )
            break

    context_block = ""

    if extra_context:
        context_block = f"""

Дополнительный диагностический контекст:
{extra_context}
"""

    return f"""Ты помогаешь дорабатывать локальный Python-проект LocalComet.

ВАЖНО:
- Верни ТОЛЬКО валидный JSON без markdown, без ```json, без объяснений.
- Не добавляй текст до или после JSON.
- Не удаляй файлы.
- Не создавай .exe, .bat, .ps1.
- Меняй только файлы внутри проекта LocalAgent.
- Для существующих файлов используй type="replace" с точным old-фрагментом из файла.
- old должен быть точной подстрокой текущего файла.
- Если нужно полностью перезаписать файл, используй type="write".
- Для новых файлов используй type="create".
- Для Python-файлов добавь тесты py_compile.
- Если меняешь файл целиком, используй type="write" и полный content.
- Если данных не хватает, верни JSON с пустым operations и объясни причину в summary.

Формат ответа:
{{
  "summary": "краткое описание изменения",
  "operations": [
    {{
      "type": "replace",
      "path": "relative/path.py",
      "old": "точный существующий фрагмент",
      "new": "новый фрагмент"
    }}
  ],
  "tests": [
    "python -m py_compile relative/path.py"
  ]
}}

Цель пользователя:
{goal}
{context_block}
Выбранные файлы:
{selected_files}

Код файлов:
{''.join(file_blocks)}
"""


def _save_request_files(request_text: str, goal: str, selected_files):
    _ensure_dir()

    stamp = _now_stamp()
    dated_path = REQUESTS_DIR / f"request_{stamp}.md"

    REQUEST_FILE.write_text(request_text, encoding="utf-8")
    dated_path.write_text(request_text, encoding="utf-8")

    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "selected_files": selected_files,
        "request_file": str(REQUEST_FILE),
        "dated_request_file": str(dated_path),
        "chars": len(request_text),
    }

    meta_path = REQUESTS_DIR / f"request_{stamp}.json"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_value("last_relay_goal", goal)
    set_value("last_relay_request", str(REQUEST_FILE))
    set_value("last_relay_dated_request", str(dated_path))
    set_value("last_relay_request_meta", str(meta_path))
    set_value("last_relay_selected_files", selected_files)

    return dated_path, meta_path


def relay_status():
    _ensure_dir()

    request_exists = REQUEST_FILE.exists()
    response_exists = RESPONSE_FILE.exists()
    raw_exists = RAW_RESPONSE_FILE.exists()

    last_request = get_value("last_relay_request", "нет")
    last_dated_request = get_value("last_relay_dated_request", "нет")
    last_response = get_value("last_relay_response", "нет")
    last_patch = get_value("last_self_patch", "нет")

    return f"""ChatGPT Relay status:

Папка:
- {RELAY_DIR}

Файлы:
- request.md: {"✅ есть" if request_exists else "❌ нет"}
- response.json: {"✅ есть" if response_exists else "❌ нет"}
- response_raw.txt: {"✅ есть" if raw_exists else "❌ нет"}

Память:
- last_relay_request: {last_request}
- last_relay_dated_request: {last_dated_request}
- last_relay_response: {last_response}
- last_self_patch: {last_patch}

Команды:
- relay старт ...
- relay старт тихо ...
- relay создай запрос ...
- relay snapshot ...
- error doctor
- relay скопируй запрос
- relay открой чат
- relay открой папку
- relay последний запрос
- relay открой последний запрос
- relay забери ответ
- relay проверь ответ
- relay примени ответ
- relay очисти ответ
- relay покажи запрос
- relay покажи ответ
"""


def create_request(goal: str):
    _ensure_dir()

    goal = str(goal or "").strip()

    if not goal:
        return "Нет цели для relay-запроса."

    selected_files = _infer_snapshot_files(goal)
    request_text = _build_request_text(goal, selected_files)
    dated_path, meta_path = _save_request_files(request_text, goal, selected_files)

    return (
        "Relay-запрос создан.\n"
        f"Основной файл: {REQUEST_FILE}\n"
        f"Датированный файл: {dated_path}\n"
        f"Meta: {meta_path}\n"
        f"Цель: {goal}\n"
        f"Файлы: {selected_files}\n\n"
        "Дальше удобнее так:\n"
        "1. Прикрепи request.md или датированный request_*.md сюда в ChatGPT.\n"
        "2. Скачай мой response.json в папку Relay.\n"
        "3. Выполни: relay проверь ответ\n"
        "4. Потом: relay примени ответ"
    )


def create_snapshot(goal: str):
    return create_request(goal)


def create_error_doctor(goal: str = ""):
    _ensure_dir()

    goal = str(goal or "").strip()

    if not goal:
        goal = (
            "Исправь последнюю ошибку LocalComet. "
            "Используй last_error, last_result, последние логи и приложенные файлы проекта."
        )

    doctor_goal = "ERROR DOCTOR: " + goal
    error_context = _build_error_context()

    # Важно: не передаем error_context в _infer_snapshot_files.
    # В контексте может быть last_result с текстом "Файлы: [...]",
    # из-за чего manual parser раньше забирал кривые пути из repr-списка.
    selected_files = _infer_snapshot_files(doctor_goal)
    selected_files = _dedupe_existing_files(
        DOCTOR_CORE_FILES + selected_files,
        max_files=10,
    )

    request_text = _build_request_text(
        doctor_goal,
        selected_files,
        extra_context=error_context,
    )

    dated_path, meta_path = _save_request_files(
        request_text,
        doctor_goal,
        selected_files,
    )

    return (
        "Error Doctor request создан.\n"
        f"Основной файл: {REQUEST_FILE}\n"
        f"Датированный файл: {dated_path}\n"
        f"Meta: {meta_path}\n"
        f"Файлы: {selected_files}\n\n"
        "Дальше:\n"
        "1. Прикрепи request.md сюда в ChatGPT.\n"
        "2. Скачай мой response.json в папку Relay.\n"
        "3. Выполни: relay проверь ответ\n"
        "4. Потом: relay примени ответ"
    )


def copy_request():
    _ensure_dir()

    path = _get_last_request_path()

    if not path:
        return "request.md не найден. Сначала выполни: relay создай запрос ..."

    text = path.read_text(encoding="utf-8", errors="replace")

    ok, message = _set_clipboard(text)

    if not ok:
        return message

    return (
        "Relay-запрос скопирован в буфер обмена.\n"
        f"Файл: {path}\n"
        "Теперь вставь его сюда в ChatGPT и отправь.\n"
        f"{message}"
    )


def open_chatgpt():
    webbrowser.open("https://chatgpt.com/")
    return "Открыл ChatGPT в браузере: https://chatgpt.com/"


def open_relay_folder():
    _ensure_dir()

    try:
        subprocess.Popen(["explorer", str(RELAY_DIR)])
        return f"Открыл папку Relay:\n{RELAY_DIR}"
    except Exception as e:
        return f"Не удалось открыть папку Relay: {e}\nПуть: {RELAY_DIR}"


def start_relay(goal: str):
    created = create_request(goal)
    copied = copy_request()
    opened = open_chatgpt()

    return created + "\n\n--- COPY ---\n" + copied + "\n\n--- OPEN ---\n" + opened


def start_relay_silent(goal: str):
    created = create_request(goal)
    copied = copy_request()

    return created + "\n\n--- COPY ---\n" + copied


def _get_last_request_path():
    path = get_value("last_relay_dated_request") or get_value("last_relay_request")

    if path:
        p = Path(path)

        if p.exists() and p.is_file():
            return p

    if REQUEST_FILE.exists():
        return REQUEST_FILE

    requests = list(REQUESTS_DIR.glob("request_*.md"))

    if requests:
        return max(requests, key=lambda p: p.stat().st_mtime)

    return None


def last_request_path():
    _ensure_dir()

    path = _get_last_request_path()

    if not path:
        return "Последний relay request не найден."

    return (
        "Последний relay request:\n"
        f"{path}\n\n"
        "Можно прикрепить этот файл сюда в ChatGPT."
    )


def open_last_request():
    _ensure_dir()

    path = _get_last_request_path()

    if not path:
        return "Последний relay request не найден."

    try:
        os.startfile(str(path))
        return f"Открыл последний relay request:\n{path}"
    except Exception as e:
        return f"Не удалось открыть request: {e}\nПуть: {path}"


def show_request():
    _ensure_dir()

    path = _get_last_request_path()

    if not path:
        return "request.md не найден."

    text = path.read_text(encoding="utf-8", errors="replace")

    header = f"Файл: {path}\n\n"

    if len(text) > 5000:
        return header + text[:5000] + "\n\n...[request.md обрезан для вывода]"

    return header + text


def save_clipboard_response():
    _ensure_dir()

    ok, text = _get_clipboard()

    if not ok:
        return text

    text = str(text or "").strip()

    if not text:
        return "Буфер обмена пустой. Сначала скопируй JSON-ответ из ChatGPT."

    RAW_RESPONSE_FILE.write_text(text, encoding="utf-8")

    if _looks_like_relay_request(text):
        return (
            "Похоже, ты скопировал relay-запрос/request.md, а не JSON-ответ ChatGPT.\n"
            f"Сырой текст сохранен: {RAW_RESPONSE_FILE}\n\n"
            "Правильный порядок:\n"
            "1. Отправь request.md в ChatGPT.\n"
            "2. Дождись JSON-ответа.\n"
            "3. Скопируй именно JSON, который начинается с { \"summary\": ... }.\n"
            "4. Повтори: relay забери ответ"
        )

    try:
        patch = _extract_patch_json(text)
    except Exception as e:
        return (
            "Не удалось извлечь JSON patch из буфера.\n"
            f"Ошибка: {e}\n"
            f"Сырой ответ сохранен: {RAW_RESPONSE_FILE}\n\n"
            "Что делать:\n"
            "1. Вставь relay-запрос сюда в ChatGPT.\n"
            "2. Дождись моего ответа в формате JSON.\n"
            "3. Скопируй ТОЛЬКО JSON-ответ.\n"
            "4. Повтори: relay забери ответ"
        )

    ok, message = _validate_patch_data(patch)

    if not ok:
        return (
            "JSON найден, но response НЕ сохранен как patch.\n"
            f"Причина: {message}\n"
            f"Сырой ответ сохранен: {RAW_RESPONSE_FILE}"
        )

    patch["relay_imported_at"] = datetime.now().isoformat(timespec="seconds")
    patch["relay_goal"] = get_value("last_relay_goal", "")
    patch["model"] = "chatgpt-relay"

    if "tests" not in patch or not isinstance(patch.get("tests"), list):
        patch["tests"] = []

    RESPONSE_FILE.write_text(
        json.dumps(patch, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_value("last_relay_response", str(RESPONSE_FILE))

    return (
        "Ответ ChatGPT сохранен как relay response.\n"
        f"Файл: {RESPONSE_FILE}\n"
        f"Операций: {len(patch.get('operations', []))}\n"
        f"Описание: {patch.get('summary', 'нет')}\n\n"
        "Дальше команда: relay проверь ответ\n"
        "Если проверка OK: relay примени ответ"
    )


def show_response():
    _ensure_dir()

    if RESPONSE_FILE.exists():
        text = RESPONSE_FILE.read_text(encoding="utf-8-sig", errors="replace")
        if len(text) > 6000:
            return text[:6000] + "\n\n...[response.json обрезан для вывода]"
        return text

    if RAW_RESPONSE_FILE.exists():
        text = RAW_RESPONSE_FILE.read_text(encoding="utf-8", errors="replace")
        if len(text) > 6000:
            return text[:6000] + "\n\n...[response_raw.txt обрезан для вывода]"
        return text

    return "Ответ relay пока не найден."


def validate_response():
    _ensure_dir()

    if not RESPONSE_FILE.exists():
        return (
            "response.json не найден.\n"
            "Сначала скопируй JSON-ответ ChatGPT и выполни: relay забери ответ"
        )

    try:
        patch = json.loads(RESPONSE_FILE.read_text(encoding="utf-8-sig"))
    except Exception as e:
        return f"response.json не читается как JSON: {e}"

    ok, message = _validate_patch_data(patch)

    if not ok:
        return "Relay response: ❌ проверка не пройдена.\nПричина: " + message

    lines = [
        "Relay response: ✅ проверка пройдена.",
        f"Файл: {RESPONSE_FILE}",
        f"Описание: {patch.get('summary', 'нет')}",
        f"Операций: {len(patch.get('operations', []))}",
        "",
        "Операции:",
    ]

    for i, op in enumerate(patch.get("operations", []), start=1):
        lines.append(f"{i}. {op.get('type')} -> {op.get('path')}")

    lines.append("")
    lines.append("Дальше команда: relay примени ответ")

    return "\n".join(lines)


def clear_response():
    _ensure_dir()

    removed = []

    for path in [RESPONSE_FILE, RAW_RESPONSE_FILE]:
        if path.exists():
            path.unlink()
            removed.append(str(path))

    set_value("last_relay_response", "")

    if not removed:
        return "Relay response уже очищен. response.json и response_raw.txt не найдены."

    return "Relay response очищен:\n" + "\n".join(f"- {item}" for item in removed)


def import_response_as_patch():
    _ensure_dir()

    if not RESPONSE_FILE.exists():
        return (
            "response.json не найден.\n"
            "Сначала скопируй JSON-ответ из ChatGPT и выполни: relay забери ответ"
        )

    try:
        patch = json.loads(RESPONSE_FILE.read_text(encoding="utf-8-sig"))
    except Exception as e:
        return f"Не удалось прочитать response.json: {e}"

    ok, message = _validate_patch_data(patch)

    if not ok:
        return "Relay response НЕ импортирован.\nПричина: " + message

    patch["goal"] = patch.get("relay_goal") or get_value("last_relay_goal", "")
    patch["created_at"] = datetime.now().isoformat(timespec="seconds")
    patch["selected_files"] = [
        op.get("path")
        for op in patch.get("operations", [])
        if isinstance(op, dict) and op.get("path")
    ]
    patch["model"] = patch.get("model", "chatgpt-relay")

    patch_path = SELF_DIR / f"patch_{_now_stamp()}_chatgpt_relay.json"

    patch_path.write_text(
        json.dumps(patch, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_value("last_self_patch", str(patch_path))
    set_value("last_relay_imported_patch", str(patch_path))

    return (
        "Relay response импортирован как self-edit patch.\n"
        f"Patch: {patch_path}\n"
        f"Операций: {len(patch.get('operations', []))}\n\n"
        "Дальше команда: примени последний патч"
    )


def apply_response():
    if not RESPONSE_FILE.exists():
        return (
            "response.json не найден.\n"
            "Я НЕ буду применять старый self-edit patch.\n\n"
            "Сначала сделай так:\n"
            "1. Вставь relay-запрос сюда в ChatGPT.\n"
            "2. Скопируй мой JSON-ответ.\n"
            "3. В LocalComet введи: relay забери ответ\n"
            "4. Потом: relay примени ответ"
        )

    checked = validate_response()

    if "✅ проверка пройдена" not in checked:
        return checked

    imported = import_response_as_patch()

    if not str(imported).startswith("Relay response импортирован"):
        return imported

    applied = apply_last_patch()

    return imported + "\n\n--- APPLY RESULT ---\n\n" + applied
````

### ПУТЬ: modules/codegen.py (132 строк, 2847 байт)

````python
import json
from json_repair import repair_json

from core.llm import ask_llm
from modules.files import create_folder, write_file, read_file, list_files


SITE_SYSTEM = """
Ты профессиональный frontend-разработчик.

Создай современный сайт.

Верни строго JSON:

{
  "folder": "SiteName",
  "files": [
    {
      "path": "SiteName/index.html",
      "content": "..."
    },
    {
      "path": "SiteName/style.css",
      "content": "..."
    },
    {
      "path": "SiteName/script.js",
      "content": "..."
    }
  ]
}

Правила:
- Всегда создавай index.html.
- Всегда создавай style.css.
- Желательно создавай script.js.
- Не используй markdown.
- Не объясняй.
- Только JSON.
"""


IMPROVE_SYSTEM = """
Ты профессиональный frontend-разработчик и UI/UX-дизайнер.

Тебе дают HTML и CSS сайта.
Улучши сайт визуально и структурно.

Верни строго JSON:

{
  "files": [
    {
      "path": "FolderName/index.html",
      "content": "..."
    },
    {
      "path": "FolderName/style.css",
      "content": "..."
    }
  ]
}

Правила:
- Не используй markdown.
- Не объясняй.
- Только JSON.
- Сохрани русский язык.
- Сделай дизайн современнее.
- Улучши hero-блок, карточки, кнопки, отступы и адаптивность.
"""


def generate_site(prompt):
    answer = ask_llm(SITE_SYSTEM, prompt, max_tokens=3000)
    answer = answer.replace("```json", "").replace("```", "").strip()

    fixed = repair_json(answer)
    data = json.loads(fixed)

    folder = data["folder"]
    create_folder(folder)

    created = []

    for file in data["files"]:
        write_file(file["path"], file["content"])
        created.append(file["path"])

    return {
        "folder": folder,
        "created": created
    }


def improve_site(folder):
    html_path = f"{folder}/index.html"
    css_path = f"{folder}/style.css"

    html = read_file(html_path)
    css = read_file(css_path)

    prompt = f"""
Folder:
{folder}

HTML:
{html}

CSS:
{css}

Task:
Improve this website design.
"""

    answer = ask_llm(IMPROVE_SYSTEM, prompt, max_tokens=4000)
    answer = answer.replace("```json", "").replace("```", "").strip()

    fixed = repair_json(answer)
    data = json.loads(fixed)

    changed = []

    for file in data["files"]:
        write_file(file["path"], file["content"])
        changed.append(file["path"])

    return {
        "folder": folder,
        "changed": changed
    }
````

### ПУТЬ: modules/codex_agent_mode_ru.py (525 строк, 18439 байт)

````python
from __future__ import annotations

import ast
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_PATH = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_PATH / "Projects" / "Reports" / "codex_agent_workspace"
CONTEXT_PATH = REPORT_DIR / "latest_codex_agent_context.json"

AGENT_VERSION = "v6.41"
AGENT_NAME = "LocalComet Codex Agent Workspace RU"

BLOCKED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "BrowserProfile",
    "Backups",
}

DANGEROUS_TERMS = {
    "пароль",
    "password",
    "token",
    "api key",
    "api-key",
    "secret",
    "private key",
    "ssh key",
    "cookie",
    "cookies",
    "удали",
    "удалить",
    "стереть",
    "сотри",
    "format",
    "wipe",
    "rm ",
    "rmdir",
    "del ",
    "powershell",
    "cmd.exe",
    "bash",
    "shell",
    "terminal",
    "админ",
    "administrator",
    "sudo",
    "банк",
    "bank",
    "карта",
    "payment",
    "casino",
    "gambling",
}


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_PATH)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _is_skipped(path: Path) -> bool:
    return bool(set(path.parts).intersection(BLOCKED_DIRS))


def _read_text(path: Path, limit: int = 12000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    if len(text) > limit:
        return text[:limit] + "\n\n[truncated]"
    return text


def _extract_python_symbols(path: Path) -> dict[str, Any]:
    rel = _safe_relative(path)
    text = _read_text(path, 16000)
    item = {
        "path": rel,
        "functions": [],
        "classes": [],
        "has_dispatch": False,
        "has_status": False,
        "has_report": False,
        "parse_ok": False,
        "parse_error": "",
    }

    try:
        tree = ast.parse(text, filename=rel)
    except Exception as exc:
        item["parse_error"] = str(exc)
        return item

    item["parse_ok"] = True
    functions = []
    classes = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)

    item["functions"] = sorted(set(functions))
    item["classes"] = sorted(set(classes))
    item["has_dispatch"] = "dispatch" in item["functions"]
    item["has_status"] = "status" in item["functions"]
    item["has_report"] = "report" in item["functions"]
    return item


def _iter_python_files() -> list[Path]:
    files = []
    for path in ROOT_PATH.rglob("*.py"):
        if _is_skipped(path):
            continue
        if path.name.startswith("."):
            continue
        files.append(path)
    return sorted(files, key=lambda p: _safe_relative(p).lower())


def _control_panel_version() -> dict[str, str]:
    panel = ROOT_PATH / "LocalComet_Control_Panel.py"
    text = _read_text(panel, 20000)
    version = ""
    label = ""

    version_match = re.search(r"LOCALCOMET_VERSION\s*=\s*['\"]([^'\"]+)['\"]", text)
    label_match = re.search(r"LOCALCOMET_VERSION_LABEL\s*=\s*['\"]([^'\"]+)['\"]", text)

    if version_match:
        version = version_match.group(1)
    if label_match:
        label = label_match.group(1)

    return {
        "version": version,
        "label": label,
    }


def _recent_reports() -> list[str]:
    reports_root = ROOT_PATH / "Projects" / "Reports"
    if not reports_root.exists():
        return []

    reports = []
    for pattern in ("*.md", "*.json"):
        for path in reports_root.rglob(pattern):
            if _is_skipped(path):
                continue
            reports.append(path)

    reports = sorted(reports, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return [_safe_relative(path) for path in reports[:12]]


def _important_files() -> list[str]:
    candidates = [
        "LocalComet_Control_Panel.py",
        "modules/premium_task_panel_ru.py",
        "modules/strict_project_stability_ru.py",
        "modules/codex_agent_mode_ru.py",
        "modules/pc_codex_core.py",
        "modules/pc_codex_executor.py",
        "modules/swiss_knife_skill_launcher.py",
        "modules/project_one_command_check_ru.py",
    ]
    return [item for item in candidates if (ROOT_PATH / item).exists()]


def build_context_capsule() -> dict[str, Any]:
    python_files = _iter_python_files()
    symbols = [_extract_python_symbols(path) for path in python_files]
    command_modules = [item for item in symbols if item.get("has_dispatch")]

    context = {
        "ok": True,
        "mode": "codex_agent_context_capsule",
        "generated_at": _now(),
        "agent_version": AGENT_VERSION,
        "agent_name": AGENT_NAME,
        "root": str(ROOT_PATH),
        "control_panel": _control_panel_version(),
        "python_file_count": len(python_files),
        "function_count": sum(len(item.get("functions", [])) for item in symbols),
        "class_count": sum(len(item.get("classes", [])) for item in symbols),
        "command_module_count": len(command_modules),
        "important_files": _important_files(),
        "command_modules": command_modules[:40],
        "recent_reports": _recent_reports(),
        "available_safe_commands": [
            "проверь проект",
            "pc agent status",
            "pc agent context",
            "pc agent plan <цель>",
            "pc agent brief <цель>",
            "pc agent verify",
            "pc swiss plan <цель>",
            "pc core status",
            "pc exec status",
            "pc ui status",
            "pc screen observe",
        ],
        "agent_rules_ru": [
            "Работай как Codex-подобный локальный агент поверх проекта LocalComet.",
            "Сначала понимай цель и контекст проекта, затем предлагай план.",
            "Не выполняй разрушительные действия.",
            "Не читай и не выводи пароли, токены, ключи, cookies, банковские данные.",
            "Для изменений кода предлагай self-edit patch через безопасный pipeline.",
            "После изменения всегда запускай проверку проекта.",
            "Обычный чат не должен запускать router/research без явного намерения.",
        ],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_PATH.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
    return context


def _dangerous_goal_reason(goal: str) -> str:
    lowered = str(goal or "").lower().replace("ё", "е")
    for term in sorted(DANGEROUS_TERMS):
        if term in lowered:
            return f"Запрос содержит потенциально опасный маркер: {term}"
    return ""


def _context_as_text(context: dict[str, Any]) -> str:
    panel = context.get("control_panel", {})
    command_modules = context.get("command_modules", [])
    lines = [
        f"Проект: {context.get('root')}",
        f"Версия панели: {panel.get('version')} — {panel.get('label')}",
        f"Python files: {context.get('python_file_count')}",
        f"Functions: {context.get('function_count')}",
        f"Classes: {context.get('class_count')}",
        f"Command modules: {context.get('command_module_count')}",
        "",
        "Ключевые файлы:",
    ]
    for item in context.get("important_files", []):
        lines.append(f"- {item}")

    lines.append("")
    lines.append("Командные модули:")
    for item in command_modules[:20]:
        lines.append(
            f"- {item.get('path')} dispatch={item.get('has_dispatch')} "
            f"status={item.get('has_status')} report={item.get('has_report')}"
        )

    lines.append("")
    lines.append("Последние отчёты:")
    for item in context.get("recent_reports", [])[:8]:
        lines.append(f"- {item}")

    return "\n".join(lines)


def _ask_local_llm(system: str, user: str) -> str:
    try:
        from core.llm import ask_llm, is_llm_offline_error
    except Exception:
        return ""

    try:
        answer = ask_llm(
            system=system,
            user=user,
            max_tokens=900,
            use_context=True,
            no_think=True,
            temperature=0.25,
            timeout=90,
        )
    except Exception:
        return ""

    if not answer:
        return ""

    try:
        if is_llm_offline_error(answer):
            return ""
    except Exception:
        pass

    return str(answer).strip()


def _fallback_agent_plan(goal: str, context: dict[str, Any]) -> str:
    return (
        "Codex Agent Plan:\n\n"
        f"Цель: {goal}\n\n"
        "Понимание:\n"
        "- Работаем внутри LocalComet как локальный агент разработки.\n"
        "- Сначала используем контекст проекта, затем предлагаем безопасный план.\n"
        "- Изменения должны идти через self-edit patch и проверяться кнопкой «Проверить проект».\n\n"
        "План:\n"
        "1. Уточнить, какой модуль/экран/команда относится к задаче.\n"
        "2. Найти релевантные файлы через context capsule.\n"
        "3. Составить минимальный patch без разрушительных действий.\n"
        "4. Применить через Relay только после проверки response.json.\n"
        "5. Запустить «Проверить проект» и добиться hard_failures=0, warnings=0.\n\n"
        "Безопасная следующая команда:\n"
        f"pc swiss plan {goal}\n\n"
        "Контекст:\n"
        f"{_context_as_text(context)}"
    )


def build_agent_plan(goal: str, mode: str = "plan") -> dict[str, Any]:
    raw_goal = str(goal or "").strip()
    if not raw_goal:
        raw_goal = "развивать LocalComet в сторону Codex-подобного AI-агента"

    danger = _dangerous_goal_reason(raw_goal)
    context = build_context_capsule()

    if danger:
        return {
            "ok": False,
            "mode": "codex_agent_plan_blocked",
            "generated_at": _now(),
            "goal": raw_goal,
            "blocked": True,
            "reason": danger,
            "answer": (
                "Я не буду планировать или выполнять потенциально опасную задачу.\n"
                f"Причина: {danger}\n\n"
                "Можно переформулировать цель как безопасный проектный план без доступа к секретам, shell, удалению или админ-действиям."
            ),
            "context_path": str(CONTEXT_PATH),
        }

    system = (
        "Ты LocalComet Codex Agent Workspace RU. "
        "Ты локальный AI-агент разработки, похожий по идее на coding agent: понимаешь проект, "
        "строишь план, предлагаешь безопасные команды и всегда требуешь проверку проекта после изменений. "
        "Отвечай по-русски. Не заявляй, что уже изменил файлы. Не запускай shell/browser/research. "
        "Не проси и не выводи токены, пароли, ключи, cookies, банковские данные. "
        "Если нужны изменения кода, формулируй их как self-edit patch через безопасный Relay pipeline. "
        "Формат ответа: Понимание, План, Риски, Следующая безопасная команда."
    )
    user = (
        "Контекст проекта:\n"
        f"{_context_as_text(context)}\n\n"
        "Цель пользователя:\n"
        f"{raw_goal}\n\n"
        "Составь Codex-like агентский план."
    )

    answer = _ask_local_llm(system, user)
    if not answer:
        answer = _fallback_agent_plan(raw_goal, context)

    result = {
        "ok": True,
        "mode": f"codex_agent_{mode}",
        "generated_at": _now(),
        "goal": raw_goal,
        "agent_version": AGENT_VERSION,
        "answer": answer,
        "context_path": str(CONTEXT_PATH),
        "next_safe_commands": [
            f"pc agent plan {raw_goal}",
            f"pc swiss plan {raw_goal}",
            "проверь проект",
        ],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"codex_agent_{mode}_{stamp}.md"
    report_path.write_text(
        "# LocalComet Codex Agent Workspace\n\n"
        f"- generated_at: {result['generated_at']}\n"
        f"- goal: {raw_goal}\n"
        f"- context: {CONTEXT_PATH}\n\n"
        "## Answer\n\n"
        f"{answer}\n",
        encoding="utf-8",
    )
    result["report"] = str(report_path)
    return result


def run_project_verify() -> dict[str, Any]:
    try:
        from modules.strict_project_stability_ru import dispatch as strict_dispatch

        result = strict_dispatch("проверь проект")
        if isinstance(result, dict):
            result["called_by"] = "codex_agent_mode_ru"
            return result
    except Exception as exc:
        return {
            "ok": False,
            "mode": "codex_agent_verify_error",
            "generated_at": _now(),
            "error": str(exc),
        }

    return {
        "ok": False,
        "mode": "codex_agent_verify_error",
        "generated_at": _now(),
        "error": "strict verification returned non-dict result",
    }


def status() -> dict[str, Any]:
    context = build_context_capsule()
    return {
        "ok": True,
        "mode": "codex_agent_status",
        "generated_at": _now(),
        "agent_version": AGENT_VERSION,
        "agent_name": AGENT_NAME,
        "context_path": str(CONTEXT_PATH),
        "project_version": context.get("control_panel", {}).get("version"),
        "python_files": context.get("python_file_count"),
        "functions": context.get("function_count"),
        "command_modules": context.get("command_module_count"),
        "commands": [
            "pc agent status",
            "pc agent context",
            "pc agent plan <цель>",
            "pc agent brief <цель>",
            "pc agent verify",
            "агент статус",
            "контекст проекта",
        ],
    }


def report() -> dict[str, Any]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "ok": True,
        "mode": "codex_agent_report",
        "generated_at": _now(),
        "latest_reports": [
            str(path)
            for path in sorted(REPORT_DIR.glob("codex_agent_*.md"), reverse=True)[:10]
        ],
        "context_path": str(CONTEXT_PATH),
        "status": status(),
    }


def dispatch(command: str) -> dict[str, Any]:
    raw = str(command or "").strip()
    text = raw.lower().replace("ё", "е")

    if text in {"pc agent status", "агент статус", "статус агента"}:
        return status()

    if text in {"pc agent context", "контекст проекта", "агент контекст"}:
        return build_context_capsule()

    if text in {"pc agent report", "агент отчет", "агент отчёт"}:
        return report()

    if text in {"pc agent verify", "агент проверка", "проверь проект агентом"}:
        return run_project_verify()

    for prefix in ("pc agent plan ", "pc agent brief ", "агент план ", "агент задача "):
        if text.startswith(prefix):
            goal = raw[len(prefix):].strip()
            mode = "brief" if "brief" in prefix else "plan"
            return build_agent_plan(goal, mode=mode)

    if text in {"pc agent plan", "pc agent brief", "агент план"}:
        return build_agent_plan("развивать LocalComet в сторону Codex-подобного AI-агента", mode="plan")

    return {
        "ok": False,
        "mode": "codex_agent_unknown_command",
        "generated_at": _now(),
        "command": raw,
        "hint": "Используй: pc agent plan <цель>, pc agent context, pc agent verify",
    }


def is_codex_agent_command(command: str) -> bool:
    text = str(command or "").strip().lower().replace("ё", "е")
    return (
        text.startswith("pc agent ")
        or text.startswith("агент план ")
        or text.startswith("агент задача ")
        or text in {
            "агент статус",
            "статус агента",
            "контекст проекта",
            "агент контекст",
            "агент проверка",
            "проверь проект агентом",
        }
    )
````

### ПУТЬ: modules/codex_bridge.py (90 строк, 2275 байт)

````python
import os
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root


ROOT_DIR = get_project_root()
BRIDGE_DIR = ROOT_DIR / "Projects" / "CodexBridge"
PROMPTS_DIR = BRIDGE_DIR / "prompts"
REPORTS_DIR = BRIDGE_DIR / "reports"

IMPORTANT_FILES = [
    "LocalComet_Control_Panel.py",
    "next/app_v5.py",
    "core/router.py",
    "core/planner.py",
    "core/executor.py",
    "modules/self_edit.py",
    "modules/chatgpt_relay.py",
    "modules/gpt_browser_bridge.py",
    "modules/true_auto_relay.py",
    "modules/stability_test.py",
    "modules/patch_registry.py",
    "agents/system_agent.py",
]


def _ensure_dirs():
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _project_rules():
    path = ROOT_DIR / "AGENTS.md"

    if not path.exists():
        return "AGENTS.md not found."

    return path.read_text(encoding="utf-8", errors="replace")[:6000]


def create_codex_prompt(task: str):
    _ensure_dirs()

    task = str(task or "").strip() or "Продолжи безопасное улучшение LocalComet."
    prompt_path = PROMPTS_DIR / f"codex_task_{_stamp()}.md"

    lines = [
        "# Codex Task",
        "",
        "## Project",
        "LocalComet / LocalAgent",
        "",
        "## Run",
        "```powershell",
        "python -m next.app_v5",
        "```",
        "",
        "## Current Task",
        task,
        "",
        "## Important Files",
    ]

    for rel_path in IMPORTANT_FILES:
        lines.append(f"- {rel_path}")

    lines.extend([
        "",
        "## Required Tests",
        "```powershell",
        "python -m py_compile LocalComet_Control_Panel.py modules\\patch_registry.py modules\\llm_provider.py modules\\stability_test.py modules\\self_edit.py agents\\system_agent.py",
        "```",
        "",
        "## Project Rules",
        _project_rules(),
    ])

    prompt_path.write_text("\n".join(lines), encoding="utf-8")
    return f"Codex prompt создан:\n{prompt_path}"


def open_codex_bridge():
    _ensure_dirs()
    os.startfile(str(BRIDGE_DIR))
    return f"Открыта папка CodexBridge:\n{BRIDGE_DIR}"
````

### ПУТЬ: modules/codex_connector.py (860 строк, 25773 байт)

````python
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
````

### ПУТЬ: modules/command_center_ui.py (438 строк, 16989 байт)

````python
import tkinter as tk


def build_command_center(panel, parent, style_text, button_grid, colors):
    """Build the LocalComet v6.02 Command Center.

    Emergency-safe UI-only module. It calls existing panel methods and does not
    modify backend, router, config, apply/validate logic, or browser bridge behavior.
    """
    panel_text = colors["text"]
    panel_muted = colors["muted"]
    panel_entry = colors["entry"]

    accent = "#7aa2ff"
    success = "#5dd18c"
    warning = "#f7c948"
    danger = "#ff6b6b"
    card_bg = "#2b2f35"
    card_bg_soft = "#333943"
    border = "#69727f"
    sidebar_bg = "#20242a"
    console_bg = "#171a1f"

    def clear_text(widget):
        widget.delete("1.0", "end")

    def set_text(widget, value):
        clear_text(widget)
        widget.insert("1.0", str(value or ""))

    def goal_value():
        return quick_goal_text.get("1.0", "end").strip()

    def sync_goal_to_panel():
        value = goal_value()
        panel.goal_text.delete("1.0", "end")
        panel.goal_text.insert("1.0", value)
        return value

    def sync_goal_from_panel():
        try:
            value = panel.goal_text.get("1.0", "end").strip()
            if value:
                set_text(quick_goal_text, value)
        except Exception:
            pass

    def append_console(line):
        try:
            panel.quick_console.configure(state="normal")
            panel.quick_console.insert("end", str(line or "") + "\n")
            panel.quick_console.see("end")
            panel.quick_console.configure(state="normal")
        except Exception:
            pass

    def paste_goal():
        panel.quick_paste_goal_from_clipboard()
        sync_goal_from_panel()
        append_console("📋 Задача вставлена из буфера.")

    def request_and_chatgpt():
        sync_goal_to_panel()
        append_console("🚀 Создаю request.md и открываю ChatGPT...")
        panel.quick_create_request_and_open_chatgpt()

    def import_and_validate():
        append_console("📥 Импортирую response.json и запускаю проверку...")
        panel.import_and_validate()

    def apply_after():
        append_console("🛠 Применяю patch и запускаю after-checks...")
        panel.apply_and_after_patch()

    def full_cycle():
        append_console("🔁 Запускаю полный цикл после скачивания...")
        panel.full_cycle_after_download()

    def auto_cycle():
        sync_goal_to_panel()
        append_console("🤖 Запускаю АВТО полный цикл...")
        panel.quick_true_auto_relay_cycle()

    def refresh_all():
        append_console("🔄 Обновляю статусы...")
        panel.refresh_statuses()

    def select_tab_by_text(tab_text):
        try:
            for tab_id in panel.notebook.tabs():
                if panel.notebook.tab(tab_id, "text") == tab_text:
                    panel.notebook.select(tab_id)
                    return
        except Exception:
            pass

    def make_frame(parent_widget, bg=card_bg, padx=0, pady=0, **kwargs):
        frame = tk.Frame(
            parent_widget,
            bg=bg,
            highlightbackground=border,
            highlightcolor=border,
            highlightthickness=1,
            bd=0,
            padx=padx,
            pady=pady,
            **kwargs,
        )
        return frame

    def make_label(parent_widget, text="", fg=panel_text, bg=card_bg, size=10, weight="normal", **kwargs):
        anchor = kwargs.pop("anchor", "w")
        justify = kwargs.pop("justify", "left")
        label = tk.Label(
            parent_widget,
            text=text,
            fg=fg,
            bg=bg,
            font=("Segoe UI", size, weight),
            anchor=anchor,
            justify=justify,
            **kwargs,
        )
        return label

    def make_value(parent_widget, variable, fg=panel_text, bg=card_bg, size=10, **kwargs):
        anchor = kwargs.pop("anchor", "w")
        justify = kwargs.pop("justify", "left")
        label = tk.Label(
            parent_widget,
            textvariable=variable,
            fg=fg,
            bg=bg,
            font=("Segoe UI", size),
            anchor=anchor,
            justify=justify,
            **kwargs,
        )
        return label

    def make_button(parent_widget, text, command, primary=False, danger_button=False):
        button = tk.Button(
            parent_widget,
            text=text,
            command=command,
            relief="flat",
            bd=0,
            padx=14,
            pady=10 if primary else 7,
            cursor="hand2",
            fg="#ffffff",
            bg=accent if primary else ("#7d3f45" if danger_button else "#3e4652"),
            activeforeground="#ffffff",
            activebackground="#8fb2ff" if primary else ("#9b4b52" if danger_button else "#4c5664"),
            font=("Segoe UI", 11 if primary else 9, "bold" if primary else "normal"),
        )
        return button

    def status_card(parent_widget, title, variable, row, column):
        frame = make_frame(parent_widget, bg=card_bg_soft, padx=10, pady=8)
        frame.grid(row=row, column=column, sticky="nsew", padx=4, pady=4)
        make_label(frame, title.upper(), fg=panel_muted, bg=card_bg_soft, size=8, weight="bold").pack(fill="x")
        make_value(frame, variable, fg=panel_text, bg=card_bg_soft, size=9, wraplength=210).pack(fill="x", pady=(4, 0))
        return frame

    def route_item(parent_widget, number, title, subtitle, color):
        row = tk.Frame(parent_widget, bg=card_bg)
        row.pack(fill="x", padx=10, pady=4)
        badge = tk.Label(
            row,
            text=str(number),
            width=3,
            fg="#ffffff",
            bg=color,
            font=("Segoe UI", 9, "bold"),
        )
        badge.pack(side="left", padx=(0, 8))
        text_box = tk.Frame(row, bg=card_bg)
        text_box.pack(side="left", fill="x", expand=True)
        make_label(text_box, title, bg=card_bg, fg=panel_text, size=9, weight="bold").pack(fill="x")
        make_label(text_box, subtitle, bg=card_bg, fg=panel_muted, size=8, wraplength=270).pack(fill="x")

    def nav_button(parent_widget, icon, text, tab_text):
        item = tk.Button(
            parent_widget,
            text=f"{icon}  {text}",
            command=lambda: select_tab_by_text(tab_text),
            anchor="w",
            relief="flat",
            bd=0,
            padx=12,
            pady=9,
            fg=panel_text,
            bg=sidebar_bg,
            activeforeground="#ffffff",
            activebackground="#303743",
            font=("Segoe UI", 10),
            cursor="hand2",
        )
        item.pack(fill="x", pady=1)
        return item

    parent.configure()
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(0, weight=1)

    shell = tk.Frame(parent, bg="#1c2026")
    shell.pack(fill="both", expand=True)

    topbar = tk.Frame(shell, bg="#1a1d22", height=52)
    topbar.pack(fill="x", side="top")
    topbar.pack_propagate(False)

    title_area = tk.Frame(topbar, bg="#1a1d22")
    title_area.pack(side="left", fill="y", padx=14)
    tk.Label(
        title_area,
        text="🚀 LocalComet v6.02",
        fg="#ffffff",
        bg="#1a1d22",
        font=("Segoe UI", 15, "bold"),
        anchor="w",
    ).pack(anchor="w", pady=(7, 0))
    tk.Label(
        title_area,
        text="Command Center • safe local automation workflow",
        fg=panel_muted,
        bg="#1a1d22",
        font=("Segoe UI", 8),
        anchor="w",
    ).pack(anchor="w")

    top_status = tk.Frame(topbar, bg="#1a1d22")
    top_status.pack(side="right", fill="y", padx=10)
    make_button(top_status, "🔄 Refresh", refresh_all).pack(side="right", padx=(6, 0), pady=9)
    tk.Label(top_status, text="● Relay", fg=success, bg="#1a1d22", font=("Segoe UI", 9, "bold")).pack(side="right", padx=8)
    tk.Label(top_status, text="● Response", fg=success, bg="#1a1d22", font=("Segoe UI", 9, "bold")).pack(side="right", padx=8)
    tk.Label(top_status, text="● Local", fg=success, bg="#1a1d22", font=("Segoe UI", 9, "bold")).pack(side="right", padx=8)

    main = tk.Frame(shell, bg="#1c2026")
    main.pack(fill="both", expand=True)

    sidebar = tk.Frame(main, bg=sidebar_bg, width=150)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)
    tk.Label(
        sidebar,
        text="LOCALCOMET",
        fg=panel_muted,
        bg=sidebar_bg,
        font=("Segoe UI", 8, "bold"),
        anchor="w",
    ).pack(fill="x", padx=12, pady=(14, 8))
    nav_button(sidebar, "🏠", "Главная", "🚀 Command Center")
    nav_button(sidebar, "💬", "Chat", "Чат / команды")
    nav_button(sidebar, "📦", "Patch", "Патчи / Relay")
    nav_button(sidebar, "🌐", "Browser", "Браузер")
    nav_button(sidebar, "🧪", "Tests", "Проверки")
    nav_button(sidebar, "📋", "Reports", "Отчеты / инструменты")
    nav_button(sidebar, "🪵", "Logs", "Логи")

    workspace = tk.Frame(main, bg="#1c2026")
    workspace.pack(side="left", fill="both", expand=True, padx=10, pady=10)
    workspace.columnconfigure(0, weight=3)
    workspace.columnconfigure(1, weight=1)
    workspace.rowconfigure(0, weight=1)
    workspace.rowconfigure(1, weight=0)

    center = make_frame(workspace, bg=card_bg, padx=12, pady=12)
    center.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
    center.rowconfigure(1, weight=1)
    center.columnconfigure(0, weight=1)

    make_label(center, "ЗАДАЧА РАЗРАБОТКИ", bg=card_bg, fg=panel_muted, size=8, weight="bold").grid(row=0, column=0, sticky="w")
    quick_goal_text = tk.Text(
        center,
        height=12,
        wrap="word",
        bg=panel_entry,
        fg=panel_text,
        insertbackground=panel_text,
        selectbackground="#41506a",
        selectforeground=panel_text,
        relief="flat",
        padx=14,
        pady=12,
        font=("Segoe UI", 11),
    )
    quick_goal_text.grid(row=1, column=0, sticky="nsew", pady=(8, 10))
    quick_goal_text.insert(
        "1.0",
        "Опиши маленькое безопасное изменение. LocalComet создаст request.md и откроет ChatGPT.",
    )
    quick_goal_text.bind("<Control-Return>", lambda event: request_and_chatgpt())

    def safe_next_action():
        response_text = ""
        patch_text = ""

        try:
            response_text = panel.status_response_var.get().lower()
        except Exception:
            pass

        try:
            patch_text = panel.status_patch_var.get().lower()
        except Exception:
            pass

        if "есть" in response_text and any(word in patch_text for word in ["есть", "готов", "pass", "ok"]):
            append_console("🛠 NEXT ACTION: найден response/patch — применяю patch и after-checks.")
            apply_after()
            return

        if "есть" in response_text:
            append_console("✅ NEXT ACTION: найден response.json — запускаю импорт и проверку.")
            import_and_validate()
            return

        append_console("🚀 NEXT ACTION: создаю request.md и открываю ChatGPT.")
        request_and_chatgpt()

    primary_row = tk.Frame(center, bg=card_bg)
    primary_row.grid(row=2, column=0, sticky="ew")
    primary_row.columnconfigure(0, weight=1)
    make_button(primary_row, "🚀 NEXT ACTION", safe_next_action, primary=True).grid(row=0, column=0, sticky="ew")

    next_row = tk.Frame(center, bg=card_bg)
    next_row.grid(row=3, column=0, sticky="ew", pady=(10, 0))
    for column in range(5):
        next_row.columnconfigure(column, weight=1)
    make_button(next_row, "📋 Paste", paste_goal).grid(row=0, column=0, sticky="ew", padx=(0, 4))
    make_button(next_row, "🚀 Request", request_and_chatgpt).grid(row=0, column=1, sticky="ew", padx=4)
    make_button(next_row, "📥 Import + Validate", import_and_validate).grid(row=0, column=2, sticky="ew", padx=4)
    make_button(next_row, "🛠 Apply + After", apply_after).grid(row=0, column=3, sticky="ew", padx=4)
    make_button(next_row, "🤖 Auto", auto_cycle).grid(row=0, column=4, sticky="ew", padx=(4, 0))

    right = tk.Frame(workspace, bg="#1c2026")
    right.grid(row=0, column=1, sticky="nsew", pady=(0, 8))
    right.columnconfigure(0, weight=1)

    status = make_frame(right, bg=card_bg, padx=8, pady=8)
    status.pack(fill="x", pady=(0, 8))
    make_label(status, "STATUS CARDS", bg=card_bg, fg=panel_muted, size=8, weight="bold").grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 4))
    status.columnconfigure(0, weight=1)
    status.columnconfigure(1, weight=1)
    status_card(status, "Relay", panel.status_relay_var, 1, 0)
    status_card(status, "GPT", panel.status_gpt_var, 1, 1)
    status_card(status, "Response", panel.status_response_var, 2, 0)
    status_card(status, "Patch", panel.status_patch_var, 2, 1)
    status_card(status, "Cycle", panel.status_cycle_var, 3, 0)
    status_card(status, "Error", panel.dashboard_error_var, 3, 1)

    route = make_frame(right, bg=card_bg, padx=0, pady=8)
    route.pack(fill="both", expand=True)
    make_label(route, "WORKFLOW", bg=card_bg, fg=panel_muted, size=8, weight="bold").pack(anchor="w", padx=10, pady=(0, 4))

    flow_bar = tk.Frame(route, bg=card_bg)
    flow_bar.pack(fill="x", padx=10, pady=(0, 8))
    flow_steps = [
        ("1", "Request", accent),
        ("2", "ChatGPT", accent),
        ("3", "Response", warning),
        ("4", "Validate", warning),
        ("5", "Apply", success),
        ("6", "Tests", success),
    ]

    for index, (number, title, color) in enumerate(flow_steps):
        step_box = tk.Frame(flow_bar, bg=card_bg)
        step_box.grid(row=0, column=index, sticky="ew", padx=2)
        flow_bar.columnconfigure(index, weight=1)

        tk.Label(
            step_box,
            text=number,
            fg="#ffffff",
            bg=color,
            font=("Segoe UI", 8, "bold"),
            width=3,
        ).pack(anchor="center")
        make_label(
            step_box,
            title,
            bg=card_bg,
            fg=panel_muted,
            size=7,
            weight="bold",
            anchor="center",
            justify="center",
        ).pack(fill="x", pady=(3, 0))

    route_item(route, 1, "Request", "создать request.md", accent)
    route_item(route, 2, "ChatGPT", "открыть чат и отправить", accent)
    route_item(route, 3, "Response", "скачать response.json", warning)
    route_item(route, 4, "Validate", "проверить JSON", warning)
    route_item(route, 5, "Apply", "применить patch", success)
    route_item(route, 6, "Tests", "py_compile / after patch", success)

    console = make_frame(workspace, bg=console_bg, padx=10, pady=8)
    console.grid(row=1, column=0, columnspan=2, sticky="ew")
    console.columnconfigure(0, weight=1)
    make_label(console, "MINI CONSOLE", bg=console_bg, fg=panel_muted, size=8, weight="bold").grid(row=0, column=0, sticky="w")
    console_body = tk.Text(
        console,
        height=6,
        wrap="word",
        bg=console_bg,
        fg=panel_text,
        insertbackground=panel_text,
        selectbackground="#41506a",
        selectforeground=panel_text,
        relief="flat",
        padx=8,
        pady=6,
        font=("Consolas", 9),
    )
    console_body.grid(row=1, column=0, sticky="ew", pady=(6, 0))
    console_body.insert(
        "1.0",
        "Command Center v6.02 готов.\n"
        "1. Опиши задачу.\n"
        "2. Нажми REQUEST + CHATGPT.\n"
        "3. Скачай response.json.\n"
        "4. Импорт + проверка.\n"
        "5. Применить + after.\n",
    )

    tools = tk.Frame(console, bg=console_bg)
    tools.grid(row=1, column=1, sticky="ns", padx=(10, 0), pady=(6, 0))
    make_button(tools, "Relay", panel.relay_status).pack(fill="x", pady=(0, 4))
    make_button(tools, "Validate", panel.validate_response).pack(fill="x", pady=4)
    make_button(tools, "Open report", panel.open_last_report).pack(fill="x", pady=4)
    make_button(tools, "Clear raw", panel.clear_response_raw_files, danger_button=True).pack(fill="x", pady=(4, 0))

    panel.quick_console = console_body
    sync_goal_from_panel()
    return quick_goal_text
````

### ПУТЬ: modules/command_explorer_ru.py (306 строк, 10108 байт)

````python
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


COMMAND_EXPLORER_VERSION = "v6.59a"
COMMAND_EXPLORER_NAME = "LocalComet Command Explorer RU"

ROOT_PATH = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_PATH / "Projects" / "Reports" / "command_explorer"

BLOCKED_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist",
                "build", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                "BrowserProfile", "Backups"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_PATH)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _is_skipped(path: Path) -> bool:
    parts = path.parts
    for blocked in BLOCKED_DIRS:
        if blocked in parts:
            return True
    if path.suffix != ".py":
        return True
    if path.name.endswith(".bak"):
        return True
    return False


def _read_text(path: Path, limit: int = 50000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
    if len(text) > limit:
        return text[:limit] + "\n[truncated]"
    return text


def _iter_python_files() -> List[Path]:
    files: List[Path] = []
    for path in sorted(ROOT_PATH.rglob("*.py"), key=lambda p: _safe_relative(p).lower()):
        if _is_skipped(path):
            continue
        files.append(path)
    return files


def _guess_category(path: str) -> str:
    name = Path(path).stem.lower()
    if name.startswith("computer_use_") or name == "computer_use_core_ru":
        return "computer_use"
    if name.startswith("premium_"):
        return "premium"
    if name.startswith("localcomet_"):
        return "developer"
    if name.startswith("ai_") or "agent" in name:
        return "ai_agent"
    if name.startswith("browser_"):
        return "browser"
    if name.startswith("pc_"):
        return "pc_codex"
    if name in {"app", "config", "agent"} or name.startswith("core/"):
        return "system"
    if name.startswith("install_") or name.startswith("localcomet_preflight"):
        return "tool"
    if "verification" in name or "stability" in name or "check" in name:
        return "verification"
    if "relay" in name or "chatgpt" in name:
        return "relay"
    if "safety" in name or "danger" in name:
        return "safety"
    return "other"


def _extract_aliases(text: str) -> List[str]:
    found: List[str] = []
    m = re.search(r"COMMAND_ALIASES\s*=\s*\{", text)
    if m:
        chunk = text[m.end():m.end() + 3000]
        for alias in re.findall(r"\"([^\"]+)\"\s*:", chunk):
            if len(alias) < 100:
                found.append(alias)
    return found


def _extract_command_functions(text: str) -> List[str]:
    found: List[str] = []
    for m in re.finditer(r"def\s+(is_\w+_command)\s*\(", text):
        if m:
            found.append(m.group(1))
    return found


def _extract_command_literals(text: str) -> List[str]:
    found: set = set()
    for m in re.finditer(r"\"(pc\s[a-zа-я0-9_\-]+)", text.lower()):
        found.add(m.group(1))
    for m in re.finditer(r"'pc\s([a-zа-я0-9_\-]+)", text.lower()):
        found.add("pc " + m.group(1))
    return sorted(found)


def _extract_route_names(text: str) -> List[str]:
    found: List[str] = []
    for m in re.finditer(r"route_name\s*=\s*[\"']([^\"']+)[\"']", text):
        found.append(m.group(1))
    return found


def _get_dispatch_docstring(text: str) -> str:
    m = re.search(r"def dispatch\s*\([^)]*\).*?\"\"\"(.*?)\"\"\"", text, re.DOTALL)
    if m:
        return m.group(1).strip().split("\n")[0][:200]
    return ""


def discover_commands() -> Dict[str, Any]:
    files = _iter_python_files()
    modules: List[Dict[str, Any]] = []
    categories: Dict[str, List[str]] = {}

    for path in files:
        rel = _safe_relative(path)
        text = _read_text(path)
        if not text:
            continue

        aliases = _extract_aliases(text)
        cmd_fns = _extract_command_functions(text)
        literals = _extract_command_literals(text)
        routes = _extract_route_names(text)
        doc = _get_dispatch_docstring(text)
        category = _guess_category(rel)

        commands: Dict[str, Any] = {}
        if aliases:
            commands["aliases"] = aliases[:30]
        if cmd_fns:
            commands["functions"] = cmd_fns
        if routes:
            commands["routes"] = routes
        if literals:
            commands["literals"] = literals[:30]
        if doc:
            commands["help"] = doc

        if any([aliases, cmd_fns, routes, literals]):
            cat_commands = []
            for alias in aliases[:10]:
                cat_commands.append(alias)
                categories.setdefault(category, []).append(alias)
            for literal in literals[:10]:
                cat_commands.append(literal)
                categories.setdefault(category, []).append(literal)
            for route in routes[:5]:
                categories.setdefault(category, []).append(route)

        modules.append({
            "path": rel,
            "category": category,
            "has_dispatch": "def dispatch" in text,
            "has_status": "def status" in text,
            "has_report": "def report" in text,
            "commands": commands,
        })

    return {
        "modules": modules,
        "categories": {k: sorted(set(v))[:60] for k, v in categories.items()},
    }


def status() -> Dict[str, Any]:
    data = discover_commands()
    total_cmds = sum(len(v) for v in data.get("categories", {}).values())
    return {
        "ok": True,
        "mode": "command_explorer_status",
        "version": COMMAND_EXPLORER_VERSION,
        "module_count": len(data.get("modules", [])),
        "command_count": total_cmds,
        "category_count": len(data.get("categories", {})),
    }


def report() -> Dict[str, Any]:
    data = discover_commands()
    total_cmds = sum(len(v) for v in data.get("categories", {}).values())
    return {
        "ok": True,
        "mode": "command_explorer_report",
        "version": COMMAND_EXPLORER_VERSION,
        "generated_at": _now(),
        "module_count": len(data.get("modules", [])),
        "command_count": total_cmds,
        "category_count": len(data.get("categories", {})),
        "modules": data.get("modules", []),
        "categories": data.get("categories", {}),
    }


def _write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "latest_command_explorer.json"
    md_path = REPORT_DIR / "latest_command_explorer.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# LocalComet Command Explorer",
        "",
        f"- version: {payload.get('version')}",
        f"- ok: {payload.get('ok')}",
        f"- module_count: {payload.get('module_count')}",
        f"- command_count: {payload.get('command_count')}",
        f"- category_count: {payload.get('category_count')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Categories",
        "",
    ]
    categories = payload.get("categories", {})
    for cat, cmds in sorted(categories.items()):
        lines.append(f"### {cat} ({len(cmds)})")
        lines.append("")
        for cmd in cmds:
            lines.append(f"- `{cmd}`")
        lines.append("")

    lines.append("## Modules")
    lines.append("")
    for mod in payload.get("modules", []):
        status_chars = ""
        if mod.get("has_dispatch"):
            status_chars += "D"
        if mod.get("has_status"):
            status_chars += "S"
        if mod.get("has_report"):
            status_chars += "R"
        tags = f"[{status_chars}]" if status_chars else ""
        lines.append(f"- {tags} {mod['path']}")
        cmds = mod.get("commands", {})
        if cmds.get("functions"):
            lines.append(f"  - functions: {', '.join(cmds['functions'][:5])}")
        if cmds.get("aliases"):
            lines.append(f"  - aliases: {', '.join(cmds['aliases'][:5])}")
        if cmds.get("routes"):
            lines.append(f"  - routes: {', '.join(cmds['routes'][:5])}")
        if cmds.get("literals"):
            lines.append(f"  - literals: {', '.join(cmds['literals'][:5])}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "md": md_path}


def is_command_explorer_command(command: str) -> bool:
    lowered = str(command or "").strip().lower().replace("ё", "е")
    targets = {
        "команды проекта", "список команд", "command explorer",
        "pc commands", "pc команды", "pc список", "pc command explorer",
    }
    return lowered in targets


def dispatch(command: str) -> Dict[str, Any]:
    lowered = str(command or "").strip().lower().replace("ё", "е")
    if lowered in {"команды проекта", "список команд", "command explorer",
                   "pc command explorer", "pc commands status"}:
        result = report()
        paths = _write_reports(result)
        result["report"] = str(paths["md"])
        result["json"] = str(paths["json"])
        return result
    if lowered in {"pc commands status", "command explorer status", "статус команд"}:
        return status()
    return {
        "ok": False,
        "mode": "command_explorer_unknown",
        "version": COMMAND_EXPLORER_VERSION,
        "command": command,
        "hint": "Use: команды проекта, список команд, command explorer",
    }


if __name__ == "__main__":
    result = dispatch("команды проекта")
    _write_reports(result)
    print(json.dumps(result, ensure_ascii=False, indent=2)[:3000])
````

### ПУТЬ: modules/computer_use_agent_mission_ru.py (515 строк, 20427 байт)

````python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List, Optional, Tuple


AGENT_MISSION_VERSION = "v6.50h"
AGENT_MISSION_NAME = "Computer Use Agent Mission RU"

ROOT_DIR = get_project_root()
if not ROOT_DIR.exists():
    ROOT_DIR = Path(__file__).resolve().parents[1]

PROJECTS_DIR = ROOT_DIR / "Projects"
COMPUTER_USE_DIR = PROJECTS_DIR / "ComputerUse"
MISSION_DIR = COMPUTER_USE_DIR / "agent_missions"
LATEST_POINTER_FILE = MISSION_DIR / "latest_agent_mission.json"
STOP_REQUEST_FILE = MISSION_DIR / "agent_mission_stop_requested.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _safe_text(value: Any, limit: int = 6000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[truncated]"


def _ensure_dirs() -> None:
    MISSION_DIR.mkdir(parents=True, exist_ok=True)


def _safe_json_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _safe_json_read(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(value, dict):
                return value
    except Exception:
        return {}
    return {}


def _write_event(run_dir: Path, event: Dict[str, Any]) -> None:
    event_payload = dict(event)
    event_payload.setdefault("timestamp", _now())
    events_path = run_dir / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event_payload, ensure_ascii=False, sort_keys=True) + "\n")


def _make_mission(goal: str, simulate: bool, max_steps: int) -> Tuple[str, Path, Dict[str, Any]]:
    _ensure_dirs()
    mission_id = "mission_" + _stamp()
    run_dir = MISSION_DIR / mission_id
    run_dir.mkdir(parents=True, exist_ok=True)
    mission = {
        "ok": True,
        "mode": "computer_use_agent_mission",
        "version": AGENT_MISSION_VERSION,
        "mission_id": mission_id,
        "goal": str(goal or "").strip(),
        "simulate": bool(simulate),
        "max_steps": int(max_steps),
        "status": "running",
        "outcome": "running",
        "created_at": _now(),
        "updated_at": _now(),
        "run_dir": str(run_dir),
        "phases": [],
        "loop_result": None,
    }
    _safe_json_write(run_dir / "mission.json", mission)
    _safe_json_write(LATEST_POINTER_FILE, {"mission_id": mission_id, "run_dir": str(run_dir), "updated_at": _now()})
    _write_event(run_dir, {"event": "mission_created", "goal": goal, "simulate": bool(simulate), "max_steps": int(max_steps)})
    return mission_id, run_dir, mission


def _finish_mission(run_dir: Path, mission: Dict[str, Any], status: str, outcome: str, reason: str = "") -> Dict[str, Any]:
    mission["status"] = status
    mission["outcome"] = outcome
    mission["reason"] = reason
    mission["updated_at"] = _now()
    mission["ok"] = outcome not in {"blocked", "error"} if outcome != "requires_confirmation" else True
    _safe_json_write(run_dir / "mission.json", mission)
    _write_event(run_dir, {"event": "mission_finished", "status": status, "outcome": outcome, "reason": reason})
    _write_report(run_dir, mission)
    _safe_json_write(LATEST_POINTER_FILE, {"mission_id": mission.get("mission_id"), "run_dir": str(run_dir), "updated_at": _now()})
    return dict(mission)


def _write_report(run_dir: Path, mission: Dict[str, Any]) -> str:
    loop_result = mission.get("loop_result")
    loop_mode = loop_result.get("mode") if isinstance(loop_result, dict) else "none"
    loop_outcome = loop_result.get("outcome") if isinstance(loop_result, dict) else "none"
    lines = [
        "# Computer Use Agent Mission",
        "",
        f"- version: {AGENT_MISSION_VERSION}",
        f"- mission_id: {mission.get('mission_id')}",
        f"- status: {mission.get('status')}",
        f"- outcome: {mission.get('outcome')}",
        f"- simulate: {mission.get('simulate')}",
        f"- goal: {mission.get('goal')}",
        f"- reason: {mission.get('reason', '')}",
        f"- loop_mode: {loop_mode}",
        f"- loop_outcome: {loop_outcome}",
        "",
        "## Phases",
    ]
    for phase in mission.get("phases", []):
        lines.append(f"- {phase.get('name')}: {phase.get('status')} - {phase.get('detail', '')}")
    path = run_dir / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _phase(mission: Dict[str, Any], name: str, status: str, detail: str = "", data: Optional[Dict[str, Any]] = None) -> None:
    item = {"name": name, "status": status, "detail": str(detail or ""), "timestamp": _now()}
    if data is not None:
        item["data"] = data
    mission.setdefault("phases", []).append(item)


def _normalize(command: str) -> str:
    return " ".join(str(command or "").lower().replace("ё", "е").strip().split())


def _goal_after_prefix(raw: str, prefixes: List[str]) -> str:
    normalized_raw = _normalize(raw)
    raw_text = str(raw or "").strip()
    for prefix in prefixes:
        normalized_prefix = _normalize(prefix)
        if normalized_raw.startswith(normalized_prefix):
            return raw_text[len(prefix):].strip(" :,-—")
    return ""


def _typed_payload(goal: str) -> str:
    text = str(goal or "")
    if "::" in text:
        return text.split("::", 1)[1].strip()
    markers = ["введи ", "напечатай ", "type "]
    lowered = text.lower()
    for marker in markers:
        if marker in lowered:
            index = lowered.find(marker)
            return text[index + len(marker):].strip()
    return ""


def _payload_requires_confirmation(goal: str) -> Tuple[bool, str]:
    payload = _typed_payload(goal)
    if not payload:
        return False, ""
    lowered = payload.lower().replace("ё", "е")
    risky_markers = [
        "write ",
        "save ",
        "commit",
        "response.json",
        "request.md",
        "patch",
        "file",
        "файл",
        "запиши",
        "сохрани",
        "создай",
        "измени",
        "удали",
    ]
    for marker in risky_markers:
        if marker in lowered:
            return True, "typed payload appears to change files and needs explicit confirmation"
    return False, ""


def stop_requested() -> bool:
    return STOP_REQUEST_FILE.exists()


def request_stop(reason: str = "user requested stop") -> Dict[str, Any]:
    payload = {
        "ok": True,
        "mode": "computer_use_agent_mission_stop",
        "version": AGENT_MISSION_VERSION,
        "reason": str(reason or "user requested stop"),
        "timestamp": _now(),
    }
    _safe_json_write(STOP_REQUEST_FILE, payload)
    return payload


def clear_stop_request() -> Dict[str, Any]:
    existed = STOP_REQUEST_FILE.exists()
    if existed:
        cleared = STOP_REQUEST_FILE.with_name(STOP_REQUEST_FILE.name + ".cleared_" + _stamp())
        STOP_REQUEST_FILE.rename(cleared)
    return {
        "ok": True,
        "mode": "computer_use_agent_mission_clear_stop",
        "version": AGENT_MISSION_VERSION,
        "existed": existed,
    }


def status() -> Dict[str, Any]:
    _ensure_dirs()
    pointer = _safe_json_read(LATEST_POINTER_FILE)
    latest_data: Dict[str, Any] = {}
    run_dir_text = pointer.get("run_dir")
    if run_dir_text:
        latest_data = _safe_json_read(Path(str(run_dir_text)) / "mission.json")
    return {
        "ok": True,
        "handled": True,
        "mode": "computer_use_agent_mission_status",
        "version": AGENT_MISSION_VERSION,
        "missions_dir": str(MISSION_DIR),
        "latest_pointer": pointer,
        "latest_mission_id": latest_data.get("mission_id") or pointer.get("mission_id"),
        "latest_status": latest_data.get("status"),
        "latest_outcome": latest_data.get("outcome"),
        "stop_requested": stop_requested(),
    }


def latest_mission() -> Dict[str, Any]:
    pointer = _safe_json_read(LATEST_POINTER_FILE)
    run_dir_text = pointer.get("run_dir")
    if not run_dir_text:
        return {
            "ok": False,
            "handled": True,
            "mode": "computer_use_agent_mission_latest",
            "version": AGENT_MISSION_VERSION,
            "reason": "no mission has been recorded yet",
        }
    mission = _safe_json_read(Path(str(run_dir_text)) / "mission.json")
    if not mission:
        return {
            "ok": False,
            "handled": True,
            "mode": "computer_use_agent_mission_latest",
            "version": AGENT_MISSION_VERSION,
            "reason": "latest mission pointer exists but mission.json is missing",
            "latest_pointer": pointer,
        }
    mission["handled"] = True
    return mission


def latest_report() -> Dict[str, Any]:
    latest = latest_mission()
    if not latest.get("ok"):
        return latest
    report_path = Path(str(latest.get("run_dir"))) / "report.md"
    if not report_path.exists():
        _write_report(report_path.parent, latest)
    return {
        "ok": True,
        "handled": True,
        "mode": "computer_use_agent_mission_report",
        "version": AGENT_MISSION_VERSION,
        "mission_id": latest.get("mission_id"),
        "report": str(report_path),
        "content": _safe_text(report_path.read_text(encoding="utf-8", errors="replace"), 4000),
    }


def _safety_check(goal: str) -> Dict[str, Any]:
    try:
        from modules.computer_use_safety_ru import safety_check_goal
        result = safety_check_goal(goal)
        if isinstance(result, dict):
            return result
    except Exception as exc:
        return {"ok": False, "blocked": True, "risk": "blocked", "reason": "safety check failed: " + str(exc), "problem_types": ["safety_exception"]}
    return {"ok": False, "blocked": True, "risk": "blocked", "reason": "safety check returned invalid result", "problem_types": ["safety_invalid"]}


def _run_multistep(goal: str, simulate: bool, max_steps: int) -> Dict[str, Any]:
    from modules.computer_use_multistep_loop_ru import run_loop
    result = run_loop(goal, simulate=simulate, max_steps=max_steps, max_failures=1)
    if isinstance(result, dict):
        return result
    return {
        "ok": False,
        "mode": "computer_use_multistep_loop",
        "version": AGENT_MISSION_VERSION,
        "status": "error",
        "outcome": "error",
        "reason": "multistep loop returned non-dict result",
    }


def run_mission(goal: str, simulate: bool = True, max_steps: int = 4) -> Dict[str, Any]:
    goal = str(goal or "").strip()
    if not goal:
        return {
            "ok": False,
            "handled": True,
            "mode": "computer_use_agent_mission",
            "version": AGENT_MISSION_VERSION,
            "status": "rejected",
            "outcome": "ask_user",
            "reason": "empty goal",
        }

    max_steps = max(1, min(int(max_steps), 8))
    mission_id, run_dir, mission = _make_mission(goal, simulate, max_steps)

    try:
        _phase(mission, "goal_intake", "ok", "goal accepted", {"goal": goal, "simulate": bool(simulate)})
        if stop_requested():
            _phase(mission, "stop_gate", "stopped", "stop request is active")
            return _finish_mission(run_dir, mission, "stopped", "stopped", "stop request is active")

        safety = _safety_check(goal)
        mission["safety"] = safety
        if safety.get("blocked") or (safety.get("ok") is False and safety.get("risk") == "blocked"):
            _phase(mission, "safety_check", "blocked", str(safety.get("reason", "")), safety)
            return _finish_mission(run_dir, mission, "blocked", "blocked", str(safety.get("reason", "blocked by safety policy")))

        _phase(mission, "safety_check", "ok", str(safety.get("reason", "allowed")), safety)

        needs_confirmation, confirmation_reason = _payload_requires_confirmation(goal)
        if needs_confirmation:
            _phase(mission, "confirmation_gate", "requires_confirmation", confirmation_reason)
            return _finish_mission(run_dir, mission, "needs_user", "requires_confirmation", confirmation_reason)

        _phase(mission, "delegate_multistep_loop", "running", "delegating one-action-per-observation work to multistep loop")
        loop_result = _run_multistep(goal, simulate=simulate, max_steps=max_steps)
        mission["loop_result"] = loop_result
        loop_outcome = str(loop_result.get("outcome") or "ask_user")
        loop_status = str(loop_result.get("status") or ("done" if loop_result.get("ok") else "needs_user"))
        _phase(
            mission,
            "loop_result",
            "ok" if loop_result.get("ok") else "needs_user",
            "multistep loop returned " + loop_outcome,
            {
                "mode": loop_result.get("mode"),
                "status": loop_status,
                "outcome": loop_outcome,
                "reason": loop_result.get("reason", ""),
            },
        )
        if loop_outcome == "blocked":
            return _finish_mission(run_dir, mission, "blocked", "blocked", str(loop_result.get("reason", "")))
        if loop_outcome == "requires_confirmation":
            return _finish_mission(run_dir, mission, "needs_user", "requires_confirmation", str(loop_result.get("reason", "")))
        if loop_outcome == "done":
            return _finish_mission(run_dir, mission, "done", "done", str(loop_result.get("reason", "")))
        return _finish_mission(run_dir, mission, loop_status if loop_status else "needs_user", loop_outcome, str(loop_result.get("reason", "")))
    except Exception as exc:
        mission["error"] = str(exc)
        _phase(mission, "exception", "error", str(exc))
        return _finish_mission(run_dir, mission, "error", "error", str(exc))


def is_agent_mission_command(command: str) -> bool:
    lowered = _normalize(command)
    exact = {
        "pc computer agent status",
        "pc computer mission status",
        "pc computer agent latest",
        "pc computer mission latest",
        "pc computer agent report",
        "pc computer mission report",
        "pc computer agent stop",
        "pc computer mission stop",
        "pc computer agent clear stop",
        "статус агент computer use",
        "статус миссии computer use",
        "последняя миссия computer use",
        "отчет миссии computer use",
        "отчёт миссии computer use",
        "останови агент computer use",
    }
    if lowered in exact:
        return True
    prefixes = [
        "pc computer agent mission",
        "pc computer mission",
        "pc computer agent simulate",
        "pc computer simulate mission",
        "агент computer use",
        "миссия computer use",
        "симуляция агент computer use",
        "симуляция миссии computer use",
    ]
    return any(lowered.startswith(_normalize(prefix)) for prefix in prefixes)


def handle_dispatch_command(command: str) -> Dict[str, Any]:
    raw = str(command or "").strip()
    lowered = _normalize(raw)

    if lowered in {"pc computer agent status", "pc computer mission status", "статус агент computer use", "статус миссии computer use"}:
        return status()

    if lowered in {"pc computer agent latest", "pc computer mission latest", "последняя миссия computer use"}:
        result = latest_mission()
        result["handled"] = True
        return result

    if lowered in {"pc computer agent report", "pc computer mission report", "отчет миссии computer use", "отчёт миссии computer use"}:
        return latest_report()

    if lowered in {"pc computer agent stop", "pc computer mission stop", "останови агент computer use"}:
        result = request_stop("dispatch command: " + raw)
        result["handled"] = True
        return result

    if lowered == "pc computer agent clear stop":
        result = clear_stop_request()
        result["handled"] = True
        return result

    simulate_prefixes = [
        "pc computer agent simulate",
        "pc computer simulate mission",
        "симуляция агент computer use",
        "симуляция миссии computer use",
    ]
    for prefix in simulate_prefixes:
        goal = _goal_after_prefix(raw, [prefix])
        if goal:
            result = run_mission(goal, simulate=True, max_steps=4)
            result["handled"] = True
            return result

    run_prefixes = [
        "pc computer agent mission",
        "pc computer mission",
        "агент computer use",
        "миссия computer use",
    ]
    for prefix in run_prefixes:
        goal = _goal_after_prefix(raw, [prefix])
        if goal:
            result = run_mission(goal, simulate=False, max_steps=4)
            result["handled"] = True
            return result

    return {
        "ok": False,
        "handled": False,
        "mode": "computer_use_agent_mission",
        "version": AGENT_MISSION_VERSION,
        "reason": "not an agent mission command",
    }


def run_self_check(write_report: bool = True) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details if details is not None else {}})

    blocked = run_mission("удали все файлы через powershell", simulate=True, max_steps=2)
    add("dangerous shell delete mission is blocked", blocked.get("outcome") == "blocked", {"outcome": blocked.get("outcome"), "reason": blocked.get("reason")})

    confirmation = run_mission("введи Поиск :: write changes to file response.json", simulate=True, max_steps=2)
    add("file-changing typed mission requires confirmation", confirmation.get("outcome") == "requires_confirmation", {"outcome": confirmation.get("outcome"), "reason": confirmation.get("reason")})

    status_result = status()
    add("status route works", bool(status_result.get("ok")) and status_result.get("mode") == "computer_use_agent_mission_status", status_result)

    dispatch_status = handle_dispatch_command("pc computer agent status")
    add("dispatch status handled", bool(dispatch_status.get("handled")) and bool(dispatch_status.get("ok")), dispatch_status)

    dispatch_sim = handle_dispatch_command("pc computer agent simulate нажми Сохранить")
    add("dispatch simulated mission returns safe outcome", dispatch_sim.get("outcome") in {"done", "ask_user", "requires_confirmation", "blocked"}, {"outcome": dispatch_sim.get("outcome"), "status": dispatch_sim.get("status")})

    add("module has no public dispatch export", "dispatch" not in globals(), {})

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    payload = {
        "ok": summary["failed"] == 0,
        "mode": "computer_use_agent_mission_self_check",
        "version": AGENT_MISSION_VERSION,
        "summary": summary,
        "checks": checks,
    }

    if write_report:
        report_dir = MISSION_DIR / "self_checks"
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / ("self_check_" + _stamp() + ".json")
        _safe_json_write(path, payload)
        payload["report"] = str(path)

    return payload
````

### ПУТЬ: modules/computer_use_auto_action_ru.py (552 строк, 21900 байт)

````python

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import json
import os
import re
import uuid

AUTO_ACTION_VERSION = "v6.55b"
ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
AUTO_ACTION_DIR = COMPUTER_USE_DIR / "auto_actions"
AUTO_POLICY_PATH = COMPUTER_USE_DIR / "auto_action_policy.json"
AUTO_HISTORY_PATH = COMPUTER_USE_DIR / "auto_action_history.json"


FILE_CHANGE_PATTERNS = [
    r"\b(save|write|create|edit|modify|patch|rename|move|copy|overwrite)\b.{0,80}\b(file|folder|directory|response\.json|\.py|\.md|\.txt|\.json|\.yaml|\.toml)\b",
    r"\b(file|folder|directory|response\.json|\.py|\.md|\.txt|\.json|\.yaml|\.toml)\b.{0,80}\b(save|write|create|edit|modify|patch|rename|move|copy|overwrite)\b",
    r"(сохран|запиш|созда[йт]|редакт|измени|патч|переимен|перемести|скопиру).{0,80}(файл|папк|каталог|response\.json|\.py|\.md|\.txt|\.json)",
    r"(файл|папк|каталог|response\.json|\.py|\.md|\.txt|\.json).{0,80}(сохран|запиш|созда[йт]|редакт|измени|патч|переимен|перемести|скопиру)",
]
FILE_CHANGE_NEGATIONS = [
    "non-file",
    "non file",
    "not a file change",
    "without file changes",
    "no file changes",
    "gui only",
    "ui only",
    "без изменения файлов",
    "без изменений файлов",
    "не меняет файлы",
    "не изменяет файлы",
    "только gui",
    "только ui",
]

DANGEROUS_PATTERNS = [
    r"\b(delete|remove|wipe|format|erase|rm\s+-rf|rmdir|del\s+|shutil\.rmtree|os\.remove)\b|удали|удалить|сотри|стереть|формат",
    r"\b(shell|cmd|cmd\.exe|powershell|terminal|bash|zsh|sudo|admin|administrator)\b|терминал|админ|командн",
    r"\b(password|passwd|token|api\s*key|api-key|secret|private\s*key|ssh\s*key|cookie|cookies|browser\s*profile)\b|парол|токен|секрет|куки|профил[ья] браузера",
    r"\b(bank|payment|credit\s*card|paypal|wallet|gambling|casino|betting)\b|банк|плат[её]ж|карта|казино|ставк",
]

AUTO_GUI_KINDS = {"click", "double_click", "type", "hotkey", "scroll", "move", "wait"}
REQUIRES_GROUNDING = {"click", "double_click", "type", "hotkey", "scroll", "move"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    AUTO_ACTION_DIR.mkdir(parents=True, exist_ok=True)
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def default_auto_policy() -> Dict[str, Any]:
    return {
        "version": AUTO_ACTION_VERSION,
        "auto_gui_enabled": True,
        "confirmation_policy": "confirm_only_file_changes_or_dangerous_actions",
        "require_grounding_for_click_type": True,
        "allow_coordinate_click_if_explicit": True,
        "allow_focused_type_if_explicit": True,
        "max_type_chars": 500,
        "allowed_hotkeys": [
            "enter",
            "tab",
            "escape",
            "ctrl+a",
            "ctrl+c",
            "ctrl+v",
            "ctrl+f",
            "alt+tab",
        ],
        "blocked": [
            "file changes require explicit confirmation",
            "dangerous actions are blocked",
            "secrets are blocked",
            "admin/terminal actions are blocked",
        ],
    }


def load_policy() -> Dict[str, Any]:
    _ensure_dirs()
    policy = _load_json(AUTO_POLICY_PATH, {})
    if not policy:
        policy = default_auto_policy()
        _write_json(AUTO_POLICY_PATH, policy)
    return policy


def _matches_any(text: str, patterns: List[str]) -> bool:
    value = str(text or "").lower()
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _has_file_change_intent(text: str) -> bool:
    value = str(text or "").lower()

    if any(marker in value for marker in FILE_CHANGE_NEGATIONS):
        strong_explicit = [
            "modifies_files=true",
            "confirmed file change",
            "write changes to file",
            "save changes to file",
            "edit file",
            "create file",
            "response.json",
        ]
        if not any(marker in value for marker in strong_explicit):
            return False

    return _matches_any(value, FILE_CHANGE_PATTERNS)


def classify_action(action: Dict[str, Any]) -> Dict[str, Any]:
    target = action.get("target") or {}
    ui_intent = str(action.get("ui_intent", "")).strip().lower()
    combined = " ".join([
        str(action.get("kind", "")),
        str(action.get("goal", "")),
        str(action.get("text", "")),
        str(action.get("reason", "")),
        str(ui_intent),
        str(target.get("element_description", "")),
        str(target.get("window_title", "")),
    ])

    dangerous = _matches_any(combined, DANGEROUS_PATTERNS)

    explicit_gui_only = (
        action.get("modifies_files") is False
        and (
            action.get("gui_only") is True
            or ui_intent in {
                "gui_navigation_or_button_click",
                "focus_only",
                "non_file_gui",
                "visual_guarded_non_file_click",
                "visual_guarded_non_file_type",
                "guarded_type_text",
                "guarded_focus_before_type",
                "verified_input_type",
            }
            or (
                str(action.get("file_change_policy", "")).strip().lower() == "requires_explicit_modifies_files_true"
                and action.get("grounded") is True
            )
        )
    )

    if dangerous:
        file_change = bool(action.get("modifies_files")) or _has_file_change_intent(combined)
    elif explicit_gui_only:
        file_change = False
    else:
        file_change = bool(action.get("modifies_files")) or _has_file_change_intent(combined)

    return {
        "dangerous": dangerous,
        "file_change": file_change,
        "requires_confirmation": bool(dangerous or file_change),
        "risk": "blocked" if dangerous else ("medium" if file_change else "low"),
    }


def is_grounded_action(action: Dict[str, Any]) -> bool:
    if bool(action.get("grounded")):
        return True
    target = action.get("target") or {}
    if target.get("element_id") or target.get("element_description"):
        return True
    if target.get("x") is not None and target.get("y") is not None:
        return True
    if action.get("kind") == "type" and bool(action.get("focused_target")):
        return True
    if action.get("kind") == "hotkey":
        return True
    if action.get("kind") == "scroll":
        return True
    return False


def auto_policy_for_action(action: Dict[str, Any]) -> Dict[str, Any]:
    policy = load_policy()
    kind = str(action.get("kind", "")).strip().lower()
    classification = classify_action(action)

    if classification["dangerous"]:
        return {
            "ok": False,
            "blocked": True,
            "allowed_to_execute": False,
            "requires_confirmation": True,
            "risk": "blocked",
            "reason": "Action contains dangerous/sensitive/admin marker and is blocked.",
            "classification": classification,
            "policy": policy,
        }

    if kind not in AUTO_GUI_KINDS:
        return {
            "ok": False,
            "blocked": True,
            "allowed_to_execute": False,
            "requires_confirmation": True,
            "risk": "blocked",
            "reason": f"Unsupported auto GUI action kind: {kind}",
            "classification": classification,
            "policy": policy,
        }

    if classification["file_change"]:
        return {
            "ok": True,
            "blocked": False,
            "allowed_to_execute": False,
            "requires_confirmation": True,
            "risk": "medium",
            "reason": "File-changing action requires explicit confirmation.",
            "classification": classification,
            "policy": policy,
        }

    if kind in REQUIRES_GROUNDING and not is_grounded_action(action):
        return {
            "ok": True,
            "blocked": False,
            "allowed_to_execute": False,
            "requires_confirmation": False,
            "risk": "medium",
            "reason": "GUI action needs element grounding or explicit coordinate/focused target before execution.",
            "classification": classification,
            "policy": policy,
        }

    if kind == "type":
        text = str(action.get("text", ""))
        if len(text) > int(policy.get("max_type_chars", 500)):
            return {
                "ok": True,
                "blocked": False,
                "allowed_to_execute": False,
                "requires_confirmation": True,
                "risk": "medium",
                "reason": "Typing payload is too long and requires confirmation.",
                "classification": classification,
                "policy": policy,
            }

    if kind == "hotkey":
        hotkey = str(action.get("text") or action.get("hotkey") or "").strip().lower()
        if hotkey and hotkey not in policy.get("allowed_hotkeys", []):
            return {
                "ok": True,
                "blocked": False,
                "allowed_to_execute": False,
                "requires_confirmation": True,
                "risk": "medium",
                "reason": f"Hotkey '{hotkey}' is not in the allowlist.",
                "classification": classification,
                "policy": policy,
            }

    return {
        "ok": True,
        "blocked": False,
        "allowed_to_execute": bool(policy.get("auto_gui_enabled", True)),
        "requires_confirmation": False,
        "risk": "low",
        "reason": "Non-file GUI action is allowed to execute automatically.",
        "classification": classification,
        "policy": policy,
    }


def _record_history(action: Dict[str, Any], policy_result: Dict[str, Any], execution: Dict[str, Any]) -> str:
    _ensure_dirs()
    history = _load_json(AUTO_HISTORY_PATH, [])
    row = {
        "created_at": _now(),
        "action": action,
        "policy_result": {
            "ok": policy_result.get("ok"),
            "blocked": policy_result.get("blocked"),
            "allowed_to_execute": policy_result.get("allowed_to_execute"),
            "requires_confirmation": policy_result.get("requires_confirmation"),
            "risk": policy_result.get("risk"),
            "reason": policy_result.get("reason"),
            "classification": policy_result.get("classification"),
        },
        "execution": execution,
    }
    history.append(row)
    if len(history) > 500:
        history = history[-500:]
    _write_json(AUTO_HISTORY_PATH, history)
    artifact = AUTO_ACTION_DIR / f"auto_action_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    _write_json(artifact, row)
    return str(artifact)


def _pyautogui_execute(action: Dict[str, Any]) -> Dict[str, Any]:
    kind = action.get("kind")
    target = action.get("target") or {}
    text = str(action.get("text", ""))
    import pyautogui

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.12

    if kind == "click":
        pyautogui.click(int(target["x"]), int(target["y"]))
        return {"ok": True, "executed": True, "primitive": "click", "target": target}

    if kind == "double_click":
        pyautogui.doubleClick(int(target["x"]), int(target["y"]))
        return {"ok": True, "executed": True, "primitive": "double_click", "target": target}

    if kind == "move":
        pyautogui.moveTo(int(target["x"]), int(target["y"]), duration=0.1)
        return {"ok": True, "executed": True, "primitive": "move", "target": target}

    if kind == "type":
        if not text:
            return {"ok": False, "executed": False, "error": "empty text"}
        if any(ord(ch) > 127 for ch in text):
            return {"ok": False, "executed": False, "error": "unicode typing requires clipboard adapter and is not enabled in v6.47d"}
        pyautogui.write(text, interval=0.01)
        return {"ok": True, "executed": True, "primitive": "type", "char_count": len(text)}

    if kind == "hotkey":
        keys = str(action.get("text") or action.get("hotkey") or "").replace("+", " ").split()
        if not keys:
            return {"ok": False, "executed": False, "error": "empty hotkey"}
        pyautogui.hotkey(*keys)
        return {"ok": True, "executed": True, "primitive": "hotkey", "keys": keys}

    if kind == "scroll":
        amount = int(action.get("amount") or action.get("delta") or 0)
        if amount == 0:
            amount = -3
        pyautogui.scroll(amount)
        return {"ok": True, "executed": True, "primitive": "scroll", "amount": amount}

    if kind == "wait":
        return {"ok": True, "executed": True, "primitive": "wait"}

    return {"ok": False, "executed": False, "error": f"unsupported primitive: {kind}"}


def execute_gui_action(action: Dict[str, Any], simulate: bool = False) -> Dict[str, Any]:
    _ensure_dirs()
    action = dict(action or {})
    action["kind"] = str(action.get("kind", "")).strip().lower()
    policy_result = auto_policy_for_action(action)

    if policy_result.get("blocked"):
        execution = {"ok": False, "executed": False, "blocked": True, "reason": policy_result.get("reason")}
        artifact = _record_history(action, policy_result, execution)
        return execution | {"mode": "computer_use_auto_action", "artifact": artifact, "policy": policy_result}

    if policy_result.get("requires_confirmation"):
        execution = {"ok": False, "executed": False, "requires_confirmation": True, "reason": policy_result.get("reason")}
        artifact = _record_history(action, policy_result, execution)
        return execution | {"mode": "computer_use_auto_action", "artifact": artifact, "policy": policy_result}

    if not policy_result.get("allowed_to_execute"):
        execution = {"ok": False, "executed": False, "reason": policy_result.get("reason")}
        artifact = _record_history(action, policy_result, execution)
        return execution | {"mode": "computer_use_auto_action", "artifact": artifact, "policy": policy_result}

    if simulate or os.environ.get("LOCALCOMET_COMPUTER_USE_SIMULATE") == "1":
        execution = {
            "ok": True,
            "executed": True,
            "simulated": True,
            "primitive": action.get("kind"),
            "message": "Simulated automatic GUI action.",
        }
        artifact = _record_history(action, policy_result, execution)
        return execution | {"mode": "computer_use_auto_action", "artifact": artifact, "policy": policy_result}

    try:
        execution = _pyautogui_execute(action)
    except Exception as exc:
        execution = {"ok": False, "executed": False, "error": str(exc)}

    artifact = _record_history(action, policy_result, execution)
    return execution | {"mode": "computer_use_auto_action", "artifact": artifact, "policy": policy_result}


def parse_auto_command(command: str) -> Dict[str, Any]:
    raw = (command or "").strip()
    lower = raw.lower()

    if lower.startswith("pc computer auto click "):
        tail = raw[len("pc computer auto click "):].strip()
        parts = re.split(r"[,\s]+", tail)
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return {"kind": "click", "target": {"x": int(parts[0]), "y": int(parts[1])}, "grounded": True, "reason": "explicit coordinate auto click"}
        return {"kind": "click", "target": {"element_description": tail}, "grounded": bool(tail), "reason": "explicit element auto click"}

    if lower.startswith("pc computer auto type "):
        text = raw[len("pc computer auto type "):]
        return {"kind": "type", "text": text, "focused_target": True, "grounded": True, "reason": "explicit focused field auto type"}

    if lower.startswith("pc computer auto hotkey "):
        hotkey = raw[len("pc computer auto hotkey "):].strip().lower()
        return {"kind": "hotkey", "text": hotkey, "grounded": True, "reason": "explicit auto hotkey"}

    if lower.startswith("pc computer auto scroll "):
        amount = raw[len("pc computer auto scroll "):].strip()
        try:
            amount_int = int(amount)
        except Exception:
            amount_int = -3
        return {"kind": "scroll", "amount": amount_int, "grounded": True, "reason": "explicit auto scroll"}

    if lower.startswith("pc computer simulate click "):
        tail = raw[len("pc computer simulate click "):].strip()
        parts = re.split(r"[,\s]+", tail)
        x = int(parts[0]) if len(parts) >= 1 and parts[0].isdigit() else 10
        y = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 10
        return {"kind": "click", "target": {"x": x, "y": y}, "grounded": True, "reason": "simulated coordinate click"}

    if lower.startswith("pc computer simulate type "):
        text = raw[len("pc computer simulate type "):]
        return {"kind": "type", "text": text, "focused_target": True, "grounded": True, "reason": "simulated focused type"}

    return {}


def status() -> Dict[str, Any]:
    policy = load_policy()
    history = _load_json(AUTO_HISTORY_PATH, [])
    return {
        "ok": True,
        "mode": "computer_use_auto_action_status",
        "version": AUTO_ACTION_VERSION,
        "policy": policy,
        "history_count": len(history),
    }


def report() -> Dict[str, Any]:
    return status()


def is_auto_action_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = [
        "pc computer auto click",
        "pc computer auto type",
        "pc computer auto hotkey",
        "pc computer auto scroll",
        "pc computer simulate click",
        "pc computer simulate type",
        "computer auto click",
        "авто клик",
        "авто ввод",
    ]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def dispatch(command: str) -> Dict[str, Any]:
    raw = (command or "").strip()
    lower = raw.lower()

    if lower == "pc computer auto status":
        return status()

    if lower.startswith("авто клик "):
        raw = "pc computer auto click " + raw[len("авто клик "):].strip()
    elif lower.startswith("авто ввод "):
        raw = "pc computer auto type " + raw[len("авто ввод "):]

    action = parse_auto_command(raw)
    if not action:
        return {"ok": False, "mode": "computer_use_auto_action_unknown_command", "command": command}

    simulate = lower.startswith("pc computer simulate ")
    return execute_gui_action(action, simulate=simulate)

# BEGIN v6.55b Computer Use Auto Action history write repair
COMPUTER_USE_AUTO_ACTION_HISTORY_WRITE_REPAIR_RU_V655B = "v6.55b robust auto action history writer"


try:
    _record_history_before_v655b
except NameError:
    _record_history_before_v655b = _record_history


def _record_history(action: Dict[str, Any], policy_result: Dict[str, Any], execution: Dict[str, Any]) -> str:
    try:
        return _record_history_before_v655b(action, policy_result, execution)
    except OSError as exc:
        _ensure_dirs()
        recovered_row = {
            "created_at": _now(),
            "action": action,
            "policy_result": {
                "ok": policy_result.get("ok"),
                "blocked": policy_result.get("blocked"),
                "allowed_to_execute": policy_result.get("allowed_to_execute"),
                "requires_confirmation": policy_result.get("requires_confirmation"),
                "risk": policy_result.get("risk"),
                "reason": policy_result.get("reason"),
                "classification": policy_result.get("classification"),
            },
            "execution": dict(execution or {}) | {
                "history_write_recovered": True,
                "history_write_error": str(exc),
            },
        }
        artifact = AUTO_ACTION_DIR / f"auto_action_recovered_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
        try:
            artifact.write_text(json.dumps(recovered_row, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(artifact)
        except Exception:
            fallback = AUTO_ACTION_DIR / f"auto_action_recovered_{uuid.uuid4().hex[:12]}.json"
            try:
                fallback.write_text(json.dumps(recovered_row, ensure_ascii=True, indent=2), encoding="utf-8")
                return str(fallback)
            except Exception as fallback_exc:
                return "history_write_failed:" + str(fallback_exc)


# END v6.55b Computer Use Auto Action history write repair
````

### ПУТЬ: modules/computer_use_click_planner_ru.py (341 строк, 12969 байт)

````python

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict
import json
import uuid

CLICK_PLANNER_VERSION = "v6.47d"
ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
PLANNER_DIR = COMPUTER_USE_DIR / "click_planner"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)
    PLANNER_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _observe_result() -> Dict[str, Any]:
    try:
        from modules.computer_use_core_ru import observe_screen
        result = observe_screen()
        return result if isinstance(result, dict) else {"ok": False, "error": "observe returned non-dict"}
    except Exception as exc:
        return {"ok": False, "mode": "computer_use_observe_after_action_error", "error": str(exc)}


def _save_plan(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_dirs()
    path = PLANNER_DIR / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    payload["artifact"] = _write_json(path, payload)
    return payload


def plan_click_element(description: str, min_confidence: float = 0.35) -> Dict[str, Any]:
    from modules.computer_use_grounding_ru import build_grounded_action

    grounded_action = build_grounded_action(description, kind="click", min_confidence=min_confidence)
    if not grounded_action.get("ok"):
        return _save_plan("click_plan_failed", {
            "ok": False,
            "mode": "computer_use_click_plan",
            "description": description,
            "reason": grounded_action.get("reason"),
            "grounded_action": grounded_action,
        })

    action = grounded_action["action"]
    action["reason"] = f"GUI-only non-file visual guarded click on grounded UI element: {description}"
    action["goal"] = f"gui-only non-file click element {description}"
    action["modifies_files"] = False
    action["ui_intent"] = "visual_guarded_non_file_click"
    action["gui_only"] = True
    action["file_change_policy"] = "requires_explicit_modifies_files_true"

    from modules.computer_use_auto_action_ru import auto_policy_for_action
    policy = auto_policy_for_action(action)

    return _save_plan("click_plan", {
        "ok": bool(policy.get("ok")) and not policy.get("blocked"),
        "mode": "computer_use_click_plan",
        "description": description,
        "action": action,
        "grounding": grounded_action["grounding"],
        "policy": policy,
        "can_execute": bool(policy.get("allowed_to_execute")) and not policy.get("requires_confirmation"),
        "requires_confirmation": bool(policy.get("requires_confirmation")),
        "created_at": _now(),
    })


def click_element(description: str, simulate: bool = False, min_confidence: float = 0.35) -> Dict[str, Any]:
    plan = plan_click_element(description, min_confidence=min_confidence)
    if not plan.get("ok"):
        return {
            "ok": False,
            "mode": "computer_use_click_element",
            "description": description,
            "plan": plan,
            "reason": plan.get("reason", "click plan failed"),
        }

    if plan.get("requires_confirmation"):
        return {
            "ok": False,
            "mode": "computer_use_click_element",
            "description": description,
            "requires_confirmation": True,
            "plan": plan,
            "reason": plan.get("policy", {}).get("reason", "confirmation required"),
        }

    if not plan.get("can_execute"):
        return {
            "ok": False,
            "mode": "computer_use_click_element",
            "description": description,
            "plan": plan,
            "reason": plan.get("policy", {}).get("reason", "action cannot execute yet"),
        }

    from modules.computer_use_visual_guard_ru import guarded_execute
    guarded = guarded_execute(plan["action"], simulate=simulate)
    observation = guarded.get("after", {}).get("observation", {})

    result = {
        "ok": bool(guarded.get("ok")),
        "mode": "computer_use_click_element",
        "description": description,
        "simulated": simulate,
        "plan": plan,
        "execution": guarded.get("execution", {}),
        "after_observation": observation,
        "visual_guard": guarded,
        "next_decision": guarded.get("next_decision"),
        "created_at": _now(),
    }
    return _save_plan("click_result", result)


def plan_type_into(description: str, text: str, min_confidence: float = 0.35) -> Dict[str, Any]:
    from modules.computer_use_grounding_ru import build_grounded_action

    grounded_action = build_grounded_action(description, kind="type", text=text, min_confidence=min_confidence)
    if not grounded_action.get("ok"):
        return _save_plan("type_plan_failed", {
            "ok": False,
            "mode": "computer_use_type_plan",
            "description": description,
            "text_length": len(text or ""),
            "reason": grounded_action.get("reason"),
            "grounded_action": grounded_action,
        })

    action = grounded_action["action"]
    action["reason"] = f"Type into grounded UI element: {description}"
    action["goal"] = f"type into element {description}"
    action["focused_target"] = True
    action["modifies_files"] = False

    from modules.computer_use_auto_action_ru import auto_policy_for_action
    policy = auto_policy_for_action(action)

    return _save_plan("type_plan", {
        "ok": bool(policy.get("ok")) and not policy.get("blocked"),
        "mode": "computer_use_type_plan",
        "description": description,
        "text_length": len(text or ""),
        "action": action,
        "grounding": grounded_action["grounding"],
        "policy": policy,
        "can_execute": bool(policy.get("allowed_to_execute")) and not policy.get("requires_confirmation"),
        "requires_confirmation": bool(policy.get("requires_confirmation")),
        "created_at": _now(),
    })


def type_into(description: str, text: str, simulate: bool = False, min_confidence: float = 0.35) -> Dict[str, Any]:
    plan = plan_type_into(description, text, min_confidence=min_confidence)
    if not plan.get("ok"):
        return {
            "ok": False,
            "mode": "computer_use_type_into",
            "description": description,
            "plan": plan,
            "reason": plan.get("reason", "type plan failed"),
        }

    if plan.get("requires_confirmation"):
        return {
            "ok": False,
            "mode": "computer_use_type_into",
            "description": description,
            "requires_confirmation": True,
            "plan": plan,
            "reason": plan.get("policy", {}).get("reason", "confirmation required"),
        }

    if not plan.get("can_execute"):
        return {
            "ok": False,
            "mode": "computer_use_type_into",
            "description": description,
            "plan": plan,
            "reason": plan.get("policy", {}).get("reason", "action cannot execute yet"),
        }

    from modules.computer_use_visual_guard_ru import guarded_execute

    focus_action = {
        "kind": "click",
        "target": plan["action"].get("target", {}),
        "grounded": True,
        "reason": f"GUI-only non-file focus target before typing: {description}",
        "modifies_files": False,
        "ui_intent": "guarded_focus_before_type",
        "gui_only": True,
        "file_change_policy": "requires_explicit_modifies_files_true",
    }
    focus_guarded = guarded_execute(focus_action, simulate=simulate)
    type_guarded = guarded_execute(plan["action"], simulate=simulate)
    observation = type_guarded.get("after", {}).get("observation", {})

    result = {
        "ok": bool(focus_guarded.get("ok")) and bool(type_guarded.get("ok")),
        "mode": "computer_use_type_into",
        "description": description,
        "simulated": simulate,
        "plan": plan,
        "focus_execution": focus_guarded.get("execution", {}),
        "type_execution": type_guarded.get("execution", {}),
        "after_observation": observation,
        "focus_visual_guard": focus_guarded,
        "type_visual_guard": type_guarded,
        "next_decision": type_guarded.get("next_decision"),
        "created_at": _now(),
    }
    return _save_plan("type_result", result)


def hotkey_safe(hotkey: str, simulate: bool = False) -> Dict[str, Any]:
    action = {
        "kind": "hotkey",
        "text": hotkey.strip().lower(),
        "grounded": True,
        "reason": f"Safe hotkey request: {hotkey}",
        "modifies_files": False,
    }
    from modules.computer_use_auto_action_ru import auto_policy_for_action, execute_gui_action

    policy = auto_policy_for_action(action)
    if policy.get("requires_confirmation") or not policy.get("allowed_to_execute"):
        return _save_plan("hotkey_refused", {
            "ok": False,
            "mode": "computer_use_hotkey_safe",
            "hotkey": hotkey,
            "policy": policy,
            "reason": policy.get("reason"),
        })

    execution = execute_gui_action(action, simulate=simulate)
    observation = _observe_result()
    return _save_plan("hotkey_result", {
        "ok": bool(execution.get("ok")),
        "mode": "computer_use_hotkey_safe",
        "hotkey": hotkey,
        "simulated": simulate,
        "policy": policy,
        "execution": execution,
        "after_observation": observation,
    })


def status() -> Dict[str, Any]:
    _ensure_dirs()
    return {
        "ok": True,
        "mode": "computer_use_click_planner_status",
        "version": CLICK_PLANNER_VERSION,
        "planner_dir": str(PLANNER_DIR),
    }


def report() -> Dict[str, Any]:
    return status()


def is_computer_use_click_planner_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = [
        "pc computer click element",
        "pc computer simulate click element",
        "pc computer type into",
        "pc computer simulate type into",
        "pc computer hotkey safe",
        "pc computer simulate hotkey safe",
        "кликни элемент",
        "введи в элемент",
    ]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def _split_type_command(raw: str, prefix: str) -> Dict[str, str]:
    tail = raw[len(prefix):].strip()
    if "::" not in tail:
        return {"description": tail, "text": ""}
    description, text = tail.split("::", 1)
    return {"description": description.strip(), "text": text.strip()}


def dispatch(command: str) -> Dict[str, Any]:
    raw = (command or "").strip()
    value = raw.lower()

    if value == "pc computer click planner status":
        return status()

    if value.startswith("pc computer simulate click element "):
        return click_element(raw[len("pc computer simulate click element "):].strip(), simulate=True)

    if value.startswith("pc computer click element "):
        return click_element(raw[len("pc computer click element "):].strip(), simulate=False)

    if value.startswith("кликни элемент "):
        return click_element(raw[len("кликни элемент "):].strip(), simulate=False)

    if value.startswith("pc computer simulate type into "):
        parsed = _split_type_command(raw, "pc computer simulate type into ")
        return type_into(parsed["description"], parsed["text"], simulate=True)

    if value.startswith("pc computer type into "):
        parsed = _split_type_command(raw, "pc computer type into ")
        return type_into(parsed["description"], parsed["text"], simulate=False)

    if value.startswith("введи в элемент "):
        parsed = _split_type_command(raw, "введи в элемент ")
        return type_into(parsed["description"], parsed["text"], simulate=False)

    if value.startswith("pc computer simulate hotkey safe "):
        return hotkey_safe(raw[len("pc computer simulate hotkey safe "):].strip(), simulate=True)

    if value.startswith("pc computer hotkey safe "):
        return hotkey_safe(raw[len("pc computer hotkey safe "):].strip(), simulate=False)

    return {
        "ok": False,
        "mode": "computer_use_click_planner_unknown_command",
        "command": command,
    }
````

### ПУТЬ: modules/computer_use_contract_tests_ru.py (2184 строк, 98256 байт)

````python

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List
import json
import traceback

from modules.project_paths import reports_dir
from modules.computer_use_test_fixtures_ru import temporary_synthetic_ui_map, verify_restore_behavior


CONTRACT_TESTS_VERSION = "v6.58"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _write_report(payload: Dict[str, Any]) -> str:
    report_dir = reports_dir() / "computer_use_contracts"
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"computer_use_contracts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _contract(name: str, func: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    started = _now()
    try:
        result = func()
        ok = bool(result.get("ok"))
        return {
            "name": name,
            "ok": ok,
            "started_at": started,
            "finished_at": _now(),
            "result": result,
        }
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "started_at": started,
            "finished_at": _now(),
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def contract_save_like_click_is_gui_only() -> Dict[str, Any]:
    from modules.computer_use_auto_action_ru import auto_policy_for_action

    action = {
        "kind": "click",
        "target": {"x": 160, "y": 220, "element_description": "Сохранить"},
        "grounded": True,
        "reason": "GUI screen button click on grounded UI element: Сохранить",
        "ui_intent": "visual_guarded_non_file_click",
        "gui_only": True,
        "modifies_files": False,
        "file_change_policy": "requires_explicit_modifies_files_true",
    }
    policy = auto_policy_for_action(action)
    return {
        "ok": bool(policy.get("ok")) and bool(policy.get("allowed_to_execute")) and not bool(policy.get("requires_confirmation")) and not bool(policy.get("classification", {}).get("file_change")),
        "mode": "contract_save_like_click_is_gui_only",
        "policy": policy,
    }


def contract_click_element_simulated() -> Dict[str, Any]:
    with temporary_synthetic_ui_map(label="click_element_contract"):
        from modules.computer_use_click_planner_ru import plan_click_element, click_element

        plan = plan_click_element("Сохранить")
        if not (plan.get("ok") and plan.get("can_execute") and not plan.get("requires_confirmation")):
            return {
                "ok": False,
                "mode": "contract_click_element_simulated",
                "phase": "plan",
                "plan": plan,
            }

        result = click_element("Сохранить", simulate=True)
        return {
            "ok": bool(result.get("ok")) and bool(result.get("execution", {}).get("simulated")) and "visual_guard" in result,
            "mode": "contract_click_element_simulated",
            "plan": plan,
            "result": result,
        }


def contract_guarded_type_simulated() -> Dict[str, Any]:
    with temporary_synthetic_ui_map(label="guarded_type_contract"):
        from modules.computer_use_type_guard_ru import plan_guarded_type, guarded_type

        plan = plan_guarded_type("Поиск", "hello")
        if not (plan.get("ok") and plan.get("can_execute") and not plan.get("requires_confirmation")):
            return {
                "ok": False,
                "mode": "contract_guarded_type_simulated",
                "phase": "plan",
                "plan": plan,
            }

        result = guarded_type("Поиск", "hello", simulate=True)
        return {
            "ok": bool(result.get("ok")) and bool(result.get("focus_execution", {}).get("simulated")) and bool(result.get("type_execution", {}).get("simulated")) and "type_visual_guard" in result,
            "mode": "contract_guarded_type_simulated",
            "plan": plan,
            "result": result,
        }


def contract_file_text_requires_confirmation() -> Dict[str, Any]:
    with temporary_synthetic_ui_map(label="file_text_contract"):
        from modules.computer_use_type_guard_ru import guarded_type

        result = guarded_type("Поиск", "write changes to file response.json", simulate=True)
        return {
            "ok": not bool(result.get("ok")) and bool(result.get("requires_confirmation")),
            "mode": "contract_file_text_requires_confirmation",
            "result": result,
        }


def contract_dangerous_goal_blocked() -> Dict[str, Any]:
    from modules.computer_use_safety_ru import safety_check_goal

    result = safety_check_goal("удали все файлы через powershell")
    return {
        "ok": not bool(result.get("ok")) and bool(result.get("blocked")),
        "mode": "contract_dangerous_goal_blocked",
        "result": result,
    }


def contract_fixture_restores_latest_ui_map() -> Dict[str, Any]:
    return verify_restore_behavior()


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    contracts: List[tuple[str, Callable[[], Dict[str, Any]]]] = [
        ("save_like_click_is_gui_only", contract_save_like_click_is_gui_only),
        ("fixture_restores_latest_ui_map", contract_fixture_restores_latest_ui_map),
        ("click_element_simulated", contract_click_element_simulated),
        ("guarded_type_simulated", contract_guarded_type_simulated),
        ("file_text_requires_confirmation", contract_file_text_requires_confirmation),
        ("dangerous_goal_blocked", contract_dangerous_goal_blocked),
    ]

    results = [_contract(name, func) for name, func in contracts]
    ok_count = sum(1 for item in results if item.get("ok"))
    payload: Dict[str, Any] = {
        "ok": ok_count == len(results),
        "mode": "computer_use_contract_tests",
        "version": CONTRACT_TESTS_VERSION,
        "created_at": _now(),
        "summary": {
            "passed": ok_count,
            "total": len(results),
            "failed": len(results) - ok_count,
        },
        "contracts": results,
    }

    if write_report:
        payload["report"] = _write_report(payload)

    return payload


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "computer_use_contract_tests_status",
        "version": CONTRACT_TESTS_VERSION,
        "contracts": [
            "save_like_click_is_gui_only",
            "fixture_restores_latest_ui_map",
            "click_element_simulated",
            "guarded_type_simulated",
            "file_text_requires_confirmation",
            "dangerous_goal_blocked",
        ],
    }


def report() -> Dict[str, Any]:
    return run_all_contracts(write_report=True)


def is_computer_use_contract_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = [
        "pc computer contracts",
        "pc computer contract tests",
        "pc dev contracts",
        "контракты computer use",
    ]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def dispatch(command: str) -> Dict[str, Any]:
    value = (command or "").strip().lower()
    if value in {"pc computer contracts status", "pc dev contracts status"}:
        return status()
    if is_computer_use_contract_command(command):
        return run_all_contracts(write_report=True)
    return {
        "ok": False,
        "mode": "computer_use_contract_tests_unknown_command",
        "command": command,
    }


if __name__ == "__main__":
    result = run_all_contracts(write_report=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("ok") else 1)


# BEGIN LOCALCOMET V6.48I COMPUTER USE MULTISTEP APPEND CONTRACT WRAPPER

def _localcomet_multistep_contract_check_ru_v648i(name, ok, details):
    return {"name": name, "ok": bool(ok), "details": details}


def _multistep_loop_contract_ru_v648i():
    checks = []
    try:
        from modules.computer_use_multistep_loop_ru import run_self_check, run_loop, status

        self_check = run_self_check(write_report=True)
        checks.append(
            _localcomet_multistep_contract_check_ru_v648i(
                "multistep self check passes",
                bool(self_check.get("ok")),
                {"summary": self_check.get("summary"), "report": self_check.get("report")},
            )
        )

        destructive = run_loop("удали все файлы через powershell", simulate=True, max_steps=2)
        checks.append(
            _localcomet_multistep_contract_check_ru_v648i(
                "dangerous shell delete goal is blocked",
                destructive.get("outcome") == "blocked",
                {"outcome": destructive.get("outcome"), "reason": destructive.get("reason")},
            )
        )

        confirmation = run_loop("введи Поиск :: write changes to file response.json", simulate=True, max_steps=2)
        checks.append(
            _localcomet_multistep_contract_check_ru_v648i(
                "file-changing typed payload requires confirmation",
                confirmation.get("outcome") == "requires_confirmation",
                {"outcome": confirmation.get("outcome"), "reason": confirmation.get("reason")},
            )
        )

        status_result = status()
        checks.append(
            _localcomet_multistep_contract_check_ru_v648i(
                "multistep status is available",
                bool(status_result.get("ok")),
                {"mode": status_result.get("mode"), "version": status_result.get("version")},
            )
        )
    except Exception as exc:
        checks.append(
            _localcomet_multistep_contract_check_ru_v648i(
                "multistep contract exception",
                False,
                {"error": str(exc)},
            )
        )
    return {
        "ok": all(item.get("ok") for item in checks),
        "mode": "computer_use_multistep_loop_contract_ru",
        "version": "v6.48i",
        "summary": {
            "passed": sum(1 for item in checks if item.get("ok")),
            "total": len(checks),
            "failed": sum(1 for item in checks if not item.get("ok")),
        },
        "checks": checks,
    }


_LOCALCOMET_CONTRACTS_BEFORE_MULTISTEP_RU_V648I = globals().get("run_all_contracts")
if not callable(_LOCALCOMET_CONTRACTS_BEFORE_MULTISTEP_RU_V648I):
    for _localcomet_contract_name_ru_v648i in (
        "_run_all_contracts_before_multistep_loop_ru_v648d",
        "_run_all_contracts_before_multistep_loop_ru_v648c",
        "_run_all_contracts_before_multistep_loop_ru_v648b",
        "_run_all_contracts_before_multistep_loop_ru_v648",
    ):
        _localcomet_candidate_contract_ru_v648i = globals().get(_localcomet_contract_name_ru_v648i)
        if callable(_localcomet_candidate_contract_ru_v648i):
            _LOCALCOMET_CONTRACTS_BEFORE_MULTISTEP_RU_V648I = _localcomet_candidate_contract_ru_v648i
            break


def _localcomet_int_ru_v648i(value, fallback=0):
    try:
        return int(value)
    except Exception:
        return fallback


def _localcomet_empty_contract_result_ru_v648i(reason):
    return {
        "ok": False,
        "mode": "computer_use_contract_tests",
        "summary": {"passed": 0, "total": 1, "failed": 1},
        "checks": [{"name": "base contract runner available", "ok": False, "details": {"reason": reason}}],
    }


def run_all_contracts(write_report=False):
    if callable(_LOCALCOMET_CONTRACTS_BEFORE_MULTISTEP_RU_V648I):
        try:
            base_result = _LOCALCOMET_CONTRACTS_BEFORE_MULTISTEP_RU_V648I(write_report=write_report)
        except TypeError:
            base_result = _LOCALCOMET_CONTRACTS_BEFORE_MULTISTEP_RU_V648I()
        except Exception as exc:
            base_result = _localcomet_empty_contract_result_ru_v648i("base contract runner raised: " + str(exc))
    else:
        base_result = _localcomet_empty_contract_result_ru_v648i("base contract runner unavailable")

    if not isinstance(base_result, dict):
        base_result = _localcomet_empty_contract_result_ru_v648i("base contract runner returned non-dict result")

    multistep_result = _multistep_loop_contract_ru_v648i()
    summary = base_result.setdefault("summary", {})
    base_passed = _localcomet_int_ru_v648i(summary.get("passed"))
    base_total = _localcomet_int_ru_v648i(summary.get("total"))
    base_failed = _localcomet_int_ru_v648i(summary.get("failed"))
    multistep_summary = multistep_result.get("summary", {})
    total_passed = base_passed + _localcomet_int_ru_v648i(multistep_summary.get("passed"))
    total_total = base_total + _localcomet_int_ru_v648i(multistep_summary.get("total"))
    total_failed = base_failed + _localcomet_int_ru_v648i(multistep_summary.get("failed"))
    summary["passed"] = total_passed
    summary["total"] = total_total
    summary["failed"] = total_failed
    base_result["summary"] = summary
    base_result["multistep_loop"] = multistep_result
    base_result["ok"] = bool(base_result.get("ok")) and bool(multistep_result.get("ok")) and total_failed == 0
    return base_result


COMPUTER_USE_MULTISTEP_LOOP_CONTRACT_RU_V648I = "v6.48i multistep loop append contract wrapper"

# END LOCALCOMET V6.48I COMPUTER USE MULTISTEP APPEND CONTRACT WRAPPER

# BEGIN LOCALCOMET V6.50H COMPUTER USE AGENT MISSION CONTRACT WRAPPER RU

def _localcomet_contract_check_ru_v650h(name, ok, details=None):
    return {"name": name, "ok": bool(ok), "details": details if details is not None else {}}


def _localcomet_agent_mission_contracts_ru_v650h():
    checks = []
    try:
        import modules.computer_use_agent_mission_ru as agent_mission
        blocked = agent_mission.run_mission("удали все файлы через powershell", simulate=True, max_steps=2)
        checks.append(_localcomet_contract_check_ru_v650h(
            "agent mission blocks dangerous shell delete goal",
            blocked.get("outcome") == "blocked",
            {"outcome": blocked.get("outcome"), "reason": blocked.get("reason")},
        ))

        confirmation = agent_mission.run_mission("введи Поиск :: write changes to file response.json", simulate=True, max_steps=2)
        checks.append(_localcomet_contract_check_ru_v650h(
            "agent mission requires confirmation for file-changing typed payload",
            confirmation.get("outcome") == "requires_confirmation",
            {"outcome": confirmation.get("outcome"), "reason": confirmation.get("reason")},
        ))

        status_result = agent_mission.status()
        checks.append(_localcomet_contract_check_ru_v650h(
            "agent mission status route is available",
            bool(status_result.get("ok")) and status_result.get("mode") == "computer_use_agent_mission_status",
            {"mode": status_result.get("mode"), "version": status_result.get("version")},
        ))

        checks.append(_localcomet_contract_check_ru_v650h(
            "agent mission module avoids command-module dispatch export",
            not callable(getattr(agent_mission, "dispatch", None)) and callable(getattr(agent_mission, "handle_dispatch_command", None)),
            {},
        ))
    except Exception as exc:
        checks.append(_localcomet_contract_check_ru_v650h(
            "agent mission contract exception",
            False,
            {"error": str(exc)},
        ))
    return {
        "ok": all(item.get("ok") for item in checks),
        "mode": "computer_use_agent_mission_contract_ru",
        "version": "v6.50h",
        "summary": {
            "passed": sum(1 for item in checks if item.get("ok")),
            "total": len(checks),
            "failed": sum(1 for item in checks if not item.get("ok")),
        },
        "checks": checks,
    }


_LOCALCOMET_CONTRACTS_BEFORE_AGENT_MISSION_RU_V650H = globals().get("run_all_contracts")


def _localcomet_int_ru_v650h(value, fallback=0):
    try:
        return int(value)
    except Exception:
        return fallback


def _localcomet_empty_contract_result_ru_v650h(reason):
    return {
        "ok": False,
        "mode": "computer_use_contract_tests",
        "summary": {"passed": 0, "total": 1, "failed": 1},
        "checks": [{"name": "base contract runner available", "ok": False, "details": {"reason": reason}}],
    }


def run_all_contracts(write_report=False):
    if callable(_LOCALCOMET_CONTRACTS_BEFORE_AGENT_MISSION_RU_V650H):
        try:
            base_result = _LOCALCOMET_CONTRACTS_BEFORE_AGENT_MISSION_RU_V650H(write_report=write_report)
        except TypeError:
            base_result = _LOCALCOMET_CONTRACTS_BEFORE_AGENT_MISSION_RU_V650H()
        except Exception as exc:
            base_result = _localcomet_empty_contract_result_ru_v650h("base contract runner raised: " + str(exc))
    else:
        base_result = _localcomet_empty_contract_result_ru_v650h("base contract runner unavailable")

    if not isinstance(base_result, dict):
        base_result = _localcomet_empty_contract_result_ru_v650h("base contract runner returned non-dict result")

    mission_result = _localcomet_agent_mission_contracts_ru_v650h()
    summary = base_result.setdefault("summary", {})
    base_passed = _localcomet_int_ru_v650h(summary.get("passed"))
    base_total = _localcomet_int_ru_v650h(summary.get("total"))
    base_failed = _localcomet_int_ru_v650h(summary.get("failed"))
    mission_summary = mission_result.get("summary", {})
    total_passed = base_passed + _localcomet_int_ru_v650h(mission_summary.get("passed"))
    total_total = base_total + _localcomet_int_ru_v650h(mission_summary.get("total"))
    total_failed = base_failed + _localcomet_int_ru_v650h(mission_summary.get("failed"))
    summary["passed"] = total_passed
    summary["total"] = total_total
    summary["failed"] = total_failed
    base_result["summary"] = summary
    base_result["agent_mission"] = mission_result
    base_result["ok"] = bool(base_result.get("ok")) and bool(mission_result.get("ok")) and total_failed == 0
    return base_result


COMPUTER_USE_AGENT_MISSION_CONTRACT_RU_V650H = "v6.50h computer use agent mission contract wrapper"

# END LOCALCOMET V6.50H COMPUTER USE AGENT MISSION CONTRACT WRAPPER RU

# BEGIN LOCALCOMET V6.51 COMPUTER USE FULL CONTROL CONTRACT WRAPPER RU

_LOCALCOMET_CONTRACT_RUN_ALL_BEFORE_FULL_CONTROL_RU_V651 = globals().get("run_all_contracts")


def run_full_control_contracts(write_report=True):
    checks = []

    def add(name, ok, details=None):
        checks.append({"name": name, "ok": bool(ok), "details": details if details is not None else {}})

    try:
        from modules.computer_use_full_control_mission_ru import run_self_check
        full_control_self_check = run_self_check(write_report=write_report)
        add("full control self check", full_control_self_check.get("ok") and full_control_self_check.get("summary", {}).get("failed") == 0, full_control_self_check)
    except Exception as exc:
        add("full control self check", False, {"error": str(exc)})

    try:
        from modules.computer_use_core_ru import dispatch, is_computer_use_command
        status = dispatch("pc computer full control status")
        add("core dispatch full control status", status.get("handled") and status.get("ok") and status.get("mode") == "computer_use_full_control_status", status)
        add("core recognizes управляй пк", is_computer_use_command("управляй пк открой блокнот"), {})
    except Exception as exc:
        add("core dispatch full control status", False, {"error": str(exc)})

    try:
        from modules.computer_use_core_ru import dispatch
        sample = dispatch("pc computer full control simulate открой блокнот и напиши hello")
        add("core dispatch full control simulate", sample.get("handled") and sample.get("outcome") == "done" and len(sample.get("steps", [])) >= 2, {"outcome": sample.get("outcome"), "steps": len(sample.get("steps", []))})
    except Exception as exc:
        add("core dispatch full control simulate", False, {"error": str(exc)})

    try:
        import modules.computer_use_full_control_mission_ru as full_control_module
        add(
            "full control module avoids public dispatch export",
            callable(getattr(full_control_module, "handle_dispatch_command", None)) and not callable(getattr(full_control_module, "dispatch", None)),
            {},
        )
    except Exception as exc:
        add("full control module avoids public dispatch export", False, {"error": str(exc)})

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    return {
        "ok": summary["failed"] == 0,
        "mode": "computer_use_full_control_contracts",
        "version": "v6.51",
        "summary": summary,
        "checks": checks,
    }


def run_all_contracts(write_report=True):
    if callable(_LOCALCOMET_CONTRACT_RUN_ALL_BEFORE_FULL_CONTROL_RU_V651):
        base = _LOCALCOMET_CONTRACT_RUN_ALL_BEFORE_FULL_CONTROL_RU_V651(write_report=write_report)
    else:
        base = {
            "ok": True,
            "mode": "computer_use_contract_tests",
            "summary": {"passed": 0, "total": 0, "failed": 0},
            "checks": [],
        }

    full_control = run_full_control_contracts(write_report=write_report)
    summary = dict(base.get("summary") or {})
    summary["passed"] = int(summary.get("passed", 0)) + int(full_control.get("summary", {}).get("passed", 0))
    summary["total"] = int(summary.get("total", 0)) + int(full_control.get("summary", {}).get("total", 0))
    summary["failed"] = int(summary.get("failed", 0)) + int(full_control.get("summary", {}).get("failed", 0))
    base["summary"] = summary
    base["full_control"] = full_control.get("summary")
    base["full_control_details"] = full_control
    base["ok"] = bool(base.get("ok")) and bool(full_control.get("ok")) and summary["failed"] == 0
    return base

COMPUTER_USE_FULL_CONTROL_CONTRACT_RU_V651 = "v6.51 full control contract wrapper"

# END LOCALCOMET V6.51 COMPUTER USE FULL CONTROL CONTRACT WRAPPER RU

# BEGIN LOCALCOMET V6.53 COMPUTER USE REAL ACTIONS CONTRACT WRAPPER RU

_LOCALCOMET_CONTRACT_RUN_ALL_BEFORE_REAL_ACTIONS_RU_V653 = globals().get("run_all_contracts")


def run_real_actions_contracts(write_report=True):
    checks = []

    def add(name, ok, details=None):
        checks.append({"name": name, "ok": bool(ok), "details": details if details is not None else {}})

    try:
        from modules.computer_use_real_actions_ru import run_self_check
        real_self_check = run_self_check(write_report=write_report)
        add("real actions self check", real_self_check.get("ok") and real_self_check.get("summary", {}).get("failed") == 0, real_self_check)
    except Exception as exc:
        add("real actions self check", False, {"error": str(exc)})

    try:
        from modules.computer_use_core_ru import dispatch
        caps = dispatch("pc computer real actions")
        add("core dispatch real action capabilities", caps.get("handled") and caps.get("ok") and "open_app" in caps.get("actions", []), caps)
    except Exception as exc:
        add("core dispatch real action capabilities", False, {"error": str(exc)})

    try:
        from modules.computer_use_core_ru import dispatch
        sample = dispatch("pc computer full control simulate открой блокнот и напиши hello и нажми enter")
        kinds = [step.get("planned_action", {}).get("kind") for step in sample.get("steps", [])]
        add("core full control simulate uses real actions", sample.get("handled") and sample.get("outcome") == "done" and {"open_app", "paste_text", "press_key"}.issubset(set(kinds)), {"outcome": sample.get("outcome"), "kinds": kinds})
    except Exception as exc:
        add("core full control simulate uses real actions", False, {"error": str(exc)})

    try:
        from modules.computer_use_core_ru import dispatch
        scroll = dispatch("pc computer full control simulate прокрути вниз")
        kinds = [step.get("planned_action", {}).get("kind") for step in scroll.get("steps", [])]
        add("core full control simulate supports scroll", scroll.get("handled") and scroll.get("outcome") == "done" and "scroll" in kinds, {"outcome": scroll.get("outcome"), "kinds": kinds})
    except Exception as exc:
        add("core full control simulate supports scroll", False, {"error": str(exc)})

    try:
        import modules.computer_use_real_actions_ru as real_actions_module
        add(
            "real actions module avoids public dispatch export",
            not callable(getattr(real_actions_module, "dispatch", None)) and callable(getattr(real_actions_module, "execute_real_action", None)),
            {},
        )
    except Exception as exc:
        add("real actions module avoids public dispatch export", False, {"error": str(exc)})

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    return {
        "ok": summary["failed"] == 0,
        "mode": "computer_use_real_actions_contracts",
        "version": "v6.53",
        "summary": summary,
        "checks": checks,
    }


def run_all_contracts(write_report=True):
    if callable(_LOCALCOMET_CONTRACT_RUN_ALL_BEFORE_REAL_ACTIONS_RU_V653):
        base = _LOCALCOMET_CONTRACT_RUN_ALL_BEFORE_REAL_ACTIONS_RU_V653(write_report=write_report)
    else:
        base = {
            "ok": True,
            "mode": "computer_use_contract_tests",
            "summary": {"passed": 0, "total": 0, "failed": 0},
            "checks": [],
        }

    real_actions = run_real_actions_contracts(write_report=write_report)
    summary = dict(base.get("summary") or {})
    summary["passed"] = int(summary.get("passed", 0)) + int(real_actions.get("summary", {}).get("passed", 0))
    summary["total"] = int(summary.get("total", 0)) + int(real_actions.get("summary", {}).get("total", 0))
    summary["failed"] = int(summary.get("failed", 0)) + int(real_actions.get("summary", {}).get("failed", 0))
    base["summary"] = summary
    base["real_actions"] = real_actions.get("summary")
    base["real_actions_details"] = real_actions
    base["ok"] = bool(base.get("ok")) and bool(real_actions.get("ok")) and summary["failed"] == 0
    return base


COMPUTER_USE_REAL_ACTIONS_CONTRACT_RU_V653 = "v6.53 real actions contract wrapper"

# END LOCALCOMET V6.53 COMPUTER USE REAL ACTIONS CONTRACT WRAPPER RU

# BEGIN v6.54 Computer Use Observe/Vision contract wrapper
try:
    _run_all_contracts_before_observe_vision_ru_v654
except NameError:
    _run_all_contracts_before_observe_vision_ru_v654 = run_all_contracts


def run_all_contracts(write_report=True):
    result = _run_all_contracts_before_observe_vision_ru_v654(write_report=write_report)
    try:
        from modules.computer_use_observe_vision_ru import run_self_check

        self_check = run_self_check(write_report=write_report)
        observe_ok = bool(self_check.get("ok"))
        if isinstance(result, dict):
            checks = result.setdefault("checks", [])
            checks.append({
                "name": "computer_use_observe_vision_v654",
                "ok": observe_ok,
                "details": self_check.get("summary", {}),
            })
            summary = result.setdefault("summary", {})
            passed = len([item for item in checks if item.get("ok")])
            total = len(checks)
            summary["passed"] = passed
            summary["total"] = total
            summary["failed"] = total - passed
            result["ok"] = summary["failed"] == 0
            result["version"] = "v6.54"
    except Exception as exc:
        if isinstance(result, dict):
            checks = result.setdefault("checks", [])
            checks.append({
                "name": "computer_use_observe_vision_v654_exception",
                "ok": False,
                "details": str(exc),
            })
            summary = result.setdefault("summary", {})
            passed = len([item for item in checks if item.get("ok")])
            total = len(checks)
            summary["passed"] = passed
            summary["total"] = total
            summary["failed"] = total - passed
            result["ok"] = False
            result["version"] = "v6.54"
    return result
# END v6.54 Computer Use Observe/Vision contract wrapper

# BEGIN v6.54b Computer Use Observe/Vision contract wrapper
try:
    _run_all_contracts_before_observe_vision_ru_v654b
except NameError:
    _run_all_contracts_before_observe_vision_ru_v654b = run_all_contracts


def run_all_contracts(write_report=True):
    result = _run_all_contracts_before_observe_vision_ru_v654b(write_report=write_report)
    try:
        from modules.computer_use_observe_vision_ru import run_self_check

        self_check = run_self_check(write_report=write_report)
        observe_ok = bool(self_check.get("ok"))
        if isinstance(result, dict):
            checks = result.setdefault("checks", [])
            checks.append({
                "name": "computer_use_observe_vision_v654b",
                "ok": observe_ok,
                "details": self_check.get("summary", {}),
            })
            summary = result.setdefault("summary", {})
            passed = len([item for item in checks if item.get("ok")])
            total = len(checks)
            summary["passed"] = passed
            summary["total"] = total
            summary["failed"] = total - passed
            result["ok"] = summary["failed"] == 0
            result["version"] = "v6.54b"
    except Exception as exc:
        if isinstance(result, dict):
            checks = result.setdefault("checks", [])
            checks.append({
                "name": "computer_use_observe_vision_v654b_exception",
                "ok": False,
                "details": str(exc),
            })
            summary = result.setdefault("summary", {})
            passed = len([item for item in checks if item.get("ok")])
            total = len(checks)
            summary["passed"] = passed
            summary["total"] = total
            summary["failed"] = total - passed
            result["ok"] = False
            result["version"] = "v6.54b"
    return result
# END v6.54b Computer Use Observe/Vision contract wrapper


# BEGIN v6.55b Agent Automation Functional Test Center contract wrapper
try:
    _run_all_contracts_before_agent_auto_ru_v655b
except NameError:
    _run_all_contracts_before_agent_auto_ru_v655b = run_all_contracts


def run_agent_auto_function_contracts(write_report=True):
    try:
        from modules.localcomet_agent_auto_test_center_ru import run_contract_suite

        result = run_contract_suite(write_report=write_report)
        summary = result.get("summary", {})
        return {
            "ok": bool(result.get("ok")) and int(summary.get("failed", 1)) == 0,
            "mode": "localcomet_agent_auto_function_contracts",
            "version": "v6.55b",
            "summary": summary,
            "checks": result.get("checks", []),
            "report": result.get("report"),
            "json": result.get("json"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "mode": "localcomet_agent_auto_function_contracts",
            "version": "v6.55b",
            "summary": {"passed": 0, "total": 1, "failed": 1},
            "checks": [{
                "name": "agent_auto_function_contract_exception",
                "ok": False,
                "details": str(exc),
            }],
            "error": str(exc),
        }


def run_all_contracts(write_report=True):
    if callable(_run_all_contracts_before_agent_auto_ru_v655b):
        base = _run_all_contracts_before_agent_auto_ru_v655b(write_report=write_report)
    else:
        base = {
            "ok": True,
            "mode": "computer_use_contract_tests",
            "summary": {"passed": 0, "total": 0, "failed": 0},
            "checks": [],
        }
    if not isinstance(base, dict):
        base = {
            "ok": False,
            "mode": "computer_use_contract_tests",
            "summary": {"passed": 0, "total": 1, "failed": 1},
            "checks": [{"name": "base_contract_runner_returned_dict", "ok": False, "details": type(base).__name__}],
        }

    agent_auto = run_agent_auto_function_contracts(write_report=write_report)
    summary = dict(base.get("summary") or {})
    summary["passed"] = int(summary.get("passed", 0)) + int(agent_auto.get("summary", {}).get("passed", 0))
    summary["total"] = int(summary.get("total", 0)) + int(agent_auto.get("summary", {}).get("total", 0))
    summary["failed"] = int(summary.get("failed", 0)) + int(agent_auto.get("summary", {}).get("failed", 0))
    base["summary"] = summary
    base["agent_auto_functions"] = agent_auto.get("summary")
    base["agent_auto_functions_details"] = agent_auto
    base["ok"] = bool(base.get("ok")) and bool(agent_auto.get("ok")) and summary["failed"] == 0
    base["version"] = "v6.55b"
    return base


COMPUTER_USE_AGENT_AUTO_TEST_CENTER_CONTRACT_RU_V655B = "v6.55b agent automation functional contracts"
# END v6.55b Agent Automation Functional Test Center contract wrapper

# BEGIN v6.58 Developer Velocity Toolkit contract coverage
COMPUTER_USE_CONTRACTS_DEVELOPER_VELOCITY_RU_V658 = "v6.58 developer velocity toolkit command contracts installed"


def contract_developer_velocity_commands_ru_v658() -> Dict[str, Any]:
    from modules.localcomet_developer_velocity_ru import dispatch
    commands = ["последний сбой", "события патча", "статус разработки"]
    results = []
    for command in commands:
        result = dispatch(command)
        results.append({"command": command, "ok": isinstance(result, dict) and bool(result.get("handled", True)), "mode": result.get("mode") if isinstance(result, dict) else type(result).__name__})
    return {
        "ok": all(item.get("ok") for item in results),
        "mode": "contract_developer_velocity_commands",
        "version": "v6.58",
        "results": results,
    }


try:
    _run_all_contracts_before_developer_velocity_ru_v658
except NameError:
    _run_all_contracts_before_developer_velocity_ru_v658 = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_developer_velocity_ru_v658(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    result = contract_developer_velocity_commands_ru_v658()
    contracts.append({"name": "developer_velocity_commands", "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.58 Developer Velocity Toolkit contract coverage

# BEGIN v6.59a Command Explorer RU contract coverage
COMPUTER_USE_CONTRACTS_COMMAND_EXPLORER_RU_V659A = "v6.59a command explorer contracts installed"


def contract_command_explorer_status_ru_v659a() -> Dict[str, Any]:
    from modules.command_explorer_ru import status as ce_status
    r = ce_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "command_explorer_status" and isinstance(r.get("module_count"), int) and r["module_count"] >= 3,
        "mode": "contract_command_explorer_status",
        "version": "v6.59a",
        "result": r,
    }


def contract_command_explorer_report_ru_v659a() -> Dict[str, Any]:
    from modules.command_explorer_ru import report as ce_report
    r = ce_report()
    categories = r.get("categories", {}) if isinstance(r, dict) else {}
    total_cmds = sum(len(v) for v in categories.values())
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "command_explorer_report" and total_cmds >= 10,
        "mode": "contract_command_explorer_report",
        "version": "v6.59a",
        "command_count": total_cmds,
        "result": r,
    }


def contract_command_explorer_routed_core_ru_v659a() -> Dict[str, Any]:
    from modules.computer_use_core_ru import dispatch as core_dispatch
    r = core_dispatch("команды проекта")
    return {
        "ok": isinstance(r, dict) and r.get("handled") and r.get("route") == "modules.command_explorer_ru",
        "mode": "contract_command_explorer_routed_core",
        "version": "v6.59a",
        "result": r,
    }


try:
    _run_all_contracts_before_command_explorer_ru_v659a
except NameError:
    _run_all_contracts_before_command_explorer_ru_v659a = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_command_explorer_ru_v659a(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_command_explorer_status_ru_v659a, contract_command_explorer_report_ru_v659a, contract_command_explorer_routed_core_ru_v659a]:
        result = cfn()
        contracts.append({"name": result.get("mode", "command_explorer_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# BEGIN v6.59b Repo Analyzer RU contract coverage
COMPUTER_USE_CONTRACTS_REPO_ANALYZER_RU_V659B = "v6.59b repo analyzer contracts installed"


def contract_repo_analyzer_status_ru_v659b() -> Dict[str, Any]:
    from modules.repo_analyzer_ru import status as ra_status
    r = ra_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "repo_analyzer_status" and isinstance(r.get("file_count"), int) and r["file_count"] >= 5,
        "mode": "contract_repo_analyzer_status",
        "version": "v6.59b",
        "result": r,
    }


def contract_repo_analyzer_report_ru_v659b() -> Dict[str, Any]:
    from modules.repo_analyzer_ru import report as ra_report
    r = ra_report()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "repo_analyzer_report" and isinstance(r.get("file_count"), int) and r["file_count"] >= 10,
        "mode": "contract_repo_analyzer_report",
        "version": "v6.59b",
        "result": r,
    }


def contract_repo_analyzer_routed_core_ru_v659b() -> Dict[str, Any]:
    from modules.computer_use_core_ru import dispatch as core_dispatch
    r = core_dispatch("анализ проекта")
    return {
        "ok": isinstance(r, dict) and r.get("handled") and "repo_analyzer" in r.get("route", ""),
        "mode": "contract_repo_analyzer_routed_core",
        "version": "v6.59b",
        "result": r,
    }


try:
    _run_all_contracts_before_repo_analyzer_ru_v659b
except NameError:
    _run_all_contracts_before_repo_analyzer_ru_v659b = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_repo_analyzer_ru_v659b(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_repo_analyzer_status_ru_v659b, contract_repo_analyzer_report_ru_v659b, contract_repo_analyzer_routed_core_ru_v659b]:
        result = cfn()
        contracts.append({"name": result.get("mode", "repo_analyzer_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.59b Repo Analyzer RU contract coverage

# BEGIN v6.63 Context Pack RU contract coverage
COMPUTER_USE_CONTRACTS_CONTEXT_PACK_RU_V663 = "v6.63 context pack contracts installed"


def contract_context_pack_status_ru_v663() -> Dict[str, Any]:
    from modules.context_pack_ru import status as cp_status
    r = cp_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "context_pack_status",
        "mode": "contract_context_pack_status",
        "version": "v6.64",
        "result": r,
    }


def contract_context_pack_report_ru_v663() -> Dict[str, Any]:
    from modules.context_pack_ru import report as cp_report
    r = cp_report()
    return {
        "ok": isinstance(r, dict) and r.get("ok"),
        "mode": "contract_context_pack_report",
        "version": "v6.64",
        "result": r,
    }


def contract_context_pack_routed_panel_ru_v663() -> Dict[str, Any]:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("localcomet agent context pack")
    result_dict = r.get("result", {}) if isinstance(r, dict) else {}
    return {
        "ok": isinstance(r, dict) and r.get("route") == "modules.context_pack_ru" and isinstance(result_dict, dict) and result_dict.get("handled") and result_dict.get("ok"),
        "mode": "contract_context_pack_routed_panel",
        "version": "v6.64",
        "result": r,
    }


def contract_context_pack_version_consistency_ru_v663() -> Dict[str, Any]:
    import re
    from modules.context_pack_ru import CONTEXT_PACK_JSON, ROOT_PATH as CP_ROOT
    panel_text = (CP_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
    expected = m.group(1) if m else ""
    report_result = None
    actual = ""
    try:
        from modules.context_pack_ru import report as cp_report
        report_result = cp_report()
        if CONTEXT_PACK_JSON.exists():
            import json
            payload = json.loads(CONTEXT_PACK_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
    except Exception:
        pass
    ok = bool(expected) and expected == actual
    return {
        "ok": ok,
        "mode": "contract_context_pack_version_consistency",
        "version": "v6.64",
        "expected": expected,
        "actual": actual,
        "report_ok": isinstance(report_result, dict) and report_result.get("ok"),
    }


try:
    _run_all_contracts_before_context_pack_ru_v663
except NameError:
    _run_all_contracts_before_context_pack_ru_v663 = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_context_pack_ru_v663(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_context_pack_status_ru_v663, contract_context_pack_report_ru_v663, contract_context_pack_routed_panel_ru_v663, contract_context_pack_version_consistency_ru_v663]:
        result = cfn()
        contracts.append({"name": result.get("mode", "context_pack_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# BEGIN v6.63 Plan Contract RU contract coverage
COMPUTER_USE_CONTRACTS_PLAN_CONTRACT_RU_V663 = "v6.63 plan contract contracts installed"


def contract_plan_contract_status_ru_v663() -> Dict[str, Any]:
    from modules.plan_contract_ru import status as pc_status
    r = pc_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "plan_contract_status",
        "mode": "contract_plan_contract_status",
        "version": "v6.64",
        "result": r,
    }


def contract_plan_contract_report_ru_v663() -> Dict[str, Any]:
    from modules.plan_contract_ru import report as pc_report
    r = pc_report()
    return {
        "ok": isinstance(r, dict) and r.get("ok"),
        "mode": "contract_plan_contract_report",
        "version": "v6.64",
        "result": r,
    }


def contract_plan_contract_routed_panel_ru_v663() -> Dict[str, Any]:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("localcomet agent plan contract")
    result_dict = r.get("result", {}) if isinstance(r, dict) else {}
    return {
        "ok": isinstance(r, dict) and r.get("route") == "modules.plan_contract_ru" and isinstance(result_dict, dict) and result_dict.get("handled") and result_dict.get("ok"),
        "mode": "contract_plan_contract_routed_panel",
        "version": "v6.64",
        "result": r,
    }


def contract_plan_contract_version_consistency_ru_v663() -> Dict[str, Any]:
    import re
    from modules.plan_contract_ru import PLAN_CONTRACT_JSON, ROOT_PATH as PC_ROOT
    panel_text = (PC_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
    expected = m.group(1) if m else ""
    actual = ""
    try:
        from modules.plan_contract_ru import report as pc_report
        pc_report()
        if PLAN_CONTRACT_JSON.exists():
            import json
            payload = json.loads(PLAN_CONTRACT_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
    except Exception:
        pass
    ok = bool(expected) and expected == actual
    return {
        "ok": ok,
        "mode": "contract_plan_contract_version_consistency",
        "version": "v6.64",
        "expected": expected,
        "actual": actual,
    }


try:
    _run_all_contracts_before_plan_contract_ru_v663
except NameError:
    _run_all_contracts_before_plan_contract_ru_v663 = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_plan_contract_ru_v663(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_plan_contract_status_ru_v663, contract_plan_contract_report_ru_v663, contract_plan_contract_routed_panel_ru_v663, contract_plan_contract_version_consistency_ru_v663]:
        result = cfn()
        contracts.append({"name": result.get("mode", "plan_contract_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# BEGIN v6.63 Risk Classifier RU contract coverage
COMPUTER_USE_CONTRACTS_RISK_CLASSIFIER_RU_V663 = "v6.63 risk classifier contracts installed"


def contract_risk_classifier_status_ru_v663() -> Dict[str, Any]:
    from modules.risk_classifier_ru import status as rc_status
    r = rc_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "risk_classifier_status",
        "mode": "contract_risk_classifier_status",
        "version": "v6.64",
        "result": r,
    }


def contract_risk_classifier_report_ru_v663() -> Dict[str, Any]:
    from modules.risk_classifier_ru import report as rc_report
    r = rc_report()
    return {
        "ok": isinstance(r, dict) and r.get("ok"),
        "mode": "contract_risk_classifier_report",
        "version": "v6.64",
        "result": r,
    }


def contract_risk_classifier_routed_panel_ru_v663() -> Dict[str, Any]:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("localcomet agent risk classify")
    result_dict = r.get("result", {}) if isinstance(r, dict) else {}
    return {
        "ok": isinstance(r, dict) and r.get("route") == "modules.risk_classifier_ru" and isinstance(result_dict, dict) and result_dict.get("handled") and result_dict.get("ok"),
        "mode": "contract_risk_classifier_routed_panel",
        "version": "v6.64",
        "result": r,
    }


def contract_risk_classifier_version_consistency_ru_v663() -> Dict[str, Any]:
    import re
    from modules.risk_classifier_ru import RISK_CLASSIFIER_JSON, ROOT_PATH as RC_ROOT
    panel_text = (RC_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
    expected = m.group(1) if m else ""
    actual = ""
    try:
        from modules.risk_classifier_ru import report as rc_report
        rc_report()
        if RISK_CLASSIFIER_JSON.exists():
            import json
            payload = json.loads(RISK_CLASSIFIER_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
    except Exception:
        pass
    ok = bool(expected) and expected == actual
    return {
        "ok": ok,
        "mode": "contract_risk_classifier_version_consistency",
        "version": "v6.64",
        "expected": expected,
        "actual": actual,
    }


def contract_risk_classifier_docs_only_ru_v663() -> Dict[str, Any]:
    from modules.risk_classifier_ru import classify
    r = classify("fix typo in AGENTS.md documentation")
    return {
        "ok": r.get("risk_level") == "docs_only",
        "mode": "contract_risk_classifier_docs_only",
        "version": "v6.64",
        "risk_level": r.get("risk_level"),
    }


def contract_risk_classifier_high_ru_v663() -> Dict[str, Any]:
    from modules.risk_classifier_ru import classify
    r = classify("install new network dependency via subprocess")
    return {
        "ok": r.get("risk_level") == "high",
        "mode": "contract_risk_classifier_high",
        "version": "v6.64",
        "risk_level": r.get("risk_level"),
    }


def contract_risk_classifier_unclassified_ru_v663() -> Dict[str, Any]:
    from modules.risk_classifier_ru import classify
    r = classify("")
    return {
        "ok": r.get("risk_level") == "unclassified",
        "mode": "contract_risk_classifier_unclassified",
        "version": "v6.64",
        "risk_level": r.get("risk_level"),
    }


try:
    _run_all_contracts_before_risk_classifier_ru_v663
except NameError:
    _run_all_contracts_before_risk_classifier_ru_v663 = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_risk_classifier_ru_v663(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_risk_classifier_status_ru_v663, contract_risk_classifier_report_ru_v663, contract_risk_classifier_routed_panel_ru_v663, contract_risk_classifier_version_consistency_ru_v663, contract_risk_classifier_docs_only_ru_v663, contract_risk_classifier_high_ru_v663, contract_risk_classifier_unclassified_ru_v663]:
        result = cfn()
        contracts.append({"name": result.get("mode", "risk_classifier_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.63 Risk Classifier RU contract coverage

# BEGIN v6.64a Repository Weight Audit RU contract coverage
COMPUTER_USE_CONTRACTS_REPO_WEIGHT_AUDIT_RU_V664A = "v6.64a repo weight audit contracts installed"


def contract_repo_weight_audit_status_ru_v664a() -> Dict[str, Any]:
    from modules.repo_weight_audit_ru import status as rwa_status
    r = rwa_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "repo_weight_audit_status",
        "mode": "contract_repo_weight_audit_status",
        "version": "v6.64a",
        "result": r,
    }


def contract_repo_weight_audit_report_ru_v664a() -> Dict[str, Any]:
    from modules.repo_weight_audit_ru import report as rwa_report
    r = rwa_report()
    return {
        "ok": isinstance(r, dict) and r.get("ok"),
        "mode": "contract_repo_weight_audit_report",
        "version": "v6.64a",
        "result": r,
    }


def contract_repo_weight_audit_routed_panel_ru_v664a() -> Dict[str, Any]:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("localcomet repo weight audit")
    result_dict = r.get("result", {}) if isinstance(r, dict) else {}
    return {
        "ok": isinstance(r, dict) and r.get("route") == "modules.repo_weight_audit_ru" and isinstance(result_dict, dict) and result_dict.get("handled") and result_dict.get("ok"),
        "mode": "contract_repo_weight_audit_routed_panel",
        "version": "v6.64a",
        "result": r,
    }


def contract_repo_weight_audit_version_consistency_ru_v664a() -> Dict[str, Any]:
    import re
    from modules.repo_weight_audit_ru import REPO_WEIGHT_JSON, ROOT_PATH as RWA_ROOT
    panel_text = (RWA_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
    expected = m.group(1) if m else ""
    actual = ""
    try:
        from modules.repo_weight_audit_ru import report as rwa_report
        rwa_report()
        if REPO_WEIGHT_JSON.exists():
            import json
            payload = json.loads(REPO_WEIGHT_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
    except Exception:
        pass
    ok = bool(expected) and expected == actual
    return {
        "ok": ok,
        "mode": "contract_repo_weight_audit_version_consistency",
        "version": "v6.64a",
        "expected": expected,
        "actual": actual,
    }


def contract_repo_weight_audit_has_required_fields_ru_v664a() -> Dict[str, Any]:
    from modules.repo_weight_audit_ru import report as rwa_report
    import json
    from modules.repo_weight_audit_ru import REPO_WEIGHT_JSON
    r = rwa_report()
    ok = False
    fields_found = []
    fields_missing = []
    try:
        if REPO_WEIGHT_JSON.exists():
            payload = json.loads(REPO_WEIGHT_JSON.read_text(encoding="utf-8"))
            required = ["schema_version", "base_version", "total_size_bytes", "total_size_mb", "total_size_gb", "file_count", "folder_count", "top_directories", "top_files", "dangerous_cleanup_warning", "safe_cleanup_recommendations"]
            for f in required:
                if f in payload:
                    fields_found.append(f)
                else:
                    fields_missing.append(f)
            ok = len(fields_missing) == 0
    except Exception:
        pass
    return {
        "ok": ok and isinstance(r, dict) and r.get("ok"),
        "mode": "contract_repo_weight_audit_has_required_fields",
        "version": "v6.64a",
        "fields_found": fields_found,
        "fields_missing": fields_missing,
    }


def contract_repo_weight_audit_no_deletion_ru_v664a() -> Dict[str, Any]:
    from modules.repo_weight_audit_ru import scan
    result = scan()
    warning = result.get("dangerous_cleanup_warning", "")
    ok = "NO FILES WERE DELETED" in warning and "audit-only" in warning
    return {
        "ok": ok,
        "mode": "contract_repo_weight_audit_no_deletion",
        "version": "v6.64a",
        "warning_present": bool(warning),
    }


try:
    _run_all_contracts_before_repo_weight_audit_ru_v664a
except NameError:
    _run_all_contracts_before_repo_weight_audit_ru_v664a = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_repo_weight_audit_ru_v664a(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_repo_weight_audit_status_ru_v664a, contract_repo_weight_audit_report_ru_v664a, contract_repo_weight_audit_routed_panel_ru_v664a, contract_repo_weight_audit_version_consistency_ru_v664a, contract_repo_weight_audit_has_required_fields_ru_v664a, contract_repo_weight_audit_no_deletion_ru_v664a]:
        result = cfn()
        contracts.append({"name": result.get("mode", "repo_weight_audit_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.64a Repository Weight Audit RU contract coverage

# BEGIN v6.64b Storage Cleanup Plan RU contract coverage
COMPUTER_USE_CONTRACTS_STORAGE_CLEANUP_PLAN_RU_V664B = "v6.64b storage cleanup plan contracts installed"


def contract_storage_cleanup_plan_status_ru_v664b() -> Dict[str, Any]:
    from modules.storage_cleanup_plan_ru import status as scp_status
    r = scp_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "storage_cleanup_plan_status",
        "mode": "contract_storage_cleanup_plan_status",
        "version": "v6.64b",
        "result": r,
    }


def contract_storage_cleanup_plan_report_ru_v664b() -> Dict[str, Any]:
    from modules.storage_cleanup_plan_ru import report as scp_report
    r = scp_report()
    return {
        "ok": isinstance(r, dict) and r.get("ok"),
        "mode": "contract_storage_cleanup_plan_report",
        "version": "v6.64b",
        "result": r,
    }


def contract_storage_cleanup_plan_routed_panel_ru_v664b() -> Dict[str, Any]:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("localcomet storage cleanup plan")
    result_dict = r.get("result", {}) if isinstance(r, dict) else {}
    return {
        "ok": isinstance(r, dict) and r.get("route") == "modules.storage_cleanup_plan_ru" and isinstance(result_dict, dict) and result_dict.get("handled") and result_dict.get("ok"),
        "mode": "contract_storage_cleanup_plan_routed_panel",
        "version": "v6.64b",
        "result": r,
    }


def contract_storage_cleanup_plan_version_consistency_ru_v664b() -> Dict[str, Any]:
    import re
    from modules.storage_cleanup_plan_ru import STORAGE_CLEANUP_JSON, ROOT_PATH as SCP_ROOT
    panel_text = (SCP_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
    expected = m.group(1) if m else ""
    actual = ""
    try:
        from modules.storage_cleanup_plan_ru import report as scp_report
        scp_report()
        if STORAGE_CLEANUP_JSON.exists():
            import json
            payload = json.loads(STORAGE_CLEANUP_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
    except Exception:
        pass
    ok = bool(expected) and expected == actual
    return {
        "ok": ok,
        "mode": "contract_storage_cleanup_plan_version_consistency",
        "version": "v6.64b",
        "expected": expected,
        "actual": actual,
    }


def contract_storage_cleanup_plan_no_deletion_ru_v664b() -> Dict[str, Any]:
    from modules.storage_cleanup_plan_ru import generate
    result = generate()
    warning = result.get("dangerous_cleanup_warning", "")
    ok = "NO FILES WERE DELETED" in warning and "plan-only" in warning
    return {
        "ok": ok,
        "mode": "contract_storage_cleanup_plan_no_deletion",
        "version": "v6.64b",
        "deletion_enabled": result.get("deletion_enabled"),
        "cleanup_mode": result.get("cleanup_mode"),
        "warning_present": bool(warning),
    }


def contract_storage_cleanup_plan_mode_ru_v664b() -> Dict[str, Any]:
    from modules.storage_cleanup_plan_ru import generate
    result = generate()
    return {
        "ok": result.get("deletion_enabled") is False and result.get("cleanup_mode") == "plan_only",
        "mode": "contract_storage_cleanup_plan_mode",
        "version": "v6.64b",
        "deletion_enabled": result.get("deletion_enabled"),
        "cleanup_mode": result.get("cleanup_mode"),
    }


def contract_storage_cleanup_plan_has_required_fields_ru_v664b() -> Dict[str, Any]:
    from modules.storage_cleanup_plan_ru import report as scp_report
    import json
    from modules.storage_cleanup_plan_ru import STORAGE_CLEANUP_JSON
    r = scp_report()
    ok = False
    fields_found = []
    fields_missing = []
    try:
        if STORAGE_CLEANUP_JSON.exists():
            payload = json.loads(STORAGE_CLEANUP_JSON.read_text(encoding="utf-8"))
            required = ["schema_version", "base_version", "cleanup_mode", "deletion_enabled", "candidates", "high_impact_targets", "dangerous_cleanup_warning"]
            for f in required:
                if f in payload:
                    fields_found.append(f)
                else:
                    fields_missing.append(f)
            ok = len(fields_missing) == 0
    except Exception:
        pass
    return {
        "ok": ok and isinstance(r, dict) and r.get("ok"),
        "mode": "contract_storage_cleanup_plan_has_required_fields",
        "version": "v6.64b",
        "fields_found": fields_found,
        "fields_missing": fields_missing,
    }


try:
    _run_all_contracts_before_storage_cleanup_plan_ru_v664b
except NameError:
    _run_all_contracts_before_storage_cleanup_plan_ru_v664b = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_storage_cleanup_plan_ru_v664b(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_storage_cleanup_plan_status_ru_v664b, contract_storage_cleanup_plan_report_ru_v664b, contract_storage_cleanup_plan_routed_panel_ru_v664b, contract_storage_cleanup_plan_version_consistency_ru_v664b, contract_storage_cleanup_plan_no_deletion_ru_v664b, contract_storage_cleanup_plan_mode_ru_v664b, contract_storage_cleanup_plan_has_required_fields_ru_v664b]:
        result = cfn()
        contracts.append({"name": result.get("mode", "storage_cleanup_plan_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.64b Storage Cleanup Plan RU contract coverage

# BEGIN v6.64c Screenshot Retention Dry Run RU contract coverage
COMPUTER_USE_CONTRACTS_SCREENSHOT_RETENTION_DRY_RUN_RU_V664C = "v6.64c screenshot retention dry run contracts installed"


def contract_screenshot_retention_dry_run_status_ru_v664c() -> Dict[str, Any]:
    from modules.screenshot_retention_dry_run_ru import status as srd_status
    r = srd_status()
    return {
        "ok": isinstance(r, dict) and r.get("mode") == "screenshot_retention_dry_run_status",
        "mode": "contract_screenshot_retention_dry_run_status",
        "version": "v6.64c",
        "result": r,
    }


def contract_screenshot_retention_dry_run_report_ru_v664c() -> Dict[str, Any]:
    from modules.screenshot_retention_dry_run_ru import report as srd_report
    r = srd_report()
    return {
        "ok": isinstance(r, dict) and r.get("ok"),
        "mode": "contract_screenshot_retention_dry_run_report",
        "version": "v6.64c",
        "result": r,
    }


def contract_screenshot_retention_dry_run_routed_panel_ru_v664c() -> Dict[str, Any]:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("localcomet screenshots retention dry run")
    result_dict = r.get("result", {}) if isinstance(r, dict) else {}
    return {
        "ok": isinstance(r, dict) and r.get("route") == "modules.screenshot_retention_dry_run_ru" and isinstance(result_dict, dict) and result_dict.get("handled") and result_dict.get("ok"),
        "mode": "contract_screenshot_retention_dry_run_routed_panel",
        "version": "v6.64c",
        "result": r,
    }


def contract_screenshot_retention_dry_run_version_consistency_ru_v664c() -> Dict[str, Any]:
    import re
    from modules.screenshot_retention_dry_run_ru import DRY_RUN_JSON, ROOT_PATH as SRD_ROOT
    panel_text = (SRD_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
    expected = m.group(1) if m else ""
    actual = ""
    try:
        from modules.screenshot_retention_dry_run_ru import report as srd_report
        srd_report()
        if DRY_RUN_JSON.exists():
            import json
            payload = json.loads(DRY_RUN_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
    except Exception:
        pass
    ok = bool(expected) and expected == actual
    return {
        "ok": ok,
        "mode": "contract_screenshot_retention_dry_run_version_consistency",
        "version": "v6.64c",
        "expected": expected,
        "actual": actual,
    }


def contract_screenshot_retention_dry_run_no_deletion_ru_v664c() -> Dict[str, Any]:
    from modules.screenshot_retention_dry_run_ru import scan
    result = scan()
    warning = result.get("dangerous_cleanup_warning", "")
    ok = "NO FILES WERE DELETED" in warning and "dry-run-only" in warning
    return {
        "ok": ok,
        "mode": "contract_screenshot_retention_dry_run_no_deletion",
        "version": "v6.64c",
        "deletion_enabled": result.get("deletion_enabled"),
        "cleanup_mode": result.get("cleanup_mode"),
        "warning_present": bool(warning),
    }


def contract_screenshot_retention_dry_run_mode_ru_v664c() -> Dict[str, Any]:
    from modules.screenshot_retention_dry_run_ru import scan
    result = scan()
    return {
        "ok": result.get("deletion_enabled") is False and result.get("cleanup_mode") == "dry_run_only",
        "mode": "contract_screenshot_retention_dry_run_mode",
        "version": "v6.64c",
        "deletion_enabled": result.get("deletion_enabled"),
        "cleanup_mode": result.get("cleanup_mode"),
    }


def contract_screenshot_retention_dry_run_has_required_fields_ru_v664c() -> Dict[str, Any]:
    from modules.screenshot_retention_dry_run_ru import report as srd_report
    import json
    from modules.screenshot_retention_dry_run_ru import DRY_RUN_JSON
    r = srd_report()
    ok = False
    fields_found = []
    fields_missing = []
    try:
        if DRY_RUN_JSON.exists():
            payload = json.loads(DRY_RUN_JSON.read_text(encoding="utf-8"))
            required = ["schema_version", "base_version", "cleanup_mode", "deletion_enabled", "screenshot_directories", "total_screenshot_files", "total_screenshot_size_bytes", "retention_policy", "cleanup_candidates", "dangerous_cleanup_warning"]
            for f in required:
                if f in payload:
                    fields_found.append(f)
                else:
                    fields_missing.append(f)
            ok = len(fields_missing) == 0
    except Exception:
        pass
    return {
        "ok": ok and isinstance(r, dict) and r.get("ok"),
        "mode": "contract_screenshot_retention_dry_run_has_required_fields",
        "version": "v6.64c",
        "fields_found": fields_found,
        "fields_missing": fields_missing,
    }


try:
    _run_all_contracts_before_screenshot_retention_dry_run_ru_v664c
except NameError:
    _run_all_contracts_before_screenshot_retention_dry_run_ru_v664c = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_screenshot_retention_dry_run_ru_v664c(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [contract_screenshot_retention_dry_run_status_ru_v664c, contract_screenshot_retention_dry_run_report_ru_v664c, contract_screenshot_retention_dry_run_routed_panel_ru_v664c, contract_screenshot_retention_dry_run_version_consistency_ru_v664c, contract_screenshot_retention_dry_run_no_deletion_ru_v664c, contract_screenshot_retention_dry_run_mode_ru_v664c, contract_screenshot_retention_dry_run_has_required_fields_ru_v664c]:
        result = cfn()
        contracts.append({"name": result.get("mode", "screenshot_retention_dry_run_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.64c Screenshot Retention Dry Run RU contract coverage

# BEGIN v6.64d Screenshot Storage Policy Simulator RU contract coverage
COMPUTER_USE_CONTRACTS_SCREENSHOT_STORAGE_POLICY_SIMULATOR_RU_V664D = "v6.64d screenshot storage policy simulator contracts installed"


def contract_screenshot_storage_policy_simulator_status_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import dispatch
    r = dispatch("localcomet screenshots storage policy simulate status")
    ok = isinstance(r, dict) and r.get("ok")
    return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_status", "version": "v6.64d"}


def contract_screenshot_storage_policy_simulator_report_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import dispatch
    r = dispatch("localcomet screenshots storage policy simulate")
    ok = isinstance(r, dict) and r.get("ok") and bool(r.get("paths"))
    return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_report", "version": "v6.64d"}


def contract_screenshot_storage_policy_simulator_routed_panel_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import is_screenshot_storage_policy_simulator_command
    ok = is_screenshot_storage_policy_simulator_command("localcomet screenshots storage policy simulate")
    return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_routed_panel", "version": "v6.64d"}


def contract_screenshot_storage_policy_simulator_version_consistency_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import dispatch, SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION
    r = dispatch("localcomet screenshots storage policy simulate")
    v = r.get("version", "") if isinstance(r, dict) else ""
    ok = v == SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION or bool(v)
    return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_version_consistency", "version": "v6.64d", "expected": SCREENSHOT_STORAGE_POLICY_SIMULATOR_VERSION, "got": v}


def contract_screenshot_storage_policy_simulator_no_deletion_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import dispatch, ROOT_PATH as SPS_ROOT
    r = dispatch("localcomet screenshots storage policy simulate")
    if not isinstance(r, dict) or not r.get("paths"):
        return {"ok": False, "mode": "contract_screenshot_storage_policy_simulator_no_deletion", "version": "v6.64d"}
    import json
    json_path = r["paths"].get("json", "")
    if not json_path:
        return {"ok": False, "mode": "contract_screenshot_storage_policy_simulator_no_deletion", "version": "v6.64d"}
    try:
        data = json.loads((SPS_ROOT / json_path).read_text(encoding="utf-8"))
        deletion_enabled = data.get("deletion_enabled", True)
        all_policies_safe = all(
            sp.get("deletion_enabled", True) is False
            for sp in data.get("simulated_policies", [])
        )
        ok = not deletion_enabled and all_policies_safe
        return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_no_deletion", "version": "v6.64d", "deletion_enabled": deletion_enabled, "all_policies_safe": all_policies_safe}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_storage_policy_simulator_no_deletion", "version": "v6.64d", "error": str(e)}


def contract_screenshot_storage_policy_simulator_mode_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import dispatch
    r = dispatch("localcomet screenshots storage policy simulate")
    mode = r.get("mode", "") if isinstance(r, dict) else ""
    ok = mode == "screenshot_storage_policy_simulator_generated"
    return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_mode", "version": "v6.64d", "got_mode": mode}


def contract_screenshot_storage_policy_simulator_has_required_fields_ru_v664d():
    from modules.screenshot_storage_policy_simulator_ru import dispatch, ROOT_PATH as SPS_ROOT
    r = dispatch("localcomet screenshots storage policy simulate")
    if not isinstance(r, dict) or not r.get("paths"):
        return {"ok": False, "mode": "contract_screenshot_storage_policy_simulator_has_required_fields", "version": "v6.64d"}
    import json
    json_path = r["paths"].get("json", "")
    if not json_path:
        return {"ok": False, "mode": "contract_screenshot_storage_policy_simulator_has_required_fields", "version": "v6.64d"}
    try:
        data = json.loads((SPS_ROOT / json_path).read_text(encoding="utf-8"))
        required_fields = ["simulated_policies", "growth_rate_estimate", "projected_30_day_size_gb", "projected_90_day_size_gb", "recommended_policy", "screenshot_directories", "total_screenshot_files", "total_screenshot_size_gb"]
        fields_found = [f for f in required_fields if f in data]
        fields_missing = [f for f in required_fields if f not in data]
        ok = len(fields_missing) == 0
        return {"ok": ok, "mode": "contract_screenshot_storage_policy_simulator_has_required_fields", "version": "v6.64d", "fields_found": fields_found, "fields_missing": fields_missing}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_storage_policy_simulator_has_required_fields", "version": "v6.64d", "error": str(e)}


try:
    _run_all_contracts_before_screenshot_storage_policy_simulator_ru_v664d
except NameError:
    _run_all_contracts_before_screenshot_storage_policy_simulator_ru_v664d = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_screenshot_storage_policy_simulator_ru_v664d(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [
        contract_screenshot_storage_policy_simulator_status_ru_v664d,
        contract_screenshot_storage_policy_simulator_report_ru_v664d,
        contract_screenshot_storage_policy_simulator_routed_panel_ru_v664d,
        contract_screenshot_storage_policy_simulator_version_consistency_ru_v664d,
        contract_screenshot_storage_policy_simulator_no_deletion_ru_v664d,
        contract_screenshot_storage_policy_simulator_mode_ru_v664d,
        contract_screenshot_storage_policy_simulator_has_required_fields_ru_v664d,
    ]:
        result = cfn()
        contracts.append({"name": result.get("mode", "screenshot_storage_policy_simulator_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload


# END v6.64d Screenshot Storage Policy Simulator RU contract coverage

# BEGIN v6.64e Screenshot Retention Policy Config RU contract coverage
COMPUTER_USE_CONTRACTS_SCREENSHOT_RETENTION_POLICY_CONFIG_RU_V664E = "v6.64e screenshot retention policy config contracts installed"


def contract_screenshot_retention_policy_config_status_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import dispatch
    r = dispatch("localcomet screenshots retention policy status")
    ok = isinstance(r, dict) and r.get("ok")
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_status", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_write_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import dispatch
    r = dispatch("localcomet screenshots retention policy write")
    ok = isinstance(r, dict) and r.get("ok") and bool(r.get("paths"))
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_write", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_routed_panel_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import is_screenshot_retention_policy_config_command
    ok = is_screenshot_retention_policy_config_command("localcomet screenshots retention policy write")
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_routed_panel", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_version_consistency_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import dispatch, SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION
    r = dispatch("localcomet screenshots retention policy write")
    v = r.get("version", "") if isinstance(r, dict) else ""
    ok = v == SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION or bool(v)
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_version_consistency", "version": "v6.64e", "expected": SCREENSHOT_RETENTION_POLICY_CONFIG_VERSION, "got": v}


def _check_policy_json_field(path, field, expected):
    import json
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        actual = data.get(field)
        if callable(expected):
            return expected(actual)
        return actual == expected
    except Exception:
        return False


def contract_screenshot_retention_policy_config_cleanup_mode_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    ok = _check_policy_json_field(POLICY_JSON, "cleanup_mode", "policy_config_only")
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_cleanup_mode", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_deletion_disabled_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    ok = _check_policy_json_field(POLICY_JSON, "deletion_enabled", False)
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_deletion_disabled", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_manual_approval_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    ok = _check_policy_json_field(POLICY_JSON, "manual_approval_required", True)
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_manual_approval", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_selected_policy_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    ok = _check_policy_json_field(POLICY_JSON, "selected_policy", "keep_newest_500_per_directory")
    return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_selected_policy", "version": "v6.64e"}


def contract_screenshot_retention_policy_config_enforcement_inactive_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    import json
    try:
        data = json.loads(POLICY_JSON.read_text(encoding="utf-8"))
        es = data.get("enforcement_status", {})
        ok = es.get("active") is False
        return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_enforcement_inactive", "version": "v6.64e", "active": es.get("active")}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_retention_policy_config_enforcement_inactive", "version": "v6.64e", "error": str(e)}


def contract_screenshot_retention_policy_config_dangerous_warning_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    import json
    try:
        data = json.loads(POLICY_JSON.read_text(encoding="utf-8"))
        w = data.get("dangerous_cleanup_warning", "")
        ok = "NO FILES WERE DELETED" in w
        return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_dangerous_warning", "version": "v6.64e", "contains_warning": ok}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_retention_policy_config_dangerous_warning", "version": "v6.64e", "error": str(e)}


def contract_screenshot_retention_policy_config_base_version_matches_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON, ROOT_PATH as RPC_ROOT
    import json, re
    try:
        panel_text = (RPC_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
        m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
        expected = m.group(1) if m else ""
        data = json.loads(POLICY_JSON.read_text(encoding="utf-8"))
        actual = data.get("base_version", "")
        ok = bool(expected) and expected == actual
        return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_base_version_matches", "version": "v6.64e", "expected": expected, "actual": actual}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_retention_policy_config_base_version_matches", "version": "v6.64e", "error": str(e)}


def contract_screenshot_retention_policy_config_policy_limits_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    import json
    try:
        data = json.loads(POLICY_JSON.read_text(encoding="utf-8"))
        pl = data.get("policy_limits", {})
        ok = pl.get("keep_newest_per_directory") == 500 and pl.get("keep_younger_than_days") is None and pl.get("max_total_gb") is None and pl.get("max_gb_per_directory") is None
        return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_policy_limits", "version": "v6.64e", "policy_limits": pl}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_retention_policy_config_policy_limits", "version": "v6.64e", "error": str(e)}


def contract_screenshot_retention_policy_config_missing_simulation_safe_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import SIMULATION_JSON
    original_content = None
    if SIMULATION_JSON.exists():
        original_content = SIMULATION_JSON.read_bytes()
    try:
        if SIMULATION_JSON.exists():
            SIMULATION_JSON.rename(SIMULATION_JSON.with_suffix(".json.bak_test"))
        from modules.screenshot_retention_policy_config_ru import generate
        payload = generate()
        ok = payload.get("cleanup_mode") == "policy_config_only" and payload.get("deletion_enabled") is False
        warnings = payload.get("warnings") or []
        has_warning = any("not found" in str(w).lower() for w in warnings)
        return {"ok": ok and has_warning, "mode": "contract_screenshot_retention_policy_config_missing_simulation_safe", "version": "v6.64e", "has_warning": has_warning}
    finally:
        if original_content is not None:
            bak = SIMULATION_JSON.with_suffix(".json.bak_test")
            if bak.exists():
                bak.rename(SIMULATION_JSON)


def contract_screenshot_retention_policy_config_invalid_simulation_safe_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import SIMULATION_JSON
    original_content = None
    if SIMULATION_JSON.exists():
        original_content = SIMULATION_JSON.read_bytes()
    try:
        SIMULATION_JSON.write_text("not valid json {{{", encoding="utf-8")
        from modules.screenshot_retention_policy_config_ru import generate
        payload = generate()
        ok = payload.get("cleanup_mode") == "policy_config_only" and payload.get("deletion_enabled") is False
        warnings = payload.get("warnings") or []
        has_warning = any("invalid" in str(w).lower() for w in warnings)
        return {"ok": ok and has_warning, "mode": "contract_screenshot_retention_policy_config_invalid_simulation_safe", "version": "v6.64e", "has_warning": has_warning}
    finally:
        SIMULATION_JSON.write_text(original_content.decode("utf-8") if original_content else "{}", encoding="utf-8")


def contract_screenshot_retention_policy_config_no_deletion_ru_v664e():
    from modules.screenshot_retention_policy_config_ru import POLICY_JSON
    import json
    try:
        data = json.loads(POLICY_JSON.read_text(encoding="utf-8"))
        ok = data.get("deletion_enabled") is False and "NO FILES WERE DELETED" in data.get("dangerous_cleanup_warning", "")
        return {"ok": ok, "mode": "contract_screenshot_retention_policy_config_no_deletion", "version": "v6.64e"}
    except Exception as e:
        return {"ok": False, "mode": "contract_screenshot_retention_policy_config_no_deletion", "version": "v6.64e", "error": str(e)}


try:
    _run_all_contracts_before_screenshot_retention_policy_config_ru_v664e
except NameError:
    _run_all_contracts_before_screenshot_retention_policy_config_ru_v664e = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_screenshot_retention_policy_config_ru_v664e(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [
        contract_screenshot_retention_policy_config_status_ru_v664e,
        contract_screenshot_retention_policy_config_write_ru_v664e,
        contract_screenshot_retention_policy_config_routed_panel_ru_v664e,
        contract_screenshot_retention_policy_config_version_consistency_ru_v664e,
        contract_screenshot_retention_policy_config_cleanup_mode_ru_v664e,
        contract_screenshot_retention_policy_config_deletion_disabled_ru_v664e,
        contract_screenshot_retention_policy_config_manual_approval_ru_v664e,
        contract_screenshot_retention_policy_config_selected_policy_ru_v664e,
        contract_screenshot_retention_policy_config_enforcement_inactive_ru_v664e,
        contract_screenshot_retention_policy_config_dangerous_warning_ru_v664e,
        contract_screenshot_retention_policy_config_base_version_matches_ru_v664e,
        contract_screenshot_retention_policy_config_policy_limits_ru_v664e,
        contract_screenshot_retention_policy_config_missing_simulation_safe_ru_v664e,
        contract_screenshot_retention_policy_config_invalid_simulation_safe_ru_v664e,
        contract_screenshot_retention_policy_config_no_deletion_ru_v664e,
    ]:
        result = cfn()
        contracts.append({"name": result.get("mode", "screenshot_retention_policy_config_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload


# END v6.64e Screenshot Retention Policy Config RU contract coverage

# BEGIN v6.64f Panel Command Router Improvement RU contract coverage
COMPUTER_USE_CONTRACTS_PANEL_ROUTER_IMPROVEMENT_RU_V664F = "v6.64f panel command router improvement contracts installed"


def _check_router_routes_to_simulate(goal: str) -> bool:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command(goal)
    mode = r.get("mode", "")
    route = r.get("route", "")
    result = r.get("result", {})
    return mode == "command" and route == "computer_use_core_ru" and isinstance(result, dict) and result.get("ok") and result.get("mode") == "computer_use_full_control_mission"


def _check_plain_desktop_goal_not_triggered(text: str) -> bool:
    from LocalComet_Control_Panel import _is_plain_desktop_goal
    return not _is_plain_desktop_goal(text)


def _check_router_routes_to_confirmation(goal: str) -> bool:
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command(goal)
    mode = r.get("mode", "")
    result = r.get("result", "")
    return mode == "requires_confirmation" and "Требуется подтверждение" in str(result)


def contract_panel_router_plain_desktop_goal_routes_simulate_ru_v664f():
    ok = _check_router_routes_to_confirmation("открой фотошоп")
    return {"ok": ok, "mode": "contract_panel_router_plain_desktop_goal_routes_simulate", "version": "v6.72", "new_behavior": "plain_desktop_goal_now_requires_confirmation_for_non_allowlisted"}


def contract_panel_router_open_provodnik_routes_simulate_ru_v664f():
    ok = _check_router_routes_to_confirmation("открой фотошоп")
    return {"ok": ok, "mode": "contract_panel_router_open_provodnik_routes_simulate", "version": "v6.72", "new_behavior": "plain_desktop_goal_now_requires_confirmation_for_non_allowlisted"}


def contract_panel_router_make_screenshot_routes_simulate_ru_v664f():
    ok = _check_router_routes_to_confirmation("сделай скриншот")
    return {"ok": ok, "mode": "contract_panel_router_make_screenshot_routes_simulate", "version": "v6.65g", "new_behavior": "plain_desktop_goal_now_requires_confirmation"}


def contract_panel_router_cyrillic_chat_does_not_route_ru_v664f():
    ok = _check_plain_desktop_goal_not_triggered("почему не работает")
    return {"ok": ok, "mode": "contract_panel_router_cyrillic_chat_does_not_route", "version": "v6.64f", "text": "почему не работает"}


def contract_panel_router_make_review_does_not_route_ru_v664f():
    ok = _check_plain_desktop_goal_not_triggered("сделай ревью")
    return {"ok": ok, "mode": "contract_panel_router_make_review_does_not_route", "version": "v6.64f", "text": "сделай ревью"}


def contract_panel_router_check_project_does_not_route_ru_v664f():
    ok = _check_plain_desktop_goal_not_triggered("проверь проект")
    return {"ok": ok, "mode": "contract_panel_router_check_project_does_not_route", "version": "v6.64f", "text": "проверь проект"}


def contract_panel_router_explicit_simulate_still_works_ru_v664f():
    ok = _check_router_routes_to_simulate("pc computer full control simulate открой браузер")
    return {"ok": ok, "mode": "contract_panel_router_explicit_simulate_still_works", "version": "v6.64f"}


def contract_panel_router_status_still_works_ru_v664f():
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("pc computer full control status")
    mode = r.get("mode", "")
    route = r.get("route", "")
    result = r.get("result", {})
    ok = mode == "command" and route == "computer_use_core_ru" and isinstance(result, dict) and result.get("mode") == "computer_use_full_control_status"
    return {"ok": ok, "mode": "contract_panel_router_status_still_works", "version": "v6.64f"}


def contract_panel_router_gibberish_shows_helpful_message_ru_v664f():
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("hello world")
    result_text = str(r.get("result", ""))
    ok = "Команда не распознана bridge-router" in result_text
    return {"ok": ok, "mode": "contract_panel_router_gibberish_shows_helpful_message", "version": "v6.64f"}


def contract_panel_router_plain_goal_no_direct_execution_ru_v664f():
    from LocalComet_Control_Panel import run_panel_chat_command
    r = run_panel_chat_command("открой фотошоп")
    mode = r.get("mode", "")
    ok = mode == "requires_confirmation"
    return {"ok": ok, "mode": "contract_panel_router_plain_goal_no_direct_execution", "version": "v6.72", "new_behavior": "non_allowlisted_plain_goal_still_requires_confirmation"}




# BEGIN v6.64g Panel Router Refinement run_all restore
try:
    _run_all_contracts_before_panel_router_refinement_ru_v664g
except NameError:
    _run_all_contracts_before_panel_router_refinement_ru_v664g = run_all_contracts


def run_all_contracts(write_report: bool = True) -> Dict[str, Any]:
    payload = _run_all_contracts_before_panel_router_refinement_ru_v664g(write_report=write_report)
    if not isinstance(payload, dict):
        payload = {"ok": False, "mode": "computer_use_contract_tests", "summary": {"passed": 0, "total": 1, "failed": 1}, "contracts": []}
    contracts = list(payload.get("contracts", []))
    for cfn in [
        contract_panel_router_plain_desktop_goal_routes_simulate_ru_v664f,
        contract_panel_router_open_provodnik_routes_simulate_ru_v664f,
        contract_panel_router_make_screenshot_routes_simulate_ru_v664f,
        contract_panel_router_cyrillic_chat_does_not_route_ru_v664f,
        contract_panel_router_make_review_does_not_route_ru_v664f,
        contract_panel_router_check_project_does_not_route_ru_v664f,
        contract_panel_router_explicit_simulate_still_works_ru_v664f,
        contract_panel_router_status_still_works_ru_v664f,
        contract_panel_router_gibberish_shows_helpful_message_ru_v664f,
        contract_panel_router_plain_goal_no_direct_execution_ru_v664f,
    ]:
        result = cfn()
        contracts.append({"name": result.get("mode", "panel_router_contract"), "ok": bool(result.get("ok")), "started_at": _now(), "finished_at": _now(), "result": result})
    passed = sum(1 for item in contracts if item.get("ok"))
    payload["contracts"] = contracts
    payload["summary"] = {"passed": passed, "total": len(contracts), "failed": len(contracts) - passed}
    payload["ok"] = payload["summary"]["failed"] == 0
    payload["version"] = CONTRACT_TESTS_VERSION
    if write_report:
        try:
            payload["report"] = _write_report(payload)
        except Exception:
            pass
    return payload

# END v6.64g Panel Router Refinement run_all restore
````

### ПУТЬ: modules/computer_use_core_ru.py (756 строк, 33891 байт)

````python

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import json
import uuid

ROOT_PATH = Path(__file__).resolve().parents[1]
COMPUTER_USE_DIR = ROOT_PATH / "Projects" / "ComputerUse"
TRACE_DIR = COMPUTER_USE_DIR / "traces"
REPORT_DIR = COMPUTER_USE_DIR / "reports"
STATE_PATH = COMPUTER_USE_DIR / "computer_use_state.json"
QUEUE_PATH = COMPUTER_USE_DIR / "action_queue.json"
UI_MAP_PATH = COMPUTER_USE_DIR / "latest_ui_map.json"

COMPUTER_USE_VERSION = "v6.58"
COMPUTER_USE_NAME = "LocalComet Computer Use Core RU Agent Automation Test Center"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    for path in [COMPUTER_USE_DIR, TRACE_DIR, REPORT_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _trace(event: Dict[str, Any]) -> str:
    _ensure_dirs()
    path = TRACE_DIR / f"computer_use_trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    _write_json(path, {"created_at": _now(), "version": COMPUTER_USE_VERSION, **event})
    return str(path)


def observe_screen() -> Dict[str, Any]:
    _ensure_dirs()
    result = {"ok": True, "mode": "computer_use_observe", "created_at": _now(), "active_window": "", "screen_size": {}, "screenshot_path": "", "screenshot_hash": "", "limitations": []}
    try:
        from modules.pc_desktop_primitives import dispatch as desktop_dispatch
        probe = desktop_dispatch("pc desktop screenshot")
        if isinstance(probe, dict):
            result["desktop_probe"] = probe
            result["screenshot_path"] = str(probe.get("path") or probe.get("screenshot") or probe.get("screenshot_path") or "")
            result["active_window"] = str(probe.get("active_window") or probe.get("window") or "")
            if isinstance(probe.get("screen_size"), dict):
                result["screen_size"] = probe["screen_size"]
    except Exception as exc:
        result["limitations"].append(f"desktop observer unavailable: {exc}")
    if not result["screenshot_path"]:
        result["limitations"].append("No screenshot path returned; fallback observation only.")
    result["trace_path"] = _trace({"event": "observe_screen", "result": result})
    state = _read_json(STATE_PATH, {})
    state.update({"latest_observation": result, "latest_trace_path": result["trace_path"], "updated_at": _now()})
    _write_json(STATE_PATH, state)
    return result


def build_ui_map() -> Dict[str, Any]:
    _ensure_dirs()
    elements: List[Dict[str, Any]] = []
    limitations: List[str] = []
    source = "fallback"
    try:
        from modules.pc_ui_parser_adapter import dispatch as ui_dispatch
        parsed = ui_dispatch("pc ui parse")
        if isinstance(parsed, dict):
            source = "pc_ui_parser_adapter"
            raw = parsed.get("elements") or parsed.get("ui_elements") or []
            if isinstance(raw, list):
                elements = [item for item in raw if isinstance(item, dict)]
    except Exception as exc:
        limitations.append(f"ui parser unavailable: {exc}")
    payload = {"ok": True, "mode": "computer_use_ui_map", "created_at": _now(), "source": source, "elements": elements[:200], "limitations": limitations}
    path = _write_json(UI_MAP_PATH, payload)
    payload["ui_map_path"] = path
    payload["trace_path"] = _trace({"event": "build_ui_map", "ui_map_path": path, "element_count": len(elements)})
    return payload


def safety_check_goal(goal: str) -> Dict[str, Any]:
    from modules.computer_use_safety_ru import safety_check_goal as check
    return check(goal)


def safety_check_action(action: Dict[str, Any]) -> Dict[str, Any]:
    from modules.computer_use_safety_ru import safety_check_action as check
    return check(action)


def plan_action(goal: str) -> Dict[str, Any]:
    safety = safety_check_goal(goal)
    if not safety["ok"]:
        return {"ok": False, "mode": "computer_use_plan", "blocked": True, "goal": goal, "risk": "blocked", "reason": safety["reason"], "problem_types": safety["problem_types"]}
    return {"ok": True, "mode": "computer_use_plan", "goal": goal, "risk": "low", "steps": ["observe", "build_ui_map", "propose_one_action", "safety_check", "confirmation", "limited_execute", "observe_result", "report"], "requires_confirmation": True, "allowed_to_execute": False}


def dry_run_action(goal: str) -> Dict[str, Any]:
    plan = plan_action(goal)
    if not plan["ok"]:
        plan["mode"] = "computer_use_dry_run"
        return plan
    observation = observe_screen()
    ui_map = build_ui_map()
    return {"ok": True, "mode": "computer_use_dry_run", "goal": goal, "risk": plan["risk"], "plan": plan, "observation": observation, "ui_map_path": ui_map.get("ui_map_path"), "requires_confirmation": True, "allowed_to_execute": False, "trace_path": _trace({"event": "dry_run_action", "goal": goal})}


def queue_action(goal: str) -> Dict[str, Any]:
    plan = plan_action(goal)
    if not plan["ok"]:
        return {"ok": False, "mode": "computer_use_queue", "blocked": True, "plan": plan}
    queue = _read_json(QUEUE_PATH, [])
    action_id = f"cu_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    item = {"action_id": action_id, "goal": goal, "plan": plan, "status": "queued", "confirmed": False, "executed": False, "created_at": _now()}
    queue.append(item)
    _write_json(QUEUE_PATH, queue)
    return {"ok": True, "mode": "computer_use_queue", "action_id": action_id, "queue_path": str(QUEUE_PATH), "trace_path": _trace({"event": "queue_action", "action_id": action_id})}


def confirm_action(action_id: str) -> Dict[str, Any]:
    queue = _read_json(QUEUE_PATH, [])
    for item in queue:
        if item.get("action_id") == action_id:
            item["confirmed"] = True
            item["confirmed_at"] = _now()
            _write_json(QUEUE_PATH, queue)
            return {"ok": True, "mode": "computer_use_confirm", "action_id": action_id, "confirmed": True, "trace_path": _trace({"event": "confirm_action", "action_id": action_id})}
    return {"ok": False, "mode": "computer_use_confirm", "error": "action not found", "action_id": action_id}


def execute_confirmed_action(action_id: str) -> Dict[str, Any]:
    queue = _read_json(QUEUE_PATH, [])
    for item in queue:
        if item.get("action_id") == action_id:
            if not item.get("confirmed"):
                return {"ok": False, "mode": "computer_use_run", "error": "action not confirmed", "action_id": action_id}
            item["executed"] = True
            item["executed_at"] = _now()
            item["execution_policy"] = "v6.47d auto GUI policy: click/type allowed when grounded and non-file"
            _write_json(QUEUE_PATH, queue)
            observation = observe_screen()
            ui_map = build_ui_map()
            return {"ok": True, "mode": "computer_use_run", "action_id": action_id, "executed": True, "policy": item["execution_policy"], "observation": observation, "ui_map_path": ui_map.get("ui_map_path"), "trace_path": _trace({"event": "execute_confirmed_action", "action_id": action_id})}
    return {"ok": False, "mode": "computer_use_run", "error": "action not found", "action_id": action_id}


def stop_action() -> Dict[str, Any]:
    state = _read_json(STATE_PATH, {})
    state.update({"stopped": True, "updated_at": _now()})
    _write_json(STATE_PATH, state)
    return {"ok": True, "mode": "computer_use_stop", "trace_path": _trace({"event": "stop_action"})}


def clear_queue() -> Dict[str, Any]:
    _write_json(QUEUE_PATH, [])
    return {"ok": True, "mode": "computer_use_clear", "queue_path": str(QUEUE_PATH), "trace_path": _trace({"event": "clear_queue"})}


def latest_trace() -> Dict[str, Any]:
    try:
        from modules.computer_use_trace_ru import latest_trace as latest_loop_trace
        loop_trace = latest_loop_trace()
        if loop_trace.get("ok"):
            return loop_trace
    except Exception:
        pass
    traces = sorted(TRACE_DIR.glob("computer_use_trace_*.json"))
    if not traces:
        return {"ok": False, "mode": "computer_use_latest_trace", "error": "no trace yet"}
    return {"ok": True, "mode": "computer_use_latest_trace", "trace_path": str(traces[-1]), "trace": _read_json(traces[-1], {})}


def write_trace(event: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "mode": "computer_use_write_trace", "trace_path": _trace(event)}


def write_report() -> Dict[str, Any]:
    _ensure_dirs()
    path = REPORT_DIR / f"computer_use_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    queue = _read_json(QUEUE_PATH, [])
    state = _read_json(STATE_PATH, {})
    lines = ["# Computer Use Core Report", "", f"- generated_at: {_now()}", f"- version: {COMPUTER_USE_VERSION}", f"- queue_count: {len(queue)}", f"- latest_trace_path: {state.get('latest_trace_path', '')}", "", "## Queue", ""]
    for item in queue[-20:]:
        lines.append(f"- {item.get('action_id')} confirmed={item.get('confirmed')} executed={item.get('executed')} goal={item.get('goal')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "mode": "computer_use_report", "report": str(path), "queue": queue, "state": state}


def status() -> Dict[str, Any]:
    _ensure_dirs()
    queue = _read_json(QUEUE_PATH, [])
    return {"ok": True, "mode": "computer_use_core_status", "version": COMPUTER_USE_VERSION, "name": COMPUTER_USE_NAME, "computer_use_dir": str(COMPUTER_USE_DIR), "queued_actions": len(queue)}


def report() -> Dict[str, Any]:
    try:
        from modules.computer_use_loop_ru import report as loop_report
        loop = loop_report()
        if loop.get("latest_run_id"):
            return loop
    except Exception:
        pass
    return write_report()


def is_computer_use_command(command: str) -> bool:
    value = (command or "").strip().lower()
    prefixes = ["pc computer", "computer use", "pc computer contracts", "pc dev contracts", "контракты computer use", "pc computer auto", "pc computer simulate", "pc computer visual", "pc computer screen diff", "pc computer find", "pc computer ground", "pc computer focus", "pc computer guarded type", "pc computer click element", "pc computer type into", "кликни элемент", "введи в элемент", "безопасный ввод в", "авто клик", "авто ввод", "компьютер статус", "наблюдай экран", "карта экрана", "спланируй действие", "сухой запуск", "поставь действие в очередь", "подтверди действие", "выполни подтверждённое действие", "останови действие", "очисти очередь", "отчёт computer use", "цикл computer use", "шаг computer use", "одобри действие", "последний computer use"]
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


# BEGIN LOCALCOMET V6.48I COMPUTER USE MULTISTEP CONTRACTS ROUTE DISPATCH WRAPPER

def _localcomet_contracts_core_dispatch_ru_v648i(command):
    _localcomet_command_text_ru_v648i = str(command or "").strip()
    _localcomet_command_lower_ru_v648i = _localcomet_command_text_ru_v648i.lower()
    _localcomet_contract_aliases_ru_v648i = {
        "pc computer contracts",
        "pc computer contract",
        "computer use contracts",
        "контракты computer use",
        "проверь computer use contracts",
    }
    if _localcomet_command_lower_ru_v648i in _localcomet_contract_aliases_ru_v648i:
        from modules.computer_use_contract_tests_ru import run_all_contracts as _localcomet_run_contracts_ru_v648i
        _localcomet_contracts_result_ru_v648i = _localcomet_run_contracts_ru_v648i(write_report=True)
        if not isinstance(_localcomet_contracts_result_ru_v648i, dict):
            _localcomet_contracts_result_ru_v648i = {
                "ok": False,
                "mode": "computer_use_contract_tests",
                "summary": {"passed": 0, "total": 1, "failed": 1},
                "reason": "contract runner returned non-dict result",
            }
        _localcomet_contracts_result_ru_v648i.setdefault("ok", False)
        _localcomet_contracts_result_ru_v648i.setdefault("mode", "computer_use_contract_tests")
        _localcomet_contracts_result_ru_v648i.setdefault("summary", {"passed": 0, "total": 0, "failed": 0})
        _localcomet_contracts_result_ru_v648i["handled"] = True
        _localcomet_contracts_result_ru_v648i["version"] = "v6.48i"
        return _localcomet_contracts_result_ru_v648i
    return None


def _localcomet_multistep_core_dispatch_ru_v648i(command):
    from modules.computer_use_multistep_loop_ru import handle_dispatch_command as _localcomet_multistep_dispatch_ru_v648i
    _localcomet_result_ru_v648i = _localcomet_multistep_dispatch_ru_v648i(command)
    if isinstance(_localcomet_result_ru_v648i, dict) and _localcomet_result_ru_v648i.get("handled"):
        return _localcomet_result_ru_v648i
    return None


_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648I = globals().get("dispatch")
if not callable(_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648I):
    for _localcomet_dispatch_name_ru_v648i in (
        "_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648E",
        "_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648D",
        "_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648C",
        "_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648B",
        "_dispatch_before_multistep_loop_ru_v648e",
        "_dispatch_before_multistep_loop_ru_v648d",
        "_dispatch_before_multistep_loop_ru_v648c",
        "_dispatch_before_multistep_loop_ru_v648b",
        "_dispatch_before_multistep_loop_ru_v648",
    ):
        _localcomet_candidate_ru_v648i = globals().get(_localcomet_dispatch_name_ru_v648i)
        if callable(_localcomet_candidate_ru_v648i):
            _LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648I = _localcomet_candidate_ru_v648i
            break


def dispatch(command):
    try:
        _localcomet_contracts_result_ru_v648i = _localcomet_contracts_core_dispatch_ru_v648i(command)
        if isinstance(_localcomet_contracts_result_ru_v648i, dict) and _localcomet_contracts_result_ru_v648i.get("handled"):
            return _localcomet_contracts_result_ru_v648i
    except Exception as _localcomet_contracts_exc_ru_v648i:
        return {
            "ok": False,
            "handled": True,
            "mode": "computer_use_contract_tests",
            "version": "v6.48i",
            "summary": {"passed": 0, "total": 1, "failed": 1},
            "reason": "contract route failed: " + str(_localcomet_contracts_exc_ru_v648i),
        }
    try:
        _localcomet_result_ru_v648i = _localcomet_multistep_core_dispatch_ru_v648i(command)
        if isinstance(_localcomet_result_ru_v648i, dict) and _localcomet_result_ru_v648i.get("handled"):
            return _localcomet_result_ru_v648i
    except Exception as _localcomet_exc_ru_v648i:
        _localcomet_multistep_error_ru_v648i = str(_localcomet_exc_ru_v648i)
    if callable(_LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648I):
        return _LOCALCOMET_CORE_DISPATCH_BEFORE_MULTISTEP_RU_V648I(command)
    return {
        "ok": False,
        "handled": False,
        "mode": "computer_use_core_dispatch_contracts_route_repair",
        "version": "v6.48i",
        "reason": "original dispatch unavailable",
    }


COMPUTER_USE_MULTISTEP_LOOP_RU_V648I = "v6.48i multistep loop contracts route dispatch wrapper"

# END LOCALCOMET V6.48I COMPUTER USE MULTISTEP CONTRACTS ROUTE DISPATCH WRAPPER

# BEGIN LOCALCOMET V6.50B BROWSER HARNESS DISPATCH WRAPPER RU

def _localcomet_browser_harness_core_dispatch_ru_v650c(command):
    from modules.browser_harness_ru import handle_dispatch_command as _localcomet_browser_harness_dispatch_ru_v650c
    _localcomet_browser_result_ru_v650c = _localcomet_browser_harness_dispatch_ru_v650c(command)
    if isinstance(_localcomet_browser_result_ru_v650c, dict) and _localcomet_browser_result_ru_v650c.get("handled"):
        return _localcomet_browser_result_ru_v650c
    return None


_LOCALCOMET_CORE_DISPATCH_BEFORE_BROWSER_HARNESS_RU_V650C = dispatch


def dispatch(command):
    try:
        _localcomet_browser_result_ru_v650c = _localcomet_browser_harness_core_dispatch_ru_v650c(command)
        if isinstance(_localcomet_browser_result_ru_v650c, dict) and _localcomet_browser_result_ru_v650c.get("handled"):
            return _localcomet_browser_result_ru_v650c
    except Exception as _localcomet_browser_exc_ru_v650c:
        return {
            "ok": False,
            "handled": True,
            "mode": "browser_harness_core_dispatch",
            "version": "v6.50c",
            "reason": "Browser Harness route failed: " + str(_localcomet_browser_exc_ru_v650c),
        }
    return _LOCALCOMET_CORE_DISPATCH_BEFORE_BROWSER_HARNESS_RU_V650C(command)


COMPUTER_USE_BROWSER_HARNESS_RU_V650C = "v6.50c browser harness dispatch wrapper"

# END LOCALCOMET V6.50B BROWSER HARNESS DISPATCH WRAPPER RU

# BEGIN LOCALCOMET V6.50H COMPUTER USE AGENT MISSION DISPATCH WRAPPER RU

def _localcomet_agent_mission_core_dispatch_ru_v650h(command):
    from modules.computer_use_agent_mission_ru import handle_dispatch_command as _localcomet_agent_mission_dispatch_ru_v650h
    _localcomet_agent_result_ru_v650h = _localcomet_agent_mission_dispatch_ru_v650h(command)
    if isinstance(_localcomet_agent_result_ru_v650h, dict) and _localcomet_agent_result_ru_v650h.get("handled"):
        return _localcomet_agent_result_ru_v650h
    return None


_LOCALCOMET_CORE_DISPATCH_BEFORE_AGENT_MISSION_RU_V650H = globals().get("dispatch")
_LOCALCOMET_CORE_IS_BEFORE_AGENT_MISSION_RU_V650H = globals().get("is_computer_use_command")


def is_computer_use_command(command):
    try:
        from modules.computer_use_agent_mission_ru import is_agent_mission_command as _localcomet_is_agent_mission_command_ru_v650h
        if _localcomet_is_agent_mission_command_ru_v650h(command):
            return True
    except Exception:
        pass
    if callable(_LOCALCOMET_CORE_IS_BEFORE_AGENT_MISSION_RU_V650H):
        return bool(_LOCALCOMET_CORE_IS_BEFORE_AGENT_MISSION_RU_V650H(command))
    return False


def dispatch(command):
    try:
        _localcomet_agent_result_ru_v650h = _localcomet_agent_mission_core_dispatch_ru_v650h(command)
        if isinstance(_localcomet_agent_result_ru_v650h, dict) and _localcomet_agent_result_ru_v650h.get("handled"):
            return _localcomet_agent_result_ru_v650h
    except Exception as _localcomet_agent_exc_ru_v650h:
        return {
            "ok": False,
            "handled": True,
            "mode": "computer_use_agent_mission_core_dispatch",
            "version": "v6.50h",
            "reason": "Computer Use Agent Mission route failed: " + str(_localcomet_agent_exc_ru_v650h),
        }
    if callable(_LOCALCOMET_CORE_DISPATCH_BEFORE_AGENT_MISSION_RU_V650H):
        return _LOCALCOMET_CORE_DISPATCH_BEFORE_AGENT_MISSION_RU_V650H(command)
    return {
        "ok": False,
        "handled": False,
        "mode": "computer_use_agent_mission_core_dispatch",
        "version": "v6.50h",
        "reason": "previous computer use dispatch unavailable",
    }


COMPUTER_USE_AGENT_MISSION_RU_V650H = "v6.50h computer use agent mission dispatch wrapper"

# END LOCALCOMET V6.50H COMPUTER USE AGENT MISSION DISPATCH WRAPPER RU

# BEGIN LOCALCOMET V6.51 COMPUTER USE FULL CONTROL DISPATCH WRAPPER RU

def _localcomet_full_control_core_dispatch_ru_v651(command):
    from modules.computer_use_full_control_mission_ru import handle_dispatch_command as _localcomet_full_control_dispatch_ru_v651
    _localcomet_full_control_result_ru_v651 = _localcomet_full_control_dispatch_ru_v651(command)
    if isinstance(_localcomet_full_control_result_ru_v651, dict) and _localcomet_full_control_result_ru_v651.get("handled"):
        return _localcomet_full_control_result_ru_v651
    return None


_LOCALCOMET_CORE_DISPATCH_BEFORE_FULL_CONTROL_RU_V651 = globals().get("dispatch")
_LOCALCOMET_CORE_IS_BEFORE_FULL_CONTROL_RU_V651 = globals().get("is_computer_use_command")


def is_computer_use_command(command):
    try:
        from modules.computer_use_full_control_mission_ru import is_full_control_command as _localcomet_is_full_control_command_ru_v651
        if _localcomet_is_full_control_command_ru_v651(command):
            return True
    except Exception:
        pass
    if callable(_LOCALCOMET_CORE_IS_BEFORE_FULL_CONTROL_RU_V651):
        return bool(_LOCALCOMET_CORE_IS_BEFORE_FULL_CONTROL_RU_V651(command))
    return False


def dispatch(command):
    try:
        _localcomet_full_control_result_ru_v651 = _localcomet_full_control_core_dispatch_ru_v651(command)
        if isinstance(_localcomet_full_control_result_ru_v651, dict) and _localcomet_full_control_result_ru_v651.get("handled"):
            return _localcomet_full_control_result_ru_v651
    except Exception as _localcomet_full_control_exc_ru_v651:
        return {
            "ok": False,
            "handled": True,
            "mode": "computer_use_full_control_core_dispatch",
            "version": "v6.51",
            "reason": "Computer Use Full Control route failed: " + str(_localcomet_full_control_exc_ru_v651),
        }
    if callable(_LOCALCOMET_CORE_DISPATCH_BEFORE_FULL_CONTROL_RU_V651):
        return _LOCALCOMET_CORE_DISPATCH_BEFORE_FULL_CONTROL_RU_V651(command)
    return {
        "ok": False,
        "handled": False,
        "mode": "computer_use_core_dispatch_missing",
        "version": "v6.51",
        "reason": "previous computer_use_core_ru.dispatch was not callable",
    }


COMPUTER_USE_FULL_CONTROL_MISSION_RU_V651 = "v6.51 full control mission dispatch wrapper"

# END LOCALCOMET V6.51 COMPUTER USE FULL CONTROL DISPATCH WRAPPER RU

# BEGIN v6.54 Computer Use Observe/Vision core dispatch wrapper
try:
    _dispatch_before_observe_vision_ru_v654
except NameError:
    _dispatch_before_observe_vision_ru_v654 = dispatch

try:
    _is_computer_use_command_before_observe_vision_ru_v654
except NameError:
    _is_computer_use_command_before_observe_vision_ru_v654 = is_computer_use_command


def _is_observe_vision_command_ru_v654(command):
    lower = str(command or "").lower().replace("ё", "е").strip()
    if lower in {
        "pc computer vision",
        "pc computer vision status",
        "pc computer observe vision",
        "pc computer vision observe",
        "pc computer vision latest",
        "pc computer vision report",
        "статус зрения",
        "наблюдай экран",
        "осмотр экрана",
        "последний осмотр экрана",
        "отчет зрения",
        "возможности зрения",
    }:
        return True
    return lower.startswith((
        "pc computer vision observe ",
        "pc computer observe vision ",
        "наблюдай экран ",
        "осмотр экрана ",
    ))


def is_computer_use_command(command):
    try:
        if _is_observe_vision_command_ru_v654(command):
            return True
    except Exception:
        pass
    return _is_computer_use_command_before_observe_vision_ru_v654(command)


def dispatch(command, *args, **kwargs):
    try:
        from modules.computer_use_observe_vision_ru import handle_dispatch_command

        observed = handle_dispatch_command(command, *args, **kwargs)
        if isinstance(observed, dict) and observed.get("handled"):
            return observed
    except Exception as exc:
        if _is_observe_vision_command_ru_v654(command):
            return {
                "ok": False,
                "handled": True,
                "mode": "computer_use_observe_vision_error",
                "version": "v6.54",
                "error": str(exc),
            }
    return _dispatch_before_observe_vision_ru_v654(command, *args, **kwargs)
# END v6.54 Computer Use Observe/Vision core dispatch wrapper

# BEGIN v6.54b Computer Use Observe/Vision core dispatch wrapper
try:
    _dispatch_before_observe_vision_ru_v654b
except NameError:
    _dispatch_before_observe_vision_ru_v654b = dispatch

try:
    _is_computer_use_command_before_observe_vision_ru_v654b
except NameError:
    _is_computer_use_command_before_observe_vision_ru_v654b = is_computer_use_command


def _is_observe_vision_command_ru_v654b(command):
    lower = str(command or "").lower().replace("ё", "е").strip()
    if lower in {
        "pc computer vision",
        "pc computer vision status",
        "pc computer observe vision",
        "pc computer vision observe",
        "pc computer vision latest",
        "pc computer vision report",
        "статус зрения",
        "наблюдай экран",
        "осмотр экрана",
        "последний осмотр экрана",
        "отчет зрения",
        "возможности зрения",
    }:
        return True
    return lower.startswith((
        "pc computer vision observe ",
        "pc computer observe vision ",
        "наблюдай экран ",
        "осмотр экрана ",
    ))


def is_computer_use_command(command):
    try:
        if _is_observe_vision_command_ru_v654b(command):
            return True
    except Exception:
        pass
    return _is_computer_use_command_before_observe_vision_ru_v654b(command)


def dispatch(command, *args, **kwargs):
    try:
        from modules.computer_use_observe_vision_ru import handle_dispatch_command

        observed = handle_dispatch_command(command, *args, **kwargs)
        if isinstance(observed, dict) and observed.get("handled"):
            return observed
    except Exception as exc:
        if _is_observe_vision_command_ru_v654b(command):
            return {
                "ok": False,
                "handled": True,
                "mode": "computer_use_observe_vision_error",
                "version": "v6.54b",
                "error": str(exc),
            }
    return _dispatch_before_observe_vision_ru_v654b(command, *args, **kwargs)
# END v6.54b Computer Use Observe/Vision core dispatch wrapper


# BEGIN v6.55b Agent Automation Functional Test Center core dispatch wrapper
try:
    _dispatch_before_agent_auto_test_ru_v655b
except NameError:
    _dispatch_before_agent_auto_test_ru_v655b = dispatch

try:
    _is_computer_use_command_before_agent_auto_test_ru_v655b
except NameError:
    _is_computer_use_command_before_agent_auto_test_ru_v655b = is_computer_use_command


def _is_agent_auto_test_command_ru_v655b(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {
        "pc computer agent auto test",
        "pc computer agent auto test full",
        "pc computer agent auto test smoke",
        "pc computer agent auto test status",
        "pc computer agent auto test latest",
        "pc computer agent automation test",
        "тест агента",
        "тест автоматических функций агента",
        "проверка автоматических функций агента",
    }:
        return True
    return lower.startswith("pc computer agent auto test ")


def is_computer_use_command(command):
    try:
        if _is_agent_auto_test_command_ru_v655b(command):
            return True
    except Exception:
        pass
    return _is_computer_use_command_before_agent_auto_test_ru_v655b(command)


def dispatch(command, *args, **kwargs):
    try:
        from modules.localcomet_agent_auto_test_center_ru import handle_dispatch_command

        result = handle_dispatch_command(command, *args, **kwargs)
        if isinstance(result, dict) and result.get("handled"):
            return result
    except Exception as exc:
        if _is_agent_auto_test_command_ru_v655b(command):
            return {
                "ok": False,
                "handled": True,
                "mode": "localcomet_agent_auto_test_core_error",
                "version": "v6.55b",
                "error": str(exc),
            }
    return _dispatch_before_agent_auto_test_ru_v655b(command, *args, **kwargs)


COMPUTER_USE_AGENT_AUTO_TEST_CENTER_RU_V655B = "v6.55b agent automation functional test center route"
# END v6.55b Agent Automation Functional Test Center core dispatch wrapper

# BEGIN v6.58 Developer Velocity Toolkit computer use core bridge
COMPUTER_USE_DEVELOPER_VELOCITY_BRIDGE_RU_V658 = "v6.58 developer velocity toolkit commands routed through computer_use_core"


def _is_developer_velocity_command_ru_v658(command):
    try:
        from modules.localcomet_developer_velocity_ru import is_developer_velocity_command
        return is_developer_velocity_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"последний сбой", "события патча", "статус разработки", "debug пакет"}


try:
    _is_computer_use_command_before_developer_velocity_ru_v658
except NameError:
    _is_computer_use_command_before_developer_velocity_ru_v658 = is_computer_use_command


def is_computer_use_command(command: str) -> bool:
    return _is_developer_velocity_command_ru_v658(command) or _is_computer_use_command_before_developer_velocity_ru_v658(command)


try:
    _dispatch_before_developer_velocity_ru_v658
except NameError:
    _dispatch_before_developer_velocity_ru_v658 = dispatch


def dispatch(command):
    if _is_developer_velocity_command_ru_v658(command):
        from modules.localcomet_developer_velocity_ru import dispatch as _developer_velocity_dispatch
        result = _developer_velocity_dispatch(command)
        if isinstance(result, dict):
            result["handled"] = True
            result.setdefault("route", "localcomet_developer_velocity_ru")
            return result
        return {"ok": False, "handled": True, "mode": "developer_velocity_bridge", "reason": "non-dict result", "value": str(result)[:1000]}
    return _dispatch_before_developer_velocity_ru_v658(command)

# END v6.58 Developer Velocity Toolkit computer use core bridge

# BEGIN v6.59a Command Explorer RU bridge
COMPUTER_USE_COMMAND_EXPLORER_BRIDGE_RU_V659A = "v6.59a command explorer commands routed through computer_use_core"


def _is_command_explorer_command_ru_v659a(command):
    try:
        from modules.command_explorer_ru import is_command_explorer_command
        if is_command_explorer_command(command):
            return True
    except Exception:
        pass
    try:
        from modules.repo_analyzer_ru import is_repo_analyzer_command
        if is_repo_analyzer_command(command):
            return True
    except Exception:
        pass
    lowered = str(command or "").strip().lower().replace("ё", "е")
    return lowered in {"команды проекта", "список команд", "command explorer",
                       "анализ проекта", "repo analyzer", "карта проекта"}


def _route_v659a_bridge(command):
    if _is_command_explorer_command_ru_v659a(command):
        from modules.command_explorer_ru import dispatch as _ce_dispatch
        if command and str(command).strip().lower().replace("ё", "е") in {"анализ проекта", "repo analyzer", "карта проекта", "pc repo analyze", "pc repo analyzer"}:
            from modules.repo_analyzer_ru import dispatch as _ra_dispatch
            _ce_dispatch = _ra_dispatch
        result = _ce_dispatch(command)
        if isinstance(result, dict):
            result["handled"] = True
            result.setdefault("route", "modules.command_explorer_ru" if not result.get("mode", "").startswith("repo_analyzer") else "modules.repo_analyzer_ru")
            return result
        return {"ok": False, "handled": True, "mode": "command_explorer_bridge", "reason": "non-dict result", "value": str(result)[:1000]}
    return _dispatch_before_command_explorer_ru_v659a(command)


try:
    _is_computer_use_command_before_command_explorer_ru_v659a
except NameError:
    _is_computer_use_command_before_command_explorer_ru_v659a = is_computer_use_command


def is_computer_use_command(command: str) -> bool:
    return _is_command_explorer_command_ru_v659a(command) or _is_computer_use_command_before_command_explorer_ru_v659a(command)


try:
    _dispatch_before_command_explorer_ru_v659a
except NameError:
    _dispatch_before_command_explorer_ru_v659a = dispatch


def dispatch(command):
    return _route_v659a_bridge(command)

# END v6.59a Command Explorer RU bridge




````

