import sys, json, subprocess

def run(cmd):
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
    return {'cmd': cmd, 'returncode': proc.returncode, 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-2000:]}

mode = sys.argv[1] if len(sys.argv) > 1 else 'status'
cmds = {
    'status': 'git status --short',
    'log': 'git log --oneline -20',
    'branch': 'git branch -a',
    'diff': 'git diff --stat',
}
cmd = cmds.get(mode, 'git status --short')
print(json.dumps(run(cmd), ensure_ascii=False))
