import sys, json
print("SKILL_OK")
print(sys.argv[1] if len(sys.argv) > 1 else "")
print(json.dumps({"echo": sys.argv[1] if len(sys.argv) > 1 else ""}, ensure_ascii=False))
