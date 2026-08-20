from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.local_model_gateway_ru import (
    DEFAULT_GENERATION_SEED,
    HARNESS_MINIMAL,
    GatewayLimits,
    HarnessAdapter,
    MANAGED_PROVIDER_ID,
    ProviderAdapter,
    _expected_assistant_context,
    _limits_for_provider,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", default="Reply with one short sentence: is the model running?")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--max-items", type=int, default=0)
    args = parser.parse_args()

    credential = args.key_file.read_text(encoding="utf-8").strip()
    limits = _limits_for_provider(
        GatewayLimits(
            first_token_timeout_seconds=30.0,
            inactivity_timeout_seconds=10.0,
            overall_timeout_seconds=180.0,
        ),
        MANAGED_PROVIDER_ID,
    )
    messages = HarnessAdapter(HARNESS_MINIMAL, limits).messages_for(
        args.prompt,
        _expected_assistant_context("ru"),
    )
    adapter = ProviderAdapter(args.port, limits, api_key=credential)
    items: list[dict[str, object]] = []
    try:
        for item in adapter.stream_chat(
            args.model,
            messages,
            threading.Event(),
            lambda: None,
            max_tokens=args.max_tokens,
            seed=DEFAULT_GENERATION_SEED,
            chat_template_kwargs={"enable_thinking": False},
            include_reasoning=True,
        ):
            if isinstance(item, dict):
                items.append({"kind": "tool_calls", "value": item})
            else:
                items.append(
                    {
                        "kind": "text",
                        "channel": getattr(item, "stream_channel", "content"),
                        "value": str(item),
                    }
                )
            if args.max_items > 0 and len(items) >= args.max_items:
                break
        print(json.dumps({"ok": True, "items": items}, ensure_ascii=False))
        return 0
    except Exception as exc:  # bounded diagnostic; no provider response or path is exposed
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "error_code": getattr(exc, "code", ""),
                    "error_message": getattr(exc, "message", ""),
                    "items_before_error": items,
                },
                ensure_ascii=False,
            )
        )
        return 1
    finally:
        adapter.close()


if __name__ == "__main__":
    raise SystemExit(main())
