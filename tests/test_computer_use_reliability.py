"""Hidden regression coverage for Computer Use reliability safeguards."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import computer_use_auto_action_ru as auto_actions
from modules import computer_use_real_actions_ru as real_actions
from modules.computer_use_real_actions_ru import build_real_action_plan, execute_real_action
from modules.computer_use_visual_guard_ru import classify_ui_markers
from modules import pc_agent_actions
from modules import tool_execution_ru as tool_execution


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

    def test_structured_result_keeps_launch_pending_non_terminal(self) -> None:
        result = tool_execution._normalize_computer_use_result(
            {"ok": True, "status": "executed", "verification": "pending"},
            action="open_app",
            request_id="r1",
            action_id="a1",
        )
        self.assertEqual(result["schema_version"], "computer_use.result.v1")
        self.assertEqual(result["status"], "launch_pending")
        self.assertFalse(result["terminal"])
        self.assertFalse(result["succeeded"])
        self.assertEqual(result["request_id"], "r1")
        self.assertEqual(result["action_id"], "a1")

    def test_structured_result_requires_verified_terminal_success(self) -> None:
        result = tool_execution._normalize_computer_use_result(
            {"ok": True, "status": "executed", "verification": "verified"},
            action="open_app",
        )
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["terminal"])
        self.assertTrue(result["succeeded"])
        self.assertEqual(result["verification"], "verified")

    def test_shell_execute_without_window_readiness_stays_pending(self) -> None:
        with patch.object(pc_agent_actions.os, "name", "nt"), \
             patch.object(pc_agent_actions, "_shell_execute_open_bounded", return_value=True), \
             patch.object(pc_agent_actions, "_wait_for_app_readiness", return_value=False):
            result = pc_agent_actions.open_app("notepad", dry_run=False)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "launch_pending")
        self.assertEqual(result["verification"], "pending")

    def test_structured_result_preserves_blocked_state(self) -> None:
        result = tool_execution._normalize_computer_use_result(
            {"ok": False, "status": "blocked", "blocked": True, "reason": "policy"},
            action="open_app",
        )
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["terminal"])
        self.assertFalse(result["succeeded"])

    def test_legacy_ok_without_verification_is_never_verified(self) -> None:
        # Acceptance P2: a bare legacy ok=true executes but must not earn
        # "verified" — the envelope reports not_applicable instead.
        result = tool_execution._normalize_computer_use_result(
            {"ok": True, "status": "executed"},
            action="wait",
        )
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["terminal"])
        self.assertTrue(result["succeeded"])
        self.assertEqual(result["verification"], "not_applicable")

    def test_explicit_backend_verification_is_preserved(self) -> None:
        result = tool_execution._normalize_computer_use_result(
            {"ok": True, "status": "completed", "verification": "verified"},
            action="open_app",
        )
        self.assertEqual(result["verification"], "verified")
        self.assertEqual(result["status"], "completed")

    def test_unknown_verification_value_is_not_verified(self) -> None:
        result = tool_execution._normalize_computer_use_result(
            {"ok": True, "status": "executed", "verification": "banana"},
            action="click_element",
        )
        self.assertEqual(result["verification"], "not_applicable")

    def test_find_intent_plans_real_browser_search(self) -> None:
        plan = build_real_action_plan("найди погоду в екатеринбурге", max_steps=8)
        self.assertTrue(plan["ok"])
        self.assertFalse(plan.get("blocked"))
        kinds = [a["kind"] for a in plan["actions"]]
        self.assertEqual(kinds, ["open_app", "wait_for_window", "type_element", "press_key"])
        self.assertEqual(plan["actions"][0]["target"], "chrome")
        self.assertEqual(plan["actions"][2]["target"], "Поиск")
        self.assertEqual(plan["actions"][2]["text"], "погоду в екатеринбурге")
        self.assertEqual(plan["actions"][3]["key"], "enter")
        self.assertTrue(all(a["real_action"] for a in plan["actions"]))

    def test_compound_search_marker_strips_locator(self) -> None:
        plan = build_real_action_plan("найди в интернете новости спорта", max_steps=8)
        typed = [a for a in plan["actions"] if a["kind"] == "type_element"]
        self.assertEqual(len(typed), 1)
        self.assertEqual(typed[0]["text"], "новости спорта")

    def test_search_intent_still_blocks_secrets(self) -> None:
        plan = build_real_action_plan("найди мой пароль", max_steps=8)
        self.assertTrue(plan["blocked"])
        self.assertEqual(plan["reason"], "secrets")
        self.assertEqual(plan["actions"], [])


class ExecutionGrantBoundaryTests(unittest.TestCase):
    """P0-2: the Python execution boundary re-verifies Rust grants for
    dangerous tools (missing/mismatched/expired/replayed material denies
    execution)."""

    def setUp(self) -> None:
        self._consumed_backup = dict(tool_execution._consumed_grants)
        self._order_backup = list(tool_execution._consumed_grants_order)
        tool_execution._consumed_grants.clear()
        tool_execution._consumed_grants_order.clear()

    def tearDown(self) -> None:
        tool_execution._consumed_grants.clear()
        tool_execution._consumed_grants_order.extend(self._order_backup)
        tool_execution._consumed_grants.update(self._consumed_backup)

    @staticmethod
    def _payload(tool: str, input_obj: dict, grant: dict | None, grant_id: str | None = None):
        payload = {
            "tool": tool,
            "input": input_obj,
            "workspace": "C:\\ws",
            "workspace_digest": "d" * 64,
            "session": "sess-1",
        }
        if grant is not None:
            payload["grant"] = grant
        if grant_id is not None:
            payload["grant_id"] = grant_id
        return payload

    @staticmethod
    def _valid_grant(tool: str, input_obj: dict, *, expires_delta_ms: int = 30_000):
        import time as _time

        return {
            "grant_id": "g" * 32,
            "tool": tool,
            "input_digest": tool_execution.canonical_input_digest_hex(input_obj),
            "workspace": "C:\\ws",
            "session": "sess-1",
            "expires_at_unix_ms": int(_time.time() * 1000) + expires_delta_ms,
        }

    def test_canonical_input_matches_rust_parity_vector(self) -> None:
        value = {"b": 1, "a": "привет", "c": [1.5, True, None], "d": {"й": "э"}, "e": 1e30, "f": 1.5e-7}
        self.assertEqual(
            tool_execution._canonicalize_tool_input(value),
            '{"a":"привет","b":1,"c":[1.5,true,null],"d":{"й":"э"},"e":1e+30,"f":1.5e-7}',
        )

    def test_dangerous_tool_without_grant_denied(self) -> None:
        payload = self._payload("computer_use", {"action": "screenshot"}, None)
        with self.assertRaises(tool_execution.ToolExecutionError) as ctx:
            tool_execution.execute_tool_call(payload)
        self.assertEqual(ctx.exception.code, "approval_required")

    def test_dangerous_tool_with_valid_grant_passes(self) -> None:
        input_obj = {"action": "screenshot"}
        payload = self._payload(
            "computer_use", input_obj, self._valid_grant("computer_use", input_obj), "g" * 32
        )
        with patch.object(tool_execution, "_computer_use", return_value={"tool": "computer_use"}) as cu:
            tool_execution.execute_tool_call(payload)
        cu.assert_called_once()

    def test_grant_digest_mismatch_denied(self) -> None:
        grant = self._valid_grant("computer_use", {"action": "screenshot"})
        grant["input_digest"] = "0" * 64
        payload = self._payload("computer_use", {"action": "screenshot"}, grant)
        with self.assertRaises(tool_execution.ToolExecutionError) as ctx:
            tool_execution.execute_tool_call(payload)
        self.assertEqual(ctx.exception.code, "approval_arguments_mismatch")

    def test_grant_tool_mismatch_denied(self) -> None:
        grant = self._valid_grant("files.delete", {"path": "a.txt"})
        payload = self._payload("computer_use", {"action": "screenshot"}, grant)
        with self.assertRaises(tool_execution.ToolExecutionError) as ctx:
            tool_execution.execute_tool_call(payload)
        self.assertEqual(ctx.exception.code, "approval_operation_mismatch")

    def test_grant_workspace_and_session_mismatch_denied(self) -> None:
        input_obj = {"action": "screenshot"}
        grant = self._valid_grant("computer_use", input_obj)
        grant["workspace"] = "C:\\other"
        payload = self._payload("computer_use", input_obj, grant)
        with self.assertRaises(tool_execution.ToolExecutionError) as ctx:
            tool_execution.execute_tool_call(payload)
        self.assertEqual(ctx.exception.code, "approval_workspace_mismatch")

        grant = self._valid_grant("computer_use", input_obj)
        grant["session"] = "sess-2"
        payload = self._payload("computer_use", input_obj, grant)
        with self.assertRaises(tool_execution.ToolExecutionError) as ctx:
            tool_execution.execute_tool_call(payload)
        self.assertEqual(ctx.exception.code, "approval_session_mismatch")

    def test_grant_envelope_id_mismatch_denied(self) -> None:
        input_obj = {"action": "screenshot"}
        grant = self._valid_grant("computer_use", input_obj)
        payload = self._payload("computer_use", input_obj, grant, "x" * 32)
        with self.assertRaises(tool_execution.ToolExecutionError) as ctx:
            tool_execution.execute_tool_call(payload)
        self.assertEqual(ctx.exception.code, "invalid_payload")

    def test_expired_grant_denied(self) -> None:
        input_obj = {"action": "screenshot"}
        grant = self._valid_grant("computer_use", input_obj, expires_delta_ms=-1_000)
        payload = self._payload("computer_use", input_obj, grant)
        with self.assertRaises(tool_execution.ToolExecutionError) as ctx:
            tool_execution.execute_tool_call(payload)
        self.assertEqual(ctx.exception.code, "approval_grant_expired")

    def test_replayed_grant_denied(self) -> None:
        input_obj = {"action": "screenshot"}
        grant = self._valid_grant("computer_use", input_obj)
        payload = self._payload("computer_use", input_obj, grant, "g" * 32)
        with patch.object(tool_execution, "_computer_use", return_value={"tool": "computer_use"}):
            tool_execution.execute_tool_call(payload)
        with self.assertRaises(tool_execution.ToolExecutionError) as ctx:
            tool_execution.execute_tool_call(payload)
        self.assertEqual(ctx.exception.code, "approval_grant_replayed")

    def test_guarded_tool_without_grant_still_executes(self) -> None:
        payload = self._payload("files.list", {"path": "."}, None)
        with patch.object(tool_execution, "WorkspacePolicy", lambda *args: object()), \
             patch.object(
                 tool_execution, "_files_list", return_value={"tool": "files.list"}
             ) as listed:
            tool_execution.execute_tool_call(payload)
        listed.assert_called_once()

    def test_guarded_tool_with_invalid_grant_denied(self) -> None:
        grant = self._valid_grant("files.list", {"path": "."})
        grant["input_digest"] = "0" * 64
        payload = self._payload("files.list", {"path": "."}, grant)
        with self.assertRaises(tool_execution.ToolExecutionError) as ctx:
            tool_execution.execute_tool_call(payload)
        self.assertEqual(ctx.exception.code, "approval_arguments_mismatch")


class TruthfulLaunchTests(unittest.TestCase):
    """P0-3: launch success requires postcondition verification, not spawn
    acceptance; the legacy queue never claims execution it did not perform."""

    def test_open_folder_without_window_stays_launch_pending(self) -> None:
        with patch.object(pc_agent_actions.os, "name", "nt"), \
             patch.object(pc_agent_actions.subprocess, "Popen", return_value=object()), \
             patch.object(pc_agent_actions, "_wait_for_folder_readiness", return_value=False):
            result = pc_agent_actions.open_folder("проект", dry_run=False)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "launch_pending")
        self.assertEqual(result["verification"], "pending")

    def test_open_folder_with_window_completes_verified(self) -> None:
        with patch.object(pc_agent_actions.os, "name", "nt"), \
             patch.object(pc_agent_actions.subprocess, "Popen", return_value=object()), \
             patch.object(pc_agent_actions, "_wait_for_folder_readiness", return_value=True):
            result = pc_agent_actions.open_folder("проект", dry_run=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["verification"], "verified")

    def test_open_folder_popen_failure_is_failed_not_success(self) -> None:
        with patch.object(pc_agent_actions.os, "name", "nt"), \
             patch.object(pc_agent_actions.subprocess, "Popen", side_effect=OSError("no broker")):
            result = pc_agent_actions.open_folder("проект", dry_run=False)
        self.assertFalse(result["ok"])
        self.assertNotEqual(result.get("status"), "completed")
        self.assertIn("error", result)

    def test_explorer_launch_is_never_verified_by_shell_image_scan(self) -> None:
        # The shell's own always-visible windows (taskbar, tray) satisfy any
        # explorer.exe image scan, so image-name readiness must refuse to
        # verify an Explorer launch; non-shell images keep the scan.
        with patch.object(pc_agent_actions, "_find_visible_process_for_image", return_value=True):
            self.assertFalse(
                pc_agent_actions._wait_for_app_readiness(image_name="explorer.exe", pid=None, timeout=0.1)
            )
            self.assertTrue(
                pc_agent_actions._wait_for_app_readiness(image_name="notepad.exe", pid=None, timeout=0.1)
            )

    def test_open_app_startfile_fallback_reports_launch_pending(self) -> None:
        backend = {"ok": False, "status": "launch_pending", "error": "quota"}
        with patch("modules.pc_agent_actions.open_app", return_value=backend), \
             patch.object(real_actions.os, "startfile", create=True, side_effect=lambda _p: None):
            result = real_actions.open_app("notepad", simulate=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "launch_pending")
        self.assertEqual(result["verification"], "pending")
        self.assertNotIn("executed", str(result.get("status")))

    def test_open_folder_startfile_fallback_reports_launch_pending(self) -> None:
        with patch.dict(sys.modules, {"modules.pc_agent_actions": None}), \
             patch.object(real_actions.os, "startfile", create=True, side_effect=lambda _p: None):
            result = real_actions.open_folder("проект", simulate=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "launch_pending")
        self.assertEqual(result["verification"], "pending")

    def test_open_folder_delegates_to_readiness_verified_launcher(self) -> None:
        delegated = {"ok": True, "status": "completed", "verification": "verified", "action": "open_folder"}
        with patch("modules.pc_agent_actions.open_folder", return_value=delegated) as pc_open:
            result = real_actions.open_folder("проект", simulate=False)
        pc_open.assert_called_once()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["mode"], "computer_use_real_open_folder")

    def test_execute_confirmed_action_never_claims_execution(self) -> None:
        from modules import computer_use_core_ru as core

        item = {"action_id": "cu_test_1", "confirmed": True, "executed": False, "goal": "наблюдение"}
        with patch.object(core, "_read_json", return_value=[item]), \
             patch.object(core, "_write_json") as write_json, \
             patch.object(core, "observe_screen", return_value={"ok": True}), \
             patch.object(core, "build_ui_map", return_value={"ui_map_path": "map.json"}):
            result = core.execute_confirmed_action("cu_test_1")
        self.assertTrue(result["ok"])
        self.assertFalse(result["executed"])
        self.assertFalse(item["executed"])
        # The queue persistence (first write) must record executed=False;
        # the trace write afterwards is expected.
        queue_write = write_json.call_args_list[0]
        persisted_item = queue_write.args[1][0]
        self.assertFalse(persisted_item["executed"])
        self.assertIn("dry_run_only", persisted_item["execution_policy"])
        self.assertIn("dry_run_only", result["policy"])


class WaitSchemaTests(unittest.TestCase):
    """P0-4: one canonical wait format (seconds, 0.1..=30.0) across the intent
    parser, the Python registry, and the sidecar executor."""

    def test_intent_parser_emits_canonical_seconds(self) -> None:
        from modules.local_model_gateway_ru import _deterministic_computer_use_call

        call = _deterministic_computer_use_call("подожди 3 секунды")
        self.assertEqual(call["name"], "computer_use")
        self.assertEqual(call["arguments"], {"action": "wait", "seconds": 3.0})

    def test_intent_parser_clamps_to_canonical_bound(self) -> None:
        from modules.local_model_gateway_ru import _deterministic_computer_use_call

        call = _deterministic_computer_use_call("подожди 100 секунд")
        self.assertEqual(call["arguments"]["seconds"], 30.0)

    def test_type_intent_accepts_instruction_tail_and_extracts_marker(self) -> None:
        from modules.local_model_gateway_ru import _deterministic_computer_use_call

        call = _deterministic_computer_use_call(
            "В уже открытом Блокноте выполни именно действие Computer Use type "
            "с текстом только этого маркера: LocalComet isolated smoke test. "
            "Не отвечай объяснением."
        )
        self.assertEqual(call["name"], "computer_use")
        self.assertEqual(call["arguments"], {"action": "type", "text": "LocalComet isolated smoke test"})

    def test_type_intent_accepts_plain_follow_up_prompt(self) -> None:
        from modules.local_model_gateway_ru import _deterministic_computer_use_call

        call = _deterministic_computer_use_call("type LocalComet isolated smoke test.")
        self.assertEqual(call["arguments"], {"action": "type", "text": "LocalComet isolated smoke test"})

    def test_registry_validates_seconds_range(self) -> None:
        from modules.local_model_gateway_ru import GatewayError, validate_tool_call

        validate_tool_call("computer_use", {"action": "wait", "seconds": 2.5})
        validate_tool_call("computer_use", {"action": "wait", "seconds": 3})
        for bad in (0.05, 31.0, "2", True, None):
            with self.assertRaises(GatewayError):
                validate_tool_call("computer_use", {"action": "wait", "seconds": bad})

    def test_executor_passes_seconds_to_wait_backend(self) -> None:
        input_obj = {"action": "wait", "seconds": 2.5}
        payload = {
            "tool": "computer_use",
            "input": input_obj,
            "workspace": "C:\\ws",
            "workspace_digest": "d" * 64,
            "session": "sess-1",
            "grant": {
                "grant_id": "w" * 32,
                "tool": "computer_use",
                "input_digest": tool_execution.canonical_input_digest_hex(input_obj),
                "workspace": "C:\\ws",
                "session": "sess-1",
                "expires_at_unix_ms": 9_999_999_999_999,
            },
            "grant_id": "w" * 32,
        }
        captured: dict = {}
        import modules.computer_use_real_actions_ru as real_backend

        def fake_execute(dispatched, simulate=False):
            captured.update(dispatched)
            return {"ok": True, "status": "executed", "seconds": dispatched.get("seconds")}

        tool_execution._consumed_grants.clear()
        try:
            with patch.object(real_backend, "execute_real_action", side_effect=fake_execute):
                result = tool_execution.execute_tool_call(payload)
        finally:
            tool_execution._consumed_grants.clear()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(captured["kind"], "wait_for_window")
        self.assertEqual(captured["seconds"], 2.5)

    def test_wait_backend_clamps_to_canonical_bound(self) -> None:
        result = real_actions.wait_for_window(seconds=100, simulate=True)
        self.assertEqual(result["seconds"], 30.0)


class GroundingSafetyTests(unittest.TestCase):
    """P0-5: fabricated title-token boxes are never execution targets; ties
    between the best executable candidates require user clarification."""

    @staticmethod
    def _real_window(text: str, x: int = 10) -> dict:
        return {
            "element_type": "window",
            "text": text,
            "bbox": {"x": x, "y": 20, "width": 400, "height": 300},
            "center": {"x": x + 200, "y": 170},
            "confidence": 0.96,
            "clickable": True,
            "source": "desktop_primitives",
        }

    @staticmethod
    def _derived_token(text: str) -> dict:
        return {
            "element_type": "text",
            "text": text,
            "bbox": {"x": 10, "y": 20, "width": 90, "height": 24},
            "center": {"x": 55, "y": 32},
            "confidence": 0.62,
            "clickable": False,
            "source": "screen_parser_adapter",
            "metadata": {"derived": True, "parent_window": "Блокнот"},
        }

    def _ground(self, elements: list) -> dict:
        import modules.computer_use_grounding_ru as grounding

        loaded = {"ok": True, "elements": elements, "element_count": len(elements), "ui_map_path": "test"}
        with patch.object(grounding, "load_latest_ui_map", return_value=loaded):
            return grounding.ground_element("сохранить")

    def test_derived_title_token_is_never_an_execution_target(self) -> None:
        result = self._ground([self._real_window("Блокнот"), self._derived_token("сохранить")])
        self.assertFalse(result["ok"])
        self.assertTrue(result["needs_user"])
        self.assertIn("structured UI evidence", result["reason"])

    def test_ambiguous_executable_candidates_require_clarification(self) -> None:
        result = self._ground([
            self._real_window("сохранить документ", x=10),
            self._real_window("сохранить как", x=500),
        ])
        self.assertFalse(result["ok"])
        self.assertTrue(result.get("ambiguous"))
        self.assertTrue(result["needs_user"])
        self.assertIn("Ambiguous", result["reason"])

    def test_clear_best_executable_candidate_grounds(self) -> None:
        result = self._ground([
            self._real_window("сохранить"),
            self._real_window("калькулятор"),
        ])
        self.assertTrue(result["ok"])
        self.assertEqual(result["text"], "сохранить")

    def test_zero_candidates_is_needs_user(self) -> None:
        result = self._ground([])
        self.assertFalse(result["ok"])
        self.assertTrue(result["needs_user"])


class ConsoleBridgeGateTests(unittest.TestCase):
    """P0-7: legacy console/GUI bridges require explicit user consent for real
    desktop actions; read-only and simulated commands pass."""

    def test_read_only_bridge_commands_pass(self) -> None:
        from modules.computer_use_console_gate_ru import bridge_gate_decision

        for command in (
            "pc computer status",
            "pc computer map",
            "pc computer find кнопку сохранить",
            "найди элемент сохранить",
            "pc computer simulate loop открой блокнот",
            "спланируй действие открой блокнот",
            "pc computer observe",
        ):
            decision = bridge_gate_decision(command)
            self.assertFalse(decision["requires_confirmation"], command)

    def test_real_bridge_commands_require_confirmation(self) -> None:
        from modules.computer_use_console_gate_ru import bridge_gate_decision

        for command in (
            "pc computer run loop открой блокнот",
            "управляй пк открой блокнот и напиши привет",
            "агент пк сделай скриншот",
            "computer use run",
        ):
            decision = bridge_gate_decision(command)
            self.assertTrue(decision["requires_confirmation"], command)

    def test_non_interactive_session_denies_real_actions(self) -> None:
        import modules.computer_use_console_gate_ru as gate

        with patch("sys.stdin") as fake_stdin:
            fake_stdin.isatty.return_value = False
            self.assertFalse(gate.confirm_interactively("pc computer run loop открой блокнот"))
            self.assertTrue(gate.confirm_interactively("pc computer status"))

    def test_control_panel_bridge_blocks_real_action_without_consent(self) -> None:
        import LocalComet_Control_Panel as panel

        with patch("modules.computer_use_console_gate_ru.confirm_interactively", return_value=False), \
             patch("modules.computer_use_core_ru.dispatch") as dispatch:
            result = panel._run_computer_use_command_bridge("pc computer run loop открой блокнот")
        dispatch.assert_not_called()
        self.assertFalse(result["result"]["ok"])
        self.assertTrue(result["result"]["blocked"])

    def test_control_panel_bridge_passes_read_only_without_prompt(self) -> None:
        import LocalComet_Control_Panel as panel

        with patch("modules.computer_use_console_gate_ru.confirm_interactively", return_value=False), \
             patch("modules.computer_use_core_ru.dispatch", return_value={"ok": True}) as dispatch:
            result = panel._run_computer_use_command_bridge("pc computer status")
        dispatch.assert_called_once()
        self.assertTrue(result["result"]["ok"])

    def test_codex_executor_requires_explicit_confirmation_phrase(self) -> None:
        from modules import pc_codex_executor

        result = pc_codex_executor.run_confirmed("открыть блокнот")
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])
        self.assertEqual(result["reason"], "Нужна явная фраза подтверждения.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
