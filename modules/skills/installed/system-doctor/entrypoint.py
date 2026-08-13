import sys, json, subprocess
from pathlib import Path

def run(cmd):
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
    return {'cmd': cmd, 'returncode': proc.returncode, 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-2000:]}

mode = sys.argv[1] if len(sys.argv) > 1 else 'help'
if mode == 'health':
    out = {
        'python': run(f'{" ".join(sys.executable.splitlines())} --version'),
        'node': run('node --version'),
        'cargo': run('cargo --version'),
    }
elif mode == 'ports':
    out = run('netstat -ano | findstr :1420 || echo PORT_1420_NOT_FOUND')
elif mode == 'logs':
    out = run('python -m modules.maintenance')
else:
    out = {'help': ['health', 'ports', 'logs']}
print(json.dumps(out, ensure_ascii=False))
