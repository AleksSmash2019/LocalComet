import threading
import time
from modules.local_model_gateway_ru import LocalModelGateway, GatewayLimits

gateway = LocalModelGateway(limits=GatewayLimits(overall_timeout_seconds=120.0))
gateway.probe({'port': 1234})
gateway.set_binding({
    'provider_id': 'openai-compatible-local',
    'harness_id': 'minimal',
    'model_id': 'qwen/qwen3-4b-2507',
    'port': 1234,
    'confirmed': True
})

with gateway._lock:
    binding = gateway._binding
    fingerprint = binding.fingerprint

events = []
def emit(method, turn_id, sequence, payload):
    events.append((method, turn_id, sequence, payload))
    if method == 'model.output.delta':
        text = payload.get('text', '')
        print('Delta:', repr(text))
    elif method == 'model.turn.completed':
        text = payload.get('text', '')
        print('Completed:', repr(text))

result = gateway.start_turn(
    {'prompt': 'Say hello in Russian', 'binding_fingerprint': fingerprint},
    emit
)
print('Result:', result)

for _ in range(60):
    time.sleep(1)
    with gateway._lock:
        active = gateway._active
    if active and active.terminal:
        print('Turn completed')
        break
else:
    print('Timeout')

print('Total events:', len(events))
for m, t, s, p in events:
    text = p.get('text', '')
    print(f'  {m} seq={s} text={repr(text)}')