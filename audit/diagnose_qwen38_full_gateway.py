from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.local_model_gateway_ru import (  # noqa: E402
    DEFAULT_GENERATION_SEED,
    HARNESS_MINIMAL,
    MANAGED_PROVIDER_ID,
    GatewayLimits,
    LocalModelGateway,
    trusted_assistant_context_payload,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--alias", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--runtime-instance-id", default="3" * 32)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--tools", action="store_true")
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()

    credential = args.key_file.read_text(encoding="utf-8").strip()
    gateway = LocalModelGateway(limits=GatewayLimits())
    gateway.managed_attach(
        {
            "port": args.port,
            "credential": credential,
            "runtime_instance_id": args.runtime_instance_id,
            "model_id": args.model,
            "expected_model_alias": args.alias,
            "binding_fingerprint": "b" * 64,
        }
    )
    binding = gateway.set_binding(
        {
            "provider_id": MANAGED_PROVIDER_ID,
            "harness_id": HARNESS_MINIMAL,
            "model_id": args.model,
            "runtime_instance_id": args.runtime_instance_id,
            "confirmed": True,
        }
    )
    request_id = "a" * 24
    events: list[dict[str, object]] = []
    terminal = threading.Event()

    def emit_event(method: str, event_request_id: str, sequence: int, payload: dict[str, object]) -> None:
        event = {"method": method, "request_id": event_request_id, "sequence": sequence, **payload}
        events.append(event)
        if method in {"model.turn.completed", "model.turn.failed", "model.turn.timed_out", "model.turn.cancelled"}:
            terminal.set()

    payload = {
        "request_id": request_id,
        "chat_session_id": "local-chat",
        "model_id": args.model,
        "submitted_at_unix_ms": int(time.time() * 1000),
        "max_tokens": args.max_tokens,
        "seed": DEFAULT_GENERATION_SEED,
        "effort": "off",
        "prompt": args.prompt,
        "assistant_context": trusted_assistant_context_payload(
            "ru",
            tools=("files.read",) if args.tools else (),
        ),
        "binding_fingerprint": binding["binding_fingerprint"],
        "messages": (
            [
                {"role": "user", "content": "Предыдущий вопрос"},
                {"role": "assistant", "content": "Предыдущий ответ"},
            ]
            if args.history
            else []
        ),
    }
    try:
        acceptance = gateway.start_turn(payload, emit_event)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "error_code": getattr(exc, "code", ""),
                    "error_message": getattr(exc, "message", str(exc)),
                    "payload_keys": sorted(payload),
                },
                ensure_ascii=False,
            )
        )
        gateway.shutdown()
        return 1
    terminal.wait(240)
    gateway.shutdown()
    summary = []
    for event in events:
        summary.append(
            {
                "method": event["method"],
                "sequence": event["sequence"],
                "text": event.get("text"),
                "stream_channel": event.get("stream_channel"),
                "metadata_keys": sorted((event.get("metadata") or {}).keys()),
                "error": (event.get("metadata") or {}).get("error"),
            }
        )
    print(json.dumps({"binding": binding, "acceptance": acceptance, "terminal": terminal.is_set(), "events": summary}, ensure_ascii=False))
    return 0 if terminal.is_set() else 1


if __name__ == "__main__":
    raise SystemExit(main())
