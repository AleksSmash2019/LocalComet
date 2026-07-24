#!/usr/bin/env python
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.project_audit_bundle_ru import create_audit_bundle


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture() -> Path:
    root = Path(tempfile.mkdtemp(prefix="localcomet_v6801_fixture_"))
    manifest = {
        "release": "v6.80.1",
        "entrypoints": ["main.py"],
        "runtime": ["modules/runtime.py"],
        "lazy_runtime": [],
        "tests": [],
        "tools": [],
    }
    _write(root / "localcomet_runtime_manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(root / "main.py", "import modules.runtime\nprint('hello')\n")
    _write(root / "modules" / "runtime.py", "VALUE = 'one'\n")
    return root


def _read_json(zip_path: Path, suffix: str):
    with zipfile.ZipFile(zip_path, "r") as zipf:
        names = [name for name in zipf.namelist() if name.endswith(suffix)]
        _assert(len(names) == 1, f"Expected exactly one {suffix}")
        return json.loads(zipf.read(names[0]).decode("utf-8"))


def test_bundle_creation_and_determinism() -> None:
    root = _fixture()
    try:
        result = create_audit_bundle(root=root, skip_tests=True, deterministic=True)
        zip_path = Path(result["zip_path"])
        _assert(zip_path.is_file(), "Bundle zip was not created.")
        _assert(result["bundle_id"], "Bundle ID is empty.")

        manifest = _read_json(zip_path, "/metadata/bundle_manifest.json")
        _assert(manifest.get("hash_algorithm") == "sha256", "Hash algorithm is not sha256.")
        _assert(isinstance(manifest.get("files"), list) and len(manifest["files"]) > 0, "Manifest files list is empty.")

        result_two = create_audit_bundle(root=root, skip_tests=True, deterministic=True)
        zip_two = Path(result_two["zip_path"])
        _assert(
            zip_path.read_bytes() == zip_two.read_bytes(),
            "Deterministic bundles differ.",
        )
        _assert(result["bundle_id"] == result_two["bundle_id"], "Deterministic bundle IDs differ.")
        zip_two.unlink(missing_ok=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_bundle_verification() -> None:
    root = _fixture()
    try:
        result = create_audit_bundle(root=root, skip_tests=True, deterministic=True)
        zip_path = Path(result["zip_path"])

        sys.path.insert(0, str(ROOT / "tools"))
        import verify_project_audit_bundle as verifier

        report = verifier.verify_bundle(zip_path)
        _assert(report["ok"] is True, f"Verification failed: {report.get('warnings', [])}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> None:
    tests = [
        test_bundle_creation_and_determinism,
        test_bundle_verification,
    ]
    for test in tests:
        start = time.perf_counter()
        test()
        print(f"PASS {test.__name__} {time.perf_counter() - start:.3f}s")
    print("ALL v6.80.1 AUDIT BUNDLE TESTS PASSED")


if __name__ == "__main__":
    main()
