"""UI fake-state gate for LocalComet (INV-UI-001).

Production UI must not generate backend state locally. State (ready, installed,
success, progress, running) must originate from backend events or invoke()
responses. This gate detects two common fake-state patterns:

  1. Math.random() anywhere in the frontend source. Fake progress/randomness
     has no legitimate place in state-bearing UI code. (LocalComet uses
     crypto.getRandomValues for identifiers, never Math.random.)

  2. A setTimeout/setInterval whose delay is a LITERAL, arithmetic or
     exponential expression evaluating to >= 1000 ms (1500, 1e3, 1000 + 500),
     including the three-argument form setTimeout(fn, ms, arg), placed near
     state-mutation keywords. This is the classic fake-progress shape, e.g.
     setTimeout(() => progress = 100, 2000). Legitimate polling/watchdog
     timers use named constants or variables without a large literal assigned
     nearby (MANAGED_HEALTH_POLL_MS, delayMs) and are therefore not flagged.

  3. A variable delay fed into a timer (const delay = 2000; setTimeout(fn,
     delay)) where a literal/expression >= 1000 ms is assigned to that
     variable close to the timer call, again near state-mutation keywords.

Timers that merely POLL the backend (invoke inside the callback) or produce
FAILURE/timeout states are fine; this gate targets locally-fabricated success.

Exit 0 if no violations, 1 if any violation, 2 on scan error.

Injection: add `Math.random()` to a store, or
`setTimeout(() => { status = 'ready' }, 2000)` -> gate exits 1.
"""

import ast
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
# Numeric delay expression: digits, exponent notation and + - * / ( ) only.
NUMERIC_EXPR = r"[0-9][0-9eE.+\-*/ ()]*[0-9)]"
# Timer delay slot terminated by `,` (three-argument form) or `)`. The
# callback gap is limited to a single statement (no `;`) like the original
# heuristic: multi-statement bodies that only reset state (auto-clear
# feedback timers such as ReviewIdentityPanel's copy badge) stay unflagged.
TIMER_CALLBACK_GAP = r"[^;]*?"
TIMER_DELAY_EXPR = re.compile(
    r"set(?:Timeout|Interval)\s*\(" + TIMER_CALLBACK_GAP + r",\s*(" + NUMERIC_EXPR + r")\s*[,)]"
)
# const/let/var assignment of a numeric expression (plain JS, no TS annotation).
VAR_NUMERIC_ASSIGN = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(" + NUMERIC_EXPR + r")\s*[;,)]"
)
CONTEXT_RADIUS = 200


def eval_delay(expr: str) -> float | None:
    """Safely evaluate a pure numeric delay expression; None when unsafe."""
    try:
        node = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None
    constants = ast.Constant, ast.BinOp, ast.UnaryOp, ast.Expression, ast.Load
    operators = ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd
    for child in ast.walk(node):
        if isinstance(child, ast.Constant):
            if not isinstance(child.value, (int, float)):
                return None
        elif not isinstance(child, constants + operators):
            return None
    try:
        return float(eval(compile(node, "<delay>", "eval")))  # noqa: S307 - AST-whitelisted numeric expression only
    except Exception:
        return None


def near_state_keywords(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - CONTEXT_RADIUS):min(len(text), end + CONTEXT_RADIUS)]
    return any(keyword in window.lower() for keyword in STATE_KEYWORDS)


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def timer_uses_var(text: str, name: str) -> re.Match[str] | None:
    """setTimeout/setInterval whose delay slot is the given identifier.

    The callback gap spans newlines but stays within one statement (no `;`),
    matching the delay-expression heuristic above.
    """
    return re.search(
        r"set(?:Timeout|Interval)\s*\("
        + TIMER_CALLBACK_GAP
        + r",\s*" + re.escape(name) + r"\s*[,)]",
        text,
    )


def scan_file(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    violations = []

    for match in MATH_RANDOM.finditer(text):
        violations.append(
            f"VIOLATION [Math.random in UI source] {path}:{line_of(text, match.start())}"
        )

    for match in TIMER_DELAY_EXPR.finditer(text):
        delay = eval_delay(match.group(1))
        if delay is None or delay < 1000:
            continue
        if near_state_keywords(text, match.start(), match.end()):
            violations.append(
                f"VIOLATION [{delay:g}ms delay expression near state mutation] "
                f"{path}:{line_of(text, match.start())}"
            )

    for assign in VAR_NUMERIC_ASSIGN.finditer(text):
        name = assign.group(1)
        delay = eval_delay(assign.group(2))
        if delay is None or delay < 1000:
            continue
        timer = timer_uses_var(text, name)
        if timer and near_state_keywords(
            text,
            min(assign.start(), timer.start()),
            max(assign.end(), timer.end()),
        ):
            violations.append(
                f"VIOLATION [variable '{name}' = {delay:g}ms near state mutation] "
                f"{path}:{line_of(text, timer.start())}"
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
