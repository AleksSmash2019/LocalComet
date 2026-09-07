#!/usr/bin/env python3
"""Extract the inline ModelFit bundle from static/modelfit.html into plain .js assets.

The Svelte app executes the ModelFit React bundle inside the MAIN window
document (WebviewWindow and iframe delivery are both broken/unwanted — see
ModelfitWorkspace). The main window's CSP is script-src 'self': inline
scripts injected into the main document never run. Serving the bundle as
real .js files keeps it same-origin ('self') so the browser executes it.

Outputs (into static/modelfit-generated/):
  boot.js       — the small classic inline scripts (error banner, font shim),
                  concatenated, minus the parent-__TAURI__ bridge block
  bundle.module.js — the big type="module" script verbatim
  bundle.css    — the single <style> block verbatim
The static/modelfit.html file stays as this script's input; nothing serves
it at runtime anymore.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "desktop" / "localcomet-desktop" / "static" / "modelfit.html"
OUT = ROOT / "desktop" / "localcomet-desktop" / "static" / "modelfit-generated"


def main() -> int:
    html = HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script([^>]*)>(.*?)</script>", html, re.S)
    classic: list[str] = []
    module_parts: list[str] = []
    for attrs, body in scripts:
        if "module" in attrs:
            module_parts.append(body)
        else:
            # Drop the iframe-era parent bridge: in the main document
            # window.parent === window and __TAURI__ already exists.
            cleaned = body.replace(
                """if (window.parent !== window && window.parent.__TAURI__) {
  window.__TAURI__ = window.parent.__TAURI__;
  window.__TAURI_INTERNALS__ = window.parent.__TAURI_INTERNALS__;
}""",
                "",
            )
            classic.append(cleaned)
    if not module_parts:
        print("FAIL: no module script found in modelfit.html", file=sys.stderr)
        return 1
    styles = re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "boot.js").write_text("\n;\n".join(classic), encoding="utf-8", newline="\n")
    (OUT / "bundle.module.js").write_text(
        "\n;\n".join(module_parts), encoding="utf-8", newline="\n"
    )
    (OUT / "bundle.css").write_text(
        "\n".join(styles), encoding="utf-8", newline="\n"
    )
    print(
        f"OK: boot.js={len(classic)} block(s), bundle.module.js="
        f"{sum(len(p) for p in module_parts)} bytes, bundle.css={sum(len(s) for s in styles)} bytes"
        f" -> {OUT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
