"""Offline contract tests for isolated hidden-desktop CDP startup (P0.1).

Root cause under test (2026-08-22 smoke): a stale prebuilt Tauri binary kept
its compile-time devUrl (:1420), loaded a FOREIGN dev-server page, and the
run blocked on "no page target" while clicking blindly for minutes. These
tests pin the fail-closed contract: binary reuse requires byte-level
provenance, CDP startup requires an answering endpoint serving OUR page URL,
and every failure is classified as explicit infrastructure error.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_isolated_hidden_desktop_cu as harness  # noqa: E402


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BinaryProvenanceTests(unittest.TestCase):
    """A cached binary may be reused ONLY with verified sha + matching devUrl."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _seed(
        self,
        dev_url: str = "http://127.0.0.1:1423",
        payload: bytes = b"MZ-fake-binary",
        source_fingerprint: str | None = None,
    ) -> Path:
        binary = self.root / "localcomet-desktop.exe"
        binary.write_bytes(payload)
        marker = {
            "dev_url": dev_url,
            "sha256": _sha(payload),
            "recorded_utc": "2026-08-22T00:00:00+00:00",
        }
        if source_fingerprint is not None:
            marker["source_fingerprint"] = source_fingerprint
        harness.binary_provenance_path(binary).write_text(json.dumps(marker), encoding="utf-8")
        return binary

    def test_reusable_when_sha_and_dev_url_match(self) -> None:
        binary = self._seed()
        result = harness.evaluate_binary_provenance(binary, "http://127.0.0.1:1423")
        self.assertTrue(result["usable"])
        self.assertEqual(result["reason"], "verified")

    def test_rebuild_when_binary_missing(self) -> None:
        binary = self.root / "localcomet-desktop.exe"
        result = harness.evaluate_binary_provenance(binary, "http://127.0.0.1:1423")
        self.assertFalse(result["usable"])
        self.assertEqual(result["reason"], "binary_missing")

    def test_rebuild_when_marker_missing(self) -> None:
        binary = self.root / "localcomet-desktop.exe"
        binary.write_bytes(b"MZ-unmarked")
        result = harness.evaluate_binary_provenance(binary, "http://127.0.0.1:1423")
        self.assertFalse(result["usable"])
        self.assertEqual(result["reason"], "provenance_marker_missing")

    def test_rebuild_when_dev_url_differs(self) -> None:
        # The exact 8/21 failure mode: binary built against :1420, run needs :1423.
        binary = self._seed(dev_url="http://localhost:1420")
        result = harness.evaluate_binary_provenance(binary, "http://127.0.0.1:1423")
        self.assertFalse(result["usable"])
        self.assertEqual(result["reason"], "dev_url_mismatch")
        self.assertEqual(result["marked_dev_url"], "http://localhost:1420")

    def test_rebuild_when_binary_bytes_changed(self) -> None:
        binary = self._seed()
        binary.write_bytes(b"MZ-tampered")
        result = harness.evaluate_binary_provenance(binary, "http://127.0.0.1:1423")
        self.assertFalse(result["usable"])
        self.assertEqual(result["reason"], "binary_sha256_mismatch")

    def test_rebuild_when_source_fingerprint_is_missing(self) -> None:
        binary = self._seed()
        fingerprint = harness.rust_build_input_fingerprint(ROOT)
        result = harness.evaluate_binary_provenance(binary, "http://127.0.0.1:1423", fingerprint)
        self.assertFalse(result["usable"])
        self.assertEqual(result["reason"], "source_fingerprint_missing")

    def test_reuse_when_source_fingerprint_matches(self) -> None:
        fingerprint = harness.rust_build_input_fingerprint(ROOT)
        binary = self._seed(source_fingerprint=fingerprint)
        result = harness.evaluate_binary_provenance(binary, "http://127.0.0.1:1423", fingerprint)
        self.assertTrue(result["usable"])
        self.assertEqual(result["reason"], "verified")
        self.assertEqual(result["source_fingerprint"], fingerprint)

    def test_rebuild_when_source_fingerprint_differs(self) -> None:
        fingerprint = harness.rust_build_input_fingerprint(ROOT)
        binary = self._seed(source_fingerprint="0" * 64)
        result = harness.evaluate_binary_provenance(binary, "http://127.0.0.1:1423", fingerprint)
        self.assertFalse(result["usable"])
        self.assertEqual(result["reason"], "source_fingerprint_mismatch")


class CdpCleanupContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_waits_for_socket_and_cancels_keepalive_tasks(self) -> None:
        events: list[str] = []

        class FakeConnection:
            async def close(self) -> None:
                events.append("close")

            async def wait_closed(self) -> None:
                events.append("wait_closed")

        driver = harness.CdpDriver()
        await driver._aclose_conn(FakeConnection())
        self.assertEqual(events, ["close", "wait_closed"])
        source = Path(harness.__file__).read_text(encoding="utf-8")
        self.assertIn("ping_interval=None", source)
        self.assertIn("asyncio.SelectorEventLoop()", source)


class ApprovalModalSelectorContractTests(unittest.TestCase):
    def test_hidden_approval_observation_and_click_cover_alertdialog(self) -> None:
        source = Path(harness.__file__).read_text(encoding="utf-8")
        selector = "[role=alertdialog][data-approval-request-id]"
        self.assertGreaterEqual(source.count(selector), 2)
        self.assertIn(selector, harness.APPROVAL_EXPRESSION)


class HiddenBrowserProfilePathTests(unittest.TestCase):
    def test_profile_is_under_worker_localappdata_hidden_root(self) -> None:
        isolated_root = Path("C:/Temp/LocalCometHiddenCU/run-001")
        expected = isolated_root / "LocalCometHiddenCU" / "browser-user-data"
        self.assertEqual(harness.hidden_browser_profile_path(isolated_root), expected)


class WaitForIsolatedPageTests(unittest.TestCase):
    """Startup authority: endpoint answers AND serves OUR dev-server port."""

    VITE = 1423

    def test_success_on_matching_page_url(self) -> None:
        fetch = mock.Mock(return_value=[{"type": "page", "url": "http://127.0.0.1:1423/"}])
        state = harness.wait_for_isolated_page(9223, self.VITE, 1.0, fetch=fetch, sleep=lambda *_: None)
        self.assertTrue(state["ok"])
        self.assertEqual(state["page_url"], "http://127.0.0.1:1423/")
        self.assertEqual(state["foreign_urls"], [])

    def test_foreign_page_target_is_classified_with_observed_urls(self) -> None:
        # The exact 8/21 evidence: hidden webview rendered someone else's :1420.
        fetch = mock.Mock(return_value=[{"type": "page", "url": "http://localhost:1420/"}])
        with self.assertRaises(harness.IsolatedStartupError) as ctx:
            harness.wait_for_isolated_page(9223, self.VITE, 0.05, fetch=fetch, sleep=lambda *_: None)
        self.assertEqual(ctx.exception.error_type, "cdp_foreign_page_target")
        self.assertIn("localhost:1420", str(ctx.exception))
        self.assertEqual(ctx.exception.details.get("foreign_urls"), ["http://localhost:1420/"])

    def test_endpoint_never_listening_is_classified(self) -> None:
        fetch = mock.Mock(side_effect=OSError("connection refused"))
        with self.assertRaises(harness.IsolatedStartupError) as ctx:
            harness.wait_for_isolated_page(9223, self.VITE, 0.05, fetch=fetch, sleep=lambda *_: None)
        self.assertEqual(ctx.exception.error_type, "cdp_endpoint_not_listening")

    def test_late_match_within_timeout_succeeds(self) -> None:
        responses = [
            OSError("not yet"),
            [{"type": "page", "url": "http://localhost:1420/"}],
            [{"type": "page", "url": "http://127.0.0.1:1423/"}, {"type": "iframe", "url": "x"}],
        ]

        def flaky(_port: int):
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        state = harness.wait_for_isolated_page(9223, self.VITE, 1.0, fetch=flaky, sleep=lambda *_: None)
        self.assertTrue(state["ok"])
        self.assertEqual(state["page_url"], "http://127.0.0.1:1423/")


class EstablishDiagnosticsTests(unittest.TestCase):
    """Fail-closed reconnect must name the observed foreign targets."""

    def test_establish_error_includes_observed_foreign_urls(self) -> None:
        driver = harness.CdpDriver()
        self.addCleanup(driver.close)
        foreign = [{"type": "page", "url": "http://localhost:1420/", "webSocketDebuggerUrl": "ws://x"}]
        with mock.patch.object(driver, "_list_page_targets", return_value=[]):
            with mock.patch.object(driver, "_diagnose_targets", return_value=["http://localhost:1420/"]):
                with self.assertRaises(RuntimeError) as ctx:
                    driver._ensure_loop().run_until_complete(driver._establish())
        self.assertIsNone(driver._conn)
        message = str(ctx.exception)
        self.assertIn("no page target on isolated port 1423", message)
        self.assertIn("http://localhost:1420/", message)


class JobObjectContractTests(unittest.TestCase):
    """Owner-scoped cleanup lease constants and structure layout."""

    def test_kill_on_job_close_flag(self) -> None:
        self.assertEqual(harness.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, 0x00002000)

    def test_extended_limit_structure_accepts_kill_flags(self) -> None:
        limits = harness.JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = (
            harness.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | harness.JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK
        )
        self.assertEqual(
            limits.BasicLimitInformation.LimitFlags,
            0x00002000 | 0x00001000,
        )
        self.assertGreater(harness.ctypes.sizeof(limits), 0)


class CleanupContractTests(unittest.TestCase):
    @mock.patch.object(harness.os, "name", "nt")
    @mock.patch.object(harness.subprocess, "run")
    def test_cleanup_is_scoped_to_owned_root_pids(self, run: mock.Mock) -> None:
        run.return_value.returncode = 0
        run.return_value.stdout = "terminated"
        run.return_value.stderr = ""
        result = harness.cleanup_owned_process_tree([101, 101, 202, 0, -1])
        self.assertEqual(result["root_pids"], [101, 101, 202, 0, -1])
        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(calls, [
            ["taskkill", "/PID", "101", "/T", "/F"],
            ["taskkill", "/PID", "202", "/T", "/F"],
        ])
        self.assertEqual(result["results"][0]["returncode"], 0)


class HiddenScenarioSelectionContractTests(unittest.TestCase):
    def test_default_automatic_candidates_exclude_calculator(self) -> None:
        ids = [item["id"] for item in harness.AUTO_SCENARIOS]
        self.assertNotIn("calculator_basic", ids)
        self.assertNotIn("calculator_repeat", ids)
        self.assertTrue({"notepad_open_type", "browser_youtube", "computer_use_click"}.issubset(ids))
        self.assertEqual(
            set(item["id"] for item in harness.SCENARIOS) - set(ids),
            set(harness.DISABLED_AUTO_SCENARIO_IDS),
        )

    def test_parent_forwards_one_case_and_explicit_scenario_to_worker(self) -> None:
        source = Path(harness.__file__).read_text(encoding="utf-8")
        self.assertIn('"--cases", str(cases)', source)
        self.assertIn('"--scenario", scenario_id', source)
        self.assertIn('scenario_pool = SCENARIOS if args.scenario else AUTO_SCENARIOS', source)
        self.assertIn('if args.scenario in DISABLED_AUTO_SCENARIO_IDS', source)


class ExpectedDevUrlTests(unittest.TestCase):
    def test_matches_patched_workspace_config_format(self) -> None:
        # patch_isolated_workspace_port rewrites devUrl to http://127.0.0.1:<port>
        # (no trailing slash); provenance markers must use the same form.
        self.assertEqual(harness.expected_isolated_dev_url(1423), "http://127.0.0.1:1423")
        self.assertRegex(harness.expected_isolated_dev_url(), r"^http://127\.0\.0\.1:\d+$")


if __name__ == "__main__":
    unittest.main()
