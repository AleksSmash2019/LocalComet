"""Deterministic bounded-task contract tests (CU-TASK-01) and launch->readiness->type
ordering contract (CU-CONTINUATION-01).

No GUI, no hidden desktop, no process spawn: planner/executor/boundary
decisions only, with faked step execution where a real desktop would be
required.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.computer_use_real_actions_ru import build_real_action_plan, run_bounded_interaction_task
from modules import tool_execution_ru as tool_exec
from modules.local_model_gateway_ru import validate_tool_call, GatewayError


BROWSER_GOAL = "Открой браузер и найди официальный сайт Python. Ничего не отправляй и не заполняй формы."


class BoundedTaskContractTests(unittest.TestCase):
    """CU-TASK-01: max 8 steps, goal <= 1200 chars, stop conditions,
    host-broker non-bypass — at every boundary layer."""

    # --- goal/max_steps boundaries --------------------------------------

    def test_gateway_goal_boundary_1200_ok_1201_rejected(self) -> None:
        validate_tool_call("computer_use", {"action": "task", "goal": "x" * 1200, "max_steps": 6})
        with self.assertRaises(GatewayError) as cm:
            validate_tool_call("computer_use", {"action": "task", "goal": "x" * 1201, "max_steps": 6})
        self.assertEqual(cm.exception.code, "invalid_payload")
        self.assertIn("1200", cm.exception.message)

    def test_gateway_max_steps_boundary_1_8(self) -> None:
        validate_tool_call("computer_use", {"action": "task", "goal": "g", "max_steps": 1})
        validate_tool_call("computer_use", {"action": "task", "goal": "g", "max_steps": 8})
        for bad in (0, 9, True, 2.5):
            with self.assertRaises(GatewayError):
                validate_tool_call("computer_use", {"action": "task", "goal": "g", "max_steps": bad})

    def test_tool_execution_boundary_rejects_out_of_contract(self) -> None:
        cases = [
            {"action": "task", "goal": "g", "max_steps": 9},
            {"action": "task", "goal": "x" * 1201, "max_steps": 6},
            {"action": "task", "goal": "", "max_steps": 6},
            {"action": "task", "goal": "g", "max_steps": True},
        ]
        for input_obj in cases:
            with self.assertRaises(tool_exec.ToolExecutionError, msg=repr(input_obj)):
                tool_exec._computer_use(None, "computer_use", input_obj, request_id="a", action_id="b")

    def test_tool_execution_dispatches_in_contract_max_steps_8(self) -> None:
        captured: dict = {}

        def fake_execute(dispatched, simulate=False):
            captured.update(dispatched)
            return {"ok": True, "status": "executed", "verification": "not_applicable", "mode": "computer_use_real_task"}

        with patch("modules.computer_use_real_actions_ru.execute_real_action", side_effect=fake_execute):
            tool_exec._computer_use(
                None,
                "computer_use",
                {"action": "task", "goal": "Нажми Ctrl+F и прокрути вниз.", "max_steps": 8},
                request_id="a",
                action_id="b",
            )
        self.assertEqual(captured["kind"], "task")
        self.assertEqual(captured["max_steps"], 8)

    def test_executor_rejects_out_of_contract_max_steps(self) -> None:
        for bad in (0, 9, True, 2.5, "6"):
            res = run_bounded_interaction_task("Нажми Ctrl+F.", simulate=True, max_steps=bad)
            self.assertFalse(res["ok"], msg=repr(bad))
            self.assertEqual(res["status"], "blocked")
            self.assertTrue(res["terminal"])
            self.assertEqual(res["steps"], [])

    # --- stop conditions -------------------------------------------------

    def test_stop_on_step_requires_confirmation(self) -> None:
        with patch(
            "modules.computer_use_real_actions_ru.execute_real_action",
            return_value={"ok": False, "status": "requires_confirmation", "requires_confirmation": True, "reason": "file change requires confirmation"},
        ):
            res = run_bounded_interaction_task("Нажми Ctrl+F и прокрути вниз.", simulate=True, max_steps=6)
        self.assertEqual(res["status"], "blocked")
        self.assertTrue(res["terminal"])
        self.assertEqual(res["completed_steps"], 0)
        self.assertIn("requires confirmation", res["reason"])

    def test_stop_on_step_blocked_status(self) -> None:
        with patch(
            "modules.computer_use_real_actions_ru.execute_real_action",
            return_value={"ok": False, "status": "blocked", "reason": "app is not allowlisted"},
        ):
            res = run_bounded_interaction_task("Нажми Ctrl+F и прокрути вниз.", simulate=True, max_steps=6)
        self.assertEqual(res["status"], "blocked")
        self.assertTrue(res["terminal"])
        self.assertEqual(res["completed_steps"], 0)

    def test_stop_on_step_failure(self) -> None:
        with patch(
            "modules.computer_use_real_actions_ru.execute_real_action",
            return_value={"ok": False, "status": "failed", "reason": "no structured UIA evidence"},
        ):
            res = run_bounded_interaction_task("Нажми Ctrl+F и прокрути вниз.", simulate=True, max_steps=6)
        self.assertEqual(res["status"], "failed")
        self.assertTrue(res["terminal"])
        self.assertIn("no structured UIA evidence", res["reason"])

    def _real_mode_decision_run(self, decision: str) -> dict:
        def fake_observe(label):
            return {"observation": {"label": label}, "ui_map": {}}, {"mode": "observe", "label": label}

        with patch("modules.computer_use_real_actions_ru._task_observe", side_effect=fake_observe), patch(
            "modules.computer_use_real_actions_ru.execute_real_action",
            return_value={"ok": True, "status": "executed", "verification": "not_applicable"},
        ), patch(
            "modules.computer_use_visual_guard_ru.compare_observations",
            return_value={"decision": decision, "reason": "contract decision", "changed_signals": 0, "stable_signals": 0},
        ):
            return run_bounded_interaction_task("Нажми Ctrl+F и прокрути вниз.", simulate=False, max_steps=6)

    def test_visual_guard_stop_terminates_task(self) -> None:
        res = self._real_mode_decision_run("stop")
        self.assertEqual(res["status"], "failed")
        self.assertTrue(res["terminal"])
        self.assertEqual(res["completed_steps"], 1)
        self.assertIn("contract decision", res["reason"])

    def test_visual_guard_ask_user_blocks_task_with_confirmation(self) -> None:
        res = self._real_mode_decision_run("ask_user")
        self.assertEqual(res["status"], "blocked")
        self.assertTrue(res["terminal"])
        self.assertTrue(res["requires_confirmation"])
        self.assertEqual(res["completed_steps"], 1)

    # --- host-broker non-bypass ------------------------------------------

    def test_executor_refuses_every_host_kind_and_never_bypasses_broker(self) -> None:
        cases = [
            ("open_app", "notepad"),
            ("open_folder", "документы"),
            ("open_url", "https://example.com"),
        ]
        for host_kind, target in cases:
            plan = {
                "ok": True,
                "actions": [
                    {"kind": host_kind, "target": target, "real_action": True},
                    {"kind": "type_element", "target": "Поиск", "text": "python", "real_action": True},
                ],
            }
            with patch("modules.computer_use_real_actions_ru.build_real_action_plan", return_value=plan):
                res = run_bounded_interaction_task("контрактная цель", simulate=True, max_steps=6)
            self.assertFalse(res["ok"], msg=host_kind)
            self.assertTrue(res["blocked"], msg=host_kind)
            self.assertTrue(res["requires_host_broker_step"], msg=host_kind)
            self.assertEqual(res["next_host_action"]["kind"], host_kind)
            self.assertEqual(res["steps"], [])

    def test_real_mode_launch_step_is_refused_before_any_execution(self) -> None:
        with patch(
            "modules.computer_use_real_actions_ru.execute_real_action",
            return_value={"ok": True, "status": "executed"},
        ) as exec_mock:
            res = run_bounded_interaction_task(BROWSER_GOAL, simulate=False, max_steps=6)
        self.assertEqual(res["status"], "blocked")
        self.assertTrue(res["requires_host_broker_step"])
        self.assertIn("cu_broker", res["reason"])
        exec_mock.assert_not_called()


class LaunchReadinessTypeContractTests(unittest.TestCase):
    """CU-CONTINUATION-01: launch -> readiness -> type ordering contract,
    deterministically, without any GUI."""

    def test_browser_goal_plan_orders_launch_readiness_type(self) -> None:
        plan = build_real_action_plan(BROWSER_GOAL, max_steps=6)
        self.assertTrue(plan["ok"])
        kinds = [action["kind"] for action in plan["actions"]]
        self.assertEqual(kinds[:2], ["open_app", "wait_for_window"])
        self.assertIn("type_element", kinds)
        self.assertIn("press_key", kinds)
        self.assertLess(kinds.index("wait_for_window"), kinds.index("type_element"))
        self.assertLess(kinds.index("type_element"), kinds.index("press_key"))

    def test_simulated_run_records_type_only_after_readiness(self) -> None:
        res = run_bounded_interaction_task(BROWSER_GOAL, simulate=True, max_steps=6)
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], "completed")
        kinds = [step["action"]["kind"] for step in res["steps"]]
        self.assertEqual(kinds[0], "open_app")
        self.assertEqual(kinds[1], "wait_for_window")
        self.assertLess(kinds.index("wait_for_window"), kinds.index("type_element"))
        self.assertLess(kinds.index("type_element"), kinds.index("press_key"))
        for index, step in enumerate(res["steps"]):
            self.assertEqual(step["step_index"], index)

    def test_notepad_task_requires_broker_launch_before_typing(self) -> None:
        goal = "Открой блокнот и напечатай LocalComet isolated smoke test."
        plan = build_real_action_plan(goal, max_steps=6)
        kinds = [action["kind"] for action in plan["actions"]]
        self.assertEqual(kinds[0], "open_app")
        self.assertIn("wait_for_window", kinds[1:3])

        res = run_bounded_interaction_task(goal, simulate=True, max_steps=6)
        self.assertFalse(res["ok"])
        self.assertTrue(res["blocked"])
        self.assertTrue(res["requires_host_broker_step"])
        self.assertEqual(res["next_host_action"]["kind"], "open_app")
        self.assertEqual(res["steps"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
