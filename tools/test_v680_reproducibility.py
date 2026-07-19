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
from pathlib import Path


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _paths_under(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    result: dict[str, str] = {}
    ignored_prefixes = (
        ".incident_backup/",
        ".localcomet/",
        ".tmp/",
        "Projects/Reports/",
        "Projects/ComputerUse/",
        "Projects/ChatGPTRelay/",
    )
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        if ".git/" in rel or "__pycache__" in rel:
            continue
        if any(rel.startswith(prefix) for prefix in ignored_prefixes):
            continue
        if path.is_file():
            result[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture(extra_manifest: dict | None = None, extra_files: dict[str, str] | None = None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="localcomet_v680_preflight_"))
    manifest = {
        "release": "fixture",
        "project": "LocalComet / LocalAgent",
        "entrypoints": ["main.py"],
        "runtime": ["modules/runtime.py"],
        "lazy_runtime": ["modules/lazy.py"],
        "tests": ["tools/test_fixture.py"],
        "tools": ["tools/tool.py"],
    }
    if extra_manifest:
        manifest.update(extra_manifest)
    _write(root / "localcomet_runtime_manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write(root / "main.py", "import modules.runtime\n")
    _write(root / "modules" / "runtime.py", "VALUE = 1\n")
    _write(root / "modules" / "lazy.py", "from modules import runtime\n")
    _write(root / "tools" / "tool.py", "print('tool')\n")
    _write(root / "tools" / "test_fixture.py", "print('test')\n")
    for rel, text in (extra_files or {}).items():
        _write(root / rel, text)
    return root


def test_import_and_root_precedence_are_read_only() -> None:
    before = _paths_under(ROOT)
    import modules.repository_preflight_ru as preflight

    after = _paths_under(ROOT)
    _assert(before == after, "Import created or modified source files.")
    with tempfile.TemporaryDirectory(prefix="localcomet_v680_root_") as temp_text:
        temp_root = Path(temp_text) / "root"
        fallback_root = Path(temp_text) / "fallback"
        os.environ["LOCALCOMET_ROOT"] = str(temp_root)
        os.environ["LOCALCOMET_ROOT_DIR"] = str(fallback_root)
        _assert(preflight.resolve_project_root() == temp_root.resolve(), "LOCALCOMET_ROOT precedence failed.")
        os.environ.pop("LOCALCOMET_ROOT", None)
        _assert(preflight.resolve_project_root() == fallback_root.resolve(), "LOCALCOMET_ROOT_DIR precedence failed.")
        before_missing = _paths_under(Path(temp_text))
        result = preflight.run_repository_preflight(fallback_root)
        after_missing = _paths_under(Path(temp_text))
        _assert(before_missing == after_missing, "Missing root preflight wrote files.")
        _assert(result["ok"] is False, "Missing root should not pass.")
        os.environ.pop("LOCALCOMET_ROOT_DIR", None)


def test_real_manifest_static_preflight() -> None:
    import modules.repository_preflight_ru as preflight

    manifest = preflight.load_runtime_manifest(ROOT)
    for key in ("entrypoints", "runtime", "lazy_runtime", "tests", "tools"):
        _assert(key in manifest and isinstance(manifest[key], list), f"Manifest key missing: {key}")
        _assert(manifest[key] == sorted(manifest[key], key=str.lower), f"Manifest list not sorted: {key}")
        _assert(len(manifest[key]) == len(set(manifest[key])), f"Manifest list not unique: {key}")
        for rel in manifest[key]:
            normalized, reason = preflight._safe_rel_path(rel)
            _assert(reason is None and normalized == rel.replace("\\", "/"), f"Unsafe manifest path: {rel}")
    result = preflight.run_repository_preflight(ROOT)
    _assert(result["summary"]["missing_count"] == 0, "Required manifest files are missing.")
    _assert(result["summary"]["syntax_error_count"] == 0, "Python syntax errors found.")
    _assert(result["summary"]["unresolved_import_count"] == 0, "Required local imports unresolved.")
    text = json.dumps(result, ensure_ascii=False, sort_keys=True)
    _assert(str(Path.home()) not in text and str(ROOT) not in text, "Root/user path leaked.")


def test_synthetic_failures_are_reported_safely() -> None:
    import modules.repository_preflight_ru as preflight

    secret_value = "sk-" + "syntheticpreflightsecret000"
    root = _fixture(
        extra_manifest={
            "runtime": ["../escape.py", "modules/missing.py", "modules/runtime.py", "modules/secret.py"],
        },
        extra_files={
            "modules/secret.py": f"API_TOKEN = '{secret_value}'\nPATH_HINT = 'C:\\\\Users\\\\Example\\\\LocalAgent'\n",
        },
    )
    try:
        result = preflight.run_repository_preflight(root)
        _assert(result["ok"] is False, "Synthetic invalid manifest passed.")
        _assert(result["unsafe_paths"], "Traversal path was not rejected.")
        _assert(result["missing"], "Missing runtime file was not reported.")
        _assert(result["secret_markers"], "Secret category missing.")
        _assert(any(item["category"].startswith("windows") for item in result["machine_paths"]), "Machine path missing.")
        text = json.dumps(result, ensure_ascii=False, sort_keys=True)
        _assert(secret_value not in text, "Secret value leaked.")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_cli_output_and_determinism() -> None:
    root = _fixture()
    try:
        before_root = _paths_under(ROOT)
        before_fixture = _paths_under(root)
        command = [sys.executable, str(ROOT / "tools" / "localcomet_preflight_audit.py"), "--root", str(root), "--json"]
        first = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", check=False)
        second = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", check=False)
        _assert(first.returncode == 0, first.stderr)
        _assert(json.loads(first.stdout) == json.loads(second.stdout), "Preflight JSON is not deterministic.")
        _assert(before_root == _paths_under(ROOT), "CLI without --output wrote to source repo.")
        _assert(before_fixture == _paths_under(root), "CLI without --output wrote to fixture.")

        output_path = Path(tempfile.mkdtemp(prefix="localcomet_v680_output_")) / "preflight.json"
        with_output = subprocess.run(
            [*command, "--output", str(output_path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        _assert(with_output.returncode == 0, with_output.stderr)
        _assert(output_path.exists(), "--output did not write requested file.")
        _assert(before_root == _paths_under(ROOT), "CLI --output wrote to source repo.")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_clean_temp_copy_passes_without_source_access() -> None:
    import modules.repository_preflight_ru as preflight

    root = _fixture()
    try:
        before_source = _paths_under(ROOT)
        result = preflight.run_repository_preflight(root)
        after_source = _paths_under(ROOT)
        _assert(result["ok"] is True, "Clean temp-copy preflight failed.")
        _assert(before_source == after_source, "Temp-copy preflight touched source repo.")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_previous_suites_and_staging() -> None:
    commands = [
        [sys.executable, "tools/test_v677_regression.py"],
        [sys.executable, "tools/test_v678_router_registry.py"],
        [sys.executable, "tools/test_v679_retention.py"],
        [sys.executable, "tools/test_v6801_audit_bundle.py"],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240, check=False)
        _assert(completed.returncode == 0, f"Regression failed: {' '.join(command)}")
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _assert(staged.returncode == 0 and staged.stdout.strip() == "", "Staged files are present.")


def main() -> None:
    tests = [
        test_import_and_root_precedence_are_read_only,
        test_real_manifest_static_preflight,
        test_synthetic_failures_are_reported_safely,
        test_cli_output_and_determinism,
        test_clean_temp_copy_passes_without_source_access,
        test_previous_suites_and_staging,
    ]
    for test in tests:
        start = time.perf_counter()
        test()
        print(f"PASS {test.__name__} {time.perf_counter() - start:.3f}s")
    print("ALL v6.80 REPRODUCIBILITY TESTS PASSED")


if __name__ == "__main__":
    main()
