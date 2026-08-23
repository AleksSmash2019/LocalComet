"""One-off steady-state UIA probe for the isolated LocalComet app.

Spawned ON the app's isolated desktop (lpDesktop) so UIA sees only that
desktop. Clicks the 'Настроить локальный AI' CTA at steady state, then dumps
the resulting control names to JSON — distinguishing a startup race in the
smoke harness from a non-invokable control.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_isolated_hidden_desktop_cu import (  # noqa: E402
    click_named,
    controls_named,
    named_status,
    uia_walk,
    uia_window,
)

REPORT = ROOT / "Projects" / "Reports" / "computer_use_real_actions" / "isolated_hidden_desktop"


def main() -> int:
    import uiautomation as auto

    out: dict[str, object] = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "desktop": os.environ.get("LC_PROBE_DESKTOP", ""),
    }
    root = uia_window(auto)
    if root is None:
        out["error"] = "LocalComet window not found on this desktop"
        REPORT.joinpath("probe_drawer.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1
    before = named_status(root)
    cta = controls_named(root, "Настроить локальный AI")
    out["cta_found"] = len(cta)
    out["cta_enabled"] = [bool(getattr(c, "IsEnabled", False)) for c in cta]
    out["cta_types"] = [str(getattr(c, "ControlTypeName", "")) for c in cta]
    clicked = click_named(root, ("Настроить локальный AI",))
    out["clicked"] = clicked
    time.sleep(6)
    root = uia_window(auto)
    after = named_status(root) if root is not None else []
    out["names_after_click"] = after
    out["drawer_open"] = any(
        name in after for name in ("Запустить выбранную", "Подобрать модель", "Модели HF")
    ) and any("Запустить выбранную" == name for name in after)
    # Also try the drawer start button directly if present.
    started = click_named(root, ("Запустить выбранную",)) if root is not None else None
    out["clicked_start"] = started
    REPORT.joinpath("probe_drawer.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("cta_found", "clicked", "drawer_open", "clicked_start")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
