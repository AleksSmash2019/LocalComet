import json
import subprocess
import sys
from pathlib import Path

TIMEOUT_SECONDS = 120


def run(args):
    try:
        proc = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return {
            'command': args,
            'returncode': 127,
            'stdout': '',
            'stderr': 'HF_SEARCH_UNAVAILABLE',
        }
    return {
        'command': args,
        'returncode': proc.returncode,
        'stdout': proc.stdout[-4000:],
        'stderr': proc.stderr[-2000:],
    }


mode = sys.argv[1] if len(sys.argv) > 1 else 'help'
if mode == 'search':
    query = ' '.join(sys.argv[2:]) or 'local model'
    out = run(['hf', 'search', query, '--limit', '10'])
elif mode == 'local_cache':
    cache = Path.home() / '.cache' / 'huggingface' / 'hub'
    items = []
    if cache.exists():
        for item in sorted(cache.iterdir()):
            if item.is_dir():
                items.append({'name': item.name, 'exists': True})
                if len(items) >= 100:
                    break
    out = {'cache': str(cache), 'items': items, 'truncated': len(items) == 100}
elif mode == 'prepare':
    out = {
        'error': 'model preparation is handled by the approved model gateway',
        'available': ['search', 'local_cache'],
    }
else:
    out = {'help': ['search <query>', 'local_cache']}
print(json.dumps(out, ensure_ascii=False))
