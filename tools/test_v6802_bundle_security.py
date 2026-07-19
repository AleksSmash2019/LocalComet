#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Callable


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.project_audit_bundle_ru import _json_bytes, create_audit_bundle
from tools.verify_project_audit_bundle import compare_bundles, verify_bundle


SECRET_VALUE = "sk-" + "v6802secretfixture000000"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture(extra: dict[str, str] | None = None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="localcomet_v6802_fixture_"))
    manifest = {
        "release": "v6.80.2",
        "entrypoints": ["main.py"],
        "runtime": ["modules/runtime.py"],
        "lazy_runtime": [],
        "tests": [],
        "tools": [],
    }
    _write(root / "localcomet_runtime_manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(root / "main.py", "import modules.runtime\nprint('hello')\n")
    _write(root / "modules" / "runtime.py", "VALUE = 'one'\n")
    for rel, text in (extra or {}).items():
        _write(root / rel, text)
    return root


def _bundle(root: Path) -> Path:
    return Path(create_audit_bundle(root=root, skip_tests=True, deterministic=True)["zip_path"])


def _root_name(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path, "r") as zipf:
        return zipf.namelist()[0].split("/")[0]


def _read_json(zip_path: Path, suffix: str):
    with zipfile.ZipFile(zip_path, "r") as zipf:
        names = [name for name in zipf.namelist() if name.endswith(suffix)]
        _assert(len(names) == 1, f"Expected {suffix}")
        return json.loads(zipf.read(names[0]).decode("utf-8"))


def _rewrite_zip(src: Path, mutator: Callable[[str, bytes, zipfile.ZipInfo], tuple[str, bytes, zipfile.ZipInfo] | None], duplicate: tuple[str, bytes] | None = None) -> Path:
    dst = Path(tempfile.mkdtemp(prefix="localcomet_v6802_zip_")) / "tampered.zip"
    with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            changed = mutator(info.filename, data, info)
            if changed is None:
                continue
            name, payload, old_info = changed
            new_info = zipfile.ZipInfo(name)
            new_info.date_time = old_info.date_time
            new_info.compress_type = zipfile.ZIP_DEFLATED
            new_info.external_attr = old_info.external_attr
            zout.writestr(new_info, payload)
        if duplicate is not None:
            zout.writestr(duplicate[0], duplicate[1])
    return dst


def _with_integrity_update(src: Path, replacements: dict[str, bytes]) -> Path:
    root = _root_name(src)

    def mutate(name: str, data: bytes, info: zipfile.ZipInfo):
        logical = name[len(root) + 1 :] if name.startswith(root + "/") else name
        if logical in replacements:
            data = replacements[logical]
        if logical == "metadata/bundle_integrity.json":
            integrity = json.loads(data.decode("utf-8"))
            entry_hashes = integrity["entry_sha256"]
            for rel, payload in replacements.items():
                if rel != "metadata/bundle_integrity.json":
                    entry_hashes[rel] = hashlib.sha256(payload).hexdigest()
            data = _json_bytes(integrity)
        return name, data, info

    return _rewrite_zip(src, mutate)


def _manifest_bytes_with(zip_path: Path, update: Callable[[dict], None]) -> bytes:
    manifest = _read_json(zip_path, "/metadata/bundle_manifest.json")
    update(manifest)
    return _json_bytes(manifest)


def _verify_false(zip_path: Path, **kwargs) -> dict:
    result = verify_bundle(zip_path, **kwargs)
    _assert(result["ok"] is False, "Tampered bundle unexpectedly verified.")
    return result


def test_valid_bundle_and_tamper_detection() -> None:
    root = _fixture()
    try:
        bundle = _bundle(root)
        valid = verify_bundle(bundle)
        _assert(valid["ok"] is True, "Valid bundle did not verify.")

        changed = _rewrite_zip(
            bundle,
            lambda n, d, i: (n, b"tampered\n", i) if n.endswith("/source/main.py") else (n, d, i),
        )
        _assert(_verify_false(changed)["hash_mismatches"], "Modified source did not cause hash failure.")

        missing = _rewrite_zip(bundle, lambda n, d, i: None if n.endswith("/source/main.py") else (n, d, i))
        _assert(_verify_false(missing)["missing"], "Missing source entry not detected.")

        root_name = _root_name(bundle)
        unexpected = _rewrite_zip(bundle, lambda n, d, i: (n, d, i), (f"{root_name}/source/unexpected.py", b"x"))
        _assert(_verify_false(unexpected)["unexpected"], "Unexpected source entry not detected.")

        duplicate = _rewrite_zip(bundle, lambda n, d, i: (n, d, i), (f"{root_name}/source/main.py", b"x"))
        _assert("duplicate" in " ".join(_verify_false(duplicate)["warnings"]).lower(), "Duplicate entry not rejected.")

        legacy = _rewrite_zip(bundle, lambda n, d, i: None if n.endswith("/metadata/bundle_integrity.json") else (n, d, i))
        legacy_result = verify_bundle(legacy)
        _assert(legacy_result["ok"] is True, "Legacy bundle without integrity metadata did not verify.")
        _assert(legacy_result["legacy_schema"] is True, "Legacy schema flag missing.")
        _assert(legacy_result["warnings"], "Legacy schema warning missing.")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_archive_path_and_schema_rejections() -> None:
    root = _fixture()
    try:
        bundle = _bundle(root)
        root_name = _root_name(bundle)
        cases = [
            (f"/{root_name}/source/abs.py", b"x", "absolute"),
            (f"{root_name}/source/../escape.py", b"x", "traversal"),
            (f"{root_name}\\source\\evil.py", b"x", "backslash"),
        ]
        for name, payload, marker in cases:
            tampered = _rewrite_zip(bundle, lambda n, d, i: (n, d, i), (name, payload))
            _assert(marker in " ".join(_verify_false(tampered)["warnings"]).lower() or marker == "backslash", f"{marker} path accepted.")

        symlink = Path(tempfile.mkdtemp(prefix="localcomet_v6802_symlink_")) / "symlink.zip"
        with zipfile.ZipFile(bundle, "r") as zin, zipfile.ZipFile(symlink, "w") as zout:
            for info in zin.infolist():
                zout.writestr(info, zin.read(info.filename))
            info = zipfile.ZipInfo(f"{root_name}/source/link.py")
            info.external_attr = (0o120777 << 16)
            zout.writestr(info, b"target")
        _assert("symlink" in " ".join(_verify_false(symlink)["warnings"]).lower(), "Symlink entry accepted.")

        malformed = _rewrite_zip(
            bundle,
            lambda n, d, i: (n, b"{bad json", i) if n.endswith("/metadata/bundle_manifest.json") else (n, d, i),
        )
        _assert("malformed json" in " ".join(_verify_false(malformed)["warnings"]).lower(), "Malformed manifest accepted.")

        wrong_id = _with_integrity_update(
            bundle,
            {"metadata/bundle_manifest.json": _manifest_bytes_with(bundle, lambda m: m.__setitem__("bundle_id", "0" * 16))},
        )
        _assert("bundle_id" in " ".join(_verify_false(wrong_id)["warnings"]).lower(), "Wrong bundle_id accepted.")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_secret_detection_and_limits() -> None:
    root = _fixture()
    try:
        bundle = _bundle(root)
        secret_zip = _with_integrity_update(bundle, {"README_AUDIT.md": f"marker {SECRET_VALUE}\n".encode("utf-8")})
        result = verify_bundle(secret_zip)
        _assert(result["ok"] is True, "Secret marker scan should not corrupt integrity.")
        _assert(any(item["category"] == "openai_api_key" for item in result["secret_findings"]), "Secret marker not detected.")

        completed = subprocess.run(
            [sys.executable, "tools/verify_project_audit_bundle.py", str(secret_zip), "--json"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        combined = completed.stdout + completed.stderr
        _assert(completed.returncode == 0, "Secret marker bundle should verify with findings.")
        _assert(SECRET_VALUE not in combined, "Secret value leaked in verifier output.")
        parsed = json.loads(completed.stdout)
        _assert(SECRET_VALUE not in json.dumps(parsed), "Secret value leaked in JSON payload.")

        _verify_false(bundle, max_single_file_mb=0.0001)
        _verify_false(bundle, max_uncompressed_mb=0.0001)

        ratio_zip = _rewrite_zip(
            bundle,
            lambda n, d, i: (n, d, i),
            (_root_name(bundle) + "/metadata/ratio.txt", b"A" * 200000),
        )
        _assert("compression" in " ".join(_verify_false(ratio_zip, max_compression_ratio=2)["warnings"]).lower(), "Compression ratio guard did not trigger.")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_compare_and_determinism_no_repo_writes() -> None:
    before = _repo_snapshot()
    old_root = _fixture({"old_only.py": "print('old')\n"})
    new_root = _fixture({"new_only.py": "print('new')\n"})
    try:
        _write(new_root / "main.py", "print('modified')\n")
        old_bundle = _bundle(old_root)
        new_bundle = _bundle(new_root)
        comparison = compare_bundles(new_bundle, old_bundle)
        _assert("new_only.py" in comparison["added"], "Compare missed added source.")
        _assert("main.py" in comparison["modified"], "Compare missed modified source.")
        _assert("old_only.py" in comparison["removed"], "Compare missed removed source.")
        _assert("modules/runtime.py" in comparison["unchanged"], "Compare missed unchanged source.")

        metadata_only = _with_integrity_update(new_bundle, {"metadata/git_status.txt": b"metadata changed\n"})
        metadata_comparison = compare_bundles(metadata_only, new_bundle)
        _assert(metadata_comparison["summary"]["metadata_only"] is True, "Metadata-only change not separated.")
        _assert("git_status" in metadata_comparison["metadata_changes"], "Git metadata change not reported.")

        invalid_previous = _rewrite_zip(old_bundle, lambda n, d, i: (n, b"x", i) if n.endswith("/source/main.py") else (n, d, i))
        try:
            compare_bundles(new_bundle, invalid_previous)
        except Exception:
            pass
        else:
            raise AssertionError("Invalid previous bundle was compared.")

        repeat_one = _bundle(new_root)
        sha_one = hashlib.sha256(repeat_one.read_bytes()).hexdigest()
        repeat_two = _bundle(new_root)
        sha_two = hashlib.sha256(repeat_two.read_bytes()).hexdigest()
        _assert(_read_json(repeat_one, "/metadata/bundle_manifest.json")["bundle_id"] == _read_json(repeat_two, "/metadata/bundle_manifest.json")["bundle_id"], "Repeated bundle IDs differ.")
        _assert(sha_one == sha_two, "Repeated deterministic ZIP hashes differ.")

        after = _repo_snapshot()
        _assert(before == after, "Verification/comparison created source-repo files.")
    finally:
        shutil.rmtree(old_root, ignore_errors=True)
        shutil.rmtree(new_root, ignore_errors=True)


def _repo_snapshot() -> str:
    items: dict[str, str] = {}
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(".git/") or "__pycache__" in rel:
            continue
        if path.is_file():
            try:
                items[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                items[rel] = "<unreadable>"
    return hashlib.sha256(json.dumps(items, sort_keys=True).encode("utf-8")).hexdigest()


def test_previous_suites_and_staging() -> None:
    commands = [
        [sys.executable, "tools/test_v677_regression.py"],
        [sys.executable, "tools/test_v678_router_registry.py"],
        [sys.executable, "tools/test_v679_retention.py"],
        [sys.executable, "tools/test_v6801_audit_bundle.py"],
    ]
    optional = ROOT / "tools" / "test_v680_reproducibility.py"
    if optional.exists():
        commands.insert(3, [sys.executable, "tools/test_v680_reproducibility.py"])
    for command in commands:
        completed = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=180, check=False)
        _assert(completed.returncode == 0, f"Regression failed: {' '.join(command)}\n{completed.stdout}\n{completed.stderr}")
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _assert(staged.returncode == 0 and staged.stdout.strip() == "", "Staged files are present.")


def main() -> None:
    tests = [
        test_valid_bundle_and_tamper_detection,
        test_archive_path_and_schema_rejections,
        test_secret_detection_and_limits,
        test_compare_and_determinism_no_repo_writes,
        test_previous_suites_and_staging,
    ]
    for test in tests:
        start = time.perf_counter()
        test()
        print(f"PASS {test.__name__} {time.perf_counter() - start:.3f}s")
    print("ALL v6.80.2 BUNDLE SECURITY TESTS PASSED")


if __name__ == "__main__":
    main()
