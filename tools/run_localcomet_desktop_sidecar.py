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
WRITE_LOCK = threading.Lock()


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


def main() -> int:
    runtime = make_runtime()
    runtime.set_async_message_writer(lambda messages: _write_messages(runtime, messages))
    decoder = FrameDecoder()
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
            try:
                replies = runtime.handle_message(message)
            except IPCProtocolError as exc:
                replies = runtime.protocol_error_messages(exc, reply_to=str(message.get("id", "unknown")))
            if not _write_messages(runtime, replies):
                return 0

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        sys.stderr.write("localcomet sidecar fatal\n")
        raise SystemExit(1)
