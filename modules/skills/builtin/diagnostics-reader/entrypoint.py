"""Bounded, read-only log diagnostics skill."""
from __future__ import annotations

import json
import sys
from pathlib import Path

MAX_BYTES = 256_000
MAX_LINES = 120
ERROR_MARKERS = ("error", "exception", "traceback", "failed", "timeout", "ошиб")


def main() -> int:
    raw = sys.argv[1] if len(sys.argv) > 1 else ""
    path_value = ""
    if raw:
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict):
            path_value = str(decoded.get("path", ""))
        elif isinstance(decoded, str):
            path_value = decoded
        else:
            path_value = raw
    path = Path(path_value).resolve()
    if not path.is_file():
        print(json.dumps({"ok": False, "error": "log file does not exist"}, separators=(",", ":")))
        return 1
    try:
        if path.stat().st_size > MAX_BYTES:
            print(json.dumps({"ok": False, "error": "log file exceeds bounded read limit"}, separators=(",", ":")))
            return 1
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        print(json.dumps({"ok": False, "error": f"log read failed: {exc.__class__.__name__}"}, separators=(",", ":")))
        return 1
    tail = lines[-MAX_LINES:]
    errors = [line for line in tail if any(marker in line.casefold() for marker in ERROR_MARKERS)][-40:]
    print(json.dumps({"ok": True, "path": str(path), "line_count": len(lines), "errors": errors, "tail": tail, "truncated": len(lines) > MAX_LINES}, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
