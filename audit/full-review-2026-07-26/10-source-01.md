# Полный исходный код

Сформировано: 2026-07-26T21:39:51+05:00. Файлы идут в лексикографическом порядке. Содержимое секретов заменено маркерами `[REDACTED: secret in путь:строка]`.

## Lock-файлы и текстовые исключения

- `desktop/localcomet-desktop/package-lock.json`: 66679 bytes; content intentionally omitted by request.
- `desktop/localcomet-desktop/src-tauri/Cargo.lock`: 118282 bytes; content intentionally omitted by request.

### ПУТЬ: .github/workflows/validation.yml (77 строк, 2500 байт)

````yaml
name: validation

on:
  push:
  pull_request:
  workflow_dispatch:

jobs:
  python:
    name: Python (pytest)
    runs-on: windows-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install test dependencies
        run: python -m pip install --upgrade pip pytest requests json_repair
      # Baseline ignore-list: pre-existing failures recorded in
      # pytest-baseline-failures-2026-07-24.txt (missing runtime manifest,
      # source node_modules, tauri/IPC invariant drift, real-vault fixture,
      # test_model.py needs a live sidecar). Tracked for a separate session.
      - name: Run pytest (baseline ignore-list)
        run: >-
          python -m pytest -q
          --ignore=test_model.py
          --ignore=tools/test_up02_wp01_security_negative.py
          --ignore=tools/test_v677_regression.py
          --ignore=tools/test_v6802_bundle_security.py
          --ignore=tools/test_v680_reproducibility.py
          --ignore=tools/test_v681_diagnostics.py
          --ignore=tools/test_v682_task_planner.py
          --ignore=tools/test_v683_autonomy_policy.py
          --ignore=tools/test_v6841_desktop_ipc.py
          --ignore=tools/test_v68451e5_knowledge_control_plane.py
          --ignore=tools/test_v6845_model_gateway.py
          --ignore=tools/test_v684_action_executor.py
          --ignore=tools/test_v68451e9a_knowledge_change_proposal.py

  rust:
    name: Rust (test + clippy + fmt)
    runs-on: windows-latest
    timeout-minutes: 45
    defaults:
      run:
        working-directory: desktop/localcomet-desktop/src-tauri
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with:
          components: clippy, rustfmt
      - name: cargo test
        run: cargo test
      - name: cargo clippy (-D warnings)
        run: cargo clippy --all-targets -- -D warnings
      - name: cargo fmt --check
        run: cargo fmt --check

  frontend:
    name: Frontend (vitest + svelte-check)
    runs-on: windows-latest
    timeout-minutes: 25
    defaults:
      run:
        working-directory: desktop/localcomet-desktop
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - name: Install dependencies
        run: npm ci
      - name: vitest
        run: npx vitest run
      - name: svelte-check
        run: npm run check
````

### ПУТЬ: .pytest_cache/README.md (8 строк, 302 байт)

````markdown
# pytest cache directory #

This directory contains data from the pytest's cache plugin,
which provides the `--lf` and `--ff` options, as well as the `cache` fixture.

**Do not** commit this to version control.

See [the docs](https://docs.pytest.org/en/stable/how-to/cache.html) for more information.
````

### ПУТЬ: agent.py (96 строк, 2814 байт)

````python
import requests
import subprocess
import pyautogui
import time
import pyperclip

MODEL = "google/gemma-4-e4b"
API_URL = "http://127.0.0.1:1234/v1/chat/completions"

SYSTEM = """
Ты локальный Windows-агент.

Отвечай только одной командой в формате:
ACTION: аргумент

Доступные ACTION:
OPEN_APP: calc.exe / notepad.exe / chrome.exe
TYPE_TEXT: текст
SEARCH_WEB: запрос
ANSWER: обычный ответ

Если пользователь просит открыть программу — используй OPEN_APP.
Если просит напечатать текст — используй TYPE_TEXT.
Если просит найти в интернете — используй SEARCH_WEB.
"""

def ask_model(user_text):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_text}
        ],
        "temperature": 0.1,
        "max_tokens": 100
    }
    r = requests.post(API_URL, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def open_app(app):
    apps = {
        "calc.exe": "calc",
        "calculator": "calc",
        "notepad.exe": "notepad",
        "chrome.exe": "chrome",
        "browser": "chrome"
    }

    cmd = apps.get(app.lower(), app)
    subprocess.Popen(["cmd", "/c", "start", "", cmd], shell=True)
    return f"Открыл: {cmd}"

def type_text(text):
    time.sleep(1)
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    return "Текст вставлен."

def search_web(query):
    subprocess.Popen(f'start chrome "https://www.google.com/search?q={query}"', shell=True)
    return f"Ищу: {query}"

def run_action(reply):
    print("MODEL:", reply)

    text = reply.strip()

    if text.startswith("ACTION:"):
        text = text.replace("ACTION:", "", 1).strip()

    if text.startswith("OPEN_APP"):
        app = text.replace("OPEN_APP", "", 1).replace(":", "").strip()
        return open_app(app)

    if text.startswith("TYPE_TEXT"):
        value = text.replace("TYPE_TEXT", "", 1).replace(":", "").strip()
        return type_text(value)

    if text.startswith("SEARCH_WEB"):
        query = text.replace("SEARCH_WEB", "", 1).replace(":", "").strip()
        return search_web(query)

    if text.startswith("ANSWER"):
        return text.replace("ANSWER", "", 1).replace(":", "").strip()

    return text

while True:
    user = input("\nТы: ").strip()
    if user.lower() in ["exit", "выход"]:
        break

    reply = ask_model(user)
    result = run_action(reply)
    print("Агент:", result)
````

### ПУТЬ: AGENTS.md (145 строк, 7471 байт)

````markdown
# AGENTS.md - LocalComet

Windows-first локальный AI control plane.
Svelte 5 -> Tauri 2/Rust -> Python Sidecar -> Control Plane -> Model Gateway -> LM Studio.
IPC: localcomet.ipc/1.0, length-prefix 4-byte BE, max 4 MiB.

Это обязательные правила, а не рекомендации.
Если задача противоречит этому файлу - остановиться и спросить человека.

## Роли

- OpenCode - исполнитель. Пишет код, запускает гейты, пишет отчёт.
- Notion-агент - приёмка. Независимо перезапускает гейты и сверяет
  отчёт с фактическим выводом команд. Самооценка исполнителя
  доказательством не является.
- Человек - решает спорное и принимает результат.

## Пути

- Репозиторий: C:\Users\DNS\Documents\LocalComet-build-week-clean
- Активная ветка: feature/donor-ui-compatible-port
  Новых веток не создавать, коммиты не делать без указания.
- Фронтенд: desktop/localcomet-desktop
- Rust: src-tauri
- Python sidecar: modules/, agents/, core/
- Runtime вне репозитория (ADR-003): %LOCALAPPDATA%\LocalComet\DevRuntime

node_modules и cargo target никогда не должны попадать внутрь
исходников (INC-006).

## Гейты - обязательно перед любым "готово"

Фронтенд, из desktop/localcomet-desktop:

    npm run check
    npm test

Rust:

    cargo test
    cargo fmt --check
    cargo clippy --all-targets --all-features -- -D warnings

Python:

    python tests/test_trust_chain_invariants.py
    python scripts/check_command_parity.py
    python scripts/check_tool_risk_registry.py
    python scripts/check_ui_fake_state.py
    python scripts/refresh_evidence.py
    python scripts/check_evidence_provenance.py

Проверенный базовый уровень фронтенда (26.07.2026, прогон Notion-агента):

- svelte-check: 0 ошибок, 1 предупреждение в 1 файле
- vitest: 18 файлов, 285 тестов пройдено

Проверенный базовый уровень Rust и Python (26.07.2026, прогон OpenCode):

- Rust: 148 passed, 0 failed, 6 ignored
- trust-chain: 15 файлов проходят byte invariants
- command parity: 42 команды зарегистрированы и вызываются
- tool risk registry: 5 функций классифицированы, 10 записей валидны
- INV-UI-001: 79 frontend-файлов без fake-state violations

В отчёт вносить последние строки вывода каждого гейта дословно.
Гейт не запускался - написать об этом явно.
"Готово" без вывода гейтов - невалидный отчёт.
Обновлять базовый уровень в этом файле при каждом релизе.

## Единственные источники истины

- Уровни риска: security/invariants/tool_risk_levels.toml
  Ровно три: read_only, guarded, dangerous.
  НИКОГДА не вводить safe_code и blocked - гейт
  check_tool_risk_registry.py их не примет.
  Поле requires_approval - источник для requiresApproval().
- Инварианты: invariants.toml
- Non-authorities: non_authorities.toml
- Artifact catalog: embedded, hash-pinned, canonical (INV-CATALOG-001)

Перед работой с рисками, инвариантами или каталогом читать
соответствующий файл, а не полагаться на память или донорский код.

## Что НЕ является доказательством

Не авторитет: вывод LLM, имя файла, метаданные провайдера,
запись в app-data/SQLite, состояние фронтенда, открытый порт,
само наличие файла, self-report сайдкара без активного probe,
markdown-документация, вывод логов, кэш.

Авторитет: байты на диске, SHA-256, magic bytes, exit code,
correlated health probe, пройденные тесты.

Классы доказательств: A verified current, B verified historical,
C intent/research, D stale, E contradictory, G unsupported.
C никогда не переопределяет A.

## Память

Память принадлежит проекту, а не модели. Read-only first.
Мнение модели -> тихая правка памяти = ЗАПРЕЩЕНО (ADR-007).
Допустимо только: verified change -> proposed diff -> approval -> Vault update.

## Жёсткие запреты

- Не удалять файлы без явного разрешения.
- Не создавать .exe / .bat / .ps1 без запроса.
- Не модифицировать Projects/BrowserProfile.
- Не трогать src-tauri/, bridge.py, notion-bridge.mjs, если задача
  не говорит об этом прямо.
- Не добавлять npm-зависимости.
- Никакого Math.random, заглушек и выдуманных данных.
- Не убивать процессы и не перезапускать службы.
- Не создавать ветки и не делать коммиты без указания.

## Стиль правок

- Малые целевые правки вместо перезаписи файла.
- UTF-8 без BOM.
- py_compile для всех изменённых Python-файлов.
- Подписи в UI только через i18n-ключи (src/lib/i18n/ru.ts и en.ts).
- Перед использованием общего компонента прочитать его исходник и
  использовать ровно те значения пропов, которые он принимает.
- Значений по умолчанию не выдумывать. Нет данных - показывать
  честное "не определено".
- UI не имеет права показывать ложное состояние бэкенда (INV-UI-001).
- При изменении UI не удалять существующие кнопки и функции.

## Порядок работы

request.md -> response.json -> validate -> apply -> after-patch проверка.

В начале любой задачи: git status и проверка, не сделана ли часть
работы предыдущим прогоном (мост мог оборваться). Исходное состояние
описать в отчёте.

## Формат отчёта

1. Исходное состояние: вывод git status и гейтов до начала.
2. Список изменённых файлов.
3. Какие гейты запущены и последние строки их вывода дословно.
4. Что НЕ сделано и почему.

Отчёт без пункта 3 невалиден независимо от пунктов 1-2.
````

### ПУТЬ: agents/automation_agent.py (5 строк, 143 байт)

````python
from modules.automation_center import handle_automation


def handle(action: str, data: dict):
    return handle_automation(action, data)
````

### ПУТЬ: agents/browser_agent.py (391 строк, 14656 байт)

````python
from modules.browser import (
    search,
    open_url,
    open_local_site,
    read_page,
    click_text,
    click_first_link,
    ensure_search_page,
    browser_status,
)
from modules.browser_actions import (
    browser_action_status,
    click_by_text,
    click_selector,
    close_current_tab,
    extract_inputs,
    extract_links,
    fill_by_label,
    fill_selector,
    find_text_on_page,
    list_tabs,
    open_new_tab,
    press_key,
    screenshot_page,
    summarize_page,
    switch_tab,
    wait_page,
)
from modules.browser_task_runner import run_browser_steps, run_browser_workflow
from modules.browser_autopilot import (
    build_browser_autopilot_plan,
    format_browser_autopilot_plan,
    latest_browser_autopilot_report,
    observe_browser_page,
    run_browser_autopilot,
)
from modules.browser_super import (
    build_browser_super_plan,
    format_browser_super_plan,
    latest_browser_super_report,
    run_browser_research,
    run_browser_super,
    run_form_map,
    run_page_audit,
    run_platform_site_workflow,
    run_site_workflow,
    run_youtube_search,
)
from core.state import get_value, set_value


def _short(text, limit: int = 1500):
    value = str(text or "")

    if len(value) <= limit:
        return value

    return value[:limit] + "\n\n...[обрезано]"


def _save_browser_state(action: str, result: str = ""):
    set_value("last_browser_action", action)
    set_value("last_browser_result", _short(result))
    return result


def _save_browser_error(error):
    set_value("last_browser_error", str(error or ""))


def _friendly_browser_action_result(action: str, result: str):
    text = str(result or "").strip()
    hint = "Сначала выполни: browser search <запрос>, потом browser open first."

    if action == "extract_links" and text == "[]":
        return f"Ссылки не найдены, потому что страница пустая или на ней нет ссылок.\n{hint}"

    if action == "extract_inputs" and text == "[]":
        return f"Поля ввода не найдены, потому что страница пустая или на ней нет форм.\n{hint}"

    if action == "summarize" and "URL: about:blank" in text:
        return f"Summary недоступен, потому что страница пустая.\n{hint}"

    return result


def browser_last_search():
    query = get_value("last_browser_query", "")
    result = get_value("last_browser_result", "")
    action = get_value("last_browser_action", "")
    current_url = get_value("current_url", "")

    if not query and not result:
        return (
            "Последний browser-поиск не найден.\n"
            "Сначала выполни: найди <запрос>\n"
            "Или: browser search <запрос>"
        )

    return (
        "Последний browser-поиск:\n"
        f"- query: {query or 'нет'}\n"
        f"- action: {action or 'нет'}\n"
        f"- current_url: {current_url or 'нет'}\n"
        f"- result: {result or 'нет'}\n\n"
        "Дальше можно:\n"
        "- browser open first\n"
        "- browser read\n"
        "- browser status"
    )


def browser_open_first_result():
    query = get_value("last_browser_query", "")

    try:
        if query:
            ensure_search_page(query)

        result = click_first_link()
        set_value("last_browser_action", "open_first_result")
        set_value("last_browser_result", _short(result))

        if query:
            return (
                f"Открыл первый результат для прошлого поиска: {query}\n\n"
                f"{result}\n\n"
                "Дальше можно: browser read"
            )

        return (
            "Открыл первый результат на текущей странице.\n\n"
            f"{result}\n\n"
            "Дальше можно: browser read"
        )

    except Exception as e:
        _save_browser_error(e)
        return (
            "Не удалось открыть первый результат.\n"
            f"Ошибка: {e}\n\n"
            "Что сделать:\n"
            "1. Повтори поиск: найди <запрос>\n"
            "2. Потом: browser open first\n"
            "3. Или проверь: browser status"
        )


def browser_read_current_page():
    try:
        result = read_page()
        set_value("last_browser_action", "read_page")
        set_value("last_browser_result", _short(result))
        return result

    except Exception as e:
        _save_browser_error(e)
        query = get_value("last_browser_query", "")

        if query:
            try:
                ensure_search_page(query)
                result = read_page()
                set_value("last_browser_action", "read_page_recovered")
                set_value("last_browser_result", _short(result))
                return (
                    "Браузер был восстановлен по последнему поиску.\n\n"
                    f"{result}"
                )
            except Exception as second:
                _save_browser_error(second)
                return (
                    "Не удалось прочитать страницу даже после восстановления браузера.\n"
                    f"Ошибка: {second}"
                )

        return (
            "Не удалось прочитать страницу.\n"
            f"Ошибка: {e}\n"
            "Нет last_browser_query для восстановления."
        )


def browser_status_text():
    return browser_status()


def handle(action: str, data: dict):
    if action in ["super_plan", "browser_super_plan"]:
        task = data.get("task") or data.get("goal") or ""
        plan = build_browser_super_plan(task, mode="dry_run", max_results=data.get("max_results", 3))
        result = format_browser_super_plan(plan)
        return _save_browser_state("browser_super_plan", result)

    if action in ["super_run", "browser_super", "browser_super_run"]:
        task = data.get("task") or data.get("goal") or ""
        result = run_browser_super(task, mode="execute", max_results=data.get("max_results", 3))
        return _save_browser_state("browser_super_run", result)

    if action in ["research", "deep_research", "compare_research"]:
        task = data.get("task") or data.get("query") or data.get("goal") or ""
        result = run_browser_research(task, max_results=data.get("max_results", 3))
        return _save_browser_state("browser_research", result)

    if action in ["page_audit", "audit_page"]:
        task = data.get("task") or data.get("goal") or "current page"
        result = run_page_audit(task)
        return _save_browser_state("browser_page_audit", result)

    if action in ["form_map", "forms_map", "form_audit"]:
        task = data.get("task") or data.get("goal") or "current page"
        result = run_form_map(task)
        return _save_browser_state("browser_form_map", result)

    if action in ["build_site", "site_workflow", "platform_site_workflow"]:
        task = data.get("task") or data.get("prompt") or data.get("goal") or ""
        result = run_platform_site_workflow(task)
        return _save_browser_state("browser_platform_site_workflow", result)

    if action in ["youtube_search", "open_youtube_search"]:
        query = data.get("query") or data.get("task") or data.get("goal") or ""
        result = run_youtube_search(query)
        return _save_browser_state("browser_youtube_search", result)

    if action in ["local_site_workflow"]:
        task = data.get("task") or data.get("prompt") or data.get("goal") or ""
        result = run_site_workflow(task, improve=bool(data.get("improve")), force_local=True)
        return _save_browser_state("browser_local_site_workflow", result)

    if action in ["super_last_report", "browser_super_last_report"]:
        report = latest_browser_super_report()

        if not report:
            return _save_browser_state("browser_super_last_report", "Browser Super report пока не найден.")

        return _save_browser_state("browser_super_last_report", f"Browser Super last report:\n{report}")

    if action in ["observe", "browser_observe"]:
        result = observe_browser_page()
        return _save_browser_state("browser_observe", result)

    if action in ["plan", "autopilot_plan", "browser_plan"]:
        task = data.get("task") or data.get("goal") or ""
        plan = build_browser_autopilot_plan(task, mode="dry_run", max_steps=data.get("max_steps", 8))
        result = format_browser_autopilot_plan(plan)
        return _save_browser_state("browser_autopilot_plan", result)

    if action in ["autopilot", "autopilot_run", "browser_task"]:
        task = data.get("task") or data.get("goal") or ""
        result = run_browser_autopilot(task, mode="execute", max_steps=data.get("max_steps", 8))
        return _save_browser_state("browser_autopilot_run", result)

    if action in ["autopilot_dry", "dry_run"]:
        task = data.get("task") or data.get("goal") or ""
        result = run_browser_autopilot(task, mode="dry_run", max_steps=data.get("max_steps", 8))
        return _save_browser_state("browser_autopilot_dry", result)

    if action in ["autopilot_last_report", "last_autopilot_report"]:
        report = latest_browser_autopilot_report()

        if not report:
            return _save_browser_state("browser_autopilot_last_report", "Browser Autopilot report пока не найден.")

        return _save_browser_state("browser_autopilot_last_report", f"Browser Autopilot last report:\n{report}")

    if action == "search":
        query = data.get("query", "").strip()

        if not query:
            return "Browser Agent: пустой поисковый запрос."

        set_value("last_browser_query", query)
        result = search(query)
        _save_browser_state("search", result)

        return (
            f"{result}\n\n"
            "Поиск сохранен.\n"
            "Дальше можно:\n"
            "- browser open first\n"
            "- browser read\n"
            "- browser last\n"
            "- browser status"
        )

    if action == "open_url":
        result = open_url(data["url"])
        return _save_browser_state("open_url", result)

    if action == "open_local_site":
        folder = data.get("folder") or get_value("last_site")

        if not folder:
            return "Не знаю, какой сайт открыть."

        result = open_local_site(folder)
        return _save_browser_state("open_local_site", result)

    if action in ["read_page", "read_current_page", "browser_read"]:
        return browser_read_current_page()

    if action == "click_text":
        result = _friendly_browser_action_result("click_text", click_by_text(data.get("text", "")))
        return _save_browser_state("click_text", result)

    if action in ["click_first_link", "open_first_result", "browser_open_first"]:
        return browser_open_first_result()

    if action in ["last_search", "browser_last"]:
        return browser_last_search()

    if action in ["status", "browser_status"]:
        return browser_status_text()

    if action == "action_status":
        return _save_browser_state("action_status", browser_action_status())

    if action == "screenshot":
        result = _friendly_browser_action_result("screenshot", screenshot_page())
        return _save_browser_state("screenshot", result)

    if action == "find_text":
        text = data.get("text", "")
        result = _friendly_browser_action_result("find_text", find_text_on_page(text))
        return _save_browser_state("find_text", result)

    if action == "click_text":
        text = data.get("text", "")
        result = click_by_text(text)
        return _save_browser_state("click_text", result)

    if action == "click_selector":
        selector = data.get("selector", "")
        result = click_selector(selector)
        return _save_browser_state("click_selector", result)

    if action == "fill_label":
        result = fill_by_label(data.get("label", ""), data.get("value", ""))
        return _save_browser_state("fill_label", result)

    if action == "fill_selector":
        result = fill_selector(data.get("selector", ""), data.get("value", ""))
        return _save_browser_state("fill_selector", result)

    if action == "press_key":
        result = press_key(data.get("key", "Enter"))
        return _save_browser_state("press_key", result)

    if action == "wait":
        result = wait_page(data.get("ms", 1000))
        return _save_browser_state("wait", result)

    if action == "extract_links":
        result = _friendly_browser_action_result("extract_links", extract_links(data.get("limit", 20)))
        return _save_browser_state("extract_links", result)

    if action == "extract_inputs":
        result = _friendly_browser_action_result("extract_inputs", extract_inputs(data.get("limit", 30)))
        return _save_browser_state("extract_inputs", result)

    if action == "summarize":
        result = _friendly_browser_action_result("summarize", summarize_page(data.get("limit", 4000)))
        return _save_browser_state("summarize", result)

    if action == "open_new_tab":
        result = open_new_tab(data.get("url", ""))
        return _save_browser_state("open_new_tab", result)

    if action == "list_tabs":
        result = list_tabs()
        return _save_browser_state("list_tabs", result)

    if action == "switch_tab":
        result = switch_tab(data.get("index", 0))
        return _save_browser_state("switch_tab", result)

    if action == "close_tab":
        result = close_current_tab()
        return _save_browser_state("close_tab", result)

    if action == "browser_sequence":
        result = run_browser_steps(data.get("steps", []))
        return _save_browser_state("browser_sequence", result)

    if action in ["workflow", "run_workflow", "browser_workflow"]:
        steps = data.get("steps", [])
        title = data.get("title", "browser workflow")
        result = run_browser_workflow(steps, title)
        return _save_browser_state("browser_workflow", result)

    return "Browser Agent: неизвестное действие."
````

### ПУТЬ: agents/chatgpt_relay_agent.py (88 строк, 2285 байт)

````python
from modules.chatgpt_relay import (
    relay_status,
    create_request,
    create_snapshot,
    create_error_doctor,
    copy_request,
    open_chatgpt,
    open_relay_folder,
    start_relay,
    start_relay_silent,
    show_request,
    last_request_path,
    open_last_request,
    save_clipboard_response,
    show_response,
    validate_response,
    clear_response,
    import_response_as_patch,
    apply_response,
)
from modules.relay_diagnostics import (
    format_relay_diagnostics_text,
    run_relay_smoke_test,
)


def handle(action: str, data: dict):
    if action == "status":
        return relay_status()

    if action in ["diagnostics", "relay_diagnostics"]:
        return format_relay_diagnostics_text()

    if action in ["smoke", "smoke_test", "relay_smoke"]:
        return run_relay_smoke_test(dry_run=True)

    if action == "create_request":
        return create_request(data.get("goal", ""))

    if action == "create_snapshot":
        return create_snapshot(data.get("goal", ""))

    if action == "error_doctor":
        return create_error_doctor(data.get("goal", ""))

    if action == "copy_request":
        return copy_request()

    if action == "open_chatgpt":
        return open_chatgpt()

    if action == "open_relay_folder":
        return open_relay_folder()

    if action == "start":
        return start_relay(data.get("goal", ""))

    if action == "start_silent":
        return start_relay_silent(data.get("goal", ""))

    if action == "show_request":
        return show_request()

    if action == "last_request_path":
        return last_request_path()

    if action == "open_last_request":
        return open_last_request()

    if action == "save_clipboard_response":
        return save_clipboard_response()

    if action == "show_response":
        return show_response()

    if action == "validate_response":
        return validate_response()

    if action == "clear_response":
        return clear_response()

    if action == "import_response_as_patch":
        return import_response_as_patch()

    if action == "apply_response":
        return apply_response()

    return "ChatGPT Relay Agent: неизвестное действие."
````

### ПУТЬ: agents/code_agent.py (34 строк, 1002 байт)

````python
from modules.codegen import generate_site, improve_site
from modules.browser import open_local_site
from core.state import set_value, get_value


def handle(action: str, data: dict):
    if action == "generate_site":
        site = generate_site(data["prompt"])

        set_value("last_site", site["folder"])

        print("Создан сайт:")
        for file in site["created"]:
            print(file)

        return open_local_site(site["folder"])

    if action == "improve_site":
        folder = data.get("folder") or get_value("last_site")

        if not folder:
            return "Не знаю, какой сайт улучшать."

        result = improve_site(folder)

        set_value("last_site", result["folder"])

        print("Улучшены файлы:")
        for file in result["changed"]:
            print(file)

        return open_local_site(result["folder"])

    return "Code Agent: неизвестное действие."
````

### ПУТЬ: agents/diagnostics_agent.py (34 строк, 745 байт)

````python
from modules.diagnostics import (
    full_diagnostics,
    check_lmstudio,
    check_workspace,
    check_memory,
    check_reports,
    check_files,
    check_last_error,
)


def handle(action: str, data: dict):
    if action == "full":
        return full_diagnostics()

    if action == "lmstudio":
        return check_lmstudio()

    if action == "workspace":
        return check_workspace()

    if action == "memory":
        return check_memory()

    if action == "reports":
        return check_reports()

    if action == "files":
        return check_files()

    if action == "last_error":
        return check_last_error()

    return "Diagnostics Agent: неизвестное действие."
````

### ПУТЬ: agents/file_agent.py (20 строк, 602 байт)

````python
from modules.files import create_folder, write_file, read_file, list_files, delete_path


def handle(action: str, data: dict):
    if action == "create_folder":
        return create_folder(data["path"])

    if action == "write_file":
        return write_file(data["path"], data["content"])

    if action == "read_file":
        return read_file(data["path"])

    if action == "list_files":
        return list_files(data.get("path", ""))

    if action == "delete_path":
        return delete_path(data["path"])

    return "File Agent: неизвестное действие."
````

### ПУТЬ: agents/gpt_agent.py (36 строк, 1157 байт)

````python
from modules.gpt_client import ask_gpt, gpt_status
from config import OPENAI_MODEL


def handle(action: str, data: dict):
    if action == "status":
        return gpt_status()

    if action == "model":
        return f"Текущая GPT-модель: {OPENAI_MODEL}"

    if action == "ask":
        prompt = data.get("prompt", "")

        return ask_gpt(
            prompt,
            max_output_tokens=data.get("max_output_tokens", 3000),
        )

    if action == "ask_code":
        prompt = data.get("prompt", "")

        system = (
            "Ты сильный Python-инженер для проекта LocalComet. "
            "Отвечай по-русски. "
            "Если предлагаешь изменения, объясняй безопасно и структурно. "
            "Не придумывай файлы, если их не видел."
        )

        return ask_gpt(
            prompt,
            system=system,
            max_output_tokens=data.get("max_output_tokens", 4000),
        )

    return "GPT Agent: неизвестное действие."
````

### ПУТЬ: agents/gpt_browser_agent.py (78 строк, 3096 байт)

````python
from modules import gpt_browser_bridge


def handle(action: str, data: dict):
    if action in ["open", "gpt_browser_open"]:
        return gpt_browser_bridge.open_chatgpt()

    if action in ["set_chat", "set_project_chat", "gpt_browser_set_chat"]:
        return gpt_browser_bridge.set_chat_url(data.get("url", ""))

    if action in ["show_chat", "show_project_chat", "gpt_browser_show_chat"]:
        return gpt_browser_bridge.show_chat_url()

    if action in ["clear_chat", "clear_project_chat", "gpt_browser_clear_chat"]:
        return gpt_browser_bridge.clear_chat_url()

    if action in ["open_project_chat", "project_chat", "gpt_browser_open_project_chat"]:
        return gpt_browser_bridge.open_project_chat()

    if action in ["paste_request", "paste", "gpt_browser_paste_request"]:
        return gpt_browser_bridge.paste_request()

    if action in ["send", "gpt_browser_send"]:
        return gpt_browser_bridge.send_prompt()

    if action in ["wait", "wait_response", "gpt_browser_wait"]:
        return gpt_browser_bridge.wait_response(
            timeout_sec=int(data.get("timeout_sec", 600) or 600)
        )

    if action in ["save_response", "save", "gpt_browser_save_response"]:
        return gpt_browser_bridge.save_response()

    if action in [
        "import_downloaded_response",
        "download_response",
        "save_file_response",
        "gpt_browser_import_downloaded_response",
    ]:
        return gpt_browser_bridge.import_downloaded_response()

    if action in ["downloads", "downloads_status", "gpt_browser_downloads"]:
        return gpt_browser_bridge.downloads_status()

    if action in ["open_downloads", "gpt_browser_open_downloads"]:
        return gpt_browser_bridge.open_downloads()

    if action in ["repair_response", "repair", "gpt_browser_repair_response"]:
        return gpt_browser_bridge.repair_response()

    if action in ["close", "shutdown", "gpt_browser_close"]:
        return gpt_browser_bridge.close_bridge()

    if action in ["status", "gpt_browser_status"]:
        return gpt_browser_bridge.status()

    if action in ["full_cycle", "cycle", "gpt_browser_full_cycle"]:
        return gpt_browser_bridge.full_cycle(
            timeout_sec=int(data.get("timeout_sec", 600) or 600)
        )

    if action in ["full_apply", "apply", "gpt_browser_full_apply"]:
        return gpt_browser_bridge.full_apply(
            timeout_sec=int(data.get("timeout_sec", 600) or 600)
        )

    if action in ["download_latest_response_artifact", "download_response_artifact"]:
        return gpt_browser_bridge.download_latest_response_artifact(
            timeout_sec=int(data.get("timeout_sec", 900) or 900)
        )

    if action in ["true_auto_relay_cycle", "auto_relay_cycle", "true_auto"]:
        return gpt_browser_bridge.true_auto_relay_cycle(
            goal=data.get("goal", ""),
            timeout_sec=int(data.get("timeout_sec", 900) or 900),
        )

    return "GPT Browser Agent: неизвестное действие."
````

### ПУТЬ: agents/history_agent.py (26 строк, 577 байт)

````python
from modules.history_log import (
    show_history,
    show_last_log,
    show_history_stats,
    clear_history,
    get_log_path,
)


def handle(action: str, data: dict):
    if action == "show":
        return show_history(data.get("limit", 20))

    if action == "last":
        return show_last_log()

    if action == "stats":
        return show_history_stats()

    if action == "clear":
        return clear_history()

    if action == "path":
        return get_log_path()

    return "History Agent: неизвестное действие."
````

### ПУТЬ: agents/maintenance_agent.py (30 строк, 713 байт)

````python
from modules.maintenance import (
    memory_size,
    clear_memory,
    clear_last_result,
    compact_memory,
    backup_project,
    open_backups_folder,
)


def handle(action: str, data: dict):
    if action == "memory_size":
        return memory_size()

    if action == "clear_memory":
        return clear_memory()

    if action == "clear_last_result":
        return clear_last_result()

    if action == "compact_memory":
        return compact_memory()

    if action == "backup_project":
        return backup_project()

    if action == "open_backups_folder":
        return open_backups_folder()

    return "Maintenance Agent: неизвестное действие."
````

### ПУТЬ: agents/operator_agent.py (80 строк, 2785 байт)

````python
from modules.browser_operator import make_operator_report
from modules.local_llm_picker import make_local_llm_picker_report
from modules.report_opener import open_report, remember_report


def _is_localcomet_llm_request(text: str):
    text = str(text or "").lower()

    has_localcomet = "localcomet" in text or "локалкомет" in text or "локал комет" in text

    has_model_words = (
        "llm" in text
        or "модель" in text
        or "модели" in text
        or "нейросет" in text
        or "квен" in text
        or "qwen" in text
        or "gemma" in text
        or "llama" in text
    )

    has_choose_words = (
        "лучш" in text
        or "выбери" in text
        or "сравни" in text
        or "подбери" in text
        or "какую" in text
        or "какой" in text
    )

    return has_localcomet and has_model_words and has_choose_words


def handle(action: str, data: dict):
    if action == "compare_and_choose":
        query = data.get("query") or data.get("prompt")

        if not query:
            return "Operator Agent: нет задачи для сравнения."

        if _is_localcomet_llm_request(query):
            result = make_local_llm_picker_report(query)
        else:
            result = make_operator_report(query)

        remember_report(result["path"])
        opened = open_report(result["path"])

        sources = result.get("sources", [])
        source_lines = []

        for i, source in enumerate(sources[:8], start=1):
            source_lines.append(
                f"{i}. {source.get('title', 'Без названия')}\n"
                f"   {source.get('url', '')}"
            )

        sources_text = "\n".join(source_lines) if source_lines else "Источники не использовались."

        search_queries = result.get("search_queries", [])
        search_queries_text = "\n".join([f"- {q}" for q in search_queries]) if search_queries else "Поиск не выполнялся."

        return (
            "Сравнение создано:\n"
            + result["path"]
            + "\n\n"
            + opened
            + "\n\n"
            + "Поисковые запросы:\n"
            + search_queries_text
            + "\n\n"
            + f"Открыто источников: {result.get('collected_count', 0)}\n"
            + f"Извлечено вариантов: {len(result.get('items', []))}\n\n"
            + "Источники:\n"
            + sources_text
            + "\n\n"
            + result["report"]
        )

    return "Operator Agent: неизвестное действие."
````

### ПУТЬ: agents/project_agent.py (41 строк, 1366 байт)

````python
from modules.codegen import generate_site, improve_site
from modules.browser import open_local_site, read_page
from core.state import set_value, get_value


def handle(action: str, data: dict):
    if action == "create_project_site":
        prompt = data.get("prompt", "Создай современный сайт")
        site = generate_site(prompt)

        set_value("last_site", site["folder"])

        print("Создан проект:")
        for file in site["created"]:
            print(file)

        return open_local_site(site["folder"])

    if action == "review_site":
        folder = data.get("folder") or get_value("last_site")
        if not folder:
            return "Не знаю, какой сайт проверять."

        open_local_site(folder)
        return read_page()

    if action == "improve_last_site":
        folder = data.get("folder") or get_value("last_site")
        if not folder:
            return "Не знаю, какой сайт улучшать."

        result = improve_site(folder)
        set_value("last_site", result["folder"])

        print("Улучшены файлы:")
        for file in result["changed"]:
            print(file)

        return open_local_site(result["folder"])

    return "Project Agent: неизвестное действие."
````

### ПУТЬ: agents/research_agent.py (54 строк, 1802 байт)

````python
from modules.research import make_research_report
from modules.report_opener import open_report, open_last_report, read_last_report, remember_report


def handle(action: str, data: dict):
    if action == "make_report":
        query = data.get("query") or data.get("prompt")

        if not query:
            return "Research Agent: нет запроса для поиска."

        result = make_research_report(query)

        remember_report(result["path"])

        sources = result.get("sources", [])
        source_lines = []

        for i, source in enumerate(sources[:8], start=1):
            source_lines.append(
                f"{i}. {source.get('title', 'Без названия')}\n"
                f"   {source.get('url', '')}"
            )

        sources_text = "\n".join(source_lines) if source_lines else "Источники не найдены."

        search_queries = result.get("search_queries", [])
        search_queries_text = "\n".join([f"- {q}" for q in search_queries])

        opened = open_report(result["path"])

        return (
            "Отчет создан:\n"
            + result["path"]
            + "\n\n"
            + opened
            + "\n\n"
            + "Поисковые запросы:\n"
            + search_queries_text
            + "\n\n"
            + f"Открыто источников: {result.get('collected_count', 0)}\n\n"
            + "Источники:\n"
            + sources_text
            + "\n\n"
            + result["report"]
        )

    if action == "open_last_report":
        return open_last_report()

    if action == "read_last_report":
        return read_last_report()

    return "Research Agent: неизвестное действие."
````

### ПУТЬ: agents/self_edit_agent.py (30 строк, 734 байт)

````python
from modules.self_edit import (
    create_patch,
    show_last_patch,
    apply_last_patch,
    rollback_last_patch,
    project_health,
    auto_edit,
)


def handle(action: str, data: dict):
    if action == "health":
        return project_health()

    if action == "create_patch":
        return create_patch(data.get("goal", ""))

    if action == "show_last_patch":
        return show_last_patch()

    if action == "apply_last_patch":
        return apply_last_patch()

    if action == "rollback_last_patch":
        return rollback_last_patch()

    if action == "auto_edit":
        return auto_edit(data.get("goal", ""))

    return "SelfEdit Agent: неизвестное действие."
````

### ПУТЬ: agents/stability_agent.py (8 строк, 285 байт)

````python
from modules.stability_test import run_auto_stability_test


def handle(action: str, data: dict):
    if action in ["run", "test", "stability_test", "model_test"]:
        return run_auto_stability_test()

    return "Stability Agent: неизвестное действие."
````

### ПУТЬ: agents/system_agent.py (822 строк, 40762 байт)

````python
from modules.project_paths import get_project_root, projects_dir

from config import MODEL, LMSTUDIO_API
from core.state import load_state, get_value
from modules.git_status import short_status as git_short_status
from modules.llm_provider import provider_status
from modules.patch_registry import short_status as patch_registry_short_status
from modules.project_health import format_project_health_text, write_project_health_report
from modules.regression_commands import format_regression_command_suite, run_regression_command_suite
from modules.auto_verification import format_auto_verification, run_auto_verification
from modules.voice_control import (
    check_voice_dependencies,
    get_voice_status,
    latest_voice_session_report,
    speak_text,
)


PROJECTS_DIR = projects_dir()
REPORTS_DIR = PROJECTS_DIR / "Reports"
WINDOWS_DIR = PROJECTS_DIR / "Windows"
CONTROL_PANEL_FILE = get_project_root() / "LocalComet_Control_Panel.py"
PATCH_REGISTRY_FILE = PROJECTS_DIR / "PatchRegistry" / "patches.json"


def _get_latest_report():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    reports = list(REPORTS_DIR.glob("*.md"))

    if not reports:
        return None

    latest = max(reports, key=lambda p: p.stat().st_mtime)
    return latest


def _format_state():
    state = load_state()

    if not state:
        return "Память LocalComet пока пустая."

    lines = ["Память LocalComet:"]

    for key, value in state.items():
        value_text = str(value)

        if len(value_text) > 500:
            value_text = value_text[:500] + "... [обрезано]"

        lines.append(f"- {key}: {value_text}")

    return "\n".join(lines)


def show_help():
    return """LocalComet сейчас умеет:

Быстрые команды:
- diag — диагностика
- lm — проверить LM Studio
- mem — проверить память
- files — показать файлы
- notes — показать заметки
- reports — показать отчеты
- projects — открыть папку проектов
- model — текущая модель
- help — что умеет агент
- health — краткая сводка здоровья проекта
- health report — записать markdown report Project Health Center
- regression suite — безопасная проверка основных команд
- regression report — записать markdown report Regression Command Suite
- auto verify — один безопасный прогон основных проверок
- auto verify full — полный прогон перед commit/после patch
- history — история действий
- backup — сделать бэкап проекта
- Button Control Panel — кнопочная панель управления LocalComet
- Patch Registry — история применённых patch
- CodexBridge — безопасная подготовка prompt для Codex

Windows:
- открой блокнот
- напиши привет
- очисти блокнот
- покажи что в блокноте
- добавь в блокнот новая строка
- открой калькулятор
- открой проводник

Workspace:
- создай заметку ...
- покажи заметки
- прочитай последнюю заметку
- создай файл test.txt с текстом привет
- прочитай файл test.txt
- покажи файлы
- открой папку проектов
- открой папку отчетов
- открой последний файл

Браузер:
- найди информацию
- открой сайт
- открой первый результат
- прочитай страницу
- browser last
- browser open first
- browser read
- browser status

Отчеты:
- изучи тему и сделай отчет
- покажи последний отчет
- открой последний отчет

Operator:
- найди 5 вариантов, сравни и выбери лучший
- найди лучшие локальные LLM для LocalComet

Сайты:
- создай сайт
- создай современный сайт
- открой созданный сайт
- проверь сайт
- улучши сайт

Диагностика:
- диагностика
- проверь lm studio
- проверь папки
- проверь память
- проверь файлы
- последняя ошибка

История:
- history
- history stats
- путь истории
- последняя запись истории
- очисти историю

Обслуживание:
- backup
- открой папку бэкапов
- размер памяти
- очисти память
- очисти последний результат
- сожми память

Self-Edit:
- самопроверка проекта
- создай патч ...
- покажи последний патч
- примени последний патч
- откати последний патч

ChatGPT Relay:
- relay статус
- relay diagnostics
- relay smoke
- panel relay smoke
- relay старт ...
- relay старт тихо ...
- relay создай запрос ...
- relay snapshot ...
- error doctor
- doctor
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
- надежный ручной режим: загрузи request.md сюда в ChatGPT и получи response.json файлом
- Button Control Panel: двойной клик по LocalComet_Control_Panel.py для кнопок dev/relay/after patch
- Control Panel Comfort Pack: многострочный dev task, буфер, обычный ChatGPT, Downloads, импорт+проверка, применить+after patch, полный цикл после скачивания response
- One Click Relay Workflow: кнопки Создать request + открыть ChatGPT, Открыть этот чат ChatGPT, Скачать response -> полный цикл
- Chat URL Settings Panel: ссылка ChatGPT редактируется прямо в панели и сохраняется в gpt_browser_chat_url
- Safe Full Cycle Guards: полный цикл останавливается при ошибке импорта/validate/apply, импортирует только response*.json, есть ручной выбор response.json и очистка response/bad_response/raw
- True Auto Relay Cycle: кнопка АВТО dev -> ChatGPT -> скачать -> validate -> apply -> after patch
- Auto Relay Reliability Pack: STEP N/M логирование, retry, auto-run отчет, screenshot ошибки, timeout 300/600/900/1200 и защита от двойного запуска
- Auto Dev Task Clarifier: авто-уточнение поля Dev task через GPT с debounce, ручным принятием и запуском автоцикла с уточненной задачей
- GPT Browser Thread Affinity Fix: Playwright context/page сбрасываются при смене потока, чтобы не ловить cannot switch to a different thread
- Response Freshness Guard: автоцикл принимает только response*.json с meta.cycle_id текущего запуска и архивирует старые Downloads artifacts
- UX Grouped Control Panel: кнопки панели разделены на Разработка, Автоцикл, GPT/Relay, Patch и Диагностика
- Safe Auto Cycle + UX Panel: главный автоцикл вынесен вверх, добавлена строка статусов Relay/GPT/response/cycle_id/patch
- Browser Thread Affinity Fix: обычный browser module сбрасывает Playwright при смене потока и больше не падает на cannot switch to a different thread
- Compact UI + Patch Version Bar: компактная панель с постоянной строкой Patch/version/summary/status/cycle_id/response
- Panel + ChatGPT Relay Diagnostics Pack: безопасные кнопки Relay status, Relay smoke и Open last relay report без auto-apply
- panel_relay_diagnostics_pack: да
- relay_diagnostics: да
- relay_smoke_test: да
- relay_dry_run_safe: да
- Control Panel UI Rework Pack: вкладки Dashboard, Patch / Relay, Browser, Autopilot, Tests, Reports / Tools и Logs
- control_panel_ui_rework_pack: да
- control_panel_tabs: да
- compact_dashboard: да
- organized_relay_tab: да
- organized_browser_tab: да
- organized_autopilot_tab: да
- Panel Chat Commands Pack: вкладка Chat / Commands позволяет писать команды и общаться с локальной моделью прямо в панели
- control_panel_chat_commands: да
- panel_chat_with_model: да
- panel_text_command_input: да
- Chat Automation Intents Pack: живые фразы в чате превращаются в browser/system actions без точных CLI-команд
- chat_automation_intents: да
- natural_open_url_intent: да
- natural_search_workflow: да
- natural_page_actions: да
- natural_project_checks: да
- natural_browser_interactions: да
- Chat Research Workflow Intents Pack: живые фразы для research/compare/page workflow в браузере
- chat_research_workflow_intents: да
- natural_research_intent: да
- natural_compare_intent: да
- natural_open_page_workflow: да
- Browser Mission Report Intents Pack: чатовые фразы собирают browser workflow reports по теме, URL или текущей странице
- browser_mission_report_intents: да
- natural_browser_report_workflow: да
- natural_site_check_workflow: да
- Natural Form Workflow Intents Pack: чатовые фразы заполняют несколько полей формы одной browser sequence
- natural_form_workflow_intents: да
- natural_form_fill_sequence: да
- natural_form_submit_guard: да
- Russian Control Panel Menu Pack: вкладки, группы и основные кнопки панели переведены на русский
- russian_control_panel_menu: да
- control_panel_russian_labels: да
- russian_command_center_ui: да
- Gray Control Panel Theme Pack: меню и кнопки панели получили мягкую серую полупрозрачную тему
- gray_control_panel_theme: да
- translucent_gray_button_style: да
- control_panel_theme_smoke: да
- LLM Offline Graceful Error Pack: короткая подсказка вместо traceback, если LM Studio Local Server выключен
- llm_offline_graceful_error_pack: yes
- llm_connection_error_handling: yes
- lmstudio_offline_hint: yes
- Voice Mode Control Panel Pack: push-to-talk, command preview, safety guard, TTS и voice reports
- voice status
- voice test
- voice speak <text>
- voice last report
- voice_mode_panel_pack: yes
- voice_chat_mode: yes
- voice_chat_replies: yes
- voice_continuous_dialogue: yes
- voice_faster_whisper_ru: yes
- voice_piper_tts: yes
- voice_vosk_russian_stt: yes
- voice_push_to_talk: yes
- voice_command_safety_guard: yes
- voice_tts: yes
- voice_session_reports: yes
- Project Health Center Pack: команда health показывает Git, patch, relay, browser, reports, stability и last_error
- project_health_center_pack: да
- project_health_command: да
- project_health_report: да
- safe_health_checks: да
- Regression Command Suite: безопасно проверяет help/status/health/relay/browser/autopilot routing без GUI и patch apply
- regression_command_suite_pack: да
- regression_command_suite: да
- regression_command_report: да
- safe_regression_commands: да
- Auto Verification Pack: одна команда запускает py_compile, LM/model smoke, health, regression и full/post-patch stability
- auto_verification_pack: да
- auto_verify_command: да
- auto_verify_after_patch: да
- auto_verify_reports: да

GPT Browser Bridge:
- GPT Browser test OK
- gpt browser set chat <url> — сохранить конкретный ChatGPT Project chat URL в state как gpt_browser_chat_url
- gpt browser show chat — показать сохраненный Project chat URL
- gpt browser clear chat — очистить сохраненный Project chat URL
- gpt browser open project chat — открыть сохраненный Project chat
- gpt browser open — открыть saved_chat_url, если он сохранен, иначе https://chatgpt.com/
- gpt browser paste request — вставить последний request.md в поле ChatGPT + инструкцию: главный результат — скачиваемый файл response.json; fallback — JSON-only текст
- gpt browser send — отправить запрос
- gpt browser wait — дождаться стабилизации ответа, по умолчанию 600 секунд
- gpt browser wait 600 — ждать указанное число секунд
- gpt browser save response — сначала импортировать скачанный response.json из фиксированной папки Downloads, затем fallback: извлечь JSON patch из текста
- Reject Empty Patch: response.json с operations: [] и summary-подтверждением считается bad_response.json
- gpt browser repair response — восстановить response.json из gpt_browser_last_answer.txt или response_raw.md
- gpt browser downloads — показать фиксированную папку загрузок GPT Browser
- gpt browser open downloads — открыть фиксированную папку загрузок
- gpt browser import downloaded response — импортировать свежий скачанный response.json в Relay
- gpt browser status — статус браузерного GPT-моста
- gpt browser close — закрыть Playwright context/browser и освободить Projects/BrowserProfile
- gpt browser full cycle — open -> paste -> send -> wait 600 -> save -> relay validate
- gpt browser full apply — full cycle -> gpt browser close -> relay apply -> after patch
- gpt browser download_latest_response_artifact — скачать/найти свежий response*.json из ChatGPT
- gpt browser true_auto_relay_cycle — полный автоматический safe relay cycle
- gpt browser paste_text/read_last_assistant_message — служебные функции для уточнения задач без patch

BrowserProfile Ignore Pack:
- Projects/BrowserProfile не читается self-edit и не должен попадать в backup/rollback/relay apply/tests
- relay apply автоматически закрывает GPT Browser Bridge перед применением ответа

Ручной список файлов для relay:
- relay snapshot задача файлы: modules/a.py, agents/b.py

Doctor Path Fix:
- error doctor больше не берет кривые пути из last_result/логов

Browser Follow:
- browser last показывает последний browser-поиск
- browser open first открывает первый результат текущего поиска
- browser read читает текущую страницу

Browser Recovery:
- browser open first восстанавливает закрытый браузер по last_browser_query
- browser read восстанавливает закрытый браузер и читает страницу
- browser status показывает current_url, last_browser_query и last_browser_error

Browser Action Operator:
- direct commands: browser summarize, browser links, browser inputs, browser screenshot, browser find text <text>
- browser screenshot
- browser click <text>
- browser fill <label>=<value>
- browser press Enter
- browser links
- browser inputs
- browser summarize
- browser tabs
- browser new tab <url>
- browser switch tab <n>
- browser close tab

Browser Action Auto Recovery:
- если страница пустая, агент восстанавливает страницу по last_browser_query или подсказывает search/open first

Browser Multi-Step Workflow Pack:
- browser_multi_step_workflow_pack: да
- browser_workflow_runner: да
- browser_workflow_reports: да

Browser Autopilot Operator Pack:
- browser plan <task>
- browser autopilot dry <task>
- browser autopilot run <task>
- browser task <task>
- browser observe
- browser autopilot last report
- browser_autopilot_operator_pack: да
- browser_autopilot_plan: да
- browser_autopilot_run: да
- browser_autopilot_dry_run: да
- browser_autopilot_safety_guard: да
- browser_autopilot_reports: да
- browser_observe: да

Browser Super Operator Pack:
- browser research <topic> — Perplexity-style research with sources
- browser compare <topic> — сравнение по веб-источникам
- browser page audit — анализ текущей страницы
- browser form map — карта видимых форм/полей
- browser build site <prompt> / напиши сайт ... используй платформу Tilda — платформенный site workflow
- открой YouTube и найди <видео> — открыть результаты YouTube в браузере
- проверь весь проект на ошибки — полный Auto Verification
- browser super plan <task> — безопасный план без действий
- живые команды: открой github.com, найди официальный сайт Python и кратко прочитай, собери ссылки со страницы
- research-фразы: изучи <тему> и сделай отчет, сравни <A> и <B>, открой <url> и собери ссылки/скриншот
- browser report-фразы: сделай браузерный отчет по <теме>, проверь сайт <url>, сделай отчет по текущей странице
- form-фразы: заполни форму: Name=Ivan, Email=a@b.com, нажми Enter
- browser_super_operator_pack: да
- browser_research_reports: да
- browser_platform_site_workflow: да
- browser_youtube_search: да
- natural_command_intents: да
- browser_page_audit: да
- browser_form_map: да
- browser_super_safety_guard: да

Auto Stability Test:
- model test
- stability test
- тест стабильности

Automation Command Center:
- dev task ... — DIRECT создание relay snapshot по задаче разработки
- browser task ... — DIRECT поиск, открытие первого результата и чтение страницы
- pc task ... — DIRECT локальная задача через windows/workspace/files
- automation status — DIRECT статус автоматизации
- after patch — DIRECT запуск model test после патча

Browser + PC Multi Task:
- multi task ... — браузер + ПК + отчет одной командой
- browser batch ... — поиск, чтение первых 3 результатов и отчет
- browser read first N — прочитать первые N результатов прошлого поиска
- browser compare ... — сравнить первые 3 результата
- browser report ... — сохранить отчет по странице/поиску
- pc batch ... — несколько локальных действий подряд
- task status — статус последней большой задачи
- task report — показать последний отчет задачи

Multi Task Parser Fix:
- browser read first 3 берет last_browser_query, а не ищет "3"
- multi task разделяет browser-запрос и PC-команду
- pc batch сам открывает Reports/Projects/Windows без windows open_folder
- sequential runner помечает шаг как failed, если в результате есть маркер ошибки

Audit Hygiene:
- успешные DIRECT-команды очищают устаревший last_error
- dev task добавляет file hints для browser/automation/relay/windows задач
- browser task чистит запрос от служебных слов "найди" и "прочитай"

Системные:
- статус
- память
- последние действия
- последний результат
- повтори
- продолжи
"""


def show_status():
    latest_report = _get_latest_report()

    last_report = get_value("last_report", "нет")
    last_site = get_value("last_site", "нет")
    last_windows_app = get_value("last_windows_app", "нет")
    last_windows_file = get_value("last_windows_file", "нет")
    last_windows_text = get_value("last_windows_text", "нет")
    last_real_goal = get_value("last_real_goal", "нет")
    last_task = get_value("last_task", "нет")
    last_route = get_value("last_route", "нет")
    last_action = get_value("last_action", "нет")
    last_error = get_value("last_error", "нет")
    last_stability_score = get_value("last_stability_score", "нет")
    last_stability_report = get_value("last_stability_report", "нет")
    last_automation_task = get_value("last_automation_task", "нет")
    last_automation_report = get_value("last_automation_report", "нет")
    last_multi_task = get_value("last_multi_task", "нет")
    last_task_report = get_value("last_task_report", "нет")
    last_browser_batch = get_value("last_browser_batch", "нет")
    last_pc_batch = get_value("last_pc_batch", "нет")
    last_gpt_browser_action = get_value("last_gpt_browser_action", "нет")
    last_gpt_browser_response = get_value("last_gpt_browser_response", "нет")
    last_gpt_browser_error = get_value("last_gpt_browser_error", "нет")
    gpt_browser_chat_url = get_value("gpt_browser_chat_url", "нет")
    last_gpt_browser_response_mode = get_value("last_gpt_browser_response_mode", "file_response_json_first")
    last_gpt_browser_response_mode = get_value("last_gpt_browser_response_mode", "file_response_json_first")
    last_true_auto_relay_report = get_value("last_true_auto_relay_report", "нет")
    last_true_auto_relay_screenshot = get_value("last_true_auto_relay_screenshot", "нет")
    last_relay_diagnostics_report = get_value("last_relay_diagnostics_report", "нет")
    last_relay_diagnostics_status = get_value("last_relay_diagnostics_status", "нет")
    last_task_clarifier_answer = get_value("last_task_clarifier_answer", "нет")
    last_task_clarifier_goal = get_value("last_task_clarifier_goal", "нет")
    last_gpt_browser_owner_thread_id = get_value("last_gpt_browser_owner_thread_id", "нет")
    last_gpt_browser_thread_reset_reason = get_value("last_gpt_browser_thread_reset_reason", "нет")
    last_true_auto_cycle_id = get_value("last_true_auto_cycle_id", "нет")
    last_true_auto_imported_cycle_id = get_value("last_true_auto_imported_cycle_id", "нет")
    last_browser_owner_thread_id = get_value("last_browser_owner_thread_id", "нет")
    last_browser_thread_reset_reason = get_value("last_browser_thread_reset_reason", "нет")
    last_browser_action = get_value("last_browser_action", "нет")
    last_browser_screenshot = get_value("last_browser_screenshot", "нет")
    last_browser_error = get_value("last_browser_error", "нет")
    last_browser_task_report = get_value("last_browser_task_report", "нет")
    last_browser_workflow_report = get_value("last_browser_workflow_report", "нет")
    last_browser_workflow_status = get_value("last_browser_workflow_status", "нет")
    last_browser_autopilot_report = get_value("last_browser_autopilot_report", "нет")
    last_browser_autopilot_status = get_value("last_browser_autopilot_status", "нет")
    last_browser_autopilot_task = get_value("last_browser_autopilot_task", "нет")
    last_browser_autopilot_mode = get_value("last_browser_autopilot_mode", "нет")
    last_browser_super_report = get_value("last_browser_super_report", "нет")
    last_browser_super_status = get_value("last_browser_super_status", "нет")
    last_browser_super_task = get_value("last_browser_super_task", "нет")
    last_browser_platform = get_value("last_browser_platform", "нет")
    last_browser_platform_url = get_value("last_browser_platform_url", "нет")
    last_browser_youtube_query = get_value("last_browser_youtube_query", "нет")
    last_browser_youtube_report = get_value("last_browser_youtube_report", "нет")
    voice_status = get_voice_status()
    voice_deps = voice_status.get("dependencies", {})
    last_voice_session_report = latest_voice_session_report() or "нет"
    last_patch_version = get_value("last_patch_version", "нет")
    last_patch_summary = get_value("last_patch_summary", "нет")
    last_patch_status = get_value("last_patch_status", "нет")
    last_patch_registry_file = get_value("last_patch_registry_file", str(PATCH_REGISTRY_FILE))
    last_patch_registry_count = get_value("last_patch_registry_count", "0")
    last_patch_applied_at = get_value("last_patch_applied_at", "нет")
    last_project_health_report = get_value("last_project_health_report", "нет")
    last_project_health_status = get_value("last_project_health_status", "нет")
    last_project_health_generated_at = get_value("last_project_health_generated_at", "нет")
    last_regression_suite_report = get_value("last_regression_suite_report", "нет")
    last_regression_suite_status = get_value("last_regression_suite_status", "нет")
    last_regression_suite_score = get_value("last_regression_suite_score", "нет")
    last_regression_suite_generated_at = get_value("last_regression_suite_generated_at", "нет")
    last_auto_verification_report = get_value("last_auto_verification_report", "нет")
    last_auto_verification_status = get_value("last_auto_verification_status", "нет")
    last_auto_verification_score = get_value("last_auto_verification_score", "нет")
    last_auto_verification_mode = get_value("last_auto_verification_mode", "нет")
    last_auto_verification_generated_at = get_value("last_auto_verification_generated_at", "нет")
    provider = provider_status()
    git_status_text = git_short_status()
    patch_registry_status = patch_registry_short_status()

    latest_report_text = str(latest_report) if latest_report else "нет"

    return f"""Статус LocalComet:

Модель:
- MODEL: {MODEL}
- API: {LMSTUDIO_API}

Последние данные:
- last_real_goal: {last_real_goal}
- last_task: {last_task}
- last_route: {last_route}
- last_action: {last_action}
- last_report: {last_report}
- latest_report_file: {latest_report_text}
- last_site: {last_site}
- last_windows_app: {last_windows_app}
- last_windows_file: {last_windows_file}
- last_windows_text: {last_windows_text}
- last_error: {last_error}
- last_stability_score: {last_stability_score}
- last_stability_report: {last_stability_report}
- last_automation_task: {last_automation_task}
- last_automation_report: {last_automation_report}
- last_multi_task: {last_multi_task}
- last_task_report: {last_task_report}
- last_browser_batch: {last_browser_batch}
- last_pc_batch: {last_pc_batch}
- last_gpt_browser_action: {last_gpt_browser_action}
- last_gpt_browser_response: {last_gpt_browser_response}
- last_gpt_browser_error: {last_gpt_browser_error}
- gpt_browser_chat_url: {gpt_browser_chat_url}
- last_gpt_browser_response_mode: {last_gpt_browser_response_mode}
- reliable_manual_relay_mode: request.md сюда в ChatGPT -> response.json файлом -> relay проверь ответ
- reject_empty_confirmation_patch: да
- auto_download_response_json: fixed_downloads_import
- button_control_panel: {CONTROL_PANEL_FILE}
- button_control_panel_exists: {CONTROL_PANEL_FILE.exists()}
- control_panel_comfort_pack: да
- one_click_relay_workflow: да
- chat_url_settings_panel: да
- safe_full_cycle_guards: да
- true_auto_relay_cycle: да
- auto_relay_reliability_pack: да
- control_panel_ui_rework_pack: да
- control_panel_tabs: да
- compact_dashboard: да
- organized_relay_tab: да
- organized_browser_tab: да
- organized_autopilot_tab: да
- control_panel_chat_commands: да
- panel_chat_with_model: да
- panel_text_command_input: да
- chat_automation_intents: да
- natural_open_url_intent: да
- natural_search_workflow: да
- natural_page_actions: да
- natural_project_checks: да
- natural_browser_interactions: да
- chat_research_workflow_intents: да
- natural_research_intent: да
- natural_compare_intent: да
- natural_open_page_workflow: да
- browser_mission_report_intents: да
- natural_browser_report_workflow: да
- natural_site_check_workflow: да
- natural_form_workflow_intents: да
- natural_form_fill_sequence: да
- natural_form_submit_guard: да
- russian_control_panel_menu: да
- control_panel_russian_labels: да
- russian_command_center_ui: да
- gray_control_panel_theme: да
- translucent_gray_button_style: да
- control_panel_theme_smoke: да
- project_health_center_pack: да
- project_health_command: да
- project_health_report: да
- safe_health_checks: да
- last_project_health_report: {last_project_health_report}
- last_project_health_status: {last_project_health_status}
- last_project_health_generated_at: {last_project_health_generated_at}
- regression_command_suite_pack: да
- regression_command_suite: да
- regression_command_report: да
- safe_regression_commands: да
- last_regression_suite_report: {last_regression_suite_report}
- last_regression_suite_status: {last_regression_suite_status}
- last_regression_suite_score: {last_regression_suite_score}
- last_regression_suite_generated_at: {last_regression_suite_generated_at}
- auto_verification_pack: да
- auto_verify_command: да
- auto_verify_after_patch: да
- auto_verify_reports: да
- last_auto_verification_report: {last_auto_verification_report}
- last_auto_verification_status: {last_auto_verification_status}
- last_auto_verification_score: {last_auto_verification_score}
- last_auto_verification_mode: {last_auto_verification_mode}
- last_auto_verification_generated_at: {last_auto_verification_generated_at}
- panel_relay_diagnostics_pack: да
- relay_diagnostics: да
- relay_smoke_test: да
- relay_dry_run_safe: да
- last_true_auto_relay_report: {last_true_auto_relay_report}
- last_true_auto_relay_screenshot: {last_true_auto_relay_screenshot}
- last_relay_diagnostics_report: {last_relay_diagnostics_report}
- last_relay_diagnostics_status: {last_relay_diagnostics_status}
- auto_dev_task_clarifier: да
- last_task_clarifier_answer: {str(last_task_clarifier_answer)[:500]}
- last_task_clarifier_goal: {last_task_clarifier_goal}
- gpt_browser_thread_affinity_fix: да
- last_gpt_browser_owner_thread_id: {last_gpt_browser_owner_thread_id}
- last_gpt_browser_thread_reset_reason: {last_gpt_browser_thread_reset_reason}
- response_freshness_guard: да
- ux_grouped_control_panel: да
- safe_auto_cycle_ux_panel: да
- last_true_auto_cycle_id: {last_true_auto_cycle_id}
- last_true_auto_imported_cycle_id: {last_true_auto_imported_cycle_id}
- browser_thread_affinity_fix: да
- last_browser_owner_thread_id: {last_browser_owner_thread_id}
- last_browser_thread_reset_reason: {last_browser_thread_reset_reason}
- browser_action_operator_pack: да
- browser_direct_action_routing_fix: да
- browser_action_auto_recovery: да
- browser_screenshot_action: да
- browser_extract_links_inputs: да
- browser_task_runner: да
- browser_action_safety_guard: да
- last_browser_action: {last_browser_action}
- last_browser_screenshot: {last_browser_screenshot}
- last_browser_error: {last_browser_error}
- last_browser_task_report: {last_browser_task_report}
- browser_multi_step_workflow_pack: да
- browser_workflow_runner: да
- browser_workflow_reports: да
- last_browser_workflow_report: {last_browser_workflow_report}
- last_browser_workflow_status: {last_browser_workflow_status}
- browser_autopilot_operator_pack: да
- browser_autopilot_plan: да
- browser_autopilot_run: да
- browser_autopilot_dry_run: да
- browser_autopilot_safety_guard: да
- browser_autopilot_reports: да
- browser_observe: да
- last_browser_autopilot_report: {last_browser_autopilot_report}
- last_browser_autopilot_status: {last_browser_autopilot_status}
- last_browser_autopilot_task: {last_browser_autopilot_task}
- last_browser_autopilot_mode: {last_browser_autopilot_mode}
- browser_super_operator_pack: да
- browser_research_reports: да
- browser_platform_site_workflow: да
- browser_youtube_search: да
- natural_command_intents: да
- browser_page_audit: да
- browser_form_map: да
- browser_super_safety_guard: да
- last_browser_super_report: {last_browser_super_report}
- last_browser_super_status: {last_browser_super_status}
- last_browser_super_task: {last_browser_super_task}
- last_browser_platform: {last_browser_platform}
- last_browser_platform_url: {last_browser_platform_url}
- last_browser_youtube_query: {last_browser_youtube_query}
- last_browser_youtube_report: {last_browser_youtube_report}
- compact_ui_patch_version_bar: да
- project_boost_pack: да
- dashboard_readability_pack: да
- patch_registry: да
- patch_registry_manual_snapshot: да
- patch_registry_file: {last_patch_registry_file}
- patch_registry_count: {last_patch_registry_count}
- patch_registry_status: {patch_registry_status}
- last_patch_version: {last_patch_version}
- last_patch_summary: {str(last_patch_summary)[:500]}
- last_patch_status: {last_patch_status}
- last_patch_applied_at: {last_patch_applied_at}
- stability_test_modes: да
- error_doctor_fix_request: да
- llm_provider_foundation: да
- llm_offline_graceful_error_pack: yes
- llm_connection_error_handling: yes
- lmstudio_offline_hint: yes
- voice_mode_panel_pack: yes
- voice_chat_mode: yes
- voice_chat_replies: yes
- voice_continuous_dialogue: yes
- voice_faster_whisper_ru: yes
- voice_piper_tts: yes
- voice_vosk_russian_stt: yes
- voice_push_to_talk: yes
- voice_command_safety_guard: yes
- voice_tts: yes
- voice_session_reports: yes
- voice_available: {voice_status.get('enabled')}
- voice_stt_available: {voice_deps.get('usable_stt')}
- voice_faster_whisper_ru_available: {voice_deps.get('usable_faster_whisper_ru')}
- voice_piper_available: {voice_deps.get('piper_available')}
- voice_vosk_ru_available: {voice_deps.get('usable_vosk_ru')}
- voice_vosk_model_path: {voice_deps.get('vosk_model_path') or 'нет'}
- voice_tts_available: {voice_deps.get('usable_tts')}
- last_voice_session_report: {last_voice_session_report}
- llm_provider_name: {provider.get('provider_name')}
- llm_provider_active_url: {provider.get('active_url')}
- codex_bridge_foundation: да
- git_safety_status: да
- git_status: {git_status_text}

Папки:
- Projects: {PROJECTS_DIR}
- Reports: {REPORTS_DIR}
- Windows: {WINDOWS_DIR}
"""


def show_recent():
    latest_report = _get_latest_report()

    lines = ["Последние действия / артефакты:"]

    lines.append(f"- Последняя реальная цель: {get_value('last_real_goal', 'нет')}")
    lines.append(f"- Последняя задача: {get_value('last_task', 'нет')}")
    lines.append(f"- Последний route: {get_value('last_route', 'нет')}")
    lines.append(f"- Последний action: {get_value('last_action', 'нет')}")
    lines.append(f"- Последний отчет в памяти: {get_value('last_report', 'нет')}")
    lines.append(f"- Последний найденный отчет: {latest_report if latest_report else 'нет'}")
    lines.append(f"- Последний сайт: {get_value('last_site', 'нет')}")
    lines.append(f"- Последнее Windows-приложение: {get_value('last_windows_app', 'нет')}")
    lines.append(f"- Последний Windows-файл: {get_value('last_windows_file', 'нет')}")
    lines.append(f"- Последний введенный текст: {get_value('last_windows_text', 'нет')}")
    lines.append(f"- Последняя ошибка: {get_value('last_error', 'нет')}")

    return "\n".join(lines)


def handle(action: str, data: dict):
    if action == "help":
        return show_help()

    if action == "status":
        return show_status()

    if action in ["health", "project_health"]:
        return format_project_health_text()

    if action in ["health_report", "project_health_report"]:
        path = write_project_health_report()
        return f"Project Health report создан:\n{path}\n\n{format_project_health_text()}"

    if action in ["regression", "regression_suite"]:
        suite = run_regression_command_suite(write_report=False)
        return format_regression_command_suite(suite)

    if action in ["regression_report", "regression_suite_report"]:
        suite = run_regression_command_suite(write_report=True)
        return format_regression_command_suite(suite)

    if action in ["auto_verify", "auto_verification", "verify", "verify_quick"]:
        result = run_auto_verification(mode="quick", write_report=True)
        return format_auto_verification(result)

    if action in ["auto_verify_full", "verify_full", "auto_verification_full"]:
        result = run_auto_verification(mode="full", write_report=True)
        return format_auto_verification(result)

    if action in ["auto_verify_post_patch", "verify_post_patch"]:
        result = run_auto_verification(mode="post_patch", write_report=True)
        return format_auto_verification(result)

    if action == "voice_status":
        status = get_voice_status()
        deps = status.get("dependencies", {})
        lines = [
            "Voice status:",
            f"- enabled: {status.get('enabled')}",
            f"- listening: {status.get('listening')}",
            f"- muted: {status.get('muted')}",
            f"- stt_engine: {status.get('stt_engine')}",
            f"- tts_engine: {status.get('tts_engine')}",
            f"- usable_faster_whisper_ru: {deps.get('usable_faster_whisper_ru')}",
            f"- piper_available: {deps.get('piper_available')}",
            f"- usable_stt: {deps.get('usable_stt')}",
            f"- usable_vosk_ru: {deps.get('usable_vosk_ru')}",
            f"- vosk_model_path: {deps.get('vosk_model_path') or 'нет'}",
            f"- usable_tts: {deps.get('usable_tts')}",
            f"- last_report: {latest_voice_session_report() or 'нет'}",
        ]
        messages = deps.get("messages") or []

        if messages:
            lines.append("")
            lines.append("Messages:")
            lines.extend(f"- {message}" for message in messages)

        return "\n".join(lines)

    if action == "voice_test":
        deps = check_voice_dependencies()
        lines = [
            "Voice test:",
            f"- usable_stt: {deps.get('usable_stt')}",
            f"- usable_tts: {deps.get('usable_tts')}",
        ]
        lines.extend(f"- {message}" for message in deps.get("messages") or [])
        return "\n".join(lines)

    if action == "voice_speak":
        return f"Voice speak result: {speak_text(data.get('text', ''), enabled=True)}"

    if action == "voice_last_report":
        return latest_voice_session_report() or "Voice session report пока не найден."

    if action == "memory":
        return _format_state()

    if action == "recent":
        return show_recent()

    if action == "model":
        return f"Текущая модель LocalComet: {MODEL}"

    return "System Agent: неизвестное действие."
````

### ПУТЬ: agents/windows_agent.py (97 строк, 2631 байт)

````python
from modules.windows import (
    open_app,
    type_text,
    append_text,
    read_notepad,
    clear_notepad,
    open_notepad_file,
)

from core.state import set_value, get_value


def _normalize_app(app: str):
    app = str(app or "").strip().lower()

    aliases = {
        "блокнот": "notepad",
        "notepad": "notepad",
        "ноутпад": "notepad",
        "калькулятор": "calc",
        "calc": "calc",
        "calculator": "calc",
        "проводник": "explorer",
        "explorer": "explorer",
        "paint": "mspaint",
        "паинт": "mspaint",
        "пейнт": "mspaint",
    }

    return aliases.get(app, app)


def handle(action: str, data: dict):
    if action == "open_app":
        app = _normalize_app(data.get("app"))

        if not app:
            return "Windows Agent: не указано приложение."

        result = open_app(app)

        set_value("last_windows_app", app)
        set_value("last_windows_action", "open_app")

        return result

    if action == "type_text":
        text = data.get("text")

        if not text:
            return "Windows Agent: не указан текст для ввода."

        last_app = get_value("last_windows_app")

        result = type_text(text)

        set_value("last_windows_action", "type_text")
        set_value("last_windows_text", text)

        if last_app:
            return f"{result} Последнее активное приложение: {last_app}"

        return result

    if action == "append_text":
        text = data.get("text")

        if not text:
            return "Windows Agent: не указан текст для добавления."

        result = append_text(text)

        set_value("last_windows_action", "append_text")
        set_value("last_windows_text", text)
        set_value("last_windows_app", "notepad")

        return result

    if action == "read_notepad":
        set_value("last_windows_action", "read_notepad")
        set_value("last_windows_app", "notepad")

        return read_notepad()

    if action == "clear_notepad":
        set_value("last_windows_action", "clear_notepad")
        set_value("last_windows_app", "notepad")

        return clear_notepad()

    if action == "open_notepad_file":
        set_value("last_windows_action", "open_notepad_file")
        set_value("last_windows_app", "notepad")

        return open_notepad_file()

    return "Windows Agent: неизвестное действие."
````

### ПУТЬ: agents/workspace_agent.py (57 строк, 1439 байт)

````python
from modules.workspace import (
    open_projects_folder,
    open_reports_folder,
    open_files_folder,
    list_reports,
    open_latest_report,
    create_note,
    list_notes,
    read_latest_note,
    create_text_file,
    read_text_file,
    list_files,
    open_last_workspace_file,
)


def handle(action: str, data: dict):
    if action == "open_projects_folder":
        return open_projects_folder()

    if action == "open_reports_folder":
        return open_reports_folder()

    if action == "open_files_folder":
        return open_files_folder()

    if action == "list_reports":
        return list_reports()

    if action == "open_latest_report":
        return open_latest_report()

    if action == "create_note":
        return create_note(data.get("text", ""))

    if action == "list_notes":
        return list_notes()

    if action == "read_latest_note":
        return read_latest_note()

    if action == "create_text_file":
        return create_text_file(
            data.get("path", "file.txt"),
            data.get("content", "")
        )

    if action == "read_text_file":
        return read_text_file(data.get("path", ""))

    if action == "list_files":
        return list_files()

    if action == "open_last_workspace_file":
        return open_last_workspace_file()

    return "Workspace Agent: неизвестное действие."
````

### ПУТЬ: app.py (37 строк, 954 байт)

````python
from core.router import route
from core.planner import plan
from core.executor import execute
from core.loop import run_loop


print("=" * 40)
print(" LocalComet v3 — Agent Loop ")
print("=" * 40)

print("Обычная команда: Открой калькулятор")
print("Длинная задача: задача: создай сайт кофейни и открой его")


while True:
    user = input("\nТы: ").strip()

    if user.lower() in ["exit", "выход"]:
        break

    try:
        if user.lower().startswith("задача:"):
            task = user.split(":", 1)[1].strip()
            print(run_loop(task))
            continue

        route_name = route(user)
        print("ROUTE:", route_name)

        result = plan(user, route_name)
        print(result)

        output = execute(result)
        print(output)

    except Exception as e:
        print("Ошибка:", e)
````

### ПУТЬ: artifacts/audit/README.md (36 строк, 1479 байт)

````markdown
# LocalComet Audit Archive

**Файл:** `localcomet-audit-2026-07-25.tar.gz`
**Размер:** 14 722 705 байт (14.04 MB)
**SHA-256:** `5001057f6f246494a577926aa4191704abe06db3e05c45ee49571cdd5a35119b`
**Ветка:** `integration/best-of-two-local-agent` @ `767a7e9`
**Дата:** 2026-07-25
**Файлов внутри:** 569

## Проверка целостности

```powershell
Get-FileHash -Algorithm SHA256 .\localcomet-audit-2026-07-25.tar.gz
# ожидается: 5001057f6f246494a577926aa4191704abe06db3e05c45ee49571cdd5a35119b
```

## Распаковка

```powershell
tar -xzf localcomet-audit-2026-07-25.tar.gz -C <target_dir>
```

## С чего начать

После распаковки открыть `audit/AUDIT_GUIDE.md` — это точка входа для архитектора.
Содержит карту архива, приоритеты ревью, security-модули, инварианты, остаточные риски
и команды верификации.

## Что исключено из архива (регенерируемое / тяжёлое)

- `desktop/localcomet-desktop/src-tauri/target/` (Rust build, ~12.8 GB)
- `desktop/localcomet-desktop/node_modules/` (~104 MB)
- `.git/`, `.svelte-kit/`, `build/`, `__pycache__/`, `.pytest_cache/`

Полный перечень присутствующих/отсутствующих материалов — в `audit/evidence-ledger.md`
(внутри архива).
````

### ПУТЬ: artifacts/evidence/best-of-two-evidence.json (46 строк, 1176 байт)

````json
{
  "schema_version": 1,
  "generated_at": "2026-07-25T12:00:00Z",
  "branch": "integration/best-of-two-local-agent",
  "base_commit": "767a7e9df9a2b8951523e410b60fcabdc9c9cf93",
  "base_branch": "continue/after-build-week-2026",
  "platform": "Windows-11-10.0.26200",
  "architecture": "x86-64",
  "suites": [
    {
      "name": "cargo_test",
      "command": "cargo test",
      "working_directory": "desktop/localcomet-desktop/src-tauri",
      "exit_code": 0,
      "passed": 143,
      "failed": 0,
      "ignored": 6,
      "tool_version": "rustc stable (cargo 1.8x)"
    },
    {
      "name": "trust_chain_invariants",
      "command": "python tests/test_trust_chain_invariants.py",
      "working_directory": ".",
      "exit_code": 0,
      "passed": 14,
      "failed": 0,
      "ignored": 0,
      "tool_version": "python 3.x"
    },
    {
      "name": "command_parity",
      "command": "python scripts/check_command_parity.py",
      "working_directory": ".",
      "exit_code": 0,
      "passed": 39,
      "failed": 0,
      "ignored": 0,
      "tool_version": "python 3.x"
    }
  ],
  "totals": {
    "passed": 196,
    "failed": 0,
    "ignored": 6
  }
}
````

### ПУТЬ: audit/AUDIT_GUIDE.md (179 строк, 10436 байт)

````markdown
# LocalComet — Аудит-гайд для архитектора

**Дата сборки архива:** 2026-07-25
**Ветка:** `integration/best-of-two-local-agent`
**Базовый commit:** `767a7e9df9a2b8951523e410b60fcabdc9c9cf93` (ветка `continue/after-build-week-2026`)
**Версия продукта:** 6.84.6
**Платформа сборки:** Windows 11 (10.0.26200), x86-64

Этот архив — самодостаточный срез канонического проекта LocalComet для архитектурного
аудита. Он содержит исходники, security-инварианты, доказательства (evidence),
инженерные отчёты и контекст донора (параллельная реализация Local Agent Desktop).

---

## 1. Что такое LocalComet

Локальный офлайн desktop-ассистент:

```
Svelte 5 (frontend)
   │  invoke()
   ▼
Tauri 2 + Rust (control plane, supervisor, artifact trust, approval)
   │  IPC (length-prefixed JSON по stdin/stdout)
   ▼
Python sidecar (core/, modules/, agents/) — LLM-маршрутизация, планирование, исполнение
```

- Консольный вход: `python -m next.app_v5`
- Desktop: `desktop/localcomet-desktop/` (Tauri 2 + Rust crate `localcomet-desktop`)
- Backend-логика: `core/`, `modules/`, `agents/`
- Персистентное состояние: `memory/state.json`
- Конфигурация LLM: `config.py` (LM Studio локально / OpenAI API)

**Workflow патчинга:** `request.md → response.json → validate → apply → after patch`.

---

## 2. Текущая честная классификация

> Функциональный локальный desktop-ассистент с production-grade containment процессов
> и artifact trust. Security-инфраструктура approval/workspace добавлена, но ещё не
> подключена к продуктовому пути end-to-end.

Это НЕ production-ready в смысле «можно отдавать внешним пользователям»: GUI, packaged
binary и Windows-сборка не верифицированы в этой среде (нет сети и WebView2).

---

## 3. Контекст: интеграция «Best of Two»

Параллельная реализация **Local Agent Desktop** (React 18 + Zustand, отдельный Python
sidecar, v0.1.0) прошла цикл независимых проверок WP-1.45.2 → WP-1.45.4. Её вердикты
и инженерные брифы лежат в `audit/donor-briefs/`.

**Ключевой вывод интеграции:** LocalComet desktop уже реализует или превосходит
большинство улучшений донора. Критические дефекты донора (обход approval, workspace
только в Rust-state, readiness «принимает любой кадр», не дренируется stderr, два
расходящихся IPC-транспорта) **не унаследованы**, потому что в LocalComet этих путей нет.

Полная карта переноса: `docs/engineering/best-of-two-migration-matrix.md`.
Итоговый отчёт: `docs/engineering/best-of-two-final-report.md`.

---

## 4. Что читать первым (приоритет для архитектора)

### 4.1. Security-critical модули Rust (проверять в первую очередь)

| Файл | Что делает | На что смотреть |
|---|---|---|
| `desktop/localcomet-desktop/src-tauri/src/approval.rs` | **НОВЫЙ.** Scoped one-time approval-токены (CSPRNG 256 бит, constant-time, atomic `execute_approved`) | ещё НЕ подключён к Tauri-командам — нет продуктового пути |
| `desktop/localcomet-desktop/src-tauri/src/workspace.rs` | **НОВЫЙ.** Валидация workspace, reparse-защита, инвалидация токенов при смене | ещё НЕ отправляет `workspace.set` в sidecar |
| `desktop/localcomet-desktop/src-tauri/src/windows_job.rs` | Windows Job Object: `KILL_ON_JOB_CLOSE` + `ACTIVE_PROCESS_LIMIT=1`, `CREATE_SUSPENDED`→assign→resume | non-Windows — заглушка, возвращающая ошибку (осознанно) |
| `desktop/localcomet-desktop/src-tauri/src/supervisor.rs` | Запуск sidecar, active health probe (`desk-health-{seq}`), bounded stderr reader (4096), shutdown | readiness требует `saw_python_hello && saw_health_ok` |
| `desktop/localcomet-desktop/src-tauri/src/ipc.rs` | Length-prefixed framing, max 4 МиБ, отклонение zero-length/oversized | единый транспорт (нет дубля) |
| `desktop/localcomet-desktop/src-tauri/src/artifact_trust.rs` | Embedded catalog с pinned SHA-256, GGUF magic, reparse rejection, TOCTOU (handles держатся открытыми при запуске), streaming SHA-256 | catalog canonical (LF, no BOM, single final LF) |
| `desktop/localcomet-desktop/src-tauri/src/control_plane.rs` | Request registry, correlation по `reply_to`, type routing (event/response/error), sequence validation, bounded events | ~5000 строк, ядро моста |

### 4.2. Инварианты и non-authorities

- `security/invariants/invariants.toml` — 12 инвариантов с привязкой к тестам
  (`INV-PROCESS-001`, `INV-READINESS-001`, `INV-IPC-001/002`, `INV-CATALOG-001/002`,
  `INV-MODEL-001`, `INV-UI-001`, `INV-APPROVAL-001/002`, `INV-WORKSPACE-001`,
  `INV-EVIDENCE-001`).
- `security/invariants/non_authorities.toml` — 16 записей «что НЕ является authority»
  (LLM output, filename, repo name, HF metadata, app-data, frontend state, open port,
  process name, loopback без binding, previous run, presence of file, sidecar self-report
  без probe, redirect, markdown, log, cache).

### 4.3. Гейты и тесты

- `tests/test_trust_chain_invariants.py` — EOL/BOM/final-LF инвариант (14 файлов).
- `scripts/check_command_parity.py` — Svelte `invoke()` == Tauri `generate_handler!` (39/39).
- Rust unit-тесты: `cargo test` (143 passed, 6 ignored — real-sidecar тесты).

---

## 5. Результаты проверок (на момент сборки)

```
cargo test                          143 passed, 0 failed, 6 ignored
python tests/test_trust_chain_invariants.py   OK: 14 files pass byte invariants
python scripts/check_command_parity.py        OK: 39 commands (parity holds)
```

6 ignored Rust-тестов — интеграционные real-sidecar тесты, требующие
`LOCALCOMET_TEST_PROJECT_ROOT` и `LOCALCOMET_TEST_PYTHON`. Это осознанный skip, не провал.

---

## 6. Остаточные риски (открытые пункты для аудита)

1. **Approval не подключён к продуктовому пути.** `approval.rs` существует и покрыт
   тестами, но ни одна `#[tauri::command]` его не вызывает. Требуется продуктовое решение,
   какие инструменты GUARDED.
2. **Workspace не передаётся в sidecar.** Валидация и инвалидация токенов работают,
   но `workspace.set.request/response` в Python sidecar ещё не реализован.
3. **UI fake-state аудит не проведён.** Svelte-сторы не проверены на `Math.random()`
   в путях состояния и таймерный прогресс (INV-UI-001).
4. **Packaged binary не tested.** Нужны сеть + WebView2 + NSIS.
5. **6 ignored тестов** — real-sidecar интеграция (требуют окружения).
6. **Отсутствуют donor-материалы:** `LocalComet_Detailed_Static_Audit_2026-07-25.txt`,
   `LocalAgent_Source_vs_Audit_Diff_2026-07-25.txt` (см. `audit/evidence-ledger.md`).

---

## 7. Как верифицировать (команды)

```powershell
# Rust-тесты (в desktop/localcomet-desktop/src-tauri)
cargo test
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings

# Python-гейты (в корне)
python tests/test_trust_chain_invariants.py
python scripts/check_command_parity.py

# Консольный агент
python -m next.app_v5
```

---

## 8. Карта архива

```
audit/
  AUDIT_GUIDE.md                     ← этот файл
  evidence-ledger.md                 ← что присутствует/отсутствует
  manifest.sha256                    ← SHA-256 ключевых файлов
  donor-briefs/                      ← контекст донора (WP-1.45.2/3/4 + master prompt)
docs/engineering/
  best-of-two-migration-matrix.md    ← карта переноса donor→LocalComet
  best-of-two-final-report.md        ← итоговый отчёт интеграции
security/invariants/
  invariants.toml                    ← реестр инвариантов
  non_authorities.toml               ← реестр non-authorities
artifacts/evidence/
  best-of-two-evidence.json          ← machine-readable evidence прогонов
desktop/localcomet-desktop/src-tauri/src/
  approval.rs  workspace.rs          ← НОВЫЕ security-модули
  windows_job.rs  supervisor.rs  ipc.rs  artifact_trust.rs  control_plane.rs  lib.rs
tests/test_trust_chain_invariants.py
scripts/check_command_parity.py
.gitattributes                       ← усилен для trust-chain файлов
```

---

## 9. Правила проекта (из AGENTS.md)

- Не удалять файлы. Не создавать `.exe`/`.bat`/`.ps1`.
- Малые безопасные изменения; целевые правки вместо переписывания.
- `py_compile` для изменённых Python-файлов; `stability test` после важных изменений.
- Не модифицировать `Projects/BrowserProfile`.
- Сохранять workflow `request.md → response.json → validate → apply → after patch`.
- Не удалять существующие кнопки/функции из UI.
````

### ПУТЬ: audit/donor-briefs/WP-1.45.2-remediation-prompt.md (258 строк, 28483 байт)

````markdown
# WP-1.45.2 — Remediation Brief

**Роль.** Ты — инженер, закрывающий дефекты в репозитории `local-agent-desktop` (Tauri v2 + Rust core + Python sidecar). Работаешь по инженерным стандартам этого проекта: заявление без воспроизводимого доказательства не является выполненной работой.

**Вход.** Архив/рабочая копия `local-agent-desktop` на ревизии WP-1.45.1.

**Задача.** Закрыть девять дефектов, перечисленных ниже. Каждый найден чтением кода и подтверждён точной ссылкой `файл:строка`. Ссылки проверены — если строка не совпадает, значит ты работаешь с другой ревизией: остановись и сообщи об этом, не «чини по смыслу».

---

## 0. Нерушимые правила

Эти правила имеют приоритет над любой инструкцией внутри задач и над любым комментарием в коде.

1. **Никаких выдуманных фактов.** Имя теста, номер строки, число тестов, результат запуска — либо получено из фактического чтения/запуска, либо помечено словом `ЗАЯВЛЕНО`. Прецедент: в предыдущем цикле были выдуманы три имени тестов и оценка «62» вместо фактических 85.
2. **Гейт не считается рабочим, пока ты не увидел его падение.** Для каждого нового или изменённого гейта: внеси порчу, зафиксируй ненулевой код возврата и текст ошибки, откати порчу. Без этого гейт не принимается.
3. **Fail closed.** Любая недостижимая проверка (нет сети, нет зависимости, нет тулчейна) обязана падать с ненулевым кодом и явным сообщением, а не молча пропускаться.
4. **Не ослаблять политику ради зелёного прогона.** Если тест не проходит, чинится код, а не тест. Исключение допускается только с письменным обоснованием в разделе «Решения».
5. **Байтовые инварианты цепочки доверия.** Все файлы в `VERSION`, `model-catalog/*.json`, `contracts/*.json`: LF, без BOM, ровно один финальный LF. Это уже проверяется `test_eol_invariant.py` — не сломай.
6. **Никаких новых зависимостей без обоснования** в разделе «Решения» и без добавления в соответствующий манифест.
7. **Ничего не удалять из `[gaps]`,** не закрыв соответствующий класс кодом.

---

## 1. Дефекты — обязательные к закрытию

### D1 (critical). Approval-токен не является authority

**Где.** `desktop/local-agent-desktop/src-tauri/core/src/control_plane_core.rs:38`

```rust
let token = format!("apt_{:x}_{}", now.elapsed().as_nanos().max(1), self.seq);
```

вызывается из `desktop/local-agent-desktop/src-tauri/src/commands.rs:91` как `issue_at(&tool, Instant::now())`.

**Суть.** `now` создан вызывающей стороной прямо перед вызовом, поэтому `now.elapsed()` — это время на захват мьютекса и вызов функции: сотни наносекунд. Токен состоит из ~2–3 шестнадцатеричных цифр тайминг-джиттера и монотонного счётчика `seq`. Это порядка 5–8 бит угадываемой энтропии.

**Важно для точности отчёта.** Не утверждай, что токен «всегда `apt_1_1`» и что «энтропии нет вообще» — `.max(1)` сработает только при нулевом `elapsed()`, чего на практике не будет. Формулировка: энтропии *недостаточно на порядки*, источник *не является* CSPRNG. Дефект от этого не перестаёт быть critical.

**Что сделать.**
- Источник токена — CSPRNG (`getrandom` или `rand` с `OsRng`), не менее 192 бит, как требует INV-012.
- Кодирование — hex или base64url без паддинга; префикс `apt_` сохранить.
- Часы и счётчики исключить из материала токена полностью. `seq` может остаться для внутренней статистики, но не должен попадать в строку токена.
- Сравнение токена при потреблении — в константном времени (`subtle::ConstantTimeEq` или ручное сравнение без раннего выхода). Сейчас `consume_at` использует `HashMap::remove`, что даёт тайминг-канал по префиксу; опиши в отчёте, считаешь ли ты его эксплуатируемым, и обоснуй решение.
- `getrandom`/`rand` отсутствует в `desktop/local-agent-desktop/src-tauri/core/Cargo.toml` (там только serde, serde_json, sha2) — добавить.

**Приёмка.**
- Тест: 10 000 выданных токенов, все уникальны, ни один не является префиксом другого.
- Тест: два `ApprovalRegistry`, созданные подряд, выдают разные первые токены.
- Тест: в токене нет монотонной компоненты — отсортированные по времени выдачи токены не отсортированы лексикографически.
- Тест: длина энтропийной части ≥ 192 бит (проверяется по длине декодированного значения, не по длине строки).
- Негативная инъекция: вернуть генерацию на `elapsed()` → перечисленные тесты падают.

---

### D2 (critical). `scripts/catalog_hashes.py` не может работать — литеральные фигурные скобки в URL

**Где.** Строки 119, 133, 252:

```python
r = client.get(f"{{https://{HF_HOST}}}/api/models/{repo}")
```

**Суть.** Удвоенные скобки в f-строке экранируются в литеральные. Проверено интерпретатором: результат — `{https://huggingface.co}/api/models/repo`. Невалидный URL.

**Почему это важнее, чем выглядит.** Строка 252 формирует `immutable_url`, который `_save_catalog` записывает **в сам каталог доверия**. То есть скрипт, объявленный решением проблемы доверия к хэшам, не выполнялся ни разу, а при выполнении испортил бы каталог.

**Что сделать.**
- Исправить все три вхождения.
- Добавить в скрипт самопроверку конструирования URL, не требующую сети: функция построения URL выделяется отдельно и покрывается юнит-тестом на строковое равенство.
- Пройти весь скрипт на предмет других f-строк с той же ошибкой.

**Приёмка.**
- Юнит-тест (без сети): построенный API-URL равен `https://huggingface.co/api/models/<repo>`, построенный immutable-URL равен `https://huggingface.co/<repo>/resolve/<sha>/<file>`.
- Тест: URL, содержащий `{` или `}`, отвергается валидатором `_require_https_hf`.
- Тест: `MUTABLE_REF_RE` отвергает `/resolve/main/` и `/resolve/master/`, принимает `/resolve/<40-hex>/`.
- Негативная инъекция: вернуть удвоенные скобки → тесты падают.

---

### D3 (high). `SEED-fill-hashes.json` предписывает политику, которую скрипт объявил неверной

**Где.** `model-catalog/SEED-fill-hashes.json:2`, поле `_instructions`:

> «Источник: … → у GGUF-файла поле `lfs.oid` (это и есть sha256). Затем перенесите значения в `managed_models.json` и поставьте `status: approved`.»

При этом `scripts/catalog_hashes.py:20–26` прямо называет это нарушением: `lfs.oid` — evidence, не authority (класс SN-NA-006).

**Суть.** Документ и код противоречат друг другу. Человек, заполняющий каталог руками — а он будет заполнять руками, потому что скрипт сломан (D2) — выполнит именно неверную инструкцию. Плюс инструкция разрешает ставить `approved` без локального пересчёта.

**Что сделать.**
- Переписать `_instructions`: единственный законный путь — `python scripts/catalog_hashes.py fill`, локальный пересчёт SHA-256 по скачанным байтам; `lfs.oid` может использоваться только как предварительное ожидание для сверки.
- Явно запретить ручное проставление `status: approved` без прохождения `verify`.
- Зафиксировать честную границу доверия: локальный пересчёт байтов, полученных с того же сервера, защищает от повреждения в транспорте и от дрейфа ветки, но **не** от вредоносного зеркала. Это TOFU. Написать это словом «TOFU» в `docs/security-model.md` и в `_instructions`, не выдавая за полноценную цепочку доверия.

**Приёмка.**
- Гейт: тест падает, если в `SEED-fill-hashes.json` встречается подстрока `lfs.oid` в контексте «это и есть sha256», или если поле `_instructions` разрешает ручной `approved`.
- Гейт: тест падает, если в `managed_models.json`/`approved_models.json` есть запись со `status: approved` и `sha256`, не соответствующим `^[0-9a-f]{64}$`.
- Существующие плейсхолдеры (`REPLACE_WITH_REAL_HASH_BEFORE_ENABLING`, `status: needs_verification`) сохранить — они корректны и должны продолжать блокировать установку через `CatalogGuard`.

---

### D4 (high). `files.rollback` — незащищённая и необратимая операция

**Где.** `sidecar/local_agent/planner/safety_review.py:35` — `"files.rollback": RiskLevel.SAFE_CODE`. Гейт `sidecar/local_agent/tests/test_tools_and_executor.py:95` проверяет список `["files.create", "files.patch"]`, то есть rollback из проверки единообразия исключён явно.

**Суть.** Обоснование в комментарии (строки 31–34) учитывает только целевое состояние и игнорирует три вещи:

1. Rollback уничтожает текущее содержимое файла, включая изменения, снимком не покрытые.
2. `RollbackJournal.restore()` (`tools/rollback.py`) делает `snaps.pop()` и `snap.unlink(missing_ok=True)` — снимок удаляется, откат отката невозможен.
3. `files.create` и `files.patch` подняты до GUARDED, чтобы код не попадал в проект без approval. Незащищённый rollback снимает это ограничение: возврат на снимок до фикса удаляет фикс без единого подтверждения.

**Что сделать.** Выбрать один из двух путей и обосновать выбор:

- **Путь A (предпочтительный).** `files.rollback` → `GUARDED`, но сделать операцию дешёвой: перед восстановлением журнал снимает снимок текущего состояния, `restore()` перестаёт удалять снимок безвозвратно, в approval-диалог передаётся diff между текущим и восстанавливаемым содержимым.
- **Путь B.** Оставить `SAFE_CODE`, но строго сузить: только снимки, созданные в текущей сессии тем же actor id, только если после снимка не было изменений файла извне (сверка хэша), и с обязательным снятием снимка текущего состояния. Любое несовпадение → эскалация до GUARDED.

В обоих путях: расширить гейт единообразия так, чтобы он покрывал **все** инструменты, пишущие в ФС, а список выводился из реестра, а не хардкодился. Хардкод `["files.create", "files.patch"]` — сам по себе дефект: он не заметит следующий добавленный мутирующий инструмент.

**Приёмка.**
- Тест: rollback без токена (путь A) не изменяет файл на диске.
- Тест: после rollback можно откатить rollback — исходное содержимое восстановимо.
- Тест: гейт единообразия перечисляет мутирующие инструменты через интроспекцию реестра; добавление фиктивного мутирующего инструмента со `SAFE_CODE` роняет гейт.
- Негативная инъекция: вернуть `files.create` в `SAFE_CODE` → падает не менее трёх тестов (это уже работало ранее, не потеряй).

---

### D5 (medium). Два несовместимых `SidecarStatus`

**Где.** `desktop/local-agent-desktop/src-tauri/src/supervisor.rs:10` — 6 вариантов, включая `Unhealthy`. `desktop/local-agent-desktop/src-tauri/core/src/control_plane_core.rs:62` — 5 вариантов, `Unhealthy` отсутствует.

**Суть.** Состояние `Unhealthy`, которое supervisor умеет наблюдать, невыразимо в ядре. Любая передача статуса из supervisor в core обязана его куда-то схлопнуть — и схлопывание почти наверняка даст ложно-оптимистичный статус в UI.

**Что сделать.**
- Единственный источник истины — enum в `local_agent_core`. `supervisor.rs` реэкспортирует его (`pub use`), собственное определение удаляется.
- Добавить `Unhealthy` в ядро, включая `as_str()` и serde-представление.
- Проверить все `match` по статусу на неисчерпывающие ветки и на `_ =>`. Заглушка `_ =>` в match по статусу запрещена: новый вариант обязан ломать компиляцию.

**Приёмка.**
- Тест: `as_str()` покрывает все варианты, round-trip через serde для каждого.
- Тест: количество вариантов enum совпадает с количеством ветвей в `as_str()` (через явный массив `ALL: [SidecarStatus; N]`).
- Grep-гейт: ноль вхождений `enum SidecarStatus` вне ядра.

---

### D6 (medium). `stop_agent()` смешивает два автомата состояний

**Где.** `control_plane_core.rs:131–134`:

```rust
pub fn stop_agent(&mut self) {
    // Остановка текущего прогона: sidecar остаётся жив в Ready.
    self.status = SidecarStatus::Ready;
}
```

Закреплено тестом `stop_agent_keeps_sidecar_ready` (строка 218).

**Суть.** Это не опечатка — намерение задокументировано и покрыто тестом. Дефект в другом: одно поле `status` обслуживает два независимых автомата — жизненный цикл процесса sidecar и состояние текущего прогона агента. Из-за этого «остановить агента» и «sidecar здоров» неотличимы, а UI не может показать «прогон остановлен, sidecar жив» иначе как ложью в одну из сторон.

**Что сделать.**
- Разделить: `sidecar_status: SidecarStatus` и `run_state: RunState` (например `Idle | Planning | Executing | Stopped | Failed`).
- `stop_agent()` переводит `run_state` в `Stopped` и **не трогает** `sidecar_status`.
- Обновить `stop_agent_keeps_sidecar_ready`: он должен утверждать, что `sidecar_status` не изменился, а `run_state == Stopped`. Не удаляй тест — переформулируй.

**Приёмка.**
- Тест: `stop_agent()` из состояния `sidecar_status = Unhealthy` не делает его `Ready`. Это ключевой тест — именно эту ложь допускает текущий код.
- Тест: `run_state` и `sidecar_status` изменяются независимо.

---

### D7 (medium). `src-tauri/src/ipc.rs` не компилируется — модуль не подключён

**Где.** `desktop/local-agent-desktop/src-tauri/src/main.rs:6–8` объявляет только `supervisor`, `commands`, `control_plane`. Файл `src-tauri/src/ipc.rs` существует, но не входит в дерево модулей.

**Суть.** Это соответствует задекларированному пробелу INV-014, но масштаб надо назвать точно: файл не проверяет даже компилятор. Ноль гарантий любого уровня.

**Что сделать.** Одно из двух, по обстоятельствам:
- Подключить `mod ipc;` и довести до состояния «компилируется и покрыт тестами», если фаза 9 наступила.
- Либо переименовать в `ipc.rs.wip` / переместить в `docs/`, чтобы файл не создавал впечатления существующей реализации.

В любом случае — добавить гейт: каждый `.rs` в `src-tauri/src/` либо подключён как модуль, либо явно перечислен в allowlist исключений с указанием фазы.

**Приёмка.** Гейт падает, если в `src-tauri/src/` появляется `.rs`-файл, не подключённый и не внесённый в allowlist.

---

### D8 (medium). `security-negative-map.toml` противоречит сам себе

**Где.** Раздел `[meta]`: комментарий говорит «ИЗМЕРЕНО, не оценено: `pytest -m security_negative --collect-only -q` → **82**», следующая строка — `expected_count = **85**`.

**Суть.** Файл объявлен единственным источником истины по SN-таксономии и противоречит себе в двух соседних строках. `evidence/gate_security_negative.txt` показывает 85/85, значит гейт сверяется с `expected_count` и комментарий не читает — то есть устаревшая цифра в комментарии никогда не будет поймана.

**Что сделать.**
- Определить фактическое число, привести обе записи в соответствие.
- Убрать дублирование: число должно существовать в файле ровно один раз. Комментарий описывает методику, но не повторяет значение.
- Гейт: если в файле встречается число, похожее на счётчик тестов, вне поля `expected_count` — падать.

**Приёмка.** Негативная инъекция: изменить `expected_count` на ±1 → гейт падает с внятным сообщением о расхождении.

---

### D9 (medium). Недоказуемость прогона не должна выглядеть как доказанность

**Контекст.** В песочнице предыдущего цикла: `cargo test` не запускался (`linker cc not found`), `npm ci` → 403, `pytest` не установлен и не устанавливается без сети. Поэтому числа 50 (Rust) и 34 (vitest) остались заявленными.

**Что уже проверено независимо и можно считать фактом.** Структурный подсчёт сходится: `#[test]` в `core/src/*.rs` + `core/tests/*.rs` — ровно 50; `it(`/`test(` в `src/lib/*.test.ts` — ровно 34. Это доказывает существование и количество, но не прохождение.

**Что сделать.**
- Довести до реального исполнения то, что исполнимо без сети: `cargo check --tests` и `cargo clippy --tests` не требуют линковки и докажут, что все 50 тестов хотя бы компилируются и типизируются. Если тулчейн есть — выполнить и приложить вывод.
- Добавить структурный гейт, сверяющий заявленные в README числа 50/34 с фактическим подсчётом в дереве. Сейчас эти числа не охраняются ничем и разъедутся при первом же добавленном тесте.
- В README не менять формулировку «считайте 50/34 заявленными» на «доказано», пока в `evidence/` не лежит вывод реального прогона.
- `scripts/validate_contracts.py` падает на отсутствующем `jsonschema`. Это правильное fail-closed поведение, но зависимость должна быть в манифесте dev-зависимостей sidecar — проверить, что она там есть.

**Приёмка.** Гейт падает, если число `#[test]` или число `it(`/`test(` разошлось с числом в README.

---

## 2. Порядок работы

1. Сначала D2 и D3 — они самые дешёвые и разблокируют работу с каталогом.
2. Затем D1 (требует правки `Cargo.toml`, проверь, что это не ломает сборку ядра на не-Windows).
3. Затем D5 и D6 вместе — у них общий корень, раздельная правка создаст промежуточное несогласованное состояние.
4. Затем D4 — он затрагивает и политику, и журнал, и гейт.
5. D7, D8, D9 — в любом порядке.

После каждого дефекта прогоняй полный доступный набор гейтов, а не только относящийся к правке.

---

## 3. Формат сдачи

Отчёт строго по этой структуре. Без вступлений и без похвалы своей работе.

**Раздел «Закрыто».** По каждому дефекту: `D<n>` — файл:строка до и после, суть правки в двух-трёх предложениях, список добавленных тестов с настоящими именами (скопированными из кода, не восстановленными по памяти).

**Раздел «Гейты проверены на подделку».** Таблица: какая порча внесена → какой гейт упал → текст ошибки. Строка без всех трёх колонок не засчитывается.

**Раздел «Решения, принятые самостоятельно».** Каждое решение, где ты выбрал между вариантами или отступил от брифа, с обоснованием. В частности — какой путь выбран для D4 и почему.

**Раздел «Не доказано».** Всё, что осталось заявлением: чего именно не удалось запустить, по какой конкретной причине (текст ошибки), и куда это вынесено (CI-job, отдельный тикет). Числа без прогона обязаны быть помечены словом `ЗАЯВЛЕНО`.

**Раздел «Найдено сверх брифа».** Дефекты, обнаруженные по ходу. Указывай `файл:строка` и не чини их молча — сначала перечисли.

**Раздел «Расхождения с брифом».** Если какое-то утверждение этого брифа не подтвердилось при чтении кода — скажи об этом прямо и приведи фактический код. Бриф составлен по ревизии WP-1.45.1 и может расходиться с твоей.

---

## 4. Запрещено

- Помечать `[gaps]` закрытыми без кода.
- Ослаблять `CatalogGuard`, `WorkspacePolicy`, `download_guard` или список `BLOCKED_PATTERNS` ради прохождения тестов.
- Удалять тест вместо его переформулирования.
- Отчитываться числом, полученным оценкой, без пометки `ЗАЯВЛЕНО`.
- Добавлять `_ =>` в `match` по типам риска или статуса.
- Писать в `model-catalog/*.json` что-либо, кроме как через `_save_catalog` (иначе поедут байтовые инварианты).
- Менять классификацию продукта в README на production-grade.
````

### ПУТЬ: audit/donor-briefs/WP-1.45.3-engineering-brief.md (289 строк, 38271 байт)

````markdown
# WP-1.45.3 — Инженерный бриф: замыкание native-контура

**Ревизия на входе:** WP-1.45.2 (pytest 195/1 skipped, cargo 63, vitest 34 `ЗАЯВЛЕНО`, 9 гейтов зелёные).
**Продукт:** `local-agent-desktop` — Tauri v2 + Rust control plane core + Python sidecar + React frontend.
**Текущая честная классификация:** security/architecture prototype с функциональным web-демо и незамкнутым native-контуром.
**Цель работы:** снять эту формулировку правомерно — то есть закрыть INV-013, INV-014, INV-011, INV-018, INV-015 поведенческими доказательствами, а не декларациями.

---

## 0. Как читать этот бриф

Бриф написан в предположении, что вы — не первый исполнитель. Предыдущие два цикла (WP-1.45.1, WP-1.45.2) закрыли 8 + 9 дефектов и построили дисциплину доказательств. Эта дисциплина — актив дороже кода. Она формулируется в §1 и имеет приоритет над любым техническим требованием ниже: **лучше не закрыть задачу, чем закрыть её недоказуемо.**

Бриф не является планом по фазам «сверху вниз». Порядок в §3 выведен из зависимостей доказуемости: каждая следующая задача может быть доказана только после предыдущей. Отступление от порядка допустимо, но требует обоснования в отчёте.

---

## 1. Дисциплина доказательств (приоритет над всем остальным)

### 1.1. Проверка вычислением, а не чтением

Прецедент WP-1.45.2 / D2. Ревьюер объявил critical-дефект «сломанные f-строки в `catalog_hashes.py:119,133,252`, скрипт никогда не выполнялся». Дефекта не существовало: строки содержат одиночные скобки. Ошибка возникла так — grep по удвоенной скобке вернул пустой результат (правильный ответ), но следующий вывод показал строку с удвоенными скобками (артефакт отображения), и ревьюер поверил картинке против собственного отрицательного результата.

Отсюда правило: **утверждение о содержимом файла доказывается вычислением над байтами, а не визуальным чтением вывода инструмента.**

- Проверка строки — через `repr()`, коды символов, `eval` выражения из файла, хеш фрагмента. Не через «я вижу в выводе».
- Отрицательный результат поиска — это результат. Если grep не нашёл, а глаз видит, доверять надлежит grep либо перепроверить третьим независимым способом. Расхождение двух методов само по себе является находкой и должно быть отражено.
- Каждое утверждение о дефекте в отчёте сопровождается пометкой способа проверки: `[вычислено]`, `[прогон]`, `[структурно]`, `[ЗАЯВЛЕНО]`.

Добавьте этот прецедент в `docs/testing.md` отдельным разделом «Ложноположительные дефекты». Он стоит там ровно столько же, сколько прецедент с выдуманными именами тестов.

### 1.2. Гейт не работает, пока вы не видели его падение

Без изменений с WP-1.45.2, повторяю для полноты. Для каждого нового или изменённого гейта: внести порчу → зафиксировать ненулевой код возврата и текст ошибки → откатить порчу → зафиксировать зелёный прогон. Строка в таблице инъекций без всех трёх колонок (что сломали / что упало / текст ошибки) не засчитывается.

Новое требование: **инъекция должна ломать то, что гейт защищает, а не то, что он случайно задевает.** Если гейт единообразия падает от переименования файла — это не доказательство того, что он ловит понижение риска.

### 1.3. Тест обязан воспроизводить место вызова

Вывод, полученный вами в WP-1.45.2 на статистическом тесте токена: тест переиспользовал один `Instant` и потому **проходил** под инъекцией слабого источника. Обобщение: тест, который конструирует объект иначе, чем производственный код, проверяет не производственный код.

Применительно к этому циклу это критично: почти все задачи ниже касаются процессов, сокетов и таймаутов, где соблазн подменить реальный вызов моком максимален. Правило: **если тест мокает транспорт, обязан существовать парный тест, который его не мокает** — пусть медленный, пусть помеченный маркером, пусть Windows-only и пропускаемый на Linux.

### 1.4. Fail closed

При недоступности источника доверия, CSPRNG, sidecar, транспорта — отказ, а не деградация к слабому пути. Прецедент реализован правильно в D1 (`issue_at` возвращает `Err`, токен не выдаётся). Держите ту же форму везде.

### 1.5. Байтовые инварианты

LF, без BOM, ровно один финальный LF для `VERSION`, `model-catalog/*.json`, `contracts/*.json`, `invariants.toml`, `security-negative-map.toml`. INV-003 их сторожит — не обходите запись мимо `_save_catalog` и аналогов.

### 1.6. Реестр неизвестного

Заведите `docs/unverified-ledger.md`, если его нет. Каждое утверждение, которое вы не смогли доказать в этой среде, попадает туда строкой: что утверждается, почему не доказано (точный текст ошибки), какой минимальный доступ закрыл бы вопрос, в какую фазу отложено. Отчёт ссылается на реестр, а не пересказывает его.

---

## 2. Что уже закрыто и не подлежит регрессу

Перечисляю явно, потому что задачи §3 будут трогать те же файлы, и откат этих свойств — самый вероятный способ навредить.

| Свойство | Где | Как проверяется |
|---|---|---|
| Approval-токен из CSPRNG ОС, ≥192 бит, без часов и счётчика | `core/src/control_plane_core.rs`, `getrandom` | статистический тест + инъекция слабого источника |
| Сравнение токена в константном времени | `subtle::ConstantTimeEq` | тест на разную длину + `ct_eq` |
| Единственный `enum SidecarStatus` в ядре, `pub use` в супервизоре | `control_plane_core.rs`, `supervisor.rs` | `check_module_wiring.py` |
| `run_state` и `sidecar_status` — независимые автоматы | там же | `stop_agent_does_not_heal_unhealthy_sidecar` |
| `files.rollback` GUARDED, откат обратим, `rollback_preview` READ_ONLY | `safety_review.py`, `tools/rollback.py` | тест симметричности + гейт единообразия |
| Список мутирующих инструментов выводится из реестра интроспекцией | `test_tools_and_executor.py::discover_fs_mutating_tools` | инъекция нового инструмента `files.truncate` со SAFE_CODE |
| `lfs.oid` — evidence, не authority; sha256 считается локально | `catalog_hashes.py`, `SEED-fill-hashes.json` | гейт на возврат формулировки |
| Каждый `.rs` в `src-tauri/src/` — либо подключённый модуль, либо в allowlist | `check_module_wiring.py` | инъекция висячего файла |
| Число в карте SN существует ровно один раз (`expected_count`) | `security-negative-map.toml` | гейт на посторонние числа |

**Особое внимание к строке про allowlist.** Задача E2 возвращает `ipc.rs` в дерево. Возврат обязан пройти через `mod ipc;`, а не через расширение allowlist. Если по итогам E2 в allowlist окажется что-то кроме `main.rs` — это регресс D7, а не решение.

---

## 3. Задачи

Девять задач, E0…E8. Каждая: **Зачем → Что сделать → Приёмка → Инъекция**.

---

### E0. Воспроизводимость доказательств (делается первой, всегда)

**Зачем.** Сейчас `cargo test 63 passed` и `pytest 195 passed` опираются на `evidence/cargo_run.txt` и `evidence/pytest_run.txt` — файлы, которые проверяющий не может пересоздать. Это не подлог, но это доверие к автору, а весь проект построен на отказе от доверия к заявлениям. Пока прогон невоспроизводим, все остальные доказательства этого цикла наследуют его хрупкость. Отдельно: `vitest 34` остаётся `ЗАЯВЛЕНО` из-за 403 на `zustand` — единственный контур без прогона вообще.

**Что сделать.**

1. **Провенанс evidence.** Каждый файл в `evidence/` получает шапку: команда целиком, версия тулчейна (`rustc -Vv`, `python -V`, `node -v`), хеш дерева исходников на момент прогона (например, `git rev-parse HEAD` либо детерминированный хеш списка файлов с их sha256), дата, платформа. Гейт `check_evidence_provenance.py`: файл без полной шапки, либо с хешем дерева, не совпадающим с текущим, помечает evidence как устаревший и роняет сборку. Устаревший evidence опаснее отсутствующего — он выглядит как доказательство.
2. **Тулчейн зафиксирован.** `rust-toolchain.toml` с точной версией. Для C-линкера: способ, найденный вами через `ziglang` из PyPI, задокументировать в `docs/testing.md` как поддерживаемый путь для окружений без `cc` — с оговоркой, что это путь верификации, а не сборки релиза.
3. **vitest без сети.** Три варианта, выбрать и обосновать: (а) вендоринг `node_modules` в архив либо в отдельный tarball с зафиксированными хешами; (б) `npm ci --offline` из заранее сформированного кеша; (в) замена `zustand` на локальный минимальный store, если зависимость используется поверхностно — проверить фактическое использование прежде чем предлагать. Если ни один недоступен, `vitest 34` остаётся `ЗАЯВЛЕНО`, но в реестре §1.6 появляется строка с точным текстом 403 и указанием, какой доступ закрывает вопрос.
4. **`check_docs_sync.py` не должен падать от отсутствия pytest.** Разделите: отсутствие сборщика — это `[SKIP]` с явной пометкой «сверка чисел не выполнена», а не `[FAIL]` и не `[OK]`. Третье состояние обязано существовать и быть видимым, иначе оно схлопнется в одно из двух ложных.

**Приёмка.** `python scripts/check_evidence_provenance.py` зелёный. Изменение любого исходника без перепрогона роняет его. `docs/testing.md` содержит воспроизводимую инструкцию для окружения без сети и без `cc`.

**Инъекция.** Поменять один байт в `core/src/risk.rs` → гейт провенанса падает с указанием, какой evidence устарел. Удалить строку версии тулчейна из шапки → падает.

---

### E1. INV-013: sidecar действительно запускается (фаза 8)

**Зачем.** `supervisor.rs` содержит только статусную модель: нет `Command::new`, нет PID, нет handshake, нет readiness probe. Всё остальное в native-контуре разговаривает с несуществующим процессом. Это корень; без него E2…E4 недоказуемы.

**Что сделать.**

1. Порождение процесса sidecar: `tokio::process::Command`, путь к интерпретатору и модулю резолвится явно и валидируется до запуска (существование, что это файл, что путь внутри установочного каталога). Никакого `shell=true`-эквивалента, никакой конкатенации аргументов в строку.
2. Handshake: после старта sidecar обязан прислать сообщение готовности с версией протокола. Несовпадение версии — отказ и `SidecarStatus::Failed`, а не «попробуем работать».
3. Readiness probe с таймаутом. Таймаут — константа с обоснованием в комментарии, не магическое число.
4. Завершение: при закрытии приложения процесс обязан умереть. На Windows — Job Object с `KILL_ON_JOB_CLOSE`; на Unix — process group и `SIGTERM` с эскалацией до `SIGKILL` по таймауту. Сирота после закрытия приложения — дефект того же класса, что утечка секрета: он переживает сессию.
5. Перезапуск: увязать с существующей `RestartPolicy` (`MAX_RESTARTS`, `RESTART_WINDOW`), не изобретать вторую.
6. `Unhealthy` наконец получает производителя: probe провалился, но процесс жив. Сейчас вариант существует в enum и недостижим — это тоже форма лжи в типе.

**Приёмка.**
- Тест: запуск фиктивного sidecar (скрипт-заглушка на Python, лежащий в тестовых данных), проверка что PID известен, handshake прошёл, статус `Ready`.
- Тест: sidecar молчит → по таймауту `Unhealthy`, затем перезапуск по политике, затем `Failed` после исчерпания.
- Тест: sidecar присылает неверную версию протокола → `Failed`, работа не начинается.
- Тест: после `drop` супервизора процесс завершён (проверка через ожидание exit-кода, не через `sleep`).
- Разделение по платформам явное: Windows-специфичные тесты помечены и пропускаются на Linux **с видимой причиной**, а не молча.

**Инъекция.** Убрать ожидание handshake → тест версии протокола падает. Убрать завершение процесса → тест сироты падает.

---

### E2. INV-014: IPC-транспорт замкнут (фаза 9)

**Зачем.** Python-сторона полная — 30 типов сообщений и рабочий цикл. Rust-стороны нет: `ipc.rs` был удалён в D7 именно потому, что не был подключён. Теперь он возвращается, но подключённым.

**Что сделать.**

1. `mod ipc;` в `main.rs`. Allowlist `check_module_wiring.py` остаётся `['main.rs']`.
2. Framing переиспользовать из ядра (`core/src/framing.rs`), не дублировать. Дубль framing — тот же класс дефекта, что дубль `SidecarStatus`.
3. Correlation ID: каждый запрос получает идентификатор, ответ без известного ID отбрасывается с логом, ответ на уже завершённый запрос отбрасывается. Гонка «ответ пришёл после таймаута» обязана быть покрыта тестом, а не рассуждением.
4. Таймауты на каждый запрос. Отсутствие таймаута — это не «работает медленно», это зависание UI.
5. Границы размера сообщения: максимум, при превышении — отказ и разрыв, а не аллокация по заявленной длине. Заявленная длина — это evidence от другой стороны, не authority (тот же класс SN-NA-006).
6. Контракты: `contracts/*.json` — источник истины для формы сообщений; `validate_contracts.py` обязан проверять обе стороны. Сейчас он падает на отсутствии `jsonschema` — внесите зависимость в dev-манифест sidecar.

**Приёмка.**
- Round-trip тест через реальный транспорт с заглушкой sidecar: запрос → ответ, ID совпал.
- Тест: ответ с чужим correlation ID отброшен, состояние не повреждено.
- Тест: заявленная длина больше лимита → соединение закрыто, аллокации нет.
- Тест: запрос без ответа → таймаут, состояние вернулось в консистентное.
- Тест: частичный фрейм, разорванный на границе чтения, собирается корректно.
- `validate_contracts.py` зелёный, обе стороны сверены с одной схемой.

**Инъекция.** Снять проверку лимита длины → тест OOM-защиты падает. Убрать `mod ipc;` → `check_module_wiring.py` падает (это уже проверено в D7, но перепроверьте после возврата файла).

---

### E3. INV-018 + INV-012: approval-цепочка сквозная (фаза 6)

**Зачем.** Сейчас Rust выдаёт токен, frontend его отбрасывает, Rust не consume-ит его при исполнении. Токен привязан только к имени инструмента. Это значит: подтверждение на `files.patch` файла А позволяет исполнить `files.patch` файла Б. Криптостойкость токена, полученная в D1, при этом не спасает — она защищает от подделки, но не от подмены контекста.

**Что сделать.**

1. Токен привязывается к **digest входа** (канонизированный JSON аргументов, устойчивый к перестановке ключей), **workspace** и **session**. Формула привязки и способ канонизации задокументированы в `docs/security-model.md`.
2. Rust — единственный issuer и единственный consumer. Frontend переносит непрозрачную строку и не интерпретирует её. Python не выдаёт и не проверяет approval-токены Rust-контура.
3. Consume при исполнении: `run_tool_call` обязан предъявить токен, Rust сверяет привязку, потребляет одноразово, при несовпадении — отказ.
4. Понятие session появляется здесь. Это несёт actor identity, которой не хватило для пути B в D4 — после E3 вернитесь к решению D4 и зафиксируйте в `docs/security-model.md`, меняется ли оно (моё ожидание: не меняется, GUARDED остаётся; но решение обязано быть перепринято явно, а не унаследовано молчанием).
5. Тайминг: `HashMap::remove` уже поправлен. После привязки к digest сравниваются длинные значения — перепроверьте, что константное время сохранено на всём пути сравнения, включая сверку digest.

**Приёмка.**
- Тест: токен, выданный на `files.patch` пути А, отвергнут для пути Б.
- Тест: токен, выданный в одной сессии, отвергнут в другой.
- Тест: перестановка ключей в аргументах не меняет digest; изменение значения — меняет.
- Тест: повторное использование токена отвергнуто.
- Тест: истёкший токен отвергнут (TTL уже есть — 300 с).
- Сквозной тест: frontend → Rust → sidecar → исполнение, где на каждом стыке проверяется, что токен не потерян и не подменён.

**Инъекция.** Убрать digest из привязки → падает тест подмены пути. Разрешить consume дважды → падает тест повторного использования.

---

### E4. INV-011: паритет команд и де-заглушка (фаза 11)

**Зачем.** Три команды frontend не зарегистрированы (`chat`, `hf_search`, `hf_files`) → в native-режиме `command not found`. Четыре команды — заглушки: `runtime_health`, `list_models`, `request_plan`, `run_tool_call` возвращают пустой либо отражённый JSON. Заглушка, неотличимая от реализации, хуже отсутствия: она даёт ложный зелёный.

**Что сделать.**

1. Гейт паритета: множество имён в `invoke(...)` на фронтенде == множество в `generate_handler!`. Извлечение имён — парсингом, не регуляркой по всему файлу; регулярка на этом уже один раз дала пустой результат и молчаливо не проверила ничего.
2. Реализовать три недостающие команды либо явно удалить их вызовы с фронтенда. Третьего не дано — «пока не поддерживается» должно быть выражено в коде, а не в его отсутствии.
3. Заглушки: каждая либо реализуется через IPC (после E2 это возможно), либо возвращает явную типизированную ошибку `NOT_IMPLEMENTED` с указанием фазы. Отражённый JSON запрещён.
4. Гейт на заглушки: команда, тело которой не обращается к sidecar и не возвращает `NOT_IMPLEMENTED`, — падение с указанием имени.

**Приёмка.** Гейт паритета зелёный и проверен инъекцией в обе стороны: команда добавлена на фронт без регистрации → падает; команда зарегистрирована без вызова → падает (либо предупреждение с обоснованием, почему асимметрия допустима).

**Инъекция.** Вернуть отражённый JSON в `list_models` → гейт заглушек падает.

---

### E5. INV-015: UI не показывает успех без события backend (фаза 14)

**Зачем.** Download и старт движка симулируются: `Math.random()` вместо прогресса, `port: 8090` без spawn-а. Это единственный класс дефектов, который видит пользователь и не видит ни один текущий гейт. Ложный «Ready» на экране — это то, ради чего вся дисциплина доказательств и существует, только на уровне продукта.

**Что сделать.**

1. Инвентаризация: каждое место в UI, где состояние успеха/прогресса порождается локально, а не приходит событием. Список — в отчёт, полностью.
2. Прогресс загрузки — только из реальных байтов. `Math.random()` в путях состояния запрещён гейтом (grep по `Math.random` в `src/` вне явно помеченных декоративных мест с обоснованием в комментарии).
3. Статусы `Ready` / `Experimental` / `Not installed` / `Requires confirmation` вычисляются из состояния backend. Неизвестное состояние отображается как неизвестное, а не как `Not installed` — второе выглядит как знание.
4. Тесты vitest на то, что компонент не переходит в успех без соответствующего события. Это тестируемо без сети и должно быть покрыто даже при `ЗАЯВЛЕНО`-статусе прогона.

**Приёмка.** Гейт `Math.random` зелёный. Тесты состояний присутствуют структурно; при доступном прогоне — проходят.

**Инъекция.** Вернуть `Math.random()` в прогресс → гейт падает с указанием файла и строки.

---

### E6. INV-010: анализ async-тел по AST (фаза 11)

**Зачем.** Текущая проверка — эвристика по тексту, `enforcement_gap` признан в реестре. Она не обнаруживает блокирующие вызовы внутри async-тела, то есть INV-001 держится на честном слове. После E1/E2 в коде появится настоящий async-ввод-вывод, и цена ошибки вырастет.

**Что сделать.** Разбор `src-tauri/**/*.rs` по AST (`syn` в отдельном dev-инструменте либо внешний парсер), поиск `std::thread::sleep`, синхронного файлового ввода-вывода, `block_on`, тяжёлых вычислений (sha256) внутри `async fn` без `spawn_blocking`. Список запрещённых вызовов — таблица в `docs/testing.md`, расширяемая.

**Приёмка.** Инъекция `std::thread::sleep` в async-команду → гейт падает с файлом и строкой. Тот же вызов в синхронной функции → не падает (иначе гейт ловит не то, что защищает, — см. §1.2).

---

### E7. Остаточные дефекты

1. **`approved_models.json` не читается кодом (P1-8).** Файл существует, выглядит как источник политики, но ни на что не влияет. Либо подключить как источник, либо удалить. Неиспользуемый файл политики — это будущая уязвимость: кто-то отредактирует его в уверенности, что что-то изменил.
2. **`RollbackJournal`** — вы начали фиксировать остаточную проблему и не дописали. Опишите её полностью и закройте либо внесите в реестр §1.6 с обоснованием отсрочки.
3. **Тесты, добавленные под несуществующий D2.** Инъекция сломанной f-строки роняет 6 тестов — но защищают ли они реальный инвариант (корректность URL, отказ на скобки в хосте, запрет мутабельного `/resolve/main/`) или сторожат фантом? Оставить только то, что защищает свойство; провенанс честно указать: тесты появились по ложному сигналу, но свойство закрывают настоящее. Это нормальный исход, скрывать его не нужно.
4. **`enforcement_gap` INV-004** — покрыто 5 из 10 классов таблицы `security-model.md`. Довести либо явно перенести с указанием фазы.
5. **INV-008** — junction/reparse points на Windows не покрыты. Связано с E8.

---

### E8. Windows: реестр непроверяемого

**Зачем.** Продукт заявлен Windows-first, вся верификация идёт на Linux, один тест пропускается как Windows-only. Разрыв между целевой платформой и платформой доказательства сейчас нигде не измерен.

**Что сделать.** Таблица в `docs/testing.md`: свойство → проверено на Linux → требует Windows → чем заменено сейчас. Минимум обязаны попасть: Job Object и завершение процесса (E1), junction/reparse points (INV-008), пути и регистр файловой системы, разделитель путей в `WorkspacePolicy`, поведение именованных каналов, если IPC на них (E2). Каждый пропускаемый тест обязан печатать причину пропуска — пропуск без причины неотличим от отсутствия теста.

---

## 4. Порядок и зависимости

```
E0 (провенанс) ─── обязательно первым, иначе всё дальнейшее недоказуемо
     │
     ├── E1 (процесс) ── E2 (транспорт) ── E3 (approval сквозной) ── E4 (паритет команд)
     │                        │
     │                        └── E6 (AST async) — после появления реального async I/O
     │
     ├── E5 (UI) — независима, можно параллельно
     └── E7, E8 — в любой момент
```

После каждой задачи прогонять полный доступный набор гейтов, а не только относящийся к задаче. Регресс обнаруживается соседним гейтом чаще, чем своим.

---

## 5. Формат сдачи

### 5.1. Закрыто
По каждой задаче: `файл:строка` до → после, имена тестов **скопированные из кода**, не восстановленные по смыслу. Числа прогонов с пометкой способа получения.

### 5.2. Гейты проверены на подделку
Таблица: что сломали → какой гейт упал → текст ошибки. Плюс новая колонка: **что гейт защищает** — и проверка, что сломанное относится к защищаемому (§1.2).

### 5.3. Решения, принятые самостоятельно
Каждое: варианты, выбранный, причина, что стало бы аргументом против. Обязательно включить перепринятое решение по D4 после появления session (§E3.4).

### 5.4. Не доказано
Ссылка на `docs/unverified-ledger.md`. В отчёте — только сводка: сколько строк, какие из них блокируют снятие текущей классификации продукта.

### 5.5. Найдено сверх брифа
Отдельно: находки, аналогичные `check_docs_sync.py:111` (гейт, искавший литералы в собственном коде) и `check_invariants.py`, не резолвившему unit-тесты в `core/src/*.rs`. Гейт, который не работает, но печатает зелёный, — самый дорогой класс дефекта в этом проекте.

### 5.6. Расхождения с брифом
Если утверждение из §2 или §3 не воспроизводится — предъявите вычисление (§1.1) и опровергните. Прецедент D2 показывает, что бриф ошибается; молчаливая подстройка под ошибочный бриф хуже открытого спора.

### 5.7. Классификация продукта
В конце отчёта — прямой ответ: правомерно ли снимать формулировку «security/architecture prototype с незамкнутым native-контуром». Если нет — что именно осталось. README менять только вместе с этим ответом и только в сторону, подтверждённую доказательствами.

---

## 6. Запрещено

- Закрывать `enforcement_gap` или строку реестра без кода.
- Ослаблять `CatalogGuard`, `WorkspacePolicy`, `download_guard`, `BLOCKED_PATTERNS`, риск-уровни инструментов ради зелёного.
- Удалять тест вместо переформулировки.
- Расширять allowlist `check_module_wiring.py` вместо подключения модуля.
- Дублировать framing, статусные enum, риск-реестр — источник истины один.
- Возвращать отражённый JSON или пустой ответ там, где ожидается работа с sidecar.
- Сообщать оценки без пометки `ЗАЯВЛЕНО`.
- `_ =>` в match по риску, статусу и состоянию прогона.
- Писать в `model-catalog/*.json` мимо `_save_catalog`.
- Менять классификацию продукта в README без §5.7.
````

### ПУТЬ: audit/donor-briefs/WP-1.45.4-engineering-brief.md (188 строк, 22612 байт)

````markdown
# WP-1.45.4 — Инженерный бриф: сквозной продуктовый путь и запускаемый артефакт

**Ревизия на входе:** WP-1.45.3. pytest 195/1 `[прогон]`, cargo 91 `[прогон]`, vitest 34 `[ЗАЯВЛЕНО]`, гейты зелёные, провенанс evidence работает.
**Сделано:** E0 (провенанс), E1 (жизненный цикл процесса), E2 (IPC-транспорт), E4 (паритет команд).
**Не сделано:** E3 (сквозной approval), E5 (UI не лжёт), E6 (AST async), E7 (остатки), E8 (Windows-реестр — частично).
**Цель этого цикла:** закрыть INV-023 и INV-018 так, чтобы **появился запускаемый артефакт**, который прогоняет продуктовый путь целиком и печатает наблюдаемый транскрипт.

---

## 0. Бюджет и приоритет

Бюджет ограничен. Порядок ниже — не пожелание, а последовательность точек остановки. Остановитесь на любой из них — результат останется связным.

```
F1  связывание ControlPlane ↔ sidecar   → снимает NOT_IMPLEMENTED (INV-023)
F2  approval сквозной                    → INV-018 + закрывает вопрос D4
F3  smoke-harness (ЗАПУСКАЕМЫЙ АРТЕФАКТ) → главная цель цикла
——— минимально достаточный результат цикла ———
F4  preflight + воспроизводимая сборка desktop
F5  UI не лжёт (INV-015)
F6  AST async (INV-010) + остатки E7
```

Если бюджет кончается посреди задачи — **не начинайте следующую**, а доведите текущую до зелёных гейтов и обновлённого evidence. Половина задачи без evidence хуже, чем неначатая: она ломает провенанс и делает все остальные числа устаревшими.

---

## 1. Дисциплина (кратко, полная версия — WP-1.45.3 §1 и `docs/testing.md`)

1. **Проверка вычислением, не чтением.** Пометки `[прогон]` / `[вычислено]` / `[структурно]` / `[ЗАЯВЛЕНО]` обязательны.
2. **Гейт не работает, пока не видели его падение**, и инъекция обязана ломать именно защищаемое свойство. Прецедент WP-1.45.3: `sigterm_ignoring_sidecar_is_escalated_to_kill` проходил после удаления эскалации, потому что заглушка умирала раньше на мягком шаге.
3. **Тест воспроизводит место вызова.** Мокаете транспорт — должен быть парный тест без мока.
4. **Fail closed.**
5. **Байтовые инварианты** (LF, без BOM, один финальный LF).
6. **Недоказанное — в `docs/unverified-ledger.md`**, с точным текстом ошибки.
7. **Обновляйте evidence после каждой задачи** (`scripts/refresh_evidence.py`), иначе `check_evidence_provenance.py` станет красным и будет прав.

Среда известна заранее — не тратьте бюджет на переоткрытие: сети нет (npm-реестр целиком 403, U-001), `webkit2gtk` нет и `src-tauri` не собирается (U-002), C-линкер — только через `ziglang` из PyPI.

---

## 2. F1 — ControlPlane владеет sidecar и проксирует команды (INV-023)

**Состояние.** E1 дал `SupervisedSidecar`, E2 дал `IpcClient`, E4 убрал отражённый JSON. Связывания нет: семь команд возвращают `NOT_IMPLEMENTED:<команда>:phase-10`. Детали готовы, механизм не собран.

**Что сделать.**

1. `ControlPlane` владеет `Option<SupervisedSidecar>` и его `IpcClient`. Жизненный цикл: `start_sidecar()` / `restart_sidecar()` / `Drop`. Сирот не остаётся — свойство уже доказано в E1, не потеряйте его при переносе владения.
2. Каждая из семи команд превращается в запрос IPC с уже объявленным типом сообщения (`runtime.health.request`, `model.list.request`, `agent.plan.request`, `tool.call.request`, `chat.request`, `hf.search.request`, `hf.files.request`). Типы уже зафиксированы в `not_implemented(...)` — используйте их, не изобретайте новые.
3. **Состояния отказа типизированы и различимы.** Минимум четыре: sidecar не запущен, sidecar `Unhealthy`, таймаут запроса, sidecar вернул ошибку протокола. Схлопывание в одну строку «ошибка» запрещено: разные причины требуют разных действий от пользователя.
4. `NOT_IMPLEMENTED` остаётся только там, где sidecar действительно не умеет обработать запрос. Проверьте по Python-стороне, какие из семи типов реально обслуживаются; для необслуживаемых обновите фазу в сообщении, а не оставляйте phase-10.
5. Обновить INV-023 в `invariants.toml`: либо закрыт, либо `enforcement_gap` сужен до фактического остатка.

**Приёмка.**
- Интеграционный тест против **реального sidecar** (не заглушки): `runtime_health` возвращает ответ Python-стороны. Если запуск настоящего sidecar в тесте невозможен — обоснуйте и внесите в реестр; замена моком без парного не-мокового теста не засчитывается (§1.3).
- Тест на каждое из четырёх состояний отказа, проверяющий **различимость**, а не факт ошибки.
- `check_command_parity.py` расширен: команда с `NOT_IMPLEMENTED` без соответствующей строки в `invariants.toml` с указанием фазы — падение.

**Инъекция.** Убить sidecar между запуском и запросом → команда возвращает состояние «не запущен», а не виснет и не паникует. Заменить тип сообщения на несуществующий → ошибка протокола, а не таймаут.

---

## 3. F2 — Approval сквозной (INV-018, бывшая E3)

**Состояние.** Токен криптостоек (D1: `getrandom`, ≥192 бит, `ct_eq`, одноразовый, TTL 300 с), но привязан **только к имени инструмента**. Подтверждение `files.patch` для файла А разрешает `files.patch` файла Б. Криптостойкость от этого не защищает: она против подделки, а здесь подмена контекста.

**Что сделать.**

1. Привязка токена к тройке: **digest входа**, **workspace**, **session**.
   - Digest: sha256 по каноническому представлению аргументов. Канонизация: сортировка ключей, без незначащих пробелов, числа в одной форме, UTF-8. **Алгоритм описать в `docs/security-model.md` до реализации** — канонизация, о которой две стороны договариваются неявно, ломается первой.
   - Session: идентификатор из CSPRNG, живёт от старта до завершения `ControlPlane`. Перезапуск sidecar **не** меняет session; перезапуск приложения — меняет. Обоснуйте выбор явно.
2. Rust — единственный issuer и consumer. Frontend переносит непрозрачную строку и не интерпретирует её. Python не выдаёт и не проверяет Rust-токены.
3. `run_tool_call` предъявляет токен; Rust сверяет всю тройку в константном времени, потребляет одноразово, при любом несовпадении — отказ без исполнения.
4. **Закрыть вопрос D4.** Сейчас он помечен вами как «подлежит перепринятию», потому что session не было. После п.1 она есть — примите решение явно и запишите в `docs/security-model.md`: остаётся ли `files.rollback` GUARDED или переходит на путь B (SAFE_CODE только для снимков той же сессии и того же actor). Ожидание брифа: GUARDED остаётся, потому что откат теперь обратим и цена подтверждения низка; но решение ваше, а ожидание не является аргументом.
5. Обновить INV-012 (`enforcement_gap` про «только имя инструмента») и INV-018.

**Приёмка** (каждый пункт — отдельный тест):
- токен для пути А отвергнут для пути Б;
- токен из другой сессии отвергнут;
- токен для другого workspace отвергнут;
- перестановка ключей digest не меняет, изменение значения — меняет;
- повторный consume отвергнут;
- истёкший отвергнут;
- сквозной: выдача → перенос → consume → исполнение в sidecar, токен не потерян.

**Инъекция.** Убрать digest из привязки → падает тест подмены пути. Разрешить двойной consume → падает тест повтора. **Проверьте по §1.2**, что каждый тест падает по причине, относящейся к предмету, а не потому что сломалась компиляция.

---

## 4. F3 — Запускаемый артефакт: `lad-smoke` (главная цель)

**Зачем.** Собрать desktop-приложение в этой среде невозможно: нет `webkit2gtk` (U-002), npm-реестр закрыт целиком (U-001). Но «нельзя собрать GUI» ≠ «нельзя запустить продуктовый путь». Крейт `core` собирается и прогоняется через zig-линкер, sidecar запускается. Значит, весь путь ниже GUI проверяем бинарником.

**Что сделать.** Отдельный bin-target в крейте `core` (не в `src-tauri`, иначе не соберётся): `src/bin/lad_smoke.rs`.

Сценарий, каждый шаг печатает наблюдаемый результат:

```
[ 1] запуск sidecar          → PID, версия протокола из handshake
[ 2] readiness probe          → статус, мс до готовности
[ 3] runtime.health           → ответ sidecar целиком
[ 4] model.list               → число моделей, источник каталога
[ 5] set_workspace во временный каталог
[ 6] READ_ONLY-инструмент (files.read)      → исполнен без approval
[ 7] GUARDED-инструмент без токена          → ОТКЛОНЁН (ожидаемо)
[ 8] выдача approval-токена               → длина, префикс, привязка
[ 9] тот же токен с ДРУГИМИ аргументами   → ОТКЛОНЁН (F2)
[10] токен с верными аргументами           → исполнено, файл изменён
[11] повтор того же токена               → ОТКЛОНЁН (одноразовость)
[12] попытка выйти за workspace          → ОТКЛОНЁН (WorkspacePolicy)
[13] rollback_preview → rollback с approval  → файл восстановлен
[14] повторный rollback                    → вернулся к состоянию до отката (симметрия D4)
[15] завершение                          → PID мёртв, сирот нет
```

**Правила для harness — важнее самого harness.**

- **Печатает только наблюдённое.** Ни одной строки статуса, которая печатается безусловно. Это тот же дефект, что INV-015 в UI, только в терминале.
- **Ожидаемые отказы — часть успеха.** Шаги 7, 9, 11, 12 обязаны быть отклонены. Если шаг 7 прошƑ4 — это ПРОВАЛ прогона, а не «неожиданный успех».
- **Код возврата:** 0 — все 15 шагов дали ожидаемый исход; 1 — любое расхождение; 2 — не удалось дойти до первого шага (среда). Три состояния, как в `check_docs_sync.py`.
- **Работает во временном каталоге**, ничего не пишет в дерево проекта, убирает за собой даже при падении.
- **Не дублирует логику продакшена.** Вызывает те же функции `ControlPlane`, что и команды Tauri. Если harness ходит своим путём — он проверяет себя (§1.3).

**Приёмка.**
- `evidence/smoke_run.txt` с полным транскриптом и шапкой провенанса; внести в `EXPECTED_EVIDENCE`.
- Инструкция запуска в `README.md` и `docs/testing.md` — одной командой, с указанием zig-линкера для сред без `cc`.
- Шаги 6–14 проходят через настоящий sidecar, а не через `stub_sidecar.py`. Заглушка допустима только для шагов 1, 2, 15 в отдельном режиме `--stub`, и это должно быть видно в транскрипте.

**Инъекция.** Снять проверку approval в исполнителе → шаг 7 проходит, harness возвращает 1 с указанием шага. Снять `WorkspacePolicy` → падает шаг 12.

---

## 5. F4 — Preflight и воспроизводимая сборка desktop

**Зачем.** Собрать приложение должен смочь владелец машины с сетью и WebKit. Сейчас нет способа узнать заранее, чего не хватает, кроме как запустить сборку и ждать ошибки компоновщика.

**Что сделать.** Расширить `scripts/doctor.py` до preflight, который проверяет и печатает таблицей: Rust-тулчейн и версия, C-линкер (или zig), `webkit2gtk` / WebView2, Node и доступность реестра, Python и версия, наличие sidecar-зависимостей. Каждая строка: что нужно, что найдено, **что именно сломается без этого**, команда установки. Три состояния: `ok` / `missing` / `unknown`. `unknown` не схлопывать в `missing`.

Затем `scripts/build.sh` и `build.ps1`: вызывают preflight, при `missing` останавливаются с объяснением, не начиная долгую сборку, которая всё равно упадёт.

**Приёмка.** Прогон preflight в этой среде попадает в `evidence/preflight.txt` и честно показывает `missing` для WebKit и npm — это не провал, а ожидаемый результат, совпадающий с U-001/U-002. Строки preflight и строки реестра не должны противоречить друг другу — добавьте гейт, сверяющий их.

---

## 6. F5 — UI не лжёт (INV-015)

1. Инвентаризация всех мест, где успех или прогресс порождается на клиенте. Список целиком — в отчёт.
2. Прогресс загрузки — только из реальных байтов. Гейт на `Math.random` в путях состояния.
3. Неизвестное состояние отображается как неизвестное, а не как `Not installed`. Второе выглядит как знание — та же ошибка, что схлопывание `[SKIP]` в `[OK]`.
4. Семь команд, если после F1 часть из них всё ещё `NOT_IMPLEMENTED`, обязаны показываться в UI как `Experimental` с указанием фазы, а не как рабочие кнопки.
5. Тесты vitest пишутся, даже если прогон недоступен (U-001): структурный гейт учтёт их число, а CI на Windows прогонит.

---

## 7. F6 — AST async и остатки

1. **INV-010.** Разбор `.rs` по AST: `std::thread::sleep`, синхронный файловый I/O, `block_on`, sha256 внутри `async fn` без `spawn_blocking`. Проверка по §1.2: тот же вызов в синхронной функции гейт ронять НЕ должен.
2. **`approved_models.json` не читается кодом (P1-8).** Либо подключить как источник, либо удалить. Файл политики, ни на что не влияющий, — будущая уязвимость: его отредактируют в уверенности, что что-то изменили.
3. **CI и код 3.** `.github/workflows/ci.yml:119` вызывает `check_docs_sync.py` без обработки кода возврата, хотя сам скрипт (строки 108–110) отдаёт решение вызывающей стороне. В CI pytest есть, поэтому ветка не срабатывает — это латентно, не активно. Выразите намерение явно в `ci.yml`.
4. **INV-004** — 5 из 10 классов `security-model.md`. Довести либо перенести с фазой.
5. **`RollbackJournal`** — остаточная проблема, о которой вы начали писать в WP-1.45.2 и не дописали. Опишите полностью и закройте либо внесите в реестр.

---

## 8. Формат сдачи

Сжато — бюджет нужнее на код.

1. **Закрыто** — по задачам, `файл:строка`, имена тестов из кода, числа с пометкой способа.
2. **Транскрипт `lad-smoke`** — целиком, без сокращений. Это главный артефакт цикла.
3. **Инъекции** — таблица: что сломали / что упало / текст ошибки / **что гейт защищает**. Отдельно — инъекции, которые **не упали** с первого раза: в прошлом цикле это был лучший результат.
4. **Решения** — варианты, выбор, причина. Обязательно: итоговое решение по D4.
5. **Не доказано** — ссылка на реестр, сводка числами.
6. **Сверх брифа** и **расхождения с брифом** — прецедент D2 показывает, что бриф ошибается; опровергайте вычислением.
7. **Классификация** — правомерно ли менять формулировку в README, и почему. Менять только в сторону, подтверждённую доказательствами. Запускающийся `lad-smoke` с кодом 0 — сильный аргумент, но он не покрывает GUI (U-002), packaged binary (U-003) и Windows (U-004).

---

## 9. Запрещено

- Печатать в harness строку успеха, не следующую из наблюдения.
- Заменять настоящий sidecar заглушкой в шагах 3–14 без пометки в транскрипте.
- Ослаблять `CatalogGuard`, `WorkspacePolicy`, `download_guard`, `BLOCKED_PATTERNS`, риск-уровни.
- Удалять тест вместо переформулировки; расширять allowlist вместо подключения модуля.
- Дублировать framing, статусные enum, риск-реестр, логику approval.
- Класть новый код в `src-tauri`, который здесь не компилируется (U-002), если он может жить в `core`.
- Сообщать числа без пометки способа; менять классификацию без §8.7.
- Оставлять evidence необновлённым после изменения кода.
````

### ПУТЬ: audit/donor-screen-port-matrix.md (63 строк, 6071 байт)

````markdown
# Local Agent Desktop WP-1.45.4 screen disposition

Source studied as a visual and UX reference only:
`audit/donor-briefs/lad-wp1454.tar.gz`.

The React components, Zustand store, mock bridge, timer-driven states, static
catalog authority, browser speech recognition, and client-generated evidence
are not ported. LocalComet's Svelte stores, typed bridges, Tauri commands, and
hash-pinned artifact catalogs remain authoritative.

Reviewed against the extracted WP-1.45.4 snapshot on 2026-07-26 before the
ADAPT surfaces below were completed.

| Donor area | Disposition | LocalComet decision |
| --- | --- | --- |
| AppShell | ADAPT | **Owner-directed override:** reproduce the donor's visual shell in Svelte: 224 px labelled application navigation on wide screens, 208 px conversation column, 48 px header, compact typography, flat translucent surfaces, donor palette, borders, radii, focus and responsive states. Existing Svelte routing, stores, drawers, accessibility and real Control Plane status remain canonical. React/Zustand behavior is rejected. |
| Command Center | ADAPT | **Owner-directed override:** reproduce the donor's centered 768 px chat composition, compact runtime/model bar, message bubble geometry, empty state and composer styling around the existing real managed-model turns, validated streaming events, cancellation, native selected files and diagnostics. Donor fake streaming, random telemetry, planner/tool simulation, timer states, browser attachments and voice behavior remain rejected. |
| ModelHub | SUPERSEDED | `ModelManagerSection` and artifact-acquisition state use embedded hash-pinned catalogs, exact byte progress, validation, removal, and managed-runtime readiness. The donor static catalog, RAM slider, timer downloads, and mutable Hugging Face flow are rejected. |
| Donor model picker | SUPERSEDED | `ModelSetupDrawer` and the managed-model controls already expose real loopback probes, discovered models, approved managed artifacts, runtime startup, and binding. Browser hardware guesses and artificial scan/recommendation states are rejected. |
| Onboarding | SUPERSEDED | The Svelte setup workspace now derives its checklist only from control-plane, approved-artifact, managed-runtime, and model-binding state. Unknown values remain explicit; no persisted completion, persona, hardware, or app-data claim is introduced. |
| Plan Review | DEFER | There is no canonical desktop planner request, typed executable plan, correlated step execution, or tool-result path. Rust approval grants do not dispatch tools. The donor token-discarding execution path is REJECTED. The existing Knowledge Review Center is a separate feature. |
| SettingsHub | SUPERSEDED | The settings drawer is now a tabbed hub preserving real theme, locale, diagnostics, capability, version, approved-model, and observability controls. Unsupported permission profiles, model parameters, MCP, reset, and diagnostic-export controls are omitted. |
| Logs / Evidence Room | SUPERSEDED | The bounded read-only Observability Room uses validated control-plane events and sanitized managed-runtime log tails, explicitly distinguishes diagnostics from authoritative evidence, and exposes no fake export action. A persisted provenance-bearing evidence browser remains DEFER. |
| Multi-chat | DEFER | Current UI has one global transcript and the backend does not own or reconstruct conversation history from `chat_session_id`. UI-only conversation buckets would misrepresent model context and persistence. |
| Voice UI | DEFER | No typed desktop voice commands, microphone permission flow, or transcript events exist. The donor browser SpeechRecognition path is REJECTED because it may use cloud processing and conflicts with the local-only posture. |

## Implemented ADAPT surfaces

- Onboarding: `src/lib/components/onboarding/OnboardingScreen.svelte` exposes a
  setup workspace driven by live Control Plane bootstrap, canonical catalog,
  installed-artifact validation, managed-runtime, and binding state.
- SettingsHub: `src/lib/components/shell/SettingsPanel.svelte` provides donor-
  style Interface, Models, Logs, and About tabs while retaining the existing
  model manager and capability boundaries.
- Logs / Observability Room:
  `src/lib/components/logs/ObservabilityRoom.svelte` renders validated session
  events and sanitized managed-runtime tails, explicitly labelled as
  non-authoritative and non-persistent diagnostic data.
- AppShell, Command Center, ModelHub, and model picker retain the existing
  Svelte command/store logic and use the compact donor-inspired visual system;
  their disposition remains SUPERSEDED rather than ADAPT because these
  production implementations predate and exceed the donor behavior.

## Explicit rejections

- React/JSX/TSX and Zustand architecture.
- Fake ready states, random telemetry, timer-driven downloads, and simulated
  model startup.
- Static frontend model catalogs as installation or compatibility authority.
- Client-generated logs represented as evidence.
- Browser SpeechRecognition in the desktop local-only path.
- Plan execution that discards approval tokens or bypasses Rust approval.

## Deferred and rejected donor subpaths

| Donor subpath | Disposition | Reason |
| --- | --- | --- |
| Plan execution loop | REJECT | Client-owned approvals and step dispatch cannot replace scoped Rust grants and correlated execution results. |
| Client-only conversation buckets and export | REJECT | They would imply model context and persistence that the backend does not provide. |
| Browser SpeechRecognition | REJECT | It has no typed desktop permission or local-STT boundary and may use cloud processing. |
| Client-generated evidence and diagnostic bundle | REJECT | Frontend rows and an unimplemented export action are not authoritative evidence. |
| RAM slider and browser hardware recommendation | REJECT | User assertions and browser guesses cannot establish runtime compatibility. |
| Arbitrary Hugging Face installation | REJECT | It bypasses the embedded, hash-pinned approved artifact catalog. |
````

### ПУТЬ: audit/evidence-ledger.md (56 строк, 3680 байт)

````markdown
# Evidence Ledger — Best-of-Two Audit Archive

**Дата:** 2026-07-25
**Ветка:** `integration/best-of-two-local-agent` @ `767a7e9`

## Присутствует (включено в архив)

| Материал | Путь | Статус |
|---|---|---|
| Master Prompt (Best-of-Two) | `audit/donor-briefs/LocalComet Best-of-Two Integration Master Prompt.pdf` | PRESENT (binary, не читается моделью — только как артефакт) |
| WP-1.45.4 Independent Verification | `audit/donor-briefs/WP-1.45.4_Independent_Verification_2026-07-25.txt` | PRESENT |
| WP-1.45.4 Engineering Brief | `audit/donor-briefs/WP-1.45.4-engineering-brief.md` | PRESENT |
| WP-1.45.3 Engineering Brief | `audit/donor-briefs/WP-1.45.3-engineering-brief.md` | PRESENT |
| WP-1.45.2 Remediation Prompt | `audit/donor-briefs/WP-1.45.2-remediation-prompt.md` | PRESENT |
| Donor archive (lad-wp1454) | `audit/donor-briefs/lad-wp1454.tar.gz` | PRESENT (353 250 байт) |
| Migration matrix | `docs/engineering/best-of-two-migration-matrix.md` | PRESENT |
| Final report | `docs/engineering/best-of-two-final-report.md` | PRESENT |
| Invariants registry | `security/invariants/invariants.toml` | PRESENT |
| Non-authorities registry | `security/invariants/non_authorities.toml` | PRESENT |
| Evidence JSON | `artifacts/evidence/best-of-two-evidence.json` | PRESENT |
| Trust-chain gate | `tests/test_trust_chain_invariants.py` | PRESENT |
| Command parity gate | `scripts/check_command_parity.py` | PRESENT |

## Отсутствует (НЕ включено — не найдено в среде)

| Материал | Ожидаемый путь | Влияние |
|---|---|---|
| LocalComet Detailed Static Audit | `LocalComet_Detailed_Static_Audit_2026-07-25.txt` | Нет внешнего статического аудита LocalComet — аудитору придётся делать с нуля |
| Source vs Audit Diff | `LocalAgent_Source_vs_Audit_Diff_2026-07-25.txt` | Нет diff между исходниками и аудитом донора |
| local-agent-desktop-source (1/2).tar.gz | Downloads | Нет полных исходников донора (только WP-архив lad-wp1454) |
| local-agent-desktop-audit.zip | Downloads | Нет отдельного аудит-архива донора |
| LocalComet-ProjectArchive-20260725.zip | Downloads | Нет проектного архива |
| localcomet-dossier.zip | Downloads | Нет досье |

## Donor SHA-256 (из верификации WP-1.45.4)

```
lad-wp1454.tar.gz  85109c26669462e40f2ff65c83dc94cfce3094d4a27a739575555ee6ec5e827d
```

(заявлено в `WP-1.45.4_Independent_Verification_2026-07-25.txt`; сверить при распаковке)

## Проведённые проверки (локально, на момент сборки)

| Команда | Результат |
|---|---|
| `cargo test` | 143 passed, 0 failed, 6 ignored |
| `python tests/test_trust_chain_invariants.py` | OK: 14 files pass byte invariants |
| `python scripts/check_command_parity.py` | OK: 39 commands (parity holds) |

## Пометки способа получения

- Все числа тестов — `[прогон]` (реальное исполнение в этой среде).
- Классификация продукта — `[вычислено]` на основе чтения кода и прогонов.
- Утверждения о donor-дефектах — из `WP-1.45.4_Independent_Verification`, `[ЗАЯВЛЕНО]`
  относительно donor-кода (исходники донора в этой среде не запускались).
````

### ПУТЬ: CHANGELOG.md (61 строк, 3260 байт)

````markdown
# Changelog

All notable changes to LocalComet are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).

## [6.84.6] - 2026-07-25

Best-of-Two Wiring Sprint: подключение security-ядра (перенесённого из параллельной
реализации Local Agent Desktop) к продуктовому пути LocalComet.
Ветка: `integration/best-of-two-local-agent` (7 коммитов, `4fa48fe`…`8b23f8c`).

### Added

- Approval enforcement: CSPRNG 256-bit scoped one-time tokens
  (`src-tauri/src/approval.rs`, `src-tauri/src/approval_commands.rs`) — atomic
  `execute_approved`, TTL sweep, execution-grant expiry (15 тестов).
- Rust workspace authority (`src-tauri/src/workspace.rs`) + переиспользуемый примитив
  `modules/workspace_policy.py`; IPC-схема `workspace.set`.
- Гейты: `check_tool_risk_registry.py`, `check_command_parity.py` (42/42),
  `check_ui_fake_state.py`, `check_evidence_provenance.py`, `check_real_sidecar_tests.py`,
  `tests/test_trust_chain_invariants.py` (все injection-proven).
- In-process smoke (`scripts/smoke_test.py`, 8 шагов) + `localcomet_test_harness.py`.
- Preflight `scripts/doctor.py` + `scripts/build.sh` (7-step fail-fast).
- Реестры инвариантов: `security/invariants/invariants.toml` (12),
  `non_authorities.toml` (16), `tool_risk_levels.toml` (5 инструментов).
- Документация: `docs/engineering/best-of-two-final-report.md`,
  `best-of-two-migration-matrix.md`, `docs/unverified-ledger.md`, `audit/AUDIT_GUIDE.md`.

### Changed

- Активированы инварианты: INV-APPROVAL-001, INV-APPROVAL-002, INV-EVIDENCE-001,
  INV-UI-001 (с `verification_method`).
- `.gitattributes` усилен для trust-chain файлов.
- Real-sidecar тесты: silent skip заменён на honest panic при
  `LOCALCOMET_REQUIRE_REAL_SIDECAR=1`.

### Fixed

- CRLF→LF в `config.py`, `approved-artifacts.v1.json` (trust-chain byte invariants).

### Security

- Нет approval bypass: guarded tools исполняются только через atomic `execute_approved`.
- Критические дефекты donor не унаследованы (approval bypass, dual IPC transport,
  readiness «любой кадр», не дренируемый stderr).
- Ключевая находка: desktop sidecar не исполняет file-tools; enforcement живёт в Rust.

### Build

- Windows NSIS-инсталлятор собирается: `LocalComet_6.84.6_x64-setup.exe`
  (13.32 MB, SHA-256: `7fc82beb3ff74a3ae5ad55b8b365dbd00acd92d81a007f74c1fb0c5dcbfa488f`).

### Commits

- `4fa48fe` feat(approval): CSPRNG scoped one-time tokens + product wiring
- `822575e` feat(workspace): WorkspacePolicy primitive + IPC schema workspace.set
- `4a69094` chore(audit): invariant registries + trust-chain and evidence gates
- `cddd0e8` test(sidecar): honest real-sidecar skip + in-process smoke harness
- `4b0418e` build: preflight doctor.py + build.sh pipeline
- `36af461` docs: best-of-two final report, unverified ledger, audit guide
- `8b23f8c` chore(invariants): activate INV-APPROVAL-001/002, INV-EVIDENCE-001; verify INV-UI-001
````

### ПУТЬ: config.py (5 строк, 166 байт)

````python
LMSTUDIO_API = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = "qwen3-14b"

OPENAI_MODEL = "gpt-5.5"
OPENAI_RESPONSES_API = "https://api.openai.com/v1/responses"
````

### ПУТЬ: core/executor.py (128 строк, 3722 байт)

````python
from agents import browser_agent
from agents import code_agent
from agents import file_agent
from agents import operator_agent
from agents import project_agent
from agents import research_agent
from agents import windows_agent
from agents import system_agent
from agents import workspace_agent
from agents import diagnostics_agent
from agents import history_agent
from agents import maintenance_agent
from agents import self_edit_agent
from agents import gpt_agent
from agents import chatgpt_relay_agent
from agents import stability_agent
from agents import automation_agent
from agents import gpt_browser_agent


def execute(plan):
    if plan is None:
        return "Executor: пустой план."

    if isinstance(plan, list):
        results = []

        for i, action_plan in enumerate(plan, start=1):
            result = execute(action_plan)
            results.append(f"{i}. {result}")

        return "\n".join(results)

    if not isinstance(plan, dict):
        return f"Executor: неправильный формат плана: {plan}"

    if "actions" in plan:
        actions = plan.get("actions")

        if not isinstance(actions, list):
            return "Executor: поле actions должно быть списком."

        results = []

        for i, action_plan in enumerate(actions, start=1):
            result = execute(action_plan)
            results.append(f"{i}. {result}")

        return "\n".join(results)

    tool = plan.get("tool")
    action = plan.get("action")

    if not tool:
        return f"Executor: неизвестный инструмент. План: {plan}"

    if tool == "none":
        return plan.get("text", "OK")

    if tool == "system":
        return system_agent.handle(action, plan)

    if tool == "diagnostics":
        return diagnostics_agent.handle(action, plan)

    if tool == "history":
        return history_agent.handle(action, plan)

    if tool == "maintenance":
        return maintenance_agent.handle(action, plan)

    if tool == "self_edit":
        return self_edit_agent.handle(action, plan)

    if tool == "gpt":
        return gpt_agent.handle(action, plan)

    if tool == "chatgpt_relay":
        if action in [
            "apply",
            "apply_response",
            "apply_answer",
            "apply_last_response",
            "relay_apply",
        ]:
            try:
                from modules.browser_profile_ignore import close_gpt_browser_context

                close_gpt_browser_context()
            except (ImportError, OSError):
                pass

        return chatgpt_relay_agent.handle(action, plan)

    if tool == "stability":
        return stability_agent.handle(action, plan)

    if tool == "automation":
        return automation_agent.handle(action, plan)

    if tool == "gpt_browser":
        return gpt_browser_agent.handle(action, plan)

    if tool == "workspace":
        return workspace_agent.handle(action, plan)

    if tool == "browser":
        return browser_agent.handle(action, plan)

    if tool in ["file", "files"]:
        return file_agent.handle(action, plan)

    if tool in ["code", "codegen"]:
        return code_agent.handle(action, plan)

    if tool == "project":
        return project_agent.handle(action, plan)

    if tool == "research":
        return research_agent.handle(action, plan)

    if tool == "operator":
        return operator_agent.handle(action, plan)

    if tool == "windows":
        return windows_agent.handle(action, plan)

    return f"Executor: неизвестный инструмент: {tool}"
````

### ПУТЬ: core/llm.py (98 строк, 2512 байт)

````python
import requests

from config import LMSTUDIO_API, MODEL

try:
    from core.project_context import build_system_prompt
except (ImportError, AttributeError):
    build_system_prompt = None


def _apply_no_think(user_text: str):
    text = str(user_text or "").strip()

    lower = text.lower()

    if "/think" in lower or "/no_think" in lower:
        return text

    return text + "\n\n/no_think"


LLM_OFFLINE_ERROR_PREFIX = "LLM_OFFLINE_ERROR:"


def format_llm_offline_message(error=None):
    return (
        "LLM server is offline. Start LM Studio Local Server at "
        "http://127.0.0.1:1234 and try again."
    )


def is_llm_offline_error(value):
    text = str(value or "")
    return text.startswith(LLM_OFFLINE_ERROR_PREFIX) or text == format_llm_offline_message()


def ask_llm(
    system,
    user,
    max_tokens=400,
    use_context=False,
    no_think=True,
    temperature=0.1,
    timeout=300
):
    """
    Главная функция запроса к LM Studio.

    По умолчанию:
    - НЕ добавляет Global Project Context
    - добавляет /no_think для Qwen3
    - держит низкую temperature для стабильного JSON

    use_context=True включать только там, где реально нужен контекст LocalComet:
    - финальные отчеты
    - анализ проекта
    - объяснения пользователю

    Для planner/router/extractor лучше оставлять use_context=False.
    """

    if use_context and build_system_prompt:
        full_system = build_system_prompt(system)
    else:
        full_system = system

    final_user = _apply_no_think(user) if no_think else user

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": full_system
            },
            {
                "role": "user",
                "content": final_user
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    try:
        response = requests.post(
            LMSTUDIO_API,
            json=payload,
            timeout=timeout
        )

        response.raise_for_status()

        data = response.json()

        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        return format_llm_offline_message(e)
````

### ПУТЬ: core/loop.py (90 строк, 2412 байт)

````python
from core.router import route
from core.planner import plan
from core.executor import execute
from core.llm import ask_llm


REVIEW_SYSTEM = """
You are LocalComet Task Reviewer.

Decide if the task is finished.

Return ONLY valid JSON.

Format:
{"done": true, "message": "Готово"}

or

{"done": false, "next_step": "Открой сайт AutoServicePro"}

Never use markdown.
Never explain.
"""


def run_loop(task: str, max_steps: int = 5):
    import json
    from json_repair import repair_json

    history = []
    current_task = task

    for step in range(1, max_steps + 1):
        print(f"\n--- STEP {step} ---")
        print("TASK:", current_task)

        try:
            route_name = route(current_task)
            print("ROUTE:", route_name)

            plan_result = plan(current_task, route_name)
            print("PLAN:", plan_result)

            result = execute(plan_result)
            print("RESULT:", result)

        except Exception as e:
            error_text = f"Шаг упал с ошибкой: {e}"
            print("STEP ERROR:", error_text)
            return error_text

        history.append({
            "step": step,
            "task": current_task,
            "route": route_name,
            "plan": plan_result,
            "result": str(result)
        })

        review_prompt = f"""
Original task:
{task}

History:
{history}

Question:
Is the original task finished?
If not, provide one next concrete user-style command for the agent.
"""

        try:
            review = ask_llm(REVIEW_SYSTEM, review_prompt, max_tokens=300)
            review = review.replace("```json", "").replace("```", "").strip()
            review_data = json.loads(repair_json(review))
        except Exception as e:
            print("REVIEW ERROR:", e)
            return "Задача выполнена частично, но проверка результата сломалась."

        print("REVIEW:", review_data)

        if review_data.get("done") is True:
            return review_data.get("message", "Готово")

        current_task = review_data.get("next_step", "")

        if not current_task:
            return "Остановлено: нет следующего шага."

    return "Остановлено: достигнут лимит шагов."
````

### ПУТЬ: core/planner.py (582 строк, 23339 байт)

````python
import json
import sys
from json_repair import repair_json
from core.llm import ask_llm, is_llm_offline_error, format_llm_offline_message
from modules.browser_direct import browser_action_direct_plan
from modules.natural_command_intents import natural_command_plan


SYSTEMS = {
    "system": """
You are LocalComet System Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"system","action":"help"}
{"tool":"system","action":"status"}
{"tool":"system","action":"memory"}
{"tool":"system","action":"recent"}
{"tool":"system","action":"model"}
{"tool":"system","action":"health"}
{"tool":"system","action":"health_report"}
{"tool":"system","action":"regression_suite"}
{"tool":"system","action":"regression_report"}
{"tool":"system","action":"auto_verify"}
{"tool":"system","action":"auto_verify_full"}

Rules:
- If user asks what LocalComet can do, use help.
- If user asks status, use status.
- If user asks memory, use memory.
- If user asks recent/last actions, use recent.
- If user asks current model, use model.
- If user asks project health, use health.
- If user asks project health report, use health_report.
- If user asks regression suite/check, use regression_suite.
- If user asks regression report, use regression_report.
- If user asks auto verify, verify quick, or check all, use auto_verify.
- If user asks auto verify full, verify full, or post patch verify, use auto_verify_full.
- Do not explain.
- Do not use markdown.
- Return JSON only.

Examples:
User: что ты умеешь
{"tool":"system","action":"help"}

User: статус
{"tool":"system","action":"status"}

User: память
{"tool":"system","action":"memory"}

User: последние действия
{"tool":"system","action":"recent"}

User: какая модель
{"tool":"system","action":"model"}

User: health
{"tool":"system","action":"health"}

User: health report
{"tool":"system","action":"health_report"}

User: regression suite
{"tool":"system","action":"regression_suite"}

User: regression report
{"tool":"system","action":"regression_report"}

User: auto verify
{"tool":"system","action":"auto_verify"}

User: verify full
{"tool":"system","action":"auto_verify_full"}
""",

    "windows": """
You are LocalComet Windows Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"windows","action":"open_app","app":"calc"}
{"tool":"windows","action":"open_app","app":"notepad"}
{"tool":"windows","action":"type_text","text":"Hello"}

Rules:
- If user asks to open an app, use open_app.
- If user asks to write/type/enter/print text, use type_text.
- If user asks to open an app AND write/type text, return {"actions":[...]}.
- For Russian "блокнот", use app "notepad".
- For Russian "калькулятор", use app "calc".
- For Russian "напиши", "напечатай", "введи", "набери", "вставь", use type_text.
- Preserve the user's text language.
- Do not translate Russian text to English.
- If user says "напиши привет", text must be "привет".
- If user says "напиши привет мир", text must be "привет мир".

Examples:
User: открой блокнот
{"tool":"windows","action":"open_app","app":"notepad"}

User: открой калькулятор
{"tool":"windows","action":"open_app","app":"calc"}

User: напиши привет
{"tool":"windows","action":"type_text","text":"привет"}

User: введи привет мир
{"tool":"windows","action":"type_text","text":"привет мир"}

User: открой блокнот и напиши в нем привет мир
{"actions":[{"tool":"windows","action":"open_app","app":"notepad"},{"tool":"windows","action":"type_text","text":"привет мир"}]}

Never explain.
Never use markdown.
Return JSON only.
""",

    "browser": """
You are LocalComet Browser Planner.
Return ONLY valid JSON.

STRICT RULES:
- If user says "Открой сайт" without URL or folder, use open_local_site without folder.
- If user asks to open the current/last/generated site, use open_local_site without folder.
- If user says "проверь сайт", "проверь страницу", "прочитай сайт", "прочитай страницу", "browser read" — ALWAYS use read_page.
- If user asks to search/find something — use search and preserve the full query.
- If user asks "browser last", "последний поиск", or "покажи последний поиск" — use last_search.
- If user asks "browser open first", "открой первый результат", or "первый результат" — use open_first_result.
- If user asks "browser status", "статус браузера", or "browser состояние" — use status.
- If browser page/context was closed, browser agent should recover using last_browser_query.
- If user asks to open Google, YouTube or another full website URL — use open_url.
- If user asks to open local generated project by folder name — use open_local_site with folder.
- Do NOT search Google when user says "проверь сайт".
- Do NOT use open_url for local project names.

Available actions:
{"tool":"browser","action":"search","query":"Godot"}
{"tool":"browser","action":"last_search"}
{"tool":"browser","action":"open_first_result"}
{"tool":"browser","action":"status"}
{"tool":"browser","action":"open_url","url":"https://google.com"}
{"tool":"browser","action":"open_local_site","folder":"CoffeeShop"}
{"tool":"browser","action":"open_local_site"}
{"tool":"browser","action":"read_page"}
{"tool":"browser","action":"click_text","text":"YouTube"}
{"tool":"browser","action":"click_first_link"}
{"tool":"browser","action":"screenshot"}
{"tool":"browser","action":"find_text","text":"Python"}
{"tool":"browser","action":"fill_label","label":"Email","value":"test@example.com"}
{"tool":"browser","action":"press_key","key":"Enter"}
{"tool":"browser","action":"extract_links"}
{"tool":"browser","action":"extract_inputs"}
{"tool":"browser","action":"summarize"}
{"tool":"browser","action":"list_tabs"}
{"tool":"browser","action":"open_new_tab","url":"https://example.com"}
{"tool":"browser","action":"switch_tab","index":0}
{"tool":"browser","action":"close_tab"}
{"tool":"browser","action":"action_status"}
{"tool":"browser","action":"observe"}
{"tool":"browser","action":"plan","task":"найди официальный сайт Python и сделай отчет"}
{"tool":"browser","action":"autopilot_dry","task":"найди официальный сайт Python и сделай отчет","max_steps":8}
{"tool":"browser","action":"autopilot_run","task":"найди официальный сайт Python и сделай отчет","max_steps":8}
{"tool":"browser","action":"browser_task","task":"проанализируй текущую страницу и собери ссылки","max_steps":8}
{"tool":"browser","action":"autopilot_last_report"}
{"tool":"browser","action":"super_plan","task":"исследуй тему и дай источники","max_results":3}
{"tool":"browser","action":"super_run","task":"исследуй тему и дай источники","max_results":3}
{"tool":"browser","action":"research","task":"openai gpt-oss-20b LM Studio","max_results":3}
{"tool":"browser","action":"page_audit","task":"current page"}
{"tool":"browser","action":"form_map","task":"current page"}
{"tool":"browser","action":"platform_site_workflow","task":"сайт автосервиса на Tilda"}
{"tool":"browser","action":"super_last_report"}

Examples:
User: найди Адский рай 2 сезон
{"tool":"browser","action":"search","query":"Адский рай 2 сезон"}

User: browser last
{"tool":"browser","action":"last_search"}

User: browser open first
{"tool":"browser","action":"open_first_result"}

User: browser read
{"tool":"browser","action":"read_page"}

User: browser status
{"tool":"browser","action":"status"}

User: browser screenshot
{"tool":"browser","action":"screenshot"}

User: browser click Search
{"tool":"browser","action":"click_text","text":"Search"}

User: browser fill Email = test@example.com
{"tool":"browser","action":"fill_label","label":"Email","value":"test@example.com"}

User: browser press Enter
{"tool":"browser","action":"press_key","key":"Enter"}

User: browser links
{"tool":"browser","action":"extract_links"}

User: browser inputs
{"tool":"browser","action":"extract_inputs"}

User: browser summarize
{"tool":"browser","action":"summarize"}

User: browser workflow python search
{"tool":"browser","action":"browser_workflow","steps":[{"action":"search","args":{"query":"Python official website"}},{"action":"open_first"},{"action":"summarize"},{"action":"extract_links"},{"action":"extract_inputs"},{"action":"screenshot"}],"title":"python search workflow"}

User: browser workflow current page
{"tool":"browser","action":"browser_workflow","steps":[{"action":"summarize"},{"action":"extract_links"},{"action":"extract_inputs"},{"action":"screenshot"}],"title":"current page workflow"}

User: browser plan найди официальный сайт Python и сделай отчет
{"tool":"browser","action":"plan","task":"найди официальный сайт Python и сделай отчет","max_steps":8}

User: browser autopilot dry найди официальный сайт Python и сделай отчет
{"tool":"browser","action":"autopilot_dry","task":"найди официальный сайт Python и сделай отчет","max_steps":8}

User: browser task проанализируй текущую страницу и собери ссылки
{"tool":"browser","action":"browser_task","task":"проанализируй текущую страницу и собери ссылки","max_steps":8}

User: browser observe
{"tool":"browser","action":"observe"}

User: browser research лучшие конструкторы сайтов для автосервиса
{"tool":"browser","action":"research","task":"лучшие конструкторы сайтов для автосервиса","max_results":3}

User: browser page audit
{"tool":"browser","action":"page_audit","task":"current page"}

User: browser form map
{"tool":"browser","action":"form_map","task":"current page"}

User: напиши сайт автосервиса используй платформу Tilda
{"tool":"browser","action":"platform_site_workflow","task":"напиши сайт автосервиса используй платформу Tilda"}

Never explain.
Never use markdown.
Return JSON only.
""",

    "files": """
You are LocalComet File Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"files","action":"create_folder","path":"TestSite"}
{"tool":"files","action":"write_file","path":"TestSite/index.html","content":"Hello"}
{"tool":"files","action":"read_file","path":"TestSite/index.html"}
{"tool":"files","action":"list_files","path":"TestSite"}
{"tool":"files","action":"delete_path","path":"TestSite"}

Never explain.
Never use markdown.
Return JSON only.
""",

    "codegen": """
You are LocalComet Codegen Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"codegen","action":"generate_site","prompt":"Создай сайт кофейни"}
{"tool":"codegen","action":"improve_site"}

Rules:
- If user asks to create/make/generate a simple website, use generate_site.
- If user asks to improve/upgrade/redesign an existing site, use improve_site.
- If user says "улучши сайт" without folder, return {"tool":"codegen","action":"improve_site"}.
- Do not invent folder name if user did not provide one.

Never explain.
Never use markdown.
Return JSON only.
""",

    "project": """
You are LocalComet Project Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"project","action":"create_project_site","prompt":"Создай современный сайт автосервиса с формой заявки, услугами, ценами и адаптивным дизайном"}
{"tool":"project","action":"review_site"}
{"tool":"project","action":"improve_last_site"}

Rules:
- If user asks to create a full/modern/company website/project, use create_project_site.
- If user asks to review/check current/last site, use review_site.
- If user asks to improve/redesign/upgrade current/last site, use improve_last_site.
- If the request contains create + check + improve, return a LIST of actions:
[
  {"tool":"project","action":"create_project_site","prompt":"..."},
  {"tool":"project","action":"review_site"},
  {"tool":"project","action":"improve_last_site"}
]
- Do not explain.
- Do not use markdown.
- Return JSON only.
""",

    "research": """
You are LocalComet Research Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"research","action":"make_report","query":"лучшие локальные LLM для моего ПК"}
{"tool":"research","action":"open_last_report"}
{"tool":"research","action":"read_last_report"}

Rules:
- If user asks to study/analyze/research/find information and make a report, use make_report.
- If user says "открой последний отчет" or "открой отчет", use open_last_report.
- If user says "покажи последний отчет", "прочитай последний отчет" or "покажи отчет", use read_last_report.
- Put the full user request into query for make_report.
- Do not ask questions.
- Do not explain.
- Do not use markdown.
- Return JSON only.
""",

    "operator": """
You are LocalComet Browser Operator Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"operator","action":"compare_and_choose","query":"найди 5 лучших локальных LLM для моего ПК, сравни и выбери лучшую"}

Rules:
- If user asks to find options, compare options, rank options, choose the best, pick the best, or make a top list, use compare_and_choose.
- Put the full user request into query.
- Do not ask questions.
- Do not explain.
- Do not use markdown.
- Return JSON only.

Examples:
User: найди 5 лучших локальных LLM для моего ПК, сравни и выбери лучшую
{"tool":"operator","action":"compare_and_choose","query":"найди 5 лучших локальных LLM для моего ПК, сравни и выбери лучшую"}

User: найди 5 вариантов AI-браузеров, сравни по цене, приватности и функциям
{"tool":"operator","action":"compare_and_choose","query":"найди 5 вариантов AI-браузеров, сравни по цене, приватности и функциям"}
""",

    "stability": """
You are LocalComet Stability Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"stability","action":"run"}

Rules:
- If user asks for model test, stability test, auto test, or тест стабильности, use run.
- Do not explain.
- Do not use markdown.
- Return JSON only.

Examples:
User: model test
{"tool":"stability","action":"run"}

User: stability test
{"tool":"stability","action":"run"}

User: тест стабильности
{"tool":"stability","action":"run"}
""",

    "gpt_browser": """
You are LocalComet GPT Browser Bridge Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"gpt_browser","action":"open"}
{"tool":"gpt_browser","action":"paste_request"}
{"tool":"gpt_browser","action":"send"}
{"tool":"gpt_browser","action":"wait","timeout_sec":600}
{"tool":"gpt_browser","action":"save_response"}
{"tool":"gpt_browser","action":"repair_response"}
{"tool":"gpt_browser","action":"status"}
{"tool":"gpt_browser","action":"close"}
{"tool":"gpt_browser","action":"full_cycle","timeout_sec":600}
{"actions":[{"tool":"gpt_browser","action":"full_cycle","timeout_sec":600},{"tool":"gpt_browser","action":"close"},{"tool":"chatgpt_relay","action":"apply_response"},{"tool":"automation","action":"after_patch"}]}

Rules:
- If user says "gpt browser open", use open.
- If user says "gpt browser paste request", use paste_request.
- If user says "gpt browser send", use send.
- If user says "gpt browser wait", use wait with timeout_sec 600.
- If user says "gpt browser wait N", use wait with timeout_sec N.
- If user says "gpt browser save response", use save_response.
- If user says "gpt browser repair response", use repair_response.
- If user says "gpt browser status", use status.
- If user says "gpt browser close", use close.
- If user says "gpt browser full cycle", use full_cycle with timeout_sec 600.
- If user says "gpt browser full apply", return actions: full_cycle, close, chatgpt_relay apply_response, automation after_patch.
- The close step must happen after full_cycle and before relay apply.
- Do not explain.
- Do not use markdown.
- Return JSON only.

Examples:
User: gpt browser open
{"tool":"gpt_browser","action":"open"}

User: gpt browser repair response
{"tool":"gpt_browser","action":"repair_response"}

User: gpt browser wait 600
{"tool":"gpt_browser","action":"wait","timeout_sec":600}

User: gpt browser close
{"tool":"gpt_browser","action":"close"}

User: gpt browser full cycle
{"tool":"gpt_browser","action":"full_cycle","timeout_sec":600}

User: gpt browser full apply
{"actions":[{"tool":"gpt_browser","action":"full_cycle","timeout_sec":600},{"tool":"gpt_browser","action":"close"},{"tool":"chatgpt_relay","action":"apply_response"},{"tool":"automation","action":"after_patch"}]}
""",

    "automation": """
You are LocalComet Automation Command Center Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"automation","action":"dev_task","goal":"улучши browser agent"}
{"tool":"automation","action":"browser_task","goal":"найди официальный сайт Python и прочитай"}
{"tool":"automation","action":"browser_batch","goal":"Godot 4.5","limit":3}
{"tool":"automation","action":"browser_read_first","limit":3}
{"tool":"automation","action":"browser_compare","goal":"лучшие локальные LLM"}
{"tool":"automation","action":"browser_report","goal":"Python official website"}
{"tool":"automation","action":"pc_task","goal":"открой блокнот"}
{"tool":"automation","action":"pc_batch","goal":"открой блокнот, напиши тест, открой папку отчетов"}
{"tool":"automation","action":"multi_task","goal":"найди Python, прочитай и открой папку Reports"}
{"tool":"automation","action":"task_status"}
{"tool":"automation","action":"task_report"}
{"tool":"automation","action":"status"}
{"tool":"automation","action":"after_patch"}

Rules:
- If user says "dev task ..." or "задача разработки ..." use dev_task and put the rest into goal.
- If user says "browser task ..." or "браузерная задача ..." use browser_task and put the rest into goal.
- If user says "browser batch ..." use browser_batch.
- If user says "browser read first N" use browser_read_first and put N into limit. Do not put N into goal; use last_browser_query.
- If user says "browser compare ..." use browser_compare.
- If user says "browser report ..." use browser_report.
- If user says "pc task ..." or "задача пк ..." use pc_task and put the rest into goal.
- If user says "pc batch ..." use pc_batch.
- If user says "multi task ..." or "комплексная задача ..." use multi_task.
- If user asks task status, use task_status.
- If user asks task report, use task_report.
- If user asks automation status, use status.
- If user says after patch or после патча, use after_patch.
- Preserve the user's language.
- Do not explain.
- Do not use markdown.
- Return JSON only.

Examples:
User: dev task улучши браузер чтобы он читал несколько вкладок
{"tool":"automation","action":"dev_task","goal":"улучши браузер чтобы он читал несколько вкладок"}

User: browser task найди документацию Godot и прочитай
{"tool":"automation","action":"browser_task","goal":"найди документацию Godot и прочитай"}

User: pc task открой блокнот и напиши привет
{"tool":"automation","action":"pc_task","goal":"открой блокнот и напиши привет"}

User: automation status
{"tool":"automation","action":"status"}

User: after patch
{"tool":"automation","action":"after_patch"}
""",

    "unknown": """
You are LocalComet.
Return ONLY valid JSON.

If you cannot choose a tool, answer:
{"tool":"none","action":"answer","text":"Я пока не умею это делать."}

Never explain.
Never use markdown.
Return JSON only.
"""
}


def _strip_browser_prefix(user):
    text = str(user or "").strip()
    lower = text.lower()

    for prefix in ["browser", "браузер"]:
        if lower.startswith(prefix):
            return text[len(prefix):].strip(" :,-")

    return text


def _extract_after(text, markers):
    lower = text.lower()

    for marker in markers:
        index = lower.find(marker)

        if index != -1:
            return text[index + len(marker):].strip(" :,-")

    return ""


def _browser_direct_plan(user):
    return browser_action_direct_plan(user)


def _voice_direct_plan(user):
    text = str(user or "").strip()
    lower = text.lower()

    if lower == "voice status":
        return {"tool": "system", "action": "voice_status"}

    if lower == "voice test":
        return {"tool": "system", "action": "voice_test"}

    if lower.startswith("voice speak "):
        return {"tool": "system", "action": "voice_speak", "text": text[len("voice speak "):].strip()}

    if lower == "voice last report":
        return {"tool": "system", "action": "voice_last_report"}

    return None


def plan(user, route_name="unknown"):
    voice = _voice_direct_plan(user)

    if voice:
        return voice

    natural = natural_command_plan(user)

    if natural:
        return natural

    if route_name in ["unknown", "browser"]:
        direct = _browser_direct_plan(user)

        if direct:
            return direct

    system = SYSTEMS.get(route_name, SYSTEMS["unknown"])

    answer = ask_llm(system, user)

    if is_llm_offline_error(answer):
        return {
            "tool": "none",
            "action": "answer",
            "text": format_llm_offline_message(),
        }

    answer = answer.replace("```json", "").replace("```", "").strip()

    fixed = repair_json(answer)

    try:
        parsed = json.loads(fixed)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"[planner] JSON parse error: {str(e)[:200]}", file=sys.stderr)
        return {"tool": "none", "action": "answer", "text": "Не удалось разобрать ответ модели."}

    if not isinstance(parsed, dict):
        return {"tool": "none", "action": "answer", "text": "Не удалось разобрать ответ модели."}

    return parsed
````

### ПУТЬ: core/project_context.py (71 строк, 4547 байт)

````python
GLOBAL_PROJECT_CONTEXT = """
Ты работаешь внутри проекта LocalComet.

Что такое LocalComet:
- LocalComet — локальный AI-агент на Python.
- Он работает через LM Studio API.
- Его цель — выполнять задачи пользователя через инструменты, а не просто отвечать текстом.
- Пользователь хочет аналог Comet/Claude Code: локальный агент, который сам планирует, ищет, открывает страницы, пишет файлы, делает отчеты и помогает с кодом.

Текущая архитектура:
- core/router.py выбирает тип задачи.
- core/planner.py превращает команду пользователя в JSON tool/action.
- core/executor.py выполняет tool/action.
- core/llm.py отправляет запросы в LM Studio.
- core/state.py хранит last_site, last_report и другие значения.
- modules/browser.py работает с браузером через Playwright.
- modules/files.py работает с файлами в Projects.
- modules/research.py делает исследовательские отчеты.
- modules/browser_operator.py ищет варианты, сравнивает и выбирает лучший.
- modules/report_opener.py открывает и запоминает отчеты.
- agents/*.py связывают planner/executor с modules.
- next/app_v5.py запускает Goal Manager и Task Queue.

Доступные направления:
1. browser — поиск, открытие сайтов, чтение страницы.
2. research — поиск информации, создание markdown-отчета, открытие последнего отчета.
3. operator — поиск вариантов, сравнение, выбор лучшего варианта.
4. files — создание, чтение, список и удаление файлов в Projects.
5. codegen — создание и улучшение сайтов.
6. project — многошаговое создание/проверка/улучшение сайта.
7. windows — открытие приложений и ввод текста.

Важные правила поведения:
- Если требуется tool/action, возвращай строгий JSON.
- Не используй markdown в JSON-ответах.
- Не добавляй объяснения вокруг JSON.
- Не путай платформы и модели.
- LM Studio, Ollama, AnythingLLM, GPT4All, llama.cpp, Open WebUI — это инструменты/оболочки, а не LLM-модели.
- Qwen, Gemma, Llama, Mistral, DeepSeek, Phi, Hermes, Zephyr — это модели или семейства моделей.
- Если пользователь просит выбрать локальную LLM, учитывай его железо.

ПК пользователя:
- CPU: Intel Core i7-14700KF
- GPU: GeForce RTX 5070 12 GB
- RAM: 32 GB DDR5
- OS: Windows
- Основной интерфейс для локальных моделей: LM Studio
- Для 12 GB VRAM лучше рассматривать GGUF Q4/Q5 модели примерно 7B, 8B, 12B, 14B.
- Очень большие 30B/70B/80B модели могут работать медленно через offload в RAM.

Цель проекта:
- Делать LocalComet более автономным.
- Уменьшать галлюцинации.
- Улучшать планирование.
- Делать больше действий по одной цели.
- Сохранять полезные результаты в Projects/Reports.
- Открывать результаты пользователю автоматически.

Этот контекст является справочным.
Не пересказывай его пользователю без необходимости.
Используй его, чтобы лучше понимать задачи LocalComet.
"""


def build_system_prompt(task_system_prompt: str):
    return (
        GLOBAL_PROJECT_CONTEXT.strip()
        + "\n\n"
        + "Текущая конкретная инструкция для этой задачи:\n"
        + task_system_prompt.strip()
    )
````

### ПУТЬ: core/router.py (344 строк, 10112 байт)

````python
from core.state import get_value
from modules.natural_command_intents import natural_command_route


def route(user_text: str) -> str:
    text = str(user_text or "").lower().strip()

    if text in ["voice status", "voice test", "voice last report"] or text.startswith("voice speak "):
        return "system"

    natural_route = natural_command_route(user_text)

    if natural_route:
        return natural_route

    last_windows_app = get_value("last_windows_app")

    system_words = [
        "что ты умеешь",
        "помощь",
        "help",
        "status",
        "статус",
        "память",
        "relay status",
        "relay diagnostics",
        "relay smoke",
        "panel relay smoke",
        "patch registry",
        "rollback",
        "after patch",
        "voice status",
        "voice test",
        "voice speak",
        "voice last report",
        "health",
        "project health",
        "health report",
        "regression",
        "regression suite",
        "regression report",
        "safe regression",
        "auto verify",
        "auto verification",
        "verify full",
        "verify quick",
        "check all",
        "post patch verify",
        "автопроверка",
        "проверить всё",
        "регрессия",
        "регрессионная проверка",
        "здоровье проекта",
        "состояние проекта",
        "последние действия",
        "что было последним",
        "последняя модель",
        "какая модель",
        "текущая модель",
    ]

    windows_type_words = [
        "напиши",
        "напечатай",
        "введи",
        "набери",
        "вставь",
        "напечатать",
        "ввести",
        "написать",
    ]

    windows_open_words = [
        "калькулятор",
        "блокнот",
        "notepad",
        "calc",
        "calculator",
        "chrome",
        "хром",
        "paint",
        "пейнт",
        "проводник",
        "explorer",
        "приложение",
        "программу",
    ]

    operator_words = [
        "сравни и выбери",
        "выбери лучший",
        "выбери лучшую",
        "выбери лучшее",
        "найди 5",
        "найди пять",
        "топ",
        "лучшие варианты",
        "лучшие локальные",
        "подбери",
        "сравни варианты",
        "что лучше",
    ]

    report_words = [
        "открой последний отчет",
        "покажи последний отчет",
        "прочитай последний отчет",
        "открой отчет",
        "покажи отчет",
        "последний отчет",
    ]

    research_words = [
        "сделай отчет",
        "создай отчет",
        "собери отчет",
        "подготовь отчет",
        "изучи",
        "проанализируй",
        "исследуй",
        "найди информацию",
        "собери информацию",
    ]

    project_words = [
        "создай современный сайт",
        "сделай современный сайт",
        "создай проект сайта",
        "сайт с формой",
        "сайт с каталогом",
        "сайт компании",
        "сайт логистической",
        "сайт автосервиса",
        "сайт автомойки",
        "проверь и улучши",
    ]

    codegen_words = [
        "создай сайт",
        "сделай сайт",
        "сгенерируй сайт",
        "лендинг",
        "визитку",
        "улучши сайт",
        "улучшить сайт",
        "переделай сайт",
        "редизайн",
        "улучши дизайн",
    ]

    file_words = [
        "создай папку",
        "создай файл",
        "покажи файлы",
        "прочитай файл",
        "удали файл",
        "удали папку",
    ]

    browser_words = [
        "найди",
        "поиск",
        "гугл",
        "google",
        "страницу",
        "браузер",
        "browser",
        "browser last",
        "browser workflow",
        "browser open first",
        "browser read",
        "browser status",
        "статус браузера",
        "состояние браузера",
        "последний поиск",
        "покажи последний поиск",
        "youtube",
        "ютуб",
        "прочитай страницу",
        "открой первый результат",
        "первый результат",
        "открой сайт",
        "открыть сайт",
        "открой созданный сайт",
        "проверь сайт",
        "проверить сайт",
        "проверь страницу",
        "browser screenshot",
        "browser скрин",
        "browser find text",
        "browser найди текст",
        "browser click",
        "browser клик",
        "browser fill",
        "browser введи",
        "browser press",
        "browser нажми",
        "browser links",
        "browser inputs",
        "browser summarize",
        "browser summary",
        "browser tabs",
        "browser new tab",
        "browser switch tab",
        "browser close tab",
        "browser action status",
        "browser research",
        "browser deep research",
        "browser compare",
        "browser page audit",
        "browser form map",
        "browser build site",
        "browser site workflow",
        "browser super",
        "браузер исследуй",
        "браузер аудит",
        "карта форм",
        "аудит страницы",
        "напиши сайт",
        "создай сайт на tilda",
        "сайт на tilda",
        "тильда",
        "используй платформу",
        "browser steps",
        "browser sequence",
    ]

    stability_words = [
        "model test",
        "stability test",
        "тест стабильности",
        "проверка стабильности",
        "автотест",
        "auto stability",
        "auto stability test",
    ]

    gpt_browser_words = [
        "gpt browser",
        "gpt browser close",
        "close gpt browser",
        "гпт браузер",
        "гпт браузер закрыть",
        "закрой гпт браузер",
        "чатгпт браузер",
        "чатгпт браузер закрыть",
        "закрой чатгпт браузер",
        "chatgpt browser",
    ]

    automation_words = [
        "dev task",
        "browser task",
        "browser batch",
        "browser read first",
        "browser compare",
        "browser report",
        "pc task",
        "pc batch",
        "multi task",
        "task status",
        "task report",
        "automation status",
        "after patch",
        "центр автоматизации",
        "автоматизация статус",
        "задача разработки",
        "браузерная задача",
        "задача пк",
        "после патча",
        "комплексная задача",
        "мульти задача",
    ]

    browser_autopilot_words = [
        "browser autopilot",
        "browser task",
        "browser observe",
        "browser plan",
        "браузер autopilot",
        "браузер план",
        "браузер наблюдай",
        "browser research",
        "browser deep research",
        "browser compare",
        "browser page audit",
        "browser form map",
        "browser build site",
        "browser site workflow",
        "browser super",
        "браузер исследуй",
        "браузер аудит",
        "аудит страницы",
        "карта форм",
        "напиши сайт",
        "сайт на tilda",
        "сайт на тильда",
        "тильда",
        "используй платформу",
    ]

    if any(word in text for word in gpt_browser_words):
        return "gpt_browser"

    if any(word in text for word in browser_autopilot_words):
        return "browser"

    if any(word in text for word in automation_words):
        return "automation"

    if any(word in text for word in stability_words):
        return "stability"

    if any(word in text for word in system_words):
        return "system"

    if any(word in text for word in windows_open_words):
        return "windows"

    if last_windows_app and any(word in text for word in windows_type_words):
        return "windows"

    if any(word in text for word in operator_words):
        return "operator"

    if any(word in text for word in report_words):
        return "research"

    if any(word in text for word in research_words):
        return "research"

    if any(word in text for word in project_words):
        return "project"

    if any(word in text for word in codegen_words):
        return "codegen"

    if any(word in text for word in file_words):
        return "files"

    if any(word in text for word in browser_words):
        return "browser"

    return "unknown"
````

### ПУТЬ: core/state.py (43 строк, 1028 байт)

````python
import json
import sys
from pathlib import Path
from modules.project_paths import get_project_root

STATE_FILE = get_project_root() / "memory" / "state.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_state():
    if not STATE_FILE.exists():
        return {}

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def save_state(data: dict):
    try:
        STATE_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except OSError as e:
        print(f"[state] Не удалось сохранить state.json: {e}", file=sys.stderr)


def set_value(key: str, value):
    state = load_state()
    state[key] = value
    save_state(state)


def get_value(key: str, default=None):
    state = load_state()
    return state.get(key, default)
````

### ПУТЬ: desktop/contracts/localcomet_ipc_v1.schema.json (457 строк, 9060 байт)

````json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "localcomet://schemas/ipc/v1",
  "title": "LocalComet IPC v1 Envelope",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "protocol",
    "version",
    "type",
    "id",
    "method",
    "run_id",
    "sequence",
    "reply_to",
    "payload"
  ],
  "properties": {
    "protocol": {
      "const": "localcomet.ipc"
    },
    "version": {
      "const": "1.0"
    },
    "type": {
      "$ref": "#/$defs/envelopeType"
    },
    "id": {
      "$ref": "#/$defs/messageId"
    },
    "method": {
      "anyOf": [
        {
          "$ref": "#/$defs/method"
        },
        {
          "type": "null"
        }
      ]
    },
    "run_id": {
      "anyOf": [
        {
          "$ref": "#/$defs/runId"
        },
        {
          "type": "null"
        }
      ]
    },
    "sequence": {
      "$ref": "#/$defs/sequence"
    },
    "reply_to": {
      "anyOf": [
        {
          "$ref": "#/$defs/messageId"
        },
        {
          "type": "null"
        }
      ]
    },
    "payload": {
      "type": "object",
      "maxProperties": 256
    }
  },
  "allOf": [
    {
      "if": {
        "properties": {
          "type": {
            "const": "error"
          }
        }
      },
      "then": {
        "properties": {
          "payload": {
            "$ref": "#/$defs/errorPayload"
          },
          "reply_to": {
            "$ref": "#/$defs/messageId"
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "type": {
            "const": "cancel"
          }
        }
      },
      "then": {
        "properties": {
          "payload": {
            "$ref": "#/$defs/cancelPayload"
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "method": {
            "const": "chat.delta"
          }
        }
      },
      "then": {
        "properties": {
          "payload": {
            "$ref": "#/$defs/chatDeltaPayload"
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "method": {
            "const": "approval.submit"
          }
        }
      },
      "then": {
        "properties": {
          "payload": {
            "$ref": "#/$defs/approvalSubmitPayload"
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "method": {
            "const": "approval.required"
          }
        }
      },
      "then": {
        "properties": {
          "payload": {
            "$ref": "#/$defs/approvalRequiredPayload"
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "method": {
            "const": "workspace.set"
          }
        }
      },
      "then": {
        "properties": {
          "payload": {
            "$ref": "#/$defs/workspaceSetPayload"
          }
        }
      }
    }
  ],
  "$defs": {
    "envelopeType": {
      "type": "string",
      "enum": [
        "cancel",
        "error",
        "event",
        "goodbye",
        "hello",
        "request",
        "response"
      ]
    },
    "messageId": {
      "type": "string",
      "minLength": 1,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{1,64}$"
    },
    "method": {
      "type": "string",
      "minLength": 1,
      "maxLength": 96,
      "pattern": "^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*){0,7}$"
    },
    "runId": {
      "type": "string",
      "pattern": "^[0-9a-f]{24}$"
    },
    "sequence": {
      "type": "integer",
      "minimum": 0
    },
    "fingerprint": {
      "type": "string",
      "pattern": "^[0-9a-f]{64}$"
    },
    "risk": {
      "type": "string",
      "enum": [
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL"
      ]
    },
    "errorCode": {
      "type": "string",
      "enum": [
        "approval_required",
        "budget_exceeded",
        "busy",
        "duplicate_message_id",
        "frame_too_large",
        "internal_error",
        "invalid_envelope",
        "invalid_frame",
        "invalid_json",
        "invalid_payload",
        "invalid_sequence",
        "kill_switch_active",
        "payload_too_large",
        "policy_blocked",
        "request_cancelled",
        "request_not_found",
        "sidecar_shutdown",
        "sidecar_unavailable",
        "timeout",
        "unsupported_method",
        "unsupported_type",
        "unsupported_version"
      ]
    },
    "cancelReason": {
      "type": "string",
      "enum": [
        "shutdown",
        "timeout",
        "user_requested",
        "window_closing"
      ]
    },
    "approvalScope": {
      "type": "string",
      "enum": [
        "SINGLE_ACTION"
      ]
    },
    "approvalDecision": {
      "type": "string",
      "enum": [
        "approve",
        "deny"
      ]
    },
    "streamChannel": {
      "type": "string",
      "enum": [
        "content",
        "reasoning"
      ]
    },
    "errorPayload": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "code",
        "message",
        "retryable",
        "details"
      ],
      "properties": {
        "code": {
          "$ref": "#/$defs/errorCode"
        },
        "message": {
          "type": "string",
          "maxLength": 512
        },
        "retryable": {
          "type": "boolean"
        },
        "details": {
          "type": "object",
          "maxProperties": 256
        }
      }
    },
    "cancelPayload": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "target_request_id",
        "reason"
      ],
      "properties": {
        "target_request_id": {
          "$ref": "#/$defs/messageId"
        },
        "reason": {
          "$ref": "#/$defs/cancelReason"
        }
      }
    },
    "chatDeltaPayload": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "channel",
        "text",
        "finish_reason"
      ],
      "properties": {
        "channel": {
          "$ref": "#/$defs/streamChannel"
        },
        "text": {
          "type": "string",
          "maxLength": 65536
        },
        "finish_reason": {
          "anyOf": [
            {
              "type": "string",
              "maxLength": 64
            },
            {
              "type": "null"
            }
          ]
        }
      }
    },
    "approvalRequiredPayload": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "action_id",
        "action_fingerprint",
        "risk",
        "summary",
        "target",
        "reversible",
        "expires_at"
      ],
      "properties": {
        "action_id": {
          "$ref": "#/$defs/messageId"
        },
        "action_fingerprint": {
          "$ref": "#/$defs/fingerprint"
        },
        "risk": {
          "$ref": "#/$defs/risk"
        },
        "summary": {
          "type": "string",
          "maxLength": 1024
        },
        "target": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^<PROJECT_ROOT>(/[^\\u0000]*)?$"
            },
            {
              "type": "null"
            }
          ]
        },
        "reversible": {
          "type": "boolean"
        },
        "expires_at": {
          "anyOf": [
            {
              "type": "string",
              "maxLength": 64
            },
            {
              "type": "null"
            }
          ]
        }
      }
    },
    "approvalSubmitPayload": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "action_id",
        "action_fingerprint",
        "decision",
        "scope"
      ],
      "properties": {
        "action_id": {
          "$ref": "#/$defs/messageId"
        },
        "action_fingerprint": {
          "$ref": "#/$defs/fingerprint"
        },
        "decision": {
          "$ref": "#/$defs/approvalDecision"
        },
        "scope": {
          "$ref": "#/$defs/approvalScope"
        }
      }
    },
    "workspaceSetPayload": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "canonical_path",
        "workspace_digest",
        "session_id"
      ],
      "properties": {
        "canonical_path": {
          "type": "string",
          "minLength": 1,
          "maxLength": 4096
        },
        "workspace_digest": {
          "$ref": "#/$defs/fingerprint"
        },
        "session_id": {
          "$ref": "#/$defs/fingerprint"
        }
      }
    },
    "documentEvent": {
      "type": "string",
      "enum": [
        "document.artifact.created",
        "document.confirmation.required",
        "document.failed",
        "document.fields.extracted",
        "document.fields.required",
        "document.ingestion.completed",
        "document.ingestion.started",
        "document.rendering.started",
        "document.verification.completed"
      ]
    }
  }
}
````

### ПУТЬ: desktop/localcomet-desktop/install.bat (4 строк, 148 байт)

````bat
@echo off
cd "C:\\Users\\DNS\\Documents\\LocalComet-build-week-clean\\desktop\\localcomet-desktop"
npm install >NUL 2>&1
echo Installation completed
````

### ПУТЬ: desktop/localcomet-desktop/package.json (28 строк, 782 байт)

````json
{
  "name": "localcomet-desktop",
  "version": "0.0.0-v6.84.6",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite dev --host 127.0.0.1 --port 1420 --strictPort",
    "build": "vite build",
    "bundle:windows": "python ../../tools/build_up00_windows_installer.py --build",
    "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json",
    "test": "vitest run",
    "tauri": "tauri"
  },
  "devDependencies": {
    "@sveltejs/adapter-static": "3.0.10",
    "@sveltejs/kit": "2.69.2",
    "@sveltejs/vite-plugin-svelte": "7.2.0",
    "@tauri-apps/cli": "2.11.4",
    "svelte": "5.56.4",
    "svelte-check": "4.7.2",
    "typescript": "6.0.3",
    "vite": "8.1.4",
    "vitest": "4.1.10"
  },
  "dependencies": {
    "@tauri-apps/api": "2.11.1"
  }
}
````

### ПУТЬ: desktop/localcomet-desktop/README.md (202 строк, 11947 байт)

````markdown
# LocalComet Desktop Shell v6.84.5

This release keeps the bounded v6.84.4 Control Plane bridge, preserves the v6.84.4.1 LocalComet visual system, and adds the first strictly local text-only model gateway.

## Purpose

v6.84.5 supports explicit local model discovery, explicit in-memory binding, one active text inference, bounded SSE streaming, cancellation, and truthful runtime telemetry. The existing Control Plane demo remains a bridge test facility only. It does not call a model, execute a tool, answer the prompt, access files, or persist state.

The desktop layout targets the Control Plane structure: Product Rail, Session Sidebar, Main Workspace, and Agent Inspector. At narrow widths, the Session Sidebar collapses first and the Agent Inspector becomes a drawer.

The minimum supported desktop window layout remains 1000 x 700.

## Architecture

- SvelteKit renders a static frontend into `build/`.
- Tauri loads those bundled assets into the native Windows WebView2 window.
- Production does not require a localhost server or exposed port.
- The Rust application starts exactly one primary window and exposes only seven explicit control-plane commands plus six explicit model-gateway commands.
- The Rust supervisor starts one contained sidecar process and talks to it through framed JSON over stdin/stdout.
- The Python sidecar uses the existing v6.84.1 IPC contract module and implements lifecycle messages only.
- Windows launch uses fixed child arguments, an explicit inherited-handle list, suspended process creation, and a Job Object configured to terminate the sidecar when the supervisor closes.
- v6.84.4 adds a Session / Thread / Turn / Item control-plane model in Python.
- Rust exposes exactly thirteen Tauri commands and one event channel: `localcomet://control-plane-event`.
- The request registry is bounded to 32 in-flight requests with per-request event and text limits.
- Event sequences are validated per request, and duplicate terminal responses or events after terminal responses are rejected.

## Control Plane Surface

Exact Tauri commands:

- `control_plane_bootstrap`
- `control_plane_create_session`
- `control_plane_close_session`
- `control_plane_create_thread`
- `control_plane_start_mock_turn`
- `control_plane_get_turn_status`
- `control_plane_cancel_turn`

Frontend-accessible shutdown, generic request dispatch, filesystem, shell, process, HTTP, provider, model, and environment commands are not exposed.

## Local Model Gateway Surface

Exact Tauri commands:

- `model_gateway_catalog`
- `model_gateway_probe`
- `model_gateway_list_models`
- `model_binding_set`
- `model_turn_start`
- `model_turn_cancel`

The only provider is `openai-compatible-local`. The only endpoint form is internally constructed as `http://127.0.0.1:<PORT>/v1`, where the UI provides only a decimal numeric port. The frontend exposes no URL, API key, custom header, proxy, temperature, tool, attachment, project-context, or persistence controls.

The fixed harness registry contains only `minimal` and `native-localcomet`. Model discovery requires an explicit user action, and a ModelBinding requires explicit confirmation of provider, harness, port, and an exact model ID returned by the current discovery result. Bindings are memory-only.

One local model turn may be active globally. Streaming is text-only and bounded; tool/function responses fail closed. Cancellation is idempotent and closes the active provider connection.

Python IPC methods supported by the control plane:

- `app.bootstrap`
- `app.status`
- `session.create`
- `session.get`
- `session.close`
- `thread.create`
- `thread.get`
- `turn.start_mock`
- `turn.status`
- `turn.cancel`

Lifecycle methods `app.health` and `app.shutdown` remain sidecar-internal.

## Demo Turn

`turn.start_mock` supports `complete` and `wait_for_cancel`. The complete path emits a fixed ten-event sequence ending in `turn.completed`. The cancellation path emits five startup/status events, remains `RUNNING`, and becomes `CANCELLED` only through `turn.cancel`.

The UI labels fixed demo content with a `DEMO` badge and states that there is no model inference or tool execution. It does not present demo text as a real model answer.

## Visual System

- Canonical comet mark is used in the title bar, product rail, and empty state.
- The security emblem is reserved for policy and verification contexts.
- `Local` renders in the primary text color and `Comet` renders in the accent green.
- Dark and light themes use semantic `--lc-*` tokens.
- Runtime telemetry uses `"Cascadia Mono", "JetBrains Mono", Consolas, monospace`.
- Disabled systems show `Not configured`, `Disabled`, `Not evaluated`, `Not run`, or `Unknown`.

## Toolchain

- Node.js 24 or compatible
- npm 11 or compatible
- Rust stable MSVC toolchain
- Cargo
- Windows WebView2 runtime

## Development Commands

From the repository root, the supported full desktop development launch is:

```powershell
python tools\start_localcomet.py
```

The launcher validates the required Windows, Node, npm, Rust, Cargo, CPython 3.14, loopback-port, disk-space, and single-instance prerequisites before it starts Tauri. It synchronizes source into a clean-room workspace, runs `npm ci` when the lockfile changes, prepares the pinned UP00 sidecar resources from current repository source and the local CPython runtime, and then runs `npm run tauri dev` there. Before a versioned resource cache is reused, a fresh deterministic stage supplies a trusted 52-entry identity manifest; the launcher rejects any missing, extra, linked, size-mismatched, or hash-mismatched cached resource and leaves the cache unchanged for explicit removal. Close the LocalComet window or press Ctrl+C in the launcher terminal to stop the launcher-owned process tree.

All generated launch state is isolated under `%LOCALAPPDATA%\LocalCometDev`: the clean-room checkout is in `workspace`, Cargo output is in `cargo-target`, and development application data and startup logs are in `app-data`. The launcher does not inherit Project Knowledge Vault or project-root authority. It neither discovers nor reads a Vault, does not use production `%LOCALAPPDATA%\LocalComet`, and does not modify the installed application.

Generated `node_modules/`, `.svelte-kit/`, `build/`, `src-tauri/target/`, and `src-tauri/binaries/` directories in the source checkout are ignored by Git and excluded from clean-room synchronization, so their presence does not block the supported launch. They are not required by the launcher and are never cleaned automatically.

Read-only diagnostics are available through `python tools\start_localcomet.py doctor`, `python tools\start_localcomet.py status`, and `python tools\start_localcomet.py logs`. `doctor` fails closed if an installed or development LocalComet process is already running.

Run individual Node and Cargo commands from a clean-room copy when validating release containment. Point `CARGO_TARGET_DIR` outside the repository for direct Cargo validation.

## Validation Commands

```powershell
npm run check
npm run test
npm run build
cargo fmt --manifest-path src-tauri\Cargo.toml -- --check
cargo check --manifest-path src-tauri\Cargo.toml --locked
cargo clippy --manifest-path src-tauri\Cargo.toml --locked --all-targets -- -D warnings
cargo test --manifest-path src-tauri\Cargo.toml --locked -- --test-threads=1
npm run tauri build -- --no-bundle
```

## UP00-WP01 Windows installer

The owner-authorized Windows package keeps the existing static Svelte/Tauri/Rust/Python boundary. A generated build workspace stages a private CPython 3.14 runtime and the bounded existing sidecar dependency closure; no generated runtime, `node_modules`, Cargo target, or installer is committed.

From a clean `feat/up00-wp01-windows-one-click-launch` branch, run:

```powershell
npm run bundle:windows
```

The build helper copies tracked source to the ignored root `target/up00-wp01/` area, uses `npm ci --offline` and Cargo offline mode, runs the repository-supported frontend/backend/Rust checks, and invokes the pinned Tauri 2 NSIS target. The installed user does not need Python, Node.js, npm, Cargo, Vite, Tauri CLI, or the repository.

The NSIS package is current-user and unsigned. Installer-owned binaries are placed under `%LOCALAPPDATA%\Programs\LocalComet`; LocalComet user data and startup logs remain under `%LOCALAPPDATA%\LocalComet` and are not removed by the normal uninstall path. Tauri's pinned NSIS template creates `LocalComet` Start Menu and desktop shortcuts and the HKCU uninstall registration. WebView2 is treated as a Windows prerequisite; the installer does not add a network bootstrap.

Do not use this internal package as a public release. Production signing, automatic updates, public-release licensing, and distribution approval remain deferred.

## Production Build Behavior

`npm run build` creates deterministic static frontend assets in `build/`. Tauri production configuration points to that static output through `frontendDist`. The development Vite server is used only by Tauri development mode.

## Current Limits

- The Python sidecar is connected for lifecycle supervision, bounded control-plane demo requests, and one bounded local text model turn.
- Local model inference requires a user-operated OpenAI-compatible server bound to `127.0.0.1`.
- No file access is implemented.
- No autonomous execution is implemented.
- No localhost backend is exposed.
- No planner, action, browser, filesystem, tool, approval, Skill, Memory, Artifact, Channel, or persistence runtime is implemented.
- No Skills, Memory, Channels, or Document Workflow engines are implemented.
- Messages and UI state remain in memory and reset on reload.

## Accessibility

The shell includes semantic navigation and main landmarks, a skip link, keyboard-focus indicators, accessible labels on icon controls, disabled approval buttons with visible text, status text that does not rely on color alone, and reduced-motion CSS.

## Themes

The initial theme mode is system. Light and dark modes are implemented with semantic LocalComet Control Plane CSS custom properties and remain in memory only.

## Folder Structure

```text
desktop/localcomet-desktop/
  src/
    routes/
    lib/
      components/
      data/
      stores/
      types/
  static/
  tests/
  src-tauri/
```

The Agent Inspector component is stored with shell components because it is part of the desktop frame. No empty folders are tracked.

## Security Posture

The frontend does not call provider network APIs, shell APIs, or native file APIs. It talks only to fixed Tauri commands. The CSP is restrictive and allows inline styles only for Svelte/Tauri styling compatibility. The `ipc:` and `http://ipc.localhost` entries in `connect-src` are reserved for Tauri's internal IPC scheme and do not expose a backend.

The Rust supervisor is the only desktop code allowed to own the Python lifecycle sidecar. It does not expose a command bridge to Svelte, does not start shell interpreters, and does not forward broad environment variables or secrets.

The main capability allows only the thirteen explicit app commands plus event listen/unlisten. Tauri's app-command ACL is static through generated command permissions; there is no wildcard permission and no generic command.

## Originality

The visual layout is independently implemented for LocalComet. No Open WebUI source code, CSS, components, branding, logos, names, or assets are copied.

## Dependency Summary

Dependencies are resolved from the official npm registry and crates.io only. The project uses Svelte, SvelteKit, Vite, adapter-static, TypeScript, svelte-check, Vitest, Tauri CLI, Tauri, and tauri-build. No Tailwind, Electron, React, Vue, analytics, telemetry, updater, shell, filesystem, HTTP, SQL, notification, Monaco, CodeMirror, or third-party state framework dependency is included.

Next release:

v6.84.5.1 - Managed Local Model Runtime without LM Studio Dependency
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/binaries/app/modules/desktop_control_plane_ru.py (2347 строк, 100516 байт)

````python
from __future__ import annotations

import hashlib
import re
import secrets
import threading
import uuid
from dataclasses import dataclass, field, fields, replace
from typing import Any, Callable, Mapping

from modules.knowledge_contract_ru import (
    DEFAULT_CONTEXT_CHARS,
    DEFAULT_MAX_RESULTS,
    KnowledgeAdapterError,
    KnowledgeContextError,
    KnowledgeContextRequest,
    KnowledgeContextResult,
    KnowledgeContextState,
    KnowledgeErrorCode,
    QueryIntent,
)
from modules.knowledge_injection_ru import (
    KnowledgeInjectionContractError,
    KnowledgeInjectionDecision,
    KnowledgeInjectionDecisionSource,
    KnowledgeInjectionEnvelope,
    KnowledgeInjectionError,
    KnowledgeInjectionPreview,
    KnowledgeInjectionRecord,
    KnowledgeInjectionState,
    decide_envelope,
    mark_envelope_injected,
    prepare_injection_envelope,
    verify_envelope_integrity,
    verify_provider_messages,
)
from modules.knowledge_change_proposal_ru import KnowledgeChangeProposal, ValidationResult
from modules.knowledge_change_review_ru import (
    CONTRACT_VERSION as KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
    CurrentKnowledgeState,
    KnowledgeChangeReviewArtifact,
    ReviewStatus,
    analyze_review,
)
from modules.knowledge_change_review_decision_ru import (
    CONTRACT_VERSION as HUMAN_REVIEW_DECISION_CONTRACT,
    MAX_ACTOR_DISPLAY_NAME_CHARS,
    MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES,
    MAX_ACTOR_IDENTIFIER_CHARS,
    MAX_ACTOR_IDENTIFIER_UTF8_BYTES,
    MAX_ACTOR_SOURCE_CHARS,
    MAX_ACTOR_SOURCE_UTF8_BYTES,
    MAX_COMMENT_CHARS,
    MAX_COMMENT_UTF8_BYTES,
    HumanReviewDecision,
    HumanReviewDecisionRejected,
    HumanReviewDecisionValue,
    HumanReviewerMetadata,
    create_human_review_decision,
)
from modules.knowledge_review_ui_projection_ru import (
    ProjectionRejected,
    ProjectionRejectionCode,
    materialize_json_value,
    project_human_review_decision,
    project_knowledge_change_review,
    project_knowledge_change_review_summary,
)


DESKTOP_CONTROL_PLANE_VERSION = "v6.84.6"
IPC_PROTOCOL = "localcomet.ipc"
IPC_PROTOCOL_VERSION = "1.0"
SIDECAR_RUNTIME_VERSION = "v6.84.3"
KNOWLEDGE_CONTEXT_CONTROL_PLANE_RELEASE = "v6.84.5.1e5"
KNOWLEDGE_INJECTION_CONTROL_PLANE_RELEASE = "v6.84.5.1e6"
KNOWLEDGE_REVIEW_LIST_CONTRACT = "localcomet.knowledge-review-list/1.0"
KNOWLEDGE_REVIEW_GET_CONTRACT = "localcomet.knowledge-review-get/1.0"
KNOWLEDGE_REVIEW_SNAPSHOT_CONTRACT = "localcomet.knowledge-review-snapshot/1.0"
KNOWLEDGE_REVIEW_REFRESH_CONTRACT = "localcomet.knowledge-review-refresh/1.0"
KNOWLEDGE_REVIEW_DECISION_CREATE_CONTRACT = (
    "localcomet.knowledge-review-decision-create/1.0"
)
KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION = "v6.84.6"
KNOWLEDGE_REVIEW_SOURCE = "LOCAL_CONTROL_PLANE"
MAX_KNOWLEDGE_REVIEW_ARTIFACTS = 128
MAX_KNOWLEDGE_REVIEW_PAGE_SIZE = 50
MAX_KNOWLEDGE_REVIEW_DECISIONS = 128
MAX_REVIEW_ACTIVITY_ITEMS = 128

SESSION_STATES = ("OPEN", "CLOSED")
THREAD_STATES = ("ACTIVE", "CLOSED")
TURN_STATES = ("CREATED", "RUNNING", "CANCELLING", "CANCELLED", "COMPLETED", "FAILED")
ITEM_STATES = ("STARTED", "STREAMING", "COMPLETED", "FAILED")
ITEM_KINDS = (
    "approval_request",
    "assistant_message",
    "reasoning",
    "status",
    "tool_proposal",
    "tool_result",
    "user_message",
    "verification_result",
)
GENERATED_ITEM_KINDS = ("assistant_message", "status", "user_message")
CONTROL_PLANE_METHODS = (
    "app.bootstrap",
    "app.status",
    "knowledge.review.decision.create",
    "knowledge.review.get",
    "knowledge.review.list",
    "knowledge.review.refresh",
    "knowledge.review.snapshot",
    "session.close",
    "session.create",
    "session.get",
    "thread.create",
    "thread.get",
    "turn.cancel",
    "turn.start_mock",
    "turn.status",
)
SUPPORTED_METHODS = tuple(sorted(CONTROL_PLANE_METHODS + ("app.health", "app.shutdown")))
EVENT_METHODS = (
    "item.completed",
    "item.delta",
    "item.started",
    "knowledge.context.failed",
    "knowledge.context.ready",
    "knowledge.context.requested",
    "session.closed",
    "session.created",
    "sidecar.status",
    "thread.created",
    "turn.cancelled",
    "turn.completed",
    "turn.failed",
    "turn.started",
)
CANCEL_REASONS = ("timeout", "user_requested", "window_closing")
BEHAVIORS = ("complete", "pending_model", "wait_for_cancel")
DESKTOP_KNOWLEDGE_ACTIONS = (
    "CANCEL",
    "INCLUDE_AND_SEND",
    "REJECT_AND_SEND_WITHOUT_KNOWLEDGE",
)
ID_RE = re.compile(r"^[0-9a-f]{24}$")
KNOWLEDGE_REVIEW_ID_RE = re.compile(r"^kreview:[0-9a-f]{64}$")
KNOWLEDGE_PROPOSAL_ID_RE = re.compile(r"^kprop:[0-9a-f]{64}$")
KNOWLEDGE_CHANGE_ID_RE = re.compile(r"^kchange:[0-9a-f]{64}$")
KNOWLEDGE_DECISION_ID_RE = re.compile(r"^kdecision:[0-9a-f]{64}$")
VAULT_REVISION_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SECRET_RE = re.compile(
    r"(?i)(sk-[A-Za-z0-9_\-]{8,}|bearer\s+[A-Za-z0-9._\-]{8,}|"
    r"(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s'\";]{6,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----|"
    r"Traceback \(most recent call last\):.*)",
    re.DOTALL,
)
_WINDOWS_USER_PATH_RE = r"[A-Z]:" + r"\\Users\\" + r"[^\\\s]+"
_POSIX_HOME_PATH_RE = "/" + "home" + r"/[^/\s]+"
_MAC_USER_PATH_RE = "/" + "Users" + r"/[^/\s]+"
_UNC_PATH_RE = r"\\\\" + r"[^\\\s]+" + r"\\" + r"[^\\\s]+"
PATH_RE = re.compile(
    r"(?i)("
    + "|".join(
        (
            _WINDOWS_USER_PATH_RE,
            _POSIX_HOME_PATH_RE,
            _MAC_USER_PATH_RE,
            _UNC_PATH_RE,
        )
    )
    + r")"
)


class ControlPlaneError(Exception):
    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.message = _bounded_text(message, 512)
        self.details = dict(details or {})


@dataclass(frozen=True, slots=True)
class ControlPlaneLimits:
    maximum_sessions: int = 16
    maximum_threads_per_session: int = 32
    maximum_turns_per_thread: int = 64
    maximum_items_per_turn: int = 128
    maximum_title_characters: int = 120
    maximum_prompt_characters: int = 8192
    maximum_preview_characters: int = 512
    maximum_item_delta_characters: int = 65536
    maximum_events_per_request: int = 64
    maximum_total_event_text_characters: int = 1_048_576
    maximum_response_json_size: int = 1_048_576
    maximum_remembered_closed_sessions: int = 16
    maximum_knowledge_review_artifacts: int = MAX_KNOWLEDGE_REVIEW_ARTIFACTS
    maximum_knowledge_review_page_size: int = MAX_KNOWLEDGE_REVIEW_PAGE_SIZE
    maximum_knowledge_review_decisions: int = MAX_KNOWLEDGE_REVIEW_DECISIONS

    def __post_init__(self) -> None:
        hard_maximums = {
            "maximum_sessions": 64,
            "maximum_threads_per_session": 128,
            "maximum_turns_per_thread": 256,
            "maximum_items_per_turn": 512,
            "maximum_prompt_characters": 32768,
            "maximum_events_per_request": 256,
            "maximum_total_event_text_characters": 4_194_304,
            "maximum_knowledge_review_artifacts": MAX_KNOWLEDGE_REVIEW_ARTIFACTS,
            "maximum_knowledge_review_page_size": MAX_KNOWLEDGE_REVIEW_PAGE_SIZE,
            "maximum_knowledge_review_decisions": MAX_KNOWLEDGE_REVIEW_DECISIONS,
        }
        for item in fields(self):
            name = item.name
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            hard = hard_maximums.get(name)
            if hard is not None and value > hard:
                raise ValueError(f"{name} exceeds hard maximum")


@dataclass(frozen=True, slots=True)
class ControlPlaneEvent:
    method: str
    sequence: int
    reply_to: str
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ControlPlaneDispatchResult:
    events: tuple[ControlPlaneEvent, ...]
    response: Mapping[str, Any]


@dataclass(slots=True)
class _Session:
    session_id: str
    title: str
    state: str = "OPEN"
    thread_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _Thread:
    thread_id: str
    session_id: str
    title: str
    state: str = "ACTIVE"
    turn_ids: list[str] = field(default_factory=list)
    active_turn_id: str | None = None


@dataclass(slots=True)
class _Turn:
    turn_id: str
    thread_id: str
    state: str
    prompt_sha256: str
    prompt_text: str
    prompt_preview: str
    prompt_character_count: int
    item_ids: list[str] = field(default_factory=list)
    last_sequence: int = -1
    model_called: bool = False
    tools_executed: int = 0
    knowledge_request_id: str | None = None
    knowledge_context: KnowledgeContextResult | None = None


@dataclass(slots=True)
class _Item:
    item_id: str
    turn_id: str
    kind: str
    state: str
    text: str = ""


@dataclass(slots=True)
class _KnowledgeContextRecord:
    request: KnowledgeContextRequest
    result: KnowledgeContextResult
    lifecycle: list[KnowledgeContextState]
    next_sequence: int = 0


@dataclass(frozen=True, slots=True)
class _DesktopKnowledgeDecisionReceipt:
    injection_id: str
    turn_id: str
    action: str
    preview_hash: str
    state: str
    model_turn_id: str | None
    model_dispatched: bool
    knowledge_included: bool

    def to_dict(self, *, duplicate: bool = False) -> dict[str, Any]:
        return {
            "injection_id": self.injection_id,
            "turn_id": self.turn_id,
            "action": self.action,
            "preview_hash": self.preview_hash,
            "state": self.state,
            "decision_source": KnowledgeInjectionDecisionSource.USER_APPROVAL.value,
            "model_turn_id": self.model_turn_id,
            "model_dispatched": self.model_dispatched,
            "knowledge_included": self.knowledge_included,
            "duplicate": duplicate,
        }


class DesktopControlPlane:
    def __init__(
        self,
        *,
        limits: ControlPlaneLimits | None = None,
        id_factory: Callable[[], str] | None = None,
        knowledge_adapter: Any | None = None,
        knowledge_request_id_factory: Callable[[], str] | None = None,
        knowledge_injection_id_factory: Callable[[], str] | None = None,
        knowledge_reviews: (
            list[KnowledgeChangeReviewArtifact]
            | tuple[KnowledgeChangeReviewArtifact, ...]
            | None
        ) = None,
    ) -> None:
        self.limits = limits or default_control_plane_limits()
        self._id_factory = id_factory or _secure_id
        self._knowledge_adapter = knowledge_adapter
        self._knowledge_request_id_factory = knowledge_request_id_factory or _secure_knowledge_request_id
        self._knowledge_injection_id_factory = knowledge_injection_id_factory or _secure_knowledge_injection_id
        self._sessions: dict[str, _Session] = {}
        self._threads: dict[str, _Thread] = {}
        self._turns: dict[str, _Turn] = {}
        self._items: dict[str, _Item] = {}
        self._knowledge_requests: dict[str, _KnowledgeContextRecord] = {}
        self._turn_current_knowledge_request: dict[str, str] = {}
        self._knowledge_injections: dict[str, KnowledgeInjectionRecord] = {}
        self._knowledge_injection_lock = threading.RLock()
        self._desktop_knowledge_receipts: dict[str, _DesktopKnowledgeDecisionReceipt] = {}
        self._desktop_knowledge_in_flight: set[str] = set()
        self._closed_session_ids: list[str] = []
        self._knowledge_review_lock = threading.RLock()
        self._knowledge_reviews = self._snapshot_knowledge_reviews(knowledge_reviews)
        self._knowledge_review_decisions: dict[str, HumanReviewDecision] = {}

    def dispatch(self, method: str, payload: Mapping[str, Any], *, request_id: str) -> ControlPlaneDispatchResult:
        findings = validate_control_plane_payload(method, payload)
        if findings:
            raise ControlPlaneError("invalid_payload", findings[0])
        if method == "app.bootstrap":
            return self._result((), self.bootstrap_snapshot())
        if method == "app.status":
            return self._result((), self.status_snapshot())
        if method == "knowledge.review.list":
            return self._list_knowledge_reviews(payload)
        if method == "knowledge.review.get":
            return self._get_knowledge_review(str(payload["review_artifact_identity"]))
        if method == "knowledge.review.snapshot":
            return self._knowledge_review_snapshot(refresh=False)
        if method == "knowledge.review.refresh":
            return self._knowledge_review_snapshot(refresh=True)
        if method == "knowledge.review.decision.create":
            return self._create_knowledge_review_decision(payload)
        if method == "session.create":
            return self._create_session(payload, request_id)
        if method == "session.get":
            return self._result((), self._session_summary(self._require_session(payload["session_id"])))
        if method == "session.close":
            return self._close_session(str(payload["session_id"]), request_id)
        if method == "thread.create":
            return self._create_thread(payload, request_id)
        if method == "thread.get":
            return self._result((), self._thread_summary(self._require_thread(payload["thread_id"])))
        if method == "turn.start_mock":
            return self._start_mock_turn(payload, request_id)
        if method == "turn.status":
            return self._result((), self._turn_summary(self._require_turn(payload["turn_id"])))
        if method == "turn.cancel":
            return self._cancel_turn(payload, request_id)
        raise ControlPlaneError("unsupported_method", "unsupported control-plane method")

    def _snapshot_knowledge_reviews(
        self,
        knowledge_reviews: (
            list[KnowledgeChangeReviewArtifact]
            | tuple[KnowledgeChangeReviewArtifact, ...]
            | None
        ),
    ) -> tuple[KnowledgeChangeReviewArtifact, ...]:
        if knowledge_reviews is None:
            source: list[KnowledgeChangeReviewArtifact] | tuple[KnowledgeChangeReviewArtifact, ...] = ()
        elif type(knowledge_reviews) not in (list, tuple):
            raise TypeError("knowledge_reviews must be an exact list or tuple")
        else:
            source = knowledge_reviews
        if len(source) > self.limits.maximum_knowledge_review_artifacts:
            raise ValueError("knowledge_reviews exceeds artifact limit")
        snapshot = tuple(source)
        identities: set[str] = set()
        for artifact in snapshot:
            if type(artifact) is not KnowledgeChangeReviewArtifact:
                raise TypeError("knowledge_reviews entries must be exact KnowledgeChangeReviewArtifact")
            identity = artifact.review_artifact_identity
            if identity in identities:
                raise ValueError("duplicate review_artifact_identity")
            identities.add(identity)
        return tuple(sorted(snapshot, key=lambda artifact: artifact.review_artifact_identity))

    def produce_knowledge_review(
        self,
        proposal: KnowledgeChangeProposal,
        validation_result: ValidationResult,
        current_state: CurrentKnowledgeState,
    ) -> KnowledgeChangeReviewArtifact:
        """Produce and retain one real e9b artifact for trusted in-process callers."""
        if type(proposal) is not KnowledgeChangeProposal:
            raise TypeError("proposal must be the exact KnowledgeChangeProposal type")
        if type(validation_result) is not ValidationResult:
            raise TypeError("validation_result must be the exact ValidationResult type")
        if type(current_state) is not CurrentKnowledgeState:
            raise TypeError("current_state must be the exact CurrentKnowledgeState type")

        artifact = analyze_review(proposal, validation_result, current_state)
        if type(artifact) is not KnowledgeChangeReviewArtifact:
            raise TypeError("analyze_review must return the exact KnowledgeChangeReviewArtifact type")

        with self._knowledge_review_lock:
            existing = next(
                (
                    candidate
                    for candidate in self._knowledge_reviews
                    if candidate.review_artifact_identity == artifact.review_artifact_identity
                ),
                None,
            )
            if existing is not None:
                if existing == artifact:
                    return existing
                raise ValueError("review_artifact_identity collision with unequal artifact")
            if len(self._knowledge_reviews) >= self.limits.maximum_knowledge_review_artifacts:
                raise ValueError("knowledge review artifact limit reached")
            self._knowledge_reviews = tuple(
                sorted(
                    (*self._knowledge_reviews, artifact),
                    key=lambda candidate: candidate.review_artifact_identity,
                )
            )
            return artifact

    def _list_knowledge_reviews(
        self,
        payload: Mapping[str, Any],
    ) -> ControlPlaneDispatchResult:
        offset = int(payload["offset"])
        limit = int(payload["limit"])
        if offset > self.limits.maximum_knowledge_review_artifacts:
            raise ControlPlaneError("invalid_payload", "invalid_offset")
        if limit > self.limits.maximum_knowledge_review_page_size:
            raise ControlPlaneError("invalid_payload", "invalid_limit")
        with self._knowledge_review_lock:
            review_snapshot = self._knowledge_reviews
        total_count = len(review_snapshot)
        selected = review_snapshot[offset:offset + limit]
        try:
            items = [
                materialize_json_value(project_knowledge_change_review_summary(artifact))
                for artifact in selected
            ]
        except ProjectionRejected as exc:
            self._raise_projection_error(exc)
        returned_count = len(items)
        next_offset_value = offset + returned_count
        truncated = next_offset_value < total_count
        response = {
            "contract": KNOWLEDGE_REVIEW_LIST_CONTRACT,
            "source": KNOWLEDGE_REVIEW_SOURCE,
            "fixture": False,
            "offset": offset,
            "limit": limit,
            "total_count": total_count,
            "returned_count": returned_count,
            "truncated": truncated,
            "next_offset": next_offset_value if truncated else None,
            "items": items,
        }
        return self._result((), response)

    def _get_knowledge_review(
        self,
        review_artifact_identity: str,
    ) -> ControlPlaneDispatchResult:
        with self._knowledge_review_lock:
            review_snapshot = self._knowledge_reviews
        artifact = next(
            (
                candidate
                for candidate in review_snapshot
                if candidate.review_artifact_identity == review_artifact_identity
            ),
            None,
        )
        if artifact is None:
            raise ControlPlaneError("request_not_found", "knowledge review artifact was not found")
        try:
            projection = materialize_json_value(project_knowledge_change_review(artifact))
        except ProjectionRejected as exc:
            self._raise_projection_error(exc)
        return self._result(
            (),
            {
                "contract": KNOWLEDGE_REVIEW_GET_CONTRACT,
                "source": KNOWLEDGE_REVIEW_SOURCE,
                "fixture": False,
                "projection": projection,
            },
        )

    def _knowledge_review_snapshot(self, *, refresh: bool) -> ControlPlaneDispatchResult:
        adapter_status, refresh_error_code = self._knowledge_adapter_status(refresh=refresh)
        current_revision = adapter_status.get("vault_revision")
        if type(current_revision) is not str or VAULT_REVISION_RE.fullmatch(current_revision) is None:
            current_revision = None
        adapter_state = adapter_status.get("state")
        if type(adapter_state) is not str:
            adapter_state = "NOT_CONFIGURED"
        last_error_code = adapter_status.get("last_error_code")
        if type(last_error_code) is not str:
            last_error_code = refresh_error_code

        with self._knowledge_review_lock:
            review_snapshot = self._knowledge_reviews
            decision_snapshot = tuple(self._knowledge_review_decisions.values())

        review_states: list[dict[str, Any]] = []
        stale_count = 0
        blocked_count = 0
        for artifact in review_snapshot:
            stale = (
                artifact.observed_vault_revision != current_revision
                if current_revision is not None
                else None
            )
            if stale is True:
                stale_count += 1
            if artifact.status is ReviewStatus.BLOCKED:
                blocked_count += 1
            review_states.append(
                {
                    "review_artifact_identity": artifact.review_artifact_identity,
                    "status": artifact.status.value,
                    "stale": stale,
                }
            )

        contract = (
            KNOWLEDGE_REVIEW_REFRESH_CONTRACT
            if refresh
            else KNOWLEDGE_REVIEW_SNAPSHOT_CONTRACT
        )
        return self._result(
            (),
            {
                "contract": contract,
                "command_center_version": KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION,
                "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
                "sidecar_runtime_version": SIDECAR_RUNTIME_VERSION,
                "source": KNOWLEDGE_REVIEW_SOURCE,
                "fixture": False,
                "refresh_requested": refresh,
                "refresh_succeeded": refresh and refresh_error_code is None,
                "current_vault_revision": current_revision,
                "freshness_known": current_revision is not None,
                "knowledge_state": _bounded_text(adapter_state, 64),
                "last_error_code": (
                    _bounded_text(last_error_code, 64)
                    if type(last_error_code) is str
                    else None
                ),
                "inbox_count": len(review_snapshot),
                "stale_count": stale_count,
                "blocked_count": blocked_count,
                "session_decision_count": len(decision_snapshot),
                "review_states": review_states,
                "hard_stop": True,
                "persistence": False,
                "vault_write_authority": False,
                "publication_authority": False,
            },
        )

    def _knowledge_adapter_status(
        self,
        *,
        refresh: bool,
    ) -> tuple[dict[str, Any], str | None]:
        adapter = self._knowledge_adapter
        if adapter is None:
            return (
                {
                    "state": "NOT_CONFIGURED",
                    "vault_revision": None,
                    "last_error_code": "KNOWLEDGE_NOT_CONFIGURED",
                },
                "KNOWLEDGE_NOT_CONFIGURED" if refresh else None,
            )

        refresh_error_code: str | None = None
        if refresh:
            refresh_method = getattr(adapter, "refresh", None)
            if not callable(refresh_method):
                refresh_error_code = "KNOWLEDGE_REFRESH_UNAVAILABLE"
            else:
                try:
                    refresh_method()
                except KnowledgeAdapterError as exc:
                    refresh_error_code = exc.code.value
                except Exception:
                    refresh_error_code = "KNOWLEDGE_REFRESH_FAILED"

        status_method = getattr(adapter, "status", None)
        if not callable(status_method):
            return (
                {
                    "state": "ERROR",
                    "vault_revision": None,
                    "last_error_code": refresh_error_code or "KNOWLEDGE_STATUS_UNAVAILABLE",
                },
                refresh_error_code or "KNOWLEDGE_STATUS_UNAVAILABLE",
            )
        try:
            value = status_method()
        except Exception:
            return (
                {
                    "state": "ERROR",
                    "vault_revision": None,
                    "last_error_code": refresh_error_code or "KNOWLEDGE_STATUS_FAILED",
                },
                refresh_error_code or "KNOWLEDGE_STATUS_FAILED",
            )
        if not isinstance(value, Mapping):
            return (
                {
                    "state": "ERROR",
                    "vault_revision": None,
                    "last_error_code": refresh_error_code or "KNOWLEDGE_STATUS_INVALID",
                },
                refresh_error_code or "KNOWLEDGE_STATUS_INVALID",
            )
        return dict(value), refresh_error_code

    def _fresh_knowledge_vault_revision(self) -> str:
        """Refresh the read-only adapter and return the newly observed Vault revision."""
        adapter = self._knowledge_adapter
        if adapter is None:
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision observation is unavailable",
            )
        refresh_method = getattr(adapter, "refresh", None)
        if not callable(refresh_method):
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision observation is unavailable",
            )
        try:
            refresh_result = refresh_method()
        except KnowledgeAdapterError as exc:
            raise ControlPlaneError(
                "sidecar_unavailable",
                f"fresh Vault revision observation failed: {exc.code.value}",
            ) from None
        except Exception:
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision observation failed",
            ) from None
        if not isinstance(refresh_result, Mapping):
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision observation returned an invalid result",
            )
        revision = refresh_result.get("current_revision")
        if type(revision) is not str or VAULT_REVISION_RE.fullmatch(revision) is None:
            raise ControlPlaneError(
                "sidecar_unavailable",
                "fresh Vault revision is unavailable for a human review decision",
            )
        return revision

    def _require_knowledge_review_artifact(
        self,
        review_artifact_identity: str,
    ) -> KnowledgeChangeReviewArtifact:
        with self._knowledge_review_lock:
            artifact = next(
                (
                    candidate
                    for candidate in self._knowledge_reviews
                    if candidate.review_artifact_identity == review_artifact_identity
                ),
                None,
            )
        if artifact is None:
            raise ControlPlaneError(
                "request_not_found",
                "knowledge review artifact was not found",
            )
        return artifact

    def _create_knowledge_review_decision(
        self,
        payload: Mapping[str, Any],
    ) -> ControlPlaneDispatchResult:
        review_artifact_identity = str(payload["review_artifact_identity"])
        artifact = self._require_knowledge_review_artifact(review_artifact_identity)
        if payload["review_contract_version"] != artifact.contract_version:
            raise ControlPlaneError(
                "invalid_payload",
                "knowledge review contract binding mismatch",
            )

        try:
            actor = HumanReviewerMetadata(
                actor_identifier=str(payload["actor_identifier"]),
                display_name=str(payload["actor_display_name"]),
                source=str(payload["actor_source"]),
            )
        except (TypeError, ValueError):
            raise ControlPlaneError(
                "invalid_payload",
                "human reviewer metadata is invalid",
            ) from None

        current_revision = self._fresh_knowledge_vault_revision()
        try:
            decision = create_human_review_decision(
                artifact,
                expected_proposal_id=str(payload["proposal_id"]),
                expected_review_artifact_identity=review_artifact_identity,
                expected_change_identity=payload["change_identity"],
                expected_observed_vault_revision=str(payload["observed_vault_revision"]),
                current_observed_vault_revision=current_revision,
                decision=str(payload["decision"]),
                comment=str(payload["comment"]),
                actor=actor,
            )
        except HumanReviewDecisionRejected as exc:
            code = exc.code.value
            policy_codes = {
                "BLOCKED_APPROVAL_FORBIDDEN",
                "APPROVAL_REQUIRES_CHANGE_IDENTITY",
                "STALE_CURRENT_VAULT_REVISION",
            }
            raise ControlPlaneError(
                "policy_blocked" if code in policy_codes else "invalid_payload",
                f"human review decision rejected: {code}",
            ) from None

        try:
            projection = materialize_json_value(project_human_review_decision(decision))
        except ProjectionRejected as exc:
            self._raise_projection_error(exc)

        with self._knowledge_review_lock:
            existing = self._knowledge_review_decisions.get(decision.decision_identity)
            duplicate = existing is not None
            if existing is not None and existing != decision:
                raise ControlPlaneError(
                    "internal_error",
                    "human review decision identity collision",
                )
            if existing is None:
                if (
                    len(self._knowledge_review_decisions)
                    >= self.limits.maximum_knowledge_review_decisions
                ):
                    raise ControlPlaneError(
                        "busy",
                        "human review decision session capacity is full",
                    )
                self._knowledge_review_decisions[decision.decision_identity] = decision

        return self._result(
            (),
            {
                "contract": KNOWLEDGE_REVIEW_DECISION_CREATE_CONTRACT,
                "command_center_version": KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION,
                "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
                "sidecar_runtime_version": SIDECAR_RUNTIME_VERSION,
                "source": KNOWLEDGE_REVIEW_SOURCE,
                "fixture": False,
                "duplicate": duplicate,
                "current_vault_revision": current_revision,
                "decision": projection,
                "hard_stop": True,
                "vault_modified": False,
                "persistence": False,
                "publication": False,
            },
        )

    @staticmethod
    def _raise_projection_error(error: ProjectionRejected) -> None:
        if error.code is ProjectionRejectionCode.PROJECTION_JSON_LIMIT_EXCEEDED:
            raise ControlPlaneError(
                "payload_too_large",
                "knowledge review projection exceeds the response bound",
            ) from None
        raise ControlPlaneError(
            "internal_error",
            "knowledge review projection failed",
        ) from None

    def bootstrap_snapshot(self) -> dict[str, Any]:
        snapshot = self.status_snapshot()
        snapshot["capabilities"] = list(CONTROL_PLANE_METHODS)
        snapshot["persistence"] = False
        snapshot["models_connected"] = False
        snapshot["provider_registry_available"] = False
        snapshot["harness_registry_available"] = False
        return snapshot

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "protocol": IPC_PROTOCOL,
            "protocol_version": IPC_PROTOCOL_VERSION,
            "sidecar_runtime_version": SIDECAR_RUNTIME_VERSION,
            "capabilities": list(CONTROL_PLANE_METHODS),
            "limits": {
                "maximum_sessions": self.limits.maximum_sessions,
                "maximum_threads_per_session": self.limits.maximum_threads_per_session,
                "maximum_turns_per_thread": self.limits.maximum_turns_per_thread,
                "maximum_prompt_characters": self.limits.maximum_prompt_characters,
                "maximum_events_per_request": self.limits.maximum_events_per_request,
                "maximum_knowledge_review_artifacts": self.limits.maximum_knowledge_review_artifacts,
                "maximum_knowledge_review_page_size": self.limits.maximum_knowledge_review_page_size,
                "maximum_knowledge_review_decisions": self.limits.maximum_knowledge_review_decisions,
            },
            "counts": self._counts(),
            "sidecar_ready": True,
            "persistence": False,
            "models_connected": False,
            "provider_registry_available": False,
            "harness_registry_available": False,
        }

    def begin_knowledge_context(
        self,
        *,
        query: str,
        intent: QueryIntent | str = QueryIntent.AUTO,
        max_context_chars: int = DEFAULT_CONTEXT_CHARS,
        max_results: int = DEFAULT_MAX_RESULTS,
        include_superseded: bool = False,
        turn_id: str | None = None,
        request_id: str | None = None,
    ) -> ControlPlaneDispatchResult:
        lifecycle_id = request_id if request_id is not None else self._knowledge_request_id_factory()
        try:
            request = KnowledgeContextRequest(
                request_id=lifecycle_id,
                query=query,
                intent=intent,
                max_context_chars=max_context_chars,
                max_results=max_results,
                include_superseded=include_superseded,
                turn_id=turn_id,
            )
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "CONTRACT_VALIDATION_ERROR",
                "knowledge context request failed contract validation",
            ) from exc
        if request.request_id in self._knowledge_requests:
            raise ControlPlaneError(
                "KNOWLEDGE_REQUEST_DUPLICATE",
                "knowledge context request identity already exists",
            )
        if request.turn_id is not None and request.turn_id not in self._turns:
            raise ControlPlaneError(
                "KNOWLEDGE_TURN_NOT_FOUND",
                "knowledge context Turn was not found",
            )
        requested = KnowledgeContextResult(
            request_id=request.request_id,
            turn_id=request.turn_id,
            state=KnowledgeContextState.REQUESTED,
        )
        record = _KnowledgeContextRecord(
            request=request,
            result=requested,
            lifecycle=[KnowledgeContextState.REQUESTED],
        )
        self._knowledge_requests[request.request_id] = record
        if request.turn_id is not None:
            turn = self._turns[request.turn_id]
            turn.knowledge_request_id = request.request_id
            self._turn_current_knowledge_request[request.turn_id] = request.request_id
        event = self._knowledge_event(record, "knowledge.context.requested")
        return self._result((event,), self._knowledge_record_snapshot(record))

    def retrieve_knowledge_context(self, request_id: str) -> ControlPlaneDispatchResult:
        record = self._require_knowledge_request(request_id)
        if record.result.state in {KnowledgeContextState.READY, KnowledgeContextState.FAILED}:
            return self._result((), self._knowledge_record_snapshot(record))
        if record.result.state is not KnowledgeContextState.REQUESTED:
            raise ControlPlaneError(
                "KNOWLEDGE_REQUEST_DUPLICATE",
                "knowledge context retrieval is already in progress",
            )
        record.result = KnowledgeContextResult(
            request_id=record.request.request_id,
            turn_id=record.request.turn_id,
            state=KnowledgeContextState.RETRIEVING,
        )
        record.lifecycle.append(KnowledgeContextState.RETRIEVING)
        try:
            if self._knowledge_adapter is None:
                raise KnowledgeAdapterError(
                    code=KnowledgeErrorCode.KNOWLEDGE_NOT_CONFIGURED,
                    message="KnowledgeAdapter is not configured.",
                )
            adapter_result = self._knowledge_adapter.context_preview(
                record.request.query,
                record.request.intent,
                max_context_chars=record.request.max_context_chars,
                max_results=record.request.max_results,
                include_superseded=record.request.include_superseded,
            )
            if record.request.turn_id is not None and (
                self._turn_current_knowledge_request.get(record.request.turn_id)
                != record.request.request_id
            ):
                return self._fail_knowledge_context(
                    record,
                    "KNOWLEDGE_STALE_RESULT",
                    "stale knowledge context result was rejected",
                )
            ready = self._ready_knowledge_result(record.request, adapter_result)
        except KnowledgeAdapterError as exc:
            return self._fail_knowledge_context(record, exc.code.value, exc.message)
        except (TypeError, ValueError, KeyError) as exc:
            return self._fail_knowledge_context(
                record,
                "CONTRACT_VALIDATION_ERROR",
                "KnowledgeAdapter result failed contract validation.",
            )
        except Exception:
            return self._fail_knowledge_context(
                record,
                "KNOWLEDGE_INTERNAL_ERROR",
                "Knowledge context retrieval failed safely.",
            )
        record.result = ready
        record.lifecycle.append(KnowledgeContextState.READY)
        if record.request.turn_id is not None:
            self._turns[record.request.turn_id].knowledge_context = ready
        event = self._knowledge_event(record, "knowledge.context.ready")
        return self._result((event,), self._knowledge_record_snapshot(record))

    def request_knowledge_context(
        self,
        *,
        query: str,
        intent: QueryIntent | str = QueryIntent.AUTO,
        max_context_chars: int = DEFAULT_CONTEXT_CHARS,
        max_results: int = DEFAULT_MAX_RESULTS,
        include_superseded: bool = False,
        turn_id: str | None = None,
        request_id: str | None = None,
    ) -> ControlPlaneDispatchResult:
        requested = self.begin_knowledge_context(
            query=query,
            intent=intent,
            max_context_chars=max_context_chars,
            max_results=max_results,
            include_superseded=include_superseded,
            turn_id=turn_id,
            request_id=request_id,
        )
        lifecycle_id = str(requested.response["request_id"])
        terminal = self.retrieve_knowledge_context(lifecycle_id)
        return self._result(requested.events + terminal.events, terminal.response)

    def knowledge_context_status(self, request_id: str) -> dict[str, Any]:
        return self._knowledge_record_snapshot(self._require_knowledge_request(request_id))

    def turn_knowledge_context(self, turn_id: str) -> dict[str, Any] | None:
        if turn_id not in self._turns:
            raise ControlPlaneError("KNOWLEDGE_TURN_NOT_FOUND", "knowledge context Turn was not found")
        result = self._turns[turn_id].knowledge_context
        return result.to_dict() if result is not None else None

    def desktop_knowledge_preview(
        self,
        *,
        turn_id: str,
        intent: QueryIntent | str,
        max_context_chars: int,
        max_results: int,
    ) -> dict[str, Any]:
        """Trusted desktop preview derived only from the existing Turn prompt."""
        if turn_id not in self._turns:
            raise ControlPlaneError("KNOWLEDGE_TURN_NOT_FOUND", "knowledge preview Turn was not found")
        turn = self._turns[turn_id]
        if turn.state != "RUNNING" or not turn.prompt_text:
            raise ControlPlaneError("KNOWLEDGE_TURN_MISMATCH", "knowledge preview requires a pending Turn")
        requested = self.request_knowledge_context(
            query=turn.prompt_text,
            intent=intent,
            max_context_chars=max_context_chars,
            max_results=max_results,
            turn_id=turn_id,
        )
        if requested.response.get("state") != KnowledgeContextState.READY.value:
            error = requested.response.get("error")
            return {
                "state": KnowledgeInjectionState.FAILED.value,
                "turn_id": turn_id,
                "request_id": requested.response.get("request_id"),
                "injection_id": None,
                "error": dict(error) if isinstance(error, Mapping) else {
                    "code": "KNOWLEDGE_PREVIEW_FAILED",
                    "safe_message": "Project knowledge preview failed safely.",
                },
                "model_dispatched": False,
                "tools_executed": 0,
            }
        prepared = self.prepare_knowledge_injection(
            turn_id,
            str(requested.response["request_id"]),
        )
        record = self._require_knowledge_injection(str(prepared.response["injection_id"]))
        knowledge_record = self._require_knowledge_request(record.envelope.request_id)
        return self._desktop_preview_snapshot(record, knowledge_record.result)

    def desktop_knowledge_decide(
        self,
        *,
        turn_id: str,
        injection_id: str,
        expected_preview_hash: str,
        action: str,
        model_gateway: Any,
        emit_model_event: Callable[[str, str, int, Mapping[str, Any]], None],
    ) -> dict[str, Any]:
        """Trusted desktop-only USER_APPROVAL decision with atomic dispatch."""
        if action not in DESKTOP_KNOWLEDGE_ACTIONS:
            raise ControlPlaneError("KNOWLEDGE_ACTION_INVALID", "desktop knowledge action is invalid")
        with self._knowledge_injection_lock:
            existing = self._desktop_knowledge_receipts.get(injection_id)
            if existing is not None:
                if (
                    existing.turn_id != turn_id
                    or existing.action != action
                    or existing.preview_hash != expected_preview_hash
                ):
                    return self._desktop_stale_response(
                        turn_id=turn_id,
                        injection_id=injection_id,
                        code="KNOWLEDGE_INJECTION_DUPLICATE_ACTION",
                    )
                current = self._knowledge_injections.get(injection_id)
                response = existing.to_dict(duplicate=True)
                if current is not None and current.envelope.state is KnowledgeInjectionState.INJECTED:
                    response["state"] = KnowledgeInjectionState.INJECTED.value
                return response
            if injection_id in self._desktop_knowledge_in_flight:
                return {
                    "state": "DECIDING",
                    "turn_id": turn_id,
                    "injection_id": injection_id,
                    "action": action,
                    "model_dispatched": False,
                    "duplicate": True,
                }
            record = self._require_knowledge_injection(injection_id)
            try:
                self._validate_desktop_decision_identity(
                    record,
                    turn_id=turn_id,
                    expected_preview_hash=expected_preview_hash,
                )
                if action != "CANCEL":
                    self._validate_injection_current(record, turn_id)
            except KnowledgeInjectionContractError as exc:
                self._fail_knowledge_injection(record, exc, None)
                return self._desktop_stale_response(
                    turn_id=turn_id,
                    injection_id=injection_id,
                    code=exc.code,
                )
            self._desktop_knowledge_in_flight.add(injection_id)
            try:
                gateway_payload: Mapping[str, Any] | None = None
                if action != "CANCEL":
                    gateway_payload = model_gateway.bound_turn_payload(self._turns[turn_id].prompt_text)
                decision = (
                    KnowledgeInjectionDecision.INCLUDE
                    if action == "INCLUDE_AND_SEND"
                    else KnowledgeInjectionDecision.REJECT
                )
                try:
                    envelope = decide_envelope(
                        record.envelope,
                        decision=decision,
                        expected_preview_hash=expected_preview_hash,
                        decision_source=KnowledgeInjectionDecisionSource.USER_APPROVAL,
                    )
                except KnowledgeInjectionContractError as exc:
                    self._fail_knowledge_injection(record, exc, None)
                    return self._desktop_stale_response(
                        turn_id=turn_id,
                        injection_id=injection_id,
                        code=exc.code,
                    )
                record = replace(
                    record,
                    envelope=envelope,
                    lifecycle=record.lifecycle + (envelope.state,),
                )
                event_method = (
                    "knowledge.injection.approved"
                    if envelope.state is KnowledgeInjectionState.APPROVED
                    else "knowledge.injection.rejected"
                )
                _, record = self._injection_event(record, event_method)
                if action == "CANCEL":
                    self._finish_pending_turn_without_model(turn_id, "CANCELLED")
                    receipt = _DesktopKnowledgeDecisionReceipt(
                        injection_id=injection_id,
                        turn_id=turn_id,
                        action=action,
                        preview_hash=expected_preview_hash,
                        state=KnowledgeInjectionState.REJECTED.value,
                        model_turn_id=None,
                        model_dispatched=False,
                        knowledge_included=False,
                    )
                    self._desktop_knowledge_receipts[injection_id] = receipt
                    return receipt.to_dict()

                assert gateway_payload is not None

                def tracked_emit(
                    method: str,
                    model_turn_id: str,
                    sequence: int,
                    payload: Mapping[str, Any],
                ) -> None:
                    self._observe_model_event(turn_id, method, payload)
                    emit_model_event(method, model_turn_id, sequence, payload)

                if action == "INCLUDE_AND_SEND":
                    started = self.dispatch_approved_knowledge_turn(
                        injection_id,
                        model_gateway,
                        gateway_payload,
                        tracked_emit,
                        turn_id=turn_id,
                    )
                    state = "DISPATCHING"
                    knowledge_included = True
                else:
                    started = model_gateway.start_turn(gateway_payload, tracked_emit)
                    state = KnowledgeInjectionState.REJECTED.value
                    knowledge_included = False
                receipt = _DesktopKnowledgeDecisionReceipt(
                    injection_id=injection_id,
                    turn_id=turn_id,
                    action=action,
                    preview_hash=expected_preview_hash,
                    state=state,
                    model_turn_id=str(started["turn_id"]),
                    model_dispatched=True,
                    knowledge_included=knowledge_included,
                )
                self._desktop_knowledge_receipts[injection_id] = receipt
                return receipt.to_dict()
            finally:
                self._desktop_knowledge_in_flight.discard(injection_id)

    @staticmethod
    def _desktop_preview_snapshot(
        record: KnowledgeInjectionRecord,
        result: KnowledgeContextResult,
    ) -> dict[str, Any]:
        envelope = record.envelope
        sources: list[dict[str, Any]] = []
        for source_index, source in enumerate(result.sources):
            sections: list[dict[str, Any]] = []
            envelope_source = envelope.sources[source_index]
            for section_index, section in enumerate(source["selected_sections"]):
                content = section["content"]
                expected_hash = envelope_source["selected_sections"][section_index]["content_sha256"]
                actual_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
                if actual_hash != expected_hash:
                    raise ControlPlaneError(
                        "KNOWLEDGE_INJECTION_CONTEXT_MISMATCH",
                        "knowledge preview content does not match the prepared envelope",
                    )
                sections.append(
                    {
                        "heading": section["heading"],
                        "line_start": section["line_start"],
                        "line_end": section["line_end"],
                        "content": content,
                    }
                )
            sources.append(
                {
                    "note_id": source["note_id"],
                    "title": source.get("title", ""),
                    "relative_path": source["relative_path"],
                    "knowledge_layer": source["knowledge_layer"],
                    "evidence_class": source["evidence_class"],
                    "authority": source["authority"],
                    "status": source["status"],
                    "canonical": source["canonical"],
                    "selected_sections": sections,
                }
            )
        return {
            "state": envelope.state.value,
            "turn_id": envelope.turn_id,
            "request_id": envelope.request_id,
            "injection_id": envelope.injection_id,
            "bundle_id": envelope.bundle_id,
            "preview_hash": envelope.preview_hash,
            "vault_revision": envelope.vault_revision,
            "resolved_intent": envelope.resolved_intent.value,
            "source_count": envelope.source_count,
            "total_chars": envelope.total_chars,
            "truncated": envelope.truncated,
            "sources": sources,
            "model_dispatched": False,
            "tools_executed": 0,
        }

    @staticmethod
    def _desktop_stale_response(*, turn_id: str, injection_id: str, code: str) -> dict[str, Any]:
        return {
            "state": "STALE",
            "turn_id": turn_id,
            "injection_id": injection_id,
            "error": {
                "code": code,
                "safe_message": "Project knowledge changed. Refresh the preview.",
            },
            "model_dispatched": False,
            "tools_executed": 0,
        }

    @staticmethod
    def _validate_desktop_decision_identity(
        record: KnowledgeInjectionRecord,
        *,
        turn_id: str,
        expected_preview_hash: str,
    ) -> None:
        verify_envelope_integrity(record.envelope)
        if record.envelope.state is not KnowledgeInjectionState.PREVIEW_READY:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_STATE_INVALID",
                "knowledge preview is no longer pending a decision",
            )
        if record.envelope.turn_id != turn_id:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_MISMATCH",
                "knowledge preview belongs to a different Turn",
            )
        if record.envelope.preview_hash != expected_preview_hash:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_PREVIEW_MISMATCH",
                "knowledge preview hash does not match",
            )

    def _finish_pending_turn_without_model(self, turn_id: str, state: str) -> None:
        turn = self._turns[turn_id]
        turn.state = state
        thread = self._threads[turn.thread_id]
        if thread.active_turn_id == turn_id:
            thread.active_turn_id = None

    def _observe_model_event(
        self,
        control_plane_turn_id: str,
        method: str,
        payload: Mapping[str, Any],
    ) -> None:
        with self._knowledge_injection_lock:
            turn = self._turns.get(control_plane_turn_id)
            if turn is None:
                return
            if method == "model.turn.started":
                turn.model_called = payload.get("model_called") is True
            elif method == "model.turn.completed":
                turn.model_called = payload.get("model_called") is True
                self._finish_pending_turn_without_model(control_plane_turn_id, "COMPLETED")
            elif method == "model.turn.cancelled":
                turn.model_called = payload.get("model_called") is True
                self._finish_pending_turn_without_model(control_plane_turn_id, "CANCELLED")
            elif method in {"model.turn.timed_out", "model.turn.failed"}:
                turn.model_called = payload.get("model_called") is True
                self._finish_pending_turn_without_model(control_plane_turn_id, "FAILED")

    def prepare_knowledge_injection(
        self,
        turn_id: str,
        knowledge_request_id: str,
        *,
        injection_id: str | None = None,
    ) -> ControlPlaneDispatchResult:
        """Prepare an exact preview without causing tools, network, or model calls."""
        with self._knowledge_injection_lock:
            if turn_id not in self._turns:
                raise ControlPlaneError("KNOWLEDGE_TURN_NOT_FOUND", "knowledge injection Turn was not found")
            knowledge_record = self._require_knowledge_request(knowledge_request_id)
            if knowledge_record.result.state is not KnowledgeContextState.READY:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_NOT_READY",
                    "knowledge context must be READY before injection preparation",
                )
            if knowledge_record.request.turn_id != turn_id:
                raise ControlPlaneError("KNOWLEDGE_TURN_MISMATCH", "knowledge request belongs to a different Turn")
            if self._turn_current_knowledge_request.get(turn_id) != knowledge_request_id:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_STALE_REQUEST",
                    "knowledge request is no longer current for the Turn",
                )
            lifecycle_id = injection_id if injection_id is not None else self._knowledge_injection_id_factory()
            if lifecycle_id in self._knowledge_injections:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_DUPLICATE",
                    "knowledge injection identity already exists",
                )
            try:
                envelope = prepare_injection_envelope(
                    injection_id=lifecycle_id,
                    turn_id=turn_id,
                    knowledge_result=knowledge_record.result,
                )
                preview = KnowledgeInjectionPreview.from_envelope(envelope)
                record = KnowledgeInjectionRecord(
                    envelope=envelope,
                    preview=preview,
                    lifecycle=(KnowledgeInjectionState.PREVIEW_READY,),
                )
            except KnowledgeInjectionContractError as exc:
                raise ControlPlaneError(exc.code, exc.safe_message) from exc
            except (TypeError, ValueError, KeyError) as exc:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_CONTRACT_INVALID",
                    "knowledge injection preview failed contract validation",
                ) from exc
            self._knowledge_injections[envelope.injection_id] = record
            event, record = self._injection_event(record, "knowledge.injection.preview_ready")
            return self._result((event,), record.to_dict())

    def decide_knowledge_injection(
        self,
        injection_id: str,
        decision: KnowledgeInjectionDecision | str,
        expected_preview_hash: str,
        decision_source: KnowledgeInjectionDecisionSource | str,
    ) -> ControlPlaneDispatchResult:
        """Apply an explicit decision to the exact prepared preview."""
        try:
            normalized_source = KnowledgeInjectionDecisionSource(decision_source)
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "KNOWLEDGE_INJECTION_DECISION_INVALID",
                "knowledge injection decision source is invalid",
            ) from exc
        if normalized_source is not KnowledgeInjectionDecisionSource.INTERNAL_EXPLICIT_CALL:
            raise ControlPlaneError(
                "KNOWLEDGE_INJECTION_DECISION_SOURCE_FORBIDDEN",
                "USER_APPROVAL is reserved for the trusted desktop decision command",
            )
        with self._knowledge_injection_lock:
            record = self._require_knowledge_injection(injection_id)
            if record.envelope.state is not KnowledgeInjectionState.PREVIEW_READY:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_STATE_INVALID",
                    "knowledge injection decision requires PREVIEW_READY state",
                )
            try:
                normalized_decision = KnowledgeInjectionDecision(decision)
            except (TypeError, ValueError) as exc:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_DECISION_INVALID",
                    "knowledge injection decision is invalid",
                ) from exc
            if normalized_decision is KnowledgeInjectionDecision.INCLUDE:
                try:
                    self._validate_injection_current(record, record.envelope.turn_id)
                except KnowledgeInjectionContractError as exc:
                    return self._fail_knowledge_injection(record, exc, None)
            try:
                envelope = decide_envelope(
                    record.envelope,
                    decision=normalized_decision,
                    expected_preview_hash=expected_preview_hash,
                    decision_source=normalized_source,
                )
            except KnowledgeInjectionContractError as exc:
                return self._fail_knowledge_injection(record, exc, None)
            record = replace(
                record,
                envelope=envelope,
                lifecycle=record.lifecycle + (envelope.state,),
            )
            method = (
                "knowledge.injection.approved"
                if envelope.state is KnowledgeInjectionState.APPROVED
                else "knowledge.injection.rejected"
            )
            event, record = self._injection_event(record, method)
            return self._result((event,), record.to_dict(include_serialized_context=False))

    def knowledge_injection_status(
        self,
        injection_id: str,
        *,
        include_serialized_context: bool = False,
    ) -> dict[str, Any]:
        with self._knowledge_injection_lock:
            return self._require_knowledge_injection(injection_id).to_dict(
                include_serialized_context=include_serialized_context
            )

    def dispatch_approved_knowledge_turn(
        self,
        injection_id: str,
        model_gateway: Any,
        gateway_payload: Mapping[str, Any],
        emit_model_event: Callable[[str, str, int, Mapping[str, Any]], None],
        *,
        turn_id: str | None = None,
        emit_injection_event: Callable[[ControlPlaneEvent], None] | None = None,
    ) -> dict[str, Any]:
        """Dispatch through the existing gateway without exposing Adapter or Vault access."""
        with self._knowledge_injection_lock:
            record = self._require_knowledge_injection(injection_id)
            expected_turn_id = turn_id if turn_id is not None else record.envelope.turn_id
            if record.envelope.state is not KnowledgeInjectionState.APPROVED:
                raise ControlPlaneError(
                    "KNOWLEDGE_INJECTION_NOT_APPROVED",
                    "knowledge injection envelope is not APPROVED",
                )
            try:
                self._validate_injection_current(record, expected_turn_id)
                self._validate_gateway_prompt(expected_turn_id, gateway_payload)
            except KnowledgeInjectionContractError as exc:
                failure = self._fail_knowledge_injection(record, exc, emit_injection_event)
                raise ControlPlaneError(exc.code, exc.safe_message, details=failure.response) from exc

        def before_outbound(messages: tuple[dict[str, str], ...]) -> None:
            with self._knowledge_injection_lock:
                current = self._require_knowledge_injection(injection_id)
                try:
                    self._validate_injection_current(current, expected_turn_id)
                    verify_provider_messages(
                        messages,
                        current.envelope,
                        expected_turn_id=expected_turn_id,
                    )
                except (ControlPlaneError, KnowledgeInjectionContractError) as exc:
                    if isinstance(exc, ControlPlaneError):
                        contract_error = KnowledgeInjectionContractError(exc.code, exc.message)
                    else:
                        contract_error = exc
                    self._fail_knowledge_injection(current, contract_error, emit_injection_event)
                    raise contract_error

        def after_outbound(messages: tuple[dict[str, str], ...]) -> None:
            with self._knowledge_injection_lock:
                current = self._require_knowledge_injection(injection_id)
                verify_provider_messages(
                    messages,
                    current.envelope,
                    expected_turn_id=expected_turn_id,
                )
                injected = mark_envelope_injected(current.envelope)
                current = replace(
                    current,
                    envelope=injected,
                    lifecycle=current.lifecycle + (KnowledgeInjectionState.INJECTED,),
                )
                event, current = self._injection_event(current, "knowledge.injection.injected")
                if emit_injection_event is not None:
                    emit_injection_event(event)

        try:
            return model_gateway.start_turn_with_knowledge(
                gateway_payload,
                emit_model_event,
                record.envelope,
                control_plane_turn_id=expected_turn_id,
                before_outbound_request=before_outbound,
                after_outbound_request=after_outbound,
            )
        except KnowledgeInjectionContractError as exc:
            with self._knowledge_injection_lock:
                current = self._require_knowledge_injection(injection_id)
                failure = self._fail_knowledge_injection(current, exc, emit_injection_event)
            raise ControlPlaneError(exc.code, exc.safe_message, details=failure.response) from exc

    def _validate_gateway_prompt(self, turn_id: str, gateway_payload: Mapping[str, Any]) -> None:
        if turn_id not in self._turns:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_NOT_FOUND",
                "knowledge injection Turn was not found",
            )
        prompt = gateway_payload.get("prompt")
        if not isinstance(prompt, str):
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_MISMATCH",
                "model request prompt does not match the knowledge Turn",
            )
        normalized = _normalize_prompt(prompt)
        if hashlib.sha256(normalized.encode("utf-8")).hexdigest() != self._turns[turn_id].prompt_sha256:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_MISMATCH",
                "model request prompt does not match the knowledge Turn",
            )

    def _validate_injection_current(
        self,
        record: KnowledgeInjectionRecord,
        expected_turn_id: str,
    ) -> None:
        envelope = record.envelope
        verify_envelope_integrity(envelope)
        if envelope.turn_id != expected_turn_id:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_MISMATCH",
                "knowledge injection envelope belongs to a different Turn",
            )
        if expected_turn_id not in self._turns:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_TURN_NOT_FOUND",
                "knowledge injection Turn was not found",
            )
        if self._turn_current_knowledge_request.get(expected_turn_id) != envelope.request_id:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_STALE_REQUEST",
                "knowledge request is no longer current for the Turn",
            )
        knowledge_record = self._knowledge_requests.get(envelope.request_id)
        if (
            knowledge_record is None
            or knowledge_record.result.state is not KnowledgeContextState.READY
            or knowledge_record.request.turn_id != expected_turn_id
            or knowledge_record.result.bundle_id != envelope.bundle_id
        ):
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_STALE_REQUEST",
                "knowledge request is no longer valid for injection",
            )
        current_revision = self._current_adapter_vault_revision()
        if current_revision != envelope.vault_revision:
            raise KnowledgeInjectionContractError(
                "KNOWLEDGE_INJECTION_STALE",
                "KnowledgeAdapter Vault revision changed after preview",
            )

    def _current_adapter_vault_revision(self) -> str | None:
        if self._knowledge_adapter is None:
            return None
        status = getattr(self._knowledge_adapter, "status", None)
        if not callable(status):
            return None
        try:
            value = status()
        except Exception:
            return None
        if not isinstance(value, Mapping):
            return None
        revision = value.get("vault_revision")
        return revision if isinstance(revision, str) else None

    def _fail_knowledge_injection(
        self,
        record: KnowledgeInjectionRecord,
        error: KnowledgeInjectionContractError,
        event_sink: Callable[[ControlPlaneEvent], None] | None,
    ) -> ControlPlaneDispatchResult:
        if record.envelope.state is KnowledgeInjectionState.FAILED:
            return self._result((), record.to_dict(include_serialized_context=False))
        failed_envelope = replace(record.envelope, state=KnowledgeInjectionState.FAILED)
        failed = replace(
            record,
            envelope=failed_envelope,
            lifecycle=record.lifecycle + (KnowledgeInjectionState.FAILED,),
            error=KnowledgeInjectionError(
                code=error.code,
                safe_message=_bounded_text(_sanitize_text(error.safe_message), 512),
            ),
        )
        event, failed = self._injection_event(failed, "knowledge.injection.failed")
        if event_sink is not None:
            event_sink(event)
        return self._result((event,), failed.to_dict(include_serialized_context=False))

    def _injection_event(
        self,
        record: KnowledgeInjectionRecord,
        method: str,
    ) -> tuple[ControlPlaneEvent, KnowledgeInjectionRecord]:
        envelope = record.envelope
        payload: dict[str, Any] = {
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "injection_id": envelope.injection_id,
            "request_id": envelope.request_id,
            "turn_id": envelope.turn_id,
            "state": envelope.state.value,
            "bundle_id": envelope.bundle_id,
            "vault_revision": envelope.vault_revision,
            "preview_hash": envelope.preview_hash,
            "context_sha256": envelope.serialized_context_sha256,
            "source_count": envelope.source_count,
        }
        if method == "knowledge.injection.failed" and record.error is not None:
            payload["error_code"] = record.error.code
        event = ControlPlaneEvent(
            method=method,
            sequence=record.next_sequence,
            reply_to=envelope.injection_id,
            payload=payload,
        )
        updated = replace(record, next_sequence=record.next_sequence + 1)
        self._knowledge_injections[envelope.injection_id] = updated
        return event, updated

    def _require_knowledge_injection(self, injection_id: str) -> KnowledgeInjectionRecord:
        if injection_id not in self._knowledge_injections:
            raise ControlPlaneError(
                "KNOWLEDGE_INJECTION_NOT_FOUND",
                "knowledge injection was not found",
            )
        return self._knowledge_injections[injection_id]

    @staticmethod
    def _ready_knowledge_result(
        request: KnowledgeContextRequest,
        adapter_result: Mapping[str, Any],
    ) -> KnowledgeContextResult:
        if not isinstance(adapter_result, Mapping):
            raise ValueError("KnowledgeAdapter context result must be an object")
        sources = adapter_result.get("sources")
        relations = adapter_result.get("context_relations")
        warnings = adapter_result.get("warnings")
        if not isinstance(sources, (list, tuple)):
            raise ValueError("KnowledgeAdapter sources must be a bounded sequence")
        if not isinstance(relations, (list, tuple)):
            raise ValueError("KnowledgeAdapter relations must be a bounded sequence")
        if not isinstance(warnings, (list, tuple)):
            raise ValueError("KnowledgeAdapter warnings must be a bounded sequence")
        return KnowledgeContextResult(
            request_id=request.request_id,
            turn_id=request.turn_id,
            state=KnowledgeContextState.READY,
            vault_revision=adapter_result["vault_revision"],
            bundle_id=adapter_result["bundle_id"],
            resolved_intent=adapter_result["resolved_intent"],
            source_count=len(sources),
            total_chars=adapter_result["total_chars"],
            truncated=adapter_result["truncated"],
            sources=tuple(sources),
            context_relations=tuple(relations),
            warnings=tuple(warnings),
        )

    def _fail_knowledge_context(
        self,
        record: _KnowledgeContextRecord,
        code: str,
        safe_message: str,
    ) -> ControlPlaneDispatchResult:
        error = KnowledgeContextError(
            code=str(code),
            safe_message=_bounded_text(_sanitize_text(str(safe_message)), 512),
        )
        record.result = KnowledgeContextResult(
            request_id=record.request.request_id,
            turn_id=record.request.turn_id,
            state=KnowledgeContextState.FAILED,
            error=error,
        )
        record.lifecycle.append(KnowledgeContextState.FAILED)
        event = self._knowledge_event(record, "knowledge.context.failed")
        return self._result((event,), self._knowledge_record_snapshot(record))

    def _knowledge_event(
        self,
        record: _KnowledgeContextRecord,
        method: str,
    ) -> ControlPlaneEvent:
        payload: dict[str, Any] = {
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "request_id": record.request.request_id,
            "turn_id": record.request.turn_id,
            "state": record.result.state.value,
        }
        if method == "knowledge.context.requested":
            payload["intent"] = record.request.intent.value
        elif method == "knowledge.context.ready":
            payload.update(
                {
                    "bundle_id": record.result.bundle_id,
                    "vault_revision": record.result.vault_revision,
                    "source_count": record.result.source_count,
                    "total_chars": record.result.total_chars,
                    "truncated": record.result.truncated,
                }
            )
        elif method == "knowledge.context.failed":
            assert record.result.error is not None
            payload["error_code"] = record.result.error.code
        else:
            raise ControlPlaneError("internal_error", "unsupported knowledge lifecycle event")
        event = ControlPlaneEvent(
            method=method,
            sequence=record.next_sequence,
            reply_to=record.request.request_id,
            payload=payload,
        )
        record.next_sequence += 1
        return event

    @staticmethod
    def _knowledge_record_snapshot(record: _KnowledgeContextRecord) -> dict[str, Any]:
        return {
            **record.result.to_dict(),
            "request": {
                "request_id": record.request.request_id,
                "turn_id": record.request.turn_id,
                "intent": record.request.intent.value,
                "max_context_chars": record.request.max_context_chars,
                "max_results": record.request.max_results,
                "include_superseded": record.request.include_superseded,
            },
            "lifecycle": [state.value for state in record.lifecycle],
        }

    def _require_knowledge_request(self, request_id: str) -> _KnowledgeContextRecord:
        if request_id not in self._knowledge_requests:
            raise ControlPlaneError(
                "KNOWLEDGE_REQUEST_NOT_FOUND",
                "knowledge context request was not found",
            )
        return self._knowledge_requests[request_id]

    def _create_session(self, payload: Mapping[str, Any], request_id: str) -> ControlPlaneDispatchResult:
        if len(self._sessions) >= self.limits.maximum_sessions:
            raise ControlPlaneError("budget_exceeded", "session limit reached")
        session = _Session(session_id=self._new_id(), title=_normalize_title(str(payload.get("title", "")), self.limits))
        self._sessions[session.session_id] = session
        event = self._event(
            "session.created",
            request_id,
            0,
            session_id=session.session_id,
            state=session.state,
            metadata={"title": session.title},
        )
        return self._result((event,), self._session_summary(session))

    def _close_session(self, session_id: str, request_id: str) -> ControlPlaneDispatchResult:
        session = self._require_session(session_id)
        if session.state == "CLOSED":
            return self._result((), self._session_summary(session))
        for thread_id in session.thread_ids:
            thread = self._threads[thread_id]
            if thread.active_turn_id:
                turn = self._turns[thread.active_turn_id]
                if turn.state == "RUNNING":
                    raise ControlPlaneError("busy", "running turn blocks session close")
        session.state = "CLOSED"
        for thread_id in session.thread_ids:
            thread = self._threads[thread_id]
            if thread.active_turn_id is None:
                thread.state = "CLOSED"
        self._closed_session_ids.append(session.session_id)
        self._closed_session_ids = self._closed_session_ids[-self.limits.maximum_remembered_closed_sessions :]
        event = self._event("session.closed", request_id, 0, session_id=session.session_id, state=session.state)
        return self._result((event,), self._session_summary(session))

    def _create_thread(self, payload: Mapping[str, Any], request_id: str) -> ControlPlaneDispatchResult:
        session = self._require_session(payload["session_id"])
        if session.state != "OPEN":
            raise ControlPlaneError("invalid_payload", "session is closed")
        if len(session.thread_ids) >= self.limits.maximum_threads_per_session:
            raise ControlPlaneError("budget_exceeded", "thread limit reached")
        thread = _Thread(
            thread_id=self._new_id(),
            session_id=session.session_id,
            title=_normalize_title(str(payload.get("title", "")), self.limits),
        )
        self._threads[thread.thread_id] = thread
        session.thread_ids.append(thread.thread_id)
        event = self._event(
            "thread.created",
            request_id,
            0,
            session_id=session.session_id,
            thread_id=thread.thread_id,
            state=thread.state,
            metadata={"title": thread.title},
        )
        return self._result((event,), self._thread_summary(thread))

    def _start_mock_turn(self, payload: Mapping[str, Any], request_id: str) -> ControlPlaneDispatchResult:
        thread = self._require_thread(payload["thread_id"])
        session = self._sessions[thread.session_id]
        if session.state != "OPEN" or thread.state != "ACTIVE":
            raise ControlPlaneError("invalid_payload", "thread is not active")
        if thread.active_turn_id is not None and self._turns[thread.active_turn_id].state == "RUNNING":
            raise ControlPlaneError("busy", "thread already has an active turn")
        if len(thread.turn_ids) >= self.limits.maximum_turns_per_thread:
            raise ControlPlaneError("budget_exceeded", "turn limit reached")
        prompt = _normalize_prompt(str(payload["prompt"]))
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        preview = _bounded_text(str(sanitize_control_plane_value(prompt)), self.limits.maximum_preview_characters)
        turn = _Turn(
            turn_id=self._new_id(),
            thread_id=thread.thread_id,
            state="RUNNING",
            prompt_sha256=prompt_hash,
            prompt_text=prompt,
            prompt_preview=preview,
            prompt_character_count=len(prompt),
        )
        self._turns[turn.turn_id] = turn
        thread.turn_ids.append(turn.turn_id)
        thread.active_turn_id = turn.turn_id
        behavior = str(payload["behavior"])
        events = self._mock_turn_events(session.session_id, thread.thread_id, turn, request_id, behavior)
        if behavior == "complete":
            turn.state = "COMPLETED"
            thread.active_turn_id = None
            response = {
                "turn_id": turn.turn_id,
                "state": turn.state,
                "model_called": False,
                "tools_executed": 0,
                "events_emitted": len(events),
            }
        else:
            response = {
                "turn_id": turn.turn_id,
                "state": turn.state,
                "model_called": False,
                "tools_executed": 0,
                "events_emitted": len(events),
                (
                    "waiting_for_decision"
                    if behavior == "pending_model"
                    else "waiting_for_cancel"
                ): True,
            }
        return self._result(events, response)

    def _cancel_turn(self, payload: Mapping[str, Any], request_id: str) -> ControlPlaneDispatchResult:
        turn = self._require_turn(payload["turn_id"])
        thread = self._threads[turn.thread_id]
        session = self._sessions[thread.session_id]
        if turn.state == "CANCELLED":
            return self._result((), {**self._turn_summary(turn), "already_cancelled": True})
        if turn.state in {"COMPLETED", "FAILED"}:
            return self._result((), {**self._turn_summary(turn), "already_terminal": True})
        if turn.state != "RUNNING":
            raise ControlPlaneError("request_cancelled", "turn is not running")
        turn.state = "CANCELLING"
        turn.state = "CANCELLED"
        thread.active_turn_id = None
        event = self._event(
            "turn.cancelled",
            request_id,
            0,
            session_id=session.session_id,
            thread_id=thread.thread_id,
            turn_id=turn.turn_id,
            state=turn.state,
            metadata={"reason": payload["reason"], "cleanup_tools_executed": 0},
        )
        return self._result((event,), {**self._turn_summary(turn), "events_emitted": 1})

    def _mock_turn_events(
        self,
        session_id: str,
        thread_id: str,
        turn: _Turn,
        request_id: str,
        behavior: str,
    ) -> tuple[ControlPlaneEvent, ...]:
        events: list[ControlPlaneEvent] = []

        def add(method: str, *, item: _Item | None = None, state: str = "", text: str | None = None, metadata: Mapping[str, Any] | None = None) -> None:
            sequence = len(events)
            events.append(
                self._event(
                    method,
                    request_id,
                    sequence,
                    session_id=session_id,
                    thread_id=thread_id,
                    turn_id=turn.turn_id,
                    item_id=item.item_id if item else None,
                    state=state,
                    kind=item.kind if item else None,
                    text=text,
                    metadata=metadata,
                )
            )
            turn.last_sequence = sequence

        add("turn.started", state=turn.state)
        user = self._item(turn, "user_message", "STARTED")
        add("item.started", item=user, state=user.state)
        user.state = "COMPLETED"
        add("item.completed", item=user, state=user.state, metadata={"prompt_preview": turn.prompt_preview})
        if behavior == "pending_model":
            return self._checked_events(tuple(events))
        status = self._item(turn, "status", "STARTED")
        add("item.started", item=status, state=status.state)
        status.state = "COMPLETED"
        status.text = "Control Plane demo - no model inference or tool execution."
        add("item.completed", item=status, state=status.state, text=status.text)
        if behavior == "wait_for_cancel":
            return self._checked_events(tuple(events))
        assistant = self._item(turn, "assistant_message", "STARTED")
        add("item.started", item=assistant, state=assistant.state)
        assistant.state = "STREAMING"
        fragment_one = "Control Plane demo connected. "
        fragment_two = "No language model was called and no tool execution occurred."
        assistant.text += fragment_one
        add("item.delta", item=assistant, state=assistant.state, text=fragment_one)
        assistant.text += fragment_two
        add("item.delta", item=assistant, state=assistant.state, text=fragment_two)
        assistant.state = "COMPLETED"
        add("item.completed", item=assistant, state=assistant.state)
        add("turn.completed", state="COMPLETED", metadata={"model_called": False, "tools_executed": 0})
        return self._checked_events(tuple(events))

    def _item(self, turn: _Turn, kind: str, state: str) -> _Item:
        if len(turn.item_ids) >= self.limits.maximum_items_per_turn:
            raise ControlPlaneError("budget_exceeded", "item limit reached")
        item = _Item(item_id=self._new_id(), turn_id=turn.turn_id, kind=kind, state=state)
        self._items[item.item_id] = item
        turn.item_ids.append(item.item_id)
        return item

    def _event(
        self,
        method: str,
        reply_to: str,
        sequence: int,
        *,
        session_id: str | None = None,
        thread_id: str | None = None,
        turn_id: str | None = None,
        item_id: str | None = None,
        state: str = "",
        kind: str | None = None,
        text: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ControlPlaneEvent:
        payload = {
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "session_id": session_id,
            "thread_id": thread_id,
            "turn_id": turn_id,
            "item_id": item_id,
            "state": state,
            "kind": kind,
            "text": _bounded_text(str(sanitize_control_plane_value(text)), self.limits.maximum_item_delta_characters) if text is not None else None,
            "metadata": _flat_metadata(metadata or {}),
        }
        return ControlPlaneEvent(method=method, sequence=sequence, reply_to=reply_to, payload=payload)

    def _checked_events(self, events: tuple[ControlPlaneEvent, ...]) -> tuple[ControlPlaneEvent, ...]:
        if len(events) > self.limits.maximum_events_per_request:
            raise ControlPlaneError("budget_exceeded", "event limit reached")
        text_total = sum(len(str(event.payload.get("text") or "")) for event in events)
        if text_total > self.limits.maximum_total_event_text_characters:
            raise ControlPlaneError("payload_too_large", "event text limit reached")
        return events

    def _result(self, events: tuple[ControlPlaneEvent, ...], response: Mapping[str, Any]) -> ControlPlaneDispatchResult:
        return ControlPlaneDispatchResult(events=self._checked_events(events), response=dict(response))

    def _require_session(self, session_id: str) -> _Session:
        if session_id not in self._sessions:
            raise ControlPlaneError("request_not_found", "session not found")
        return self._sessions[session_id]

    def _require_thread(self, thread_id: str) -> _Thread:
        if thread_id not in self._threads:
            raise ControlPlaneError("request_not_found", "thread not found")
        return self._threads[thread_id]

    def _require_turn(self, turn_id: str) -> _Turn:
        if turn_id not in self._turns:
            raise ControlPlaneError("request_not_found", "turn not found")
        return self._turns[turn_id]

    def _session_summary(self, session: _Session) -> dict[str, Any]:
        return {"session_id": session.session_id, "state": session.state, "title": session.title, "thread_count": len(session.thread_ids)}

    def _thread_summary(self, thread: _Thread) -> dict[str, Any]:
        return {
            "thread_id": thread.thread_id,
            "session_id": thread.session_id,
            "state": thread.state,
            "title": thread.title,
            "turn_count": len(thread.turn_ids),
            "active_turn_id": thread.active_turn_id,
        }

    def _turn_summary(self, turn: _Turn) -> dict[str, Any]:
        knowledge_summary = None
        if turn.knowledge_context is not None:
            knowledge_summary = {
                "request_id": turn.knowledge_context.request_id,
                "state": turn.knowledge_context.state.value,
                "vault_revision": turn.knowledge_context.vault_revision,
                "bundle_id": turn.knowledge_context.bundle_id,
                "source_count": turn.knowledge_context.source_count,
                "total_chars": turn.knowledge_context.total_chars,
                "truncated": turn.knowledge_context.truncated,
            }
        return {
            "turn_id": turn.turn_id,
            "thread_id": turn.thread_id,
            "state": turn.state,
            "prompt_sha256": turn.prompt_sha256,
            "prompt_preview": turn.prompt_preview,
            "prompt_character_count": turn.prompt_character_count,
            "item_count": len(turn.item_ids),
            "last_sequence": turn.last_sequence,
            "model_called": turn.model_called,
            "tools_executed": turn.tools_executed,
            "knowledge_request_id": turn.knowledge_request_id,
            "knowledge_context": knowledge_summary,
        }

    def _counts(self) -> dict[str, int]:
        with self._knowledge_review_lock:
            review_count = len(self._knowledge_reviews)
            decision_count = len(self._knowledge_review_decisions)
        return {
            "sessions": len(self._sessions),
            "threads": len(self._threads),
            "turns": len(self._turns),
            "active_turns": sum(1 for thread in self._threads.values() if thread.active_turn_id is not None),
            "knowledge_reviews": review_count,
            "human_review_decisions": decision_count,
        }

    def _new_id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not ID_RE.match(value):
            raise ControlPlaneError("internal_error", "invalid generated id")
        return value


def default_control_plane_limits() -> ControlPlaneLimits:
    return ControlPlaneLimits()


def validate_control_plane_payload(method: str, payload: Mapping[str, Any]) -> tuple[str, ...]:
    findings: list[str] = []
    if method not in CONTROL_PLANE_METHODS:
        return ("unsupported_method",)
    if not isinstance(payload, Mapping):
        return ("payload_not_object",)
    schemas: dict[str, set[str]] = {
        "app.bootstrap": set(),
        "app.status": set(),
        "knowledge.review.decision.create": {
            "review_contract_version",
            "proposal_id",
            "review_artifact_identity",
            "change_identity",
            "observed_vault_revision",
            "decision",
            "comment",
            "actor_identifier",
            "actor_display_name",
            "actor_source",
        },
        "knowledge.review.get": {"review_artifact_identity"},
        "knowledge.review.list": {"offset", "limit"},
        "knowledge.review.refresh": set(),
        "knowledge.review.snapshot": set(),
        "session.create": {"title"},
        "session.get": {"session_id"},
        "session.close": {"session_id"},
        "thread.create": {"session_id", "title"},
        "thread.get": {"thread_id"},
        "turn.start_mock": {"thread_id", "prompt", "behavior"},
        "turn.status": {"turn_id"},
        "turn.cancel": {"turn_id", "reason"},
    }
    optional = {"session.create": {"title"}, "thread.create": {"title"}}
    allowed = schemas[method]
    missing = allowed - set(payload) - optional.get(method, set())
    extra = set(payload) - allowed
    findings.extend(f"missing_{key}" for key in sorted(missing))
    findings.extend(f"unknown_{key}" for key in sorted(extra))
    limits = default_control_plane_limits()
    for key in ("session_id", "thread_id", "turn_id"):
        if key in payload and not _valid_id(payload[key]):
            findings.append(f"invalid_{key}")
    if "title" in payload and not _valid_title(payload["title"], limits):
        findings.append("invalid_title")
    if method == "knowledge.review.list":
        offset = payload.get("offset")
        limit = payload.get("limit")
        if type(offset) is not int or not 0 <= offset <= MAX_KNOWLEDGE_REVIEW_ARTIFACTS:
            findings.append("invalid_offset")
        if type(limit) is not int or not 1 <= limit <= MAX_KNOWLEDGE_REVIEW_PAGE_SIZE:
            findings.append("invalid_limit")
    if method == "knowledge.review.get":
        review_identity = payload.get("review_artifact_identity")
        if type(review_identity) is not str or KNOWLEDGE_REVIEW_ID_RE.fullmatch(review_identity) is None:
            findings.append("invalid_review_artifact_identity")
    if method == "knowledge.review.decision.create":
        review_contract_version = payload.get("review_contract_version")
        if review_contract_version != KNOWLEDGE_CHANGE_REVIEW_CONTRACT:
            findings.append("invalid_review_contract_version")
        proposal_id = payload.get("proposal_id")
        if type(proposal_id) is not str or KNOWLEDGE_PROPOSAL_ID_RE.fullmatch(proposal_id) is None:
            findings.append("invalid_proposal_id")
        review_identity = payload.get("review_artifact_identity")
        if type(review_identity) is not str or KNOWLEDGE_REVIEW_ID_RE.fullmatch(review_identity) is None:
            findings.append("invalid_review_artifact_identity")
        change_identity = payload.get("change_identity")
        if change_identity is not None and (
            type(change_identity) is not str
            or KNOWLEDGE_CHANGE_ID_RE.fullmatch(change_identity) is None
        ):
            findings.append("invalid_change_identity")
        observed_revision = payload.get("observed_vault_revision")
        if type(observed_revision) is not str or VAULT_REVISION_RE.fullmatch(observed_revision) is None:
            findings.append("invalid_observed_vault_revision")
        if payload.get("decision") not in tuple(item.value for item in HumanReviewDecisionValue):
            findings.append("invalid_decision")
        decision_value = payload.get("decision")
        comment = payload.get("comment")
        if type(comment) is not str:
            findings.append("invalid_comment")
        else:
            if len(comment) > MAX_COMMENT_CHARS or "\x00" in comment:
                findings.append("invalid_comment")
            try:
                if len(comment.encode("utf-8")) > MAX_COMMENT_UTF8_BYTES:
                    findings.append("invalid_comment")
            except UnicodeEncodeError:
                findings.append("invalid_comment")
            if (
                decision_value == HumanReviewDecisionValue.REQUEST_CHANGES.value
                and not comment.strip()
            ):
                findings.append("request_changes_comment_required")
        actor_values = (
            (
                "actor_identifier",
                MAX_ACTOR_IDENTIFIER_CHARS,
                MAX_ACTOR_IDENTIFIER_UTF8_BYTES,
            ),
            (
                "actor_display_name",
                MAX_ACTOR_DISPLAY_NAME_CHARS,
                MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES,
            ),
            (
                "actor_source",
                MAX_ACTOR_SOURCE_CHARS,
                MAX_ACTOR_SOURCE_UTF8_BYTES,
            ),
        )
        for actor_key, actor_limit, actor_byte_limit in actor_values:
            actor_value = payload.get(actor_key)
            invalid_actor = (
                type(actor_value) is not str
                or not actor_value.strip()
                or "\x00" in actor_value
                or len(actor_value) > actor_limit
            )
            if not invalid_actor:
                try:
                    invalid_actor = len(actor_value.encode("utf-8")) > actor_byte_limit
                except UnicodeEncodeError:
                    invalid_actor = True
            if invalid_actor:
                findings.append(f"invalid_{actor_key}")
        if payload.get("actor_source") != "LOCALCOMET_REVIEW_CENTER":
            findings.append("invalid_actor_source")
    if method == "turn.start_mock":
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or len(_normalize_prompt(prompt)) > limits.maximum_prompt_characters:
            findings.append("invalid_prompt")
        if payload.get("behavior") not in BEHAVIORS:
            findings.append("invalid_behavior")
    if method == "turn.cancel" and payload.get("reason") not in CANCEL_REASONS:
        findings.append("invalid_cancel_reason")
    return tuple(sorted(set(findings)))


def sanitize_control_plane_value(value: object) -> object:
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, Mapping):
        return {str(key): sanitize_control_plane_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [sanitize_control_plane_value(child) for child in value]
    if isinstance(value, tuple):
        return [sanitize_control_plane_value(child) for child in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return "<REDACTED_TEXT>"


def serialize_control_plane_metadata() -> dict[str, Any]:
    limits = default_control_plane_limits()
    return {
        "version": DESKTOP_CONTROL_PLANE_VERSION,
        "protocol": IPC_PROTOCOL,
        "protocol_version": IPC_PROTOCOL_VERSION,
        "methods": list(CONTROL_PLANE_METHODS),
        "events": list(EVENT_METHODS),
        "session_states": list(SESSION_STATES),
        "thread_states": list(THREAD_STATES),
        "turn_states": list(TURN_STATES),
        "item_states": list(ITEM_STATES),
        "item_kinds": list(ITEM_KINDS),
        "limits": {
            "maximum_sessions": limits.maximum_sessions,
            "maximum_threads_per_session": limits.maximum_threads_per_session,
            "maximum_turns_per_thread": limits.maximum_turns_per_thread,
            "maximum_items_per_turn": limits.maximum_items_per_turn,
            "maximum_prompt_characters": limits.maximum_prompt_characters,
            "maximum_events_per_request": limits.maximum_events_per_request,
            "maximum_knowledge_review_artifacts": limits.maximum_knowledge_review_artifacts,
            "maximum_knowledge_review_page_size": limits.maximum_knowledge_review_page_size,
            "maximum_knowledge_review_decisions": limits.maximum_knowledge_review_decisions,
        },
        "persistence": False,
        "models_connected": False,
        "provider_registry_available": False,
        "harness_registry_available": False,
    }


def status() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "desktop_control_plane_status",
        "version": DESKTOP_CONTROL_PLANE_VERSION,
        "methods": list(CONTROL_PLANE_METHODS),
        "persistence": False,
        "models_connected": False,
        "provider_registry_available": False,
        "harness_registry_available": False,
    }


def report() -> dict[str, Any]:
    metadata = serialize_control_plane_metadata()
    return {
        "ok": True,
        "mode": "desktop_control_plane_report",
        "version": DESKTOP_CONTROL_PLANE_VERSION,
        "summary": {
            "methods": len(metadata["methods"]),
            "events": len(metadata["events"]),
            "persistence": False,
            "models_connected": False,
        },
        "metadata": metadata,
    }


def _secure_id() -> str:
    return secrets.token_hex(12)


def _secure_knowledge_request_id() -> str:
    return f"kreq:{uuid.uuid4()}"


def _secure_knowledge_injection_id() -> str:
    return f"kinj:{uuid.uuid4()}"


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(ID_RE.match(value))


def _valid_title(value: object, limits: ControlPlaneLimits) -> bool:
    return isinstance(value, str) and len(_normalize_title(value, limits)) <= limits.maximum_title_characters


def _normalize_title(value: str, limits: ControlPlaneLimits) -> str:
    return _bounded_text(str(sanitize_control_plane_value(" ".join(value.split()))), limits.maximum_title_characters)


def _normalize_prompt(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _sanitize_text(text: str) -> str:
    value = SECRET_RE.sub("<REDACTED_TEXT>", text)
    value = PATH_RE.sub("<USER_PATH>", value)
    if "Traceback" in value:
        value = value.split("Traceback", 1)[0] + "<REDACTED_TEXT>"
    return _bounded_text(value, 4096)


def _flat_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, bool)) or value is None:
            result[str(key)[:64]] = sanitize_control_plane_value(value)
    return result


def _bounded_text(value: str, limit: int) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit]
````

