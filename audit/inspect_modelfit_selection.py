from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "desktop" / "localcomet-desktop" / "static" / "modelfit.html"
raw = source.read_text(encoding="utf-8")
needles = ["function wp", "function xp", "qualityScore", "hardwareDemandScore", "recommend", "recommendation", "wl.filter", "wl.map"]
out = []
for needle in needles:
    positions = []
    offset = 0
    while True:
        index = raw.find(needle, offset)
        if index < 0:
            break
        positions.append(index)
        offset = index + len(needle)
    out.append(f"===== {needle}: {positions[:20]} =====")
    for index in positions[:5]:
        start = max(0, index - 700)
        end = min(len(raw), index + 1600)
        out.append(raw[start:end])
(root / "audit" / "modelfit-selection-snippets.txt").write_text("\n\n".join(out), encoding="utf-8")
print("saved", len(out), "sections")
