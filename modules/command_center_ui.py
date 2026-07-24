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
