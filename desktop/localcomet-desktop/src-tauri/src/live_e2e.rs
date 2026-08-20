//! Live end-to-end managed-runtime proofs (P0-2 / P0-10).
//!
//! These tests drive the REAL production path with no mocks in the objects
//! under test:
//!
//! ```text
//! ArtifactTrustService (real installed artifacts)
//! -> ManagedRuntimeSupervisor::start (real llama-server in a job object)
//! -> readiness probes (/health + /v1/models exact alias)
//! -> ControlPlaneBridge -> real Python sidecar -> model.managed.attach
//! -> reserve_model_turn + ensure_turn_binding + request_model_turn_reserved
//! -> gateway SSE inference against the live llama-server
//! -> turn terminal event observed through the real Tauri event channel
//! ```
//!
//! The custom-model test drives the real `managed_runtime_start` command with
//! an approval minted through the real `request_approval` prompt roundtrip.
//!
//! Environment (honesty-gated like the real-sidecar tests):
//!
//! ```text
//! LOCALCOMET_TEST_PROJECT_ROOT  repo root (sidecar runner + modules)
//! LOCALCOMET_TEST_PYTHON        system python executable
//! LOCALCOMET_LIVE_MODEL_ROOT    app-data root with installed model+runtime
//! LOCALCOMET_LIVE_MODEL_ID      optional, default qwen2.5-1.5b-instruct-q4-k-m
//! LOCALCOMET_LIVE_RUNTIME_ID    optional, default llama-cpp-windows-x86-64-cpu-bootstrap
//! LOCALCOMET_LIVE_CUSTOM_MODEL_ID  optional, enables the custom approval path
//! LOCALCOMET_REQUIRE_LIVE_MODEL=1  hard-fails when the env is incomplete
//! ```
//!
//! Without the environment the tests are silent no-ops; with
//! LOCALCOMET_REQUIRE_LIVE_MODEL set they panic instead of skipping, so CI can
//! never mistake an unstarted proof for a green one.

#[cfg(all(test, debug_assertions))]
mod tests {
    use crate::artifact_trust::ArtifactTrustService;
    use crate::control_plane::{
        AssistantContext, ControlPlaneBridge, ModelRequestIdentity, CONTROL_PLANE_EVENT_CHANNEL,
    };
    use crate::managed_runtime::{
        managed_runtime_start, ManagedModelState, ManagedRuntimeState, ManagedRuntimeSupervisor,
    };
    use crate::supervisor::{DesktopSidecarSupervisor, SupervisorConfig};
    use serde_json::{json, Value};
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::sync::{Arc, Mutex, OnceLock};
    use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
    use tauri::{Listener, Manager};

    /// Serialize the heavy live tests (sidecar + webview window + llama-server).
    static LIVE_E2E_GUARD: OnceLock<Mutex<()>> = OnceLock::new();

    struct LiveHarness {
        _app: tauri::App,
        app_handle: tauri::AppHandle,
        bridge: Arc<ControlPlaneBridge>,
        sidecar: Arc<DesktopSidecarSupervisor>,
        runtime: Arc<ManagedRuntimeSupervisor>,
        artifacts: Arc<ArtifactTrustService>,
        approval_dispatcher: Option<Arc<crate::approval::FrontendApprovalDispatcher>>,
        events: Arc<Mutex<Vec<Value>>>,
    }

    impl Drop for LiveHarness {
        fn drop(&mut self) {
            let _ = self.runtime.stop(&self.bridge);
            let _ = self.sidecar.shutdown();
        }
    }

    fn env_or_warn(name: &str) -> Option<String> {
        std::env::var(name).ok().filter(|value| !value.is_empty())
    }

    fn live_env() -> Option<(PathBuf, PathBuf, PathBuf, String, String)> {
        let project_root = std::env::var_os("LOCALCOMET_TEST_PROJECT_ROOT").map(PathBuf::from);
        let python = std::env::var_os("LOCALCOMET_TEST_PYTHON").map(PathBuf::from);
        let model_root = std::env::var_os("LOCALCOMET_LIVE_MODEL_ROOT").map(PathBuf::from);
        let model_id = env_or_warn("LOCALCOMET_LIVE_MODEL_ID")
            .unwrap_or_else(|| "qwen2.5-1.5b-instruct-q4-k-m".to_owned());
        let runtime_id = env_or_warn("LOCALCOMET_LIVE_RUNTIME_ID")
            .unwrap_or_else(|| "llama-cpp-windows-x86-64-cpu-bootstrap".to_owned());
        match (project_root, python, model_root) {
            (Some(project_root), Some(python), Some(model_root)) => {
                Some((project_root, python, model_root, model_id, runtime_id))
            }
            _ => {
                if std::env::var_os("LOCALCOMET_REQUIRE_LIVE_MODEL").is_some() {
                    panic!(
                        "LOCALCOMET_REQUIRE_LIVE_MODEL is set but the live-model environment \
                         (LOCALCOMET_TEST_PROJECT_ROOT, LOCALCOMET_TEST_PYTHON, \
                         LOCALCOMET_LIVE_MODEL_ROOT) is not available"
                    );
                }
                eprintln!(
                    "SKIP: live e2e test - set LOCALCOMET_TEST_PROJECT_ROOT, \
                     LOCALCOMET_TEST_PYTHON and LOCALCOMET_LIVE_MODEL_ROOT to enable"
                );
                None
            }
        }
    }

    fn build_harness(
        project_root: &std::path::Path,
        python: &std::path::Path,
        model_root: &std::path::Path,
    ) -> LiveHarness {
        // Real Wry app handle with a hidden "main" webview window so the
        // bridge's window-scoped event emission follows the production route.
        // Commands are driven through app.manage/app.state exactly like lib.rs.
        // any_thread: cargo test runs tests off the main thread on Windows.
        let app = tauri::Builder::default()
            .any_thread()
            .setup(|app| {
                tauri::WebviewWindowBuilder::new(app, "main", tauri::WebviewUrl::default())
                    .title("localcomet-live-e2e")
                    .visible(false)
                    .build()?;
                Ok(())
            })
            .build(tauri::test::mock_context(tauri::test::noop_assets()))
            .expect("build live e2e tauri app");

        let app_handle = app.handle().clone();
        if app_handle.get_webview_window("main").is_none() {
            // Setup-window registration did not survive build(); create the
            // hidden window directly on the handle instead.
            tauri::WebviewWindowBuilder::new(&app_handle, "main", tauri::WebviewUrl::default())
                .title("localcomet-live-e2e")
                .visible(false)
                .build()
                .expect("create live e2e main window");
        }
        assert!(
            app_handle.get_webview_window("main").is_some(),
            "live e2e requires the main webview window for event emission"
        );
        let events: Arc<Mutex<Vec<Value>>> = Arc::new(Mutex::new(Vec::new()));
        {
            let sink = Arc::clone(&events);
            app_handle.listen_any(CONTROL_PLANE_EVENT_CHANNEL, move |event| {
                if let Ok(payload) = serde_json::from_str::<Value>(event.payload()) {
                    sink.lock()
                        .expect("live e2e event sink poisoned")
                        .push(payload);
                }
            });
        }

        let sidecar = Arc::new(DesktopSidecarSupervisor::new(
            SupervisorConfig::debug_for_tests(project_root.to_path_buf(), python.to_path_buf()),
        ));
        sidecar
            .start_and_wait_ready(Duration::from_secs(20))
            .expect("live e2e sidecar ready");

        let bridge = Arc::new(ControlPlaneBridge::new(
            Arc::clone(&sidecar),
            app_handle.clone(),
        ));
        // Wire the bridge as the frame router exactly like lib.rs does:
        // without it, sidecar responses are dropped and every bridge request
        // times out.
        sidecar.set_frame_router(Arc::clone(&bridge) as Arc<dyn crate::supervisor::SidecarFrameRouter>);
        let artifacts = Arc::new(
            ArtifactTrustService::production(model_root)
                .expect("artifact trust service for live model root"),
        );
        let runtime = Arc::new(ManagedRuntimeSupervisor::new(Arc::clone(&artifacts)));

        let approval_state = crate::approval_commands::ApprovalState::new(app_handle.clone());
        let approval_dispatcher = approval_state.dispatcher.as_ref().map(Arc::clone);
        // Legacy listener retained for compatibility with the live harness;
        // production approval issuance now happens in the Rust background path
        // and does not open a user-facing card.
        if let Some(dispatcher) = approval_state.dispatcher.as_ref() {
            let dispatcher = Arc::clone(dispatcher);
            app_handle.listen_any("request_tool_approval", move |event| {
                if let Ok(payload) = serde_json::from_str::<Value>(event.payload()) {
                    if let Some(request_id) = payload.get("request_id").and_then(Value::as_str) {
                        let _ = dispatcher
                            .resolve(request_id, crate::approval::ApprovalDecision::Approve);
                    }
                }
            });
        }
        app.manage(Arc::clone(&bridge));
        app.manage(Arc::clone(&runtime));
        app.manage(approval_state);

        LiveHarness {
            _app: app,
            app_handle,
            bridge,
            sidecar,
            runtime,
            artifacts,
            approval_dispatcher,
            events,
        }
    }

    static TURN_COUNTER: AtomicU64 = AtomicU64::new(1);

    /// Confirms the managed binding through the real production flow:
    /// a scoped token is minted by the Rust approval boundary (without a
    /// second UI prompt after an already approved Ready start), then the real
    /// model_binding_set command runs exactly as the UI does.
    fn confirm_model_binding(
        harness: &LiveHarness,
        model_id: &str,
        runtime_instance_id: &str,
    ) -> Result<Value, crate::control_plane::BridgeError> {
        let input = json!({
            "provider_id": "managed-llama-cpp",
            "harness_id": "minimal",
            "port": null,
            "model_id": model_id,
            "runtime_instance_id": runtime_instance_id,
        });
        let envelope = crate::approval_commands::request_approval(
            harness
                ._app
                .state::<crate::approval_commands::ApprovalState>(),
            harness._app.state::<Arc<ManagedRuntimeSupervisor>>(),
            "model.binding.set".to_owned(),
            input,
        )
        .expect("background binding approval issued by Rust");
        tauri::async_runtime::block_on(crate::control_plane::model_binding_set(
            harness._app.state::<Arc<ControlPlaneBridge>>(),
            harness
                ._app
                .state::<crate::approval_commands::ApprovalState>(),
            "managed-llama-cpp".to_owned(),
            "minimal".to_owned(),
            None,
            model_id.to_owned(),
            Some(runtime_instance_id.to_owned()),
            envelope.token,
            envelope.approval_id,
            envelope.call_id,
        ))
    }

    /// Drives a turn through the same ordering as the model_turn_start
    /// command: reserve -> ensure_turn_binding -> dispatch.
    fn start_inference_turn(
        harness: &LiveHarness,
        model_id: &str,
        binding_fingerprint: &str,
        prompt: &str,
        max_tokens: u16,
    ) -> Result<Value, crate::control_plane::BridgeError> {
        let sequence = TURN_COUNTER.fetch_add(1, Ordering::SeqCst);
        let now_ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64;
        // The gateway requires 24 lowercase hex turn ids (TURN_ID_RE).
        let turn_id = format!("{sequence:024x}");
        let identity = ModelRequestIdentity {
            request_id: turn_id.clone(),
            chat_session_id: format!("live-e2e-session-{sequence:08}"),
            model_id: model_id.to_owned(),
            submitted_at_unix_ms: now_ms,
            max_tokens,
            seed: crate::control_plane::DEFAULT_MODEL_SEED,
            binding_fingerprint: binding_fingerprint.to_owned(),
        };
        let assistant_context = AssistantContext::trusted("en", false, None)?;
        let wire_digest = crate::control_plane::model_turn_wire_digest(
            &crate::control_plane::model_turn_wire_payload(
                &identity,
                prompt,
                &assistant_context,
                &[],
            ),
        );
        harness
            .bridge
            .reserve_model_turn(&identity, Vec::new(), wire_digest, "off")?;
        crate::control_plane::dispatch_gate_for_model_turn(
            &harness.runtime,
            &harness.bridge,
            &identity.model_id,
            &identity.binding_fingerprint,
        )?;
        harness.bridge.request_model_turn_reserved(
            identity,
            prompt.to_owned(),
            assistant_context,
            Vec::new(),
            "off".to_owned(),
        )
    }

    /// Waits for the terminal event of a turn and returns (joined deltas, terminal).
    fn wait_for_turn_terminal(
        harness: &LiveHarness,
        request_id: &str,
        timeout: Duration,
    ) -> (String, Value) {
        let deadline = Instant::now() + timeout;
        loop {
            {
                let events = harness.events.lock().expect("live e2e event sink poisoned");
                let mut deltas = String::new();
                let mut terminal = None;
                for event in events.iter() {
                    if event.get("request_id").and_then(Value::as_str) != Some(request_id) {
                        continue;
                    }
                    match event.get("method").and_then(Value::as_str) {
                        Some("model.output.delta") => {
                            if let Some(text) = event.get("text").and_then(Value::as_str) {
                                deltas.push_str(text);
                            }
                        }
                        Some(
                            "model.turn.completed"
                            | "model.turn.failed"
                            | "model.turn.timed_out"
                            | "model.turn.cancelled",
                        ) => {
                            terminal = Some(event.clone());
                        }
                        _ => {}
                    }
                }
                if let Some(terminal) = terminal {
                    return (deltas, terminal);
                }
            }
            if Instant::now() >= deadline {
                let events = harness.events.lock().expect("live e2e event sink poisoned");
                let methods: Vec<String> = events
                    .iter()
                    .map(|event| {
                        format!(
                            "{}:{}",
                            event.get("method").and_then(Value::as_str).unwrap_or("?"),
                            event
                                .get("request_id")
                                .and_then(Value::as_str)
                                .unwrap_or("-")
                        )
                    })
                    .collect();
                panic!(
                    "live e2e turn {request_id} did not reach a terminal event in time;                      captured events: {methods:?}; bridge warnings: {:?}",
                    harness.bridge.warnings_snapshot()
                );
            }
            std::thread::sleep(Duration::from_millis(250));
        }
    }

    #[test]
    fn live_managed_model_start_ready_inference_stop_restart_inference() {
        let Some((project_root, python, model_root, model_id, runtime_id)) = live_env() else {
            return;
        };
        let _guard = LIVE_E2E_GUARD
            .get_or_init(|| Mutex::new(()))
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let harness = build_harness(&project_root, &python, &model_root);

        // --- capability report for the selected engine (P0-6) ---
        let capability = harness
            .runtime
            .runtime_capability(&runtime_id, Some(&model_id))
            .expect("capability probe for the live runtime");
        assert_eq!(capability.runtime_id, runtime_id);
        assert!(
            capability.available,
            "runtime must be usable: {capability:?}"
        );
        assert!(capability.safe_to_start);

        // --- start -> ready (P0-2) ---
        let first = match harness.runtime.start(
            &model_id,
            None,
            Some(&runtime_id),
            &harness.bridge,
            None,
            None,
        ) {
            Ok(response) => response,
            Err(error) => {
                let snapshot = harness.sidecar.snapshot();
                eprintln!("live e2e start failed: {error:?}");
                eprintln!("sidecar stderr tail: {:?}", snapshot.stderr_tail);
                eprintln!(
                    "managed runtime stdout tail: {:?}",
                    harness.runtime.logs().stdout_tail
                );
                eprintln!(
                    "managed runtime stderr tail: {:?}",
                    harness.runtime.logs().stderr_tail
                );
                panic!("live managed model start reaches Ready: {error:?}");
            }
        };
        assert_eq!(first.state, ManagedRuntimeState::Ready);
        assert_eq!(first.model_state, ManagedModelState::Ready);
        assert!(first.inference_ready);
        assert_eq!(
            first.runtime_id, runtime_id,
            "start response must bind runtime_id"
        );
        assert_eq!(first.model_id, model_id);

        let status = harness.runtime.status(&harness.bridge);
        assert_eq!(status.state, ManagedRuntimeState::Ready);
        assert_eq!(status.runtime_id.as_deref(), Some(runtime_id.as_str()));
        let first_fingerprint = status
            .binding_fingerprint
            .clone()
            .expect("backend reports the active binding fingerprint");

        // --- double start is rejected (concurrency matrix) ---
        let busy = harness
            .runtime
            .start(
                &model_id,
                None,
                Some(&runtime_id),
                &harness.bridge,
                None,
                None,
            )
            .expect_err("second start while Ready must fail");
        assert_eq!(busy.code, "busy");

        // --- confirm binding through the production flow, then infer ---
        let binding = confirm_model_binding(&harness, &model_id, &first.runtime_instance_id)
            .expect("binding confirmed through the real command");
        assert_eq!(binding["provider_id"], "managed-llama-cpp");
        // The turn must present the composed fingerprint the user confirmed
        // (exactly what the UI passes), not the attach-level fingerprint.
        let composed_fingerprint = binding["binding_fingerprint"]
            .as_str()
            .expect("composed binding fingerprint")
            .to_owned();
        assert_ne!(composed_fingerprint, first_fingerprint);

        // --- inference through the real gateway (first proof) ---
        let accepted = start_inference_turn(
            &harness,
            &model_id,
            &composed_fingerprint,
            "Reply with exactly one word: ready",
            64,
        )
        .expect("live turn accepted");
        let request_id = accepted["request_id"]
            .as_str()
            .expect("request id")
            .to_owned();
        assert_eq!(accepted["state"], "Accepted");
        let (first_deltas, first_terminal) =
            wait_for_turn_terminal(&harness, &request_id, Duration::from_secs(180));
        assert_eq!(
            first_terminal["method"], "model.turn.completed",
            "turn must complete, terminal: {first_terminal}"
        );
        assert!(
            !first_deltas.trim().is_empty(),
            "inference must produce output text"
        );

        // --- turn with a corrupted binding fingerprint is rejected (P0-3) ---
        let mut corrupted = composed_fingerprint.clone();
        let flip = if corrupted.starts_with('0') { '1' } else { '0' };
        corrupted.replace_range(0..1, &flip.to_string());
        let mismatch =
            start_inference_turn(&harness, &model_id, &corrupted, "should never dispatch", 16)
                .expect_err("corrupted fingerprint must be rejected");
        assert_eq!(mismatch.code, "binding_mismatch");

        // --- stop -> stopped ---
        let stopped = harness
            .runtime
            .stop(&harness.bridge)
            .expect("live managed model stop");
        assert!(stopped.stopped);
        let status_after_stop = harness.runtime.status(&harness.bridge);
        assert_eq!(status_after_stop.state, ManagedRuntimeState::Stopped);
        assert!(status_after_stop.runtime_instance_id.is_none());

        // --- restart creates a fresh runtime instance (P0-2 second half) ---
        let second = harness
            .runtime
            .start(
                &model_id,
                None,
                Some(&runtime_id),
                &harness.bridge,
                None,
                None,
            )
            .expect("live managed model restart reaches Ready");
        assert_eq!(second.state, ManagedRuntimeState::Ready);
        assert_ne!(
            second.runtime_instance_id, first.runtime_instance_id,
            "restart must allocate a fresh runtime instance"
        );

        // --- second inference on the restarted runtime ---
        let second_binding =
            confirm_model_binding(&harness, &model_id, &second.runtime_instance_id)
                .expect("binding re-confirmed after restart");
        let second_composed = second_binding["binding_fingerprint"]
            .as_str()
            .expect("second composed binding fingerprint")
            .to_owned();
        let accepted_two = start_inference_turn(
            &harness,
            &model_id,
            &second_composed,
            "Reply with exactly one word: online",
            64,
        )
        .expect("second live turn accepted");
        let request_two = accepted_two["request_id"]
            .as_str()
            .expect("request id")
            .to_owned();
        let (second_deltas, second_terminal) =
            wait_for_turn_terminal(&harness, &request_two, Duration::from_secs(180));
        assert_eq!(
            second_terminal["method"], "model.turn.completed",
            "second turn must complete, terminal: {second_terminal}"
        );
        assert!(!second_deltas.trim().is_empty());
    }

    #[test]
    fn live_custom_model_requires_exact_approval_then_infers() {
        let Some((project_root, python, model_root, _model_id, _runtime_id)) = live_env() else {
            return;
        };
        let Some(custom_model_id) = env_or_warn("LOCALCOMET_LIVE_CUSTOM_MODEL_ID") else {
            eprintln!(
                "SKIP: live custom model e2e - set LOCALCOMET_LIVE_CUSTOM_MODEL_ID to enable"
            );
            return;
        };
        let _guard = LIVE_E2E_GUARD
            .get_or_init(|| Mutex::new(()))
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let harness = build_harness(&project_root, &python, &model_root);

        let custom = harness
            .artifacts
            .custom_model(&custom_model_id)
            .expect("custom model lookup")
            .expect("custom model is registered in the durable manifest");
        let custom_sha256 = custom.asset_sha256.clone();
        let runtime_id = custom
            .compatible_runtime_ids
            .first()
            .expect("custom model has a compatible runtime")
            .clone();

        // Approval input comes from the same source of truth the command uses.
        let input = harness
            .runtime
            .runtime_start_approval_input(&custom_model_id, Some(&custom_sha256), Some(&runtime_id))
            .expect("custom approval input");
        assert_eq!(
            input,
            json!({
                "model_id": custom_model_id,
                "custom_sha256": custom_sha256,
                "runtime_id": runtime_id,
            }),
            "custom approval input must bind model, digest and runtime"
        );

        // A start with an unknown approval token must be refused by the real
        // command before anything launches (P0-5).
        let forged = tauri::async_runtime::block_on(managed_runtime_start(
            harness._app.state::<Arc<ManagedRuntimeSupervisor>>(),
            harness._app.state::<Arc<ControlPlaneBridge>>(),
            harness
                ._app
                .state::<crate::approval_commands::ApprovalState>(),
            custom_model_id.clone(),
            Some(custom_sha256.clone()),
            Some(runtime_id.clone()),
            format!("lcap_{}", "f".repeat(64)),
            format!("appr_{}", "f".repeat(32)),
            format!("call_{}", "f".repeat(32)),
            None,
            None,
        ))
        .expect_err("forged approval token must be rejected");
        assert_eq!(forged.code, "approval_token_unknown");

        // Legacy listener retained for compatibility with the live harness;
        // production approval issuance now happens in the Rust background path
        // and does not open a user-facing card.
        let dispatcher = harness
            .approval_dispatcher
            .as_ref()
            .expect("frontend approval dispatcher")
            .clone();
        harness
            .app_handle
            .listen_any("request_tool_approval", move |event| {
                if let Ok(payload) = serde_json::from_str::<Value>(event.payload()) {
                    if let Some(request_id) = payload.get("request_id").and_then(Value::as_str) {
                        let _ = dispatcher
                            .resolve(request_id, crate::approval::ApprovalDecision::Approve);
                    }
                }
            });

        let state_ref = harness
            ._app
            .state::<crate::approval_commands::ApprovalState>();
        let envelope = crate::approval_commands::request_approval(
            state_ref,
            harness._app.state::<Arc<ManagedRuntimeSupervisor>>(),
            "runtime.start".to_owned(),
            input.clone(),
        )
        .expect("background approval issued by Rust");

        // Consume the token through the same validator the command uses,
        // then prove single-use: a replay of the exact same approval material
        // is rejected (P0-5).
        crate::approval_commands::validate_approval_token(
            &harness
                ._app
                .state::<crate::approval_commands::ApprovalState>(),
            "runtime.start",
            &input,
            &envelope.token,
            &envelope.approval_id,
            &envelope.call_id,
        )
        .expect("exact approval validates once");
        let replay = crate::approval_commands::validate_approval_token(
            &harness
                ._app
                .state::<crate::approval_commands::ApprovalState>(),
            "runtime.start",
            &input,
            &envelope.token,
            &envelope.approval_id,
            &envelope.call_id,
        )
        .expect_err("approval replay must be rejected");
        assert_eq!(replay.code, "approval_token_consumed");

        // Fresh approval, then the real command start with exact approval.
        let envelope_two = crate::approval_commands::request_approval(
            harness
                ._app
                .state::<crate::approval_commands::ApprovalState>(),
            harness._app.state::<Arc<ManagedRuntimeSupervisor>>(),
            "runtime.start".to_owned(),
            input.clone(),
        )
        .expect("second approval issued");

        let started = tauri::async_runtime::block_on(managed_runtime_start(
            harness._app.state::<Arc<ManagedRuntimeSupervisor>>(),
            harness._app.state::<Arc<ControlPlaneBridge>>(),
            harness
                ._app
                .state::<crate::approval_commands::ApprovalState>(),
            custom_model_id.clone(),
            Some(custom_sha256.clone()),
            Some(runtime_id.clone()),
            envelope_two.token,
            envelope_two.approval_id,
            envelope_two.call_id,
            None,
            None,
        ))
        .expect("custom model start with exact approval reaches Ready");
        assert_eq!(started.state, ManagedRuntimeState::Ready);
        assert_eq!(started.runtime_id, runtime_id);
        assert_eq!(started.model_id, custom_model_id);

        let custom_binding =
            confirm_model_binding(&harness, &custom_model_id, &started.runtime_instance_id)
                .expect("custom binding confirmed through the real command");
        let custom_composed = custom_binding["binding_fingerprint"]
            .as_str()
            .expect("custom composed binding fingerprint")
            .to_owned();
        let accepted = start_inference_turn(
            &harness,
            &custom_model_id,
            &custom_composed,
            "Reply with exactly one word: ready",
            512,
        )
        .expect("custom model live turn accepted");
        let request_id = accepted["request_id"]
            .as_str()
            .expect("request id")
            .to_owned();
        let (deltas, terminal) =
            wait_for_turn_terminal(&harness, &request_id, Duration::from_secs(240));
        assert_eq!(
            terminal["method"], "model.turn.completed",
            "custom turn must complete, terminal: {terminal}"
        );
        assert!(!deltas.trim().is_empty());
    }
}
