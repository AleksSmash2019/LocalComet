import json
import subprocess
import sys

TIMEOUT_SECONDS = 120
COMMANDS = {
    'status': ['git', 'status', '--short'],
    'log': ['git', 'log', '--oneline', '-20'],
    'branch': ['git', 'branch', '-a'],
    'diff': ['git', 'diff', '--stat'],
}


def run(args):
    proc = subprocess.run(
        args,
        shell=False,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
    return {
        'command': args,
        'returncode': proc.returncode,
        'stdout': proc.stdout[-4000:],
        'stderr': proc.stderr[-2000:],
    }


mode = sys.argv[1] if len(sys.argv) > 1 else 'status'
args = COMMANDS.get(mode)
if args is None:
    out = {
        'error': f'unknown mode: {mode}',
        'allowed_modes': sorted(COMMANDS),
    }
else:
    out = run(args)
print(json.dumps(out, ensure_ascii=False))
