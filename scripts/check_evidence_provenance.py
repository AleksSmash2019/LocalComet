"""Verify LocalComet evidence provenance (CURRENT tier only).

Evidence model (owner decision 2026-07-29, B5 Evidence Model Fix):
  current    = artifacts/evidence/*.txt (top-level only, non-recursive glob).
               MUST match the live tree_digest; reported STALE otherwise.
  historical = artifacts/evidence/historical/*.txt.
               Honest snapshots of older source trees; checked SEPARATELY by
               scripts/check_historical_evidence.py (body_sha256 integrity +
               original tree_digest preservation). This gate does NOT inspect
               the historical/ directory and does NOT require historical files
               to match the current tree.

For every top-level artifacts/evidence/*.txt file:
  - require a complete provenance header (command, exit_code, tree_digest,
    body_sha256);
  - recompute the current source tree digest;
  - report STALE if the recorded tree_digest no longer matches (sources changed
    after the evidence was captured);
  - report BODY_MISMATCH if the recorded body_sha256 does not match the body.

Exit 0 if all current evidence is fresh and intact, 1 otherwise.

Injection: modify any source file covered by refresh_evidence.SOURCE_GLOBS
without re-running refresh_evidence.py -> this gate exits 1 (STALE).
"""

import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from refresh_evidence import EVIDENCE_DIR, tree_digest  # noqa: E402

# Meta-evidence (checker output, provenance snapshots) lives here; NOT scanned.
META_DIR = EVIDENCE_DIR / "meta"

REQUIRED_FIELDS = ("command", "exit_code", "tree_digest", "body_sha256")
REQUIRED_EVIDENCE_FILES = (
    "cargo_test.txt",
    "trust_chain.txt",
    "cmd_parity.txt",
    "tool_risk_registry.txt",
)


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

    evidence_files = [EVIDENCE_DIR / name for name in REQUIRED_EVIDENCE_FILES]
    missing_files = [path.name for path in evidence_files if not path.is_file()]
    if missing_files:
        print(f"FAIL: MISSING_REQUIRED_EVIDENCE: {', '.join(missing_files)}")
        return 1

    live_digest = tree_digest()
    problems = 0
    for path in evidence_files:
        header, body = parse_evidence(path.read_text(encoding="utf-8"))
        if header is None or body is None:
            problems += 1
            print(f"FAIL: MALFORMED_HEADER: {path.name}")
            continue
        missing_fields = [field for field in REQUIRED_FIELDS if not header.get(field)]
        if missing_fields:
            problems += 1
            print(f"FAIL: MISSING_FIELDS: {path.name} {', '.join(missing_fields)}")
            continue
        if header["exit_code"] != "0":
            problems += 1
            print(f"FAIL: NONZERO_EXIT: {path.name} exit_code={header['exit_code']}")
        actual_body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if header["body_sha256"] != actual_body_sha:
            problems += 1
            print(f"FAIL: BODY_MISMATCH: {path.name}")
        if header["tree_digest"] != live_digest:
            problems += 1
            print(
                f"FAIL: STALE: {path.name} tree_digest {header['tree_digest'][:16]}... "
                f"!= current {live_digest[:16]}..."
            )

    if problems:
        print(f"\n{problems} provenance problem(s) across {len(evidence_files)} file(s)")
        return 1

    print(f"OK: {len(evidence_files)} evidence file(s) fresh and intact (tree={live_digest[:16]}...)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
