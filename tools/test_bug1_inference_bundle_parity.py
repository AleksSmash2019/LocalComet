#!/usr/bin/env python
"""Bug #1 reproduction: inference fails with `invalid_payload: assistant
conversation context is invalid`.

Root cause: the running desktop sidecar loads its gateway module from the
built app bundle (%LOCALAPPDATA%\\LocalComet\\DevRuntime\\cargo-target\\debug\\
app\\modules\\local_model_gateway_ru.py). That bundled copy is stale and
expects only two conversation keys {locale, project_context_available}, while
the Rust bridge (control_plane.rs AssistantContext::trusted) serializes three
{locale, project_context_available, selected_files_context_available}. The set
mismatch makes _validate_assistant_context reject every model turn.

The repository source is internally consistent (three keys on both the Rust and
Python sides); only the deployed bundle is out of sync. This test:

  PART A - guards source parity: the repo gateway must accept the exact payload
           the Rust bridge serializes. Passes today and must keep passing.
  PART B - reproduces the bug: the deployed bundle gateway must accept the same
           payload. Fails today (stale bundle) and passes once the app bundle is
           rebuilt so modules/ is refreshed from source.

Run directly: python tools/test_bug1_inference_bundle_parity.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]

APPLICATION_VERSION = "v6.84.6"

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


def rust_bridge_assistant_context(
    locale: str, selected_files_context_available: bool
) -> dict:
    """Mirror of control_plane.rs AssistantContext::trusted serialization."""
    return {
        "application": {
            "name": "LocalComet",
            "mode": "local_offline_desktop_assistant",
            "version": APPLICATION_VERSION,
        },
        "conversation": {
            "locale": locale,
            "project_context_available": False,
            "selected_files_context_available": selected_files_context_available,
        },
        "capabilities": {
            "local_chat": True,
            "local_model_inference": True,
            "internet": False,
            "email": False,
            "browser": False,
            "filesystem": False,
            "vault": False,
            "computer_use": False,
            "shell": False,
            "tools": [],
        },
    }


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


def deployed_bundle_modules_dir() -> Path | None:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    candidate = (
        Path(base)
        / "LocalComet"
        / "DevRuntime"
        / "cargo-target"
        / "debug"
        / "app"
        / "modules"
    )
    if (candidate / "local_model_gateway_ru.py").is_file():
        return candidate
    return None


def check_source_parity() -> None:
    for locale in ("ru", "en"):
        for selected in (False, True):
            payload = rust_bridge_assistant_context(locale, selected)
            result = validate_with_root(ROOT, payload)
            assert result == "ACCEPTED", (
                f"PART A source parity broken: repo gateway rejected the Rust "
                f"bridge payload (locale={locale}, selected_files={selected}): "
                f"{result}"
            )
    print("PART A OK: repo gateway accepts the Rust bridge assistant_context")


def check_deployed_bundle() -> bool:
    bundle_modules = deployed_bundle_modules_dir()
    if bundle_modules is None:
        print(
            "PART B SKIP: deployed bundle gateway not found under "
            "%LOCALAPPDATA%\\LocalComet\\DevRuntime; cannot reproduce the "
            "running-sidecar bug on this machine"
        )
        return True
    bundle_root = bundle_modules.parent
    payload = rust_bridge_assistant_context("ru", False)
    result = validate_with_root(bundle_root, payload)
    if result == "ACCEPTED":
        print("PART B OK: deployed bundle gateway accepts the Rust bridge payload")
        return True
    print(
        "PART B FAIL: deployed bundle gateway rejected the Rust bridge payload: "
        f"{result}\n"
        f"  bundle: {bundle_modules / 'local_model_gateway_ru.py'}\n"
        "  This reproduces Bug #1 (request_model_turn_reserved -> invalid_payload).\n"
        "  Fix: rebuild the app bundle so modules/ is refreshed from source, "
        "then restart the app."
    )
    return False


def main() -> int:
    check_source_parity()
    bundle_ok = check_deployed_bundle()
    if not bundle_ok:
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
