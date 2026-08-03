"""Byte-compile every Python source file in the repository.

AGENTS.md requires py_compile for every changed Python file. This gate widens
that rule to the whole tree so a syntax error can never reach a commit just
because the author forgot which files they touched.

Scope is the git index (`git ls-files -- *.py`): exactly the files that can
reach a commit. That deliberately excludes the shipped sidecar bundle under
src-tauri/binaries/ (build output, covered by check_bundle_parity.py) and the
vendored Python/ runtime. When git is unavailable the gate falls back to a
filesystem walk with an equivalent exclude set.

Compilation uses the builtin compile() on the raw source bytes, so the PEP 263
encoding cookie is honoured and nothing is written to disk. (py_compile is
deliberately not used: with quiet=2 it swallows the exception that doraise=True
is supposed to raise, and with cfile=None it still writes __pycache__ entries.)

Exit 0 if every file compiles, 1 otherwise.

Injection: introduce a SyntaxError in any tracked *.py -> this gate exits 1.
"""

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Fallback only: directory names that are never committed project source.
EXCLUDE_PARTS = {
    "__pycache__",
    "node_modules",
    ".git",
    "target",
    ".svelte-kit",
    "build",
    "dist",
    ".venv",
    "venv",
    "Python",
    "binaries",
    "artifacts",
    ".hermes",
    ".pi-subagents",
    ".pytest_cache",
    ".idea",
}


def tracked_files() -> list[pathlib.Path] | None:
    """Python files in the git index, or None if git cannot answer."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", "*.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return [REPO_ROOT / rel for rel in result.stdout.split("\0") if rel]


def walked_files() -> list[pathlib.Path]:
    return [
        path
        for path in REPO_ROOT.rglob("*.py")
        if path.is_file() and not any(part in EXCLUDE_PARTS for part in path.parts)
    ]


def source_files() -> tuple[list[pathlib.Path], str]:
    tracked = tracked_files()
    if tracked is None:
        return sorted(walked_files(), key=lambda p: p.as_posix()), "filesystem walk"
    return sorted(tracked, key=lambda p: p.as_posix()), "git index"


def main() -> int:
    files, scope = source_files()
    if not files:
        print(f"FAIL: no Python source files found ({scope})")
        return 1

    failures: list[tuple[str, str]] = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if not path.is_file():
            failures.append((rel, "listed in git index but missing on disk"))
            continue
        try:
            compile(path.read_bytes(), rel, "exec", dont_inherit=True)
        except SyntaxError as exc:
            failures.append((rel, f"line {exc.lineno}: {exc.msg}"))
        except (ValueError, UnicodeDecodeError) as exc:
            failures.append((rel, f"{exc.__class__.__name__}: {exc}"))

    for rel, detail in failures:
        print(f"FAIL: COMPILE_ERROR: {rel}: {detail}")

    if failures:
        print(f"\n{len(failures)} compile error(s) across {len(files)} file(s) ({scope})")
        return 1

    print(f"OK: {len(files)} Python file(s) compile clean ({scope})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
