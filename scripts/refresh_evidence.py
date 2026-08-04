"""Refresh LocalComet evidence with provenance headers.

Runs the project gates and records each result with a provenance header:
command, exit code, source tree digest, body SHA-256, timestamp, platform.

The tree digest binds the evidence to the exact source state. If the sources
change without re-running this script, check_evidence_provenance.py reports the
evidence as STALE (rule 1.6: stale evidence is worse than missing evidence).

Exit 0 if all gates pass, 1 otherwise.
"""

import datetime
import hashlib
import pathlib
import platform
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
EVIDENCE_DIR = REPO_ROOT / "artifacts" / "evidence"

SOURCE_GLOBS = [
    "desktop/localcomet-desktop/src-tauri/src/**/*.rs",
    "desktop/localcomet-desktop/src-tauri/Cargo.toml",
    "desktop/localcomet-desktop/src-tauri/Cargo.lock",
    "desktop/localcomet-desktop/src/**/*.ts",
    "desktop/localcomet-desktop/src/**/*.svelte",
    "desktop/contracts/*.json",
    "core/**/*.py",
    "modules/**/*.py",
    "agents/**/*.py",
    "next/**/*.py",
    "tests/**/*.py",
    "scripts/**/*.py",
    "tools/**/*.py",
    "security/invariants/*.toml",
    "security/contracts/**/*.json",
    ".gitattributes",
    "config.py",
    "agent.py",
    "app.py",
    "LocalComet_Control_Panel.py",
    "LocalComet_Patch_Panel.py",
]

EXCLUDE_PARTS = {"__pycache__", "node_modules", ".git", "target", ".svelte-kit", "build"}


def file_sha256(path: pathlib.Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def source_files() -> list[pathlib.Path]:
    seen: set[pathlib.Path] = set()
    files: list[pathlib.Path] = []
    for pattern in SOURCE_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            if not path.is_file():
                continue
            if any(part in EXCLUDE_PARTS for part in path.parts):
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(path)
    return sorted(files, key=lambda p: p.as_posix())


def tree_digest() -> str:
    entries = []
    for path in source_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        entries.append(f"{rel}:{file_sha256(path)}")
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


def run_and_save(name: str, cmd: list[str], digest: str) -> int:
    result = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    body = (result.stdout or "") + (result.stderr or "")
    body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    header = (
        f"# command: {' '.join(cmd)}\n"
        f"# exit_code: {result.returncode}\n"
        f"# tree_digest: {digest}\n"
        f"# body_sha256: {body_sha}\n"
        f"# timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n"
        f"# platform: {platform.system()} {platform.machine()} python={sys.version.split()[0]}\n"
        f"# source_files: {len(source_files())}\n"
        "---\n"
    )
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE_DIR / f"{name}.txt"
    out.write_text(header + body, encoding="utf-8", newline="\n")
    status = "OK" if result.returncode == 0 else "FAIL"
    print(f"[{status}] evidence/{name}.txt exit={result.returncode} tree={digest[:16]}...")
    return result.returncode


def main() -> int:
    digest = tree_digest()
    print(f"tree_digest: {digest} ({len(source_files())} source files)")
    cargo_manifest = "desktop/localcomet-desktop/src-tauri/Cargo.toml"
    codes = [
        run_and_save("cargo_test", ["cargo", "test", "--manifest-path", cargo_manifest], digest),
        run_and_save("trust_chain", ["python", "tests/test_trust_chain_invariants.py"], digest),
        run_and_save("cmd_parity", ["python", "scripts/check_command_parity.py"], digest),
        run_and_save("tool_risk_registry", ["python", "scripts/check_tool_risk_registry.py"], digest),
    ]
    if all(code == 0 for code in codes):
        print("evidence refreshed: all gates green")
        return 0
    print("evidence refreshed: one or more gates FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
