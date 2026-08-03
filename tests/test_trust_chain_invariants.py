"""Trust-chain byte invariants for LocalComet.

Verifies that all trust-chain files maintain:
- No UTF-8 BOM
- LF line endings (no CRLF, no bare CR)
- Exactly one final LF
- Non-empty content
"""

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

TRUST_CHAIN_FILES = [
    "config.py",
    "localcomet_runtime_manifest.json",
    ".gitattributes",
    "desktop/contracts/localcomet_ipc_v1.schema.json",
    "desktop/localcomet-desktop/src-tauri/resources/localcomet/approved-artifacts.v1.json",
    "desktop/localcomet-desktop/src-tauri/Cargo.toml",
    "desktop/localcomet-desktop/package.json",
    "desktop/localcomet-desktop/tsconfig.json",
    "desktop/localcomet-desktop/svelte.config.js",
    "desktop/localcomet-desktop/vite.config.ts",
    "desktop/localcomet-desktop/vitest.config.ts",
    "third_party/llama.cpp/LICENSE-MIT.txt",
]

UTF8_BOM = b"\xef\xbb\xbf"


def check_file(path: pathlib.Path) -> list[str]:
    errors = []
    if not path.exists():
        errors.append(f"MISSING: {path}")
        return errors

    raw = path.read_bytes()

    if len(raw) == 0:
        errors.append(f"EMPTY: {path}")
        return errors

    if raw.startswith(UTF8_BOM):
        errors.append(f"BOM: {path}")

    if b"\r\n" in raw:
        errors.append(f"CRLF: {path}")

    if b"\r" in raw.replace(b"\r\n", b""):
        errors.append(f"BARE_CR: {path}")

    if not raw.endswith(b"\n"):
        errors.append(f"NO_FINAL_LF: {path}")

    if raw.endswith(b"\n\n"):
        errors.append(f"MULTIPLE_FINAL_LF: {path}")

    return errors


def main() -> int:
    all_errors = []
    checked = 0

    for relative in TRUST_CHAIN_FILES:
        path = REPO_ROOT / relative
        checked += 1
        all_errors.extend(check_file(path))

    security_dir = REPO_ROOT / "security" / "invariants"
    if security_dir.is_dir():
        for toml_file in sorted(security_dir.glob("*.toml")):
            checked += 1
            all_errors.extend(check_file(toml_file))

    if checked == 0:
        print("FAIL: no trust-chain files found")
        return 1

    if all_errors:
        for error in all_errors:
            print(f"FAIL: {error}")
        print(f"\n{len(all_errors)} violation(s) in {checked} file(s)")
        return 1

    print(f"OK: {checked} trust-chain files pass byte invariants")
    return 0


if __name__ == "__main__":
    sys.exit(main())
