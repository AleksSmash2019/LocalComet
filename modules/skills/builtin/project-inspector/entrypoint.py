"""Model-agnostic project map skill."""
from __future__ import annotations

import json
import sys
from pathlib import Path

MAX_FILES = 120
EXTENSIONS = {".py", ".ts", ".tsx", ".svelte", ".rs", ".toml", ".json", ".md", ".yaml", ".yml"}
SKIP_DIRS = {".git", "node_modules", "target", "__pycache__", ".venv", "venv"}


def main() -> int:
    raw = sys.argv[1] if len(sys.argv) > 1 else ""
    path_value = "."
    if raw:
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict):
            path_value = str(decoded.get("path", "."))
        elif isinstance(decoded, str):
            path_value = decoded
        else:
            path_value = raw
    root = Path(path_value).resolve()
    if not root.is_dir():
        print(json.dumps({"ok": False, "error": "project root is not a directory"}, separators=(",", ":")))
        return 1
    files: list[str] = []
    try:
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                continue
            files.append(path.relative_to(root).as_posix())
            if len(files) >= MAX_FILES:
                break
    except OSError as exc:
        print(json.dumps({"ok": False, "error": f"project scan failed: {exc.__class__.__name__}"}, separators=(",", ":")))
        return 1
    print(json.dumps({"ok": True, "root": str(root), "files": files, "truncated": len(files) >= MAX_FILES}, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
