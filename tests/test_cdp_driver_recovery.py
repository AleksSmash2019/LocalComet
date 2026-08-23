"""Deterministic unit tests for CdpDriver WebSocket lifecycle recovery.

Covers the campaign_1000_final root cause: a stale WebSocket must never keep
receiving commands. Every test here is offline (fake connections only) and
bounded вЂ” no browser, no app spawn, no campaign evidence writes.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from run_isolated_hidden_desktop_cu import CdpDriver  # noqa: E402


TOKEN_RE = re.compile(r"lc-submit-[0-9a-f]{32}")


class FakeConn:
    """Scriptable stand-in for a websockets ClientConnection."""

    def __init__(self, script):
        self.sent: list[str] = []
        self.closed = False
        self._script = list(script)

    async def send(self, raw: str) -> None:
        self.sent.append(raw)

    async def recv(self):
        if not self._script:
            await asyncio.sleep(3600)
            return ""
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self) -> None:
        self.closed = True


class ResponsiveConn(FakeConn):
    """Auto-replies to the most recent command with a fixed value."""

    def __init__(self, value="answer"):
        super().__init__([])
        self.value = value

    async def recv(self):
        while not self.sent:
            await asyncio.sleep(3600)
        data = json.loads(self.sent[-1])
        return json.dumps({"id": data["id"], "result": {"result": {"value": self.value}}})


def reply(message_id: int, value) -> str:
    return json.dumps({"id": message_id, "result": {"result": {"value": value}}})


class CdpDriverRecoveryTests(unittest.TestCase):
    def test_recv_timeout_disposes_socket_and_reports_error(self) -> None:
        driver = CdpDriver()
        self.addCleanup(driver.close)
        conn = FakeConn([])  # recv hangs forever -> recv timeout
        driver._conn = conn
        establish_calls = []

        async def fake_establish():
            establish_calls.append(1)
            raise RuntimeError("cdp: no page target")

        driver._establish = fake_establish  # type: ignore[method-assign]
        result = driver.eval("1+1", timeout=0.2)
        self.assertIsInstance(result, dict)
        self.assertIn("__error", result)
        self.assertIn("cdp eval failed", result["__error"])
        # The stale socket was deterministically closed and never reused.
        self.assertTrue(conn.closed)
        self.assertIsNone(driver._conn)
        # Bounded budget: exactly one recovery attempt after the initial try.
        self.assertEqual(len(establish_calls), CdpDriver.CDP_MAX_ATTEMPTS - 1)
        self.assertTrue(driver.last_error.startswith("cdp eval failed"))

    def test_disconnect_triggers_reconnect_success(self) -> None:
        driver = CdpDriver()
        self.addCleanup(driver.close)
        bad = FakeConn([ConnectionResetError("socket closed")])
        good = ResponsiveConn("answer")
        driver._conn = bad
        closed_flags = []

        orig_aclose = CdpDriver._aclose_conn

        async def tracking_aclose(inner_self, c):
            closed_flags.append(c)
            await orig_aclose(inner_self, c)

        async def fake_establish():
            driver._conn = good
            return good

        driver._establish = fake_establish  # type: ignore[method-assign]
        with mock.patch.object(CdpDriver, "_aclose_conn", tracking_aclose):
            result = driver.eval("'q'", timeout=0.4)
        self.assertEqual(result, "answer")
        self.assertIn(bad, closed_flags)
        self.assertFalse(good.closed)

    def test_reconnect_failure_is_terminal_never_success(self) -> None:
        driver = CdpDriver()
        self.addCleanup(driver.close)
        conn = FakeConn([TimeoutError("cdp recv timeout")])
        driver._conn = conn
        establish_calls = []

        async def failing_establish():
            establish_calls.append(1)
            raise RuntimeError("cdp: no page target")

        driver._establish = failing_establish  # type: ignore[method-assign]
        result = driver.eval("1+1", timeout=0.2)
        self.assertIsInstance(result, dict)
        self.assertNotIn("value", result)
        self.assertTrue(str(result.get("__error", "")))
        self.assertEqual(len(establish_calls), CdpDriver.CDP_MAX_ATTEMPTS - 1)
        self.assertTrue(conn.closed)

    def test_stale_page_identity_fails_closed(self) -> None:
        driver = CdpDriver()
        self.addCleanup(driver.close)
        self.addCleanup(driver.close)
        with mock.patch.object(driver, "_list_page_targets", return_value=[]):
            with self.assertRaises(RuntimeError):
                driver._ensure_loop().run_until_complete(driver._establish())
        foreign = {"type": "page", "url": "http://127.0.0.1:9999/", "webSocketDebuggerUrl": "ws://x"}
        with mock.patch.object(driver, "_list_page_targets", return_value=[foreign]):
            with self.assertRaises(RuntimeError):
                driver._ensure_loop().run_until_complete(driver._establish())
        self.assertIsNone(driver._conn)

    def test_establish_accepts_only_isolated_port_page(self) -> None:
        driver = CdpDriver()
        self.addCleanup(driver.close)
        ours = {
            "type": "page",
            "url": "http://localhost:1423/",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1",
        }
        sent = []

        async def fake_ws_connect(url, **kwargs):
            sent.append((url, kwargs))
            return FakeConn([])

        fake_ws_module = types.SimpleNamespace(connect=fake_ws_connect)
        with mock.patch.dict(sys.modules, {"websockets": fake_ws_module}):
            with mock.patch.object(driver, "_list_page_targets", return_value=[ours]):
                conn = driver._ensure_loop().run_until_complete(driver._establish())
        self.assertIsInstance(conn, FakeConn)
        self.assertIn(":1423", driver.target_url)
        url_used, kwargs = sent[0]
        self.assertEqual(url_used, "ws://127.0.0.1:9223/devtools/page/1")
        self.assertTrue(kwargs.get("open_timeout"))

    def test_retry_resends_identical_expression_for_idempotency(self) -> None:
        # Attempt 1 times out AFTER send; attempt 2 must resend the exact same
        # expression (stable submit token) so the page-side guard prevents a
        # duplicate prompt click.
        driver = CdpDriver()
        self.addCleanup(driver.close)
        expressions: list[str] = []

        async def evaluate_spy(inner_self, expression, timeout=10.0, await_promise=False):
            expressions.append(expression)
            if len(expressions) == 1:
                raise TimeoutError("cdp recv timeout")
            return "submitted"

        with mock.patch.object(CdpDriver, "_evaluate", evaluate_spy):
            with mock.patch.object(CdpDriver, "_dispose_socket", lambda inner_self: None):
                driver.submit_prompt("РїСЂРёРІРµС‚")
        self.assertEqual(len(expressions), CdpDriver.CDP_MAX_ATTEMPTS)
        self.assertEqual(expressions[0], expressions[1])
        self.assertEqual(len(TOKEN_RE.findall(expressions[0])), 1)

    def test_duplicate_submission_token_differs_between_prompts(self) -> None:
        driver = CdpDriver()
        self.addCleanup(driver.close)
        seen: list[str] = []

        def fake_eval(inner_self, expression, timeout=10.0, await_promise=False):
            seen.append(expression)
            return "submitted"

        with mock.patch.object(CdpDriver, "eval", fake_eval):
            driver.submit_prompt("РїРµСЂРІС‹Р№")
            driver.submit_prompt("РІС‚РѕСЂРѕР№")
        tokens = [TOKEN_RE.findall(e)[0] for e in seen]
        self.assertEqual(len(tokens), 2)
        self.assertNotEqual(tokens[0], tokens[1])

    def test_submit_prompt_accepts_already_submitted_and_rejects_no_send(self) -> None:
        driver = CdpDriver()
        self.addCleanup(driver.close)
        with mock.patch.object(driver, "eval", return_value="already-submitted"):
            self.assertTrue(driver.submit_prompt("С‚РµРєСЃС‚"))
        with mock.patch.object(driver, "eval", return_value="no-send"):
            self.assertFalse(driver.submit_prompt("С‚РµРєСЃС‚"))
        with mock.patch.object(driver, "eval", return_value={"__error": "cdp eval failed: x"}):
            self.assertFalse(driver.submit_prompt("С‚РµРєСЃС‚"))

    def test_close_disposes_socket_and_loop(self) -> None:
        driver = CdpDriver()
        self.addCleanup(driver.close)
        conn = FakeConn([])
        driver._conn = conn
        driver.eval("'warm'", timeout=0.2)
        self.assertIsNotNone(driver._loop)
        driver.close()
        self.assertTrue(conn.closed)
        self.assertIsNone(driver._conn)
        self.assertIsNone(driver._loop)


if __name__ == "__main__":
    unittest.main()
