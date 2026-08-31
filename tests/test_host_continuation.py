"""Focused tests for broker-controlled host continuation."""
import hashlib
import time
import unittest
from unittest.mock import patch

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.computer_use_continuation_ru import issue_continuation, validate_continuation, clear_store
from modules.computer_use_real_actions_ru import run_bounded_interaction_task, build_real_action_plan
from modules import tool_execution_ru as tool_exec
from modules.local_model_gateway_ru import validate_tool_call, GatewayError


class HostContinuationTests(unittest.TestCase):
    def setUp(self):
        clear_store()

    def test_valid_host_chain_simulated(self):
        goal = "Открой браузер и найди официальный сайт Python. Ничего не отправляй и не заполняй формы."
        res = run_bounded_interaction_task(goal, simulate=True, max_steps=6)
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], "completed")
        # host + 3 interactions
        self.assertGreaterEqual(len(res["steps"]), 4)
        kinds = [s["action"]["kind"] for s in res["steps"]]
        self.assertIn("open_app", kinds)
        self.assertIn("type_element", kinds)
        self.assertIn("press_key", kinds)

    def test_broker_only_host_execution(self):
        # Direct open_url without broker should be blocked in tool_execution
        with self.assertRaises(tool_exec.ToolExecutionError) as cm:
            tool_exec._computer_use(None, "computer_use", {"action": "open_url", "target": "chrome", "url": "https://example.com"}, request_id="a", action_id="b")
        self.assertIn("host broker", str(cm.exception))

    def test_parent_digest_binding(self):
        parent_digest = hashlib.sha256(b"parent").hexdigest()
        per_step = hashlib.sha256(b"step1").hexdigest()
        cap = issue_continuation(parent_request_id="a"*24, parent_action_id="call_1", parent_digest=parent_digest, per_step_digest=per_step, session="sess", step_index=1, allowed_next_actions={"type_element"}, target="поиск", pid=1, desktop=None, remaining_steps=2)
        # wrong parent digest should fail
        with self.assertRaises(ValueError) as cm:
            validate_continuation(cap.token, expected_parent_digest=hashlib.sha256(b"other").hexdigest(), expected_per_step_digest=per_step, expected_step_index=1, expected_target="поиск", expected_session="sess", expected_action="type_element")
        self.assertIn("parent digest", str(cm.exception))

    def test_per_step_digest_binding(self):
        parent_digest = hashlib.sha256(b"parent").hexdigest()
        per_step = hashlib.sha256(b"step1").hexdigest()
        cap = issue_continuation(parent_request_id="a"*24, parent_action_id="call_1", parent_digest=parent_digest, per_step_digest=per_step, session="sess", step_index=1, allowed_next_actions={"type_element"}, target="поиск", pid=1, desktop=None, remaining_steps=2)
        with self.assertRaises(ValueError):
            validate_continuation(cap.token, expected_parent_digest=parent_digest, expected_per_step_digest=hashlib.sha256(b"other").hexdigest(), expected_step_index=1, expected_target="поиск", expected_session="sess", expected_action="type_element")

    def test_one_time_reuse_fails(self):
        parent_digest = hashlib.sha256(b"parent").hexdigest()
        per_step = hashlib.sha256(b"step1").hexdigest()
        cap = issue_continuation(parent_request_id="a"*24, parent_action_id="call_1", parent_digest=parent_digest, per_step_digest=per_step, session="sess", step_index=1, allowed_next_actions={"type_element"}, target="поиск", pid=1, desktop=None, remaining_steps=2)
        validate_continuation(cap.token, expected_parent_digest=parent_digest, expected_per_step_digest=per_step, expected_step_index=1, expected_target="поиск", expected_session="sess", expected_action="type_element")
        with self.assertRaises(ValueError) as cm:
            validate_continuation(cap.token, expected_parent_digest=parent_digest, expected_per_step_digest=per_step, expected_step_index=1, expected_target="поиск", expected_session="sess", expected_action="type_element")
        self.assertIn("already used", str(cm.exception))

    def test_wrong_target_fails(self):
        parent_digest = hashlib.sha256(b"parent").hexdigest()
        per_step = hashlib.sha256(b"step1").hexdigest()
        cap = issue_continuation(parent_request_id="a"*24, parent_action_id="call_1", parent_digest=parent_digest, per_step_digest=per_step, session="sess", step_index=1, allowed_next_actions={"type_element"}, target="поиск", pid=1, desktop=None, remaining_steps=2)
        with self.assertRaises(ValueError) as cm:
            validate_continuation(cap.token, expected_parent_digest=parent_digest, expected_per_step_digest=per_step, expected_step_index=1, expected_target="другой", expected_session="sess", expected_action="type_element")
        self.assertIn("wrong target", str(cm.exception))

    def test_wrong_order_fails(self):
        parent_digest = hashlib.sha256(b"parent").hexdigest()
        per_step = hashlib.sha256(b"step1").hexdigest()
        cap = issue_continuation(parent_request_id="a"*24, parent_action_id="call_1", parent_digest=parent_digest, per_step_digest=per_step, session="sess", step_index=1, allowed_next_actions={"type_element"}, target="поиск", pid=1, desktop=None, remaining_steps=2)
        with self.assertRaises(ValueError) as cm:
            validate_continuation(cap.token, expected_parent_digest=parent_digest, expected_per_step_digest=per_step, expected_step_index=2, expected_target="поиск", expected_session="sess", expected_action="type_element")
        self.assertIn("step order", str(cm.exception))

    def test_wrong_action_allowed_set(self):
        parent_digest = hashlib.sha256(b"parent").hexdigest()
        per_step = hashlib.sha256(b"step1").hexdigest()
        cap = issue_continuation(parent_request_id="a"*24, parent_action_id="call_1", parent_digest=parent_digest, per_step_digest=per_step, session="sess", step_index=1, allowed_next_actions={"type_element"}, target="поиск", pid=1, desktop=None, remaining_steps=2)
        with self.assertRaises(ValueError) as cm:
            validate_continuation(cap.token, expected_parent_digest=parent_digest, expected_per_step_digest=per_step, expected_step_index=1, expected_target="поиск", expected_session="sess", expected_action="press_key")
        self.assertIn("not allowed", str(cm.exception))

    def test_expiry_fails(self):
        parent_digest = hashlib.sha256(b"parent").hexdigest()
        per_step = hashlib.sha256(b"step1").hexdigest()
        cap = issue_continuation(parent_request_id="a"*24, parent_action_id="call_1", parent_digest=parent_digest, per_step_digest=per_step, session="sess", step_index=1, allowed_next_actions={"type_element"}, target="поиск", pid=1, desktop=None, remaining_steps=2, ttl_ms=10)
        time.sleep(0.02)
        with self.assertRaises(ValueError) as cm:
            validate_continuation(cap.token, expected_parent_digest=parent_digest, expected_per_step_digest=per_step, expected_step_index=1, expected_target="поиск", expected_session="sess", expected_action="type_element")
        self.assertIn("expired", str(cm.exception))

    def test_real_host_step_refused_fail_closed(self):
        # Phase 1 authority boundary: in real mode the sidecar task runner must
        # refuse launch steps entirely (Rust cu_broker owns real spawns), never
        # execute them via the sidecar shell fallback.
        goal = "Открой браузер и найди официальный сайт Python. Ничего не отправляй."
        with patch(
            "modules.computer_use_real_actions_ru.execute_real_action",
            return_value={"ok": True, "status": "launch_pending", "verification": "pending"},
        ) as exec_mock:
            res = run_bounded_interaction_task(goal, simulate=False, max_steps=6)
        self.assertEqual(res["status"], "blocked")
        self.assertTrue(res["terminal"])
        self.assertTrue(res.get("requires_host_broker_step"))
        self.assertIn("cu_broker", str(res.get("reason", "")))
        # The sidecar must not have attempted any host execution itself.
        exec_mock.assert_not_called()

    def test_changed_query_fails_due_to_digest(self):
        goal1 = "Открой браузер и найди официальный сайт Python. Ничего не отправляй."
        goal2 = "Открой браузер и найди другой сайт. Ничего не отправляй."
        res1 = run_bounded_interaction_task(goal1, simulate=True, max_steps=6)
        self.assertTrue(res1["ok"])
        # Simulate continuation reuse with changed query: parent digest mismatch
        parent_digest1 = hashlib.sha256(goal1.encode()).hexdigest()
        parent_digest2 = hashlib.sha256(goal2.encode()).hexdigest()
        per_step = hashlib.sha256(b"step").hexdigest()
        cap = issue_continuation(parent_request_id="a"*24, parent_action_id="call_1", parent_digest=parent_digest1, per_step_digest=per_step, session="sess", step_index=0, allowed_next_actions={"open_app"}, target="chrome", pid=1, desktop=None, remaining_steps=5)
        with self.assertRaises(ValueError):
            validate_continuation(cap.token, expected_parent_digest=parent_digest2, expected_per_step_digest=per_step, expected_step_index=0, expected_target="chrome", expected_session="sess", expected_action="open_app")

    def test_approval_bypass_without_grant_blocked(self):
        # Guarded computer_use task without grant should be denied at tool_execution layer
        with self.assertRaises(tool_exec.ToolExecutionError) as cm:
            tool_exec.execute_tool_call({"tool": "computer_use", "workspace": "ws", "workspace_digest": "d", "session": "s", "input": {"action": "task", "goal": "найди секрет", "max_steps": 6}})
        self.assertIn("grant", str(cm.exception).lower())

    def test_secret_negative_blocked(self):
        plan = build_real_action_plan("найди мой пароль", max_steps=6)
        self.assertTrue(plan["blocked"])
        goal = "Открой браузер и найди мой пароль. Ничего не отправляй."
        res = run_bounded_interaction_task(goal, simulate=True, max_steps=6)
        self.assertTrue(res["blocked"] or res["status"] == "blocked")

    def test_destructive_negative_blocked(self):
        plan = build_real_action_plan("удали файлы", max_steps=6)
        self.assertTrue(plan["blocked"])

    def test_form_submit_negative(self):
        # Form submit should be blocked via _blocked_goal or _validate_bounded_search_query
        goal = "Открой браузер и найди официальный сайт Python и отправь форму"
        res = run_bounded_interaction_task(goal, simulate=True, max_steps=6)
        # The query contains disallowed instruction or is blocked; should be blocked or fail
        self.assertTrue(res.get("blocked") or not res.get("ok") or "отправь форму" in res.get("reason","").lower() or res["status"] in {"blocked","failed"})

    def test_arbitrary_url_negative(self):
        goal = "Открой браузер и найди https://evil.example"
        res = run_bounded_interaction_task(goal, simulate=True, max_steps=6)
        # Should not invent URL; either blocked or query invalid
        self.assertTrue(res.get("blocked") or res["status"] in {"blocked","failed"} or "arbitrary" in str(res.get("reason","")).lower())

    def test_max_steps_bounded(self):
        goal = "Открой браузер и найди официальный сайт Python. Ничего не отправляй."
        # In-contract budget runs and never exceeds it.
        res = run_bounded_interaction_task(goal, simulate=True, max_steps=8)
        self.assertLessEqual(len(res.get("steps", [])), 6)

    def test_out_of_contract_max_steps_fails_closed(self):
        goal = "Открой браузер и найди официальный сайт Python. Ничего не отправляй."
        for bad in (0, 9, 10, True, 2.5, "6"):
            res = run_bounded_interaction_task(goal, simulate=True, max_steps=bad)
            self.assertFalse(res["ok"], msg=f"max_steps={bad!r} must fail closed")
            self.assertEqual(res["status"], "blocked")
            self.assertTrue(res["terminal"])
            self.assertEqual(res["steps"], [])

    def test_read_only_actions_unchanged(self):
        from modules.tool_execution_ru import COMPUTER_USE_READ_ONLY_ACTIONS
        self.assertEqual(COMPUTER_USE_READ_ONLY_ACTIONS, frozenset({"screenshot", "wait", "wait_for_window", "observe", "scroll"}))

    def test_host_token_validation_failure_fails_closed(self):
        # A failed host capability check must stop the task (fail closed),
        # never be swallowed so interaction continues.
        goal = "Открой браузер и найди официальный сайт Python. Ничего не отправляй."
        with patch(
            "modules.computer_use_continuation_ru.validate_continuation",
            side_effect=ValueError("tampered capability"),
        ):
            res = run_bounded_interaction_task(goal, simulate=True, max_steps=6)
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "blocked")
        self.assertTrue(res.get("terminal"))
        self.assertIn("host continuation validation failed", str(res.get("reason", "")))

    def test_simulation_marks_synthetic_pid(self):
        # The synthetic simulation PID must never look like a real process in envelopes.
        goal = "Открой браузер и найди официальный сайт Python. Ничего не отправляй и не заполняй формы."
        res = run_bounded_interaction_task(goal, simulate=True, max_steps=6)
        self.assertTrue(res["ok"])
        host_result = res["steps"][0]["result"]
        self.assertTrue(host_result.get("simulated"))
        self.assertTrue(host_result.get("pid_synthetic"))

    def test_simulation_task_verification_is_not_applicable_not_verified(self):
        # Simulation must not earn a "verified" task-level verdict.
        goal = "Открой браузер и найди официальный сайт Python. Ничего не отправляй и не заполняй формы."
        res = run_bounded_interaction_task(goal, simulate=True, max_steps=6)
        self.assertEqual(res["verification"], "not_applicable")
        self.assertFalse(res["postcondition_evidence"]["asserted"])

    def test_markup_query_blocked(self):
        # _validate_bounded_search_query must reject markup characters, not silently pass them.
        goal = "Открой браузер и найди <script>alert(1)</script>"
        res = run_bounded_interaction_task(goal, simulate=True, max_steps=6)
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "blocked")

    def test_task_envelope_never_claims_rust_broker_enforcement(self):
        # Honesty contract (master prompt section 4): the Python-local capability
        # chain must be explicitly marked as NOT Rust cu_broker enforcement.
        goal = "Открой браузер и найди официальный сайт Python. Ничего не отправляй и не заполняй формы."
        res = run_bounded_interaction_task(goal, simulate=True, max_steps=6)
        self.assertEqual(res.get("continuation_protocol"), "python_local_capability_v1")
        self.assertFalse(res.get("rust_broker_enforced"))
        host_result = res["steps"][0]["result"]
        self.assertIn(host_result.get("host_execution_authority"), {"simulation_only", "sidecar_shell_allowlist"})
        self.assertFalse(host_result.get("rust_broker_enforced"))
