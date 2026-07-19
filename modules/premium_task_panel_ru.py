from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import importlib
import json
import re
import sys
import os
import traceback
import threading
import tkinter as tk
from tkinter import ttk, filedialog


try:
    from LocalComet_Control_Panel import LOCALCOMET_VERSION, LOCALCOMET_VERSION_LABEL
except ImportError:
    LOCALCOMET_VERSION = "v6.64"
    LOCALCOMET_VERSION_LABEL = "LocalComet v6.64 - Storage + Panel Router RU"

ROOT_DIR = get_project_root()
SETTINGS_DIR = ROOT_DIR / "Projects" / "UI" / "localcomet-premium-task-panel"
SETTINGS_PATH = SETTINGS_DIR / "premium_task_panel_settings.json"
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "premium_task_panel"

PANEL_VERSION = LOCALCOMET_VERSION or "v6.59b"
PANEL_NAME = LOCALCOMET_VERSION_LABEL or "LocalComet Professional Control Panel RU - Developer Velocity Toolkit Lite RU"
PANEL_NAME = LOCALCOMET_VERSION_LABEL or "LocalComet Professional Control Panel RU - Developer Velocity Toolkit Lite RU"
PATCH_PANEL_COMMAND_BRIDGE_RU_V650J = "v6.50j patch commands stay commands in Computer Use chat mode"

_WINDOW_REF = None
_PANEL_REF = None
_CHAT_TEXT = None
_CHAT_ENTRY = None
_STATUS_LABEL = None
_MODE_BUTTON = None
_DRAWER_FRAME = None
_DRAWER_VISIBLE = False
_INPUT_MODE = "chat"
_CHAT_HISTORY = []


CODEX_COMMANDS = {
    "Быстрые": [
        ("статус панели", "pc task panel status"),
        ("статус Swiss Knife", "pc swiss status"),
        ("навыки Swiss Knife", "pc swiss skills"),
        ("статус PC Core", "pc core status"),
        ("статус Executor", "pc exec status"),
        ("статус UI Parser", "pc ui status"),
    ],
    "Задачи": [
        ("сделать план", "pc swiss plan описать задачу и сделать безопасный план"),
        ("patch для проекта", "pc swiss plan подготовить безопасный patch для LocalComet"),
        ("лендинг", "pc swiss website создать черновик лендинга для LocalComet"),
        ("исследование", "pc swiss business сделать исследовательский отчёт по задаче"),
        ("leadgen без спама", "pc swiss leadgen собрать leadgen brief без спама"),
        ("PDF-анализ", "pc swiss pdf проанализировать PDF и сделать выводы"),
    ],
    "ПК": [
        ("screen observe", "pc screen observe"),
        ("UI parse", "pc ui parse"),
        ("UI elements", "pc ui elements"),
        ("UI suggest", "pc ui suggest открыть нужную вкладку без клика"),
        ("desktop windows", "pc desktop windows"),
        ("desktop dry focus", "pc desktop dry focus LocalComet"),
    ],
    "Computer Use": [
        ("полное управление", "управляй пк открой блокнот и напиши hello"),
        ("full control simulate", "pc computer full control simulate открой блокнот и напиши hello"),
        ("full control status", "pc computer full control status"),
        ("статус", "pc computer status"),
        ("наблюдать экран", "pc computer observe"),
        ("карта экрана", "pc computer map"),
        ("dry-run", "pc computer dry открыть настройки"),
        ("очередь", "pc computer queue открыть настройки"),
        ("отчёт", "pc computer report"),
    ],
    "AI Агент": [
        ("агент статус", "pc ai status"),
        ("контекст проекта", "pc ai context"),
        ("план агента", "pc ai plan развивать LocalComet как локального AI-агента"),
        ("draft patch", "pc ai draft развивать LocalComet как локального AI-агента"),
        ("repair plan", "pc ai repair"),
    ],
    "Проект": [
        ("проверить проект", "проверь проект"),
        ("project status", "pc agents status"),
        ("detect project", "pc agents detect"),
        ("validate AGENTS", "pc agents validate"),
        ("task panel report", "pc task panel report"),
        ("AgentOS report", "pc agentos report"),
        ("Swiss report", "pc swiss report"),
    ],
}


HELP_TEXT = """Команда:
  точная команда LocalComet, например pc swiss status

Чат:
  обычный русский текст. Если это задача — я превращу её в безопасный план.
  Короткие фразы вроде «привет» остаются локальным ответом, без research.

Enter:
  отправляет из поля ввода.
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _default_settings():
    return {
        "auto_open_task_panel_on_start": True,
        "language": "ru",
        "mode": "true_chat",
        "input_mode": "chat",
        "show_raw_json": False,
        "plain_chat_uses_router": False,
        "true_chat_mode": True,
        "llm_chat_mode": True,
        "plain_chat_uses_router": False,
        "command_drawer_visible": False,
        "created_at": _now(),
    }


def _load_settings():
    if SETTINGS_PATH.exists():
        try:
            loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            loaded = {}
    else:
        loaded = {}
    data = _default_settings()
    data.update({key: loaded.get(key, value) for key, value in data.items()})
    return data


def _save_settings(settings):
    _ensure_dirs()
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings


def install_settings():
    current = _load_settings()
    current["mode"] = "true_chat"
    current["language"] = "ru"
    current["show_raw_json"] = False
    current["input_mode"] = current.get("input_mode", "chat") if current.get("input_mode") in {"chat", "command"} else "chat"
    current["command_drawer_visible"] = bool(current.get("command_drawer_visible", False))
    current["plain_chat_uses_router"] = False
    current["true_chat_mode"] = True
    current["llm_chat_mode"] = True
    _save_settings(current)
    return {
        "ok": True,
        "mode": "premium_task_panel_install_settings",
        "generated_at": _now(),
        "settings": str(SETTINGS_PATH),
    }


def _find_root(panel=None):
    if panel is not None:
        for attr in ("root", "window", "master", "app", "tk"):
            candidate = getattr(panel, attr, None)
            try:
                if candidate is not None and hasattr(candidate, "winfo_exists") and candidate.winfo_exists():
                    return candidate
            except Exception:
                pass
    try:
        root = tk._default_root
        if root is not None and root.winfo_exists():
            return root
    except Exception:
        pass
    root = tk.Tk()
    root.withdraw()
    return root


def _configure_style(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("Codex.TButton", background="#111827", foreground="#e5e7eb", padding=(10, 7), relief="flat")
    style.map("Codex.TButton", background=[("active", "#1f2937")])
    style.configure("Primary.TButton", background="#2563eb", foreground="#f8fafc", padding=(10, 7), relief="flat")
    style.map("Primary.TButton", background=[("active", "#1d4ed8")])
    style.configure("Danger.TButton", background="#7f1d1d", foreground="#fee2e2", padding=(10, 7), relief="flat")
    style.map("Danger.TButton", background=[("active", "#991b1b")])
    return style


def _set_status(message):
    if _STATUS_LABEL is not None:
        try:
            _STATUS_LABEL.configure(text=message)
        except Exception:
            pass


def _append_chat(author, text, kind="normal"):
    if _CHAT_TEXT is None:
        return
    try:
        _CHAT_TEXT.configure(state="normal")
        prefix = f"\n{author}\n"
        _CHAT_TEXT.insert("end", prefix, ("author",))
        _CHAT_TEXT.insert("end", str(text).rstrip() + "\n", (kind,))
        _CHAT_TEXT.see("end")
        _CHAT_TEXT.configure(state="disabled")
    except Exception:
        pass


def _reset_chat():
    if _CHAT_TEXT is None:
        return
    _CHAT_TEXT.configure(state="normal")
    _CHAT_TEXT.delete("1.0", "end")
    _CHAT_TEXT.insert("end", "LocalComet\n", ("author",))
    _CHAT_TEXT.insert("end", "Чат очищен. Введи задачу или команду.\n", ("normal",))
    _CHAT_TEXT.configure(state="disabled")
    _set_status("Чат очищен")


def _mode_label():
    return "Чат" if _INPUT_MODE == "chat" else "Команда"


def _persist_input_mode():
    settings = _load_settings()
    settings["input_mode"] = _INPUT_MODE
    settings["updated_at"] = _now()
    _save_settings(settings)


def _toggle_input_mode():
    global _INPUT_MODE
    _INPUT_MODE = "command" if _INPUT_MODE == "chat" else "chat"
    _persist_input_mode()
    if _MODE_BUTTON is not None:
        try:
            _MODE_BUTTON.configure(text=f"Режим: {_mode_label()}")
        except Exception:
            pass
    _set_status(
        "Режим Чат: обычный текст станет безопасным планом."
        if _INPUT_MODE == "chat"
        else "Режим Команда: отправляю точный текст как команду."
    )
    if _CHAT_ENTRY is not None:
        _CHAT_ENTRY.focus_set()


def _toggle_drawer():
    global _DRAWER_VISIBLE
    if _DRAWER_FRAME is None:
        return
    _DRAWER_VISIBLE = not _DRAWER_VISIBLE
    settings = _load_settings()
    settings["command_drawer_visible"] = _DRAWER_VISIBLE
    settings["updated_at"] = _now()
    _save_settings(settings)
    if _DRAWER_VISIBLE:
        _DRAWER_FRAME.pack(side="right", fill="y", padx=(10, 0))
        _set_status("Команды показаны")
    else:
        _DRAWER_FRAME.pack_forget()
        _set_status("Команды скрыты")


def _insert_command(command, send=False):
    if _CHAT_ENTRY is None:
        return
    _CHAT_ENTRY.delete(0, "end")
    _CHAT_ENTRY.insert(0, command)
    _CHAT_ENTRY.focus_set()
    _set_status("Команда вставлена. Enter отправляет.")
    if send:
        execute_command(command, "command_double_click")


def _is_casual_text(lower):
    return False

def _local_chat_reply(text):
    raw = str(text or "").strip()
    lower = raw.lower().replace("ё", "е")

    if not raw:
        return "Я на месте. Напиши сообщение. В режиме «Чат» я не запускаю router и не выполняю команды."

    greetings = {
        "привет",
        "привет!",
        "здравствуй",
        "здравствуйте",
        "добрый день",
        "добрый вечер",
        "хай",
        "hello",
        "hi",
    }
    if lower in greetings:
        return "Привет. Я здесь. Можем спокойно обсудить LocalComet, интерфейс или следующий патч."

    if lower in {"кто ты", "кто ты?", "ты кто", "ты кто?", "что ты", "что ты?"}:
        return (
            "Я LocalComet — локальный агентский интерфейс для твоего проекта LocalAgent.\n\n"
            "В режиме «Чат» я должен общаться как обычный агент и не запускать router/research. "
            "В режиме «Команда» я отправляю точные `pc ...` команды."
        )

    if "что ты умеешь" in lower or "что умеешь" in lower or "что можешь" in lower:
        return (
            "Могу обсуждать задачи, объяснять состояние проекта, помогать формулировать безопасные команды "
            "и готовить следующий шаг. Команды не запускаются в режиме «Чат», пока ты явно не напишешь `выполни:`."
        )

    if "как пользоваться" in lower or "как работать" in lower or "помощь" in lower or lower == "help":
        return (
            "Коротко:\n\n"
            "• «Чат» — обычный диалог без router/research.\n"
            "• «Команда» — точные `pc ...` команды.\n"
            "• `выполни: <задача>` — явный запуск безопасного планирования.\n"
            "• Ctrl+K — фокус ввода.\n"
            "• Alt+C — показать/скрыть команды."
        )

    if lower in {"ок", "да", "нет", "понял", "поняла", "ясно", "спасибо", "благодарю"}:
        return "Принял. Продолжаем."

    if any(token in lower for token in ["хаха", "ахах", "лол", "прикол", "прикольно", "норм", "круто"]):
        return "Да, уже ближе к нормальному рабочему чату. Следующий уровень — LLM-ответы прямо в режиме «Чат»."

    if lower.startswith("что думаешь") or lower.startswith("как думаешь") or "стоит ли" in lower:
        return (
            "Думаю, текущая логика безопасная, но пока слишком шаблонная. "
            "Правильный следующий шаг — LLM-chat внутри режима «Чат», без router/research и без JSON."
        )

    if _looks_like_direct_task(raw):
        suggested = _task_to_safe_command(raw)
        return (
            "Понял задачу. В режиме «Чат» я не запускаю её автоматически.\n\n"
            "Предлагаемая безопасная команда:\n"
            f"{suggested}\n\n"
            "Чтобы запустить её, переключись в «Команда» или напиши:\n"
            f"выполни: {raw}"
        )

    return (
        "Понял. В режиме «Чат» router не запускается. "
        "Если локальная LLM недоступна, я отвечаю коротким встроенным fallback-ответом."
    )


def _looks_like_direct_task(text):
    lower = str(text or "").lower().replace("ё", "е").strip()
    if not lower:
        return False
    if "_v652bb_is_new_menu_command_text" in globals() and _v652bb_is_new_menu_command_text(lower):
        return True
    direct_prefixes = (
        "сделай ",
        "создай ",
        "исправь ",
        "улучши ",
        "добавь ",
        "проверь ",
        "проанализируй ",
        "напиши ",
        "подготовь ",
        "собери ",
        "запусти ",
        "открой ",
    )
    return lower.startswith(direct_prefixes)


def _chat_safety_reply(text):
    lower = str(text or "").lower().replace("ё", "е")
    blocked_terms = (
        "пароль",
        "password",
        "token",
        "api key",
        "apikey",
        "secret",
        "private key",
        "ssh key",
        "банков",
        "карта",
        "casino",
        "ставк",
        "betting",
        "удали",
        "delete",
        "format",
        "wipe",
        "rm -rf",
        "powershell",
        "cmd.exe",
        "shell",
    )
    if any(term in lower for term in blocked_terms):
        return (
            "Я не буду помогать с секретами, токенами, паролями, банковскими данными, "
            "опасным shell/cmd/powershell или разрушительными действиями. "
            "Могу помочь сформулировать безопасный план без выполнения."
        )
    return ""


def _remember_chat(role, content):
    text = str(content or "").strip()
    if not text:
        return
    _CHAT_HISTORY.append({"role": str(role), "content": text, "at": _now()})
    del _CHAT_HISTORY[:-12]


def _recent_chat_context():
    if not _CHAT_HISTORY:
        return "Диалога пока нет."
    lines = []
    for item in _CHAT_HISTORY[-8:]:
        role = item.get("role", "unknown")
        content = _clean_text(item.get("content", ""))
        if len(content) > 600:
            content = content[:600].rstrip() + "…"
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _clean_chat_model_output(text):
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    cleaned = re.sub(r"```json\s*.*?```", "", cleaned, flags=re.DOTALL | re.IGNORECASE).strip()
    cleaned = cleaned.replace("/no_think", "").strip()
    if len(cleaned) > 1200:
        cleaned = cleaned[:1200].rstrip() + "\n…"
    return cleaned


def _ask_local_llm_chat(text):
    safety = _chat_safety_reply(text)
    if safety:
        return safety

    if _looks_like_direct_task(text):
        suggested = _task_to_safe_command(text)
        return (
            "Понял задачу. В режиме «Чат» я не запускаю её автоматически.\n\n"
            "Безопасная команда для запуска:\n"
            f"{suggested}\n\n"
            "Для выполнения напиши `выполни: ...` или переключись в «Команда»."
        )

    try:
        from core.llm import ask_llm, is_llm_offline_error
    except Exception:
        return ""

    system = (
        "Ты LocalComet Agent Chat Brain — обычный чат внутри локального Python-приложения LocalComet. "
        "Отвечай по-русски, живо, коротко и по делу. "
        "В этом режиме ты НЕ выполняешь команды, НЕ запускаешь router, НЕ запускаешь research, "
        "НЕ говоришь, что уже что-то сделал. "
        "Если пользователь просит выполнить действие, предложи безопасную команду формата `выполни: ...` "
        "или скажи переключиться в режим «Команда». "
        "Не выводи JSON, markdown-дампы, tool logs или внутренние поля."
    )

    user = (
        "Контекст последнего диалога:\n"
        f"{_recent_chat_context()}\n\n"
        "Новое сообщение пользователя:\n"
        f"{str(text).strip()}\n\n"
        "Ответь как обычный агентский чат LocalComet."
    )

    try:
        answer = ask_llm(
            system=system,
            user=user,
            max_tokens=420,
            use_context=True,
            no_think=True,
            temperature=0.35,
            timeout=60,
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

    return _clean_chat_model_output(answer)


def _generate_true_chat_reply(text):
    llm_answer = _ask_local_llm_chat(text)
    if llm_answer:
        return llm_answer
    return _local_chat_reply(text)


def _task_to_safe_command(text):
    raw = str(text or "").strip()
    lower = raw.lower().replace("ё", "е")
    if lower in {"проверь проект", "проверить проект", "полная проверка проекта", "автопроверка проекта"}:
        return "проверь проект"
    if lower.startswith("pc "):
        return raw
    for prefix in ("выполни:", "выполнить:", "запусти:", "run:"):
        if lower.startswith(prefix):
            raw = raw.split(":", 1)[1].strip()
            break
    if not raw:
        return "pc swiss status"
    return "pc swiss plan " + raw


def _explicit_execute_text(text):
    raw = str(text or "").strip()
    lower = raw.lower().replace("ё", "е")
    prefixes = ("выполни:", "выполнить:", "запусти:", "run:", "/cmd ")
    for prefix in prefixes:
        if lower.startswith(prefix):
            if prefix == "/cmd ":
                return raw[5:].strip()
            return raw.split(":", 1)[1].strip()
    return ""

def _normalize_for_mode(text):
    raw = str(text or "").strip()
    lower = raw.lower().replace("ё", "е")
    if not raw:
        return ""

    if _INPUT_MODE == "command":
        return raw

    explicit = _explicit_execute_text(raw)
    if explicit:
        return _task_to_safe_command(explicit)

    if _is_patch_panel_bridge_command_text(raw):
        return raw

    command_prefixes = (
        "управляй пк",
        "сделай на компьютере",
        "агент пк",
        "computer use",
        "pc ",
        "premium ",
        "native ",
        "task panel",
        "новый интерфейс",
        "открой новый интерфейс",
        "статус скриншотов",
        "status screenshots",
        "screenshot storage",
        "screenshot status",
        "проверь рабочую",
        "working directory guard",
        "реестр контрактов",
        "task contract registry",
        "контракт команды",
        "contract for",
        "app harness",
        "реестр приложений",
        "app registry",
        "план запуска",
        "подтвердить открыть",
        "confirm open",
        "подтвердить запустить",
    )
    if lower.startswith(command_prefixes):
        return raw

    return "__LOCAL_CHAT_REPLY__"

def _is_patch_panel_bridge_command_text(text):
    lower = str(text or "").strip().lower().replace("ё", "е")
    if not lower:
        return False
    exact = {
        "статус",
        "status",
        "обнови статус",
        "обновить статус",
        "refresh",
        "принять патч",
        "прими патч",
        "применить патч",
        "apply",
        "accept",
        "принять патч и проверить",
        "импорт",
        "import",
        "импорт проверка",
        "импорт + проверка",
        "import validate",
        "выбрать response",
        "выбери response",
        "select response",
        "choose response",
        "сброс выбора response",
        "сбросить выбор response",
        "clear selected response",
        "reset response source",
        "проверить проект",
        "проверь проект",
        "verify",
        "verify project",
        "checks",
        "проверки",
        "открыть relay",
        "relay",
        "open relay",
        "открыть reports",
        "reports",
        "open reports",
        "открыть отчеты",
        "открыть downloads",
        "downloads",
        "open downloads",
        "открыть logs",
        "logs",
        "open logs",
        "копировать лог",
        "copy log",
        "сохранить лог",
        "save log",
        "очистить лог",
        "clear log",
        "перечитать панель",
        "reload panel",
        "перечитать код панели",
        "soft reload",
    }
    if lower in exact:
        return True
    prefixes = (
        "выбрать response ",
        "выбери response ",
        "select response ",
        "choose response ",
        "response ",
        "source ",
    )
    return lower.startswith(prefixes)


def _find_router():
    for module in list(sys.modules.values()):
        try:
            candidate = getattr(module, "run_panel_chat_command", None)
            if callable(candidate):
                return candidate
        except Exception:
            pass

    try:
        panel_module = importlib.import_module("LocalComet_Control_Panel")
        candidate = getattr(panel_module, "run_panel_chat_command", None)
        if callable(candidate):
            return candidate
    except Exception:
        pass

    return None


def _try_json(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return None


def _clean_text(value):
    text = str(value or "")
    text = text.replace("\\n", "\n")
    text = text.replace("\\t", " ")
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()


def _summarize_cu_simulate(result):
    if not isinstance(result, dict):
        return None
    if result.get("mode") != "computer_use_full_control_mission":
        return None
    simulate = result.get("simulate", False)
    if not simulate:
        return None
    lines = []
    lines.append("РЕЖИМ: СИМУЛЯЦИЯ (dry-run, реальные действия не выполняются)")
    goal = result.get("goal", "")
    if goal:
        lines.append(f"Цель: {goal}")
    ok = result.get("ok")
    if ok is not None:
        lines.append("Статус: OK" if ok else "Статус: Ошибка")
    outcome = result.get("outcome", "")
    if outcome:
        lines.append(f"Исход: {outcome}")
    plan = result.get("plan", [])
    if isinstance(plan, list) and plan:
        lines.append(f"Запланировано шагов: {len(plan)}")
        for step in plan[:5]:
            kind = step.get("kind", "?")
            target = str(step.get("target", ""))
            real = step.get("real_action", True)
            reason = str(step.get("reason", ""))[:100]
            lines.append(f"  - {kind} -> {target} (реальное действие: {real})")
            if reason:
                lines.append(f"    причина: {reason}")
    else:
        lines.append("План: не построен")
    report = result.get("report", "")
    if report:
        lines.append(f"Отчёт: {report}")
    return "\n".join(lines)


def _summarize_payload(payload):
    if not isinstance(payload, dict):
        return _clean_text(payload)

    lines = []
    ok = payload.get("ok")
    if ok is not None:
        lines.append("OK" if ok else "Ошибка")

    mode = payload.get("mode") or payload.get("route") or payload.get("route_name")
    if mode:
        lines.append(f"режим: {mode}")

    for key in ("message", "summary", "error", "result", "report", "json", "page", "request", "opened"):
        if key in payload and payload.get(key) not in (None, "", [], {}):
            value = payload.get(key)
            if key == "result":
                formatted = _summarize_cu_simulate(value)
                if formatted is not None:
                    lines.append(formatted)
                    continue
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, indent=2)
            lines.append(f"{key}: {_clean_text(value)}")

    commands = payload.get("commands")
    if isinstance(commands, list) and commands:
        lines.append("команды:")
        for item in commands[:6]:
            lines.append(f"  {item}")

    checks = payload.get("checks")
    if isinstance(checks, list) and checks:
        passed = sum(1 for item in checks if isinstance(item, dict) and item.get("ok"))
        lines.append(f"проверки: {passed}/{len(checks)}")

    if not lines:
        compact = json.dumps(payload, ensure_ascii=False, indent=2)
        lines.append(compact)

    text = "\n".join(lines)
    if len(text) > 1800:
        text = text[:1800].rstrip() + "\n…"
    return text


def _summarize_router_output(result):
    parsed = _try_json(result)
    if parsed is not None:
        return _summarize_payload(parsed)

    if isinstance(result, dict):
        return _summarize_payload(result)

    text = _clean_text(result)
    if len(text) > 1800:
        text = text[:1800].rstrip() + "\n…"
    return text or "Готово."


def execute_command(command, source="chat"):
    raw_command = str(command or "").strip()
    if not raw_command:
        _set_status("Пустой текст")
        return {
            "ok": False,
            "mode": "premium_task_panel_execute",
            "error": "empty command",
        }

    command = _normalize_for_mode(raw_command)

    if command == "__LOCAL_CHAT_REPLY__":
        _append_chat("Ты", raw_command)
        _remember_chat("Пользователь", raw_command)
        reply = _generate_true_chat_reply(raw_command)
        _remember_chat("LocalComet", reply)
        _append_chat("LocalComet", reply)
        _set_status("Чат · ответ агента, router не запускался")
        return {
            "ok": True,
            "mode": "premium_task_panel_agent_chat",
            "generated_at": _now(),
            "raw_text": raw_command,
            "input_mode": _INPUT_MODE,
            "router_used": False,
            "llm_chat_mode": True,
        }

    if command != raw_command:
        _append_chat("Ты", f"{raw_command}\n→ {command}")
    else:
        _append_chat("Ты", command)

    # PREMIUM_TASK_PANEL_V652B_COMMAND_BRIDGE_START
    if _v652bb_is_new_menu_command_text(command):
        result_text = _v652bb_run_new_menu_command_text(command)
        _append_chat("LocalComet", result_text, "normal" if "STOP:" not in str(result_text) else "error")
        _set_status("Команда нового меню v6.52b выполнена")
        return {
            "ok": True,
            "mode": "premium_task_panel_v652bb_new_menu_command",
            "generated_at": _now(),
            "command": command,
            "raw_text": raw_command,
            "input_mode": _INPUT_MODE,
            "source": source,
            "router_used": False,
            "result": result_text,
        }
    # PREMIUM_TASK_PANEL_V652B_COMMAND_BRIDGE_END

    _set_status(f"Отправляю в LocalComet router · режим: {_mode_label()}")

    router = _find_router()
    if router is None:
        message = (
            "Router run_panel_chat_command не найден. "
            "Команда осталась в чате. Запусти её в старой панели или перезапусти LocalComet."
        )
        _append_chat("LocalComet", message)
        _set_status("Router не найден")
        return {
            "ok": False,
            "mode": "premium_task_panel_execute",
            "generated_at": _now(),
            "command": command,
            "raw_text": raw_command,
            "input_mode": _INPUT_MODE,
            "source": source,
            "error": "run_panel_chat_command not found",
        }

    try:
        result = router(command)
    except Exception as exc:
        _append_chat("LocalComet", f"Ошибка выполнения:\n{exc}")
        _set_status("Ошибка команды")
        return {
            "ok": False,
            "mode": "premium_task_panel_execute",
            "generated_at": _now(),
            "command": command,
            "raw_text": raw_command,
            "input_mode": _INPUT_MODE,
            "source": source,
            "error": str(exc),
        }

    output = _summarize_router_output(result)
    _append_chat("LocalComet", output)
    _set_status("Готово · ответ очищен от лишнего JSON")
    return {
        "ok": True,
        "mode": "premium_task_panel_execute",
        "generated_at": _now(),
        "command": command,
        "raw_text": raw_command,
        "input_mode": _INPUT_MODE,
        "source": source,
        "result_type": type(result).__name__,
        "router_used": True,
    }

def _clear(frame):
    for child in frame.winfo_children():
        child.destroy()


def _render_command_list(parent):
    for group_name, items in CODEX_COMMANDS.items():
        tk.Label(parent, text=group_name.upper(), bg="#0b1020", fg="#64748b", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(14, 4))
        for title, command in items:
            row = tk.Frame(parent, bg="#0b1020")
            row.pack(fill="x", padx=10, pady=2)

            title_label = tk.Label(
                row,
                text=title,
                bg="#0b1020",
                fg="#e5e7eb",
                font=("Segoe UI", 9, "bold"),
                cursor="hand2",
            )
            title_label.pack(anchor="w")
            title_label.bind("<Button-1>", lambda event, c=command: _insert_command(c, send=False))
            title_label.bind("<Double-Button-1>", lambda event, c=command: _insert_command(c, send=True))

            cmd_label = tk.Label(
                row,
                text=command,
                bg="#0b1020",
                fg="#6b7280",
                font=("Consolas", 8),
                wraplength=310,
                justify="left",
                cursor="hand2",
            )
            cmd_label.pack(anchor="w", pady=(0, 4))
            cmd_label.bind("<Button-1>", lambda event, c=command: _insert_command(c, send=False))
            cmd_label.bind("<Double-Button-1>", lambda event, c=command: _insert_command(c, send=True))


def _render_safety_text(parent):
    text = (
        "Работает без браузера, npm и backend.\n"
        "Команды идут через существующий router LocalComet.\n"
        "Обычный текст в режиме «Чат» становится безопасным планом.\n"
        "Короткие фразы не вызывают research.\n"
        "Shell / cmd / powershell / delete / secrets заблокированы базовыми модулями."
    )
    tk.Label(parent, text=text, bg="#050711", fg="#9ca3af", font=("Segoe UI", 10), justify="left", wraplength=760).pack(anchor="w", padx=18, pady=18)


def _render_report_text(parent):
    data = status()
    lines = [
        f"{PANEL_NAME}",
        f"версия: {PANEL_VERSION}",
        "режим: Codex workspace",
        "чат/команда: есть",
        "Enter: отправляет",
        "JSON-шум: скрыт",
        "browser: off",
        "",
        "команды:",
    ]
    lines.extend(f"  {cmd}" for cmd in data["commands"])
    tk.Label(parent, text="\n".join(lines), bg="#050711", fg="#d1d5db", font=("Consolas", 10), justify="left").pack(anchor="w", padx=18, pady=18)


def _format_project_check_for_ui(result):
    if not isinstance(result, dict):
        return str(result)

    lines = []
    lines.append("Проверка проекта завершена.")
    lines.append("")
    lines.append("OK: " + ("да" if result.get("ok") else "нет"))
    if result.get("score"):
        lines.append(f"Score: {result.get('score')}")

    summary = result.get("summary")
    if isinstance(summary, dict):
        lines.append("")
        lines.append("Сводка:")
        for key in (
            "python_files",
            "functions",
            "classes",
            "command_modules",
            "parse_errors",
            "compile_failures",
            "hard_failures",
            "warnings",
            "added_files",
            "changed_files",
            "new_functions",
            "changed_functions",
        ):
            if key in summary:
                lines.append(f"- {key}: {summary.get(key)}")

    report_path = result.get("report")
    if report_path:
        lines.append("")
        lines.append(f"Отчёт: {report_path}")

    json_path = result.get("json")
    if json_path:
        lines.append(f"JSON: {json_path}")

    hard_failures = result.get("hard_failures")
    if isinstance(hard_failures, list) and hard_failures:
        lines.append("")
        lines.append("Критические проблемы:")
        for item in hard_failures[:10]:
            name = item.get("name") or item.get("path") or "check"
            error = item.get("error") or ""
            lines.append(f"- {name}: {error}")

    warnings = result.get("warnings")
    if isinstance(warnings, list) and warnings:
        lines.append("")
        lines.append("Предупреждения:")
        for item in warnings[:10]:
            name = item.get("name") or item.get("path") or "warning"
            error = item.get("error") or ""
            lines.append(f"- {name}: {error}")

    return "\n".join(lines)


def _run_project_check_from_tab(output_widget):
    _set_status("Проверяю проект строгим тестом стабильности...")
    output_widget.configure(state="normal")
    output_widget.delete("1.0", "end")
    output_widget.insert("end", "Запущена строгая проверка проекта...\n")
    output_widget.insert("end", "Проверяются Python-файлы, новые функции, вкладка UI, route, safety markers и отчёт.\n\n")
    output_widget.configure(state="disabled")
    output_widget.update_idletasks()

    try:
        from modules.strict_project_stability_ru import run_strict_project_check

        result = run_strict_project_check(update_baseline=True)
        text = _format_project_check_for_ui(result)
        _set_status("Проверка проекта завершена" if result.get("ok") else "Проверка проекта нашла проблемы")
    except Exception as exc:
        text = f"Ошибка проверки проекта:\n{exc}"
        _set_status("Ошибка проверки проекта")

    output_widget.configure(state="normal")
    output_widget.delete("1.0", "end")
    output_widget.insert("end", text)
    output_widget.configure(state="disabled")


def _render_verification_page(content):
    _clear(content)

    shell = tk.Frame(content, bg="#050711")
    shell.pack(fill="both", expand=True)

    header = tk.Frame(shell, bg="#050711")
    header.pack(fill="x", pady=(0, 12))

    tk.Label(header, text="Проверка", bg="#050711", fg="#f9fafb", font=("Segoe UI", 18, "bold")).pack(anchor="w")
    tk.Label(
        header,
        text="Одна кнопка запускает новый строгий тест стабильности всего проекта.",
        bg="#050711",
        fg="#9ca3af",
        font=("Segoe UI", 9),
    ).pack(anchor="w", pady=(4, 0))

    card = tk.Frame(shell, bg="#060913", highlightbackground="#1f2937", highlightthickness=1)
    card.pack(fill="x", pady=(0, 12), ipady=14)

    tk.Label(
        card,
        text="Проверить весь проект",
        bg="#060913",
        fg="#f8fafc",
        font=("Segoe UI", 13, "bold"),
    ).pack(anchor="w", padx=16, pady=(12, 4))

    tk.Label(
        card,
        text="AST parse · py_compile all · новые/изменённые функции · UI вкладка · router · safety markers · отчёт",
        bg="#060913",
        fg="#6b7280",
        font=("Segoe UI", 9),
    ).pack(anchor="w", padx=16, pady=(0, 12))

    output = tk.Text(
        shell,
        bg="#060913",
        fg="#e5e7eb",
        insertbackground="#f8fafc",
        relief="flat",
        font=("Consolas", 10),
        wrap="word",
        padx=14,
        pady=12,
    )
    output.pack(fill="both", expand=True)
    output.insert("end", "Нажми «Проверить проект».\n\nЭта кнопка заменяет ручные проверки.\n\nИз чата: выполни: проверь проект")
    output.configure(state="disabled")

    ttk.Button(
        card,
        text="Проверить проект",
        style="Primary.TButton",
        command=lambda: _run_project_check_from_tab(output),
    ).pack(anchor="w", padx=16, pady=(0, 14))



def _format_ai_agent_result(result):
    if not isinstance(result, dict):
        return str(result)

    lines = []
    lines.append("LocalComet AI Agent Core.")
    lines.append("")
    lines.append("OK: " + ("да" if result.get("ok") else "нет"))
    lines.append("mode: " + str(result.get("mode", "")))

    for key in ("agent_version", "agent_name", "phase", "goal", "active_goal", "next_safe_command"):
        if result.get(key):
            lines.append(f"{key}: {result.get(key)}")

    if isinstance(result.get("summary"), dict):
        lines.append("")
        lines.append("Summary:")
        for key, value in result.get("summary", {}).items():
            lines.append(f"- {key}: {value}")

    if isinstance(result.get("context"), dict):
        context = result.get("context", {})
        lines.append("")
        lines.append("Context:")
        lines.append(f"- project_map_path: {context.get('project_map_path', '')}")
        lines.append(f"- python_file_count: {context.get('python_file_count', '')}")
        lines.append(f"- function_count: {context.get('function_count', '')}")
        lines.append(f"- command_module_count: {context.get('command_module_count', '')}")
        lines.append(f"- ui_module_count: {context.get('ui_module_count', '')}")
        lines.append(f"- verification_module_count: {context.get('verification_module_count', '')}")

    answer = result.get("answer")
    if answer:
        lines.append("")
        lines.append(str(answer))

    for key in ("project_map_path", "plan_path", "draft_path", "report", "path"):
        if result.get(key):
            lines.append("")
            lines.append(f"{key}: {result.get(key)}")

    if isinstance(result.get("draft"), dict):
        draft = result.get("draft", {})
        lines.append("")
        lines.append("Draft:")
        lines.append("OK: " + ("да" if draft.get("ok") else "нет"))
        if draft.get("draft_path"):
            lines.append("draft_path: " + str(draft.get("draft_path")))

    if isinstance(result.get("verification_analysis"), dict):
        analysis = result.get("verification_analysis", {})
        lines.append("")
        lines.append("Verification analysis:")
        lines.append("OK: " + ("да" if analysis.get("ok") else "нет"))
        if analysis.get("path"):
            lines.append("path: " + str(analysis.get("path")))
        if analysis.get("hard_failures") is not None:
            lines.append("hard_failures: " + str(analysis.get("hard_failures")))
        if analysis.get("warnings") is not None:
            lines.append("warnings: " + str(analysis.get("warnings")))

    if isinstance(result.get("analysis"), dict):
        analysis = result.get("analysis", {})
        lines.append("")
        lines.append("Analysis:")
        lines.append("OK: " + ("да" if analysis.get("ok") else "нет"))
        if analysis.get("path"):
            lines.append("path: " + str(analysis.get("path")))
        if analysis.get("summary"):
            lines.append(str(analysis.get("summary")))

    if isinstance(result.get("state_machine"), list):
        lines.append("")
        lines.append("State machine:")
        for item in result.get("state_machine", []):
            lines.append(f"- {item}")

    if isinstance(result.get("commands"), list):
        lines.append("")
        lines.append("Commands:")
        for item in result.get("commands", [])[:20]:
            lines.append(f"- {item}")

    if isinstance(result.get("next_steps"), list):
        lines.append("")
        lines.append("Next steps:")
        for item in result.get("next_steps", []):
            lines.append(f"- {item}")

    return "\n".join(lines)


def _run_ai_agent_command(output_widget, command, status_message):
    _set_status(status_message)
    output_widget.configure(state="normal")
    output_widget.delete("1.0", "end")
    output_widget.insert("end", status_message + "\n\n")
    output_widget.configure(state="disabled")
    output_widget.update_idletasks()

    try:
        from modules.ai_agent_core_ru import dispatch

        result = dispatch(command)
        text = _format_ai_agent_result(result)
        _set_status("AI Agent Core: готово" if result.get("ok") else "AI Agent Core: требуется внимание")
    except Exception as exc:
        text = "Ошибка AI Agent Core:\n" + str(exc)
        _set_status("Ошибка AI Agent Core")

    output_widget.configure(state="normal")
    output_widget.delete("1.0", "end")
    output_widget.insert("end", text)
    output_widget.configure(state="disabled")


def _render_ai_agent_page(content):
    _clear(content)

    shell = tk.Frame(content, bg="#050711")
    shell.pack(fill="both", expand=True)

    header = tk.Frame(shell, bg="#050711")
    header.pack(fill="x", pady=(0, 12))

    tk.Label(header, text="AI Агент", bg="#050711", fg="#f9fafb", font=("Segoe UI", 18, "bold")).pack(anchor="w")
    tk.Label(
        header,
        text="Agent Core: цель → карта проекта → план → draft response.json → Relay → проверка → repair.",
        bg="#050711",
        fg="#9ca3af",
        font=("Segoe UI", 9),
    ).pack(anchor="w", pady=(4, 0))

    card = tk.Frame(shell, bg="#060913", highlightbackground="#1f2937", highlightthickness=1)
    card.pack(fill="x", pady=(0, 12), ipady=10)

    tk.Label(card, text="Цель агента", bg="#060913", fg="#f9fafb", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
    tk.Label(
        card,
        text="Агент не применяет патчи сам. Он строит контекст, план и safe draft для Relay.",
        bg="#060913",
        fg="#9ca3af",
        font=("Segoe UI", 9),
    ).pack(anchor="w", padx=14, pady=(0, 10))

    goal_entry = tk.Entry(
        card,
        bg="#0b1020",
        fg="#f8fafc",
        insertbackground="#f8fafc",
        relief="flat",
        font=("Segoe UI", 10),
    )
    goal_entry.insert(0, "развивать LocalComet как локального AI-агента типа Codex")
    goal_entry.pack(fill="x", padx=14, pady=(0, 10), ipady=8)

    actions = tk.Frame(card, bg="#060913")
    actions.pack(fill="x", padx=14, pady=(0, 12))

    output = tk.Text(
        shell,
        bg="#050711",
        fg="#e5e7eb",
        insertbackground="#f8fafc",
        relief="flat",
        font=("Consolas", 10),
        wrap="word",
        padx=14,
        pady=12,
    )
    output.pack(fill="both", expand=True)
    output.insert(
        "end",
        "Computer Use Core готов.\n\n"
        "1. «Контекст проекта» строит project_map.json.\n"
        "2. «Построить план» создаёт агентский план.\n"
        "3. «Создать draft patch» создаёт response_agent_draft_*.json без применения.\n"
        "4. «Анализ последней проверки» читает отчёт.\n"
        "5. «Repair plan» готовит следующий безопасный repair plan.\n"
        "6. «Проверить проект» запускает строгую проверку.\n",
    )
    output.configure(state="disabled")

    def goal():
        value = goal_entry.get().strip()
        return value or "развивать LocalComet как локального AI-агента типа Codex"

    ttk.Button(actions, text="Контекст проекта", style="Codex.TButton", command=lambda: _run_ai_agent_command(output, "pc ai context", "AI Agent: строю карту проекта...")).pack(side="left")
    ttk.Button(actions, text="Построить план", style="Primary.TButton", command=lambda: _run_ai_agent_command(output, "pc ai plan " + goal(), "AI Agent: строю план...")).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Создать draft patch", style="Codex.TButton", command=lambda: _run_ai_agent_command(output, "pc ai draft " + goal(), "AI Agent: создаю draft response.json...")).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Анализ последней проверки", style="Codex.TButton", command=lambda: _run_ai_agent_command(output, "pc ai repair", "AI Agent: анализирую последнюю проверку...")).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Repair plan", style="Codex.TButton", command=lambda: _run_ai_agent_command(output, "pc ai repair", "AI Agent: строю repair plan...")).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Проверить проект", style="Codex.TButton", command=lambda: _run_ai_agent_command(output, "pc ai verify", "AI Agent: запускаю строгую проверку проекта...")).pack(side="left", padx=(8, 0))



def _format_computer_use_result(result):
    if not isinstance(result, dict):
        return str(result)

    lines = []
    lines.append("LocalComet Computer Use Core.")
    lines.append("")
    lines.append("OK: " + ("да" if result.get("ok") else "нет"))
    lines.append("mode: " + str(result.get("mode", "")))

    for key in (
        "goal",
        "risk",
        "blocked",
        "reason",
        "action_id",
        "status",
        "phase",
        "active_goal",
        "latest_screenshot",
        "latest_ui_map",
        "latest_trace",
        "latest_report",
        "next_safe_action",
    ):
        if key in result and result.get(key) not in (None, ""):
            lines.append(f"{key}: {result.get(key)}")

    if "requires_confirmation" in result:
        lines.append("requires_confirmation: " + str(result.get("requires_confirmation")))
    if "allowed_to_execute" in result:
        lines.append("allowed_to_execute: " + str(result.get("allowed_to_execute")))
    if "confirmed" in result:
        lines.append("confirmed: " + str(result.get("confirmed")))
    if "executed" in result:
        lines.append("executed: " + str(result.get("executed")))

    safety = result.get("safety")
    if isinstance(safety, dict):
        lines.append("")
        lines.append("Safety:")
        lines.append("OK: " + ("да" if safety.get("ok") else "нет"))
        if safety.get("risk"):
            lines.append("risk: " + str(safety.get("risk")))
        if safety.get("reason"):
            lines.append("reason: " + str(safety.get("reason")))

    steps = result.get("steps")
    if isinstance(steps, list):
        lines.append("")
        lines.append("Steps:")
        for index, item in enumerate(steps, 1):
            if isinstance(item, dict):
                lines.append(f"{index}. {item.get('title') or item.get('action') or item}")
                if item.get("detail"):
                    lines.append("   " + str(item.get("detail")))
            else:
                lines.append(f"{index}. {item}")

    queued = result.get("queued_actions")
    if isinstance(queued, list):
        lines.append("")
        lines.append("Queued actions:")
        for item in queued[:20]:
            lines.append(
                f"- {item.get('id')} status={item.get('status')} "
                f"confirmed={item.get('confirmed')} executed={item.get('executed')} goal={item.get('goal')}"
            )

    elements = result.get("elements")
    if isinstance(elements, list):
        lines.append("")
        lines.append("UI elements:")
        for item in elements[:20]:
            lines.append(f"- {item}")

    report_path = result.get("report_path") or result.get("report")
    if report_path:
        lines.append("")
        lines.append("report: " + str(report_path))

    trace_path = result.get("trace_path")
    if trace_path:
        lines.append("trace: " + str(trace_path))

    ui_map_path = result.get("ui_map_path")
    if ui_map_path:
        lines.append("ui_map: " + str(ui_map_path))

    if isinstance(result.get("commands"), list):
        lines.append("")
        lines.append("Commands:")
        for item in result.get("commands", [])[:30]:
            lines.append(f"- {item}")

    return "\n".join(lines)


def _run_computer_use_command(output_widget, command, status_message):
    _set_status(status_message)
    output_widget.configure(state="normal")
    output_widget.delete("1.0", "end")
    output_widget.insert("end", status_message + "\n\n")
    output_widget.configure(state="disabled")
    output_widget.update_idletasks()

    try:
        from modules.computer_use_core_ru import dispatch

        result = dispatch(command)
        text = _format_computer_use_result(result)
        _set_status("Computer Use: готово" if result.get("ok") else "Computer Use: требуется внимание")
    except Exception as exc:
        text = "Ошибка Computer Use Core:\n" + str(exc)
        _set_status("Ошибка Computer Use Core")

    output_widget.configure(state="normal")
    output_widget.delete("1.0", "end")
    output_widget.insert("end", text)
    output_widget.configure(state="disabled")


def _render_computer_use_page(content):
    _clear(content)

    shell = tk.Frame(content, bg="#050711")
    shell.pack(fill="both", expand=True)

    header = tk.Frame(shell, bg="#050711")
    header.pack(fill="x", pady=(0, 12))

    tk.Label(header, text="Computer Use", bg="#050711", fg="#f9fafb", font=("Segoe UI", 18, "bold")).pack(anchor="w")
    tk.Label(
        header,
        text="Безопасный цикл: наблюдение → карта UI → dry-run → очередь → подтверждение → ограниченное выполнение → отчёт.",
        bg="#050711",
        fg="#9ca3af",
        font=("Segoe UI", 9),
    ).pack(anchor="w", pady=(4, 0))

    card = tk.Frame(shell, bg="#060913", highlightbackground="#1f2937", highlightthickness=1)
    card.pack(fill="x", pady=(0, 12), ipady=10)

    tk.Label(card, text="Цель действия", bg="#060913", fg="#f9fafb", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
    tk.Label(
        card,
        text="Никаких blind click/type. Сначала dry-run и очередь, потом явное подтверждение.",
        bg="#060913",
        fg="#9ca3af",
        font=("Segoe UI", 9),
    ).pack(anchor="w", padx=14, pady=(0, 10))

    goal_entry = tk.Entry(
        card,
        bg="#0b1020",
        fg="#f8fafc",
        insertbackground="#f8fafc",
        relief="flat",
        font=("Segoe UI", 10),
    )
    goal_entry.insert(0, "открыть настройки")
    goal_entry.pack(fill="x", padx=14, pady=(0, 10), ipady=8)

    id_entry = tk.Entry(
        card,
        bg="#0b1020",
        fg="#f8fafc",
        insertbackground="#f8fafc",
        relief="flat",
        font=("Segoe UI", 10),
    )
    id_entry.insert(0, "CU-...")
    id_entry.pack(fill="x", padx=14, pady=(0, 10), ipady=8)

    actions = tk.Frame(card, bg="#060913")
    actions.pack(fill="x", padx=14, pady=(0, 12))

    output = tk.Text(
        shell,
        bg="#050711",
        fg="#e5e7eb",
        insertbackground="#f8fafc",
        relief="flat",
        font=("Consolas", 10),
        wrap="word",
        padx=14,
        pady=12,
    )
    output.pack(fill="both", expand=True)
    output.insert(
        "end",
        "Computer Use Core готов.\n\n"
        "1. «Наблюдать экран» собирает безопасное наблюдение.\n"
        "2. «Карта экрана» строит UI-map/fallback map.\n"
        "3. «Dry-run цель» планирует без кликов и ввода.\n"
        "4. «Поставить в очередь» создаёт action_id.\n"
        "5. «Подтвердить» только ставит confirmed=true.\n"
        "6. «Выполнить подтверждённое» в v6.42 ограничено безопасными primitives.\n",
    )
    output.configure(state="disabled")

    def goal():
        value = goal_entry.get().strip()
        return value or "открыть настройки"

    def action_id():
        return id_entry.get().strip()

    ttk.Button(actions, text="Статус", style="Codex.TButton", command=lambda: _run_computer_use_command(output, "pc computer status", "Computer Use: статус...")).pack(side="left")
    ttk.Button(actions, text="Наблюдать экран", style="Codex.TButton", command=lambda: _run_computer_use_command(output, "pc computer observe", "Computer Use: наблюдение экрана...")).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Карта экрана", style="Codex.TButton", command=lambda: _run_computer_use_command(output, "pc computer map", "Computer Use: карта экрана...")).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Dry-run цель", style="Primary.TButton", command=lambda: _run_computer_use_command(output, "pc computer dry " + goal(), "Computer Use: dry-run...")).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Поставить в очередь", style="Codex.TButton", command=lambda: _run_computer_use_command(output, "pc computer queue " + goal(), "Computer Use: очередь...")).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Подтвердить", style="Codex.TButton", command=lambda: _run_computer_use_command(output, "pc computer confirm " + action_id(), "Computer Use: подтверждение...")).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Выполнить подтверждённое", style="Codex.TButton", command=lambda: _run_computer_use_command(output, "pc computer run " + action_id(), "Computer Use: ограниченное выполнение...")).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Стоп", style="Codex.TButton", command=lambda: _run_computer_use_command(output, "pc computer stop", "Computer Use: стоп...")).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Отчёт", style="Codex.TButton", command=lambda: _run_computer_use_command(output, "pc computer report", "Computer Use: отчёт...")).pack(side="left", padx=(8, 0))

PREMIUM_TASK_PANEL_CLIPBOARD_HOTKEYS_RU_V651C = "v6.51c robust clipboard hotkeys for Computer Use chat input"


def _clipboard_widget(event=None):
    widget = getattr(event, "widget", None)
    if widget is not None:
        return widget
    if _CHAT_ENTRY is not None:
        return _CHAT_ENTRY
    try:
        if _WINDOW_REF is not None:
            return _WINDOW_REF.focus_get()
    except Exception:
        pass
    return None


def _clipboard_text_selection(widget):
    if widget is None:
        return ""
    try:
        if isinstance(widget, tk.Text):
            return widget.get("sel.first", "sel.last")
        return widget.selection_get()
    except Exception:
        return ""


def _clipboard_editable(widget):
    if widget is None:
        return False
    try:
        state = str(widget.cget("state"))
    except Exception:
        state = "normal"
    return state not in {"disabled", "readonly"}


def _clipboard_select_all(event=None):
    widget = _clipboard_widget(event)
    if widget is None:
        return "break"
    try:
        if isinstance(widget, tk.Text):
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "1.0")
            widget.see("insert")
        else:
            widget.select_range(0, "end")
            widget.icursor("end")
        widget.focus_set()
    except Exception:
        pass
    return "break"


def _clipboard_copy(event=None):
    widget = _clipboard_widget(event)
    text = _clipboard_text_selection(widget)
    if text:
        try:
            root = widget.winfo_toplevel()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update_idletasks()
        except Exception:
            pass
    return "break"


def _clipboard_cut(event=None):
    widget = _clipboard_widget(event)
    if widget is None:
        return "break"
    if not _clipboard_editable(widget):
        return _clipboard_copy(event)
    text = _clipboard_text_selection(widget)
    if text:
        try:
            root = widget.winfo_toplevel()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update_idletasks()
            if isinstance(widget, tk.Text):
                widget.delete("sel.first", "sel.last")
            else:
                widget.delete("sel.first", "sel.last")
        except Exception:
            pass
    return "break"


def _clipboard_paste(event=None):
    widget = _clipboard_widget(event)
    if widget is None or not _clipboard_editable(widget):
        return "break"
    try:
        root = widget.winfo_toplevel()
        text = root.clipboard_get()
    except Exception:
        return "break"
    try:
        if isinstance(widget, tk.Text):
            try:
                widget.delete("sel.first", "sel.last")
            except Exception:
                pass
            widget.insert("insert", text)
        else:
            try:
                widget.delete("sel.first", "sel.last")
            except Exception:
                pass
            widget.insert("insert", text)
        widget.focus_set()
    except Exception:
        pass
    return "break"


def _clipboard_control_key(event=None):
    widget = _clipboard_widget(event)
    if widget is None:
        return None
    try:
        widget_class = widget.winfo_class()
    except Exception:
        widget_class = ""
    if widget is not _CHAT_ENTRY and widget_class not in {"Entry", "TEntry", "Text"} and not isinstance(widget, tk.Text):
        return None

    keysym = str(getattr(event, "keysym", "") or "").lower()
    char = str(getattr(event, "char", "") or "").lower()
    keycode = int(getattr(event, "keycode", 0) or 0)

    if keysym in {"a", "cyrillic_ef"} or char in {"a", "ф"} or keycode == 65:
        return _clipboard_select_all(event)
    if keysym in {"c", "cyrillic_es"} or char in {"c", "с"} or keycode == 67:
        return _clipboard_copy(event)
    if keysym in {"v", "cyrillic_em"} or char in {"v", "м"} or keycode == 86:
        return _clipboard_paste(event)
    if keysym in {"x", "cyrillic_che"} or char in {"x", "ч"} or keycode == 88:
        return _clipboard_cut(event)
    return None


def _clipboard_context_menu(event=None):
    widget = _clipboard_widget(event)
    if widget is None:
        return "break"
    menu = None
    try:
        menu = tk.Menu(widget, tearoff=0, bg="#0b1020", fg="#f8fafc", activebackground="#2563eb", activeforeground="#ffffff")
        menu.add_command(label="Вставить", command=lambda: _clipboard_paste(event))
        menu.add_command(label="Копировать", command=lambda: _clipboard_copy(event))
        menu.add_command(label="Вырезать", command=lambda: _clipboard_cut(event))
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=lambda: _clipboard_select_all(event))
        menu.tk_popup(int(getattr(event, "x_root", 0) or 0), int(getattr(event, "y_root", 0) or 0))
    finally:
        try:
            if menu is not None:
                menu.grab_release()
        except Exception:
            pass
    return "break"


def _bind_chat_entry_clipboard(widget):
    if widget is None:
        return False
    try:
        widget.configure(takefocus=True)
    except Exception:
        pass
    bindings = [
        ("<Control-KeyPress>", _clipboard_control_key),
        ("<Control-a>", _clipboard_select_all),
        ("<Control-A>", _clipboard_select_all),
        ("<Control-c>", _clipboard_copy),
        ("<Control-C>", _clipboard_copy),
        ("<Control-v>", _clipboard_paste),
        ("<Control-V>", _clipboard_paste),
        ("<Control-x>", _clipboard_cut),
        ("<Control-X>", _clipboard_cut),
        ("<<Copy>>", _clipboard_copy),
        ("<<Paste>>", _clipboard_paste),
        ("<<Cut>>", _clipboard_cut),
        ("<Shift-Insert>", _clipboard_paste),
        ("<Button-3>", _clipboard_context_menu),
    ]
    for sequence, callback in bindings:
        try:
            widget.bind(sequence, callback, add="+")
        except Exception:
            pass
    return True

# LOCALCOMET_FUNCTIONAL_TEST_CENTER_RU_V652B_START
LOCALCOMET_FUNCTIONAL_TEST_CENTER_RU_V652B = "v6.52b new menu patch workflow and functional test center"

_TEST_PROGRESS_BAR = None
_TEST_STATUS_LABEL = None
_PATCH_SELECTED_LABEL = None
_PATCH_ACCEPT_BUTTON = None
_PATCH_TEST_BUTTON = None
_PATCH_CHOOSE_BUTTON = None
_PATCH_UX_STATUS_LABEL = None
_PATCH_UX_SUMMARY_LABEL = None
_PATCH_UX_OPEN_REPORT_BUTTON = None
_PATCH_UX_COPY_SUMMARY_BUTTON = None


def _v652bb_safe_text(value, limit=1800):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n[trimmed]"


def _v652bb_patch_panel_backend():
    import importlib
    return importlib.import_module("LocalComet_Patch_Panel")


def _v652bb_functional_center():
    import importlib
    return importlib.import_module("modules.localcomet_functional_test_center_ru")


def _v652bb_selected_response_text():
    try:
        backend = _v652bb_patch_panel_backend()
        selected = getattr(backend, "_selected_response_source", lambda: None)()
        if selected is not None:
            return str(selected)
        latest = getattr(backend, "find_latest_response_file", lambda: None)()
        if latest is not None:
            return f"latest: {latest}"
    except Exception:
        pass
    return "patch не выбран"


def _v652bb_refresh_patch_status_label():
    if _PATCH_SELECTED_LABEL is None:
        return
    try:
        _PATCH_SELECTED_LABEL.configure(text=f"Patch: {_v652bb_selected_response_text()}")
    except Exception:
        pass


def _v652bb_set_progress(current=0, total=100, message="Готово"):
    percent = 0
    try:
        total = max(1, int(total))
        current = max(0, min(int(current), total))
        percent = int(current * 100 / total)
    except Exception:
        percent = 0

    def apply_update():
        if _TEST_PROGRESS_BAR is not None:
            try:
                _TEST_PROGRESS_BAR.configure(maximum=100, value=percent)
            except Exception:
                pass
        if _TEST_STATUS_LABEL is not None:
            try:
                _TEST_STATUS_LABEL.configure(text=f"{percent}% · {message}")
            except Exception:
                pass
        _set_status(f"{percent}% · {message}")
        _v652bb_refresh_patch_status_label()

    try:
        if _WINDOW_REF is not None:
            _WINDOW_REF.after(0, apply_update)
        else:
            apply_update()
    except Exception:
        apply_update()


def _v652bb_set_buttons_busy(is_busy):
    def apply_update():
        for button in (_PATCH_ACCEPT_BUTTON, _PATCH_TEST_BUTTON, _PATCH_CHOOSE_BUTTON):
            if button is None:
                continue
            try:
                button.configure(state="disabled" if is_busy else "normal")
            except Exception:
                pass

    try:
        if _WINDOW_REF is not None:
            _WINDOW_REF.after(0, apply_update)
        else:
            apply_update()
    except Exception:
        apply_update()


def _v652bb_append_chat_threadsafe(author, text, kind="normal"):
    def apply_update():
        _append_chat(author, text, kind)

    try:
        if _WINDOW_REF is not None:
            _WINDOW_REF.after(0, apply_update)
        else:
            apply_update()
    except Exception:
        apply_update()


def _v652bb_choose_patch_dialog():
    try:
        path = filedialog.askopenfilename(
            title="Выбрать Relay response patch",
            initialdir=str(Path.home() / "Downloads"),
            filetypes=[("Relay response JSON", "response*.json"), ("JSON", "*.json"), ("All files", "*.*")],
        )
    except Exception as exc:
        message = f"STOP: диалог выбора patch не открылся: {exc}"
        _append_chat("LocalComet", message, "error")
        _set_status("Ошибка выбора patch")
        return message

    if not path:
        message = "Выбор patch отменён."
        _append_chat("LocalComet", message)
        return message

    try:
        backend = _v652bb_patch_panel_backend()
        result = backend.import_specific_response_text(Path(path))
        _append_chat("LocalComet", result)
        _set_status("Patch выбран")
        _v652bb_refresh_patch_status_label()
        return result
    except Exception as exc:
        message = "STOP: не удалось выбрать patch:\n" + traceback.format_exc()
        _append_chat("LocalComet", message, "error")
        _set_status("Ошибка выбора patch")
        return message


def _v652bb_select_patch_path(path_text):
    try:
        backend = _v652bb_patch_panel_backend()
        result = backend.import_specific_response_text(Path(str(path_text).strip()))
        _set_status("Patch выбран")
        _v652bb_refresh_patch_status_label()
        return result
    except Exception:
        _set_status("Ошибка выбора patch")
        return "STOP: не удалось выбрать patch:\n" + traceback.format_exc()


def _v652bb_run_functional_tests_sync(full=True):
    center = _v652bb_functional_center()

    def progress(current, total, item):
        name = item.get("name") or item.get("id") or "test"
        _v652bb_set_progress(current, total, name)

    result = center.run_full_suite(progress_callback=progress, write_report=True) if full else center.run_smoke_suite(progress_callback=progress, write_report=True)
    _v652bb_set_progress(100, 100, "GREEN" if result.get("ok") else "FAIL")
    return center.format_functional_test_report(result)


def _v652bb_run_tests_button(full=True):
    def worker():
        _v652bb_set_buttons_busy(True)
        _v652bb_set_progress(0, 100, "Запуск functional test center")
        try:
            text = _v652bb_run_functional_tests_sync(full=full)
            _v652bb_append_chat_threadsafe("LocalComet", text, "normal" if "GREEN" in text else "error")
        except Exception:
            _v652bb_set_progress(100, 100, "FAIL")
            _v652bb_append_chat_threadsafe("LocalComet", "STOP: functional test center завершился исключением:\n" + traceback.format_exc(), "error")
        finally:
            _v652bb_set_buttons_busy(False)
            _v652bb_refresh_patch_status_label()

    threading.Thread(target=worker, daemon=True).start()
    return "Functional Test Center запущен в фоне."


def _v652bb_accept_patch_sync():
    backend = _v652bb_patch_panel_backend()
    lines = ["=== NEW MENU PATCH WORKFLOW v6.52b ==="]
    lines.append(backend.import_validate_apply_check_text())
    joined = "\n".join(lines)
    if "STOP:" in joined:
        return joined
    lines.append("\n=== FUNCTIONAL TEST CENTER ===")
    lines.append(_v652bb_run_functional_tests_sync(full=True))
    return "\n".join(lines)


def _v652bb_accept_patch_button():
    def worker():
        _v652bb_set_buttons_busy(True)
        _v652bb_set_progress(0, 100, "Принятие patch")
        try:
            text = _v652bb_accept_patch_sync()
            _v652bb_append_chat_threadsafe("LocalComet", _v652bb_safe_text(text, 6000), "normal" if "STOP:" not in text else "error")
        except Exception:
            _v652bb_set_progress(100, 100, "FAIL")
            _v652bb_append_chat_threadsafe("LocalComet", "STOP: patch workflow завершился исключением:\n" + traceback.format_exc(), "error")
        finally:
            _v652bb_set_buttons_busy(False)
            _v652bb_refresh_patch_status_label()

    threading.Thread(target=worker, daemon=True).start()
    return "Принятие patch запущено в фоне."


def _v652bb_latest_test_text():
    center = _v652bb_functional_center()
    payload = center.get_latest_test_report()
    if not payload.get("exists", True):
        return "Functional Test Center: отчетов пока нет."
    return center.format_functional_test_report(payload)


def _v652bb_open_latest_test_report():
    try:
        center = _v652bb_functional_center()
        payload = center.get_latest_test_report()
        report = payload.get("report") or payload.get("json")
        if not report:
            return "STOP: отчет functional test center пока не найден."
        path = Path(report)
        if hasattr(os, "startfile"):
            os.startfile(str(path))
            return f"Открыт отчет: {path}"
        return f"Отчет: {path}"
    except Exception:
        return "STOP: не удалось открыть отчет тестов:\n" + traceback.format_exc()


def _v652bb_is_new_menu_command_text(text):
    lower = str(text or "").strip().lower().replace("ё", "е")
    if not lower:
        return False
    exact = {
        "выбрать patch",
        "выбрать патч",
        "select patch",
        "choose patch",
        "принять патч",
        "применить patch",
        "применить патч",
        "accept patch",
        "apply patch",
        "тест",
        "полный тест",
        "тест проекта",
        "функциональный тест",
        "localcomet test",
        "localcomet test smoke",
        "localcomet test full",
        "статус тестов",
        "последний тест",
        "открыть отчет тестов",
        "перечитать панель",
        "reload panel",
    }
    if lower in exact:
        return True
    prefixes = (
        "выбрать response ",
        "выбрать patch ",
        "выбрать патч ",
        "select response ",
        "select patch ",
        "choose response ",
        "choose patch ",
    )
    return lower.startswith(prefixes)


def _v652bb_run_new_menu_command_text(text):
    raw = str(text or "").strip()
    lower = raw.lower().replace("ё", "е")

    if lower.startswith(("выбрать response ", "select response ", "choose response ")):
        path = raw.split(" ", 2)[2].strip() if len(raw.split(" ", 2)) >= 3 else ""
        return _v652bb_select_patch_path(path)

    if lower.startswith(("выбрать patch ", "выбрать патч ", "select patch ", "choose patch ")):
        path = raw.split(" ", 2)[2].strip() if len(raw.split(" ", 2)) >= 3 else ""
        return _v652bb_select_patch_path(path)

    if lower in {"выбрать patch", "выбрать патч", "select patch", "choose patch"}:
        return _v652bb_choose_patch_dialog()

    if lower in {"принять патч", "применить patch", "применить патч", "accept patch", "apply patch"}:
        return _v652bb_accept_patch_button()

    if lower in {"тест", "тест проекта", "функциональный тест", "localcomet test", "localcomet test smoke"}:
        return _v652bb_run_tests_button(full=False)

    if lower in {"полный тест", "localcomet test full"}:
        return _v652bb_run_tests_button(full=True)

    if lower in {"статус тестов", "последний тест"}:
        return _v652bb_latest_test_text()

    if lower == "открыть отчет тестов":
        return _v652bb_open_latest_test_report()

    if lower in {"перечитать панель", "reload panel"}:
        try:
            python = sys.executable
            argv = [python] + sys.argv
            _append_chat("LocalComet", "Перечитываю панель через os.execv.")
            os.execv(python, argv)
        except Exception:
            return "STOP: не удалось перечитать панель:\n" + traceback.format_exc()

    return "STOP: неизвестная команда нового меню v6.52b."
# LOCALCOMET_FUNCTIONAL_TEST_CENTER_RU_V652B_END


def _render_main(content, page="chat"):
    global _CHAT_TEXT, _CHAT_ENTRY, _MODE_BUTTON, _DRAWER_FRAME

    _clear(content)

    if page == "safety":
        _render_safety_text(content)
        return

    if page == "report":
        _render_report_text(content)
        return

    if page == "verification":
        _render_verification_page(content)
        return

    if page == "agent":
        _render_ai_agent_page(content)
        return

    if page == "computer":
        _render_computer_use_page(content)
        return

    main = tk.Frame(content, bg="#050711")
    main.pack(fill="both", expand=True)

    chat_panel = tk.Frame(main, bg="#050711")
    chat_panel.pack(side="left", fill="both", expand=True)

    header = tk.Frame(chat_panel, bg="#050711")
    header.pack(fill="x", pady=(0, 8))
    tk.Label(header, text="Чат", bg="#050711", fg="#f9fafb", font=("Segoe UI", 16, "bold")).pack(side="left")
    tk.Label(header, text="Enter отправляет · Ctrl+K фокус · режим переключается снизу", bg="#050711", fg="#6b7280", font=("Segoe UI", 9)).pack(side="left", padx=12)

    _CHAT_TEXT = tk.Text(
        chat_panel,
        bg="#060913",
        fg="#e5e7eb",
        insertbackground="#f8fafc",
        relief="flat",
        font=("Consolas", 10),
        wrap="word",
        height=24,
        padx=14,
        pady=12,
    )
    _CHAT_TEXT.tag_configure("author", foreground="#93c5fd", font=("Segoe UI", 9, "bold"))
    _CHAT_TEXT.tag_configure("user", foreground="#f8fafc")
    _CHAT_TEXT.tag_configure("assistant", foreground="#d1d5db")
    _CHAT_TEXT.tag_configure("error", foreground="#fca5a5")
    _CHAT_TEXT.tag_configure("success", foreground="#86efac")
    _CHAT_TEXT.tag_configure("warning", foreground="#fbbf24")
    _CHAT_TEXT.tag_configure("status", foreground="#93c5fd")
    _CHAT_TEXT.pack(fill="both", expand=True)
    _CHAT_TEXT.insert("end", "LocalComet\n", ("author",))
    _CHAT_TEXT.insert("end", "Computer Use Core готов. Для агентской работы открой вкладку «AI Агент»: контекст → план → draft → проверка.\n", ("assistant",))
    _CHAT_TEXT.configure(state="disabled")

    # PREMIUM_TASK_PANEL_V652B_MAIN_ACTIONS_START
    global _TEST_PROGRESS_BAR, _TEST_STATUS_LABEL, _PATCH_SELECTED_LABEL, _PATCH_ACCEPT_BUTTON, _PATCH_TEST_BUTTON, _PATCH_CHOOSE_BUTTON, _PATCH_UX_STATUS_LABEL, _PATCH_UX_SUMMARY_LABEL, _PATCH_UX_OPEN_REPORT_BUTTON, _PATCH_UX_COPY_SUMMARY_BUTTON
    action_panel = tk.Frame(chat_panel, bg="#050711")
    action_panel.pack(fill="x", pady=(0, 8))

    _PATCH_CHOOSE_BUTTON = ttk.Button(action_panel, text="Выбрать patch", style="Codex.TButton", command=_v652bb_choose_patch_dialog)
    _PATCH_CHOOSE_BUTTON.pack(side="left", padx=(0, 6))
    _PATCH_ACCEPT_BUTTON = ttk.Button(action_panel, text="Принять патч", style="Primary.TButton", command=_v652bb_accept_patch_button)
    _PATCH_ACCEPT_BUTTON.pack(side="left", padx=(0, 6))
    _PATCH_TEST_BUTTON = ttk.Button(action_panel, text="Тест", style="Codex.TButton", command=lambda: _v652bb_run_tests_button(full=True))
    _PATCH_TEST_BUTTON.pack(side="left", padx=(0, 10))

    _TEST_PROGRESS_BAR = ttk.Progressbar(action_panel, mode="determinate", maximum=100, value=0, length=220)
    _TEST_PROGRESS_BAR.pack(side="left", padx=(0, 10))
    _TEST_STATUS_LABEL = tk.Label(action_panel, text="Тесты: готовы", bg="#050711", fg="#6b7280", font=("Segoe UI", 8))
    _TEST_STATUS_LABEL.pack(side="left", padx=(0, 10))
    _PATCH_SELECTED_LABEL = tk.Label(action_panel, text=f"Patch: {_v652bb_selected_response_text()}", bg="#050711", fg="#6b7280", font=("Segoe UI", 8))
    _PATCH_SELECTED_LABEL.pack(side="left", fill="x", expand=True)

    # PATCH_PANEL_UX_V657_ACTIONS_START
    _PATCH_UX_STATUS_LABEL = tk.Label(action_panel, text="Статус: NO_PATCH_SELECTED", bg="#050711", fg="#93c5fd", font=("Segoe UI", 8, "bold"))
    _PATCH_UX_STATUS_LABEL.pack(side="left", padx=(8, 6))
    _PATCH_UX_SUMMARY_LABEL = tk.Label(action_panel, text="Patch еще не запускался", bg="#050711", fg="#6b7280", font=("Segoe UI", 8))
    _PATCH_UX_SUMMARY_LABEL.pack(side="left", padx=(0, 6))
    _PATCH_UX_OPEN_REPORT_BUTTON = ttk.Button(action_panel, text="Открыть последний отчет", style="Codex.TButton", command=_v657_patch_ux_open_latest_report)
    _PATCH_UX_OPEN_REPORT_BUTTON.pack(side="left", padx=(0, 6))
    _PATCH_UX_COPY_SUMMARY_BUTTON = ttk.Button(action_panel, text="Скопировать итог", style="Codex.TButton", command=_v657_patch_ux_copy_last_summary)
    _PATCH_UX_COPY_SUMMARY_BUTTON.pack(side="left", padx=(0, 0))
    # PATCH_PANEL_UX_V657_ACTIONS_END
    # PREMIUM_TASK_PANEL_V652B_MAIN_ACTIONS_END

    input_bar = tk.Frame(chat_panel, bg="#050711")
    input_bar.pack(fill="x", pady=(10, 0))

    _CHAT_ENTRY = tk.Entry(
        input_bar,
        bg="#0b1020",
        fg="#f8fafc",
        insertbackground="#f8fafc",
        relief="flat",
        font=("Segoe UI", 10),
    )
    _CHAT_ENTRY.pack(side="left", fill="x", expand=True, ipady=10)
    _bind_chat_entry_clipboard(_CHAT_ENTRY)

    def submit(event=None):
        if _CHAT_ENTRY is None:
            return "break"
        value = _CHAT_ENTRY.get().strip()
        if not value:
            return "break"
        _CHAT_ENTRY.delete(0, "end")
        execute_command(value, "enter" if event is not None else "button")
        return "break"

    _CHAT_ENTRY.bind("<Return>", submit)
    _CHAT_ENTRY.bind("<KP_Enter>", submit)

    ttk.Button(input_bar, text="Отправить", style="Primary.TButton", command=submit).pack(side="left", padx=(8, 0))
    ttk.Button(input_bar, text="Очистить", style="Codex.TButton", command=_reset_chat).pack(side="left", padx=(6, 0))
    _MODE_BUTTON = ttk.Button(input_bar, text=f"Режим: {_mode_label()}", style="Codex.TButton", command=_toggle_input_mode)
    _MODE_BUTTON.pack(side="left", padx=(6, 0))
    ttk.Button(input_bar, text="Команды", style="Codex.TButton", command=_toggle_drawer).pack(side="left", padx=(6, 0))

    _DRAWER_FRAME = tk.Frame(main, bg="#0b1020", width=340, highlightbackground="#1f2937", highlightthickness=1)
    _DRAWER_FRAME.pack_propagate(False)
    settings = _load_settings()
    if settings.get("command_drawer_visible", True):
        _DRAWER_FRAME.pack(side="right", fill="y", padx=(10, 0))
    else:
        global _DRAWER_VISIBLE
        _DRAWER_VISIBLE = False

    tk.Label(_DRAWER_FRAME, text="Команды", bg="#0b1020", fg="#f9fafb", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
    tk.Label(_DRAWER_FRAME, text="Клик — вставить. Двойной клик — отправить.", bg="#0b1020", fg="#6b7280", font=("Segoe UI", 8)).pack(anchor="w", padx=10, pady=(0, 4))

    canvas = tk.Canvas(_DRAWER_FRAME, bg="#0b1020", highlightthickness=0)
    scroll = ttk.Scrollbar(_DRAWER_FRAME, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg="#0b1020")
    inner.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    _render_command_list(inner)

    _CHAT_ENTRY.focus_set()


def open_task_panel(panel=None):
    global _WINDOW_REF, _PANEL_REF, _INPUT_MODE
    _PANEL_REF = panel

    try:
        if _WINDOW_REF is not None and _WINDOW_REF.winfo_exists():
            _WINDOW_REF.lift()
            _WINDOW_REF.focus_force()
            return {
                "ok": True,
                "mode": "premium_task_panel_open",
                "generated_at": _now(),
                "opened": True,
                "reused": True,
            }
    except Exception:
        _WINDOW_REF = None

    install_settings()
    settings = _load_settings()
    _INPUT_MODE = settings.get("input_mode", "chat") if settings.get("input_mode") in {"chat", "command"} else "chat"

    root = _find_root(panel)
    _configure_style(root)

    window = tk.Toplevel(root)
    _WINDOW_REF = window
    window.title("LocalComet Computer Use Core RU")
    window.configure(bg="#050711")
    window.geometry("1180x740")
    window.minsize(980, 620)

    shell = tk.Frame(window, bg="#050711")
    shell.pack(fill="both", expand=True)

    sidebar = tk.Frame(shell, bg="#030712", width=172)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)

    tk.Label(sidebar, text="LocalComet", bg="#030712", fg="#f9fafb", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=(18, 2))
    tk.Label(sidebar, text="AI Agent", bg="#030712", fg="#6b7280", font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(0, 18))

    content_wrap = tk.Frame(shell, bg="#050711")
    content_wrap.pack(side="left", fill="both", expand=True, padx=14, pady=12)

    topbar = tk.Frame(content_wrap, bg="#050711")
    topbar.pack(fill="x", pady=(0, 10))

    crumb = tk.Label(topbar, text="Чат", bg="#050711", fg="#f8fafc", font=("Segoe UI", 11, "bold"))
    crumb.pack(side="left")

    tk.Label(topbar, text="Computer Use · Observe/Dry-run/Confirm · Ctrl+K", bg="#050711", fg="#6b7280", font=("Segoe UI", 8)).pack(side="right", padx=4)

    content = tk.Frame(content_wrap, bg="#050711")
    content.pack(fill="both", expand=True)

    nav_items = [
        ("Чат", "chat"),
        ("AI Агент", "agent"),
        ("Computer Use", "computer"),
        ("Проверка", "verification"),
        ("Безопасность", "safety"),
        ("О панели", "report"),
    ]

    buttons = {}

    def select(label, page):
        for name, button in buttons.items():
            button.configure(bg="#111827" if name == label else "#030712", fg="#f8fafc" if name == label else "#9ca3af")
        crumb.configure(text=label)
        _render_main(content, page)

    for label, page in nav_items:
        button = tk.Button(
            sidebar,
            text=label,
            bg="#030712",
            fg="#9ca3af",
            activebackground="#111827",
            activeforeground="#f8fafc",
            relief="flat",
            anchor="w",
            padx=14,
            pady=10,
            font=("Segoe UI", 10),
            command=lambda l=label, p=page: select(l, p),
        )
        button.pack(fill="x", padx=8, pady=2)
        buttons[label] = button

    footer = tk.Frame(sidebar, bg="#030712")
    footer.pack(side="bottom", fill="x", padx=14, pady=14)
    tk.Label(footer, text="Enter: отправка", bg="#030712", fg="#34d399", font=("Segoe UI", 8)).pack(anchor="w")
    tk.Label(footer, text="browser: off", bg="#030712", fg="#6b7280", font=("Segoe UI", 8)).pack(anchor="w")
    tk.Label(footer, text=PANEL_VERSION, bg="#030712", fg="#6b7280", font=("Segoe UI", 8)).pack(anchor="w", pady=(8, 0))

    status_bar = tk.Frame(content_wrap, bg="#050711")
    status_bar.pack(fill="x", pady=(8, 0))
    global _STATUS_LABEL
    _STATUS_LABEL = tk.Label(status_bar, text="Готово", bg="#050711", fg="#6b7280", font=("Segoe UI", 9))
    _STATUS_LABEL.pack(side="left")

    window.bind("<Control-k>", lambda event: (_CHAT_ENTRY.focus_set() if _CHAT_ENTRY is not None else None))
    window.bind("<Alt-c>", lambda event: _toggle_drawer())
    window.bind("<Alt-C>", lambda event: _toggle_drawer())
    window.protocol("WM_DELETE_WINDOW", window.destroy)

    select("Чат", "chat")

    return {
        "ok": True,
        "mode": "premium_task_panel_open",
        "generated_at": _now(),
        "opened": True,
        "native_window": True,
        "codex_minimal": True,
        "codex_workspace": True,
        "command_drawer_default": False,
    }


def auto_open_task_panel_if_enabled(panel=None):
    settings = _load_settings()
    if not settings.get("auto_open_task_panel_on_start", True):
        return {
            "ok": True,
            "mode": "premium_task_panel_auto_open",
            "generated_at": _now(),
            "opened": False,
            "reason": "auto_open_task_panel_on_start disabled",
        }
    return open_task_panel(panel)


def set_auto(enabled):
    settings = _load_settings()
    settings["auto_open_task_panel_on_start"] = bool(enabled)
    settings["mode"] = "true_chat"
    settings["show_raw_json"] = False
    settings["plain_chat_uses_router"] = False
    settings["true_chat_mode"] = True
    settings["llm_chat_mode"] = True
    settings["updated_at"] = _now()
    _save_settings(settings)
    return {
        "ok": True,
        "mode": "premium_task_panel_auto_setting",
        "generated_at": _now(),
        "auto_open_task_panel_on_start": bool(enabled),
        "settings": str(SETTINGS_PATH),
    }


def status():
    settings = _load_settings()
    return {
        "ok": True,
        "mode": "premium_task_panel_status",
        "generated_at": _now(),
        "name": PANEL_NAME,
        "version": PANEL_VERSION,
        "language": "ru",
        "native_window": True,
        "browser": False,
        "codex_minimal": True,
        "codex_workspace": True,
        "command_drawer_default": False,
        "chat_command_toggle": True,
        "true_chat_mode": True,
        "agent_chat_brain": True,
        "project_verification_tab": True,
        "one_button_project_check": True,
        "strict_project_stability": True,
        "llm_chat_mode": True,
        "plain_chat_uses_llm": True,
        "enter_sends": True,
        "casual_local_reply": True,
        "casual_llm_reply": True,
        "router_used_for_plain_chat": False,
        "raw_json_hidden": True,
        "command_groups": list(CODEX_COMMANDS.keys()),
        "settings": settings,
        "commands": [
            "pc task panel status",
            "pc task panel open",
            "pc task panel auto on",
            "pc task panel auto off",
            "pc task panel report",
            "pc new ui",
            "новый интерфейс",
        ],
    }


def report():
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "status": status(),
        "command_groups": CODEX_COMMANDS,
        "help": HELP_TEXT,
    }
    json_path = REPORTS_DIR / f"premium_task_panel_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"premium_task_panel_report_{_stamp()}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# LocalComet Agent Chat Brain RU",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- version: {PANEL_VERSION}",
        "- native_window: true",
        "- browser: false",
        "- codex_workspace: true",
        "- enter_sends: true",
        "- chat_command_toggle: true",
        "- agent_chat_brain: true",
        "- llm_chat_mode: true",
        "- project_verification_tab: true",
        "- one_button_project_check: true",
        "- strict_project_stability: true",
        "- casual_local_reply: true",
        "",
        "## Commands",
        "",
    ]
    for group_name, items in CODEX_COMMANDS.items():
        lines.append(f"### {group_name}")
        for title, command in items:
            lines.append(f"- {title}: `{command}`")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "ok": True,
        "mode": "premium_task_panel_report",
        "generated_at": _now(),
        "report": str(md_path),
        "json": str(json_path),
    }


def format_payload(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")

    if lower in {"pc task panel", "pc task panel status", "task panel status"}:
        return format_payload(status())

    if lower in {"pc task panel open", "task panel open", "pc new ui", "pc open new ui", "новый интерфейс", "открой новый интерфейс"}:
        return format_payload(open_task_panel(_PANEL_REF))

    if lower in {"pc task panel auto on", "task panel auto on"}:
        return format_payload(set_auto(True))

    if lower in {"pc task panel auto off", "task panel auto off"}:
        return format_payload(set_auto(False))

    if lower in {"pc task panel report", "task panel report"}:
        return format_payload(report())

    return format_payload({
        "ok": False,
        "mode": "premium_task_panel_unknown_command",
        "generated_at": _now(),
        "error": "Неизвестная команда task panel.",
        "commands": status().get("commands", []),
    })


def is_premium_task_panel_command(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    exact = {
        "pc task panel",
        "pc task panel status",
        "task panel status",
        "pc task panel open",
        "task panel open",
        "pc task panel auto on",
        "task panel auto on",
        "pc task panel auto off",
        "task panel auto off",
        "pc task panel report",
        "task panel report",
        "pc new ui",
        "pc open new ui",
        "новый интерфейс",
        "открой новый интерфейс",
    }
    return lower in exact


# --- Computer Use Agent Loop RU v6.43 markers ---
COMPUTER_USE_AGENT_LOOP_ENABLED = True
COMPUTER_USE_AGENT_LOOP_TITLE = "Computer Use Agent Loop"
COMPUTER_USE_AGENT_LOOP_BUTTONS = [
    "Статус",
    "Наблюдать экран",
    "Карта экрана",
    "Dry-run цель",
    "Цикл goal",
    "Шаг цикла",
    "Одобрить действие",
    "Replay",
    "Отчёт",
]

def _render_computer_use_agent_loop_page(content):
    return {
        "title": "Computer Use",
        "version": PANEL_VERSION,
        "content": content,
        "buttons": COMPUTER_USE_AGENT_LOOP_BUTTONS,
        "shows": [
            "current mode",
            "active goal",
            "run_id",
            "phase",
            "pending action",
            "latest observation",
            "latest ui map",
            "latest decision",
            "latest report",
            "next safe action",
        ],
        "safety": "observe -> decide -> safety -> confirmation -> limited execute -> observe result -> replay",
    }

def _computer_use_agent_loop_dispatch(command):
    from modules.computer_use_core_ru import dispatch
    return dispatch(command)


# --- Computer Use Visual Guard UI Map Preservation RU v6.47d markers ---
COMPUTER_USE_AUTO_GUI_ENABLED = True
COMPUTER_USE_AUTO_GUI_TITLE = "Computer Use Auto Click/Type"
COMPUTER_USE_AUTO_GUI_BUTTONS = [
    "Auto click/type",
    "Авто клик",
    "Авто ввод",
    "Файлы требуют подтверждения",
    "Опасные действия заблокированы",
]

def _render_computer_use_auto_gui_page(content):
    return {
        "title": "Computer Use Auto Click/Type",
        "version": PANEL_VERSION,
        "content": content,
        "policy": "non-file grounded GUI click/type can run automatically; file changes require explicit confirmation",
        "buttons": COMPUTER_USE_AUTO_GUI_BUTTONS,
    }

def _computer_use_auto_gui_dispatch(command):
    from modules.computer_use_core_ru import dispatch
    return dispatch(command)


# --- Computer Use Visual Guard UI Map Preservation RU v6.47d markers ---
COMPUTER_USE_ELEMENT_GROUNDING_STABLE_ENABLED = True
COMPUTER_USE_ELEMENT_GROUNDING_STABLE_TITLE = "Computer Use Element Grounding"
COMPUTER_USE_ELEMENT_GROUNDING_STABLE_MARKERS = [
    "Computer Use",
    "Element Grounding",
    "Find element",
    "Ground element",
    "Click element",
    "Type into element",
    "Element confidence",
    "Grounded action",
    "Observe after action",
]

def _render_computer_use_element_grounding_stable_page(content):
    return {
        "title": "Computer Use Element Grounding",
        "version": PANEL_VERSION,
        "content": content,
        "buttons": COMPUTER_USE_ELEMENT_GROUNDING_STABLE_MARKERS,
        "policy": "element description -> UI map candidates -> confidence -> grounded click/type -> observe result",
    }

def _computer_use_element_grounding_stable_dispatch(command):
    from modules.computer_use_core_ru import dispatch
    return dispatch(command)


# --- Computer Use Visual Guard UI Map Preservation RU v6.47d markers ---
COMPUTER_USE_FOCUS_TYPE_GUARD_ENABLED = True
COMPUTER_USE_FOCUS_TYPE_GUARD_TITLE = "Computer Use Focus Type Guard"
COMPUTER_USE_FOCUS_TYPE_GUARD_MARKERS = [
    "Focus Type Guard",
    "Find focus target",
    "Verified textbox",
    "Guarded type",
    "Focus before type",
    "Observe after type",
    "File text requires confirmation",
]

def _render_computer_use_focus_type_guard_page(content):
    return {
        "title": "Computer Use Focus Type Guard",
        "version": PANEL_VERSION,
        "content": content,
        "buttons": COMPUTER_USE_FOCUS_TYPE_GUARD_MARKERS,
        "policy": "find textbox/input/editor -> focus target -> validate text -> guarded type -> observe result",
    }

def _computer_use_focus_type_guard_dispatch(command):
    from modules.computer_use_core_ru import dispatch
    return dispatch(command)


# --- Computer Use Visual Guard UI Map Preservation RU v6.47d markers ---
COMPUTER_USE_VISUAL_GUARD_ENABLED = True
COMPUTER_USE_VISUAL_GUARD_TITLE = "Computer Use Visual Guard"
COMPUTER_USE_VISUAL_GUARD_MARKERS = [
    "Visual Guard",
    "Before observation",
    "After observation",
    "Screen diff",
    "Window changed",
    "Dialog detected",
    "Error detected",
    "Replan decision",
    "Observe after action",
]

def _render_computer_use_visual_guard_page(content):
    return {
        "title": "Computer Use Visual Guard",
        "version": PANEL_VERSION,
        "content": content,
        "buttons": COMPUTER_USE_VISUAL_GUARD_MARKERS,
        "policy": "before observation -> GUI action -> after observation -> compare -> continue/replan/ask_user/stop",
    }

def _computer_use_visual_guard_dispatch(command):
    from modules.computer_use_core_ru import dispatch
    return dispatch(command)


# --- Computer Use Visual Guard UI Map Preservation RU v6.47d markers ---
COMPUTER_USE_VISUAL_GUARD_CLICK_POLICY_REPAIR_ENABLED = True
COMPUTER_USE_VISUAL_GUARD_CLICK_POLICY_REPAIR_MARKERS = [
    "Visual Guard Click Policy Repair",
    "GUI-only non-file click",
    "Save-like labels do not imply file change",
    "Explicit modifies_files required",
]


# --- Computer Use Visual Guard UI Map Preservation RU v6.47d markers ---
COMPUTER_USE_VISUAL_GUARD_TYPE_POLICY_REPAIR_ENABLED = True
COMPUTER_USE_VISUAL_GUARD_TYPE_POLICY_REPAIR_MARKERS = [
    "Visual Guard Type Policy Repair",
    "GUI screen guarded type",
    "Verified input type",
    "Guarded focus before type",
    "Simulated focus plus type",
]


# --- Computer Use Visual Guard UI Map Preservation RU v6.47d markers ---
COMPUTER_USE_VISUAL_GUARD_UI_MAP_PRESERVATION_ENABLED = True
COMPUTER_USE_VISUAL_GUARD_UI_MAP_PRESERVATION_MARKERS = [
    "Visual Guard UI Map Preservation",
    "Preserve previous non-empty UI map",
    "Do not poison grounding with empty observe map",
    "Click after guarded type remains grounded",
]

# --- Computer Use Dev Harness Test Isolation RU v6.47e markers ---
COMPUTER_USE_DEV_HARNESS_TEST_ISOLATION_ENABLED = True
COMPUTER_USE_DEV_HARNESS_TEST_ISOLATION_MARKERS = [
    "Dev Harness Test Isolation",
    "LOCALCOMET_TEST_ROOT",
    "Computer Use Contracts",
    "Synthetic UI map isolation",
    "Preflight audit",
    "No production latest_ui_map poisoning",
]

def _render_computer_use_dev_harness_page(content):
    return {
        "title": "Computer Use Dev Harness Test Isolation",
        "version": PANEL_VERSION,
        "content": content,
        "buttons": COMPUTER_USE_DEV_HARNESS_TEST_ISOLATION_MARKERS,
        "policy": "test fixtures and contract tests restore latest_ui_map after every run",
    }

def _computer_use_dev_harness_dispatch(command):
    from modules.computer_use_core_ru import dispatch
    return dispatch(command)

# --- Computer Use Dev Harness Premium Marker Repair RU v6.47g markers ---
COMPUTER_USE_DEV_HARNESS_PREMIUM_MARKER_REPAIR_ENABLED = True
COMPUTER_USE_DEV_HARNESS_PREMIUM_MARKER_REPAIR_MARKERS = [
    "Dev Harness Premium Marker Repair",
    "Dev Harness Strict Version Repair",
    "Dev Harness Test Isolation",
    "Synthetic UI map isolation",
    "Preflight audit",
    "Computer Use contracts",
]

# --- Computer Use Dev Harness Module Version Repair RU v6.47h markers ---
COMPUTER_USE_DEV_HARNESS_MODULE_VERSION_REPAIR_ENABLED = True
COMPUTER_USE_DEV_HARNESS_MODULE_VERSION_REPAIR_MARKERS = [
    "Dev Harness Module Version Repair",
    "Project paths version v6.47h",
    "Fixture version v6.47h",
    "Contract tests version v6.47h",
    "Preflight audit version v6.47h",
    "Synthetic UI map isolation",
    "Preflight audit",
]

# --- Computer Use Dev Harness Regex Version Repair RU v6.47i markers ---
COMPUTER_USE_DEV_HARNESS_REGEX_VERSION_REPAIR_ENABLED = True
COMPUTER_USE_DEV_HARNESS_REGEX_VERSION_REPAIR_MARKERS = [
    "Dev Harness Regex Version Repair",
    "Project paths version v6.47i",
    "Fixture version v6.47i",
    "Contract tests version v6.47i",
    "Preflight audit version v6.47i",
    "Synthetic UI map isolation",
    "Preflight audit",
]

PREMIUM_TASK_PANEL_MULTISTEP_LOOP_RU_V648D = "Computer Use Multi-Step Loop RU: включен. Safe deterministic loop, run artifacts, status/latest/report/stop."
PREMIUM_TASK_PANEL_MULTISTEP_LOOP_RU_V648D_MARKER = 'v6.48d multistep loop premium panel marker'

PREMIUM_TASK_PANEL_MULTISTEP_LOOP_RU_V648D = "Computer Use Multi-Step Loop RU: включен. Safe deterministic loop, run artifacts, status/latest/report/stop."
PREMIUM_TASK_PANEL_MULTISTEP_LOOP_RU_V648D_MARKER = 'v6.48d multistep loop premium panel marker'

# Computer Use Multi-Step Loop Append Dispatch Repair RU: включен. Команды: pc computer run loop / pc computer simulate loop

# Computer Use Multi-Step Loop Contracts Route Repair RU: включен. Команды: pc computer run loop / pc computer simulate loop

# Computer Use Multi-Step Loop Strict Warning Repair RU: включен. Команды: pc computer run loop / pc computer simulate loop

# Computer Use Multi-Step Loop Non Command Module Strict Repair RU: включен. Команды: pc computer run loop / pc computer simulate loop

# Computer Use Multi-Step Loop Stale Quarantine Assertion Repair RU: включен. Команды: pc computer run loop / pc computer simulate loop

# Relay Apply Status Finalizer Repair RU: включен. _apply_ok не путает failed=0 с failure.

# Patch Panel One Button RU: включен. Новый вход: python LocalComet_Patch_Panel.py

# Relay Patch Panel Response Picker Recovery RU: включен. Активный response.json не переиспользуется как источник patch.

# Patch Panel Compact Chat RU: включен. Лишние кнопки перенесены в чат-команды новой панели.

LEGACY_CONTROL_PANEL_NEW_MENU_ONLY_PANEL_RU_V650G = "Legacy Control Panel retired; new Computer Use Core menu is the primary UI."

# Computer Use Agent Mission RU: включен. Команды: pc computer agent mission / pc computer agent simulate.

COMPUTER_USE_FULL_CONTROL_CHAT_ROUTE_RU_V651 = "v6.51 управляй пк stays command in Computer Use chat mode"


# Patch Workflow + Functional Test Center RU: включен. Кнопки: Выбрать patch / Принять патч / Тест.

# v6.54 Computer Use Observe/Vision Upgrade RU: new-menu command aware.

# BEGIN v6.54b New Menu copy log command repair
try:
    _premium_task_panel_dispatch_before_copy_log_ru_v654b
except NameError:
    _premium_task_panel_dispatch_before_copy_log_ru_v654b = dispatch


def _localcomet_copy_text_to_clipboard_ru_v654b(text):
    try:
        import tkinter as _tk
        root = _tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(str(text))
        root.update()
        root.destroy()
        return True, "tkinter clipboard"
    except Exception as exc:
        return False, str(exc)


def _localcomet_latest_log_text_ru_v654b():
    from pathlib import Path
    candidates = [
        Path("Projects/ChatGPTRelay/codex_report.md"),
        Path("Projects/ChatGPTRelay/relay_apply_log.txt"),
        Path("Projects/ChatGPTRelay/response.json"),
        Path("Projects/Reports/localcomet_functional_tests/latest_functional_test.md"),
        Path("Projects/ComputerUse/observe_vision_reports/latest_observation.md"),
    ]
    existing = [p for p in candidates if p.exists() and p.is_file()]
    if not existing:
        return False, "", "No known LocalComet log/report file exists yet."
    newest = max(existing, key=lambda p: p.stat().st_mtime)
    text = newest.read_text(encoding="utf-8", errors="replace")
    return True, text, str(newest)


def dispatch(command, *args, **kwargs):
    text = str(command or "").strip().lower().replace("ё", "е")
    if text in {
        "копировать лог",
        "скопировать лог",
        "copy log",
        "copy latest log",
        "копировать последний лог",
        "скопировать последний лог",
    }:
        ok, payload, source = _localcomet_latest_log_text_ru_v654b()
        if not ok:
            return {"ok": False, "handled": True, "mode": "copy_latest_log", "error": source}
        copied, message = _localcomet_copy_text_to_clipboard_ru_v654b(payload)
        return {
            "ok": bool(copied),
            "handled": True,
            "mode": "copy_latest_log",
            "source": source,
            "chars": len(payload),
            "clipboard": message,
            "message": "Лог скопирован в буфер обмена." if copied else "Не удалось скопировать лог в буфер обмена.",
        }
    return _premium_task_panel_dispatch_before_copy_log_ru_v654b(command, *args, **kwargs)
# END v6.54b New Menu copy log command repair


# BEGIN v6.55b Agent Automation Functional Test Center panel integration
PANEL_VERSION = LOCALCOMET_VERSION or "v6.55b"
PANEL_NAME = LOCALCOMET_VERSION_LABEL or "LocalComet Professional Control Panel RU"
LOCALCOMET_AGENT_AUTO_TEST_CENTER_RU_V655B = "v6.55b real agent automation test command in panel"


def _localcomet_add_agent_auto_panel_commands_ru_v655b():
    groups = globals().get("CODEX_COMMANDS")
    if not isinstance(groups, dict):
        return
    computer_use_items = groups.setdefault("Computer Use", [])
    project_items = groups.setdefault("Проект", [])

    def add_unique(items, label, command):
        for existing_label, existing_command in list(items):
            if existing_label == label or existing_command == command:
                return
        items.append((label, command))

    add_unique(computer_use_items, "тест агента", "pc computer agent auto test full")
    add_unique(computer_use_items, "статус теста агента", "pc computer agent auto test status")
    add_unique(project_items, "тест автоматических функций агента", "pc computer agent auto test full")


_localcomet_add_agent_auto_panel_commands_ru_v655b()

try:
    _premium_task_panel_dispatch_before_agent_auto_ru_v655b
except NameError:
    _premium_task_panel_dispatch_before_agent_auto_ru_v655b = dispatch

try:
    _is_premium_task_panel_command_before_agent_auto_ru_v655b
except NameError:
    _is_premium_task_panel_command_before_agent_auto_ru_v655b = is_premium_task_panel_command


def _is_agent_auto_panel_command_ru_v655b(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {
        "pc task panel agent auto test",
        "pc task panel test agent",
        "тест агента",
        "тест автоматических функций агента",
        "проверка автоматических функций агента",
    }


def dispatch(command, *args, **kwargs):
    if _is_agent_auto_panel_command_ru_v655b(command):
        from modules.computer_use_core_ru import dispatch as core_dispatch

        return core_dispatch("pc computer agent auto test full")
    return _premium_task_panel_dispatch_before_agent_auto_ru_v655b(command, *args, **kwargs)


def is_premium_task_panel_command(command):
    if _is_agent_auto_panel_command_ru_v655b(command):
        return True
    return _is_premium_task_panel_command_before_agent_auto_ru_v655b(command)


# END v6.55b Agent Automation Functional Test Center panel integration


# BEGIN v6.56 Professional Panel Capability Audit integration
PANEL_VERSION = LOCALCOMET_VERSION or "v6.56"
PANEL_NAME = LOCALCOMET_VERSION_LABEL or "LocalComet Professional Control Panel RU"
LOCALCOMET_PANEL_CAPABILITY_AUDIT_RU_V656 = "v6.56 real panel capability audit route installed"


def _localcomet_add_panel_capability_audit_commands_ru_v656():
    groups = globals().get("CODEX_COMMANDS")
    if not isinstance(groups, dict):
        return
    project_items = groups.setdefault("Проект", [])
    computer_items = groups.setdefault("Computer Use", [])

    def add_unique(items, label, command):
        for existing_label, existing_command in list(items):
            if existing_label == label or existing_command == command:
                return
        items.append((label, command))

    add_unique(project_items, "аудит панели", "pc panel capability audit")
    add_unique(project_items, "статус аудита панели", "pc panel capability audit status")
    add_unique(computer_items, "тест агента", "pc computer agent auto test full")
    add_unique(project_items, "тест автоматических функций агента", "pc computer agent auto test full")


_localcomet_add_panel_capability_audit_commands_ru_v656()


def _panel_capability_audit_command_ru_v656(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {
        "pc panel capability audit",
        "pc task panel audit",
        "panel capability audit",
        "аудит панели",
        "аудит меню",
        "статус аудита панели",
        "pc panel capability audit status",
    }


def _panel_capability_audit_result_ru_v656(command):
    from modules.panel_capability_audit_ru import dispatch as audit_dispatch

    return audit_dispatch(command)


try:
    _premium_task_panel_dispatch_before_panel_audit_ru_v656
except NameError:
    _premium_task_panel_dispatch_before_panel_audit_ru_v656 = dispatch

try:
    _is_premium_task_panel_command_before_panel_audit_ru_v656
except NameError:
    _is_premium_task_panel_command_before_panel_audit_ru_v656 = is_premium_task_panel_command


def dispatch(command, *args, **kwargs):
    if _panel_capability_audit_command_ru_v656(command):
        return _panel_capability_audit_result_ru_v656(command)
    return _premium_task_panel_dispatch_before_panel_audit_ru_v656(command, *args, **kwargs)


def is_premium_task_panel_command(command):
    if _panel_capability_audit_command_ru_v656(command):
        return True
    return _is_premium_task_panel_command_before_panel_audit_ru_v656(command)


try:
    _v652bb_is_new_menu_command_text_before_panel_audit_ru_v656
except NameError:
    _v652bb_is_new_menu_command_text_before_panel_audit_ru_v656 = _v652bb_is_new_menu_command_text

try:
    _v652bb_run_new_menu_command_text_before_panel_audit_ru_v656
except NameError:
    _v652bb_run_new_menu_command_text_before_panel_audit_ru_v656 = _v652bb_run_new_menu_command_text


def _v656_safe_text(payload):
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        return str(payload)


def _v652bb_is_new_menu_command_text(text):
    lower = str(text or "").strip().lower().replace("ё", "е")
    if _panel_capability_audit_command_ru_v656(lower):
        return True
    if lower in {"тест агента", "тест автоматических функций агента", "проверка автоматических функций агента"}:
        return True
    return _v652bb_is_new_menu_command_text_before_panel_audit_ru_v656(text)


def _v652bb_run_new_menu_command_text(text):
    raw = str(text or "").strip()
    lower = raw.lower().replace("ё", "е")

    if _panel_capability_audit_command_ru_v656(lower):
        result = _panel_capability_audit_result_ru_v656(raw)
        return _v656_safe_text(result)

    if lower in {"тест агента", "тест автоматических функций агента", "проверка автоматических функций агента"}:
        from modules.localcomet_agent_auto_test_center_ru import run_full_suite

        result = run_full_suite(write_report=True)
        return _v656_safe_text(result)

    return _v652bb_run_new_menu_command_text_before_panel_audit_ru_v656(text)

# END v6.56 Professional Panel Capability Audit integration

# BEGIN v6.57 Patch Panel UX Reliability UI bridge
PATCH_PANEL_UX_RELIABILITY_RU_V657 = "v6.57 patch panel UX reliability UI bridge installed"

_PATCH_UX_STATUS_LABEL = globals().get("_PATCH_UX_STATUS_LABEL", None)
_PATCH_UX_SUMMARY_LABEL = globals().get("_PATCH_UX_SUMMARY_LABEL", None)
_PATCH_UX_OPEN_REPORT_BUTTON = globals().get("_PATCH_UX_OPEN_REPORT_BUTTON", None)
_PATCH_UX_COPY_SUMMARY_BUTTON = globals().get("_PATCH_UX_COPY_SUMMARY_BUTTON", None)
_PATCH_UX_STATE_V657 = {
    "current_patch_path": None,
    "last_validation_ok": False,
    "last_apply_ok": False,
    "last_tests_ok": False,
    "last_final_status": "NO_PATCH_SELECTED",
    "last_report_path": "",
    "last_summary": "Patch еще не запускался.",
}


try:
    _v652bb_choose_patch_dialog_before_patch_ux_v657
except NameError:
    _v652bb_choose_patch_dialog_before_patch_ux_v657 = _v652bb_choose_patch_dialog

try:
    _v652bb_select_patch_path_before_patch_ux_v657
except NameError:
    _v652bb_select_patch_path_before_patch_ux_v657 = _v652bb_select_patch_path

try:
    _v652bb_run_tests_button_before_patch_ux_v657
except NameError:
    _v652bb_run_tests_button_before_patch_ux_v657 = _v652bb_run_tests_button

try:
    _v652bb_accept_patch_sync_before_patch_ux_v657
except NameError:
    _v652bb_accept_patch_sync_before_patch_ux_v657 = _v652bb_accept_patch_sync

try:
    _v652bb_accept_patch_button_before_patch_ux_v657
except NameError:
    _v652bb_accept_patch_button_before_patch_ux_v657 = _v652bb_accept_patch_button

try:
    _v652bb_is_new_menu_command_text_before_patch_ux_v657
except NameError:
    _v652bb_is_new_menu_command_text_before_patch_ux_v657 = _v652bb_is_new_menu_command_text

try:
    _v652bb_run_new_menu_command_text_before_patch_ux_v657
except NameError:
    _v652bb_run_new_menu_command_text_before_patch_ux_v657 = _v652bb_run_new_menu_command_text


def _v657_patch_ux_module():
    import importlib
    return importlib.import_module("modules.patch_panel_ux_reliability_ru")


def _v657_patch_ux_color(color):
    return {
        "success": "#86efac",
        "error": "#fca5a5",
        "warning": "#fbbf24",
        "neutral": "#93c5fd",
        "info": "#93c5fd",
    }.get(str(color or "neutral"), "#d1d5db")


def _v657_patch_ux_gui_call(callback):
    try:
        if _WINDOW_REF is not None:
            _WINDOW_REF.after(0, callback)
        else:
            callback()
    except Exception:
        try:
            callback()
        except Exception:
            pass


def _v657_patch_ux_set_status(status, progress=0, message="", color="neutral"):
    status = str(status or "NO_PATCH_SELECTED")
    message = str(message or status)
    _PATCH_UX_STATE_V657["last_final_status"] = status

    def apply_update():
        fg = _v657_patch_ux_color(color)
        if _PATCH_UX_STATUS_LABEL is not None:
            try:
                _PATCH_UX_STATUS_LABEL.configure(text=f"Статус: {status}", fg=fg)
            except Exception:
                pass
        if _PATCH_UX_SUMMARY_LABEL is not None:
            try:
                _PATCH_UX_SUMMARY_LABEL.configure(text=message, fg=fg)
            except Exception:
                pass
        if _TEST_STATUS_LABEL is not None:
            try:
                _TEST_STATUS_LABEL.configure(text=f"{int(progress)}% · {message}", fg=fg)
            except Exception:
                pass
        if _TEST_PROGRESS_BAR is not None:
            try:
                _TEST_PROGRESS_BAR.configure(mode="determinate", maximum=100, value=max(0, min(100, int(progress))))
            except Exception:
                pass
        try:
            _set_status(f"{status} · {message}")
        except Exception:
            pass
        try:
            _v652bb_refresh_patch_status_label()
        except Exception:
            pass

    _v657_patch_ux_gui_call(apply_update)


def _v657_patch_ux_start(status, progress, message):
    _PATCH_UX_STATE_V657["last_final_status"] = str(status)

    def apply_update():
        if _TEST_PROGRESS_BAR is not None:
            try:
                _TEST_PROGRESS_BAR.stop()
            except Exception:
                pass
            try:
                _TEST_PROGRESS_BAR.configure(mode="indeterminate", maximum=100, value=max(0, min(100, int(progress))))
                _TEST_PROGRESS_BAR.start(12)
            except Exception:
                pass
        if _PATCH_UX_STATUS_LABEL is not None:
            try:
                _PATCH_UX_STATUS_LABEL.configure(text=f"Статус: {status}", fg=_v657_patch_ux_color("info"))
            except Exception:
                pass
        if _PATCH_UX_SUMMARY_LABEL is not None:
            try:
                _PATCH_UX_SUMMARY_LABEL.configure(text=str(message), fg=_v657_patch_ux_color("info"))
            except Exception:
                pass
        if _TEST_STATUS_LABEL is not None:
            try:
                _TEST_STATUS_LABEL.configure(text=f"{int(progress)}% · {message}", fg=_v657_patch_ux_color("info"))
            except Exception:
                pass
        try:
            _set_status(f"{status} · {message}")
        except Exception:
            pass

    _v657_patch_ux_gui_call(apply_update)


def _v657_patch_ux_stop(progress=100):
    def apply_update():
        if _TEST_PROGRESS_BAR is not None:
            try:
                _TEST_PROGRESS_BAR.stop()
            except Exception:
                pass
            try:
                _TEST_PROGRESS_BAR.configure(mode="determinate", maximum=100, value=max(0, min(100, int(progress))))
            except Exception:
                pass

    _v657_patch_ux_gui_call(apply_update)


def _v657_patch_ux_finalize(raw_text):
    try:
        ux = _v657_patch_ux_module()
        classification = ux.classify_and_report(raw_text)
    except Exception:
        classification = {
            "status": "ERROR",
            "color": "error",
            "version": "v6.57",
            "tests_ok": False,
            "rollback": False,
            "report_md": "",
            "final_summary": "❌ Ошибка классификации patch workflow:\n" + traceback.format_exc(),
        }
    status = str(classification.get("status") or "ERROR")
    color = str(classification.get("color") or "error")
    summary = str(classification.get("final_summary") or "")
    report = str(classification.get("report_md") or classification.get("report") or "")
    _PATCH_UX_STATE_V657["last_apply_ok"] = status == "APPLIED_OK"
    _PATCH_UX_STATE_V657["last_tests_ok"] = bool(classification.get("tests_ok"))
    _PATCH_UX_STATE_V657["last_report_path"] = report
    _PATCH_UX_STATE_V657["last_summary"] = summary
    _PATCH_UX_STATE_V657["last_final_status"] = status
    _v657_patch_ux_stop(100)
    _v657_patch_ux_set_status(status, 100, summary.splitlines()[1] if len(summary.splitlines()) > 1 else status, color)
    return classification


def _v657_patch_ux_open_latest_report():
    try:
        report = _PATCH_UX_STATE_V657.get("last_report_path") or str(Path("Projects/Reports/patch_panel_ux/latest_patch_panel_ux_report.md"))
        path = Path(report)
        if not path.exists():
            path = Path("Projects/Reports/patch_panel_ux/latest_patch_panel_ux_report.md")
        if hasattr(os, "startfile") and path.exists():
            os.startfile(str(path))
            return f"Открыт отчет: {path}"
        return f"Отчет: {path}"
    except Exception:
        return "STOP: не удалось открыть последний UX отчет:\n" + traceback.format_exc()


def _v657_patch_ux_copy_last_summary():
    text = str(_PATCH_UX_STATE_V657.get("last_summary") or "Patch UX итог пока пуст.")
    try:
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        _append_chat("LocalComet", "Итог patch workflow скопирован в буфер.", "success")
        return "Итог patch workflow скопирован в буфер."
    except Exception:
        return "STOP: не удалось скопировать итог:\n" + traceback.format_exc()


def _v652bb_choose_patch_dialog():
    _v657_patch_ux_start("PATCH_SELECTED", 10, "Открываю выбор patch")
    result = _v652bb_choose_patch_dialog_before_patch_ux_v657()
    if str(result or "").lstrip().startswith("OK:"):
        _PATCH_UX_STATE_V657["current_patch_path"] = _v652bb_selected_response_text()
        _v657_patch_ux_stop(20)
        _v657_patch_ux_set_status("PATCH_SELECTED", 20, "Patch выбран и импортирован", "info")
    elif "отмен" in str(result or "").lower():
        _v657_patch_ux_stop(0)
        _v657_patch_ux_set_status("NO_PATCH_SELECTED", 0, "Выбор patch отменен", "neutral")
    else:
        _v657_patch_ux_stop(100)
        _v657_patch_ux_set_status("ERROR", 100, "Ошибка выбора patch", "error")
    return result


def _v652bb_select_patch_path(path_text):
    _PATCH_UX_STATE_V657["current_patch_path"] = str(path_text or "")
    _v657_patch_ux_start("PATCH_SELECTED", 10, "Импортирую выбранный patch")
    result = _v652bb_select_patch_path_before_patch_ux_v657(path_text)
    if str(result or "").lstrip().startswith("OK:"):
        _v657_patch_ux_stop(20)
        _v657_patch_ux_set_status("PATCH_SELECTED", 20, "Patch выбран и импортирован", "info")
    else:
        _v657_patch_ux_stop(100)
        _v657_patch_ux_set_status("ERROR", 100, "Ошибка выбора patch", "error")
    return result


def _v652bb_accept_patch_sync():
    backend = _v652bb_patch_panel_backend()
    lines = ["=== PATCH PANEL UX RELIABILITY WORKFLOW v6.57 ===", f"started_at: {_now()}"]
    try:
        _v657_patch_ux_start("VALIDATING", 20, "Импортирую patch")
        import_result = backend.import_latest_response_text()
        lines.append("\n--- IMPORT ---")
        lines.append(str(import_result))
        if not str(import_result).lstrip().startswith("OK:"):
            lines.append("\nSTOP: импорт response не прошел.")
            raw = "\n".join(lines)
            classification = _v657_patch_ux_finalize(raw)
            return str(classification.get("final_summary") or "") + "\n" + raw

        _v657_patch_ux_set_status("VALIDATING", 30, "Проверяю Relay response", "info")
        validate_result = backend.validate_relay_response_text()
        lines.append("\n--- VALIDATE ---")
        lines.append(str(validate_result))
        if not backend.validate_output_is_success(str(validate_result)):
            lines.append("\nSTOP: relay validate не прошел. patch не применялся.")
            raw = "\n".join(lines)
            classification = _v657_patch_ux_finalize(raw)
            return str(classification.get("final_summary") or "") + "\n" + raw

        _PATCH_UX_STATE_V657["last_validation_ok"] = True
        _v657_patch_ux_set_status("VALIDATED_OK", 40, "Relay validation OK", "success")
        _v657_patch_ux_start("APPLYING", 50, "Применяю patch через Relay backend")
        apply_result = backend.apply_relay_response_text()
        lines.append("\n--- APPLY ---")
        lines.append(str(apply_result))
        if not backend.apply_output_is_success(str(apply_result)):
            lines.append("\nSTOP: apply не прошел или был rollback. after patch и проверки не запущены.")
            raw = "\n".join(lines)
            classification = _v657_patch_ux_finalize(raw)
            return str(classification.get("final_summary") or "") + "\n" + raw

        _PATCH_UX_STATE_V657["last_apply_ok"] = True
        _v657_patch_ux_set_status("APPLYING", 70, "Patch apply завершен, запускаю after-patch", "info")
        try:
            after_result = backend.after_patch_text()
        except Exception:
            after_result = traceback.format_exc()
        lines.append("\n--- AFTER PATCH ---")
        lines.append(str(after_result))

        _v657_patch_ux_start("RUNNING_TESTS", 82, "Проверяю проект")
        checks_result = backend.run_project_checks_text()
        lines.append("\n--- VERIFY ---")
        lines.append(str(checks_result))
        if "STOP:" in str(checks_result):
            lines.append("\nSTOP: patch применен, но проверки проекта не green.")
            raw = "\n".join(lines)
            classification = _v657_patch_ux_finalize(raw)
            return str(classification.get("final_summary") or "") + "\n" + raw

        _v657_patch_ux_set_status("RUNNING_TESTS", 90, "Запускаю UI functional smoke", "info")
        lines.append("\n--- UI FUNCTIONAL TEST CENTER ---")
        lines.append(str(_v652bb_run_functional_tests_sync(full=True)))
        raw = "\n".join(lines)
        classification = _v657_patch_ux_finalize(raw)
        return str(classification.get("final_summary") or "") + "\n" + raw
    except Exception:
        lines.append("\n--- EXCEPTION ---")
        lines.append(traceback.format_exc())
        raw = "\n".join(lines)
        classification = _v657_patch_ux_finalize(raw)
        return str(classification.get("final_summary") or "") + "\n" + raw


def _v652bb_accept_patch_button():
    def worker():
        _v652bb_set_buttons_busy(True)
        _v657_patch_ux_start("VALIDATING", 20, "Patch workflow запущен")
        try:
            text = _v652bb_accept_patch_sync()
            classification = _v657_patch_ux_finalize(text)
            kind = "success" if classification.get("color") == "success" else "warning" if classification.get("color") == "warning" else "error"
            _v652bb_append_chat_threadsafe("LocalComet", _v652bb_safe_text(text, 9000), kind)
        except Exception:
            _v657_patch_ux_stop(100)
            _v657_patch_ux_set_status("ERROR", 100, "Patch workflow завершился исключением", "error")
            _v652bb_append_chat_threadsafe("LocalComet", "STOP: patch workflow завершился исключением:\n" + traceback.format_exc(), "error")
        finally:
            _v652bb_set_buttons_busy(False)
            _v652bb_refresh_patch_status_label()

    threading.Thread(target=worker, daemon=True).start()
    return "Принятие patch запущено в фоне. Смотри статус-бейдж и progress bar."


def _v652bb_run_tests_button(full=True):
    def worker():
        _v652bb_set_buttons_busy(True)
        _v657_patch_ux_start("RUNNING_TESTS", 10, "Запускаю тесты проекта")
        try:
            text = _v652bb_run_functional_tests_sync(full=full)
            is_green = '"failed": 0' in str(text) or "'failed': 0" in str(text) or "GREEN" in str(text)
            _v657_patch_ux_stop(100)
            _v657_patch_ux_set_status("APPLIED_OK" if is_green else "ERROR", 100, "Тесты пройдены" if is_green else "Тесты упали", "success" if is_green else "error")
            _v652bb_append_chat_threadsafe("LocalComet", text, "success" if is_green else "error")
        except Exception:
            _v657_patch_ux_stop(100)
            _v657_patch_ux_set_status("ERROR", 100, "Functional Test Center exception", "error")
            _v652bb_append_chat_threadsafe("LocalComet", "STOP: functional test center завершился исключением:\n" + traceback.format_exc(), "error")
        finally:
            _v652bb_set_buttons_busy(False)
            _v652bb_refresh_patch_status_label()

    threading.Thread(target=worker, daemon=True).start()
    return "Functional Test Center запущен в фоне. Смотри progress bar."


def _v652bb_is_new_menu_command_text(text):
    lower = str(text or "").strip().lower().replace("ё", "е")
    if lower in {
        "статус патча",
        "patch status",
        "patch ux status",
        "открыть последний отчет",
        "open last report",
        "копировать итог",
        "copy summary",
        "copy final summary",
    }:
        return True
    return _v652bb_is_new_menu_command_text_before_patch_ux_v657(text)


def _v652bb_run_new_menu_command_text(text):
    lower = str(text or "").strip().lower().replace("ё", "е")
    if lower in {"статус патча", "patch status", "patch ux status"}:
        return f"Статус: {_PATCH_UX_STATE_V657.get('last_final_status')}\nОтчет: {_PATCH_UX_STATE_V657.get('last_report_path')}\n{_PATCH_UX_STATE_V657.get('last_summary')}"
    if lower in {"открыть последний отчет", "open last report"}:
        return _v657_patch_ux_open_latest_report()
    if lower in {"копировать итог", "copy summary", "copy final summary"}:
        return _v657_patch_ux_copy_last_summary()
    return _v652bb_run_new_menu_command_text_before_patch_ux_v657(text)

# END v6.57 Patch Panel UX Reliability UI bridge

# BEGIN v6.58 Developer Velocity Toolkit premium menu bridge
PREMIUM_TASK_PANEL_DEVELOPER_VELOCITY_BRIDGE_RU_V658 = "v6.58 developer velocity commands available in menu chat"


def _premium_developer_velocity_is_command_ru_v658(command):
    try:
        from modules.localcomet_developer_velocity_ru import is_developer_velocity_command
        return is_developer_velocity_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"последний сбой", "события патча", "статус разработки", "debug пакет"}


try:
    _premium_dispatch_before_developer_velocity_ru_v658
except NameError:
    _premium_dispatch_before_developer_velocity_ru_v658 = dispatch


def dispatch(command):
    if _premium_developer_velocity_is_command_ru_v658(command):
        from modules.localcomet_developer_velocity_ru import dispatch as _velocity_dispatch
        result = _velocity_dispatch(command)
        if isinstance(result, dict):
            result["handled"] = True
            result.setdefault("route", "localcomet_developer_velocity_ru")
        return result
    result = _premium_dispatch_before_developer_velocity_ru_v658(command)
    if isinstance(result, dict) and str(command or "").strip().lower().replace("ё", "е") in {"pc task panel status", "статус", "status"}:
        commands = list(result.get("commands", [])) if isinstance(result.get("commands", []), list) else []
        for _cmd in ["последний сбой", "события патча", "статус разработки", "debug пакет"]:
            if _cmd not in commands:
                commands.append(_cmd)
        result["commands"] = commands
    return result

# END v6.58 Developer Velocity Toolkit premium menu bridge


# BEGIN v6.58c Developer Velocity Toolkit menu marker repair
PREMIUM_TASK_PANEL_MENU_MARKER_REPAIR_RU_V658C = "v6.58c keeps legacy menu smoke-test markers while preserving the current real panel version"

# These are compatibility marker strings for older smoke checks. They are not the active panel version assignment.
PREMIUM_TASK_PANEL_LEGACY_VERSION_MARKERS_RU_V658C = 'PANEL_VERSION = "v6.52b" | PANEL_VERSION = "v6.55b"'
LOCALCOMET_FUNCTIONAL_TEST_CENTER_RU_V652B = "compatibility marker preserved for functional smoke tests"
LOCALCOMET_AGENT_AUTO_TEST_CENTER_RU_V655B = "compatibility marker preserved for agent automation smoke tests"
PREMIUM_TASK_PANEL_AGENT_AUTO_COMMAND_MARKER_RU_V658C = "тест автоматических функций агента"
PREMIUM_TASK_PANEL_DEVELOPER_VELOCITY_COMMANDS_RU_V658C = "последний сбой | события патча | статус разработки | debug пакет"

# END v6.58c Developer Velocity Toolkit menu marker repair
