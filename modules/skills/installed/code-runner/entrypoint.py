import json
import subprocess
import sys

TIMEOUT_SECONDS = 120


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


ALLOWED_SHELL_COMMANDS = {
    ('git', 'status', '--short'): ['git', 'status', '--short'],
    ('git', 'diff', '--stat'): ['git', 'diff', '--stat'],
    ('git', 'log', '--oneline', '-20'): ['git', 'log', '--oneline', '-20'],
    ('python', '-m', 'pytest', '-q'): [sys.executable, '-m', 'pytest', '-q'],
}

mode = sys.argv[1] if len(sys.argv) > 1 else 'status'
if mode == 'status':
    out = run(['git', 'status', '--short'])
elif mode == 'test':
    out = run([sys.executable, '-m', 'pytest', '-q'])
elif mode == 'shell':
    requested = tuple(sys.argv[2:])
    args = ALLOWED_SHELL_COMMANDS.get(requested)
    if args is None:
        out = {
            'error': 'arbitrary shell commands are disabled; use an allowlisted command',
            'allowed_commands': [list(command) for command in ALLOWED_SHELL_COMMANDS],
        }
    else:
        out = run(args)
else:
    out = {'error': f'unknown mode: {mode}'}
print(json.dumps(out, ensure_ascii=False))
