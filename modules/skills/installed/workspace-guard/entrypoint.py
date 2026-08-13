import sys, json
from pathlib import Path

mode = sys.argv[1] if len(sys.argv) > 1 else 'help'
if mode == 'policy':
    policy = {
        'allowed_roots': [str(Path.home() / 'Documents' / 'LocalComet-build-week-clean'), str(Path.home() / 'Documents' / 'LocalCometVault')],
        'forbidden_paths': ['src-tauri/target', 'node_modules', '.git', 'AppData'],
        'read_only_by_default': True,
    }
    print(json.dumps({'policy': policy}, ensure_ascii=False))
elif mode == 'validate':
    target = sys.argv[2] if len(sys.argv) > 2 else '.'
    path = Path(target).resolve()
    forbidden = ['src-tauri/target', 'node_modules', '.git', 'AppData']
    ok = not any(part in forbidden for part in path.parts)
    print(json.dumps({'path': str(path), 'allowed': ok}, ensure_ascii=False))
else:
    print(json.dumps({'help': ['policy', 'validate <path>']}, ensure_ascii=False))
