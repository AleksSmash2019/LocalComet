from __future__ import annotations

import json
from modules.pc_agent_actions import open_app as pc_open_app
from modules.computer_use_real_actions_ru import execute_real_action
from modules.tool_execution_ru import _computer_use

results = {
    "pc_agent_actions": pc_open_app("notepad", dry_run=False),
    "real_actions": execute_real_action({"kind": "open_app", "target": "notepad"}, simulate=False),
    "sidecar_dispatch": _computer_use(None, "computer_use", {"action": "open_app", "target": "notepad"}),
}
print(json.dumps(results, ensure_ascii=False, sort_keys=True))
