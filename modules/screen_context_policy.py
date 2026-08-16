"""Default-off screen-context policy with no synthetic capture fallback.

The module owns policy and retention only. A real capture adapter must provide
an observation explicitly; when capture is disabled or unavailable no event is
created and no placeholder data is returned.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Protocol

MAX_OBSERVATION_CHARS = 50_000
DEFAULT_RETENTION_SECONDS = 300
DEFAULT_MAX_CONTEXT_AGE_SECONDS = 30
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
SECRET_RE = re.compile(r"\b(?:sk|token|secret|api[_-]?key)[=:][^\s,;]+", re.IGNORECASE)


class ScreenContextError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class ScreenContextConfig:
    capture_enabled: bool = False
    audio_enabled: bool = False
    paused: bool = False
    denylisted_apps: frozenset[str] = frozenset()
    retention_seconds: int = DEFAULT_RETENTION_SECONDS
    max_context_age_seconds: int = DEFAULT_MAX_CONTEXT_AGE_SECONDS

    def __post_init__(self) -> None:
        if self.retention_seconds < 0 or self.max_context_age_seconds < 0:
            raise ValueError("retention and context age must be non-negative")


@dataclass(frozen=True, slots=True)
class ScreenObservation:
    context_id: str
    app_id: str
    captured_at_unix_ms: int
    redacted_text: str
    source: str = "screen_adapter"


class ScreenCaptureAdapter(Protocol):
    def capture(self) -> Mapping[str, object]:
        """Return adapter-owned observation data; never called while disabled."""


def redact_screen_text(text: str) -> str:
    if not isinstance(text, str):
        raise ScreenContextError("INVALID_OBSERVATION", "screen text must be a string")
    if len(text) > MAX_OBSERVATION_CHARS:
        raise ScreenContextError("OBSERVATION_TOO_LARGE", "screen observation exceeds the size limit")
    redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    return SECRET_RE.sub(lambda match: match.group(0).split("=", 1)[0] + "=[REDACTED_SECRET]", redacted)


class ScreenContextController:
    def __init__(
        self,
        config: ScreenContextConfig | None = None,
        *,
        clock: callable = time.time,
    ) -> None:
        self.config = config or ScreenContextConfig()
        self._clock = clock
        self._events: dict[str, ScreenObservation] = {}

    def status(self) -> dict[str, object]:
        return {
            "capture_enabled": self.config.capture_enabled,
            "audio_enabled": self.config.audio_enabled,
            "paused": self.config.paused,
            "active_indicator": bool(self.config.capture_enabled and not self.config.paused),
            "retention_seconds": self.config.retention_seconds,
            "stored_events": len(self._events),
        }

    def set_paused(self, paused: bool) -> dict[str, object]:
        self.config = ScreenContextConfig(
            capture_enabled=self.config.capture_enabled,
            audio_enabled=self.config.audio_enabled,
            paused=bool(paused),
            denylisted_apps=self.config.denylisted_apps,
            retention_seconds=self.config.retention_seconds,
            max_context_age_seconds=self.config.max_context_age_seconds,
        )
        return self.status()

    def capture(self, adapter: ScreenCaptureAdapter | None = None) -> ScreenObservation | None:
        if not self.config.capture_enabled or self.config.paused:
            return None
        if adapter is None:
            raise ScreenContextError("CAPTURE_ADAPTER_UNAVAILABLE", "screen capture adapter is not configured")
        payload = adapter.capture()
        app_id = payload.get("app_id")
        text = payload.get("text", "")
        captured_at = payload.get("captured_at_unix_ms", int(self._clock() * 1000))
        if not isinstance(app_id, str) or not app_id.strip():
            raise ScreenContextError("INVALID_OBSERVATION", "screen observation app_id is required")
        if app_id.casefold() in self.config.denylisted_apps:
            return None
        if not isinstance(captured_at, int) or isinstance(captured_at, bool):
            raise ScreenContextError("INVALID_OBSERVATION", "capture timestamp is invalid")
        redacted = redact_screen_text(text)
        material = f"{app_id}\0{captured_at}\0{redacted}".encode("utf-8")
        context_id = "screen-" + hashlib.sha256(material).hexdigest()[:24]
        observation = ScreenObservation(context_id, app_id, captured_at, redacted)
        self._events[context_id] = observation
        self.purge_expired()
        return observation

    def retrieve(self, context_id: str, *, now_unix_ms: int | None = None) -> ScreenObservation:
        observation = self._events.get(context_id)
        if observation is None:
            raise ScreenContextError("CONTEXT_NOT_FOUND", "screen context was not found")
        now = now_unix_ms if now_unix_ms is not None else int(self._clock() * 1000)
        age_ms = now - observation.captured_at_unix_ms
        if age_ms < 0 or age_ms > self.config.max_context_age_seconds * 1000:
            raise ScreenContextError("CONTEXT_EXPIRED", "screen context has expired")
        return observation

    def purge_expired(self, *, now_unix_ms: int | None = None) -> int:
        now = now_unix_ms if now_unix_ms is not None else int(self._clock() * 1000)
        cutoff = now - self.config.retention_seconds * 1000
        expired = [
            context_id
            for context_id, observation in self._events.items()
            if observation.captured_at_unix_ms < cutoff
        ]
        for context_id in expired:
            self._events.pop(context_id, None)
        return len(expired)

    def delete_all(self) -> dict[str, object]:
        self._events.clear()
        verified = not self._events
        if not verified:
            raise ScreenContextError("DELETE_ALL_UNVERIFIED", "screen context deletion could not be verified")
        return {"deleted": True, "verified": True}


__all__ = [
    "ScreenCaptureAdapter",
    "ScreenContextConfig",
    "ScreenContextController",
    "ScreenContextError",
    "ScreenObservation",
    "redact_screen_text",
]
