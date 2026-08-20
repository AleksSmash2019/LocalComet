from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "desktop" / "localcomet-desktop" / "static" / "modelfit.html"
raw = source.read_text(encoding="utf-8")
start = raw.index("const wl=[")
end = raw.index("];", start) + 2
print(f"start={start} end={end} length={end-start}")
print(raw[end:end+500])
(root / "audit" / "modelfit-registry-array.txt").write_text(raw[start:end], encoding="utf-8")
