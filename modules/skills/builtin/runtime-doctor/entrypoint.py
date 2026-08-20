"""Fast, fixed-command runtime health skill."""
from __future__ import annotations

import json
import subprocess
import sys

COMMANDS = {
    "python": [sys.executable, "--version"],
    "node": ["node", "--version"],
    "git": ["git", "--version"],
}
MAX_OUTPUT = 2000


def run(name: str) -> dict[str, object]:
    command = COMMANDS[name]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, shell=False, timeout=5, check=False)
    except (FileNotFoundError, OSError) as exc:
        return {"name": name, "available": False, "error": exc.__class__.__name__}
    except subprocess.TimeoutExpired:
        return {"name": name, "available": False, "error": "timeout"}
    return {
        "name": name,
        "available": completed.returncode == 0,
        "returncode": completed.returncode,
        "output": ((completed.stdout or "") + (completed.stderr or ""))[:MAX_OUTPUT].strip(),
    }


def main() -> int:
    requested: list[str]
    raw = sys.argv[1] if len(sys.argv) > 1 else ""
    if raw:
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict):
            value = decoded.get("checks", sorted(COMMANDS))
            requested = [str(item) for item in value] if isinstance(value, list) else sorted(COMMANDS)
        elif isinstance(decoded, list):
            requested = [str(item) for item in decoded]
        else:
            requested = sys.argv[1:]
    else:
        requested = sorted(COMMANDS)
    unknown = sorted(set(requested) - set(COMMANDS))
    if unknown:
        print(json.dumps({"ok": False, "error": "unsupported check", "allowed": sorted(COMMANDS)}, separators=(",", ":")))
        return 1
    checks = [run(name) for name in requested]
    print(json.dumps({"ok": all(item["available"] for item in checks), "checks": checks}, ensure_ascii=False, separators=(",", ":")))
    return 0 if all(item["available"] for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
