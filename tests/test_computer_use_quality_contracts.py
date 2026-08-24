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
    run_bounded_interaction_task,
    paste_text,
    press_hotkey,
    resolve_folder_path,
)
from modules.local_model_gateway_ru import _deterministic_computer_use_call


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
        result = press_hotkey(["ctrl", "f"], simulate=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "simulated")
        self.assertEqual(result["keys"], ["ctrl", "f"])

    def test_non_allowlisted_hotkey_is_blocked_even_in_simulation(self) -> None:
        # ctrl+s (save file) is deliberately outside the allowlist: the unified
        # hotkey policy applies at the execution primitive for every caller,
        # and simulation must reflect what real execution would do.
        result = press_hotkey(["ctrl", "s"], simulate=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "blocked")
        self.assertIn("allowlist", result["reason"])

    def test_mission_hotkey_delegates_to_the_shared_allowlist(self) -> None:
        # The mission module must not keep a private keybd_event path: its
        # hotkey executor delegates to the shared primitive, so the same
        # allowlist verdicts apply to mission plans.
        from modules.computer_use_full_control_mission_ru import _press_hotkey

        blocked = _press_hotkey(["ctrl", "s"], simulate=True)
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("allowlist", blocked["reason"])

        allowed = _press_hotkey(["ctrl", "f"], simulate=True)
        self.assertTrue(allowed["ok"])
        self.assertEqual(allowed["status"], "simulated")

    def test_natural_key_and_hotkey_prompts_do_not_fall_into_click(self) -> None:
        key = _deterministic_computer_use_call("Нажми Enter и сообщи результат.")
        self.assertEqual(key["arguments"], {"action": "key", "text": "enter"})

        hotkey = _deterministic_computer_use_call("Нажми Ctrl+F и сообщи результат.")
        self.assertEqual(hotkey["arguments"], {"action": "hotkey", "text": "ctrl+f"})

    def test_natural_click_prompt_strips_button_prefix_and_status_tail(self) -> None:
        click = _deterministic_computer_use_call("Кликни по кнопке Пуск и сообщи, что произошло.")
        self.assertEqual(click["arguments"], {"action": "click", "target": "Пуск"})

    def test_natural_paste_and_double_click_prompts_map_to_narrow_actions(self) -> None:
        paste = _deterministic_computer_use_call("Вставь текст: LocalComet paste smoke.")
        self.assertEqual(paste["arguments"], {"action": "paste", "text": "LocalComet paste smoke"})

        double_click = _deterministic_computer_use_call("Двойной клик по кнопке Чат и сообщи результат.")
        self.assertEqual(double_click["arguments"], {"action": "double_click", "target": "Чат"})

        drag = _deterministic_computer_use_call("Перетащи курсор из точки 100,100 в точку 200,200.")
        self.assertEqual(drag["arguments"], {"action": "drag", "coordinate": [100, 100, 200, 200]})
        self.assertIsNone(_deterministic_computer_use_call("Перетащи объект в безопасное место."))

    def test_compound_prompt_maps_to_bounded_task(self) -> None:
        from modules.local_model_gateway_ru import _deterministic_computer_use_call

        result = _deterministic_computer_use_call(
            "Кликни по кнопке Поиск, затем введи в поле Поиск текст hello."
        )
        self.assertEqual(result["arguments"]["action"], "task")
        self.assertIn("goal", result["arguments"])
        self.assertEqual(result["arguments"]["max_steps"], 6)

    def test_bounded_task_simulation_is_finite_without_gui_side_effects(self) -> None:
        result = run_bounded_interaction_task(
            "Нажми Ctrl+F и прокрути вниз.", simulate=True, max_steps=6
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["verification"], "not_applicable")
        self.assertEqual(result["completed_steps"], 2)
        self.assertLessEqual(result["total_steps"], 6)

    def test_bounded_task_refuses_launch_and_requires_host_broker(self) -> None:
        result = run_bounded_interaction_task(
            "Открой блокнот и нажми Enter.", simulate=True, max_steps=6
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])
        self.assertTrue(result["requires_host_broker_step"])
        self.assertEqual(result["next_host_action"]["kind"], "open_app")

    def test_plain_goal_uses_non_executing_grounded_fallback(self) -> None:
        plan = build_real_action_plan("разберись с открытым окном")
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["summary"]["real_actions"], 0)
        self.assertEqual(plan["actions"][0]["kind"], "delegate_multistep")
        self.assertFalse(plan["actions"][0]["real_action"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
