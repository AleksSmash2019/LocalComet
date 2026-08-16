from __future__ import annotations
import json
import sys
from pathlib import Path

ledger = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
for item in ledger:
    print(f"{item['mutation_id']}|status={item.get('status')}|red_passed={item.get('red_passed')}|green_passed={item.get('green_passed')}|rollback={item.get('rollback_verified')}|test={item['test'].strip()}")
integrity = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
print(f"INTEGRITY|completed={integrity['mutations_completed']}|expected={integrity['mutations_expected']}|all_red={integrity['all_red']}|all_green_after_rollback={integrity['all_green_after_rollback']}|all_rollbacks_verified={integrity['all_rollbacks_verified']}")
