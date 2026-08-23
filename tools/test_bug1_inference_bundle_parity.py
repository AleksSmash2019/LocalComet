#!/usr/bin/env python
"""Regression guard for `invalid_payload: assistant conversation context is invalid`.

The Rust bridge and Python gateway deliberately use an exact, fail-closed
``assistant_context`` schema. Any unilateral Rust field addition rejects every
turn before the gateway reaches llama-server. This test:

  PART A - guards source parity: the Rust conversation struct must have the
           three canonical fields and the repo gateway must accept the exact
           payload serialized from that contract.
  PART B - verifies deployment parity: the deployed bundle gateway must accept
           the same payload. It fails if modules/ has drifted from source.

Run directly: python tools/test_bug1_inference_bundle_parity.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]

RUST_CONTROL_PLANE = (
    ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "src" / "control_plane.rs"
)
RUST_MANIFEST = RUST_CONTROL_PLANE.parents[1] / "Cargo.toml"
RUST_CONTRACT_PREFIX = "LOCALCOMET_ASSISTANT_CONTEXT_CONTRACT="

_SUBPROCESS_PROGRAM = (
    "import sys, json\n"
    "root = sys.argv[1]\n"
    "sys.path.insert(0, root)\n"
    "from modules.local_model_gateway_ru import _validate_assistant_context, GatewayError\n"
    "payload = json.load(sys.stdin)\n"
    "try:\n"
    "    _validate_assistant_context(payload)\n"
    "    print('ACCEPTED')\n"
    "except GatewayError as exc:\n"
    "    print('REJECTED:' + exc.code + ':' + exc.message)\n"
)


def validate_with_root(root: Path, payload: dict) -> str:
    """Run _validate_assistant_context from `root` in an isolated interpreter.

    Mirrors the sidecar runner: isolated mode plus sys.path.insert(0, root).
    Returns the single result line, e.g. 'ACCEPTED' or 'REJECTED:<code>:<msg>'.
    """
    completed = subprocess.run(
        [sys.executable, "-I", "-c", _SUBPROCESS_PROGRAM, str(root)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(root),
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"validator subprocess failed under {root}:\n{completed.stderr}"
        )
    return completed.stdout.strip().splitlines()[-1]


def rust_bridge_assistant_contexts() -> list[tuple[str, dict]]:
    env = os.environ.copy()
    if not env.get("CARGO_TARGET_DIR"):
        local_app_data = env.get("LOCALAPPDATA")
        target = (
            Path(local_app_data) / "LocalComet" / "BuildCache" / "CargoTarget"
            if local_app_data
            else Path(tempfile.gettempdir()) / "localcomet-cargo-target"
        )
        env["CARGO_TARGET_DIR"] = str(target)
    target = Path(env["CARGO_TARGET_DIR"]).resolve()
    assert not target.is_relative_to(ROOT.resolve()), (
        f"CARGO_TARGET_DIR must stay outside source: {target}"
    )
    completed = subprocess.run(
        [
            "cargo",
            "test",
            "--manifest-path",
            str(RUST_MANIFEST),
            "--lib",
            "assistant_context_contract_payloads_are_machine_readable",
            "--",
            "--nocapture",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0:
        raise RuntimeError(f"Rust assistant-context contract test failed:\n{output}")
    contract_lines = [
        line.split(RUST_CONTRACT_PREFIX, 1)[1]
        for line in output.splitlines()
        if RUST_CONTRACT_PREFIX in line
    ]
    assert len(contract_lines) == 1, "Rust assistant-context contract payload is missing"
    payloads = json.loads(contract_lines[0])
    assert isinstance(payloads, list) and payloads, "Rust assistant-context contract is empty"
    result: list[tuple[str, dict]] = []
    for item in payloads:
        assert isinstance(item, dict) and set(item) == {"case", "context"}
        assert isinstance(item["case"], str) and isinstance(item["context"], dict)
        result.append((item["case"], item["context"]))
    return result


def assert_binding_preserves_validation_cache() -> None:
    source = RUST_CONTROL_PLANE.read_text(encoding="utf-8")
    start = source.index("pub async fn model_binding_set(")
    end = source.index("#[tauri::command]", start + 1)
    binding_command = source[start:end]
    assert "invalidate_validation_cache" not in binding_command, (
        "A successful model binding must not evict the verified artifact hash; "
        "binding does not mutate model bytes and launch already force-validates them"
    )


def deployed_bundle_modules_dir() -> Path:
    override = os.environ.get("LOCALCOMET_BUNDLE_MODULES")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise RuntimeError("LOCALAPPDATA is not set; deployed runtime cannot be resolved")
    return Path(base) / "LocalCometDev" / "workspace" / "modules"


def check_source_parity(payloads: list[tuple[str, dict]]) -> None:
    for case, payload in payloads:
        result = validate_with_root(ROOT, payload)
        assert result == "ACCEPTED", (
            "PART A source parity broken: repo gateway rejected the exact Rust "
            f"bridge payload (case={case}): {result}"
        )
    print("PART A OK: repo gateway accepts the Rust bridge assistant_context")


def check_deployed_bundle(payloads: list[tuple[str, dict]]) -> bool:
    bundle_modules = deployed_bundle_modules_dir()
    if not bundle_modules.is_dir() or not (bundle_modules / "local_model_gateway_ru.py").is_file():
        print(
            "PART B FAIL: deployed bundle gateway not found under the supported "
            f"LocalCometDev runtime: {bundle_modules}"
        )
        return False
    bundle_root = bundle_modules.parent
    for case, payload in payloads:
        result = validate_with_root(bundle_root, payload)
        if result != "ACCEPTED":
            print(
                "PART B FAIL: deployed bundle gateway rejected the exact Rust "
                f"bridge payload (case={case}): {result}\n"
                f"  bundle: {bundle_modules / 'local_model_gateway_ru.py'}\n"
                "  Rebuild the app bundle so modules/ is refreshed from source."
            )
            return False
    print("PART B OK: deployed bundle gateway accepts the Rust bridge payloads")
    return True


def main() -> int:
    assert_binding_preserves_validation_cache()
    payloads = rust_bridge_assistant_contexts()
    check_source_parity(payloads)
    bundle_ok = check_deployed_bundle(payloads)
    if not bundle_ok:
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
