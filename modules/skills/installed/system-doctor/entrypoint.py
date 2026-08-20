import json
import subprocess
import sys

TIMEOUT_SECONDS = 30


def run(args: list[str]) -> dict:
    try:
        proc = subprocess.run(args, shell=False, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except FileNotFoundError:
        return {"command": args, "returncode": 127, "stdout": "", "stderr": "command unavailable"}
    except subprocess.TimeoutExpired:
        return {"command": args, "returncode": 124, "stdout": "", "stderr": "command timed out"}
    return {"command": args, "returncode": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:]}


mode = sys.argv[1] if len(sys.argv) > 1 else "help"
if mode == "health":
    out = {"python": run([sys.executable, "--version"]), "node": run(["node", "--version"]), "cargo": run(["cargo", "--version"])}
elif mode == "ports":
    out = run(["netstat", "-ano"])
    if out["returncode"] == 0:
        lines = [line for line in out["stdout"].splitlines() if ":1420" in line]
        out["stdout"] = "\n".join(lines) if lines else "PORT_1420_NOT_FOUND"
elif mode == "logs":
    out = run([sys.executable, "-m", "modules.maintenance"])
else:
    out = {"help": ["health", "ports", "logs"]}
print(json.dumps(out, ensure_ascii=False))

