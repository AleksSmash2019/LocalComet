"""Model-agnostic, read-only workspace inventory skill."""
from __future__ import annotations

import json
import sys
from pathlib import Path

MAX_ENTRIES = 200
MAX_DEPTH = 3


def _relative_entries(root: Path) -> dict[str, object]:
    if not root.exists():
        return {"ok": False, "error": "workspace does not exist"}
    if not root.is_dir():
        return {"ok": False, "error": "workspace is not a directory"}
    entries: list[dict[str, object]] = []
    try:
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
            relative = path.relative_to(root)
            if len(relative.parts) > MAX_DEPTH:
                continue
            if any(part in {".git", "node_modules", "target", "__pycache__"} for part in relative.parts):
                continue
            entries.append({"path": relative.as_posix(), "is_dir": path.is_dir()})
            if len(entries) >= MAX_ENTRIES:
                break
    except OSError as exc:
        return {"ok": False, "error": f"workspace scan failed: {exc.__class__.__name__}"}
    return {
        "ok": True,
        "root": str(root),
        "entries": entries,
        "truncated": len(entries) >= MAX_ENTRIES,
    }


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
    result = _relative_entries(Path(path_value).resolve())
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
