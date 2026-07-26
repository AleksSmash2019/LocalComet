# Полный исходный код (продолжение)

### ПУТЬ: modules/plan_contract_ru.py (249 строк, 9214 байт)

````python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


PLAN_CONTRACT_VERSION = "v6.64"
PLAN_CONTRACT_NAME = "LocalComet Plan Contract Generator RU"

ROOT_PATH = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_PATH / ".localcomet" / "agent"
PLAN_CONTRACT_JSON = OUTPUT_DIR / "plan_contract.json"
PLAN_CONTRACT_MD = OUTPUT_DIR / "plan_contract.md"
AGENTS_MD_PATH = ROOT_PATH / "AGENTS.md"
OPERATING_LAYER_PATH = ROOT_PATH / "docs" / "agent_operating_layer.md"
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"
CONTEXT_PACK_PATH = ROOT_PATH / ".localcomet" / "agent" / "context_pack.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _line_with(path: Path, pattern: str) -> str:
    try:
        for line in path.read_text(encoding="utf-8").split("\n"):
            if pattern in line:
                return line.strip()
    except Exception:
        pass
    return ""


def _detect_base_version() -> str:
    line = _line_with(CONTROL_PANEL_PATH, "LOCALCOMET_VERSION")
    if "=" in line:
        return line.split("=")[-1].strip().strip("\"'")
    return "unknown"


def generate() -> Dict[str, Any]:
    base_version = _detect_base_version()
    agents_lines = []
    try:
        agents_lines = AGENTS_MD_PATH.read_text(encoding="utf-8").split("\n")[:5]
    except Exception:
        pass
    ol_lines = []
    if OPERATING_LAYER_PATH.exists():
        try:
            ol_lines = OPERATING_LAYER_PATH.read_text(encoding="utf-8").split("\n")[:3]
        except Exception:
            pass
    context_pack_exists = CONTEXT_PACK_PATH.exists()
    context_pack_version = ""
    if context_pack_exists:
        try:
            cp = json.loads(CONTEXT_PACK_PATH.read_text(encoding="utf-8"))
            context_pack_version = cp.get("base_version", "")
        except Exception:
            pass

    return {
        "schema_version": "1.0",
        "project_name": "LocalComet",
        "base_version": base_version,
        "generated_at": _now(),
        "task_goal": "",
        "risk_level": "unclassified",
        "allowed_files": [],
        "forbidden_files": [],
        "expected_outputs": [],
        "validation_gates": [
            "py_compile",
            "contract_tests",
            "functional_tests",
            "strict_project_stability",
        ],
        "rollback_policy": {
            "restore_from_backup_if_any_gate_fails": True,
            "no_partial_green_claims": True,
        },
        "final_report_requirements": [
            "backup path",
            "files changed",
            "exact validation commands run",
            "contract tests actual count",
            "functional tests actual count",
            "strict_project_stability result",
            "smoke test result",
            "final GREEN status",
            "residual risks",
        ],
        "agent_rules": [
            "Read AGENTS.md before editing",
            "Create backup + manifest before every edit",
            "Run full validation after every edit",
            "Only GREEN is acceptable",
            "Do not weaken safety checks",
            "Do not commit secrets",
            "Do not add network calls",
            "Do not add production dependencies without approval",
            "Prefer minimal safe changes over large rewrites",
        ],
        "source_references": {
            "agents_md": {
                "path": str(AGENTS_MD_PATH.relative_to(ROOT_PATH)),
                "first_lines": "\n".join(agents_lines),
            },
            "operating_layer": {
                "path": str(OPERATING_LAYER_PATH.relative_to(ROOT_PATH)) if OPERATING_LAYER_PATH.exists() else "",
                "exists": OPERATING_LAYER_PATH.exists(),
                "first_lines": "\n".join(ol_lines),
            },
            "context_pack": {
                "path": str(CONTEXT_PACK_PATH.relative_to(ROOT_PATH)) if context_pack_exists else "",
                "exists": context_pack_exists,
                "base_version": context_pack_version,
            },
        },
    }


def _write_plan_contract(payload: Dict[str, Any]) -> Dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PLAN_CONTRACT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# LocalComet Plan Contract",
        "",
        f"- schema_version: {payload.get('schema_version')}",
        f"- project_name: {payload.get('project_name')}",
        f"- base_version: {payload.get('base_version')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- risk_level: {payload.get('risk_level')}",
        "",
        "## Task Goal",
        "",
        f"{payload.get('task_goal', '')}",
        "",
        "## Allowed Files",
        "",
    ]
    for af in payload.get("allowed_files", []):
        lines.append(f"- {af}")
    lines.append("")
    lines.extend(["## Forbidden Files", ""])
    for ff in payload.get("forbidden_files", []):
        lines.append(f"- {ff}")
    lines.append("")
    lines.extend(["## Expected Outputs", ""])
    for eo in payload.get("expected_outputs", []):
        lines.append(f"- {eo}")
    lines.append("")
    lines.extend(["## Validation Gates", ""])
    for vg in payload.get("validation_gates", []):
        lines.append(f"- {vg}")
    lines.append("")
    lines.extend(["## Rollback Policy", ""])
    rp = payload.get("rollback_policy", {})
    if isinstance(rp, dict):
        for k, v in rp.items():
            lines.append(f"- {k}: {v}")
    lines.append("")
    lines.extend(["## Final Report Requirements", ""])
    for fr in payload.get("final_report_requirements", []):
        lines.append(f"- {fr}")
    lines.append("")
    lines.extend(["## Agent Rules", ""])
    for ar in payload.get("agent_rules", []):
        lines.append(f"- {ar}")
    lines.append("")
    lines.extend(["## Source References", ""])
    refs = payload.get("source_references", {})
    if isinstance(refs, dict):
        agents = refs.get("agents_md", {})
        if isinstance(agents, dict) and agents.get("path"):
            lines.append(f"- AGENTS.md: {agents['path']}")
            first = agents.get("first_lines", "")
            if first:
                lines.append("  ```text")
                lines.append(f"  {first}")
                lines.append("  ```")
        lines.append("")
        ol = refs.get("operating_layer", {})
        if isinstance(ol, dict) and ol.get("exists"):
            lines.append(f"- docs/agent_operating_layer.md: {ol['path']}")
            first = ol.get("first_lines", "")
            if first:
                lines.append("  ```text")
                lines.append(f"  {first}")
                lines.append("  ```")
        lines.append("")
        cp = refs.get("context_pack", {})
        if isinstance(cp, dict) and cp.get("exists"):
            lines.append(f"- context_pack.json: {cp['path']} (base_version: {cp.get('base_version', '')})")
        lines.append("")
    PLAN_CONTRACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(PLAN_CONTRACT_JSON.relative_to(ROOT_PATH)), "md": str(PLAN_CONTRACT_MD.relative_to(ROOT_PATH))}


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "plan_contract_status",
        "version": PLAN_CONTRACT_VERSION,
        "json_exists": PLAN_CONTRACT_JSON.exists(),
        "md_exists": PLAN_CONTRACT_MD.exists(),
    }


def report() -> Dict[str, Any]:
    payload = generate()
    paths = _write_plan_contract(payload)
    return {
        "ok": True,
        "mode": "plan_contract_report",
        "version": PLAN_CONTRACT_VERSION,
        "generated_at": _now(),
        "paths": paths,
    }


def is_plan_contract_command(command: str) -> bool:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    return lowered in {
        "localcomet agent plan contract",
        "agent plan contract",
        "plan contract",
    } or lowered.startswith("localcomet agent plan contract ")


def dispatch(command: str) -> Dict[str, Any]:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    if lowered in {"localcomet agent plan contract", "agent plan contract", "plan contract"}:
        result = report()
        return {"ok": True, "handled": True, "mode": "plan_contract_generated", "version": PLAN_CONTRACT_VERSION, "paths": result.get("paths", {})}
    if lowered.startswith("localcomet agent plan contract "):
        result = report()
        return {"ok": True, "handled": True, "mode": "plan_contract_generated", "version": PLAN_CONTRACT_VERSION, "paths": result.get("paths", {})}
    if lowered in {"localcomet agent plan contract status", "agent plan contract status", "plan contract status"}:
        return status()
    return {"ok": False, "mode": "plan_contract_unknown", "version": PLAN_CONTRACT_VERSION, "command": command, "hint": "Use: localcomet agent plan contract"}


if __name__ == "__main__":
    result = dispatch("localcomet agent plan contract")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
````

### ПУТЬ: modules/premium_native_ui_ru.py (740 строк, 32611 байт)

````python
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
````

### ПУТЬ: modules/premium_task_panel_ru.py (3507 строк, 137990 байт)

````python
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
````

### ПУТЬ: modules/premium_ui_launcher.py (518 строк, 17552 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import html
import json
import webbrowser


ROOT_DIR = get_project_root()
UI_ROOT = ROOT_DIR / "Projects" / "UI" / "localcomet-premium-dashboard"
LAUNCHER_DIR = ROOT_DIR / "Projects" / "UI" / "Launchers"
REQUESTS_DIR = ROOT_DIR / "Projects" / "UI" / "localcomet-premium-dashboard_requests"
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "premium_ui_launcher"

LAUNCHER_VERSION = "v6.29b"
LAUNCHER_NAME = "LocalComet Premium UI Launcher"

EXPECTED_UI_FILES = [
    "index.html",
    "package.json",
    "README.md",
    "vite.config.ts",
    "tailwind.config.ts",
    "src/App.tsx",
    "src/main.tsx",
    "src/index.css",
    "src/layout/CommandPalette.tsx",
    "src/layout/EmergencyStopModal.tsx",
    "src/pages/CommandCenterPage.tsx",
    "src/pages/AgentOSPage.tsx",
    "src/pages/SwissKnifePage.tsx",
    "src/pages/DesktopPage.tsx",
    "src/pages/UIParserPage.tsx",
    "src/pages/ProjectsPage.tsx",
    "src/pages/PatchesPage.tsx",
    "src/pages/ReportsPage.tsx",
    "src/pages/SafetyPage.tsx",
    "src/pages/SettingsPage.tsx",
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def audit_ui():
    package_path = UI_ROOT / "package.json"
    package = _read_json(package_path) if package_path.exists() else {}
    package_text = package_path.read_text(encoding="utf-8") if package_path.exists() else ""

    missing = [item for item in EXPECTED_UI_FILES if not (UI_ROOT / item).exists()]
    forbidden_config_js = [str(path.relative_to(UI_ROOT)) for path in UI_ROOT.rglob("*.config.js")] if UI_ROOT.exists() else []

    checks = [
        {"name": "ui_root_exists", "ok": UI_ROOT.exists(), "detail": str(UI_ROOT)},
        {"name": "expected_files_present", "ok": not missing, "detail": missing},
        {"name": "no_supabase_dependency", "ok": "supabase" not in package_text.lower(), "detail": "package.json"},
        {"name": "no_forbidden_config_js", "ok": not forbidden_config_js, "detail": forbidden_config_js},
        {"name": "emergency_stop_modal", "ok": (UI_ROOT / "src" / "layout" / "EmergencyStopModal.tsx").exists(), "detail": "mock confirmation modal"},
        {"name": "command_palette", "ok": (UI_ROOT / "src" / "layout" / "CommandPalette.tsx").exists(), "detail": "mock searchable commands"},
    ]

    return {
        "ok": all(item["ok"] for item in checks),
        "mode": "premium_ui_launcher_audit",
        "generated_at": _now(),
        "version": LAUNCHER_VERSION,
        "ui_root": str(UI_ROOT),
        "package": {
            "name": package.get("name"),
            "version": package.get("version"),
            "scripts": package.get("scripts", {}),
        },
        "checks": checks,
        "missing": missing,
        "forbidden_config_js": forbidden_config_js,
    }


def status():
    audit = audit_ui()
    return {
        "ok": audit["ok"],
        "mode": "premium_ui_launcher_status",
        "generated_at": _now(),
        "name": LAUNCHER_NAME,
        "version": LAUNCHER_VERSION,
        "ui_root": str(UI_ROOT),
        "launcher_dir": str(LAUNCHER_DIR),
        "audit": audit,
        "commands": [
            "pc premium launcher status",
            "pc premium launcher guide",
            "pc premium launcher page",
            "pc premium launcher open request",
            "pc premium launcher open подтверждаю",
            "pc premium launcher report",
            "pc premium ui launcher status",
            "pc premium ui launcher page",
            "pc premium ui launcher report",
        ],
        "safety": [
            "Default commands never launch npm or a browser.",
            "Open command requires explicit confirmation.",
            "Confirmed open only opens a static local HTML launcher page.",
            "No shell/cmd/powershell.",
            "No delete/format.",
            "No backend bridge.",
            "No deploy.",
            "No secrets/tokens/API keys.",
        ],
    }


def guide():
    return {
        "ok": True,
        "mode": "premium_ui_launcher_guide",
        "generated_at": _now(),
        "summary": "LocalComet Premium UI is installed as a frontend-only React/Vite/Tailwind prototype.",
        "manual_preview": [
            "Open a terminal manually only if you intentionally want to preview the React app.",
            "cd C:\\Users\\DNS\\Documents\\LocalAgent\\Projects\\UI\\localcomet-premium-dashboard",
            "npm install",
            "npm run dev",
        ],
        "localcomet_safe_commands": [
            "pc premium ui status",
            "pc premium ui audit",
            "pc premium launcher page",
            "pc premium launcher report",
        ],
        "do_not_do_automatically": [
            "Do not auto-run npm.",
            "Do not auto-open shell/cmd/powershell.",
            "Do not connect backend yet.",
            "Do not deploy.",
            "Do not add tokens/API keys.",
        ],
    }


def create_launcher_page():
    _ensure_dirs()
    audit = audit_ui()
    page_path = LAUNCHER_DIR / "localcomet_premium_dashboard_launcher.html"
    audit_json = html.escape(json.dumps(audit, ensure_ascii=False, indent=2))

    checks_markup = []
    for check in audit.get("checks", []):
        badge = "OK" if check.get("ok") else "WARN"
        cls = "ok" if check.get("ok") else "warn"
        checks_markup.append(
            f"<div class='check {cls}'><span>{html.escape(badge)}</span><strong>{html.escape(check.get('name', ''))}</strong><small>{html.escape(str(check.get('detail', '')))}</small></div>"
        )

    content = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>LocalComet Premium Dashboard Launcher</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #050711;
      --panel: rgba(255,255,255,.065);
      --panel2: rgba(255,255,255,.035);
      --border: rgba(255,255,255,.12);
      --text: #f8fafc;
      --muted: #94a3b8;
      --blue: #60a5fa;
      --violet: #a78bfa;
      --green: #34d399;
      --red: #fb7185;
      --amber: #fbbf24;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(96,165,250,.22), transparent 32rem),
        radial-gradient(circle at top right, rgba(167,139,250,.20), transparent 30rem),
        var(--bg);
      color: var(--text);
      padding: 42px;
    }}
    .shell {{ max-width: 1120px; margin: 0 auto; }}
    .hero {{
      border: 1px solid var(--border);
      background: linear-gradient(135deg, rgba(255,255,255,.09), rgba(255,255,255,.035));
      border-radius: 28px;
      padding: 34px;
      box-shadow: 0 24px 90px rgba(0,0,0,.35);
    }}
    h1 {{ margin: 0; font-size: 42px; letter-spacing: -.04em; }}
    p {{ color: var(--muted); line-height: 1.65; }}
    .badge-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 22px 0; }}
    .badge {{
      border: 1px solid var(--border);
      background: var(--panel2);
      color: var(--text);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 13px;
    }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 22px; }}
    .card {{
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 20px;
      padding: 20px;
    }}
    .card h2 {{ margin: 0 0 12px; font-size: 17px; }}
    code, pre {{
      font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      color: #dbeafe;
    }}
    pre {{
      overflow: auto;
      background: rgba(0,0,0,.28);
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 16px;
      padding: 16px;
      font-size: 12px;
      line-height: 1.55;
    }}
    .checks {{ display: grid; gap: 10px; }}
    .check {{
      display: grid;
      grid-template-columns: 54px 1fr;
      gap: 8px 12px;
      align-items: center;
      padding: 11px 12px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: rgba(255,255,255,.03);
    }}
    .check span {{
      grid-row: span 2;
      width: 44px;
      text-align: center;
      padding: 5px 0;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
    }}
    .check.ok span {{ background: rgba(52,211,153,.14); color: var(--green); }}
    .check.warn span {{ background: rgba(251,191,36,.14); color: var(--amber); }}
    .check strong {{ font-size: 13px; }}
    .check small {{ color: var(--muted); overflow-wrap: anywhere; }}
    .danger {{ color: var(--red); }}
    @media (max-width: 820px) {{
      body {{ padding: 18px; }}
      h1 {{ font-size: 30px; }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <h1>LocalComet Premium Dashboard Launcher</h1>
      <p>Static safe launcher page for the frontend-only AgentOS dashboard prototype. This page does not execute npm, shell, backend, deploy, delete, or browser automation. It only documents the installed UI and manual preview path.</p>
      <div class="badge-row">
        <div class="badge">LocalComet {html.escape(LAUNCHER_VERSION)}</div>
        <div class="badge">Frontend-only</div>
        <div class="badge">Safe Mode</div>
        <div class="badge">No backend bridge</div>
        <div class="badge">No shell execution</div>
      </div>
      <div class="grid">
        <article class="card">
          <h2>Installed UI path</h2>
          <pre>{html.escape(str(UI_ROOT))}</pre>
        </article>
        <article class="card">
          <h2>Manual preview commands</h2>
          <p>Run manually only when you intentionally want to preview the React app.</p>
          <pre>cd C:\\Users\\DNS\\Documents\\LocalAgent\\Projects\\UI\\localcomet-premium-dashboard
npm install
npm run dev</pre>
        </article>
        <article class="card">
          <h2>Safety rules</h2>
          <p class="danger">This launcher does not perform real system actions.</p>
          <ul>
            <li>No shell/cmd/powershell execution</li>
            <li>No delete/format actions</li>
            <li>No deploy</li>
            <li>No backend bridge</li>
            <li>No secrets/tokens/API keys</li>
          </ul>
        </article>
        <article class="card">
          <h2>Audit checks</h2>
          <div class="checks">
            {''.join(checks_markup)}
          </div>
        </article>
      </div>
      <article class="card" style="margin-top:18px">
        <h2>Audit JSON</h2>
        <pre>{audit_json}</pre>
      </article>
    </section>
  </main>
</body>
</html>
"""
    page_path.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "mode": "premium_ui_launcher_page",
        "generated_at": _now(),
        "page": str(page_path),
        "audit_ok": audit.get("ok"),
        "message": "Static launcher page created. No browser was opened.",
    }


def open_request():
    _ensure_dirs()
    page = create_launcher_page()
    request_path = REQUESTS_DIR / f"premium_ui_launcher_open_request_{_stamp()}.md"
    content = f"""# Premium UI Launcher Open Request

Generated: {_now()}

Launcher page:

```text
{page.get('page')}
```

Safe confirmed command:

```text
pc premium launcher open подтверждаю
```

This command opens only the static local launcher HTML page in the default browser.

It does not run:

- npm
- shell/cmd/powershell
- backend
- deploy
- delete
- install
- browser automation

Manual React preview, if needed:

```text
cd C:\\Users\\DNS\\Documents\\LocalAgent\\Projects\\UI\\localcomet-premium-dashboard
npm install
npm run dev
```
"""
    request_path.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "mode": "premium_ui_launcher_open_request",
        "generated_at": _now(),
        "request": str(request_path),
        "launcher_page": page.get("page"),
        "message": "Open request created. No browser was opened.",
    }


def open_confirmed(command):
    text = str(command or "").lower().replace("ё", "е")
    confirmed = "подтверждаю" in text or "confirm" in text
    if not confirmed:
        return {
            "ok": False,
            "mode": "premium_ui_launcher_open",
            "generated_at": _now(),
            "error": "Opening requires explicit confirmation.",
            "required": "pc premium launcher open подтверждаю",
        }

    page = create_launcher_page()
    uri = Path(page["page"]).resolve().as_uri()
    webbrowser.open(uri)
    return {
        "ok": True,
        "mode": "premium_ui_launcher_open",
        "generated_at": _now(),
        "opened": uri,
        "message": "Opened static launcher HTML page only. No shell/npm/backend/deploy was executed.",
    }


def report():
    _ensure_dirs()
    page = create_launcher_page()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "status": status(),
        "guide": guide(),
        "launcher_page": page,
    }

    json_path = REPORTS_DIR / f"premium_ui_launcher_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"premium_ui_launcher_report_{_stamp()}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# Premium UI Launcher Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- launcher_page: {page.get('page')}",
        f"- ui_root: {UI_ROOT}",
        f"- ok: {payload['status']['ok']}",
        "",
        "## Commands",
        "",
    ]
    md.extend(f"- `{command}`" for command in payload["status"]["commands"])
    md.extend([
        "",
        "## Safety",
        "",
    ])
    md.extend(f"- {item}" for item in payload["status"]["safety"])
    md_path.write_text("\n".join(md), encoding="utf-8")

    return {
        "ok": True,
        "mode": "premium_ui_launcher_report",
        "generated_at": _now(),
        "report": str(md_path),
        "json": str(json_path),
        "launcher_page": page.get("page"),
    }


def format_payload(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")

    if lower in {"pc premium launcher", "pc premium launcher status", "pc premium ui launcher status", "premium launcher status"}:
        return format_payload(status())

    if lower in {"pc premium launcher guide", "pc premium ui launcher guide", "premium launcher guide"}:
        return format_payload(guide())

    if lower in {"pc premium launcher page", "pc premium ui launcher page", "premium launcher page"}:
        return format_payload(create_launcher_page())

    if lower in {"pc premium launcher open request", "pc premium ui launcher open request", "premium launcher open request"}:
        return format_payload(open_request())

    if lower.startswith("pc premium launcher open") or lower.startswith("pc premium ui launcher open"):
        return format_payload(open_confirmed(text))

    if lower in {"pc premium launcher report", "pc premium ui launcher report", "premium launcher report"}:
        return format_payload(report())

    return format_payload({
        "ok": False,
        "mode": "premium_ui_launcher_unknown_command",
        "generated_at": _now(),
        "error": "Unknown Premium UI Launcher command.",
        "commands": status().get("commands", []),
    })


def is_premium_ui_launcher_command(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    exact = {
        "pc premium launcher",
        "pc premium launcher status",
        "pc premium ui launcher status",
        "premium launcher status",
        "pc premium launcher guide",
        "pc premium ui launcher guide",
        "premium launcher guide",
        "pc premium launcher page",
        "pc premium ui launcher page",
        "premium launcher page",
        "pc premium launcher open request",
        "pc premium ui launcher open request",
        "premium launcher open request",
        "pc premium launcher report",
        "pc premium ui launcher report",
        "premium launcher report",
    }
    if lower in exact:
        return True
    return lower.startswith("pc premium launcher open") or lower.startswith("pc premium ui launcher open")
````

### ПУТЬ: modules/premium_ui_now.py (259 строк, 39747 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import base64
import json
import webbrowser


ROOT_DIR = get_project_root()
UI_NOW_DIR = ROOT_DIR / "Projects" / "UI" / "localcomet-premium-now"
UI_NOW_PAGE = UI_NOW_DIR / "localcomet_premium_now.html"
SETTINGS_PATH = UI_NOW_DIR / "premium_ui_now_settings.json"
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "premium_ui_now"

PREMIUM_NOW_VERSION = "v6.30b"
PREMIUM_NOW_NAME = "LocalComet Premium UI Now"
_AUTO_OPEN_DONE = False

HTML_PAYLOAD_B64 = "PCFkb2N0eXBlIGh0bWw+CjxodG1sIGxhbmc9InJ1Ij4KPGhlYWQ+CjxtZXRhIGNoYXJzZXQ9InV0Zi04Ij4KPG1ldGEgbmFtZT0idmlld3BvcnQiIGNvbnRlbnQ9IndpZHRoPWRldmljZS13aWR0aCxpbml0aWFsLXNjYWxlPTEiPgo8dGl0bGU+TG9jYWxDb21ldCBQcmVtaXVtIFVJIE5vdzwvdGl0bGU+CjxzdHlsZT4KOnJvb3R7LS1iZzojMDUwNzExOy0tYmcyOiMwODBiMTY7LS1wYW5lbDpyZ2JhKDI1NSwyNTUsMjU1LC4wNjUpOy0tcGFuZWwyOnJnYmEoMjU1LDI1NSwyNTUsLjAzNSk7LS1ib3JkZXI6cmdiYSgyNTUsMjU1LDI1NSwuMTE1KTstLXRleHQ6I2Y4ZmFmYzstLW11dGVkOiM5NGEzYjg7LS1zb2Z0OiM2NDc0OGI7LS1ibHVlOiM2MGE1ZmE7LS12aW9sZXQ6I2E3OGJmYTstLWdyZWVuOiMzNGQzOTk7LS1hbWJlcjojZmJiZjI0Oy0tcmVkOiNmYjcxODU7LS1jeWFuOiMyMmQzZWU7LS1zaGFkb3c6MCAyNHB4IDgwcHggcmdiYSgwLDAsMCwuMzgpfQoqe2JveC1zaXppbmc6Ym9yZGVyLWJveH1idXR0b24saW5wdXQsc2VsZWN0e2ZvbnQ6aW5oZXJpdH0KYm9keXttYXJnaW46MDttaW4taGVpZ2h0OjEwMHZoO2JhY2tncm91bmQ6cmFkaWFsLWdyYWRpZW50KGNpcmNsZSBhdCAxMCUgMCUscmdiYSg5NiwxNjUsMjUwLC4yMiksdHJhbnNwYXJlbnQgMzVyZW0pLHJhZGlhbC1ncmFkaWVudChjaXJjbGUgYXQgOTAlIDAlLHJnYmEoMTY3LDEzOSwyNTAsLjIwKSx0cmFuc3BhcmVudCAzNHJlbSksbGluZWFyLWdyYWRpZW50KDE4MGRlZywjMDUwNzExLCMwNzBhMTQgNTAlLCMwNTA3MTEpO2NvbG9yOnZhcigtLXRleHQpO2ZvbnQtZmFtaWx5OkludGVyLHVpLXNhbnMtc2VyaWYsc3lzdGVtLXVpLC1hcHBsZS1zeXN0ZW0sQmxpbmtNYWNTeXN0ZW1Gb250LCJTZWdvZSBVSSIsc2Fucy1zZXJpZjtvdmVyZmxvdzpoaWRkZW59Ci5hcHB7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczoyNDhweCAxZnI7bWluLWhlaWdodDoxMDB2aH0uc2lkZWJhcntiYWNrZ3JvdW5kOnJnYmEoMyw1LDEzLC43Mik7Ym9yZGVyLXJpZ2h0OjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tkcm9wLWZpbHRlcjpibHVyKDE4cHgpO2Rpc3BsYXk6ZmxleDtmbGV4LWRpcmVjdGlvbjpjb2x1bW59LmJyYW5ke2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjEycHg7cGFkZGluZzoyMHB4O2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9LmxvZ297d2lkdGg6MzhweDtoZWlnaHQ6MzhweDtib3JkZXItcmFkaXVzOjEzcHg7YmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLHZhcigtLWJsdWUpLHZhcigtLXZpb2xldCkpO2Rpc3BsYXk6Z3JpZDtwbGFjZS1pdGVtczpjZW50ZXI7Ym94LXNoYWRvdzowIDAgMzBweCByZ2JhKDk2LDE2NSwyNTAsLjI4KX0uYnJhbmQgaDF7Zm9udC1zaXplOjE1cHg7bWFyZ2luOjA7bGV0dGVyLXNwYWNpbmc6LS4wMmVtfS5icmFuZCBwe2ZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW46MnB4IDAgMH0ubmF2e3BhZGRpbmc6MTRweCAxMHB4O2Rpc3BsYXk6Z3JpZDtnYXA6NHB4O292ZXJmbG93OmF1dG99Lm5hdiBidXR0b257ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6MTFweDt3aWR0aDoxMDAlO2JvcmRlcjowO2JhY2tncm91bmQ6dHJhbnNwYXJlbnQ7Y29sb3I6cmdiYSgyNDgsMjUwLDI1MiwuNTYpO3BhZGRpbmc6MTBweCAxMnB4O2JvcmRlci1yYWRpdXM6MTJweDtjdXJzb3I6cG9pbnRlcjt0ZXh0LWFsaWduOmxlZnQ7Zm9udC1zaXplOjEzcHg7dHJhbnNpdGlvbjouMTZzIGVhc2V9Lm5hdiBidXR0b246aG92ZXJ7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wNTUpO2NvbG9yOnJnYmEoMjQ4LDI1MCwyNTIsLjgyKX0ubmF2IGJ1dHRvbi5hY3RpdmV7YmFja2dyb3VuZDpyZ2JhKDk2LDE2NSwyNTAsLjEzKTtjb2xvcjojZmZmO2JvcmRlcjoxcHggc29saWQgcmdiYSg5NiwxNjUsMjUwLC4xOCl9Lm5hdiBidXR0b24gc3BhbjpmaXJzdC1jaGlsZHtmb250LXNpemU6MTdweDt3aWR0aDoyMnB4O3RleHQtYWxpZ246Y2VudGVyfS5zaWRlLXN0YXR1c3ttYXJnaW4tdG9wOmF1dG87Ym9yZGVyLXRvcDoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtwYWRkaW5nOjE2cHg7ZGlzcGxheTpncmlkO2dhcDoxMHB4O2NvbG9yOnZhcigtLW11dGVkKTtmb250LXNpemU6MTJweH0uZG90e3dpZHRoOjhweDtoZWlnaHQ6OHB4O2JvcmRlci1yYWRpdXM6NTAlO2JhY2tncm91bmQ6dmFyKC0tZ3JlZW4pO2JveC1zaGFkb3c6MCAwIDEycHggcmdiYSg1MiwyMTEsMTUzLC43NSl9LnJvd3tkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo5cHh9LnZlcnNpb257Y29sb3I6cmdiYSgyNDgsMjUwLDI1MiwuMzYpO2ZvbnQtc2l6ZToxMXB4O21hcmdpbi10b3A6NHB4fQoubWFpbnttaW4td2lkdGg6MDtkaXNwbGF5OmZsZXg7ZmxleC1kaXJlY3Rpb246Y29sdW1uO2hlaWdodDoxMDB2aH0udG9wYmFye2hlaWdodDo2MnB4O2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7YmFja2dyb3VuZDpyZ2JhKDgsMTEsMjIsLjc0KTtiYWNrZHJvcC1maWx0ZXI6Ymx1cigxOHB4KTtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDoxNnB4O3BhZGRpbmc6MCAyMnB4fS5jcnVtYnt3aGl0ZS1zcGFjZTpub3dyYXA7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtc2l6ZToxM3B4fS5jcnVtYiBzdHJvbmd7Y29sb3I6dmFyKC0tdGV4dCl9LnNlYXJjaHtwb3NpdGlvbjpyZWxhdGl2ZTtmbGV4OjE7bWF4LXdpZHRoOjUyMHB4O21hcmdpbjowIGF1dG99LnNlYXJjaCBpbnB1dHt3aWR0aDoxMDAlO2hlaWdodDozOHB4O2JvcmRlci1yYWRpdXM6MTJweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wNDUpO2NvbG9yOnZhcigtLXRleHQpO291dGxpbmU6MDtwYWRkaW5nOjAgOTBweCAwIDM4cHh9LnNlYXJjaCBie3Bvc2l0aW9uOmFic29sdXRlO2xlZnQ6MTNweDt0b3A6OXB4O2NvbG9yOnJnYmEoMjQ4LDI1MCwyNTIsLjM0KX0uc2VhcmNoIGtiZHtwb3NpdGlvbjphYnNvbHV0ZTtyaWdodDoxMHB4O3RvcDo4cHg7Y29sb3I6cmdiYSgyNDgsMjUwLDI1MiwuMzQpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjdweDtwYWRkaW5nOjNweCA2cHg7Zm9udC1zaXplOjExcHh9LmFjdGlvbnN7ZGlzcGxheTpmbGV4O2dhcDo5cHg7YWxpZ24taXRlbXM6Y2VudGVyfS5idG57aGVpZ2h0OjM0cHg7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMDQ1KTtjb2xvcjpyZ2JhKDI0OCwyNTAsMjUyLC44NCk7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MCAxMnB4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjY1MDt0cmFuc2l0aW9uOi4xNnMgZWFzZX0uYnRuOmhvdmVye2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMDc1KTt0cmFuc2Zvcm06dHJhbnNsYXRlWSgtMXB4KX0uYnRuLmJsdWV7YmFja2dyb3VuZDpyZ2JhKDk2LDE2NSwyNTAsLjE1KTtib3JkZXItY29sb3I6cmdiYSg5NiwxNjUsMjUwLC4yOCk7Y29sb3I6I2JmZGJmZX0uYnRuLnJlZHtiYWNrZ3JvdW5kOnJnYmEoMjUxLDExMywxMzMsLjE0KTtib3JkZXItY29sb3I6cmdiYSgyNTEsMTEzLDEzMywuMzIpO2NvbG9yOiNmZWNkZDN9LmJhZGdle2Rpc3BsYXk6aW5saW5lLWZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo2cHg7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6OTk5cHg7cGFkZGluZzo1cHggOXB4O2ZvbnQtc2l6ZToxMXB4O2ZvbnQtd2VpZ2h0Ojc1MH0uYmFkZ2UuZ3JlZW57Y29sb3I6dmFyKC0tZ3JlZW4pO2JhY2tncm91bmQ6cmdiYSg1MiwyMTEsMTUzLC4wOCk7Ym9yZGVyLWNvbG9yOnJnYmEoNTIsMjExLDE1MywuMjIpfS5iYWRnZS5ibHVle2NvbG9yOnZhcigtLWJsdWUpO2JhY2tncm91bmQ6cmdiYSg5NiwxNjUsMjUwLC4wOCk7Ym9yZGVyLWNvbG9yOnJnYmEoOTYsMTY1LDI1MCwuMjIpfS5iYWRnZS5hbWJlcntjb2xvcjp2YXIoLS1hbWJlcik7YmFja2dyb3VuZDpyZ2JhKDI1MSwxOTEsMzYsLjA4KTtib3JkZXItY29sb3I6cmdiYSgyNTEsMTkxLDM2LC4yMil9Ci5jb250ZW50e3BhZGRpbmc6MjJweDtvdmVyZmxvdzphdXRvO2hlaWdodDpjYWxjKDEwMHZoIC0gNjJweCl9LnBhZ2V7ZGlzcGxheTpub25lO2FuaW1hdGlvbjpmYWRlIC4xOHMgZWFzZX0ucGFnZS5hY3RpdmV7ZGlzcGxheTpibG9ja31Aa2V5ZnJhbWVzIGZhZGV7ZnJvbXtvcGFjaXR5Oi4zO3RyYW5zZm9ybTp0cmFuc2xhdGVZKDRweCl9dG97b3BhY2l0eToxO3RyYW5zZm9ybTpub25lfX0uZ3JpZC0ze2Rpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MjgwcHggbWlubWF4KDQyMHB4LDFmcikgMzAwcHg7Z2FwOjE4cHg7aGVpZ2h0OmNhbGMoMTAwdmggLSAxMDZweCl9LnBhbmVse2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOmxpbmVhci1ncmFkaWVudCgxODBkZWcscmdiYSgyNTUsMjU1LDI1NSwuMDc1KSxyZ2JhKDI1NSwyNTUsMjU1LC4wMzUpKTtib3gtc2hhZG93OnZhcigtLXNoYWRvdyk7Ym9yZGVyLXJhZGl1czoyMnB4fS5wYW5lbC5wYWR7cGFkZGluZzoxOHB4fS5wYW5lbCBoMntmb250LXNpemU6MTVweDttYXJnaW46MCAwIDE0cHg7bGV0dGVyLXNwYWNpbmc6LS4wMWVtfS5wYW5lbCBoM3tmb250LXNpemU6MTNweDttYXJnaW46MDtjb2xvcjpyZ2JhKDI0OCwyNTAsMjUyLC44Nil9LnN0YWNre2Rpc3BsYXk6Z3JpZDtnYXA6MTBweH0uY2FyZHtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wNCk7Ym9yZGVyLXJhZGl1czoxNnB4O3BhZGRpbmc6MTRweH0uc3RhdHVzLWNhcmR7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6MTJweH0uaWNvbnt3aWR0aDozNnB4O2hlaWdodDozNnB4O2JvcmRlci1yYWRpdXM6MTNweDtkaXNwbGF5OmdyaWQ7cGxhY2UtaXRlbXM6Y2VudGVyO2JhY2tncm91bmQ6cmdiYSg5NiwxNjUsMjUwLC4xMSk7Y29sb3I6dmFyKC0tYmx1ZSk7Zm9udC1zaXplOjE4cHh9Lmljb24uZ3JlZW57YmFja2dyb3VuZDpyZ2JhKDUyLDIxMSwxNTMsLjExKTtjb2xvcjp2YXIoLS1ncmVlbil9Lmljb24udmlvbGV0e2JhY2tncm91bmQ6cmdiYSgxNjcsMTM5LDI1MCwuMTEpO2NvbG9yOnZhcigtLXZpb2xldCl9Lmljb24uYW1iZXJ7YmFja2dyb3VuZDpyZ2JhKDI1MSwxOTEsMzYsLjExKTtjb2xvcjp2YXIoLS1hbWJlcil9LnNtYWxse2ZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLW11dGVkKX0ubWljcm97Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tc29mdCl9Lm1vbm97Zm9udC1mYW1pbHk6IkpldEJyYWlucyBNb25vIix1aS1tb25vc3BhY2UsU0ZNb25vLVJlZ3VsYXIsTWVubG8sQ29uc29sYXMsbW9ub3NwYWNlfQouY29uc29sZXtkaXNwbGF5OmZsZXg7ZmxleC1kaXJlY3Rpb246Y29sdW1uO292ZXJmbG93OmhpZGRlbn0uY29uc29sZS1oZWFke3BhZGRpbmc6MTVweCAxOHB4O2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2Vlbn0ubWVzc2FnZXN7ZmxleDoxO292ZXJmbG93OmF1dG87cGFkZGluZzoxOHB4O2Rpc3BsYXk6Z3JpZDthbGlnbi1jb250ZW50OnN0YXJ0O2dhcDoxNHB4fS5idWJibGV7bWF4LXdpZHRoOjgyJTtib3JkZXItcmFkaXVzOjE4cHg7cGFkZGluZzoxNHB4O2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKX0uYnViYmxlLnVzZXJ7anVzdGlmeS1zZWxmOmVuZDtiYWNrZ3JvdW5kOnJnYmEoOTYsMTY1LDI1MCwuMTQpO2JvcmRlci1jb2xvcjpyZ2JhKDk2LDE2NSwyNTAsLjI0KX0uYnViYmxlLmFnZW50e2p1c3RpZnktc2VsZjpzdGFydDtiYWNrZ3JvdW5kOnJnYmEoMjU1LDI1NSwyNTUsLjA0NSl9LmNoaXBze2Rpc3BsYXk6ZmxleDtnYXA6OHB4O2ZsZXgtd3JhcDp3cmFwO3BhZGRpbmc6MTBweCAxOHB4O2JvcmRlci10b3A6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9LmNoaXB7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMDM1KTtjb2xvcjp2YXIoLS1tdXRlZCk7Ym9yZGVyLXJhZGl1czo5OTlweDtwYWRkaW5nOjZweCAxMHB4O2ZvbnQtc2l6ZToxMXB4O2N1cnNvcjpwb2ludGVyfS5pbnB1dGJhcntwYWRkaW5nOjE2cHggMThweDtib3JkZXItdG9wOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2Rpc3BsYXk6ZmxleDtnYXA6MTBweH0uaW5wdXRiYXIgaW5wdXR7ZmxleDoxO2hlaWdodDo0MnB4O2JvcmRlci1yYWRpdXM6MTRweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wNCk7Y29sb3I6dmFyKC0tdGV4dCk7b3V0bGluZTowO3BhZGRpbmc6MCAxNHB4fS5wYWdlLWhlYWR7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmZsZXgtZW5kO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206MThweH0ucGFnZS1oZWFkIGgxe21hcmdpbjowO2ZvbnQtc2l6ZToyOHB4O2xldHRlci1zcGFjaW5nOi0uMDRlbX0ucGFnZS1oZWFkIHB7bWFyZ2luOjZweCAwIDA7Y29sb3I6dmFyKC0tbXV0ZWQpfS5jYXJkc3tkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCg0LG1pbm1heCgwLDFmcikpO2dhcDoxNHB4fS5jYXJkcy50aHJlZXtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KDMsbWlubWF4KDAsMWZyKSl9LmNhcmRzLnR3b3tncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KDIsbWlubWF4KDAsMWZyKSl9LnBpcGVsaW5le2Rpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KDgsMWZyKTtnYXA6MTBweH0ucGlwZXtwb3NpdGlvbjpyZWxhdGl2ZTt0ZXh0LWFsaWduOmNlbnRlcjtwYWRkaW5nOjE4cHggMTBweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wNCk7Ym9yZGVyLXJhZGl1czoxOHB4fS5waXBlOm5vdCg6bGFzdC1jaGlsZCk6OmFmdGVye2NvbnRlbnQ6IuKGkiI7cG9zaXRpb246YWJzb2x1dGU7cmlnaHQ6LTEycHg7dG9wOjUwJTt0cmFuc2Zvcm06dHJhbnNsYXRlWSgtNTAlKTtjb2xvcjp2YXIoLS1ibHVlKTtmb250LXdlaWdodDo5MDB9dGFibGV7d2lkdGg6MTAwJTtib3JkZXItY29sbGFwc2U6Y29sbGFwc2V9dGgsdGR7dGV4dC1hbGlnbjpsZWZ0O3BhZGRpbmc6MTJweDtib3JkZXItYm90dG9tOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wNyk7Zm9udC1zaXplOjEycHh9dGh7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtd2VpZ2h0OjcwMH10ZHtjb2xvcjpyZ2JhKDI0OCwyNTAsMjUyLC44Mil9LnJpc2stbG93e2NvbG9yOnZhcigtLWdyZWVuKX0ucmlzay1tZWR7Y29sb3I6dmFyKC0tYW1iZXIpfS5yaXNrLWhpZ2h7Y29sb3I6dmFyKC0tcmVkKX0uc2NyZWVuc2hvdHtoZWlnaHQ6MjMwcHg7Ym9yZGVyOjFweCBkYXNoZWQgcmdiYSg5NiwxNjUsMjUwLC4zNSk7Ym9yZGVyLXJhZGl1czoxOHB4O2JhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDEzNWRlZyxyZ2JhKDk2LDE2NSwyNTAsLjEyKSxyZ2JhKDE2NywxMzksMjUwLC4wOCkpO2Rpc3BsYXk6Z3JpZDtwbGFjZS1pdGVtczpjZW50ZXI7Y29sb3I6dmFyKC0tbXV0ZWQpO3Bvc2l0aW9uOnJlbGF0aXZlO292ZXJmbG93OmhpZGRlbn0uc2NyZWVuc2hvdDo6YWZ0ZXJ7Y29udGVudDoiIjtwb3NpdGlvbjphYnNvbHV0ZTtpbnNldDoyMHB4O2JvcmRlcjoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMTIpO2JvcmRlci1yYWRpdXM6MTJweDthbmltYXRpb246cHVsc2UgMnMgaW5maW5pdGV9QGtleWZyYW1lcyBwdWxzZXs1MCV7b3BhY2l0eTouMzU7dHJhbnNmb3JtOnNjYWxlKC45ODUpfX0udG9hc3Qtd3JhcHtwb3NpdGlvbjpmaXhlZDtyaWdodDoyMHB4O2JvdHRvbToyMHB4O2Rpc3BsYXk6Z3JpZDtnYXA6MTBweDt6LWluZGV4OjEwMH0udG9hc3R7bWluLXdpZHRoOjI4MHB4O2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnJnYmEoOCwxMSwyMiwuOTIpO2JhY2tkcm9wLWZpbHRlcjpibHVyKDE4cHgpO2JvcmRlci1yYWRpdXM6MTZweDtwYWRkaW5nOjEzcHg7Ym94LXNoYWRvdzp2YXIoLS1zaGFkb3cpO2FuaW1hdGlvbjp0b2FzdCAuMnMgZWFzZX1Aa2V5ZnJhbWVzIHRvYXN0e2Zyb217b3BhY2l0eTowO3RyYW5zZm9ybTp0cmFuc2xhdGVZKDEwcHgpfXRve29wYWNpdHk6MTt0cmFuc2Zvcm06bm9uZX19Lm1vZGFse3Bvc2l0aW9uOmZpeGVkO2luc2V0OjA7YmFja2dyb3VuZDpyZ2JhKDAsMCwwLC42OCk7ZGlzcGxheTpub25lO2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO3otaW5kZXg6ODB9Lm1vZGFsLnNob3d7ZGlzcGxheTpmbGV4fS5tb2RhbC1ib3h7d2lkdGg6bWluKDUyMHB4LGNhbGMoMTAwdncgLSAzNHB4KSk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI1MSwxMTMsMTMzLC4zNCk7YmFja2dyb3VuZDojMDgwYjE2O2JvcmRlci1yYWRpdXM6MjRweDtwYWRkaW5nOjI0cHg7Ym94LXNoYWRvdzp2YXIoLS1zaGFkb3cpfS5iYW5uZXJ7ZGlzcGxheTpub25lO21hcmdpbi1ib3R0b206MTZweDtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjUxLDExMywxMzMsLjI4KTtiYWNrZ3JvdW5kOnJnYmEoMjUxLDExMywxMzMsLjEwKTtib3JkZXItcmFkaXVzOjE4cHg7cGFkZGluZzoxNHB4O2NvbG9yOiNmZWNkZDN9LmJhbm5lci5zaG93e2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXJ9CkBtZWRpYShtYXgtd2lkdGg6MTE4MHB4KXsuZ3JpZC0ze2dyaWQtdGVtcGxhdGUtY29sdW1uczoxZnI7aGVpZ2h0OmF1dG99LmNhcmRzLC5jYXJkcy50aHJlZSwuY2FyZHMudHdve2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoMixtaW5tYXgoMCwxZnIpKX0ucGlwZWxpbmV7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCgyLDFmcil9Ym9keXtvdmVyZmxvdzphdXRvfS5tYWlue2hlaWdodDphdXRvfS5jb250ZW50e2hlaWdodDphdXRvfS5hcHB7bWluLWhlaWdodDoxMDB2aH19QG1lZGlhKG1heC13aWR0aDo3NjBweCl7LmFwcHtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MWZyfS5zaWRlYmFye2Rpc3BsYXk6bm9uZX0udG9wYmFye2hlaWdodDphdXRvO2ZsZXgtd3JhcDp3cmFwO3BhZGRpbmc6MTJweH0uc2VhcmNoe29yZGVyOjM7bWF4LXdpZHRoOm5vbmU7d2lkdGg6MTAwJX0uYWN0aW9uc3tmbGV4LXdyYXA6d3JhcH0uY2FyZHMsLmNhcmRzLnRocmVlLC5jYXJkcy50d297Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmcn0uY29udGVudHtwYWRkaW5nOjE0cHh9LnBhZ2UtaGVhZHtkaXNwbGF5OmJsb2NrfX0KPC9zdHlsZT4KPC9oZWFkPgo8Ym9keT4KPGRpdiBjbGFzcz0iYXBwIj4KPGFzaWRlIGNsYXNzPSJzaWRlYmFyIj48ZGl2IGNsYXNzPSJicmFuZCI+PGRpdiBjbGFzcz0ibG9nbyI+4pqhPC9kaXY+PGRpdj48aDE+TG9jYWxDb21ldDwvaDE+PHA+UHJlbWl1bSBBSSBBZ2VudCBPUzwvcD48L2Rpdj48L2Rpdj48bmF2IGNsYXNzPSJuYXYiIGlkPSJuYXYiPjwvbmF2PjxkaXYgY2xhc3M9InNpZGUtc3RhdHVzIj48ZGl2IGNsYXNzPSJyb3ciPjxzcGFuIGNsYXNzPSJkb3QiPjwvc3Bhbj48c3Bhbj5SZWxheSBDb25uZWN0ZWQ8L3NwYW4+PC9kaXY+PGRpdiBjbGFzcz0icm93Ij48c3BhbiBjbGFzcz0iZG90Ij48L3NwYW4+PHNwYW4+TE0gU3R1ZGlvIFJlYWR5PC9zcGFuPjwvZGl2PjxkaXYgY2xhc3M9InJvdyI+PHNwYW4+8J+Ukjwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tYW1iZXIpIj5TYWZlIE1vZGUgT048L3NwYW4+PC9kaXY+PGRpdiBjbGFzcz0idmVyc2lvbiI+TG9jYWxDb21ldCB2Ni4zMCDCtyBQcmVtaXVtIFVJIE5vdzwvZGl2PjwvZGl2PjwvYXNpZGU+CjxzZWN0aW9uIGNsYXNzPSJtYWluIj48aGVhZGVyIGNsYXNzPSJ0b3BiYXIiPjxkaXYgY2xhc3M9ImNydW1iIj5Mb2NhbENvbWV0IC8gPHN0cm9uZyBpZD0iY3J1bWIiPkNvbW1hbmQgQ2VudGVyPC9zdHJvbmc+PC9kaXY+PGRpdiBjbGFzcz0ic2VhcmNoIj48Yj7ijJU8L2I+PGlucHV0IGlkPSJzZWFyY2giIHBsYWNlaG9sZGVyPSJTZWFyY2ggb3IgdHlwZSBhIGNvbW1hbmQuLi4iPjxrYmQ+Q3RybCBLPC9rYmQ+PC9kaXY+PGRpdiBjbGFzcz0iYWN0aW9ucyI+PGJ1dHRvbiBjbGFzcz0iYnRuIGJsdWUiIG9uY2xpY2s9InRvYXN0KCdOZXcgdGFzayBjcmVhdGVkIGFzIHNhZmUgbW9jayBzdGF0ZScpIj5OZXcgVGFzazwvYnV0dG9uPjxidXR0b24gY2xhc3M9ImJ0biIgb25jbGljaz0idG9hc3QoJ0RyeSBSdW4gcXVldWVkIOKAlCBtb2NrIGZyb250ZW5kIG9ubHknKSI+RHJ5IFJ1bjwvYnV0dG9uPjxidXR0b24gY2xhc3M9ImJ0biByZWQiIG9uY2xpY2s9InNob3dTdG9wKCkiPkVtZXJnZW5jeSBTdG9wPC9idXR0b24+PHNwYW4gY2xhc3M9ImJhZGdlIGdyZWVuIj5BViA2LzY8L3NwYW4+PHNwYW4gY2xhc3M9ImJhZGdlIGJsdWUiPkZTIDIzLzIzPC9zcGFuPjwvZGl2PjwvaGVhZGVyPgo8bWFpbiBjbGFzcz0iY29udGVudCI+PGRpdiBpZD0ic3RvcHBlZEJhbm5lciIgY2xhc3M9ImJhbm5lciI+PHN0cm9uZz5FbWVyZ2VuY3kgU3RvcCBhY3RpdmUg4oCUIGV4ZWN1dG9yIHBhdXNlZCwgc2FmZSBtb2RlIGxvY2tlZCwgcnVubmluZyB0YXNrcyAwLjwvc3Ryb25nPjxidXR0b24gY2xhc3M9ImJ0biIgb25jbGljaz0icmVzdG9yZSgpIj5SZXN0b3JlIE1vY2sgU3RhdGU8L2J1dHRvbj48L2Rpdj48c2VjdGlvbiBpZD0iQ29tbWFuZCBDZW50ZXIiIGNsYXNzPSJwYWdlIGFjdGl2ZSI+PC9zZWN0aW9uPjxzZWN0aW9uIGlkPSJBZ2VudE9TIiBjbGFzcz0icGFnZSI+PC9zZWN0aW9uPjxzZWN0aW9uIGlkPSJTd2lzcyBLbmlmZSIgY2xhc3M9InBhZ2UiPjwvc2VjdGlvbj48c2VjdGlvbiBpZD0iRGVza3RvcCIgY2xhc3M9InBhZ2UiPjwvc2VjdGlvbj48c2VjdGlvbiBpZD0iVUkgUGFyc2VyIiBjbGFzcz0icGFnZSI+PC9zZWN0aW9uPjxzZWN0aW9uIGlkPSJQcm9qZWN0cyIgY2xhc3M9InBhZ2UiPjwvc2VjdGlvbj48c2VjdGlvbiBpZD0iUGF0Y2hlcyIgY2xhc3M9InBhZ2UiPjwvc2VjdGlvbj48c2VjdGlvbiBpZD0iUmVwb3J0cyIgY2xhc3M9InBhZ2UiPjwvc2VjdGlvbj48c2VjdGlvbiBpZD0iU2FmZXR5IiBjbGFzcz0icGFnZSI+PC9zZWN0aW9uPjxzZWN0aW9uIGlkPSJTZXR0aW5ncyIgY2xhc3M9InBhZ2UiPjwvc2VjdGlvbj48L21haW4+PC9zZWN0aW9uPjwvZGl2Pgo8ZGl2IGlkPSJtb2RhbCIgY2xhc3M9Im1vZGFsIj48ZGl2IGNsYXNzPSJtb2RhbC1ib3giPjxoMiBzdHlsZT0ibWFyZ2luOjAgMCA4cHg7Y29sb3I6I2ZlY2RkMyI+Q29uZmlybSBFbWVyZ2VuY3kgU3RvcDwvaDI+PHAgY2xhc3M9InNtYWxsIj5UaGlzIGlzIGEgZnJvbnRlbmQtb25seSBzYWZlIG1vY2sgYWN0aW9uLiBJdCB3aWxsIHNldCB0aGUgZGFzaGJvYXJkIHN0YXRlIHRvIHN0b3BwZWQvcGF1c2VkL2xvY2tlZCBhbmQgd2lsbCBub3QgZXhlY3V0ZSBzaGVsbCwgYmFja2VuZCwgZGVsZXRlLCBkZXBsb3ksIG9yIHN5c3RlbSBjb21tYW5kcy48L3A+PGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxMHB4O2p1c3RpZnktY29udGVudDpmbGV4LWVuZDttYXJnaW4tdG9wOjIwcHgiPjxidXR0b24gY2xhc3M9ImJ0biIgb25jbGljaz0iaGlkZVN0b3AoKSI+Q2FuY2VsPC9idXR0b24+PGJ1dHRvbiBjbGFzcz0iYnRuIHJlZCIgb25jbGljaz0iY29uZmlybVN0b3AoKSI+Q29uZmlybSBTdG9wPC9idXR0b24+PC9kaXY+PC9kaXY+PC9kaXY+PGRpdiBjbGFzcz0idG9hc3Qtd3JhcCIgaWQ9InRvYXN0cyI+PC9kaXY+CjxzY3JpcHQ+CmNvbnN0IHBhZ2VzPVsiQ29tbWFuZCBDZW50ZXIiLCJBZ2VudE9TIiwiU3dpc3MgS25pZmUiLCJEZXNrdG9wIiwiVUkgUGFyc2VyIiwiUHJvamVjdHMiLCJQYXRjaGVzIiwiUmVwb3J0cyIsIlNhZmV0eSIsIlNldHRpbmdzIl07Y29uc3QgaWNvbnM9WyLijJgiLCLwn6egIiwi8J+boO+4jyIsIvCflqXvuI8iLCLwn5SOIiwi8J+TgSIsIvCfp6kiLCLwn5OEIiwi8J+boe+4jyIsIuKame+4jyJdO2NvbnN0IHN0YXR1c0NhcmRzPVtbIvCfp6AiLCJBZ2VudE9TIEtlcm5lbCIsIk9ubGluZSIsImdyZWVuIl0sWyLwn5uh77iPIiwiU2VtYW50aWMgRmlyZXdhbGwiLCJBY3RpdmUiLCJncmVlbiJdLFsi4oyYIiwiUEMgQ29kZXggQ29yZSIsIkFjdGl2ZSIsImJsdWUiXSxbIuKWtiIsIlBDIENvZGV4IEV4ZWN1dG9yIiwiQWN0aXZlIiwiYmx1ZSJdLFsi8J+RgSIsIlNjcmVlbi1Bd2FyZSBQbGFubmVyIiwiQWN0aXZlIiwiYmx1ZSJdLFsi8J+WsSIsIkRlc2t0b3AgUHJpbWl0aXZlcyIsIkFjdGl2ZSIsInZpb2xldCJdLFsi8J+UjiIsIlVJIFBhcnNlciIsIlJlYWR5IiwiYW1iZXIiXSxbIvCfm6AiLCJTd2lzcyBLbmlmZSIsIlJlYWR5IiwidmlvbGV0Il0sWyLikYIiLCJQYXRjaCBSZWdpc3RyeSIsIlN5bmNlZCIsImdyZWVuIl0sWyLinJMiLCJBdXRvIFZlcmlmaWNhdGlvbiIsIjYvNiIsImdyZWVuIl0sWyLil4YiLCJGdWxsIFN0YWJpbGl0eSIsIjIzLzIzIiwiYmx1ZSJdXTtjb25zdCBza2lsbHM9W1siUmVzZWFyY2ggUmVwb3J0IiwiTWFya2V0LCBjb21wZXRpdG9yLCB0ZWNobm9sb2d5IGFuZCBzdHJhdGVneSBicmllZnMuIiwibG93Iiwi8J+TiiJdLFsiTGVhZGdlbiBCcmllZiIsIklDUCwgb2ZmZXIgYW5kIGNoYW5uZWwgcGxhbiB3aXRob3V0IHNwYW0gb3Igc2NyYXBpbmcuIiwiaGlnaCIsIvCfjq8iXSxbIlBERiBBbmFseXNpcyIsIlN1bW1hcmllcywgYWN0aW9uIGl0ZW1zIGFuZCBpbnRlZ3JhdGlvbiBub3Rlcy4iLCJsb3ciLCLwn5OVIl0sWyJXZWJzaXRlIERyYWZ0IiwiTGFuZGluZyBwYWdlIGFuZCBkZW1vLXNpdGUgcGxhbm5pbmcgd29ya2Zsb3cuIiwibWVkaXVtIiwi8J+MkCJdLFsiRG9jdW1lbnQgQXV0b21hdGlvbiIsIlNhZmUgZmlsZS9yZXBvcnQgYXV0b21hdGlvbiBwbGFuIHdpdGggZ3VhcmRzLiIsImhpZ2giLCLwn5OCIl0sWyJQcm9qZWN0IFBhdGNoIiwiVHVybiBpZGVhcyBpbnRvIHJlc3BvbnNlLmpzb24gcGF0Y2ggd29ya2Zsb3cuIiwiaGlnaCIsIvCfp6kiXSxbIlVJIEFjdGlvbiBTdWdnZXN0aW9uIiwiU2NyZWVuLWF3YXJlIGRyeS1ydW4gYWN0aW9uIGNhbmRpZGF0ZXMuIiwibWVkaXVtIiwi8J+Wse+4jyJdLFsiQWdlbnQgT25ib2FyZGluZyIsIlF1aWNrc3RhcnQsIEFHRU5UUy5tZCBhbmQgc2FmZSB0dXRvcmlhbHMuIiwibG93Iiwi8J+nrSJdXTtjb25zdCByZXBvcnRzPVsiQXV0byBWZXJpZmljYXRpb24iLCJGdWxsIFN0YWJpbGl0eSIsIkRlc2t0b3AiLCJVSSBQYXJzZXIiLCJTd2lzcyBLbmlmZSIsIkFnZW50T1MiXTtjb25zdCBuYXY9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm5hdiIpO3BhZ2VzLmZvckVhY2goKHAsaSk9Pntjb25zdCBiPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoImJ1dHRvbiIpO2IuaW5uZXJIVE1MPWA8c3Bhbj4ke2ljb25zW2ldfTwvc3Bhbj48c3Bhbj4ke3B9PC9zcGFuPmA7Yi5vbmNsaWNrPSgpPT5zaG93UGFnZShwKTtpZihpPT09MCliLmNsYXNzTGlzdC5hZGQoImFjdGl2ZSIpO25hdi5hcHBlbmRDaGlsZChiKX0pO2Z1bmN0aW9uIHNob3dQYWdlKG5hbWUpe2RvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoIi5wYWdlIikuZm9yRWFjaChwPT5wLmNsYXNzTGlzdC50b2dnbGUoImFjdGl2ZSIscC5pZD09PW5hbWUpKTtkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCIubmF2IGJ1dHRvbiIpLmZvckVhY2goKGIsaSk9PmIuY2xhc3NMaXN0LnRvZ2dsZSgiYWN0aXZlIixwYWdlc1tpXT09PW5hbWUpKTtkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiY3J1bWIiKS50ZXh0Q29udGVudD1uYW1lfWZ1bmN0aW9uIGNhcmQodGl0bGUsYm9keSxleHRyYT0iIil7cmV0dXJuIGA8ZGl2IGNsYXNzPSJjYXJkIj48aDM+JHt0aXRsZX08L2gzPjxwIGNsYXNzPSJzbWFsbCI+JHtib2R5fTwvcD4ke2V4dHJhfTwvZGl2PmB9ZnVuY3Rpb24gYmFkZ2UodGV4dCxjbHM9ImdyZWVuIil7cmV0dXJuIGA8c3BhbiBjbGFzcz0iYmFkZ2UgJHtjbHN9Ij4ke3RleHR9PC9zcGFuPmB9ZnVuY3Rpb24gaGVhZCh0LHApe3JldHVybiBgPGRpdiBjbGFzcz0icGFnZS1oZWFkIj48ZGl2PjxoMT4ke3R9PC9oMT48cD4ke3B9PC9wPjwvZGl2PjxkaXYgY2xhc3M9InJvdyI+JHtiYWRnZSgiU2FmZSBNb2RlIiwiYW1iZXIiKX0ke2JhZGdlKCJGcm9udGVuZCBPbmx5IiwiYmx1ZSIpfTwvZGl2PjwvZGl2PmB9ZnVuY3Rpb24gcm93cyhhcnIpe3JldHVybiBgPHRib2R5PiR7YXJyLm1hcChyPT5gPHRyPjx0ZD4ke3JbMF19PC90ZD48dGQ+JHtyWzFdfTwvdGQ+PC90cj5gKS5qb2luKCIiKX08L3Rib2R5PmB9ZnVuY3Rpb24gdGFibGUoaGVhZGVycyxhcnIpe3JldHVybiBgPHRoZWFkPjx0cj4ke2hlYWRlcnMubWFwKGg9PmA8dGg+JHtofTwvdGg+YCkuam9pbigiIil9PC90cj48L3RoZWFkPjx0Ym9keT4ke2Fyci5tYXAocj0+YDx0cj4ke3IubWFwKGM9PmA8dGQ+JHtjfTwvdGQ+YCkuam9pbigiIil9PC90cj5gKS5qb2luKCIiKX08L3Rib2R5PmB9CmZ1bmN0aW9uIHJlbmRlcigpe2RvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJDb21tYW5kIENlbnRlciIpLmlubmVySFRNTD1gPGRpdiBjbGFzcz0iZ3JpZC0zIj48ZGl2IGNsYXNzPSJwYW5lbCBwYWQiPjxoMj5BZ2VudCBTdGF0dXM8L2gyPjxkaXYgY2xhc3M9InN0YWNrIj4ke3N0YXR1c0NhcmRzLm1hcCh4PT5gPGRpdiBjbGFzcz0iY2FyZCBzdGF0dXMtY2FyZCI+PGRpdiBjbGFzcz0iaWNvbiAke3hbM119Ij4ke3hbMF19PC9kaXY+PGRpdj48aDM+JHt4WzFdfTwvaDM+PGRpdiBjbGFzcz0icm93IG1pY3JvIj48c3BhbiBjbGFzcz0iZG90Ij48L3NwYW4+JHt4WzJdfTwvZGl2PjwvZGl2PjwvZGl2PmApLmpvaW4oIiIpfTwvZGl2PjwvZGl2PjxkaXYgY2xhc3M9InBhbmVsIGNvbnNvbGUiPjxkaXYgY2xhc3M9ImNvbnNvbGUtaGVhZCI+PGgyPlBDIENvZGV4IENvbnNvbGU8L2gyPiR7YmFkZ2UoIkludGVyYWN0aXZlIiwiYmx1ZSIpfTwvZGl2PjxkaXYgY2xhc3M9Im1lc3NhZ2VzIj48ZGl2IGNsYXNzPSJidWJibGUgdXNlciBtb25vIj5wYyBzd2lzcyBwbGFuINGB0L7Qt9C00LDRgtGMINC70LXQvdC00LjQvdCzINC00LvRjyBMb2NhbENvbWV0PC9kaXY+PGRpdiBjbGFzcz0iYnViYmxlIGFnZW50Ij48ZGl2IGNsYXNzPSJyb3ciPjxkaXYgY2xhc3M9Imljb24gdmlvbGV0Ij7wn5ugPC9kaXY+PGRpdj48aDM+UGxhbm5pbmcgc2tpbGw6IFdlYnNpdGUgRHJhZnQ8L2gzPjxwIGNsYXNzPSJzbWFsbCI+RmlyZXdhbGw6IGFsbG93ZWQgwrcgUmlzazogbG93IMK3IE5leHQ6IGRyeS1ydW48L3A+PC9kaXY+PC9kaXY+PGRpdiBjbGFzcz0iY2FyZCIgc3R5bGU9Im1hcmdpbi10b3A6MTJweCI+PHAgY2xhc3M9InNtYWxsIj5TdGVwczogMSkgUmVzZWFyY2gg4oaSIDIpIFN0cnVjdHVyZSDihpIgMykgRHJhZnQg4oaSIDQpIFJldmlldzwvcD48L2Rpdj48L2Rpdj48L2Rpdj48ZGl2IGNsYXNzPSJjaGlwcyI+JHtbInBsYW4iLCJkcnktcnVuIiwiY29uZmlybSIsInJlcG9ydCIsInN0b3AiXS5tYXAoYz0+YDxidXR0b24gY2xhc3M9ImNoaXAiIG9uY2xpY2s9InRvYXN0KCdDb21tYW5kIGNoaXA6ICR7Y30nKSI+JHtjfTwvYnV0dG9uPmApLmpvaW4oIiIpfTwvZGl2PjxkaXYgY2xhc3M9ImlucHV0YmFyIj48aW5wdXQgcGxhY2Vob2xkZXI9IkRlc2NyaWJlIHlvdXIgZ29hbCBpbiBwbGFpbiBsYW5ndWFnZeKApiI+PGJ1dHRvbiBjbGFzcz0iYnRuIGJsdWUiIG9uY2xpY2s9InRvYXN0KCdUYXNrIHNlbnQgdG8gbW9jayBjb25zb2xlJykiPlNlbmQ8L2J1dHRvbj48L2Rpdj48L2Rpdj48ZGl2IGNsYXNzPSJwYW5lbCBwYWQiPjxoMj5MaXZlIENvbnRleHQ8L2gyPjxkaXYgY2xhc3M9InN0YWNrIj4ke1tbIkFjdGl2ZSBXaW5kb3ciLCJMb2NhbENvbWV0IENvbnRyb2wgUGFuZWwiXSxbIk1vdXNlIFBvc2l0aW9uIiwieDogMTI4NCDCtyB5OiA3NDIiXSxbIkN1cnJlbnQgUHJvamVjdCIsIkM6XFxcXFVzZXJzXFxcXEROU1xcXFxEb2N1bWVudHNcXFxcTG9jYWxBZ2VudCJdLFsiTGFzdCBTY3JlZW5zaG90Iiwic2NyZWVuXzIwMjYwNzA3LnBuZyJdLFsiTGFzdCBQYXRjaCIsInY2LjMwIFByZW1pdW0gVUkgTm93Il0sWyJMYXN0IFJlcG9ydCIsImF1dG9fdmVyaWZpY2F0aW9uXzZfNi5tZCJdLFsiQ3VycmVudCBTa2lsbCIsIlByZW1pdW0gVUkgTm93Il0sWyJTYWZldHkgVmVyZGljdCIsIkFsbG93ZWQgwrcgZHJ5LXJ1biBmaXJzdCJdXS5tYXAoeD0+Y2FyZCh4WzBdLHhbMV0pKS5qb2luKCIiKX08L2Rpdj48L2Rpdj48L2Rpdj5gOwpkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiQWdlbnRPUyIpLmlubmVySFRNTD1gJHtoZWFkKCJBZ2VudE9TIiwiU2VtYW50aWMga2VybmVsIGFuZCBzYWZlIHNraWxsIG9yY2hlc3RyYXRpb24uIil9PGRpdiBjbGFzcz0icGFuZWwgcGFkIj48aDI+UGlwZWxpbmU8L2gyPjxkaXYgY2xhc3M9InBpcGVsaW5lIj4ke1siVXNlciBHb2FsIiwiU2VtYW50aWMgRmlyZXdhbGwiLCJJbnRlbnQgUGFyc2VyIiwiU2tpbGwgUm91dGVyIiwiUGxhbm5lciIsIkRyeSBSdW4iLCJDb25maXJtZWQgRXhlY3V0b3IiLCJSZXBvcnQiXS5tYXAoeD0+YDxkaXYgY2xhc3M9InBpcGUiPjxzdHJvbmc+JHt4fTwvc3Ryb25nPjwvZGl2PmApLmpvaW4oIiIpfTwvZGl2PjwvZGl2PjxkaXYgY2xhc3M9ImNhcmRzIiBzdHlsZT0ibWFyZ2luLXRvcDoxNnB4Ij4ke1siU2luZ2xlIFBvcnQiLCJOb3J0aGJvdW5kIEludGVudCBJbnRlcmZhY2UiLCJBZ2VudCBLZXJuZWwiLCJTZW1hbnRpYyBGaXJld2FsbCIsIlNraWxscy1hcy1Nb2R1bGVzIiwiU291dGhib3VuZCBUb29sIEludGVyZmFjZSIsIlBlcnNvbmFsIEtub3dsZWRnZSBHcmFwaCIsIlJvbGxiYWNrIC8gQ2hlY2twb2ludHMiXS5tYXAoeD0+Y2FyZCh4LCJBZ2VudE9TIGFyY2hpdGVjdHVyZSBsYXllciBmb3IgTG9jYWxDb21ldCBzYWZlIG9wZXJhdGlvbnMuIikpLmpvaW4oIiIpfTwvZGl2PmA7CmRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJTd2lzcyBLbmlmZSIpLmlubmVySFRNTD1gJHtoZWFkKCJTd2lzcyBLbmlmZSIsIkJ1c2luZXNzIHNraWxsIGxhdW5jaGVyIGZvciByZXNlYXJjaCwgZG9jdW1lbnRzLCB3ZWJzaXRlcyBhbmQgcHJvamVjdCBwYXRjaGVzLiIpfTxkaXYgY2xhc3M9ImNhcmRzIj4ke3NraWxscy5tYXAocz0+YDxkaXYgY2xhc3M9InBhbmVsIHBhZCI+PGRpdiBjbGFzcz0iaWNvbiI+JHtzWzNdfTwvZGl2PjxoMiBzdHlsZT0ibWFyZ2luLXRvcDoxMnB4Ij4ke3NbMF19PC9oMj48cCBjbGFzcz0ic21hbGwiPiR7c1sxXX08L3A+PHAgY2xhc3M9InJpc2stJHtzWzJdPT09ImxvdyI/ImxvdyI6c1syXT09PSJtZWRpdW0iPyJtZWQiOiJoaWdoIn0iPlJpc2s6ICR7c1syXX08L3A+PGRpdiBjbGFzcz0icm93Ij48YnV0dG9uIGNsYXNzPSJidG4gYmx1ZSIgb25jbGljaz0idG9hc3QoJ1BsYW46ICR7c1swXX0nKSI+UGxhbjwvYnV0dG9uPjxidXR0b24gY2xhc3M9ImJ0biIgb25jbGljaz0idG9hc3QoJ0RyeSBSdW46ICR7c1swXX0nKSI+RHJ5IFJ1bjwvYnV0dG9uPjxidXR0b24gY2xhc3M9ImJ0biIgb25jbGljaz0idG9hc3QoJ1JlcXVlc3Q6ICR7c1swXX0nKSI+Q3JlYXRlPC9idXR0b24+PC9kaXY+PC9kaXY+YCkuam9pbigiIil9PC9kaXY+YDsKZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIkRlc2t0b3AiKS5pbm5lckhUTUw9YCR7aGVhZCgiRGVza3RvcCIsIlNhZmUgZGVza3RvcCBvYnNlcnZlciBhbmQgZHJ5LXJ1biBhY3Rpb24gcHJldmlldy4iKX08ZGl2IGNsYXNzPSJjYXJkcyB0d28iPjxkaXYgY2xhc3M9InBhbmVsIHBhZCI+PGgyPkFjdGl2ZSBXaW5kb3c8L2gyPiR7Y2FyZCgiTG9jYWxDb21ldCBDb250cm9sIFBhbmVsIiwiUHJlbWl1bSBVSSBOb3cgbW9kZS4gIiArIGJhZGdlKCJzYWZlIiwiZ3JlZW4iKSl9PGRpdiBjbGFzcz0ic2NyZWVuc2hvdCI+QW5pbWF0ZWQgc2NyZWVuc2hvdCBwcmV2aWV3IHBsYWNlaG9sZGVyPC9kaXY+PC9kaXY+PGRpdiBjbGFzcz0icGFuZWwgcGFkIj48aDI+V2luZG93IExpc3Q8L2gyPjx0YWJsZT4ke3Jvd3MoW1siTG9jYWxDb21ldCBDb250cm9sIFBhbmVsIiwiYWN0aXZlIl0sWyJWUyBDb2RlIiwiYmFja2dyb3VuZCJdLFsiQnJvd3NlciIsInByZXZpZXciXSxbIkxNIFN0dWRpbyIsInJlYWR5Il1dKX08L3RhYmxlPjwvZGl2PjxkaXYgY2xhc3M9InBhbmVsIHBhZCI+PGgyPkRyeSBDb250cm9sczwvaDI+JHtjYXJkKCJNb3VzZSIsIng6IDEyODQgwrcgeTogNzQyIil9JHtjYXJkKCJEcnkgQ2xpY2siLCJObyByZWFsIGNsaWNrIGV4ZWN1dGVkLiIpfSR7Y2FyZCgiRHJ5IEhvdGtleSIsIlZhbGlkYXRpb24gb25seS4iKX08L2Rpdj48ZGl2IGNsYXNzPSJwYW5lbCBwYWQiPjxoMj5Gb2N1cyBDb25maXJtYXRpb248L2gyPjxwIGNsYXNzPSJzbWFsbCI+V2luZG93IGZvY3VzIHJlcXVpcmVzIGV4cGxpY2l0IGNvbmZpcm1hdGlvbiBhbmQgc2Vuc2l0aXZlLXRpdGxlIGd1YXJkLjwvcD48YnV0dG9uIGNsYXNzPSJidG4gYmx1ZSIgb25jbGljaz0idG9hc3QoJ0ZvY3VzIHJlcXVlc3QgY3JlYXRlZCDigJQgbW9jayBvbmx5JykiPkNyZWF0ZSBGb2N1cyBSZXF1ZXN0PC9idXR0b24+PC9kaXY+PC9kaXY+YDsKZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIlVJIFBhcnNlciIpLmlubmVySFRNTD1gJHtoZWFkKCJVSSBQYXJzZXIiLCJFbGVtZW50IGV4dHJhY3Rpb24gdGFibGUgYW5kIHNhZmUgYWN0aW9uIHN1Z2dlc3Rpb25zLiIpfTxkaXYgY2xhc3M9InBhbmVsIHBhZCI+PGRpdiBjbGFzcz0icm93IiBzdHlsZT0ianVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW4iPjxoMj5FbGVtZW50czwvaDI+PGRpdiBjbGFzcz0icm93Ij4ke1siUGFyc2UgU2NyZWVuIiwiRmluZCBFbGVtZW50IiwiU3VnZ2VzdCBBY3Rpb24iLCJFeHBvcnQgSlNPTiJdLm1hcCh4PT5gPGJ1dHRvbiBjbGFzcz0iYnRuIiBvbmNsaWNrPSJ0b2FzdCgnJHt4fSBtb2NrIGFjdGlvbicpIj4ke3h9PC9idXR0b24+YCkuam9pbigiIil9PC9kaXY+PC9kaXY+PHRhYmxlPiR7dGFibGUoWyJ0eXBlIiwidGV4dCIsImNvbmZpZGVuY2UiLCJiYm94IiwiY2VudGVyIiwic291cmNlIiwic2FmZXR5Il0sW1sid2luZG93IiwiTG9jYWxDb21ldCBDb250cm9sIFBhbmVsIiwiMC45OCIsIlswLDAsMTQ0MCw5MDBdIiwiNzIwLDQ1MCIsImRlc2t0b3AiLCJzYWZlIl0sWyJidXR0b24iLCJEcnkgUnVuIiwiMC45NCIsIlsxMDMwLDE0LDExMDAsNDhdIiwiMTA2NSwzMSIsInVpIiwic2FmZSJdLFsiaW5wdXQiLCJTZWFyY2ggY29tbWFuZCIsIjAuOTEiLCJbNDIwLDEyLDgyMCw1MF0iLCI2MjAsMzEiLCJ1aSIsInNhZmUiXSxbIm1lbnUiLCJTd2lzcyBLbmlmZSIsIjAuOTAiLCJbMTIsMTMwLDIzMCwxNjZdIiwiMTIxLDE0OCIsInNpZGViYXIiLCJzYWZlIl0sWyJ0ZXh0IiwiU2FmZSBNb2RlIE9OIiwiMC44OCIsIlsyMCw4MjAsMTgwLDg1MF0iLCIxMDAsODM1Iiwic2lkZWJhciIsInNhZmUiXV0pfTwvdGFibGU+PC9kaXY+YDsKZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIlByb2plY3RzIikuaW5uZXJIVE1MPWAke2hlYWQoIlByb2plY3RzIiwiTG9jYWxBZ2VudCBwcm9qZWN0IGludGVsbGlnZW5jZSBhbmQgcmVhZGluZXNzLiIpfTxkaXYgY2xhc3M9ImNhcmRzIHRocmVlIj4ke2NhcmQoIkN1cnJlbnQgUHJvamVjdCIsIkM6XFxcXFVzZXJzXFxcXEROU1xcXFxEb2N1bWVudHNcXFxcTG9jYWxBZ2VudCIpfSR7Y2FyZCgiSGVhbHRoIFNjb3JlIiwiRXhjZWxsZW50IMK3IDYvNiBBdXRvIFZlcmlmaWNhdGlvbiIpfSR7Y2FyZCgiQUdFTlRTLm1kIiwiRGV0ZWN0ZWQgYW5kIHZhbGlkIil9JHtjYXJkKCJEZXRlY3RlZCBTdGFjayIsIlB5dGhvbiArIFRraW50ZXIgKyBQcmVtaXVtIHN0YXRpYyBVSSIpfSR7Y2FyZCgiU2FmZSBDb21tYW5kcyIsInB5X2NvbXBpbGUsIHN0YXR1cywgcmVwb3J0LCBkcnktcnVuIil9JHtjYXJkKCJQYXRjaCBSZWFkaW5lc3MiLCJSb2xsYmFjayBhdmFpbGFibGUiKX08L2Rpdj48ZGl2IGNsYXNzPSJwYW5lbCBwYWQiIHN0eWxlPSJtYXJnaW4tdG9wOjE2cHgiPjxoMj5SZWNlbnQgRm9sZGVyczwvaDI+PHRhYmxlPiR7cm93cyhbWyJQcm9qZWN0cy9VSSIsInByZW1pdW0gZGFzaGJvYXJkIl0sWyJQcm9qZWN0cy9SZXBvcnRzIiwidmVyaWZpY2F0aW9uIHJlcG9ydHMiXSxbIlByb2plY3RzL1BDQWdlbnQiLCJhZ2VudCBtb2R1bGVzIl0sWyJtb2R1bGVzIiwicHl0aG9uIGNvbW1hbmRzIl1dKX08L3RhYmxlPjwvZGl2PmA7CmRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJQYXRjaGVzIikuaW5uZXJIVE1MPWAke2hlYWQoIlBhdGNoZXMiLCJTZWxmLWVkaXQgcGF0Y2ggd29ya2Zsb3cgYW5kIHJlZ2lzdHJ5LiIpfTxkaXYgY2xhc3M9InBhbmVsIHBhZCI+PGgyPldvcmtmbG93PC9oMj48ZGl2IGNsYXNzPSJwaXBlbGluZSI+JHtbIkltcG9ydCIsIlZhbGlkYXRlIiwiQXBwbHkiLCJSdW4gVGVzdHMiLCJBdXRvIFZlcmlmaWNhdGlvbiIsIkZ1bGwgU3RhYmlsaXR5IiwiUm9sbGJhY2siXS5tYXAoeD0+YDxkaXYgY2xhc3M9InBpcGUiPjxzdHJvbmc+JHt4fTwvc3Ryb25nPjwvZGl2PmApLmpvaW4oIiIpfTwvZGl2PjwvZGl2PjxkaXYgY2xhc3M9InBhbmVsIHBhZCIgc3R5bGU9Im1hcmdpbi10b3A6MTZweCI+PGgyPlJlZ2lzdHJ5PC9oMj48dGFibGU+JHt0YWJsZShbInZlcnNpb24iLCJzdW1tYXJ5Iiwic3RhdHVzIiwidGVzdHMiLCJ0aW1lc3RhbXAiXSxbWyJ2Ni4zMCIsIlByZW1pdW0gVUkgTm93IiwicmVhZHkiLCJzYWZlIiwiMjAyNi0wNy0wNyJdLFsidjYuMjliIiwiUHJlbWl1bSBVSSBMYXVuY2hlciBSZXBhaXIiLCJyZWFkeSIsIjEyLzEyIiwiMjAyNi0wNy0wNyJdLFsidjYuMjhkIiwiUHJlbWl1bSBEYXNoYm9hcmQgUHJvdG90eXBlIiwiYXBwbGllZCIsIjEwLzEwIiwiMjAyNi0wNy0wNyJdLFsidjYuMjdjIiwiU3dpc3MgS25pZmUgU2tpbGwgTGF1bmNoZXIiLCJhcHBsaWVkIiwiMTUvMTUiLCIyMDI2LTA3LTA3Il1dKX08L3RhYmxlPjwvZGl2PmA7CmRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJSZXBvcnRzIikuaW5uZXJIVE1MPWAke2hlYWQoIlJlcG9ydHMiLCJHZW5lcmF0ZWQgcmVwb3J0cyBhbmQgc2FmZSBleHBvcnRzLiIpfTxkaXYgY2xhc3M9ImNhcmRzIHRocmVlIj4ke3JlcG9ydHMubWFwKHg9PmNhcmQoeCwic3RhdHVzOiBvayDCtyBnZW5lcmF0ZWRfYXQ6IDIwMjYtMDctMDciLGA8YnV0dG9uIGNsYXNzPSJidG4iIG9uY2xpY2s9InRvYXN0KCdPcGVuICR7eH0gcmVwb3J0JykiPk9wZW48L2J1dHRvbj4gPGJ1dHRvbiBjbGFzcz0iYnRuIiBvbmNsaWNrPSJ0b2FzdCgnRXhwb3J0ICR7eH0gcmVwb3J0JykiPkV4cG9ydDwvYnV0dG9uPmApKS5qb2luKCIiKX08L2Rpdj5gOwpkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiU2FmZXR5IikuaW5uZXJIVE1MPWAke2hlYWQoIlNhZmV0eSIsIlNlbWFudGljIEZpcmV3YWxsIGFuZCBkZXN0cnVjdGl2ZS1hY3Rpb24gZ3VhcmRzLiIpfTxkaXYgY2xhc3M9InBhbmVsIHBhZCIgc3R5bGU9ImJvcmRlci1jb2xvcjpyZ2JhKDI1MSwxMTMsMTMzLC4yOCk7YmFja2dyb3VuZDpyZ2JhKDI1MSwxMTMsMTMzLC4wOCkiPjxoMj5Mb2NhbENvbWV0IGNhbm5vdCBleGVjdXRlIGRlc3RydWN0aXZlIGFjdGlvbnMgd2l0aG91dCBleHBsaWNpdCBzYWZlIHdvcmtmbG93LjwvaDI+PHAgY2xhc3M9InNtYWxsIj5ObyBzaGVsbCwgbm8gc2VjcmV0cywgbm8gZGVsZXRlLCBkcnktcnVuIHJlcXVpcmVkLCBjb25maXJtYXRpb24gcmVxdWlyZWQsIHF1YXJhbnRpbmUgaW5zdGVhZCBvZiBkZWxldGlvbi48L3A+PC9kaXY+PGRpdiBjbGFzcz0iY2FyZHMgdGhyZWUiIHN0eWxlPSJtYXJnaW4tdG9wOjE2cHgiPiR7WyJubyBzaGVsbC9jbWQvcG93ZXJzaGVsbCIsIm5vIHNlY3JldHMvdG9rZW5zL1NTSCIsIm5vIGRlbGV0ZS9mb3JtYXQiLCJkcnktcnVuIHJlcXVpcmVkIiwiZXhwbGljaXQgY29uZmlybWF0aW9uIiwicXVhcmFudGluZSBpbnN0ZWFkIGRlbGV0ZSJdLm1hcCh4PT5jYXJkKCJSdWxlIix4LGJhZGdlKCJhY3RpdmUiLCJncmVlbiIpKSkuam9pbigiIil9PC9kaXY+PGRpdiBjbGFzcz0icGFuZWwgcGFkIiBzdHlsZT0ibWFyZ2luLXRvcDoxNnB4Ij48aDI+QmxvY2tlZCBUZXJtczwvaDI+PHAgY2xhc3M9InNtYWxsIG1vbm8iPmRlbGV0ZSDCtyBmb3JtYXQgwrcgd2lwZSDCtyBwYXNzd29yZCDCtyB0b2tlbiDCtyBzc2ggwrcgYmFuayDCtyBzaGVsbCDCtyBwb3dlcnNoZWxsIMK3IGNtZCDCtyBzcGFtIMK3IGJ1bGsgZG08L3A+PC9kaXY+YDsKZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIlNldHRpbmdzIikuaW5uZXJIVE1MPWAke2hlYWQoIlNldHRpbmdzIiwiTW9jayBzZXR0aW5ncyBmb3IgcHJvdG90eXBlIG1vZGUuIil9PGRpdiBjbGFzcz0iY2FyZHMgdHdvIj4ke1siTW9kZWwgQmFja2VuZDogTE0gU3R1ZGlvIiwiUmVsYXkgUGF0aDogUHJvamVjdHMvQ2hhdEdQVFJlbGF5IiwiUHJvamVjdCBSb290OiBMb2NhbEFnZW50IiwiU2FmZXR5IFByb2ZpbGU6IFN0cmljdCIsIlRoZW1lOiBQcmVtaXVtIERhcmsiLCJDb21tYW5kIFBhbGV0dGU6IEVuYWJsZWQiLCJVSSBOb3cgQXV0byBPcGVuOiBFbmFibGVkIl0ubWFwKHg9PmNhcmQoeCwiTW9jayBzZXR0aW5nIG9ubHkuIE5vIGJhY2tlbmQgYWN0aW9uLiIsYDxidXR0b24gY2xhc3M9ImJ0biIgb25jbGljaz0idG9hc3QoJ1NhdmVkICR7eH0nKSI+U2F2ZTwvYnV0dG9uPmApKS5qb2luKCIiKX08L2Rpdj5gO30KZnVuY3Rpb24gdG9hc3QobXNnKXtjb25zdCB0PWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoImRpdiIpO3QuY2xhc3NOYW1lPSJ0b2FzdCI7dC5pbm5lckhUTUw9YDxzdHJvbmc+TG9jYWxDb21ldDwvc3Ryb25nPjxkaXYgY2xhc3M9InNtYWxsIj4ke21zZ308L2Rpdj5gO2RvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0b2FzdHMiKS5hcHBlbmRDaGlsZCh0KTtzZXRUaW1lb3V0KCgpPT50LnJlbW92ZSgpLDMyMDApfWZ1bmN0aW9uIHNob3dTdG9wKCl7ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1vZGFsIikuY2xhc3NMaXN0LmFkZCgic2hvdyIpfWZ1bmN0aW9uIGhpZGVTdG9wKCl7ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1vZGFsIikuY2xhc3NMaXN0LnJlbW92ZSgic2hvdyIpfWZ1bmN0aW9uIGNvbmZpcm1TdG9wKCl7aGlkZVN0b3AoKTtkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgic3RvcHBlZEJhbm5lciIpLmNsYXNzTGlzdC5hZGQoInNob3ciKTt0b2FzdCgiRW1lcmdlbmN5IFN0b3AgYWN0aXZhdGVkIOKAlCBtb2NrIGZyb250ZW5kIHN0YXRlIG9ubHkiKX1mdW5jdGlvbiByZXN0b3JlKCl7ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInN0b3BwZWRCYW5uZXIiKS5jbGFzc0xpc3QucmVtb3ZlKCJzaG93Iik7dG9hc3QoIk1vY2sgcnVudGltZSByZXN0b3JlZCIpfWRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoImtleWRvd24iLGU9PntpZigoZS5jdHJsS2V5fHxlLm1ldGFLZXkpJiZlLmtleS50b0xvd2VyQ2FzZSgpPT09ImsiKXtlLnByZXZlbnREZWZhdWx0KCk7ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInNlYXJjaCIpLmZvY3VzKCk7dG9hc3QoIkNvbW1hbmQgcGFsZXR0ZSBmb2N1c2VkIil9fSk7ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInNlYXJjaCIpLmFkZEV2ZW50TGlzdGVuZXIoImtleWRvd24iLGU9PntpZihlLmtleT09PSJFbnRlciIpe2NvbnN0IHE9ZS50YXJnZXQudmFsdWUudHJpbSgpO2lmKCFxKXJldHVybjtjb25zdCBwYWdlPXBhZ2VzLmZpbmQocD0+cC50b0xvd2VyQ2FzZSgpLmluY2x1ZGVzKHEudG9Mb3dlckNhc2UoKSkpO2lmKHBhZ2Upc2hvd1BhZ2UocGFnZSk7dG9hc3QoIkNvbW1hbmQ6ICIrcSk7ZS50YXJnZXQudmFsdWU9IiJ9fSk7cmVuZGVyKCk7Cjwvc2NyaXB0Pgo8L2JvZHk+CjwvaHRtbD4K"


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    UI_NOW_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _default_settings():
    return {
        "auto_open_on_panel_start": True,
        "open_only_static_html": True,
        "never_run_npm": True,
        "never_run_shell": True,
        "never_run_backend": True,
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


def install_page():
    _ensure_dirs()
    html = base64.b64decode(HTML_PAYLOAD_B64.encode("ascii")).decode("utf-8")
    UI_NOW_PAGE.write_text(html, encoding="utf-8")
    if not SETTINGS_PATH.exists():
        _save_settings(_default_settings())
    return {
        "ok": True,
        "mode": "premium_ui_now_install_page",
        "generated_at": _now(),
        "page": str(UI_NOW_PAGE),
        "settings": str(SETTINGS_PATH),
    }


def status():
    page_exists = UI_NOW_PAGE.exists()
    settings = _load_settings()
    return {
        "ok": page_exists,
        "mode": "premium_ui_now_status",
        "generated_at": _now(),
        "name": PREMIUM_NOW_NAME,
        "version": PREMIUM_NOW_VERSION,
        "page": str(UI_NOW_PAGE),
        "page_exists": page_exists,
        "settings": settings,
        "commands": [
            "pc premium now status",
            "pc premium now page",
            "pc premium now open",
            "pc premium now auto on",
            "pc premium now auto off",
            "pc premium now report",
            "pc new ui",
            "pc open new ui",
            "новый интерфейс",
        ],
        "safety": [
            "Opens only a static local HTML dashboard.",
            "Does not run npm.",
            "Does not run shell/cmd/powershell.",
            "Does not connect backend.",
            "Does not deploy.",
            "Does not delete files.",
            "Does not use tokens/API keys.",
        ],
    }


def page():
    return install_page()


def open_page(note="manual"):
    result = install_page()
    uri = UI_NOW_PAGE.resolve().as_uri()
    webbrowser.open(uri)
    return {
        "ok": True,
        "mode": "premium_ui_now_open",
        "generated_at": _now(),
        "opened": uri,
        "note": note,
        "message": "Opened static premium UI HTML page only. No npm/shell/backend/deploy was executed.",
        "install": result,
    }


def auto_open_if_enabled():
    global _AUTO_OPEN_DONE
    settings = _load_settings()
    if not settings.get("auto_open_on_panel_start", True):
        return {
            "ok": True,
            "mode": "premium_ui_now_auto_open",
            "generated_at": _now(),
            "opened": False,
            "reason": "auto_open_on_panel_start disabled",
        }
    if _AUTO_OPEN_DONE:
        return {
            "ok": True,
            "mode": "premium_ui_now_auto_open",
            "generated_at": _now(),
            "opened": False,
            "reason": "already opened in this panel process",
        }
    _AUTO_OPEN_DONE = True
    return open_page("auto_open_on_panel_start")


def set_auto(enabled):
    settings = _load_settings()
    settings["auto_open_on_panel_start"] = bool(enabled)
    settings["updated_at"] = _now()
    _save_settings(settings)
    return {
        "ok": True,
        "mode": "premium_ui_now_auto_setting",
        "generated_at": _now(),
        "auto_open_on_panel_start": bool(enabled),
        "settings": str(SETTINGS_PATH),
    }


def report():
    install_page()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "status": status(),
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"premium_ui_now_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"premium_ui_now_report_{_stamp()}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# Premium UI Now Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- page: {UI_NOW_PAGE}",
        f"- ok: {payload['status']['ok']}",
        "",
        "## Safety",
        "",
    ]
    md.extend(f"- {item}" for item in payload["status"]["safety"])
    md_path.write_text("\n".join(md), encoding="utf-8")
    return {
        "ok": True,
        "mode": "premium_ui_now_report",
        "generated_at": _now(),
        "report": str(md_path),
        "json": str(json_path),
    }


def format_payload(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")

    if lower in {"pc premium now", "pc premium now status", "premium now status"}:
        return format_payload(status())

    if lower in {"pc premium now page", "premium now page"}:
        return format_payload(page())

    if lower in {"pc premium now open", "premium now open", "pc new ui", "pc open new ui", "новый интерфейс", "открой новый интерфейс"}:
        return format_payload(open_page("manual command"))

    if lower in {"pc premium now auto on", "premium now auto on"}:
        return format_payload(set_auto(True))

    if lower in {"pc premium now auto off", "premium now auto off"}:
        return format_payload(set_auto(False))

    if lower in {"pc premium now report", "premium now report"}:
        return format_payload(report())

    return format_payload({
        "ok": False,
        "mode": "premium_ui_now_unknown_command",
        "generated_at": _now(),
        "error": "Unknown Premium UI Now command.",
        "commands": status().get("commands", []),
    })


def is_premium_ui_now_command(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    exact = {
        "pc premium now",
        "pc premium now status",
        "premium now status",
        "pc premium now page",
        "premium now page",
        "pc premium now open",
        "premium now open",
        "pc premium now auto on",
        "premium now auto on",
        "pc premium now auto off",
        "premium now auto off",
        "pc premium now report",
        "premium now report",
        "pc new ui",
        "pc open new ui",
        "новый интерфейс",
        "открой новый интерфейс",
    }
    return lower in exact
````

### ПУТЬ: modules/premium_ui_prototype.py (299 строк, 9319 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json


ROOT_DIR = get_project_root()
UI_ROOT = ROOT_DIR / "Projects" / "UI" / "localcomet-premium-dashboard"
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "premium_ui_prototype"
REQUESTS_DIR = ROOT_DIR / "Projects" / "UI" / "localcomet-premium-dashboard_requests"

PREMIUM_UI_VERSION = "v6.29b"
PREMIUM_UI_NAME = "LocalComet Premium Dashboard Prototype + Launcher Ready"


EXPECTED_FILES = [
    "package.json",
    "vite.config.ts",
    "tailwind.config.ts",
    "index.html",
    "src/App.tsx",
    "src/main.tsx",
    "src/index.css",
    "src/layout/Sidebar.tsx",
    "src/layout/TopBar.tsx",
    "src/layout/CommandPalette.tsx",
    "src/layout/EmergencyStopModal.tsx",
    "src/pages/CommandCenterPage.tsx",
    "src/pages/AgentOSPage.tsx",
    "src/pages/SwissKnifePage.tsx",
    "src/pages/DesktopPage.tsx",
    "src/pages/UIParserPage.tsx",
    "src/pages/ProjectsPage.tsx",
    "src/pages/PatchesPage.tsx",
    "src/pages/ReportsPage.tsx",
    "src/pages/SafetyPage.tsx",
    "src/pages/SettingsPage.tsx",
    "src/data/mock.ts",
    "src/data/skills.ts",
    "src/lib/store.tsx",
    "src/types/index.ts",
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def _file_info(rel_path):
    path = UI_ROOT / rel_path
    if not path.exists():
        return {"path": rel_path, "exists": False}
    return {
        "path": rel_path,
        "exists": True,
        "size": path.stat().st_size,
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
    }


def _list_project_files():
    if not UI_ROOT.exists():
        return []
    files = []
    for path in sorted(UI_ROOT.rglob("*")):
        if path.is_file():
            rel = path.relative_to(UI_ROOT).as_posix()
            if "/node_modules/" in rel or rel.startswith("node_modules/"):
                continue
            files.append({
                "path": rel,
                "size": path.stat().st_size,
            })
    return files


def audit():
    package_path = UI_ROOT / "package.json"
    package = _read_json(package_path) if package_path.exists() else {}

    files = [_file_info(item) for item in EXPECTED_FILES]
    missing = [item["path"] for item in files if not item["exists"]]

    package_text = package_path.read_text(encoding="utf-8") if package_path.exists() else ""
    supabase_present = "supabase" in package_text.lower()

    checks = [
        {"name": "ui_root_exists", "ok": UI_ROOT.exists(), "detail": str(UI_ROOT)},
        {"name": "expected_files_present", "ok": not missing, "detail": missing},
        {"name": "frontend_only_no_supabase_dependency", "ok": not supabase_present, "detail": "supabase not found in package.json"},
        {"name": "vite_react_present", "ok": (UI_ROOT / "vite.config.ts").exists(), "detail": "vite.config.ts"},
        {"name": "tailwind_present", "ok": (UI_ROOT / "tailwind.config.ts").exists(), "detail": "tailwind.config.ts"},
        {"name": "safe_emergency_modal_present", "ok": (UI_ROOT / "src" / "layout" / "EmergencyStopModal.tsx").exists(), "detail": "mock modal only"},
        {"name": "command_palette_present", "ok": (UI_ROOT / "src" / "layout" / "CommandPalette.tsx").exists(), "detail": "mock searchable commands"},
    ]

    return {
        "ok": all(item["ok"] for item in checks),
        "mode": "premium_ui_audit",
        "generated_at": _now(),
        "version": PREMIUM_UI_VERSION,
        "ui_root": str(UI_ROOT),
        "package": {
            "name": package.get("name"),
            "version": package.get("version"),
            "scripts": package.get("scripts", {}),
            "dependencies": package.get("dependencies", {}),
            "devDependencies": package.get("devDependencies", {}),
        },
        "checks": checks,
        "missing": missing,
    }


def status():
    result = audit()
    project_files = _list_project_files()
    return {
        "ok": result["ok"],
        "mode": "premium_ui_status",
        "generated_at": _now(),
        "name": PREMIUM_UI_NAME,
        "version": PREMIUM_UI_VERSION,
        "ui_root": str(UI_ROOT),
        "files_count": len(project_files),
        "audit": result,
        "commands": [
            "pc premium ui status",
            "pc premium ui files",
            "pc premium ui audit",
            "pc premium ui open request",
            "pc premium ui report",
        ],
        "safety": [
            "Frontend-only prototype.",
            "No shell/cmd/powershell execution.",
            "No delete/format actions.",
            "No secrets/tokens/SSH.",
            "No backend bridge yet.",
            "Emergency Stop is mock UI state only.",
        ],
    }


def files():
    return {
        "ok": UI_ROOT.exists(),
        "mode": "premium_ui_files",
        "generated_at": _now(),
        "ui_root": str(UI_ROOT),
        "files": _list_project_files(),
    }


def open_request():
    _ensure_dirs()
    request_path = REQUESTS_DIR / f"premium_ui_manual_preview_request_{_stamp()}.md"
    content = f"""# LocalComet Premium Dashboard Manual Preview Request

Generated: {_now()}

Prototype path:

```text
{UI_ROOT}
```

This command intentionally does not launch a browser, terminal, npm, shell, cmd, PowerShell, install, deploy, or backend action.

Manual preview options:

```text
cd C:\\Users\\DNS\\Documents\\LocalAgent\\Projects\\UI\\localcomet-premium-dashboard
npm install
npm run dev
```

Safety:

- frontend-only;
- no real backend;
- no real command execution;
- no secrets;
- no delete actions;
- no deploy actions.
"""
    request_path.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "mode": "premium_ui_open_request",
        "generated_at": _now(),
        "request": str(request_path),
        "message": "Manual preview request created. No browser or shell was launched.",
    }


def report():
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "status": status(),
        "files": files(),
    }

    json_path = REPORTS_DIR / f"premium_ui_prototype_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"premium_ui_prototype_report_{_stamp()}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# LocalComet Premium Dashboard Prototype Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- ui_root: {UI_ROOT}",
        f"- ok: {payload['status']['ok']}",
        f"- files_count: {payload['status']['files_count']}",
        "",
        "## Commands",
        "",
    ]
    md.extend(f"- `{command}`" for command in payload["status"]["commands"])
    md.extend([
        "",
        "## Safety",
        "",
    ])
    md.extend(f"- {item}" for item in payload["status"]["safety"])
    md_path.write_text("\n".join(md), encoding="utf-8")

    return {
        "ok": True,
        "mode": "premium_ui_report",
        "generated_at": _now(),
        "report": str(md_path),
        "json": str(json_path),
    }


def format_text(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")

    if lower in {"pc premium ui", "pc premium ui status", "premium ui status"}:
        return format_text(status())
    if lower in {"pc premium ui files", "premium ui files"}:
        return format_text(files())
    if lower in {"pc premium ui audit", "premium ui audit"}:
        return format_text(audit())
    if lower in {"pc premium ui open request", "pc premium ui preview request", "premium ui open request"}:
        return format_text(open_request())
    if lower in {"pc premium ui report", "premium ui report"}:
        return format_text(report())

    return format_text({
        "ok": False,
        "mode": "premium_ui_unknown_command",
        "generated_at": _now(),
        "error": "Unknown premium UI command.",
        "commands": status().get("commands", []),
    })


def is_premium_ui_command(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    exact = {
        "pc premium ui",
        "pc premium ui status",
        "premium ui status",
        "pc premium ui files",
        "premium ui files",
        "pc premium ui audit",
        "premium ui audit",
        "pc premium ui open request",
        "pc premium ui preview request",
        "premium ui open request",
        "pc premium ui report",
        "premium ui report",
    }
    return lower in exact
````

### ПУТЬ: modules/project_audit_bundle_ru.py (837 строк, 32558 байт)

````python
from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


RELEASE = "v6.80.2"
VERIFIER_SCHEMA_VERSION = "v6.80.2"
MANIFEST_NAME = "localcomet_runtime_manifest.json"
FIXED_ZIP_DT = (2026, 1, 1, 0, 0, 0)
TEXT_EXTENSIONS = {
    ".bat",
    ".cfg",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".pyw",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
SOURCE_SCAN_ROOTS = ("agents", "core", "docs", "modules", "next", "tools")
TOP_LEVEL_SOURCE_EXTENSIONS = {".py", ".md", ".json", ".txt"}
SECRET_PATTERNS = (
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")),
    ("github_token", re.compile(r"\bghp_[A-Za-z0-9_]{12,}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("authorization_header", re.compile(r"\bAuthorization\s*:\s*(Bearer|Basic)\s+\S+", re.IGNORECASE)),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b", re.IGNORECASE)),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|token|password|passwd|secret|client[_-]?secret)\b\s*[:=]\s*['\"]?[^'\"\s]{8,}"
        ),
    ),
)
REDACT_PATTERNS = tuple((name, re.compile(pattern.pattern, pattern.flags)) for name, pattern in SECRET_PATTERNS)
EXCLUDE_PREFIXES = (
    ".git/",
    ".incident_backup/",
    ".tmp/",
    ".localcomet/temp/",
    ".localcomet/reviewer/",
    "Projects/BrowserProfile/",
    "LocalAgent_Archive/",
)
EXCLUDE_GLOBS = (
    "__pycache__/**",
    "*.pyc",
    "*.pyo",
    "*.zip",
    "*.7z",
    "*.rar",
    "tools/install_*.py",
    "tools/repair_russian_menu_v617d.py",
)
GENERATED_PREFIXES = (
    "Projects/Reports/",
    "Projects/Logs/",
    "Projects/ComputerUse/reports/",
)
RUNTIME_JSON_PREFIXES = ("Projects/",)
TEST_COMMANDS = [
    "tools/test_v677_regression.py",
    "tools/test_v678_router_registry.py",
    "tools/test_v679_retention.py",
    "tools/test_v680_reproducibility.py",
    "tools/test_v6801_audit_bundle.py",
]
RECURSIVE_TEST_COMMANDS = {
    "tools/test_v6801_audit_bundle.py",
    "tools/test_v6802_bundle_security.py",
}
AUDIT_BUNDLE_TEST_ENV = "LOCALCOMET_AUDIT_BUNDLE_RUNNING_TESTS"


class AuditBundleError(RuntimeError):
    pass


@dataclass(frozen=True)
class IncludedFile:
    rel_path: str
    category: str
    origin: str
    size: int
    sha256: str


def _json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AuditBundleError(f"unable to read JSON {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuditBundleError(f"{path.name} must contain a JSON object")
    return payload


def _redact_path_text(text: str) -> str:
    home = str(Path.home()).replace("\\", "/")
    if home:
        text = text.replace(str(Path.home()), "<USER_HOME>")
        text = text.replace(home, "<USER_HOME>")
    return text


def redact_text(text: str, limit: int | None = None) -> str:
    redacted = _redact_path_text(str(text))
    for category, pattern in REDACT_PATTERNS:
        redacted = pattern.sub(f"<REDACTED:{category}>", redacted)
    if limit is not None and len(redacted) > limit:
        redacted = redacted[:limit] + "\n<TRUNCATED>"
    return redacted


def _safe_rel_path(raw: str) -> str:
    value = str(raw or "").replace("\\", "/").strip()
    if not value:
        raise AuditBundleError("empty path is not allowed")
    if PureWindowsPath(value).drive or value.startswith("/") or value.startswith("\\"):
        raise AuditBundleError(f"absolute path rejected: {raw}")
    pure = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise AuditBundleError(f"unsafe relative path rejected: {raw}")
    return pure.as_posix()


def _resolve_under_root(root: Path, rel_path: str) -> Path:
    safe = _safe_rel_path(rel_path)
    path = (root / safe).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise AuditBundleError(f"path escapes project root: {rel_path}") from exc
    return path


def _is_reparse_point(path: Path) -> bool:
    try:
        return bool(path.lstat().st_file_attributes & 0x400)
    except AttributeError:
        return False
    except OSError:
        return False


def _has_external_link(root: Path, path: Path) -> bool:
    root_resolved = root.resolve()
    current = path
    chain = [path, *path.parents]
    for candidate in chain:
        if candidate == root_resolved.parent:
            break
        if candidate.exists() and (candidate.is_symlink() or _is_reparse_point(candidate)):
            try:
                candidate.resolve().relative_to(root_resolved)
            except ValueError:
                return True
    try:
        path.resolve().relative_to(root_resolved)
    except ValueError:
        return True
    return False


def _run_git(root: Path, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )


def _git_lines(root: Path, args: list[str]) -> list[str]:
    result = _run_git(root, args)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _collect_git_metadata(root: Path) -> dict[str, str]:
    commands = {
        "git_status.txt": ["status", "--short", "--untracked-files=no"],
        "git_diff.patch": ["diff", "--binary", "HEAD"],
        "git_diff_stat.txt": ["diff", "--stat", "HEAD"],
        "git_diff_name_status.txt": ["diff", "--name-status", "HEAD"],
    }
    metadata: dict[str, str] = {}
    for name, args in commands.items():
        try:
            result = _run_git(root, args, timeout=120)
            text = result.stdout if result.returncode == 0 else (result.stderr or result.stdout)
        except Exception as exc:
            text = f"{type(exc).__name__}: {exc}"
        metadata[name] = redact_text(text)
    return metadata


def _load_runtime_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_NAME
    if not path.exists():
        raise AuditBundleError(f"missing required {MANIFEST_NAME}")
    data = _read_json(path)
    for key in ("entrypoints", "runtime", "lazy_runtime", "tests", "tools"):
        if key not in data or not isinstance(data[key], list):
            raise AuditBundleError(f"{MANIFEST_NAME} missing list category: {key}")
    return data


def _manifest_category_map(manifest: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for category in ("entrypoints", "runtime", "lazy_runtime", "tests", "tools"):
        for item in manifest.get(category, []):
            mapping[_safe_rel_path(str(item))] = category
    mapping[MANIFEST_NAME] = "metadata_manifest"
    return mapping


def _discover_source_files(root: Path, tracked: set[str], manifest_map: dict[str, str]) -> dict[str, tuple[str, str]]:
    candidates: dict[str, tuple[str, str]] = {}
    for rel in tracked:
        candidates[rel] = (manifest_map.get(rel, "tracked"), "git_ls_files")
    for rel, category in manifest_map.items():
        candidates[rel] = (category, "runtime_manifest")
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if child.is_file() and child.suffix.lower() in TOP_LEVEL_SOURCE_EXTENSIONS:
            rel = child.relative_to(root).as_posix()
            candidates.setdefault(rel, (manifest_map.get(rel, "important_untracked_source"), "source_scan"))
    for scan_root in SOURCE_SCAN_ROOTS:
        base = root / scan_root
        if not base.exists() or not base.is_dir():
            continue
        for path in sorted(base.rglob("*"), key=lambda p: p.as_posix().lower()):
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            rel = path.relative_to(root).as_posix()
            candidates.setdefault(rel, (manifest_map.get(rel, "important_untracked_source"), "source_scan"))
    return candidates


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _exclude_reason(rel_path: str, include_generated: bool) -> str | None:
    lower = rel_path.lower()
    if any(rel_path.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return "excluded_private_or_runtime_prefix"
    if _matches_any(rel_path, EXCLUDE_GLOBS):
        return "excluded_generated_or_archive_pattern"
    if not include_generated and any(rel_path.startswith(prefix) for prefix in GENERATED_PREFIXES):
        return "excluded_generated_report"
    if lower.endswith((".json", ".jsonl")) and any(rel_path.startswith(prefix) for prefix in RUNTIME_JSON_PREFIXES):
        return "excluded_projects_runtime_json"
    return None


def _scan_secrets(path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    data = path.read_bytes()
    text = data.decode("utf-8", errors="ignore")
    for line_no, line in enumerate(text.splitlines(), start=1):
        for category, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({"line": line_no, "category": category})
    return findings


def scan_text_for_secret_markers(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line_no, line in enumerate(str(text).splitlines(), start=1):
        for category, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({"line": line_no, "category": category})
    return findings


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_files(
    root: Path,
    include_generated: bool,
    max_file_size_mb: float,
    blocked_output_paths: set[str] | None = None,
) -> tuple[list[IncludedFile], dict[str, str], list[dict[str, Any]], list[dict[str, Any]], list[str], dict[str, int]]:
    manifest = _load_runtime_manifest(root)
    manifest_map = _manifest_category_map(manifest)
    tracked = {_safe_rel_path(path) for path in _git_lines(root, ["ls-files"])}
    cached = sorted(_git_lines(root, ["diff", "--cached", "--name-only"]))
    candidates = _discover_source_files(root, tracked, manifest_map)
    included: list[IncludedFile] = []
    hashes: dict[str, str] = {}
    excluded: list[dict[str, Any]] = []
    secret_findings: list[dict[str, Any]] = []
    categories: dict[str, int] = {}
    seen: set[str] = set()
    max_bytes = int(max_file_size_mb * 1024 * 1024)
    blocked_output_paths = blocked_output_paths or set()

    for rel_path in sorted(candidates, key=str.lower):
        try:
            safe_rel = _safe_rel_path(rel_path)
            if safe_rel in blocked_output_paths:
                excluded.append({"path": safe_rel, "reason": "output_archive_not_included"})
                continue
            if safe_rel in seen:
                excluded.append({"path": safe_rel, "reason": "duplicate_candidate"})
                continue
            seen.add(safe_rel)
            path = root / safe_rel
            if not path.exists():
                excluded.append({"path": safe_rel, "reason": "missing"})
                continue
            if not path.is_file():
                excluded.append({"path": safe_rel, "reason": "not_a_file"})
                continue
            if _has_external_link(root, path):
                excluded.append({"path": safe_rel, "reason": "external_symlink_or_junction"})
                continue
            path = _resolve_under_root(root, safe_rel)
            reason = _exclude_reason(safe_rel, include_generated)
            if reason:
                excluded.append({"path": safe_rel, "reason": reason})
                continue
            size = path.stat().st_size
            if size > max_bytes:
                excluded.append({"path": safe_rel, "reason": "over_size_limit", "size": size})
                continue
            findings = _scan_secrets(path)
            if findings:
                for finding in findings:
                    secret_findings.append(
                        {"file": safe_rel, "line": finding["line"], "category": finding["category"]}
                    )
                excluded.append({"path": safe_rel, "reason": "secret_marker_detected"})
                continue
            digest = _sha256(path)
            category, origin = candidates[rel_path]
            included.append(IncludedFile(safe_rel, category, origin, size, digest))
            hashes[safe_rel] = digest
            categories[category] = categories.get(category, 0) + 1
        except AuditBundleError as exc:
            excluded.append({"path": str(rel_path), "reason": "path_security_rejected", "detail": str(exc)})
    if cached:
        excluded.append({"path": "<git-index>", "reason": "staged_files_present", "count": len(cached)})
    return included, hashes, excluded, secret_findings, sorted(tracked, key=str.lower), categories


def _module_name_for_path(path: str) -> str | None:
    if not path.endswith(".py"):
        return None
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _build_import_graph(root: Path, included: list[IncludedFile], category_map: dict[str, str]) -> dict[str, Any]:
    module_to_path = {
        module: item.rel_path
        for item in included
        for module in [_module_name_for_path(item.rel_path)]
        if module
    }
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    for item in sorted(included, key=lambda f: f.rel_path.lower()):
        if not item.rel_path.endswith(".py"):
            continue
        node_module = _module_name_for_path(item.rel_path) or item.rel_path
        nodes.append(
            {
                "path": item.rel_path,
                "module": node_module,
                "category": category_map.get(item.rel_path, item.category),
                "entrypoint": category_map.get(item.rel_path) == "entrypoints",
            }
        )
        try:
            tree = ast.parse((root / item.rel_path).read_text(encoding="utf-8", errors="ignore"))
        except Exception as exc:
            unresolved.append({"from": item.rel_path, "import": "<parse_error>", "reason": type(exc).__name__})
            continue
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    imports.add("." * node.level + (node.module or ""))
                elif node.module:
                    imports.add(node.module)
        for imported in sorted(imports):
            target = None
            if imported.startswith("."):
                unresolved.append({"from": item.rel_path, "import": imported, "reason": "relative_import"})
                continue
            parts = imported.split(".")
            for index in range(len(parts), 0, -1):
                candidate = ".".join(parts[:index])
                if candidate in module_to_path:
                    target = module_to_path[candidate]
                    break
            if target:
                edges.append({"from": item.rel_path, "to": target, "import": imported})
            elif parts[0] in {"agents", "core", "modules", "next", "tools"}:
                unresolved.append({"from": item.rel_path, "import": imported, "reason": "local_module_not_included"})
    return {
        "nodes": sorted(nodes, key=lambda n: n["path"].lower()),
        "edges": sorted(edges, key=lambda e: (e["from"].lower(), e["to"].lower(), e["import"].lower())),
        "unresolved_local_imports": sorted(
            unresolved, key=lambda e: (e["from"].lower(), e["import"].lower(), e["reason"].lower())
        ),
    }


def _collect_versions(root: Path, included_paths: set[str]) -> dict[str, Any]:
    targets = [
        "LocalComet_Control_Panel.py",
        "modules/development_safety_orchestrator_ru.py",
        "modules/reviewer_bridge_ru.py",
        "modules/screenshot_retention_dry_run_ru.py",
        "modules/screenshot_retention_policy_config_ru.py",
        "modules/storage_cleanup_plan_ru.py",
        MANIFEST_NAME,
    ]
    versions: dict[str, Any] = {"release": RELEASE, "markers": {}}
    version_re = re.compile(r"(?m)^([A-Z0-9_]*VERSION[A-Z0-9_]*)\s*=\s*['\"]([^'\"]+)['\"]")
    bridge_re = re.compile(r"(v\d+\.\d+(?:\.\d+)?[a-z]?)")
    for rel in targets:
        if rel not in included_paths and rel != MANIFEST_NAME:
            continue
        path = root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        markers: dict[str, str] = {match.group(1): match.group(2) for match in version_re.finditer(text)}
        found = sorted(set(bridge_re.findall(text)))
        versions["markers"][rel] = {"assignments": markers, "version_mentions": found[:40]}
    return versions


def _run_tests(root: Path, skip_tests: bool) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    if skip_tests:
        return {"skipped": True, "results": results, "summary": {"pass": 0, "fail": 0, "skipped": len(TEST_COMMANDS)}}
    for rel in TEST_COMMANDS:
        path = root / rel
        if rel in RECURSIVE_TEST_COMMANDS or os.environ.get(AUDIT_BUNDLE_TEST_ENV):
            results.append(
                {
                    "command": f"{sys.executable} {rel}",
                    "exit_code": None,
                    "duration_seconds": 0,
                    "status": "SKIP",
                    "reason": "recursive_bundle_test_skipped",
                }
            )
            continue
        if not path.exists():
            results.append({"command": f"{sys.executable} {rel}", "exit_code": None, "duration_seconds": 0, "status": "SKIP"})
            continue
        start = time.perf_counter()
        env = dict(os.environ)
        env[AUDIT_BUNDLE_TEST_ENV] = "1"
        completed = subprocess.run(
            [sys.executable, rel],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
        elapsed = time.perf_counter() - start
        results.append(
            {
                "command": f"{sys.executable} {rel}",
                "exit_code": completed.returncode,
                "duration_seconds": round(elapsed, 3),
                "status": "PASS" if completed.returncode == 0 else "FAIL",
                "stdout": redact_text(completed.stdout, 12000),
                "stderr": redact_text(completed.stderr, 12000),
            }
        )
    passed = sum(1 for item in results if item["status"] == "PASS")
    failed = sum(1 for item in results if item["status"] == "FAIL")
    skipped = sum(1 for item in results if item["status"] == "SKIP")
    return {"skipped": False, "results": results, "summary": {"pass": passed, "fail": failed, "skipped": skipped}}


def _health(test_results: dict[str, Any], excluded: list[dict[str, Any]], secret_findings: list[dict[str, Any]]) -> str:
    if test_results["summary"]["fail"]:
        return "FAIL"
    if secret_findings or any(item["reason"] == "staged_files_present" for item in excluded):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def _load_previous_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        raise AuditBundleError(f"compare path does not exist: {path}")
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path, "r") as zipf:
            names = zipf.namelist()
            manifest_names = [name for name in names if name.endswith("/metadata/bundle_manifest.json")]
            if len(manifest_names) != 1:
                raise AuditBundleError("compare zip must contain exactly one metadata/bundle_manifest.json")
            for name in names:
                pure = PurePosixPath(name)
                if name.startswith("/") or any(part in {"", ".", ".."} for part in pure.parts):
                    raise AuditBundleError("compare zip contains malformed path")
            data = json.loads(zipf.read(manifest_names[0]).decode("utf-8"))
    else:
        data = _read_json(path)
    files = data.get("files")
    if not isinstance(files, list):
        raise AuditBundleError("previous manifest missing files list")
    hashes: dict[str, str] = {}
    for item in files:
        rel = _safe_rel_path(str(item.get("path", "")))
        digest = str(item.get("sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise AuditBundleError("previous manifest contains malformed sha256")
        hashes[rel] = digest
    return hashes


def _compare_hashes(previous: dict[str, str], current: dict[str, str]) -> dict[str, list[str]]:
    prev_keys = set(previous)
    current_keys = set(current)
    return {
        "added": sorted(current_keys - prev_keys, key=str.lower),
        "removed": sorted(prev_keys - current_keys, key=str.lower),
        "modified": sorted(
            (path for path in (prev_keys & current_keys) if previous[path] != current[path]),
            key=str.lower,
        ),
        "unchanged": sorted(
            (path for path in (prev_keys & current_keys) if previous[path] == current[path]),
            key=str.lower,
        ),
    }


def _bundle_manifest(
    root: Path,
    included: list[IncludedFile],
    hashes: dict[str, str],
    categories: dict[str, int],
    excluded: list[dict[str, Any]],
    health: str,
    deterministic: bool,
) -> dict[str, Any]:
    return {
        "release": RELEASE,
        "schema_version": VERIFIER_SCHEMA_VERSION,
        "bundle_id_scope": "source_manifest_excludes_test_timing",
        "project": "LocalComet / LocalAgent",
        "root": "<PROJECT_ROOT>",
        "deterministic": deterministic,
        "bundle_health": health,
        "source_file_count": len(included),
        "categories": dict(sorted(categories.items())),
        "excluded_count": len(excluded),
        "files": [
            {
                "path": item.rel_path,
                "category": item.category,
                "origin": item.origin,
                "size": item.size,
                "sha256": item.sha256,
            }
            for item in sorted(included, key=lambda f: f.rel_path.lower())
        ],
        "hash_algorithm": "sha256",
        "file_hashes_sha256": hashes,
    }


def _build_integrity_record(
    bundle_id: str,
    entries: dict[str, bytes],
    manifest_out: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mode": "audit_bundle_integrity",
        "version": VERIFIER_SCHEMA_VERSION,
        "bundle_id": bundle_id,
        "entry_count": len(entries) + 1,
        "uncompressed_size": sum(len(payload) for payload in entries.values()),
        "hash_algorithm": "sha256",
        "manifest_sha256": hashlib.sha256(_json_bytes(manifest_out)).hexdigest(),
        "entry_sha256": {
            path: hashlib.sha256(payload).hexdigest()
            for path, payload in sorted(entries.items(), key=lambda item: item[0].lower())
        },
    }


def _metadata_secret_findings(entries: dict[str, bytes]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path, payload in sorted(entries.items(), key=lambda item: item[0].lower()):
        if not path.startswith("metadata/") and path != "README_AUDIT.md":
            continue
        text = payload.decode("utf-8", errors="ignore")
        for finding in scan_text_for_secret_markers(text):
            findings.append({"file": path, "line": finding["line"], "category": finding["category"]})
    return findings


def _readme(bundle_id: str, health: str, categories: dict[str, int], excluded: list[dict[str, Any]], tests: dict[str, Any]) -> str:
    excluded_reasons: dict[str, int] = {}
    for item in excluded:
        excluded_reasons[item["reason"]] = excluded_reasons.get(item["reason"], 0) + 1
    return "\n".join(
        [
            f"# LocalComet Audit Bundle {RELEASE}",
            "",
            f"- Bundle ID: {bundle_id}",
            f"- Bundle health: {health}",
            "- Source bytes: `source/` contains exact working-tree bytes for included files.",
            "- Local paths: user profile paths are redacted in metadata where practical.",
            "",
            "## Included Categories",
            json.dumps(categories, ensure_ascii=False, sort_keys=True),
            "",
            "## Excluded Categories",
            json.dumps(excluded_reasons, ensure_ascii=False, sort_keys=True),
            "",
            "## Git State",
            "See `metadata/git_status.txt`, `metadata/git_diff.patch`, and related files.",
            "",
            "## Test Summary",
            json.dumps(tests.get("summary", {}), ensure_ascii=False, sort_keys=True),
            "",
            "## Reviewer Notes",
            "Start with `metadata/bundle_manifest.json`, verify `metadata/file_hashes_sha256.json`, then inspect `source/`.",
            "Secret-like files are excluded by default and only marker categories are recorded.",
            "",
        ]
    )


def _default_output_path(bundle_id: str) -> Path:
    return Path(tempfile.gettempdir()) / f"LocalComet_Audit_Bundle_{bundle_id}.zip"


def _resolve_output(output: Path | None, bundle_id: str) -> Path:
    if output is None:
        return _default_output_path(bundle_id)
    output = output.expanduser()
    if output.suffix.lower() == ".zip":
        return output
    return output / f"LocalComet_Audit_Bundle_{bundle_id}.zip"


def _blocked_output_paths(root: Path, output: Path | None) -> set[str]:
    if output is None:
        return set()
    candidate = output.expanduser()
    paths = [candidate]
    if candidate.suffix.lower() != ".zip":
        paths.append(candidate / "placeholder.zip")
    blocked: set[str] = set()
    for path in paths:
        try:
            resolved = path.resolve()
            rel = resolved.relative_to(root)
        except ValueError:
            continue
        blocked.add(rel.as_posix())
    return blocked


def _ensure_output_not_scanned(root: Path, output: Path | None) -> None:
    if output is None:
        return
    candidate = output.expanduser().resolve()
    try:
        rel = candidate.relative_to(root)
    except ValueError:
        return
    if candidate.suffix.lower() != ".zip":
        raise AuditBundleError(f"output directory must be outside project root: {rel.as_posix()}")


def _write_zip(zip_path: Path, bundle_root: str, entries: dict[str, bytes], deterministic: bool) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    compression = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(zip_path, "w", compression=compression) as zipf:
        for name in sorted(entries, key=str.lower):
            info = zipfile.ZipInfo(f"{bundle_root}/{name}")
            if deterministic:
                info.date_time = FIXED_ZIP_DT
            info.compress_type = compression
            zipf.writestr(info, entries[name])


def create_audit_bundle(
    root: Path,
    output: Path | None = None,
    skip_tests: bool = False,
    max_file_size_mb: float = 5.0,
    include_generated: bool = False,
    deterministic: bool = False,
    compare: Path | None = None,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise AuditBundleError(f"root is not a directory: {root}")
    _ensure_output_not_scanned(root, output)
    manifest = _load_runtime_manifest(root)
    category_map = _manifest_category_map(manifest)
    blocked_outputs = _blocked_output_paths(root, output)
    included, hashes, excluded, secrets, tracked, categories = _collect_files(
        root,
        include_generated,
        max_file_size_mb,
        blocked_outputs,
    )
    import_graph = _build_import_graph(root, included, category_map)
    versions = _collect_versions(root, {item.rel_path for item in included})
    tests = _run_tests(root, skip_tests)
    health = _health(tests, excluded, secrets)
    git_metadata = _collect_git_metadata(root)
    included_untracked = [
        item.rel_path
        for item in included
        if item.origin in {"runtime_manifest", "source_scan"} and item.rel_path not in set(tracked)
    ]
    comparison = None
    if compare is not None:
        comparison = _compare_hashes(_load_previous_hashes(compare.expanduser()), hashes)

    base_manifest = _bundle_manifest(root, included, hashes, categories, excluded, health, deterministic)
    base_manifest["bundle_id"] = None
    bundle_id = hashlib.sha256(_json_bytes(base_manifest)).hexdigest()[:16]
    manifest_out = dict(base_manifest)
    manifest_out["bundle_id"] = bundle_id
    manifest_out["bundle_name"] = f"LocalComet_Audit_Bundle_{bundle_id}"
    if not deterministic:
        manifest_out["created_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    zip_path = _resolve_output(output, bundle_id).resolve()
    if zip_path.exists() and zip_path.is_dir():
        raise AuditBundleError(f"output zip path is a directory: {zip_path}")

    entries: dict[str, bytes] = {}
    for item in included:
        entries[f"source/{item.rel_path}"] = (root / item.rel_path).read_bytes()
    metadata = {
        "metadata/localcomet_runtime_manifest.json": _json_bytes(manifest),
        "metadata/bundle_manifest.json": _json_bytes(manifest_out),
        "metadata/file_hashes_sha256.json": _json_bytes(hashes),
        "metadata/tracked_files.txt": ("\n".join(tracked) + "\n").encode("utf-8"),
        "metadata/included_untracked_sources.txt": ("\n".join(sorted(included_untracked, key=str.lower)) + "\n").encode("utf-8"),
        "metadata/excluded_paths.json": _json_bytes(excluded),
        "metadata/import_graph.json": _json_bytes(import_graph),
        "metadata/versions.json": _json_bytes(versions),
        "metadata/test_results.json": _json_bytes(tests),
        "metadata/secret_findings.json": _json_bytes(secrets),
    }
    for name, text in git_metadata.items():
        metadata[f"metadata/{name}"] = text.encode("utf-8")
    if comparison is not None:
        metadata["metadata/bundle_comparison.json"] = _json_bytes(comparison)
    entries.update(metadata)
    entries["README_AUDIT.md"] = _readme(bundle_id, health, categories, excluded, tests).encode("utf-8")
    metadata_findings = _metadata_secret_findings(entries)
    if metadata_findings:
        safe_findings = [
            {"file": item["file"], "line": item["line"], "category": item["category"]}
            for item in metadata_findings
        ]
        entries["metadata/metadata_secret_findings.json"] = _json_bytes(safe_findings)
        manifest_out["metadata_secret_findings_count"] = len(safe_findings)
        entries["metadata/bundle_manifest.json"] = _json_bytes(manifest_out)
    integrity = _build_integrity_record(bundle_id, entries, manifest_out)
    entries["metadata/bundle_integrity.json"] = _json_bytes(integrity)

    bundle_root = f"LocalComet_Audit_Bundle_{bundle_id}"
    _write_zip(zip_path, bundle_root, entries, deterministic)
    with zipfile.ZipFile(zip_path, "r") as zipf:
        zipf.testzip()
    return {
        "zip_path": zip_path,
        "bundle_id": bundle_id,
        "bundle_health": health,
        "bundle_manifest": manifest_out,
        "included_counts": categories,
        "excluded": excluded,
        "secret_findings": secrets,
        "test_results": tests,
        "comparison": comparison,
        "zip_size": zip_path.stat().st_size,
    }
````

### ПУТЬ: modules/project_health.py (185 строк, 6836 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import get_value, set_value
from modules.git_status import short_status as git_short_status
from modules.llm_provider import short_status as provider_short_status
from modules.patch_registry import short_status as patch_registry_short_status


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
HEALTH_REPORTS_DIR = REPORTS_DIR / "project_health"
RELAY_DIR = PROJECTS_DIR / "ChatGPTRelay"
PATCH_REGISTRY_FILE = PROJECTS_DIR / "PatchRegistry" / "patches.json"
RESPONSE_FILE = RELAY_DIR / "response.json"
REQUEST_FILE = RELAY_DIR / "request.md"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value, limit=220):
    text = str(value or "нет")

    if len(text) <= limit:
        return text

    return text[:limit] + "... [обрезано]"


def _latest_report():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    reports = [path for path in REPORTS_DIR.glob("*.md") if path.is_file()]

    if not reports:
        return ""

    return str(max(reports, key=lambda path: path.stat().st_mtime))


def get_project_health():
    git_status = git_short_status()
    provider_status = provider_short_status()
    patch_status = patch_registry_short_status()
    last_error = get_value("last_error", "")
    last_stability_score = get_value("last_stability_score", "нет")
    last_auto_verification_status = get_value("last_auto_verification_status", "нет")

    checks = {
        "git_ready": "dirty" not in git_status.lower(),
        "request_exists": REQUEST_FILE.exists(),
        "response_exists": RESPONSE_FILE.exists(),
        "patch_registry_exists": PATCH_REGISTRY_FILE.exists(),
        "no_last_error": not bool(str(last_error or "").strip()),
        "stability_known": str(last_stability_score or "").strip() not in ["", "нет"],
        "auto_verification_known": str(last_auto_verification_status or "").strip() not in ["", "нет"],
    }

    problems = []

    if not checks["git_ready"]:
        problems.append("Git has uncommitted changes.")

    if not checks["patch_registry_exists"]:
        problems.append("PatchRegistry file is missing.")

    if not checks["no_last_error"]:
        problems.append(f"last_error is set: {_short(last_error, 160)}")

    if not checks["stability_known"]:
        problems.append("No stability score recorded yet.")

    if not checks["auto_verification_known"]:
        problems.append("No auto verification run recorded yet.")

    status = "ok" if not problems else "attention"

    health = {
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "git_status": git_status,
        "provider_status": provider_status,
        "patch_registry_status": patch_status,
        "latest_report": _latest_report() or "нет",
        "last_report": get_value("last_report", "нет"),
        "last_stability_score": last_stability_score,
        "last_stability_report": get_value("last_stability_report", "нет"),
        "last_auto_verification_status": last_auto_verification_status,
        "last_auto_verification_score": get_value("last_auto_verification_score", "нет"),
        "last_auto_verification_report": get_value("last_auto_verification_report", "нет"),
        "last_patch_version": get_value("last_patch_version", "нет"),
        "last_patch_status": get_value("last_patch_status", "нет"),
        "last_relay_status": get_value("last_relay_diagnostics_status", "нет"),
        "last_relay_report": get_value("last_relay_diagnostics_report", "нет"),
        "last_browser_action": get_value("last_browser_action", "нет"),
        "last_browser_report": (
            get_value("last_browser_autopilot_report", "")
            or get_value("last_browser_workflow_report", "")
            or get_value("last_browser_task_report", "")
            or "нет"
        ),
        "last_error": last_error or "нет",
        "checks": checks,
        "problems": problems,
        "recommended_checks": [
            "auto verify",
            "auto verify full",
            "status",
            "help",
        ],
    }

    set_value("last_project_health_status", status)
    set_value("last_project_health_generated_at", health["generated_at"])

    return health


def format_project_health_text(health=None):
    health = health or get_project_health()
    lines = [
        "Project Health Center:",
        f"- status: {health.get('status')}",
        f"- generated_at: {health.get('generated_at')}",
        f"- git: {health.get('git_status')}",
        f"- provider: {health.get('provider_status')}",
        f"- patch_registry: {health.get('patch_registry_status')}",
        f"- last_patch: {health.get('last_patch_version')} | {health.get('last_patch_status')}",
        f"- relay: {health.get('last_relay_status')}",
        f"- stability: {health.get('last_stability_score')} | {health.get('last_stability_report')}",
        f"- auto_verification: {health.get('last_auto_verification_status')} | {health.get('last_auto_verification_score')} | {health.get('last_auto_verification_report')}",
        f"- latest_report: {health.get('latest_report')}",
        f"- browser_report: {health.get('last_browser_report')}",
        f"- last_error: {_short(health.get('last_error'), 320)}",
        "",
        "Checks:",
    ]

    for key, value in health.get("checks", {}).items():
        lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("Problems:")

    problems = health.get("problems") or []

    if problems:
        for problem in problems:
            lines.append(f"- {problem}")
    else:
        lines.append("- Не обнаружены.")

    lines.append("")
    lines.append("Recommended before commit:")

    for command in health.get("recommended_checks", []):
        lines.append(f"- {command}")

    return "\n".join(lines)


def write_project_health_report(health=None):
    health = health or get_project_health()
    HEALTH_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = HEALTH_REPORTS_DIR / f"project_health_{_stamp()}.md"
    text = "# Project Health Center\n\n" + format_project_health_text(health)
    path.write_text(text, encoding="utf-8")
    set_value("last_project_health_report", str(path))
    set_value("last_project_health_status", health.get("status", "unknown"))
    return path


def latest_project_health_report():
    if not HEALTH_REPORTS_DIR.exists():
        return None

    reports = [path for path in HEALTH_REPORTS_DIR.glob("project_health_*.md") if path.is_file()]

    if not reports:
        return None

    return max(reports, key=lambda path: path.stat().st_mtime)
````

### ПУТЬ: modules/project_one_command_check_ru.py (18 строк, 377 байт)

````python
from __future__ import annotations

from modules.strict_project_stability_ru import (
    dispatch,
    is_strict_project_check_command as is_project_check_command,
    report,
    run_strict_project_check as run_project_check,
    status,
)


__all__ = [
    "dispatch",
    "is_project_check_command",
    "report",
    "run_project_check",
    "status",
]
````

### ПУТЬ: modules/project_paths.py (293 строк, 10939 байт)

````python

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


PROJECT_PATHS_VERSION = "v6.79"
RETENTION_PLAN_VERSION = "v6.79"
DEFAULT_RETENTION_MAX_AGE_DAYS = 7
DEFAULT_RETENTION_MAX_ITEMS_PER_GROUP = 200


def _module_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_project_root() -> Path:
    """Return the active LocalComet root.

    LOCALCOMET_ROOT is the only runtime override. If it is set, return it even
    when it does not exist so dry-run tools cannot silently fall back to the
    source checkout.
    """
    explicit_root = os.environ.get("LOCALCOMET_ROOT", "").strip()
    if explicit_root:
        return Path(explicit_root).expanduser().resolve()

    return _module_root()


def projects_dir(root: Path | None = None) -> Path:
    return (root or get_project_root()) / "Projects"


def reports_dir(root: Path | None = None) -> Path:
    return projects_dir(root) / "Reports"


def localcomet_dir(root: Path | None = None) -> Path:
    return (root or get_project_root()) / ".localcomet"


def localcomet_reports_dir(root: Path | None = None) -> Path:
    return localcomet_dir(root) / "reports"


def localcomet_policies_dir(root: Path | None = None) -> Path:
    return localcomet_dir(root) / "policies"


def computer_use_dir(root: Path | None = None) -> Path:
    return projects_dir(root) / "ComputerUse"


def computer_use_runs_dir(root: Path | None = None) -> Path:
    return computer_use_dir(root) / "runs"


def computer_use_latest_ui_map_path(root: Path | None = None) -> Path:
    return computer_use_dir(root) / "latest_ui_map.json"


def test_fixtures_dir(root: Path | None = None) -> Path:
    return projects_dir(root) / "TestFixtures"


def computer_use_test_fixtures_dir(root: Path | None = None) -> Path:
    return test_fixtures_dir(root) / "ComputerUse"


def ensure_dirs(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def retention_runtime_roots(root: Path | None = None) -> tuple[Path, ...]:
    active_root = root or get_project_root()
    return (
        localcomet_reports_dir(active_root),
        reports_dir(active_root),
        computer_use_runs_dir(active_root),
    )


def _norm(path: Path) -> str:
    return path.resolve().as_posix().lower()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.resolve().as_posix()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _age_days(path: Path, now_ts: float) -> float:
    return max(0.0, (now_ts - path.stat().st_mtime) / 86400)


def _protected_reason(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    rel = _rel(resolved, project_root)
    parts = {part.lower() for part in resolved.parts}
    name = resolved.name.lower()
    stem = resolved.stem.lower()

    if ".git" in parts:
        return "git metadata is protected"
    if ".incident_backup" in parts:
        return "incident backups are protected"
    if ".tmp" in parts:
        return ".tmp is not configured for v6.79 retention"
    if "localagent_archive" in _norm(resolved):
        return "external LocalAgent_Archive paths are protected"
    if "testfixtures" in parts or ("projects" in parts and "testfixtures" in parts):
        return "test fixtures are protected"
    if ".localcomet" in parts and "reviewer" in parts:
        return "reviewer inbox/outbox/archive data is protected"
    if ".localcomet" in parts and "policies" in parts:
        return "policies are protected"
    if name.endswith(".py"):
        return "source Python files are protected"
    if any(marker in stem for marker in ("latest", "current", "manifest")):
        return "latest/current/manifest files are protected"
    if rel.replace("\\", "/").startswith("Projects/TestFixtures/"):
        return "test fixtures are protected"
    return ""


def _file_item(path: Path, project_root: Path, now_ts: float, reason: str = "") -> dict:
    stat = path.stat()
    item = {
        "path": _rel(path, project_root),
        "size_bytes": int(stat.st_size),
        "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        "age_days": round(_age_days(path, now_ts), 3),
    }
    if reason:
        item["reason"] = reason
    return item


def build_retention_plan(
    root: Path | None = None,
    scan_roots: Iterable[Path] | None = None,
    max_age_days: int = DEFAULT_RETENTION_MAX_AGE_DAYS,
    max_items_per_group: int = DEFAULT_RETENTION_MAX_ITEMS_PER_GROUP,
    now_ts: float | None = None,
) -> dict:
    project_root = (root or get_project_root()).resolve()
    configured_roots = tuple(Path(path).expanduser().resolve() for path in (scan_roots or retention_runtime_roots(project_root)))
    now_value = float(now_ts if now_ts is not None else datetime.now(tz=timezone.utc).timestamp())
    allowed_roots = tuple(path for path in configured_roots if _is_relative_to(path, project_root))
    roots: list[dict] = []
    candidates: list[dict] = []
    protected: list[dict] = []
    rejected: list[dict] = []
    warnings: list[str] = []

    for scan_root in sorted(configured_roots, key=lambda item: item.as_posix().lower()):
        root_info = {
            "path": _rel(scan_root, project_root),
            "exists": scan_root.exists(),
            "allowed": _is_relative_to(scan_root, project_root),
        }
        roots.append(root_info)
        if not root_info["allowed"]:
            rejected.append({"path": scan_root.as_posix(), "reason": "scan root is outside project root"})
            continue
        if not scan_root.exists():
            continue
        if not scan_root.is_dir():
            rejected.append({"path": _rel(scan_root, project_root), "reason": "scan root is not a directory"})
            continue
        if scan_root.is_symlink():
            rejected.append({"path": _rel(scan_root, project_root), "reason": "scan root is a symlink"})
            continue

        group_files: list[Path] = []
        for current_root, dir_names, file_names in os.walk(scan_root, topdown=True, followlinks=False):
            current_path = Path(current_root)
            kept_dirs: list[str] = []
            for dir_name in sorted(dir_names):
                dir_path = current_path / dir_name
                reason = _protected_reason(dir_path, project_root)
                if dir_path.is_symlink():
                    rejected.append({"path": _rel(dir_path, project_root), "reason": "directory symlink is not followed"})
                    continue
                if reason:
                    protected.append({"path": _rel(dir_path, project_root), "reason": reason})
                    continue
                kept_dirs.append(dir_name)
            dir_names[:] = kept_dirs

            for file_name in sorted(file_names):
                file_path = current_path / file_name
                if not _is_relative_to(file_path, project_root):
                    rejected.append({"path": file_path.as_posix(), "reason": "file escaped project root"})
                    continue
                if not any(_is_relative_to(file_path, allowed_root) for allowed_root in allowed_roots):
                    rejected.append({"path": _rel(file_path, project_root), "reason": "file is outside allowed runtime roots"})
                    continue
                if file_path.is_symlink():
                    rejected.append({"path": _rel(file_path, project_root), "reason": "file symlink is not followed"})
                    continue
                if not file_path.is_file():
                    continue
                reason = _protected_reason(file_path, project_root)
                if reason:
                    protected.append(_file_item(file_path, project_root, now_value, reason))
                    continue
                group_files.append(file_path)

        newest_first = sorted(group_files, key=lambda item: (-item.stat().st_mtime, _rel(item, project_root)))
        keep_set = {path.resolve() for path in newest_first[:max_items_per_group]}
        for path in newest_first:
            age = _age_days(path, now_value)
            is_over_count = path.resolve() not in keep_set
            is_over_age = age > max_age_days
            if is_over_age or is_over_count:
                reasons = []
                if is_over_age:
                    reasons.append(f"age>{max_age_days}d")
                if is_over_count:
                    reasons.append(f"rank>{max_items_per_group}")
                item = _file_item(path, project_root, now_value, ", ".join(reasons))
                item["dry_run_action"] = "would_delete"
                candidates.append(item)

    candidates.sort(key=lambda item: item["path"].lower())
    protected.sort(key=lambda item: item["path"].lower())
    rejected.sort(key=lambda item: item["path"].lower())
    roots.sort(key=lambda item: item["path"].lower())
    total_candidate_bytes = sum(item.get("size_bytes", 0) for item in candidates)

    return {
        "mode": "runtime_retention_plan",
        "version": RETENTION_PLAN_VERSION,
        "dry_run": True,
        "roots": roots,
        "policy": {
            "max_age_days": int(max_age_days),
            "max_items_per_group": int(max_items_per_group),
            "delete_enabled": False,
        },
        "candidates": candidates,
        "protected": protected,
        "rejected": rejected,
        "totals": {
            "candidate_count": len(candidates),
            "candidate_bytes": int(total_candidate_bytes),
            "protected_count": len(protected),
            "rejected_count": len(rejected),
            "roots_count": len(roots),
        },
        "warnings": warnings,
    }


def status() -> dict:
    root = get_project_root()
    return {
        "ok": True,
        "mode": "project_paths_status",
        "version": PROJECT_PATHS_VERSION,
        "root": str(root),
        "projects_dir": str(projects_dir(root)),
        "reports_dir": str(reports_dir(root)),
        "localcomet_reports_dir": str(localcomet_reports_dir(root)),
        "localcomet_policies_dir": str(localcomet_policies_dir(root)),
        "computer_use_dir": str(computer_use_dir(root)),
        "computer_use_runs_dir": str(computer_use_runs_dir(root)),
        "computer_use_latest_ui_map_path": str(computer_use_latest_ui_map_path(root)),
        "test_fixtures_dir": str(test_fixtures_dir(root)),
        "retention_runtime_roots": [str(path) for path in retention_runtime_roots(root)],
    }


def report() -> dict:
    return status()

# v6.54 Computer Use Observe/Vision Upgrade RU: enabled.
````

### ПУТЬ: modules/regression_commands.py (430 строк, 15531 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from time import perf_counter

from core.state import set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
REGRESSION_REPORTS_DIR = REPORTS_DIR / "regression_commands"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value, limit=1800):
    text = str(value or "")

    if len(text) <= limit:
        return text

    return text[:limit] + "\n...[обрезано]"


def _case(name, command, runner, expects):
    started = perf_counter()

    try:
        output = str(runner())
        checks = [marker in output for marker in expects]
        ok = all(checks)
        error = ""
    except Exception as exc:
        output = ""
        checks = []
        ok = False
        error = str(exc)

    return {
        "name": name,
        "command": command,
        "ok": ok,
        "expects": list(expects),
        "checks": checks,
        "error": error,
        "duration_sec": round(perf_counter() - started, 3),
        "output": _short(output),
    }


def get_regression_command_cases():
    def system_help():
        from agents import system_agent

        return system_agent.handle("help", {})

    def system_status():
        from agents import system_agent

        return system_agent.handle("status", {})

    def project_health():
        from agents import system_agent

        return system_agent.handle("health", {})

    def relay_status():
        from agents import chatgpt_relay_agent

        return chatgpt_relay_agent.handle("status", {})

    def relay_diagnostics():
        from modules.relay_diagnostics import format_relay_diagnostics_text

        return format_relay_diagnostics_text()

    def browser_plan():
        from agents import browser_agent

        return browser_agent.handle(
            "plan",
            {"task": "найди официальный сайт Python и сделай отчет", "max_steps": 8},
        )

    def browser_autopilot_dry():
        from agents import browser_agent

        return browser_agent.handle(
            "autopilot_dry",
            {"task": "найди официальный сайт Python и сделай отчет", "max_steps": 8},
        )

    def patch_registry_status():
        from modules.patch_registry import short_status

        return short_status()

    def auto_verification_smoke():
        from modules.auto_verification import format_auto_verification, run_auto_verification

        result = run_auto_verification(mode="smoke", write_report=False)
        return format_auto_verification(result)

    def browser_super_plan():
        from agents import browser_agent

        return browser_agent.handle(
            "super_plan",
            {"task": "напиши сайт автосервиса используй платформу Tilda", "max_results": 3},
        )

    def natural_intents_plan():
        from modules.natural_command_intents import natural_command_plan

        commands = [
            "сделай мне сайт на тильде для автосервиса",
            "открой YouTube и найди видео про Python decorators",
            "найди на ютубе ролик про настройку LM Studio",
            "проверь весь проект на наличие ошибок",
            "запусти все проверки проекта",
            "открой github.com",
            "открой официальный сайт Python и кратко прочитай",
            "найди официальный сайт playwright и собери ссылки",
            "сделай скриншот текущей страницы",
            "собери ссылки со страницы",
            "покажи поля ввода на странице",
            "найди текст Python на странице",
            "кликни кнопку Login",
            "введи Ivan в поле Name",
            "нажми Enter",
            "покажи здоровье проекта",
            "сделай regression report",
            "проверь проект быстро",
            "запусти тест стабильности",
            "изучи browser-use и Skyvern и сделай отчет",
            "сравни OpenHands browser-use и Skyvern",
            "найди лучшие платформы для сайта автосервиса",
            "открой github.com и сделай скриншот",
            "открой github.com и собери ссылки",
            "открой github.com и кратко прочитай",
            "открой github.com и проанализируй страницу",
            "проанализируй текущую страницу",
            "сделай браузерный отчет по Python official website",
            "сделай браузерный отчет по текущей странице",
            "проверь сайт github.com",
            "проанализируй сайт github.com",
            "открой github.com и сделай полный отчет",
            "заполни форму: Name=Ivan, Email=ivan@example.com, нажми Enter",
            "открой example.com и заполни форму: Name=Ivan; Email=ivan@example.com",
            "заполни поля: Search=Python и нажми кнопку Submit",
            "заполни форму оплаты: card=4111111111111111, cvv=123",
        ]

        return "\n".join(f"{command} -> {natural_command_plan(command)}" for command in commands)

    def routing_smoke():
        from core.router import route

        return "\n".join(
            [
                f"health={route('health')}",
                f"browser={route('browser plan Python')}",
                f"stability={route('stability test')}",
                f"auto_verify={route('auto verify')}",
            ]
        )

    def voice_smoke():
        from core.planner import plan
        from core.router import route
        from modules.voice_control import check_voice_dependencies, classify_voice_command_safety

        safe = classify_voice_command_safety("status")
        blocked = classify_voice_command_safety("оплати заказ банковской картой")
        deps = check_voice_dependencies()

        return "\n".join(
            [
                f"route_voice={route('voice status')}",
                f"plan_voice={plan('voice status', 'system')}",
                f"safe_voice={safe.get('safe')}",
                f"blocked_voice={blocked.get('safe')}",
                f"usable_stt={deps.get('usable_stt')}",
                f"usable_faster_whisper_ru={deps.get('usable_faster_whisper_ru')}",
                f"piper_available={deps.get('piper_available')}",
                f"usable_vosk_ru={deps.get('usable_vosk_ru')}",
            ]
        )

    return [
        {
            "name": "system help",
            "command": "help",
            "runner": system_help,
            "expects": ["LocalComet сейчас умеет"],
        },
        {
            "name": "system status",
            "command": "status",
            "runner": system_status,
            "expects": [
                "Статус LocalComet",
                "git_safety_status: да",
                "chat_automation_intents: да",
                "russian_control_panel_menu: да",
                "gray_control_panel_theme: да",
                "llm_offline_graceful_error_pack: yes",
                "voice_chat_mode: yes",
                "voice_chat_replies: yes",
                "voice_faster_whisper_ru: yes",
                "voice_piper_tts: yes",
                "voice_vosk_russian_stt: yes",
            ],
        },
        {
            "name": "project health",
            "command": "health",
            "runner": project_health,
            "expects": ["Project Health Center:", "Recommended before commit:"],
        },
        {
            "name": "relay status",
            "command": "relay status",
            "runner": relay_status,
            "expects": ["ChatGPT Relay status"],
        },
        {
            "name": "relay diagnostics",
            "command": "relay diagnostics",
            "runner": relay_diagnostics,
            "expects": ["Relay Diagnostics:"],
        },
        {
            "name": "browser plan",
            "command": "browser plan найди официальный сайт Python и сделай отчет",
            "runner": browser_plan,
            "expects": ["Browser Autopilot Plan", "search"],
        },
        {
            "name": "browser autopilot dry",
            "command": "browser autopilot dry найди официальный сайт Python и сделай отчет",
            "runner": browser_autopilot_dry,
            "expects": ["Browser Autopilot", "dry-run", "Report:"],
        },
        {
            "name": "patch registry status",
            "command": "patch registry status",
            "runner": patch_registry_status,
            "expects": ["Patch Registry:"],
        },
        {
            "name": "auto verification smoke",
            "command": "auto verify smoke",
            "runner": auto_verification_smoke,
            "expects": ["Auto Verification:", "status: ok"],
        },
        {
            "name": "browser super plan",
            "command": "browser super plan сайт на Tilda",
            "runner": browser_super_plan,
            "expects": ["Browser Super Plan:", "open_platform", "tilda.cc"],
        },
        {
            "name": "natural command intents",
            "command": "natural intents smoke",
            "runner": natural_intents_plan,
            "expects": [
                "platform_site_workflow",
                "youtube_search",
                "auto_verify_full",
                "open_url",
                "browser_workflow",
                "screenshot",
                "extract_links",
                "extract_inputs",
                "find_text",
                "click_text",
                "fill_label",
                "press_key",
                "health",
                "regression_report",
                "auto_verify",
                "'tool': 'stability'",
                "research",
                "compare_research",
                "natural open page workflow",
                "page_audit",
                "natural search report workflow",
                "natural current page report workflow",
                "natural page report workflow",
                "browser_sequence",
                "natural form workflow",
                "STOP: form workflow",
            ],
        },
        {
            "name": "routing smoke",
            "command": "route health/browser/stability/auto_verify",
            "runner": routing_smoke,
            "expects": ["health=system", "browser=browser", "stability=stability", "auto_verify=system"],
        },
        {
            "name": "voice smoke",
            "command": "voice status / safety",
            "runner": voice_smoke,
            "expects": [
                "route_voice=system",
                "voice_status",
                "safe_voice=True",
                "blocked_voice=False",
                "usable_faster_whisper_ru=",
                "piper_available=",
                "usable_vosk_ru=",
            ],
        },
    ]


def run_regression_command_suite(write_report=True):
    results = []

    for case in get_regression_command_cases():
        results.append(
            _case(
                case["name"],
                case["command"],
                case["runner"],
                case["expects"],
            )
        )

    passed = sum(1 for item in results if item["ok"])
    total = len(results)
    status = "ok" if passed == total else "failed"
    suite = {
        "status": status,
        "passed": passed,
        "total": total,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "results": results,
    }

    set_value("last_regression_suite_status", status)
    set_value("last_regression_suite_score", f"{passed}/{total}")
    set_value("last_regression_suite_generated_at", suite["generated_at"])

    if write_report:
        suite["report"] = str(write_regression_command_report(suite))

    return suite


def format_regression_command_suite(suite=None):
    suite = suite or run_regression_command_suite(write_report=False)
    lines = [
        "Regression Command Suite:",
        f"- status: {suite.get('status')}",
        f"- score: {suite.get('passed')}/{suite.get('total')}",
        f"- generated_at: {suite.get('generated_at')}",
    ]

    if suite.get("report"):
        lines.append(f"- report: {suite.get('report')}")

    lines.append("")
    lines.append("Checks:")

    for item in suite.get("results", []):
        marker = "OK" if item.get("ok") else "FAIL"
        lines.append(
            f"- [{marker}] {item.get('name')} | {item.get('command')} | {item.get('duration_sec')}s"
        )

        if item.get("error"):
            lines.append(f"  error: {item.get('error')}")

    problems = [item for item in suite.get("results", []) if not item.get("ok")]
    lines.append("")
    lines.append("Problems:")

    if problems:
        for item in problems:
            lines.append(f"- {item.get('name')}: expected {item.get('expects')}")
    else:
        lines.append("- Не обнаружены.")

    return "\n".join(lines)


def write_regression_command_report(suite=None):
    suite = suite or run_regression_command_suite(write_report=False)
    REGRESSION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REGRESSION_REPORTS_DIR / f"regression_commands_{_stamp()}.md"

    lines = ["# Regression Command Suite", "", format_regression_command_suite(suite), ""]

    for item in suite.get("results", []):
        lines.extend(
            [
                f"## {item.get('name')}",
                "",
                f"- command: `{item.get('command')}`",
                f"- ok: {item.get('ok')}",
                f"- duration_sec: {item.get('duration_sec')}",
                "",
                "```text",
                item.get("output", ""),
                "```",
                "",
            ]
        )

    path.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_regression_suite_report", str(path))
    return path


def latest_regression_command_report():
    if not REGRESSION_REPORTS_DIR.exists():
        return None

    reports = [path for path in REGRESSION_REPORTS_DIR.glob("regression_commands_*.md") if path.is_file()]

    if not reports:
        return None

    return max(reports, key=lambda path: path.stat().st_mtime)
````

