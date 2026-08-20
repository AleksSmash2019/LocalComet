import json
import sys
from pathlib import Path

MAX_FILES = 20
MAX_LINES = 200
ERROR_MARKERS = ("error", "exception", "traceback")


def log_files() -> list[Path]:
    return sorted((path for path in Path.cwd().glob("*.log") if path.is_file()), key=lambda path: path.stat().st_mtime, reverse=True)[:MAX_FILES]


def tail(path: Path, limit: int) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except OSError:
        return []


mode = sys.argv[1] if len(sys.argv) > 1 else "help"
if mode in {"errors", "trace"}:
    files = []
    for path in log_files():
        lines = tail(path, MAX_LINES)
        if mode == "errors":
            lines = [line for line in lines if any(marker in line.lower() for marker in ERROR_MARKERS)]
        if lines:
            files.append({"name": path.name, "lines": lines})
    out = {"files": files, "status": "ok" if files else "NO_LOGS"}
else:
    out = {"help": ["errors", "trace"]}
print(json.dumps(out, ensure_ascii=False))
