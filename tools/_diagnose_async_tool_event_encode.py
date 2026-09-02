from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.desktop_ipc_contract_ru import IPCProtocolError, encode_frame, validate_envelope  # noqa: E402


def main() -> int:
    call = {
        "id": "call_youtube_001",
        "name": "computer_use",
        "arguments": {
            "action": "open_url",
            "target": "browser",
            "url": "https://www.youtube.com/",
        },
    }
    metadata = {
        "provider_id": "managed-llama-cpp",
        "harness_id": "minimal",
        "request_id": "0123456789abcdef01234567",
        "turn_id": "0123456789abcdef01234567",
        "chat_session_id": "chat_session_1",
        "model_id": "qwen3-1.7b-instruct-q4-k-m",
        "submitted_at_unix_ms": 1750000000000,
        "max_tokens": 128,
        "seed": 42,
        "effort": "off",
        "stream_channel": "content",
        "binding_fingerprint": "a" * 64,
        "model_called": False,
        "tools_executed": 1,
        "persistence": False,
        "generated_bytes": 0,
        "tool_calls": [call],
    }
    payload = {
        "control_plane_version": "v7.0.5",
        "model_gateway_version": "v7.0.5",
        "request_id": metadata["request_id"],
        "turn_id": metadata["turn_id"],
        "chat_session_id": metadata["chat_session_id"],
        "session_id": None,
        "thread_id": None,
        "item_id": None,
        "kind": None,
        "state": "Streaming",
        "provider_id": metadata["provider_id"],
        "harness_id": metadata["harness_id"],
        "model_id": metadata["model_id"],
        "submitted_at_unix_ms": metadata["submitted_at_unix_ms"],
        "max_tokens": metadata["max_tokens"],
        "seed": metadata["seed"],
        "effort": metadata["effort"],
        "stream_channel": metadata["stream_channel"],
        "binding_fingerprint": metadata["binding_fingerprint"],
        "text": None,
        "model_called": metadata["model_called"],
        "tools_executed": metadata["tools_executed"],
        "persistence": metadata["persistence"],
        "generated_bytes": metadata["generated_bytes"],
        "metadata": metadata,
        "tool_calls": [call],
    }
    event = {
        "protocol": "localcomet.ipc",
        "version": 3,
        "type": "event",
        "id": "py-event-000001",
        "method": "model.tool.request",
        "run_id": metadata["turn_id"],
        "sequence": 1,
        "reply_to": None,
        "payload": payload,
    }
    findings = validate_envelope(event)
    print("findings=" + json.dumps(findings, sort_keys=True))
    if findings:
        return 3
    try:
        framed = encode_frame(event)
        print(f"encoded_bytes={len(framed)}")
    except IPCProtocolError as exc:
        print(f"encode_error_type={type(exc).__name__}")
        print(f"encode_error_code={exc.code}")
        print(f"encode_error_message={exc.message}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
