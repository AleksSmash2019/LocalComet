import sys, json
from pathlib import Path

try:
    from modules.browser_direct import BrowserHarness
    harness = BrowserHarness()
    mode = sys.argv[1] if len(sys.argv) > 1 else 'help'
    if mode == 'open':
        url = sys.argv[2] if len(sys.argv) > 2 else 'https://example.com'
        print(json.dumps({'opened': harness.open(url)}, ensure_ascii=False))
    elif mode == 'fetch':
        print(json.dumps({'text': harness.page_text()[:6000]}, ensure_ascii=False))
    elif mode == 'screenshot':
        path = Path('browser_screenshot.png')
        harness.screenshot(path)
        print(json.dumps({'screenshot': str(path)}, ensure_ascii=False))
    else:
        print(json.dumps({'help': ['open <url>', 'fetch', 'screenshot']}, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({'error': str(exc)}, ensure_ascii=False))
