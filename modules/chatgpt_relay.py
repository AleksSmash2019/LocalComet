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
