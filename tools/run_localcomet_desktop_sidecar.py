from __future__ import annotations

import sys
import threading
from pathlib import Path


def _prepare_import_path() -> None:
    runner = Path(__file__)
    if runner.is_symlink():
        raise RuntimeError("sidecar runner symlink is not allowed")
    root = runner.resolve(strict=True).parents[1]
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


_prepare_import_path()

from modules.desktop_ipc_contract_ru import FrameDecoder, IPCProtocolError  # noqa: E402
from modules.desktop_sidecar_runtime_ru import make_runtime  # noqa: E402


READ_CHUNK_BYTES = 8192
WRITE_LOCK = threading.RLock()
SERIALIZED_ACCEPTANCE_METHODS = frozenset(
    ("model.turn.start", "knowledge.turn.decide")
)


def _write_messages(runtime, messages) -> bool:
    try:
        payload = runtime.encode_messages(messages)
        if payload:
            with WRITE_LOCK:
                sys.stdout.buffer.write(payload)
                sys.stdout.buffer.flush()
        return True
    except BrokenPipeError:
        return False


class _AcceptanceWriteGate:
    """Keep acceptance ahead of async events without holding WRITE_LOCK in handlers."""

    def __init__(self, runtime) -> None:
        self._runtime = runtime
        self._lock = threading.Lock()
        self._active_token: object | None = None
        self._buffered: list[tuple[dict, ...]] = []

    def begin(self) -> object:
        token = object()
        with self._lock:
            if self._active_token is not None:
                raise RuntimeError("nested sidecar acceptance gate")
            self._active_token = token
            self._buffered.clear()
        return token

    def write_async(self, messages) -> bool:
        batch = tuple(messages)
        with self._lock:
            if self._active_token is not None:
                self._buffered.append(batch)
                return True
        return _write_messages(self._runtime, batch)

    def finish(self, token: object, response_messages=(), *, flush: bool) -> bool:
        # WRITE_LOCK is acquired only after the handler has released gateway
        # locks. It stays held while the gate opens and the acceptance response
        # plus buffered events are drained in that order.
        with WRITE_LOCK:
            with self._lock:
                if self._active_token is not token:
                    raise RuntimeError("sidecar acceptance gate token mismatch")
                buffered = tuple(self._buffered)
                self._buffered.clear()
                self._active_token = None
            if not flush:
                return False
            if not _write_messages(self._runtime, response_messages):
                return False
            for batch in buffered:
                if not _write_messages(self._runtime, batch):
                    return False
        return True


def _handle_and_write(runtime, message, acceptance_gate: _AcceptanceWriteGate) -> bool:
    def handle():
        try:
            return runtime.handle_message(message)
        except IPCProtocolError as exc:
            return runtime.protocol_error_messages(
                exc,
                reply_to=str(message.get("id", "unknown")),
            )

    if message.get("method") not in SERIALIZED_ACCEPTANCE_METHODS:
        return _write_messages(runtime, handle())

    token = acceptance_gate.begin()
    try:
        response_messages = handle()
    except BaseException:
        acceptance_gate.finish(token, flush=False)
        raise
    return acceptance_gate.finish(token, response_messages, flush=True)


def main() -> int:
    runtime = make_runtime()
    acceptance_gate = _AcceptanceWriteGate(runtime)
    runtime.set_async_message_writer(acceptance_gate.write_async)
    decoder = FrameDecoder()
    try:
        if not _write_messages(runtime, runtime.startup_messages()):
            return 0

        while not runtime.shutdown_requested:
            chunk = sys.stdin.buffer.read1(READ_CHUNK_BYTES)
            if not chunk:
                break
            try:
                messages = decoder.feed(chunk)
            except IPCProtocolError as exc:
                if not _write_messages(runtime, runtime.protocol_error_messages(exc)):
                    return 0
                continue
            for message in messages:
                if not _handle_and_write(runtime, message, acceptance_gate):
                    return 0

        return 0
    finally:
        runtime.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        sys.stderr.write("localcomet sidecar fatal\n")
        raise SystemExit(1)
