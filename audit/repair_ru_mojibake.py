from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
changed = 0
out_lines = []
for line in text.splitlines(keepends=True):
    if any(marker in line for marker in ('Р', 'С', 'вЂ', 'Р', 'Рџ')):
        candidates = []
        for encoding in ('cp1251', 'cp1252', 'latin1'):
            try:
                candidates.append(line.encode(encoding).decode('utf-8'))
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        def badness(value: str) -> int:
            return sum(value.count(marker) for marker in ('Р', 'С', 'вЂ', 'Р', 'Рџ', 'Ѓ', '™'))
        repaired = min(candidates, key=badness, default=line)
        if repaired != line and badness(repaired) < badness(line):
            line = repaired
            changed += 1
    out_lines.append(line)
new_text = ''.join(out_lines)
if new_text == text:
    print('no changes')
else:
    path.write_text(new_text, encoding='utf-8', newline='')
    print(f'repaired_lines={changed}')
