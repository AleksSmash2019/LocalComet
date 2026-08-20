"""Regression tests for fail-closed sidecar mutation and Computer Use folders."""

import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.computer_use_real_actions_ru import open_folder, resolve_folder_path
from modules.tool_execution_ru import (
    ToolExecutionError,
    _files_create_folder,
    _files_delete,
    _resolve_public_fetch_target,
)
from modules.workspace_policy import make_policy


class ToolExecutionFailClosedTests(unittest.TestCase):
    def test_mutating_files_tools_do_not_touch_workspace(self):
        with tempfile.TemporaryDirectory() as workspace:
            policy = make_policy(workspace, session_id="a" * 64)
            candidate = Path(workspace) / "must-not-exist"
            with self.assertRaises(ToolExecutionError) as create_error:
                _files_create_folder(policy, "files.create_folder", {"path": str(candidate)})
            self.assertEqual(create_error.exception.code, "feature_disabled")
            self.assertFalse(candidate.exists())

            existing = Path(workspace) / "must-remain.txt"
            existing.write_text("keep", encoding="utf-8")
            with self.assertRaises(ToolExecutionError) as delete_error:
                _files_delete(policy, "files.delete", {"path": str(existing)})
            self.assertEqual(delete_error.exception.code, "feature_disabled")
            self.assertTrue(existing.exists())

    def test_unknown_folder_is_blocked_instead_of_falling_back_to_project_root(self):
        self.assertIsNone(resolve_folder_path("not-an-allowlisted-folder"))
        result = open_folder("not-an-allowlisted-folder", simulate=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "blocked")

    def test_web_fetch_pins_checked_public_dns_result(self):
        answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
        with patch("modules.tool_execution_ru.socket.getaddrinfo", return_value=answers):
            parsed, connect_ip = _resolve_public_fetch_target("https://example.test/path")
        self.assertEqual(parsed.hostname, "example.test")
        self.assertEqual(connect_ip, "93.184.216.34")

    def test_web_fetch_rejects_private_or_nonstandard_targets(self):
        private_answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]
        with patch("modules.tool_execution_ru.socket.getaddrinfo", return_value=private_answers):
            with self.assertRaises(ToolExecutionError) as private_error:
                _resolve_public_fetch_target("https://rebind.test/")
        self.assertEqual(private_error.exception.code, "policy_denied")
        with self.assertRaises(ToolExecutionError) as port_error:
            _resolve_public_fetch_target("https://example.test:8443/")
        self.assertEqual(port_error.exception.code, "policy_denied")


if __name__ == "__main__":
    unittest.main()
