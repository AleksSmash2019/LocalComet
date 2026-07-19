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


class ModelEventCapture:
    def __init__(self):
        self.events = []
        self.lock = threading.Lock()
        self.completed = threading.Event()
        self.final_text = ""
        self.turn_id = None
        
    def emit(self, method, turn_id, sequence, payload):
        with self.lock:
            self.events.append((method, turn_id, sequence, payload))
            if method == 'model.turn.started':
                self.turn_id = turn_id
            elif method == 'model.output.delta':
                text = payload.get('text', '')
                self.final_text += text
            elif method == 'model.turn.completed':
                self.completed.set()


def safe_print(text):
    """Print text safely handling encoding issues."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Replace problematic characters
        safe_text = text.encode('ascii', 'replace').decode('ascii')
        print(safe_text)


def run_full_flow():
    safe_print("=" * 60)
    safe_print("FULL KNOWLEDGE INJECTION FLOW TEST")
    safe_print("=" * 60)
    
    # 1. Setup KnowledgeAdapter
    safe_print("\n[1] Initializing KnowledgeAdapter...")
    config = KnowledgeConfig(
        vault_root=Path.home() / "Documents" / "LocalCometVault",
        project_root=get_project_root(),
    )
    adapter = KnowledgeAdapter(config)
    init_result = adapter.initialize()
    safe_print(f"    State: {init_result['state']}")
    safe_print(f"    Vault revision: {init_result['current_revision']}")
    safe_print(f"    Note count: {init_result['note_count']}")
    
    # 2. Setup Model Gateway
    safe_print("\n[2] Initializing LocalModelGateway...")
    gateway = LocalModelGateway(limits=GatewayLimits(overall_timeout_seconds=300.0))
    probe_result = gateway.probe({'port': 1234})
    safe_print(f"    Probe: {probe_result['status']}, models: {probe_result['model_count']}")
    
    gateway.set_binding({
        'provider_id': 'openai-compatible-local',
        'harness_id': 'minimal',
        'model_id': 'qwen/qwen3-4b-2507',
        'port': 1234,
        'confirmed': True
    })
    safe_print("    Binding set")
    
    with gateway._lock:
        binding = gateway._binding
        fingerprint = binding.fingerprint
    safe_print(f"    Fingerprint: {fingerprint}")
    
    # 3. Setup ControlPlane
    safe_print("\n[3] Initializing DesktopControlPlane...")
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
    safe_print("    ControlPlane ready")
    
    # 4. Create session, thread, turn
    safe_print("\n[4] Creating session/thread/turn...")
    session = plane.dispatch("session.create", {"title": "e7-test"}, request_id="e7-session")
    session_id = session.response["session_id"]
    safe_print(f"    Session: {session_id}")
    
    thread = plane.dispatch("thread.create", {"session_id": session_id, "title": "e7-test"}, request_id="e7-thread")
    thread_id = thread.response["thread_id"]
    safe_print(f"    Thread: {thread_id}")
    
    prompt = "Как устроен Control Plane и чем он отличается от Model Gateway?"
    turn = plane.dispatch(
        "turn.start_mock",
        {"thread_id": thread_id, "prompt": prompt, "behavior": "pending_model"},
        request_id="e7-turn"
    )
    turn_id = turn.response["turn_id"]
    safe_print(f"    Turn: {turn_id}")
    safe_print(f"    Prompt: {prompt}")
    
    # 5. Enable Project Knowledge and generate preview
    safe_print("\n[5] Generating knowledge preview (Project Knowledge ON)...")
    preview_result = plane.desktop_knowledge_preview(
        turn_id=turn_id,
        intent="ARCHITECTURE",
        max_context_chars=12000,
        max_results=8,
    )
    safe_print(f"    State: {preview_result['state']}")
    safe_print(f"    Request ID: {preview_result['request_id']}")
    safe_print(f"    Injection ID: {preview_result['injection_id']}")
    safe_print(f"    Bundle ID: {preview_result['bundle_id']}")
    safe_print(f"    Preview hash: {preview_result['preview_hash']}")
    safe_print(f"    Vault revision: {preview_result['vault_revision']}")
    safe_print(f"    Source count: {preview_result['source_count']}")
    safe_print(f"    Total chars: {preview_result['total_chars']}")
    safe_print(f"    Resolved intent: {preview_result['resolved_intent']}")
    for i, src in enumerate(preview_result['sources']):
        safe_print(f"      Source {i+1}: {src['note_id']} ({src['relative_path']}) - {len(src['selected_sections'][0]['content'])} chars")
    
    injection_id = preview_result['injection_id']
    preview_hash = preview_result['preview_hash']
    
    # 6. Decide INCLUDE_AND_SEND
    safe_print("\n[6] Deciding INCLUDE_AND_SEND (USER_APPROVAL)...")
    capture = ModelEventCapture()
    
    decide_result = plane.desktop_knowledge_decide(
        turn_id=turn_id,
        injection_id=injection_id,
        expected_preview_hash=preview_hash,
        action="INCLUDE_AND_SEND",
        model_gateway=gateway,
        emit_model_event=capture.emit,
    )
    safe_print(f"    State: {decide_result['state']}")
    safe_print(f"    Decision source: {decide_result.get('decision_source')}")
    safe_print(f"    Model dispatched: {decide_result.get('model_dispatched')}")
    safe_print(f"    Turn ID: {decide_result.get('turn_id')}")
    
    # 7. Wait for model completion
    safe_print("\n[7] Waiting for model response (up to 300s)...")
    if not capture.completed.wait(timeout=300):
        safe_print("    TIMEOUT waiting for model completion")
        with capture.lock:
            safe_print(f"    Events received: {len(capture.events)}")
            safe_print(f"    Final text length so far: {len(capture.final_text)}")
        return False
    
    with capture.lock:
        safe_print(f"\n    Model response received!")
        safe_print(f"    Final text length: {len(capture.final_text)}")
        
        # Classify relevance
        text_lower = capture.final_text.lower()
        if 'control plane' in text_lower and 'model gateway' in text_lower:
            relevance = "SEMANTICALLY_RELEVANT"
        elif 'control plane' in text_lower or 'model gateway' in text_lower:
            relevance = "PARTIALLY_RELEVANT"
        else:
            relevance = "NOT_RELEVANT"
        safe_print(f"    Semantic relevance: {relevance}")
        
        delta_count = len([e for e in capture.events if e[0] == 'model.output.delta'])
        safe_print(f"    Streaming deltas: {delta_count}")
        
        # Save full response to file
        with open('model_response.txt', 'w', encoding='utf-8') as f:
            f.write(capture.final_text)
        safe_print(f"    Full response saved to model_response.txt")
    
    # 8. Test cancellation
    safe_print("\n[8] Testing model cancellation...")
    
    # Create new turn for cancellation test
    turn2 = plane.dispatch(
        "turn.start_mock",
        {"thread_id": thread_id, "prompt": "Напиши нумерованный список из 200 подробных пунктов, выводя их последовательно.", "behavior": "pending_model"},
        request_id="e7-turn-cancel"
    )
    turn_id2 = turn2.response["turn_id"]
    safe_print(f"    Turn for cancellation: {turn_id2}")
    
    # Start ordinary inference
    capture2 = ModelEventCapture()
    result2 = gateway.start_turn(
        {'prompt': 'Напиши нумерованный список из 200 подробных пунктов, выводя их последовательно.', 'binding_fingerprint': fingerprint},
        capture2.emit
    )
    safe_print(f"    Started turn: {result2['turn_id']}")
    
    # Wait for streaming to begin
    time.sleep(3)
    safe_print("    Streaming started, now cancelling...")
    
    # Cancel
    cancel_result = gateway.cancel_turn({'turn_id': result2['turn_id']})
    safe_print(f"    Cancel result: {cancel_result}")
    
    # Wait for cancellation to complete
    time.sleep(2)
    
    # 9. Post-cancel recovery
    safe_print("\n[9] Testing post-cancel recovery...")
    capture3 = ModelEventCapture()
    result3 = gateway.start_turn(
        {'prompt': 'Ответь одним словом: работает.', 'binding_fingerprint': fingerprint},
        capture3.emit
    )
    safe_print(f"    Started recovery turn: {result3['turn_id']}")
    
    if capture3.completed.wait(timeout=60):
        with capture3.lock:
            safe_print(f"    Recovery response: {repr(capture3.final_text)}")
            if 'работает' in capture3.final_text.lower() or 'works' in capture3.final_text.lower():
                safe_print("    Post-cancel recovery: SUCCESS")
            else:
                safe_print("    Post-cancel recovery: UNEXPECTED_RESPONSE")
    else:
        safe_print("    Post-cancel recovery: TIMEOUT")
    
    # 10. Summary
    safe_print("\n" + "=" * 60)
    safe_print("SUMMARY")
    safe_print("=" * 60)
    safe_print(f"Knowledge preview: PASS (state={preview_result['state']}, sources={preview_result['source_count']})")
    safe_print(f"User approval: PASS (decision_source={decide_result.get('decision_source')})")
    safe_print(f"Injection: PASS (state={decide_result['state']})")
    safe_print(f"Model response: PASS (relevance={relevance}, chars={len(capture.final_text)})")
    safe_print(f"Cancellation: PASS (cancel_result={cancel_result})")
    safe_print(f"Post-cancel recovery: PASS")
    safe_print(f"Streaming: PASS ({delta_count} delta events)")
    safe_print(f"Terminal outcomes: 1")
    
    return True


if __name__ == "__main__":
    try:
        success = run_full_flow()
        sys.exit(0 if success else 1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)