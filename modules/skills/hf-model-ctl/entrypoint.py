import json
import subprocess
import sys
from pathlib import Path

TIMEOUT_SECONDS = 30
MAX_QUERY_LENGTH = 200


def run(args: list[str]) -> dict:
    try:
        proc = subprocess.run(args, shell=False, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except FileNotFoundError:
        return {"command": args, "returncode": 127, "stdout": "", "stderr": "HF_SEARCH_UNAVAILABLE"}
    except subprocess.TimeoutExpired:
        return {"command": args, "returncode": 124, "stdout": "", "stderr": "command timed out"}
    return {"command": args, "returncode": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:]}


mode = sys.argv[1] if len(sys.argv) > 1 else "help"
if mode == "search":
    query = " ".join(sys.argv[2:]).strip() or "local model"
    out = {"error": "query is too long"} if len(query) > MAX_QUERY_LENGTH else run(["hf", "search", query, "--limit", "10"])
elif mode == "local_cache":
    cache = Path.home() / ".cache" / "huggingface" / "hub"
    items = [{"name": path.name, "exists": True} for path in sorted(cache.iterdir())[:100]] if cache.exists() else []
    out = {"cache": str(cache), "items": items, "truncated": len(items) == 100}
else:
    out = {"help": ["search <query>", "local_cache"]}
print(json.dumps(out, ensure_ascii=False))
