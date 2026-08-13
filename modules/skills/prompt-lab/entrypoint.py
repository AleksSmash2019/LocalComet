import sys, json
mode = sys.argv[1] if len(sys.argv) > 1 else 'help'
if mode == 'templates':
    templates = [
        {'id': 'code-review', 'prompt': 'Review this code for bugs, security issues, and performance: {code}'},
        {'id': 'refactor', 'prompt': 'Refactor this code for clarity and maintainability: {code}'},
        {'id': 'explain', 'prompt': 'Explain this code in simple terms: {code}'},
    ]
    print(json.dumps({'templates': templates}, ensure_ascii=False))
elif mode == 'compare':
    print(json.dumps({'candidates': ['A: concise', 'B: detailed'], 'recommendation': 'use A for quick answers, B for deep analysis'}, ensure_ascii=False))
else:
    print(json.dumps({'help': ['templates', 'compare']}, ensure_ascii=False))
