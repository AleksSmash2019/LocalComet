from __future__ import annotations

import time
from typing import Any, Mapping

TERMINAL_METHODS = frozenset(("model.turn.completed", "model.turn.cancelled", "model.turn.timed_out", "model.turn.failed"))

def wait_for_terminal(events: list[tuple[str, str, int, Mapping[str, Any]]], timeout: float = 3.0, *, latest_only: bool = False) -> tuple[str, str, int, Mapping[str, Any]]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        candidates = [events[-1]] if latest_only and events else events
        terminals = [event for event in candidates if event[0] in TERMINAL_METHODS]
        if terminals:
            return terminals[-1]
        time.sleep(0.005)
    raise AssertionError(f"model turn did not terminate: {[event[0] for event in events]}")
