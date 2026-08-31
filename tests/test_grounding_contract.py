from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import computer_use_grounding_ru as grounding


def _element(element_id: str, name: str, role: str = "button", confidence: float = 0.9):
    # Elements stand in for a real structured UIA producer readback: only
    # source="uia_automation" with a control_type identity is executable.
    return {
        "element_id": element_id,
        "role": role,
        "name": name,
        "confidence": confidence,
        "clickable": True,
        "source": "uia_automation",
        "metadata": {"control_type": "ButtonControl", "automation_id": element_id, "hwnd": 4242},
        "bounds": {"x": 10, "y": 10, "width": 100, "height": 30},
    }


def _window_box(name: str):
    # Coarse GetWindowRect box (desktop_primitives): structured enough to be
    # a search candidate, never an execution target.
    return {
        "element_id": "window_001",
        "role": "window",
        "name": name,
        "confidence": 0.96,
        "clickable": True,
        "source": "desktop_primitives",
        "bounds": {"x": 10, "y": 20, "width": 400, "height": 300},
    }


class GroundingContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_loader = grounding.load_latest_ui_map

    def tearDown(self) -> None:
        grounding.load_latest_ui_map = self._original_loader

    def _load_with(self, elements):
        grounding.load_latest_ui_map = lambda: {
            "ok": True,
            "elements": elements,
            "ui_map_path": "memory",
        }

    def test_structural_bonus_alone_cannot_pass_threshold(self):
        # High-confidence button with ZERO semantic overlap with the query.
        self._load_with([_element("btn_001", "Настройки", confidence=1.0)])
        result = grounding.ground_element("Сохранить документ")
        self.assertFalse(result["ok"])
        self.assertTrue(
            (result.get("best", {}).get("score", 1.0)) < result["min_confidence"]
        )

    def test_clear_semantic_match_passes(self):
        self._load_with([
            _element("btn_save", "Сохранить документ"),
            _element("btn_cancel", "Отмена"),
        ])
        result = grounding.ground_element("нажми Сохранить")
        self.assertTrue(result["ok"])
        self.assertEqual(result["element_id"], "btn_save")

    def test_ambiguous_equal_candidates_require_user(self):
        self._load_with([
            _element("btn_save_a", "Сохранить"),
            _element("btn_save_b", "Сохранить"),
        ])
        result = grounding.ground_element("нажми Сохранить")
        self.assertFalse(result["ok"])
        self.assertTrue(result.get("ambiguous"))
        self.assertTrue(result.get("needs_user"))

    def test_exe_suffix_target_maps_to_same_entry(self):
        # Broker-side parity at the grounding layer is out of scope here; this
        # asserts the exe-stripping rule used by the Rust broker has a
        # matching semantic in scoring: "calc.exe" query hits "calc" names.
        self._load_with([_element("btn_calc", "calc")])
        result = grounding.ground_element("открой calc.exe кнопку")
        self.assertTrue(result["ok"])

    def test_window_level_box_is_never_an_execution_target(self):
        # A whole-window GetWindowRect box matches the query semantically but
        # carries no UIA control identity: grounding must fail closed instead
        # of clicking the window center.
        self._load_with([_window_box("Сохранить документ")])
        result = grounding.ground_element("нажми Сохранить")
        self.assertFalse(result["ok"])
        self.assertTrue(result["needs_user"])
        self.assertIn("structured UI evidence", result["reason"])

    def test_real_producer_target_carries_provenance(self):
        self._load_with([_element("btn_save", "Сохранить документ")])
        result = grounding.ground_element("нажми Сохранить")
        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "uia_automation")
        target = result["target"]
        self.assertEqual(target["producer"], "uia_automation")
        self.assertEqual(target["control_type"], "ButtonControl")
        self.assertEqual(target["automation_id"], "btn_save")

    def test_derived_token_with_high_score_is_never_executable(self):
        derived = {
            "element_id": "title_token_000",
            "role": "text",
            "name": "Сохранить",
            "confidence": 0.99,
            "clickable": False,
            "source": "screen_parser_adapter",
            "metadata": {"derived": True, "parent_window": "Блокнот"},
            "bounds": {"x": 10, "y": 10, "width": 90, "height": 24},
        }
        self._load_with([derived])
        result = grounding.ground_element("нажми Сохранить")
        self.assertFalse(result["ok"])
        self.assertTrue(result["needs_user"])
        self.assertIn("structured UI evidence", result["reason"])


if __name__ == "__main__":
    unittest.main()
