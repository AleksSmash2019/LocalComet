"""Hidden, deterministic quality contracts for Computer Use fail-closed behavior."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.computer_use_real_actions_ru import (
    build_real_action_plan,
    open_app,
    paste_text,
    press_hotkey,
    resolve_folder_path,
)


class ComputerUseQualityContracts(unittest.TestCase):
    """Never operate the desktop: validate planner/executor decisions only."""

    def test_destructive_goal_is_blocked_before_any_action_is_emitted(self) -> None:
        plan = build_real_action_plan("удали все файлы в папке")
        self.assertFalse(plan["ok"])
        self.assertTrue(plan["blocked"])
        self.assertEqual(plan["reason"], "destructive_delete")
        self.assertEqual(plan["actions"], [])

    def test_terminal_goal_is_blocked_before_any_action_is_emitted(self) -> None:
        plan = build_real_action_plan("открой powershell и выполни команду")
        self.assertFalse(plan["ok"])
        self.assertTrue(plan["blocked"])
        self.assertEqual(plan["reason"], "terminal_admin")
        self.assertEqual(plan["actions"], [])

    def test_unknown_folder_has_no_default_workspace_fallback(self) -> None:
        self.assertIsNone(resolve_folder_path("C:\\Windows"))
        self.assertIsNone(resolve_folder_path("весь компьютер"))

    def test_unknown_application_is_blocked_without_launch_attempt(self) -> None:
        result = open_app("powershell", simulate=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "app is not allowlisted")

    def test_secret_text_requires_confirmation_even_in_hidden_simulation(self) -> None:
        result = paste_text("password=do-not-send", simulate=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "requires_confirmation")
        self.assertTrue(result["requires_confirmation"])

    def test_allowlisted_hotkey_is_simulated_without_visible_input(self) -> None:
        result = press_hotkey(["ctrl", "s"], simulate=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "simulated")
        self.assertEqual(result["keys"], ["ctrl", "s"])

    def test_plain_goal_uses_non_executing_grounded_fallback(self) -> None:
        plan = build_real_action_plan("разберись с открытым окном")
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["summary"]["real_actions"], 0)
        self.assertEqual(plan["actions"][0]["kind"], "delegate_multistep")
        self.assertFalse(plan["actions"][0]["real_action"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
