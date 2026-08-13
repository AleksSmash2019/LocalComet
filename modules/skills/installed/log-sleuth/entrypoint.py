import sys, json, subprocess

def run(cmd):
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
    return {'cmd': cmd, 'returncode': proc.returncode, 'stdout': proc.stdout[-6000:], 'stderr': proc.stderr[-3000:]}

mode = sys.argv[1] if len(sys.argv) > 1 else 'help'
if mode == 'errors':
    out = run('powershell -Command "Get-Content -Path *.log -Tail 200 -ErrorAction SilentlyContinue | Select-String -Pattern ERROR,Exception,Traceback" || echo NO_LOGS')
elif mode == 'trace':
    out = run('powershell -Command "Get-Content -Path *.log -Tail 100 -ErrorAction SilentlyContinue" || echo NO_LOGS')
else:
    out = {'help': ['errors', 'trace']}
print(json.dumps(out, ensure_ascii=False))
