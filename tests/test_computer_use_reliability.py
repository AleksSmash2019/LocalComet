"""Hidden regression coverage for Computer Use reliability safeguards."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import computer_use_auto_action_ru as auto_actions
from modules import computer_use_real_actions_ru as real_actions
from modules.computer_use_real_actions_ru import build_real_action_plan, execute_real_action
from modules.computer_use_visual_guard_ru import classify_ui_markers


class ComputerUseReliabilityTests(unittest.TestCase):
    def test_russian_text_uses_unicode_sendinput_path_without_clipboard(self) -> None:
        original = auto_actions._send_unicode_text
        try:
            auto_actions._send_unicode_text = lambda text: {
                "ok": True,
                "executed": True,
                "primitive": "unicode_sendinput",
                "char_count": len(text),
                "clipboard_preserved": True,
            }
            result = auto_actions._pyautogui_execute({"kind": "type", "text": "Привет, мир"})
        finally:
            auto_actions._send_unicode_text = original
        self.assertTrue(result["ok"])
        self.assertEqual(result["primitive"], "unicode_sendinput")
        self.assertTrue(result["clipboard_preserved"])

    def test_normal_close_button_is_not_treated_as_a_modal_dialog(self) -> None:
        markers = classify_ui_markers({"elements": [{"role": "button", "name": "Закрыть"}]})
        self.assertFalse(markers["dialog_like"])
        self.assertFalse(markers["error_like"])

    def test_alert_dialog_with_error_is_detected(self) -> None:
        markers = classify_ui_markers({"elements": [{"role": "alertdialog", "name": "Ошибка подключения"}]})
        self.assertTrue(markers["dialog_like"])
        self.assertTrue(markers["error_like"])

    def test_basic_notepad_plan_stays_executable_in_hidden_simulation(self) -> None:
        plan = build_real_action_plan("открой блокнот и напиши Привет", max_steps=8)
        self.assertTrue(plan["ok"])
        self.assertIn("open_app", [item["kind"] for item in plan["actions"]])
        self.assertIn("paste_text", [item["kind"] for item in plan["actions"]])
        result = execute_real_action({"kind": "paste_text", "text": "Привет"}, simulate=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "simulated")

    def test_active_window_text_preserves_clipboard_when_executed(self) -> None:
        original = auto_actions._send_unicode_text
        try:
            auto_actions._send_unicode_text = lambda text: {
                "ok": True,
                "executed": True,
                "primitive": "unicode_sendinput",
                "char_count": len(text),
                "clipboard_preserved": True,
            }
            result = real_actions.paste_text("Привет", simulate=False)
        finally:
            auto_actions._send_unicode_text = original
        self.assertTrue(result["ok"])
        self.assertTrue(result["clipboard_preserved"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
