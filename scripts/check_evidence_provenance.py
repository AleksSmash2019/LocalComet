"""Verify LocalComet evidence provenance.

For every artifacts/evidence/*.txt file:
  - require a complete provenance header (command, exit_code, tree_digest,
    body_sha256);
  - recompute the current source tree digest;
  - report STALE if the recorded tree_digest no longer matches (sources changed
    after the evidence was captured);
  - report BODY_MISMATCH if the recorded body_sha256 does not match the body.

Exit 0 if all evidence is fresh and intact, 1 otherwise.

Injection: modify any source file covered by refresh_evidence.SOURCE_GLOBS
without re-running refresh_evidence.py -> this gate exits 1 (STALE).
"""

import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from refresh_evidence import EVIDENCE_DIR, tree_digest  # noqa: E402

REQUIRED_FIELDS = ("command", "exit_code", "tree_digest", "body_sha256")


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


def main() -> int:
    if not EVIDENCE_DIR.is_dir():
        print(f"FAIL: evidence directory missing: {EVIDENCE_DIR}")
        return 1

    evidence_files = sorted(EVIDENCE_DIR.glob("*.txt"))
    if not evidence_files:
        print("FAIL: no evidence files found (run scripts/refresh_evidence.py)")
        return 1

    current_digest = tree_digest()
    errors = []

    for path in evidence_files:
        text = path.read_text(encoding="utf-8")
        fields, body = parse_evidence(text)
        if fields is None:
            errors.append(f"MISSING_PROVENANCE: {path.name} has no provenance header")
            continue
        for field in REQUIRED_FIELDS:
            if field not in fields:
                errors.append(f"MISSING_FIELD: {path.name} lacks '{field}'")
        if "tree_digest" in fields and fields["tree_digest"] != current_digest:
            errors.append(
                f"STALE: {path.name} tree_digest {fields['tree_digest'][:16]}... "
                f"!= current {current_digest[:16]}..."
            )
        if "body_sha256" in fields and body is not None:
            actual = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if actual != fields["body_sha256"]:
                errors.append(f"BODY_MISMATCH: {path.name} body hash changed")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"\n{len(errors)} provenance problem(s) across {len(evidence_files)} file(s)")
        return 1

    print(
        f"OK: {len(evidence_files)} evidence file(s) fresh and intact "
        f"(tree={current_digest[:16]}...)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
