from __future__ import annotations
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
for item in payload['results']:
    print(f"{item['gate_id']}|exit={item['exit_code']}|timeout={item['timed_out']}|seconds={item['duration_seconds']}|passed={item['passed']}")
print(f"ALL_PASSED|{payload['all_passed']}")
