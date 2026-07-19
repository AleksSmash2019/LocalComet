"""Quick real-model smoke test for SSE UTF-8 fix."""
from __future__ import annotations
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.local_model_gateway_ru import (
    LocalModelGateway, GatewayLimits,
)

limits = GatewayLimits(
    read_chunk_bytes=512,
    overall_timeout_seconds=60,
    idle_timeout_seconds=15,
)

gateway = LocalModelGateway(limits=limits)
probe = gateway.probe({"port": 1234})
print(f"Probe: {probe['status']}, models: {probe['model_count']}")

listed = gateway.list_models({"port": 1234})
model_ids = [m["model_id"] for m in listed["models"]]

binding = gateway.set_binding({
    "provider_id": "openai-compatible-local",
    "harness_id": "minimal",
    "port": 1234,
    "model_id": "qwen/qwen3-4b-2507",
    "confirmed": True,
})
print(f"Binding: {binding['binding_fingerprint'][:16]}...")

prompt = "Расскажи кратко что такое Control Plane?"
events = []

def emit(method, turn_id, seq, payload):
    events.append((method, payload))

result = gateway.start_turn(
    {"prompt": prompt, "binding_fingerprint": binding["binding_fingerprint"]},
    emit,
)
print(f"Turn: {result['turn_id'][:16]}..., state={result['state']}")

time.sleep(15)

deltas = [p.get("text", "") for m, p in events if m == "model.output.delta"]
full_text = "".join(deltas)
dc = len(deltas)
garbled = full_text.count("\ufffd")

print(f"\nDeltas: {dc}")
print(f"Full text length: {len(full_text)}")
print(f"Garbled chars: {garbled}")

print(f"\nFirst 300 chars: {full_text[:300]}")

terminal = [m for m, p in events if "completed" in m or "failed" in m or "cancelled" in m]
print(f"Terminal events: {terminal}")

if dc > 0 and garbled == 0:
    print("\n*** SMOKE PASS: No garbled UTF-8 characters ***")
elif dc > 0:
    print(f"\n*** SMOKE WARNING: {garbled} garbled characters ***")
else:
    print("\n*** SMOKE INFO: No deltas received ***")
