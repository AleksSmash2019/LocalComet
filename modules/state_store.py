"""State store facade for LocalComet agents (T11).

Agents should import `get_value`, `set_value`, `load_state` from this module
rather than directly from `core.state`.  This keeps the agent layer decoupled
from the core internals and provides a single choke point for future
observability hooks (telemetry, validation, caching).

Current implementation: thin delegation to `core.state` with no added logic.
"""

from __future__ import annotations

from core.state import get_value, load_state, save_state, set_value

__all__ = ["get_value", "load_state", "save_state", "set_value"]
