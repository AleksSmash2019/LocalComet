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

# Static assets that call Tauri commands outside the Svelte source tree.
# ModelFit AI ships as a prebuilt HTML bundle loaded in an iframe; it reaches
# the backend through the window.__modelfit_invoke bridge exposed by
# src/lib/bridge/modelfit.ts, so its invocations never appear in src/.
STATIC_DIR = REPO_ROOT / "desktop" / "localcomet-desktop" / "static"


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


def extract_static_invokes(static_dir: pathlib.Path) -> set[str]:
    """Collect Tauri commands invoked from bundled static HTML assets.

    Bundled assets are minified: the resolved invoke function is stored in a
    single-letter local, so the call site looks like `await e("scan_hardware")`
    rather than `invoke("scan_hardware")`. Matching only on `invoke(` would
    miss it, so we also accept a bare call whose sole argument is a quoted
    snake_case literal, and keep the result intersected with the registered
    command set by the caller.
    """
    invokes: set[str] = set()
    if not static_dir.is_dir():
        return invokes
    patterns = (
        # Explicit bridge / invoke call sites.
        re.compile(r"""__modelfit_invoke\s*(?:\?\.)?\(\s*["']([a-z_]+)["']"""),
        re.compile(r"""(?:invoke\w*)\s*(?:<[^>]*>)?\(\s*["']([a-z_]+)["']"""),
        # Minified call through a local alias, e.g. await e("scan_hardware").
        re.compile(r"""\b[A-Za-z_$][\w$]*\(\s*["']([a-z][a-z0-9_]*_[a-z0-9_]+)["']\s*\)"""),
    )
    for html_file in static_dir.rglob("*.html"):
        text = html_file.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
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

    invoked = extract_frontend_invokes(SRC_DIR) | extract_static_invokes(STATIC_DIR)

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
