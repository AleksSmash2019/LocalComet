import sys, json
from pathlib import Path

EXTENSIONS = {'.py', '.ts', '.svelte', '.rs', '.toml', '.json', '.md', '.yaml', '.yml'}
root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
files = []
for path in root.rglob('*'):
    if path.is_file() and path.suffix in EXTENSIONS:
        files.append(str(path.relative_to(root)))
print(json.dumps({'root': str(root), 'file_count': len(files), 'files': files[:200], 'truncated': len(files) > 200}, ensure_ascii=False))
