"""Generate third-party NOTICE bundles for LocalComet dependencies.

Sources of truth (bytes on disk, no network):
- Rust crates: Cargo.lock + license fields from the local cargo registry
  checkout (registry src), which is exactly what offline builds compile.
- npm packages: package-lock.json + node_modules/<pkg>/package.json.

Output: docs/THIRD-PARTY-NOTICES-rust.md and docs/THIRD-PARTY-NOTICES-npm.md
(each a license inventory table; full upstream texts ship in the repo and are
linked from audit/provenance_inventory_current_*.json).

Run: py -3.14 tools/generate_notice_bundles.py
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop" / "localcomet-desktop"
DOCS = ROOT / "docs"

UNKNOWN = "UNKNOWN"


def rust_crates() -> list[tuple[str, str, str]]:
    lock_path = DESKTOP / "src-tauri" / "Cargo.lock"
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    seen: dict[str, str] = {}
    for pkg in lock.get("package", []):
        name = pkg.get("name", "")
        version = pkg.get("version", "")
        source = pkg.get("source", "")
        if not name or not version:
            continue
        # Workspace/local crates have no source URL.
        if not source:
            continue
        seen[f"{name}@{version}"] = source
    registry_roots = sorted((Path.home() / ".cargo" / "registry" / "src").glob("index.crates.io-*"))
    out: list[tuple[str, str, str]] = []
    missing = []
    for key, _source in sorted(seen.items()):
        name, version = key.rsplit("@", 1)
        license_field = None
        for reg in registry_roots:
            manifest = reg / f"{name}-{version}" / "Cargo.toml"
            if manifest.is_file():
                try:
                    data = tomllib.loads(manifest.read_bytes().decode("utf-8", errors="replace"))
                except Exception:
                    continue
                pkg_tbl = data.get("package", {})
                license_field = pkg_tbl.get("license") or pkg_tbl.get("license-file")
                break
        if license_field is None:
            missing.append(key)
            license_field = UNKNOWN
        out.append((name, version, str(license_field)))
    if missing:
        print(f"rust: no local Cargo.toml for {len(missing)} crate(s): {missing[:5]}", file=sys.stderr)
    return out


def npm_packages() -> list[tuple[str, str, str]]:
    lock_path = DESKTOP / "package-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    node_modules = DESKTOP / "node_modules"
    out: list[tuple[str, str, str]] = []
    missing = []
    for key, meta in sorted(lock.get("packages", {}).items()):
        if not key:  # root package
            continue
        name = key.removeprefix("node_modules/")
        if "node_modules/" in name:  # nested dep, covered by its own hoisted entry
            continue
        version = str(meta.get("version", ""))
        license_field = meta.get("license")
        if license_field is None:
            pkg_json = node_modules / name / "package.json"
            if pkg_json.is_file():
                try:
                    license_field = json.loads(pkg_json.read_text(encoding="utf-8")).get("license")
                except Exception:
                    license_field = None
        if license_field is None:
            missing.append(f"{name}@{version}")
            license_field = UNKNOWN
        if isinstance(license_field, dict):
            license_field = license_field.get("type", UNKNOWN)
        out.append((name, version, str(license_field)))
    if missing:
        print(f"npm: no license field for {len(missing)} package(s): {missing[:5]}", file=sys.stderr)
    return out


def write_markdown(path: Path, title: str, rows: list[tuple[str, str, str]]) -> None:
    total = len(rows)
    unknown = [r for r in rows if r[2] == UNKNOWN]
    lines = [
        f"# {title}",
        "",
        f"Generated {__import__('datetime').date.today().isoformat()} by `tools/generate_notice_bundles.py` "
        "from `Cargo.lock` / `package-lock.json` and the local dependency checkouts that offline builds compile.",
        "",
        f"Packages: **{total}**; license fields resolved: **{total - len(unknown)}**; unresolved: **{len(unknown)}**.",
        "",
        "Package | Version | License",
        "---|---|---",
    ]
    for name, version, license_field in rows:
        safe_license = re.sub(r"[|\r\n]+", " ", license_field) or UNKNOWN
        lines.append(f"{name} | {version} | {safe_license}")
    if unknown:
        lines += ["", "## Unresolved license fields", ""]
        lines += [f"- {name}@{version}" for name, version, _ in unknown]
        lines += [
            "",
            "Unresolved entries must be cleared manually before any public redistribution "
            "(upstream Cargo.toml/package.json on the pinned version is the authority).",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {path} ({total} packages, {len(unknown)} unresolved)")


def main() -> int:
    DOCS.mkdir(exist_ok=True)
    write_markdown(
        DOCS / "THIRD-PARTY-NOTICES-rust.md",
        "Third-Party Notices — Rust dependencies (Cargo.lock)",
        rust_crates(),
    )
    write_markdown(
        DOCS / "THIRD-PARTY-NOTICES-npm.md",
        "Third-Party Notices — npm dependencies (package-lock.json)",
        npm_packages(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
