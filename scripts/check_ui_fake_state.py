"""UI fake-state gate for LocalComet (INV-UI-001).

Production UI must not generate backend state locally. State (ready, installed,
success, progress, running) must originate from backend events or invoke()
responses. This gate detects two common fake-state patterns:

  1. Math.random() anywhere in the frontend source. Fake progress/randomness
     has no legitimate place in state-bearing UI code. (LocalComet uses
     crypto.getRandomValues for identifiers, never Math.random.)

  2. A setTimeout/setInterval with a LITERAL delay >= 1000 ms placed near
     state-mutation keywords. This is the classic fake-progress shape, e.g.
     setTimeout(() => progress = 100, 2000). Legitimate polling/watchdog timers
     use named constants or variables (MANAGED_HEALTH_POLL_MS, delayMs) and are
     therefore not flagged.

Timers that merely POLL the backend (invoke inside the callback) or produce
FAILURE/timeout states are fine; this gate targets locally-fabricated success.

Exit 0 if no violations, 1 if any violation, 2 on scan error.

Injection: add `Math.random()` to a store, or
`setTimeout(() => { status = 'ready' }, 2000)` -> gate exits 1.
"""

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "desktop" / "localcomet-desktop" / "src"

STATE_KEYWORDS = (
    "store",
    "state",
    "ready",
    "status",
    "progress",
    "installed",
    "success",
    "running",
    "completed",
    "lifecycle",
)

MATH_RANDOM = re.compile(r"Math\.random\s*\(")
# setTimeout/setInterval with a literal numeric delay of >= 1000 ms.
LONG_LITERAL_TIMER = re.compile(r"set(?:Timeout|Interval)\s*\([^;]*?,\s*(\d{4,})\s*\)")


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def scan_file(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    violations = []

    for match in MATH_RANDOM.finditer(text):
        violations.append(
            f"VIOLATION [Math.random in UI source] {path}:{line_of(text, match.start())}"
        )

    for match in LONG_LITERAL_TIMER.finditer(text):
        delay = int(match.group(1))
        if delay < 1000:
            continue
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + 200)
        context = text[start:end].lower()
        if any(keyword in context for keyword in STATE_KEYWORDS):
            violations.append(
                f"VIOLATION [literal {delay}ms timer near state mutation] "
                f"{path}:{line_of(text, match.start())}"
            )

    return violations


def main() -> int:
    if not SRC_DIR.is_dir():
        print(f"FAIL: cannot find {SRC_DIR}")
        return 2

    files = [
        path
        for pattern in ("*.ts", "*.svelte", "*.js")
        for path in SRC_DIR.rglob(pattern)
        if "node_modules" not in path.parts
    ]

    all_violations = []
    for path in sorted(files):
        all_violations.extend(scan_file(path))

    if all_violations:
        for violation in all_violations:
            print(violation)
        print(f"\n{len(all_violations)} fake-state violation(s) in {len(files)} file(s)")
        return 1

    print(f"OK: no fake-state violations in {len(files)} frontend file(s) (INV-UI-001)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
