#!/usr/bin/env python
"""i18n key gate for LocalComet desktop.

Every statically referenced translation key ($t('x.y') / t('x.y') in .svelte
and .ts files) must exist in both ru.ts and en.ts, otherwise the UI silently
falls back to rendering the raw key (e.g. the historical 'item.new_chat' hole).
Dynamic references ($t('item.' + raw)) are not resolvable by static analysis
and are intentionally skipped.
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND_ROOT = REPO_ROOT / "desktop" / "localcomet-desktop" / "src"
I18N_DIR = REPO_ROOT / "desktop" / "localcomet-desktop" / "src" / "lib" / "i18n"

KEY_RE = re.compile(r"(?<!\w)\$?t\(\s*'([A-Za-z0-9_.-]+)'\s*\)")
KEY_INSIDE_RE = re.compile(r"[\"']([A-Za-z0-9_.-]+)[\"']")


def collect_used_keys() -> list[str]:
    keys: set[str] = set()
    for path in FRONTEND_ROOT.rglob("*"):
        if path.suffix not in {".svelte", ".ts"}:
            continue
        text = path.read_text(encoding="utf-8")
        for match in KEY_RE.finditer(text):
            keys.add(match.group(1))
    return sorted(keys)


def collect_locale_keys(path: pathlib.Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    keys: set[str] = set()
    in_entry = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("export const") or stripped.startswith("const") or stripped.startswith("}"):
            in_entry = False
        if in_entry and stripped.endswith(","):
            match = re.match(r"^(['\"])([A-Za-z0-9_.-]+)\1:", stripped)
            if match:
                keys.add(match.group(2))
        if stripped.startswith("export const") or re.match(r"^[a-zA-Z0-9_]+:\s*\{", stripped):
            in_entry = True
    return keys


def main() -> int:
    if not I18N_DIR.exists():
        print(f"FAIL: i18n dir missing: {I18N_DIR}")
        return 2
    ru = collect_locale_keys(I18N_DIR / "ru.ts")
    en = collect_locale_keys(I18N_DIR / "en.ts")
    if not ru or not en:
        print("FAIL: parse produced empty locale key sets")
        return 2

    used = collect_used_keys()
    missing_ru = [key for key in used if key not in ru]
    missing_en = [key for key in used if key not in en]

    if missing_ru or missing_en:
        if missing_ru:
            print(f"FAIL: used keys missing from ru.ts: {missing_ru}")
        if missing_en:
            print(f"FAIL: used keys missing from en.ts: {missing_en}")
        return 1
    print(f"OK: {len(used)} used i18n key(s) present in ru.ts ({len(ru)}) and en.ts ({len(en)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())