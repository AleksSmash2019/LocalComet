from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "desktop" / "localcomet-desktop" / "static" / "modelfit.html"
out = ROOT / "audit" / "modelfit-registry-index.txt"
raw = source.read_text(encoding="utf-8")
pattern = re.compile(
    r'\{id:"([^"]+)",name:"([^"]+)".*?'
    r'qualityScore:(\d+),speedScore:(\d+),hardwareDemandScore:(\d+)\}'
)
lines = [
    f"{match.group(1)}\t{match.group(2)}\tquality={match.group(3)}\tspeed={match.group(4)}\thardware={match.group(5)}"
    for match in pattern.finditer(raw)
]
out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
print(f"extracted={len(lines)}")
for line in lines:
    print(line)
