from __future__ import annotations

import json
from pathlib import Path

import uiautomation as auto
import win32gui

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Projects" / "Reports" / "computer_use_real_actions" / "hidden_ui_run" / "tauri_uia_probe.json"


def main() -> int:
    hwnd = win32gui.FindWindow(None, "LocalComet")
    if not hwnd:
        raise RuntimeError("LocalComet top-level window not found")
    window = auto.ControlFromHandle(hwnd)
    controls: list[dict] = []
    queue = [(window, 0)]
    while queue and len(controls) < 20_000:
        control, depth = queue.pop(0)
        try:
            rect = control.BoundingRectangle
            row = {
                "depth": depth,
                "name": str(control.Name or "")[:240],
                "control_type": str(control.ControlTypeName or ""),
                "automation_id": str(control.AutomationId or "")[:120],
                "enabled": bool(control.IsEnabled),
                "rect": [rect.left, rect.top, rect.right, rect.bottom],
            }
            controls.append(row)
            if depth < 12:
                queue.extend((child, depth + 1) for child in control.GetChildren())
        except Exception:
            continue
    output = {"window": {"name": window.Name, "control_type": window.ControlTypeName}, "control_count": len(controls), "controls": controls}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    named = [row for row in controls if row["name"]]
    print(json.dumps({"control_count": len(controls), "named_controls": named[:160]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
