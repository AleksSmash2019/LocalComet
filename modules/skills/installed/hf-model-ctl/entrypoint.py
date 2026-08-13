import sys, json, subprocess
from pathlib import Path

def run(cmd):
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
    return {'cmd': cmd, 'returncode': proc.returncode, 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-2000:]}

mode = sys.argv[1] if len(sys.argv) > 1 else 'help'
if mode == 'search':
    query = ' '.join(sys.argv[2:]) or 'local model'
    out = run(f'hf search "{query}" --limit 10 || echo HF_SEARCH_UNAVAILABLE')
elif mode == 'local_cache':
    cache = Path.home() / '.cache' / 'huggingface' / 'hub'
    items = []
    if cache.exists():
        for path in sorted(cache.iterdir())[:100]:
            items.append({'name': path.name, 'exists': True})
    out = {'cache': str(cache), 'items': items, 'truncated': len(items) == 100}
else:
    out = {'help': ['search <query>', 'local_cache']}
print(json.dumps(out, ensure_ascii=False))
