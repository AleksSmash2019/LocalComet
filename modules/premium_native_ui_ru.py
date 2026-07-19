from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import tkinter as tk
from tkinter import ttk


ROOT_DIR = get_project_root()
SETTINGS_DIR = ROOT_DIR / "Projects" / "UI" / "localcomet-premium-native"
SETTINGS_PATH = SETTINGS_DIR / "premium_native_ui_settings.json"
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "premium_native_ui"

PREMIUM_NATIVE_VERSION = "v6.31"
PREMIUM_NATIVE_NAME = "LocalComet Premium UI RU"
_WINDOW_REF = None


PAGES = [
    "Командный центр",
    "AgentOS",
    "Швейцарский нож",
    "Рабочий стол",
    "UI Парсер",
    "Проекты",
    "Патчи",
    "Отчёты",
    "Безопасность",
    "Настройки",
]


STATUS_ITEMS = [
    ("AgentOS Kernel", "В сети", "#34d399"),
    ("Семантический firewall", "Активен", "#34d399"),
    ("PC Codex Core", "Активен", "#60a5fa"),
    ("PC Codex Executor", "Активен", "#60a5fa"),
    ("Screen-Aware Planner", "Готов", "#60a5fa"),
    ("Desktop Primitives", "Готов", "#a78bfa"),
    ("UI Parser Adapter", "Готов", "#fbbf24"),
    ("Swiss Knife Launcher", "Готов", "#a78bfa"),
    ("Patch Registry", "Синхронизирован", "#34d399"),
    ("Auto Verification", "6/6", "#34d399"),
    ("Full Stability", "23/23", "#60a5fa"),
]


SKILLS = [
    ("Исследовательский отчёт", "Рынок, конкуренты, стратегия, технологии.", "низкий"),
    ("Leadgen Brief", "ICP, оффер, каналы без спама и парсинга.", "высокий"),
    ("PDF-анализ", "Краткое содержание, действия, выводы.", "низкий"),
    ("Черновик сайта", "Структура лендинга и демо-сайта.", "средний"),
    ("Автоматизация документов", "Безопасный план обработки файлов.", "высокий"),
    ("Project Patch", "Идея → response.json patch workflow.", "высокий"),
    ("UI Action Suggestion", "Dry-run предложения действий по экрану.", "средний"),
    ("Онбординг агента", "AGENTS.md, quickstart и безопасные уроки.", "низкий"),
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _default_settings():
    return {
        "auto_open_native_on_panel_start": True,
        "disable_browser_auto_open": True,
        "language": "ru",
        "theme": "premium_dark",
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
    settings = _default_settings()
    settings.update({key: loaded.get(key, value) for key, value in settings.items()})
    return settings


def _save_settings(settings):
    _ensure_dirs()
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings


def install_settings():
    _ensure_dirs()
    if not SETTINGS_PATH.exists():
        _save_settings(_default_settings())
    return {
        "ok": True,
        "mode": "premium_native_ui_install_settings",
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

    style.configure("Premium.TFrame", background="#050711")
    style.configure("Panel.TFrame", background="#0b1020", relief="flat")
    style.configure("Premium.TLabel", background="#050711", foreground="#f8fafc")
    style.configure("Muted.TLabel", background="#050711", foreground="#94a3b8")
    style.configure("Panel.TLabel", background="#0b1020", foreground="#f8fafc")
    style.configure("Small.Panel.TLabel", background="#0b1020", foreground="#94a3b8")
    style.configure("Premium.TButton", background="#1d4ed8", foreground="#f8fafc", padding=(12, 8), relief="flat")
    style.map("Premium.TButton", background=[("active", "#2563eb")])
    style.configure("Ghost.TButton", background="#111827", foreground="#dbeafe", padding=(12, 8), relief="flat")
    style.map("Ghost.TButton", background=[("active", "#1f2937")])
    style.configure("Danger.TButton", background="#881337", foreground="#ffe4e6", padding=(12, 8), relief="flat")
    style.map("Danger.TButton", background=[("active", "#be123c")])
    return style


def _clear(frame):
    for child in frame.winfo_children():
        child.destroy()


def _panel(parent, title=None, subtitle=None):
    frame = tk.Frame(parent, bg="#0b1020", highlightbackground="#243047", highlightthickness=1)
    if title:
        tk.Label(frame, text=title, bg="#0b1020", fg="#f8fafc", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=(12, 2))
    if subtitle:
        tk.Label(frame, text=subtitle, bg="#0b1020", fg="#94a3b8", font=("Segoe UI", 9), wraplength=420, justify="left").pack(anchor="w", padx=14, pady=(0, 10))
    return frame


def _metric(parent, title, value, color="#60a5fa"):
    frame = tk.Frame(parent, bg="#111827", highlightbackground="#243047", highlightthickness=1)
    tk.Label(frame, text=title, bg="#111827", fg="#94a3b8", font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(10, 2))
    tk.Label(frame, text=value, bg="#111827", fg=color, font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=12, pady=(0, 10))
    return frame


def _toast(window, message):
    top = tk.Toplevel(window)
    top.overrideredirect(True)
    top.configure(bg="#0b1020")
    top.attributes("-topmost", True)
    label = tk.Label(
        top,
        text=message,
        bg="#0b1020",
        fg="#f8fafc",
        font=("Segoe UI", 10),
        padx=18,
        pady=12,
        highlightbackground="#243047",
        highlightthickness=1,
    )
    label.pack()
    try:
        x = window.winfo_rootx() + window.winfo_width() - 360
        y = window.winfo_rooty() + window.winfo_height() - 90
        top.geometry(f"330x54+{max(0, x)}+{max(0, y)}")
    except Exception:
        top.geometry("330x54+80+80")
    top.after(2400, top.destroy)


def _render_command_center(content, window):
    _clear(content)

    grid = tk.Frame(content, bg="#050711")
    grid.pack(fill="both", expand=True)

    left = _panel(grid, "Статус агента", "Все ключевые подсистемы LocalComet.")
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    mid = _panel(grid, "PC Codex Console", "Командный центр с безопасным dry-run workflow.")
    mid.grid(row=0, column=1, sticky="nsew", padx=10)
    right = _panel(grid, "Живой контекст", "Снимок текущего состояния проекта и рабочего стола.")
    right.grid(row=0, column=2, sticky="nsew", padx=(10, 0))

    grid.columnconfigure(0, weight=0, minsize=260)
    grid.columnconfigure(1, weight=1, minsize=460)
    grid.columnconfigure(2, weight=0, minsize=280)
    grid.rowconfigure(0, weight=1)

    for name, state, color in STATUS_ITEMS:
        row = tk.Frame(left, bg="#111827", highlightbackground="#243047", highlightthickness=1)
        row.pack(fill="x", padx=14, pady=4)
        tk.Label(row, text="●", bg="#111827", fg=color, font=("Segoe UI", 11)).pack(side="left", padx=(10, 8), pady=8)
        tk.Label(row, text=name, bg="#111827", fg="#f8fafc", font=("Segoe UI", 9, "bold")).pack(side="left", pady=8)
        tk.Label(row, text=state, bg="#111827", fg="#94a3b8", font=("Segoe UI", 8)).pack(side="right", padx=10, pady=8)

    messages = tk.Frame(mid, bg="#0b1020")
    messages.pack(fill="both", expand=True, padx=14, pady=10)

    samples = [
        ("Вы", "pc swiss plan создать лендинг для LocalComet"),
        ("LocalComet", "Планирование навыка: Черновик сайта\nFirewall: разрешено · Риск: низкий · Следующий шаг: dry-run"),
        ("LocalComet", "Шаги: 1) исследование → 2) структура → 3) черновик → 4) проверка"),
    ]

    for author, text in samples:
        bubble = tk.Frame(messages, bg="#111827" if author == "LocalComet" else "#1d4ed8", padx=12, pady=10)
        bubble.pack(anchor="w" if author == "LocalComet" else "e", fill="x", padx=8, pady=6)
        tk.Label(bubble, text=author, bg=bubble["bg"], fg="#bfdbfe", font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(bubble, text=text, bg=bubble["bg"], fg="#f8fafc", font=("Segoe UI", 10), justify="left", wraplength=520).pack(anchor="w")

    input_frame = tk.Frame(mid, bg="#0b1020")
    input_frame.pack(fill="x", padx=14, pady=(0, 14))
    entry = tk.Entry(input_frame, bg="#111827", fg="#f8fafc", insertbackground="#f8fafc", relief="flat", font=("Segoe UI", 10))
    entry.insert(0, "Опиши задачу обычным языком...")
    entry.pack(side="left", fill="x", expand=True, ipady=9)
    ttk.Button(input_frame, text="Отправить", style="Premium.TButton", command=lambda: _toast(window, "Команда добавлена как безопасный mock-запрос")).pack(side="left", padx=(10, 0))

    context = [
        ("Активное окно", "LocalComet Control Panel"),
        ("Проект", r"<USER_HOME>\Documents\LocalAgent"),
        ("Последний patch", "v6.31 Native Premium UI RU"),
        ("Auto Verification", "6/6"),
        ("Full Stability", "23/23"),
        ("Режим", "Безопасный · dry-run first"),
    ]

    for title, value in context:
        box = tk.Frame(right, bg="#111827", highlightbackground="#243047", highlightthickness=1)
        box.pack(fill="x", padx=14, pady=5)
        tk.Label(box, text=title, bg="#111827", fg="#94a3b8", font=("Segoe UI", 8)).pack(anchor="w", padx=10, pady=(8, 1))
        tk.Label(box, text=value, bg="#111827", fg="#f8fafc", font=("Segoe UI", 9, "bold"), wraplength=230, justify="left").pack(anchor="w", padx=10, pady=(0, 8))


def _render_agentos(content, window):
    _clear(content)
    header = _panel(content, "AgentOS", "Семантическое ядро, firewall, skills-as-modules и безопасная маршрутизация.")
    header.pack(fill="x", pady=(0, 12))
    pipeline = tk.Frame(header, bg="#0b1020")
    pipeline.pack(fill="x", padx=14, pady=14)
    steps = ["Цель", "Firewall", "Intent", "Skill Router", "Planner", "Dry-run", "Executor", "Report"]
    for idx, step in enumerate(steps):
        box = tk.Frame(pipeline, bg="#111827", highlightbackground="#243047", highlightthickness=1)
        box.grid(row=0, column=idx, sticky="ew", padx=4)
        tk.Label(box, text=step, bg="#111827", fg="#f8fafc", font=("Segoe UI", 9, "bold"), padx=8, pady=14).pack()
        pipeline.columnconfigure(idx, weight=1)

    cards = tk.Frame(content, bg="#050711")
    cards.pack(fill="both", expand=True)
    items = [
        "Single Port",
        "Northbound Intent Interface",
        "Agent Kernel",
        "Semantic Firewall",
        "Skills-as-Modules",
        "Southbound Tool Interface",
        "Personal Knowledge Graph",
        "Rollback / Checkpoints",
    ]
    for i, item in enumerate(items):
        box = _metric(cards, item, "активно", "#34d399" if i % 2 == 0 else "#60a5fa")
        box.grid(row=i // 4, column=i % 4, sticky="nsew", padx=6, pady=6)
        cards.columnconfigure(i % 4, weight=1)


def _render_swiss(content, window):
    _clear(content)
    header = _panel(content, "Швейцарский нож", "Навыки для бизнеса, документов, сайтов, исследований и patch workflow.")
    header.pack(fill="x", pady=(0, 12))
    grid = tk.Frame(content, bg="#050711")
    grid.pack(fill="both", expand=True)
    for i, (name, desc, risk) in enumerate(SKILLS):
        box = _panel(grid, name, desc)
        box.grid(row=i // 4, column=i % 4, sticky="nsew", padx=6, pady=6)
        color = "#34d399" if risk == "низкий" else "#fbbf24" if risk == "средний" else "#fb7185"
        tk.Label(box, text=f"Риск: {risk}", bg="#0b1020", fg=color, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(0, 10))
        buttons = tk.Frame(box, bg="#0b1020")
        buttons.pack(fill="x", padx=14, pady=(0, 14))
        ttk.Button(buttons, text="План", style="Premium.TButton", command=lambda n=name: _toast(window, f"План: {n}")).pack(side="left")
        ttk.Button(buttons, text="Dry-run", style="Ghost.TButton", command=lambda n=name: _toast(window, f"Dry-run: {n}")).pack(side="left", padx=6)
        grid.columnconfigure(i % 4, weight=1)


def _render_desktop(content, window):
    _clear(content)
    header = _panel(content, "Рабочий стол", "Наблюдение и dry-run примитивы без слепых кликов.")
    header.pack(fill="x", pady=(0, 12))
    grid = tk.Frame(content, bg="#050711")
    grid.pack(fill="both", expand=True)

    active = _panel(grid, "Активное окно", "LocalComet Control Panel · Premium Native UI RU")
    active.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=6)
    canvas = tk.Canvas(active, bg="#111827", highlightthickness=1, highlightbackground="#243047", height=230)
    canvas.pack(fill="x", padx=14, pady=14)
    canvas.create_rectangle(26, 26, 430, 180, outline="#60a5fa", dash=(4, 3))
    canvas.create_text(228, 104, text="Preview рабочего стола", fill="#94a3b8", font=("Segoe UI", 12, "bold"))

    windows = _panel(grid, "Окна", "Список безопасного наблюдения.")
    windows.grid(row=0, column=1, sticky="nsew", padx=8, pady=6)
    for name, state in [("LocalComet Control Panel", "активно"), ("VS Code", "фон"), ("Браузер", "фон"), ("LM Studio", "готово")]:
        tk.Label(windows, text=f"{name} — {state}", bg="#111827", fg="#f8fafc", font=("Segoe UI", 10), padx=10, pady=8).pack(fill="x", padx=14, pady=4)

    controls = _panel(grid, "Dry-run управление", "Клики и hotkeys только как проверка/план.")
    controls.grid(row=0, column=2, sticky="nsew", padx=(8, 0), pady=6)
    for label in ["Dry Click", "Dry Hotkey", "Focus Request", "Screenshot Report"]:
        ttk.Button(controls, text=label, style="Ghost.TButton", command=lambda l=label: _toast(window, f"{l}: mock-запрос создан")).pack(fill="x", padx=14, pady=6)

    for col in range(3):
        grid.columnconfigure(col, weight=1)


def _render_table_page(content, title, subtitle, headers, rows):
    _clear(content)
    header = _panel(content, title, subtitle)
    header.pack(fill="x", pady=(0, 12))
    table = _panel(content, "Данные", None)
    table.pack(fill="both", expand=True)
    for c, h in enumerate(headers):
        tk.Label(table, text=h, bg="#111827", fg="#94a3b8", font=("Segoe UI", 9, "bold"), padx=10, pady=8).grid(row=0, column=c, sticky="ew", padx=1, pady=1)
        table.columnconfigure(c, weight=1)
    for r, row in enumerate(rows, start=1):
        for c, cell in enumerate(row):
            tk.Label(table, text=cell, bg="#0b1020", fg="#f8fafc", font=("Segoe UI", 9), padx=10, pady=8, wraplength=300, justify="left").grid(row=r, column=c, sticky="ew", padx=1, pady=1)


def _render_generic(content, window, page_name):
    if page_name == "UI Парсер":
        _render_table_page(
            content,
            "UI Парсер",
            "Элементы интерфейса и безопасные предложения действий.",
            ["тип", "текст", "уверенность", "bbox", "безопасность"],
            [
                ["window", "LocalComet Control Panel", "0.98", "[0,0,1440,900]", "safe"],
                ["button", "Dry Run", "0.94", "[1030,14,1100,48]", "safe"],
                ["input", "Командная строка", "0.91", "[420,12,820,50]", "safe"],
                ["menu", "Швейцарский нож", "0.90", "[12,130,230,166]", "safe"],
            ],
        )
        return

    if page_name == "Проекты":
        rows = [
            ["Текущий проект", r"<USER_HOME>\Documents\LocalAgent", "активен"],
            ["AGENTS.md", "обнаружен и валиден", "ok"],
            ["Стек", "Python + Tkinter + Premium Native UI", "ok"],
            ["Patch readiness", "rollback доступен", "ok"],
        ]
        _render_table_page(content, "Проекты", "Project intelligence и состояние LocalAgent.", ["объект", "значение", "статус"], rows)
        return

    if page_name == "Патчи":
        rows = [
            ["v6.31", "Native Premium UI RU", "готово"],
            ["v6.30b", "Premium UI Now Repair", "не нужен после native repair"],
            ["v6.29b", "Premium UI Launcher", "применён"],
            ["v6.28d", "Premium Dashboard Prototype", "применён"],
            ["v6.27c", "Swiss Knife Skill Launcher", "применён"],
        ]
        _render_table_page(content, "Патчи", "Self-edit registry и история обновлений.", ["версия", "описание", "статус"], rows)
        return

    if page_name == "Отчёты":
        rows = [
            ["Auto Verification", "6/6", "открыть"],
            ["Full Stability", "23/23", "открыть"],
            ["Premium Native UI", "создан", "открыть"],
            ["Swiss Knife", "готов", "открыть"],
        ]
        _render_table_page(content, "Отчёты", "Сводки и безопасные отчёты.", ["отчёт", "статус", "действие"], rows)
        return

    if page_name == "Безопасность":
        _clear(content)
        header = _panel(content, "Безопасность", "Strict profile: без shell, секретов, удаления и слепых действий.")
        header.pack(fill="x", pady=(0, 12))
        grid = tk.Frame(content, bg="#050711")
        grid.pack(fill="both", expand=True)
        rules = [
            "Запрещены shell/cmd/powershell",
            "Запрещены пароли, токены, SSH-ключи",
            "Запрещены delete/format/wipe",
            "Сначала dry-run",
            "Подтверждение для реальных действий",
            "Карантин вместо удаления",
            "Без банковских/платёжных операций",
            "Без спама и массовых DM",
        ]
        for i, rule in enumerate(rules):
            box = _metric(grid, "Правило", rule, "#34d399")
            box.grid(row=i // 4, column=i % 4, sticky="nsew", padx=6, pady=6)
            grid.columnconfigure(i % 4, weight=1)
        return

    if page_name == "Настройки":
        rows = [
            ["Язык", "Русский", "активно"],
            ["Тема", "Premium Dark", "активно"],
            ["Auto-open", "Native window", "активно"],
            ["Browser auto-open", "отключён", "safe"],
            ["Backend bridge", "не подключён", "safe"],
        ]
        _render_table_page(content, "Настройки", "Настройки native premium режима.", ["настройка", "значение", "статус"], rows)
        return


def open_premium_native_ui(panel=None):
    global _WINDOW_REF

    try:
        if _WINDOW_REF is not None and _WINDOW_REF.winfo_exists():
            _WINDOW_REF.lift()
            _WINDOW_REF.focus_force()
            return {
                "ok": True,
                "mode": "premium_native_ui_open",
                "generated_at": _now(),
                "opened": True,
                "reused": True,
            }
    except Exception:
        _WINDOW_REF = None

    install_settings()
    root = _find_root(panel)
    _configure_style(root)

    window = tk.Toplevel(root)
    _WINDOW_REF = window
    window.title("LocalComet Premium UI RU")
    window.configure(bg="#050711")
    window.geometry("1320x820")
    window.minsize(1120, 720)

    shell = tk.Frame(window, bg="#050711")
    shell.pack(fill="both", expand=True)

    sidebar = tk.Frame(shell, bg="#03050d", width=242)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)

    brand = tk.Frame(sidebar, bg="#03050d")
    brand.pack(fill="x", padx=16, pady=16)
    tk.Label(brand, text="⚡", bg="#1d4ed8", fg="#f8fafc", width=3, height=2, font=("Segoe UI", 14, "bold")).pack(side="left")
    title_box = tk.Frame(brand, bg="#03050d")
    title_box.pack(side="left", padx=10)
    tk.Label(title_box, text="LocalComet", bg="#03050d", fg="#f8fafc", font=("Segoe UI", 13, "bold")).pack(anchor="w")
    tk.Label(title_box, text="Premium AI Agent OS", bg="#03050d", fg="#94a3b8", font=("Segoe UI", 8)).pack(anchor="w")

    content_wrap = tk.Frame(shell, bg="#050711")
    content_wrap.pack(side="left", fill="both", expand=True)

    topbar = tk.Frame(content_wrap, bg="#080b16", height=60)
    topbar.pack(fill="x")
    topbar.pack_propagate(False)

    crumb = tk.Label(topbar, text="LocalComet / Командный центр", bg="#080b16", fg="#f8fafc", font=("Segoe UI", 11, "bold"))
    crumb.pack(side="left", padx=18)

    search = tk.Entry(topbar, bg="#111827", fg="#f8fafc", insertbackground="#f8fafc", relief="flat", font=("Segoe UI", 10))
    search.insert(0, "Поиск или команда…")
    search.pack(side="left", fill="x", expand=True, padx=16, ipady=8)

    ttk.Button(topbar, text="Новая задача", style="Premium.TButton", command=lambda: _toast(window, "Новая задача создана как безопасный mock-запрос")).pack(side="left", padx=4)
    ttk.Button(topbar, text="Dry-run", style="Ghost.TButton", command=lambda: _toast(window, "Dry-run поставлен в очередь")).pack(side="left", padx=4)
    ttk.Button(topbar, text="Emergency Stop", style="Danger.TButton", command=lambda: _show_emergency(window)).pack(side="left", padx=(4, 14))

    content = tk.Frame(content_wrap, bg="#050711")
    content.pack(fill="both", expand=True, padx=18, pady=18)

    buttons = {}
    def select(page_name):
        for name, button in buttons.items():
            button.configure(bg="#111827" if name == page_name else "#03050d", fg="#f8fafc" if name == page_name else "#94a3b8")
        crumb.configure(text=f"LocalComet / {page_name}")
        if page_name == "Командный центр":
            _render_command_center(content, window)
        elif page_name == "AgentOS":
            _render_agentos(content, window)
        elif page_name == "Швейцарский нож":
            _render_swiss(content, window)
        elif page_name == "Рабочий стол":
            _render_desktop(content, window)
        else:
            _render_generic(content, window, page_name)

    icons = ["⌘", "🧠", "🛠", "🖥", "🔎", "📁", "🧩", "📄", "🛡", "⚙"]
    nav = tk.Frame(sidebar, bg="#03050d")
    nav.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    for icon, page_name in zip(icons, PAGES):
        btn = tk.Button(
            nav,
            text=f"{icon}  {page_name}",
            bg="#03050d",
            fg="#94a3b8",
            activebackground="#111827",
            activeforeground="#f8fafc",
            relief="flat",
            anchor="w",
            padx=14,
            pady=10,
            font=("Segoe UI", 10),
            command=lambda p=page_name: select(p),
        )
        btn.pack(fill="x", pady=2)
        buttons[page_name] = btn

    footer = tk.Frame(sidebar, bg="#03050d")
    footer.pack(fill="x", padx=14, pady=14)
    tk.Label(footer, text="● Relay подключён", bg="#03050d", fg="#34d399", font=("Segoe UI", 9)).pack(anchor="w", pady=2)
    tk.Label(footer, text="● Safe Mode ON", bg="#03050d", fg="#fbbf24", font=("Segoe UI", 9)).pack(anchor="w", pady=2)
    tk.Label(footer, text="LocalComet v6.31", bg="#03050d", fg="#64748b", font=("Segoe UI", 8)).pack(anchor="w", pady=(8, 0))

    def run_search(event=None):
        query = search.get().strip().lower().replace("ё", "е")
        mapping = {page.lower().replace("ё", "е"): page for page in PAGES}
        for key, value in mapping.items():
            if query and (query in key or key in query):
                select(value)
                return
        _toast(window, f"Команда: {search.get().strip()}")

    search.bind("<Return>", run_search)

    window.bind("<Control-k>", lambda event: search.focus_set())
    window.protocol("WM_DELETE_WINDOW", window.destroy)

    select("Командный центр")

    return {
        "ok": True,
        "mode": "premium_native_ui_open",
        "generated_at": _now(),
        "opened": True,
        "native_window": True,
        "browser": False,
    }


def _show_emergency(window):
    modal = tk.Toplevel(window)
    modal.title("Emergency Stop")
    modal.configure(bg="#080b16")
    modal.geometry("520x260")
    modal.transient(window)
    modal.grab_set()
    tk.Label(modal, text="Подтвердить Emergency Stop", bg="#080b16", fg="#fecdd3", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=22, pady=(22, 8))
    tk.Label(
        modal,
        text="Это безопасное frontend-состояние native UI. Оно не запускает shell, backend, удаление, deploy или системные команды.",
        bg="#080b16",
        fg="#94a3b8",
        wraplength=460,
        justify="left",
        font=("Segoe UI", 10),
    ).pack(anchor="w", padx=22, pady=(0, 18))

    buttons = tk.Frame(modal, bg="#080b16")
    buttons.pack(side="bottom", fill="x", padx=22, pady=18)
    ttk.Button(buttons, text="Отмена", style="Ghost.TButton", command=modal.destroy).pack(side="right", padx=6)
    ttk.Button(buttons, text="Остановить", style="Danger.TButton", command=lambda: (modal.destroy(), _toast(window, "Emergency Stop активирован — mock-состояние"))).pack(side="right")


def auto_open_native_if_enabled(panel=None):
    settings = _load_settings()
    if not settings.get("auto_open_native_on_panel_start", True):
        return {
            "ok": True,
            "mode": "premium_native_ui_auto_open",
            "generated_at": _now(),
            "opened": False,
            "reason": "auto_open_native_on_panel_start disabled",
        }
    return open_premium_native_ui(panel)


def set_auto(enabled):
    settings = _load_settings()
    settings["auto_open_native_on_panel_start"] = bool(enabled)
    settings["updated_at"] = _now()
    _save_settings(settings)
    return {
        "ok": True,
        "mode": "premium_native_ui_auto_setting",
        "generated_at": _now(),
        "auto_open_native_on_panel_start": bool(enabled),
        "settings": str(SETTINGS_PATH),
    }


def status():
    settings = _load_settings()
    return {
        "ok": True,
        "mode": "premium_native_ui_status",
        "generated_at": _now(),
        "name": PREMIUM_NATIVE_NAME,
        "version": PREMIUM_NATIVE_VERSION,
        "native_window": True,
        "browser_auto_open": False,
        "language": "ru",
        "settings": settings,
        "commands": [
            "pc native ui status",
            "pc native ui open",
            "pc native ui auto on",
            "pc native ui auto off",
            "pc native ui report",
            "pc new ui",
            "новый интерфейс",
        ],
        "safety": [
            "Открывается native Tkinter окно, не браузер.",
            "Не запускает npm.",
            "Не запускает shell/cmd/powershell.",
            "Не подключает backend.",
            "Не делает deploy.",
            "Не удаляет файлы.",
            "Не использует токены/API keys.",
        ],
    }


def report():
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "status": status(),
    }
    json_path = REPORTS_DIR / f"premium_native_ui_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"premium_native_ui_report_{_stamp()}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# Premium Native UI RU Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        "- native_window: true",
        "- browser_auto_open: false",
        "- language: ru",
        "",
        "## Safety",
        "",
    ]
    md.extend(f"- {item}" for item in payload["status"]["safety"])
    md_path.write_text("\n".join(md), encoding="utf-8")
    return {
        "ok": True,
        "mode": "premium_native_ui_report",
        "generated_at": _now(),
        "report": str(md_path),
        "json": str(json_path),
    }


def format_payload(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")

    if lower in {"pc native ui", "pc native ui status", "native ui status"}:
        return format_payload(status())

    if lower in {"pc native ui open", "native ui open", "pc new ui", "pc open new ui", "новый интерфейс", "открой новый интерфейс"}:
        return format_payload(open_premium_native_ui())

    if lower in {"pc native ui auto on", "native ui auto on"}:
        return format_payload(set_auto(True))

    if lower in {"pc native ui auto off", "native ui auto off"}:
        return format_payload(set_auto(False))

    if lower in {"pc native ui report", "native ui report"}:
        return format_payload(report())

    return format_payload({
        "ok": False,
        "mode": "premium_native_ui_unknown_command",
        "generated_at": _now(),
        "error": "Неизвестная команда native premium UI.",
        "commands": status().get("commands", []),
    })


def is_premium_native_ui_command(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    exact = {
        "pc native ui",
        "pc native ui status",
        "native ui status",
        "pc native ui open",
        "native ui open",
        "pc native ui auto on",
        "native ui auto on",
        "pc native ui auto off",
        "native ui auto off",
        "pc native ui report",
        "native ui report",
        "pc new ui",
        "pc open new ui",
        "новый интерфейс",
        "открой новый интерфейс",
    }
    return lower in exact
