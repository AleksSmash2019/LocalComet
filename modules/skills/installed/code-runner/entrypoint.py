import sys, json, subprocess
from pathlib import Path

def run(cmd):
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
    return {'cmd': cmd, 'returncode': proc.returncode, 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-2000:]}

mode = sys.argv[1] if len(sys.argv) > 1 else 'status'
if mode == 'status':
    out = run('git status --short')
elif mode == 'test':
    out = run('python -m pytest -q')
elif mode == 'shell':
    out = run(' '.join(sys.argv[2:]) or 'echo no command')
else:
    out = {'error': f'unknown mode: {mode}'}
print(json.dumps(out, ensure_ascii=False))
