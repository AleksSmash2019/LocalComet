"""Long-conversation memory regression tests (audit P0: 2-message history).

The harness used to slice chat history to the last 2 messages and the gateway
capped payload at 4 messages, so anything said earlier than one turn ago was
invisible to the model (S2 «длинный разговор» failed by construction).
These tests pin the new contract:
  - GatewayLimits.maximum_messages == 32;
  - 32 messages validate, 33 are rejected fail-closed;
  - the frontend history window constants (30 messages, 8 KiB per message)
    stay inside the gateway budget — mirrored here from modelGateway.ts so
    the two sides cannot drift apart.
"""
from __future__ import annotations

import pathlib
import re
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from modules.local_model_gateway_ru import GatewayLimits, _validate_messages

FRONTEND_STORE = REPO_ROOT / "desktop/localcomet-desktop/src/lib/stores/modelGateway.ts"


class LongConversationLimitsTests(unittest.TestCase):
    def test_gateway_accepts_32_messages_and_rejects_33(self) -> None:
        limits = GatewayLimits()
        self.assertEqual(limits.maximum_messages, 32)
        base = [{"role": "system", "content": "system prompt"}]
        history = [{"role": "user", "content": f"turn {i}"} for i in range(31)]
        _validate_messages(tuple(base + history), limits)  # must not raise

        overflow = base + history + [{"role": "user", "content": "one too many"}]
        with self.assertRaises(Exception) as ctx:
            _validate_messages(tuple(overflow), limits)
        self.assertEqual(getattr(ctx.exception, "code", ""), "invalid_payload")

    def test_frontend_history_window_stays_inside_gateway_budget(self) -> None:
        source = FRONTEND_STORE.read_text(encoding="utf-8")
        window = re.search(r"MAX_HISTORY_MESSAGES\s*=\s*(\d+)", source)
        per_message = re.search(r"MAX_HISTORY_MESSAGE_BYTES\s*=\s*([\d_]+)", source)
        self.assertIsNotNone(window, "frontend history window constant missing")
        self.assertIsNotNone(per_message, "frontend per-message byte bound missing")
        window_n = int(window.group(1))
        per_message_n = int(per_message.group(1).replace("_", ""))
        # gateway counts system + new prompt on top of the history window
        self.assertLessEqual(window_n + 2, GatewayLimits().maximum_messages)
        # the whole window must fit the harness byte cap (2x prompt budget)
        self.assertLessEqual(window_n * per_message_n, GatewayLimits().maximum_prompt_bytes * 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
