from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import uiautomation as auto
import win32gui

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "Projects" / "Reports" / "computer_use_real_actions" / "hidden_ui_run"


def window() -> Any:
    hwnd = win32gui.FindWindow(None, "LocalComet")
    if not hwnd:
        raise RuntimeError("LocalComet window not found")
    return auto.ControlFromHandle(hwnd)


def walk(root: Any, max_nodes: int = 20_000) -> list[Any]:
    found: list[Any] = []
    queue = [root]
    while queue and len(found) < max_nodes:
        control = queue.pop(0)
        found.append(control)
        try:
            queue.extend(control.GetChildren())
        except Exception:
            pass
    return found


def find_control(name: str, control_type: str | None = None) -> Any | None:
    for control in walk(window()):
        try:
            if str(control.Name or "").strip() != name:
                continue
            if control_type and str(control.ControlTypeName or "") != control_type:
                continue
            return control
        except Exception:
            continue
    return None


def snapshot(label: str) -> dict[str, Any]:
    controls: list[dict[str, Any]] = []
    for control in walk(window()):
        try:
            rect = control.BoundingRectangle
            controls.append({
                "name": str(control.Name or "")[:240],
                "control_type": str(control.ControlTypeName or ""),
                "automation_id": str(control.AutomationId or "")[:120],
                "enabled": bool(control.IsEnabled),
                "rect": [rect.left, rect.top, rect.right, rect.bottom],
            })
        except Exception:
            continue
    output = {"label": label, "window_visible": bool(win32gui.IsWindowVisible(win32gui.FindWindow(None, "LocalComet"))), "controls": controls}
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / f"uia_{label}.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def click(name: str, occurrence: int = 0) -> dict[str, Any]:
    matches: list[Any] = []
    for control in walk(window()):
        try:
            if str(control.Name or "").strip() == name and str(control.ControlTypeName or "") in {"ButtonControl", "TextControl"}:
                matches.append(control)
        except Exception:
            continue
    if occurrence >= len(matches):
        return {"ok": False, "reason": "not_found", "name": name, "count": len(matches)}
    control = matches[occurrence]
    try:
        if not control.IsEnabled:
            return {"ok": False, "reason": "disabled", "name": name, "count": len(matches)}
        rect = control.BoundingRectangle
        if str(control.ControlTypeName or "") == "ButtonControl":
            try:
                control.Click()
            except Exception:
                control.Invoke()
        else:
            try:
                control.Click()
            except Exception:
                rect_center = control.BoundingRectangle
                auto.Click((rect_center.left + rect_center.right) // 2, (rect_center.top + rect_center.bottom) // 2)
        return {"ok": True, "name": name, "count": len(matches), "rect": [rect.left, rect.top, rect.right, rect.bottom]}
    except Exception as exc:
        return {"ok": False, "reason": "uia_action_error", "name": name, "error": type(exc).__name__}


def type_text(text: str) -> dict[str, Any]:
    edits: list[Any] = []
    for control in walk(window()):
        try:
            if str(control.ControlTypeName or "") == "EditControl":
                edits.append(control)
        except Exception:
            continue
    if not edits:
        return {"ok": False, "reason": "edit_not_found"}
    edit = edits[-1]
    if not edit.IsEnabled:
        return {"ok": False, "reason": "edit_disabled", "name": str(edit.Name or "")}
    edit.Click()
    auto.SendKeys(text, interval=0)
    return {"ok": True, "text_length": len(text), "edit_name": str(edit.Name or "")}


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: tauri_uia_user_actions.py snapshot LABEL | click NAME [OCCURRENCE] | point X Y | type TEXT | hotkey CTRL_COMMA")
    command = sys.argv[1]
    if command == "snapshot":
        label = sys.argv[2] if len(sys.argv) > 2 else "current"
        result = snapshot(label)
    elif command == "click":
        name = sys.argv[2]
        occurrence = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        result = click(name, occurrence)
    elif command == "type":
        result = type_text(sys.argv[2])
    elif command == "point" and len(sys.argv) > 3:
        root = window()
        root.SetFocus()
        auto.Click(int(sys.argv[2]), int(sys.argv[3]))
        result = {"ok": True, "point": [int(sys.argv[2]), int(sys.argv[3])]}
    elif command == "hotkey" and len(sys.argv) > 2 and sys.argv[2] == "CTRL_COMMA":
        root = window()
        root.SetFocus()
        auto.SendKeys("{Ctrl},")
        result = {"ok": True, "hotkey": "CTRL_COMMA"}
    else:
        raise SystemExit("unsupported command: {command}")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
