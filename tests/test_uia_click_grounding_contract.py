"""Deterministic grounding contract for click/double-click (CU-UIA-01).

Proves, without any GUI or hidden desktop:
- only structured UIA producer elements (source="uia_automation" with a
  control_type identity) become executable click targets;
- derived/search-only tokens and window-level boxes never do;
- bare coordinates are never grounding evidence for click/double-click;
- the simulated click/double-click path carries producer provenance.
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

from modules import computer_use_grounding_ru as grounding
from modules.computer_use_test_fixtures_ru import temporary_latest_ui_map


def _uia_element(element_id: str, name: str, role: str = "button") -> dict:
    """A real structured UIA producer readback element."""
    return {
        "element_id": element_id,
        "role": role,
        "name": name,
        "text": name,
        "confidence": 0.95,
        "clickable": True,
        "source": "uia_automation",
        "metadata": {"control_type": "ButtonControl", "automation_id": element_id, "hwnd": 4242},
        "bounds": {"x": 100, "y": 200, "w": 120, "h": 40},
    }


def _window_box(name: str) -> dict:
    return {
        "element_id": "window_001",
        "role": "window",
        "name": name,
        "confidence": 0.96,
        "clickable": True,
        "source": "desktop_primitives",
        "bounds": {"x": 10, "y": 20, "w": 400, "h": 300},
    }


class UiaClickGroundingContractTests(unittest.TestCase):
    def _ground(self, elements: list) -> dict:
        loaded = {"ok": True, "elements": elements, "element_count": len(elements), "ui_map_path": "memory"}
        with patch.object(grounding, "load_latest_ui_map", return_value=loaded):
            return grounding.ground_element("нажми Сохранить")

    def test_real_producer_element_is_executable_with_provenance(self) -> None:
        result = self._ground([_uia_element("btn_save", "Сохранить документ")])
        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "uia_automation")
        self.assertEqual(result["control_type"], "ButtonControl")
        self.assertEqual(result["target"]["producer"], "uia_automation")
        self.assertEqual(result["target"]["automation_id"], "btn_save")
        self.assertIsNotNone(result["target"]["x"])
        self.assertIsNotNone(result["target"]["y"])

    def test_click_and_double_click_actions_carry_producer_source(self) -> None:
        self._ground_elements = [_uia_element("btn_save", "Сохранить документ")]
        for kind in ("click", "double_click"):
            with patch.object(
                grounding,
                "load_latest_ui_map",
                return_value={"ok": True, "elements": self._ground_elements, "ui_map_path": "memory"},
            ):
                built = grounding.build_grounded_action("нажми Сохранить", kind=kind)
            self.assertTrue(built["ok"], msg=kind)
            action = built["action"]
            self.assertEqual(action["kind"], kind)
            self.assertTrue(action["grounded"])
            self.assertEqual(action["grounding_source"], "uia_automation")
            self.assertEqual(action["target"]["producer"], "uia_automation")

    def test_window_box_never_grounds_a_click(self) -> None:
        result = self._ground([_window_box("Сохранить документ")])
        self.assertFalse(result["ok"])
        self.assertTrue(result["needs_user"])
        self.assertIn("structured UI evidence", result["reason"])

    def test_mixed_window_and_derived_never_grounds_a_click(self) -> None:
        derived = {
            "element_id": "title_token_000",
            "role": "text",
            "name": "Сохранить",
            "confidence": 0.99,
            "clickable": False,
            "source": "screen_parser_adapter",
            "metadata": {"derived": True, "parent_window": "Блокнот"},
            "bounds": {"x": 10, "y": 10, "w": 90, "h": 24},
        }
        result = self._ground([_window_box("Блокнот"), derived])
        self.assertFalse(result["ok"])
        self.assertTrue(result["needs_user"])
        self.assertIn("structured UI evidence", result["reason"])

    def test_uia_element_without_control_type_is_not_executable(self) -> None:
        element = _uia_element("btn_save", "Сохранить документ")
        element["metadata"] = {"automation_id": "btn_save"}  # control_type missing
        result = self._ground([element])
        self.assertFalse(result["ok"])
        self.assertTrue(result["needs_user"])

    def test_guarded_click_plan_uses_real_producer_grounding(self) -> None:
        payload = {
            "ok": True,
            "mode": "contract",
            "elements": [_uia_element("btn_save", "Сохранить")],
        }
        with temporary_latest_ui_map(payload=payload, label="uia_click_grounding"):
            from modules.computer_use_click_planner_ru import plan_click_element, click_element

            plan = plan_click_element("Сохранить")
            self.assertTrue(plan["ok"])
            self.assertTrue(plan["can_execute"])
            self.assertEqual(plan["action"]["grounding_source"], "uia_automation")
            self.assertEqual(plan["action"]["target"]["producer"], "uia_automation")

            result = click_element("Сохранить", simulate=True)
            self.assertTrue(result["ok"])
            self.assertTrue(result["execution"]["simulated"])

    def test_guarded_click_fails_closed_without_producer_elements(self) -> None:
        payload = {
            "ok": True,
            "mode": "contract",
            "elements": [_window_box("Сохранить")],
        }
        with temporary_latest_ui_map(payload=payload, label="uia_click_window_box"):
            from modules.computer_use_click_planner_ru import plan_click_element

            plan = plan_click_element("Сохранить")
            self.assertFalse(plan["ok"])
            self.assertIn("structured UI evidence", plan["reason"])

    def test_double_click_executes_two_grounded_clicks(self) -> None:
        payload = {
            "ok": True,
            "mode": "contract",
            "elements": [_uia_element("btn_chat", "Чат")],
        }
        with temporary_latest_ui_map(payload=payload, label="uia_double_click"):
            from modules.computer_use_real_actions_ru import click_element

            result = click_element("Чат", simulate=True, double=True)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "simulated")
            first = result["first"]
            second = result["second"]
            self.assertTrue(first["execution"]["simulated"])
            self.assertTrue(second["execution"]["simulated"])
            for click in (first, second):
                self.assertEqual(click["plan"]["action"]["grounding_source"], "uia_automation")

    def test_bare_coordinates_are_not_click_grounding_evidence(self) -> None:
        from modules.computer_use_auto_action_ru import (
            auto_policy_for_action,
            execute_gui_action,
            is_grounded_action,
            parse_auto_command,
        )

        # Explicit coordinate auto click: coordinates alone are not grounding.
        parsed = parse_auto_command("pc computer auto click 100 200")
        self.assertFalse(parsed["grounded"])
        self.assertEqual(list(parsed["target"].keys()), ["x", "y"])
        self.assertFalse(is_grounded_action(parsed))
        policy = auto_policy_for_action(parsed)
        self.assertFalse(policy["allowed_to_execute"])
        self.assertIn("grounding", policy["reason"])
        execution = execute_gui_action(dict(parsed), simulate=True)
        self.assertFalse(execution["executed"])
        self.assertFalse(execution.get("simulated"))

        # Simulated coordinate click mirrors the real refusal.
        simulated = {"kind": "click", "target": {"x": 10, "y": 10}, "grounded": True, "reason": "simulated coordinate click"}
        self.assertFalse(is_grounded_action(simulated))
        policy = auto_policy_for_action(simulated)
        self.assertFalse(policy["allowed_to_execute"])

    def test_ungrounded_named_auto_click_is_refused(self) -> None:
        from modules.computer_use_auto_action_ru import auto_policy_for_action, parse_auto_command

        parsed = parse_auto_command("pc computer auto click Сохранить")
        self.assertFalse(parsed["grounded"])
        policy = auto_policy_for_action(parsed)
        self.assertFalse(policy["allowed_to_execute"])
        self.assertIn("grounding", policy["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
