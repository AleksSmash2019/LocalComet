from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import uiautomation as auto
import win32gui

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "Projects" / "Reports" / "computer_use_real_actions" / "hidden_ui_run"
REPORT_PATH = REPORT_DIR / "real_tauri_ui_1000_attempts.jsonl"
SUMMARY_PATH = REPORT_DIR / "real_tauri_ui_1000_summary.json"

PROMPTS = (
    "Открой Блокнот и напечатай: LocalComet smoke test",
    "Открой калькулятор и введи 2 плюс 2",
    "Сделай снимок экрана текущего рабочего стола",
    "Открой Блокнот",
    "Переключись на окно Блокнота",
    "Набери в текущем приложении короткий тестовый текст",
    "Открой меню Пуск",
    "Закрой Блокнот, если он открыт",
    "Сделай клик в центре текущего окна",
    "Проверь, какое окно сейчас активно",
    "Открой Проводник",
    "Открой папку Документы",
    "Вернись к предыдущему окну",
    "Нажми клавишу Escape",
    "Нажми клавишу Enter",
    "Сделай скриншот текущего состояния",
    "Открой новое окно Блокнота",
    "Напечатай в Блокноте слово проверка",
    "Закрой текущее окно",
    "Покажи текущее состояние экрана",
)


def get_window() -> Any:
    hwnd = win32gui.FindWindow(None, "LocalComet")
    if not hwnd:
        raise RuntimeError("LocalComet window not found")
    return auto.ControlFromHandle(hwnd)


def walk(root: Any, max_nodes: int = 20_000) -> list[Any]:
    output: list[Any] = []
    queue = [root]
    while queue and len(output) < max_nodes:
        control = queue.pop(0)
        output.append(control)
        try:
            queue.extend(control.GetChildren())
        except Exception:
            continue
    return output


def named_controls(root: Any, control_type: str | None = None) -> list[Any]:
    matches: list[Any] = []
    for control in walk(root):
        try:
            if control_type and str(control.ControlTypeName or "") != control_type:
                continue
            matches.append(control)
        except Exception:
            continue
    return matches


def find_edit(root: Any) -> Any | None:
    candidates = named_controls(root, "EditControl")
    return candidates[-1] if candidates else None


def find_button(root: Any, name: str) -> Any | None:
    for control in named_controls(root, "ButtonControl"):
        try:
            if str(control.Name or "").strip() == name:
                return control
        except Exception:
            continue
    return None


def status_names(root: Any) -> list[str]:
    names: list[str] = []
    for control in walk(root):
        try:
            name = str(control.Name or "").strip()
            if name and name not in names:
                names.append(name)
        except Exception:
            continue
    return names


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    counts = {"attempted": 0, "accepted": 0, "blocked_model_not_ready": 0, "ui_errors": 0}
    started = datetime.now(timezone.utc).isoformat()
    with REPORT_PATH.open("w", encoding="utf-8") as report:
        for index in range(1, 1001):
            prompt = f"{PROMPTS[(index - 1) % len(PROMPTS)]} (сценарий {index:04d})"
            row: dict[str, Any] = {
                "case_id": f"REAL-CU-{index:04d}",
                "prompt": prompt,
                "interaction": ["focus_window", "open_chat", "inspect_composer", "attempt_input", "inspect_send"],
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            counts["attempted"] += 1
            try:
                root = get_window()
                root.SetFocus()
                chat = find_button(root, "Чат")
                if chat is not None and chat.IsEnabled:
                    try:
                        chat.Click()
                    except Exception:
                        chat.Invoke()
                time.sleep(0.005)
                root = get_window()
                edit = find_edit(root)
                send = find_button(root, "Отправить")
                composer_enabled = bool(edit is not None and edit.IsEnabled)
                send_enabled = bool(send is not None and send.IsEnabled)
                row["composer_enabled"] = composer_enabled
                row["send_enabled"] = send_enabled
                if not composer_enabled or not send_enabled:
                    counts["blocked_model_not_ready"] += 1
                    row["outcome"] = "BLOCKED_MODEL_NOT_READY"
                    row["evidence"] = "The real Tauri composer or send control is disabled; no prompt was submitted."
                else:
                    edit.Click()
                    auto.SendKeys(prompt, interval=0)
                    time.sleep(0.01)
                    send = find_button(get_window(), "Отправить")
                    if send is None or not send.IsEnabled:
                        counts["ui_errors"] += 1
                        row["outcome"] = "UI_ERROR_SEND_DISABLED_AFTER_INPUT"
                    else:
                        send.Click()
                        counts["accepted"] += 1
                        row["outcome"] = "SUBMITTED_FOR_REAL_BACKEND_OBSERVATION"
                        row["evidence"] = "User prompt was typed into the real Tauri composer and submitted via the real send control."
            except Exception as exc:
                counts["ui_errors"] += 1
                row["outcome"] = "UI_ERROR"
                row["error_type"] = type(exc).__name__
                row["error"] = str(exc)[:240]
            report.write(json.dumps(row, ensure_ascii=False) + "\n")
            if index % 50 == 0:
                report.flush()
                print(json.dumps({"progress": index, **counts}, ensure_ascii=False))
    summary = {
        "campaign": "real_tauri_user_style_computer_use_attempts",
        "requested_cases": 1000,
        "attempted": counts["attempted"],
        "unique_case_ids": counts["attempted"],
        "accepted_for_backend": counts["accepted"],
        "blocked_model_not_ready": counts["blocked_model_not_ready"],
        "ui_errors": counts["ui_errors"],
        "completed_computer_use_executions": 0,
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "interpretation": "These are real Tauri UI attempts. BLOCKED_MODEL_NOT_READY is not a PASS and is not counted as a completed Computer Use execution.",
        "report_jsonl": str(REPORT_PATH),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if counts["attempted"] == 1000 and counts["ui_errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
