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


class SecurityNegativeTests(unittest.TestCase):
    def test_no_new_external_authority_api_is_added(self) -> None:
        additions = added_product_lines()
        forbidden = {
            "browser network": r"\bfetch\s*\(|XMLHttpRequest|WebSocket|EventSource|sendBeacon",
            "filesystem plugin": r"@tauri-apps/plugin-fs|\b(readFile|writeFile|readDir)\s*\(",
            "shell plugin": r"@tauri-apps/plugin-shell|Command::new|std::process",
            "Python process": r"\bsubprocess\b|\bos\.system\s*\(",
            "external HTTP client": r"\brequests\.|\burllib\.|\bsmtplib\.|\bwebbrowser\.",
        }
        for label, pattern in forbidden.items():
            with self.subTest(label=label):
                self.assertIsNone(re.search(pattern, additions, re.IGNORECASE))

    def test_no_new_tauri_command_or_generic_raw_ipc_is_added(self) -> None:
        current = git("grep", "-h", "#\\[tauri::command\\]", "HEAD", "--", "desktop/localcomet-desktop/src-tauri/src")
        predecessor = git("grep", "-h", "#\\[tauri::command\\]", BASE, "--", "desktop/localcomet-desktop/src-tauri/src")
        self.assertEqual(predecessor.count("#[tauri::command]"), current.count("#[tauri::command]"))
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
