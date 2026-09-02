//! Test module extracted from `control_plane.rs` during the 2026-09-02 refactor.
//! Content is verbatim; paths inside (`super::`, `crate::`) are unchanged.

use super::*;
// COPIED-IMPORTS: parent use-bindings (private imports are not glob-visible)
use crate::ipc;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

#[test]
fn sanitize_text_masks_real_sk_secret_token() {
    assert_eq!(
        sanitize_text("token: sk-AbCd1234567890 done", 1024),
        "token: <REDACTED_TEXT> done"
    );
}

#[test]
fn sanitize_text_keeps_legit_sk_substrings() {
    assert_eq!(
        sanitize_text("task-1, disk-usage, flask-app", 1024),
        "task-1, disk-usage, flask-app"
    );
}

#[test]
fn sanitize_text_keeps_sk_prefix_without_long_tail() {
    assert_eq!(sanitize_text("sk-short stays", 1024), "sk-short stays");
    assert_eq!(
        sanitize_text("edge sk-1234567 stays", 1024),
        "edge sk-1234567 stays"
    );
}

#[test]
fn method_enum_maps_to_exact_wire_vocabulary() {
    let wires: Vec<&str> = CONTROL_PLANE_METHOD_VOCABULARY
        .iter()
        .map(|(wire, method)| {
            assert_eq!(*wire, method.as_wire());
            *wire
        })
        .collect();
    assert_eq!(
        wires.len(),
        CONTROL_PLANE_METHOD_COUNT,
        "control-plane method vocabulary count mismatch"
    );
    assert!(wires.contains(&"turn.start_mock"));
    assert!(wires.contains(&"model.turn.start"));
    assert!(wires.contains(&"model.managed.attach"));
    assert!(wires.contains(&"model.managed.detach"));
    assert!(wires.contains(&"knowledge.turn.preview"));
    assert!(wires.contains(&"knowledge.turn.decide"));
    let review_wires: Vec<&str> = wires
        .iter()
        .copied()
        .filter(|wire| wire.starts_with("knowledge.review."))
        .collect();
    assert_eq!(
        review_wires,
        vec![
            "knowledge.review.list",
            "knowledge.review.get",
            "knowledge.review.snapshot",
            "knowledge.review.refresh",
            "knowledge.review.decision.create",
        ]
    );
    assert_eq!(
        ControlPlaneMethod::KnowledgeReviewList.timeout(),
        REQUEST_TIMEOUT
    );
    assert_eq!(
        ControlPlaneMethod::KnowledgeReviewGet.timeout(),
        REQUEST_TIMEOUT
    );
    assert_eq!(
        ControlPlaneMethod::KnowledgeReviewDecisionCreate.timeout(),
        Duration::from_secs(5)
    );
    assert_eq!(
        ControlPlaneMethod::ModelManagedAttach.timeout(),
        Duration::from_secs(300)
    );
    assert_eq!(
        ControlPlaneMethod::ModelManagedDetach.timeout(),
        Duration::from_secs(2)
    );
    assert!(!wires.contains(&"turn.start"));
    assert!(!wires.iter().any(|wire| wire.contains("register")));
    assert!(!wires.iter().any(|wire| wire.contains("publish")));
    assert!(!wires.iter().any(|wire| wire.contains("write")));
}

#[test]
#[should_panic(expected = "control-plane method vocabulary count mismatch")]
fn method_vocabulary_count_mismatch_fails_clearly() {
    validate_control_plane_method_count(CONTROL_PLANE_METHOD_COUNT - 1);
}

#[test]
fn tool_call_method_maps_wire_and_timeout() {
    assert_eq!(ControlPlaneMethod::ToolCall.as_wire(), "tool.call");
    assert_eq!(
        ControlPlaneMethod::ToolCall.timeout(),
        Duration::from_secs(30)
    );
    assert!(CONTROL_PLANE_METHOD_VOCABULARY
        .iter()
        .any(|(wire, method)| *wire == "tool.call" && *method == ControlPlaneMethod::ToolCall));
}

#[test]
fn build_tool_call_request_with_correlation_keeps_raw_input_unchanged() {
    let input = json!({"action": "type", "text": "LocalComet hidden marker"});
    let request_id = "0123456789abcdef01234567";
    let action_id = "call_0123456789abcdef0123456789abcdef";
    let (method, payload) = build_tool_call_request_with_correlation(
        "computer_use",
        &input,
        "/workspace",
        "digest",
        "session-1",
        None,
        Some(request_id),
        Some(action_id),
    )
    .unwrap();

    assert_eq!(method, ControlPlaneMethod::ToolCall);
    assert_eq!(payload["input"], input);
    assert_eq!(payload["request_id"], request_id);
    assert_eq!(payload["action_id"], action_id);
    assert!(validate_payload_for_method(method, &payload).is_ok());
    assert!(!payload["input"]
        .as_object()
        .unwrap()
        .contains_key("request_id"));
    assert!(!payload["input"]
        .as_object()
        .unwrap()
        .contains_key("action_id"));
}

#[test]
fn build_tool_call_request_builds_exact_payloads() {
    let input = json!({"path": "notes.txt"});
    let (method, payload) = build_tool_call_request(
        "files.read",
        &input,
        "/workspace",
        "digest",
        "session-1",
        None,
    )
    .unwrap();
    assert_eq!(method, ControlPlaneMethod::ToolCall);
    assert_eq!(
        payload,
        json!({
            "tool": "files.read",
            "input": {"path": "notes.txt"},
            "workspace": "/workspace",
            "workspace_digest": "digest",
            "session": "session-1",
        })
    );
    assert!(validate_payload_for_method(method, &payload).is_ok());

    let (grant_method, grant_payload) = build_tool_call_request(
        "files.write",
        &input,
        "/workspace",
        "digest",
        "session-1",
        Some(&crate::approval::ExecutionGrant {
            grant_id: "grant-abc".to_string(),
            tool: "files.write".to_string(),
            input_digest: [0u8; 32],
            workspace: "/workspace".to_string(),
            session: "session-1".to_string(),
            nonce: [0u8; 16],
            valid_until: std::time::Instant::now() + std::time::Duration::from_secs(30),
            approval_id: String::new(),
            call_id: String::new(),
        }),
    )
    .unwrap();
    assert_eq!(grant_method, ControlPlaneMethod::ToolCall);
    assert_eq!(grant_payload["tool"], "files.write");
    assert_eq!(grant_payload["grant_id"], "grant-abc");
    let grant_object = grant_payload
        .get("grant")
        .and_then(Value::as_object)
        .expect("grant object present");
    assert_eq!(
        grant_object.get("grant_id").and_then(Value::as_str),
        Some("grant-abc")
    );
    assert_eq!(
        grant_object.get("tool").and_then(Value::as_str),
        Some("files.write")
    );
    assert_eq!(
        grant_object.get("input_digest").and_then(Value::as_str),
        Some("0".repeat(64).as_str())
    );
    assert_eq!(
        grant_object.get("workspace").and_then(Value::as_str),
        Some("/workspace")
    );
    assert_eq!(
        grant_object.get("session").and_then(Value::as_str),
        Some("session-1")
    );
    let expires = grant_object
        .get("expires_at_unix_ms")
        .and_then(Value::as_u64)
        .expect("expiry present");
    assert!(
        expires > 0
            && expires
                <= std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis() as u64
                    + 31_000
    );
    assert!(validate_payload_for_method(grant_method, &grant_payload).is_ok());
}

/// Canonical bounded wait: `seconds` (0.1..=30.0) is the single wait format
/// accepted end-to-end (intent parser -> this schema -> executor).
#[test]
fn computer_use_wait_seconds_schema_canonical() {
    let valid = json!({"action": "wait", "seconds": 2.5});
    assert!(validate_model_tool_arguments("computer_use", &valid).is_ok());
    let integer_form = json!({"action": "wait", "seconds": 3});
    assert!(validate_model_tool_arguments("computer_use", &integer_form).is_ok());
    for invalid in [
        json!({"action": "wait", "seconds": 0.01}),
        json!({"action": "wait", "seconds": 31.0}),
        json!({"action": "wait", "seconds": "2"}),
        json!({"action": "wait", "seconds": null}),
        json!({"action": "wait", "duration_ms": 500}),
    ] {
        assert!(
            validate_model_tool_arguments("computer_use", &invalid).is_err(),
            "must reject {invalid}"
        );
    }
}

#[test]
fn computer_use_task_schema_is_bounded() {
    let valid = json!({
        "action": "task",
        "goal": "Нажми Ctrl+F и прокрути вниз.",
        "max_steps": 2
    });
    assert!(validate_model_tool_arguments("computer_use", &valid).is_ok());
    let default_steps = json!({"action": "task", "goal": "safe interaction"});
    assert!(validate_model_tool_arguments("computer_use", &default_steps).is_ok());
    for invalid in [
        json!({"action": "task", "goal": ""}),
        json!({"action": "task", "goal": "x".repeat(1201)}),
        json!({"action": "task", "goal": "safe", "max_steps": 0}),
        json!({"action": "task", "goal": "safe", "max_steps": 9}),
        json!({"action": "task", "goal": "safe", "max_steps": 2.5}),
        json!({"action": "task", "goal": "safe", "unexpected": true}),
    ] {
        assert!(
            validate_model_tool_arguments("computer_use", &invalid).is_err(),
            "must reject {invalid}"
        );
    }
}

#[test]
fn tool_call_payload_validation_rejects_extras_missing_and_blank() {
    let valid = json!({
        "tool": "files.read",
        "input": {},
        "workspace": "/w",
        "workspace_digest": "d",
        "session": "s",
    });
    assert!(validate_payload_for_method(ControlPlaneMethod::ToolCall, &valid).is_ok());

    let mut extra = valid.as_object().unwrap().clone();
    extra.insert("surprise".to_owned(), json!(true));
    assert!(
        validate_payload_for_method(ControlPlaneMethod::ToolCall, &Value::Object(extra)).is_err()
    );

    let mut missing = valid.as_object().unwrap().clone();
    missing.remove("workspace_digest");
    assert!(
        validate_payload_for_method(ControlPlaneMethod::ToolCall, &Value::Object(missing)).is_err()
    );

    let mut blank_tool = valid.as_object().unwrap().clone();
    blank_tool.insert("tool".to_owned(), json!(""));
    assert!(
        validate_payload_for_method(ControlPlaneMethod::ToolCall, &Value::Object(blank_tool))
            .is_err()
    );

    let mut blank_grant = valid.as_object().unwrap().clone();
    blank_grant.insert("grant_id".to_owned(), json!(""));
    assert!(
        validate_payload_for_method(ControlPlaneMethod::ToolCall, &Value::Object(blank_grant))
            .is_err()
    );

    assert!(validate_payload_for_method(ControlPlaneMethod::ToolCall, &json!([])).is_err());
}

#[test]
fn knowledge_review_request_helpers_build_exact_forwarding_payloads() {
    let identity = format!("kreview:{}", "a".repeat(64));
    let proposal_id = format!("kprop:{}", "b".repeat(64));
    let change_identity = format!("kchange:{}", "c".repeat(64));
    let revision = format!("sha256:{}", "d".repeat(64));
    let (list_method, list_payload) = build_knowledge_review_list_request(7, 25).unwrap();
    assert_eq!(list_method, ControlPlaneMethod::KnowledgeReviewList);
    assert_eq!(list_payload, json!({"offset":7,"limit":25}));
    assert!(validate_payload_for_method(list_method, &list_payload).is_ok());

    let (get_method, get_payload) = build_knowledge_review_get_request(&identity).unwrap();
    assert_eq!(get_method, ControlPlaneMethod::KnowledgeReviewGet);
    assert_eq!(get_payload, json!({"review_artifact_identity":identity}));
    assert!(validate_payload_for_method(get_method, &get_payload).is_ok());

    for method in [
        ControlPlaneMethod::KnowledgeReviewSnapshot,
        ControlPlaneMethod::KnowledgeReviewRefresh,
    ] {
        assert!(validate_payload_for_method(method, &json!({})).is_ok());
        assert!(validate_payload_for_method(method, &json!({"extra": true})).is_err());
    }

    let (decision_method, decision_payload) = build_knowledge_review_decision_create_request(
        KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
        &proposal_id,
        &identity,
        Some(&change_identity),
        &revision,
        "REQUEST_CHANGES",
        "Please provide stronger evidence.",
        "local-user",
        "Local user",
        KNOWLEDGE_REVIEW_ACTOR_SOURCE,
    )
    .unwrap();
    assert_eq!(
        decision_method,
        ControlPlaneMethod::KnowledgeReviewDecisionCreate
    );
    assert_eq!(
        decision_payload,
        json!({
            "review_contract_version": KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
            "proposal_id": proposal_id,
            "review_artifact_identity": identity,
            "change_identity": change_identity,
            "observed_vault_revision": revision,
            "decision": "REQUEST_CHANGES",
            "comment": "Please provide stronger evidence.",
            "actor_identifier": "local-user",
            "actor_display_name": "Local user",
            "actor_source": KNOWLEDGE_REVIEW_ACTOR_SOURCE,
        })
    );
    assert!(validate_payload_for_method(decision_method, &decision_payload).is_ok());
}

#[test]
fn knowledge_review_payload_validation_rejects_extras_limits_and_bad_identity() {
    assert!(build_knowledge_review_list_request(0, 1).is_ok());
    assert!(build_knowledge_review_list_request(MAX_KNOWLEDGE_REVIEW_OFFSET, 50).is_ok());
    assert!(build_knowledge_review_list_request(MAX_KNOWLEDGE_REVIEW_OFFSET + 1, 1).is_err());
    assert!(build_knowledge_review_list_request(0, 0).is_err());
    assert!(build_knowledge_review_list_request(0, MAX_KNOWLEDGE_REVIEW_LIMIT + 1).is_err());
    assert!(validate_payload_for_method(
        ControlPlaneMethod::KnowledgeReviewList,
        &json!({"offset":0,"limit":10,"extra":true})
    )
    .is_err());
    assert!(validate_payload_for_method(
        ControlPlaneMethod::KnowledgeReviewList,
        &json!({"offset":0,"limit":"10"})
    )
    .is_err());
    assert!(validate_payload_for_method(
        ControlPlaneMethod::KnowledgeReviewList,
        &json!({"offset":0})
    )
    .is_err());

    let valid = format!("kreview:{}", "0123456789abcdef".repeat(4));
    assert!(ensure_review_artifact_identity(&valid).is_ok());
    assert!(ensure_review_artifact_identity(&valid.to_ascii_uppercase()).is_err());
    assert!(ensure_review_artifact_identity("kreview:abc").is_err());
    assert!(ensure_review_artifact_identity("../kreview:bad").is_err());
    assert!(validate_payload_for_method(
        ControlPlaneMethod::KnowledgeReviewGet,
        &json!({"review_artifact_identity":valid,"extra":true})
    )
    .is_err());
}

#[test]
fn knowledge_review_decision_payload_is_exact_bounded_and_deny_by_default() {
    let review_id = format!("kreview:{}", "a".repeat(64));
    let proposal_id = format!("kprop:{}", "b".repeat(64));
    let change_identity = format!("kchange:{}", "c".repeat(64));
    let revision = format!("sha256:{}", "d".repeat(64));

    let build = |decision: &str, change: Option<&str>, comment: &str| {
        build_knowledge_review_decision_create_request(
            KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
            &proposal_id,
            &review_id,
            change,
            &revision,
            decision,
            comment,
            "local-user",
            "Local user",
            KNOWLEDGE_REVIEW_ACTOR_SOURCE,
        )
    };
    assert!(build("APPROVE", Some(&change_identity), "").is_ok());
    assert!(build("APPROVE", None, "").is_ok());
    assert!(build("REQUEST_CHANGES", Some(&change_identity), "   ").is_err());
    assert!(build("REJECT", None, "").is_ok());
    assert!(build("AUTO_APPROVE", Some(&change_identity), "").is_err());
    assert!(build("REJECT", None, &"x".repeat(MAX_REVIEW_COMMENT_CHARS + 1)).is_err());
    assert!(build("REJECT", None, &"😀".repeat(1_025)).is_err());

    let (_, valid_payload) = build("REJECT", None, "").unwrap();
    let mut with_extra = valid_payload.clone();
    with_extra
        .as_object_mut()
        .unwrap()
        .insert("write_vault".into(), Value::Bool(true));
    assert!(validate_payload_for_method(
        ControlPlaneMethod::KnowledgeReviewDecisionCreate,
        &with_extra
    )
    .is_err());
}

#[test]
fn knowledge_review_response_guard_enforces_one_megabyte_limit() {
    assert!(ensure_knowledge_review_response_bound(&json!({"items":[]})).is_ok());
    let empty_envelope_bytes = serde_json::to_vec(&json!({"payload":""})).unwrap().len();
    let at_limit = json!({
        "payload": "x".repeat(MAX_KNOWLEDGE_REVIEW_RESPONSE_JSON_BYTES - empty_envelope_bytes)
    });
    assert_eq!(
        serde_json::to_vec(&at_limit).unwrap().len(),
        MAX_KNOWLEDGE_REVIEW_RESPONSE_JSON_BYTES
    );
    assert!(ensure_knowledge_review_response_bound(&at_limit).is_ok());

    let over_limit = json!({
        "payload": "x".repeat(
            MAX_KNOWLEDGE_REVIEW_RESPONSE_JSON_BYTES - empty_envelope_bytes + 1
        )
    });
    assert!(ensure_knowledge_review_response_bound(&over_limit).is_err());
}

#[test]
fn knowledge_review_commands_permissions_and_capability_are_static_and_narrow() {
    let lib_source = include_str!("lib.rs");
    let permissions = include_str!("../permissions/knowledge-review-command-center.toml");
    let capability = include_str!("../capabilities/main.json");

    for command in [
        "knowledge_review_list",
        "knowledge_review_get",
        "knowledge_review_snapshot",
        "knowledge_review_refresh",
        "knowledge_review_decision_create",
    ] {
        assert_eq!(lib_source.matches(command).count(), 2);
    }
    for permission in [
        "allow-knowledge-review-list",
        "allow-knowledge-review-get",
        "allow-knowledge-review-snapshot",
        "allow-knowledge-review-refresh",
        "allow-knowledge-review-decision-create",
    ] {
        assert_eq!(capability.matches(permission).count(), 1);
    }
    for command in [
        "knowledge_review_snapshot",
        "knowledge_review_refresh",
        "knowledge_review_decision_create",
    ] {
        assert_eq!(permissions.matches(&format!("\"{command}\"")).count(), 1);
    }
    assert!(permissions.contains("bounded in-memory human review decision artifact"));
    assert!(!permissions.contains('*'));
    assert!(!capability.contains('*'));
    for source in [lib_source, permissions, capability] {
        assert!(!source.contains("knowledge_review_register"));
        assert!(!source.contains("knowledge_review_raw"));
        assert!(!source.contains("knowledge_review_publish"));
        assert!(!source.contains("knowledge_review_write"));
    }
}

#[test]
fn registry_enforces_size_and_duplicate_ids() {
    let mut registry = RequestRegistry::default();
    assert!(registry.insert("deskcp-0000000001".into(), None).is_ok());
    assert!(registry.insert("deskcp-0000000001".into(), None).is_err());
    for index in 2..=MAX_IN_FLIGHT_REQUESTS {
        registry
            .insert(format!("deskcp-{index:010}"), None)
            .unwrap();
    }
    assert!(registry.insert("deskcp-9999999999".into(), None).is_err());
}

#[test]
fn pending_terminal_wakes_and_records_result() {
    let pending = PendingRequest::new("deskcp-0000000001".into(), None);
    finish_pending(&pending, Ok(json!({"state":"COMPLETED"})));
    let mut guard = pending.state.lock().unwrap();
    assert!(guard.terminal_seen || guard.terminal.is_some());
    assert_eq!(
        guard.terminal.take().unwrap().unwrap()["state"],
        "COMPLETED"
    );
}

#[test]
fn registry_failure_drains_before_pending_state_is_finished() {
    let mut registry = RequestRegistry::default();
    let pending = registry.insert("deskcp-0000000001".into(), None).unwrap();
    let drained = registry.drain_all();
    assert!(registry.entries.is_empty());
    assert_eq!(drained.len(), 1);

    finish_pending(
        &drained[0],
        Err(BridgeError::new("sidecar_stopped", "sidecar stopped")),
    );
    let mut state = pending.state.lock().unwrap();
    let error = state.terminal.take().unwrap().unwrap_err();
    assert_eq!(error.code, "sidecar_stopped");
}

#[test]
fn command_input_validation_rejects_bad_values() {
    assert!(ensure_id("turn_id", "abcdefabcdefabcdefabcdef").is_ok());
    assert!(ensure_id("turn_id", "../bad").is_err());
    assert!(ensure_runtime_instance_id("abcdefabcdefabcdefabcdefabcdefab").is_ok());
    assert!(ensure_runtime_instance_id("abcdefabcdefabcdefabcdef").is_err());
    assert!(ensure_runtime_instance_id("ABCDEFABCDEFABCDEFABCDEFABCDEFAB").is_err());
    assert!(ensure_len(
        "prompt",
        &"x".repeat(MAX_PROMPT_CHARS + 1),
        MAX_PROMPT_CHARS
    )
    .is_err());
    assert!(validate_payload_for_method(
        ControlPlaneMethod::TurnCancel,
        &json!({"turn_id":"abcdefabcdefabcdefabcdef","reason":"user_requested"})
    )
    .is_ok());
    assert!(validate_payload_for_method(
        ControlPlaneMethod::TurnCancel,
        &json!({"turn_id":"abcdefabcdefabcdefabcdef","reason":"user_requested","extra":true})
    )
    .is_err());
    assert!(ensure_model_port(1024).is_ok());
    assert!(ensure_model_port(1023).is_err());
    assert!(ensure_provider("openai-compatible-local").is_ok());
    assert!(ensure_provider("https://example.test").is_err());
    assert!(ensure_harness("minimal").is_ok());
    assert!(ensure_harness("dynamic").is_err());
}

#[test]
fn event_validation_rejects_unknown_method_and_bad_id() {
    assert!(allowed_event_method("item.delta"));
    assert!(allowed_event_method("model.output.delta"));
    assert!(!allowed_event_method("provider.ready"));
    let event = json!({
        "method":"item.delta",
        "reply_to":"deskcp-0000000001",
        "sequence":0,
        "payload":{
            "control_plane_version":"v6.84.4",
            "session_id":"abcdefabcdefabcdefabcdef",
            "thread_id":null,
            "turn_id":null,
            "item_id":null,
            "state":"STREAMING",
            "kind":"assistant_message",
            "text":"hello",
            "metadata":{}
        }
    });
    assert!(ui_event_from_envelope(&event).is_ok());
}

fn model_identity() -> ModelRequestIdentity {
    ModelRequestIdentity {
        request_id: "0123456789abcdef01234567".into(),
        chat_session_id: "chat_session_1".into(),
        model_id: "qwen3-1.7b-instruct-q4-k-m".into(),
        submitted_at_unix_ms: 1_750_000_000_000,
        max_tokens: 128,
        seed: DEFAULT_MODEL_SEED,
        binding_fingerprint: "a".repeat(64),
    }
}

#[test]
fn reservation_check_releases_request_registry_before_writer_wait() {
    let identity = model_identity();
    let request_id = identity.request_id.clone();
    let registry = Arc::new(Mutex::new(ModelRequestRegistry::default()));
    registry
        .lock()
        .unwrap()
        .insert(identity, Vec::new())
        .unwrap();

    let worker_registry = Arc::clone(&registry);
    let (checked_tx, checked_rx) = std::sync::mpsc::channel();
    let (release_tx, release_rx) = std::sync::mpsc::channel();
    let worker = thread::spawn(move || {
        assert!(model_request_reservation_exists(
            &worker_registry,
            &request_id
        ));
        checked_tx.send(()).unwrap();
        release_rx.recv().unwrap();
    });

    checked_rx.recv_timeout(Duration::from_secs(1)).unwrap();
    assert!(registry.try_lock().is_ok());
    release_tx.send(()).unwrap();
    worker.join().unwrap();
}

#[test]
fn model_turn_wire_digest_covers_assistant_context() {
    let identity = model_identity();
    let neutral = AssistantContext::trusted("ru", false, None).expect("trusted context");
    let baseline =
        model_turn_wire_digest(&model_turn_wire_payload(&identity, "prompt", &neutral, &[]));
    assert_eq!(
        baseline,
        model_turn_wire_digest(&model_turn_wire_payload(&identity, "prompt", &neutral, &[])),
        "the digest must be stable for identical inputs"
    );

    let mut with_tools = neutral.clone();
    with_tools.capabilities.tools = vec!["files.read".to_string()];
    assert_ne!(
        baseline,
        model_turn_wire_digest(&model_turn_wire_payload(
            &identity,
            "prompt",
            &with_tools,
            &[]
        )),
        "a capability/tool grant change must change the wire digest"
    );

    let mut with_filesystem = neutral.clone();
    with_filesystem.capabilities.filesystem = true;
    assert_ne!(
        baseline,
        model_turn_wire_digest(&model_turn_wire_payload(
            &identity,
            "prompt",
            &with_filesystem,
            &[]
        )),
        "a capability flag change must change the wire digest"
    );

    let mut with_locale = neutral.clone();
    with_locale.conversation.locale = "en".to_string();
    assert_ne!(
        baseline,
        model_turn_wire_digest(&model_turn_wire_payload(
            &identity,
            "prompt",
            &with_locale,
            &[]
        )),
        "a conversation context change must change the wire digest"
    );

    assert_ne!(
        baseline,
        model_turn_wire_digest(&model_turn_wire_payload(&identity, "other", &neutral, &[])),
        "a prompt change must change the wire digest"
    );
}

#[test]
fn model_turn_dispatch_requires_the_reserved_wire_digest() {
    let identity = model_identity();
    let request_id = identity.request_id.clone();
    let neutral = AssistantContext::trusted("ru", false, None).expect("trusted context");
    let reserved =
        model_turn_wire_digest(&model_turn_wire_payload(&identity, "prompt", &neutral, &[]));
    let registry = Mutex::new(ModelRequestRegistry::default());

    // Missing reservation.
    assert_eq!(
        model_request_reservation_authorizes_wire(&registry, &request_id, &reserved)
            .unwrap_err()
            .code,
        "request_not_found"
    );

    registry
        .lock()
        .unwrap()
        .insert(identity.clone(), Vec::new())
        .unwrap();

    // Reserved but unbound: fail closed.
    assert_eq!(
        model_request_reservation_authorizes_wire(&registry, &request_id, &reserved)
            .unwrap_err()
            .code,
        "protocol_mismatch"
    );

    registry
        .lock()
        .unwrap()
        .bind_reserved_wire_digest(&request_id, reserved)
        .expect("bind reserved wire digest");
    assert!(model_request_reservation_authorizes_wire(&registry, &request_id, &reserved).is_ok());

    // A payload whose assistant_context escalates capabilities cannot dispatch
    // on a reservation authorized for the capability-neutral context.
    let mut escalated = neutral.clone();
    escalated.capabilities.tools = vec!["files.read".to_string()];
    let escalated_digest = model_turn_wire_digest(&model_turn_wire_payload(
        &identity,
        "prompt",
        &escalated,
        &[],
    ));
    assert_eq!(
        model_request_reservation_authorizes_wire(&registry, &request_id, &escalated_digest)
            .unwrap_err()
            .code,
        "protocol_mismatch"
    );

    // Rebinding an already bound reservation is refused.
    assert_eq!(
        registry
            .lock()
            .unwrap()
            .bind_reserved_wire_digest(&request_id, escalated_digest)
            .unwrap_err()
            .code,
        "protocol_mismatch"
    );
}

fn model_event(
    identity: &ModelRequestIdentity,
    method: &str,
    sequence: u64,
    state: &str,
    text: Option<&str>,
) -> UiControlPlaneEvent {
    let model_called = matches!(
        method,
        "model.turn.started" | "model.output.delta" | "model.turn.completed"
    ) || sequence > 0;
    let generated_bytes = text.map(str::len).unwrap_or_else(|| {
        if sequence > 0 {
            MAX_MODEL_EVENT_TEXT_PER_REQUEST
        } else {
            0
        }
    });
    let error = matches!(method, "model.turn.failed" | "model.turn.timed_out").then(|| {
        json!({
            "code": "model_request_failed",
            "message": "local model request failed",
            "retryable": true,
        })
    });
    let mut metadata = json!({
        "provider_id": "managed-llama-cpp",
        "harness_id": "minimal",
        "request_id": identity.request_id,
        "turn_id": identity.request_id,
        "chat_session_id": identity.chat_session_id,
        "model_id": identity.model_id,
        "submitted_at_unix_ms": identity.submitted_at_unix_ms,
        "max_tokens": identity.max_tokens,
        "seed": identity.seed,
        "effort": "off",
        "binding_fingerprint": identity.binding_fingerprint,
        "model_called": model_called,
        "tools_executed": 0,
        "persistence": false,
        "generated_bytes": generated_bytes,
    });
    if let Some(error) = error {
        metadata["error"] = error;
    }
    UiControlPlaneEvent {
        method: method.into(),
        sequence,
        reply_to: identity.request_id.clone(),
        request_id: Some(identity.request_id.clone()),
        chat_session_id: Some(identity.chat_session_id.clone()),
        model_id: Some(identity.model_id.clone()),
        control_plane_version: DESKTOP_STATUS_BRIDGE_VERSION.into(),
        session_id: None,
        thread_id: None,
        turn_id: Some(identity.request_id.clone()),
        item_id: None,
        state: state.into(),
        kind: None,
        text: text.map(str::to_owned),
        metadata,
    }
}

#[test]
fn typed_model_command_payloads_are_exact() {
    let identity = model_identity();
    let payload = json!({
        "request_id": identity.request_id,
        "chat_session_id": identity.chat_session_id,
        "model_id": identity.model_id,
        "submitted_at_unix_ms": identity.submitted_at_unix_ms,
        "max_tokens": identity.max_tokens,
        "seed": identity.seed,
        "effort": "off",
        "prompt": "hello",
        "assistant_context": AssistantContext::trusted("ru", false, None).unwrap(),
        "binding_fingerprint": identity.binding_fingerprint,
        "messages": [],
    });
    assert!(validate_payload_for_method(ControlPlaneMethod::ModelTurnStart, &payload).is_ok());
    let mut without_effort = payload.clone();
    without_effort
        .as_object_mut()
        .expect("model turn payload object")
        .remove("effort");
    assert!(
        validate_payload_for_method(ControlPlaneMethod::ModelTurnStart, &without_effort).is_err()
    );
    assert!(validate_payload_for_method(
        ControlPlaneMethod::ModelTurnStart,
        &json!({"prompt":"hello","binding_fingerprint":"a".repeat(64)})
    )
    .is_err());
    assert!(validate_payload_for_method(
        ControlPlaneMethod::ModelTurnCancel,
        &model_cancel_payload("0123456789abcdef01234567")
    )
    .is_ok());
    assert_eq!(
        model_cancel_payload("0123456789abcdef01234567"),
        json!({"request_id":"0123456789abcdef01234567"})
    );
    assert_eq!(
        model_cancel_request_envelope("deskcp-0000000001", "0123456789abcdef01234567"),
        json!({
            "protocol": ipc::IPC_PROTOCOL,
            "version": ipc::IPC_PROTOCOL_VERSION,
            "type": "request",
            "id": "deskcp-0000000001",
            "method": "model.turn.cancel",
            "run_id": null,
            "sequence": 0,
            "reply_to": null,
            "payload": {"request_id":"0123456789abcdef01234567"},
        })
    );
    assert!(validate_payload_for_method(
        ControlPlaneMethod::ModelTurnCancel,
        &json!({"turn_id":"0123456789abcdef01234567"})
    )
    .is_err());
}

#[test]
fn model_acceptance_requires_all_immutable_fields() {
    let identity = model_identity();
    let response = json!({
        "request_id": identity.request_id,
        "turn_id": identity.request_id,
        "chat_session_id": identity.chat_session_id,
        "model_id": identity.model_id,
        "submitted_at_unix_ms": identity.submitted_at_unix_ms,
        "max_tokens": identity.max_tokens,
    "seed": identity.seed,
        "binding_fingerprint": identity.binding_fingerprint,
        "state": "Accepted",
        "effort": "off",
        "provider_id": "managed-llama-cpp",
        "harness_id": "minimal",
        "model_called": false,
        "tools_executed": 0,
        "persistence": false,
    });
    assert!(validate_model_acceptance(&response, &identity, "off").is_ok());
    let mut wrong = response;
    wrong["model_id"] = json!("foreign-model");
    assert!(validate_model_acceptance(&wrong, &identity, "off").is_err());
    let mut extra = project_model_acceptance(&identity, "managed-llama-cpp", "minimal", "off");
    extra["untrusted"] = json!("cross-webview");
    assert!(validate_model_acceptance(&extra, &identity, "off").is_err());
}

#[test]
fn knowledge_model_receipts_cover_include_and_reject_dispatch() {
    let hash = format!("sha256:{}", "a".repeat(64));
    let include_payload = json!({
        "turn_id": "0123456789abcdef01234567",
        "injection_id": "kinj:approved-1",
        "expected_preview_hash": hash,
        "action": "INCLUDE_AND_SEND",
    });
    let include =
        pending_knowledge_model(ControlPlaneMethod::KnowledgeTurnDecide, &include_payload).unwrap();
    assert!(include.include_knowledge);
    let include_receipt = json!({
        "injection_id": include.injection_id,
        "turn_id": include.turn_id,
        "action": "INCLUDE_AND_SEND",
        "preview_hash": include.preview_hash,
        "state": "DISPATCHING",
        "decision_source": "USER_APPROVAL",
        "model_turn_id": "fedcba9876543210fedcba98",
        "model_dispatched": true,
        "knowledge_included": true,
        "duplicate": false,
    });
    assert_eq!(
        validate_knowledge_model_receipt(&include_receipt, &include).unwrap(),
        "fedcba9876543210fedcba98"
    );

    let reject_payload = json!({
        "turn_id": "0123456789abcdef01234567",
        "injection_id": "kinj:approved-1",
        "expected_preview_hash": format!("sha256:{}", "a".repeat(64)),
        "action": "REJECT_AND_SEND_WITHOUT_KNOWLEDGE",
    });
    let reject =
        pending_knowledge_model(ControlPlaneMethod::KnowledgeTurnDecide, &reject_payload).unwrap();
    assert!(!reject.include_knowledge);
    let mut reject_receipt = include_receipt;
    reject_receipt["action"] = json!("REJECT_AND_SEND_WITHOUT_KNOWLEDGE");
    reject_receipt["state"] = json!("REJECTED");
    reject_receipt["knowledge_included"] = json!(false);
    assert!(validate_knowledge_model_receipt(&reject_receipt, &reject).is_ok());
    let mut cancel_payload = reject_payload;
    cancel_payload["action"] = json!("CANCEL");
    assert!(
        pending_knowledge_model(ControlPlaneMethod::KnowledgeTurnDecide, &cancel_payload).is_none()
    );
}

#[test]
fn assistant_context_is_trusted_typed_and_fail_closed() {
    let russian = AssistantContext::trusted("ru", false, None).unwrap();
    let english = AssistantContext::trusted("en", false, None).unwrap();
    let with_files = AssistantContext::trusted("ru", true, None).unwrap();
    assert_eq!(russian.application.name, "LocalComet");
    assert_eq!(russian.application.mode, "local_offline_desktop_assistant");
    assert_eq!(russian.application.version, DESKTOP_STATUS_BRIDGE_VERSION);
    assert_eq!(russian.conversation.locale, "ru");
    assert_eq!(english.conversation.locale, "en");
    assert!(!russian.conversation.project_context_available);
    assert!(!russian.conversation.selected_files_context_available);
    assert!(with_files.conversation.selected_files_context_available);
    assert!(!with_files.capabilities.filesystem);
    assert!(russian.capabilities.local_chat);
    assert!(russian.capabilities.local_model_inference);
    assert!(!russian.capabilities.internet);
    assert!(!russian.capabilities.email);
    assert!(!russian.capabilities.browser);
    // internet toggle is opt-in — when granted, both internet and browser reflect it
    let with_internet = AssistantContext::trusted(
        "ru",
        false,
        Some(&AgentPermissions {
            files: false,
            shell: false,
            tools: false,
            computer_use: false,
            internet: true,
        }),
    )
    .unwrap();
    assert!(with_internet.capabilities.internet);
    assert!(with_internet.capabilities.browser);
    assert!(with_internet
        .capabilities
        .tools
        .iter()
        .any(|t| t == "web.search"));
    assert!(with_internet
        .capabilities
        .tools
        .iter()
        .any(|t| t == "web.fetch"));
    assert!(!russian.capabilities.filesystem);
    assert!(!russian.capabilities.vault);
    assert!(!russian.capabilities.computer_use);
    assert!(!russian.capabilities.shell);
    assert!(russian.capabilities.tools.is_empty());
    assert!(AssistantContext::trusted("fr", false, None).is_ok());
    assert!(AssistantContext::trusted("ar", false, None).is_ok());
    assert!(AssistantContext::trusted("xx", false, None).is_err());

    assert_eq!(
        serde_json::to_value(&russian).unwrap(),
        json!({
            "application": {
                "name": "LocalComet",
                "mode": "local_offline_desktop_assistant",
                "version": DESKTOP_STATUS_BRIDGE_VERSION,
            },
            "conversation": {
                "locale": "ru",
                "project_context_available": false,
                "selected_files_context_available": false,
            },
            "capabilities": {
                "local_chat": true,
                "local_model_inference": true,
                "internet": false,
                "email": false,
                "browser": false,
                "filesystem": false,
                "vault": false,
                "computer_use": false,
                "shell": false,
                "tools": [],
            },
        }),
        "Rust must serialize the exact assistant_context accepted by the sidecar",
    );

    let serialized = serde_json::to_string(&russian).unwrap();
    assert!(!serialized.contains("C:\\"));
    assert!(!serialized.contains("/home/"));
    assert!(!serialized.to_ascii_lowercase().contains("secret"));
}

#[test]
fn assistant_context_contract_payloads_are_machine_readable() {
    let cases = [
        ("neutral", None),
        (
            "files",
            Some(AgentPermissions {
                files: true,
                shell: false,
                tools: false,
                computer_use: false,
                internet: false,
            }),
        ),
        (
            "shell",
            Some(AgentPermissions {
                files: false,
                shell: true,
                tools: false,
                computer_use: false,
                internet: false,
            }),
        ),
        (
            "computer_use",
            Some(AgentPermissions {
                files: false,
                shell: false,
                tools: false,
                computer_use: true,
                internet: false,
            }),
        ),
        (
            "internet",
            Some(AgentPermissions {
                files: false,
                shell: false,
                tools: false,
                computer_use: false,
                internet: true,
            }),
        ),
    ];
    let payloads: Vec<Value> = cases
        .iter()
        .map(|(name, permissions)| {
            json!({
                "case": name,
                "context": AssistantContext::trusted("ru", false, permissions.as_ref())
                    .expect("trusted context"),
            })
        })
        .collect();
    println!(
        "LOCALCOMET_ASSISTANT_CONTEXT_CONTRACT={}",
        serde_json::to_string(&payloads).expect("serialize assistant context contract")
    );
}

#[test]
fn removing_knowledge_admission_wakes_its_watchdog_immediately() {
    let context = PendingKnowledgeModel {
        turn_id: "0123456789abcdef01234567".into(),
        injection_id: "kinj:approved-1".into(),
        preview_hash: format!("sha256:{}", "a".repeat(64)),
        include_knowledge: true,
    };
    let admission = KnowledgeAdmission::new(context);
    let watchdog = Arc::clone(&admission.watchdog);
    let mut admissions = HashMap::new();
    admissions.insert("fedcba9876543210fedcba98".to_owned(), admission);
    let (finished_tx, finished_rx) = std::sync::mpsc::channel();
    let waiter = thread::spawn(move || {
        finished_tx
            .send(watchdog.wait_for_timeout(Duration::from_secs(5)))
            .unwrap();
    });

    let removed = admissions.remove("fedcba9876543210fedcba98");
    drop(removed);
    assert!(!finished_rx
        .recv_timeout(Duration::from_millis(500))
        .expect("removed admission should wake watchdog"));
    waiter.join().unwrap();
}

#[test]
fn model_event_metadata_is_transactional_exact_and_projected() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let mut invalid = model_event(&identity, "model.turn.started", 0, "Streaming", None);
    invalid.metadata["untrusted"] = json!({"raw": "sidecar"});
    assert!(
        validate_and_record_model_event(&mut entry, &invalid, "model.turn.started", 0).is_err()
    );
    assert!(entry.provider_id.is_none());
    assert!(!entry.started_seen);
    assert_eq!(entry.next_sequence, 0);

    let valid = model_event(&identity, "model.turn.started", 0, "Streaming", None);
    validate_and_record_model_event(&mut entry, &valid, "model.turn.started", 0).unwrap();
    let projected = project_model_event_metadata(&valid).unwrap();
    assert_eq!(projected["provider_id"], "managed-llama-cpp");
    assert_eq!(projected["harness_id"], "minimal");
    assert!(projected.get("request_id").is_none());
    assert!(projected.get("untrusted").is_none());
}

#[test]
fn projected_tool_event_preserves_validated_tool_calls() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".into()]);
    let event = structured_tool_event(
        &identity,
        "model.tool.request",
        vec![("files.read", valid_tool_arguments_json("files.read"))],
    );
    validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0).unwrap();
    let projected = project_model_event_metadata(&event).unwrap();
    assert_eq!(projected["tool_calls"], event.metadata["tool_calls"]);
}

#[test]
fn knowledge_audit_is_allowed_only_on_started_event_and_projected() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    entry.accepted = true;
    entry.knowledge_model = true;
    entry.knowledge_included = true;
    entry.knowledge_injection_id = Some("kinj:approved-1".into());
    let mut started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
    let hash = format!("sha256:{}", "b".repeat(64));
    let metadata = started.metadata.as_object_mut().unwrap();
    metadata.insert("knowledge_injection_id".into(), json!("kinj:approved-1"));
    metadata.insert("knowledge_request_id".into(), json!("kreq:request-1"));
    metadata.insert(
        "knowledge_bundle_id".into(),
        json!(format!("kb:{}", "c".repeat(64))),
    );
    for key in [
        "knowledge_vault_revision",
        "knowledge_preview_hash",
        "knowledge_context_sha256",
    ] {
        metadata.insert(key.into(), json!(hash));
    }
    metadata.insert("knowledge_source_count".into(), json!(1));
    metadata.insert(
        "knowledge_serialization_format".into(),
        json!("localcomet.knowledge-context.v1"),
    );
    metadata.insert("knowledge_decision_source".into(), json!("USER_APPROVAL"));
    metadata.insert("knowledge_synthetic_message".into(), json!(true));
    metadata.insert("knowledge_context_reference_data".into(), json!(true));
    validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap();
    let projected = project_model_event_metadata(&started).unwrap();
    assert_eq!(projected["knowledge_injection_id"], "kinj:approved-1");

    let delta = model_event(&identity, "model.output.delta", 1, "Streaming", Some("x"));
    validate_and_record_model_event(&mut entry, &delta, "model.output.delta", 1).unwrap();
    let projected_delta = project_model_event_metadata(&delta).unwrap();
    assert!(projected_delta.get("knowledge_injection_id").is_none());
}

#[test]
fn buffered_terminal_is_owned_when_registry_cleanup_wins() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let terminal = model_event(&identity, "model.turn.cancelled", 0, "Cancelled", None);
    validate_and_record_model_event(&mut entry, &terminal, "model.turn.cancelled", 0).unwrap();
    entry.buffered_events.push(terminal);
    let owned = take_authoritative_buffered_terminal(&mut entry).unwrap();
    assert_eq!(owned.len(), 1);
    assert_eq!(owned[0].method, "model.turn.cancelled");
    assert!(entry.buffered_events.is_empty());
}

#[test]
fn synthetic_terminal_matches_frontend_metadata_shape_and_metrics() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity, Vec::new());
    entry.provider_id = Some("managed-llama-cpp".into());
    entry.harness_id = Some("native-localcomet".into());
    entry.model_called = true;
    entry.generated_bytes = 42;
    let event = model_terminal_event(
        &entry,
        "model.turn.timed_out",
        "TimedOut",
        "request_timed_out",
        "untrusted detail",
    );
    assert_eq!(event.metadata["provider_id"], "managed-llama-cpp");
    assert_eq!(event.metadata["harness_id"], "native-localcomet");
    assert_eq!(event.metadata["model_called"], true);
    assert_eq!(event.metadata["generated_bytes"], 42);
    assert_eq!(event.metadata["error"]["code"], "request_timed_out");
    assert_eq!(
        event.metadata["error"]["message"],
        "model request timed out"
    );
}

#[test]
fn model_event_sequence_is_strict_and_terminal_is_unique() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    entry.accepted = true;
    let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
    assert!(
        validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap()
    );
    let delta = model_event(
        &identity,
        "model.output.delta",
        1,
        "Streaming",
        Some("hello"),
    );
    assert!(validate_and_record_model_event(&mut entry, &delta, "model.output.delta", 1).unwrap());
    let completed = model_event(&identity, "model.turn.completed", 2, "Completed", None);
    assert!(
        validate_and_record_model_event(&mut entry, &completed, "model.turn.completed", 2).unwrap()
    );
    assert!(
        validate_and_record_model_event(&mut entry, &completed, "model.turn.completed", 2).is_err()
    );
    let late = model_event(
        &identity,
        "model.output.delta",
        3,
        "Streaming",
        Some("late"),
    );
    assert!(validate_and_record_model_event(&mut entry, &late, "model.output.delta", 3).is_err());
}

#[test]
fn acceptance_release_gate_preserves_buffered_event_order() {
    let identity = model_identity();
    let mut registry = ModelRequestRegistry::default();
    let _watchdog = registry.insert(identity.clone(), Vec::new()).unwrap();
    {
        let entry = registry.entries.get_mut(&identity.request_id).unwrap();
        let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        assert!(validate_and_record_model_event(entry, &started, "model.turn.started", 0).unwrap());
        assert!(model_event_is_gated(entry));
        entry.buffered_events.push(started);
        entry.accepted = true;
        assert!(begin_model_event_release(entry));
    }

    let first_batch = registry
        .take_release_batch(&identity.request_id)
        .expect("accepted event batch");
    {
        let entry = registry.entries.get_mut(&identity.request_id).unwrap();
        let delta = model_event(
            &identity,
            "model.output.delta",
            1,
            "Streaming",
            Some("next"),
        );
        assert!(validate_and_record_model_event(entry, &delta, "model.output.delta", 1).unwrap());
        assert!(model_event_is_gated(entry));
        entry.buffered_events.push(delta);
    }
    let second_batch = registry
        .take_release_batch(&identity.request_id)
        .expect("event received while releasing");
    assert!(registry.take_release_batch(&identity.request_id).is_none());
    assert!(!model_event_is_gated(
        registry.entries.get(&identity.request_id).unwrap()
    ));

    let sequences: Vec<u64> = first_batch
        .into_iter()
        .chain(second_batch)
        .map(|event| event.sequence)
        .collect();
    assert_eq!(sequences, vec![0, 1]);
}

#[test]
fn synthetic_terminal_waits_behind_an_owned_release_batch() {
    let identity = model_identity();
    let mut registry = ModelRequestRegistry::default();
    let _watchdog = registry.insert(identity.clone(), Vec::new()).unwrap();
    {
        let entry = registry.entries.get_mut(&identity.request_id).unwrap();
        entry.accepted = true;
        let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        validate_and_record_model_event(entry, &started, "model.turn.started", 0).unwrap();
        entry.buffered_events.push(started);
        assert!(begin_model_event_release(entry));
    }
    let first_batch = registry
        .take_release_batch(&identity.request_id)
        .expect("release owner should take the started event");
    assert!(registry
        .remove_or_queue_synthetic_terminal(
            &identity.request_id,
            "model.turn.timed_out",
            "TimedOut",
            "request_timed_out",
            "model request exceeded the bounded lifetime",
        )
        .is_none());
    assert!(registry.entries.contains_key(&identity.request_id));
    let terminal_batch = registry
        .take_release_batch(&identity.request_id)
        .expect("release owner should take the queued terminal");

    let methods: Vec<_> = first_batch
        .iter()
        .chain(terminal_batch.iter())
        .map(|event| (event.sequence, event.method.as_str()))
        .collect();
    assert_eq!(
        methods,
        vec![(0, "model.turn.started"), (1, "model.turn.timed_out")]
    );
    assert!(registry.entries[&identity.request_id].cancel_after_synthetic_release);
    assert!(registry.take_release_batch(&identity.request_id).is_none());
    assert!(!registry.entries.contains_key(&identity.request_id));
}

#[test]
fn cancellation_reserved_before_acceptance_forces_a_second_cancel() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity, Vec::new());
    entry.cancel_requested_before_acceptance = true;
    entry.cancel_pending = false;

    let (release, needs_recancel) = record_model_acceptance(&mut entry);
    assert!(!release);
    assert!(needs_recancel);
    assert!(entry.cancel_requested_before_acceptance);
    assert!(model_event_is_gated(&entry));

    entry.cancel_pending = true;
    assert!(model_event_is_gated(&entry));
    entry.cancel_pending = false;
    entry.cancel_accepted = true;
    entry.cancel_requested_before_acceptance = false;
    assert!(begin_model_event_release(&mut entry));
}

#[test]
fn cancellation_terminal_before_acceptance_keeps_entry_until_acceptance() {
    let identity = model_identity();
    let mut registry = ModelRequestRegistry::default();
    let _watchdog = registry.insert(identity.clone(), Vec::new()).unwrap();
    {
        let entry = registry.entries.get_mut(&identity.request_id).unwrap();
        entry.cancel_pending = true;
        let cancelled = model_event(&identity, "model.turn.cancelled", 0, "Cancelled", None);
        assert!(
            validate_and_record_model_event(entry, &cancelled, "model.turn.cancelled", 0).unwrap()
        );
        assert!(model_event_is_gated(entry));
        entry.buffered_events.push(cancelled);

        entry.cancel_pending = false;
        entry.cancel_accepted = true;
        assert!(!begin_model_event_release(entry));
    }
    assert!(registry.entries.contains_key(&identity.request_id));

    {
        let entry = registry.entries.get_mut(&identity.request_id).unwrap();
        entry.accepted = true;
        assert!(begin_model_event_release(entry));
    }
    let terminal_batch = registry
        .take_release_batch(&identity.request_id)
        .expect("cancel terminal remains buffered until acceptance");
    assert_eq!(terminal_batch.len(), 1);
    assert_eq!(terminal_batch[0].method, "model.turn.cancelled");
    assert!(registry.entries.contains_key(&identity.request_id));
    assert!(registry.take_release_batch(&identity.request_id).is_none());
    assert!(!registry.entries.contains_key(&identity.request_id));
}

#[test]
fn accepted_request_does_not_release_events_during_cancel_round_trip() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    entry.cancel_pending = true;
    let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
    assert!(
        validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap()
    );
    entry.buffered_events.push(started);
    entry.accepted = true;
    assert!(!begin_model_event_release(&mut entry));
    assert_eq!(entry.buffered_events.len(), 1);

    entry.cancel_pending = false;
    assert!(begin_model_event_release(&mut entry));
}

#[test]
fn pre_ack_delta_releases_before_cancelled_terminal() {
    let identity = model_identity();
    let mut registry = ModelRequestRegistry::default();
    let _watchdog = registry.insert(identity.clone(), Vec::new()).unwrap();
    {
        let entry = registry.entries.get_mut(&identity.request_id).unwrap();
        entry.accepted = true;
        let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        validate_and_record_model_event(entry, &started, "model.turn.started", 0).unwrap();
        entry.cancel_pending = true;
        let delta = model_event(
            &identity,
            "model.output.delta",
            1,
            "Streaming",
            Some("raced delta"),
        );
        validate_and_record_model_event(entry, &delta, "model.output.delta", 1).unwrap();
        assert!(model_event_is_gated(entry));
        entry.buffered_events.push(delta);

        entry.cancel_pending = false;
        entry.cancel_accepted = true;
        assert!(begin_model_event_release(entry));
    }
    let batch = registry
        .take_release_batch(&identity.request_id)
        .expect("pre-ack delta batch");
    assert_eq!(batch.len(), 1);
    assert_eq!(batch[0].method, "model.output.delta");
    assert!(registry.take_release_batch(&identity.request_id).is_none());

    let entry = registry.entries.get_mut(&identity.request_id).unwrap();
    let cancelled = model_event(&identity, "model.turn.cancelled", 2, "Cancelled", None);
    assert!(validate_and_record_model_event(entry, &cancelled, "model.turn.cancelled", 2).unwrap());
}

#[test]
fn model_event_rejects_foreign_identity_and_out_of_order_sequence() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let out_of_order = model_event(&identity, "model.turn.started", 1, "Streaming", None);
    assert!(
        validate_and_record_model_event(&mut entry, &out_of_order, "model.turn.started", 1)
            .is_err()
    );
    let mut foreign = model_event(&identity, "model.turn.started", 0, "Streaming", None);
    foreign.request_id = Some("fedcba9876543210fedcba98".into());
    assert!(
        validate_and_record_model_event(&mut entry, &foreign, "model.turn.started", 0).is_err()
    );
    let mut wrong_binding = model_event(&identity, "model.turn.started", 0, "Streaming", None);
    wrong_binding.metadata["binding_fingerprint"] = json!("b".repeat(64));
    assert!(
        validate_and_record_model_event(&mut entry, &wrong_binding, "model.turn.started", 0)
            .is_err()
    );
}

#[test]
fn model_event_envelope_uses_run_id_fallback_and_typed_top_level_identity() {
    let identity = model_identity();
    let envelope = json!({
        "method": "model.turn.started",
        "sequence": 0,
        "reply_to": null,
        "run_id": identity.request_id,
        "payload": {
            "control_plane_version": DESKTOP_STATUS_BRIDGE_VERSION,
            "request_id": identity.request_id,
            "chat_session_id": identity.chat_session_id,
            "model_id": identity.model_id,
            "session_id": null,
            "thread_id": null,
            "turn_id": identity.request_id,
            "item_id": null,
            "state": "Streaming",
            "kind": null,
            "text": null,
            "metadata": {},
        }
    });
    let event = ui_event_from_envelope(&envelope).expect("typed model event envelope");
    assert_eq!(event.reply_to, identity.request_id);
    assert_eq!(
        event.request_id.as_deref(),
        Some(identity.request_id.as_str())
    );
    assert_eq!(
        event.chat_session_id.as_deref(),
        Some(identity.chat_session_id.as_str())
    );
    assert_eq!(event.model_id.as_deref(), Some(identity.model_id.as_str()));
    assert!(event.session_id.is_none());
}

#[test]
fn accepted_cancellation_rejects_content_and_completion() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    entry.accepted = true;
    let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
    validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap();
    entry.cancel_accepted = true;
    let late = model_event(
        &identity,
        "model.output.delta",
        1,
        "Streaming",
        Some("late"),
    );
    assert!(validate_and_record_model_event(&mut entry, &late, "model.output.delta", 1).is_err());
    let completed = model_event(&identity, "model.turn.completed", 1, "Completed", None);
    assert!(
        validate_and_record_model_event(&mut entry, &completed, "model.turn.completed", 1).is_err()
    );
    let failed = model_event(&identity, "model.turn.failed", 1, "Failed", None);
    assert!(validate_and_record_model_event(&mut entry, &failed, "model.turn.failed", 1).is_err());
    let timed_out = model_event(&identity, "model.turn.timed_out", 1, "TimedOut", None);
    assert!(
        validate_and_record_model_event(&mut entry, &timed_out, "model.turn.timed_out", 1).is_err()
    );
    let cancelled = model_event(&identity, "model.turn.cancelled", 1, "Cancelled", None);
    assert!(
        validate_and_record_model_event(&mut entry, &cancelled, "model.turn.cancelled", 1).unwrap()
    );
}

#[test]
fn cancel_ack_and_registry_cleanup_are_bounded() {
    let identity = model_identity();
    let active = json!({
        "request_id": identity.request_id,
        "turn_id": identity.request_id,
        "state": "Cancelling",
        "accepted": true,
        "already_terminal": false,
        "worker_alive": true,
    });
    assert_eq!(
        validate_model_cancel_ack(&active, &identity.request_id).unwrap(),
        ModelCancelAcknowledgement {
            accepted: true,
            already_terminal: false
        }
    );
    let mut incoherent = active.clone();
    incoherent["worker_alive"] = json!(false);
    assert!(validate_model_cancel_ack(&incoherent, &identity.request_id).is_err());
    let stopped = json!({
        "request_id": identity.request_id,
        "turn_id": identity.request_id,
        "state": "Cancelled",
        "accepted": true,
        "already_terminal": false,
        "worker_alive": false,
    });
    assert!(validate_model_cancel_ack(&stopped, &identity.request_id).is_ok());
    let mut registry = ModelRequestRegistry::default();
    let _watchdog = registry.insert(identity.clone(), Vec::new()).unwrap();
    assert_eq!(registry.entries.len(), 1);
    registry.remove(&identity.request_id);
    assert!(registry.entries.is_empty());
    assert_eq!(
        terminal_model_cancel_ack(&identity.request_id),
        json!({
            "request_id": identity.request_id,
            "turn_id": identity.request_id,
            "state": "Cancelled",
            "accepted": false,
            "already_terminal": true,
            "worker_alive": false,
        })
    );
    let terminal = model_terminal_event(
        &ModelRequestEntry::new(identity, Vec::new()),
        "model.turn.failed",
        "Failed",
        "protocol_mismatch",
        "invalid event",
    );
    assert_eq!(terminal.metadata["model_called"], false);
    assert_eq!(terminal.metadata["tools_executed"], 0);
    assert_eq!(terminal.metadata["persistence"], false);
    assert_eq!(terminal.metadata["generated_bytes"], 0);
    assert_eq!(
        terminal.metadata["binding_fingerprint"],
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    );
}

#[test]
fn watchdog_touch_slides_inactivity_deadline_bug4() {
    let watchdog = std::sync::Arc::new(ModelRequestWatchdog::new());
    let (done_tx, done_rx) = std::sync::mpsc::channel();
    let waiter = {
        let watchdog = std::sync::Arc::clone(&watchdog);
        thread::spawn(move || {
            let timed_out = watchdog.wait_for_timeout(Duration::from_millis(600));
            done_tx.send(timed_out).unwrap();
        })
    };
    // Touch three times inside the original window; each touch slides the
    // deadline, so the waiter must NOT observe a timeout for >= 1.2 s.
    for _ in 0..3 {
        thread::sleep(Duration::from_millis(150));
        watchdog.touch();
    }
    // No timeout within 600 ms of the last touch.
    assert!(
        done_rx.recv_timeout(Duration::from_millis(500)).is_err(),
        "touch must slide the inactivity deadline"
    );
    watchdog.cancel();
    assert!(
        !done_rx
            .recv_timeout(Duration::from_millis(500))
            .expect("cancel must wake the waiter"),
        "cancel is not a timeout"
    );
    waiter.join().unwrap();
}

#[test]
fn removing_model_request_wakes_watchdog_without_full_timeout() {
    let identity = model_identity();
    let mut registry = ModelRequestRegistry::default();
    let watchdog = registry.insert(identity.clone(), Vec::new()).unwrap();
    let (finished_tx, finished_rx) = std::sync::mpsc::channel();
    let waiter = thread::spawn(move || {
        let timed_out = watchdog.wait_for_timeout(Duration::from_secs(5));
        finished_tx.send(timed_out).unwrap();
    });

    registry.remove(&identity.request_id);
    assert!(!finished_rx
        .recv_timeout(Duration::from_millis(500))
        .expect("removed request should wake watchdog"));
    waiter.join().unwrap();
}

#[test]
fn empty_model_delta_advances_sequence_and_is_forwarded_for_ordering() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
    validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap();
    let empty = model_event(&identity, "model.output.delta", 1, "Streaming", Some(""));
    assert!(validate_and_record_model_event(&mut entry, &empty, "model.output.delta", 1).unwrap());
    assert_eq!(entry.next_sequence, 2);
}

#[test]
fn t0_unknown_model_event_method_is_rejected() {
    assert!(!allowed_model_event_method("provider.unknown"));
    assert!(!allowed_model_event_method("model.tool.unknown"));
    assert!(!allowed_model_event_method(""));
}

#[test]
fn t1_model_tool_request_is_allowed_model_event() {
    assert!(allowed_model_event_method("model.tool.request"));
    assert!(allowed_event_method("model.tool.request"));
}

#[test]
fn t2_model_turn_tool_calls_is_allowed_model_event() {
    assert!(allowed_model_event_method("model.turn.tool_calls"));
    assert!(allowed_event_method("model.turn.tool_calls"));
}

#[test]
fn tool_events_reach_specialized_branch_and_are_denied_without_permissive_acceptance() {
    let identity = model_identity();
    for method in ["model.tool.request", "model.turn.tool_calls"] {
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let event = model_event(&identity, method, 0, "Streaming", None);
        let result = validate_and_record_model_event(&mut entry, &event, method, 0);
        let error = result.expect_err("tool event must be denied before B2");
        assert_ne!(
            error.code, "unsupported_method",
            "{method} must not be unsupported_method"
        );
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(entry.next_sequence, 0);
        assert_eq!(entry.event_count, 0);
    }
}

#[test]
fn unknown_method_in_validator_remains_unsupported_method() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let event = model_event(&identity, "model.turn.unknown", 0, "Streaming", None);
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.unknown", 0)
        .expect_err("unknown method must be rejected");
    assert_eq!(error.code, "unsupported_method");
}

#[test]
fn b2_content_event_remains_valid_when_tools_are_disabled() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
    validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap();
    let delta = model_event(
        &identity,
        "model.output.delta",
        1,
        "Streaming",
        Some("hello"),
    );
    assert!(validate_and_record_model_event(&mut entry, &delta, "model.output.delta", 1).unwrap());
    assert_eq!(entry.next_sequence, 2);
    assert_eq!(entry.event_count, 2);
}

#[test]
fn computer_use_tool_call_has_a_longer_bounded_deadline() {
    let computer_use = serde_json::json!({"tool": "computer_use"});
    let ordinary_tool = serde_json::json!({"tool": "files.read"});
    assert_eq!(
        request_timeout_for_payload(ControlPlaneMethod::ToolCall, &computer_use),
        COMPUTER_USE_TOOL_CALL_TIMEOUT
    );
    assert_eq!(
        request_timeout_for_payload(ControlPlaneMethod::ToolCall, &ordinary_tool),
        TOOL_CALL_TIMEOUT
    );
}

#[test]
fn b2_model_tool_request_is_rejected_when_request_tools_are_disabled() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let event = model_event(&identity, "model.tool.request", 0, "Streaming", None);
    let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect_err("tool event must be rejected when tools are disabled");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(entry.next_sequence, 0, "state must not advance");
    assert_eq!(entry.event_count, 0, "event must not be recorded");
    assert_eq!(entry.generated_bytes, 0, "generated_bytes must not advance");
    assert!(
        error.message.contains("not permitted")
            || error.message.contains("not enabled")
            || error.message.contains("disabled"),
        "B2 RED: expected tools-disabled reason, got: {}",
        error.message
    );
}

#[test]
fn b2_terminal_tool_calls_are_rejected_when_request_tools_are_disabled() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let event = model_event(&identity, "model.turn.tool_calls", 0, "ToolCalls", None);
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("terminal tool event must be rejected when tools are disabled");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(!entry.terminal_seen, "terminal must not be accepted");
    assert_eq!(entry.next_sequence, 0, "state must not advance");
    assert_eq!(entry.event_count, 0, "event must not be recorded");
    assert!(
        error.message.contains("not permitted")
            || error.message.contains("not enabled")
            || error.message.contains("disabled"),
        "B2 RED: expected tools-disabled reason, got: {}",
        error.message
    );
}

#[test]
fn b2_tool_permissions_do_not_leak_between_adjacent_requests() {
    let identity_a = model_identity();
    let identity_b = ModelRequestIdentity {
        request_id: "fedcba9876543210fedcba98".into(),
        chat_session_id: "chat_session_2".into(),
        model_id: "qwen3-1.7b-instruct-q4-k-m".into(),
        submitted_at_unix_ms: 1_750_000_000_001,
        max_tokens: 128,
        seed: DEFAULT_MODEL_SEED,
        binding_fingerprint: "b".repeat(64),
    };
    let entry_a = ModelRequestEntry::new(identity_a.clone(), vec!["files.read".to_string()]);
    let mut entry_b = ModelRequestEntry::new(identity_b.clone(), Vec::new());
    assert!(entry_a.tools_are_enabled());
    assert!(!entry_b.tools_are_enabled());
    assert!(entry_b.permitted_tool_names.is_empty());
    let event_b = model_event(&identity_b, "model.tool.request", 0, "Streaming", None);
    let error = validate_and_record_model_event(&mut entry_b, &event_b, "model.tool.request", 0)
        .expect_err("tool event on disabled request B must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(entry_b.next_sequence, 0);
    assert_eq!(entry_b.event_count, 0);
    assert_eq!(entry_a.next_sequence, 0, "entry A state must be unaffected");
    assert_eq!(entry_a.event_count, 0, "entry A state must be unaffected");
    assert!(
        error.message.contains("not permitted"),
        "B2: expected tools-disabled reason for B, got: {}",
        error.message
    );
}

#[test]
fn b2_tool_event_cannot_enable_tools_for_a_disabled_request() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let event = model_event(&identity, "model.tool.request", 0, "Streaming", None);
    let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect_err("tool event must not enable tools for a disabled request");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(entry.next_sequence, 0);
    assert_eq!(entry.event_count, 0);
    assert!(
        error.message.contains("not permitted")
            || error.message.contains("not enabled")
            || error.message.contains("disabled"),
        "B2 RED: expected tools-disabled reason, got: {}",
        error.message
    );
}

#[test]
fn b2_unknown_method_remains_unsupported_after_b2() {
    assert!(!allowed_model_event_method("model.tool.unknown"));
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let event = model_event(&identity, "model.turn.unknown", 0, "Streaming", None);
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.unknown", 0)
        .expect_err("unknown method must be rejected");
    assert_eq!(error.code, "unsupported_method");
}

#[test]
fn b2_tool_methods_remain_registered_after_b2() {
    assert!(allowed_model_event_method("model.tool.request"));
    assert!(allowed_model_event_method("model.turn.tool_calls"));
    assert!(allowed_event_method("model.tool.request"));
    assert!(allowed_event_method("model.turn.tool_calls"));
}

#[test]
fn b2_enabled_request_records_valid_tool_request() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    assert!(entry.tools_are_enabled());
    let event = tool_event_with_name(&identity, "model.tool.request", "files.read");
    validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect("enabled valid tool request must be recorded");
    assert_eq!(entry.next_sequence, 1);
    assert_eq!(entry.event_count, 1);
    assert_eq!(
        entry.intermediate_tool_calls,
        event.metadata["tool_calls"].as_array().unwrap().clone()
    );
    assert!(!entry.terminal_seen);
}

#[test]
fn b2_request_entry_snapshots_empty_tool_context() {
    let identity = model_identity();
    let entry = ModelRequestEntry::new(identity, Vec::new());
    assert!(!entry.tools_are_enabled());
    assert!(entry.permitted_tool_names.is_empty());
}

#[test]
fn b2_request_entry_snapshots_enabled_tool_context() {
    let identity = model_identity();
    let entry = ModelRequestEntry::new(
        identity,
        vec!["files.read".to_string(), "files.list".to_string()],
    );
    assert!(entry.tools_are_enabled());
    assert_eq!(entry.permitted_tool_names, vec!["files.read", "files.list"]);
}

#[test]
fn b2_request_entry_owns_tool_snapshot() {
    let identity = model_identity();
    let mut tools = vec!["files.read".to_string()];
    let entry = ModelRequestEntry::new(identity, tools.clone());
    tools.clear();
    assert!(entry.tools_are_enabled());
    assert_eq!(entry.permitted_tool_names, vec!["files.read"]);
}

#[test]
fn b3f_registered_model_tools_is_closed_deterministic_and_bounded() {
    assert_eq!(REGISTERED_MODEL_TOOLS.len(), 11);
    assert_eq!(
        REGISTERED_MODEL_TOOLS,
        &[
            "files.read",
            "files.list",
            "files.write",
            "files.create_folder",
            "files.delete",
            "shell",
            "computer_use",
            "web.search",
            "web.fetch",
            "skills.invoke",
            "system.time",
        ]
    );
    let as_set: std::collections::HashSet<&&str> = REGISTERED_MODEL_TOOLS.iter().collect();
    assert_eq!(as_set.len(), 11, "no duplicates");
}

fn tool_event_with_name(
    identity: &ModelRequestIdentity,
    method: &str,
    tool_name: &str,
) -> UiControlPlaneEvent {
    structured_tool_event(
        identity,
        method,
        vec![(tool_name, valid_tool_arguments_json(tool_name))],
    )
}

fn valid_tool_arguments_json(tool_name: &str) -> &'static str {
    match tool_name {
        "files.write" => r#"{"path":"notes.txt","content":"hello"}"#,
        "files.read" | "files.list" | "files.create_folder" | "files.delete" => {
            r#"{"path":"notes.txt"}"#
        }
        _ => "{}",
    }
}

#[test]
fn b3m_disabled_request_rejects_tool_event() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let event = tool_event_with_name(&identity, "model.tool.request", "files.read");
    let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect_err("disabled request must reject");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(entry.next_sequence, 0);
    assert_eq!(entry.event_count, 0);
}

#[test]
fn b3m_permitted_tool_request_is_recorded() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let event = tool_event_with_name(&identity, "model.tool.request", "files.read");
    validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect("permitted tool request must be recorded");
    assert_eq!(entry.next_sequence, 1);
    assert_eq!(entry.event_count, 1);
    assert_eq!(
        entry.intermediate_tool_calls,
        event.metadata["tool_calls"].as_array().unwrap().clone()
    );
}

#[test]
fn b3m_registered_but_not_permitted_tool_is_rejected() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let event = tool_event_with_name(&identity, "model.tool.request", "files.delete");
    let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect_err("non-permitted tool must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(
        error.message.contains("not permitted for this request"),
        "B3M RED: expected membership rejection, got: {}",
        error.message
    );
    assert_eq!(entry.next_sequence, 0);
    assert_eq!(entry.event_count, 0);
}

#[test]
fn b3m_unknown_tool_is_rejected_by_membership() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let event = tool_event_with_name(&identity, "model.tool.request", "unknown.tool");
    let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect_err("unknown tool must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(
        error.message.contains("not permitted for this request"),
        "B3M RED: expected membership rejection, got: {}",
        error.message
    );
    assert_eq!(entry.next_sequence, 0);
}

#[test]
fn b3m_case_confusion_rejected() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let event = tool_event_with_name(&identity, "model.tool.request", "FILES.READ");
    let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect_err("case-confused name must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(
        error.message.contains("not permitted for this request"),
        "B3M RED: expected exact-match rejection, got: {}",
        error.message
    );
}

#[test]
fn b3m_whitespace_and_prefix_confusion_rejected() {
    let identity = model_identity();
    for name in [
        " files.read",
        "files.read ",
        "files.read.extra",
        "evil.files.read",
    ] {
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = tool_event_with_name(&identity, "model.tool.request", name);
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err(&format!("{name:?} must be rejected"));
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("not permitted for this request"),
            "B3M RED: {name:?} expected membership rejection, got: {}",
            error.message
        );
    }
}
#[test]
fn b3m_terminal_batch_all_permitted_is_recorded() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(
        identity.clone(),
        vec!["files.read".to_string(), "files.list".to_string()],
    );
    let event = structured_tool_event(
        &identity,
        "model.turn.tool_calls",
        vec![
            ("files.read", valid_tool_arguments_json("files.read")),
            ("files.list", valid_tool_arguments_json("files.list")),
        ],
    );
    let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
    for (sequence, call) in calls.iter().enumerate() {
        let mut request = raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
        request.sequence = sequence as u64;
        request.metadata["tools_executed"] = json!(sequence + 1);
        validate_and_record_model_event(
            &mut entry,
            &request,
            "model.tool.request",
            sequence as u64,
        )
        .expect("matching intermediate request must be recorded");
    }
    let mut terminal = event;
    terminal.sequence = calls.len() as u64;
    validate_and_record_model_event(
        &mut entry,
        &terminal,
        "model.turn.tool_calls",
        calls.len() as u64,
    )
    .expect("matching terminal must be recorded");
    assert!(entry.terminal_seen);
    assert_eq!(entry.next_sequence, (calls.len() + 1) as u64);
    assert_eq!(entry.event_count, calls.len() + 1);
    assert_eq!(entry.intermediate_tool_calls, calls);
}

#[test]
fn b3m_terminal_batch_with_forbidden_name_rejected_atomically() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(
        identity.clone(),
        vec!["files.read".to_string(), "files.list".to_string()],
    );
    let event = structured_tool_event(
        &identity,
        "model.turn.tool_calls",
        vec![
            ("files.read", valid_tool_arguments_json("files.read")),
            ("files.delete", valid_tool_arguments_json("files.delete")),
        ],
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("batch with forbidden name must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(
        error.message.contains("not permitted for this request"),
        "B3M RED: expected atomic membership rejection, got: {}",
        error.message
    );
    assert!(!entry.terminal_seen, "terminal must not be accepted");
    assert_eq!(entry.next_sequence, 0);
    assert_eq!(entry.event_count, 0);
}

#[test]
fn b3m_terminal_batch_with_unknown_name_rejected_atomically() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let event = structured_tool_event(
        &identity,
        "model.turn.tool_calls",
        vec![
            ("files.read", valid_tool_arguments_json("files.read")),
            ("unknown.tool", "{}"),
        ],
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("batch with unknown name must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(
        error.message.contains("not permitted for this request"),
        "B3M RED: expected atomic rejection, got: {}",
        error.message
    );
    assert!(!entry.terminal_seen);
}

#[test]
fn b3m_adjacent_request_isolation() {
    let identity_a = model_identity();
    let identity_b = ModelRequestIdentity {
        request_id: "fedcba9876543210fedcba98".into(),
        chat_session_id: "chat_session_2".into(),
        model_id: "qwen3-1.7b-instruct-q4-k-m".into(),
        submitted_at_unix_ms: 1_750_000_000_001,
        max_tokens: 128,
        seed: DEFAULT_MODEL_SEED,
        binding_fingerprint: "b".repeat(64),
    };
    let entry_a = ModelRequestEntry::new(
        identity_a.clone(),
        vec!["files.read".to_string(), "files.list".to_string()],
    );
    let mut entry_b = ModelRequestEntry::new(identity_b.clone(), vec!["files.read".to_string()]);
    let event_b = tool_event_with_name(&identity_b, "model.tool.request", "files.list");
    let error = validate_and_record_model_event(&mut entry_b, &event_b, "model.tool.request", 0)
        .expect_err("files.list not permitted for B");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(
        error.message.contains("not permitted for this request"),
        "B3M RED: B must reject files.list, got: {}",
        error.message
    );
    assert_eq!(entry_a.next_sequence, 0, "A state unchanged");
    assert_eq!(entry_b.next_sequence, 0, "B state unchanged");
}

fn structured_tool_event(
    identity: &ModelRequestIdentity,
    method: &str,
    calls: Vec<(&str, &str)>,
) -> UiControlPlaneEvent {
    let state = if method == "model.turn.tool_calls" {
        "ToolCalls"
    } else {
        "Streaming"
    };
    let mut event = model_event(identity, method, 0, state, None);
    let tool_calls: Vec<serde_json::Value> = calls
        .iter()
        .enumerate()
        .map(|(i, (name, args))| {
            json!({
                "id": format!("call_{:03}", i + 1),
                "name": name,
                "arguments": serde_json::from_str::<serde_json::Value>(args)
                    .expect("test fixture arguments must be valid JSON"),
            })
        })
        .collect();
    event.metadata["tool_calls"] = json!(tool_calls);
    event.metadata["tools_executed"] =
        json!(event.metadata["tool_calls"].as_array().map_or(0, Vec::len));
    event
}
#[test]
fn b4c_text_only_tool_event_rejected() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let event = model_event(
        &identity,
        "model.tool.request",
        0,
        "Streaming",
        Some("files.read"),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect_err("text-only tool event must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(
        error.message.contains("invalid tool event transition"),
        "text-bearing tool event must be rejected before metadata parsing, got: {}",
        error.message
    );
}

#[test]
fn b4c_structured_single_call_is_recorded() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let event = structured_tool_event(
        &identity,
        "model.tool.request",
        vec![("files.read", "{\"path\":\"a.txt\"}")],
    );
    validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect("structured tool request must be admitted and recorded");
    assert_eq!(entry.next_sequence, 1);
    assert_eq!(entry.event_count, 1);
    assert_eq!(
        entry.intermediate_tool_calls,
        event.metadata["tool_calls"].as_array().unwrap().clone()
    );
}

#[test]
fn b4c_structured_terminal_batch_admitted_past_metadata() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(
        identity.clone(),
        vec!["files.read".to_string(), "files.list".to_string()],
    );
    let event = structured_tool_event(
        &identity,
        "model.turn.tool_calls",
        vec![
            ("files.read", "{\"path\":\"a.txt\"}"),
            ("files.list", "{\"path\":\".\"}"),
        ],
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("must be rejected");
    assert!(
        !error.message.contains("metadata shape mismatch"),
        "B4C RED: structured batch should be admitted, got: {}",
        error.message
    );
}

#[test]
fn b4c_structured_name_is_membership_authority_over_text() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let mut event = structured_tool_event(
        &identity,
        "model.tool.request",
        vec![("files.delete", "{\"path\":\"x\"}")],
    );
    event.text = Some("files.read".to_string());
    let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect_err("must be rejected");
    assert!(
        !error.message.contains("metadata shape mismatch"),
        "B4C RED: structured event should pass metadata, got: {}",
        error.message
    );
}

#[test]
fn b4c_non_tool_event_cannot_carry_tool_calls() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
    validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap();
    let mut delta = model_event(&identity, "model.output.delta", 1, "Streaming", Some("hi"));
    delta.metadata["tool_calls"] = json!([{"id":"call_001","name":"files.read","arguments":{}}]);
    let error = validate_and_record_model_event(&mut entry, &delta, "model.output.delta", 1)
        .expect_err("content event with tool_calls must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(error.message.contains("metadata shape mismatch"));
}

#[test]
fn b4c_structured_batch_forbidden_name_atomic() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(
        identity.clone(),
        vec!["files.read".to_string(), "files.list".to_string()],
    );
    let event = structured_tool_event(
        &identity,
        "model.turn.tool_calls",
        vec![
            ("files.read", "{\"path\":\"a.txt\"}"),
            ("files.delete", "{\"path\":\"x\"}"),
        ],
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("must be rejected");
    assert!(
        !error.message.contains("metadata shape mismatch"),
        "B4C RED: structured batch should pass metadata, got: {}",
        error.message
    );
    assert!(!entry.terminal_seen);
    assert_eq!(entry.next_sequence, 0);
}

fn raw_tool_event(
    identity: &ModelRequestIdentity,
    method: &str,
    tool_calls: serde_json::Value,
) -> UiControlPlaneEvent {
    let state = if method == "model.turn.tool_calls" {
        "ToolCalls"
    } else {
        "Streaming"
    };
    let mut event = model_event(identity, method, 0, state, None);
    event.metadata["tool_calls"] = tool_calls;
    event.metadata["tools_executed"] = if method == "model.tool.request" {
        json!(1)
    } else {
        json!(event.metadata["tool_calls"].as_array().map_or(0, Vec::len))
    };
    event
}

#[test]
fn b4a_valid_single_id_is_recorded() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let event = raw_tool_event(
        &identity,
        "model.tool.request",
        json!([{"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}}]),
    );
    validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect("valid single id must be recorded");
    assert_eq!(entry.next_sequence, 1);
    assert_eq!(entry.event_count, 1);
    assert_eq!(
        entry.intermediate_tool_calls,
        event.metadata["tool_calls"].as_array().unwrap().clone()
    );
}

#[test]
fn b4a_missing_id_rejected() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let event = raw_tool_event(
        &identity,
        "model.tool.request",
        json!([{"name":"files.read","arguments":"{\"path\":\"a.txt\"}"}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect_err("missing id must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(
        error.message.contains("tool call id"),
        "B4A RED: expected id-required error, got: {}",
        error.message
    );
    assert_eq!(entry.next_sequence, 0);
}

#[test]
fn b4a_null_id_rejected() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let event = raw_tool_event(
        &identity,
        "model.tool.request",
        json!([{"id":null,"name":"files.read","arguments":{}}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect_err("null id must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(
        error.message.contains("tool call id"),
        "B4A RED: expected id-type error, got: {}",
        error.message
    );
}

#[test]
fn b4a_numeric_id_rejected() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let event = raw_tool_event(
        &identity,
        "model.tool.request",
        json!([{"id":123,"name":"files.read","arguments":{}}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect_err("numeric id must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(
        error.message.contains("tool call id"),
        "B4A RED: expected id-type error, got: {}",
        error.message
    );
}

#[test]
fn b4a_empty_id_rejected() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let event = raw_tool_event(
        &identity,
        "model.tool.request",
        json!([{"id":"","name":"files.read","arguments":{}}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect_err("empty id must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(
        error.message.contains("tool call id"),
        "B4A RED: expected id-required error, got: {}",
        error.message
    );
}

#[test]
fn b4a_whitespace_id_rejected() {
    let identity = model_identity();
    for ws in [" ", "\t", "\n"] {
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = raw_tool_event(
            &identity,
            "model.tool.request",
            json!([{"id":ws,"name":"files.read","arguments":{}}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err(&format!("whitespace id {ws:?} must be rejected"));
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("tool call id"),
            "B4A RED: expected id-required error for {ws:?}, got: {}",
            error.message
        );
    }
}

#[test]
fn b4a_distinct_terminal_ids_are_recorded() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(
        identity.clone(),
        vec!["files.read".to_string(), "files.list".to_string()],
    );
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([
            {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
            {"id":"call_002","name":"files.list","arguments":{"path":"."}}
        ]),
    );
    let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
    for (sequence, call) in calls.iter().enumerate() {
        let mut request = raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
        request.sequence = sequence as u64;
        request.metadata["tools_executed"] = json!(sequence + 1);
        validate_and_record_model_event(
            &mut entry,
            &request,
            "model.tool.request",
            sequence as u64,
        )
        .expect("matching intermediate request must be recorded");
    }
    let mut terminal = event;
    terminal.sequence = calls.len() as u64;
    validate_and_record_model_event(
        &mut entry,
        &terminal,
        "model.turn.tool_calls",
        calls.len() as u64,
    )
    .expect("matching terminal must be recorded");
    assert!(entry.terminal_seen);
    assert_eq!(entry.next_sequence, (calls.len() + 1) as u64);
    assert_eq!(entry.event_count, calls.len() + 1);
    assert_eq!(entry.intermediate_tool_calls, calls);
}

#[test]
fn b4a_duplicate_terminal_id_rejected() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(
        identity.clone(),
        vec!["files.read".to_string(), "files.list".to_string()],
    );
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([
            {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
            {"id":"call_001","name":"files.list","arguments":{"path":"."}}
        ]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("duplicate id must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(
        error.message.contains("duplicate tool call id"),
        "B4A RED: expected duplicate-id error, got: {}",
        error.message
    );
    assert!(!entry.terminal_seen);
    assert_eq!(entry.next_sequence, 0);
}

#[test]
fn b4a_duplicate_id_same_tool_rejected() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([
            {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
            {"id":"call_001","name":"files.read","arguments":{"path":"b.txt"}}
        ]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("duplicate id same tool must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(
        error.message.contains("duplicate tool call id"),
        "B4A RED: expected duplicate-id error, got: {}",
        error.message
    );
}

#[test]
fn b4a_adjacent_request_id_scope_is_independent() {
    let identity_a = model_identity();
    let identity_b = ModelRequestIdentity {
        request_id: "fedcba9876543210fedcba98".into(),
        chat_session_id: "chat_session_2".into(),
        model_id: "qwen3-1.7b-instruct-q4-k-m".into(),
        submitted_at_unix_ms: 1_750_000_000_001,
        max_tokens: 128,
        seed: DEFAULT_MODEL_SEED,
        binding_fingerprint: "b".repeat(64),
    };
    let mut entry_a = ModelRequestEntry::new(identity_a.clone(), vec!["files.read".to_string()]);
    let mut entry_b = ModelRequestEntry::new(identity_b.clone(), vec!["files.read".to_string()]);
    let event_a = raw_tool_event(
        &identity_a,
        "model.tool.request",
        json!([{"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}}]),
    );
    let event_b = raw_tool_event(
        &identity_b,
        "model.tool.request",
        json!([{"id":"call_001","name":"files.read","arguments":{"path":"b.txt"}}]),
    );
    validate_and_record_model_event(&mut entry_a, &event_a, "model.tool.request", 0)
        .expect("request A must record its id");
    validate_and_record_model_event(&mut entry_b, &event_b, "model.tool.request", 0)
        .expect("request B must independently record the same id");
    assert_eq!(
        entry_a.intermediate_tool_calls,
        event_a.metadata["tool_calls"].as_array().unwrap().clone()
    );
    assert_eq!(
        entry_b.intermediate_tool_calls,
        event_b.metadata["tool_calls"].as_array().unwrap().clone()
    );
    assert_eq!(entry_a.next_sequence, 1);
    assert_eq!(entry_b.next_sequence, 1);
}

fn b5_entry(identity: &ModelRequestIdentity) -> ModelRequestEntry {
    ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()])
}

#[test]
fn b5_valid_path_object_is_recorded() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}}]),
    );
    let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
    for (sequence, call) in calls.iter().enumerate() {
        let mut request = raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
        request.sequence = sequence as u64;
        request.metadata["tools_executed"] = json!(sequence + 1);
        validate_and_record_model_event(
            &mut entry,
            &request,
            "model.tool.request",
            sequence as u64,
        )
        .expect("matching intermediate request must be recorded");
    }
    let mut terminal = event;
    terminal.sequence = calls.len() as u64;
    validate_and_record_model_event(
        &mut entry,
        &terminal,
        "model.turn.tool_calls",
        calls.len() as u64,
    )
    .expect("matching terminal must be recorded");
    assert!(entry.terminal_seen);
    assert_eq!(entry.next_sequence, (calls.len() + 1) as u64);
    assert_eq!(entry.event_count, calls.len() + 1);
    assert_eq!(entry.intermediate_tool_calls, calls);
}

#[test]
fn b5_valid_batch_is_recorded() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([
            {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
            {"id":"call_002","name":"files.read","arguments":{"path":"b.txt"}}
        ]),
    );
    let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
    for (sequence, call) in calls.iter().enumerate() {
        let mut request = raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
        request.sequence = sequence as u64;
        request.metadata["tools_executed"] = json!(sequence + 1);
        validate_and_record_model_event(
            &mut entry,
            &request,
            "model.tool.request",
            sequence as u64,
        )
        .expect("matching intermediate request must be recorded");
    }
    let mut terminal = event;
    terminal.sequence = calls.len() as u64;
    validate_and_record_model_event(
        &mut entry,
        &terminal,
        "model.turn.tool_calls",
        calls.len() as u64,
    )
    .expect("matching terminal must be recorded");
    assert!(entry.terminal_seen);
    assert_eq!(entry.next_sequence, (calls.len() + 1) as u64);
    assert_eq!(entry.event_count, calls.len() + 1);
    assert_eq!(entry.intermediate_tool_calls, calls);
}

#[test]
fn b5_missing_arguments_required() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read"}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("missing arguments must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments are required");
}

#[test]
fn b5_null_arguments_must_be_object() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments":null}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("null arguments must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments must be an object");
}

#[test]
fn b5_string_scalar_arguments_must_be_object() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments":"hello"}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("string scalar arguments must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments must be an object");
}

#[test]
fn b5_stringified_object_arguments_must_be_object() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments":"{\"path\":\"a.txt\"}"}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("stringified object arguments must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments must be an object");
}

#[test]
fn b5_empty_string_arguments_must_be_object() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments":""}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("empty string arguments must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments must be an object");
}

#[test]
fn b5_whitespace_string_arguments_must_be_object() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments":"   "}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("whitespace string arguments must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments must be an object");
}

#[test]
fn b5_array_arguments_must_be_object() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments":[1,2]}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("array arguments must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments must be an object");
}

#[test]
fn b5_number_arguments_must_be_object() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments":5}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("number arguments must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments must be an object");
}

#[test]
fn b5_boolean_arguments_must_be_object() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments":true}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("boolean arguments must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments must be an object");
}

#[test]
fn b5_missing_arguments_leaves_entry_unchanged() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read"}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("missing arguments must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments are required");
    assert_eq!(entry.next_sequence, 0);
    assert!(!entry.terminal_seen);
    assert_eq!(entry.event_count, 0);
}

#[test]
fn b5_unknown_tool_precedes_arguments() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.unknown","arguments":{}}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("unknown tool must be rejected before arguments");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool is not permitted for this request");
}

#[test]
fn b5_missing_id_precedes_arguments() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"name":"files.read","arguments":{}}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("missing id must be rejected before arguments");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call id is required");
}

#[test]
fn b5_duplicate_id_precedes_arguments() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([
            {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
            {"id":"call_001","name":"files.read","arguments":{"path":"b.txt"}}
        ]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("duplicate id must be rejected before arguments");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "duplicate tool call id");
}

#[test]
fn b5_adjacent_requests_independent() {
    let identity_a = model_identity();
    let identity_b = ModelRequestIdentity {
        request_id: "fedcba9876543210fedcba98".into(),
        chat_session_id: "chat_session_2".into(),
        model_id: "qwen3-1.7b-instruct-q4-k-m".into(),
        submitted_at_unix_ms: 1_750_000_000_001,
        max_tokens: 128,
        seed: DEFAULT_MODEL_SEED,
        binding_fingerprint: "b".repeat(64),
    };
    let mut entry_a = b5_entry(&identity_a);
    let mut entry_b = b5_entry(&identity_b);
    let event_a = raw_tool_event(
        &identity_a,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}}]),
    );
    let event_b = raw_tool_event(
        &identity_b,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments":{"path":"b.txt"}}]),
    );
    for (entry, event) in [(&mut entry_a, event_a), (&mut entry_b, event_b)] {
        let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
        let request = raw_tool_event(
            &entry.identity,
            "model.tool.request",
            json!([calls[0].clone()]),
        );
        validate_and_record_model_event(entry, &request, "model.tool.request", 0)
            .expect("adjacent request prefix must be recorded independently");
        let mut terminal = event;
        terminal.sequence = 1;
        validate_and_record_model_event(entry, &terminal, "model.turn.tool_calls", 1)
            .expect("adjacent terminal must match only its own prefix");
        assert!(entry.terminal_seen);
        assert_eq!(entry.next_sequence, 2);
        assert_eq!(entry.intermediate_tool_calls, calls);
    }
}

#[test]
fn b5_batch_second_call_invalid_arguments_atomic() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([
            {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
            {"id":"call_002","name":"files.read","arguments":"{\"path\":\"b.txt\"}"}
        ]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("invalid second call must be rejected atomically");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments must be an object");
    assert_eq!(entry.next_sequence, 0);
    assert!(!entry.terminal_seen);
    assert_eq!(entry.event_count, 0);
}

// ---- B5L resource-limit test helpers (test-only; deterministic counters) ----

fn count_bytes(v: &Value) -> usize {
    serde_json::to_string(v).unwrap().len()
}

fn count_depth(v: &Value) -> usize {
    match v {
        Value::Object(map) => 1 + map.values().map(count_depth).max().unwrap_or(0),
        Value::Array(items) => 1 + items.iter().map(count_depth).max().unwrap_or(0),
        _ => 0,
    }
}

fn count_keys(v: &Value) -> usize {
    match v {
        Value::Object(map) => map.len() + map.values().map(count_keys).sum::<usize>(),
        Value::Array(items) => items.iter().map(count_keys).sum::<usize>(),
        _ => 0,
    }
}

fn count_nodes(v: &Value) -> usize {
    match v {
        Value::Object(map) => 1 + map.values().map(count_nodes).sum::<usize>(),
        Value::Array(items) => 1 + items.iter().map(count_nodes).sum::<usize>(),
        _ => 1,
    }
}

fn args_with_bytes(target: usize) -> Value {
    assert!(target >= 8, "target must cover the object overhead");
    let value = json!({ "p": "A".repeat(target - 8) });
    assert_eq!(
        count_bytes(&value),
        target,
        "args_with_bytes must hit exact byte target"
    );
    value
}

fn args_with_depth(depth: usize) -> Value {
    assert!(depth >= 1, "depth must be at least the root object");
    let mut value = json!({});
    for _ in 1..depth {
        value = json!({ "a": value });
    }
    assert_eq!(
        count_depth(&value),
        depth,
        "args_with_depth must hit exact depth target"
    );
    value
}

fn args_with_keys(keys: usize) -> Value {
    let mut map = serde_json::Map::new();
    for index in 0..keys {
        map.insert(format!("k{index}"), json!(1));
    }
    let value = Value::Object(map);
    assert_eq!(
        count_keys(&value),
        keys,
        "args_with_keys must hit exact key target"
    );
    value
}

fn args_with_nodes(nodes: usize) -> Value {
    assert!(nodes >= 2, "nodes must cover root object and array");
    let elements = nodes - 2;
    let value = json!({ "arr": vec![json!(1); elements] });
    assert_eq!(
        count_nodes(&value),
        nodes,
        "args_with_nodes must hit exact node target"
    );
    value
}

fn args_with_unicode_bytes(target: usize) -> Value {
    assert!(target >= 8, "target must cover the object overhead");
    let body = target - 8;
    let mut text = "é".repeat(body / 2);
    if body % 2 == 1 {
        text.push('A');
    }
    let value = json!({ "p": text });
    assert_eq!(
        count_bytes(&value),
        target,
        "args_with_unicode_bytes must hit exact byte target"
    );
    value
}

fn args_depth_and_keys_violation() -> Value {
    let mut inner = json!({});
    for level in 0..32 {
        let mut map = serde_json::Map::new();
        for k in 0..16 {
            map.insert(format!("k{level}_{k}"), json!(1));
        }
        map.insert("n".to_string(), inner);
        inner = Value::Object(map);
    }
    assert!(count_depth(&inner) > 32, "must exceed depth limit");
    assert!(count_keys(&inner) > 512, "must exceed key limit");
    assert!(count_bytes(&inner) <= 65_536, "must not exceed byte limit");
    assert!(count_nodes(&inner) <= 4_096, "must not exceed node limit");
    inner
}

// ---- B5L RED tests ----

#[test]
fn b5l_exact_byte_limit_reaches_schema_validation() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let arguments = args_with_bytes(65_536);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
    );
    let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
    for (sequence, call) in calls.iter().enumerate() {
        let mut request = raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
        request.sequence = sequence as u64;
        request.metadata["tools_executed"] = json!(sequence + 1);
        validate_and_record_model_event(
            &mut entry,
            &request,
            "model.tool.request",
            sequence as u64,
        )
        .expect_err("exact resource limit must pass bounds and reach schema validation");
    }
    assert_eq!(entry.next_sequence, 0);
    assert_eq!(entry.event_count, 0);
    assert!(!entry.terminal_seen);
}

#[test]
fn b5l_exact_depth_limit_reaches_schema_validation() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let arguments = args_with_depth(32);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
    );
    let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
    for (sequence, call) in calls.iter().enumerate() {
        let mut request = raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
        request.sequence = sequence as u64;
        request.metadata["tools_executed"] = json!(sequence + 1);
        validate_and_record_model_event(
            &mut entry,
            &request,
            "model.tool.request",
            sequence as u64,
        )
        .expect_err("exact resource limit must pass bounds and reach schema validation");
    }
    assert_eq!(entry.next_sequence, 0);
    assert_eq!(entry.event_count, 0);
    assert!(!entry.terminal_seen);
}

#[test]
fn b5l_exact_key_limit_reaches_schema_validation() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let arguments = args_with_keys(512);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
    );
    let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
    for (sequence, call) in calls.iter().enumerate() {
        let mut request = raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
        request.sequence = sequence as u64;
        request.metadata["tools_executed"] = json!(sequence + 1);
        validate_and_record_model_event(
            &mut entry,
            &request,
            "model.tool.request",
            sequence as u64,
        )
        .expect_err("exact resource limit must pass bounds and reach schema validation");
    }
    assert_eq!(entry.next_sequence, 0);
    assert_eq!(entry.event_count, 0);
    assert!(!entry.terminal_seen);
}

#[test]
fn b5l_exact_node_limit_reaches_schema_validation() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let arguments = args_with_nodes(4_096);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
    );
    let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
    for (sequence, call) in calls.iter().enumerate() {
        let mut request = raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
        request.sequence = sequence as u64;
        request.metadata["tools_executed"] = json!(sequence + 1);
        validate_and_record_model_event(
            &mut entry,
            &request,
            "model.tool.request",
            sequence as u64,
        )
        .expect_err("exact resource limit must pass bounds and reach schema validation");
    }
    assert_eq!(entry.next_sequence, 0);
    assert_eq!(entry.event_count, 0);
    assert!(!entry.terminal_seen);
}

#[test]
fn b5l_unicode_within_byte_limit_reaches_schema_validation() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let arguments = args_with_unicode_bytes(65_536);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
    );
    let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
    for (sequence, call) in calls.iter().enumerate() {
        let mut request = raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
        request.sequence = sequence as u64;
        request.metadata["tools_executed"] = json!(sequence + 1);
        validate_and_record_model_event(
            &mut entry,
            &request,
            "model.tool.request",
            sequence as u64,
        )
        .expect_err("exact resource limit must pass bounds and reach schema validation");
    }
    assert_eq!(entry.next_sequence, 0);
    assert_eq!(entry.event_count, 0);
    assert!(!entry.terminal_seen);
}

#[test]
fn b5l_byte_limit_plus_one_rejected() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let arguments = args_with_bytes(65_537);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("byte limit + 1 must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments exceed maximum size");
}

#[test]
fn b5l_depth_limit_plus_one_rejected() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let arguments = args_with_depth(33);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("depth limit + 1 must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(
        error.message,
        "tool call arguments exceed maximum nesting depth"
    );
}

#[test]
fn b5l_key_limit_plus_one_rejected() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let arguments = args_with_keys(513);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("key limit + 1 must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(
        error.message,
        "tool call arguments exceed maximum object key count"
    );
}

#[test]
fn b5l_node_limit_plus_one_rejected() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let arguments = args_with_nodes(4_097);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("node limit + 1 must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(
        error.message,
        "tool call arguments exceed maximum node count"
    );
}

#[test]
fn b5l_unicode_byte_limit_plus_one_rejected() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let arguments = args_with_unicode_bytes(65_537);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("unicode byte limit + 1 must be rejected");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments exceed maximum size");
}

#[test]
fn b5l_multiple_violations_follow_fixed_precedence() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let arguments = args_depth_and_keys_violation();
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("multiple violations must follow fixed precedence");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(
        error.message,
        "tool call arguments exceed maximum nesting depth"
    );
}

#[test]
fn b5l_invalid_second_call_rejects_batch_atomically() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let oversized = args_with_bytes(65_537);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([
            {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
            {"id":"call_002","name":"files.read","arguments": oversized}
        ]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("invalid second call must be rejected atomically");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments exceed maximum size");
    assert_eq!(entry.next_sequence, 0);
    assert!(!entry.terminal_seen);
    assert_eq!(entry.event_count, 0);
    assert!(!entry.started_seen);
    assert_eq!(entry.generated_bytes, 0);
    assert!(entry.provider_id.is_none());
    assert!(entry.harness_id.is_none());
}

#[test]
fn b5l_failure_does_not_mutate_entry() {
    let identity = model_identity();
    let mut entry = b5_entry(&identity);
    let arguments = args_with_bytes(65_537);
    let event = raw_tool_event(
        &identity,
        "model.turn.tool_calls",
        json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("failure must not mutate entry");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(error.message, "tool call arguments exceed maximum size");
    assert_eq!(entry.next_sequence, 0);
    assert!(!entry.terminal_seen);
    assert_eq!(entry.event_count, 0);
    assert!(!entry.started_seen);
    assert_eq!(entry.generated_bytes, 0);
    assert!(entry.provider_id.is_none());
    assert!(entry.harness_id.is_none());
}

#[test]
fn adr015_phase_c_shared_tool_event_contract_is_accepted_only_when_tools_are_enabled() {
    let corpus: Value = serde_json::from_str(include_str!(
        "../../../../security/contracts/adr015_tool_event_parity_v1.json"
    ))
    .expect("Phase C parity corpus must be valid JSON");
    let identity_value = corpus["identity"]
        .as_object()
        .expect("Phase C identity must be an object");
    let identity = ModelRequestIdentity {
        request_id: identity_value["requestId"]
            .as_str()
            .expect("requestId must be a string")
            .into(),
        chat_session_id: identity_value["chatSessionId"]
            .as_str()
            .expect("chatSessionId must be a string")
            .into(),
        model_id: identity_value["modelId"]
            .as_str()
            .expect("modelId must be a string")
            .into(),
        submitted_at_unix_ms: identity_value["submittedAtUnixMs"]
            .as_u64()
            .expect("submittedAtUnixMs must be an unsigned integer"),
        max_tokens: identity_value["maxTokens"]
            .as_u64()
            .expect("maxTokens must be an unsigned integer") as u16,
        seed: identity_value["seed"]
            .as_u64()
            .expect("seed must be an unsigned integer") as u32,
        binding_fingerprint: identity_value["bindingFingerprint"]
            .as_str()
            .expect("bindingFingerprint must be a string")
            .into(),
    };
    let enabled = corpus["enabled"]
        .as_object()
        .expect("enabled contract must be an object");
    let permitted_tools = enabled["permittedTools"]
        .as_array()
        .expect("permittedTools must be an array")
        .iter()
        .map(|tool| tool.as_str().expect("tool must be a string").to_owned())
        .collect();
    let mut entry = ModelRequestEntry::new(identity.clone(), permitted_tools);
    let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
    validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0)
        .expect("tool-event contract requires an accepted started event");
    for case in enabled["events"]
        .as_array()
        .expect("enabled events must be an array")
    {
        let method = case["method"].as_str().expect("method must be a string");
        let sequence = case["sequence"]
            .as_u64()
            .expect("sequence must be an integer");
        let mut event = raw_tool_event(&identity, method, case["toolCalls"].clone());
        event.sequence = sequence;
        event.state = case["state"]
            .as_str()
            .expect("state must be a string")
            .to_owned();
        event.metadata["tools_executed"] = case["toolsExecuted"].clone();
        // The Python gateway emits a started event first, then a pure tool-call stream.
        event.metadata["model_called"] = json!(true);
        event.metadata["generated_bytes"] = json!(0);
        validate_and_record_model_event(&mut entry, &event, method, sequence)
            .expect("Python-emitted Phase C contract event must pass Rust validation");
    }
    assert!(entry.terminal_seen);
    assert_eq!(entry.intermediate_tool_calls.len(), 2);

    let disabled = corpus["disabled"]
        .as_object()
        .expect("disabled contract must be an object");
    let method = disabled["method"]
        .as_str()
        .expect("method must be a string");
    let sequence = disabled["sequence"]
        .as_u64()
        .expect("sequence must be an integer");
    let mut disabled_entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
    validate_and_record_model_event(&mut disabled_entry, &started, "model.turn.started", 0)
        .expect("disabled contract still requires a valid started event");
    let mut event = raw_tool_event(&identity, method, disabled["toolCalls"].clone());
    event.sequence = sequence;
    event.state = disabled["state"]
        .as_str()
        .expect("state must be a string")
        .to_owned();
    event.metadata["tools_executed"] = disabled["toolsExecuted"].clone();
    event.metadata["model_called"] = json!(true);
    event.metadata["generated_bytes"] = json!(0);
    let error = validate_and_record_model_event(&mut disabled_entry, &event, method, sequence)
        .expect_err("tools=[] must reject the shared tool event contract");
    assert_eq!(error.code, "protocol_mismatch");
    assert_eq!(disabled_entry.next_sequence, 1);
    assert!(disabled_entry.intermediate_tool_calls.is_empty());
}

// ---- B6 cross-event provenance RED helpers and tests ----

#[derive(Debug, PartialEq)]
struct B6EntrySnapshot {
    identity: ModelRequestIdentity,
    provider_id: Option<String>,
    harness_id: Option<String>,
    knowledge_model: bool,
    knowledge_acceptance_seen: bool,
    knowledge_injection_id: Option<String>,
    knowledge_included: bool,
    accepted: bool,
    cancel_pending: bool,
    cancel_accepted: bool,
    cancel_requested_before_acceptance: bool,
    cancel_after_synthetic_release: bool,
    releasing_events: bool,
    remove_after_release: bool,
    started_seen: bool,
    terminal_seen: bool,
    next_sequence: u64,
    event_count: usize,
    event_text: usize,
    model_called: bool,
    generated_bytes: u64,
    buffered_events: Vec<String>,
    tools_enabled: bool,
    permitted_tool_names: Vec<String>,
    intermediate_tool_calls: Vec<Value>,
}

fn b6_snapshot(entry: &ModelRequestEntry) -> B6EntrySnapshot {
    B6EntrySnapshot {
        identity: entry.identity.clone(),
        provider_id: entry.provider_id.clone(),
        harness_id: entry.harness_id.clone(),
        knowledge_model: entry.knowledge_model,
        knowledge_acceptance_seen: entry.knowledge_acceptance_seen,
        knowledge_injection_id: entry.knowledge_injection_id.clone(),
        knowledge_included: entry.knowledge_included,
        accepted: entry.accepted,
        cancel_pending: entry.cancel_pending,
        cancel_accepted: entry.cancel_accepted,
        cancel_requested_before_acceptance: entry.cancel_requested_before_acceptance,
        cancel_after_synthetic_release: entry.cancel_after_synthetic_release,
        releasing_events: entry.releasing_events,
        remove_after_release: entry.remove_after_release,
        started_seen: entry.started_seen,
        terminal_seen: entry.terminal_seen,
        next_sequence: entry.next_sequence,
        event_count: entry.event_count,
        event_text: entry.event_text,
        model_called: entry.model_called,
        generated_bytes: entry.generated_bytes,
        buffered_events: entry
            .buffered_events
            .iter()
            .map(|event| serde_json::to_string(event).expect("buffered event must serialize"))
            .collect(),
        tools_enabled: entry.tools_enabled,
        permitted_tool_names: entry.permitted_tool_names.clone(),
        intermediate_tool_calls: entry.intermediate_tool_calls.clone(),
    }
}

fn b6_calls() -> Value {
    json!([
        {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
        {"id":"call_002","name":"files.list","arguments":{"path":"."}}
    ])
}

fn b6_tool_event(
    identity: &ModelRequestIdentity,
    method: &str,
    sequence: u64,
    tool_calls: Value,
) -> UiControlPlaneEvent {
    let mut event = raw_tool_event(identity, method, tool_calls);
    event.sequence = sequence;
    if method == "model.tool.request" {
        event.metadata["tools_executed"] = json!(sequence + 1);
    }
    event
}

fn b6_entry(identity: &ModelRequestIdentity) -> ModelRequestEntry {
    ModelRequestEntry::new(
        identity.clone(),
        vec!["files.read".to_string(), "files.list".to_string()],
    )
}

fn b6_submit_prefix(entry: &mut ModelRequestEntry, calls: &Value) {
    // Use the production validator; failing at its current placeholder is the earliest B6 RED,
    // because accepting and accumulating intermediate requests is itself missing B6 behavior.
    for (sequence, call) in calls
        .as_array()
        .expect("B6 fixture calls must be an array")
        .iter()
        .enumerate()
    {
        let event = b6_tool_event(
            &entry.identity,
            "model.tool.request",
            sequence as u64,
            json!([call.clone()]),
        );
        validate_and_record_model_event(entry, &event, "model.tool.request", sequence as u64)
            .expect("intermediate tool request must be accepted and accumulated");
    }
}

fn b6_assert_provenance_rejection(error: &BridgeError) {
    assert_eq!(error.code, "protocol_mismatch");
    // This seam receives serde_json::Value, so lexical and key-order wire-byte assertions are invalid.
    // Exact wording is intentionally not frozen by ADR-015.
    assert!(
        error.message.contains("tool call provenance mismatch"),
        "expected provenance mismatch, got: {}",
        error.message
    );
}

#[test]
fn b6_terminal_without_intermediate_request_is_rejected_atomically() {
    let identity = model_identity();
    let mut entry = b6_entry(&identity);
    let before = b6_snapshot(&entry);
    let event = b6_tool_event(&identity, "model.turn.tool_calls", 0, b6_calls());
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
        .expect_err("terminal without an intermediate request must be rejected");
    b6_assert_provenance_rejection(&error);
    assert_eq!(b6_snapshot(&entry), before);
}

#[test]
fn b6_exact_ordered_two_call_prefix_then_identical_terminal_is_recorded() {
    let identity = model_identity();
    let mut entry = b6_entry(&identity);
    let calls = b6_calls();
    b6_submit_prefix(&mut entry, &calls);
    let mut event = b6_tool_event(&identity, "model.turn.tool_calls", 2, calls);
    // A mixed OpenAI response keeps its accumulated assistant text on the
    // terminal tool batch so the frontend can preserve it in history.
    event.text = Some("explanation before tool execution".into());
    validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 2)
        .expect("matching mixed-content terminal must be accepted and recorded");
    assert!(entry.terminal_seen);
    assert_eq!(entry.next_sequence, 3);
    assert_eq!(entry.event_count, 3);
}

#[test]
fn b6_terminal_mismatch_cases_are_rejected_atomically() {
    let identity = model_identity();
    let prefix = b6_calls();
    let cases = [
        (
            "missing",
            json!([
                {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}}
            ]),
        ),
        (
            "extra",
            json!([
                {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
                {"id":"call_002","name":"files.list","arguments":{"path":"."}},
                {"id":"call_003","name":"files.read","arguments":{"path":"b.txt"}}
            ]),
        ),
        (
            "reordered",
            json!([
                {"id":"call_002","name":"files.list","arguments":{"path":"."}},
                {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}}
            ]),
        ),
        (
            "changed id",
            json!([
                {"id":"call_009","name":"files.read","arguments":{"path":"a.txt"}},
                {"id":"call_002","name":"files.list","arguments":{"path":"."}}
            ]),
        ),
        (
            "changed permitted name",
            json!([
                {"id":"call_001","name":"files.list","arguments":{"path":"a.txt"}},
                {"id":"call_002","name":"files.list","arguments":{"path":"."}}
            ]),
        ),
        (
            "changed argument value",
            json!([
                {"id":"call_001","name":"files.read","arguments":{"path":"b.txt"}},
                {"id":"call_002","name":"files.list","arguments":{"path":"."}}
            ]),
        ),
    ];

    for (label, terminal_calls) in cases {
        let mut entry = b6_entry(&identity);
        b6_submit_prefix(&mut entry, &prefix);
        let before = b6_snapshot(&entry);
        let event = b6_tool_event(&identity, "model.turn.tool_calls", 2, terminal_calls);
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 2)
            .expect_err(&format!("{label} mismatch must be rejected"));
        b6_assert_provenance_rejection(&error);
        assert_eq!(b6_snapshot(&entry), before, "{label} mutated entry");
    }
}

#[test]
fn b6_object_key_order_is_insignificant_after_parsing() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.write".to_string()]);
    let prefix = json!([{
        "id":"call_001",
        "name":"files.write",
        "arguments":{"path":"a.txt","content":"hello"}
    }]);
    b6_submit_prefix(&mut entry, &prefix);
    let terminal: Value = serde_json::from_str(
        r#"[{"arguments":{"content":"hello","path":"a.txt"},"name":"files.write","id":"call_001"}]"#,
    )
    .expect("reordered object fixture must parse");
    let event = b6_tool_event(&identity, "model.turn.tool_calls", 1, terminal);
    validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 1)
        .expect("object member order must not affect parsed structural equality");
    assert!(entry.terminal_seen);
}

#[test]
fn b6_missing_argument_field_differs_from_null() {
    let identity = model_identity();
    let prefix = json!([{
        "id":"call_001","name":"files.read","arguments":{"path":"a.txt"}
    }]);
    let mut entry = b6_entry(&identity);
    b6_submit_prefix(&mut entry, &prefix);
    let before = b6_snapshot(&entry);
    let terminal = json!([{
        "id":"call_001","name":"files.read","arguments":{"path":null}
    }]);
    let event = b6_tool_event(&identity, "model.turn.tool_calls", 1, terminal);
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 1)
        .expect_err("missing must differ from explicit null");
    assert!(error
        .message
        .contains("argument field path must be a string"));
    assert_eq!(b6_snapshot(&entry), before);
}

#[test]
fn b6_unknown_tool_call_envelope_field_is_rejected_atomically() {
    let identity = model_identity();
    let mut entry = b6_entry(&identity);
    let before = b6_snapshot(&entry);
    let event = b6_tool_event(
        &identity,
        "model.tool.request",
        0,
        json!([{
            "id":"call_001","name":"files.read","arguments":{},"unexpected":true
        }]),
    );
    let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
        .expect_err("closed tool-call envelope must reject unknown fields");
    assert_eq!(error.code, "protocol_mismatch");
    assert!(error.message.contains("unknown fields"));
    assert_eq!(b6_snapshot(&entry), before);
}

fn b7_tool_event(
    identity: &ModelRequestIdentity,
    method: &str,
    sequence: u64,
    calls: Value,
    tools_executed: Value,
) -> UiControlPlaneEvent {
    let mut event = if calls.is_null() {
        model_event(identity, method, sequence, "Streaming", None)
    } else {
        b6_tool_event(identity, method, sequence, calls)
    };
    event.metadata["tools_executed"] = tools_executed;
    event
}

fn b7_snapshot(entry: &ModelRequestEntry) -> (u64, usize, bool, bool, u64, usize) {
    (
        entry.next_sequence,
        entry.event_count,
        entry.started_seen,
        entry.terminal_seen,
        entry.generated_bytes,
        entry.intermediate_tool_calls.len(),
    )
}

#[test]
fn b7_cumulative_tools_executed_is_sequence_consistent_and_atomic() {
    let identity = model_identity();
    let calls = b6_calls();
    let mut entry = b6_entry(&identity);

    let first = b7_tool_event(
        &identity,
        "model.tool.request",
        0,
        json!([calls[0].clone()]),
        json!(1),
    );
    validate_and_record_model_event(&mut entry, &first, "model.tool.request", 0)
        .expect("first request count must be one");

    for invalid in [
        json!(0),
        json!(1),
        json!(3),
        json!(-1),
        json!(1.5),
        json!("2"),
        json!(9_007_199_254_740_992_u64),
    ] {
        let before = b7_snapshot(&entry);
        let event = b7_tool_event(
            &identity,
            "model.tool.request",
            1,
            json!([calls[1].clone()]),
            invalid,
        );
        validate_and_record_model_event(&mut entry, &event, "model.tool.request", 1)
            .expect_err("invalid cumulative count must be rejected");
        assert_eq!(b7_snapshot(&entry), before, "rejection must be atomic");
    }

    let second = b7_tool_event(
        &identity,
        "model.tool.request",
        1,
        json!([calls[1].clone()]),
        json!(2),
    );
    validate_and_record_model_event(&mut entry, &second, "model.tool.request", 1)
        .expect("second request count must be two");

    let before = b7_snapshot(&entry);
    let bad_terminal = b7_tool_event(
        &identity,
        "model.turn.tool_calls",
        2,
        calls.clone(),
        json!(1),
    );
    validate_and_record_model_event(&mut entry, &bad_terminal, "model.turn.tool_calls", 2)
        .expect_err("terminal count must match accumulated calls");
    assert_eq!(b7_snapshot(&entry), before);

    let terminal = b7_tool_event(&identity, "model.turn.tool_calls", 2, calls, json!(2));
    validate_and_record_model_event(&mut entry, &terminal, "model.turn.tool_calls", 2)
        .expect("matching terminal count must be accepted");
    assert!(entry.terminal_seen);
}

#[test]
fn b7_tools_disabled_rejects_nonzero_count_atomically() {
    let identity = model_identity();
    let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
    let before = b7_snapshot(&entry);
    let event = b7_tool_event(&identity, "model.turn.started", 0, Value::Null, json!(1));
    validate_and_record_model_event(&mut entry, &event, "model.turn.started", 0)
        .expect_err("tools-disabled context must require zero");
    assert_eq!(b7_snapshot(&entry), before);
}

#[test]
fn b8_invalid_terminal_batches_preserve_complete_entry_snapshot() {
    let identity = model_identity();
    let valid_calls = b6_calls();
    let cases = vec![
        (
            "unknown later tool",
            json!([
                valid_calls[0].clone(),
                {"id":"call_002","name":"files.unknown","arguments":{}}
            ]),
            None,
        ),
        (
            "deep later arguments",
            json!([
                valid_calls[0].clone(),
                {"id":"call_002","name":"files.list","arguments":args_with_depth(33)}
            ]),
            None,
        ),
        (
            "oversized later arguments",
            json!([
                valid_calls[0].clone(),
                {"id":"call_002","name":"files.list","arguments":args_with_bytes(65_537)}
            ]),
            None,
        ),
        (
            "missing later id",
            json!([
                valid_calls[0].clone(),
                {"name":"files.list","arguments":{"path":"."}}
            ]),
            None,
        ),
        (
            "duplicate later id",
            json!([
                valid_calls[0].clone(),
                {"id":"call_001","name":"files.list","arguments":{"path":"."}}
            ]),
            None,
        ),
        (
            "unknown later envelope field",
            json!([
                valid_calls[0].clone(),
                {"id":"call_002","name":"files.list","arguments":{"path":"."},"unexpected":true}
            ]),
            None,
        ),
        (
            "provenance mismatch",
            json!([
                valid_calls[0].clone(),
                {"id":"call_002","name":"files.list","arguments":{"path":"elsewhere"}}
            ]),
            None,
        ),
        (
            "terminal counter mismatch",
            valid_calls.clone(),
            Some(json!(1)),
        ),
    ];

    for (label, terminal_calls, tools_executed) in cases {
        let mut entry = b6_entry(&identity);
        b6_submit_prefix(&mut entry, &valid_calls);
        entry.accepted = true;
        entry.cancel_pending = true;
        entry.buffered_events.push(model_event(
            &identity,
            "model.output.delta",
            99,
            "Streaming",
            Some("buffered sentinel"),
        ));
        let before = b6_snapshot(&entry);
        let mut event = b6_tool_event(&identity, "model.turn.tool_calls", 2, terminal_calls);
        if let Some(value) = tools_executed {
            event.metadata["tools_executed"] = value;
        }
        validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 2)
            .expect_err(&format!("{label} must reject the whole terminal batch"));
        assert_eq!(b6_snapshot(&entry), before, "{label} mutated entry");
    }
}

#[test]
fn b8_event_budget_failure_after_valid_terminal_batch_is_atomic() {
    let identity = model_identity();
    let calls = b6_calls();
    let mut entry = b6_entry(&identity);
    b6_submit_prefix(&mut entry, &calls);
    entry.event_count = MAX_MODEL_EVENTS_PER_REQUEST;
    let before = b6_snapshot(&entry);
    let event = b6_tool_event(&identity, "model.turn.tool_calls", 2, calls);
    let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 2)
        .expect_err("event budget failure must reject before terminal commit");
    assert_eq!(error.code, "budget_exceeded");
    assert_eq!(b6_snapshot(&entry), before);
}

#[test]
fn b8_valid_terminal_commits_once_and_adjacent_request_stays_unchanged() {
    let identity_a = model_identity();
    let identity_b = ModelRequestIdentity {
        request_id: "fedcba9876543210fedcba98".into(),
        chat_session_id: "chat_session_2".into(),
        model_id: identity_a.model_id.clone(),
        submitted_at_unix_ms: identity_a.submitted_at_unix_ms + 1,
        max_tokens: identity_a.max_tokens,
        seed: DEFAULT_MODEL_SEED,
        binding_fingerprint: "b".repeat(64),
    };
    let calls = b6_calls();
    let mut entry_a = b6_entry(&identity_a);
    let entry_b = b6_entry(&identity_b);
    b6_submit_prefix(&mut entry_a, &calls);
    let before_b = b6_snapshot(&entry_b);
    let event = b6_tool_event(&identity_a, "model.turn.tool_calls", 2, calls.clone());
    validate_and_record_model_event(&mut entry_a, &event, "model.turn.tool_calls", 2)
        .expect("valid matching terminal must commit");
    assert!(entry_a.terminal_seen);
    assert_eq!(entry_a.next_sequence, 3);
    assert_eq!(entry_a.event_count, 3);
    assert_eq!(
        entry_a.intermediate_tool_calls,
        calls
            .as_array()
            .expect("calls fixture must be an array")
            .clone()
    );
    let after_first_commit = b6_snapshot(&entry_a);
    validate_and_record_model_event(&mut entry_a, &event, "model.turn.tool_calls", 2)
        .expect_err("terminal batch must not commit twice");
    assert_eq!(b6_snapshot(&entry_a), after_first_commit);
    assert_eq!(b6_snapshot(&entry_b), before_b);
}

fn b9_call(id: &str, name: &str, arguments: Value) -> Value {
    json!({"id": id, "name": name, "arguments": arguments})
}

fn b9_entry(identity: &ModelRequestIdentity, name: &str) -> ModelRequestEntry {
    ModelRequestEntry::new(identity.clone(), vec![name.to_string()])
}

#[test]
fn b9_accepts_exact_argument_schema_for_every_registered_file_tool() {
    let identity = model_identity();
    let cases = [
        ("files.read", json!({"path":"notes.txt"})),
        ("files.list", json!({"path":"."})),
        ("files.write", json!({"path":"notes.txt","content":"hello"})),
        ("files.create_folder", json!({"path":"drafts"})),
        ("files.delete", json!({"path":"old.txt"})),
    ];

    for (name, arguments) in cases {
        let mut entry = b9_entry(&identity, name);
        let call = b9_call("call_001", name, arguments);
        let request = b6_tool_event(&identity, "model.tool.request", 0, json!([call.clone()]));
        validate_and_record_model_event(&mut entry, &request, "model.tool.request", 0)
            .expect("exact registered tool schema must be accepted");
        let terminal = b6_tool_event(&identity, "model.turn.tool_calls", 1, json!([call]));
        validate_and_record_model_event(&mut entry, &terminal, "model.turn.tool_calls", 1)
            .expect("matching terminal must be accepted");
    }
}

#[test]
fn b9_rejects_malformed_intermediate_arguments_atomically() {
    let identity = model_identity();
    let cases = [
        ("missing required", "files.read", json!({})),
        ("null required", "files.read", json!({"path":null})),
        ("wrong type", "files.read", json!({"path":7})),
        (
            "extra key",
            "files.read",
            json!({"path":"notes.txt","recursive":true}),
        ),
        (
            "nested wrong type",
            "files.write",
            json!({"path":"notes.txt","content":{"text":"hello"}}),
        ),
        (
            "write missing content",
            "files.write",
            json!({"path":"notes.txt"}),
        ),
    ];

    for (label, name, arguments) in cases {
        let mut entry = b9_entry(&identity, name);
        let before = b6_snapshot(&entry);
        let event = b6_tool_event(
            &identity,
            "model.tool.request",
            0,
            json!([b9_call("call_001", name, arguments)]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err(&format!("{label} must be rejected"));
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(b6_snapshot(&entry), before, "{label} mutated entry");
    }
}

#[test]
fn b9_terminal_schema_validation_precedes_provenance_and_is_atomic() {
    let identity = model_identity();
    let valid = b9_call(
        "call_001",
        "files.write",
        json!({"path":"notes.txt","content":"hello"}),
    );
    let malformed = [
        json!({"path":"notes.txt"}),
        json!({"path":"notes.txt","content":null}),
        json!({"path":"notes.txt","content":9}),
        json!({"path":"notes.txt","content":"hello","mode":"append"}),
        json!({"path":{"nested":"notes.txt"},"content":"hello"}),
    ];

    for arguments in malformed {
        let mut entry = b9_entry(&identity, "files.write");
        let request = b6_tool_event(&identity, "model.tool.request", 0, json!([valid.clone()]));
        validate_and_record_model_event(&mut entry, &request, "model.tool.request", 0)
            .expect("valid prefix must be accepted");
        let before = b6_snapshot(&entry);
        let terminal = b6_tool_event(
            &identity,
            "model.turn.tool_calls",
            1,
            json!([b9_call("call_001", "files.write", arguments)]),
        );
        let error =
            validate_and_record_model_event(&mut entry, &terminal, "model.turn.tool_calls", 1)
                .expect_err("malformed terminal arguments must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("tool files.write"),
            "schema error must precede provenance comparison: {}",
            error.message
        );
        assert_eq!(b6_snapshot(&entry), before);
    }
}

#[test]
fn b6_adjacent_model_request_entries_are_isolated() {
    let identity_a = model_identity();
    let identity_b = ModelRequestIdentity {
        request_id: "fedcba9876543210fedcba98".into(),
        chat_session_id: "chat_session_2".into(),
        model_id: "qwen3-1.7b-instruct-q4-k-m".into(),
        submitted_at_unix_ms: 1_750_000_000_001,
        max_tokens: 128,
        seed: DEFAULT_MODEL_SEED,
        binding_fingerprint: "b".repeat(64),
    };
    let calls = b6_calls();
    let mut entry_a = b6_entry(&identity_a);
    let mut entry_b = b6_entry(&identity_b);
    b6_submit_prefix(&mut entry_a, &calls);
    let before_a = b6_snapshot(&entry_a);
    let before_b = b6_snapshot(&entry_b);
    let event_b = b6_tool_event(&identity_b, "model.turn.tool_calls", 0, calls);
    let error = validate_and_record_model_event(&mut entry_b, &event_b, "model.turn.tool_calls", 0)
        .expect_err("entry B cannot use entry A's intermediate requests");
    b6_assert_provenance_rejection(&error);
    assert_eq!(b6_snapshot(&entry_a), before_a);
    assert_eq!(b6_snapshot(&entry_b), before_b);
}

// ---- B10 malicious-sidecar defense-in-depth (deterministic adversarial corpus) ----
//
// Bounding chain for tool-call `id` length and intermediate_tool_calls growth
// (settled by inspection, no redundant Rust check added):
//   * every sidecar event arrives as one IPC frame bounded by
//     `ipc::MAX_FRAME_BYTES` (4 MiB), so a single `id` cannot exceed that frame;
//   * `entry.intermediate_tool_calls` only grows on an accepted
//     `model.tool.request`, and each acceptance consumes one event of the
//     `MAX_MODEL_EVENTS_PER_REQUEST` (2048) budget, which is checked before
//     mutation, so growth is bounded by 2048 frames;
//   * the Python gateway is the upstream authority and additionally caps a turn
//     at `MAX_TOOL_CALLS_PER_TURN` (10).
// Bound = frame size * event budget, both enforced before mutation.

/// Deterministic LCG: no external crates, no entropy, reproducible corpus.
struct B10Rng(u64);

impl B10Rng {
    fn new(seed: u64) -> Self {
        Self(seed)
    }

    fn next_u32(&mut self) -> u32 {
        self.0 = self
            .0
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        (self.0 >> 33) as u32
    }

    fn pick<'a, T>(&mut self, items: &'a [T]) -> &'a T {
        let index = self.next_u32() as usize % items.len();
        &items[index]
    }
}

fn b10_entry(identity: &ModelRequestIdentity) -> ModelRequestEntry {
    ModelRequestEntry::new(
        identity.clone(),
        REGISTERED_MODEL_TOOLS
            .iter()
            .map(|name| (*name).to_string())
            .collect(),
    )
}

fn b10_read_call(id: &str, arguments: Value) -> Value {
    json!({"id": id, "name": "files.read", "arguments": arguments})
}

fn b10_reject(entry: &mut ModelRequestEntry, event: &UiControlPlaneEvent, label: &str) {
    let before = b6_snapshot(entry);
    let method = event.method.clone();
    let sequence = event.sequence;
    let error = validate_and_record_model_event(entry, event, &method, sequence)
        .expect_err(&format!("{label} must be rejected"));
    assert!(
        matches!(
            error.code.as_str(),
            "protocol_mismatch" | "budget_exceeded" | "invalid_sequence"
        ),
        "{label} produced unstable error code {}",
        error.code
    );
    assert!(!error.message.is_empty(), "{label} lost its error message");
    assert_eq!(b6_snapshot(entry), before, "{label} mutated entry state");
}

#[test]
fn b10_boundary_limits_accept_at_limit_and_reject_beyond() {
    let identity = model_identity();

    // At-limit payloads must be accepted by the boundary.
    // args_with_bytes/keys/nodes build non-schema fields, so accept-side cases
    // use schema-valid arguments that still sit exactly on a structural limit.
    let at_depth = args_with_depth(MAX_ARGUMENT_DEPTH);
    assert_eq!(count_depth(&at_depth), MAX_ARGUMENT_DEPTH);

    let accepted = [
        ("bytes at limit", args_with_bytes(MAX_ARGUMENT_BYTES)),
        ("depth at limit", at_depth),
        ("keys at limit", args_with_keys(MAX_ARGUMENT_OBJECT_KEYS)),
        ("nodes at limit", args_with_nodes(MAX_ARGUMENT_NODES)),
    ];
    for (label, arguments) in accepted {
        let mut entry = b10_entry(&identity);
        let event = b6_tool_event(
            &identity,
            "model.tool.request",
            0,
            json!([b10_read_call("call_001", arguments)]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("non-schema structural payloads still fail per-tool schema");
        assert_eq!(
            error.code, "protocol_mismatch",
            "{label} must fail on schema, not on a resource limit"
        );
        assert!(
            error.message.contains("tool files.read"),
            "{label} must reach per-tool schema validation, got: {}",
            error.message
        );
    }

    // Beyond-limit payloads must fail earlier, on the resource-limit checks.
    let over_limit = [
        (
            "bytes over limit",
            args_with_bytes(MAX_ARGUMENT_BYTES + 1),
            "maximum size",
        ),
        (
            "depth over limit",
            args_with_depth(MAX_ARGUMENT_DEPTH + 1),
            "maximum nesting depth",
        ),
        (
            "keys over limit",
            args_with_keys(MAX_ARGUMENT_OBJECT_KEYS + 1),
            "maximum object key count",
        ),
        (
            "nodes over limit",
            args_with_nodes(MAX_ARGUMENT_NODES + 1),
            "maximum node count",
        ),
        (
            "unicode bytes over limit",
            args_with_unicode_bytes(MAX_ARGUMENT_BYTES + 1),
            "maximum size",
        ),
    ];
    for (label, arguments, expected) in over_limit {
        let mut entry = b10_entry(&identity);
        let before = b6_snapshot(&entry);
        let event = b6_tool_event(
            &identity,
            "model.tool.request",
            0,
            json!([b10_read_call("call_001", arguments)]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err(&format!("{label} must be rejected"));
        assert_eq!(error.code, "protocol_mismatch", "{label}");
        assert!(
            error.message.contains(expected),
            "{label} produced unstable message: {}",
            error.message
        );
        assert_eq!(b6_snapshot(&entry), before, "{label} mutated entry state");
    }
}

#[test]
fn b10_hostile_envelopes_are_rejected_atomically() {
    let identity = model_identity();
    let huge_id = "i".repeat(200_000);
    let cases: Vec<(&str, Value)> = vec![
        (
            "unknown envelope field",
            json!({"id":"c1","name":"files.read","arguments":{"path":"a"},"x":1}),
        ),
        (
            "missing id",
            json!({"name":"files.read","arguments":{"path":"a"}}),
        ),
        (
            "id wrong type",
            json!({"id":7,"name":"files.read","arguments":{"path":"a"}}),
        ),
        (
            "empty id",
            json!({"id":"","name":"files.read","arguments":{"path":"a"}}),
        ),
        (
            "whitespace id",
            json!({"id":"   ","name":"files.read","arguments":{"path":"a"}}),
        ),
        (
            "name wrong type",
            json!({"id":"c1","name":42,"arguments":{"path":"a"}}),
        ),
        (
            "unregistered tool",
            json!({"id":"c1","name":"files.exec","arguments":{"path":"a"}}),
        ),
        (
            "arguments not an object",
            json!({"id":"c1","name":"files.read","arguments":"{\"path\":\"a\"}"}),
        ),
        (
            "arguments null",
            json!({"id":"c1","name":"files.read","arguments":null}),
        ),
        (
            "arguments array",
            json!({"id":"c1","name":"files.read","arguments":[]}),
        ),
        (
            "NUL byte in path",
            json!({"id":"c1","name":"files.read","arguments":{"path":"a\u{0000}b","extra":1}}),
        ),
        (
            "control chars with extra key",
            json!({"id":"c1","name":"files.read","arguments":{"path":"a\u{0007}\u{001b}b","x":1}}),
        ),
        (
            "unicode replacement path with extra key",
            json!({"id":"c1","name":"files.read","arguments":{"path":"\u{fffd}\u{202e}evil","x":1}}),
        ),
        ("envelope not an object", json!("call_001")),
    ];

    for (label, call) in cases {
        let mut entry = b10_entry(&identity);
        let event = b6_tool_event(&identity, "model.tool.request", 0, json!([call]));
        b10_reject(&mut entry, &event, label);
    }

    // Huge id is not covered by MAX_ARGUMENT_BYTES; it is bounded upstream by
    // ipc::MAX_FRAME_BYTES. At the validator seam it must not panic and must
    // still be classified deterministically by the remaining rules.
    let mut entry = b10_entry(&identity);
    let duplicate = json!([
        {"id": huge_id.clone(), "name":"files.read","arguments":{"path":"a"}},
        {"id": huge_id, "name":"files.list","arguments":{"path":"."}}
    ]);
    let event = b6_tool_event(&identity, "model.turn.tool_calls", 0, duplicate);
    b10_reject(&mut entry, &event, "duplicate huge ids");

    // Empty and non-array tool_calls metadata.
    for (label, calls) in [
        ("empty tool_calls", json!([])),
        ("tool_calls not an array", json!({"id":"c1"})),
    ] {
        let mut entry = b10_entry(&identity);
        let event = b6_tool_event(&identity, "model.tool.request", 0, calls);
        b10_reject(&mut entry, &event, label);
    }

    // model.tool.request must carry exactly one call.
    let mut entry = b10_entry(&identity);
    let event = b6_tool_event(
        &identity,
        "model.tool.request",
        0,
        json!([
            {"id":"c1","name":"files.read","arguments":{"path":"a"}},
            {"id":"c2","name":"files.list","arguments":{"path":"."}}
        ]),
    );
    b10_reject(&mut entry, &event, "batched intermediate request");
}

#[test]
fn b10_hostile_terminal_batches_are_rejected_atomically() {
    let identity = model_identity();
    let calls = b6_calls();

    let cases: Vec<(&str, Value, Option<Value>)> = vec![
        (
            "provenance reordered",
            json!([calls[1].clone(), calls[0].clone()]),
            None,
        ),
        (
            "provenance truncated",
            json!([calls[0].clone()]),
            Some(json!(1)),
        ),
        (
            "provenance extended",
            json!([
                calls[0].clone(),
                calls[1].clone(),
                {"id":"call_003","name":"files.read","arguments":{"path":"c.txt"}}
            ]),
            Some(json!(3)),
        ),
        ("count near u64 max", calls.clone(), Some(json!(u64::MAX))),
        (
            "count at unsafe integer",
            calls.clone(),
            Some(json!(9_007_199_254_740_992_u64)),
        ),
        ("count zero", calls.clone(), Some(json!(0))),
        ("count negative", calls.clone(), Some(json!(-1))),
        ("count fractional", calls.clone(), Some(json!(2.5))),
        ("count as string", calls.clone(), Some(json!("2"))),
    ];

    for (label, terminal_calls, tools_executed) in cases {
        let mut entry = b6_entry(&identity);
        b6_submit_prefix(&mut entry, &calls);
        let mut event = b6_tool_event(&identity, "model.turn.tool_calls", 2, terminal_calls);
        if let Some(value) = tools_executed {
            event.metadata["tools_executed"] = value;
        }
        b10_reject(&mut entry, &event, label);
    }

    // A huge hostile batch must be rejected without unbounded work.
    let mut entry = b6_entry(&identity);
    b6_submit_prefix(&mut entry, &calls);
    let huge: Vec<Value> = (0..2_000)
        .map(|index| json!({"id": format!("c{index}"), "name":"files.read", "arguments":{"path":"a.txt"}}))
        .collect();
    let mut event = b6_tool_event(&identity, "model.turn.tool_calls", 2, json!(huge));
    event.metadata["tools_executed"] = json!(2_000);
    let started = std::time::Instant::now();
    b10_reject(&mut entry, &event, "huge hostile terminal batch");
    assert!(
        started.elapsed() < std::time::Duration::from_secs(5),
        "huge hostile batch validation must stay bounded"
    );
}

#[test]
fn b10_repeated_hostile_events_are_atomic_under_seeded_corpus() {
    let identity = model_identity();
    let calls = b6_calls();
    let mut entry = b6_entry(&identity);
    b6_submit_prefix(&mut entry, &calls);
    entry.accepted = true;
    let before = b6_snapshot(&entry);

    let names = ["files.read", "files.list", "files.exec", "", "FILES.READ"];
    let ids = [
        "",
        " ",
        "call_001",
        "call_002",
        "\u{0000}",
        "x".repeat(4096).leak() as &str,
    ];
    let arg_shapes = [
        json!({}),
        json!({"path":null}),
        json!({"path":1}),
        json!({"path":"a.txt","extra":true}),
        json!({"path":{"nested":"a"}}),
        // Control/NUL characters are schema-valid `path` strings under the frozen
        // ADR-015 contract, so they are paired with a structural violation here and
        // covered on their own in b10_control_characters_in_path_are_schema_valid.
        json!({"path":"\u{0000}\u{001b}","extra":1}),
        json!([]),
        json!("string"),
    ];
    let methods = ["model.tool.request", "model.turn.tool_calls"];
    let counts = [
        json!(0),
        json!(1),
        json!(2),
        json!(3),
        json!(-1),
        json!(u64::MAX),
    ];

    let mut rng = B10Rng::new(0x05EE_DB10_u64);
    let started = std::time::Instant::now();
    for iteration in 0..512 {
        let method = *rng.pick(&methods);
        let call = json!({
            "id": rng.pick(&ids),
            "name": rng.pick(&names),
            "arguments": rng.pick(&arg_shapes).clone(),
        });
        let mut event = b6_tool_event(&identity, method, 2, json!([call]));
        event.metadata["tools_executed"] = rng.pick(&counts).clone();
        b10_reject(
            &mut entry,
            &event,
            &format!("seeded hostile event {iteration}"),
        );
    }
    assert!(
        started.elapsed() < std::time::Duration::from_secs(20),
        "seeded hostile corpus must stay bounded"
    );
    assert_eq!(
        b6_snapshot(&entry),
        before,
        "hostile corpus must leave the entry untouched"
    );
}

#[test]
fn b10_valid_control_commits_once_and_adjacent_request_is_isolated() {
    let identity_a = model_identity();
    let identity_b = ModelRequestIdentity {
        request_id: "0f0f0f0f0f0f0f0f0f0f0f0f".into(),
        chat_session_id: "chat_session_b10".into(),
        model_id: identity_a.model_id.clone(),
        submitted_at_unix_ms: identity_a.submitted_at_unix_ms + 7,
        max_tokens: identity_a.max_tokens,
        seed: DEFAULT_MODEL_SEED,
        binding_fingerprint: "c".repeat(64),
    };
    let calls = b6_calls();
    let mut entry_a = b6_entry(&identity_a);
    let mut entry_b = b6_entry(&identity_b);
    b6_submit_prefix(&mut entry_a, &calls);
    let before_b = b6_snapshot(&entry_b);

    // Hostile traffic against A must not touch B.
    let hostile = b6_tool_event(
        &identity_a,
        "model.turn.tool_calls",
        2,
        json!([calls[1].clone(), calls[0].clone()]),
    );
    b10_reject(
        &mut entry_a,
        &hostile,
        "reordered provenance before valid commit",
    );
    assert_eq!(b6_snapshot(&entry_b), before_b);

    let terminal = b6_tool_event(&identity_a, "model.turn.tool_calls", 2, calls.clone());
    validate_and_record_model_event(&mut entry_a, &terminal, "model.turn.tool_calls", 2)
        .expect("valid terminal must commit exactly once");
    assert!(entry_a.terminal_seen);
    let after_commit = b6_snapshot(&entry_a);

    // Replay of the same accepted terminal must be rejected without mutation.
    b10_reject(&mut entry_a, &terminal, "terminal replay");
    assert_eq!(b6_snapshot(&entry_a), after_commit);
    assert_eq!(b6_snapshot(&entry_b), before_b, "adjacent request mutated");

    // B still rejects A's provenance.
    let stolen = b6_tool_event(&identity_b, "model.turn.tool_calls", 0, calls);
    b10_reject(&mut entry_b, &stolen, "cross-request provenance theft");
}

#[test]
fn b10_control_characters_in_path_are_schema_valid_at_the_rust_boundary() {
    // ADR-015 freezes the per-tool schema as "path is a string"; the control plane
    // deliberately does not sanitize path contents, because workspace containment is
    // enforced downstream. This test pins that boundary so a future change is explicit.
    // The downstream NUL handling gap found by the B10 corpus is fixed in
    // modules/tool_execution_ru.py, not here.
    let identity = model_identity();
    for path in ["a\u{0000}b.txt", "a\u{001b}[31m.txt", "\u{202e}txt.exe"] {
        let mut entry = b10_entry(&identity);
        let call = b10_read_call("call_001", json!({ "path": path }));
        let event = b6_tool_event(&identity, "model.tool.request", 0, json!([call.clone()]));
        validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect("path strings are schema-valid regardless of control characters");
        assert_eq!(entry.intermediate_tool_calls, vec![call]);
    }
}
