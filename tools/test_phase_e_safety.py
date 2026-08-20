from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from modules.browser_safety_policy import BrowserSafetyPolicy, BrowserStatus
from modules.screen_context_policy import (
    ScreenContextConfig,
    ScreenContextController,
    ScreenContextError,
)


class FakeCapture:
    def __init__(self, app_id: str = "editor", text: str = "contact a@example.com token=secret") -> None:
        self.app_id = app_id
        self.text = text

    def capture(self) -> dict[str, object]:
        return {"app_id": self.app_id, "text": self.text, "captured_at_unix_ms": 1_000}


def test_screen_capture_is_default_off_and_does_not_create_event() -> None:
    controller = ScreenContextController(clock=lambda: 1.0)
    assert controller.capture(FakeCapture()) is None
    assert controller.status()["stored_events"] == 0


def test_screen_pause_and_denied_app_do_not_create_event() -> None:
    paused = ScreenContextController(
        ScreenContextConfig(capture_enabled=True, paused=True), clock=lambda: 1.0
    )
    assert paused.capture(FakeCapture()) is None

    denied = ScreenContextController(
        ScreenContextConfig(capture_enabled=True, denylisted_apps=frozenset({"blocked-app"})),
        clock=lambda: 1.0,
    )
    assert denied.capture(FakeCapture(app_id="blocked-app")) is None
    assert denied.status()["stored_events"] == 0


def test_screen_capture_redacts_and_expiry_blocks_retrieval() -> None:
    controller = ScreenContextController(
        ScreenContextConfig(capture_enabled=True, max_context_age_seconds=2),
        clock=lambda: 1.0,
    )
    observation = controller.capture(FakeCapture())
    assert observation is not None
    assert "a@example.com" not in observation.redacted_text
    assert "secret" not in observation.redacted_text
    assert controller.retrieve(observation.context_id, now_unix_ms=2_000) == observation
    with pytest.raises(ScreenContextError) as expired:
        controller.retrieve(observation.context_id, now_unix_ms=4_000)
    assert expired.value.code == "CONTEXT_EXPIRED"


def test_screen_delete_all_is_verified() -> None:
    controller = ScreenContextController(ScreenContextConfig(capture_enabled=True), clock=lambda: 1.0)
    observation = controller.capture(FakeCapture())
    assert observation is not None
    assert controller.delete_all() == {"deleted": True, "verified": True}
    assert controller.status()["stored_events"] == 0


def test_browser_read_only_allowlist_and_dangerous_action_barrier() -> None:
    policy = BrowserSafetyPolicy({"example.com"})
    read = policy.decide(url="https://docs.example.com/page", action="read")
    assert read.status is BrowserStatus.ALLOWED

    blocked = policy.decide(url="https://example.com/account", action="submit")
    assert blocked.status is BrowserStatus.BLOCKED
    assert blocked.reason_code == "APPROVAL_REQUIRED"
    assert blocked.requires_approval is True

    approved = policy.decide(url="https://example.com/account", action="submit", approval_present=True)
    assert approved.status is BrowserStatus.ALLOWED

    with pytest.raises(Exception):
        policy.decide(url="https://evil.example.net", action="read")


def test_browser_login_captcha_and_2fa_wait_for_user() -> None:
    policy = BrowserSafetyPolicy({"example.com"})
    for signal in ("login", "captcha", "2fa"):
        decision = policy.decide(url="https://example.com", action="read", user_intervention_signal=signal)
        assert decision.status is BrowserStatus.WAITING_FOR_USER
        assert decision.reason_code == "USER_INTERVENTION_REQUIRED"
        assert decision.takeover_reason == signal
