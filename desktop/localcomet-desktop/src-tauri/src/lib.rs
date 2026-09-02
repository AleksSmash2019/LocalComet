mod app_data_root;
mod approval;
mod approval_commands;
mod artifact_acquisition;
mod artifact_trust;
mod artifact_validation_cache;
#[allow(dead_code)]
mod checkpoint;
mod checkpoint_commands;
mod coding_commands;
mod coding_orchestrator;
mod comctl_delay_load_guard;
mod control_plane;
mod cu_broker;
mod cu_continuation;
#[allow(dead_code)]
mod diagnostics;
mod files;
mod gguf_metadata;
mod hardware;
mod hf_catalog;
#[allow(dead_code)]
mod intent_compiler;
mod ipc;
mod knowledge;
mod managed_runtime;
mod permission_context;
#[allow(dead_code, unused_imports)]
mod project_intelligence;
mod secure_fs;
mod single_instance;
mod skills;
mod startup;
mod supervisor;
#[allow(dead_code)]
mod task_ledger;
mod terminal_runner;
mod voice;
mod windows_job;
mod workspace;

use approval_commands::{
    cu_broker_continuation_complete, cu_broker_continuation_consume, cu_broker_continuation_revoke,
    cu_broker_observe, execute_approved, request_approval, resolve_tool_approval, run_tool_call,
    set_workspace, ApprovalState,
};
use artifact_acquisition::{
    cancel_artifact_download, get_artifact_download_state, list_approved_downloadable_artifacts,
    remove_managed_model, start_approved_artifact_download, ArtifactAcquisitionManager,
};
use artifact_trust::{
    get_model_storage_info, import_custom_model, managed_artifact_trust_bundle,
    managed_artifact_validation_status, managed_installed_artifacts, managed_model_catalog,
    managed_model_readiness, managed_runtime_catalog, open_model_storage_folder,
    ArtifactTrustService,
};
use checkpoint_commands::{
    checkpoint_compare, checkpoint_list, checkpoint_restore_approval, checkpoint_restore_files,
    checkpoint_restore_task,
};
use coding_commands::{
    coding_cancel, coding_events, coding_list_tasks, coding_recover_task, coding_start,
    coding_start_approval,
};
use control_plane::{
    control_plane_bootstrap, control_plane_cancel_turn, control_plane_close_session,
    control_plane_create_session, control_plane_create_thread, control_plane_get_turn_status,
    control_plane_start_mock_turn, knowledge_review_decision_create, knowledge_review_get,
    knowledge_review_list, knowledge_review_refresh, knowledge_review_snapshot, model_binding_set,
    model_gateway_catalog, model_gateway_list_models, model_gateway_probe, model_turn_cancel,
    model_turn_start, ControlPlaneBridge,
};
use files::{
    files_capability_status, forget_selected_file, list_selected_files, preview_selected_file,
    select_files, SelectedFilesManager,
};
use intent_compiler::intent_compile;
use lsp::lsp_diagnostics;
#[cfg(all(test, debug_assertions))]
mod live_e2e;
mod lsp;
use hardware::scan_hardware;
use hf_catalog::{hf_list_repo_files, hf_search_models};
use knowledge::{knowledge_turn_decide, knowledge_turn_preview};
use managed_runtime::{
    managed_runtime_capability, managed_runtime_logs, managed_runtime_start,
    managed_runtime_start_trusted, managed_runtime_status, managed_runtime_stop,
    managed_runtime_stop_trusted, ManagedRuntimeSupervisor,
};
use skills::{
    skills_compile, skills_disable, skills_enable, skills_install, skills_list, skills_uninstall,
};
use std::sync::Arc;
use std::time::Duration;
use supervisor::{DesktopSidecarSupervisor, LivenessPolicy, SupervisorError};
use tauri::Manager;
use voice::{speak_local_text, stop_local_text};

const BACKEND_READINESS_TIMEOUT: Duration = Duration::from_secs(8);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    startup::record(
        startup::StartupPhase::SingleInstance,
        "begin",
        "LC_START_000",
    );
    let _single_instance: single_instance::SingleInstanceGuard = match single_instance::acquire() {
        Ok(Some(guard)) => {
            startup::record(
                startup::StartupPhase::SingleInstance,
                "success",
                "LC_START_000",
            );
            guard
        }
        Ok(None) => {
            startup::record(
                startup::StartupPhase::SingleInstance,
                "already_running",
                "LC_START_DUPLICATE",
            );
            return;
        }
        Err(_) => {
            startup::report_failure(startup::StartupPhase::SingleInstance, "LC_START_001");
            return;
        }
    };

    let run_result = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            startup::record(startup::StartupPhase::BackendStart, "begin", "LC_START_100");
            let local_data_dir = match app.path().local_data_dir() {
                Ok(path) => path,
                Err(_) => {
                    startup::report_failure_with_reason(
                        startup::StartupPhase::BackendStart,
                        "LC_START_101",
                        "local_data_unavailable",
                    );
                    app.handle().exit(1);
                    return Ok(());
                }
            };
            let application_data_root =
                match app_data_root::resolve_application_data_root(&local_data_dir) {
                    Ok(path) => path,
                    Err(error) => {
                        startup::report_application_data_root_failure(error);
                        app.handle().exit(1);
                        return Ok(());
                    }
                };
            let artifact_trust = match ArtifactTrustService::production(&application_data_root) {
                Ok(service) => Arc::new(service),
                Err(_) => {
                    startup::report_failure_with_reason(
                        startup::StartupPhase::BackendStart,
                        "LC_START_101",
                        "artifact_trust_unavailable",
                    );
                    app.handle().exit(1);
                    return Ok(());
                }
            };
            let supervisor = Arc::new(DesktopSidecarSupervisor::default());
            let bridge = Arc::new(ControlPlaneBridge::new(
                Arc::clone(&supervisor),
                app.handle().clone(),
            ));
            supervisor.set_frame_router(bridge.clone());
            if let Err(error) = supervisor.start_and_wait_ready(BACKEND_READINESS_TIMEOUT) {
                let (phase, code, reason) = match error {
                    SupervisorError::ReadinessTimeout => (
                        startup::StartupPhase::BackendReadiness,
                        "LC_START_102",
                        "sidecar_readiness_timeout",
                    ),
                    SupervisorError::ExitedBeforeReady => (
                        startup::StartupPhase::BackendReadiness,
                        "LC_START_103",
                        "sidecar_exited_before_ready",
                    ),
                    SupervisorError::Unavailable(_) => (
                        startup::StartupPhase::BackendStart,
                        "LC_START_101",
                        "sidecar_unavailable",
                    ),
                    SupervisorError::Io(_) => (
                        startup::StartupPhase::BackendStart,
                        "LC_START_101",
                        "sidecar_io",
                    ),
                };
                let _ = supervisor.shutdown();
                startup::report_failure_with_reason(phase, code, reason);
                app.handle().exit(1);
                return Ok(());
            }
            startup::record(
                startup::StartupPhase::BackendStart,
                "success",
                "LC_START_100",
            );
            startup::record(
                startup::StartupPhase::BackendReadiness,
                "success",
                "LC_START_100",
            );
            bridge.emit_sidecar_status();
            let _ = supervisor.spawn_liveness_monitor(LivenessPolicy::default());
            let snapshot = supervisor.snapshot();
            let _ = (
                snapshot.running,
                snapshot.saw_python_hello,
                snapshot.saw_health_ok,
                snapshot.saw_goodbye,
                snapshot.last_frame,
                snapshot.stderr_tail,
            );
            app.manage(Arc::clone(&supervisor));
            app.manage(bridge);
            app.manage(Arc::clone(&artifact_trust));
            app.manage(Arc::new(ArtifactAcquisitionManager::new(Arc::clone(
                &artifact_trust,
            ))));
            app.manage(Arc::new(ManagedRuntimeSupervisor::new(artifact_trust)));
            app.manage(SelectedFilesManager::default());
            app.manage(ApprovalState::new(app.handle().clone()));
            // F-03: typed permission context (default-deny). Only the exact
            // isolated-hidden sentinel can arm an expiring, desktop-bound
            // IsolatedHiddenTest context; normal sessions never receive one
            // and every dangerous action still consumes its scoped one-time
            // approval token afterwards.
            // Session binding uses the real registry session so B1 validation
            // can verify session/workspace/desktop together after set_workspace
            // re-binds the workspace digest.
            if let Some(state) = app.try_state::<ApprovalState>() {
                // Capability arming MUST happen before the context is issued:
                // set_agent_permissions rotates the approval registry (and its
                // session id), so a context captured earlier would be bound to
                // a dead session and every later dispatch would fail with
                // permission_context_session_mismatch.
                state.set_agent_permissions(control_plane::AgentPermissions {
                    files: true,
                    shell: true,
                    tools: true,
                    computer_use: true,
                    internet: false,
                });
                // Session binding uses the real registry session so B1 validation
                // can verify session/workspace/desktop together after set_workspace
                // re-binds the workspace digest.
                let session = state.session_id();
                // Workspace digest is pending until set_workspace re-binds it;
                // use the sentinel that sync_isolated_workspace_digest will
                // replace with the concrete digest.
                let pending_ws = state
                    .workspace_identity()
                    .map(|(_, digest)| digest)
                    .unwrap_or_else(|| crate::approval::NON_WORKSPACE_APPROVAL_SCOPE.to_string());
                if let Some(context) = startup::isolated_permission_context(
                    &session,
                    &pending_ws,
                    std::env::var("LC_HIDDEN_DESKTOP_NAME").ok().as_deref(),
                ) {
                    state.set_permission_context(context);
                }
            }
            let Some(window) = app.get_webview_window("main") else {
                let _ = supervisor.shutdown();
                startup::report_failure(startup::StartupPhase::WindowDisplay, "LC_START_201");
                app.handle().exit(1);
                return Ok(());
            };
            let invisible = std::env::var("LOCALCOMET_INVISIBLE").ok().as_deref() == Some("1");
            let window_result = if invisible {
                window.hide()
            } else {
                window.show()
            };
            if window_result.is_err() {
                let _ = supervisor.shutdown();
                startup::report_failure(startup::StartupPhase::WindowDisplay, "LC_START_201");
                app.handle().exit(1);
                return Ok(());
            }
            startup::record(
                startup::StartupPhase::WindowDisplay,
                "success",
                "LC_START_200",
            );
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                if let (Some(runtime), Some(bridge)) = (
                    window.try_state::<Arc<ManagedRuntimeSupervisor>>(),
                    window.try_state::<Arc<ControlPlaneBridge>>(),
                ) {
                    let _ = runtime.stop(&bridge);
                }
                if let Some(supervisor) = window.try_state::<Arc<DesktopSidecarSupervisor>>() {
                    let _ = supervisor.shutdown();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            control_plane_bootstrap,
            control_plane_create_session,
            control_plane_close_session,
            control_plane_create_thread,
            control_plane_start_mock_turn,
            control_plane_get_turn_status,
            control_plane_cancel_turn,
            model_gateway_catalog,
            model_gateway_probe,
            model_gateway_list_models,
            model_binding_set,
            model_turn_start,
            model_turn_cancel,
            knowledge_turn_preview,
            knowledge_turn_decide,
            knowledge_review_list,
            knowledge_review_get,
            knowledge_review_snapshot,
            knowledge_review_refresh,
            knowledge_review_decision_create,
            managed_runtime_status,
            managed_runtime_capability,
            managed_runtime_catalog,
            managed_model_catalog,
            managed_installed_artifacts,
            managed_artifact_trust_bundle,
            get_model_storage_info,
            open_model_storage_folder,
            import_custom_model,
            managed_artifact_validation_status,
            managed_model_readiness,
            list_approved_downloadable_artifacts,
            start_approved_artifact_download,
            get_artifact_download_state,
            cancel_artifact_download,
            remove_managed_model,
            managed_runtime_start,
            managed_runtime_start_trusted,
            managed_runtime_stop,
            managed_runtime_stop_trusted,
            managed_runtime_logs,
            files_capability_status,
            select_files,
            list_selected_files,
            preview_selected_file,
            forget_selected_file,
            request_approval,
            execute_approved,
            resolve_tool_approval,
            run_tool_call,
            cu_broker_observe,
            cu_broker_continuation_consume,
            cu_broker_continuation_complete,
            cu_broker_continuation_revoke,
            speak_local_text,
            stop_local_text,
            scan_hardware,
            hf_search_models,
            hf_list_repo_files,
            set_workspace,
            skills_list,
            skills_compile,
            skills_install,
            skills_enable,
            skills_disable,
            skills_uninstall,
            intent_compile,
            checkpoint_list,
            checkpoint_compare,
            checkpoint_restore_approval,
            checkpoint_restore_files,
            checkpoint_restore_task,
            lsp_diagnostics,
            coding_start_approval,
            coding_start,
            coding_events,
            coding_list_tasks,
            coding_recover_task,
            coding_cancel
        ])
        .run(tauri::generate_context!());

    if run_result.is_err() {
        startup::report_failure(startup::StartupPhase::WindowDisplay, "LC_START_202");
    }
}
