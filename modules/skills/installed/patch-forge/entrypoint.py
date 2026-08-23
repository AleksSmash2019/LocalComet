import json
import subprocess
import sys
from collections.abc import Sequence


def run(args: Sequence[str]) -> dict[str, object]:
    proc = subprocess.run(
        list(args),
        shell=False,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return {
        "code": proc.returncode,
        "stdout": proc.stdout[-2000:],
        "stderr": proc.stderr[-2000:],
    }


mode = sys.argv[1] if len(sys.argv) > 1 else "help"
if mode == "diff":
    target = sys.argv[2] if len(sys.argv) > 2 else "."
    out = run(["git", "diff", "--", target])
elif mode == "status":
    out = run(["git", "status", "--short"])
elif mode == "validate":
    patch_path = sys.argv[2] if len(sys.argv) > 2 else "patch.diff"
    out = run(["git", "apply", "--check", patch_path])
else:
    out = {"help": ["diff [path]", "status", "validate [patch_path]"]}

print(json.dumps(out, ensure_ascii=False))