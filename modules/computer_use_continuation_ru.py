from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from typing import FrozenSet, Optional

CONTINUATION_VERSION = "v1"
MAX_STEPS = 6
CONTINUATION_TTL_MS = 30_000
PER_STEP_TIMEOUT_MS = 5_000
WALL_CLOCK_TIMEOUT_MS = 120_000


@dataclass(frozen=True)
class ContinuationCapability:
    token: str
    parent_request_id: str
    parent_action_id: str
    parent_digest: str
    per_step_digest: str
    session: str
    step_index: int
    allowed_next_actions: FrozenSet[str]
    target: str
    pid: Optional[int]
    desktop: Optional[str]
    expires_at_ms: int
    remaining_steps: int
    issued_at_ms: int


_lock = threading.Lock()
_store: dict[str, ContinuationCapability] = {}
_consumed: set[str] = set()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _canonical_digest_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def issue_continuation(
    *,
    parent_request_id: str,
    parent_action_id: str,
    parent_digest: str,
    per_step_digest: str,
    session: str,
    step_index: int,
    allowed_next_actions: set[str] | FrozenSet[str],
    target: str,
    pid: Optional[int],
    desktop: Optional[str],
    remaining_steps: int,
    ttl_ms: int = CONTINUATION_TTL_MS,
) -> ContinuationCapability:
    if not parent_request_id or not parent_action_id:
        raise ValueError("parent correlation missing")
    if len(parent_digest) != 64 or len(per_step_digest) != 64:
        raise ValueError("digest must be 64 hex")
    if not session:
        raise ValueError("session missing")
    if not (0 <= step_index < MAX_STEPS):
        raise ValueError("step_index out of range")
    if remaining_steps < 0 or remaining_steps > MAX_STEPS:
        raise ValueError("remaining_steps out of range")
    if ttl_ms <= 0 or ttl_ms > 600_000:
        raise ValueError("ttl out of range")
    allowed = frozenset(a.strip().lower() for a in allowed_next_actions if a.strip())
    if not allowed:
        raise ValueError("allowed_next_actions empty")
    token = "cont_" + secrets.token_hex(16)
    now = _now_ms()
    cap = ContinuationCapability(
        token=token,
        parent_request_id=parent_request_id,
        parent_action_id=parent_action_id,
        parent_digest=parent_digest.lower(),
        per_step_digest=per_step_digest.lower(),
        session=session.lower(),
        step_index=step_index,
        allowed_next_actions=allowed,
        target=target.strip().lower(),
        pid=pid,
        desktop=(desktop or "").strip().lower() or None,
        expires_at_ms=now + ttl_ms,
        remaining_steps=remaining_steps,
        issued_at_ms=now,
    )
    with _lock:
        _store[token] = cap
        # prune expired
        for key, val in list(_store.items()):
            if val.expires_at_ms <= now:
                _store.pop(key, None)
    return cap


def validate_continuation(
    token: str,
    *,
    expected_parent_digest: str,
    expected_per_step_digest: str,
    expected_step_index: int,
    expected_target: str,
    expected_session: str,
    expected_action: str,
) -> ContinuationCapability:
    if not token or not token.startswith("cont_"):
        raise ValueError("continuation token is missing or invalid")
    now = _now_ms()
    with _lock:
        cap = _store.get(token)
        if cap is None:
            if token in _consumed:
                raise ValueError("continuation was already used (one-time)")
            raise ValueError("continuation not found or expired")
        if token in _consumed:
            raise ValueError("continuation was already used (one-time)")
        if cap.expires_at_ms <= now:
            _store.pop(token, None)
            raise ValueError("continuation window expired before readiness was observed")
        if cap.parent_digest != expected_parent_digest.lower():
            raise ValueError("continuation parent digest mismatch")
        if cap.per_step_digest != expected_per_step_digest.lower():
            raise ValueError("continuation per-step digest mismatch")
        if cap.step_index != expected_step_index:
            raise ValueError("continuation step order mismatch")
        if cap.session != expected_session.lower():
            raise ValueError("continuation session mismatch")
        if cap.target != expected_target.strip().lower():
            raise ValueError("continuation wrong target")
        if expected_action.strip().lower() not in cap.allowed_next_actions:
            raise ValueError("continuation wrong order: action not allowed")
        if cap.remaining_steps <= 0:
            raise ValueError("continuation remaining-step budget exhausted")
        # one-time use: mark consumed
        _consumed.add(token)
        _store.pop(token, None)
        return cap


def peek_continuation(token: str) -> Optional[ContinuationCapability]:
    with _lock:
        return _store.get(token)


def clear_store() -> None:
    with _lock:
        _store.clear()
        _consumed.clear()


def _prune_expired() -> None:
    now = _now_ms()
    with _lock:
        for key, val in list(_store.items()):
            if val.expires_at_ms <= now:
                _store.pop(key, None)
