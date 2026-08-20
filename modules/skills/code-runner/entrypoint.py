import json
import subprocess
import sys

TIMEOUT_SECONDS = 30
ALLOWED_COMMANDS = {
    ("git", "status", "--short"): ["git", "status", "--short"],
    ("git", "diff", "--stat"): ["git", "diff", "--stat"],
    ("git", "log", "--oneline", "-20"): ["git", "log", "--oneline", "-20"],
    ("python", "-m", "pytest", "-q"): [sys.executable, "-m", "pytest", "-q"],
}


def run(args: list[str]) -> dict:
    try:
        proc = subprocess.run(args, shell=False, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except FileNotFoundError:
        return {"command": args, "returncode": 127, "stdout": "", "stderr": "command unavailable"}
    except subprocess.TimeoutExpired:
        return {"command": args, "returncode": 124, "stdout": "", "stderr": "command timed out"}
    return {"command": args, "returncode": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:]}


mode = sys.argv[1] if len(sys.argv) > 1 else "status"
if mode == "status":
    out = run(["git", "status", "--short"])
elif mode == "test":
    out = run([sys.executable, "-m", "pytest", "-q"])
elif mode == "shell":
    requested = tuple(sys.argv[2:])
    args = ALLOWED_COMMANDS.get(requested)
    out = run(args) if args is not None else {"error": "arbitrary shell commands are disabled", "allowed_commands": [list(command) for command in ALLOWED_COMMANDS]}
else:
    out = {"error": f"unknown mode: {mode}"}
print(json.dumps(out, ensure_ascii=False))
