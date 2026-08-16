from __future__ import annotations
import json
import sys
from pathlib import Path

ledger = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
integrity = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
parts = []
for item in ledger:
    parts.append('%s:%s:%s:%s:%s' % (item['mutation_id'], item.get('status'), item.get('red_passed'), item.get('green_passed'), item.get('rollback_verified')))
print(';'.join(parts))
print('INTEGRITY completed=%s expected=%s all_red=%s all_green_after_rollback=%s all_rollbacks_verified=%s' % (integrity['mutations_completed'], integrity['mutations_expected'], integrity['all_red'], integrity['all_green_after_rollback'], integrity['all_rollbacks_verified']))
