#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.project_audit_bundle_ru import AuditBundleError, create_audit_bundle


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create deterministic LocalComet audit bundle.")
    parser.add_argument("--root", default=str(ROOT), help="Project root to bundle.")
    parser.add_argument("--output", default=None, help="Output directory or .zip path.")
    parser.add_argument("--skip-tests", action="store_true", help="Record skipped tests instead of running them.")
    parser.add_argument("--max-file-size-mb", type=float, default=5.0, help="Per-file size limit.")
    parser.add_argument("--include-generated", action="store_true", help="Include generated reports where safe.")
    parser.add_argument("--deterministic", action="store_true", help="Use fixed timestamps and stable metadata.")
    parser.add_argument("--compare", default=None, help="Previous bundle_manifest.json or bundle zip to compare.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = create_audit_bundle(
            root=Path(args.root),
            output=Path(args.output) if args.output else None,
            skip_tests=args.skip_tests,
            max_file_size_mb=args.max_file_size_mb,
            include_generated=args.include_generated,
            deterministic=args.deterministic,
            compare=Path(args.compare) if args.compare else None,
        )
    except AuditBundleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: internal failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    print(str(result["zip_path"]))
    print(json.dumps({"bundle_id": result["bundle_id"], "bundle_health": result["bundle_health"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
