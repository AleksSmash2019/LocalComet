from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BASE = "ee221944eca092580e333b804f4e408a89a0bc76"
PRODUCT_PATHS = (
    "desktop/localcomet-desktop/src",
    "desktop/localcomet-desktop/src-tauri/src",
    "modules/local_model_gateway_ru.py",
)

# Approved-by: operator, 2026-07-25
# Sources: eaf20ce (artifact_acquisition ×5), c0c57bf (files ×5),
# plus pre-existing commands from BASE ee221944.
# Additions: request_approval/execute_approved/set_workspace (INV-APPROVAL-001/002),
# run_tool_call (ADR-013) — approved by owner 2026-07-27.
ALLOWED_TAURI_COMMANDS = frozenset((
    "cancel_artifact_download",
    "control_plane_bootstrap",
    "control_plane_cancel_turn",
    "control_plane_close_session",
    "control_plane_create_session",
    "control_plane_create_thread",
    "control_plane_get_turn_status",
    "control_plane_start_mock_turn",
    "execute_approved",  # INV-APPROVAL-001/002 (security/invariants/invariants.toml)
    "files_capability_status",
    "forget_selected_file",
    "get_artifact_download_state",
    "knowledge_review_decision_create",
    "knowledge_review_get",
    "knowledge_review_list",
    "knowledge_review_refresh",
    "knowledge_review_snapshot",
    "knowledge_turn_decide",
    "knowledge_turn_preview",
    "list_approved_downloadable_artifacts",
    "list_selected_files",
    "managed_artifact_validation_status",
    "managed_installed_artifacts",
    "managed_model_catalog",
    "managed_model_readiness",
    "managed_runtime_catalog",
    "managed_runtime_logs",
    "managed_runtime_start",
    "managed_runtime_status",
    "managed_runtime_stop",
    "model_binding_set",
    "model_gateway_catalog",
    "model_gateway_list_models",
    "model_gateway_probe",
    "model_turn_cancel",
    "model_turn_start",
    "preview_selected_file",
    "remove_managed_model",
    "request_approval",  # INV-APPROVAL-001/002 (security/invariants/invariants.toml)
    "run_tool_call",     # ADR-013
    "select_files",
    "set_workspace",  # INV-APPROVAL-001/002 (security/invariants/invariants.toml)
    "start_approved_artifact_download",
))


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def added_product_lines() -> str:
    diff = git("diff", "--unified=0", f"{BASE}..HEAD", "--", *PRODUCT_PATHS)
    return "\n".join(
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


def _extract_tauri_command_names() -> set[str]:
    output = git(
        "grep", "-A2", "#\\[tauri::command\\]", "HEAD",
        "--", "desktop/localcomet-desktop/src-tauri/src",
    )
    names: set[str] = set()
    for line in output.splitlines():
        match = re.search(r"pub\s+(?:async\s+)?fn\s+([a-z_0-9]+)\s*\(", line)
        if match:
            names.add(match.group(1))
    return names


class SecurityNegativeTests(unittest.TestCase):
    def test_no_new_external_authority_api_is_added(self) -> None:
        additions = added_product_lines()
        forbidden = {
            "browser network": r"\bfetch\s*\(|XMLHttpRequest|WebSocket|EventSource|sendBeacon",
            "filesystem plugin": r"@tauri-apps/plugin-fs|\b(readFile|writeFile|readDir)\s*\(",
            "shell plugin": r"@tauri-apps/plugin-shell|Command::new|std::process::Command|std::process::exit|std::process::abort",
            "Python process": r"\bsubprocess\b|\bos\.system\s*\(",
            "external HTTP client": r"\brequests\.|\burllib\.|\bsmtplib\.|\bwebbrowser\.",
        }
        for label, pattern in forbidden.items():
            with self.subTest(label=label):
                self.assertIsNone(re.search(pattern, additions, re.IGNORECASE))
        self.assertIsNotNone(
            re.search(forbidden["shell plugin"], "std::process::Command"),
            "Regression: shell plugin pattern must still detect std::process::Command",
        )
        self.assertIsNotNone(
            re.search(forbidden["shell plugin"], "Command::new"),
            "Regression: shell plugin pattern must still detect Command::new",
        )
        self.assertIsNone(
            re.search(forbidden["shell plugin"], "std::process::id()"),
            "Regression: shell plugin pattern must not match std::process::id()",
        )

    def test_no_new_tauri_command_or_generic_raw_ipc_is_added(self) -> None:
        actual = _extract_tauri_command_names()
        unexpected = actual - ALLOWED_TAURI_COMMANDS
        self.assertEqual(set(), unexpected, f"Unapproved tauri commands: {sorted(unexpected)}")
        missing = ALLOWED_TAURI_COMMANDS - actual
        self.assertEqual(set(), missing, f"Allowlist entries not found in source: {sorted(missing)}")
        additions = added_product_lines()
        self.assertNotIn("invoke_raw", additions)
        self.assertNotIn("generic_ipc", additions)

    def test_frontend_cannot_supply_capabilities_or_system_instruction(self) -> None:
        bridge = (ROOT / "desktop/localcomet-desktop/src/lib/bridge/modelGateway.ts").read_text(encoding="utf-8")
        start = bridge.index("export async function startModelTurn")
        end = bridge.index("export async function cancelModelTurn", start)
        public_turn = bridge[start:end]
        self.assertIn("locale: AssistantLocale", public_turn)
        self.assertNotIn("assistantContext", public_turn)
        self.assertNotIn("systemInstruction", public_turn)

        rust = (ROOT / "desktop/localcomet-desktop/src-tauri/src/control_plane.rs").read_text(encoding="utf-8")
        command_start = rust.index("pub async fn model_turn_start(")
        signature_end = rust.index(") -> Result<Value, BridgeError>", command_start)
        signature = rust[command_start:signature_end]
        self.assertIn("locale: String", signature)
        self.assertNotIn("assistant_context", signature)
        self.assertNotIn("system_instruction", signature)

    def test_capability_defaults_are_explicit_and_fail_closed(self) -> None:
        rust = (ROOT / "desktop/localcomet-desktop/src-tauri/src/control_plane.rs").read_text(encoding="utf-8")
        for field in ("internet", "email", "browser", "filesystem", "vault", "computer_use", "shell"):
            self.assertIn(f"{field}: false", rust)
        self.assertIn("tools: Vec::new()", rust)
        gateway = (ROOT / "modules/local_model_gateway_ru.py").read_text(encoding="utf-8")
        self.assertIn("set(capabilities) != set(ASSISTANT_CONTEXT_CAPABILITY_KEYS)", gateway)
        self.assertIn('raise GatewayError("invalid_payload", "assistant context is not trusted")', gateway)

    def test_no_model_runtime_or_forbidden_executable_is_tracked(self) -> None:
        tracked = git("ls-files").splitlines()
        forbidden = [
            path
            for path in tracked
            if Path(path).suffix.lower() in {".gguf", ".exe", ".bat", ".ps1"}
        ]
        self.assertEqual([], forbidden)


if __name__ == "__main__":
    unittest.main()
