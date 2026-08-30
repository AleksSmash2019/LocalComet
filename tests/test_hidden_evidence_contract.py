import sys
import base64
import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for path in (ROOT, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_isolated_hidden_desktop_cu import (  # noqa: E402
    classify_case,
    cancel_safe_state_verified,
    cancel_terminal_only_verified,
    continuation_cancel_trace_verified,
    validate_correlation,
    GUARDED_SCENARIO_IDS,
    validate_screenshot_evidence,
    _uia_control_text,
    _browser_target_matches,
    CdpDriver,
    IsolatedStartupError,
    require_native_process_alive,
    resolve_native_child_pid,
    wait_for_window,
    cdp_wait_for_turn,
    submit_prompt_with_card_baseline,
    _process_present,
    classify_coding_result,
    materialize_rendered_screenshot,
    browser_listener_identity,
)


REQUEST_ID = "0123456789abcdef01234567"
MODEL_ACTION_ID = "call_0123456789abcdef0123456789ab"
APPROVAL_PROMPT_ID = "appr_0123456789abcdef0123456789abcdef"
APPROVAL_ID = "appr_abcdef0123456789abcdef0123456789"
APPROVAL_CALL_ID = "call_abcdef0123456789abcdef0123456789"
INPUT_DIGEST = "a" * 64
SCREENSHOT_SHA = "b" * 64


class _ReaderRange:
    def GetText(self, _length):
        return "LocalComet isolated smoke test."


class _ReaderTextPattern:
    DocumentRange = _ReaderRange()


class _ReaderValuePattern:
    Value = "LocalComet isolated smoke test."


class _DirectReaderControl:
    Name = ""

    def GetTextPattern(self):
        return _ReaderTextPattern()

    def GetValuePattern(self):
        return _ReaderValuePattern()

    def GetPattern(self, _pattern_id):
        raise AssertionError("generic PatternId path should not be needed")


class _PatternIds:
    TextPattern = 10014
    ValuePattern = 10002


class _FakeProcess:
    def __init__(self, returncode):
        self.returncode = returncode
        self.pid = 4242

    def poll(self):
        return self.returncode


class HiddenEvidenceContractTests(unittest.TestCase):
    def test_native_liveness_guard_fails_closed_after_tauri_exit(self):
        require_native_process_alive(_FakeProcess(None), "before_cdp_startup")
        with self.assertRaises(IsolatedStartupError) as caught:
            require_native_process_alive(_FakeProcess(-1073741819), "after_cdp_startup")
        self.assertEqual(caught.exception.error_type, "native_process_exited")
        self.assertEqual(caught.exception.details, {"pid": 4242, "returncode": -1073741819, "stage": "after_cdp_startup"})

    @mock.patch("run_isolated_hidden_desktop_cu.os.name", "nt")
    @mock.patch("run_isolated_hidden_desktop_cu.time.sleep")
    @mock.patch("run_isolated_hidden_desktop_cu._windows_process_table")
    def test_native_child_resolver_ignores_wrapper_and_walks_owned_descendants(self, table, _sleep):
        table.return_value = [
            {"ProcessId": 100, "ParentProcessId": 1, "Name": "npm.exe"},
            {"ProcessId": 200, "ParentProcessId": 100, "Name": "cargo.exe"},
            {"ProcessId": 300, "ParentProcessId": 200, "Name": "localcomet-desktop.exe"},
        ]
        self.assertEqual(resolve_native_child_pid(100, timeout=1), 300)
        table.assert_called_once_with()

    def test_unresolved_native_child_fails_closed_before_stale_page_use(self):
        process = _FakeProcess(None)
        process.native_pid_resolved = False
        process.launcher = _FakeProcess(None)
        with self.assertRaises(IsolatedStartupError) as caught:
            require_native_process_alive(process, "before_cdp_startup")
        self.assertEqual(caught.exception.error_type, "native_process_unresolved")
        self.assertEqual(caught.exception.details["launcher_pid"], 4242)

    def test_window_wait_stops_immediately_when_native_process_exits(self):
        with self.assertRaises(IsolatedStartupError) as caught:
            wait_for_window(None, 600, _FakeProcess(-1073741819))
        self.assertEqual(caught.exception.error_type, "native_process_exited")
        self.assertEqual(caught.exception.details["stage"], "window_wait")

    def test_turn_wait_reports_native_exit_before_stale_cdp_reads(self):
        driver = mock.Mock()
        result = cdp_wait_for_turn(
            driver,
            timeout=30,
            min_tool_cards=1,
            native_process=_FakeProcess(-1073741819),
        )
        self.assertEqual(result["state"], "native_process_exited")
        self.assertEqual(result["native_process_error"], "native_process_exited")
        self.assertEqual(result["native_process_details"]["stage"], "turn_observation")
        driver.approval_evidence.assert_not_called()

    def test_submit_baseline_is_captured_before_fast_card_mount(self):
        class _FastCardDriver:
            def __init__(self):
                self.cards = 0

            def tool_card_count(self):
                return self.cards

            def submit_prompt(self, _prompt):
                # Model/UI work can synchronously mount the card before the
                # submit call returns.
                self.cards += 1
                return True

        driver = _FastCardDriver()
        submitted, baseline = submit_prompt_with_card_baseline(driver, "open the official Python website")
        self.assertTrue(submitted)
        self.assertEqual(baseline, 0)
        self.assertEqual(driver.tool_card_count(), baseline + 1)

    def test_read_only_text_reader_accepts_direct_uia_patterns(self):
        values = _uia_control_text(_DirectReaderControl(), _PatternIds())
        self.assertIn(("uia_text_pattern", "LocalComet isolated smoke test."), values)
        self.assertIn(("uia_value_pattern", "LocalComet isolated smoke test."), values)

    def test_correlation_requires_real_ids_and_prompt_matches_model_event(self):
        observation = {
            "approval_prompt": {
                "approval_request_id": APPROVAL_PROMPT_ID,
                "model_request_id": REQUEST_ID,
                "model_action_id": MODEL_ACTION_ID,
            }
        }
        evidence = {
            "request_id": REQUEST_ID,
            "action_id": MODEL_ACTION_ID,
            "approval_id": APPROVAL_ID,
            "approval_call_id": APPROVAL_CALL_ID,
            "input_digest": INPUT_DIGEST,
        }
        result = validate_correlation(observation, evidence, approvals=1)
        failed_checks = [key for key, value in result["checks"].items() if not value]
        self.assertEqual(failed_checks, [], result["checks"])
        self.assertEqual(result["status"], "validated", result)

    def test_correlation_missing_ids_is_incomplete_not_green(self):
        result = validate_correlation(
            {"approval_prompt": {"approval_request_id": APPROVAL_PROMPT_ID}},
            {"request_id": "not-exposed", "action_id": "", "approval_id": "", "approval_call_id": "", "input_digest": ""},
            approvals=1,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "incomplete")

    def test_screenshot_requires_present_png_evidence_metadata(self):
        valid = validate_screenshot_evidence(
            {
                "screenshot_present": True,
                "screenshot_sha256": SCREENSHOT_SHA,
                "screenshot_backend": "printwindow",
                "screenshot_scope": "window",
                "screenshot_bytes": "1234",
                "screenshot_capture_pid": "4242",
            },
            expected_pid=4242,
        )
        self.assertTrue(valid["ok"])
        mismatch = validate_screenshot_evidence(
            {
                "screenshot_present": True,
                "screenshot_sha256": SCREENSHOT_SHA,
                "screenshot_backend": "gdi_bitblt",
                "screenshot_scope": "window",
                "screenshot_bytes": "1234",
                "screenshot_capture_pid": "9999",
            },
            expected_pid=4242,
        )
        self.assertFalse(mismatch["ok"])
        self.assertFalse(mismatch["checks"]["capture_pid_matches_owner"])
        invalid = validate_screenshot_evidence({
            "screenshot_present": True,
            "screenshot_sha256": "",
            "screenshot_backend": "",
            "screenshot_scope": "",
            "screenshot_bytes": "0",
        })
        self.assertFalse(invalid["ok"])

    @mock.patch("run_isolated_hidden_desktop_cu.os.name", "nt")
    @mock.patch("run_isolated_hidden_desktop_cu.subprocess.run")
    def test_browser_listener_identity_requires_exact_pid_port_and_profile(self, run):
        profile = Path("C:/Users/DNS/AppData/Local/LocalCometHiddenCU/run/browser-user-data")
        process = {"ProcessId": 4321, "Name": "chrome.exe", "CommandLine": f'chrome.exe --remote-debugging-port=9333 --user-data-dir="{profile}"'}
        run.return_value = mock.Mock(returncode=0, stdout=json.dumps({"listeners": [4321], "process": process}))
        valid = browser_listener_identity(9333, 4321, profile)
        probe_script = run.call_args.args[0][-1]
        self.assertIn("$expectedPid=4321", probe_script)
        self.assertIn("ProcessId=' + $expectedPid", probe_script)
        self.assertNotIn("$pid=4321", probe_script)
        self.assertTrue(valid["ok"], valid)
        self.assertTrue(all(valid["checks"].values()))

        run.return_value = mock.Mock(returncode=0, stdout=json.dumps({"listeners": [9999], "process": process}))
        foreign = browser_listener_identity(9333, 4321, profile)
        self.assertFalse(foreign["ok"])
        self.assertFalse(foreign["checks"]["listener_owner_pid"])

        mismatched_profile = process | {"CommandLine": "chrome.exe --remote-debugging-port=9333 --user-data-dir=C:/foreign"}
        run.return_value = mock.Mock(returncode=0, stdout=json.dumps({"listeners": [4321], "process": mismatched_profile}))
        wrong_profile = browser_listener_identity(9333, 4321, profile)
        self.assertFalse(wrong_profile["ok"])
        self.assertFalse(wrong_profile["checks"]["isolated_profile"])

    def test_rendered_screenshot_persists_png_and_rejects_hash_mismatch(self):
        raw = b"\x89PNG\r\n\x1a\nrendered-window"
        data_url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")

        class _ScreenshotDriver:
            def eval(self, _expression, timeout=15.0):
                self.timeout = timeout
                return data_url

        expected = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "captured.png"
            valid = materialize_rendered_screenshot(_ScreenshotDriver(), output, expected)
            self.assertTrue(valid["ok"], valid)
            self.assertEqual(output.read_bytes(), raw)
            mismatch = materialize_rendered_screenshot(_ScreenshotDriver(), output, "0" * 64)
            self.assertFalse(mismatch["ok"])
            self.assertEqual(mismatch["reason"], "rendered screenshot hash mismatch")

    def test_cancel_terminal_only_and_full_safe_state_are_distinct(self):
        terminal_only = {
            "backend_acknowledged": True,
            "terminal_cancelled": True,
            "no_new_tool_cards": True,
            "composer_ready_after": True,
            "stop_control_gone": True,
        }
        self.assertTrue(cancel_terminal_only_verified(terminal_only))
        self.assertFalse(cancel_safe_state_verified(terminal_only))
        full = {
            **terminal_only,
            "host_continuation_correlated": True,
            "post_grant_revocation_verified": True,
            "no_stale_host_replay": True,
            "replay_rejected": True,
            "trace_secret_free": True,
        }
        self.assertTrue(cancel_safe_state_verified(full))
        for key in tuple(full):
            incomplete = dict(full)
            incomplete[key] = False
            self.assertFalse(cancel_safe_state_verified(incomplete), key)
        self.assertFalse(cancel_terminal_only_verified(None))
        self.assertFalse(cancel_safe_state_verified(None))

    def test_continuation_cancel_trace_requires_leased_revoke_and_no_replay(self):
        trace = [
            {
                "command": "cu_broker_continuation_consume",
                "args": {"grantRef": "<redacted:cgr>", "requestId": REQUEST_ID, "actionKind": "observe"},
                "response": {"status": "leased"},
            },
            {
                "command": "cu_broker_observe",
                "args": {"requestId": REQUEST_ID},
                "response": {"found": False},
            },
            {
                "command": "cu_broker_continuation_revoke",
                "args": {"grantRef": "<redacted:cgr>", "reason": "turn cancelled or stopped"},
                "response": {"revoked": 1},
            },
            {
                "event": "continuation_replay_rejected",
                "request_id": REQUEST_ID,
                "status": "continuation_replayed",
            },
        ]
        facts = continuation_cancel_trace_verified(trace, REQUEST_ID)
        self.assertTrue(facts["host_continuation_correlated"])
        self.assertTrue(facts["post_grant_revocation_verified"])
        self.assertTrue(facts["no_stale_host_replay"])
        self.assertTrue(facts["trace_secret_free"])

        replay = trace + [{"command": "cu_broker_observe", "args": {"requestId": REQUEST_ID}, "response": {"found": False}}]
        replay_facts = continuation_cancel_trace_verified(replay, REQUEST_ID)
        self.assertFalse(replay_facts["no_stale_host_replay"])
        no_replay = continuation_cancel_trace_verified(trace[:-1], REQUEST_ID)
        self.assertFalse(no_replay["replay_rejected"])
        self.assertFalse(cancel_safe_state_verified({
            "backend_acknowledged": True,
            "terminal_cancelled": True,
            "no_new_tool_cards": True,
            "composer_ready_after": True,
            "stop_control_gone": True,
            **no_replay,
        }))

        leaked = [
            {"command": "cu_broker_continuation_consume", "args": {"grantRef": "cgr_0123456789abcdef", "requestId": REQUEST_ID, "actionKind": "observe"}, "response": {"status": "leased"}},
            {"command": "cu_broker_continuation_revoke", "args": {"grantRef": "<redacted:cgr>"}, "response": {"revoked": 1}},
        ]
        leaked_facts = continuation_cancel_trace_verified(leaked, REQUEST_ID)
        self.assertFalse(leaked_facts["trace_secret_free"])

    def test_replay_rejection_requires_matching_request_and_typed_status(self):
        base = [
            {
                "command": "cu_broker_continuation_consume",
                "args": {"grantRef": "<redacted:cgr>", "requestId": REQUEST_ID, "actionKind": "observe"},
                "response": {"status": "leased"},
            },
            {
                "command": "cu_broker_observe",
                "args": {"requestId": REQUEST_ID},
                "response": {"found": False},
            },
            {
                "command": "cu_broker_continuation_revoke",
                "args": {"grantRef": "<redacted:cgr>", "reason": "turn cancelled or stopped"},
                "response": {"revoked": 1},
            },
        ]
        foreign = continuation_cancel_trace_verified(
            base + [{"event": "continuation_replay_rejected", "request_id": "deadbeef" + REQUEST_ID[8:], "status": "continuation_replayed"}],
            REQUEST_ID,
        )
        self.assertFalse(foreign["replay_rejected"])
        self.assertFalse(foreign["no_stale_host_replay"])
        untyped = continuation_cancel_trace_verified(
            base + [{"event": "continuation_replay_rejected", "request_id": REQUEST_ID, "status": "replay_rejected"}],
            REQUEST_ID,
        )
        self.assertFalse(untyped["replay_rejected"])
        self.assertFalse(untyped["no_stale_host_replay"])
        unexpected = continuation_cancel_trace_verified(
            base + [{"event": "continuation_replay_unexpected_success", "request_id": REQUEST_ID, "status": "unexpected_success"}],
            REQUEST_ID,
        )
        self.assertTrue(unexpected["replay_unexpected_success"])
        self.assertFalse(unexpected["no_stale_host_replay"])

    def test_replay_unexpected_success_fails_safe_state(self):
        terminal = {
            "backend_acknowledged": True,
            "terminal_cancelled": True,
            "no_new_tool_cards": True,
            "composer_ready_after": True,
            "stop_control_gone": True,
        }
        base = [
            {
                "command": "cu_broker_continuation_consume",
                "args": {"grantRef": "<redacted:cgr>", "requestId": REQUEST_ID, "actionKind": "observe"},
                "response": {"status": "leased"},
            },
            {
                "command": "cu_broker_observe",
                "args": {"requestId": REQUEST_ID},
                "response": {"found": False},
            },
            {
                "command": "cu_broker_continuation_revoke",
                "args": {"grantRef": "<redacted:cgr>", "reason": "turn cancelled or stopped"},
                "response": {"revoked": 1},
            },
        ]
        rejected = continuation_cancel_trace_verified(
            base + [{"event": "continuation_replay_rejected", "request_id": REQUEST_ID, "status": "continuation_replayed"}],
            REQUEST_ID,
        )
        self.assertTrue(cancel_safe_state_verified({**terminal, **rejected}))
        unexpected = continuation_cancel_trace_verified(
            base + [{"event": "continuation_replay_unexpected_success", "request_id": REQUEST_ID, "status": "unexpected_success"}],
            REQUEST_ID,
        )
        self.assertTrue(unexpected["replay_unexpected_success"])
        self.assertFalse(cancel_safe_state_verified({**terminal, **unexpected}))

    def test_guarded_pass_without_approval_is_not_independently_verified(self):
        self.assertIn("notepad_open_type", GUARDED_SCENARIO_IDS)
        correlation = validate_correlation(
            {},
            {"request_id": "", "action_id": "", "approval_id": "", "approval_call_id": "", "input_digest": ""},
            approvals=0,
            approval_required=True,
        )
        self.assertFalse(correlation["ok"])
        self.assertEqual(correlation["status"], "required_but_absent")
        self.assertEqual(
            classify_case(
                "PASS",
                0,
                True,
                correlation_ok=correlation["ok"],
                text_ok=True,
                approval_required=True,
            ),
            "NOT_INDEPENDENTLY_VERIFIED",
        )

    def test_guarded_session_capability_requires_digest_and_ids(self):
        evidence = {
            "request_id": REQUEST_ID,
            "action_id": MODEL_ACTION_ID,
            "input_digest": INPUT_DIGEST,
        }
        valid = validate_correlation(
            {}, evidence, approvals=0, session_capability_required=True, session_capability_ok=True
        )
        self.assertTrue(valid["ok"], valid)
        self.assertEqual(valid["status"], "session_capability_validated")
        self.assertEqual(
            classify_case(
                "PASS",
                0,
                True,
                correlation_ok=valid["ok"],
                text_ok=True,
                session_capability_required=True,
                session_capability_ok=True,
            ),
            "VERIFIED_SUCCESS",
        )
        missing_digest = validate_correlation(
            {}, {"request_id": REQUEST_ID, "action_id": MODEL_ACTION_ID},
            approvals=0,
            session_capability_required=True,
            session_capability_ok=True,
        )
        self.assertFalse(missing_digest["ok"])
        self.assertEqual(missing_digest["status"], "incomplete")

    def test_read_only_pass_without_approval_remains_not_required(self):
        correlation = validate_correlation({}, {}, approvals=0, approval_required=False)
        self.assertTrue(correlation["ok"])
        self.assertEqual(correlation["status"], "not_required")

    def test_pass_requires_text_and_screenshot_proof_when_requested(self):
        self.assertEqual(
            classify_case("PASS", 1, True, correlation_ok=True, text_required=True, text_ok=False),
            "NOT_INDEPENDENTLY_VERIFIED",
        )
        self.assertEqual(
            classify_case("PASS", 0, True, correlation_ok=True, screenshot_required=True, screenshot_ok=False),
            "NOT_INDEPENDENTLY_VERIFIED",
        )
        self.assertEqual(
            classify_case(
                "PASS",
                1,
                True,
                correlation_ok=True,
                text_required=True,
                text_ok=True,
                screenshot_required=True,
                screenshot_ok=True,
            ),
            "VERIFIED_SUCCESS",
        )

    def test_compile_verified_only_coding_result_requires_negatives_and_no_broken_bytes(self):
        parsed = {
            "result": {"status": "compile_verified_only"},
            "replay": {"rejected": True},
            "tamper": {"rejected": True},
            "compile_failure": {"status": "failed"},
        }
        fixture = {
            "exists": True,
            "content_matches_new": True,
            "rollback_restored_own_preimage": True,
            "left_broken": False,
        }
        self.assertEqual(classify_coding_result(parsed, fixture), ("CODING_FLOW_VERIFIED", "VERIFIED_SUCCESS"))
        broken_fixture = {**fixture, "left_broken": True}
        self.assertEqual(classify_coding_result(parsed, broken_fixture), ("ROLLBACK_UNPROVEN", "NOT_INDEPENDENTLY_VERIFIED"))
        missing_rollback_proof = {**fixture, "rollback_restored_own_preimage": False}
        self.assertEqual(classify_coding_result(parsed, missing_rollback_proof), ("ROLLBACK_UNPROVEN", "NOT_INDEPENDENTLY_VERIFIED"))

    def test_pass_without_correlation_is_never_verified(self):
        self.assertEqual(
            classify_case("PASS", 0, True),
            "NOT_INDEPENDENTLY_VERIFIED",
        )

    def test_browser_url_policy_requires_approved_https_target(self):
        self.assertTrue(
            _browser_target_matches(
                "https://www.youtube.com/watch?v=abc",
                "YouTube",
                "browser_youtube",
            )
        )
        self.assertTrue(
            _browser_target_matches(
                "https://docs.python.org/3/",
                "Python Documentation",
                "browser_readonly_search",
            )
        )
        self.assertTrue(
            _browser_target_matches(
                "https://learn.microsoft.com/en-us/windows/apps/windows-notepad",
                "Windows Notepad help",
                "browser_second_readonly_search",
            )
        )
        for url, title, scenario in (
            ("http://www.youtube.com/", "YouTube", "browser_youtube"),
            ("https://evil.example/", "YouTube", "browser_youtube"),
            ("https://python.org/", "", "browser_readonly_search"),
            ("https://learn.microsoft.com/en-us/windows/apps/", "Windows help", "browser_second_readonly_search"),
            ("https://user:pass@python.org/", "Python", "browser_readonly_search"),
        ):
            self.assertFalse(_browser_target_matches(url, title, scenario))

    def test_setup_action_prefers_stable_product_ids_and_excludes_hf_navigation(self):
        driver = CdpDriver()
        with mock.patch.object(driver, "eval", return_value="managed-primary") as evaluate:
            self.assertEqual(driver.click_setup_action(), "managed-primary")
        expression = evaluate.call_args.args[0]
        self.assertIn("managed-model-primary-action", expression)
        self.assertIn("chat-setup-local-ai", expression)
        self.assertIn("Настроить локальный AI", expression)
        self.assertNotIn("Подобрать модель", expression)

    def test_setup_diagnostics_is_bounded_and_structured(self):
        driver = CdpDriver()
        payload = {"drawer": True, "drawerState": "NotInstalled", "primary": [{"disabled": False}]}
        with mock.patch.object(driver, "eval", return_value=payload):
            self.assertEqual(driver.setup_diagnostics(), payload)

    def test_required_process_and_browser_proof_fail_closed_on_missing_values(self):
        self.assertEqual(
            classify_case(
                "PASS",
                0,
                None,
                correlation_ok=True,
                process_required=True,
            ),
            "NOT_INDEPENDENTLY_VERIFIED",
        )
        self.assertEqual(
            classify_case(
                "PASS",
                0,
                True,
                correlation_ok=True,
                browser_required=True,
                browser_ok=None,
            ),
            "NOT_INDEPENDENTLY_VERIFIED",
        )

    @mock.patch("run_isolated_hidden_desktop_cu.os.name", "nt")
    @mock.patch("run_isolated_hidden_desktop_cu._descendant_pids", return_value={100, 300, 0, 4})
    @mock.patch("run_isolated_hidden_desktop_cu.subprocess.run")
    def test_process_presence_requires_owned_observed_pid_and_exact_image(self, run, _descendants):
        run.return_value = mock.Mock(
            stdout='"chrome.exe","300","Console","1,234 K"\r\n',
            returncode=0,
        )
        self.assertTrue(_process_present(["chrome.exe"], [100], observed_pid=300))
        self.assertFalse(_process_present(["chrome.exe"], [100], observed_pid=301))
        run.return_value.stdout = '"explorer.exe","300","Console","1,234 K"\r\n'
        self.assertFalse(_process_present(["chrome.exe"], [100], observed_pid=300))
        self.assertEqual(run.call_args.args[0][0:3], ["tasklist", "/FI", "PID eq 300"])
        _descendants.assert_called()


if __name__ == "__main__":
    unittest.main()
