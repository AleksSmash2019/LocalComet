#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.repository_preflight_ru import run_repository_preflight


def _json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)


def _safe_output_path(raw: str, root: Path) -> Path:
    path = Path(raw).expanduser().resolve()
    if path.exists() and path.is_dir():
        raise ValueError("output path is a directory")
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return path
    raise ValueError("output path must be outside the source repository")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LocalComet read-only repository preflight.")
    parser.add_argument("--root", default=str(ROOT), help="Project root to inspect.")
    parser.add_argument("--json", action="store_true", help="Print stable JSON.")
    parser.add_argument("--output", default=None, help="Write JSON to an explicit file outside the repo.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    try:
        result = run_repository_preflight(root)
        text = _json(result)
        if args.output:
            out_path = _safe_output_path(args.output, root)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text + "\n", encoding="utf-8")
        if args.json:
            print(text)
        else:
            summary = result.get("summary", {})
            print(
                "LocalComet preflight "
                f"ok={result.get('ok')} "
                f"missing={summary.get('missing_count')} "
                f"syntax={summary.get('syntax_error_count')} "
                f"imports={summary.get('unresolved_import_count')} "
                f"unsafe={summary.get('unsafe_path_count')}"
            )
        return 0 if result.get("ok") else 1
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {type(exc).__name__}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
