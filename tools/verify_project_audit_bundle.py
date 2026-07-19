#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
import zipfile
from pathlib import PurePosixPath
from typing import Any

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.project_audit_bundle_ru import (
    EXCLUDE_GLOBS,
    EXCLUDE_PREFIXES,
    RELEASE,
    VERIFIER_SCHEMA_VERSION,
    _json_bytes,
    _matches_any,
    redact_text,
    scan_text_for_secret_markers,
)


REQUIRED_METADATA = {
    "bundle_manifest.json",
    "file_hashes_sha256.json",
    "tracked_files.txt",
    "included_untracked_sources.txt",
    "excluded_paths.json",
    "git_status.txt",
    "git_diff.patch",
    "git_diff_stat.txt",
    "git_diff_name_status.txt",
    "import_graph.json",
    "versions.json",
    "test_results.json",
    "secret_findings.json",
    "localcomet_runtime_manifest.json",
}
TEXT_SUFFIXES = (".txt", ".json", ".md", ".patch", ".py", ".csv", ".yml", ".yaml", ".toml", ".html", ".css", ".js")


class VerificationFailure(Exception):
    pass


def _ok_result() -> dict[str, Any]:
    return {
        "mode": "audit_bundle_verification",
        "version": VERIFIER_SCHEMA_VERSION,
        "ok": False,
        "legacy_schema": False,
        "bundle_id": "",
        "integrity": {},
        "security": {},
        "missing": [],
        "unexpected": [],
        "hash_mismatches": [],
        "secret_findings": [],
        "warnings": [],
        "summary": {},
    }


def _safe_zip_name(name: str) -> None:
    if not name or "\\" in name:
        raise VerificationFailure("archive path contains empty text or backslash")
    if unicodedata.normalize("NFKC", name) != name:
        raise VerificationFailure("archive path changes under Unicode NFKC normalization")
    if name.startswith("/") or name.startswith("\\"):
        raise VerificationFailure("archive path is absolute")
    pure = PurePosixPath(name)
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise VerificationFailure("archive path contains traversal or empty segment")


def _source_rel_from_entry(bundle_root: str, name: str) -> str | None:
    prefix = f"{bundle_root}/source/"
    if not name.startswith(prefix):
        return None
    return name[len(prefix) :]


def _metadata_rel_from_entry(bundle_root: str, name: str) -> str | None:
    prefix = f"{bundle_root}/metadata/"
    if not name.startswith(prefix):
        return None
    return name[len(prefix) :]


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0o170000
    return mode == 0o120000


def _json_from_zip(zipf: zipfile.ZipFile, name: str) -> Any:
    try:
        return json.loads(zipf.read(name).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationFailure(f"malformed JSON: {name}: {exc}") from exc


def _recompute_bundle_id(manifest: dict[str, Any]) -> str:
    base = dict(manifest)
    base["bundle_id"] = None
    base.pop("bundle_name", None)
    base.pop("created_at_utc", None)
    return hashlib.sha256(_json_bytes(base)).hexdigest()[:16]


def _excluded_source_present(rel: str) -> bool:
    if any(rel.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return True
    if _matches_any(rel, EXCLUDE_GLOBS):
        return True
    return False


def verify_bundle(
    bundle_zip: Path,
    max_entries: int = 10000,
    max_uncompressed_mb: float = 500,
    max_single_file_mb: float = 10,
    max_compression_ratio: float = 100.0,
) -> dict[str, Any]:
    result = _ok_result()
    bundle_zip = bundle_zip.expanduser()
    try:
        with zipfile.ZipFile(bundle_zip, "r") as zipf:
            infos = zipf.infolist()
            names = [info.filename for info in infos]
            if len(names) > max_entries:
                raise VerificationFailure("archive exceeds max entry count")
            if len(names) != len(set(names)):
                raise VerificationFailure("duplicate ZIP entries detected")
            if not names:
                raise VerificationFailure("empty archive")
            for info in infos:
                _safe_zip_name(info.filename)
                if _is_symlink(info):
                    raise VerificationFailure("symlink ZIP entry rejected")
            bundle_roots = {PurePosixPath(name).parts[0] for name in names}
            if len(bundle_roots) != 1:
                raise VerificationFailure("archive must contain exactly one bundle root")
            bundle_root = next(iter(bundle_roots))
            total_uncompressed = sum(info.file_size for info in infos)
            if total_uncompressed > int(max_uncompressed_mb * 1024 * 1024):
                raise VerificationFailure("archive exceeds max uncompressed size")
            for info in infos:
                if info.file_size > int(max_single_file_mb * 1024 * 1024):
                    raise VerificationFailure(f"entry exceeds max file size: {info.filename}")
                if info.compress_size == 0 and info.file_size > 0:
                    raise VerificationFailure(f"entry has suspicious compression metadata: {info.filename}")
                if info.compress_size and info.file_size / max(info.compress_size, 1) > max_compression_ratio:
                    raise VerificationFailure(f"entry compression ratio is suspicious: {info.filename}")

            metadata_names = {
                rel
                for name in names
                for rel in [_metadata_rel_from_entry(bundle_root, name)]
                if rel is not None
            }
            missing_metadata = sorted(REQUIRED_METADATA - metadata_names)
            if missing_metadata:
                result["missing"].extend(f"metadata/{name}" for name in missing_metadata)
                raise VerificationFailure("required metadata missing")
            manifest_name = f"{bundle_root}/metadata/bundle_manifest.json"
            manifest = _json_from_zip(zipf, manifest_name)
            if not isinstance(manifest, dict):
                raise VerificationFailure("bundle manifest must be an object")
            if manifest.get("release") not in {RELEASE, "v6.80.1"}:
                raise VerificationFailure("unsupported bundle release")
            legacy_schema = manifest.get("release") == "v6.80.1" or "bundle_integrity.json" not in metadata_names
            result["legacy_schema"] = bool(legacy_schema)
            if manifest.get("hash_algorithm") != "sha256":
                raise VerificationFailure("unsupported hash algorithm")
            files = manifest.get("files")
            if not isinstance(files, list):
                raise VerificationFailure("manifest files must be a list")
            listed_paths: list[str] = []
            source_hashes: dict[str, str] = {}
            for item in files:
                if not isinstance(item, dict):
                    raise VerificationFailure("manifest file item must be an object")
                rel = item.get("path")
                digest = item.get("sha256")
                if not isinstance(rel, str) or not isinstance(digest, str):
                    raise VerificationFailure("manifest file item missing path or sha256")
                _safe_zip_name(rel)
                if rel != PurePosixPath(rel).as_posix() or rel in listed_paths:
                    raise VerificationFailure("manifest paths must be sorted unique normalized paths")
                if _excluded_source_present(rel):
                    raise VerificationFailure(f"excluded path present in source manifest: {rel}")
                listed_paths.append(rel)
                source_hashes[rel] = digest
            if listed_paths != sorted(listed_paths, key=str.lower):
                raise VerificationFailure("manifest paths are not sorted")
            source_entries = sorted(
                rel
                for name in names
                for rel in [_source_rel_from_entry(bundle_root, name)]
                if rel is not None
            )
            listed_sorted = sorted(listed_paths, key=str.lower)
            missing_sources = sorted(set(listed_sorted) - set(source_entries), key=str.lower)
            unexpected_sources = sorted(set(source_entries) - set(listed_sorted), key=str.lower)
            result["missing"].extend(missing_sources)
            result["unexpected"].extend(unexpected_sources)
            if missing_sources or unexpected_sources:
                raise VerificationFailure("source entries do not match manifest")
            for rel in listed_sorted:
                data = zipf.read(f"{bundle_root}/source/{rel}")
                digest = hashlib.sha256(data).hexdigest()
                if digest != source_hashes[rel]:
                    result["hash_mismatches"].append({"path": rel, "expected": source_hashes[rel], "actual": digest})
            if result["hash_mismatches"]:
                raise VerificationFailure("source hash mismatch")
            file_hashes_name = f"{bundle_root}/metadata/file_hashes_sha256.json"
            file_hashes = _json_from_zip(zipf, file_hashes_name)
            if file_hashes != source_hashes:
                raise VerificationFailure("file_hashes_sha256.json does not match manifest")
            expected_bundle_id = _recompute_bundle_id(manifest)
            if manifest.get("bundle_id") != expected_bundle_id:
                raise VerificationFailure("bundle_id does not match deterministic manifest content")
            for name in names:
                logical_name = name[len(bundle_root) + 1 :] if name.startswith(bundle_root + "/") else name
                if logical_name in {"metadata/secret_findings.json", "metadata/metadata_secret_findings.json"}:
                    continue
                suffix = PurePosixPath(name).suffix.lower()
                if suffix in TEXT_SUFFIXES or "/metadata/" in name or name.endswith("README_AUDIT.md"):
                    text = zipf.read(name).decode("utf-8", errors="ignore")
                    for finding in scan_text_for_secret_markers(text):
                        result["secret_findings"].append(
                            {"file": name, "line": finding["line"], "category": finding["category"]}
                        )
            integrity_name = f"{bundle_root}/metadata/bundle_integrity.json"
            if "bundle_integrity.json" in metadata_names:
                integrity = _json_from_zip(zipf, integrity_name)
                if integrity.get("bundle_id") != manifest.get("bundle_id"):
                    raise VerificationFailure("bundle_integrity bundle_id mismatch")
                expected_count = len(names)
                if integrity.get("entry_count") != expected_count:
                    raise VerificationFailure("bundle_integrity entry count mismatch")
                entry_hashes = integrity.get("entry_sha256")
                if not isinstance(entry_hashes, dict):
                    raise VerificationFailure("bundle_integrity entry_sha256 missing")
                logical_names = sorted(
                    name[len(bundle_root) + 1 :]
                    for name in names
                    if name != integrity_name
                )
                if sorted(entry_hashes, key=str.lower) != sorted(logical_names, key=str.lower):
                    raise VerificationFailure("bundle_integrity entry list mismatch")
                for logical_name in logical_names:
                    actual = hashlib.sha256(zipf.read(f"{bundle_root}/{logical_name}")).hexdigest()
                    if entry_hashes.get(logical_name) != actual:
                        raise VerificationFailure(f"bundle_integrity hash mismatch: {logical_name}")
                result["integrity"] = {
                    "bundle_id_recomputed": expected_bundle_id,
                    "hashes_verified": len(listed_sorted),
                    "entry_count": expected_count,
                    "uncompressed_size": total_uncompressed,
                }
            else:
                result["warnings"].append("metadata/bundle_integrity.json missing in legacy bundle")
                result["integrity"] = {
                    "bundle_id_recomputed": expected_bundle_id,
                    "hashes_verified": len(listed_sorted),
                    "entry_count": len(names),
                    "uncompressed_size": total_uncompressed,
                }
            result["ok"] = True
            result["bundle_id"] = str(manifest.get("bundle_id"))
            result["security"] = {
                "path_checks": "PASS",
                "duplicate_entries": "PASS",
                "symlink_entries": "PASS",
                "limits": "PASS",
                "secret_marker_count": len(result["secret_findings"]),
            }
            result["summary"] = {
                "source_files": len(listed_sorted),
                "metadata_files": len(metadata_names),
                "entries": len(names),
                "warnings": len(result["warnings"]),
                "legacy_schema": bool(result["legacy_schema"]),
            }
            result["_source_hashes"] = source_hashes
            result["_git_status_sha256"] = hashlib.sha256(zipf.read(f"{bundle_root}/metadata/git_status.txt")).hexdigest()
            result["_versions_sha256"] = hashlib.sha256(zipf.read(f"{bundle_root}/metadata/versions.json")).hexdigest()
            result["_categories"] = manifest.get("categories", {})
            return result
    except VerificationFailure as exc:
        result["ok"] = False
        result["warnings"].append(redact_text(str(exc)))
        return result
    except Exception as exc:
        raise RuntimeError(redact_text(f"{type(exc).__name__}: {exc}")) from exc


def compare_bundles(new_zip: Path, old_zip: Path, **limits: Any) -> dict[str, Any]:
    old = verify_bundle(old_zip, **limits)
    new = verify_bundle(new_zip, **limits)
    if not old.get("ok") or not new.get("ok"):
        raise VerificationFailure("cannot compare invalid bundle")
    old_hashes = old["_source_hashes"]
    new_hashes = new["_source_hashes"]
    old_paths = set(old_hashes)
    new_paths = set(new_hashes)
    metadata_changes: list[str] = []
    if old.get("_git_status_sha256") != new.get("_git_status_sha256"):
        metadata_changes.append("git_status")
    if old.get("_versions_sha256") != new.get("_versions_sha256"):
        metadata_changes.append("versions")
    if old.get("_categories") != new.get("_categories"):
        metadata_changes.append("manifest_categories")
    return {
        "mode": "audit_bundle_comparison",
        "version": VERIFIER_SCHEMA_VERSION,
        "old_bundle_id": old["bundle_id"],
        "new_bundle_id": new["bundle_id"],
        "added": sorted(new_paths - old_paths, key=str.lower),
        "modified": sorted((p for p in old_paths & new_paths if old_hashes[p] != new_hashes[p]), key=str.lower),
        "removed": sorted(old_paths - new_paths, key=str.lower),
        "unchanged": sorted((p for p in old_paths & new_paths if old_hashes[p] == new_hashes[p]), key=str.lower),
        "metadata_changes": sorted(metadata_changes),
        "summary": {
            "old_source_files": len(old_hashes),
            "new_source_files": len(new_hashes),
            "source_changes": len(new_paths - old_paths)
            + len(old_paths - new_paths)
            + sum(1 for p in old_paths & new_paths if old_hashes[p] != new_hashes[p]),
            "metadata_only": bool(metadata_changes)
            and old_hashes == new_hashes,
        },
    }


def _public(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if not key.startswith("_")}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify LocalComet audit bundle integrity.")
    parser.add_argument("bundle")
    parser.add_argument("--json", action="store_true", help="Emit stable JSON.")
    parser.add_argument("--compare", default=None, help="Previous bundle zip to compare against.")
    parser.add_argument("--max-entries", type=int, default=10000)
    parser.add_argument("--max-uncompressed-mb", type=float, default=500.0)
    parser.add_argument("--max-single-file-mb", type=float, default=10.0)
    parser.add_argument("--max-compression-ratio", type=float, default=100.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    limits = {
        "max_entries": args.max_entries,
        "max_uncompressed_mb": args.max_uncompressed_mb,
        "max_single_file_mb": args.max_single_file_mb,
        "max_compression_ratio": args.max_compression_ratio,
    }
    try:
        if args.compare:
            payload = compare_bundles(Path(args.bundle), Path(args.compare), **limits)
        else:
            payload = verify_bundle(Path(args.bundle), **limits)
        public = _public(payload)
        if args.json:
            print(json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            if public.get("ok", True):
                print(f"OK {public.get('bundle_id', public.get('new_bundle_id', 'comparison'))}")
            else:
                print("FAIL " + "; ".join(public.get("warnings", [])))
        return 0 if public.get("ok", True) else 1
    except VerificationFailure as exc:
        payload = {"mode": "audit_bundle_comparison", "version": VERIFIER_SCHEMA_VERSION, "ok": False, "warnings": [redact_text(str(exc))]}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("FAIL " + payload["warnings"][0])
        return 1
    except Exception as exc:
        message = redact_text(f"{type(exc).__name__}: {exc}")
        if args.json:
            print(json.dumps({"ok": False, "error": message}, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("ERROR " + message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
