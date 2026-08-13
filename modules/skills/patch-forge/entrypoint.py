import sys, json, subprocess

def run(cmd):
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
    return {'cmd': cmd, 'returncode': proc.returncode, 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-2000:]}

mode = sys.argv[1] if len(sys.argv) > 1 else 'help'
if mode == 'diff':
    target = ' '.join(sys.argv[2:]) or 'desktop/localcomet-desktop/src-tauri/src'
    out = run(f'git diff -- {target}')
elif mode == 'status':
    out = run('git status --short')
elif mode == 'validate':
    patch_path = ' '.join(sys.argv[2:]) or 'patch.diff'
    out = run(f'git apply --check {patch_path}')
else:
    out = {'help': ['diff [path]', 'status', 'validate [patch_path]']}
print(json.dumps(out, ensure_ascii=False))
