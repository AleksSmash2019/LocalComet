"""Command parity gate for LocalComet desktop.

Verifies that every Tauri command registered in generate_handler![]
has a corresponding invoke() call in the Svelte frontend, and vice versa.

Exit codes:
  0 - parity holds
  1 - mismatch detected
  2 - could not parse sources
"""

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LIB_RS = REPO_ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "src" / "lib.rs"
SRC_DIR = REPO_ROOT / "desktop" / "localcomet-desktop" / "src"


def extract_registered_commands(lib_rs_text: str) -> set[str]:
    match = re.search(
        r"generate_handler!\[(.*?)\]", lib_rs_text, re.DOTALL
    )
    if not match:
        return set()
    body = match.group(1)
    return {
        name.strip()
        for name in body.split(",")
        if name.strip() and not name.strip().startswith("//")
    }


def extract_frontend_invokes(src_dir: pathlib.Path) -> set[str]:
    invokes = set()
    pattern = re.compile(
        r"""(?:invoke\w*)\s*(?:<[^>]*>)?\(\s*["']([a-z_]+)["']"""
    )
    for ts_file in src_dir.rglob("*.ts"):
        text = ts_file.read_text(encoding="utf-8", errors="replace")
        invokes.update(pattern.findall(text))
    for svelte_file in src_dir.rglob("*.svelte"):
        text = svelte_file.read_text(encoding="utf-8", errors="replace")
        invokes.update(pattern.findall(text))
    return invokes


def main() -> int:
    if not LIB_RS.exists():
        print(f"FAIL: cannot find {LIB_RS}")
        return 2

    lib_text = LIB_RS.read_text(encoding="utf-8", errors="replace")
    registered = extract_registered_commands(lib_text)

    if not registered:
        print("FAIL: no commands found in generate_handler!")
        return 2

    if not SRC_DIR.is_dir():
        print(f"FAIL: cannot find {SRC_DIR}")
        return 2

    invoked = extract_frontend_invokes(SRC_DIR)

    registered_not_invoked = registered - invoked
    invoked_not_registered = invoked - registered

    errors = []
    for cmd in sorted(registered_not_invoked):
        errors.append(f"REGISTERED_NOT_INVOKED: {cmd}")
    for cmd in sorted(invoked_not_registered):
        errors.append(f"INVOKED_NOT_REGISTERED: {cmd}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(
            f"\n{len(registered)} registered, {len(invoked)} invoked, "
            f"{len(errors)} mismatch(es)"
        )
        return 1

    print(
        f"OK: {len(registered)} commands registered and invoked "
        f"(parity holds)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
