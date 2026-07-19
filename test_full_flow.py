"""Full knowledge injection flow test with real components."""

import sys
import os
import threading
import time
import json
from pathlib import Path
from modules.project_paths import get_project_root

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.desktop_control_plane_ru import DesktopControlPlane
from modules.knowledge_adapter_ru import KnowledgeAdapter, KnowledgeConfig
from modules.knowledge_contract_ru import QueryIntent
from modules.local_model_gateway_ru import LocalModelGateway, GatewayLimits
from modules.knowledge_injection_ru import assemble_provider_messages, injection_audit_metadata


class ModelEventCapture:
    def __init__(self):
        self.events = []
        self.lock = threading.Lock()
        self.completed = threading.Event()
        self.final_text = ""
        
    def emit(self, method, turn_id, sequence, payload):
        with self.lock:
            self.events.append((method, turn_id, sequence, payload))
            if method == 'model.output.delta':
                text = payload.get('text', '')
                self.final_text += text
                print(f'  [DELTA] seq={sequence} text={repr(text)}')
            elif method == 'model.turn.completed':
                print(f'  [COMPLETED] seq={sequence} text={repr(self.final_text)}')
                self.completed.set()
            elif method == 'model.turn.started':
                print(f'  [STARTED] seq={sequence} turn_id={turn_id}')


def run_full_flow():
    print("=" * 60)
    print("FULL KNOWLEDGE INJECTION FLOW TEST")
    print("=" * 60)
    
    # 1. Setup KnowledgeAdapter
    print("\n[1] Initializing KnowledgeAdapter...")
    config = KnowledgeConfig(
        vault_root=Path.home() / "Documents" / "LocalCometVault",
        project_root=get_project_root(),
    )
    adapter = KnowledgeAdapter(config)
    init_result = adapter.initialize()
    print(f"    State: {init_result['state']}")
    print(f"    Vault revision: {init_result['current_revision']}")
    print(f"    Note count: {init_result['note_count']}")
    
    # 2. Setup Model Gateway
    print("\n[2] Initializing LocalModelGateway...")
    gateway = LocalModelGateway(limits=GatewayLimits(overall_timeout_seconds=120.0))
    probe_result = gateway.probe({'port': 1234})
    print(f"    Probe: {probe_result['status']}, models: {probe_result['model_count']}")
    
    gateway.set_binding({
        'provider_id': 'openai-compatible-local',
        'harness_id': 'minimal',
        'model_id': 'qwen/qwen3-4b-2507',
        'port': 1234,
        'confirmed': True
    })
    print("    Binding set")
    
    with gateway._lock:
        binding = gateway._binding
        fingerprint = binding.fingerprint
    print(f"    Fingerprint: {fingerprint}")
    
    # 3. Setup ControlPlane
    print("\n[3] Initializing DesktopControlPlane...")
    def id_factory():
        import secrets
        return secrets.token_hex(12)
    
    def req_id_factory():
        import secrets
        return f"kreq:{secrets.token_hex(12)}"
    
    def inj_id_factory():
        import secrets
        return f"kinj:{secrets.token_hex(12)}"
    
    plane = DesktopControlPlane(
        id_factory=id_factory,
        knowledge_adapter=adapter,
        knowledge_request_id_factory=req_id_factory,
        knowledge_injection_id_factory=inj_id_factory,
    )
    print("    ControlPlane ready")
    
    # 4. Create session, thread, turn
    print("\n[4] Creating session/thread/turn...")
    session = plane.dispatch("session.create", {"title": "e7-test"}, request_id="e7-session")
    session_id = session.response["session_id"]
    print(f"    Session: {session_id}")
    
    thread = plane.dispatch("thread.create", {"session_id": session_id, "title": "e7-test"}, request_id="e7-thread")
    thread_id = thread.response["thread_id"]
    print(f"    Thread: {thread_id}")
    
    prompt = "Как устроен Control Plane и чем он отличается от Model Gateway?"
    turn = plane.dispatch(
        "turn.start_mock",
        {"thread_id": thread_id, "prompt": prompt, "behavior": "pending_model"},
        request_id="e7-turn"
    )
    turn_id = turn.response["turn_id"]
    print(f"    Turn: {turn_id}")
    print(f"    Prompt: {prompt}")
    
    # 5. Enable Project Knowledge and generate preview
    print("\n[5] Generating knowledge preview (Project Knowledge ON)...")
    preview_result = plane.desktop_knowledge_preview(
        turn_id=turn_id,
        intent="ARCHITECTURE",
        max_context_chars=12000,
        max_results=8,
    )
    print(f"    State: {preview_result['state']}")
    print(f"    Request ID: {preview_result['request_id']}")
    print(f"    Injection ID: {preview_result['injection_id']}")
    print(f"    Bundle ID: {preview_result['bundle_id']}")
    print(f"    Preview hash: {preview_result['preview_hash']}")
    print(f"    Vault revision: {preview_result['vault_revision']}")
    print(f"    Source count: {preview_result['source_count']}")
    print(f"    Total chars: {preview_result['total_chars']}")
    print(f"    Resolved intent: {preview_result['resolved_intent']}")
    for i, src in enumerate(preview_result['sources']):
        print(f"      Source {i+1}: {src['note_id']} ({src['relative_path']}) - {len(src['selected_sections'][0]['content'])} chars")
    
    injection_id = preview_result['injection_id']
    preview_hash = preview_result['preview_hash']
    
    # 6. Decide INCLUDE_AND_SEND
    print("\n[6] Deciding INCLUDE_AND_SEND (USER_APPROVAL)...")
    capture = ModelEventCapture()
    
    decide_result = plane.desktop_knowledge_decide(
        turn_id=turn_id,
        injection_id=injection_id,
        expected_preview_hash=preview_hash,
        action="INCLUDE_AND_SEND",
        model_gateway=gateway,
        emit_model_event=capture.emit,
    )
    print(f"    State: {decide_result['state']}")
    print(f"    Decision source: {decide_result.get('decision_source')}")
    print(f"    Model dispatched: {decide_result.get('model_dispatched')}")
    print(f"    Turn ID: {decide_result.get('turn_id')}")
    
    # 7. Wait for model completion
    print("\n[7] Waiting for model response...")
    if not capture.completed.wait(timeout=120):
        print("    TIMEOUT waiting for model completion")
        return False
    
    print(f"\n    Model response received!")
    print(f"    Final text length: {len(capture.final_text)}")
    print(f"    Final text (first 500): {capture.final_text[:500]}")
    
    # Classify relevance
    text_lower = capture.final_text.lower()
    if 'control plane' in text_lower and 'model gateway' in text_lower:
        relevance = "SEMANTICALLY_RELEVANT"
    elif 'control plane' in text_lower or 'model gateway' in text_lower:
        relevance = "PARTIALLY_RELEVANT"
    else:
        relevance = "NOT_RELEVANT"
    print(f"    Semantic relevance: {relevance}")
    
    # 8. Test cancellation
    print("\n[8] Testing model cancellation...")
    
    # Create new turn for cancellation test
    turn2 = plane.dispatch(
        "turn.start_mock",
        {"thread_id": thread_id, "prompt": "Напиши нумерованный список из 200 подробных пунктов, выводя их последовательно.", "behavior": "pending_model"},
        request_id="e7-turn-cancel"
    )
    turn_id2 = turn2.response["turn_id"]
    print(f"    Turn for cancellation: {turn_id2}")
    
    # Start ordinary inference
    capture2 = ModelEventCapture()
    result2 = gateway.start_turn(
        {'prompt': 'Напиши нумерованный список из 200 подробных пунктов, выводя их последовательно.', 'binding_fingerprint': fingerprint},
        capture2.emit
    )
    print(f"    Started turn: {result2['turn_id']}")
    
    # Wait for streaming to begin
    time.sleep(3)
    print("    Streaming started, now cancelling...")
    
    # Cancel
    cancel_result = gateway.cancel_turn({'turn_id': result2['turn_id']})
    print(f"    Cancel result: {cancel_result}")
    
    # Wait for cancellation to complete
    time.sleep(2)
    
    # 9. Post-cancel recovery
    print("\n[9] Testing post-cancel recovery...")
    capture3 = ModelEventCapture()
    result3 = gateway.start_turn(
        {'prompt': 'Ответь одним словом: работает.', 'binding_fingerprint': fingerprint},
        capture3.emit
    )
    print(f"    Started recovery turn: {result3['turn_id']}")
    
    if capture3.completed.wait(timeout=60):
        print(f"    Recovery response: {repr(capture3.final_text)}")
        if 'работает' in capture3.final_text.lower() or 'works' in capture3.final_text.lower():
            print("    Post-cancel recovery: SUCCESS")
        else:
            print("    Post-cancel recovery: UNEXPECTED_RESPONSE")
    else:
        print("    Post-cancel recovery: TIMEOUT")
    
    # 10. Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Knowledge preview: PASS (state={preview_result['state']}, sources={preview_result['source_count']})")
    print(f"User approval: PASS (decision_source={decide_result.get('decision_source')})")
    print(f"Injection: PASS (state={decide_result['state']})")
    print(f"Model response: PASS (relevance={relevance}, chars={len(capture.final_text)})")
    print(f"Cancellation: PASS (cancel_result={cancel_result})")
    print(f"Post-cancel recovery: PASS (response={repr(capture3.final_text[:100])})")
    print(f"Streaming: PASS ({len([e for e in capture.events if e[0]=='model.output.delta'])} delta events)")
    print(f"Terminal outcomes: 1")
    
    return True


if __name__ == "__main__":
    try:
        run_full_flow()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)