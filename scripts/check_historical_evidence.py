"""Verify LocalComet HISTORICAL evidence layout and integrity.

Evidence model (owner decision 2026-07-29, B5 Evidence Model Fix):
  historical = artifacts/evidence/historical/*.txt.
  Each historical file is an honest snapshot of an OLDER source tree
  (8a0d1d80... B4A closure/baseline or cc18487b... B5 RED). It is STALE relative
  to the current tree BY DESIGN. Unlike check_evidence_provenance.py this gate
  must NOT require tree_digest == current; a historical file MUST carry an
  ORIGINAL tree digest and must NEVER claim the current tree.

Per historical/*.txt:
  - require a complete provenance header (command, exit_code, tree_digest,
    body_sha256);
  - require evidence_status == HISTORICAL;
  - report BODY_MISMATCH if body_sha256 != sha256(body);
  - report WRONG_TREE if tree_digest is not an original tree, or equals current.

Manifest integrity:
  - read historical/B5_HISTORICAL_EVIDENCE_MANIFEST.sha256;
  - the manifest file set must equal the .txt set on disk (no orphan/gap);
  - report MANIFEST_MISMATCH if a file's whole-file SHA-256 differs (expect 0).

Exit 0 iff all files are valid and the manifest has 0 divergences.
"""

import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from refresh_evidence import tree_digest as _compute_tree_digest  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HISTORICAL_DIR = REPO_ROOT / "artifacts" / "evidence" / "historical"
MANIFEST_NAME = "B5_HISTORICAL_EVIDENCE_MANIFEST.sha256"

REQUIRED_FIELDS = ("command", "exit_code", "tree_digest", "body_sha256")

ORIGINAL_TREES = frozenset(
    {
        # B4A closure / baseline
        "8a0d1d80e798f3d2a93cf84fd76829844186c88386e61ac906c067c3de7e7d88",
        # B5 RED
        "cc18487be7113bd5e12ead31aff35f923bf34a70b77892bf135b99d9971cb498",
    }
)
CURRENT_TREE = _compute_tree_digest()

# Pinned audited set; update on a legitimate composition change.
EXPECTED_HISTORICAL_COUNT = 46


def parse_evidence(text: str):
    if "\n---\n" not in text:
        return None, None
    header_part, body = text.split("\n---\n", 1)
    fields = {}
    for line in header_part.split("\n"):
        if line.startswith("# ") and ":" in line:
            key, _, value = line[2:].partition(":")
            fields[key.strip()] = value.strip()
    return fields, body


def file_sha256(path: pathlib.Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_manifest(path: pathlib.Path):
    entries = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        entries[parts[1]] = (parts[0], parts[2] if len(parts) >= 3 else "")
    return entries


def main() -> int:
    if not HISTORICAL_DIR.is_dir():
        print(f"FAIL: historical directory missing: {HISTORICAL_DIR}")
        return 1

    evidence_files = sorted(HISTORICAL_DIR.glob("*.txt"))
    if len(evidence_files) != EXPECTED_HISTORICAL_COUNT:
        print(
            f"FAIL: expected {EXPECTED_HISTORICAL_COUNT} historical files, "
            f"found {len(evidence_files)}"
        )
        return 1

    errors = []
    body_mismatch = 0
    valid = 0
    header_trees = {}

    for path in evidence_files:
        problems = []
        fields, body = parse_evidence(path.read_text(encoding="utf-8"))
        if fields is None:
            problems.append("MISSING_PROVENANCE: no provenance header")
        else:
            for field in REQUIRED_FIELDS:
                if field not in fields:
                    problems.append(f"MISSING_FIELD: lacks '{field}'")
            if fields.get("evidence_status") != "HISTORICAL":
                problems.append(
                    f"BAD_STATUS: evidence_status={fields.get('evidence_status')!r} != HISTORICAL"
                )
            if "body_sha256" in fields and body is not None:
                if hashlib.sha256(body.encode("utf-8")).hexdigest() != fields["body_sha256"]:
                    problems.append("BODY_MISMATCH: body hash changed")
                    body_mismatch += 1
            tree = fields.get("tree_digest")
            header_trees[path.name] = tree or ""
            if tree == CURRENT_TREE:
                problems.append("WRONG_TREE: historical file claims the CURRENT tree")
            elif tree not in ORIGINAL_TREES:
                problems.append(f"WRONG_TREE: tree_digest {str(tree)[:16]}... is not original")
        if problems:
            for p in problems:
                errors.append(f"{path.name}: {p}")
        else:
            valid += 1

    manifest_path = HISTORICAL_DIR / MANIFEST_NAME
    manifest_divergences = 0
    if not manifest_path.is_file():
        errors.append(f"MANIFEST_MISSING: {MANIFEST_NAME} not in historical/")
    else:
        entries = parse_manifest(manifest_path)
        on_disk = {p.name for p in evidence_files}
        for missing in sorted(on_disk - set(entries)):
            errors.append(f"MANIFEST_GAP: {missing} on disk but not in manifest")
        for orphan in sorted(set(entries) - on_disk):
            errors.append(f"MANIFEST_ORPHAN: {orphan} in manifest but not on disk")
        for fname in sorted(on_disk & set(entries)):
            expected_sha, manifest_tree = entries[fname]
            if file_sha256(HISTORICAL_DIR / fname) != expected_sha.lower():
                errors.append(f"MANIFEST_MISMATCH: {fname} whole-file sha256 differs")
                manifest_divergences += 1
            if manifest_tree and header_trees.get(fname) != manifest_tree:
                errors.append(f"MANIFEST_TREE_MISMATCH: {fname} header tree != manifest tree")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(
            f"\nHistorical evidence: {valid} valid, {body_mismatch} BODY_MISMATCH, "
            f"{manifest_divergences} manifest divergence(s), {len(errors)} problem(s)"
        )
        return 1

    print(
        f"Historical evidence: {valid} valid, {body_mismatch} BODY_MISMATCH, "
        f"original digests preserved"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
