#!/usr/bin/env python
"""Regenerate localcomet_runtime_manifest.json from the current source tree.

The manifest lists all Python source files categorized by role.  It must
be regenerated whenever .py files are added to or removed from the project.

Determinism check:
    python scripts/generate_runtime_manifest.py
    git diff --exit-code localcomet_runtime_manifest.json

If the diff is empty the manifest is up to date.  A non-empty diff means
the tree changed since the last committed manifest.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generate() -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {
        "entrypoints": [],
        "runtime": [],
        "lazy_runtime": [],
        "tests": [],
        "tools": [],
    }

    def rel(f: Path) -> str:
        return f.relative_to(ROOT).as_posix()

    entrypoints_set: set[str] = set()
    for name in ("app.py", "LocalComet_Control_Panel.py", "config.py", "next/app_v5.py", "GenerateCapabilityMap.py"):
        if (ROOT / name).is_file():
            categories["entrypoints"].append(name)
            entrypoints_set.add(name)

    for directory in ("core", "agents", "next"):
        dp = ROOT / directory
        if dp.is_dir():
            for f in dp.rglob("*.py"):
                r = rel(f)
                if "__pycache__" not in r and r not in entrypoints_set:
                    categories["runtime"].append(r)

    dp = ROOT / "modules"
    if dp.is_dir():
        for f in dp.rglob("*.py"):
            r = rel(f)
            if "__pycache__" not in r:
                categories["lazy_runtime"].append(r)

    dp = ROOT / "tools"
    if dp.is_dir():
        for f in dp.glob("test_*.py"):
            categories["tests"].append(rel(f))
    for f in ROOT.glob("test_*.py"):
        categories["tests"].append(rel(f))

    for directory in ("tools", "scripts"):
        dp = ROOT / directory
        if dp.is_dir():
            for f in dp.glob("*.py"):
                r = rel(f)
                if not f.name.startswith("test_") and "__pycache__" not in r:
                    categories["tools"].append(r)

    for key in categories:
        categories[key] = sorted(categories[key], key=str.casefold)

    return categories


def main() -> None:
    manifest = generate()
    out = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    target = ROOT / "localcomet_runtime_manifest.json"
    target.write_text(out, encoding="utf-8", newline="\n")
    total = sum(len(v) for v in manifest.values())
    print(f"Wrote {target.name}: {total} entries")
    for key, values in manifest.items():
        print(f"  {key}: {len(values)}")


if __name__ == "__main__":
    main()
